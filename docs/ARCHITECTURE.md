# 技术架构（ARCHITECTURE）

- 状态：Draft v0.1（2026-09-12）　上游标准：OKF v0.2（技能 `~/Doubao/skills/okf-wiki`，内核不改）
- 一句话：**原始层按形态分工留档（不可变）→ OKF 知识层按 type 分条目、在 topics 融合 → 上层服务自己做号。**

---

## 1. 分层架构

```
① 来源层（平台无关·开放扩展，ADR-012）
   老许源：B站视频(743✓)  B站图文(4366,M2)  推荐书(M4)
   外部源 library/08_sources/<source_id>/：其他UP/公众号/视频号/抖音/播客/电子书/第三方报告PDF/付费社区…
              │
② 加工层   下载→FunASR转写｜抓正文→图OCR｜正版→书摘｜PDF·网页→抽取综合（统一：防风控+水位增量；原料 raw/cleaned 不进公有 Git）
              │
③ 原始层（只读·本地留档·不进公有 Git）
   老许：01_video 04_transcript 06_articles 07_books；外部：08_sources/*/{raw,cleaned}
              │
④ 知识层（清洗后"用自己话重组、带来源"的成品，才入库）
   concepts/videos(VideoNote) articles(ArticleNote) books(BookNote) reports(ReportNote)
              └──────────────► topics/ 主题页：同一知识点多来源分栏互证、去重、标矛盾
                                index.md(导航) log.md(倒序)
              │
⑤ 应用层   选题参考 · 文案底稿（钩子→知识点→案例→结论，全部带出处）
```

> **三层不混淆（ADR-012）**：①原始下载件（视频/PDF/原网页）与②逐字转写/原文抽取（transcript、article/ocr、采集 CSV）都是**原料**，只留本地、不进公有仓；③只有"用自己话重组、带来源"的知识成品入库。type 表**载体形态**、与作者/平台解耦，外部来源复用同一套 Video/Article/Book/Report Note。

## 2. 目录结构（在现有基础上只增不改）

```
bili-up/
├─ docs/                     # 【新】商业开发文档（PRD/架构/路线/台账/决策）
├─ library/
│  ├─ 00_manifest/           # 台账：manifest.json/csv（743，权威）、refine_queue.json
│  │  └─ sources.json        # 【新】源清单 + 增量水位（见 §5）
│  ├─ 01_video/              # 720p 原片 13G（.gitignore，不入库）
│  ├─ 02_audio/
│  ├─ 04_transcript/         # 视频转写（不可变，已入库）
│  ├─ 06_articles/           # 【新】图文：<id>/article.md + images/ + ocr/（原料，不进公有Git）
│  ├─ 07_books/              # 【新】书籍：<isbn或书名>/bookmap.md、notes/、合法源说明
│  ├─ 08_sources/            # 【新·ADR-012】平台无关外部来源：<source_id>/{raw,cleaned(均不入库),SOURCE.md,manifest.json(入库)}
│  └─ 05_knowledge/          # OKF 知识包（融合层，成品；公有仓只放成品）
│     ├─ index.md log.md README.md
│     └─ concepts/
│        ├─ videos/<22分类>/<bvid>.md   # VideoNote（现有743，仅 stable 入公有仓）
│        ├─ articles/<分类>/<aid>.md    # 【新】ArticleNote
│        ├─ books/<书名>.md             # 【新】BookNote
│        ├─ reports/<slug>.md           # 【新】ReportNote：第三方报告/综合研究清洗结果
│        └─ topics/                    # 横向主题页（融合核心，现有10占位，多来源分栏）
└─ *.py *.sh                 # 流水线脚本（见 §6）
```

约定：新增层不改变现有 743 篇路径与 bvid.md 命名；OKF 链接目标仍不得含空格/半角括号，故**条目文件名一律用稳定 ID**（视频 bvid、图文 aid、书籍 ISBN/拼音 slug），人类可读标题放链接文本与正文。

## 3. 三类知识条目 schema（OKF 标准档，type 区分）

均沿用现有 VideoNote frontmatter（唯一必填 `type`），只扩展 type 与少量来源字段：

