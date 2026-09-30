import pytest
from mcp import Client

from normokontrol_mcp import __version__
from normokontrol_mcp.server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_ping_is_listed() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()
    assert "ping" in {tool.name for tool in result.tools}


@pytest.mark.anyio
async def test_ping_returns_version() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("ping", {})
    assert not result.is_error
    text = result.content[0].text  # type: ignore[union-attr]
    assert __version__ in text
    assert "сервер работает" in text
