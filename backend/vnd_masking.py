"""
Маскирование персональных и организационных данных в ВНД перед анализом.
Названия реквизитов (ИНН, ОГРН и т.д.) сохраняются; значения заменяются на * по длине.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

_RE_FLAGS = re.IGNORECASE | re.UNICODE

# Слова, которые не являются ФИО в трёхсловных конструкциях
_NOT_FIO_WORDS = frozenset(
    {
        "федеральный",
        "закон",
        "положение",
        "регламент",
        "инструкция",
        "приказ",
        "утвержден",
        "утверждено",
        "российской",
        "федерации",
        "внутренний",
        "нормативный",
        "документ",
        "организация",
        "организации",
        "общие",
        "общий",
        "положения",
        "требования",
        "защита",
        "информации",
        "персональных",
        "данных",
        "трудовой",
        "договор",
        "ответственный",
        "ответственного",
        "назначении",
        "назначение",
        "руководитель",
        "руководителя",
        "директор",
        "директора",
        "главный",
        "главного",
        "отдел",
        "отдела",
        "управление",
        "управления",
        "департамент",
        "служба",
        "комитет",
        "министерство",
        "россия",
        "россии",
        "москва",
        "москвы",
        "санкт",
        "петербург",
    }
)

# (regex, номер группы со значением для маскирования)
_LABELED_VALUE_PATTERNS: List[Tuple[str, int]] = [
    # Реквизиты — метка остаётся
    (r"(\bИНН\s*(?:№\.?|:)?\s*)([\d\s]{10,12})", 2),
    (r"(\bОГРНИП\s*(?:№\.?|:)?\s*)([\d\s]{13,17})", 2),
    (r"(\bОГРН\s*(?:№\.?|:)?\s*)([\d\s]{13,15})", 2),
    (r"(\bКПП\s*(?:№\.?|:)?\s*)([\d\s]{8,10})", 2),
    (r"(\bБИК\s*(?:№\.?|:)?\s*)([\d\s]{8,10})", 2),
    (r"(\bОКПО\s*(?:№\.?|:)?\s*)([\d\s]{7,10})", 2),
    (r"(\bОКВЭД[\s\d\.]*\s*)([\d\.\s]{4,20})", 2),
    (r"(\bр/?\s*с\.?\s*(?:№\.?|:)?\s*)([\d\s]{19,22})", 2),
    (r"(\bк/?\s*с\.?\s*(?:№\.?|:)?\s*)([\d\s]{19,22})", 2),
    (r"(\bРасчётный\s+счёт\s*(?:№\.?|:)?\s*)([\d\s]{19,22})", 2),
    (r"(\bКорр(?:еспондентский)?\.?\s+счёт\s*(?:№\.?|:)?\s*)([\d\s]{19,22})", 2),
    (r"(\bТел(?:ефон)?\.?\s*(?:№\.?|:)?\s*)([\+\d\s\(\)\-]{5,25})", 2),
    (r"(\bE-?mail\s*[:—\-]?\s*)([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", 2),
    (r"(\bЭл\.?\s*почта\s*[:—\-]?\s*)([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", 2),
    # Название / наименование предприятия — метка остаётся
    (
        r"((?:Полное\s+)?(?:наименование|Название)\s+"
        r"(?:организации|предприятия|компании|юридического\s+лица)?\s*[:—\-]\s*)"
        r"([^\n;]+)",
        2,
    ),
    (
        r"(\b(?:Организация|Предприятие|Компания|Наименование\s+организации)\s*[:—\-]\s*)"
        r"([^\n;]+)",
        2,
    ),
    # Адрес — метка остаётся
    (
        r"((?:Юридический|Фактический|Почтовый)?\s*"
        r"Адрес(?:\s+организации|\s+предприятия)?\s*[:—\-]\s*)"
        r"([^\n;]+)",
        2,
    ),
    (r"(\bМестонахождение\s*[:—\-]\s*)([^\n;]+)", 2),
    # ФИО после должностных меток — метка остаётся
    (
        r"(\b(?:ФИО|Директор|Руководитель|Утвердил|Согласовал|Подпись|"
        r"Исполнитель|Ответственный(?:\s+лицо)?)\s*[:—\-]\s*)"
        r"([^\n;]+)",
        2,
    ),
]

_ORG_QUOTED_PATTERNS: List[Tuple[str, int]] = [
    (r'((?:ООО|ОАО|ЗАО|ПАО|АО|НКО|ИП)\s*[«"])([^»"]+)([»"])', 2),
    (
        r'(Общество\s+с\s+ограниченной\s+ответственностью\s*[«"])([^»"]+)([»"])',
        2,
    ),
    (
        r'(Акционерное\s+общество\s*[«"])([^»"]+)([»"])',
        2,
    ),
    (
        r'(Публичное\s+акционерное\s+общество\s*[«"])([^»"]+)([»"])',
        2,
    ),
]

_STREET_PATTERNS: List[Tuple[str, int]] = [
    (
        r"(\b(?:ул\.|улица|пр\.|проспект|пр-кт|пер\.|переулок|бульвар|б-р|ш\.|шоссе|"
        r"наб\.|набережная|пл\.|площадь|д\.|дом|корп\.|корпус|стр\.|строение|оф\.|офис|"
        r"кв\.|квартира|г\.|город)\s+)([^\n,;]+)",
        2,
    ),
]

_FIO_PATTERNS = [
    r"\b[А-ЯЁ][а-яё\-]{1,40}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.",
    r"\b[А-ЯЁ][а-яё\-]{1,40}\s+[А-ЯЁ][а-яё\-]{1,40}\s+[А-ЯЁ][а-яё\-]{1,40}\b",
]

# Ссылки на НПА не маскируются (ФЗ, ГОСТ, положения/указания ЦБ РФ и т.п.)
_LEGAL_REFERENCE_PATTERNS: List[str] = [
    r"(?:Положение|Указание|Инструкция)\s+Банка\s+России"
    r"(?:\s*\([^)]*\))?\s+от\s+\d{1,2}\.\d{1,2}\.\d{4}\s+№\s*[\w\-/]+(?:\s*[«\"][^»\"]+[»\"])?",
    r"ГОСТ(?:\s*Р)?\s*[\d]+(?:\.[\d]+)*(?:\s*—\s*[\d.]+)?(?:\s*\([^)]*\))?"
    r"(?:\s*[«\"][^»\"]+[»\"])?",
    r"Федеральн\w+\s+закон\w*(?:\s+от\s+\d{1,2}\.\d{1,2}\.\d{4})?"
    r"(?:\s+№\s*[\d\-–—]+(?:\s*[-–—]?\s*ФЗ)?)?(?:\s*[«\"][^»\"]+[»\"])?",
    r"(?:\d+[\d\-–—]*\s*[-–—]?\s*)?ФЗ\s*(?:от\s+\d{1,2}\.\d{1,2}\.\d{4}\s+)?(?:№\s*)?[\d\-–—]+"
    r"(?:\s*[-–—]?\s*ФЗ)?(?:\s*[«\"][^»\"]+[»\"])?",
    r"Постановлен\w+\s+Правительства\s+(?:РФ\s+)?от\s+\d{1,2}\.\d{1,2}\.\d{4}"
    r"\s+№\s*[\d\-–—]+(?:\s*[«\"][^»\"]+[»\"])?",
    r"Трудовой\s+кодекс\s+РФ",
    r"Кодекс\s+РФ\s+об\s+административных\s+правонарушениях",
    r"\bКоАП\s+РФ\b",
    r"(?:\d+\)\s*)?(?:Положение|Указание|Инструкция)\s+Банка\s+России[^\n«»]*[«\"][^»\"]+[»\"]",
    r"(?:\d+\)\s*)?ГОСТ(?:\s*Р)?\s*[\d.]+(?:\s*—\s*[\d.]+)?[^\n«»]*[«\"][^»\"]+[»\"]",
    r"(?:\d+\)\s*)?Федеральн\w+\s+закон\w*[^\n«»]*[«\"][^»\"]+[»\"]",
]

_NPA_PLACEHOLDER_PREFIX = "\uE000NPA:"
_NPA_PLACEHOLDER_SUFFIX = "\uE001"


def _mask_chars(value: str) -> str:
    return "*" * len(value)


def _sub_mask_group(text: str, pattern: str, value_group: int) -> str:
    def repl(match: re.Match) -> str:
        value = match.group(value_group)
        if not value:
            return match.group(0)
        full = match.group(0)
        prefix = full[: match.start(value_group) - match.start(0)]
        suffix = full[match.end(value_group) - match.start(0) :]
        return prefix + _mask_chars(value) + suffix

    return re.sub(pattern, repl, text, flags=_RE_FLAGS)


def _looks_like_fio(text: str) -> bool:
    if re.fullmatch(r"[А-ЯЁ][а-яё\-]{1,40}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.", text):
        return True
    words = text.split()
    if len(words) != 3:
        return False
    if any(w.lower().strip(".,;:") in _NOT_FIO_WORDS for w in words):
        return False
    return all(re.fullmatch(r"[А-ЯЁ][а-яё\-]+", w.strip(".,;:")) for w in words)


def _mask_fio(text: str) -> str:
    def repl(match: re.Match) -> str:
        fragment = match.group(0)
        if _looks_like_fio(fragment):
            return _mask_chars(fragment)
        return fragment

    for pattern in _FIO_PATTERNS:
        text = re.sub(pattern, repl, text)
    return text


def _apply_patterns(text: str, patterns: Iterable[Tuple[str, int]]) -> str:
    result = text
    for pattern, group in patterns:
        result = _sub_mask_group(result, pattern, group)
    return result


def _merge_spans(spans: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda item: (item[0], -(item[1] - item[0])))
    merged: List[Tuple[int, int]] = []
    for start, end in ordered:
        if not merged or start >= merged[-1][1]:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        merged[-1] = (prev_start, max(prev_end, end))
    return merged


def _find_legal_reference_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for pattern in _LEGAL_REFERENCE_PATTERNS:
        for match in re.finditer(pattern, text, flags=_RE_FLAGS):
            spans.append((match.start(), match.end()))
    return _merge_spans(spans)


def protect_legal_references(text: str) -> Tuple[str, dict]:
    """Временно заменить ссылки на НПА плейсхолдерами перед маскированием."""
    if not text:
        return text, {}

    spans = _find_legal_reference_spans(text)
    if not spans:
        return text, {}

    placeholders: dict = {}
    parts: List[str] = []
    last = 0
    for index, (start, end) in enumerate(spans):
        parts.append(text[last:start])
        key = f"{_NPA_PLACEHOLDER_PREFIX}{index}{_NPA_PLACEHOLDER_SUFFIX}"
        placeholders[key] = text[start:end]
        parts.append(key)
        last = end
    parts.append(text[last:])
    return "".join(parts), placeholders


def restore_legal_references(text: str, placeholders: dict) -> str:
    """Вернуть защищённые ссылки на НПА после маскирования."""
    if not text or not placeholders:
        return text
    result = text
    for key in sorted(placeholders.keys(), key=len, reverse=True):
        result = result.replace(key, placeholders[key])
    return result


def is_legal_reference_fragment(fragment: str) -> bool:
    """Проверить, относится ли фрагмент к ссылке на ФЗ, ГОСТ или акт ЦБ РФ."""
    value = (fragment or "").strip()
    if len(value) < 3:
        return False

    lowered = value.lower()
    legal_markers = (
        "гост",
        "федеральн",
        " закон",
        " фз",
        "-фз",
        "положение банка",
        "указание банка",
        "инструкция банка",
        "банка россии",
        "постановлен",
        "правительства рф",
        "трудовой кодекс",
        "коап",
        "кодекс рф",
    )
    if not any(marker in lowered for marker in legal_markers):
        return False

    if "«" in value or "»" in value or '"' in value:
        return True
    if re.search(r"\d+\s*[-–—]?\s*фз", lowered):
        return True
    if re.search(r"гост\s*р?\s*[\d]", lowered):
        return True
    if re.search(r"№\s*[\d]+(?:-п|-у|-и)\b", lowered):
        return True
    return re.search(
        r"(?:положение|указание|инструкция)\s+банка\s+россии",
        lowered,
    ) is not None


def mask_vnd_sensitive_data(text: str) -> str:
    """Замаскировать название предприятия, реквизиты, адреса и ФИО в тексте ВНД."""
    if not text or not text.strip():
        return text

    protected, placeholders = protect_legal_references(text)
    result = protected
    result = _apply_patterns(result, _LABELED_VALUE_PATTERNS)
    result = _apply_patterns(result, _ORG_QUOTED_PATTERNS)
    result = _apply_patterns(result, _STREET_PATTERNS)
    result = _mask_fio(result)
    return restore_legal_references(result, placeholders)


def mask_vnd_chunks(chunks: List[str], chunk_size: int = 1000) -> List[str]:
    """Замаскировать текст и заново разбить на чанки."""
    if not chunks:
        return chunks
    masked = mask_vnd_sensitive_data("\n".join(chunks))
    if not masked:
        return []
    return [masked[i : i + chunk_size] for i in range(0, len(masked), chunk_size)]
