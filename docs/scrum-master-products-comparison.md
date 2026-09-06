# Scrum Master 产品调研对比报告

> 调研日期：2026-09-06
> 目的：对比市面成熟 Scrum Master / 敏捷站会 / 工程效能产品，明确它们在**报告输出什么维度**、**为不同角色提供什么视角**，作为本项目（Scrum Master Agent）的参照系与差异化锚点。

---

## 一、摘要（TL;DR）

市面上的「Scrum Master 类产品」实际上分成了**三个泾渭分明的赛道**，它们输出的维度与服务的角色完全不同：

| 赛道 | 代表产品 | 核心能力 | 报告维度重心 | 服务角色 |
|---|---|---|---|---|
| **A. 会议/站会助手**（仪式自动化） | Spinach AI、Geekbot、Standuply、Range、DailyBot、Status Hero | 自动记录、摘要、行动项、同步 Jira | 「谁说了什么 → 决策/行动项/阻塞/情绪」 | 团队全员、SM、PM |
| **B. 工程效能平台**（指标+改进） | LinearB、Swarmia、Waydev | DORA/SPACE 指标 + 工作流自动化 + 团队健康 | 「交付效率/周期时间/健康度/投资分配」 | EM、Director |
| **C. 高管/经营智能**（战略对齐） | Jellyfish、Pluralsight Flow | 投资分配、研发资本化、董事会级报告 | 「钱花在哪、产能规划、业务对齐」 | VP/CTO/CFO |

**关键洞察**：
1. **没有一家产品同时覆盖「每日站会级」和「高管级」两种粒度**——这正是本项目（一份 raw JSON 派生多角色视图）的机会。
2. **报告维度已从「记录」演进到「诊断」**：成熟产品都在输出**健康度、情绪、预测、教练建议**，而非只记录「昨天/今天/阻塞」。
3. **角色视角是产品的分水岭**：C 类产品靠「给高管看的语言」卖出 10 万美元级合同；A 类产品靠「给团队减负」走 PLG。本项目当前偏 A 类，向上兼容 B/C 是差异化方向。

---

## 二、产品横向对比总表

### 2.1 会议/站会助手（赛道 A）

| 产品 | 定位 | 站会形式 | AI 能力 | 核心集成 | 报告维度 | 定价（参考） |
|---|---|---|---|---|---|---|
| **Spinach AI** | AI Scrum Master，实时参与四大仪式 | 实时（进会）+ 异步 | 转写/摘要/行动项/决策/预测阻塞/写干系人 recap | Zoom、Meet、Teams、Slack、Jira、Linear | 摘要、决策、行动项(owner)、阻塞、win、干系人 recap | 免费 3 人；Pro $5/人/月 |
| **Geekbot** | 异步站会 bot | 异步（Slack/Teams 表单） | 弱（汇总） | Slack、Teams | 昨日/今日/阻塞、mood、自定义问题 | 免费 10 人；$2.5-3/人/月 |
| **Standuply** | 敏捷仪式自动化 | 异步（文字/语音/视频） | 中（汇总） | Slack、Jira、Trello、GitHub | 三问、KPI 追踪、敏捷报告 | 免费；$5/人/月起 |
| **Range** | 异步 check-in + 团队建设 | 异步 + 会议议程 | 弱 | Slack、邮件、OKR | 目标进展、mood、flag/阻塞 | 免费 12 人；$8/人/月 |
| **DailyBot** | 多平台 check-in + 文化 | 异步 | 中（AI 摘要） | Slack、Teams、Discord、Jira | 三问、mood/情绪、kudos | 免费 10 人；$3/人/月 |
| **Status Hero** | 极简异步站会 | 异步（邮件/Slack/Teams） | 弱 | 邮件、Slack、Teams、Jira | 目标/成就/阻塞、mood、dashboard | $3.5/人/月起 |

### 2.2 工程效能 / 经营智能平台（赛道 B / C）

