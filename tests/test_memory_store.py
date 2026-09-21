import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import memory_store
import gpt_api


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"

        patches = [
            patch.object(gpt_api, "GPT_DIR", self.data_dir / "gpt"),
            patch.object(gpt_api, "IMAGE_DIR", self.data_dir / "images"),
            patch.object(memory_store, "DATA_DIR", self.data_dir),
            patch.object(memory_store, "MEMORIES_FILE", self.data_dir / "memories.json"),
            patch.object(memory_store, "CATEGORIES_FILE", self.data_dir / "memory_categories.json"),
            patch.object(memory_store, "MEMORY_UPLOAD_DIR", self.data_dir / "memory_uploads")
        ]

        for current_patch in patches:
            current_patch.start()
            self.addCleanup(current_patch.stop)

        memory_store.initialize()

    def sample(self):
        return {
            "상위태그": "글카",
            "제목": "GTX960 전원부 점검",
            "우선도": 4,
            "상태": "진행중",
            "작업내용": [{
                "작업날짜": "2026-09-18",
                "요약": "C2342 이상 의심",
                "세부": "전압 측정 후 부품 교체",
                "결과": "출력 확인"
            }],
            "최종결론": "테스트 진행 중"
        }

    def test_basic_save_cannot_replace_work_and_work_save_preserves_basic(self):
        item = memory_store.create_memory(self.sample())
        key = item["메모키"]
        saved = memory_store.update_memory_fields(key, {
            "버전": item["버전"], "제목": "new title", "최종결론": "new conclusion",
            "작업내용": [], "첨부파일": []})
        self.assertEqual(saved["작업내용"], item["작업내용"])
        changed = memory_store.change_work(key, 0, {
            "버전": saved["버전"], "작업날짜": "2026-09-21", "요약": "changed",
            "세부": "before {12:[1,2,999]} after", "제목": "must not save"})
        self.assertEqual(changed["제목"], "new title")
        self.assertEqual(changed["최종결론"], "new conclusion")
        self.assertEqual(changed["작업내용"][0]["요약"], "changed")
        deleted = memory_store.change_work(key, 0, {"버전": changed["버전"]}, delete=True)
        self.assertEqual(deleted["작업내용"], [])
        self.assertEqual(deleted["제목"], "new title")

    def test_stale_work_index_cannot_modify_different_work(self):
        data = self.sample()
        data["작업내용"].append({"작업날짜": "2026-09-21", "요약": "second", "세부": "second"})
        item = memory_store.create_memory(data)
        key = item["메모키"]
        current = memory_store.change_work(key, 0, {"버전": item["버전"]}, delete=True)
        with self.assertRaisesRegex(ValueError, "변경되었습니다"):
            memory_store.change_work(key, 0, {"버전": item["버전"]}, delete=True)
        self.assertEqual(memory_store.get_memory(key)["작업내용"], current["작업내용"])
        with self.assertRaises(ValueError):
            memory_store.change_work(key, -1, {"버전": current["버전"]}, delete=True)

    def test_point_reference_image_endpoint_preserves_original(self):
        from PIL import Image
        import app
        path = gpt_api.IMAGE_DIR / "12.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 40), "red").save(path)
        original = path.read_bytes()
        gpt_api.add_point_data(12, .25, .75, "IC")
        result = app.get_memory_image(12)
        self.assertEqual(result["points"][0]["annotation"], "IC")
        self.assertEqual(len([b for b in result["content_items"] if b["type"] == "image"]), 1)
        self.assertEqual(path.read_bytes(), original)

    def test_create_uses_key_outside_stored_memory(self):
        created = memory_store.create_memory(self.sample())
        stored = memory_store.load_memories()
        key = created["메모키"]

        self.assertIn(key, stored)
        self.assertNotIn("메모키", stored[key])
        self.assertNotIn("아이디", stored[key])
        self.assertEqual(stored[key]["상위태그"], "글카")

    def test_searches_all_words_in_work_content(self):
        memory_store.create_memory(self.sample())
        memory_store.create_memory({
            **self.sample(),
            "상위태그": "배송",
            "제목": "택배 문의",
            "우선도": 2
        })

        results = memory_store.search_memories("GTX960 C2342")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["제목"], "GTX960 전원부 점검")
        self.assertEqual(memory_store.search_memories(category="배송")[0]["제목"], "택배 문의")
        self.assertEqual(len(memory_store.search_memories(minimum_priority=4)), 1)

    def test_empty_default_work_row_is_not_saved(self):
        data = self.sample()
        data["작업내용"] = [{
            "작업날짜": "2026-09-18",
            "요약": "",
            "세부": "",
            "결과": ""
        }]
        created = memory_store.create_memory(data)
        self.assertEqual(created["작업내용"], [])

    def test_category_can_be_added_and_used(self):
        categories = memory_store.add_category("개발")
        self.assertIn("개발", categories)

        created = memory_store.create_memory({
            **self.sample(),
            "상위태그": "개발"
        })
        self.assertEqual(created["상위태그"], "개발")

    def test_image_attachment_and_delete(self):
        created = memory_store.create_memory(self.sample())
        key = created["메모키"]
        attachment = memory_store.add_attachment(
            key,
            b"image-data",
            "image/jpeg",
            ".jpg",
            "측정.jpg",
            "C2342 주변"
        )

        path, stored_attachment = memory_store.get_attachment_path(
            key,
            attachment["아이디"]
        )
        self.assertEqual(path.read_bytes(), b"image-data")
        self.assertEqual(stored_attachment["설명"], "C2342 주변")

        memory_store.delete_attachment(key, attachment["아이디"])
        self.assertTrue(path.exists())  # Shared plugin images must remain available.
        self.assertEqual(memory_store.get_memory(key)["첨부파일"], [])

    def test_validation_rejects_unknown_category(self):
        with self.assertRaisesRegex(ValueError, "등록되지 않은"):
            memory_store.create_memory({
                **self.sample(),
                "상위태그": "없는태그"
            })


if __name__ == "__main__":
    unittest.main()
