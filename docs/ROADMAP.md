# 路线图（ROADMAP）

- 单人项目，**用"完成定义 DoD"驱动，不设硬性日历 deadline**；每阶段可独立交付、可随时中断续做。状态：✅完成 / 🚧进行中 / ⬜未开始。

| 里程碑 | 状态 | 目标 | 关键交付 | 完成定义 DoD |
| --- | --- | --- | --- | --- |
| **M0 存量底座** | ✅ | 743 视频可离线、有骨架 | 全量清单、720p 原片、FunASR 转写、OKF 骨架、生成器/校验、Git 仓（ADR-012 起公有、只放成品） | 743 下载+转写 100%；`okf_validate` 0E；仓库可 clone 复现 |
| **M1 存量精修** | 🚧 | 把 draft 精修成可靠素材 | 逐篇 VideoNote stable；横向 topics | 01_钻石 58 篇先全绿作为整类样板；再逐类铺开至 743；校验 0E/0W |
| **M2 图文线** | 🚧 | 纳入 UP 图文动态(4366 DRAW) | harvest_articles、Vision OCR、去水印、ArticleNote | 链路已跑通并完成 20 篇试点（见 survey-articles-m2-pilot.md、ADR-011）；待全量 4366 篇落 06_articles，再编译知识层 ArticleNote 并校验 |
| **M3 增量跟踪** | ⬜ | 新内容可发现、可自动入库 | sources.json 水位、track_updates（report/--auto） | 拉第1页即可列出新增、与空间页人工核对漏检为0；--auto 跑通"新视频→draft→队列"且成功后才移水位 |
| **M4 书籍权威层** | ⬜ | 用权威书补体系、校口播 | 书单、合法获取、BookNote、bookmap | 书单登记完整；每本来源合法可溯；核心主题有书与视频交叉注记 |
| **M5 融合与创作** | ⬜ | topics 融合 + 服务做号 | 10+ topics 成稿、文案模板、选题参考 | 任一选题 10 分钟内产出带出处文案底稿；主题页含视频/图文/书/外部报告等多来源 |

## 外部来源线（平台无关，ADR-012，按需穿插、不设固定里程碑）
- 老许之外的来源（其他 UP、公众号/视频号/抖音、播客、电子书、第三方报告 PDF、付费社区等）统一进 `library/08_sources/<source_id>/`：原始件落 `raw/`、转写/采集数据落 `cleaned/`（均不进公有 Git），来源档案 `SOURCE.md` + 计数 `manifest.json` 入库。
- 清洗后按载体落知识层：外部视频→VideoNote、图文→ArticleNote、电子书→BookNote、报告/综合研究→**ReportNote**（`concepts/reports/`）；融合仍只在 topics 多来源分栏。**不为沉淀而沉淀**：清洗后确有增量价值才建条目。首个外部来源 `community-scys`（生财有术珠宝创业情报，2026-09）已产出一篇 ReportNote。

## 阶段依赖
- M1 与 M2 可并行（不同来源、同一知识结构）。
- M3 依赖 M0 的清单/下载链路与 M2 的图文采集（共用源清单）。
- M4 依赖 M1 攒出"推荐书单"；M5 依赖前四者有足够存量。

## 迭代节奏建议（solo）
- 每个工作单元控制在 1–4 小时（对应 BACKLOG 一张卡），结束即一次 Git 提交（Conventional Commits）。
- 每完成一个里程碑：跑全量校验、更新本文件状态、打一个 tag（如 `m0-baseline`）。
- 大改生成器/结构属高扩散变更，先在 DECISIONS 记录方案再动。
