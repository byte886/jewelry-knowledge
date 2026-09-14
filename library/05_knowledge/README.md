---
type: Meta
title: "05_knowledge 珠宝视频 OKF 本地知识包说明"
description: "本 OKF bundle 的结构、type 词表、加工纪律与新会话恢复顺序（schema 层）"
generated: { by: "doubao/okf-wiki", at: 2026-09-12T11:45:27+08:00 }
status: stable
---
# 05_knowledge —— 珠宝视频 OKF 本地知识包

本目录是 OKF v0.2 bundle（方法见 `~/Doubao/skills/okf-wiki`），由 `../build_knowledge.py` 确定性生成。

## 结构
- `index.md` 根导航（唯一带 okf_version 的 index）；`log.md` 倒序变更。
- `concepts/videos/<分类>/<bvid>.md`：单视频 `VideoNote`（标准档）；文件名用 bvid（稳定、无空格），中文标题见 frontmatter/正文。
- `concepts/topics/`：10 个跨视频横向主题占位，第二步语义加工填充。
- 原始资料 `../../04_transcript/` 不可变，条目 sources 指回它与 B 站原视频。

## type 词表
- `VideoNote` 单条视频条目；`Concept` 跨视频主题；`Meta` 本说明页。

## 状态与加工纪律
- 自动骨架一律 `status: draft`、不写 `verified`；逐篇纠错/精要后升 `stable` 并补 `verified`。
- 机器字段以 manifest 为权威、脚本重算，不手改；易变值不抄进正文；改条目同步 index 并在 log 追加。

## 新会话恢复顺序
读本页 → 根 index → 分类 index → 按需打开条目，不整库注入。交付前跑 `python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge`。
