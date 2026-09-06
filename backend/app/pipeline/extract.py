"""用 LangChain 把 DSU 转录转成结构化记录。

优先走 `with_structured_output`；内部模型网关不支持函数调用时，
自动降级到「prompt + JsonOutputParser」。两条路都没法用时才退回规则切分，
保证流水线永远出得来报告。
"""

from __future__ import annotations

import json
from datetime import date

from pydantic import BaseModel, Field

from app.config import Pod, get_settings
from app.models import (
    ActionItem,
    DsuRecord,
    PersonUpdate,
    Risk,
    DeliveryMetrics,
    QualityMetrics,
    MeetingQuality,
    SentimentMetrics,
    SprintMetrics,
)

SYSTEM = """你是一位资深 Scrum Master，负责把每日站会转录整理成结构化记录。

严格按维度输出，不要臆造：
1. updates: 按人切分「昨天 / 今天 / 阻塞」，忠于原话。提到 Jira 工单号(如 PAY-123)
   填进 jira_keys，提到 PR 号填进 prs。
2. decisions: 会上明确的结论。没有就空数组。
3. action_items: 必须有 owner 和可验证的动作，尽量带 due。
4. risks: 延期、依赖、资源、质量风险，标注 low/medium/high。
5. delivery: 已完成/计划条目数、WIP、冲刺承诺与完成情况、范围变更。
6. blocker_summary: 新增与解决的阻塞数；跨团队依赖和外部依赖单独列。
7. quality: 缺陷开关、CI 失败、部署次数、线上事故。
8. flow: 卡住超过 3 天的工单(写清卡在哪个状态)、周期时间。
9. team: 全程没发言的人、每人的在办条目数(看负载是否失衡)。
10. sentiment: 从措辞与语气判断团队情绪 overall(positive/neutral/stressed/negative)、
    异常信号 signals、可能的过载/burnout 成员 burnout_risk，附一句 note。
11. meeting: 站会是否聚焦——focus_score(0-100)、是否围绕三大问题 on_agenda、
    跑题内容 tangents，附一句 note。
12. sprint: 冲刺目标 goal、承诺点数 committed_points、已完成点数 completed_points、
    近期速度 velocity_points、燃尽状态 burndown(on_track/behind/ahead/unknown)、
    范围蔓延 scope_creep。
13. 转录里没提到的维度留 0 或空数组，不要编数字。
"""


class BlockersDraft(BaseModel):
    new: int = 0
    resolved: int = 0
    cross_team: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class FlowDraft(BaseModel):
    stale_tickets: list[str] = Field(default_factory=list)
    cycle_time_days: float | None = None


class TeamDraft(BaseModel):
    silent: list[str] = Field(default_factory=list)
    load_by_person: dict[str, int] = Field(default_factory=dict)


class DsuDraft(BaseModel):
    sprint: str = ""
    attendees: list[str] = Field(default_factory=list)
    updates: list[PersonUpdate] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    delivery: DeliveryMetrics = Field(default_factory=DeliveryMetrics)
    blocker_summary: BlockersDraft = Field(default_factory=BlockersDraft)
    quality: QualityMetrics = Field(default_factory=QualityMetrics)
    flow: FlowDraft = Field(default_factory=FlowDraft)
    team: TeamDraft = Field(default_factory=TeamDraft)
    sentiment: SentimentMetrics = Field(default_factory=SentimentMetrics)
    meeting: MeetingQuality = Field(default_factory=MeetingQuality)
    sprint_m: SprintMetrics = Field(default_factory=SprintMetrics)


