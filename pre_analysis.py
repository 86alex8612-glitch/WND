"""
Этап 1 анализа ВНД: сфера деятельности, форма собственности, области законодательства.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from openai import OpenAI
from config import settings

ACTIVITY_SPHERES = [
    "Производство",
    "Торговля",
    "Услуги",
    "Финансы",
    "Строительство",
    "Сельское хозяйство",
    "Информационные технологии (IT)",
    "Посредническая деятельность",
    "Образовательные услуги",
    "Медицинские услуги",
    "Другое",
]

OWNERSHIP_FORMS = [
    "Государственные предприятия",
    "Частные компании",
    "Предприятия со смешанной формой собственности",
]

LEGAL_AREA_OPTIONS = [
    "Персональные данные",
    "Информационная безопасность",
    "Безопасность финансовых (банковских) операций",
    "Трудовое законодательство",
    "Противодействие коррупции",
    "Коммерческая тайна",
    "Государственная тайна",
    "Образовательная деятельность",
    "Медицинская деятельность",
    "Закупки и контрактная система",
    "Другое",
]

# Документы/темы, применимые только к указанным сферам деятельности
SPHERE_RESTRICTED_KEYWORDS = {
    "57580": ["Финансы"],
    "безопасность финансовых": ["Финансы"],
    "банковск": ["Финансы"],
    "395-1": ["Финансы"],
    "161-фз": ["Финансы"],
    "национальн": ["Финансы"],  # 161-ФЗ НПС
}

SPHERE_TO_LEGAL_AREAS = {
    "Финансы": ["Безопасность финансовых (банковских) операций", "Информационная безопасность", "Персональные данные"],
    "Информационные технологии (IT)": ["Информационная безопасность", "Персональные данные", "Коммерческая тайна"],
    "Образовательные услуги": ["Образовательная деятельность", "Персональные данные", "Информационная безопасность"],
    "Медицинские услуги": ["Медицинская деятельность", "Персональные данные", "Информационная безопасность"],
}

FILENAME_SPHERE_HINTS = {
    "банк": "Финансы",
    "финанс": "Финансы",
    "кредит": "Финансы",
    "it": "Информационные технологии (IT)",
    "информацион": "Информационные технологии (IT)",
    "иб": "Информационные технологии (IT)",
    "bezopas": "Информационные технологии (IT)",
    "безопас": "Информационная безопасность",
    "персональн": "Персональные данные",
    "пдн": "Персональные данные",
    "152": "Персональные данные",
    "образован": "Образовательные услуги",
    "медицин": "Медицинские услуги",
    "труд": "Трудовое законодательство",
    "закуп": "Закупки и контрактная система",
}

FILENAME_LEGAL_HINTS = {
    "персональн": "Персональные данные",
    "пдн": "Персональные данные",
    "152": "Персональные данные",
    "информацион": "Информационная безопасность",
    "иб": "Информационная безопасность",
    "57580": "Безопасность финансовых (банковских) операций",
    "банк": "Безопасность финансовых (банковских) операций",
    "труд": "Трудовое законодательство",
    "коррупц": "Противодействие коррупции",
    "коммерческ": "Коммерческая тайна",
    "гостайн": "Государственная тайна",
    "образован": "Образовательная деятельность",
    "медицин": "Медицинская деятельность",
    "закуп": "Закупки и контрактная система",
    "223": "Закупки и контрактная система",
    "44-фз": "Закупки и контрактная система",
}

# Базовый перечень применимых ФНД по областям законодательства (этап 1)
LEGAL_AREA_FND_BASE: Dict[str, List[Dict[str, object]]] = {
    "Персональные данные": [
        {
            "title": "Федеральный закон № 152-ФЗ «О персональных данных»",
            "number": "152-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 3", "ст. 5", "ст. 6", "ст. 9", "ст. 18.1", "ст. 19", "ст. 22"],
            "reason": "Базовый ФНД для ВНД по обработке персональных данных",
        },
        {
            "title": "Постановление Правительства РФ № 1119 «Об утверждении требований к защите персональных данных»",
            "number": "1119",
            "type": "Постановление",
            "role": "дополнительный",
            "key_articles": ["требования к уровню защищённости ПДн"],
            "reason": "Подзаконные требования к защите ПДн",
        },
    ],
    "Информационная безопасность": [
        {
            "title": "Федеральный закон № 149-ФЗ «Об информации, информационных технологиях и о защите информации»",
            "number": "149-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 10", "ст. 16", "ст. 19"],
            "reason": "Общие требования к защите информации",
        },
        {
            "title": "Федеральный закон № 187-ФЗ «О безопасности критической информационной инфраструктуры»",
            "number": "187-ФЗ",
            "type": "ФЗ",
            "role": "дополнительный",
            "key_articles": ["ст. 6", "ст. 10", "ст. 11"],
            "reason": "При наличии значимых объектов КИИ",
        },
    ],
    "Безопасность финансовых (банковских) операций": [
        {
            "title": "ГОСТ Р 57580.1-2017 «Защита информации финансовых организаций»",
            "number": "57580.1-2017",
            "type": "ГОСТ",
            "role": "основной",
            "key_articles": ["разделы о мерах защиты информации"],
            "reason": "Отраслевой стандарт для финансовых организаций",
        },
        {
            "title": "ГОСТ Р 57580.2-2018 «Методика оценки соответствия»",
            "number": "57580.2-2018",
            "type": "ГОСТ",
            "role": "дополнительный",
            "key_articles": ["методика оценки соответствия"],
            "reason": "Оценка соответствия требованиям 57580.1",
        },
        {
            "title": "Федеральный закон № 161-ФЗ «О национальной платёжной системе»",
            "number": "161-ФЗ",
            "type": "ФЗ",
            "role": "дополнительный",
            "key_articles": ["ст. 27", "ст. 28"],
            "reason": "При осуществлении платёжной деятельности",
        },
    ],
    "Трудовое законодательство": [
        {
            "title": "Трудовой кодекс РФ",
            "number": "ТК РФ",
            "type": "Кодекс",
            "role": "основной",
            "key_articles": ["ст. 16", "ст. 22", "ст. 81", "ст. 209", "ст. 212"],
            "reason": "Базовый ФНД для локальных нормативных актов по труду",
        },
    ],
    "Противодействие коррупции": [
        {
            "title": "Федеральный закон № 273-ФЗ «О противодействии коррупции»",
            "number": "273-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 8", "ст. 13"],
            "reason": "Антикоррупционные требования к ВНД",
        },
    ],
    "Коммерческая тайна": [
        {
            "title": "Федеральный закон № 98-ФЗ «О коммерческой тайне»",
            "number": "98-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 4", "ст. 5", "ст. 10"],
            "reason": "Режим коммерческой тайны",
        },
    ],
    "Государственная тайна": [
        {
            "title": "Закон РФ № 5485-1 «О государственной тайне»",
            "number": "5485-1",
            "type": "Закон",
            "role": "основной",
            "key_articles": ["ст. 12", "ст. 20"],
            "reason": "Режим государственной тайны",
        },
    ],
    "Образовательная деятельность": [
        {
            "title": "Федеральный закон № 273-ФЗ «Об образовании в РФ»",
            "number": "273-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 28", "ст. 41", "ст. 43"],
            "reason": "Локальные акты образовательной организации",
        },
    ],
    "Медицинская деятельность": [
        {
            "title": "Федеральный закон № 323-ФЗ «Об основах охраны здоровья граждан»",
            "number": "323-ФЗ",
            "type": "ФЗ",
            "role": "основной",
            "key_articles": ["ст. 13", "ст. 79", "ст. 80"],
            "reason": "ВНД медицинской организации",
        },
    ],
    "Закупки и контрактная система": [
        {
            "title": "Федеральный закон № 44-ФЗ «О контрактной системе»",
            "number": "44-ФЗ",
            "type": "ФЗ",
            "role": "дополнительный",
            "key_articles": ["ст. 2", "ст. 33", "ст. 34"],
            "reason": "Для заказчиков по 44-ФЗ",
        },
        {
            "title": "Федеральный закон № 223-ФЗ «О закупках отдельными видами юридических лиц»",
            "number": "223-ФЗ",
            "type": "ФЗ",
            "role": "дополнительный",
            "key_articles": ["ст. 2", "ст. 4"],
            "reason": "Для заказчиков по 223-ФЗ",
        },
    ],
}


def _match_from_hints(text: str, hints: Dict[str, str]) -> Optional[str]:
    lower = (text or "").lower()
    for key, value in hints.items():
        if key in lower:
            return value
    return None


def _guess_ownership(text: str) -> Optional[str]:
    lower = (text or "").lower()
    if any(w in lower for w in ("государствен", "бюджет", "федеральн", "муниципаль", "гку", "фгбу")):
        return "Государственные предприятия"
    if any(w in lower for w in ("ооо", "ао", "пао", "зао", "частн", "коммерческ")):
        return "Частные компании"
    if "смешан" in lower:
        return "Предприятия со смешанной формой собственности"
    return None


def _guess_legal_areas(text: str) -> List[str]:
    lower = (text or "").lower()
    found = []
    for key, area in FILENAME_LEGAL_HINTS.items():
        if key in lower and area not in found:
            found.append(area)
    return found


def _llm_detect(filename: str, vnd_name: str, excerpt: str) -> dict:
    if not settings.openai_api_key or not excerpt.strip():
        return {}

    prompt = f"""Проанализируй внутренний нормативный документ и верни JSON.
