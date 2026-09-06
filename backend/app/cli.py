"""命令行入口：本地调试与 GitHub Actions 都用它。"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from app.config import get_pod, load_pods
from app.pipeline.run import run_pipeline, today_for


async def _run(args) -> None:
    if args.pod == "all":
        pods = [p.id for p in load_pods()]
    else:
        pods = [args.pod]

    for pod_id in pods:
        pod = get_pod(pod_id)
        day = date.fromisoformat(args.date) if args.date else today_for(pod)
        result = await run_pipeline(
            pod_id,
            day,
            do_publish=args.publish,
            use_mcp=not args.no_mcp,
        )
        print(
            json.dumps(
                {
                    "pod": result.pod,
                    "date": result.date,
                    "local_html": result.local_html,
                    "url": result.url,
                    "published": result.published,
                    "pending_approval": result.pending_approval,
                    "notes": result.notes,
                },
                ensure_ascii=False,
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrum Master Agent")
    parser.add_argument("action", choices=["generate", "publish"])
    parser.add_argument("--pod", required=True, help="pod id 或 all")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    parser.add_argument("--publish", action="store_true", help="发布到 GitHub")
    parser.add_argument("--no-mcp", action="store_true", help="跳过 Jira/GitHub 富化")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
