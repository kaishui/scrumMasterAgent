from __future__ import annotations

from datetime import datetime

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
