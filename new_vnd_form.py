"""
Справочники и нормализация формы «Создать новый» ВНД.
"""
from __future__ import annotations

from typing import Dict, List, Optional

LEGAL_AREAS = [
    {
        "id": "corporate",
        "label": "Корпоративное право",
        "examples": "Устав, Положение о Генеральном директоре; Положение о Совете директоров, Акционерное соглашение",
    },
    {
        "id": "personal_data",
        "label": "Персональные данные (152-ФЗ)",
        "examples": "Политика обработки ПДн, Согласие на обработку; Модель угроз ПДн, Положение об уничтожении ПДн",
    },
    {
        "id": "confidentiality_ib",
        "label": "Конфиденциальность и ИБ",
        "examples": "Положение о коммерческой тайне + NDA; Политика ИБ, Регламент реагирования на инциденты",
    },
    {
        "id": "labor",
        "label": "Трудовые отношения (ТК РФ)",
        "examples": "ПВТР, Положение об оплате труда; Положение об удаленной работе, KPI, Ученические договоры",
    },
    {
        "id": "contracts_procurement",
        "label": "Договоры и Закупки",
        "examples": "Стандартные формы договоров; Положение о закупках (223-ФЗ), Регламент проверки контрагентов",
    },
    {
        "id": "finance_risks",
        "label": "Финансы и Риски",
        "examples": "Учетная политика (БУ и НУ); Кредитная/Депозитная политика, Положение об управлении рисками",
    },
    {
        "id": "compliance_ethics",
        "label": "Комплаенс и Этика",
        "examples": "Антикоррупционная политика; Правила ПОД/ФТ (115-ФЗ), Кодекс деловой этики",
    },
    {"id": "custom", "label": "Указать своё", "examples": "", "custom": True},
]

ACTIVITY_SPHERES = [
    {
        "id": "finance",
        "label": "Финансовый сектор",
        "description": "Отраслевой регулятор: Банк России (ЦБ РФ). Максимальные требования к ВНД, рискам и ИБ.",
    },
    {
        "id": "it_telecom",
        "label": "IT, Телеком и Высокие технологии",
        "description": "Регуляторы: Минцифры, Роскомнадзор, ФСТЭК, ФСБ. Фокус на ИБ и персональные данные.",
    },
    {
        "id": "trade_services",
        "label": "Торговля и Услуги (B2C и B2B)",
        "description": "Регуляторы: Роспотребнадзор, ФНС. Фокус на права потребителей, трудовое право и договоры.",
    },
    {
        "id": "manufacturing",
        "label": "Производство и Промышленность",
        "description": "Регуляторы: Ростехнадзор, Росприроднадзор, ГИТ. Фокус на охрану труда, экологию и ГОСТы.",
    },
    {
        "id": "construction_realestate",
        "label": "Строительство и Недвижимость",
        "description": "Регуляторы: Минстрой, СРО, Росреестр.",
    },
    {
        "id": "social",
        "label": "Социально-значимые сферы",
        "description": "Регуляторы: Минздрав, Минпросвещения, Рособрнадзор. Требуются обязательные лицензии.",
    },
]

OWNERSHIP_FORMS = [
    {"group": "Коммерческие организации", "options": [
        "ООО (Общество с ограниченной ответственностью)",
        "АО (Непубличное) (Акционерное общество)",
        "ПАО (Публичное акционерное общество)",
        "ИП (Индивидуальный предприниматель)",
        "Производственные кооперативы / Артели",
    ]},
    {"group": "Некоммерческие организации (НКО)", "options": [
        "Фонды (Благотворительные, общественные)",
        "Ассоциации и союзы (Объединения бизнесов)",
        "Автономные некоммерческие организации (АНО)",
        "Потребительские кооперативы (Включая КПК в финансовом секторе)",
    ]},
    {"group": "Государственный и муниципальный сектор", "options": [
        "Федеральные органы государственной власти",
        "Органы государственной власти субъектов РФ",
        "Органы местного самоуправления (муниципальные органы)",
    ]},
]

TARGET_AUDIENCES = [
    {"id": "all_employees", "label": "Для всех сотрудников"},
    {"id": "managers", "label": "Для руководителей структурных подразделений"},
    {"id": "clients", "label": "Клиентов"},
    {"id": "employees_clients", "label": "Все сотрудники и клиенты"},
    {"id": "custom", "label": "Указать своё", "custom": True},
]

ORG_BRAND_NAME = "DialogAI"


def build_organization_name(ownership_form: str) -> str:
    """Наименование организации для текста ВНД: форма собственности + DialogAI."""
    form = (ownership_form or "").strip()
    brand = ORG_BRAND_NAME

    if form.startswith("ООО"):
        return f"ООО «{brand}»"
    if form.startswith("ПАО"):
        return f"ПАО «{brand}»"
    if form.startswith("АО"):
        return f"АО «{brand}»"
    if form.startswith("ИП"):
        return f"ИП {brand}"
    if "кооператив" in form.lower() or "Артел" in form:
        return f"Производственный кооператив «{brand}»"
    if form.startswith("Фонды"):
        return f"Фонд «{brand}»"
    if form.startswith("Ассоциации"):
        return f"Ассоциация «{brand}»"
    if form.startswith("Автономные"):
        return f"АНО «{brand}»"
    if form.startswith("Потребительские"):
        return f"Потребительский кооператив «{brand}»"
    if form.startswith("Федеральные"):
        return f"Федеральный орган государственной власти «{brand}»"
    if form.startswith("Органы государственной власти субъектов"):
        return f"Орган государственной власти субъекта РФ «{brand}»"
    if form.startswith("Органы местного самоуправления"):
        return f"Орган местного самоуправления «{brand}»"

    prefix = form.split("(")[0].strip() if form else "ООО"
    if len(prefix) > 40:
        prefix = "ООО"
    return f"{prefix} «{brand}»"


