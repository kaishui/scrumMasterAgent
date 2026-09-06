"""发布：一次性把 HTML / JSON / 索引批量提交到 pod 目录。

同日重跑覆盖同一路径，天然幂等，不会产出 2026-09-06-v2.html 这种垃圾。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.config import Pod, get_settings
from app.models import DsuRecord
from app.pipeline.render import render_pod_index, render_root

INDEX_PATH = "data/dsu-index.json"


def save_local(record: DsuRecord, pod: Pod, html: str) -> Path:
    """写到 .workdir，供前端本地预览，不进 Git。"""
    root = get_settings().workdir
    target = root / record.html_path(pod.folder)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")

    raw = root / record.json_path(pod.folder)
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(
        json.dumps(json.loads(record.model_dump_json()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


async def publish(pod: Pod, record: DsuRecord, html: str, history: list[dict]) -> str:
    settings = get_settings()
    if not settings.github_owner or not settings.github_repo:
        raise RuntimeError("GITHUB_OWNER / GITHUB_REPO 未配置，跳过发布")

    date_str = record.date.isoformat()
    entries = [e for e in history if e["date"] != date_str]
    entries.append({"date": date_str, "url": f"dsu/{date_str}.html"})
    entries.sort(key=lambda e: e["date"], reverse=True)

    pod_index = render_pod_index(pod.name, pod.id, entries[:60])
    index = _merge_index(pod, record, date_str)

    files = {
        record.html_path(pod.folder): html,
        record.json_path(pod.folder): json.dumps(
            json.loads(record.model_dump_json()), ensure_ascii=False, indent=2
        ),
        f"{pod.folder}/index.html": pod_index,
        INDEX_PATH: json.dumps(index, ensure_ascii=False, indent=2),
    }

    # 延迟导入：MCP 依赖缺失不影响本地渲染与预览
    from app.mcp_client import GitHub, MCPHub

    async with MCPHub(only=["github"]) as hub:
        gh = GitHub(hub, settings.github_owner, settings.github_repo, settings.github_branch)
        await gh.push_files(files, message=f"dsu: {pod.id} {date_str}")
        root_index = render_root(_root_pods(index))
        await gh.push_files(
            {"index.html": root_index}, message=f"dsu: refresh root index ({date_str})"
        )

    return f"https://{settings.github_owner}.github.io/{settings.github_repo}/{pod.folder}/dsu/{date_str}.html"


def _merge_index(pod: Pod, record: DsuRecord, date_str: str) -> dict:
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "pods": _index_for(pod, record, date_str),
    }


def _index_for(pod: Pod, record: DsuRecord, date_str: str) -> list[dict]:
    return [
        {
            "id": pod.id,
            "name": pod.name,
            "folder": pod.folder,
            "latest": {
                "date": date_str,
                "url": f"{pod.folder}/dsu/{date_str}.html",
                "raw": f"{pod.folder}/raw/{date_str}.json",
                "blockers": record.open_blockers,
                "risk": record.risk_level,
            },
        }
    ]


def _root_pods(index: dict) -> list[dict]:
    return [
        {"id": p["id"], "name": p["name"], "entries": [p["latest"]]}
        for p in index.get("pods", [])
    ]