Название файла: {filename}
Название документа: {vnd_name}
Фрагмент текста:
{excerpt[:4000]}

Поля JSON (строго):
{{
  "activity_sphere": одно из {json.dumps(ACTIVITY_SPHERES, ensure_ascii=False)} или null,
  "ownership_form": одно из {json.dumps(OWNERSHIP_FORMS, ensure_ascii=False)} или null,
  "legal_areas": массив строк из {json.dumps(LEGAL_AREA_OPTIONS, ensure_ascii=False)},
  "confidence": {{"activity_sphere": 0.0-1.0, "ownership_form": 0.0-1.0, "legal_areas": 0.0-1.0}}
}}

Если данных недостаточно — null и низкая confidence."""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON без markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        return json.loads(raw)
    except Exception:
        return {}


def _fnd_dedupe_key(item: dict) -> str:
    number = str(item.get("number") or "").strip().lower()
    title = str(item.get("title") or "").strip().lower()
    return number or title


def _merge_fnd_lists(*lists: List[dict]) -> List[dict]:
    merged: List[dict] = []
    seen = set()
    for items in lists:
        for item in items or []:
            if not isinstance(item, dict):
                continue
            key = _fnd_dedupe_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _heuristic_applicable_fnd(stage1: dict, combined_text: str) -> List[dict]:
    """Базовый перечень ФНД по областям законодательства и сфере деятельности."""
    items: List[dict] = []
    for area in stage1.get("legal_areas") or []:
        for entry in LEGAL_AREA_FND_BASE.get(area, []):
            items.append(dict(entry))

    sphere = stage1.get("activity_sphere") or ""
    lower = (combined_text or "").lower()
    if sphere == "Финансы" or "безопасность финансовых" in (stage1.get("legal_areas") or []):
        for entry in LEGAL_AREA_FND_BASE.get("Безопасность финансовых (банковских) операций", []):
            items.append(dict(entry))
        if any(k in lower for k in ("банк", "кредит", "платёж", "платеж", "нпс")):
            items.append(
                {
                    "title": "Федеральный закон № 395-1 «О банках и банковской деятельности»",
                    "number": "395-1",
                    "type": "ФЗ",
                    "role": "дополнительный",
                    "key_articles": ["ст. 56", "ст. 57"],
                    "reason": "Банковская деятельность",
                }
            )
    return _merge_fnd_lists(items)


def _llm_detect_applicable_fnd(stage1: dict, filename: str, vnd_name: str, excerpt: str) -> List[dict]:
    """Уточнить перечень применимых ФНД с помощью LLM."""
    if not settings.openai_api_key or not excerpt.strip():
        return []

    areas = ", ".join(stage1.get("legal_areas") or [])
    prompt = f"""Определи федеральные нормативные документы (ФНД), которые должны быть применены
