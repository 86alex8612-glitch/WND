"""
Формирование PDF отчёта анализа — визуально как блок превью на экране.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import textwrap
from typing import List, Optional, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_PREVIEW = {
    "body_font_size": 11.4,
    "body_leading": 17.7,
    "body_pad": 12,
    "body_bg": "#fafafa",
    "body_border": "#e5e5e5",
    "summary_font_size": 11.0,
    "summary_leading": 16.5,
    "summary_bg": "#f8f9fa",
    "summary_accent": "#007bff",
    "title_font_size": 13.5,
    "title_color": "#333333",
    "text_color": "#333333",
    "emoji_icon_pt": 13.0,
}

_EMOJI_FONT_CANDIDATES = (
    "C:/Windows/Fonts/seguiemj.ttf",
    "C:/Windows/Fonts/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/google-noto-emoji/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
)

_EMOJI_TEXT_FALLBACKS = {
    "✅": "[OK]",
    "❌": "[X]",
    "⚠️": "[!]",
    "⚠": "[!]",
    "🔴": "[высокий]",
    "🟡": "[средний]",
    "🟢": "[низкий]",
    "ℹ️": "[инфо]",
    "ℹ": "[инфо]",
    "🚨": "[!]",
    "💰": "",
    "⚖️": "",
    "⚖": "",
    "📋": "",
    "📄": "",
    "📊": "",
    "📅": "",
    "📌": "",
    "🔗": "",
    "⚡": "",
    "🧾": "",
    "🧱": "",
    "📚": "",
    "🏦": "",
    "🔟": "10.",
    "9️⃣": "9.",
    "8️⃣": "8.",
    "7️⃣": "7.",
    "6️⃣": "6.",
    "5️⃣": "5.",
    "4️⃣": "4.",
    "3️⃣": "3.",
    "2️⃣": "2.",
    "1️⃣": "1.",
}


_EMOJI_RE = re.compile(
    r"(?:\d\uFE0F?\u20E3)"
    r"|(?:[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F600-\U0001F64F"
    r"\u2705\u274C\u26A0\u2139\u2696\u2699\u2695\u2694\u26D4\u2B50]+(?:\uFE0F)?)"
)


class _EmojiImageCache:
    """Рендер цветных эмодзи в PNG для встраивания в Paragraph."""

    def __init__(self) -> None:
        self._paths: dict[str, str] = {}
        self._font_path = next((p for p in _EMOJI_FONT_CANDIDATES if os.path.exists(p)), "")
        self.enabled = bool(self._font_path)
        self._cache_dir = os.path.join(
            os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
            "wnd_report_emoji",
        )

    def _render_path(self, emoji: str) -> Optional[str]:
        if not self.enabled:
            return None
        if emoji in self._paths:
            return self._paths[emoji]

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self.enabled = False
            return None

        pixel_size = 34
        try:
            font = ImageFont.truetype(self._font_path, pixel_size)
            image = Image.new("RGBA", (pixel_size + 6, pixel_size + 6), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            draw.text((1, 0), emoji, font=font, embedded_color=True)
            os.makedirs(self._cache_dir, exist_ok=True)
            digest = hashlib.sha1(emoji.encode("utf-8")).hexdigest()[:16]
            path = os.path.join(self._cache_dir, f"{digest}.png")
            image.save(path, "PNG")
            self._paths[emoji] = path
            return path
        except Exception:
            return None

    def img_markup(self, emoji: str) -> str:
        path = self._render_path(emoji)
        size = _PREVIEW["emoji_icon_pt"]
        if path:
            return f'<img src="{path}" width="{size}" height="{size}" valign="middle"/>'
        if emoji in _EMOJI_TEXT_FALLBACKS:
            return escape(_EMOJI_TEXT_FALLBACKS[emoji])
        return escape(_normalize_symbols_for_plaintext(emoji))


_EMOJI_CACHE = _EmojiImageCache()


def _normalize_symbols_for_plaintext(text: str) -> str:
    """Текстовая версия: эмодзи -> читаемые подписи (для .txt fallback)."""
    if not text:
        return ""
    normalized = str(text).replace("\uFE0F", "")
    replacements = (
        ("✅", "[OK]"),
        ("❌", "[X]"),
        ("⚠️", "[!]"),
        ("⚠", "[!]"),
        ("🔴", "[высокий]"),
        ("🟡", "[средний]"),
        ("🟢", "[низкий]"),
        ("ℹ️", "[инфо]"),
        ("ℹ", "[инфо]"),
        ("🚨", "[!]"),
        ("💰", ""),
        ("⚖️", ""),
        ("⚖", ""),
        ("🏦", ""),
        ("📋", ""),
        ("📄", ""),
        ("📊", ""),
        ("📅", ""),
        ("📌", ""),
        ("🔗", ""),
        ("⚡", ""),
        ("🧾", ""),
        ("🧱", ""),
        ("📚", ""),
        ("🔟", "10."),
        ("9️⃣", "9."),
        ("8️⃣", "8."),
        ("7️⃣", "7."),
        ("6️⃣", "6."),
        ("5️⃣", "5."),
        ("4️⃣", "4."),
        ("3️⃣", "3."),
        ("2️⃣", "2."),
        ("1️⃣", "1."),
        ("━", "-"),
        ("—", "-"),
    )
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"(\d)\u20e3", r"\1.", normalized)
    normalized = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F600-\U0001F64F]+",
        "",
        normalized,
    )
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _text_to_paragraph_markup(text: str) -> str:
    """Текст -> ReportLab markup: эмодзи как цветные иконки, остальное экранируется."""
    if not text:
        return ""

    parts: List[str] = []
    last = 0
    for match in _EMOJI_RE.finditer(text):
        if match.start() > last:
            parts.append(escape(text[last:match.start()]))
        parts.append(_EMOJI_CACHE.img_markup(match.group(0)))
        last = match.end()
    parts.append(escape(text[last:]))
    return "".join(parts).replace("\n", "<br/>")


def _format_report_heading(title: Optional[str], report_name: Optional[str] = None) -> str:
    heading = (title or report_name or "Правовой анализ").strip()
    if heading.startswith("Этап 2."):
        heading = heading[len("Этап 2."):].strip()
    return heading


def _register_report_fonts() -> Tuple[str, str]:
    regular = "ReportFont"
    bold = "ReportFontBold"

    candidates: List[Tuple[str, str]] = []

    try:
        import reportlab

        dejavu_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        candidates.append(
            (
                os.path.join(dejavu_dir, "DejaVuSans.ttf"),
                os.path.join(dejavu_dir, "DejaVuSans-Bold.ttf"),
            )
        )
    except Exception:
        pass

    project_fonts = os.path.join(os.path.dirname(__file__), "fonts")
    candidates.extend(
        [
            (os.path.join(project_fonts, "DejaVuSans.ttf"), os.path.join(project_fonts, "DejaVuSans-Bold.ttf")),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
            ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ]
    )

    registered_regular = False
    registered_bold = False
    for reg_path, bold_path in candidates:
        if not os.path.exists(reg_path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(regular, reg_path))
            registered_regular = True
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont(bold, bold_path))
                registered_bold = True
            break
        except Exception:
            continue

    if not registered_regular:
        regular = "Helvetica"
        bold = "Helvetica-Bold"
    elif not registered_bold:
        bold = regular

    return regular, bold


def _clean_report_text(text: str) -> str:
    """Базовая очистка без удаления эмодзи (для PDF)."""
    if not text:
        return ""
    cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.encode("utf-8", errors="ignore").decode("utf-8")
    cleaned = "".join(
        ch if ch.isprintable() or ch in "\n\t" else " "
        for ch in cleaned
    )
    cleaned = cleaned.replace("━", "─")
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def _sanitize_report_text(text: str) -> str:
    return _normalize_symbols_for_plaintext(_clean_report_text(text))


def _summary_html_to_markup(html: str) -> str:
    if not html:
        return ""
    text = str(html)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(/)?(strong|b)>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _clean_report_text(text)
    return _text_to_paragraph_markup(text.strip())


def _wrap_long_lines(text: str, width: int = 96) -> str:
    wrapped: List[str] = []
    for line in text.split("\n"):
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.wrap(line, width=width) or [""])
    return "\n".join(wrapped)


def _split_text_blocks(text: str, max_lines: int = 10, max_chars: int = 700) -> List[str]:
    text = _wrap_long_lines(text)
    lines = text.split("\n")
    blocks: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current and (len(current) >= max_lines or current_len + line_len > max_chars):
            blocks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        blocks.append("\n".join(current))
    return blocks or [text]


def _build_body_paragraphs(body_text: str, body_style: ParagraphStyle) -> list:
    blocks = _split_text_blocks(body_text)
    return [Paragraph(_text_to_paragraph_markup(block), body_style) for block in blocks]


def _result_card_table(body_paragraphs: list, width: float) -> Table:
    rows = [[paragraph] for paragraph in body_paragraphs]
    table = Table(rows, colWidths=[width], splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_PREVIEW["body_bg"])),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(_PREVIEW["body_border"])),
                ("LEFTPADDING", (0, 0), (-1, -1), _PREVIEW["body_pad"]),
                ("RIGHTPADDING", (0, 0), (-1, -1), _PREVIEW["body_pad"]),
                ("TOPPADDING", (0, 0), (-1, 0), _PREVIEW["body_pad"]),
                ("BOTTOMPADDING", (0, -1), (-1, -1), _PREVIEW["body_pad"]),
                ("TOPPADDING", (0, 1), (-1, -2), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _summary_table(summary_html: str, summary_style: ParagraphStyle, width: float) -> Table:
    table = Table(
        [[Paragraph(_summary_html_to_markup(summary_html), summary_style)]],
        colWidths=[width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_PREVIEW["summary_bg"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(_PREVIEW["summary_accent"])),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def build_analysis_report_plaintext(
    content: str,
    report_name: Optional[str] = None,
    title: Optional[str] = None,
    summary_html: Optional[str] = None,
) -> str:
    """Текстовая версия отчёта (та же структура, что PDF) — для fallback и копирования."""
    body_text = _sanitize_report_text(content)
    if not body_text:
        raise ValueError("Пустой отчёт")

    parts: List[str] = []
    heading = _format_report_heading(title, report_name)
    if heading:
        parts.append(heading)
        parts.append("")

    if summary_html and summary_html.strip():
        summary_text = re.sub(r"<br\s*/?>", "\n", summary_html, flags=re.IGNORECASE)
        summary_text = re.sub(r"<[^>]+>", "", summary_text)
        summary_text = _normalize_symbols_for_plaintext(summary_text.strip())
        if summary_text:
            parts.append(summary_text)
            parts.append("")

    parts.append(body_text)
    return "\n".join(parts).strip() + "\n"


def build_analysis_report_pdf(
    filepath: str,
    content: str,
    report_name: Optional[str] = None,
    title: Optional[str] = None,
    summary_html: Optional[str] = None,
) -> None:
    with open(filepath, "wb") as handle:
        handle.write(
            build_analysis_report_pdf_bytes(
                content,
                report_name=report_name,
                title=title,
                summary_html=summary_html,
            )
        )


def build_analysis_report_pdf_bytes(
    content: str,
    report_name: Optional[str] = None,
    title: Optional[str] = None,
    summary_html: Optional[str] = None,
) -> bytes:
    regular_font, bold_font = _register_report_fonts()
    body_text = _clean_report_text(content)
    if not body_text:
        raise ValueError("Пустой отчёт")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=report_name or "Отчёт анализа ВНД",
        author="НейроКонсультант по ВНД",
    )

    title_style = ParagraphStyle(
        "ReportTitle",
        fontName=bold_font,
        fontSize=_PREVIEW["title_font_size"],
        leading=_PREVIEW["title_font_size"] * 1.25,
        textColor=colors.HexColor(_PREVIEW["title_color"]),
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "AnalysisReportBody",
        fontName=regular_font,
        fontSize=_PREVIEW["body_font_size"],
        leading=_PREVIEW["body_leading"],
        textColor=colors.HexColor(_PREVIEW["text_color"]),
    )
    summary_style = ParagraphStyle(
        "Stage1Summary",
        fontName=regular_font,
        fontSize=_PREVIEW["summary_font_size"],
        leading=_PREVIEW["summary_leading"],
        textColor=colors.HexColor(_PREVIEW["text_color"]),
    )

    story = []
    heading = _format_report_heading(title, report_name)
    if heading:
        story.append(Paragraph(_text_to_paragraph_markup(heading), title_style))

    if summary_html and summary_html.strip():
        story.append(_summary_table(summary_html, summary_style, doc.width))
        story.append(Spacer(1, 10))

    body_paragraphs = _build_body_paragraphs(body_text, body_style)
    story.append(_result_card_table(body_paragraphs, doc.width))
    doc.build(story)
    return buffer.getvalue()
