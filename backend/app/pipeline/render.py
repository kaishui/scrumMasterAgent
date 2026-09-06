from __future__ import annotations

from datetime import datetime

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from app.config import Pod
from app.models import DsuRecord

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_dsu(record: DsuRecord, pod_name: str) -> str:
    return _env.get_template("dsu.html.j2").render(
        record=record,
        pod_name=pod_name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def render_pod_index(pod_name: str, pod_id: str, entries: list[dict]) -> str:
    return _env.get_template("index.html.j2").render(
        title=f"{pod_name} · DSU 归档",
        pods=[{"id": pod_id, "name": pod_name, "entries": entries}],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def render_root(pods: list[dict]) -> str:
    return _env.get_template("index.html.j2").render(
        title="Scrum DSU 总览",
        pods=pods,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ---------- LLM 摘要与教练建议（渲染前生成叙事内容）----------


class CoachingDraft(BaseModel):
    notes: list[str] = Field(default_factory=list)


SUMMARY_SYSTEM = (
    "你是 Scrum Master 的报告摘要生成器。用一段话(80-120 字)给干系人写执行摘要，"
    "覆盖：今天最关键的进展、最需要关注的风险/阻塞、以及下一步行动。客观、克制，不要客套话。"
)
COACH_SYSTEM = (
    "你是资深 Scrum Master 教练。基于这份站会数据，给出 2-4 条给团队/Scrum Master 的"
    "改进建议，每条一句话、可执行，聚焦流程与协作问题(如阻塞升级、WIP 收敛、会议聚焦)。"
)


async def summarize(record: DsuRecord, pod: Pod) -> DsuRecord:
    """LLM 摘要 + 教练建议：面向干系人的执行摘要与面向 SM 的改进建议。失败则原样返回。"""
    from app.llm import complete, complete_json, ready

    if not ready():
        return record

    brief = _brief(record, pod)
    record.executive_summary = await complete(SUMMARY_SYSTEM, brief)
    draft = await complete_json(COACH_SYSTEM, brief, CoachingDraft)
    if draft:
        record.coaching_notes = [n for n in draft.notes if n.strip()]
    return record


def _brief(record: DsuRecord, pod: Pod) -> str:
    lines = [
        f"Pod: {pod.name}({pod.id}) 日期 {record.date} 健康度 {record.health_score}",
        f"阻塞: {record.blockers or '无'}",
        f"逾期行动项: {record.overdue_actions or '无'}",
        f"风险: {[r.text for r in record.risks] or '无'}",
        f"燃尽: {record.sprint_m.burndown} 进度 {record.sprint_m.progress_pct}%",
        f"情绪: {record.sentiment.overall}",
        f"决策: {record.decisions or '无'}",
    ]
    return "\n".join(lines)
