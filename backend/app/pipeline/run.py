"""流水线编排：抽取 → 富化 → 趋势对比 → 渲染 → 原子提交。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Pod, get_pod, get_settings
from app.models import DsuRecord, Risk
from app.pipeline import enrich, extract, ingest, publish, render, trends


@dataclass
class RunResult:
    pod: str
    date: str
    record: DsuRecord
    local_html: str
    url: str = ""
    published: bool = False
    pending_approval: bool = False
    notes: list[str] = field(default_factory=list)


def today_for(pod: Pod) -> date:
    return datetime.now(ZoneInfo(pod.meeting.timezone)).date()


async def run_pipeline(
    pod_id: str,
    day: date | None = None,
    transcript_path: Path | None = None,
    do_publish: bool = False,
    use_mcp: bool = True,
) -> RunResult:
    settings = get_settings()
    pod = get_pod(pod_id)
    day = day or today_for(pod)

    transcript = ingest.load_transcript(pod, day, transcript_path)
    transcript = await ingest.clean_transcript(pod, transcript)  # LLM ① 清洗字幕

    record = await extract.extract(pod, day, transcript)  # LLM ② 结构化

    if use_mcp:
        try:
            record = await enrich.enrich(record, pod)
        except Exception as exc:  # MCP 挂了不该阻断出报告
            record.risks.append(Risk(level="medium", text=f"Jira/GitHub 富化失败：{exc}"))

    try:
        record = await enrich.analyze(record, pod, transcript)  # LLM ③ 洞察
    except Exception:
        pass

    previous = trends.previous_record(pod, day)
    record = trends.apply_trends(record, pod, previous)

    try:
        record = await trends.narrate(record, pod, previous)  # LLM ④ 趋势解读 + 预测
    except Exception:
        pass

    try:
        record = await render.summarize(record, pod)  # LLM ⑤ 摘要 + 教练建议
    except Exception:
        pass

    html = render.render_dsu(record, pod.name)
    local = publish.save_local(record, pod, html)

    result = RunResult(
        pod=pod.id,
        date=day.isoformat(),
        record=record,
        local_html=str(local),
    )

    if not do_publish:
        result.notes.append("仅生成本地草稿，未发布")
        return result

    # auto_commit 打开时跳过人工闸门，生成即提交
    gated = not settings.auto_commit and (settings.require_human_approval or pod.require_approval)
    if gated and not record.approved:
        result.pending_approval = True
        result.notes.append("等待人工确认后再发布")
        return result

    history = _local_history(pod)
    result.url = await publish.publish(pod, record, html, history)
    result.published = True
    result.notes.append("已原子提交：HTML + JSON + 索引在同一个 commit")
    return result


def _local_history(pod: Pod) -> list[dict]:
    root = get_settings().workdir / pod.folder / "raw"
    if not root.exists():
        return []
    out = []
    for f in sorted(root.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({"date": data.get("date", f.stem), "url": f"dsu/{f.stem}.html"})
    return out
