import asyncio
import unittest

import gpt_api
import gpt_mcp
import memory_store


class NoWorkResultTests(unittest.TestCase):
    def test_result_is_not_an_api_or_plugin_input(self):
        self.assertNotIn('result', gpt_api.WorkPayload.model_json_schema()['properties'])
        tools = asyncio.run(gpt_mcp.inventory_mcp.list_tools())
        tool = next(tool for tool in tools if tool.name == 'add_work')
        self.assertNotIn('result', tool.input_schema['properties'])

    def test_local_save_discards_legacy_result_but_keeps_work(self):
        normalized = memory_store.normalize_work_items([{
            '작업날짜': '2026-09-19', '요약': '요약', '세부': '상세', '결과': '삭제 대상'
        }])
        self.assertEqual(normalized, [{'작업날짜': '2026-09-19', '요약': '요약', '세부': '상세'}])
