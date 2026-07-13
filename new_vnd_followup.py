"""
Уточняющие вопросы и чек-листы разделов для «Создать новый» ВНД.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --- Уточняющие вопросы по областям законодательства ---

_FOLLOWUP_PERSONAL_DATA = [
    {
        "id": "pd_subjects",
        "label": "Категории субъектов персональных данных",
        "type": "multiselect",
        "required": True,
        "options": [
            {"id": "employees", "label": "Сотрудники"},
            {"id": "clients", "label": "Клиенты / контрагенты"},
            {"id": "candidates", "label": "Соискатели"},
            {"id": "visitors", "label": "Посетители сайта / пользователи сервисов"},
            {"id": "other", "label": "Иные категории"},
        ],
    },
    {
        "id": "pd_subjects_other",
        "label": "Укажите иные категории субъектов",
        "type": "text",
        "required": True,
        "show_if": {"field": "pd_subjects", "contains": "other"},
    },
    {
        "id": "legal_bases",
        "label": "Основные основания обработки ПДн",
        "type": "multiselect",
        "required": True,
        "options": [
            {"id": "consent", "label": "Согласие субъекта"},
            {"id": "contract", "label": "Исполнение договора"},
            {"id": "law", "label": "Требования закона"},
            {"id": "legitimate_interest", "label": "Законный интерес оператора"},
        ],
    },
    {
        "id": "cross_border",
        "label": "Трансграничная передача персональных данных",
        "type": "select",
        "required": True,
        "options": [
            {"id": "no", "label": "Не осуществляется"},
            {"id": "yes", "label": "Осуществляется"},
            {"id": "planned", "label": "Планируется"},
        ],
    },
    {
        "id": "cross_border_details",
        "label": "Страны, получатели и основание трансграничной передачи",
        "type": "textarea",
        "required": True,
        "show_if": {"field": "cross_border", "values": ["yes", "planned"]},
    },
    {
        "id": "third_party",
        "label": "Передача ПДн третьим лицам / поручение обработки",
        "type": "select",
        "required": True,
        "options": [
            {"id": "no", "label": "Не передаётся"},
            {"id": "processors", "label": "Поручение обработки (обработчики)"},
            {"id": "both", "label": "Поручение и передача третьим лицам"},
        ],
    },
    {
        "id": "third_party_details",
        "label": "Кому передаются / поручается обработка (хостинг, CRM, бухгалтерия и т.п.)",
        "type": "textarea",
        "required": True,
        "show_if": {"field": "third_party", "values": ["processors", "both"]},
    },
    {
        "id": "storage_period",
        "label": "Сроки хранения и порядок уничтожения ПДн",
        "type": "textarea",
        "required": True,
        "placeholder": "Например: данные клиентов — 5 лет после окончания договора; данные сотрудников — 75 лет в кадровых документах…",
    },
    {
        "id": "security_level",
        "label": "Уровень защищённости / основные меры",
        "type": "select",
        "required": True,
        "options": [
            {"id": "basic", "label": "Базовые организационные и технические меры"},
            {"id": "standard", "label": "Стандартный уровень (УЗ-2 / типовые меры ФСТЭК)"},
            {"id": "enhanced", "label": "Повышенный уровень"},
        ],
    },
    {
        "id": "dpo",
        "label": "Ответственный за организацию обработки ПДн",
        "type": "select",
        "required": True,
        "options": [
            {"id": "director", "label": "Генеральный директор"},
            {"id": "appointed", "label": "Назначенное ответственное лицо"},
            {"id": "dpo", "label": "Выделенный DPO / специалист по ПДн"},
        ],
    },
    {
        "id": "publication",
        "label": "Публикация политики",
        "type": "multiselect",
        "required": True,
        "options": [
            {"id": "website", "label": "На официальном сайте"},
            {"id": "office", "label": "В месте доступа для субъектов"},
            {"id": "request", "label": "По запросу субъекта"},
        ],
    },
]

_FOLLOWUP_CONFIDENTIALITY = [
    {
        "id": "secret_types",
        "label": "Виды защищаемой информации",
        "type": "multiselect",
        "required": True,
        "options": [
            {"id": "commercial", "label": "Коммерческая тайна"},
            {"id": "personal", "label": "Персональные данные"},
            {"id": "official", "label": "Служебная информация"},
            {"id": "ib", "label": "Информация в ИС"},
        ],
    },
    {
        "id": "access_model",
        "label": "Модель разграничения доступа",
        "type": "select",
        "required": True,
        "options": [
            {"id": "rbac", "label": "По ролям / должностям"},
            {"id": "need_to_know", "label": "По принципу «need-to-know»"},
            {"id": "mixed", "label": "Комбинированная"},
        ],
    },
    {
        "id": "incident_response",
        "label": "Реагирование на инциденты ИБ",
        "type": "select",
        "required": True,
        "options": [
            {"id": "yes", "label": "Есть регламент / требуется описать"},
            {"id": "no", "label": "Пока не требуется"},
        ],
    },
]

_FOLLOWUP_LABOR = [
    {
        "id": "work_modes",
        "label": "Режимы работы",
        "type": "multiselect",
        "required": True,
        "options": [
            {"id": "office", "label": "Офис"},
            {"id": "remote", "label": "Удалённая работа"},
            {"id": "hybrid", "label": "Гибрид"},
            {"id": "shift", "label": "Сменный график"},
        ],
    },
    {
        "id": "kpi_system",
        "label": "Система KPI / премирования",
        "type": "select",
        "required": True,
        "options": [
            {"id": "yes", "label": "Применяется"},
            {"id": "no", "label": "Не применяется"},
        ],
    },
]

_FOLLOWUP_DEFAULT = [
    {
        "id": "key_processes",
        "label": "Ключевые процессы, которые должен регламентировать документ",
        "type": "textarea",
        "required": True,
        "placeholder": "Перечислите основные процедуры, права и обязанности…",
    },
    {
        "id": "responsible_roles",
        "label": "Ответственные должностные лица / подразделения",
        "type": "textarea",
        "required": True,
        "placeholder": "Например: генеральный директор, юридический отдел, HR…",
    },
    {
        "id": "special_requirements",
        "label": "Особые требования или ограничения",
        "type": "textarea",
        "required": False,
        "placeholder": "Лицензии, отраслевые стандарты, гостайна…",
    },
]

FOLLOWUP_BY_AREA: Dict[str, List[dict]] = {
    "personal_data": _FOLLOWUP_PERSONAL_DATA,
    "confidentiality_ib": _FOLLOWUP_CONFIDENTIALITY,
    "labor": _FOLLOWUP_LABOR,
    "corporate": _FOLLOWUP_DEFAULT,
    "contracts_procurement": _FOLLOWUP_DEFAULT,
    "finance_risks": _FOLLOWUP_DEFAULT,
    "compliance_ethics": _FOLLOWUP_DEFAULT,
    "custom": _FOLLOWUP_DEFAULT,
}

# --- Чек-листы обязательных разделов ---

CHECKLIST_BY_AREA: Dict[str, List[str]] = {
    "personal_data": [
        "Общие положения: цели, задачи, нормативная база (152-ФЗ, подзаконные акты, ГОСТ), область применения",
        "Термины и определения по ст. 3 152-ФЗ (оператор, субъект, обработка, автоматизированная обработка и др.)",
        "Принципы обработки персональных данных (ст. 5 152-ФЗ)",
        "Правовые основания и условия обработки (ст. 6 152-ФЗ) — с учётом ответов пользователя",
        "Категории субъектов и состав обрабатываемых ПДн",
        "Порядок сбора, хранения, обработки, передачи, уничтожения ПДn",
        "Права субъектов персональных данных и порядок их реализации (ст. 14–17 152-ФЗ)",
        "Трансграничная передача (ст. 22 152-ФЗ) — отдельный подраздел; если не осуществляется — явный запрет",
        "Поручение обработки / передача третьим лицам (ст. 6, 19 152-ФЗ)",
        "Меры по обеспечению безопасности ПДн",
        "Ответственное лицо / порядок назначения",
        "Ответственность за нарушения",
        "Порядок ознакомления и публикации политики",
        "Приложения: формы согласия, заявления субъекта (при необходимости)",
    ],
    "confidentiality_ib": [
        "Общие положения и область применения",
        "Термины: коммерческая тайна, конфиденциальная информация, ИС",
        "Классификация и маркировка информации",
        "Режим коммерческой тайны / доступа",
        "Обязанности работников, NDA",
        "Меры информационной безопасности",
        "Реагирование на инциденты",
        "Ответственность и порядок ознакомления",
    ],
    "labor": [
        "Общие положения, нормативная база (ТК РФ)",
        "Права и обязанности работника и работодателя",
        "Режим работы, дисциплина",
        "Оплата труда / KPI (если применимо)",
        "Удалённая работа (если применимо)",
        "Ответственность, порядок ознакомления",
    ],
}

DEFAULT_CHECKLIST = [
    "Общие положения (цели, нормативная база, область применения)",
    "Термины и определения",
    "Основная часть: процессы, права, обязанности",
    "Ответственность",
    "Порядок ознакомления",
    "Приложения (при необходимости)",
]

SECTION_BLUEPRINT: Dict[str, List[dict]] = {
    "personal_data": [
        {"id": "general", "title": "1. Общие положения", "articles": "3–8"},
        {"id": "terms", "title": "2. Термины и определения", "articles": "5–10"},
        {"id": "principles", "title": "3. Принципы обработки персональных данных", "articles": "4–6"},
        {"id": "conditions", "title": "4. Правовые основания и условия обработки", "articles": "6–10"},
        {"id": "procedures", "title": "5. Порядок обработки персональных данных", "articles": "8–15"},
        {"id": "rights", "title": "6. Права субъектов персональных данных", "articles": "8–12"},
        {"id": "cross_border", "title": "7. Трансграничная передача персональных данных", "articles": "6–10"},
        {"id": "third_party", "title": "8. Передача третьим лицам и поручение обработки", "articles": "6–10"},
        {"id": "security", "title": "9. Меры по обеспечению безопасности персональных данных", "articles": "6–10"},
        {"id": "responsibility", "title": "10. Ответственность", "articles": "4–6"},
        {"id": "familiarization", "title": "11. Порядок ознакомления и приложения", "articles": "4–8"},
    ],
}


def get_followup_questions(legal_area_id: str) -> List[dict]:
    area = (legal_area_id or "").strip() or "custom"
    return list(FOLLOWUP_BY_AREA.get(area, _FOLLOWUP_DEFAULT))


def get_checklist(legal_area_id: str) -> List[str]:
    area = (legal_area_id or "").strip() or "custom"
    return list(CHECKLIST_BY_AREA.get(area, DEFAULT_CHECKLIST))


def get_section_blueprint(legal_area_id: str) -> List[dict]:
    area = (legal_area_id or "").strip() or "custom"
    if area in SECTION_BLUEPRINT:
        return list(SECTION_BLUEPRINT[area])
    return [
        {"id": "general", "title": "1. Общие положения", "articles": "6–10"},
        {"id": "terms", "title": "2. Термины и определения", "articles": "5–8"},
        {"id": "main", "title": "3. Основная часть", "articles": "10–20"},
        {"id": "responsibility", "title": "4. Ответственность", "articles": "4–6"},
        {"id": "familiarization", "title": "5. Порядок ознакомления и приложения", "articles": "4–6"},
    ]


def _answer_visible(question: dict, answers: dict) -> bool:
    cond = question.get("show_if")
    if not cond:
        return True
    field = cond.get("field", "")
    value = answers.get(field)
    if cond.get("values"):
        return str(value) in cond["values"]
    if cond.get("contains"):
        if isinstance(value, list):
            return cond["contains"] in value
        return cond["contains"] in str(value or "").split(",")
    return True


def _label_for_answer(question: dict, raw: Any) -> str:
    if question.get("type") == "multiselect":
        ids = raw if isinstance(raw, list) else [x.strip() for x in str(raw or "").split(",") if x.strip()]
        labels = []
        for opt in question.get("options") or []:
            if opt.get("id") in ids:
                labels.append(opt.get("label") or opt["id"])
        return ", ".join(labels) if labels else ", ".join(ids)
    if question.get("type") == "select":
        for opt in question.get("options") or []:
            if opt.get("id") == raw:
                return opt.get("label") or str(raw)
        return str(raw or "")
    return str(raw or "").strip()


def validate_followup_answers(legal_area_id: str, answers: dict) -> tuple:
    """Проверить ответы на уточняющие вопросы. Возвращает (normalized, missing_ids)."""
    answers = answers or {}
    missing: List[str] = []
    normalized: Dict[str, Any] = {}

    for q in get_followup_questions(legal_area_id):
        qid = q["id"]
        if not _answer_visible(q, answers):
            continue
        raw = answers.get(qid)
        if q.get("type") == "multiselect":
            if isinstance(raw, list):
                val = [str(x).strip() for x in raw if str(x).strip()]
            else:
                val = [x.strip() for x in str(raw or "").split(",") if x.strip()]
            normalized[qid] = val
            if q.get("required") and not val:
                missing.append(qid)
        else:
            val = str(raw or "").strip() if raw is not None else ""
            normalized[qid] = val
            if q.get("required") and not val:
                missing.append(qid)

    return normalized, missing


def followup_to_prompt_context(legal_area_id: str, answers: dict) -> str:
    """Текст ответов на уточняющие вопросы для промптов."""
    lines: List[str] = []
    for q in get_followup_questions(legal_area_id):
        if not _answer_visible(q, answers):
            continue
        raw = answers.get(q.get("id"))
        if raw is None or raw == "" or raw == []:
            continue
        label = _label_for_answer(q, raw)
        if label:
            lines.append(f"- {q.get('label', q['id'])}: {label}")
    if not lines:
        return "Уточняющие ответы не предоставлены."
    return "Уточняющие ответы пользователя:\n" + "\n".join(lines)


def checklist_to_prompt_text(legal_area_id: str) -> str:
    items = get_checklist(legal_area_id)
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


# --- Ориентиры для блока «Рекомендации» (сопутствующие документы) ---

COMPANION_DOCS_HINTS: Dict[str, List[dict]] = {
    "personal_data": [
        {"kind": "Приказ", "title": "О назначении ответственного за организацию обработки персональных данных", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Положение", "title": "Об обработке и защите персональных данных работников", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Согласие (форма)", "title": "Согласие субъекта на обработку персональных данных", "confidentiality": "Персональные данные (ограниченный доступ)"},
        {"kind": "Модель угроз", "title": "Модель угроз безопасности персональных данных", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Положение", "title": "Об уничтожении (обезличивании) персональных данных", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Регламент", "title": "Реагирования на инциденты, связанные с персональными данными", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Соглашение", "title": "О поручении обработки персональных данных (с обработчиком)", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Инструкция", "title": "Порядок работы с обращениями субъектов персональных данных", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
    "confidentiality_ib": [
        {"kind": "Приказ", "title": "Об утверждении перечня сведений, составляющих коммерческую тайну", "confidentiality": "Коммерческая тайна"},
        {"kind": "Положение", "title": "О коммерческой тайне", "confidentiality": "Коммерческая тайна"},
        {"kind": "Соглашение", "title": "О неразглашении конфиденциальной информации (NDA)", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Политика", "title": "Информационной безопасности", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Регламент", "title": "Реагирования на инциденты информационной безопасности", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Инструкция", "title": "По работе с конфиденциальной информацией", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
    "labor": [
        {"kind": "Положение", "title": "Об оплате труда и премировании", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Положение", "title": "О дистанционной (удалённой) работе", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Приказ", "title": "Об утверждении штатного расписания", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Положение", "title": "О персональных данных работников", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Регламент", "title": "По охране труда и технике безопасности", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
    "corporate": [
        {"kind": "Устав", "title": "Общества (актуализированная редакция)", "confidentiality": "Общедоступный"},
        {"kind": "Положение", "title": "О единоличном исполнительном органе", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Положение", "title": "О Совете директоров (наблюдательном совете)", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Приказ", "title": "О делопроизводстве и документообороте", "confidentiality": "Для служебного пользования (ДСП)"},
    ],
    "contracts_procurement": [
        {"kind": "Положение", "title": "О закупках товаров, работ и услуг", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Регламент", "title": "Проверки контрагентов (due diligence)", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Типовая форма", "title": "Договора поставки / оказания услуг", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
    "finance_risks": [
        {"kind": "Положение", "title": "Об учётной политике", "confidentiality": "Коммерческая тайна"},
        {"kind": "Положение", "title": "О внутреннем контроле и управлении рисками", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Приказ", "title": "О назначении ответственных за финансовую отчётность", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
    "compliance_ethics": [
        {"kind": "Кодекс", "title": "Корпоративной этики и делового поведения", "confidentiality": "Общедоступный"},
        {"kind": "Положение", "title": "О противодействии коррупции", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Регламент", "title": "Рассмотрения конфликта интересов", "confidentiality": "Для служебного пользования (ДСП)"},
    ],
    "custom": [
        {"kind": "Приказ", "title": "О введении в действие локального нормативного акта", "confidentiality": "Конфиденциально (внутренний документ)"},
        {"kind": "Положение", "title": "О делопроизводстве", "confidentiality": "Для служебного пользования (ДСП)"},
        {"kind": "Инструкция", "title": "По применению настоящего документа", "confidentiality": "Конфиденциально (внутренний документ)"},
    ],
}

CONFIDENTIALITY_LEVELS = [
    "Общедоступный",
    "Конфиденциально (внутренний документ)",
    "Для служебного пользования (ДСП)",
    "Коммерческая тайна",
    "Персональные данные (ограниченный доступ)",
    "Сведения, составляющие государственную тайну",
]


def companion_docs_hints_to_prompt_text(legal_area_id: str) -> str:
    """Ориентиры сопутствующих документов для блока «Рекомендации»."""
    area = (legal_area_id or "").strip() or "custom"
    hints = COMPANION_DOCS_HINTS.get(area, COMPANION_DOCS_HINTS["custom"])
    lines = [
        f"{i + 1}. {h['kind']}: «{h['title']}» — {h['confidentiality']}"
        for i, h in enumerate(hints)
    ]
    levels = ", ".join(CONFIDENTIALITY_LEVELS)
    return (
        "Типовые сопутствующие документы (ориентир, можно дополнить и уточнить):\n"
        + "\n".join(lines)
        + f"\n\nДопустимые уровни конфиденциальности: {levels}."
    )


def get_followup_options_for_api() -> dict:
    return {area: get_followup_questions(area) for area in FOLLOWUP_BY_AREA}