| 产品 | 定位 | 指标框架 | 团队健康/情绪 | 报告维度 | 服务角色 | 定价（参考） |
|---|---|---|---|---|---|---|
| **LinearB** | 效能指标 + 工作流自动化 | DORA + 周期时间 + 冲刺 | 部分（满意度调研） | 交付频率、Lead Time、CFR、MTTR、周期时间、PR 自动化 | EM、Director | 免费；付费 $49/月起 |
| **Swarmia** | 开发者体验优先的效能 | DORA + SPACE + 投资分配 | 内置 DX 调研 | 周期时间、投资去向、working agreement、团队健康 | EM、开发者 | $23-45/dev/月；免费 ≤9 人 |
| **Waydev** | 框架化效能 + 团队健康 | DORA + SPACE | 倦怠/敬业度指标 | 交付指标、burnout、engagement、自定义仪表盘 | EM | $45.75/dev/月 |
| **Jellyfish** | 高管级工程智能 | 投资分配 + DevFinOps | 弱 | 研发投入分配、资本化、产能规划、资源建模 | VP/CTO/CFO | $100K+/年 |
| **Pluralsight Flow** | 高管投资分配 | 投资分配 + 产能 | 弱 | 钱花在哪、产能、业务对齐 | VP/CTO | 按 dev 计费 |
| **Faros AI** | 开源效能数据平台 | 自定义（30+ 连接器） | 自建 | 完全自定义 | Eng Ops / 数据团队 | 开源自托管 |

---

## 三、报告维度对比（核心）

### 3.1 各家输出维度的拆解

**Spinach AI**（维度最全的站会助手）
- 会议摘要（分层：要点 / 章节 / 视频高亮）
- 决策（decisions）
- 行动项（action items，含 owner + 自动建 Jira ticket）
- 阻塞（blockers）
- 胜利/进展（wins）
- 干系人 recap（stakeholder recap，剥离内部细节）
- 冲刺规划：估算建议、潜在阻塞预测
- 回顾：跨期模式识别、改进项

**Geekbot / Standuply / DailyBot / Range / Status Hero**（异步三问 + 扩展）
- 昨日完成 / 今日计划 / 阻塞（三问，可变自定义问题）
- 情绪 / mood（可选匿名）
- 参与度 / 出勤（谁没填）
- 目标进展（Range：OKR 关联）
- kudos / 团队文化（DailyBot）

**LinearB / Swarmia / Waydev**（工程效能）
- DORA 四指标：部署频率、Lead Time for Changes、变更失败率 CFR、平均恢复时间 MTTR
- 周期时间 Cycle Time（各阶段拆解：编码/评审/合并）
- 冲刺追踪：速率、燃尽、范围
- 投资分配（Swarmia/Flow/Jellyfish：功能/维护/技术债/非计划工作占比）
- 团队健康：DX 调研、倦怠、engagement
- PR 自动化：评审周转、卡住 PR

**Jellyfish / Pluralsight Flow**（经营智能）
- 研发投入分配（allocation）
- 研发资本化（capitalization）
- 产能规划（capacity planning）
- 资源建模 / 情景模拟（scenario modeling）
- 董事会级叙事（board-level narrative）

### 3.2 维度矩阵（横向汇总）

| 维度 | Spinach | Geekbot | Standuply | Range | DailyBot | Status Hero | LinearB | Swarmia | Waydev | Jellyfish |
|---|---|---|---|---|---|---|---|---|---|---|
| 昨日/今日/阻塞（三问） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| 决策 | ✅ | — | — | — | — | — | — | — | — | — |
| 行动项（owner/due） | ✅ | — | ⚠️ | — | — | ⚠️ | — | — | — | — |
| 阻塞 + 老化追踪 | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | — | — | — | — |
| 情绪 / mood | — | ✅ | — | ✅ | ✅ | ✅ | — | ⚠️(调研) | ✅(倦怠) | — |
| 会议质量/聚焦度 | — | — | — | — | — | — | — | — | — | — |
| 健康度评分 | — | — | — | — | — | — | ⚠️ | ✅ | ✅ | — |
| 冲刺健康/燃尽/速度 | ⚠️ | — | ⚠️ | — | — | — | ✅ | ✅ | ✅ | — |
| 冲刺预测/风险预警 | ✅ | — | — | — | — | — | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 周期时间/Lead Time | — | — | — | — | — | — | ✅ | ✅ | ✅ | ⚠️ |
| WIP 限制/流动 | — | — | — | — | — | — | ✅ | ✅ | ✅ | — |
| DORA 四指标 | — | — | — | — | — | — | ✅ | ✅ | ✅ | ⚠️ |
| 反复主题（跨期） | ✅(回顾) | — | — | — | — | — | — | ✅ | — | — |
| 教练/改进建议 | ⚠️ | — | — | — | — | — | ⚠️ | ✅ | ⚠️ | — |
| 投资分配/资本化 | — | — | — | — | — | — | — | ✅ | — | ✅ |
| 干系人/高管 recap | ✅ | — | — | — | — | — | — | — | — | ✅ |

