from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # LLM（兼容 OpenAI 协议的任意网关 / 内部模型服务）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # Zoom Server-to-Server OAuth
    zoom_account_id: str = ""
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    # 取谁名下的录制，通常用 'me'
    zoom_user_id: str = "me"

    # 内部 Jira（Server / Data Center）
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    # true 表示 Server/DC，用 PAT 做 Basic 认证；false 为 Cloud
    jira_dc: bool = True

    # GitHub 发布目标
    github_owner: str = ""
    github_repo: str = ""
    github_branch: str = "main"

    # 生成后直接提交，不等人工确认
    auto_commit: bool = False

    mcp_config: Path = ROOT / "config" / "mcp.json"
    pods_config: Path = ROOT / "config" / "pods.yaml"

    workdir: Path = ROOT / ".workdir"
    timezone: str = "Asia/Shanghai"
    require_human_approval: bool = True


class Meeting(BaseModel):
    """source: local_file | zoom | teams | feishu"""

    source: str = "local_file"
    path: str = ""
    time: str = "09:30"
    timezone: str = "Asia/Shanghai"
    # zoom 模式下按主题匹配会议
    zoom_topic: str = ""


class Pod(BaseModel):
    id: str
    name: str
    folder: str
    jira_board: int | None = None
    jira_project: str = ""
    github_repos: list[str] = []
    members: list[str] = []
    meeting: Meeting = Meeting()
    wip_limit: int | None = None
    require_approval: bool = True
    allow_jira_write: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_pods() -> list[Pod]:
    cfg = yaml.safe_load(get_settings().pods_config.read_text(encoding="utf-8")) or {}
    defaults = cfg.get("defaults", {})
    pods: list[Pod] = []
    for raw in cfg.get("pods", []):
        data = dict(raw)
        data.setdefault("require_approval", defaults.get("require_approval", True))
        data.setdefault("allow_jira_write", defaults.get("allow_jira_write", False))
        data.setdefault("jira_project", defaults.get("jira_project", ""))
        data.setdefault("wip_limit", defaults.get("wip_limit"))
        pods.append(Pod(**data))
    return pods


def get_pod(pod_id: str) -> Pod:
    for pod in load_pods():
        if pod.id == pod_id:
            return pod
    raise KeyError(f"unknown pod: {pod_id}")


def transcript_dir(pod: Pod) -> Path:
    return ROOT / (pod.meeting.path or f"data/transcripts/{pod.id}")