async def extract(pod: Pod, day: date, transcript: str) -> DsuRecord:
    settings = get_settings()
    if not settings.llm_api_key:
        return _fallback(pod, day, transcript)

    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.2,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM),
            (
                "human",
                "Pod: {pod}\n日期: {day}\n已知成员: {members}\nWIP 上限: {wip}\n\n会议转录:\n{transcript}",
            ),
        ]
    )

    draft = None
    try:
        chain = prompt | llm.with_structured_output(DsuDraft, method="function_calling")
        draft = await chain.ainvoke(
            {
                "pod": f"{pod.name}({pod.id})",
                "day": day.isoformat(),
                "members": ", ".join(pod.members) or "未知",
                "wip": pod.wip_limit or "未设置",
                "transcript": transcript,
            }
        )
    except Exception:
        from langchain_core.output_parsers import JsonOutputParser

        parser = JsonOutputParser(pydantic_object=DsuDraft)
        chain = prompt | llm | parser
        try:
            raw = await chain.ainvoke(
                {
                    "pod": f"{pod.name}({pod.id})",
                    "day": day.isoformat(),
                    "members": ", ".join(pod.members) or "未知",
                    "wip": pod.wip_limit or "未设置",
                    "transcript": transcript,
                }
            )
            draft = DsuDraft(**raw) if isinstance(raw, dict) else None
        except Exception:
            draft = None

    if draft is None:
        return _fallback(pod, day, transcript)

    return _to_record(pod, day, draft)


def _to_record(pod: Pod, day: date, draft: DsuDraft) -> DsuRecord:
    from app.models import BlockerMetrics, FlowMetrics, TeamMetrics

    return DsuRecord(
        pod=pod.id,
        date=day,
        sprint=draft.sprint,
        attendees=draft.attendees or [u.person for u in draft.updates],
        updates=draft.updates,
        decisions=draft.decisions,
        action_items=draft.action_items,
        risks=draft.risks,
        delivery=draft.delivery,
        blockers_m=BlockerMetrics(
            new=draft.blocker_summary.new,
            resolved=draft.blocker_summary.resolved,
            cross_team=draft.blocker_summary.cross_team,
            external=draft.blocker_summary.external,
        ),
        quality=draft.quality,
        flow=FlowMetrics(
            cycle_time_days=draft.flow.cycle_time_days,
            stale_tickets=draft.flow.stale_tickets,
            wip_limit=pod.wip_limit,
        ),
        team=TeamMetrics(
            participants=len(draft.attendees or draft.updates),
            silent=draft.team.silent,
            load_by_person=draft.team.load_by_person,
            overloaded=_overloaded(draft.team.load_by_person, pod.wip_limit),
        ),
        sentiment=draft.sentiment,
        sprint_m=draft.sprint_m,
        meeting=draft.meeting,
        source="langchain",
    )


def _overloaded(load: dict[str, int], limit: int | None) -> list[str]:
    if not limit:
        return []
    return sorted(name for name, n in load.items() if n > limit)


def _fallback(pod: Pod, day: date, transcript: str) -> DsuRecord:
    """无 LLM 时按「说话人: 内容」切分，只做最基本的归类。"""
    updates: dict[str, PersonUpdate] = {}
    for line in transcript.splitlines():
        if ":" not in line and "：" not in line:
            continue
        sep = ":" if ":" in line else "："
        person, _, content = line.partition(sep)
        person, content = person.strip()[:32], content.strip()
        if not person or not content:
            continue
        bucket = updates.setdefault(person.lower(), PersonUpdate(person=person))
        lowered = content.lower()
        if content.lstrip().startswith("阻塞") or "阻塞：" in content:
            bucket.blockers.append(content)
        elif any(k in lowered for k in ("今天", "today", "接下来", "计划", "plan")):
            bucket.today.append(content)
        else:
            bucket.yesterday.append(content)

    from app.models import BlockerMetrics, FlowMetrics, TeamMetrics

    people = list(updates.values())
    return DsuRecord(
        pod=pod.id,
        date=day,
        attendees=[u.person for u in people],
        updates=people,
        delivery=DeliveryMetrics(
            done_yesterday=sum(len(u.yesterday) for u in people),
            planned_today=sum(len(u.today) for u in people),
            wip=sum(len(u.today) for u in people),
        ),
        blockers_m=BlockerMetrics(),
        quality=QualityMetrics(),
        flow=FlowMetrics(wip_limit=pod.wip_limit),
        team=TeamMetrics(
            participants=len(people),
            load_by_person={u.person: len(u.today) for u in people},
            silent=[m for m in pod.members if m not in {u.person.lower() for u in people}],
        ),
        source="rule-based-fallback",
    )
