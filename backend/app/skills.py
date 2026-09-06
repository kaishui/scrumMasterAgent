"""流水线各环节的「skill」：角色定义 + 提示词模板 + 输出 schema（LangChain 统一组织）。

五个 LLM 触点 ↔ 五个 skill：

    ┌──────────┬────────────────────┬─────────────────────────────┬──────────────────────┐
    │ 阶段     │ skill              │ 职责                        │ 输出                 │
    ├──────────┼────────────────────┼─────────────────────────────┼──────────────────────┤
    │ ingest   │ transcript_cleaner │ 字幕清洗                    │ 文本                 │
    │ extract  │ standup_structurer │ 结构化 + 情绪/会议/冲刺     │ DsuDraft             │
    │ enrich   │ insight_engine     │ 可行动洞察                  │ InsightsDraft        │
    │ trends   │ trend_narrator     │ 跨期主题 + 冲刺预测         │ TrendNarrativeDraft  │
    │ render   │ report_summarizer  │ 执行摘要 + 教练建议         │ 文本 + CoachingDraft │
    └──────────┴────────────────────┴─────────────────────────────┴──────────────────────┘

各 pipeline 模块用法：

    from app import skills, llm

    # 纯文本 skill
    text = await llm.run(skills.clean_prompt, transcript=raw)

    # 结构化 skill
    draft = await llm.run_structured(
        skills.structurer_prompt, skills.DsuDraft,
        pod="支付组(payments-pod)", day="2026-09-06",
        members="alice, bob, carol", wip="3", transcript=raw,
    )

设计原则（全链路统一）：
- 每个 skill 都是「角色 + 规则 + 输出约束」三段式 system prompt，明确「不要臆造」。
- 结构化 skill 用 pydantic schema 强约束输出，配合 with_structured_output / JsonOutputParser 降级。
- prompt 只描述「怎么做」，不携带业务数据；数据经 human 模板变量注入，便于复用与测试。
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.models import (
    ActionItem,
    DeliveryMetrics,
    Forecast,
    Insight,
    MeetingQuality,
    PersonUpdate,
    QualityMetrics,
    Risk,
    SentimentMetrics,
    SprintMetrics,
)


# ============================================================================
# ① transcript_cleaner —— ingest：把原始字幕清洗成干净对话
# ============================================================================

CLEAN_SYSTEM = """你是「会议转录清洗器」。把原始 Zoom/VTT 字幕整理成干净、可读、可被下游结构化抽取的对话文本。

规则：
1. 去掉时间轴、行号、WEBVTT/SRT 头、空白行与字幕元信息。
2. 保留或推断说话人，统一输出格式「说话人: 内容」；无法确定说话人时标为「未知:」。
3. 去掉语气词（嗯、啊、呃、然后、那个…）与重复的碎句，但保留关键术语、工单号(如 PAY-123)和 PR 号。
4. 把同一人被他人打断、跨段出现的连续发言合并成一条。
5. 忠实原意：不新增、不删减、不改写事实，不改动专有名词。

只输出清洗后的对话文本，不要任何解释或前言。"""

clean_prompt = ChatPromptTemplate.from_messages(
    [("system", CLEAN_SYSTEM), ("human", "{transcript}")]
)


# ============================================================================
# ② standup_structurer —— extract：结构化 + 情绪/会议质量/冲刺健康
# ============================================================================

class BlockersDraft(BaseModel):
    new: int = 0
    resolved: int = 0
    cross_team: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class FlowDraft(BaseModel):
    stale_tickets: list[str] = Field(default_factory=list)
    cycle_time_days: float | None = None


class TeamDraft(BaseModel):
    silent: list[str] = Field(default_factory=list)
    load_by_person: dict[str, int] = Field(default_factory=dict)


class DsuDraft(BaseModel):
    sprint: str = ""
    attendees: list[str] = Field(default_factory=list)
    updates: list[PersonUpdate] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    delivery: DeliveryMetrics = Field(default_factory=DeliveryMetrics)
    blocker_summary: BlockersDraft = Field(default_factory=BlockersDraft)
    quality: QualityMetrics = Field(default_factory=QualityMetrics)
    flow: FlowDraft = Field(default_factory=FlowDraft)
    team: TeamDraft = Field(default_factory=TeamDraft)
    sentiment: SentimentMetrics = Field(default_factory=SentimentMetrics)
    meeting: MeetingQuality = Field(default_factory=MeetingQuality)
    sprint_m: SprintMetrics = Field(default_factory=SprintMetrics)


STRUCTURER_SYSTEM = """你是资深 Scrum Master，负责把每日站会(Daily Standup)转录整理成结构化记录。

严格按维度输出，忠于原话，不要臆造：

1. updates：按人切分「昨天 yesterday / 今天 today / 阻塞 blockers」。提到 Jira 工单号(如 PAY-123)
   填进 jira_keys，提到 PR 号填进 prs。
2. decisions：会上明确的结论。没有就空数组。
3. action_items：必须有 owner 和可验证的动作，尽量带 due。
4. risks：延期、依赖、资源、质量风险，标注 low/medium/high。
5. delivery：昨日完成/今日计划条目数、WIP、冲刺承诺与完成情况、范围变更。
6. blocker_summary：新增(new)与解决(resolved)的阻塞数；跨团队依赖(cross_team)和外部依赖(external)单独列。
7. quality：缺陷开关、CI 失败、部署次数、线上事故。
8. flow：卡住超过 3 天的工单(写清卡在哪个状态)、周期时间 cycle_time_days。
9. team：全程没发言的人(silent)、每人当前在办条目数(load_by_person，看负载是否失衡)。
10. sentiment：从措辞与语气判断团队情绪 overall(positive/neutral/stressed/negative)、
    异常信号 signals、可能的过载/burnout 成员 burnout_risk，附一句 note。