```yaml
# ArticleNote（图文）
type: ArticleNote
title: / description: / tags: []
sources:
  - {id: src-bili, resource: "https://www.bilibili.com/read/opus或文章URL", author: "human:宝石学家老许", last_modified: ...}
  - {id: src-ocr,   resource: "../../../../06_articles/<id>/ocr/fig1.txt", title: "内嵌图OCR文本"}
generated: {by, at}
status: draft|stable
review: "ai-refined / pending-human-check"
aid: <专栏文章ID>
category: / published: / words:
```

```yaml
# BookNote（书摘/章节知识）
type: BookNote
title: / description: / tags: []
sources:
  - {id: book, resource: "ISBN 978-... ", title: "系统宝石学（第2版）", author: "张蓓莉主编", publisher: "地质出版社", year: 2006, acquired_via: "正版纸书/电子书/图书馆/公开样章"}
generated / status / review 同上
isbn: / authors: [] / chapters: []
```

```yaml
# ReportNote（第三方报告 PDF / 多源综合研究的清洗结果；ADR-012）
type: ReportNote
title: / description: / tags: []
sources:
  - {id: src-source, resource: "../../../08_sources/<source_id>/SOURCE.md", title: "来源档案", author: "report:机构 或 community:社区多篇汇编"}
generated: {by, at}
status: draft|stable
review: "ai-refined / pending-human-check"   # 机器初编不写 verified: human
source_kind: / sample: {}                    # 来源性质与样本漏斗（计数，易变值不抄进正文）
```
- ReportNote 是"原料（PDF/采集数据，留 raw/cleaned 不入库）→ 自己话综合"后的成品；原文不整段搬运，结论可溯（来源档案 + 原文链接/本地路径）。

- VideoNote 维持现状不变。四类条目都在正文末尾链回 topics 与相关条目；**融合只发生在 topics**：主题页按来源分栏（"视频怎么讲 / 图文怎么整理 / 书里权威定义 / 报告·社区怎么说"），矛盾处显式标注，不强行统一。
- 信任纪律延续：不写 `verified` 冒充人工；易变值（播放数、进度、日期）只进 frontmatter/台账，不抄进正文。

## 4. 图文采集与 OCR

> 2026-09-12 M2-0 实测（详见 [survey-articles-m2-0.md](./survey-articles-m2-0.md)）：本 UP 图文是**两条通道**，主通道是动态图文，不是专栏。

- **通道 A 专栏长文 cv（本 UP 仅 1 篇，游客 code=0 可读）**：列表 `GET x/space/article?mid=1841256325&pn=1&ps=30&sort=publish_time`；正文 `GET x/article/view?id=<aid>`。
- **通道 B 图文动态 opus/DRAW（主通道）**：在 `x/polymer/web-dynamic/v1/feed/space` 动态流里筛 `type=DYNAMIC_TYPE_DRAW`（最新样本约占两成）；游客只能读前 1–2 页，全量需独立小号登录态慢翻；正文/图走 opus 详情，链接形如 `bilibili.com/opus/<id_str>`。**不要只筛 AV，否则会漏掉全部图文。**
- 落地：正文转 Markdown 存 `06_articles/<id>/article.md`；内嵌图下载到 `images/`，逐张 OCR 存 `ocr/`，正文以图注形式回插 `[图N：OCR摘要]`。
- **OCR 选型**：中文珠宝图文优先本地 **PaddleOCR（中文模型、可离线）**；表格类图额外做结构化。OCR 文本一律标注"画面识别，可能有误"。先用 3–5 张样图验证识别率再批量。
- 视频画面**不**全量 OCR，仅当关键信息只在画面（板书/价格表/证书特写）时按需抽帧。

## 5. 增量跟踪：水位（watermark）机制

通用做法：持久化"上次成功处理到的位置"，下次只取其后的新内容；**先成功落地、再推进水位**（at-least-once，崩溃不丢，重复可去重）。

