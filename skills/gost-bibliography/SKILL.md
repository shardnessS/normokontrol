---
name: gost-bibliography
description: Formats reference lists and bibliographic records under the Russian standard GOST R 7.0.100-2018 — список литературы, список использованных источников, библиографическое описание книг, статей, сайтов, законов и стандартов. Use when the user asks to format, fix or sort a bibliography for a Russian coursework, thesis (курсовая, ВКР, диплом, реферат) or article, e.g. «оформи список литературы по ГОСТу», «как правильно записать источник».
---

# Reference list per GOST R 7.0.100-2018

A deterministic script builds the records. Your job is to turn the user's sources into structured
data, run the script and hand its output over unchanged.

## Workflow

1. Collect the sources in any form (pasted list, citations, links, photos of title pages).
2. Convert each source into an object following [references/source-format.md](references/source-format.md).
   Copy names, titles, numbers and publishers exactly as given. **Never invent missing data** (city,
   publisher, year, pages, access date): leave the field out — the script will report it.
3. Keep the order in which the sources are cited in the work. Use alphabetical order only if the user
   asks for it or their university requires it.
4. Save the list as `sources.json` and run from this skill's directory:

   ```bash
   python scripts/format_bibliography.py sources.json
   ```

   Options: `--order alphabetical`, `--preset <id>`, `--json`. If `python` fails with
   `ModuleNotFoundError`, run the same command with `uv run` instead of `python`.

5. Give the user the numbered list **exactly as printed**. Do not retype, reword or "fix" it:
   punctuation, the dashes and the non-breaking spaces are intentional. Offer it as a block the user
   can copy into Word.
6. If the output has «Предупреждения», list in Russian what is missing for which source and ask the
   user. Run the script again after they answer. Do not fill the gaps yourself.

## Errors

On invalid input the script prints a JSON error with `message_ru` to stderr and exits with code 2.
These are mistakes in `sources.json` — fix the file and rerun; ask the user only if data is missing.

## Limits

- Supported types: `book`, `article`, `web` (page or whole site), `law`, `standard`. For other types
  (dissertation, article in a conference volume, patent) tell the user they are not supported yet. If
  the user still wants a record, write it by analogy and state clearly that it was not produced by the
  script.
- If the user gives only a DOI, ISBN or link, look the metadata up (web search if available), show the
  found data to the user for confirmation, then format it.
- Reply in Russian.