11. meeting：站会是否聚焦——focus_score(0-100)、是否围绕三大问题 on_agenda、
    跑题内容 tangents，附一句 note。
12. sprint_m：冲刺目标 goal、承诺点数 committed_points、已完成点数 completed_points、
    近期速度 velocity_points、燃尽 burndown(on_track/behind/ahead/unknown)、范围蔓延 scope_creep。

转录里没提到的维度留 0 或空数组，不要编数字。"""

structurer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", STRUCTURER_SYSTEM),
        (
            "human",
            "Pod: {pod}\n日期: {day}\n已知成员: {members}\nWIP 上限: {wip}\n\n会议转录:\n{transcript}",
        ),
    ]
)


# ============================================================================
# ③ insight_engine —— enrich：综合站会 + Jira/PR，提炼可行动洞察
# ============================================================================

class InsightsDraft(BaseModel):
    insights: list[Insight] = Field(default_factory=list)


INSIGHT_SYSTEM = """你是 Scrum Master 的报告洞察引擎。基于站会内容与 Jira/GitHub 工单状态，提炼 3-6 条可行动洞察。

每条洞察包含：
- kind：blocker(阻塞) / risk(风险) / win(亮点) / trend(趋势) / action(行动建议)
- text：一句话，具体、可行动，点名到人/事/工单
- severity：low / medium / high
- owner：负责人；不知道就留空

只输出真实存在的信号，不要为了凑数而编造。"""

insight_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", INSIGHT_SYSTEM),
        (
            "human",
            "Pod: {pod}\n站会内容:\n{transcript}\n"
            "Jira 状态: {jira_brief}\nPR: {pulls_brief}\n"
            "阻塞: {blockers}\n风险: {risks}",
        ),
    ]
)


# ============================================================================
# ④ trend_narrator —— trends：跨期反复主题 + 冲刺结果预测
# ============================================================================

class TrendNarrativeDraft(BaseModel):
    recurring_themes: list[str] = Field(default_factory=list)
    forecast: Forecast = Field(default_factory=Forecast)


TREND_SYSTEM = """你是 Scrum Master 的趋势解读引擎。对比本期与上一期的站会数据，输出两个维度：

1. recurring_themes：跨期反复出现的主题或问题(如「部署失败连续出现」「某依赖长期阻塞」)，最多 3 条。
2. forecast：预测冲刺能否按期完成，包含：
   - on_track：能否按期(bool)
   - confidence：置信度 0-1
   - projected_completion_pct：预计完成比例 0-100
   - reasoning：2-3 句基于数据的理由

基于数据，不要臆造；数据不足时 confidence 调低并在 reasoning 说明。"""

trend_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", TREND_SYSTEM),
        (
            "human",
            "Pod: {pod}\n"
            "本期: 阻塞 {blockers}、WIP {wip}、逾期行动项 {overdue}、健康度 {health}、"
            "燃尽 {burndown}、进度 {progress}%\n"
            "阻塞变化 {blocker_delta}、WIP 变化 {wip_delta}、本期解决 {resolved}\n"
            "上一期: {prev_brief}\n"
            "风险: {risks}",
        ),
    ]
)


# ============================================================================
# ⑤ report_summarizer —— render：执行摘要 + 教练建议
# ============================================================================

class CoachingDraft(BaseModel):
    notes: list[str] = Field(default_factory=list)


SUMMARY_SYSTEM = """你是 Scrum Master 的报告摘要生成器。用一段话(80-120 字)给干系人写执行摘要，覆盖三点：
1. 今天最关键的进展；
2. 最需要关注的风险/阻塞；
3. 下一步行动。
客观、克制，不要客套话，不要堆砌数据。"""

summary_prompt = ChatPromptTemplate.from_messages(
    [("system", SUMMARY_SYSTEM), ("human", "{brief}")]
)


COACH_SYSTEM = """你是资深 Scrum Master 教练。基于这份站会数据，给出 2-4 条给团队/Scrum Master 的改进建议。

每条要求：
- 一句话、可执行；
- 聚焦流程与协作问题(如阻塞升级、WIP 收敛、会议聚焦、负载均衡)；
- 指出问题与具体做法，不空喊口号。"""

coach_prompt = ChatPromptTemplate.from_messages(
    [("system", COACH_SYSTEM), ("human", "{brief}")]
)


# ============================================================================
# skill 注册表：自文档化，便于列清单 / 批量测试 / 前端展示
# ============================================================================

SKILLS: dict[str, dict] = {
    "transcript_cleaner": {
        "stage": "ingest",
        "description": "把原始字幕清洗成干净对话，保留说话人与事实",
        "output": "text",
        "prompt": clean_prompt,
    },
    "standup_structurer": {
        "stage": "extract",
        "description": "结构化站会：三问 + 情绪/会议质量/冲刺健康",
        "output": "DsuDraft",
        "schema": DsuDraft,
        "prompt": structurer_prompt,
    },
    "insight_engine": {
        "stage": "enrich",
        "description": "综合站会 + Jira/PR 状态，提炼可行动洞察",
        "output": "InsightsDraft",
        "schema": InsightsDraft,
        "prompt": insight_prompt,
    },
    "trend_narrator": {
        "stage": "trends",
        "description": "识别跨期反复主题 + 预测冲刺结果",
        "output": "TrendNarrativeDraft",
        "schema": TrendNarrativeDraft,
        "prompt": trend_prompt,
    },
    "report_summarizer": {
        "stage": "render",
        "description": "执行摘要(文本) + 教练建议(CoachingDraft)",
        "output": "text + CoachingDraft",
        "schema": CoachingDraft,
        "prompt": summary_prompt,  # 摘要用；教练建议见 coach_prompt
    },
}
