---
name: gost-document
description: Builds a Word .docx of a Russian coursework, thesis or report formatted under GOST 7.32-2017 from a Markdown draft — margins, fonts, numbered sections, figure and table captions, numbered formulas, table of contents, reference list, appendices, page numbers. Use when the user asks to format their work by GOST, e.g. «оформи курсовую по ГОСТу», «сделай docx по ГОСТ 7.32», «собери ВКР в Word», or gives a draft to turn into a formatted document.
---

# Formatted .docx from a draft (GOST 7.32-2017)

A deterministic script builds the document. Your job is to prepare the draft in the expected format,
run the script and report the result. You format the user's text; you never write or change the
content of the work.

## Workflow

1. Ask which university preset to use if the user mentions one (`gost-rules` skill lists presets);
   otherwise use `gost-7.32-2017`.
2. Turn the user's text into a Markdown draft following
   [references/input-format.md](references/input-format.md):
   - keep the user's wording exactly; only add the markup (headings, figure/table/formula markup,
     references);
   - remove manual numbers from headings, captions and formulas — the script numbers everything;
   - turn citations into `[@key]` and put the sources into `sources.yaml` (format of the
     `gost-bibliography` skill, every source with an `id`);
   - put images next to the draft and reference them by relative path.
3. Run from this skill's directory:

   ```bash
   python scripts/build.py path/to/draft.md
   ```

   Options: `--preset <id>`, `--output path.docx`. If `python` fails with `ModuleNotFoundError`, run
   the same command with `uv run` instead of `python`. The result is written next to the draft as
   `<name>_gost.docx`; the draft itself is never changed.
4. Give the user the .docx and the summary line (sections, figures, tables, formulas, sources).
   Tell them to confirm «update fields» when Word asks — this fills in the table of contents.
5. Report every «Предупреждение» in Russian (e.g. a source not cited in the text) and ask what to do.

## Errors

On invalid input the script prints a JSON error with `message_ru` and `location` («файл:строка») to
stderr and exits with code 2. Fix the draft at that line and rerun; ask the user only when the fix
needs their decision (e.g. a missing image or source data).

## Limits

- The title page is not generated yet; tell the user to add it from their university template.
- Formulas support a LaTeX subset (see the reference); rewrite unsupported constructs with supported
  ones and keep the meaning.
- Reply in Russian.
