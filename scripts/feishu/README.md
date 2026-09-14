# scripts/feishu — 本地图文 → 飞书知识库的渲染层

本地 `library/06_articles` 是唯一权威源，本目录只负责把本地内容渲染成飞书 docx XML，
**不抓取、不回写本地、不反向改飞书副本**。飞书空间「珠宝知识库」(`7684926682473467058`) 只是发布层。

## 两个渲染器

| 脚本 | 版本 | 用途 |
| --- | --- | --- |
| `article_to_xml.py` | v1 平铺 | 逐图堆 OCR 散行，仅用于原始对照/快速上线，可读性差 |
| `feishu_doc.py` | **v2 话题化（正式成品用）** | 读结构化 spec 渲染成五块结构，支持表格、内联本地图 |

## v2 五块结构（用户拍板的标准）

1. **话题概述**：一句话讲清这是什么、多少件/款、按什么线索组织（原动态往往随机跳话题，必须先归并）。
2. **原图**：原图全部保留，逐张带 caption；超长货盘长图先用 PIL 切片读清再整体上传。
3. **结构化主体**：按内容类型选形态——
   - 现货货盘 `goods_price` → 清单表（名称/重量/编码/证书/标价/单价等，单价由重量与标价**现算**）
   - 款式目录 `catalog` → 按设计形态分组表（款号对应原图编号，据图判读要注明）
   - 设计稿 `image_only` → 逐图设计元素表（左成品/右设计稿对照）
   - 直播活动 `event` → 关键信息表（主题/时间/形式/视觉）
   - 知识科普 `knowledge` → 要点
4. **有价值评论**：默认不采集；仅爆款且讨论有信息量时单独保留。
5. **选品 / 做号观察**：面向自营号的可复用判断（品类定位、工艺卖点、内容选题、可借鉴手法、做号纪律）。

纪律：只组织、不臆造；图面没标主石名称时不把素面蓝幻彩说成蓝宝石，统一写"蓝色系彩宝，以证书为准"；
孤立噪声散行（"卖掉了""ct"残片）删除；直播类内容归空间节点「04 直播活动」。

## 全量单篇操作

```bash
# 1) 多模态逐张读 images/（必要时 PIL 切长图），核对 ocr/*.txt 但以读图为准
# 2) 产出 spec（先看五块骨架）
python3 scripts/feishu/feishu_doc.py --skeleton
# 3) 填好 spec.json 后渲染
python3 scripts/feishu/feishu_doc.py spec.json -o out.xml
# 4) 覆盖已有节点 / 在某分类节点下新建
lark-cli docs +update --as user --doc <obj_token> --command overwrite --doc-format xml --content @out.xml
lark-cli docs +create --as user --parent-token <wiki分类节点> --doc-format xml --content @out.xml
# 5) 回读校验：h2 数、表格 <tr> 行数、<img> 数与预期一致
lark-cli docs +fetch --as user --doc <obj_token> --doc-format xml | grep -o '<img' | wc -l
```

> overwrite 会清空重写，新 XML 里必须用 `<img path="@绝对路径" width=.. caption=".."/>` 把全部图片重带；
> 含多图时命令可能超 15s 被移后台，用 TaskOutput 等完成。竖图 width≈300–440、横总览≈520、超长货盘图≈380。

## 分类节点 node_token（空间 7684926682473467058）

01 现货货盘 `IxLbwPyLLiSwAHkbTM6cqaZZn3f`｜02 款式目录 `ICJTwYzZAiuxNgkTD71cUDsanke`｜
03 设计稿与客订 `AuOpwddH8iTagxkbinWcm3nMnDc`｜04 直播活动 `NZ6pw0fB0iDa3akjl6ycKdbBn2d`｜
05 知识科普 `WtzfwfjaAiWdKYktE86cTZw1nmc`｜06 视频精解(试点) `A4QHwdobhi9CcPk0lM2c6oIqnyh`。

## 首批试点（2026-09-13，已上线 v2）

蓝宝石货盘、哥伦比亚祖母绿货盘（01）、18K 祖母绿耳钉 19 款（02）、客订设计稿 9 组（03）、
香港珠宝展复盘直播预告（04）；另有 3 篇视频精解试点在 06（概述+章节时间线+要点，不堆逐字稿）。
