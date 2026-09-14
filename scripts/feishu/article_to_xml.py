#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
article_to_xml.py — [v1 平铺版] 把 06_articles 单篇成品转成飞书 XML（逐图图文混排）。

v1 只按图顺序平铺 OCR 文字，适合「原始对照 / 快速上线」；正式可读成品用 v2 话题化渲染
feishu_doc.py（五块结构：概述 / 原图 / 结构化主体 / 评论 / 选品做号观察），见同目录 README。

输入一篇 raw 目录（含 meta.json / article.md / images/），输出飞书 XML 到 stdout 或 -o 文件。
原图用 <img path="@绝对路径"/> 内联上传；OCR 文字按图顺序排在对应图后；剥离 OKF frontmatter。
这是"本地为源 → 飞书发布"的渲染层，不回写本地。

用法：
  /usr/bin/python3 scripts/feishu/article_to_xml.py <raw单篇目录> [-o out.xml]
"""
import argparse
import datetime
import json
import re
from pathlib import Path

from feishu_doc import esc

CN_TZ = datetime.timezone(datetime.timedelta(hours=8))

CN = {"goods_price": "现货行情/货盘", "catalog": "款式目录", "event": "直播/活动",
      "knowledge": "知识科普", "mixed_text": "图文待细分", "image_only": "纯图/设计稿"}


def parse_article_body(md: str):
    """返回 {图序号(int 从1): [文字行...]}；只取『图文正文』到『图片清单』之间。"""
    m = re.search(r"## 图文正文.*?\n(.*?)\n## 图片清单", md, re.S)
    seg = m.group(1) if m else ""
    figs, cur = {}, None
    for line in seg.splitlines():
        h = re.match(r"###\s*图\s*(\d+)", line.strip())
        if h:
            cur = int(h.group(1)); figs[cur] = []
        elif cur is not None:
            t = line.strip()
            if t and not t.startswith("> （"):
                figs[cur].append(t)
            elif t.startswith("> （"):
                figs[cur] = []  # 纯图占位，保持空
    return figs


def build(article_dir: Path) -> str:
    meta = json.loads((article_dir / "meta.json").read_text(encoding="utf-8"))
    md = (article_dir / "article.md").read_text(encoding="utf-8")
    figs = parse_article_body(md)
    imgs = meta.get("images", [])
    pub_ts = meta.get("pub_ts")
    pub = (datetime.datetime.fromtimestamp(int(pub_ts), CN_TZ).strftime("%Y-%m-%d")
           if pub_ts else "")
    ctype = CN.get(meta.get("content_type"), meta.get("content_type", ""))
    dyn = str(meta.get("id", ""))
    opus = f"https://www.bilibili.com/opus/{dyn}"

    # 主题：取第一段非空文字前 14 字，否则用类型
    topic = ""
    for k in sorted(figs):
        if figs[k]:
            topic = re.sub(r"[：:].*$", "", figs[k][0])[:14]; break
    title = f"{pub}｜{ctype}" + (f"｜{topic}" if topic else "")

    x = [f"<title>{esc(title)}</title>"]
    x.append(
        f'<callout emoji="📌" background-color="light-gray">'
        f'<p>作者：宝石学家老许　发布：{pub}　类型：{ctype}　图片：{len(imgs)} 张</p>'
        f'<p>原页：<a href="{opus}">B站图文动态 {dyn}</a>　｜　状态：Vision OCR 机器初稿（draft，未人工校）</p>'
        f'</callout>')
    for i, im in enumerate(imgs, 1):
        fp = (article_dir / "images" / im["file"]).resolve()
        x.append(f"<h2>图 {i}</h2>")
        x.append(f'<img path="@{fp}" caption="图 {i}" width="600"/>')
        lines = figs.get(i, [])
        if lines:
            for ln in lines:
                x.append(f"<p>{esc(ln)}</p>")
        else:
            x.append('<p><span text-color="gray">（纯实物图 / 设计稿，画面无文字，信息在图本身）</span></p>')
    x.append("<hr/>")
    x.append('<p><span text-color="gray">本地源头：gemology-kb/library/06_articles；由 scripts/feishu/article_to_xml.py 渲染，飞书为发布层、本地为唯一源。</span></p>')
    return "\n".join(x) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("article_dir")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    xml = build(Path(a.article_dir))
    if a.out:
        Path(a.out).write_text(xml, encoding="utf-8")
        print(f"写出 {a.out}（{len(xml)} 字符）")
    else:
        print(xml)


if __name__ == "__main__":
    main()
