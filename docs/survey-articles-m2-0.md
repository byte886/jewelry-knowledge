# M2-0 图文存量盘点（实测记录）

- 日期：2026-09-12　方式：纯游客、urllib 强制直连、只读小样本（防风控）
- 结论一句话：老许几乎不写传统专栏长文（仅 1 篇），真正的"图文"是**动态里的图文动态 `DYNAMIC_TYPE_DRAW`（opus）**，最新样本里约占两成，值得单开一条采集线；精确总量需登录态慢速全翻。

## 1. 实测事实
| 探测 | 接口 | 结果 |
| --- | --- | --- |
| 传统专栏列表 | `x/space/article?mid&pn=1&ps=30&sort=publish_time` | 游客 **code=0**，`count=1`，仅 `aid=23277965`（2023-04-24《想买宝石不知道哪儿买…》，疑似引流/活动文） |
| 动态流首页 | `x/polymer/web-dynamic/v1/feed/space?host_mid=...`（offset 空） | 游客 **code=0**（nav 返回 -101 未登录不影响读取）；本屏 13 条 = **10 视频 AV + 3 图文 DRAW** |
| 图文样例 | DRAW 三条 | 图数 9 / 1 / 1，id 例 976496557498040327、1247012323884793876、1246768485655117846（opus 链接形如 `/opus/<id_str>`） |
| 唯一专栏正文 | `x/article/view?id=23277965` | **未取到**：探测期间触发 -509（见 §3），冷却后补看 |

## 2. 关键判断
1. **图文有两条独立通道，别混**：
   - 专栏长文 cv：`x/space/article`（列表）+ `x/article/view`（正文）——本 UP 基本不用；
   - 图文动态 opus/DRAW：在 `feed/space` 动态流里按 `type=DYNAMIC_TYPE_DRAW` 筛，正文/图走 opus 详情。
2. **之前"只出视频"的根因**：`bili_list.list_dynamic` 只提取了 `DYNAMIC_TYPE_AV`，把 DRAW/ARTICLE 跳过了；视频下载器的"只出视频"过滤同理，都不会带出图文。不是数据丢了，是通道没选。
3. **量级（粗估，非定论）**：最新屏 DRAW 占比约 23%。该 UP 视频 743，动态总数≥743，图文或在**百量级**；这是单屏外推，**必须全量核实后才能写进台账**。
4. 游客读 feed 有"深度墙"（历史实测约前 2 页）。要精确统计全部 DRAW，需要复用列 743 视频的办法：独立小号 Chrome（.chrome-prof3）登录态 + 慢速翻 feed，只统计不落正文。

## 3. 风控记录（本次教训）
- 短时间内连续 `warmup`(finger+首页) + article 列表 + feed 首页 + article 正文，第 4 组请求时 `finger/spi` 返回 **503**、article 返回 **code=-509 请求过于频繁**。
- 处置：**立即停止全部 B 站请求、冷却（≥15 分钟），不换参数重试**。
- 固化纪律：① 一个采集会话只 warmup 一次并复用 opener/cookie；② 不同接口之间拉长到 5–10s 以上，探测类脚本不要连发；③ 任一 503/-509/-352/412 即整体冷却。

## 4. 下一步（M2-0b / M2-1）
- M2-0b（冷却后）：启动 .chrome-prof3 独立小号，慢速翻 feed 全量，只抽取 DRAW/ARTICLE 的 id、时间、图数、文字摘要，落 `library/00_manifest/articles_manifest.json`，得到精确图文总量与时间跨度。
- M2-1：按清单抓 opus 正文 + 下载内嵌图；M2-2/3：PaddleOCR 样验后批量 OCR；再生成 ArticleNote（见 ARCHITECTURE §3/§4）。
- 探测脚本留档：`probe_article_list.py`、`probe_dynamic_types.py`。
