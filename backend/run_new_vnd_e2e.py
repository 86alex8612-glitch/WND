"""E2E: Создать новый — анализ + многоэтапная генерация."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = "http://localhost:8011"
TIMEOUT = 900  # 15 мин на generate

# Данные из последнего файла IN/ВНД_Политика обработки персональных данных_20260701_002329.docx
PAYLOAD = {
    "document_name": "Политика обработки персональных данных",
    "document_topic": (
        "Регламентация сбора, хранения, обработки и защиты персональных данных "
        "сотрудников и клиентов ООО «DialgAI»"
    ),
    "legal_area": "personal_data",
    "activity_sphere": "it_telecom",
    "ownership_form": "ООО (Общество с ограниченной ответственностью)",
    "state_secret": "no",
    "employees_count": "50",
    "branches": "нет",
    "target_audience": "all_employees",
    "followup_answers": {
        "pd_subjects": ["employees", "clients"],
        "legal_bases": ["consent", "contract", "law"],
        "cross_border": "no",
        "third_party": "processors",
        "third_party_details": "Хостинг-провайдер, CRM-система, бухгалтерский аутсорсинг",
        "storage_period": (
            "Данные клиентов — 5 лет после окончания договора; "
            "данные сотрудников — в сроки, установленные законодательством о кадровом учёте"
        ),
        "security_level": "basic",
        "dpo": "appointed",
        "publication": ["website", "office"],
    },
}


def post(path: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"e2e_new_vnd_{stamp}.json"

    print("=== E2E: Создать новый ВНД ===")
    print("Форма:", PAYLOAD["document_name"])
    print("Организация: ООО «DialgAI» (из формы собственности)")

    t0 = time.time()
    print("\n[1/2] Анализ...")
    try:
        analyze = post("/api/create/new/analyze", PAYLOAD)
    except urllib.error.HTTPError as exc:
        print("Ошибка анализа:", exc.read().decode("utf-8", errors="replace"))
        return 1

    analysis = analyze.get("analysis", "")
    laws = analyze.get("laws", [])
    form = analyze.get("form", {})
    print(f"  OK за {time.time() - t0:.1f}с, законов: {len(laws)}")
    print(f"  Анализ (начало): {analysis[:300]}...")

    t1 = time.time()
    print("\n[2/2] Генерация по разделам (может занять несколько минут)...")
    try:
        result = post(
            "/api/create/new/generate",
            {"form": form, "analysis": analysis, "laws": laws},
        )
    except urllib.error.HTTPError as exc:
        print("Ошибка генерации:", exc.read().decode("utf-8", errors="replace"))
        return 1

    doc = result.get("document", "")
    sections = result.get("plan_sections") or []
    mode = result.get("generation_mode", "")
    print(f"  OK за {time.time() - t1:.1f}с")
    print(f"  Режим: {mode}, разделов в плане: {len(sections)}")
    print(f"  Длина документа: {len(doc)} символов")

    out = {
        "payload": PAYLOAD,
        "analyze_seconds": round(time.time() - t0, 1),
        "generate_seconds": round(time.time() - t1, 1),
        "laws_count": len(laws),
        "plan_sections": sections,
        "generation_mode": mode,
        "document_length": len(doc),
        "document_preview": doc[:2000],
        "analysis_preview": analysis[:1500],
    }
    log_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЛог сохранён: {log_path}")

    preview_path = log_dir / f"e2e_new_vnd_{stamp}_doc.txt"
    preview_path.write_text(doc, encoding="utf-8")
    print(f"Текст документа: {preview_path}")
    print(f"\nОбщее время: {time.time() - t0:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
