#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2-0 图文存量探测②：UP 动态流类型分布（只读、只拉首页1屏，防风控）。
- 传统专栏 x/space/article 实测仅 1 篇；B站"图文"主要是动态里的 DRAW/opus。
- 本脚本拉 feed/space 首页，统计各 DYNAMIC_TYPE_* 数量，打印非视频类型样例与图片数，
  据此判断图文线工作量，不做全量翻页。
"""
import json, time, urllib.parse, importlib.util, collections


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bl = load("bili_list", "bili_list.py")
bl.warmup(); time.sleep(1.2)
mixin = bl.get_mixin(); time.sleep(1.2)

params = {"host_mid": bl.UID, "offset": "", "timezone_offset": -480, "platform": "web",
          "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote"}
url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?" + bl.sign(params, mixin)
d = bl.get(url, referer=f"https://space.bilibili.com/{bl.UID}/dynamic", origin=True)
print("code =", d.get("code"), d.get("message"))
if d.get("code") != 0:
    print(json.dumps(d, ensure_ascii=False)[:400]); raise SystemExit

data = d["data"]; items = data.get("items", [])
print(f"本屏动态 {len(items)} 条，has_more={data.get('has_more')}\n")

cnt = collections.Counter(it.get("type") for it in items)
print("=== 类型分布（本屏样本）===")
for t, n in cnt.most_common():
    print(f"  {n:>2}  {t}")

print("\n=== 非视频(AV)动态样例 ===")
shown = 0
for it in items:
    t = it.get("type")
    if t == "DYNAMIC_TYPE_AV":
        continue
    md = (it.get("modules") or {}).get("module_dynamic") or {}
    major = md.get("major") or {}
    desc = ((md.get("desc") or {}).get("text") or "").strip().replace("\n", " ")
    npic = 0; kind = list(major.keys())[0] if major else "none"
    draw = major.get("draw")
    if draw: npic = draw.get("count") or len(draw.get("items") or [])
    opus = major.get("opus")
    if opus: npic = len(opus.get("pics") or []) or npic
    print(f"- {t} major={kind} 图{npic} id={it.get('id_str')} | {desc[:40]}")
    shown += 1
    if shown >= 15: break
