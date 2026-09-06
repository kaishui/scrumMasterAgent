# LLM Skills 与 Prompt 设计（LangChain）

> 代码实现：`backend/app/skills.py`（skill 定义）+ `backend/app/llm.py`（运行封装）。
> 本文档逐环节列出每个 skill 的角色、完整 prompt、输出 schema 与 LangChain 链写法。

---

## 一、总览：五个 skill ↔ 五个流水线环节

全链路「字幕 → 报告」有五个 LLM 触点，每个触点对应一个 **skill**（角色定义 + prompt + 输出约束）：

| 阶段 | skill | 职责 | 输出类型 | 输出 schema |
|---|---|---|---|---|
| ingest | `transcript_cleaner` | 字幕清洗 | 文本 | — |
| extract | `standup_structurer` | 结构化 + 情绪/会议/冲刺 | JSON | `DsuDraft` |
| enrich | `insight_engine` | 可行动洞察 | JSON | `InsightsDraft` |
| trends | `trend_narrator` | 跨期主题 + 冲刺预测 | JSON | `TrendNarrativeDraft` |
| render | `report_summarizer` | 执行摘要 + 教练建议 | 文本 + JSON | `CoachingDraft` |

对应代码里的调用链（`backend/app/pipeline/run.py`）：

```python
transcript = await ingest.clean_transcript(pod, transcript)      # ① transcript_cleaner
record     = await extract.extract(pod, day, transcript)         # ② standup_structurer
record     = await enrich.analyze(record, pod, transcript)       # ③ insight_engine
record     = await trends.narrate(record, pod, previous)         # ④ trend_narrator
record     = await render.summarize(record, pod)                 # ⑤ report_summarizer
```

---

## 二、统一设计模式

每个 skill 的 prompt 都是**「角色 + 规则 + 输出约束」三段式**，且遵循三条铁律：

1. **明确「不要臆造」**：所有 skill 都要求「忠于原话 / 只输出真实信号 / 数据不足就留空或降置信度」——这是可信报告的生命线。
2. **数据与 prompt 分离**：prompt 只写「怎么做」，业务数据（pod、日期、转录、Jira 状态）通过 human 模板的变量注入。这样 prompt 可复用、可单测、可调。
3. **可独立降级**：结构化 skill 走 `with_structured_output` → `JsonOutputParser` → `None`（留空），任何一步失败都不阻断出报告。

运行时封装（`app/llm.py`）：

```python
async def run(prompt, **kwargs) -> str:
    """文本 skill：ChatPromptTemplate → 文本。失败返回空串。"""
    if not ready(): return ""
    try:
        resp = await (prompt | _chat()).ainvoke(kwargs)
        return (getattr(resp, "content", "") or "").strip()
    except Exception:
        return ""

async def run_structured(prompt, schema, **kwargs):
    """结构化 skill：function calling 优先，失败降级 JsonOutputParser。"""
    if not ready(): return None
    llm = _chat()
    try:
        return await (prompt | llm.with_structured_output(schema, method="function_calling")).ainvoke(kwargs)
    except Exception:
        pass
    try:
        parser = JsonOutputParser(pydantic_object=schema)
        raw = await (prompt | llm | parser).ainvoke(kwargs)
        return schema(**raw) if isinstance(raw, dict) else None
    except Exception:
        return None
```

---

## 三、逐个 skill 详解

### ① `transcript_cleaner`（ingest：字幕清洗）

**System Prompt**：

```text
你是「会议转录清洗器」。把原始 Zoom/VTT 字幕整理成干净、可读、可被下游结构化抽取的对话文本。

规则：
1. 去掉时间轴、行号、WEBVTT/SRT 头、空白行与字幕元信息。
2. 保留或推断说话人，统一输出格式「说话人: 内容」；无法确定说话人时标为「未知:」。
3. 去掉语气词（嗯、啊、呃、然后、那个…）与重复的碎句，但保留关键术语、工单号(如 PAY-123)和 PR 号。
4. 把同一人被他人打断、跨段出现的连续发言合并成一条。
5. 忠实原意：不新增、不删减、不改写事实，不改动专有名词。

只输出清洗后的对话文本，不要任何解释或前言。
```