REQUIRED_FIELDS = [
    "document_name",
    "document_topic",
    "legal_area",
    "activity_sphere",
    "ownership_form",
    "state_secret",
    "employees_count",
    "branches",
    "target_audience",
]


def get_new_vnd_form_options() -> dict:
    from new_vnd_followup import get_followup_options_for_api

    return {
        "legal_areas": LEGAL_AREAS,
        "activity_spheres": ACTIVITY_SPHERES,
        "ownership_forms": OWNERSHIP_FORMS,
        "target_audiences": TARGET_AUDIENCES,
        "state_secret_options": [
            {"id": "no", "label": "Нет"},
            {"id": "yes", "label": "Да"},
        ],
        "followup_questions": get_followup_options_for_api(),
    }


def _resolve_legal_area(data: dict) -> str:
    area_id = (data.get("legal_area") or "").strip()
    if area_id == "custom":
        return (data.get("legal_area_custom") or "").strip()
    for item in LEGAL_AREAS:
        if item["id"] == area_id:
            label = item["label"]
            examples = item.get("examples") or ""
            return f"{label}. Примеры: {examples}" if examples else label
    return area_id


def _resolve_target_audience(data: dict) -> str:
    aud_id = (data.get("target_audience") or "").strip()
    if aud_id == "custom":
        return (data.get("target_audience_custom") or "").strip()
    for item in TARGET_AUDIENCES:
        if item["id"] == aud_id:
            return item["label"]
    return aud_id


def _resolve_activity_label(data: dict) -> str:
    sphere_id = (data.get("activity_sphere") or "").strip()
    for item in ACTIVITY_SPHERES:
        if item["id"] == sphere_id:
            return f"{item['label']}. {item.get('description', '')}"
    return sphere_id


def validate_new_vnd_form(data: dict) -> tuple:
    """Проверить форму без исключения. Возвращает (normalized_or_none, missing_fields)."""
    from new_vnd_followup import followup_to_prompt_context, validate_followup_answers

    normalized = {
        "document_name": (data.get("document_name") or "").strip(),
        "document_topic": (data.get("document_topic") or "").strip(),
        "legal_area": (data.get("legal_area") or "").strip(),
        "legal_area_custom": (data.get("legal_area_custom") or "").strip(),
        "activity_sphere": (data.get("activity_sphere") or "").strip(),
        "ownership_form": (data.get("ownership_form") or "").strip(),
        "state_secret": (data.get("state_secret") or "").strip(),
        "employees_count": (data.get("employees_count") or "").strip(),
        "branches": (data.get("branches") or "").strip(),
        "target_audience": (data.get("target_audience") or "").strip(),
        "target_audience_custom": (data.get("target_audience_custom") or "").strip(),
    }

    missing: List[str] = []
    for field in REQUIRED_FIELDS:
        if not normalized.get(field):
            missing.append(field)

    if normalized["legal_area"] == "custom" and not normalized["legal_area_custom"]:
        if "legal_area_custom" not in missing:
            missing.append("legal_area_custom")
    if normalized["target_audience"] == "custom" and not normalized["target_audience_custom"]:
        if "target_audience_custom" not in missing:
            missing.append("target_audience_custom")

    if missing:
        return None, missing

    normalized["legal_area_resolved"] = _resolve_legal_area(normalized)
    normalized["activity_sphere_resolved"] = _resolve_activity_label(normalized)
    normalized["target_audience_resolved"] = _resolve_target_audience(normalized)
    normalized["state_secret_label"] = "Да" if normalized["state_secret"] == "yes" else "Нет"
    normalized["organization_name"] = build_organization_name(normalized.get("ownership_form", ""))

    raw_followup = data.get("followup_answers") or {}
    followup, followup_missing = validate_followup_answers(normalized["legal_area"], raw_followup)
    if followup_missing:
        for fid in followup_missing:
            missing.append(f"followup:{fid}")

    normalized["followup_answers"] = followup
    normalized["followup_context"] = followup_to_prompt_context(normalized["legal_area"], followup)
    if missing:
        return None, missing
    return normalized, []


def normalize_new_vnd_form(data: dict) -> dict:
    """Нормализовать и проверить форму создания нового ВНД."""
    normalized, missing = validate_new_vnd_form(data)
    if missing:
        raise ValueError(f"Не заполнены обязательные поля: {', '.join(missing)}")
    return normalized


def form_to_prompt_context(form: dict) -> str:
    """Текст вводных данных для промптов."""
    org_name = form.get("organization_name") or build_organization_name(form.get("ownership_form", ""))
    return f"""Название документа: {form.get('document_name', '')}
Тема документа (краткое описание): {form.get('document_topic', '')}
Область законодательства: {form.get('legal_area_resolved', '')}
Сфера деятельности предприятия: {form.get('activity_sphere_resolved', '')}
Форма собственности: {form.get('ownership_form', '')}
Наименование организации в документе: {org_name}
Отношение к гостайне: {form.get('state_secret_label', '')}
Количество сотрудников в организации (примерно): {form.get('employees_count', '')}
Наличие филиалов/представительств: {form.get('branches', '')}
Целевая аудитория документа: {form.get('target_audience_resolved', '')}

{form.get('followup_context', '')}"""
