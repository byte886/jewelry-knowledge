# 百度网盘同步（NETDISK_SYNC）

> 成品备份与跨设备访问。**只传成品，不传过程件**；风格对齐高顿/股票项目。通用上传器 `scripts/netdisk/baidu_upload.py`，项目编排 `scripts/netdisk/sync_netdisk.py`。

## 1. 平台机制（先理解，避免踩坑）
- 百度网盘开放平台的"应用"决定一个独立沙箱 `/apps/<应用名>/`（沙箱外读写报 31064），客户端里对应「我的应用数据/<应用名>/」。本账号当前唯一应用为「CPA课程归档」；**已决定不再为珠宝单独建应用**（2026-09-12 决策，理由见第 8 节），各项目以沙箱内平级"领域知识库"目录隔离。
- 当前共用沙箱内按"领域知识库"开**平级顶层目录**隔离、互不混入（2026-09-12 云端 list 实测）：

| 沙箱顶层目录 | 归属 | 说明 |
|---|---|---|
| `会计知识库/高顿/` | 高顿项目 | **CPA/会计专用**；原顶层 `高顿/` 已被归入本组，其它项目不进入 |
| `股票知识库/` | stock 项目 | 01-视频号短视频 / 02-视频号直播回放 / 03-公众号文章 / 04-书籍精华 / 05-知识成品 |
| `珠宝知识库/` | 本项目 | 2026-09-12 建；本次网盘重组**未改变其路径与 5 个子目录名**，同步映射、断点均仍有效 |

- 命名风格：顶层「领域知识库」中文 + 子目录「编号-中文」。

## 2. 珠宝知识库目录与本地映射
| 网盘目录 | 本地来源 | 传什么 |
|---|---|---|
| `珠宝知识库/01-视频原片/` | `library/01_video/` | `*.mp4`（13G，全量慢传） |
| `珠宝知识库/02-视频转写/` | `library/04_transcript/` | **仅 transcript.md**，跳过 transcript.json/音频 |
| `珠宝知识库/03-图文动态/` | `library/06_articles/`（M2 才建） | 图文正文 + OCR 成品 |
| `珠宝知识库/04-书籍精华/` | `library/07_books/`（M4 才建） | 书摘/章节知识 |
| `珠宝知识库/05-知识成品/` | `library/05_knowledge/` | OKF 全部 `.md` |

内部相对路径保持同构（分类/`标题 [BV]`/transcript.md），便于双向对账。

## 3. 凭证
- `.secrets/baidu_credentials.enc`：AES-256-CBC + pbkdf2 加密（与高顿/股票同一账号同一应用，直接复用）。**加密件可入库**（无口令解不开），明文/token 绝不入库、不回显。
- 运行时用环境变量给口令：`export BAIDU_ENC_PASS='<向用户索取，不写入仓库>'`。
- access_token 约 30 天、refresh_token 约 10 年；过期(111)用 refresh_token 走 `oauth/2.0/token?grant_type=refresh_token` 刷新并**回存加密件**。
- API 强制直连（脚本内 curl 不走系统代理）。

## 4. 同步命令（项目根运行）
```bash
export BAIDU_ENC_PASS='<向用户索取>'
P="/usr/bin/python3 scripts/netdisk/sync_netdisk.py"
$P --dry-run                                   # 只列计划与远程名映射，不传
$P --only knowledge,transcript --limit 3       # 选层限量试传
$P --only transcript --sleep 1                 # 只同步某层；--sleep 文件间隔(视频自动×3)
$P                                             # 全量同步（含 13G 视频，建议 nohup 后台）
$P --force                                     # 忽略断点强制重传
```
- `--only` 取值：`video / transcript / article / book / knowledge`，逗号组合。
- 过滤规则（硬编码）：跳过 `02_audio/ workspace/ _archive/ secrets/ .secrets/ __pycache__/`、`.DS_Store`、`transcript.json`。

## 5. 断点与可靠性
- 已传记录：`workspace/netdisk/uploaded.tsv`（相对路径 + size + 网盘路径）；重跑时已传且大小一致自动跳过。失败清单 `failed.tsv`，**单文件失败不中断整体**，修复后重跑即续。
- 上传三步 `precreate → superfile2(4MB 分片) → create`；按大小+MD5 分片，网盘已存在同文件会**秒传**；同名覆盖 `rtype=3`（precreate/create 都带）。
- **emoji/特殊字符**：百度 `create` 拒绝 emoji（errno -7，全库 96 个路径命中）。同步器只对**网盘远程名**去 emoji/半角非法字符，**本地文件名保持不动**；`--dry-run` 会用 `[名字含emoji将净化]` 标出差异。
- URL query 参数已做百分号编码，中文/空格/方括号 `[BV号]` 路径可正常上传。

## 6. 全量策略建议
1. 先传文本层（小、快、价值高）：`--only knowledge,transcript`，约 1500 个 md。
2. 视频层 13G 单独后台、慢速：`nohup env BAIDU_ENC_PASS=... /usr/bin/python3 scripts/netdisk/sync_netdisk.py --only video --sleep 4 > workspace/logs/netdisk-video.log 2>&1 &`，可随时中断、重跑续传。
3. 传完用 `baidu_upload.py list <网盘目录>` 分层回列，数量与本地对账。

## 7. 单文件/手工操作（通用上传器）
```bash
U=scripts/netdisk/baidu_upload.py
$U list  "/apps/CPA课程归档/珠宝知识库"          # 列目录
$U mkdir "/apps/CPA课程归档/珠宝知识库/xx"        # 建目录(31061=已存在,忽略)
$U upload "<本地文件>" "<完整网盘路径>"           # 单文件上传(自动建父目录)
```

## 8. 决策：不建珠宝独立 App（2026-09-12，见 ADR-010）
- **结论**：维持共用「CPA课程归档」应用沙箱，珠宝用其下平级目录 `珠宝知识库/`，不再单独创建百度应用。
- **理由**：同一百度账号、同一 token 下，沙箱内"领域知识库"目录级隔离与独立 App 沙箱在功能/权限/备份上等价；云端已按 会计/股票/珠宝 分好，同步映射与断点已实测可用，省去再建应用、再走 OAuth、再维护一套凭证和切换 `NETDISK_BASE` 的成本。
- 个人认证应用数量上限网上"1 个 / 2 个"说法矛盾，本决策后无需再核实。
- 将来若确需物理独立（换账号、对外授权等），再走：控制台建"软件"类应用 → 取 AppID/AppKey/SecretKey/SignKey → OAuth 授权 → **另存**加密凭证（勿覆盖现凭证）→ 改 `sync_netdisk.py` 的 `NETDISK_BASE` 到新沙箱。
