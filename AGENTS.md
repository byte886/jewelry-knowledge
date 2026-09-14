# AGENTS.md — AI 操作手册（gemology-kb）

> 读者：每次接手本项目的 AI 代理。命令式、可执行。与 [README.md](README.md)（给人看的概览）互补；已在专文讲清的只链接、不复制。
> 项目根：`~/Desktop/gemology-kb`（实体目录；Git 仓**公有**，仅放清洗后成品，原料/逐字稿只留本地，见 ADR-012 与 §3）。

## 1. 这个项目是什么
把 B 站 UP「宝石学家老许」（mid=1841256325，珠宝科普）的**视频 + 图文 + 推荐书**，以及 `08_sources/` 下**平台无关的外部来源**（其他 UP、公众号/视频号/抖音、电子书、第三方报告、付费社区等，ADR-012）做成结构化本地珠宝知识库，最终作为用户自营 B 站号/视频号的选题与文案弹药库。**不做量化**（ADR-006）。当前：视频线（743 下载+转写）已完成，主线是 M1 存量精修，其次 M2 图文线。阶段与口径见 [docs/ROADMAP.md](docs/ROADMAP.md)、[docs/BACKLOG.md](docs/BACKLOG.md)。

## 2. 开工前必读顺序（不靠对话记忆猜）
1. 本文件（规则）→ 2. [README.md](README.md)（现状/规模/怎么跑）→ 3. [docs/README.md](docs/README.md)（文档地图）→ 4. ARCHITECTURE（结构/schema）、BACKLOG（到哪了、下一步）→ 5. 易变进度现读台账：`library/00_manifest/manifest.json`、`refine_queue.json`，**不把计数/日期抄进正文**。

## 3. 存储分工（硬约束，四地分离）
| 位置 | 放什么 | 不放什么 |
|---|---|---|
| **Git 仓（公有，ADR-012）** | 清洗后"自己话"的知识成品（`05_knowledge` 的 stable/topics/reports）、代码、`docs/`、台账元数据 | 媒体；**逐字转写/原文抽取/外部采集原文**（`04_transcript`、`06_articles`、`08_sources/*/{raw,cleaned}`、`05` 里的逐字 draft）；**任何凭证（含加密 `.enc`）**、`workspace/`、`_archive/` |
| **本地 `~/Desktop/gemology-kb`** | 原始资源 + 知识成品，**唯一权威源** | —— |
| **百度网盘** | 仅**成品**镜像（见 §6 与 [docs/NETDISK_SYNC.md](docs/NETDISK_SYNC.md)） | 过程件、`transcript.json`、`02_audio/`、日志 |
| **飞书** | 暂缓；将来只发成品知识，且**不进「AI 情报站」** | 原始素材、过程留痕 |

## 4. 目录约定（只记非显然部分）
- `library/00_manifest/` 台账元数据；`01_video/` 原片、`02_audio/` 转写中间件、`04_transcript/` 逐字稿、`06_articles/`(M2 图文原文/OCR) 都是**原料，只留本地、不进公有 Git**；`05_knowledge/` 是知识成品（`concepts/videos` 仅 stable 入库、逐字 draft 留本地；`topics/`、`reports/` 成品入库）；`07_books/`(M4)。
- `library/08_sources/<source_id>/`（ADR-012，**平台无关外部来源**）：`raw/`（原始 PDF/网页/视频）、`cleaned/`（转写/采集数据）不入库；`SOURCE.md`（来源档案）、`manifest.json`（计数与映射）入库。`source_id=<平台>-<主体>`，平台开放枚举，新增平台只加目录、不改架构。
- `scripts/netdisk/` 网盘上传；其余采集/转写/建库脚本在**仓库根**（用相对 `library/` 路径运行，**不要移进子目录**，会断路径）。
- `workspace/`：所有过程件（日志、断点、临时快照、netdisk 上传台账）唯一收口，**不入库、不传网盘**；`_archive/`：被取代脚本的本地留底（不入库）。根目录不得散落临时文件。
- `.secrets/`、`secrets/`：凭证（cookie/token，**含加密 `*.enc`**）一律只留本地、不入公有仓（弱口令加密件放公开仓仍有离线爆破风险）。

