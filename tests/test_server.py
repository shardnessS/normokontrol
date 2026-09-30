import json

import pytest
from mcp import Client

from normokontrol_mcp import __version__
from normokontrol_mcp.server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_tools_are_listed() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()
    assert {"ping", "list_presets", "get_rules"} <= {tool.name for tool in result.tools}


@pytest.mark.anyio
async def test_ping_returns_version() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("ping", {})
    assert not result.is_error
    text = result.content[0].text  # type: ignore[union-attr]
    assert __version__ in text
    assert "сервер работает" in text


@pytest.mark.anyio
async def test_list_presets_tool() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("list_presets", {"country": "RU"})
    assert not result.is_error
    assert result.structured_content is not None
    ids = [item["id"] for item in result.structured_content["result"]]
    assert "gost-7.32-2017" in ids


@pytest.mark.anyio
async def test_get_rules_tool() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_rules", {"preset_id": "gost-7.32-2017"})
    assert not result.is_error
    assert "Поля" in result.content[0].text  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_get_rules_unknown_preset_is_structured_error() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_rules", {"preset_id": "nope"})
    assert result.is_error
    text = result.content[0].text  # type: ignore[union-attr]
    # SDK добавляет префикс «Error executing tool <name>: », дальше — наш JSON.
    assert text.startswith("Error executing tool get_rules: ")
    error = json.loads(text.split(": ", 1)[1])
    assert error["error_code"] == "preset_not_found"
    assert "не найден" in error["message_ru"]


@pytest.mark.anyio
async def test_preset_resource() -> None:
    async with Client(mcp) as client:
        templates = await client.list_resource_templates()
        result = await client.read_resource("normokontrol://presets/gost-7.32-2017")
    assert any(t.uri_template == "normokontrol://presets/{preset_id}" for t in templates.resource_templates)
    text = result.contents[0].text  # type: ignore[union-attr]
    assert "id: gost-7.32-2017" in text
    assert "left: 30" in text
