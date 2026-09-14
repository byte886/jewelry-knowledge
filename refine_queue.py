#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精修队列：给 743 篇 draft 按"信息密度/视频类型"分档，便于分批语义精修、断点续做。
- full  : 知识/原理/选购/避坑/鉴定/价格方法论 -> 完整精修（样板结构）
- lite  : 时效行情、上新带货、招生游学、活动预告 -> 轻量精修（一句话+几条要点）
- story : 文化/历史/起源/故事/盘点叙事 -> 中等摘要
- done  : 对应 bvid.md 已 status: stable/deprecated（跳过，不重复精修）
输出 library/00_manifest/refine_queue.json；幂等，可随时重跑刷新进度。
"""
import json, os, re, collections

BASE = os.path.dirname(os.path.abspath(__file__))
MAN = os.path.join(BASE, "library/00_manifest/manifest.json")
KB = os.path.join(BASE, "library/05_knowledge/concepts/videos")
OUT = os.path.join(BASE, "library/00_manifest/refine_queue.json")

LITE = re.compile(r"上新|一口价|备货|招生|研修班|游学|招贤|活动|预告|直播|抽奖|福利|"
                  r"资讯|快报|财富密码|跳水|大跌|涨价|涨幅超|冷清|联名")
STORY = re.compile(r"故事|历史|起源|恒久远|营销|盘点|名钻|皇室|文化|一路开挂|背后")

def tier_of(title):
    if LITE.search(title):
        return "lite"
    if STORY.search(title):
        return "story"
    return "full"

def is_done(cat, bvid):
    p = os.path.join(KB, cat, bvid + ".md")
    if not os.path.exists(p):
        return False
    head = open(p, encoding="utf-8").read()[:800]
    return bool(re.search(r"^status:\s*(stable|deprecated)", head, re.M))

def main():
    d = json.load(open(MAN, encoding="utf-8"))
    vids = d if isinstance(d, list) else d["videos"]
    queue, stat = [], collections.defaultdict(lambda: collections.Counter())
    for x in vids:
        cat, bv, title = x["category"], x["bvid"], x["title"]
        done = is_done(cat, bv)
        tier = "done" if done else tier_of(title)
        stat[cat][tier] += 1
        queue.append({"bvid": bv, "title": title, "category": cat,
                      "duration": x.get("length"), "words": x.get("words"),
                      "tier": tier})
    json.dump(queue, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 总览
    order = sorted(stat)
    print(f"{'分类':<22}{'full':>5}{'lite':>5}{'story':>6}{'done':>5}{'合计':>6}")
    tf = collections.Counter()
    for c in order:
        s = stat[c]; n = sum(s.values())
        tf += s
        print(f"{c:<20}{s['full']:>6}{s['lite']:>5}{s['story']:>6}{s['done']:>5}{n:>6}")
    print("-"*50)
    print(f"{'全部':<20}{tf['full']:>6}{tf['lite']:>5}{tf['story']:>6}{tf['done']:>5}{sum(tf.values()):>6}")
    print("队列已写:", OUT)

if __name__ == "__main__":
    main()