**Human 模板**：`{transcript}`

**LangChain 定义**：

```python
clean_prompt = ChatPromptTemplate.from_messages(
    [("system", CLEAN_SYSTEM), ("human", "{transcript}")]
)
```

**调用**：

```python
cleaned = await llm.run(skills.clean_prompt, transcript=raw) or raw  # 失败原样返回
```

---

### ② `standup_structurer`（extract：结构化）

**System Prompt**：

```text
你是资深 Scrum Master，负责把每日站会(Daily Standup)转录整理成结构化记录。

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

转录里没提到的维度留 0 或空数组，不要编数字。
```

**Human 模板**：

```text
Pod: {pod}
日期: {day}
已知成员: {members}
WIP 上限: {wip}

会议转录:
{transcript}
```

**输出 schema**：`DsuDraft`（12 个字段，见 `app/skills.py`；其中 `sentiment`/`meeting`/`sprint_m` 直接复用 `models.py` 的 `SentimentMetrics`/`MeetingQuality`/`SprintMetrics`）。

**调用**：

```python
draft = await llm.run_structured(
    skills.structurer_prompt, skills.DsuDraft,
    pod=f"{pod.name}({pod.id})", day=day.isoformat(),
    members=", ".join(pod.members) or "未知",
    wip=pod.wip_limit or "未设置", transcript=transcript,
)
```

---

### ③ `insight_engine`（enrich：可行动洞察）

**System Prompt**：

```text
你是 Scrum Master 的报告洞察引擎。基于站会内容与 Jira/GitHub 工单状态，提炼 3-6 条可行动洞察。

每条洞察包含：
- kind：blocker(阻塞) / risk(风险) / win(亮点) / trend(趋势) / action(行动建议)
- text：一句话，具体、可行动，点名到人/事/工单
- severity：low / medium / high
- owner：负责人；不知道就留空

只输出真实存在的信号，不要为了凑数而编造。
```

**Human 模板**：

```text
Pod: {pod}
站会内容:
{transcript}
Jira 状态: {jira_brief}
PR: {pulls_brief}
阻塞: {blockers}
风险: {risks}
```

> 关键：这个 skill 在 `enrich.enrich()`（MCP 拉 Jira/PR 真实状态）**之后**运行，所以能把「站会里说的话」和「工具里的真实状态」对齐，避免报告出现过期信息。

**调用**：

```python
draft = await llm.run_structured(
    skills.insight_prompt, skills.InsightsDraft,
    pod=pod.name, transcript=transcript[:4000],
    jira_brief=jira_brief, pulls_brief=pulls_brief,
    blockers=record.blockers or "无",
    risks=[r.text for r in record.risks] or "无",
)
```

---

### ④ `trend_narrator`（trends：跨期主题 + 预测）

**System Prompt**：

```text
你是 Scrum Master 的趋势解读引擎。对比本期与上一期的站会数据，输出两个维度：

1. recurring_themes：跨期反复出现的主题或问题(如「部署失败连续出现」「某依赖长期阻塞」)，最多 3 条。
2. forecast：预测冲刺能否按期完成，包含：
   - on_track：能否按期(bool)
   - confidence：置信度 0-1
   - projected_completion_pct：预计完成比例 0-100
   - reasoning：2-3 句基于数据的理由

基于数据，不要臆造；数据不足时 confidence 调低并在 reasoning 说明。
```

**Human 模板**：

```text
Pod: {pod}
本期: 阻塞 {blockers}、WIP {wip}、逾期行动项 {overdue}、健康度 {health}、燃尽 {burndown}、进度 {progress}%
阻塞变化 {blocker_delta}、WIP 变化 {wip_delta}、本期解决 {resolved}
上一期: {prev_brief}
风险: {risks}
```