`00_manifest/sources.json`：
```json
{
  "bilibili:1841256325": {
    "kind": "bili-up", "videos": {"last_max_created": 1789000000, "known_count": 743, "last_check_at": "..."},
    "articles": {"last_max_pub_time": 0, "known_aids": [], "last_check_at": "..."}
  }
}
```
- **发现增量成本很低**：只需拉 UP 投稿/专栏**第 1 页（最新一屏）**与 `last_max_created` 比较（用 unix 整数比较，规避时区问题），列出"新增候选"，**不需要翻全量**（全量历史才需要慢速翻页，已完成）。
- 两档执行：
  1. `report`（默认、安全）：只产出 `new_content_report.md`——有哪些新视频/图文、标题、时长、建议分类，**先让人知道有什么可采**；
  2. `--auto`：对新增项自动走下载→转写/图文抓取→生成 draft→进 refine_queue，全部完成后才把水位前移。
- 节奏：**手动/低频（建议每周一次）优先**，不做高频定时（防风控，见 ADR-009）。迟到内容（UP 补传/改时间）用"回看最近 2 页 + known ID 去重"兜底。

## 6. 脚本规划（纯标准库优先，解释器约定见根 README）

| 脚本 | 状态 | 职责 |
| --- | --- | --- |
| batch_build / batch_transcribe / run_pipeline | 已有 | 全量下载、转写（断点续跑） |
| build_knowledge.py | 已有 | 幂等生成 OKF 包（保护 stable、清孤儿、写 log） |
| refine_queue.py | 已有 | 精修分档队列 full/lite/story/done |
| collect_articles.py | 待建 | 拉专栏列表+正文+内嵌图，落 06_articles |
| ocr_images.py | 待建 | 对 06_articles/images 批量 OCR（PaddleOCR） |
| track_updates.py | 待建 | 读 sources.json 水位→拉第1页→出 report 或 --auto 采集→推进水位 |
| ingest_book.py | 待建（轻） | 把合法获取的书整理为 BookNote 骨架 + bookmap |
| build_knowledge.py 扩展 | 待改 | 识别 articles/books，统一生成 index/log、保护各类型 stable |

## 7. 书籍层与合规

- 先在视频精修时登记"推荐书单"（哪期推荐、书名作者、推荐理由）。
- 已核实的权威候选（用作权威骨架，非全量采购，按需）：
  - 《系统宝石学（第2版）》张蓓莉主编，地质出版社 2006，ISBN 9787116048225，国家珠宝玉石质量检验师指定教材；
  - GIA 推荐书单（含 B.W.Anderson《Gem Testing》等）https://www.gia.edu/library-recommended-books-gemology ；
  - NGTC 专著系列（《钻石辨假》《珠宝首饰评估》等）https://www.ngtc.com.cn/kjyf/zhuanzhu/index.html ；
  - 国标 GB/T 16552《珠宝玉石 名称》、GB/T 16553《珠宝玉石 鉴定》。
- 获取优先级：正版纸书/电子书 > 图书馆借阅 > 出版社/电商合法试读样章 > 公开权威资料；**不找盗版全书**。AI 先调研可获得性，找不到的进"待获取清单"反馈。
- 合规依据《著作权法》第 24 条：为个人学习研究可使用已发表作品、为说明问题可适当引用，但须注明作者与作品名、不影响其正常使用、不损害权益。落地上：BookNote 以**自己的话总结**为主、少量必要引用并标页码、本地私有库、不分发不公开。

## 8. 防风控与安全（沿用已验证经验）

- B 站强制直连（清代理），单线程、限速、随机间隔，撞 412/-352 立即停、冷却 10–30 分钟，不反复重试；详见技能 `multiplatform-media-fetch/references/bilibili-up-listing.md`。
- 浏览器用独立 `--user-data-dir`（.chrome-prof3 登小号，已 gitignore），不碰主号、不动用户日常 Chrome。
- 凭证/cookie（secrets/、*.netscape.txt）一律不入库、不在日志与产出中回显。

## 9. 复现 / 新会话恢复（交接）

1. clone 私有仓（不含 01_video，需要原片另行本地保留）；
2. 读 `docs/README.md` → PRD → 本架构 → BACKLOG 当前 in-progress；
3. 读 `library/05_knowledge/index.md` 与 `refine_queue.json` 掌握进度；
4. 解释器路径、运行命令见根 README；校验：`python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge --json`。
