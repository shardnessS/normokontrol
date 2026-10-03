---
name: gost-bibliography
description: Formats reference lists and bibliographic records under the Russian standard GOST R 7.0.100-2018 — список литературы, список использованных источников, библиографическое описание книг, статей, глав и докладов, диссертаций, патентов, сайтов, законов и стандартов; finds source data by DOI, ISBN or link. Use when the user asks to format, fix or sort a bibliography for a Russian coursework, thesis (курсовая, ВКР, диплом, реферат) or article, e.g. «оформи список литературы по ГОСТу», «как правильно записать источник».
---

# Reference list per GOST R 7.0.100-2018

A deterministic script builds the records. Your job is to turn the user's sources into structured
data, run the script and hand its output over unchanged.

## Workflow

1. Collect the sources in any form (pasted list, citations, DOIs, ISBNs, links, photos of title pages).
2. Build `sources.json` — a list in citation order. Each item is either
   - an object following [references/source-format.md](references/source-format.md), or
   - a plain string with a DOI, ISBN or URL — the script looks it up (Crossref, Open Library, page
     meta tags).

   Copy names, titles, numbers and publishers exactly as given. **Never invent missing data** (city,
   publisher, year, pages, access date): leave the field out — the script will report it.
3. Keep the order in which the sources are cited in the work. Use alphabetical order only if the user
   asks for it or their university requires it.
4. Run from this skill's directory:

   ```bash
   python scripts/format_bibliography.py sources.json
   ```

   Options: `--order alphabetical`, `--preset <id>`, `--json`. If `python` fails with
   `ModuleNotFoundError`, run the same command with `uv run` instead of `python`.

5. Give the user the numbered list **exactly as printed**. Do not retype, reword or "fix" it:
   punctuation, the dashes and the non-breaking spaces are intentional. Offer it as a block the user
   can copy into Word.
6. Act on the sections after the list:
   - «Предупреждения» — tell the user in Russian what is missing for which source and ask for it.
     Records found automatically must be checked against the original; say so.
   - «Не удалось оформить автоматически» — structure these sources yourself as objects (see
     step 7 if the reason is the network) and run the script again.

7. **No network** (reason «Нет доступа к сети» or «Сеть отключена», typical in the claude.ai sandbox):
   find the metadata with your web search if you have it, show what you found to the user for
   confirmation, then put it into `sources.json` as an object. Without web search, ask the user for the
   data.

To only look sources up (without formatting), run `python scripts/lookup.py <doi|isbn|url> ...` — it
prints JSON objects ready to paste into `sources.json`.

## Errors

On invalid input the script prints a JSON error with `message_ru` to stderr and exits with code 2.
These are mistakes in `sources.json` — fix the file and rerun; ask the user only if data is missing.

## Limits

- Supported types: `book` (also e-books and single volumes), `book_chapter`, `conference_paper`,
  `article`, `thesis` (dissertation or its abstract), `patent`, `web` (page or whole site), `law`,
  `standard`. For anything else (maps, music scores, archive documents) tell the user it is not
  supported. If they still want a record, write it by analogy and state clearly that it was not
  produced by the script.
- Open Library rarely knows Russian ISBNs; for Russian books expect «не найдена» and use web search or
  the title page.
- Reply in Russian.