> 关键：`apply_trends()`（规则）先算出相邻两期的数值变化（阻塞老化、行动项携带），再交给这个 skill 做**语义层面的解读**——规则负责「数」，LLM 负责「解释」。

**调用**：

```python
draft = await llm.run_structured(
    skills.trend_prompt, skills.TrendNarrativeDraft,
    pod=pod.name, blockers=record.open_blockers, wip=record.wip,
    overdue=len(record.overdue_actions), health=record.health_score,
    burndown=record.sprint_m.burndown, progress=record.sprint_m.progress_pct,
    blocker_delta=record.trend.blockers, wip_delta=record.trend.wip,
    resolved=record.trend.resolved_since_last, prev_brief=prev_brief,
    risks=[r.text for r in record.risks] or "无",
)
```

---

### ⑤ `report_summarizer`（render：摘要 + 教练建议）

拆成两个 prompt：一个文本（执行摘要）、一个结构化（教练建议），共用同一份 `{brief}`。

**执行摘要 System Prompt**：

```text
你是 Scrum Master 的报告摘要生成器。用一段话(80-120 字)给干系人写执行摘要，覆盖三点：
1. 今天最关键的进展；
2. 最需要关注的风险/阻塞；
3. 下一步行动。
客观、克制，不要客套话，不要堆砌数据。
```

**教练建议 System Prompt**：

```text
你是资深 Scrum Master 教练。基于这份站会数据，给出 2-4 条给团队/Scrum Master 的改进建议。

每条要求：
- 一句话、可执行；
- 聚焦流程与协作问题(如阻塞升级、WIP 收敛、会议聚焦、负载均衡)；
- 指出问题与具体做法，不空喊口号。
```

**调用**：

```python
brief = _brief(record, pod)  # 把健康度/阻塞/风险/燃尽/情绪/决策压缩成一段
record.executive_summary = await llm.run(skills.summary_prompt, brief=brief)
draft = await llm.run_structured(skills.coach_prompt, skills.CoachingDraft, brief=brief)
```

---

## 四、降级链（全链路统一）

```
with_structured_output（function calling）
        │ 失败
        ▼
JsonOutputParser（prompt 里内嵌 JSON 格式说明）
        │ 失败
        ▼
返回 None / 空串（该字段留空，其余维度照常）  ← LLM 挂了也绝不阻断出报告
```

- 文本 skill（①⑤ 摘要）：失败返回空串，字段留空。
- 结构化 skill（②③④⑤ 教练）：失败返回 `None`，字段保持默认空值。
- 唯一例外是 `extract`：LLM 全链路失败时退回**规则切分**（按「说话人: 内容」分桶），保证 `updates` 至少有内容，报告永远出得来。

---

## 五、如何新增 / 修改一个 skill

1. 在 `backend/app/skills.py` 里加一段：`XXX_SYSTEM` + `xxx_prompt = ChatPromptTemplate.from_messages([...])`，结构化 skill 再加一个 pydantic `XxxDraft`（复用 `models.py` 的维度类型）。
2. 在 `SKILLS` 注册表登记 metadata（stage / description / output / schema / prompt）。
3. 在对应 pipeline 模块里 `from app import skills` 后调用 `llm.run` / `llm.run_structured`，变量名与 human 模板占位符对齐。
4. 跑 `backend/verify.sh` 确认 import + fallback 路径不回归。

**调 prompt 的通用心法**（基于本项目踩坑）：
- 结构化字段越具体越好——每条规则写清「字段名 + 含义 + 何时留空」。
- 「不要臆造」必须显式写进 prompt，且配合 `Literal` 枚举与默认空值兜底。
- 需要 LLM 判断「是否有信号」的（如情绪、预测），要给出「数据不足时如何降级」的指令，避免编造。
