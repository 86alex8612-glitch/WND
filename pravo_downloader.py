"""
Загрузка федеральных документов с портала pravo.gov.ru и добавление в базу ФЗ.
"""
import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import settings

PRAVO_BASE = "http://publication.pravo.gov.ru"
PRAVO_API_BASE = f"{PRAVO_BASE}/api"
PRAVO_PDF_URL = f"{PRAVO_BASE}/file/pdf"
REQUEST_TIMEOUT = 45

DOCUMENT_TYPE_FEDERAL_LAW = "82a8bf1c-3bc7-47ed-827f-7affd43a7f27"
DOCUMENT_TYPE_FEDERAL_CONST_LAW = "93273da3-3133-4acf-96c2-4adc1ae70e19"

FEDERAL_BLOCKS = ["assembly", "government", "president"]

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"pravo_{datetime.now().strftime('%Y%m%d')}.log"

logger = logging.getLogger("pravo_downloader")
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_handler.formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def _api_get(path: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """GET-запрос к API publication.pravo.gov.ru."""
    url = f"{PRAVO_API_BASE}/{path.lstrip('/')}"
    if params:
        encoded = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    encoded.append((key, item))
            else:
                encoded.append((key, value))
        if encoded:
            url = f"{url}?{urllib.parse.urlencode(encoded)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WND-NeuroConsultant/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as exc:
        logger.error("Ошибка запроса к pravo.gov.ru (%s): %s", url, exc)
        return None


def _download_binary(url: str) -> Optional[bytes]:
    """Скачать бинарный файл."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WND-NeuroConsultant/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            content = resp.read()
            if len(content) < 100:
                logger.warning("Слишком маленький файл (%s байт): %s", len(content), url)
                return None
            return content
    except Exception as exc:
        logger.error("Ошибка скачивания %s: %s", url, exc)
        return None


def _sanitize_filename(name: str) -> str:
    """Безопасное имя файла."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] if name else "document"


def _extract_fz_number(ref: Dict) -> Optional[str]:
    number = (ref.get("number") or "").strip()
    if number:
        match = re.search(r"(\d+)", number)
        if match:
            return f"{match.group(1)}-ФЗ"

    raw = (ref.get("raw") or ref.get("title") or ref.get("context_snippet") or "").lower()
    match = re.search(r"(\d+)\s*[-–—]?\s*(?:фз|fz)", raw, re.I)
    if match:
        return f"{match.group(1)}-ФЗ"
    return None


def _extract_document_date(ref: Dict) -> Optional[str]:
    for field in ("document_date", "raw", "title", "context_snippet", "search_query"):
        text = ref.get(field) or ""
        match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", text)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = f"20{year}" if int(year) < 70 else f"19{year}"
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def _normalize_name(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("\n", " ")).strip()


def _is_federal_law_item(item: Dict) -> bool:
    name = _normalize_name(item.get("complexName") or item.get("title") or "")
    number = (item.get("number") or "").upper()
    if "федеральный закон" in name or number.endswith("-ФЗ") or number.endswith("-FZ"):
        return True
    doc_type = item.get("documentTypeId") or ""
    return doc_type in {DOCUMENT_TYPE_FEDERAL_LAW, DOCUMENT_TYPE_FEDERAL_CONST_LAW}


def _is_wrong_document_for_fz(item: Dict) -> bool:
    name = _normalize_name(item.get("complexName") or item.get("title") or "")
    wrong_markers = (
        "постановление правительства",
        "приказ ",
        "распоряжение ",
        "письмо ",
        "указ президента",
    )
    return any(marker in name for marker in wrong_markers)


def _score_candidate(item: Dict, ref: Dict, fz_number: Optional[str]) -> int:
    name = _normalize_name(item.get("complexName") or item.get("title") or "")
    score = 0

    if _is_federal_law_item(item):
        score += 100
    if _is_wrong_document_for_fz(item):
        score -= 200

    if fz_number:
        item_number = (item.get("number") or "").upper().replace(" ", "")
        if item_number == fz_number.upper().replace(" ", ""):
            score += 80
        elif fz_number.split("-")[0] in re.sub(r"[^\d]", "", item_number):
            score += 20

    ref_date = _extract_document_date(ref)
    item_date = (item.get("documentDate") or item.get("publishDateShort") or "")[:10]
    if ref_date:
        if item_date.startswith(ref_date):
            score += 80
        else:
            score -= 50

    ref_keywords = [
        word for word in re.findall(r"[а-яёa-z0-9]{5,}", _normalize_name(ref.get("title", "")))
        if word not in {"федеральный", "закон", "российской", "федерации", "россии"}
    ]
    for word in ref_keywords[:6]:
        if word in name:
            score += 15

    quote_match = re.search(r"[«\"]([^»\"]{6,})[»\"]", ref.get("title") or ref.get("context_snippet") or "")
    if quote_match:
        quote = _normalize_name(quote_match.group(1))
        if quote and quote in name:
            score += 120

    if "кодекс" in _normalize_name(ref.get("title", "")) and "кодекс" in name:
        score += 40

    return score


def _search_documents(params: Dict) -> List[Dict]:
    result = _api_get("Documents", params)
    if not result:
        return []
    return result.get("items") or []


def _pick_best_candidate(candidates: List[Dict], ref: Dict, fz_number: Optional[str]) -> Optional[Dict]:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda item: _score_candidate(item, ref, fz_number),
        reverse=True,
    )
    best = ranked[0]
    if _score_candidate(best, ref, fz_number) <= 0:
        return None
    return best


