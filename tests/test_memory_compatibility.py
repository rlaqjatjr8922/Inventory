import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gpt_api
import memory_store


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        for module, attribute, value in [
            (memory_store, 'DATA_DIR', self.data),
            (memory_store, 'MEMORIES_FILE', self.data / 'memories.json'),
            (memory_store, 'CATEGORIES_FILE', self.data / 'memory_categories.json'),
            (memory_store, 'MEMORY_UPLOAD_DIR', self.data / 'memory_uploads'),
            (gpt_api, 'GPT_DIR', self.data / 'gpt'),
            (gpt_api, 'IMAGE_DIR', self.data / 'images'),
        ]:
            current = patch.object(module, attribute, value)
            current.start()
            self.addCleanup(current.stop)
        memory_store.initialize()

    def sample(self, **changes):
        return {'제목': '호환성 점검', '상위태그': '글카', '상태': '진행중',
                '우선도': 2, '최종결론': '', '작업내용': [], **changes}

    def test_site_create_plugin_read_and_plugin_work_site_read(self):
        item = memory_store.create_memory(self.sample())
        pid = int(item['메모키'])
        self.assertEqual(gpt_api.search_projects_data()['검색결과'][0]['아이디'], pid)
        gpt_api.add_work_data(pid, '플러그인 작업 내용')
        site = memory_store.get_memory(str(pid))
        self.assertEqual(site['작업내용'][0]['세부'], '플러그인 작업 내용')
        memory_store.update_memory(str(pid), {**site, '제목': '사이트 수정'})
        self.assertEqual(gpt_api.get_project_data(pid, True)['제목'], '사이트 수정')

    def test_plugin_category_is_available_in_site_editor(self):
        gpt_api._save(9, self.sample(상위태그='플러그인태그', extra='preserve'))
        self.assertIn('플러그인태그', memory_store.load_categories())
        item = memory_store.get_memory('9')
        memory_store.update_memory('9', {**item, '최종결론': '완료'})
        self.assertEqual(gpt_api._load(9)['extra'], 'preserve')

    def test_site_stale_edit_cannot_erase_new_plugin_work(self):
        item = memory_store.create_memory(self.sample())
        gpt_api.add_work_data(int(item['메모키']), '새 기록')
        with self.assertRaisesRegex(ValueError, '변경되었습니다'):
            memory_store.update_memory(item['메모키'], {**item, '제목': '옛 화면'})
        self.assertEqual(gpt_api._load(int(item['메모키']))['작업내용'][0]['세부'], '새 기록')

    def test_site_and_plugin_images_use_global_ids(self):
        first, path = gpt_api._save_image_bytes(b'plugin-image', '.jpg')
        item = memory_store.create_memory(self.sample())
        attachment = memory_store.add_attachment(item['메모키'], b'site-image',
                                                'image/jpeg', '.jpg', 'test.jpg', '')
        self.assertNotEqual(first, attachment['아이디'])
        self.assertEqual(gpt_api.get_image_path(attachment['아이디']).read_bytes(), b'site-image')
        gpt_api.add_work_data(int(item['메모키']), f'[[이미지:{first}]]')
        self.assertEqual(memory_store.get_attachment_path(item['메모키'], first)[0], path)
        visible = memory_store.get_memory(item['메모키'])['첨부파일']
        self.assertTrue(next(a for a in visible if a['아이디'] == first)['참조전용'])
        memory_store.delete_memory(item['메모키'])
        self.assertTrue(path.exists())
        with self.assertRaises(gpt_api.GPTAPIError):
            gpt_api.get_project_data(int(item['메모키']))

    def test_migration_preserves_original_and_remaps_colliding_images(self):
        gpt_api._save(1, self.sample(제목='기존 플러그인'))
        gpt_api._save_image_bytes(b'existing-image', '.jpg')
        upload = self.data / 'memory_uploads' / 'old-key' / '1.jpg'
        upload.parent.mkdir(parents=True)
        upload.write_bytes(b'legacy-image')
        legacy = {'old-key': self.sample(최종결론='[[이미지:1]]', 첨부파일=[{
            '아이디': 1, '파일경로': 'memory_uploads/old-key/1.jpg', '콘텐츠형식': 'image/jpeg',
        }], 작업내용=[{'작업날짜': '2026-09-18', '세부': '측정 [[이미지:1]]', '요약': '', '결과': ''}])}
        memory_store.save_json(memory_store.MEMORIES_FILE, legacy)
        original = memory_store.MEMORIES_FILE.read_bytes()
        memory_store.initialize()
        migrated = memory_store.get_memory('old-key')
        new_id = migrated['첨부파일'][0]['아이디']
        self.assertNotEqual(new_id, 1)
        self.assertEqual(migrated['최종결론'], f'[[이미지:{new_id}]]')
        self.assertIn(f'[[이미지:{new_id}]]', migrated['작업내용'][0]['세부'])
        self.assertEqual(gpt_api.get_image_path(1).read_bytes(), b'existing-image')
        self.assertEqual(gpt_api.get_image_path(new_id).read_bytes(), b'legacy-image')
        self.assertEqual(memory_store.MEMORIES_FILE.read_bytes(), original)
        self.assertTrue(upload.exists())
        memory_store.initialize()
        self.assertEqual(len(memory_store.load_memories()), 2)
        memory_store.delete_memory('old-key')
        memory_store.initialize()
        self.assertEqual(len(memory_store.load_memories()), 1)
        created = memory_store.create_memory(self.sample())
        self.assertNotEqual(created['메모키'], migrated['메모키'])

    def test_malformed_legacy_store_is_not_ignored(self):
        memory_store.MEMORIES_FILE.write_text('{broken', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            memory_store.initialize()


if __name__ == '__main__':
    unittest.main()
