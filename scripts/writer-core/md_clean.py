# -*- coding: utf-8 -*-
"""M_MD_CLEAN — чистка markdown-авторефератов от служебных блоков.

Источник проблемы: md-файлы, полученные конвертером PDF->md «по чанкам»,
содержат служебные блоки, которые гибридный экстрактор принимает за
параграфы текста:

  * YAML frontmatter        (--- source: pdf / file: / md5: / pages: ---)
  * служебные заголовки     "# <имя файла>", "## Чанки", "### Чанк N (...)",
                            "**Файл:** ...", "**Страниц:** ...", "**Обработано:** ..."
  * титульные обрывки       "На правах рукописи", "Бибиков Петр Сергеевич",
                            "Специальность 2.6.17 — Материаловедение",
                            "Москва — 2021", "2" (номера страниц), "х", " Р"
  * фрагменты швов чанков   обрывки слов на границах чанков

clean_md() удаляет служебные строки, СОХРАНЯЯ реальное содержание внутри
«Чанк N» (заголовок чанка убирается, текст под ним остаётся). Разделители
параграфов (пустые строки) сохраняются — блоки не склеиваются.

split_paragraphs_clean() — разбиение очищенного текста на параграфы по
пустым строкам, отбрасывая пустые и короче 15 символов.

Принципы аккуратности:
  * заголовки реальных разделов («Актуальность темы исследования»,
    «ОБЩАЯ ХАРАКТЕРИСТИКА РАБОТЫ») НЕ являются markdown-заголовками в
    этих файлах — они не удаляются (правила работают только со строками
    вида "# ..." и со служебными паттернами);
  * титульная страница отрезается ЦЕЛИКОМ только при обнаружении маркера
    «Москва — 19XX/20XX» в пределах первого чанка (детерминированная
    гарантия против ложных срабатываний в теле текста);
  * удаление строк никогда не склеивает разные параграфы: на месте
    удалённой строки остаётся пустая строка-разделитель.
"""
from __future__ import annotations

import re

_MIN_PARAGRAPH_CHARS = 15

_RE_FENCE = re.compile(r"^(?:---|\.\.\.)\s*$")
_RE_HEADER = re.compile(r"^(#{1,6})\s*(.*?)\s*$")
_RE_CHUNK_HEADER = re.compile(r"^#{1,6}\s*чанк\s*\d+", re.IGNORECASE)
_RE_BOLD_META = re.compile(
    r"^\*\*(?:Файл|Страниц|Обработано|Источник|Дата|Время|source)\s*[:*]*",
    re.IGNORECASE)
_RE_PLAIN_META = re.compile(
    r"^(?:Файл|Страниц|Обработано|Источник|source)\s*:", re.IGNORECASE)
_RE_BARE_NUMBER = re.compile(r"^\d{1,4}$")
_RE_MOSCOW_YEAR = re.compile(
    r"^\s*москва\s*[—–-]?\s*(?:19|20)\d{2}\s*(?:г\.?)?\s*$", re.IGNORECASE)
_RE_SPECIALITY = re.compile(r"^\s*специальность\s+\d", re.IGNORECASE)

# Служебные слова в markdown-заголовках (конвертер «по чанкам»).
_SERVICE_HEADER_KEYWORDS = (
    "чанк", "файл", "страниц", "обработано", "источник", "source",
    "md5", ".pdf", ".md", ".docx",
)

# Точные строки титульной страницы авторефератов (страховка, если маркер
# «Москва — YYYY» не найден). Сравнение по целой строке, case-insensitive.
_TITLE_LINES = (
    "на правах рукописи",
    "автореферат",
    "диссертации на соискание ученой степени",
    "диссертация на соискание ученой степени",
    "на соискание ученой степени",
    "кандидата технических наук",
    "доктора технических наук",
    "оглавление",
)

_CYR_LAT = re.compile(r"[A-Za-zА-Яа-яЁё0-9]")


def _strip_frontmatter(lines: list[str]) -> list[str]:
    """Убрать YAML frontmatter: '---' в начале … закрывающий '---'/'...'."""
    if not lines:
        return lines
    if not _RE_FENCE.match(lines[0].strip()):
        # страховка: нет открывающего ---, но есть строка 'source:'
        for i, ln in enumerate(lines[:20]):
            if re.match(r"^\s*source\s*:", ln, re.IGNORECASE):
                j = i + 1
                while j < len(lines) and j < i + 20 and not _RE_FENCE.match(
                        lines[j].strip()):
                    j += 1
                return lines[j + 1:] if j < len(lines) else lines[i + 1:]
        return lines
    for i in range(1, len(lines)):
        if _RE_FENCE.match(lines[i].strip()):
            return lines[i + 1:]
    return lines[1:]  # незакрытый frontmatter — отрезаем первый блок