def _enrich_reference_for_search(ref: Dict) -> Dict:
    """Дополнить ссылку данными из context_snippet перед поиском."""
    enriched = dict(ref)
    context = enriched.get("context_snippet") or ""

    if context and (not enriched.get("number") or not enriched.get("document_date")):
        try:
            from federal_refs import enrich_reference_from_context
            enriched = enrich_reference_from_context(context, enriched)
        except Exception as exc:
            logger.debug("Не удалось обогатить ссылку из контекста: %s", exc)

    return enriched


def _build_search_queries(ref: Dict) -> List[str]:
    """Сформировать список поисковых запросов (от точного к широкому)."""
    queries: List[str] = []

    def add_query(value: Optional[str]) -> None:
        value = re.sub(r"\s+", " ", (value or "").strip())
        if value and len(value) > 4 and value not in queries:
            queries.append(value)

    add_query(ref.get("search_query"))
    add_query(ref.get("title"))

    fz_number = _extract_fz_number(ref)
    ref_date = _extract_document_date(ref)
    if fz_number and ref_date:
        day, month, year = ref_date.split("-")
        add_query(f"Федеральный закон от {int(day)}.{int(month)}.{year} № {fz_number}")
    if fz_number:
        add_query(f"Федеральный закон {fz_number}")

    context = ref.get("context_snippet") or ""
    for pattern in (
        r"Федеральн\w+\s+закон\w*[^.\n]{0,120}",
        r"[Пп]остановление\s+[Пп]равительства[^.\n]{0,120}",
        r"[Уу]каз\s+[Пп]резидента[^.\n]{0,120}",
    ):
        for match in re.finditer(pattern, context, re.IGNORECASE):
            add_query(match.group(0))

    name_match = re.search(r"[«\"]([^»\"]{8,})[»\"]", ref.get("title") or context)
    if name_match:
        add_query(f'Федеральный закон "{name_match.group(1).strip()}"')

    return queries


