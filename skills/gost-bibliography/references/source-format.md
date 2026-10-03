# Source format for `format_bibliography.py`

The input file is a JSON (or YAML) list of sources, or an object
`{"sources": [...], "order": "by_citation" | "alphabetical", "preset": "<id>"}`.
Each source has a `type`. Unknown fields are rejected. Omit fields you do not know.

Common fields (all types):

| Field | Meaning |
|---|---|
| `id` | Citation key used in the text, optional |
| `title` | Main title exactly as printed (required) |
| `subtitle` | Other title information: «учебник», «монография», «учебное пособие для вузов» |
| `url`, `accessed` | Online resource address and access date (`YYYY-MM-DD` or `DD.MM.YYYY`) |
| `access_mode` | Access restriction as printed, e.g. «для авториз. пользователей» |
| `site` | Host site or e-library: «ЭБС Лань». « : [сайт]» is added unless the value already has « : », e.g. «Минтруд России : официальный сайт» |

Names: `"Иванов Иван Иванович"`, `"Иванов И. И."` or `"Иванов, Иван"` — all are accepted; the script
builds initials and the right word order. List authors in title-page order.

## book

Fields: `authors`, `responsibility` (further statements as printed: «под редакцией …», «перевод с
английского …», an issuing organisation), `edition`, `city`, `publisher`, `year`, `pages` (number or
text like «215, [1]»), `illustrations` («ил.»), `series`, `notes`, `isbn`; for an e-book also `site`,
`url`, `accessed`, `access_mode`.

```json
{
  "type": "book",
  "authors": ["Иванов Иван Иванович", "Петров Пётр Петрович"],
  "title": "Основы программирования",
  "subtitle": "учебник",
  "edition": "2-е изд., перераб. и доп.",
  "city": "Москва",
  "publisher": "Юрайт",
  "year": 2020,
  "pages": 350,
  "isbn": "978-5-534-00000-0"
}
```

An e-book with only a link (if it is on an e-library site, also set `site`, and `access_mode` when
access is restricted):

```json
{
  "type": "book",
  "authors": ["Канке Виктор Андреевич"],
  "title": "Философия",
  "subtitle": "учебник",
  "city": "Москва",
  "publisher": "ИНФРА-М",
  "year": 2019,
  "pages": 291,
  "url": "https://new.znanium.com/read?id=337682",
  "accessed": "2019-10-02"
}
```

A collection without authors: leave `authors` out, put editors or compilers into `responsibility`:

```json
{
  "type": "book",
  "title": "Электрические аппараты",
  "subtitle": "учебник и практикум",
  "responsibility": ["под редакцией П. А. Курбатова"],
  "city": "Москва",
  "publisher": "Юрайт",
  "year": 2018,
  "pages": 247
}
```

## article (journal article)

Fields: `authors`, `responsibility`, `journal`, `year`, `volume` (Т.), `issue` (№), `pages` (range
«136-144»), `notes`, `doi`, `url`, `accessed`, `access_mode`.

```json
{
  "type": "article",
  "authors": ["Козлова И. И."],
  "title": "Тенденции формирования промышленного сортимента земляники в Российской Федерации",
  "journal": "Садоводство и виноградарство",
  "year": 2019,
  "issue": 2,
  "pages": "25-32"
}
```

A foreign article: write the title and journal in the original language; numbering labels follow the
language automatically (Vol., no., P.).

```json
{
  "type": "article",
  "authors": ["Shchitov S. V.", "Krivutsa Z. F.", "Kurkov Yu. B."],
  "title": "Increasing the Efficiency of Transport and Technological Complexes Used in Crop Harvesting",
  "journal": "Journal of Engineering and Applied Sciences",
  "year": 2018,
  "volume": 13,
  "issue": 16,
  "pages": "6850-6854",
  "doi": "10.3923/jeasci.2018.6850.6854"
}
```

## web (web page or whole website)

A page on a site — set `site`:

```json
{
  "type": "web",
  "title": "Порядок присвоения номера ISBN",
  "site": "Российская книжная палата",
  "year": 2018,
  "url": "http://bookchamber.ru/isbn.html",
  "accessed": "2018-05-22"
}
```

Fields for a page: `authors`, `responsibility`, `site`, `year`, `date` (publication date as printed,
«2 февр.»). A whole website — no `site`; use `subtitle` («научная электронная библиотека»), `city`,
`publisher`, `year` (a range like «2000 – » for a site that is still updated):

```json
{
  "type": "web",
  "title": "eLIBRARY.RU",
  "subtitle": "научная электронная библиотека",
  "city": "Москва",
  "year": "2000 – ",
  "url": "https://elibrary.ru",
  "accessed": "2024-01-09"
}
```

## law (laws, codes, decrees)

Fields: `act_type` («Федеральный закон», «Постановление Правительства Российской Федерации»), `date`
(as printed after «от»: «29.12.2012»), `number` («273-ФЗ»), `details` (each part after « : », e.g.
«принят Государственной Думой 21 декабря 2012 года»), and either the official publication
(`publication`, `year`, `issue`, `article`) or `site` + `url` + `accessed`.

```json
{
  "type": "law",
  "title": "Об образовании в Российской Федерации",
  "act_type": "Федеральный закон",
  "date": "29.12.2012",
  "number": "273-ФЗ",
  "publication": "Собрание законодательства Российской Федерации",
  "year": 2012,
  "issue": "53, ч. 1",
  "article": 7598
}
```

## standard (GOST, GOST R, ISO …)

Fields: `designation` («ГОСТ Р 7.0.100–2018»), `kind` («национальный стандарт Российской Федерации»),
`details` («издание официальное», «введен впервые»), `effective_date` (`YYYY-MM-DD`),
`responsibility`, `edition`, `city`, `publisher`, `year`, `pages`; or `site` + `url` + `accessed`.

```json
{
  "type": "standard",
  "designation": "ГОСТ Р 57618.1–2017",
  "title": "Инфраструктура маломерного флота. Общие положения",
  "kind": "национальный стандарт Российской Федерации",
  "details": ["издание официальное", "введен впервые"],
  "effective_date": "2018-01-01",
  "responsibility": ["разработан ООО «Техречсервис»"],
  "city": "Москва",
  "publisher": "Стандартинформ",
  "year": 2017,
  "pages": "IV, 7"
}
```
