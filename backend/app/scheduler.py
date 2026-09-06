"""定时跑批：每个 pod 在自己的会议时间之后触发。

本地用 APScheduler 常驻；生产环境推荐直接换成 GitHub Actions cron，
省一台常开机器（见 .github/workflows/daily-dsu.yml）。
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import load_pods
from app.pipeline.run import run_pipeline, today_for


def build() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    for pod in load_pods():
        hour, minute = _shift(pod.meeting.time, 15)  # 会议结束后 15 分钟开跑
        trigger = CronTrigger(
            hour=hour, minute=minute, day_of_week="mon-fri", timezone=pod.meeting.timezone
        )
        scheduler.add_job(
            _job,
            trigger,
            args=[pod.id],
            id=f"dsu-{pod.id}",
            replace_existing=True,
        )
    return scheduler


async def _job(pod_id: str) -> None:
    await run_pipeline(pod_id, today_for(_pod(pod_id)), do_publish=True)


def _shift(hhmm: str, minutes: int) -> tuple[int, int]:
    parts = (hhmm.split(":") + ["0"])[:2]
    total = int(parts[0]) * 60 + int(parts[1]) + minutes
    return (total // 60) % 24, total % 60


def _pod(pod_id: str):
    from app.config import get_pod

    return get_pod(pod_id)