def _gather_candidates(ref: Dict) -> List[Dict]:
    """Собрать кандидатов на pravo.gov.ru для одного запроса."""
    search_query = ref.get("search_query") or ref.get("title") or ""
    fz_number = _extract_fz_number(ref)
    candidates: List[Dict] = []

    if fz_number or "федеральный закон" in _normalize_name(search_query):
        params_list = [
            {
                "PageSize": 30,
                "DocumentTypes": [DOCUMENT_TYPE_FEDERAL_LAW],
                "Number": fz_number or search_query[:50],
                "NumberSearchType": 0,
            },
        ]
        if fz_number:
            params_list.append({
                "PageSize": 30,
                "DocumentTypes": [DOCUMENT_TYPE_FEDERAL_LAW, DOCUMENT_TYPE_FEDERAL_CONST_LAW],
                "Number": fz_number,
                "NumberSearchType": 0,
            })

        for params in params_list:
            for item in _search_documents(params):
                if not _is_wrong_document_for_fz(item):
                    candidates.append(item)

    if "кодекс" in _normalize_name(search_query):
        code_name = search_query.split("кодекс")[0].strip() or search_query
        for params in (
            {"PageSize": 20, "Name": code_name[:120]},
            {"PageSize": 20, "Name": search_query[:120]},
        ):
            for item in _search_documents(params):
                name = _normalize_name(item.get("complexName") or item.get("title") or "")
                if "кодекс" in name and code_name[:8].lower() in name:
                    candidates.append(item)

    if "конститу" in _normalize_name(search_query):
        for item in _search_documents({"PageSize": 10, "Name": "Конституция Российской Федерации"}):
            candidates.append(item)

    if not candidates:
        for block in FEDERAL_BLOCKS:
            params: Dict = {"PageSize": 10, "Block": block, "Name": search_query[:120]}
            if fz_number:
                params = {
                    "PageSize": 10,
                    "Block": block,
                    "DocumentTypes": [DOCUMENT_TYPE_FEDERAL_LAW],
                    "Number": fz_number,
                    "NumberSearchType": 0,
                }
            for item in _search_documents(params):
                if not _is_wrong_document_for_fz(item):
                    candidates.append(item)

    unique = {}
    for item in candidates:
        eo = item.get("eoNumber")
        if eo:
            unique[eo] = item
    return list(unique.values())


def search_document(ref: Dict) -> Optional[Dict]:
    """Поиск документа на pravo.gov.ru с обогащением и повторными попытками."""
    enriched = _enrich_reference_for_search(ref)
    queries = _build_search_queries(enriched)
    fz_number = _extract_fz_number(enriched)

    logger.info(
        "Поиск документа: title=%s, number=%s, queries=%s",
        enriched.get("title"),
        fz_number or enriched.get("number"),
        len(queries),
    )

    all_candidates: List[Dict] = []
    for attempt, query in enumerate(queries, start=1):
        search_ref = dict(enriched)
        search_ref["search_query"] = query
        logger.info("Попытка поиска %s/%s: %s", attempt, len(queries), query[:120])
        candidates = _gather_candidates(search_ref)
        all_candidates.extend(candidates)

        unique = {}
        for item in all_candidates:
            eo = item.get("eoNumber")
            if eo:
                unique[eo] = item

        best = _pick_best_candidate(list(unique.values()), enriched, fz_number)
        if best:
            logger.info(
                "Найден документ (попытка %s): %s | eo=%s",
                attempt,
                (best.get("complexName") or best.get("title") or "")[:120].replace("\n", " "),
                best.get("eoNumber"),
            )
            return best

    logger.warning(
        "Документ не найден на pravo.gov.ru после %s попыток: %s",
        len(queries),
        enriched.get("title") or enriched.get("search_query"),
    )
    return None


def download_document_pdf(eo_number: str, save_path: Path) -> bool:
    """Скачать PDF документа по номеру электронного опубликования."""
    url = f"{PRAVO_PDF_URL}?eoNumber={eo_number}"
    logger.info("Скачивание PDF: %s -> %s", url, save_path.name)
    content = _download_binary(url)
    if not content:
        return False

    if not content[:4].startswith(b"%PDF"):
        logger.error("Файл не является PDF: %s", url)
        return False

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)
    logger.info("PDF сохранён: %s (%s байт)", save_path, len(content))
    return True


def _get_fz_store():
    from vector_store import init_vector_stores, fz_store as fz_store_ref
    init_vector_stores()
    return fz_store_ref


def _get_bases_info() -> Dict:
    from vector_store import init_vector_stores
    return init_vector_stores()


def _is_file_indexed_in_fz(filename: str) -> bool:
    fz_store_ref = _get_fz_store()
    if not fz_store_ref or not filename:
        return False
    try:
        all_results = fz_store_ref.collection.get()
        for metadata in (all_results or {}).get("metadatas") or []:
            if metadata and metadata.get("filename") == filename:
                return True
    except Exception as exc:
        logger.warning("Не удалось проверить индекс ФЗ: %s", exc)
    return False


