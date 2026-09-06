"""趋势维度：单看一天的 DSU 意义有限，SM 报告的价值在对比。

- 阻塞老化：同一个阻塞连续出现几天（>3 天就该升级）
- 行动项闭环：上期未完成的行动项自动带过来
- 与前一期的增减对比
"""

from __future__ import annotations

import json
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from app.config import Pod, get_settings
from app.models import ActionItem, DsuRecord


def previous_record(pod: Pod, day: date) -> DsuRecord | None:
    raw_dir = get_settings().workdir / pod.folder / "raw"
    if not raw_dir.exists():
        return None
    candidates: list[tuple[date, Path]] = []
    for f in raw_dir.glob("*.json"):
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < day:
            candidates.append((d, f))
    if not candidates:
        return None
    _, path = max(candidates)
    try:
        return DsuRecord(**json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def apply_trends(record: DsuRecord, pod: Pod, previous: DsuRecord | None) -> DsuRecord:
    record.blockers_m.total = record.open_blockers

    if previous is None:
        record.blockers_m.aging_days = {b: 1 for b in record.blockers}
        record.blockers_m.new = record.open_blockers
        return record

    prev_blockers = previous.blockers
    prev_aging = previous.blockers_m.aging_days or {}
    gap = (record.date - previous.date).days or 1

    aging: dict[str, int] = {}
    resolved = 0
    for prev_b in prev_blockers:
        match = _best_match(prev_b, record.blockers)
        if match is None:
            resolved += 1
        else:
            aging[match] = prev_aging.get(prev_b, 1) + gap

    new = 0
    for b in record.blockers:
        if b not in aging:
            aging[b] = 1
            new += 1

    record.blockers_m.aging_days = aging
    record.blockers_m.new = new
    record.blockers_m.resolved = resolved
    record.trend.blockers = record.open_blockers - previous.open_blockers
    record.trend.wip = record.wip - previous.wip
    record.trend.overdue_actions = len(record.overdue_actions) - len(previous.overdue_actions)
    record.trend.resolved_since_last = resolved

    # 上期没做完的行动项带过来，避免石沉大海
    carried = [
        ActionItem(
            owner=a.owner,
            text=a.text,
            due=a.due,
            jira_key=a.jira_key,
            carried_from=previous.date.isoformat(),
        )
        for a in previous.action_items
        if not a.done and not _exists(a.text, record.action_items)
    ]
    record.action_items = carried + record.action_items

    if pod.wip_limit is not None and record.flow.wip_limit is None:
        record.flow.wip_limit = pod.wip_limit

    return record


def _exists(text: str, items: list[ActionItem]) -> bool:
    return any(_ratio(text, i.text) > 0.75 for i in items)


def _best_match(target: str, pool: list[str]) -> str | None:
    best, score = None, 0.0
    for item in pool:
        r = _ratio(target, item)
        if r > score:
            best, score = item, r
    return best if score > 0.6 else None


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()