> 图例：✅ 原生支持；⚠️ 部分/间接；— 不支持。

### 3.3 对本项目的对齐情况

本项目（Scrum Master Agent）的报告维度覆盖如下，与矩阵对照：

| 本项目维度 | 字段 | 对标产品 | 是否领先 |
|---|---|---|---|
| 执行摘要 | `executive_summary` | Spinach（干系人 recap） | 持平 |
| 敏捷健康雷达（六维加权） | `health_breakdown` + `health_score` | Swarmia / Waydev | 领先（站会级产品无人做） |
| 可行动洞察 | `insights` | Spinach / LinearB | 持平 |
| 冲刺健康 | `sprint_m` | LinearB / Swarmia | 持平 |
| 冲刺预测 | `forecast` | Spinach（阻塞预测） | 持平 |
| 团队情绪 | `sentiment` | DailyBot / Range | 领先（从语气识别，非自报） |
| 会议质量 | `meeting` | 无 | **领先（独家）** |
| 反复出现的主题 | `recurring_themes` | Spinach（回顾）/ Swarmia | 领先（每日级） |
| 教练建议 | `coaching_notes` | Swarmia | 持平 |
| 交付进展 | `delivery` | 三问类 | 持平 |
| 阻塞与依赖（aging） | `blockers_m` | Spinach / Swarmia | 领先（跨日 aging + 跨团队依赖分列） |
| 质量与风险 | `quality` + `risks` | LinearB（DORA 质量） | 持平（DORA 尚缺） |
| 流动效率 | `flow` | LinearB / Swarmia | 持平 |
| 团队信号 | `team` | Swarmia | 领先（沉默/过载） |
| 行动闭环 | `action_items` + `trend` | Spinach | 持平 |
| 趋势对比 | `trend` | LinearB | 持平 |

**差距（市面有、本项目缺）**：
- **DORA 四指标**（部署频率 / Lead Time / CFR / MTTR）——需从 CI/CD + 部署系统接入，当前只有 `quality.deploys`。
- **投资分配**（功能 / 维护 / 技术债 / 非计划工作占比）——需要 Jira 标签 + 分类规则。
- **速率历史 / 冲刺完成率趋势**——当前有 `velocity_points` 单点，缺跨冲刺时间序列。
- **团队 DX 调研**（Swarmia 式主动问卷）——当前只有被动情绪识别。

---

## 四、不同角色的视角对比（核心）

### 4.1 各家为角色提供什么

**Spinach AI**
- 团队：站会摘要 + 各自行动项推送
- SM：决策 + 阻塞 + 行动项 + 跨期回顾模式
- 干系人/管理层：stakeholder recap（剥离内部细节的进展话术）

**Geekbot / DailyBot / Status Hero**
- 团队：三问汇总 + mood
- 管理者：参与度分析、谁没填、mood 趋势
- 无明确的高管层输出

**LinearB / Swarmia**
- 开发者：自己的指标、working agreement、评审周转
- EM：团队 DORA、周期时间、阻塞、健康度
- 无董事会级输出（Swarmia 刻意不做）

**Jellyfish / Pluralsight Flow**
- VP/CTO：投资分配、产能、资本化
- CFO：研发资本化合规报告
- 不看日常站会（刻意不做）

### 4.2 角色 × 维度 矩阵

| 角色 | 三问助手（A 类） | 效能平台（B 类） | 经营智能（C 类） | 本项目（目标覆盖） |
|---|---|---|---|---|
| **开发者** | ✅ 自己的更新/阻塞 | ✅ 自己的指标 | — | ✅ 自己的条目 + 被 owner 的行动项 |
| **Scrum Master** | ✅ 决策/行动项/阻塞 | ⚠️ 团队健康 | — | ✅ 趋势 + 老化阻塞 + 沉默/过载 + 教练建议 |
| **EM / Lead** | ⚠️ 参与度 | ✅ DORA/周期/健康 | — | ✅ health 趋势 + 冲刺进度 + 跨 pod 阻塞 |
| **Product Owner** | ✅ 摘要/决策 | ⚠️ 投资 | — | ✅ delivery + 范围变更 + 阻塞 + Jira 状态 |
| **VP / 总监** | — | ⚠️ | ✅ 投资分配 | ⚠️ 周/月聚合（health/阻塞/缺陷/部署） |
| **跨团队协作者** | — | ⚠️ 依赖 | — | ✅ cross_team / external 依赖 |
| **HR / People Ops** | ⚠️ mood | ✅ 倦怠/engagement | — | ✅ 沉默/过载/出席率（burnout 早信号） |
| **新人 onboarding** | — | — | — | ✅ 历史决策 + Jira/PR + scope 变更史 |
| **客户/干系人** | ✅ recap | — | ⚠️ | ✅ health + 阻塞摘要 + ETA |

