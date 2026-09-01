"""面评报告服务：整合消息、每题评分和能力画像，生成 Markdown 与 PDF。"""
import logging
import uuid
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape

from app.database.session_service import SessionService
from app.services.scoring_service import get_session_scores

logger = logging.getLogger(__name__)

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

_styles = {
    "title": ParagraphStyle("title", fontName="STSong-Light", fontSize=20, leading=26, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="STSong-Light", fontSize=16, leading=22, spaceBefore=12, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="STSong-Light", fontSize=13, leading=18, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="STSong-Light", fontSize=10.5, leading=17, spaceAfter=4),
    "bullet": ParagraphStyle("bullet", fontName="STSong-Light", fontSize=10.5, leading=17, leftIndent=12, bulletIndent=2, spaceAfter=2),
}


def _md_to_flowables(markdown_text: str) -> list:
    flowables = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            flowables.append(Paragraph(escape(line[4:].strip()), _styles["h2"]))
        elif line.startswith("## "):
            flowables.append(Paragraph(escape(line[3:].strip()), _styles["h1"]))
        elif line.startswith("# "):
            flowables.append(Paragraph(escape(line[2:].strip()), _styles["h1"]))
        elif line.startswith("- ") or line.startswith("* "):
            flowables.append(Paragraph(escape(line[2:].strip()), _styles["bullet"], bulletText="•"))
        elif line[:3].strip().rstrip(".").isdigit() and ". " in line[:6]:
            parts = line.split(". ", 1)
            flowables.append(Paragraph(escape(parts[1].strip()), _styles["bullet"], bulletText=parts[0] + "."))
        else:
            flowables.append(Paragraph(escape(line), _styles["body"]))
    return flowables


def render_pdf(title: str, markdown_text: str) -> str:
    out_dir = Path("static") / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}.pdf"
    fpath = out_dir / fname
    doc = SimpleDocTemplate(
        str(fpath), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=title,
    )
    story = [Paragraph(escape(title), _styles["title"]), Spacer(1, 6)]
    story.extend(_md_to_flowables(markdown_text))
    doc.build(story)
    return f"/static/reports/{fname}"


async def generate_session_report(session_id: str) -> dict:
    """生成会话面评报告。"""
    service = SessionService()
    session = await service.get_session(session_id, include_resume_content=True)
    if not session:
        raise ValueError("会话不存在")

    scores = await get_session_scores(session_id)
    profile = await service.get_profile(session_id)

    lines = [f"# 面试评估报告：{session.title or session_id}", ""]
    lines.append(f"- 会话 ID：{session_id}")
    lines.append(f"- 模式：{session.metadata.mode}")
    lines.append(f"- 状态：{'已完成' if session.metadata.status == 'completed' else session.metadata.status}")
    lines.append("")

    if scores:
        lines.append("## 一、逐题评分")
        lines.append("")
        total = 0
        for s in scores:
            dims = s.get("dimensions") or {}
            dim_text = "、".join(f"{k}: {v}" for k, v in dims.items() if not isinstance(v, list))
            lines.append(f"### 第 {s['question_index'] + 1} 题")
            lines.append(f"- 问题：{s['question_text']}")
            lines.append(f"- 回答：{s['answer_text'][:200]}")
            lines.append(f"- 得分：{s.get('total', 0)}（{dim_text}）")
            lines.append(f"- 点评：{s.get('comment', '')}")
            dims = s.get("dimensions") or {}
            if dims.get("strengths"):
                lines.append(f"- 亮点：{';'.join(dims['strengths'])}")
            if dims.get("weaknesses"):
                lines.append(f"- 不足：{';'.join(dims['weaknesses'])}")
            if dims.get("suggestions"):
                lines.append(f"- 改进建议：{';'.join(dims['suggestions'])}")
            lines.append("")
            try:
                total += float(s.get("total") or 0)
            except (TypeError, ValueError):
                pass
        avg = round(total / len(scores), 1)
        lines.append(f"### 本轮平均分：{avg}")
        lines.append("")

    if profile:
        lines.append("## 二、能力画像")
        lines.append("")
        for key, label in [
            ("professional_competence", "专业能力"),
            ("execution_results", "执行与结果导向"),
            ("logic_problem_solving", "逻辑与问题解决"),
            ("communication", "沟通表达力"),
            ("growth_potential", "成长潜力"),
            ("collaboration", "协作能力"),
        ]:
            item = profile.get(key)
            if item:
                lines.append(f"- {label}：{item.get('score', 0)}/10")
                if item.get("evidence"):
                    lines.append(f"  - 证据：{item['evidence']}")
        if profile.get("skill_tags"):
            lines.append(f"- 技能标签：{'、'.join(profile['skill_tags'])}")
        if profile.get("overall_assessment"):
            lines.append("")
            lines.append("### 综合评价")
            lines.append(profile["overall_assessment"])
        if profile.get("key_strengths"):
            lines.append("")
            lines.append("### 主要优势")
            for s in profile["key_strengths"]:
                lines.append(f"- {s}")
        if profile.get("key_weaknesses"):
            lines.append("")
            lines.append("### 待提升项")
            for s in profile["key_weaknesses"]:
                lines.append(f"- {s}")
        if profile.get("recommendation"):
            lines.append("")
            lines.append(f"- 录用建议：{profile['recommendation']}")
        lines.append("")

    lines.append("## 三、面试对话记录")
    lines.append("")
    for msg in session.messages:
        role = "候选人" if msg.role == "user" else "面试官"
        content = (msg.content or "").strip()
        if content and content != "[语音]":
            lines.append(f"**{role}**：{content}")
            lines.append("")

    markdown = "\n".join(lines)
    pdf_url = render_pdf(session.title or "面试评估报告", markdown)
    return {"markdown": markdown, "pdf_url": pdf_url}