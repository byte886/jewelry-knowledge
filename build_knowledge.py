#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_knowledge.py —— 把 04_transcript 的 743 篇自动转写，按 OKF v0.2（标准档）
确定性"编译"成本地知识包 library/05_knowledge（bundle）。

设计纪律（对齐 ~/Doubao/skills/okf-wiki，且通过 okf_validate.py）：
- 04_transcript 是不可变原始资料，本脚本不改它；条目用 sources 指回它与 B 站原视频。
- **条目文件名 = bvid.md**：唯一、无空格/括号/emoji，跨平台与 Markdown 链接安全
  （OKF 校验器链接目标不允许空白）；中文标题在 frontmatter/正文/索引链接文本里。
- frontmatter 机器字段由台账与转写稿权威生成；description 为客观、确定性描述（不编造内容摘要）。
- 本轮是"批量回填骨架"：条目一律 status: draft、**不写 verified**（不冒充人工复核）；
  逐篇精要、同音字纠错、横向主题在后续分批做，再升 stable / 加 verified。
- 幂等：每次清空重建 concepts/videos、concepts/topics（均为本脚本生成物），重写各 index/log 当天块。
- 纯标准库。
"""
import json
import os
import re
import shutil
import datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(ROOT, "library")
MANIFEST = os.path.join(LIB, "00_manifest", "manifest.json")
TRANS_DIR = os.path.join(LIB, "04_transcript")
KB = os.path.join(LIB, "05_knowledge")
VID_CDIR = os.path.join(KB, "concepts", "videos")
TOP_CDIR = os.path.join(KB, "concepts", "topics")
AUTHOR = "宝石学家老许"
UP_MID = "1841256325"
GEN_BY = "doubao/okf-wiki"
TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime.now(TZ).replace(microsecond=0)
NOW_ISO = NOW.isoformat()
TODAY = NOW.strftime("%Y-%m-%d")

TOPIC_ORDER = [
    "01_钻石", "02_彩色宝石", "03_玉石", "04_有机宝石", "05_金属首饰与佩戴",
    "06_鉴定与避坑", "07_行情与选购", "08_行业与商业", "09_品牌新品与动态",
    "10_珠宝文化与故事", "11_其他",
]
# 规划中的横向主题（第二步语义加工；本轮先建占位页，避免前向死链）
PLANNED_TOPICS = [
    ("钻石选购与4C", "钻石 4C、证书、切工净度颜色与选购要点"),
    ("彩色宝石图谱与价值", "红蓝宝/祖母绿/碧玺/帕帕拉恰等彩宝品类与价值判断"),
    ("玉石", "翡翠/和田玉等玉石品类、种水与鉴别"),
    ("有机宝石", "珍珠/琥珀/珊瑚等有机宝石"),
    ("镶嵌工艺与佩戴", "镶嵌方式、牢固度、金属材质与日常佩戴"),
    ("鉴定与避坑", "套证/合成/优化处理/二手钻等鉴定与防骗"),
    ("行情价格与选购话术", "价格逻辑、进店问法、保值与变现"),
    ("行业与商业", "珠宝行业、定制生意、创业与供应链"),
    ("品牌与新品动态", "品牌、新品与市场动态"),
    ("珠宝文化与故事", "生辰石、珠宝历史文化与客订故事"),
]


def yq(s) -> str:
    if s is None:
        return '""'
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def len_to_sec(length: str) -> int:
    try:
        sec = 0
        for n in [int(x) for x in str(length).strip().split(":")]:
            sec = sec * 60 + n
        return sec
    except ValueError:
        return 0


def created_iso(ts) -> str:
    try:
        return dt.datetime.fromtimestamp(int(ts), TZ).replace(microsecond=0).isoformat()
    except Exception:
        return ""


def parse_transcript(path):
    paras = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").strip()
            if not line or line.startswith(("# ", "> ", "## ")):
                continue
            paras.append(line)
    words = sum(len(re.sub(r"\s", "", p)) for p in paras)
    return paras, words


def build_bvid_transcript_map():
    m = {}
    for dirpath, _d, files in os.walk(TRANS_DIR):
        if "transcript.md" in files:
            mm = re.search(r"\[(BV[0-9A-Za-z]+)\]", os.path.basename(dirpath))
            if mm:
                m[mm.group(1)] = os.path.join(dirpath, "transcript.md")
    return m


def render_concept(item, paras, words, rel_to_transcript) -> str:
    bvid = item["bvid"]
    sec = len_to_sec(item.get("length", "0"))
    pub = created_iso(item.get("created"))
    cat = item.get("category", "")
    season = item.get("season", "") or ""
    url = item.get("url", f"https://www.bilibili.com/video/{bvid}")
    title = item.get("title", "")
    desc = f"{AUTHOR}「{cat}」口播视频《{title}》的转写知识条目（时长{item.get('length','')}，自动初稿待精修）"
    tags = [cat] + ([season] if season else [])

    fm = ["---", "type: VideoNote", f"title: {yq(title)}", f"description: {yq(desc)}",
          "tags: [" + ", ".join(yq(t) for t in tags) + "]", "sources:"]
    fm += ["  - id: src-bili", f"    resource: {yq(url)}", f"    title: {yq(title)}",
           f"    author: \"human:{AUTHOR}(mid {UP_MID})\""]
    if pub:
        fm.append(f"    last_modified: {pub}")
    fm += ["  - id: src-transcript", f"    resource: {yq(rel_to_transcript)}",
           '    title: "本地自动转写稿（FunASR SenseVoiceSmall，未人工校）"']
    fm.append(f"generated: {{ by: \"{GEN_BY}\", at: {NOW_ISO} }}")
    fm.append("status: draft")
    fm += [f"bvid: {yq(bvid)}", f"duration_sec: {sec}", f"duration: {yq(item.get('length',''))}"]
    if pub:
        fm.append(f"published: {pub}")
    fm.append(f"category: {yq(cat)}")
    if season:
        fm.append(f"season: {yq(season)}")
    fm += [f"play: {int(item.get('play') or 0)}", f"words: {words}", "---"]

    body = [f"# {title} ［{bvid}］", ""]
    meta = f"> 所属：{cat}"
    if season:
        meta += f"　合集：{season}"
    meta += f"　时长：{item.get('length','')}　发布：{pub[:10]}　播放：{item.get('play',0)}　正文约 {words} 字"
    body += [meta, "> 本信息块由 frontmatter 派生；状态 **draft（自动转写初稿，未人工校，含同音错字）**。", "",
             f"原视频：{url} [^src-bili]；本地转写稿见 [^src-transcript]。", "",
             "## 内容转写（自动初稿，待校）", ""]
    body += paras
    body += ["", "## 精要提炼", "",
             "> 待第二批语义加工：纠错同音字、去口水、提炼 3–6 条要点与可检索结论；完成后升 status: stable 并补 verified。", "",
             "## 关联", "",
             "- 横向主题：待 `concepts/topics/` 沉淀后回填。", "",
             "## 来源", "",
             f"[^src-bili]: B 站原视频：{url}（{AUTHOR}）",
             f"[^src-transcript]: 本地 FunASR 自动转写稿（相对路径）：{rel_to_transcript}", ""]
    return "\n".join(fm) + "\n\n" + "\n".join(body)


def render_topic(name, sub):
    fm = ["---", "type: Concept", f"title: {yq(name)}",
          f"description: {yq('横向主题：' + sub + '（规划占位，待从多篇 VideoNote 提炼）')}",
          f"tags: [横向主题]", f"generated: {{ by: \"{GEN_BY}\", at: {NOW_ISO} }}",
          "status: draft", "---"]
    body = [f"# {name}", "", f"> {sub}", "",
            "## 概述", "", "> 待第二步语义加工：跨该主题下的多篇 VideoNote 归纳稳定结论，并逐点挂来源脚注。", "",
            "## 关联条目", "", "> 生成精修时，回填该主题覆盖的 VideoNote（bvid）链接。", ""]
    return "\n".join(fm) + "\n\n" + "\n".join(body)


def main():
    d = json.load(open(MANIFEST, encoding="utf-8"))
    videos = d if isinstance(d, list) else d.get("videos", [])
    tmap = build_bvid_transcript_map()

    # topics 全由脚本生成，可清空重建；videos 保留已精修(stable/deprecated)条目，不整体删除
    shutil.rmtree(TOP_CDIR, ignore_errors=True)
    os.makedirs(TOP_CDIR, exist_ok=True)
    os.makedirs(VID_CDIR, exist_ok=True)
    valid_bvids = {x["bvid"] for x in videos}

    cat_items = {}
    miss_t = 0
    total_words = total_sec = written = 0

    for it in videos:
        bvid = it["bvid"]
        cat = it.get("category", "11_其他")
        tpath = tmap.get(bvid)
        if not tpath:
            miss_t += 1
            paras, words = [], 0
        else:
            paras, words = parse_transcript(tpath)
        total_words += words
        total_sec += len_to_sec(it.get("length", "0"))
        cdir = os.path.join(VID_CDIR, cat)
        os.makedirs(cdir, exist_ok=True)
        rel = os.path.relpath(tpath, cdir) if tpath else ""
        cpath = os.path.join(cdir, f"{bvid}.md")
        # 保护已精修条目：若已存在且 status 非 draft（stable/deprecated），重跑时不覆盖
        already = os.path.exists(cpath) and bool(
            re.search(r"^status:\s*(stable|deprecated)",
                      open(cpath, encoding="utf-8").read()[:800], re.M))
        if not already:
            with open(cpath, "w", encoding="utf-8") as f:
                f.write(render_concept(it, paras, words, rel))
        written += 1
        cat_items.setdefault(cat, []).append((it, bvid, words))

    def cat_key(c):
        return (0, TOPIC_ORDER.index(c)) if c in TOPIC_ORDER else (1, c)

    # 各分类子 index（链接目标 = bvid.md，无空白，校验安全）
    for cat, rows in cat_items.items():
        rows.sort(key=lambda r: -(r[0].get("created") or 0))
        L = [f"# {cat}（{len(rows)} 篇）", "",
             "> 子目录页只做导航；按发布倒序；链接文本是标题，目标是 bvid 条目。", ""]
        for it, bvid, words in rows:
            L.append(f"* [{it['title']}]({bvid}.md) - {it.get('length','')} · 约{words}字 · {created_iso(it.get('created'))[:10]}")
        L.append("")
        with open(os.path.join(VID_CDIR, cat, "index.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # 清理 videos 下已不在台账的孤儿 bvid 条目（保留 index.md 与所有现存条目）
    for dp, _dd, fs in os.walk(VID_CDIR):
        for fn in fs:
            stem = fn[:-3] if fn.endswith(".md") else fn
            if fn.endswith(".md") and fn != "index.md" and stem not in valid_bvids:
                os.remove(os.path.join(dp, fn))

    # topics 占位页 + 其 index
    for name, sub in PLANNED_TOPICS:
        with open(os.path.join(TOP_CDIR, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write(render_topic(name, sub))
    tl = ["# 横向主题（concepts/topics）", "",
          "> 跨视频沉淀的稳定知识，一篇一个主题，从多篇 VideoNote 提炼（第二步语义加工）。", ""]
    for name, sub in PLANNED_TOPICS:
        tl.append(f"* [{name}](./{name}.md) - {sub}（占位待提炼）")
    tl.append("")
    with open(os.path.join(TOP_CDIR, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(tl))

    cats_sorted = sorted(cat_items.keys(), key=cat_key)
    topic_cats = [c for c in cats_sorted if c in TOPIC_ORDER]
    season_cats = [c for c in cats_sorted if c not in TOPIC_ORDER]
    hh, mm = total_sec // 3600, (total_sec % 3600) // 60

    idx = ["---", 'okf_version: "0.2"', "---",
           "# 宝石学家老许 · 珠宝科普知识库（OKF bundle）", "",
           f"> UP：{AUTHOR}（mid {UP_MID}）｜条目 {written} 篇｜分类 {len(cat_items)} 个（11 主题 + 11 官方合集）",
           f"> 总时长约 {hh}小时{mm}分｜正文约 {total_words/10000:.1f} 万字｜生成于 {NOW_ISO}｜条目状态 draft（自动初稿，待分批精修）",
           "> 阅读顺序：本页定位 → 分类子 index → bvid 条目；原始转写在 ../../04_transcript/ 不可变。", "",
           "# 一、主题类（按材质/维度）", ""]
    for c in topic_cats:
        idx.append(f"* [{c}](concepts/videos/{c}/index.md) - {len(cat_items[c])} 篇")
    idx += ["", "# 二、官方合集", ""]
    for c in season_cats:
        idx.append(f"* [{c}](concepts/videos/{c}/index.md) - {len(cat_items[c])} 篇")
    idx += ["", "# 三、横向主题与治理", "",
            "* [横向主题 topics](concepts/topics/index.md) - 跨视频稳定知识（10 个规划占位）",
            "* [变更日志 log.md](log.md)", "* [本 bundle 说明 README.md](README.md)", ""]
    with open(os.path.join(KB, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx))

    readme = ["---", "type: Meta",
              'title: "05_knowledge 珠宝视频 OKF 本地知识包说明"',
              'description: "本 OKF bundle 的结构、type 词表、加工纪律与新会话恢复顺序（schema 层）"',
              f"generated: {{ by: \"{GEN_BY}\", at: {NOW_ISO} }}", "status: stable", "---",
              "# 05_knowledge —— 珠宝视频 OKF 本地知识包", "",
              "本目录是 OKF v0.2 bundle（方法见 `~/Doubao/skills/okf-wiki`），由 `../build_knowledge.py` 确定性生成。", "",
              "## 结构",
              "- `index.md` 根导航（唯一带 okf_version 的 index）；`log.md` 倒序变更。",
              "- `concepts/videos/<分类>/<bvid>.md`：单视频 `VideoNote`（标准档）；文件名用 bvid（稳定、无空格），中文标题见 frontmatter/正文。",
              "- `concepts/topics/`：10 个跨视频横向主题占位，第二步语义加工填充。",
              "- 原始资料 `../../04_transcript/` 不可变，条目 sources 指回它与 B 站原视频。", "",
              "## type 词表",
              "- `VideoNote` 单条视频条目；`Concept` 跨视频主题；`Meta` 本说明页。", "",
              "## 状态与加工纪律",
              "- 自动骨架一律 `status: draft`、不写 `verified`；逐篇纠错/精要后升 `stable` 并补 `verified`。",
              "- 机器字段以 manifest 为权威、脚本重算，不手改；易变值不抄进正文；改条目同步 index 并在 log 追加。", "",
              "## 新会话恢复顺序",
              "读本页 → 根 index → 分类 index → 按需打开条目，不整库注入。交付前跑 "
              "`python3 ~/Doubao/skills/okf-wiki/scripts/okf_validate.py library/05_knowledge`。", ""]
    with open(os.path.join(KB, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme))

    logp = os.path.join(KB, "log.md")
    s_stable = 0  # 已精修(stable)条目数，随重跑实时统计
    for _dp, _dd, _fs in os.walk(VID_CDIR):
        for _fn in _fs:
            if _fn.endswith(".md") and re.search(
                    r"^status:\s*stable",
                    open(os.path.join(_dp, _fn), encoding="utf-8").read()[:800], re.M):
                s_stable += 1
    head = ["# Directory Update Log", "",
            "<!-- 倒序：## YYYY-MM-DD；行首约定 Creation/Update/Deprecation。 -->", "",
            f"## {TODAY}",
            "* **Creation**: 初始化 OKF bundle（根 index、README/Meta、10 个 topics 占位）。",
            f"* **Creation**: 从 04_transcript 批量编译 {written} 个 VideoNote（文件名=bvid，status: draft，未人工校）与 22 个分类子 index。",
            f"* **Update**: 逐篇语义精修推进中，已 stable {s_stable}/{written}（AI 精修、待人工复核；分档见 00_manifest/refine_queue.json）。",
            ""]
    # 只保留"非今天"的历史日期块，当天块由 head 确定性重建，避免重跑重复累积
    history = []
    if os.path.exists(logp):
        old = open(logp, encoding="utf-8").read().splitlines()
        keep = False
        for l in old:
            m = re.match(r"## \d{4}-\d{2}-\d{2}", l)
            if m:
                keep = (l.strip() != f"## {TODAY}")
            if keep:
                history.append(l)
        while history and not history[0].strip():
            history.pop(0)
    out = head + history
    with open(logp, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")

    print(f"[done] 条目 {written}，缺转写 {miss_t}，分类 {len(cat_items)}，"
          f"净正文字数 {total_words}，总时长 {hh}h{mm}m -> {KB}")


if __name__ == "__main__":
    main()
