import asyncio
import base64
from io import BytesIO
from PIL import Image
import json
import os
import tempfile
import threading
import time
import unittest

from pathlib import Path
from unittest.mock import patch

from fastapi.openapi.utils import get_openapi

import gpt_api
import gpt_mcp


class GPTAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"
        self.gpt_dir = self.data_dir / "gpt"
        self.image_dir = self.data_dir / "images"

        patches = [
            patch.object(gpt_api, "GPT_DIR", self.gpt_dir),
            patch.object(gpt_api, "IMAGE_DIR", self.image_dir),
        ]
        for current_patch in patches:
            current_patch.start()
            self.addCleanup(current_patch.stop)

        gpt_api._ensure_directories()
        with gpt_api._CAMERA_LOCK:
            gpt_api._CAMERA_REQUESTS.clear()
        self.addCleanup(self.clear_camera_requests)

    def clear_camera_requests(self):
        with gpt_api._CAMERA_LOCK:
            gpt_api._CAMERA_REQUESTS.clear()

    def write_project(self, project_id=123, **changes):
        data = {
            "상위태그": "글카",
            "제목": "MSI GTX 960 전원부 점검",
            "생성일시": "2026-09-17T10:00:00+09:00",
            "수정일시": "2026-09-18T12:00:00+09:00",
            "우선도": 4,
            "상태": "진행중",
            "작업내용": [{
                "작업날짜": "2026-09-17",
                "요약": "12V 입력 저항 측정",
                "세부": "12V_F와 GND 사이 43Ω 측정",
                "결과": "추가 점검 필요",
            }],
            "최종결론": "",
        }
        data.update(changes)
        (self.gpt_dir / f"{project_id}.json").write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
        return data

    def read_project(self, project_id=123):
        return json.loads((self.gpt_dir / f"{project_id}.json").read_text(encoding="utf-8"))

    def test_search_uses_only_requested_filters_and_returns_ids(self):
        self.write_project(123)
        self.write_project(
            456,
            상위태그="배송",
            제목="파워 배송 문의",
            상태="완료",
            수정일시="2026-09-10T12:00:00+09:00",
        )
        (self.gpt_dir / "broken.json").write_text("not-json", encoding="utf-8")

        result = gpt_api.search_projects_data(category="글카", title="gtx", status="진행중")

        self.assertEqual(
            result,
            {"검색결과": [{"아이디": 123, "제목": "MSI GTX 960 전원부 점검"}]},
        )

    def test_get_project_defaults_to_compact_view(self):
        self.write_project()

        compact = gpt_api.get_project_data(123)
        detailed = gpt_api.get_project_data(123, detail=True)

        self.assertEqual(
            compact,
            {
                "아이디": 123,
                "제목": "MSI GTX 960 전원부 점검",
                "작업내용": {"2026-09-17": "12V 입력 저항 측정"},
            },
        )
        self.assertEqual(detailed["아이디"], 123)
        self.assertEqual(detailed["작업내용"][0]["세부"], "12V_F와 GND 사이 43Ω 측정")
        self.assertIn("우선도", detailed)

    def test_same_day_work_requires_explicit_merged_overwrite(self):
        self.write_project(작업내용=[])

        with (
            patch.object(gpt_api, "_today", return_value="2026-09-18"),
            patch.object(gpt_api, "_now", return_value="2026-09-18T15:00:00+09:00"),
        ):
            first = gpt_api.add_work_data(
                123,
                "NVVDD 0.918V 측정. [[이미지:7]]",
            )
            before_second = self.read_project()

            second = gpt_api.add_work_data(
                123,
                "R728 탈거 후 1.05kΩ 측정",
            )
            after_second = self.read_project()

            final_content = (
                "NVVDD 0.918V 측정. [[이미지:7]]\n"
                "R728 탈거 후 1.05kΩ 측정"
            )
            third = gpt_api.add_work_data(
                123,
                final_content,
                overwrite=True,
            )

        self.assertTrue(first["저장됨"])
        self.assertFalse(second["저장됨"])
        self.assertTrue(second["병합필요"])
        self.assertEqual(second["기존기록"]["세부"], "NVVDD 0.918V 측정. [[이미지:7]]")
        self.assertEqual(second["새기록"]["세부"], "R728 탈거 후 1.05kΩ 측정")
        self.assertEqual(before_second, after_second, "병합 전 첫 재호출은 파일을 바꾸면 안 됩니다.")

        stored = self.read_project()["작업내용"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["세부"], final_content)
        self.assertNotIn("결과", stored[0])
        self.assertEqual(third["처리"], "overwritten")

    def test_work_payload_accepts_existing_korean_names(self):
        payload = gpt_api.WorkPayload.model_validate({
            "내용": "상세 기록",
            "덮어쓰기": True,
            "요약": "짧은 요약",
        })
        self.assertEqual(payload.content, "상세 기록")
        self.assertTrue(payload.overwrite)
        self.assertNotIn("result", payload.model_dump())

    def test_update_project_only_changes_supplied_fields(self):
        self.write_project()

        with patch.object(gpt_api, "_now", return_value="2026-09-18T16:00:00+09:00"):
            result = gpt_api.update_project_data(123, {
                "제목": "GTX 960 수리 완료",
                "상태": "완료",
                "최종결론": "PK616BA 교체 후 정상",
            })

        stored = self.read_project()
        self.assertTrue(result["수정됨"])
        self.assertEqual(stored["제목"], "GTX 960 수리 완료")
        self.assertEqual(stored["상태"], "완료")
        self.assertEqual(stored["우선도"], 4)
        self.assertEqual(stored["최종결론"], "PK616BA 교체 후 정상")

    def test_latest_image_tracks_only_successful_tool_calls(self):
        import image_points
        db = self.image_dir.parent / "inventory.sqlite3"
        self.assertIsNone(image_points.latest_tool_image(db)["image_id"])
        for image_id in (91, 92):
            Image.new("RGB", (20, 20), "red").save(self.image_dir / f"{image_id}.png")
        gpt_api.get_image(91)
        first = image_points.latest_tool_image(db)
        self.assertEqual(first["image_id"], 91)
        # Admin image rendering must not update the GPT pointer.
        gpt_api._image_response(92, self.image_dir / "92.png")
        self.assertEqual(image_points.latest_tool_image(db), first)
        asyncio.run(gpt_mcp.inventory_mcp.call_tool("get_image", {"image_id": 92}))
        self.assertEqual(image_points.latest_tool_image(db)["image_id"], 92)
        with patch.object(gpt_api, "take_photo_data", return_value=(91, self.image_dir / "91.png")):
            asyncio.run(gpt_mcp.inventory_mcp.call_tool("take_photo", {}))
        self.assertEqual(image_points.latest_tool_image(db)["image_id"], 91)
        with patch.object(gpt_api, "take_photo_data", return_value=(92, self.image_dir / "92.png")):
            gpt_api.take_photo()
        last = image_points.latest_tool_image(db)
        self.assertEqual(last["image_id"], 92)
        with self.assertRaises(gpt_mcp.ToolError):
            asyncio.run(gpt_mcp.inventory_mcp.call_tool("get_image", {"image_id": 999}))
        self.assertEqual(image_points.latest_tool_image(db), last)
        gpt_api.get_image(92)
        self.assertGreater(image_points.latest_tool_image(db)["revision"], last["revision"])

    def test_get_image_response_contains_image_blocks_and_id(self):
        path = self.image_dir / "41.jpg"
        Image.new("RGB", (2400, 1200), "red").save(path)
        original = path.read_bytes()
        response = gpt_api.get_image(41)
        self.assertEqual(response["image_id"], 41)
        self.assertEqual(response["content"], "image_id: 41")
        block = response["content_items"][1]
        self.assertEqual(block["type"], "image")
        self.assertEqual(block["mimeType"], "image/jpeg")
        decoded = base64.b64decode(block["data"], validate=True)
        with Image.open(BytesIO(decoded)) as picture:
            self.assertEqual(picture.size, (1600, 800))
            self.assertEqual(picture.format, "JPEG")
        self.assertEqual(path.read_bytes(), original)

    def test_png_content_detected_from_bytes_and_camera_matches_get_image(self):
        path = self.image_dir / "42.jpg"
        Image.new("RGBA", (16, 12), (1, 2, 3, 100)).save(path, format="PNG")
        with patch.object(gpt_api, "take_photo_data", return_value=(42, path)):
            response = gpt_api.take_photo()
            result = asyncio.run(gpt_mcp.inventory_mcp.call_tool("take_photo", {}))
        self.assertEqual(response, gpt_api.get_image(42))
        block = response["content_items"][1]
        self.assertEqual(block["mimeType"], "image/png")
        self.assertEqual(result.content[1].type, "image")
        self.assertEqual(result.content[1].data, block["data"])
        self.assertEqual(result.model_dump_json(by_alias=True).count(block["data"]), 1)
        self.assertIsNone(result.meta)
        with Image.open(BytesIO(base64.b64decode(block["data"], validate=True))) as picture:
            self.assertEqual(picture.format, "PNG")
            self.assertEqual(picture.mode, "RGBA")

    def test_invalid_image_is_reported_as_tool_error(self):
        (self.image_dir / "43.jpg").write_bytes(b"invalid")
        with self.assertRaises(gpt_mcp.ToolError):
            asyncio.run(gpt_mcp.inventory_mcp.call_tool("get_image", {"image_id": 43}))

    def test_take_photo_relays_to_laptop_agent_and_saves_next_image_id(self):
        (self.image_dir / "8.png").write_bytes(b"old")

        def laptop_agent():
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                pending = gpt_api.claim_camera_request()
                if pending:
                    gpt_api.complete_camera_request(
                        pending["request_id"],
                        b"new-jpeg",
                        ".jpg",
                    )
                    return
                time.sleep(0.01)

        worker = threading.Thread(target=laptop_agent, daemon=True)
        with patch.dict(
            os.environ,
            {"CAMERA_AGENT_TOKEN": "test-token", "CAMERA_REQUEST_TIMEOUT": "5"},
        ):
            worker.start()
            image_id, path = gpt_api.take_photo_data()
            worker.join(timeout=2)

        self.assertEqual(image_id, 9)
        self.assertEqual(path.read_bytes(), b"new-jpeg")
        self.assertFalse(worker.is_alive())

    def test_scoped_openapi_contains_exactly_eight_tools(self):
        routes = [
            route
            for route in gpt_api.router.routes
            if getattr(route, "operation_id", None) in gpt_api.TOOL_NAMES
        ]
        schema = get_openapi(title="test", version="1", routes=routes)
        operation_ids = {
            operation["operationId"]
            for path in schema["paths"].values()
            for operation in path.values()
        }

        self.assertEqual(operation_ids, gpt_api.TOOL_NAMES)
        self.assertNotIn("/gpt/", schema["paths"])
        self.assertNotIn("/gpt/latest-image", schema["paths"])

    def test_mcp_exposes_exactly_eight_tools_and_image_with_id(self):
        Image.new("RGB", (24, 16), "blue").save(self.image_dir / "55.webp")

        tools = asyncio.run(gpt_mcp.inventory_mcp.list_tools())
        names = {tool.name for tool in tools}
        result = asyncio.run(gpt_mcp.inventory_mcp.call_tool(
            "get_image",
            {"image_id": 55},
        ))

        self.assertEqual(names, gpt_api.TOOL_NAMES)
        self.assertEqual(result.content[0].type, "text")
        self.assertIn("55", result.content[0].text)
        self.assertEqual(result.content[1].type, "image")
        self.assertEqual(result.content[1].mime_type, "image/jpeg")
        self.assertTrue(result.content[1].data)
        self.assertEqual(result.structured_content, {"image_id": 55, "mime_type": "image/jpeg", "points": []})
        self.assertIsNone(result.meta)
        self.assertEqual(sum(block.type == "image" for block in result.content), 1)
        serialized = result.model_dump_json(by_alias=True)
        self.assertEqual(serialized.count(result.content[1].data), 1)
        image_tools = [tool for tool in tools if tool.name in {"get_image", "take_photo"}]
        for tool in image_tools:
            self.assertFalse((tool.meta or {}).get("openai/outputTemplate"))
        widget = asyncio.run(gpt_mcp.inventory_mcp.read_resource(gpt_mcp.IMAGE_WIDGET_URI))
        self.assertNotIn("uploadFile", widget[0].content)
        self.assertNotIn("sendFollowUpMessage", widget[0].content)

    def test_points_persist_update_independently_and_preserve_original(self):
        from concurrent.futures import ThreadPoolExecutor
        for image_id in (71, 72):
            Image.new("RGB", (20, 20), "red").save(self.image_dir / f"{image_id}.jpg")
        path = self.image_dir / "71.jpg"
        original = path.read_bytes()
        self.assertEqual(gpt_api.get_image(71)["points"], [])
        first = gpt_api.add_point_data(71, 0, 1, "corner")
        self.assertEqual(first, dict(image_id=71, point_id=1, x=0, y=1, annotation="corner"))
        self.assertEqual(gpt_api.add_point_data(72, 1, 0, "other")["point_id"], 1)
        moved = gpt_api.update_point_data(71, 1, x=0.5, y=0.25)
        self.assertEqual(moved["annotation"], "corner")
        renamed = gpt_api.update_point_data(71, 1, annotation="")
        self.assertEqual((renamed["x"], renamed["y"], renamed["annotation"]), (0.5, 0.25, ""))
        with ThreadPoolExecutor(max_workers=6) as pool:
            ids = list(pool.map(lambda _: gpt_api.add_point_data(71, .2, .3, "parallel")["point_id"], range(12)))
        self.assertEqual(sorted(ids), list(range(2, 14)))
        result = asyncio.run(gpt_mcp.inventory_mcp.call_tool("get_image", {"image_id": 71}))
        self.assertEqual(result.structured_content["points"], gpt_api.get_image(71)["points"])
        self.assertEqual(len(result.structured_content["points"]), 13)
        self.assertEqual(path.read_bytes(), original)

    def test_point_errors_and_http_mcp_tools(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        Image.new("RGB", (20, 20), "blue").save(self.image_dir / "81.png")
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(gpt_api.GPTAPIError):
                gpt_api.add_point_data(81, value, 0, "bad")
        with self.assertRaises(gpt_api.GPTAPIError):
            gpt_api.add_point_data(999, 0, 0, "missing")
        app = FastAPI()
        app.include_router(gpt_api.router)
        with TestClient(app) as client:
            result = client.post("/gpt/image/81/points", json={"x": 0, "y": 1, "annotation": "test"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(client.patch("/gpt/image/81/points/1", json={"annotation": "new"}).json()["x"], 0)
            self.assertEqual(client.patch("/gpt/image/81/points/1", json={}).status_code, 422)
            self.assertEqual(client.patch("/gpt/image/81/points/999", json={"x": 0}).status_code, 404)
            self.assertEqual(client.post("/gpt/image/81/points", json={"x": 2, "y": 0, "annotation": "bad"}).status_code, 422)
        added = asyncio.run(gpt_mcp.inventory_mcp.call_tool("add_point", {"image_id": 81, "x": .5, "y": .5, "annotation": "mcp"}))
        self.assertIn('mcp', added.content[0].text)
        updated = asyncio.run(gpt_mcp.inventory_mcp.call_tool("update_point", {"image_id": 81, "point_id": 2, "annotation": "updated"}))
        self.assertIn('updated', updated.content[0].text)



if __name__ == "__main__":
    unittest.main()
