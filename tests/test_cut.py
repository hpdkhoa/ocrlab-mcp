import asyncio

from ocrlab.server import mcp


def test_eight_tools_became_three():
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert sorted(tools) == ["ocr_find", "ocr_line", "ocr_read"]
    actions = [a for t in tools.values() for a in t.input_schema["properties"]["action"]["enum"]]
    assert sorted(actions) == sorted(["pdf_info", "read_page", "read_pages", "find", "words_in", "read_image", "line_fit", "line_follow"])
