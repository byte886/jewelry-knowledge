# docs · 珠宝知识库工程文档地图

这是「宝石学家老许」珠宝学个人知识库的**工程治理目录**。单人开发，用最少文档承载关键决策，3 秒找到要改哪里。

## 阅读顺序
1. [PRD.md](./PRD.md) — 为什么做、做什么、不做什么、成功标准（先读）。
2. [ARCHITECTURE.md](./ARCHITECTURE.md) — 分层、目录、三类条目 schema、增量水位、OCR、书籍、防风控。
3. [ROADMAP.md](./ROADMAP.md) — M0–M5 里程碑与每阶段完成定义。
4. [BACKLOG.md](./BACKLOG.md) — 拆到 1–4h 的任务台账（从这里领活）。
5. [DECISIONS.md](./DECISIONS.md) — 关键决策 ADR（为什么这么定）。
6. [NETDISK_SYNC.md](./NETDISK_SYNC.md) — 百度网盘成品同步：沙箱机制、目录映射、断点、排错。
7. [MEDIA_ARCHIVE_OPS.md](./MEDIA_ARCHIVE_OPS.md) — 视频原片：为何不转码、漏合流无损修复、类内序号命名、外置介质 rsync 归档与三重校验（ADR-013）。

> AI 代理操作规则与命令速查看根目录 [AGENTS.md](../AGENTS.md)（开工先读）。

## 新会话 / 新机器如何快速接手
```bash
# 1) 进入项目、看进度（项目已实体迁移到桌面）
cd ~/Desktop/gemology-kb
cat docs/BACKLOG.md                 # 当前 in-progress 的任务卡
cat library/05_knowledge/index.md          # OKF 知识包导航
/usr/bin/python3 refine_queue.py | head    # 刷新并查看精修分档队列（full/lite/story/done）
# 2) 校验知识包
python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge --json
# 3) 继续精修：从 refine_queue.json 选 full 档 → 读 04_transcript 原文 → 写 stable 条目 → build+validate
```
- 知识格式标准看技能 `~/Doubao/skills/okf-wiki/SKILL.md`；下载/转写/防风控看 `~/Doubao/skills/multiplatform-media-fetch/`。
- 根目录 `AGENTS.md` 是 AI 操作手册（规则/命令/异常，开工先读），`README.md` 是项目概览与采集流水线交接。

## 仓库
- 远程：`git@github.com:byte886/jewelry-knowledge.git`（**公有**，只放清洗后成品；ADR-012 已取代 ADR-003 的私有设定）。
- 提交规范：Conventional Commits（`feat:/fix:/docs:/chore:/refactor:`）。
- **不入库**：13G 原始视频/音频、cookie/登录态（secrets、.chrome-prof*）、venv、日志、`workspace/`、`_archive/`、`.secrets` 明文（仅 `*.enc` 放行），见 `.gitignore`。

## 边界一句话
本地为源、私有留存、个人学习研究使用；不公开分发他人转写/书籍内容；防风控第一、接受慢速。
