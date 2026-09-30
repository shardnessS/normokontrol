# Журнал архитектурных решений

Формат: дата — решение — причина.

## 2026-09-30 — Название `normokontrol-mcp`

Рабочее имя `gost-mcp` заменено на `normokontrol-mcp`.

- «GOST» неоднозначно (семейство криптоалгоритмов, прокси-проекты), на GitHub уже есть `mcp-gost` и `gost-standardizer-mcp`.
- «Нормоконтроль» точно описывает назначение инструмента; транслитерация по ГОСТ 7.79-2000 (система Б). Вариант `normocontrol` из черновика ТЗ — смесь транслитерации и английского.
- Имя свободно на PyPI и GitHub (проверено 2026-09-30).

Производные имена: пакет `normokontrol_mcp`, команда `normokontrol-mcp`, переменные окружения `NORMOKONTROL_*`, схема ресурсов `normokontrol://`.

## 2026-09-30 — MCP SDK 2.x: `MCPServer` вместо `FastMCP`

В `mcp` 2.x класс `FastMCP` переименован в `mcp.server.mcpserver.MCPServer`, API декораторов тот же. Используем `mcp>=2.2,<3`. В ТЗ «FastMCP» читать как `MCPServer`.

## 2026-09-30 — MCP Inspector на Windows и `uvx`

`npx @modelcontextprotocol/inspector --cli uvx --from . normokontrol-mcp` на Windows закрывает соединение, хотя тот же запуск `uvx` работает с MCP-клиентом Python SDK (stdio). Для отладки используем `npx @modelcontextprotocol/inspector uv run normokontrol-mcp` (как в CLAUDE.md) — работает. Причина, вероятно, в способе запуска дочернего процесса Inspector'ом; к серверу не относится.
