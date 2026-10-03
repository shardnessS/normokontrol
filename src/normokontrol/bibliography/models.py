"""Source models: book, chapter / conference paper, article, thesis, patent, web, law, standard."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from normokontrol.bibliography.names import InvalidNameError, parse_name

_RU_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


class _SourceBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str | None = Field(default=None, description="Citation key used in the text, e.g. ivanov2020")
    title: str = Field(min_length=1, description="Main title exactly as on the title page")
    subtitle: str | None = Field(
        default=None,
        description="Other title information, e.g. «учебное пособие»; several parts joined by ' : '",
    )
    url: str | None = Field(default=None, description="URL for an online resource")
    accessed: dt.date | None = Field(default=None, description="Date the URL was accessed (YYYY-MM-DD)")
    access_mode: str | None = Field(
        default=None, description="Access restriction, e.g. «для авторизир. пользователей»"
    )
    site: str | None = Field(
        default=None,
        description="Host website or e-library the resource is on, e.g. «ЭБС Лань»; "
        "« : [сайт]» is added unless the value already contains ' : ', "
        "e.g. «Минтруд России : официальный сайт»",
    )

    @field_validator("accessed", mode="before")
    @classmethod
    def _russian_date(cls, value: object) -> object:
        return _parse_russian_date(value)

    @property
    def electronic(self) -> bool:
        return self.url is not None


def _parse_russian_date(value: object) -> object:
    """Accept «01.09.2026» in addition to ISO dates."""
    if isinstance(value, str) and (match := _RU_DATE.match(value.strip())):
        day, month, year = (int(part) for part in match.groups())
        return dt.date(year, month, day)
    return value


def _check_authors(value: list[str]) -> list[str]:
    for author in value:
        try:
            parse_name(author)
        except InvalidNameError as exc:
            raise ValueError(str(exc)) from None
    return value


Authors = Annotated[
    list[str],
    Field(description="Authors in title-page order: «Иванов Иван Иванович» or «Иванов И. И.»"),
]
Responsibility = Annotated[
    list[str],
    Field(
        description="Further statements of responsibility, each as printed: «под редакцией А. А. Иванова», "
        "«перевод с английского …», «Московский государственный университет»"
    ),
]


class Book(_SourceBase):
    type: Literal["book"]
    authors: Authors = []
    responsibility: Responsibility = []
    edition: str | None = Field(
        default=None, description="Edition statement, e.g. «2-е изд., перераб. и доп.»"
    )
    city: str | None = None
    publisher: str | None = None
    year: int | str | None = None
    pages: int | str | None = Field(default=None, description="Number of pages, e.g. 350 or «215, [1]»")
    illustrations: str | None = Field(default=None, description="Other physical details, e.g. «ил.»")
    series: str | None = Field(default=None, description="Series title, optionally with « ; number»")
    notes: list[str] = Field(default=[], description="Notes as printed, e.g. «Библиогр.: с. 329–342»")
    isbn: str | None = None
    doi: str | None = None

    _authors = field_validator("authors")(_check_authors)


class BookChapter(_SourceBase):
    """A chapter or section of a book, or a paper in conference proceedings / a collection of papers."""

    type: Literal["book_chapter", "conference_paper"]
    authors: Authors = []
    responsibility: Responsibility = []
    book_title: str | None = Field(default=None, description="Title of the book / proceedings / collection")
    book_subtitle: str | None = Field(
        default=None,
        description="Other title information of the book, e.g. «материалы всероссийской конференции "
        "(Москва, 16 ноября 2018 г.)», «сборник научных трудов»",
    )
    book_responsibility: list[str] = Field(
        default=[], description="Editors, compilers, issuing organisation of the book, each as printed"
    )
    edition: str | None = None
    city: str | None = None
    publisher: str | None = None
    year: int | str | None = None
    isbn: str | None = None
    part: str | None = Field(
        default=None, description="Volume or issue of the book as printed, e.g. «Вып. 25»"
    )
    section: str | None = Field(default=None, description="Section of the book as printed, e.g. «Раздел 1»")
    pages: str | int | None = Field(default=None, description="Page range of the chapter, e.g. «61–78»")
    doi: str | None = None

    _authors = field_validator("authors")(_check_authors)


class Thesis(_SourceBase):
    """A dissertation or the author's abstract of a dissertation (автореферат)."""

    type: Literal["thesis"]
    authors: Authors = Field(
        default=[],
        description="The author as on the title page, usually full name «Аврамова Елена Викторовна»",
    )
    kind: Literal["dissertation", "abstract"] = Field(
        default="dissertation", description="dissertation — диссертация, abstract — автореферат диссертации"
    )
    specialty: str | None = Field(
        default=None, description="Specialty code and name, e.g. «05.25.03 «Библиотековедение…»»"
    )
    degree: str | None = Field(
        default=None, description="Degree in genitive, e.g. «кандидата педагогических наук»"
    )
    responsibility: Responsibility = []
    city: str | None = None
    year: int | str | None = None
    pages: int | str | None = None
    illustrations: str | None = None
    notes: list[str] = Field(
        default=[], description="Notes as printed, e.g. «Место защиты: Ин-т психологии РАН»"
    )

    _authors = field_validator("authors")(_check_authors)