def _delete_file_from_fz_index(filename: str) -> None:
    fz_store_ref = _get_fz_store()
    if not fz_store_ref or not filename:
        return
    try:
        all_results = fz_store_ref.collection.get()
        ids_to_delete = []
        for idx, metadata in enumerate((all_results or {}).get("metadatas") or []):
            if metadata and metadata.get("filename") == filename:
                ids_to_delete.append(all_results["ids"][idx])
        if ids_to_delete:
            fz_store_ref.collection.delete(ids=ids_to_delete)
            logger.info("Удалены старые чанки для %s: %s шт.", filename, len(ids_to_delete))
    except Exception as exc:
        logger.warning("Не удалось удалить старые чанки %s: %s", filename, exc)


def _create_metadata_text_file(pdf_path: Path, doc: Dict) -> Path:
    """Создать текстовый файл с метаданными, если PDF без текстового слоя."""
    txt_path = pdf_path.with_suffix(".txt")
    parts = [
        (doc.get("complexName") or "").replace("\n", " ").strip(),
        (doc.get("name") or "").replace("\n", " ").strip(),
        (doc.get("title") or "").replace("<br />", " ").replace("\n", " ").strip(),
    ]
    if doc.get("number"):
        parts.append(f"Номер: {doc.get('number')}")
    if doc.get("documentDate"):
        parts.append(f"Дата документа: {doc.get('documentDate')}")
    if doc.get("publishDateShort"):
        parts.append(f"Дата опубликования: {doc.get('publishDateShort')}")

    text = "\n\n".join(part for part in parts if part and part.strip())
    if len(text) < 40:
        text = f"{text}\n\nФедеральный документ {pdf_path.stem}"

    txt_path.write_text(text, encoding="utf-8")
    logger.info("Создан текстовый файл для индексации: %s", txt_path.name)
    return txt_path


def _index_fz_document(file_path: Path, doc: Optional[Dict] = None) -> Dict:
    """Проиндексировать файл в базу ФЗ, с fallback на .txt при пустом PDF."""
    from document_loader import process_single_file, load_pdf

    fz_store_ref = _get_fz_store()
    if not fz_store_ref:
        return {"status": "error", "message": "Векторная база ФЗ не инициализирована", "total_chunks": 0}

    _delete_file_from_fz_index(file_path.name)

    index_result = process_single_file(str(file_path), fz_store_ref, "fz")
    if index_result.get("status") == "success" and index_result.get("total_chunks", 0) > 0:
        return index_result

    if file_path.suffix.lower() == ".pdf" and doc:
        try:
            pdf_chunks = load_pdf(str(file_path))
        except Exception:
            pdf_chunks = []
        if not pdf_chunks:
            txt_path = _create_metadata_text_file(file_path, doc)
            _delete_file_from_fz_index(txt_path.name)
            return process_single_file(str(txt_path), fz_store_ref, "fz")

    return index_result


