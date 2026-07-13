"""
Обнаружение ссылок на федеральные документы в тексте ВНД.
"""
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from config import settings
from document_loader import extract_full_text

# Результат последнего поиска ссылок (для панели «Помощник в создании ВНД» и др.)
_session_federal_refs_result: Optional[Dict] = None


# Шаблоны ссылок на федеральные НПА
_REFERENCE_PATTERNS = [
    (
        "federal_law",
        re.compile(
            r"(Федеральн\w+\s+закон\w*"
            r"(?:\s+от\s+\d{1,2}\.\d{1,2}\.\d{2,4})?"
            r"\s*(?:№|N|No\.?\s*)?\s*\d+\s*[-–—]?\s*(?:ФЗ|фз|FZ|Fz|fz))",
            re.UNICODE | re.IGNORECASE,
        ),
    ),
    (
        "federal_law_short",
        re.compile(
            r"\b(?:ФЗ|фз)\s+(?:от\s+\d{1,2}\.\d{1,2}\.\d{2,4}\s+)?(?:№|N)?\s*(\d+\s*[-–—]?\s*(?:[FfФ][ZzЗ]|[Фф][Зз]|[Ff][Zz]|\d+))",
            re.IGNORECASE | re.UNICODE,
        ),
    ),
    (
        "federal_law_number_only",
        re.compile(
            r"(?:№|N)\s*(\d+\s*[-–—]\s*(?:[FfФ][ZzЗ]|[Фф][Зз]))",
            re.IGNORECASE | re.UNICODE,
        ),
    ),
    (
        "code",
        re.compile(
            r"((?:Трудов\w+|Гражданск\w+|Уголовн\w+|Административн\w+|Налогов\w+|Бюджетн\w+|"
            r"Земельн\w+|Жилищн\w+|Семейн\w+|Лесн\w+|Водн\w+|Градостроительн\w+|Таможенн\w+|"
            r"Уголовно-исполнительн\w+|Арбитражн\w+\s+процессуальн\w+|Гражданск\w+\s+процессуальн\w+|"
            r"Уголовно-процессуальн\w+)\s+кодекс\w*"
            r"(?:\s+Российской\s+Федерации|\s+РФ)?)",
            re.IGNORECASE | re.UNICODE,
        ),
    ),
    (
        "constitution",
        re.compile(
            r"(Конститу(?:ция|ции|цией)\s+Российской\s+Федерации|Конституция\s+РФ)",
            re.IGNORECASE | re.UNICODE,
        ),
    ),
    (
        "government_decree",
        re.compile(
            r"([Пп]остановление\s+[Пп]равительства\s+(?:РФ|Российской\s+Федерации)"
            r"(?:\s+от\s+\d{1,2}\.\d{1,2}\.\d{2,4})?"
            r"(?:\s+(?:№|N)\s*[\d\-]+(?:\s*[-–—]\s*[а-яА-Яa-zA-Z]+)?)?)",
            re.UNICODE,
        ),
    ),
    (
        "presidential_decree",
        re.compile(
            r"([Уу]каз\s+[Пп]резидента\s+(?:РФ|Российской\s+Федерации)"
            r"(?:\s+от\s+\d{1,2}\.\d{1,2}\.\d{2,4})?"
            r"(?:\s+(?:№|N)\s*[\d\-]+)?)",
            re.UNICODE,
        ),
    ),
    (
        "federal_law_named",
        re.compile(
            r'[Ff]едеральн(?:ый|ого)\s+закон\s+[«"]([^»"]+)[»"]',
            re.UNICODE,
        ),
    ),
]

_TYPE_LABELS = {
    "federal_law": "Федеральный закон",
    "federal_law_short": "Федеральный закон",
    "federal_law_number_only": "Федеральный закон",
    "federal_law_named": "Федеральный закон",
    "code": "Кодекс",
    "constitution": "Конституция",
    "government_decree": "Постановление Правительства РФ",
    "presidential_decree": "Указ Президента РФ",
}