def _is_service_header(line: str, seen_chunk: bool) -> bool:
    """Служебный markdown-заголовок? (реальные разделы не трогаем)."""
    m = _RE_HEADER.match(line)
    if not m:
        return False
    level = len(m.group(1))
    text = m.group(2)
    low = text.lower()
    if _RE_CHUNK_HEADER.match(line):
        return True
    if any(k in low for k in _SERVICE_HEADER_KEYWORDS):
        return True
    # H1-заголовок до первого чанка — это заголовок-«имя файла» конвертера.
    # Удаляем ТОЛЬКО если он похож на имя файла (цифры, латиница/дефисы),
    # чтобы не зацепить реальный раздел («# Введение») в рукописном md.
    if level == 1 and not seen_chunk:
        has_digit = bool(re.search(r"\d", text))
        latinish = bool(re.match(r"^[\w\s\-_.]+$", text)) \
            and not re.search(r"[А-Яа-яЁё]", text)
        if has_digit or latinish or len(text) < 4:
            return True
    return False


def _is_title_fragment(line: str) -> bool:
    """Титульный обрывок / фрагмент шва чанка.

    * голое число ("2") — номер страницы;
    * «Москва — 2021» (отдельной строкой);
    * строка без единой буквы/цифры (чистая пунктуация: "—", "…", "***");
    * короткая строка (< 3 слов) без знаков препинания и без цифр
      (обрывки слов на швах чанков: "х", " Р", "2");
    * точные титульные фразы;
    * «Специальность 2.6.17 — …» (код специальности титульного листа).
    """
    s = line.strip()
    if not s:
        return False
    if _RE_BARE_NUMBER.match(s):
        return True
    if _RE_MOSCOW_YEAR.match(s):
        return True
    if _RE_SPECIALITY.match(s):
        return True
    if not _CYR_LAT.search(s):
        return True
    low = s.lower()
    if low in _TITLE_LINES:
        return True
    words = s.split()
    if len(words) < 3 and not re.search(r"[.,;:!?—–«»()\[\]\"']", s) \
            and not re.search(r"\d", s):
        return True
    return False


def _truncate_title_page(lines: list[str]) -> list[str]:
    """Отрезать титульную страницу целиком (до «Москва — 19XX/20XX»).

    Срабатывает ТОЛЬКО если маркер найден в пределах первого чанка
    (до заголовка «### Чанк 1») или в первых 150 строках, если чанк один.
    Это убирает имя автора, название, специальность, «На правах рукописи»
    и т.п. — всё, что идёт до «Москва — YYYY» на титульном листе.
    """
    chunk_idx = [i for i, ln in enumerate(lines) if _RE_CHUNK_HEADER.match(ln)]
    moscow = None
    for i, ln in enumerate(lines):
        if _RE_MOSCOW_YEAR.match(ln.strip()):
            moscow = i
            break
    if moscow is None:
        return lines
    limit = chunk_idx[1] if len(chunk_idx) >= 2 else 150
    if moscow < limit:
        return lines[moscow + 1:]
    return lines


def clean_md(text: str) -> str:
    """Очистить markdown-автореферат от служебных блоков.

    Возвращает текст, пригодный для разбиения на параграфы:
    frontmatter, служебные заголовки, мета-строки, титульная страница и
    титульные обрывки удалены; реальное содержание «Чанк N» сохранено;
    пустые строки-разделители параграфов не склеиваются.
    """
    if not text:
        return ""
    text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")

    lines = text.split("\n")
    lines = _strip_frontmatter(lines)
    lines = _truncate_title_page(lines)

    out: list[str] = []
    seen_chunk = False
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")          # разделитель параграфов
            continue
        if _RE_BOLD_META.match(ln) or _RE_PLAIN_META.match(ln):
            out.append("")
            continue
        if _RE_CHUNK_HEADER.match(ln):
            seen_chunk = True
            out.append("")          # заголовок чанка уходит, содержимое ниже — нет
            continue
        if _is_service_header(ln, seen_chunk):
            out.append("")
            continue
        if _is_title_fragment(ln):
            out.append("")
            continue
        out.append(ln.rstrip())

    cleaned = "\n".join(out)
    # схлопнуть серии пустых строк в один разделитель параграфов
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
    return cleaned.strip()


def split_paragraphs_clean(text: str,
                           min_chars: int = _MIN_PARAGRAPH_CHARS) -> list[str]:
    """Очищенный текст -> параграфы (по пустым строкам).

    Отбрасывает пустые блоки и блоки короче `min_chars` символов
    (титульные обрывки, номера страниц, фрагменты швов).
    """
    blocks = re.split(r"\n[ \t]*\n", text)
    out: list[str] = []
    for b in blocks:
        s = b.strip()
        if len(s) >= min_chars:
            out.append(s)
    return out


if __name__ == "__main__":
    import sys
    src = sys.stdin.read() if len(sys.argv) < 2 else open(
        sys.argv[1], encoding="utf-8").read()
    cleaned = clean_md(src)
    paras = split_paragraphs_clean(cleaned)
    print(f"chars: {len(src)} -> {len(cleaned)}; paragraphs: {len(paras)}")
    for i, p in enumerate(paras[:40], 1):
        print(f"--- {i} [{len(p)}] {p[:90]!r}")