### 4.3 关键结论

1. **角色视角的市场缺口**：A 类产品止步于「团队 + 干系人 recap」，B/C 类产品止步于「EM + 高管」，**没有一个产品把「同一份数据」从开发者一路派生到 VP**。本项目的「一份 raw JSON → 多角色视图」架构正好填补这个缺口。
2. **本项目角色设计已对齐最佳实践**（见记忆中的「角色视图设计」）：SM 趋势视图、EM health 聚合、PO 范围变更、跨团队依赖、HR burnout 早信号，均与 Swarmia / Spinach 的做法一致。
3. **可立即借鉴的两点**：
   - Spinach 的 **stakeholder recap**（面向干系人剥内部细节）→ 本项目已有 `executive_summary`，可再增强为「自动生成面向不同读者的多段摘要」。
   - Swarmia 的 **working agreements + DX 调研**（把主观反馈与客观指标关联）→ 本项目可加一个「情绪 vs 指标交叉」面板。

---

## 五、差异点与借鉴清单

| # | 借鉴点 | 来源 | 本项目落地建议 | 优先级 |
|---|---|---|---|---|
| 1 | 干系人 recap 分角色话术 | Spinach | `executive_summary` 扩展为多受众摘要（SM/干系人/高管） | P1 |
| 2 | 阻塞预测（会前预警） | Spinach | `forecast` 前移，站会前生成「今日风险清单」 | P1 |
| 3 | DORA 四指标 | LinearB/Swarmia | 接 CI/CD + 部署系统，补 `deploy_frequency/lead_time/cfr/mttr` | P2 |
| 4 | 投资分配（功能/维护/债） | Jellyfish/Swarmia | Jira label 分类规则 → `investment_balance` | P2 |
| 5 | 速率/完成率时间序列 | LinearB | 聚合多期 raw JSON，输出趋势面板 | P2（已在路线 P5） |
| 6 | 团队健康调研 | Swarmia | 主动问卷 + 与客观指标交叉 | P3 |
| 7 | working agreements | Swarmia | PR 大小/评审周转的自定义团队规范告警 | P3 |
| 8 | 会议计时/发言顺序 | Spinach | 站会主持辅助（可见计时、随机发言） | P4 |

---

## 六、结论

1. **定位清晰化**：本项目应坚持「**站会级诊断 + 多角色派生**」这条差异化路线——向上对标 Spinach（仪式自动化），向右对标 Swarmia（团队健康 + 开发者体验），向上兼容 Jellyfish（高管投资视图），但不做纯财务/资本化（那是 C 类的红海）。

2. **维度补强优先级**：先补 **DORA 质量四指标**（P2，价值最高、市面最通用）和**分角色摘要**（P1），再考虑投资分配与 DX 调研。

3. **护城河**：市面上没有产品同时做到「每日站会自动诊断」+「六维健康雷达」+「情绪/会议质量/反复主题」+「多角色派生」。这正是本项目要守住并放大的位置。

---

## 附：参考资料

- Spinach AI 官网与「AI Scrum Master」专题（2026-08）：<https://www.spinach.ai/content/ai-scrum-master>
- Geekbot 官网：<https://geekbot.com>
- The Complete Guide to Async Standup Tools 2025（Steady 对比）：<http://steady.so/best-async-standup-tools/>
- 12 Standuply Alternatives 2025（Friday/ClickUp）：<https://friday.app/p/standuply-alternatives>
- Best developer experience tools 2026（Sourcegraph）：<https://about.sourcegraph.com/blog/best-developer-experience-tools-for-2026>
- Engineering Analytics Compared 2026（wetheflywheel）：<http://wetheflywheel.com/en/guides/developer-productivity-tools>
- AI Scrum Master 17 Use Cases（AgileFever）：<https://www.agilefever.com/use-cases-genai-agentic-ai-agile-scrum-master-role/>
- What Scrum Master Work Will AI Automate（Scrum Day India）：<https://www.scrumdayindia.org/blogs/will-ai-replace-the-scrum-master/scrum-master-tasks-ai-automates.html>

> 注：定价与功能为 2026-09 调研快照，SaaS 产品更新频繁，正式选型前请以官网最新为准。
