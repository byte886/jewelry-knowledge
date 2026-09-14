# PRD · 珠宝学个人知识库与内容弹药库

- 文档状态：Draft v0.1（2026-09-12）　Owner：本人（solo）　协作方：AI 助手
- 配套文档：[ARCHITECTURE.md](./ARCHITECTURE.md)（怎么建）、[ROADMAP.md](./ROADMAP.md)（分几步）、[BACKLOG.md](./BACKLOG.md)（任务台账）、[DECISIONS.md](./DECISIONS.md)（决策记录）
- 方法说明：本 PRD 采用单人/独立开发者通用的 **Lean One-Pager** 结构（问题优先、显式"不做清单"、MVP 边界、成功指标），参考 Lenny Rachitsky 1-Pager 与多篇 solo/indie PRD 实践。

---

## 1. 背景与问题（Problem）

我在做一个国内珠宝方向的自媒体（B 站号 / 视频号），需要成体系、可溯源、能跨会话复用的专业素材。当前已把 B 站 UP「宝石学家老许」（mid=1841256325）的 **743 条投稿全部下载并语音转写**（约 107 万字、41.2 小时），并按 OKF v0.2 搭起本地知识包骨架。

现状痛点：
1. 素材只有视频一种形态，**UP 的图文专栏、推荐的书还没纳入**，知识不完整。
2. UP 持续更新，靠人工发现新内容、重复走下载转写流程，成本高且易漏。
3. 转写是 ASR 初稿、量很大，需要逐篇精修才能成为可靠素材。
4. 跨会话/跨工具会"失忆"，需要一个 AI 也能按图索骥的稳定结构（已用 OKF + Git 解决一半）。
5. 写自己的脚本时，缺一个"事实准确、术语规范、随取随用"的弹药库。

## 2. 目标用户（Users，只有一个主用户）

- **主用户：我自己**——珠宝内容创作者/运营。场景：选题、写脚本、核对专业事实、跟踪对标账号。
- **次要"用户"：AI 协作者**——在任意新会话里，靠仓库 + OKF 知识包快速恢复上下文、按既定规范继续加工，不需要我重复交代。

## 3. 目标与成功标准（Goals / Success Metrics）

| 目标 | 可验证的成功标准 |
| --- | --- |
| G1 存量成库 | 743 篇全部从 draft 精修为 stable；`okf_validate` 保持 0 错误 |
| G2 增量不遗漏 | 跑一次跟踪脚本能列出"自上次以来的新视频/新图文"清单；漏检率 0（以 UP 空间页为准人工抽查） |
| G3 多形态融合 | 图文、书籍以独立 type 入库，并在 topics 主题页与视频互相关联；任一主题能一次取到视频/图文/书三类来源 |
| G4 直接服务创作 | 给定一个选题，能在 10 分钟内基于知识库产出"带事实出处"的文案底稿（钩子→知识点→案例→结论） |
| G5 可复现可交接 | 仅凭仓库 + docs，新会话/新机器能复现整条流水线；关键步骤有脚本、有台账、有决策记录 |

## 4. 范围（Scope）

### 4.1 In（要做）
- 存量 743 视频的逐篇语义精修（进行中）与横向 topics 提炼。
- 采集 UP 的**图文专栏**：正文 + 内嵌图 OCR，形成 ArticleNote。
- **增量跟踪**：基于水位（watermark）发现新视频/新图文，先出"可采清单"，支持一键自动采集转写入库。
- **书籍层**：汇总视频推荐书单，经合法渠道获取，做书摘/知识地图 BookNote，作为权威骨架交叉校验视频口播。
- 面向自己做号的**文案产出能力**（选题参考 + 文案模板 + 事实出处）。
- 全程版本管理（Git 私有仓）与防风控、合规留痕。

### 4.2 Out（明确不做 / "Not Doing List"）
- **不做任何"量化交易/行情量化系统"**（此前提法已撤销，与本项目无关）。
- 不做多用户、SaaS、Web 服务、对外发布平台；这是单人本地库。
- **不自动采集微信视频号**：平台封闭、无公开接口、风控极强；如确需，只能手动导出视频后走本地转写。
- 不引入向量数据库：约千篇规模用 OKF 的 index 渐进式披露 + 关键词即可，避免过度工程。
- 不做视频的全量逐帧 OCR（成本极高）；只对"信息只在画面里"的关键帧按需 OCR。
- 不获取/不分发盗版书籍全文，不把他人转写/书籍内容公开（故仓库私有，见 ADR-003）。

## 5. 需求与优先级（MoSCoW）

- **Must（M1–M3）**：存量精修流水线；图文采集 + OCR；增量水位跟踪；OKF 三类型融合结构。
- **Should（M4）**：书籍权威层；topics 横向提炼。
- **Could（M5）**：文案模板与选题参考、半自动成稿。
- **Won't（本期）**：见 4.2。

## 6. 形态与信息架构（高层，细节见 ARCHITECTURE）

原始层按形态**分工留档、不可变**；知识层用 `VideoNote / ArticleNote / BookNote` 三类条目承载，在 `topics/` 主题页**融合互证**；上层是创作应用。目录、schema、数据流见 ARCHITECTURE.md。

## 7. 风险与合规（Risks）

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| B 站风控/封号 | 高 | 直连、慢速、只读公开数据、独立游客/小号 profile、撞限流即冷却；增量发现只看第 1 页，详见 ADR-009 |
| 版权（视频转写/图文/书） | 中高 | 个人学习研究合理使用、本地留存、**仓库私有**、书摘用自己的话并标出处、不全文复制不分发（《著作权法》第 24 条） |
| ASR/OCR 错误导致专业事实出错 | 中 | 精修必做同音纠错、听不到标"待核"、用权威书/国标交叉校验、不写 verified 冒充人工 |
| 单人精力有限、长工程烂尾 | 中 | Lean 文档 + BACKLOG 拆到 1–4h 小任务 + 每阶段 DoD + Git 随时可续 |
| 跨会话失忆 | 中 | OKF bundle + 本 docs + Git 提交历史，新会话按 README 恢复 |

## 8. 开放问题（Open Questions，需后续定）
1. 书籍获取：先由 AI 通过公开/合法渠道调研可获得性，找不到的书登记"待获取清单"再反馈（用户已指示）。
2. 未来若要把知识库同步飞书：珠宝内容不进"AI 情报站"，单独建珠宝知识空间（届时另议）。
3. 仓库当前私有；若日后想公开"工具脚本"，评估把纯脚本拆成独立公开仓、数据继续私有。

## 9. 参考来源（方法论与事实核验）
- Lean/1-Pager PRD：Lenny Rachitsky 1-Pager 等，汇总见 https://www.prodmgmt.world/blog/prd-template-guide ；solo MVP 五要素 https://devtools.shingoirie.com/blog/en/indie-dev-mvp-requirements-minimum/ ；solo spec-driven https://tekk.coach/spec-driven-development/sdd-for-solo-developers/
- 增量水位/检查点：watermark 模式 https://theneuralbase.com/data-pipeline-for-ml/learn/intermediate/watermarks-for-progress/ ；checkpoint 语义 https://unstructured.io/insights/incremental-data-ingestion-strategies-for-continuous-pipelines
- B 站专栏接口：https://github.com/xiaotwins/bilibili-API-collect/blob/master/article/list.md
- 著作权合理使用：《中华人民共和国著作权法》第 24 条 http://www.npc.gov.cn/c2/c30834/202011/t20201119_308796.html
