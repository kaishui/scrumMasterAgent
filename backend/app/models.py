from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class JiraRef(BaseModel):
    key: str
    summary: str = ""
    status: str = ""
    assignee: str = ""
    url: str = ""


class PullRef(BaseModel):
    repo: str
    number: int
    title: str = ""
    state: str = ""
    url: str = ""


class PersonUpdate(BaseModel):
    person: str
    yesterday: list[str] = Field(default_factory=list)
    today: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    jira_keys: list[str] = Field(default_factory=list)
    prs: list[int] = Field(default_factory=list)


class ActionItem(BaseModel):
    owner: str = ""
    text: str
    due: date | None = None
    jira_key: str | None = None
    done: bool = False
    # 从哪一期带过来的，用来算闭环周期
    carried_from: str | None = None

    @property
    def overdue(self) -> bool:
        if self.done or self.due is None:
            return False
        return self.due < date.today()


class Risk(BaseModel):
    level: Literal["low", "medium", "high"] = "medium"
    text: str
    owner: str = ""


# ---------- 报告维度 ----------


class DeliveryMetrics(BaseModel):
    """交付进展：做完了什么、还剩多少、范围有没有蔓延。"""

    done_yesterday: int = 0
    planned_today: int = 0
    wip: int = 0
    sprint_commitment: int = 0
    sprint_completed: int = 0
    sprint_remaining: int = 0
    scope_changes: list[str] = Field(default_factory=list)


class BlockerMetrics(BaseModel):
    """阻塞与依赖：数量、老化天数、跨团队与外部依赖。"""

    total: int = 0
    new: int = 0
    resolved: int = 0
    aging_days: dict[str, int] = Field(default_factory=dict)
    cross_team: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class QualityMetrics(BaseModel):
    """质量与风险：缺陷、CI、部署、线上事故。"""

    bugs_opened: int = 0
    bugs_closed: int = 0
    bugs_open: int = 0
    ci_failures: int = 0
    deploys: int = 0
    incidents: list[str] = Field(default_factory=list)


class FlowMetrics(BaseModel):
    """流动效率：卡在哪、卡多久、WIP 有没有超上限。"""

    cycle_time_days: float | None = None
    lead_time_days: float | None = None
    stale_tickets: list[str] = Field(default_factory=list)
    wip_limit: int | None = None

    @property
    def wip_breached(self) -> bool:
        return self.wip_limit is not None and len(self.stale_tickets) > self.wip_limit


class TeamMetrics(BaseModel):
    """团队与协作：参与度、负载是否失衡。"""

    participants: int = 0
    silent: list[str] = Field(default_factory=list)
    load_by_person: dict[str, int] = Field(default_factory=dict)
    overloaded: list[str] = Field(default_factory=list)


class TrendDelta(BaseModel):
    """与前一期对比，只看变化量。"""

    blockers: int = 0
    wip: int = 0
    overdue_actions: int = 0
    resolved_since_last: int = 0


class DsuRecord(BaseModel):
    """一期 DSU 的结构化原件，也是对外数据契约。"""

    pod: str
    date: date
    sprint: str = ""
    attendees: list[str] = Field(default_factory=list)
    updates: list[PersonUpdate] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    jira: list[JiraRef] = Field(default_factory=list)
    pulls: list[PullRef] = Field(default_factory=list)

    delivery: DeliveryMetrics = Field(default_factory=DeliveryMetrics)
    blockers_m: BlockerMetrics = Field(default_factory=BlockerMetrics)
    quality: QualityMetrics = Field(default_factory=QualityMetrics)
    flow: FlowMetrics = Field(default_factory=FlowMetrics)
    team: TeamMetrics = Field(default_factory=TeamMetrics)
    trend: TrendDelta = Field(default_factory=TrendDelta)

    source: str = ""
    approved: bool = False

    @computed_field
    @property
    def blockers(self) -> list[str]:
        out: list[str] = []
        for u in self.updates:
            out.extend(f"{u.person}: {b}" for b in u.blockers)
        return out

    @computed_field
    @property
    def open_blockers(self) -> int:
        return len(self.blockers)

    @computed_field
    @property
    def wip(self) -> int:
        return self.delivery.wip or sum(len(u.today) for u in self.updates)

    @computed_field
    @property
    def overdue_actions(self) -> list[str]:
        return [a.text for a in self.action_items if a.overdue]

    @computed_field
    @property
    def risk_level(self) -> str:
        score = self.health_score
        if score < 60:
            return "high"
        if score < 80:
            return "medium"
        return "low"

    @computed_field
    @property
    def health_score(self) -> int:
        """团队健康度 0-100：阻塞、逾期行动项、风险、流动停滞各扣一档。"""
        score = 100
        score -= min(30, self.open_blockers * 10)
        score -= min(20, len(self.overdue_actions) * 7)
        score -= min(20, sum(4 for r in self.risks if r.level == "high"))
        score -= min(15, sum(2 for r in self.risks if r.level == "medium"))
        score -= min(15, len(self.flow.stale_tickets) * 3)
        if self.flow.wip_breached:
            score -= 10
        return max(0, score)

    def json_path(self, folder: str) -> str:
        return f"{folder}/raw/{self.date.isoformat()}.json"

    def html_path(self, folder: str) -> str:
        return f"{folder}/dsu/{self.date.isoformat()}.html"
