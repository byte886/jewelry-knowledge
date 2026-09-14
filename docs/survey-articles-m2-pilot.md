# M2 图文采集 · 20 篇试点实测报告

- 日期：2026-09-13　方式：登录小号 Chrome（.chrome-prof3/9223）只读、单线程慢速、强制直连
- 对应决策：[ADR-011](DECISIONS.md)；前序盘点：[survey-articles-m2-0.md](survey-articles-m2-0.md)
- 结论一句话：**「登录态 detail 取图 → 下图 → macOS Vision OCR → 去固定水印 → 内容类型分类 → ArticleNote 初稿」整条链路已跑通且稳定，可进入全量；图文以现货货盘/设计稿/活动为主，纯知识科普图文稀少。**

## 1. 采集链路（已固化为脚本）

| 环节 | 实现 | 说明 |
| --- | --- | --- |
| 取清单 | `articles_dynamic_scan.json`（M2-0 已全量翻取） | 11539 动态，其中 DRAW 图文 **4366**、图片计数合计 **13930** 张 |
| 取详情 | 登录页面上下文 `fetch x/polymer/web-dynamic/v1/detail?id=<id>` | code=0、无需 wbi；图在 `major.draw.items[].src`，兼容 `major.opus.pics[].url` |
| 下图 | urllib + UA/Referer、https 直连 | new_dyn 图床多为 `.png`（1080 宽竖图），单张 0.8–1.8s |
| OCR | `scripts/ocr/ocr_vision`（macOS Vision，zh-Hans+en-US，accurate） | 离线免费、约 1s/张；源码 `ocr_vision.swift` |
| 去水印 | `scripts/ocr/clean_watermark.py` | 整行判定去固定品牌水印，原始 OCR 保留可追溯 |
| 纠错 | `scripts/ocr/correct_ocr.py` | 高置信固定错形（ct 单位、小数点、宝石/字段形近），保守不强改低置信碎错 |
| 拼稿/分类 | `scripts/harvest_articles.py` | ArticleNote 初稿 + `content_type`；支持断点、幂等、`--rebuild` 离线重建 |
| 完整性校验 | `scripts/verify_articles.py` | 图数=OCR数=meta数=article清单逐一对齐，全量断点续跑后必跑（思路移植高顿 verify_ocr） |

产物结构（原始层，文本入库、图片二进制 gitignore）：

```
library/06_articles/raw/<yyyy-mm>/<动态id>/
  meta.json            # 元数据 + 每图 URL/尺寸/原始字/有效字 + content_type
  images/NN.png|jpg    # 原图（不入库，本地+网盘）
  ocr/NN.txt           # Vision OCR 原始逐行文本（含水印，可追溯）
  article.md           # 去水印后按图顺序的 ArticleNote（OKF 标准档，status:draft）
```

## 2. 20 篇试点构成（实数）

- 总图 81 张 = OCR 文本 81 个，全部采通、零失败；frontmatter 全部合规。
- 去水印后有效字合计 971；**带文字 10 篇 / 纯图（设计稿或实物图）10 篇，各占一半**。

| 内容类型 content_type | 篇数 | 占比 | 典型内容 |
| --- | --- | --- | --- |
| image_only 纯图/设计稿 | 10 | 50% | 客订设计效果图、成品实物图（画面只有斜排水印，OCR 后有效字为 0，价值在图本身） |
| goods_price 现货行情/货盘 | 6 | 30% | 精切蓝宝石/黄蓝宝/灰尖晶的克拉、切工、价格；哥伦比亚祖母绿货盘（名称/标价/编码/重量/证书） |
| event 直播/活动 | 2 | 10% | 香港珠宝展复盘直播预告、永乐拍卖专场 |
| catalog 款式目录 | 1 | 5% | 18k 金钻石祖母绿耳钉 款1–款19 |
| mixed_text 待细分 | 1 | 5% | 宝石种类标签（沙佛莱/粉蓝宝/黄蓝宝/蓝宝石/白蓝宝） |
| knowledge 知识科普 | **0** | 0% | 20 篇内未出现图文版科普长卡 |

年份覆盖 2021–2026（分层抽样每年图最多的 1 篇 + 2026 年连续 15 篇）。

## 3. OCR 质量评估

**识别可靠、可直接用的部分**：
- 中文货品/品类标签准确：皇家蓝、无烧矢车菊、无烧蓝宝、18k金天然钻石祖母绿耳钉、沙佛莱、灰尖晶；
- 数字+单位、切工形状基本可用：1.22ct、阿斯切、水滴、椭圆、爱心、盾牌、四边形；
- 现货要素成列可读：名称/标价/编码/重量/证书、`卖掉了`（售出状态）、`$9899/5399`（价格带）。

