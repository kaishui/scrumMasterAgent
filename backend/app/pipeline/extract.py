"""用 LangChain 把 DSU 转录转成结构化记录（skill: standup_structurer）。

优先走 `with_structured_output`；内部模型网关不支持函数调用时，
自动降级到「prompt + JsonOutputParser」。两条路都没法用时才退回规则切分，
保证流水线永远出得来报告。prompt 与输出 schema 集中在 `app/skills.py`。
"""

from __future__ import annotations

from datetime import date

from app import skills
from app.config import Pod, get_settings
from app.models import DeliveryMetrics, DsuRecord, PersonUpdate, QualityMetrics


async def extract(pod: Pod, day: date, transcript: str) -> DsuRecord:
    settings = get_settings()
    if not settings.llm_api_key:
        return _fallback(pod, day, transcript)

    from app.llm import run_structured

    draft = await run_structured(
        skills.structurer_prompt,
        skills.DsuDraft,
        pod=f"{pod.name}({pod.id})",
        day=day.isoformat(),
        members=", ".join(pod.members) or "未知",
        wip=pod.wip_limit or "未设置",
        transcript=transcript,
    )
    if draft is None:
        return _fallback(pod, day, transcript)
    return _to_record(pod, day, draft)


def _to_record(pod: Pod, day: date, draft: "skills.DsuDraft") -> DsuRecord:
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
