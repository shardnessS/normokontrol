# Установка

Нужен [uv](https://docs.astral.sh/uv/getting-started/installation/). Python отдельно ставить не требуется — uv скачает его сам.

- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Проверка: `uvx normokontrol-mcp` должен запуститься и ждать ввода (выход — Ctrl+C).

> Пока пакет не опубликован на PyPI, вместо `uvx normokontrol-mcp` используйте запуск из исходников:
> `uv --directory /путь/к/normokontrol-mcp run normokontrol-mcp`
> (в JSON-конфигах ниже: `"command": "uv"`, `"args": ["--directory", "/путь/к/normokontrol-mcp", "run", "normokontrol-mcp"]`).

## Claude Desktop

Меню **Settings → Developer → Edit Config** откроет `claude_desktop_config.json`
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`, macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`).

```json
{
  "mcpServers": {
    "normokontrol": {
      "command": "uvx",
      "args": ["normokontrol-mcp"]
    }
  }
}
```

Перезапустите Claude Desktop. В списке инструментов появится `ping`.

## Claude Code

```bash
claude mcp add normokontrol -- uvx normokontrol-mcp
```

Проверка: `claude mcp list` или команда `/mcp` внутри сессии.

## Cursor

Файл `~/.cursor/mcp.json` (для всех проектов) или `.cursor/mcp.json` (для одного проекта):

```json
{
  "mcpServers": {
    "normokontrol": {
      "command": "uvx",
      "args": ["normokontrol-mcp"]
    }
  }
}
```

## Проверка через MCP Inspector

Нужен Node.js.

```bash
npx @modelcontextprotocol/inspector uvx normokontrol-mcp
```

Откроется веб-интерфейс: вкладка **Tools → List Tools → ping → Run Tool**.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `NORMOKONTROL_PRESETS_DIR` | Папка с собственными пресетами вузов (этап 1) |
| `NORMOKONTROL_OFFLINE=1` | Запретить сетевые запросы (DOI, ISBN, URL) |