def _normalize_fz_number(raw: str) -> str:
    """Нормализовать номер ФЗ (например 152-ФЗ)."""
    m = re.search(r"(\d+)", raw)
    if m:
        return f"{m.group(1)}-ФЗ"
    return raw.strip()


_MONTHS_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# Известные базовые законы: номер -> ключевые слова названия (для проверки согласованности).
_KNOWN_FZ_TITLES = {
    "152": ("персональн", "данных"),
    "115": ("иностранн", "легализац", "отмыван", "терроризм", "правовом положении"),
}


def _clean_law_name(name: str) -> str:
    """Очистить название закона от артеfactов таблиц и переносов PDF."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    cut_patterns = (
        r"\s+\d{1,4}\s+Наименован",
        r"\s+Наименован\s*ие\s+процесса",
        r"\s+Цель\s+обработки",
        r"\s+Категория\s+субъект",
        r"\s+Наследник\s+\d",
        r"\s+п\.\d",
        r"\s+ст\.\d",
        r"\s+ФЗ\s*[-–—]?\s*\d",
    )
    for pattern in cut_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            name = name[: match.start()].strip()
    name = re.sub(r"\s+\d{1,3}\s*$", "", name)
    return name.strip(" «»\"'")

def _slug_law_name(name: str) -> str:
    name = _clean_law_name(name)
    name = re.sub(r"\s+", " ", name.lower()).strip()
    return name[:80] if name else ""


def _normalize_law_name(title: str) -> Optional[str]:
    """Извлечь и нормализовать название закона из кавычек."""
    match = re.search(r'[«"]([^»"]+)[»"]', title or "")
    if not match:
        return None
    name = _clean_law_name(match.group(1))
    name = re.sub(r"\s+", " ", name.lower()).strip()
    return name or None


def _titles_compatible(number: Optional[str], law_name: Optional[str]) -> bool:
    """Проверить, согласуются ли номер ФЗ и название закона."""
    if not number or not law_name:
        return True
    num = re.sub(r"[^\d]", "", str(number).split("-")[0])
    hints = _KNOWN_FZ_TITLES.get(num)
    if not hints:
        return True
    return any(hint in law_name for hint in hints)


def _parse_document_date(day: str, month: str, year: str) -> Optional[str]:
    try:
        if "." in day:
            parts = day.split(".")
            if len(parts) == 3:
                d, m, y = parts
                if len(y) == 2:
                    y = f"20{y}" if int(y) < 70 else f"19{y}"
                return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            return None
        month_num = _MONTHS_MAP.get(month.lower())
        if not month_num:
            return None
        return f"{int(year):04d}-{month_num:02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return None


def _extract_document_date_from_text(text: str) -> Optional[str]:
    text = text or ""
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", text)
    if match:
        return _parse_document_date(match.group(0), "", "")
    match = re.search(
        r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|"
        r"сентября|октября|ноября|декабря)\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_document_date(match.group(1), match.group(2), match.group(3))
    return None


_CONTEXT_WINDOW = 120

_FULL_CITATION_PATTERN = re.compile(
    r"Федеральн\w+\s+закон\w*\s+от\s+"
    r"(?:(\d{1,2}\.\d{1,2}\.\d{2,4})|(\d{1,2})\s+"
    r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+"
    r"(\d{4})\s*г(?:\.|ода)?)"
    r"\s*(?:№|N)\s*(\d+)\s*[-–—]?\s*(?:ФЗ|фз|FZ|fz)\s*[«\"]([^»\"]+)[»\"]",
    re.UNICODE | re.IGNORECASE,
)

_FZ_ABBR_CITATION_PATTERN = re.compile(
    r"(?:ФЗ|фз)\s*[-–—]?\s*(\d+)\s*[«\"]([^»\"]+)[»\"]",
    re.UNICODE | re.IGNORECASE,
)

_ARTICLE_CITATION_PATTERN = re.compile(
    r"(?:ст\.?|стать[ейя]\s+)\d+[^\n]{0,40}?"
    r"Федеральн\w+\s+закон\w*\s+от\s+"
    r"(?:(\d{1,2}\.\d{1,2}\.\d{2,4})|(\d{1,2})\s+"
    r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+"
    r"(\d{4})\s*г(?:\.|ода)?)"
    r"\s*(?:№|N)\s*(\d+)\s*[-–—]?\s*(?:ФЗ|фз|FZ|fz)"
    r"(?:\s*[«\"]([^»\"]+)[»\"])?",
    re.UNICODE | re.IGNORECASE,
)

_FULL_REFERENCE_PATTERNS = [
    _FULL_CITATION_PATTERN,
    _FZ_ABBR_CITATION_PATTERN,
]


def _update_search_query(ref: Dict) -> None:
    """Пересобрать search_query по полям ссылки."""
    number = ref.get("number")
    document_date = ref.get("document_date")
    title = ref.get("title") or ""

    if document_date and number:
        num_digits = re.sub(r"[^\d]", "", number.split("-")[0])
        if isinstance(document_date, str) and "." in document_date:
            ref["search_query"] = f"Федеральный закон от {document_date} № {num_digits}-ФЗ"
        else:
            ref["search_query"] = f"Федеральный закон {number} от {document_date}"
    elif number:
        ref["search_query"] = f"Федеральный закон {number}"
    elif title:
        ref["search_query"] = title


def _build_citation_reference(
    match: re.Match,
    ref_type: str = "federal_law_full",
    law_name: Optional[str] = None,
    number_raw: Optional[str] = None,
    document_date: Optional[str] = None,
) -> Dict:
    """Собрать ссылку из полной цитаты (номер, дата и название из одного фрагмента)."""
    if law_name is None:
        groups = match.groups()
        if ref_type == "federal_law_abbr":
            number_raw = groups[0]
            law_name = groups[1].strip()
            document_date = None
        else:
            dotted_date, day, month, year, number_raw, quoted_name = groups[:6]
            if dotted_date:
                document_date = _extract_document_date_from_text(dotted_date)
            elif day and month and year:
                document_date = _parse_document_date(day, month, year)
            else:
                document_date = None
            law_name = (quoted_name or "").strip()
            law_name = _clean_law_name(law_name)

    if law_name:
        law_name = _clean_law_name(law_name)
    number = _normalize_fz_number(number_raw or "")
    title = f"Федеральный закон «{law_name}»" if law_name else f"Федеральный закон {number}"
    raw = re.sub(r"\s+", " ", match.group(0).strip())

    ref = {
        "title": title,
        "type": _TYPE_LABELS.get("federal_law", "Федеральный закон"),
        "number": number,
        "document_date": document_date,
        "raw": raw,
        "match_start": match.start(),
        "match_end": match.end(),
        "source_pattern": ref_type,
    }
    _update_search_query(ref)
    return ref


def _spans_overlap(start: int, end: int, claimed: List[Tuple[int, int]]) -> bool:
    return any(start < claimed_end and end > claimed_start for claimed_start, claimed_end in claimed)


def _extract_full_citations(text: str) -> Tuple[List[Dict], List[Tuple[int, int]]]:
    """Извлечь полные цитаты ФЗ с датой, номером и названием из одного фрагмента."""
    found: List[Dict] = []
    claimed: List[Tuple[int, int]] = []
    seen_keys: Set[str] = set()

    patterns = (
        (_FULL_CITATION_PATTERN, "federal_law_full"),
        (_ARTICLE_CITATION_PATTERN, "federal_law_article"),
        (_FZ_ABBR_CITATION_PATTERN, "federal_law_abbr"),
    )

    for pattern, ref_type in patterns:
        for match in pattern.finditer(text):
            if _spans_overlap(match.start(), match.end(), claimed):
                continue

            groups = match.groups()
            if ref_type == "federal_law_abbr":
                number_raw, law_name = groups[0], groups[1]
                document_date = None
            else:
                dotted_date, day, month, year, number_raw = groups[0], groups[1], groups[2], groups[3], groups[4]
                law_name = groups[5] if len(groups) > 5 else None
                if dotted_date:
                    document_date = _extract_document_date_from_text(dotted_date)
                elif day and month and year:
                    document_date = _parse_document_date(day, month, year)
                else:
                    document_date = None

            if not law_name:
                continue

            law_name = _clean_law_name(re.sub(r"\s+", " ", law_name.strip()))
            if len(law_name) < 8:
                continue

            number = _normalize_fz_number(number_raw or "")
            if not _titles_compatible(number, _slug_law_name(law_name)):
                continue

            dedupe_key = f"{number}|{document_date or ''}|{_slug_law_name(law_name)}"
            if dedupe_key in seen_keys:
                claimed.append((match.start(), match.end()))
                continue
            seen_keys.add(dedupe_key)

            ref = _build_citation_reference(match, ref_type, law_name, number_raw, document_date)
            found.append(ref)
            claimed.append((match.start(), match.end()))

    return found, claimed


def _build_reference(ref_type: str, match: re.Match) -> Dict:
    """Сформировать объект ссылки из совпадения regex."""
    full_text = match.group(0).strip()
    full_text = re.sub(r"\s+", " ", full_text)

    number = None
    document_date = None
    if ref_type == "federal_law":
        title = match.group(1).strip()
        full_text = title
        num_match = re.search(r"(\d+)\s*-\s*(?:ФЗ|FZ|фз|fz)", title, re.I)
        if num_match:
            number = f"{num_match.group(1)}-ФЗ"
        date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{2,4})", title)
        if date_match:
            document_date = date_match.group(1)
    elif ref_type in ("federal_law_short", "federal_law_number_only"):
        try:
            number = _normalize_fz_number(match.group(1))
            title = f"Федеральный закон {number}"
        except IndexError:
            title = full_text
    elif ref_type == "federal_law_named":
        cleaned_name = _clean_law_name(match.group(1).strip())
        title = f'Федеральный закон «{cleaned_name}»'
        full_text = title
    elif ref_type == "code":
        title = match.group(1).strip()
    elif ref_type == "constitution":
        title = match.group(1).strip()
    else:
        title = full_text

    search_query = title
    if number:
        search_query = f"Федеральный закон {number}"
    if document_date and number:
        search_query = f"Федеральный закон от {document_date} № {number.replace('-ФЗ', '').replace('-фз', '')}-ФЗ"

    return {
        "title": title,
        "type": _TYPE_LABELS.get(ref_type, "Федеральный документ"),
        "number": number,
        "document_date": document_date,
        "search_query": search_query,
        "raw": full_text,
        "match_start": match.start(),
        "match_end": match.end(),
        "source_pattern": ref_type,
    }


def _find_local_citation_in_context(context: str, ref: Dict) -> Optional[Dict]:
    """Найти в узком контексте полную цитату, согласованную с уже известным названием/номером."""
    ref_name = _normalize_law_name(ref.get("title") or "")
    ref_number = ref.get("number")

    for pattern, ref_type in (
        (_FULL_CITATION_PATTERN, "federal_law_full"),
        (_FZ_ABBR_CITATION_PATTERN, "federal_law_abbr"),
    ):
        for match in pattern.finditer(context):
            candidate = _build_citation_reference(match, ref_type)
            cand_name = _normalize_law_name(candidate.get("title") or "")
            cand_number = candidate.get("number")

            if ref_name and cand_name and ref_name != cand_name:
                continue
            if ref_number and cand_number and ref_number != cand_number:
                continue
            if ref_name and cand_name and not _titles_compatible(cand_number, cand_name):
                continue
            return candidate
    return None


def enrich_reference_from_context(text: str, ref: Dict) -> Dict:
    """Дополнить неполную ссылку только согласованной локальной цитатой."""
    enriched = dict(ref)
    start = enriched.get("match_start", 0)
    end = enriched.get("match_end", start + len(enriched.get("raw", "")))
    window_start = max(0, int(start) - _CONTEXT_WINDOW)
    window_end = min(len(text), int(end) + _CONTEXT_WINDOW)
    context = text[window_start:window_end]
    enriched["context_snippet"] = re.sub(r"\s+", " ", context).strip()

    if enriched.get("number") and enriched.get("title"):
        law_name = _normalize_law_name(enriched.get("title") or "")
        if law_name and not _titles_compatible(enriched.get("number"), law_name):
            enriched["number"] = None
            _update_search_query(enriched)

    if not enriched.get("number") or not enriched.get("document_date"):
        local = _find_local_citation_in_context(context, enriched)
        if local:
            if not enriched.get("number") and local.get("number"):
                enriched["number"] = local["number"]
            if not enriched.get("document_date") and local.get("document_date"):
                enriched["document_date"] = local["document_date"]
            if local.get("title") and len(local.get("title", "")) > len(enriched.get("title", "")):
                enriched["title"] = local["title"]
            enriched["raw"] = local.get("raw") or enriched.get("raw")
            enriched["enriched_from_context"] = True

    _update_search_query(enriched)
    return enriched


def enrich_references_from_context(text: str, references: List[Dict]) -> List[Dict]:
    """Обогатить все ссылки контекстом и пересобрать search_query."""
    return [enrich_reference_from_context(text, ref) for ref in references]


def detect_federal_references(text: str) -> List[Dict]:
    """Найти ссылки на федеральные документы в тексте."""
    if not text or not text.strip():
        return []

    found: List[Dict] = []
    seen: Set[str] = set()
    claimed: List[Tuple[int, int]] = []

    full_citations, claimed = _extract_full_citations(text)
    for ref in full_citations:
        key = "|".join(sorted(_reference_identity_keys(ref)))
        if key in seen:
            continue
        seen.add(key)
        found.append(ref)

    for ref_type, pattern in _REFERENCE_PATTERNS:
        if ref_type in {"federal_law", "federal_law_named"}:
            continue
        for match in pattern.finditer(text):
            if _spans_overlap(match.start(), match.end(), claimed):
                continue
            if ref_type == "federal_law_number_only":
                before = text[max(0, match.start() - 40):match.start()].lower()
                if "закон" in before:
                    continue
            ref = _build_reference(ref_type, match)
            key = "|".join(sorted(_reference_identity_keys(ref)))
            if key in seen:
                continue
            seen.add(key)
            found.append(ref)
            claimed.append((match.start(), match.end()))

    for match in _REFERENCE_PATTERNS[0][1].finditer(text):
        if _spans_overlap(match.start(), match.end(), claimed):
            continue
        ref = _build_reference("federal_law", match)
        if not ref.get("number"):
            continue
        key = "|".join(sorted(_reference_identity_keys(ref)))
        if key in seen:
            continue
        seen.add(key)
        found.append(ref)
        claimed.append((match.start(), match.end()))

    for match in _REFERENCE_PATTERNS[-1][1].finditer(text):
        if _spans_overlap(match.start(), match.end(), claimed):
            continue
        ref = _build_reference("federal_law_named", match)
        key = "|".join(sorted(_reference_identity_keys(ref)))
        if key in seen:
            continue
        seen.add(key)
        found.append(ref)
        claimed.append((match.start(), match.end()))

    return found


def _collect_fz_index_entries() -> Tuple[Set[str], str]:
    """Собрать имена файлов и текстовые метки из папки FZ и векторной базы ФЗ."""
    names: Set[str] = set()
    combined_text_parts: List[str] = []

    fz_folder = Path(settings.fz_folder)
    if fz_folder.exists():
        for file_path in fz_folder.iterdir():
            if not file_path.is_file():
                continue
            stem = file_path.stem.lower()
            names.add(file_path.name.lower())
            names.add(stem)
            combined_text_parts.append(stem)

    try:
        from vector_store import init_vector_stores, fz_store

        init_vector_stores()
        if fz_store:
            all_results = fz_store.collection.get()
            metadatas = (all_results or {}).get("metadatas") or []
            for metadata in metadatas:
                if not metadata:
                    continue
                filename = metadata.get("filename") or metadata.get("source") or ""
                if not filename:
                    continue
                filename = Path(str(filename)).name
                stem = Path(filename).stem.lower()
                names.add(filename.lower())
                names.add(stem)
                combined_text_parts.append(stem)
    except Exception as e:
        print(f"Предупреждение: не удалось прочитать векторную базу ФЗ: {e}")

    return names, " ".join(combined_text_parts).lower()


def _reference_matches_index(ref: Dict, indexed_names: Set[str], indexed_text: str) -> bool:
    """Проверить, есть ли ссылка в локальной базе федеральных документов."""
    title = (ref.get("title") or "").lower()
    search_query = (ref.get("search_query") or title).lower()
    number = ref.get("number")

    if number:
        fz_num = re.sub(r"[^\d]", "", number.split("-")[0])
        law_name = _normalize_law_name(ref.get("title") or "")
        if fz_num and law_name and fz_num in _KNOWN_FZ_TITLES and not _titles_compatible(number, law_name):
            pass
        elif fz_num:
            for name in indexed_names:
                if fz_num not in name.lower():
                    continue
                if law_name:
                    title_words = [
                        w for w in re.findall(r"[а-яёa-z]{5,}", law_name)
                        if w not in {"противодействии", "положении", "российской", "федерации"}
                    ]
                    if title_words:
                        matches = sum(1 for word in title_words if word in name.lower())
                        if matches >= max(1, len(title_words) // 2):
                            return True
                        continue
                num_patterns = (
                    fz_num,
                    f"{fz_num}-фз",
                    f"{fz_num}-fz",
                    f"№ {fz_num}",
                )
                for pattern in num_patterns:
                    if pattern in name.lower():
                        return True
            if fz_num in indexed_text and ("фз" in indexed_text or "закон" in indexed_text):
                if not law_name or _titles_compatible(number, law_name):
                    return True

    if "конститу" in title and "конститу" in indexed_text:
        return True

    if "кодекс" in title:
        code_word = title.split()[0] if title.split() else ""
        if code_word and len(code_word) > 4 and code_word in indexed_text:
            return True

    title_words = [
        w for w in re.findall(r"[а-яёa-z0-9]{4,}", title, re.IGNORECASE)
        if w not in {"федеральный", "закон", "российской", "федерации", "россии"}
    ]
    if title_words:
        matches = sum(1 for word in title_words if word in indexed_text)
        if matches >= max(1, len(title_words) // 2):
            return True

    for name in indexed_names:
        if search_query and len(search_query) > 12 and search_query[:40] in name:
            return True
        if title and len(title) > 12 and title[:40] in name:
            return True

    return False


def _reference_identity_keys(ref: Dict) -> Set[str]:
    """Ключи идентичности документа для объединения созвучных ссылок."""
    keys: Set[str] = set()

    number = ref.get("number")
    num = re.sub(r"[^\d]", "", str(number).split("-")[0]) if number else ""
    law_name = _normalize_law_name(ref.get("title") or "")
    document_date = ref.get("document_date")

    if num and law_name:
        keys.add(f"law:{num}:{_slug_law_name(law_name)}")
        if document_date:
            keys.add(f"law:{num}:{document_date}")
    elif num:
        keys.add(f"fz:{num}")
    elif law_name:
        keys.add(f"name:{law_name}")

    title = (ref.get("title") or "").lower()
    if "конститу" in title:
        keys.add("constitution")
    if "кодекс" in title:
        code_word = title.split()[0] if title.split() else ""
        if code_word and len(code_word) > 4:
            keys.add(f"code:{code_word}")

    if ref.get("type") == "Постановление Правительства РФ":
        decree_num = re.search(r"(?:№|n)\s*([\d\-]+)", ref.get("raw") or title, re.I)
        if decree_num:
            keys.add(f"decree:gov:{decree_num.group(1)}")
    if ref.get("type") == "Указ Президента РФ":
        decree_num = re.search(r"(?:№|n)\s*([\d\-]+)", ref.get("raw") or title, re.I)
        if decree_num:
            keys.add(f"decree:pres:{decree_num.group(1)}")

    if not keys:
        raw_key = re.sub(r"\s+", " ", (ref.get("raw") or ref.get("title") or "").lower()).strip()
        if raw_key:
            keys.add(f"raw:{raw_key[:120]}")

    return keys


def _pick_group_representative(group_refs: List[Dict]) -> Dict:
    """Выбрать наиболее полную ссылку из группы созвучных."""
    def score(item: Dict) -> Tuple[int, int]:
        title = item.get("title") or ""
        return (
            1 if item.get("number") else 0,
            len(title),
        )

    return max(group_refs, key=score)


def reconcile_references_by_local_base(references: List[Dict]) -> Dict:
    """
    Разделить ссылки с учётом объединения созвучных формулировок одного документа.
    Если один вариант ссылки есть в базе — все созвучные считаются найденными.
    """
    indexed_names, indexed_text = _collect_fz_index_entries()
    if not references:
        return {
            "references": [],
            "unique_references": [],
            "found": [],
            "missing": [],
            "total_detected": 0,
            "found_count": 0,
            "missing_count": 0,
            "unique_documents": 0,
        }

    parent = list(range(len(references)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    key_to_indices: Dict[str, List[int]] = defaultdict(list)
    ref_keys: List[Set[str]] = []

    for index, ref in enumerate(references):
        keys = _reference_identity_keys(ref)
        ref_keys.append(keys)
        for key in keys:
            key_to_indices[key].append(index)

    for indices in key_to_indices.values():
        first = indices[0]
        for other in indices[1:]:
            union(first, other)

    for index, ref in enumerate(references):
        law_name = _normalize_law_name(ref.get("title") or "")
        if not law_name or ref.get("number"):
            continue
        for other_index, other_ref in enumerate(references):
            if index == other_index or not other_ref.get("number"):
                continue
            other_name = _normalize_law_name(other_ref.get("title") or "")
            if law_name == other_name and _titles_compatible(other_ref.get("number"), law_name):
                union(index, other_index)

    groups: Dict[int, List[int]] = defaultdict(list)
    for index in range(len(references)):
        groups[find(index)].append(index)

    group_in_base: Dict[int, bool] = {}
    for group_id, indices in groups.items():
        group_in_base[group_id] = any(
            _reference_matches_index(references[i], indexed_names, indexed_text)
            for i in indices
        )

    reconciled_references: List[Dict] = []
    for index, ref in enumerate(references):
        ref_copy = dict(ref)
        group_id = find(index)
        ref_copy["in_local_base"] = group_in_base[group_id]
        ref_copy["identity_keys"] = sorted(ref_keys[index])
        ref_copy["group_id"] = group_id
        reconciled_references.append(ref_copy)

    found: List[Dict] = []
    missing: List[Dict] = []
    unique_references: List[Dict] = []
    seen_groups: Set[int] = set()

    for index, ref in enumerate(reconciled_references):
        group_id = find(index)
        if group_id in seen_groups:
            continue
        seen_groups.add(group_id)

        group_refs = [reconciled_references[i] for i in groups[group_id]]
        representative = dict(_pick_group_representative(group_refs))
        representative["variants_count"] = len(group_refs)
        representative["match_start"] = min(
            item.get("match_start", 0) for item in group_refs
        )
        representative["in_local_base"] = group_in_base[group_id]
        variant_titles = [
            item.get("title") or item.get("raw") or ""
            for item in group_refs
            if (item.get("title") or item.get("raw"))
        ]
        if len(variant_titles) > 1:
            representative["variant_titles"] = variant_titles

        unique_references.append(representative)
        if group_in_base[group_id]:
            found.append(representative)
        else:
            missing.append(representative)

    unique_references.sort(key=lambda item: item.get("match_start", 0))

    return {
        "references": reconciled_references,
        "unique_references": unique_references,
        "found": found,
        "missing": missing,
        "total_detected": len(references),
        "found_count": len(found),
        "missing_count": len(missing),
        "unique_documents": len(seen_groups),
    }


def save_session_federal_refs_result(result: Dict) -> None:
    """Сохранить результат поиска ссылок для текущей сессии анализа."""
    global _session_federal_refs_result
    _session_federal_refs_result = dict(result)


def get_session_federal_refs_result() -> Optional[Dict]:
    """Получить сохранённый результат поиска ссылок."""
    return _session_federal_refs_result


def clear_session_federal_refs_result() -> None:
    """Очистить сохранённый результат поиска ссылок."""
    global _session_federal_refs_result
    _session_federal_refs_result = None


def find_vnd_file(filename: str = "") -> Path:
    """Найти файл ВНД в папке IN по имени или взять последний загруженный."""
    in_folder = Path(settings.in_folder)
    if not in_folder.exists():
        raise FileNotFoundError(f"Папка IN не найдена: {in_folder}")

    if filename:
        direct = in_folder / Path(filename).name
        if direct.exists() and direct.is_file():
            return direct

        target = filename.lower()
        for candidate in in_folder.iterdir():
            if candidate.is_file() and candidate.name.lower() == target:
                return candidate

    candidates = [
        path for path in in_folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".doc", ".txt", ".md"}
    ]
    if not candidates:
        raise FileNotFoundError("В папке IN нет загруженных документов")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def detect_federal_references_from_file(file_path: str) -> Dict:
    """Извлечь текст из файла ВНД и найти ссылки на федеральные документы."""
    path = Path(file_path)
    if not path.exists():
        return {
            "status": "error",
            "message": f"Файл не найден: {file_path}",
            "references": [],
            "unique_references": [],
            "found_references": [],
            "missing_references": [],
            "found_count": 0,
            "missing_count": 0,
        }

    text = extract_full_text(str(path), apply_vnd_mask=True)
    if not text.strip():
        return {
            "status": "warning",
            "message": "Не удалось извлечь текст из документа",
            "references": [],
            "unique_references": [],
            "found_references": [],
            "missing_references": [],
            "found_count": 0,
            "missing_count": 0,
        }

    references = detect_federal_references(text)
    references = enrich_references_from_context(text, references)
    split = reconcile_references_by_local_base(references)

    result = {
        "status": "success",
        "message": (
            f"Найдено ссылок: {split['total_detected']}; "
            f"уникальных документов: {split['unique_documents']}; "
            f"в локальной базе: {split['found_count']}; "
            f"отсутствует: {split['missing_count']}"
        ),
        "references": split["references"],
        "unique_references": split.get("unique_references") or [],
        "found_references": split["found"],
        "missing_references": split["missing"],
        "found_count": split["found_count"],
        "missing_count": split["missing_count"],
        "total_detected": split["total_detected"],
        "unique_documents": split["unique_documents"],
        "text_length": len(text),
    }
    save_session_federal_refs_result(result)
    return result
