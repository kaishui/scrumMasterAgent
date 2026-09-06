from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings, load_pods
from app.models import DsuRecord
from app.pipeline import publish, render
from app.pipeline.run import run_pipeline, today_for

app = FastAPI(title="Scrum Master Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/pods")
async def list_pods():
    return [p.model_dump() for p in load_pods()]


@app.get("/api/dsu/{pod_id}")
async def list_dsu(pod_id: str):
    root = get_settings().workdir / _folder(pod_id) / "raw"
    if not root.exists():
        return []
    out = []
    for f in sorted(root.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


@app.get("/api/dsu/{pod_id}/{day}")
async def get_dsu(pod_id: str, day: str):
    path = get_settings().workdir / _folder(pod_id) / "raw" / f"{day}.json"
    if not path.exists():
        raise HTTPException(404, "没有这一天的 DSU")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/dsu/{pod_id}/{day}", response_class=HTMLResponse)
async def view_dsu(pod_id: str, day: str):
    path = get_settings().workdir / _folder(pod_id) / "dsu" / f"{day}.html"
    if not path.exists():
        raise HTTPException(404, "没有这一天的报告")
    return path.read_text(encoding="utf-8")


@app.post("/api/dsu/{pod_id}/generate")
async def generate(
    pod_id: str,
    day: str | None = None,
    transcript_path: str | None = None,
    do_publish: bool = False,
    use_mcp: bool = True,
):
    from app.config import get_pod

    pod = get_pod(pod_id)
    target = date.fromisoformat(day) if day else today_for(pod)
    result = await run_pipeline(
        pod_id,
        target,
        Path(transcript_path) if transcript_path else None,
        do_publish=do_publish,
        use_mcp=use_mcp,
    )
    return {
        "pod": result.pod,
        "date": result.date,
        "local_html": result.local_html,
        "url": result.url,
        "published": result.published,
        "pending_approval": result.pending_approval,
        "notes": result.notes,
        "record": json.loads(result.record.model_dump_json()),
    }


@app.post("/api/dsu/{pod_id}/{day}/approve")
async def approve(pod_id: str, day: str):
    """人工确认闸门：把草稿标记为已确认并真正发布。"""
    from app.config import get_pod

    pod = get_pod(pod_id)
    raw = get_settings().workdir / pod.folder / "raw" / f"{day}.json"
    if not raw.exists():
        raise HTTPException(404, "草稿不存在，先跑一次 generate")

    record = DsuRecord(**json.loads(raw.read_text(encoding="utf-8")))
    record.approved = True
    raw.write_text(
        json.dumps(json.loads(record.model_dump_json()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    html = render.render_dsu(record, pod.name)
    publish.save_local(record, pod, html)
    url = await publish.publish(pod, record, html, _history(pod))
    return {"published": True, "url": url}


def _history(pod) -> list[dict]:
    root = get_settings().workdir / pod.folder / "raw"
    if not root.exists():
        return []
    return [{"date": f.stem, "url": f"dsu/{f.stem}.html"} for f in sorted(root.glob("*.json"), reverse=True)]


def _folder(pod_id: str) -> str:
    from app.config import get_pod

    return get_pod(pod_id).folder