def download_and_index_reference(ref: Dict) -> Dict:
    """Скачать один федеральный документ и добавить в базу ФЗ."""
    title = ref.get("title") or ref.get("search_query") or "Документ"
    result: Dict = {
        "title": title,
        "status": "error",
        "message": "",
        "filename": None,
        "chunks": 0,
    }

    doc = search_document(ref)
    if not doc:
        result["message"] = "Документ не найден на pravo.gov.ru"
        logger.error("%s -> %s", title, result["message"])
        return result

    eo_number = doc.get("eoNumber")
    complex_name = doc.get("complexName") or doc.get("title") or title
    if not eo_number:
        result["message"] = "Не получен номер электронного опубликования"
        logger.error("%s -> %s", title, result["message"])
        return result

    fz_folder = Path(settings.fz_folder)
    fz_folder.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_filename(complex_name.split("\n")[0])
    pdf_path = fz_folder / f"{safe_name}.pdf"
    txt_path = pdf_path.with_suffix(".txt")

    already_indexed = _is_file_indexed_in_fz(pdf_path.name) or _is_file_indexed_in_fz(txt_path.name)

    if pdf_path.exists() and already_indexed:
        result["status"] = "exists"
        result["message"] = "Документ уже есть в базе ФЗ"
        result["filename"] = pdf_path.name if _is_file_indexed_in_fz(pdf_path.name) else txt_path.name
        result["eo_number"] = eo_number
        result["chunks"] = 0
        logger.info("%s уже проиндексирован: %s", title, result["filename"])
        return result

    if not pdf_path.exists():
        if not download_document_pdf(eo_number, pdf_path):
            result["message"] = "Не удалось скачать PDF с pravo.gov.ru"
            logger.error("%s -> %s (eo=%s)", title, result["message"], eo_number)
            return result
    elif not already_indexed:
        logger.info("%s: PDF уже на диске, но не в векторной базе — индексация", title)

    index_result = _index_fz_document(pdf_path, doc)
    chunks = index_result.get("total_chunks", 0) or 0

    if index_result.get("status") == "success" and chunks > 0:
        indexed_name = index_result.get("filename") or pdf_path.name
        result["status"] = "success"
        result["message"] = f"Документ добавлен в базу ФЗ ({chunks} чанков)"
        result["filename"] = indexed_name
        result["eo_number"] = eo_number
        result["chunks"] = chunks
        logger.info("%s успешно добавлен в базу ФЗ (%s чанков)", title, chunks)
    else:
        result["status"] = "error"
        result["message"] = index_result.get("message") or "Не удалось добавить документ в базу ФЗ"
        result["filename"] = pdf_path.name
        result["chunks"] = 0
        logger.error("%s -> %s", title, result["message"])

    return result


def download_and_index_references(references: List[Dict]) -> Dict:
    """Скачать список федеральных документов."""
    logger.info("=" * 60)
    logger.info("Старт загрузки федеральных документов: %s шт.", len(references or []))
    logger.info("Лог файл: %s", LOG_FILE)

    bases_before = _get_bases_info()
    fz_before = (bases_before.get("fz") or {}).get("count", 0)

    if not references:
        return {
            "status": "error",
            "message": "Список документов пуст",
            "downloaded": [],
            "failed": [],
            "log_file": str(LOG_FILE),
            "bases_info": bases_before,
            "fz_chunks_before": fz_before,
            "fz_chunks_added": 0,
        }

    downloaded = []
    failed = []
    total_chunks_added = 0

    for ref in references:
        item_result = download_and_index_reference(ref)
        if item_result["status"] in ("success", "exists"):
            downloaded.append(item_result)
            total_chunks_added += item_result.get("chunks") or 0
        else:
            failed.append(item_result)

    bases_after = _get_bases_info()
    fz_after = (bases_after.get("fz") or {}).get("count", 0)
    chunks_delta = max(0, fz_after - fz_before)

    all_ok = len(failed) == 0 and len(downloaded) > 0
    any_ok = len(downloaded) > 0 and (total_chunks_added > 0 or chunks_delta > 0 or any(
        item.get("status") == "exists" for item in downloaded
    ))

    if all_ok and (total_chunks_added > 0 or chunks_delta > 0 or any(
        item.get("status") == "exists" for item in downloaded
    )):
        status = "success"
        message = f"Документы подкачены. База ФЗ: {fz_after} чанков (+{chunks_delta})"
    elif any_ok:
        status = "partial"
        message = f"Часть документов подкачена. База ФЗ: {fz_after} чанков (+{chunks_delta})"
    else:
        status = "error"
        message = "Актуальные документы скачать не удалось. Добавьте их вручную"

    logger.info(
        "Загрузка завершена: успешно=%s, ошибок=%s, статус=%s, чанков было=%s, стало=%s",
        len(downloaded),
        len(failed),
        status,
        fz_before,
        fz_after,
    )
    for item in failed:
        logger.error("Не загружен: %s -> %s", item.get("title"), item.get("message"))

    return {
        "status": status,
        "message": message,
        "downloaded": downloaded,
        "failed": failed,
        "total": len(references),
        "success_count": len(downloaded),
        "failed_count": len(failed),
        "log_file": str(LOG_FILE),
        "bases_info": bases_after,
        "fz_chunks_before": fz_before,
        "fz_chunks_after": fz_after,
        "fz_chunks_added": chunks_delta,
    }
