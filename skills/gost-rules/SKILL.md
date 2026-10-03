---
name: gost-rules
description: Answers questions about formatting requirements for Russian academic works (курсовая, ВКР, диплом, реферат, отчёт о НИР) under GOST 7.32-2017 and university guidelines — margins, font, line spacing, indents, headings, page numbers, figure and table captions, formulas, appendices, lists, reference list layout. Use when the user asks what the rules are, e.g. «какие поля по ГОСТу», «какой шрифт и интервал», «как подписать рисунок», «требования нормоконтроля».
---

# GOST formatting rules

Answer questions about how a Russian academic work must be formatted, using the rules stored in
formatting presets. The presets were checked against the text of GOST 7.32-2017; every rule carries
the clause it comes from.

## Workflow

1. Get the rules of the preset. Run from this skill's directory:

   ```bash
   python scripts/presets.py rules gost-7.32-2017
   ```

   If `python` fails with `ModuleNotFoundError`, run the same command with `uv run` instead of `python`.

2. If the user names a university, run `python scripts/presets.py list` and use that university's
   preset when one exists. A preset marked «НЕ сверен с методичкой» may differ from the current
   guidelines — say so in the answer.

3. Answer in Russian, briefly, quoting the values from the output and the source in brackets, e.g.
   «Поля: левое 30 мм, правое 15 мм, верхнее и нижнее 20 мм (ГОСТ 7.32-2017, п. 6.1.1)».

## Rules for answering

- Values come only from the script output. Do not answer formatting questions from memory.
- Requirements marked «Не ГОСТ» are common university requirements, not the standard. Tell the user
  their university guidelines (методичка) take priority.
- If the question is not covered by the output (e.g. the exact title page layout of a given
  university), say that the preset does not cover it and advise checking the методичка. Do not invent
  rules.
- To format a reference list use the `gost-bibliography` skill; this skill only explains the rules.

## Own presets (Claude Code only)

Users can add university presets as YAML files in a folder set by the `NORMOKONTROL_PRESETS_DIR`
environment variable; `python scripts/presets.py yaml gost-7.32-2017` prints the base preset to copy.
A preset inherits the base with `extends: gost-7.32-2017` and overrides only what differs.
