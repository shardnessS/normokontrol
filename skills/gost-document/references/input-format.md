# Draft format for `build.py`

The draft is a Markdown file (UTF-8). Only the elements below are recognised; everything else is a
plain paragraph. Numbers of sections, figures, tables, formulas and appendices are assigned by the
script — never type them.

## Parameters block (front matter)

```yaml
---
preset: gost-7.32-2017        # or a university preset id
work_type: coursework         # coursework | vkr | report | essay
sources: sources.yaml         # file next to the draft, or an inline list
order: by_citation            # optional: by_citation | alphabetical (default — from the preset)
title_page:                   # kept for the title page (next stage); not rendered yet
  university: "…"
  title: "…"
  author: "…"
---
```

`sources` uses the format of the `gost-bibliography` skill (`references/source-format.md` there).
Every source needs an `id` — it is the citation key.

## Headings

| Markdown | Result |
|---|---|
| `# ВВЕДЕНИЕ`, `# ЗАКЛЮЧЕНИЕ`, `# РЕФЕРАТ`, … | Structural element: capitals, centred, new page, no number |
| `# СОДЕРЖАНИЕ` | Table of contents (a Word field, filled in when the file is opened) |
| `# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ` | The reference list is generated here from `sources`; leave it empty. If omitted, it is added before the appendices |
| `# Анализ предметной области` | Section «1 Анализ предметной области», new page |
| `## Обзор решений` | Subsection «1.1 Обзор решений» |
| `### Пункт` | «1.1.1 Пункт» |
| `# ПРИЛОЖЕНИЕ {#app:code}` + `## Листинг программы` | «ПРИЛОЖЕНИЕ А» with the title on the next line; further `##` inside are «А.1 …» |

Structural elements cannot have subsections. Appendices go last.

## Text

- Paragraphs are separated by an empty line; line breaks inside a paragraph are joined.
- A paragraph starting with «где» (explanation after a formula) keeps its line breaks: one symbol per line.
- `**bold**`, `*italic*`, `` `code` ``.
- Lists: `- item` → «— item»; `а) item` → letters (ГОСТ excludes ё, з, й, о, ч, ъ, ы, ь); `1. item` → «1) item».

## Figures, tables, formulas

```markdown
![Архитектура системы](img/arch.png){#fig:arch}

: Сравнение аналогов {#tbl:compare}

| Решение | Цена |
|---|---|
| А | 100 |

$$ E = mc^2 $$ {#eq:energy}
```

- Image path is relative to the draft; PNG, JPG, GIF, BMP, TIFF (not SVG). Wide images are scaled to
  the text width.
- A table must have a caption line `: Название {#tbl:id}` right before it.
- Formulas: LaTeX subset — `^ _ \frac \sqrt \sum \prod \int \left( \right)`, Greek letters, `\cdot
  \times \le \ge \ne \approx \infty`, `\sin \cos \ln \log \exp \lim \max \min`, `\text{…}`. A formula
  without `{#eq:…}` is not numbered.
- Code listing: a fenced block with three backticks.

## References

| In the draft | In the document |
|---|---|
| `[@fig:arch]` | `1` — write «на рисунке [@fig:arch]» |
| `[@tbl:compare]` | `1` |
| `[@eq:energy]` | `(1)` |
| `[@app:code]` | `А` |
| `[@ivanov2020]` | `[3]` — number in the reference list |
| `[@ivanov2020, с. 15]` | `[3, с. 15]` |

Unknown labels and keys are errors with the line number.
