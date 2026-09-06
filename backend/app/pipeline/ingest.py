"""会议来源适配层。

- local_file: 本地文本文件，P0 阶段用
- zoom: 通过 Zoom Server-to-Server OAuth 拉取云录制的 transcript(VTT)
- teams / feishu: 预留接口，接的时候补一个分支即可

Zoom 下来的原始 VTT 会缓存到 data/transcripts/<pod>/，避免重复拉、也便于人工修订。
"""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path

from app.config import Pod, get_settings, transcript_dir

SUFFIXES = (".txt", ".md", ".vtt", ".srt")
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API = "https://api.zoom.us/v2"


def load_transcript(pod: Pod, day: date, explicit: Path | None = None) -> str:
    if explicit is not None:
        return _clean(Path(explicit).read_text(encoding="utf-8"))

    cached = _cached(pod, day)
    if cached is not None:
        return _clean(cached.read_text(encoding="utf-8"))

    if pod.meeting.source == "local_file":
        text = _from_local_file(pod, day)
    elif pod.meeting.source == "zoom":
        text = _from_zoom(pod, day)
    else:
        raise NotImplementedError(
            f"meeting source '{pod.meeting.source}' 还没接；"
            f"先把转录放到 {transcript_dir(pod)}/{day.isoformat()}.txt 可绕过"
        )

    _cache(pod, day, text)
    return _clean(text)


# ---------- local file ----------


def _from_local_file(pod: Pod, day: date) -> str:
    base = transcript_dir(pod)
    stamp = day.isoformat()
    for suffix in SUFFIXES:
        candidate = base / f"{stamp}{suffix}"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    if base.exists():
        files = sorted(p for p in base.iterdir() if p.suffix in SUFFIXES)
        if files:
            return files[-1].read_text(encoding="utf-8")

    raise FileNotFoundError(f"{pod.id} 在 {stamp} 没有转录（找过 {base}）")


# ---------- zoom ----------


def _from_zoom(pod: Pod, day: date) -> str:
    import httpx  # 延迟导入：不开 Zoom 时不需要装

    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("ZOOM_ACCOUNT_ID", settings.zoom_account_id),
            ("ZOOM_CLIENT_ID", settings.zoom_client_id),
            ("ZOOM_CLIENT_SECRET", settings.zoom_client_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Zoom 未配置：{', '.join(missing)}")

    token = _zoom_token(settings)
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30, headers=headers) as client:
        resp = client.get(
            f"{ZOOM_API}/users/{settings.zoom_user_id}/recordings",
            params={"from": day.isoformat(), "to": day.isoformat(), "page_size": 100},
        )
        resp.raise_for_status()
        meetings = resp.json().get("meetings", [])

        topic = pod.meeting.zoom_topic
        if topic:
            meetings = [m for m in meetings if topic.lower() in (m.get("topic") or "").lower()]
        if not meetings:
            raise FileNotFoundError(f"Zoom 上找不到 {day} 的{pod.name}录制")

        for meeting in meetings:
            for f in meeting.get("recording_files", []):
                if f.get("file_type") != "TRANSCRIPT":
                    continue
                url = f.get("download_url")
                if not url:
                    continue
                vtt = client.get(url)
                vtt.raise_for_status()
                return vtt.text

    raise FileNotFoundError(f"{day} 的 Zoom 录制没有 transcript，确认云录制已开启音频转写")


def _zoom_token(settings) -> str:
    import httpx

    basic = base64.b64encode(
        f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode()
    ).decode()
    resp = httpx.post(
        ZOOM_TOKEN_URL,
        params={"grant_type": "account_credentials", "account_id": settings.zoom_account_id},
        headers={"Authorization": f"Basic {basic}"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------- cache ----------


def _cached(pod: Pod, day: date) -> Path | None:
    base = transcript_dir(pod)
    for suffix in SUFFIXES:
        candidate = base / f"{day.isoformat()}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _cache(pod: Pod, day: date, text: str) -> None:
    base = transcript_dir(pod)
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{day.isoformat()}.vtt").write_text(text, encoding="utf-8")


def _clean(text: str) -> str:
    """去掉 VTT/SRT 的时间轴与序号，只留说话内容。"""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        if line.upper().startswith(("WEBVTT", "NOTE", "STYLE", "Kind:", "Language:")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()
