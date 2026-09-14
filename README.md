# 宝石学家老许 · 珠宝知识库（gemology-kb）

把 B 站 UP「宝石学家老许」（UID/mid=1841256325，约 24.7 万粉，珠宝科普）的**视频 + 图文 + 推荐书**采集、转写/OCR 后建成本地结构化知识库，作为用户自营 B 站号/视频号的选题与文案弹药库。全程防风控第一。

- **项目位置（实体目录）**：`~/Desktop/gemology-kb`（本地目录名沿用）；**公有 Git 仓**：https://github.com/byte886/jewelry-knowledge ，只版本化"清洗后的知识成品/代码/文档"，原始件与逐字转写只留本地、不入库（ADR-012）。
- AI 接手先读 [AGENTS.md](AGENTS.md)；工程文档地图见 [docs/README.md](docs/README.md)；网盘见 [docs/NETDISK_SYNC.md](docs/NETDISK_SYNC.md)。

## 当前进度
- **视频线已完成**：投稿 **743** 个（官方 count 为准，总时长 41.2h，跨度 2021-04~2026-09）全部下载（`01_video`，约 13G）并 FunASR 转写（`04_transcript` 743 篇）。
- **图文存量盘点完成（M2-0）**：动态流翻到账号起点，动态共 11539 条，其中图文 4367（DRAW 4366 + 专栏 1），清单 `00_manifest/articles_dynamic_scan.json`；正文采集/OCR 为 M2，未动工。
- **知识层**：`05_knowledge`（OKF v0.2）已建 743 篇视频条目 + topics 占位，共 779 个 md；精修 stable 20/743，其余在 `refine_queue.json` 队列。
- **外部来源（平台无关，ADR-012）**：`08_sources/<source_id>/` 承接老许之外的任意来源（其他 UP、公众号/视频号/抖音、电子书、第三方报告、付费社区）；首个为 `community-scys`（生财有术珠宝创业情报），清洗为 `concepts/reports/` 下一篇 ReportNote。

## 四地存储分工（硬约束）
| 位置 | 内容 |
|---|---|
| Git **公有**仓 | 清洗后"自己话"的知识成品（05 的 stable/topics/reports）、代码、`docs/`、台账元数据；**不放媒体、逐字转写/原文抽取/外部采集原文、逐字 draft、任何凭证（含加密 .enc）、过程件**（ADR-012） |
| 本地桌面项目 | 原始资源 + 知识成品，**唯一权威源** |
| 百度网盘 `珠宝知识库/` | 仅成品镜像（编号-中文目录，映射与命令见 [docs/NETDISK_SYNC.md](docs/NETDISK_SYNC.md)） |
| 飞书 | 暂缓；将来只发成品，且不进「AI 情报站」 |

## 关键实测事实（长期有效）
- **列清单最难、下载不难**：游客对"空间列表"接口风控极强；最终用「独立小号 Chrome 登录 + 本地算 wbi + 登录页内 fetch `x/space/wbi/arc/search`」一次列全，主号零风险。详见技能 `multiplatform-media-fetch/references/bilibili-up-listing.md`。
- 单条 BV 解析/下载游客即可，720p 无需 cookie；全库**字幕覆盖率 0%**，故全部走 FunASR（SenseVoiceSmall+fsmn-vad）。
- 竖屏按"较短边 res"选流（按帧高会误选 360p）；B 站强制直连，走代理必 412。

## 主要决策（ADR 见 docs/DECISIONS.md）
- 统一 **720p 原片留存、不压缩**（源已是 HEVC/AV1 约 600kbps，重压仅省 26-35% 却损画质、耗时，磁盘充足；2026-09-11 确认）。
- OKF v0.2、本地为源（ADR-001）；仓库**公有但只放清洗后成品、原料与逐字稿不入库**（ADR-012，变更 ADR-003/005 的私有设定）；不引入向量库（ADR-008）；终局是做号弹药库、不做量化（ADR-006）。

## 目录结构
```
gemology-kb/
├── AGENTS.md / README.md        # AI 手册 / 人读概览
├── docs/                        # PRD/ARCHITECTURE/ROADMAP/BACKLOG/DECISIONS/NETDISK_SYNC
├── library/
│   ├── 00_manifest/             # manifest.json/.csv、refine_queue.json、articles_dynamic_scan.json（台账）
│   ├── 01_video/<分类>/<标题 [BV]>.mp4     # 原片(不入git)
│   ├── 02_audio/                # 转写抽取音频(过程件)
│   ├── 04_transcript/<分类>/<标题 [BV]>/{transcript.md, transcript.json}  # 逐字转写=原料(不进公有Git)
│   ├── 05_knowledge/            # OKF 知识成品(concepts/videos 仅stable、topics、reports、index/log)
│   ├── 06_articles/ 07_books/   # M2 图文(原料不进公有Git) / M4 书（待建）
│   ├── 08_sources/<source_id>/  # 平台无关外部源:raw,cleaned(不入库)+SOURCE.md,manifest.json(入库)
├── scripts/netdisk/             # baidu_upload.py(通用) + sync_netdisk.py(成品同步)
├── *.py / run_pipeline.sh       # 采集/转写/建库正式脚本（留根，用相对 library/ 路径，勿移动）
├── .secrets/ secrets/           # 凭证/cookie（含加密 .enc，一律只留本地、不入公有仓）
├── workspace/                   # 过程件唯一收口(日志/断点/上传台账，不入库不传网盘)
└── _archive/                    # 被取代脚本本地留底(不入库)
```

## 脚本与运行
- 解释器：下载用含 yt-dlp 的 venv（`/Users/wenjiechen/Doubao/chats/2026-09-05/new-chat-2/.venv/bin/python`）；转写 FunASR venv 由脚本自动发现；编排/网盘统一 `/usr/bin/python3`（纯标准库）。
- `run_pipeline.sh`：下载+转写，nohup 脱离会话、断点续跑；`batch_build.py`（规划+慢速下载，`--plan-only/--limit`）、`batch_transcribe.py`（批量转写）、`build_knowledge.py`/`refine_queue.py`（建库/精修队列）。
- 网盘同步：`export BAIDU_ENC_PASS=...` 后 `python3 scripts/netdisk/sync_netdisk.py --dry-run`，详见 [docs/NETDISK_SYNC.md](docs/NETDISK_SYNC.md)。
- OKF 校验：`python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge --json`（E 必须为 0）。

## 下一步
按 [docs/BACKLOG.md](docs/BACKLOG.md)：M1 存量精修（主线）→ M2 图文采集+OCR → M3 增量跟踪水位 → M4 书籍层 → M5 融合与创作。