## 5. 核心规则
1. **防风控第一（B 站）**：强制直连（走代理必 412）；只操作独立小号实例 `.chrome-prof3`（端口 9223），**绝不碰用户日常 Chrome（9222/主号）**；慢速、单线程、限速；撞 412/-352/-509/空态**立即停手冷却，不换参数反复重试**。方法先读技能 `~/Doubao/skills/multiplatform-media-fetch/references/bilibili-up-listing.md`。
2. **本地是唯一源**：知识成品先在 `05_knowledge/` 成稿并过校验，再谈同步网盘/飞书；禁止反向直接改外部副本。
3. **OKF v0.2 格式**：`05_knowledge/` 条目带 frontmatter（唯一必填 `type`），提交前必过机械校验且 E=0：
   `python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge --json`。机器初编**不得**写 `verified: human`；横向链接只能指向已存在的 topics 占位，否则报死链。type 按**载体**分 VideoNote/ArticleNote/BookNote/**ReportNote**，与作者/平台解耦（外部来源同此套，ADR-012）；**只有"自己话成品"才进公有仓**——逐字 draft/原文不入库，`concepts/videos` 靠 `.gitignore` 成品门禁（默认忽略 draft、逐行放行 stable 与各 index.md，stable 增删要同步该段）。
4. **网盘只传成品、幂等可续**：用 `scripts/netdisk/sync_netdisk.py`；远程名自动去除 emoji（百度 create 拒绝 emoji，errno -7；**本地文件名一律不动**）；断点 `workspace/netdisk/uploaded.tsv`，重跑自动跳过、失败落 failed.tsv 不中断。
5. **命名语言分层**：本地目录/代码/脚本/桌面入口用英文；百度网盘展示层对齐高顿/股票，用「顶层中文 + 编号-中文」（珠宝知识库/01-视频原片…）。
6. **凭证安全**：明文 token/cookie/密钥绝不入库、不回显、不写进任何文档；百度加密件用环境变量 `BAIDU_ENC_PASS` 提供口令（口令向用户要，不落盘）。
7. **变更分级**：L0（错字/单处小修）直接改；L1（批量移动/重命名、改命名或治理规范、新增持久机制、≥5 处级联）先出「方案+影响清单」经用户确认再动；拿不准就高不就低。新增/移动文件后检查 `.gitignore`。
8. **问题驱动**：发现脚本 bug/流程缺陷/文档缺口，当场评估并修复或归档，不留僵尸脚本与重复实现（0 引用一次性脚本移 `_archive/` 带说明，不硬删）。

## 6. 常用命令（均在项目根运行）
```bash
# 进度（现读台账，不凭记忆）
/usr/bin/python3 - <<'PY'
import json,collections
m=json.load(open("library/00_manifest/manifest.json"))
rows=m["videos"] if isinstance(m,dict) and "videos" in m else m
print(collections.Counter(v.get("status") for v in rows))
PY

# 采集/下载/转写（解释器见 README「脚本与运行」，下载用专用 venv，转写 FunASR 自动发现）
./run_pipeline.sh                      # 下载+转写，断点续跑
/usr/bin/python3 refine_queue.py       # 精修队列
/usr/bin/python3 build_knowledge.py    # 建/刷新知识条目

# OKF 校验（提交前必过，E=0）
python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge --json

# 百度网盘成品同步（细节见 docs/NETDISK_SYNC.md）
export BAIDU_ENC_PASS='<向用户索取>'
/usr/bin/python3 scripts/netdisk/sync_netdisk.py --dry-run                      # 先看计划
/usr/bin/python3 scripts/netdisk/sync_netdisk.py --only knowledge,transcript    # 只同步文本层
/usr/bin/python3 scripts/netdisk/sync_netdisk.py                                # 全量(含13G视频,建议后台)
```

## 7. 异常处理
- 先 `grep` 文档/脚本找既有解法，再尝试自动修复；**先怀疑 AI 自身**（端点、参数、ID、文件选取、最近改动，约九成在此），token/凭证失效最后怀疑且须有只读请求硬证据，不轻易让用户重新登录。
- B 站限流：见 §5.1，冷却后换全新节奏一次慢跑完，不做零散试探。
- 网盘错误码：31061 目录已存在(忽略)、31064 越出应用沙箱、111 token 过期(用 refresh_token 刷新)、-7 远程名非法(同步器已自动去 emoji)、同名覆盖需 rtype=3（上传器已带）。

## 8. 完成定义（DoD）
成品可读且数量与台账一致 → OKF 校验 E=0 → 过程件已收口 `workspace/`、根目录无散落 → `.gitignore` 与文档同步、确认本次 add 不含原料/逐字稿 → 按里程碑 commit（信息写清，公有仓可直接 push；推送前再核对无他人原文）→ 需备份的成品走网盘同步并核对。
