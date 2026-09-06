"""统一的 MCP 客户端：用一份 mcp.json 同时挂上 Jira 与 GitHub。

连接方式用 stdio，和 `~/.workbuddy/mcp.json` 里 server 的写法完全一致，
因此本地调试换 server 不需要改业务代码。
"""

from __future__ import annotations

import json
import os
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def _expand(value: str) -> str:
    return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)


class MCPHub:
    def __init__(self, config_path: Path | None = None, only: list[str] | None = None):
        from app.config import get_settings

        self.config_path = Path(config_path or get_settings().mcp_config)
        self.only = only
        self.sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "MCPHub":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def start(self) -> None:
        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        await self._stack.__aenter__()
        for name, srv in cfg.get("mcpServers", {}).items():
            if self.only and name not in self.only:
                continue
            env = {**os.environ, **{k: _expand(v) for k, v in srv.get("env", {}).items()}}
            params = StdioServerParameters(
                command=srv["command"],
                args=srv.get("args", []),
                env=env,
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session

    async def aclose(self) -> None:
        await self._stack.aclose()

    async def call(self, server: str, tool: str, **args: Any) -> Any:
        session = self.sessions.get(server)
        if session is None:
            raise RuntimeError(f"MCP server not connected: {server}")
        result = await session.call_tool(tool, args)
        text = "".join(getattr(c, "text", "") for c in result.content)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    async def tools(self, server: str) -> list[str]:
        result = await self.sessions[server].list_tools()
        return [t.name for t in result.tools]


class Jira:
    """Jira MCP 封装。默认只读；写操作需要 pod.allow_jira_write 显式放行。"""

    def __init__(self, hub: MCPHub, allow_write: bool = False):
        self.hub = hub
        self.allow_write = allow_write

    async def issue(self, key: str) -> dict:
        data = await self.hub.call("jira", "jira_get_issue", issue_key=key)
        return _first(data)

    async def board_issues(self, board_id: int, jql: str = "", limit: int = 50) -> list[dict]:
        data = await self.hub.call(
            "jira", "jira_get_board_issues", board_id=board_id, jql=jql, max_results=limit
        )
        return _as_list(data)

    async def create_issue(self, project: str, summary: str, description: str = "") -> dict:
        if not self.allow_write:
            raise PermissionError("Jira write disabled (allow_jira_write=false)")
        data = await self.hub.call(
            "jira",
            "jira_create_issue",
            project_key=project,
            summary=summary,
            description=description,
            issue_type="Task",
        )
        return _first(data)


class GitHub:
    """GitHub MCP 封装：批量提交 + 读文件，用于发布静态报告。"""

    def __init__(self, hub: MCPHub, owner: str, repo: str, branch: str = "main"):
        self.hub = hub
        self.owner = owner
        self.repo = repo
        self.branch = branch

    async def push_files(self, files: dict[str, str], message: str) -> Any:
        payload = [{"path": p, "content": c} for p, c in files.items()]
        return await self.hub.call(
            "github",
            "push_files",
            owner=self.owner,
            repo=self.repo,
            branch=self.branch,
            message=message,
            files=payload,
        )

    async def get_file(self, path: str) -> dict | None:
        try:
            data = await self.hub.call(
                "github",
                "get_file_contents",
                owner=self.owner,
                repo=self.repo,
                path=path,
                branch=self.branch,
            )
        except Exception:
            return None
        return _first(data)

    async def open_pulls(self, repo: str) -> list[dict]:
        data = await self.hub.call(
            "github", "list_pull_requests", owner=self.owner, repo=repo, state="open"
        )
        return _as_list(data)


def _first(data: Any) -> Any:
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def _as_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("issues", "items", "results", "values"):
            if isinstance(data.get(key), list):
                return data[key]
    return []
