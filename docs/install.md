# Установка

Набор состоит из скиллов (Agent Skills) для Claude:

| Скилл | Что делает |
|---|---|
| `gost-rules` | Отвечает на вопросы о требованиях ГОСТ 7.32-2017: поля, шрифт, заголовки, подписи рисунков и таблиц |
| `gost-bibliography` | Оформляет список литературы по ГОСТ Р 7.0.100-2018 |

Скиллы оформления документа (`gost-document`) и нормоконтроля (`gost-normokontrol`) появятся на следующих этапах.

## Где взять архивы

Пока нет релиза, архивы собираются так:

- **Из GitHub Actions.** Откройте последний успешный запуск CI в разделе Actions репозитория и скачайте артефакт `skills`: внутри лежат `gost-rules.zip` и `gost-bibliography.zip`.
- **Локально.** В папке репозитория выполните `uv run python tools/build_skills.py`. Архивы появятся в `dist/`.

## claude.ai и Claude Desktop

1. **Settings → Capabilities**: включите **Code execution and file creation** (без него скрипты скиллов не запустятся).
2. Там же в разделе **Skills** нажмите **Upload skill** и загрузите `gost-rules.zip`, затем `gost-bibliography.zip`.
3. Проверьте в новом чате: «Какие поля нужны по ГОСТ 7.32?» или «Оформи по ГОСТу: Иванов И. И. Основы программирования, Москва, Юрайт, 2020, 350 страниц».

В claude.ai документы, которые вы прикладываете к чату, обрабатываются в песочнице Claude. Скрипты скиллов никуда их не отправляют.

## Claude Code

Установка плагином из GitHub (подключает все скиллы сразу):

```bash
/plugin marketplace add shardnessS/normokontrol
```

```bash
/plugin install normokontrol@normokontrol
```

Скриптам нужен Python 3.11+ с пакетами `pydantic` и `PyYAML`. Проще всего поставить [uv](https://docs.astral.sh/uv/getting-started/installation/): тогда Claude запустит скрипт через `uv run`, и пакеты подтянутся сами.

- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Без плагина: распакуйте архивы из `dist/` в `~/.claude/skills/` (для всех проектов) или в `.claude/skills/` проекта.

## Свои пресеты вузов (Claude Code)

Положите YAML-файлы пресетов в папку и укажите её в переменной окружения `NORMOKONTROL_PRESETS_DIR`. Пример пресета — в `SPEC.md`, раздел 6; базовый пресет выводит команда `presets.py yaml gost-7.32-2017` скилла `gost-rules`.