при создании и правовом анализе данного внутреннего нормативного документа (ВНД).

Название файла: {filename}
Название документа: {vnd_name}
Сфера деятельности: {stage1.get('activity_sphere') or 'не указана'}
Форма собственности: {stage1.get('ownership_form') or 'не указана'}
Области законодательства: {areas}

Фрагмент текста ВНД:
{excerpt[:3500]}

Верни JSON:
{{
  "applicable_fnd": [
    {{
      "title": "полное название ФНД",
      "number": "номер (152-ФЗ, 57580.1-2017 и т.д.) или пустая строка",
      "type": "ФЗ|ГОСТ|Постановление|Положение ЦБ|Кодекс|Закон",
      "role": "основной|дополнительный",
      "key_articles": ["ст. 5", "ст. 6"],
      "reason": "краткое обоснование применимости к теме ВНД"
    }}
  ]
}}

Включи основной ФЗ по теме документа и все дополнительные применимые ФНД, ГОСТ, постановления, положения ЦБ.
Укажи конкретные статьи/пункты, которые должны быть отражены в ВНД."""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON без markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        data = json.loads(raw)
        result = []
        for item in data.get("applicable_fnd") or []:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            articles = item.get("key_articles") or []
            if isinstance(articles, str):
                articles = [articles]
            result.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "number": str(item.get("number") or "").strip(),
                    "type": str(item.get("type") or "ФНД").strip(),
                    "role": str(item.get("role") or "дополнительный").strip(),
                    "key_articles": [str(a).strip() for a in articles if str(a).strip()],
                    "reason": str(item.get("reason") or "").strip(),
                }
            )
        return result
    except Exception:
        return []


def detect_applicable_fnd(stage1: dict, filename: str, vnd_name: str, vnd_text: str) -> List[dict]:
    """Определить ФНД, применимые при создании и анализе данного ВНД."""
    combined = f"{filename} {vnd_name} {vnd_text[:3000]}"
    base = _heuristic_applicable_fnd(stage1, combined)
    llm_items = _llm_detect_applicable_fnd(stage1, filename, vnd_name, vnd_text)
    return _merge_fnd_lists(base, llm_items)


def format_applicable_fnd_context(fnd_list: List[dict]) -> str:
    """Текст перечня ФНД для промпта анализа."""
    if not fnd_list:
        return "Применимые ФНД: не определены автоматически — определи их по теме ВНД.\n"

    lines = ["=== ПРИМЕНИМЫЕ ФНД (обязательная база для анализа) ==="]
    for index, item in enumerate(fnd_list, start=1):
        articles = ", ".join(item.get("key_articles") or []) or "—"
        lines.append(
            f"{index}. [{item.get('role', 'ФНД')}] {item.get('title', '')}"
            + (f" ({item.get('number')})" if item.get("number") else "")
            + f" — релевантные статьи/пункты: {articles}"
        )
        if item.get("reason"):
            lines.append(f"   Обоснование: {item['reason']}")
    lines.append(
        "ОБЯЗАТЕЛЬНО проверь отражение требований каждого ФНД в тексте ВНД. "
        "В отчёте укажи, какие ФНД и какие статьи/пункты не учтены или учтены частично."
    )
    return "\n".join(lines) + "\n"


def detect_stage1(filename: str, vnd_name: str, vnd_text: str) -> dict:
    """Определить параметры этапа 1 из названия и текста документа."""
    combined = f"{filename} {vnd_name} {vnd_text[:3000]}"

    activity = _match_from_hints(combined, FILENAME_SPHERE_HINTS)
    ownership = _guess_ownership(combined)
    legal_areas = _guess_legal_areas(combined)

    llm = _llm_detect(filename, vnd_name, vnd_text)
    conf = llm.get("confidence") or {}

    if llm.get("activity_sphere") in ACTIVITY_SPHERES:
        if conf.get("activity_sphere", 0) >= 0.55 or not activity:
            activity = llm["activity_sphere"]

    if llm.get("ownership_form") in OWNERSHIP_FORMS:
        if conf.get("ownership_form", 0) >= 0.55 or not ownership:
            ownership = llm["ownership_form"]

    for area in llm.get("legal_areas") or []:
        if area in LEGAL_AREA_OPTIONS and area not in legal_areas:
            legal_areas.append(area)

    if activity and activity in SPHERE_TO_LEGAL_AREAS:
        for area in SPHERE_TO_LEGAL_AREAS[activity]:
            if area not in legal_areas:
                legal_areas.append(area)

    needs_user = []
    if not activity:
        needs_user.append("activity_sphere")
    if not ownership:
        needs_user.append("ownership_form")
    if not legal_areas:
        needs_user.append("legal_areas")

    stage1_draft = {
        "activity_sphere": activity or "Другое",
        "ownership_form": ownership or "Частные компании",
        "legal_areas": legal_areas or ["Другое"],
    }
    applicable_fnd = detect_applicable_fnd(stage1_draft, filename, vnd_name, vnd_text)

    return {
        "activity_sphere": activity,
        "ownership_form": ownership,
        "legal_areas": legal_areas,
        "needs_user_input": needs_user,
        "detected_from_document": bool(activity or ownership or legal_areas),
        "applicable_fnd": applicable_fnd,
        "options": {
            "activity_spheres": ACTIVITY_SPHERES,
            "ownership_forms": OWNERSHIP_FORMS,
            "legal_areas": LEGAL_AREA_OPTIONS,
        },
    }


LOWER_LEVEL_DOCUMENT_OPTIONS = {
    "provisions": "Положения",
    "regulations": "Регламенты",
    "appointment_orders": "Приказы о назначении ответственных лиц",
    "instructions": "Инструкции",
}


def normalize_stage1_answers(data: dict) -> dict:
    """Проверить и нормализовать ответы пользователя этапа 1."""
    activity = data.get("activity_sphere")
    ownership = data.get("ownership_form")
    legal_areas = data.get("legal_areas") or []

    if activity and activity not in ACTIVITY_SPHERES:
        activity = "Другое"
    if ownership and ownership not in OWNERSHIP_FORMS:
        ownership = "Частные компании"

    normalized_areas = []
    for area in legal_areas:
        if area in LEGAL_AREA_OPTIONS and area not in normalized_areas:
            normalized_areas.append(area)
    if not normalized_areas:
        normalized_areas = ["Другое"]

    raw_lower = data.get("lower_level_documents") or []
    lower_level_documents = []
    if isinstance(raw_lower, list):
        for item in raw_lower:
            key = str(item).strip()
            if key in LOWER_LEVEL_DOCUMENT_OPTIONS and key not in lower_level_documents:
                lower_level_documents.append(key)

    return {
        "activity_sphere": activity or "Другое",
        "ownership_form": ownership or "Частные компanies",
        "legal_areas": normalized_areas,
        "lower_level_documents": lower_level_documents,
        "applicable_fnd": data.get("applicable_fnd") or [],
    }


def format_stage1_context(stage1: dict) -> str:
    areas = ", ".join(stage1.get("legal_areas") or [])
    raw_lower = stage1.get("lower_level_documents") or []
    if raw_lower:
        lower_labels = ", ".join(LOWER_LEVEL_DOCUMENT_OPTIONS.get(k, k) for k in raw_lower)
        lower_line = f"Документы нижнего уровня, принятые в организации: {lower_labels}\n"
    else:
        lower_line = (
            "Документы нижнего уровня, принятые в организации: не указаны "
            "(при анализе иерархии ВНД учитывай, что детализация может отсутствовать)\n"
        )
    return (
        f"Сфера деятельности: {stage1.get('activity_sphere', 'не указана')}\n"
        f"Форма собственности: {stage1.get('ownership_form', 'не указана')}\n"
        f"Области законодательства для анализа: {areas}\n"
        f"{lower_line}"
        "При анализе учитывай только нормы, относящиеся к указанным областям и сфере деятельности. "
        "Не применяй отраслевые требования (например, ГОСТ 57580), если они не соответствуют сфере. "
        "Учитывай иерархию ВНД: оценивай документ отдельно по его уровню; требования вне зоны — перечисляй "
        "для проверки в иных ВНД (по отмеченным типам документов этапа 1) с указанием конкретных п.п./подп. ФНД.\n"
        + format_applicable_fnd_context(stage1.get("applicable_fnd") or [])
    )


def is_law_document_relevant(filename: str, document_text: str, stage1: dict) -> bool:
    """Фильтр применимости найденного фрагмента закона/ГОСТ к параметрам этапа 1."""
    if not stage1:
        return True

    sphere = stage1.get("activity_sphere", "")
    legal_areas = stage1.get("legal_areas") or []
    combined = f"{filename} {document_text[:400]}".lower()

    for keyword, allowed_spheres in SPHERE_RESTRICTED_KEYWORDS.items():
        if keyword in combined and sphere not in allowed_spheres:
            if "Безопасность финансовых (банковских) операций" not in legal_areas:
                return False

    if "57580" in combined:
        if sphere != "Финансы" and "Безопасность финансовых (банковских) операций" not in legal_areas:
            return False

    return True
