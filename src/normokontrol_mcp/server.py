"""MCP server entry point: registers tools, resources and prompts."""

import json
from collections.abc import Callable
from functools import wraps
from typing import Literal, ParamSpec, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from pydantic import BaseModel

from normokontrol_mcp import __version__
from normokontrol_mcp.bibliography import formatter
from normokontrol_mcp.bibliography.models import Source
from normokontrol_mcp.errors import NormokontrolError
from normokontrol_mcp.presets import loader
from normokontrol_mcp.presets.describe import describe_preset

mcp = MCPServer(
    name="normokontrol-mcp",
    version=__version__,
    instructions=(
        "Formats and checks Russian academic works (coursework, theses, reports) "
        "according to GOST 7.32-2017 and GOST R 7.0.100-2018. "
        "The server only formats and validates; it never writes the content of the work."
    ),
)

P = ParamSpec("P")
R = TypeVar("R")


def _structured_errors(error_cls: type[Exception]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Turn NormokontrolError into an MCP error whose text is `{error_code, message_ru, location}` JSON."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except NormokontrolError as exc:
                raise error_cls(json.dumps(exc.to_dict(), ensure_ascii=False)) from exc

        return wrapper

    return decorator


@mcp.tool()
def ping() -> str:
    """Health check. Returns the server name and version to confirm the server is reachable."""
    return f"normokontrol-mcp {__version__}: сервер работает"


@mcp.tool()
@_structured_errors(ToolError)
def list_presets(country: str | None = None) -> list[loader.PresetSummary]:
    """List available formatting presets (GOST base and university-specific).

    Each item has `id` (pass it to other tools), a Russian `name`, `country`, `extends` (parent preset)
    and `verified`: false means the rules were not yet checked against the current university guidelines.
    Presets from the user's NORMOKONTROL_PRESETS_DIR folder have `builtin: false`; a broken preset
    file is still listed with an `error` message. Optionally filter by ISO country code, e.g. "RU".
    """
    return loader.list_presets(country)


@mcp.tool()
@_structured_errors(ToolError)
def get_rules(preset_id: str) -> str:
    """Explain the formatting rules of a preset in Russian, after inheritance is applied.

    Covers page margins, fonts, spacing, headings, page numbers, figure/table captions, formulas,
    bibliography and appendices, each with the GOST clause or guideline it comes from.
    Use this to answer the user's questions about formatting requirements.
    """
    return describe_preset(loader.load_preset(preset_id))


class BibliographyWarning(BaseModel):
    index: int
    source_id: str | None
    message_ru: str


class BibliographyResult(BaseModel):
    text: str
    entries: list[str]
    warnings: list[BibliographyWarning]


@mcp.tool()
@_structured_errors(ToolError)
def format_bibliography(
    sources: list[Source],
    order: Literal["by_citation", "alphabetical"] | None = None,
    preset_id: str = "gost-7.32-2017",
) -> BibliographyResult:
    """Format a numbered reference list per GOST R 7.0.100-2018 from structured sources.

    Pass sources in the order they are first cited in the text. Supported `type`s: book, article,
    web (a page with `site`, or a whole website), law, standard. Copy names, titles and numbers exactly
    as printed; do not invent missing data. `order` defaults to the preset's rule. The result has the
    ready list (`text`, one entry per line), `entries`, and Russian `warnings` about missing fields —
    show them to the user and ask for the data rather than guessing.
    """
    preset = loader.load_preset(preset_id)
    style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
    result = formatter.format_bibliography(
        sources,
        order=order or preset.bibliography.order,
        numbering=preset.bibliography.numbering,
        style=style,
    )
    return BibliographyResult(
        text=result.text,
        entries=result.entries,
        warnings=[BibliographyWarning(**vars(w)) for w in result.warnings],
    )


@mcp.resource(
    "normokontrol://presets/{preset_id}",
    name="preset",
    description="Resolved preset (after `extends` inheritance) as YAML.",
    mime_type="application/yaml",
)
@_structured_errors(ResourceError)
def preset_resource(preset_id: str) -> str:
    return loader.dump_yaml(loader.load_preset(preset_id))


def main() -> None:
    """Run the server over stdio."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