class Patent(_SourceBase):
    """A patent; the record starts with «Патент № …» (GOST R 7.0.100-2018 with Amendment, 2020)."""

    type: Literal["patent"]
    number: str | None = Field(default=None, description="Patent number, e.g. «2637215»")
    country: str = Field(default="Российская Федерация", description="Country that granted the patent")
    classification: str | None = Field(
        default=None, description="Classification as printed, e.g. «МПК B02C 19/16 (2006.01)»"
    )
    application: str | None = Field(default=None, description="Application number, e.g. «2017105030»")
    filed: dt.date | None = Field(default=None, description="Application date (заявлено)")
    published: dt.date | None = Field(default=None, description="Publication date (опубликовано)")
    inventors: list[str] = Field(default=[], description="Inventors as printed, e.g. «Артеменко К. И.»")
    responsibility: Responsibility = Field(
        default=[], description="Applicant / patent holder as printed, e.g. «заявитель БГТУ»"
    )
    pages: int | str | None = None
    illustrations: str | None = None

    @field_validator("filed", "published", mode="before")
    @classmethod
    def _patent_dates(cls, value: object) -> object:
        return _parse_russian_date(value)


class Article(_SourceBase):
    type: Literal["article"]
    authors: Authors = []
    responsibility: Responsibility = []
    journal: str | None = Field(default=None, description="Journal title")
    year: int | str | None = None
    volume: str | int | None = Field(default=None, description="Volume (Т.)")
    issue: str | int | None = Field(default=None, description="Issue number (№)")
    pages: str | int | None = Field(default=None, description="Page range, e.g. «136–144»")
    notes: list[str] = Field(
        default=[], description="Notes as printed, e.g. «Библиогр.: с. 142–143 (17 назв.)»"
    )
    doi: str | None = None

    _authors = field_validator("authors")(_check_authors)


class Web(_SourceBase):
    """A web page on a site (`site` set) or a whole website (`site` empty)."""

    type: Literal["web"]
    authors: Authors = []
    responsibility: Responsibility = []
    city: str | None = Field(default=None, description="Whole website only: place of publication")
    publisher: str | None = Field(default=None, description="Whole website only: owner/publisher")
    year: int | str | None = Field(
        default=None, description="Year of publication; for a whole website a range like «2000 – »"
    )
    date: str | None = Field(
        default=None, description="Publication date on the site as printed, e.g. «2 февр.»"
    )

    _authors = field_validator("authors")(_check_authors)


class Law(_SourceBase):
    type: Literal["law"]
    act_type: str | None = Field(default=None, description="Kind of act, e.g. «Федеральный закон»")
    number: str | None = Field(default=None, description="Act number, e.g. «273-ФЗ»")
    date: str | None = Field(
        default=None, description="Date of the act as printed after «от», e.g. «29.12.2012»"
    )
    details: list[str] = Field(
        default=[],
        description="Further title information, each part separated by ' : ', e.g. "
        "«принят Государственной Думой 21 декабря 2012 года»",
    )
    publication: str | None = Field(
        default=None,
        description="Official publication, e.g. «Собрание законодательства Российской Федерации»",
    )
    year: int | str | None = None
    issue: str | int | None = None
    article: str | int | None = Field(default=None, description="Article number in the publication (Ст.)")
    pages: str | int | None = None


class Standard(_SourceBase):
    """A standard; the record starts with its designation (GOST R 7.0.100-2018, appendix examples)."""

    type: Literal["standard"]
    designation: str | None = Field(default=None, description="E.g. «ГОСТ Р 7.0.100–2018»")
    kind: str | None = Field(default=None, description="E.g. «национальный стандарт Российской Федерации»")
    details: list[str] = Field(
        default=[], description="Further title information, e.g. «издание официальное», «введен впервые»"
    )
    effective_date: dt.date | None = Field(default=None, description="Date of introduction (дата введения)")
    responsibility: Responsibility = []
    edition: str | None = None
    city: str | None = None
    publisher: str | None = None
    year: int | str | None = None
    pages: int | str | None = None

    @field_validator("effective_date", mode="before")
    @classmethod
    def _effective_date(cls, value: object) -> object:
        return _parse_russian_date(value)


Source = Annotated[
    Book | BookChapter | Article | Thesis | Patent | Web | Law | Standard, Field(discriminator="type")
]
SOURCE_TYPES = (
    "book",
    "book_chapter",
    "conference_paper",
    "article",
    "thesis",
    "patent",
    "web",
    "law",
    "standard",
)
