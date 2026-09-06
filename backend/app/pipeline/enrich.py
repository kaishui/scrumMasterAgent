"""用 Jira / GitHub MCP 补齐真实状态，避免报告里出现过期信息。"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.config import Pod
from app.models import DsuRecord, Insight, JiraRef, PullRef

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")
PR_RE = re.compile(r"(?:#|PR\s*|pr\s*)(\d{2,6})")


async def enrich(record: DsuRecord, pod: Pod) -> DsuRecord:
    # 延迟导入：没装 mcp 依赖时，纯本地渲染链路依然能跑
    from app.mcp_client import GitHub, Jira, MCPHub

    async with MCPHub() as hub:
        jira = Jira(hub, allow_write=pod.allow_jira_write)
        gh = GitHub(hub, owner=_owner(), repo=_repo(), branch=_branch())
        await _enrich_jira(record, pod, jira)
        await _enrich_pulls(record, pod, gh)
    return record


async def _enrich_jira(record: DsuRecord, pod: Pod, jira: Jira) -> None:
    keys: list[str] = []
    for u in record.updates:
        for content in [*u.yesterday, *u.today, *u.blockers]:
            keys.extend(KEY_RE.findall(content))
        keys.extend(u.jira_keys)
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        try:
            data = await jira.issue(key)
        except Exception:
            record.jira.append(JiraRef(key=key, summary="(Jira 不可达)"))
            continue
        fields = data.get("fields", data)
        record.jira.append(
            JiraRef(
                key=key,
                summary=fields.get("summary", ""),
                status=(fields.get("status") or {}).get("name", "")
                if isinstance(fields.get("status"), dict)
                else str(fields.get("status", "")),
                assignee=(fields.get("assignee") or {}).get("displayName", "")
                if isinstance(fields.get("assignee"), dict)
                else "",
                url=f"{_jira_base()}/browse/{key}",
            )
        )


async def _enrich_pulls(record: DsuRecord, pod: Pod, gh: GitHub) -> None:
    opened: dict[str, list[dict]] = {}
    for repo in pod.github_repos:
        try:
            opened[repo] = await gh.open_pulls(repo)
        except Exception:
            opened[repo] = []

    for u in record.updates:
        for content in [*u.yesterday, *u.today]:
            u.prs.extend(int(n) for n in PR_RE.findall(content))
        u.prs = sorted(set(u.prs))

    numbers = {n for u in record.updates for n in u.prs}
    if not numbers:
        return
    for repo, pulls in opened.items():
        for pr in pulls:
            if int(pr.get("number", 0)) in numbers:
                record.pulls.append(
                    PullRef(
                        repo=repo,
                        number=int(pr["number"]),
                        title=pr.get("title", ""),
                        state=pr.get("state", ""),
                        url=pr.get("html_url", pr.get("url", "")),
                    )
                )


def _owner() -> str:
    from app.config import get_settings

    return get_settings().github_owner


def _repo() -> str:
    from app.config import get_settings

    return get_settings().github_repo


def _branch() -> str:
    from app.config import get_settings

    return get_settings().github_branch


def _jira_base() -> str:
    import os

    return os.getenv("JIRA_URL", "").rstrip("/")


# ---------- LLM 洞察 ----------


class InsightsDraft(BaseModel):
    insights: list[Insight] = Field(default_factory=list)


async def analyze(record: DsuRecord, pod: Pod, transcript: str) -> DsuRecord:
    """LLM 洞察：综合站会内容与 Jira/GitHub 富化结果，产出可行动洞察。失败则原样返回。"""
    from app.llm import complete_json, ready

    if not ready():
        return record

    jira_brief = "; ".join(f"{j.key}:{j.status}" for j in record.jira) or "无"
    pulls_brief = "; ".join(f"{p.repo}#{p.number}:{p.state}" for p in record.pulls) or "无"
    system = (
        "你是 Scrum Master 的报告洞察引擎。基于站会内容与工具状态，提炼 3-6 条可行动洞察。"
        "每条包含 kind(blocker/risk/win/trend/action)、text(一句话，具体可行动)、"
        "severity(low/medium/high)、owner(负责人，不知道留空)。只输出真实存在的信号，不要编造。"
    )
    user = (
        f"Pod: {pod.name}\n站会内容:\n{transcript[:4000]}\n"
        f"Jira 状态: {jira_brief}\nPR: {pulls_brief}\n"
        f"阻塞: {record.blockers or '无'}\n风险: {[r.text for r in record.risks] or '无'}"
    )
    draft = await complete_json(system, user, InsightsDraft)
    if draft:
        record.insights = [i for i in draft.insights if i.text.strip()]
    return record