**已知错误（机器初稿标 draft，知识层精修时用"误识纠错表"处理）**：
- 单位：`ct` 易误作 `c/g/Gt`（2.11Gt、1ci、2.26g）；
- 数字：小数点误作逗号（1,34ct）、价格被作者主动打码（$4XXX）；
- 形近字：蓝→遊（黄遊宝）、圆→园（椭园）、小字段落"名称/重量/编码"偶发乱码（名冰/車量/编积）；
- 繁体艺术字（拍卖图录）识别较弱。

**水印治理（关键）**：该号每张图铺满固定水印（宝石学家老许®/許多福珠寶/原創設計/DESIGN AND VALUE/COLORED GEMSTONE/TEXTURE OF MATERIAL，含大量 OCR 残缺变体），不去水印会把纯设计稿虚增成 800+“字”。`clean_watermark.py` 数据驱动建表 + 整行判定后：3 条纯设计稿从 813/889/33 字全部清到 **0**，现货/标签/预告行零误伤。故信息密度一律以 `clean_chars`（去水印有效字）为准，不看原始 `ocr_chars`。

**纠错层与其边界（参考高顿 OCR SOP）**：高顿课件是规整 PPT，固定 sed 纠错（高顿教肓→高顿教育）足够；珠宝货盘是手机截图、字体花、字段密集，错形多变。故 `correct_ocr.py` 只做**零误伤的高置信纠错**：重量单位归一（`2.11Gt/2.26g/1ci→ct`）、小数点误逗号（`1,34ct→1.34ct`）、特异形近（哥伦比业亚→哥伦比亚、車量/更量→重量、GULDD→GUILD 证书）。像"3的/色孙/祖母姿/但茑烧"这类**无法高置信还原的字段/品种碎错保留原样、不硬猜**——这与高顿 SOP「Vision 对表格只能出平铺文字、字段级结构交 AI 视觉」一致：现货货盘（goods_price）要结构化成"品类×克拉×切工×价格带"，留 M2-2 对货盘图走多模态视觉重识别，正则只负责把可读性拉到可用基线。

## 4. 关键判断

1. **图文与视频分工明确**：知识体系化讲解主要在 743 条视频里；图文动态承担"现货上新/货盘、客订设计、款式目录、活动预告"，是**做号选品、价格带与货盘结构分析、设计灵感**的弹药，而非科普长文（试点 knowledge=0）。全量后需复核该占比，但分层抽样已覆盖各年，趋势较稳。
2. **现货/设计稿按用户口径全部保留**（ADR-011）：不做"纯科普"过滤，只做 content_type 分类；纯图也保留原图，后续可用于做号图集/设计参考。
3. **动态本身零文字是常态**：4366 条 DRAW 里有标题仅 1、有正文 desc 的 0，价值全在图，必须 OCR，不能依赖动态文字字段。

## 5. 全量方案（待用户拍板后启动）

- 规模：4366 篇 / 13930 张图；按当前节奏（下图+OCR 约 2.5s/张、detail 3–5s/篇）串行约 **10–15 小时**。
- 打法：后台分批、断点续跑（脚本已支持 done 跳过、`--rebuild` 离线重出稿）；建议按年份分批、夜间/空闲跑，单批后抽查 OCR 与分类。OCR 进程不要挂在交互终端（高顿实测会被退出），用 `nohup ... &` 脱离会话 + `tail -f` 看日志，避免会话/休眠带停；每批结束跑 `scripts/verify_articles.py` 对账（残缺即补采）。
- 防风控：沿用 ADR-009——直连、单线程、慢速随机间隔，命中 code!=0/412/-352 立即停手冷却，不换参硬撞；只读公开动态、用小号不碰主号。
- 全量完成后进入 M2-2：按主题把 ArticleNote 编译进 `05_knowledge`（现货行情可额外结构化为"品类×克拉×切工×价格带"表，服务选品与行情）。

## 6. 复现命令

```bash
# 前置：9223 登录 Chrome 已开并停在 space.bilibili.com，export CHROME_DEV_WS=$(curl -s 127.0.0.1:9223/json/version | python3 -c "import sys,json;print(json.load(sys.stdin)['webSocketDebuggerUrl'])")
python3 scripts/harvest_articles.py --limit 15        # 按 scan 顺序采
python3 scripts/harvest_articles.py --ids <id>,<id>   # 指定动态
python3 scripts/harvest_articles.py --rebuild         # 不联网，按最新清洗/纠错/模板重建所有 article.md
python3 scripts/ocr/clean_watermark.py library/06_articles/raw   # 查看去水印前后对照
python3 scripts/ocr/correct_ocr.py library/06_articles/raw       # 查看各篇纠错处数
python3 scripts/verify_articles.py                    # 完整性/一致性对账（残缺退出码 1）
```
