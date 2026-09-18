import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import memory_store


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"

        patches = [
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
        self.assertFalse(path.exists())
        self.assertEqual(memory_store.get_memory(key)["첨부파일"], [])

    def test_validation_rejects_unknown_category(self):
        with self.assertRaisesRegex(ValueError, "등록되지 않은"):
            memory_store.create_memory({
                **self.sample(),
                "상위태그": "없는태그"
            })


if __name__ == "__main__":
    unittest.main()
