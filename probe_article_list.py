#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2-0 图文专栏存量探测（只读、单次、防风控）：
- 复用 bili_list 的纯 urllib 直连/设备指纹 warmup；
- 只请求 UP 专栏列表第 1 页，不翻页；
- 打印 code/count、本页字段结构、前若干篇元数据与列表自带的配图数，
  用来判断：游客态能否取图文、总量量级、后续 OCR 工作量。
用法: /usr/bin/python3 probe_article_list.py
"""
import json, time, importlib.util, sys


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bl = load("bili_list", "bili_list.py")

bl.warmup()
time.sleep(1.5)

url = ("https://api.bilibili.com/x/space/article?"
       f"mid={bl.UID}&pn=1&ps=30&sort=publish_time")
print("\n[GET]", url)
d = bl.get(url, referer=f"https://space.bilibili.com/{bl.UID}/article", origin=True)

print("code =", d.get("code"), " message =", d.get("message"))
if d.get("code") != 0:
    print("!! 游客态被拒/异常，原始返回片段：", json.dumps(d, ensure_ascii=False)[:400])
    sys.exit(0)

data = d.get("data", {})
arts = data.get("articles", []) or []
page = {k: data.get(k) for k in ("pn", "ps", "count")}
print("page =", page, " 本页条数 =", len(arts))
if arts:
    print("\n列表项字段 keys =", sorted(arts[0].keys()))
    print("\n前 8 篇：")
    for a in arts[:8]:
        imgs = a.get("image_urls") or a.get("image_url") or []
        print(f"- aid={a.get('id')} 图{len(imgs) if isinstance(imgs, list) else '?'} "
              f"阅{a.get('view')} 评{a.get('reply')} "
              f"{time.strftime('%Y-%m-%d', time.localtime(a.get('publish_time', 0)))}  "
              f"{(a.get('title') or '').strip()[:34]}")
    # 本页配图量分布（仅列表自带缩略图，正文图数需抽正文统计）
    cnts = [len(a.get('image_urls') or []) for a in arts if isinstance(a.get('image_urls'), list)]
    if cnts:
        print(f"\n本页列表自带缩略图：合计{sum(cnts)} 平均{sum(cnts)/len(cnts):.1f} 最多{max(cnts)}")
