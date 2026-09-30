"""MCP server entry point: registers tools, resources and prompts."""

from mcp.server.mcpserver import MCPServer

from normokontrol_mcp import __version__

mcp = MCPServer(
    name="normokontrol-mcp",
    version=__version__,
    instructions=(
        "Formats and checks Russian academic works (coursework, theses, reports) "
        "according to GOST 7.32-2017 and GOST R 7.0.100-2018. "
        "The server only formats and validates; it never writes the content of the work."
    ),
)


@mcp.tool()
def ping() -> str:
    """Health check. Returns the server name and version to confirm the server is reachable."""
    return f"normokontrol-mcp {__version__}: сервер работает"


def main() -> None:
    """Run the server over stdio."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
