#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按详情接口取每个合集/系列的全部 bvid，建立完整 bvid->合集名 映射。"""
import importlib.util, json, urllib.parse


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


cdpm = load("cdp_client", "cdp_client.py"); bl = load("bili_list", "bili_list.py")
FETCH = r"""
(async () => {
  const r = await fetch(%s, {credentials:'include', headers:{'Accept':'application/json'}});
  const t = await r.text(); try { return JSON.parse(t); } catch(e){ return {_status:r.status,_text:t.slice(0,150)}; }
})()
"""


def fj(sid, cdp, path, params, signed):
    q = bl.sign(params, mixin) if signed else urllib.parse.urlencode(params)
    return cdp.eval(sid, FETCH % json.dumps("https://api.bilibili.com" + path + "?" + q),
                    await_promise=True, timeout=30)


def pick_archives(d):
    if not isinstance(d, dict): return []
    for k in ("archives",):
        if isinstance(d.get(k), list): return d[k]
    li = d.get("list")
    if isinstance(li, dict) and isinstance(li.get("archives"), list): return li["archives"]
    if isinstance(d.get("archives_list"), list): return d["archives_list"]
    return []


cdp = cdpm.CDP()
try:
    t = cdpm.find_space_page(cdp, bl.UID); sid = cdp.attach(t["targetId"])
    mixin = bl.get_mixin()
    groups = json.load(open("up_seasons.json"))
    bmap, multi = {}, {}
    for g in groups:
        kind, gid, name, total = g["kind"], g["id"], g["name"], g["meta_total"]
        arcs, used = [], None
        if kind == "season":
            cands = [("/x/polymer/web-space/seasons_archives_list",
                      {"mid": bl.UID, "season_id": gid, "page_num": 1, "page_size": 100,
                       "sort_reverse": "false"}, True)]
        else:
            cands = [("/x/polymer/web-space/series/archives",
                      {"mid": bl.UID, "series_id": gid, "page_num": 1, "page_size": 100}, True),
                     ("/x/series/archives",
                      {"mid": bl.UID, "series_id": gid, "only_normal": "true", "sort": "desc",
                       "pn": 1, "ps": 100}, False)]
        for path, params, signed in cands:
            j = fj(sid, cdp, path, params, signed)
            arcs = pick_archives(j.get("data")) if j.get("code") == 0 else []
            if arcs:
                used = path.lstrip("/").split("/")[-1]; break
            else:
                print(f"  尝试 {path.split('/')[-1]} code={j.get('code')} msg={j.get('message')}")
        for a in arcs:
            bv = a.get("bvid")
            if not bv: continue
            if bv in bmap and bmap[bv] != name:
                multi.setdefault(bv, [bmap[bv]]).append(name)
            else:
                bmap[bv] = name
        ok = "OK" if len(arcs) >= (total or 0) else "不足"
        print(f"[{kind}] {name}: 取得{len(arcs)}/{total} [{ok}] via {used}")
    json.dump(bmap, open("season_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({k: v for k, v in multi.items()}, open("season_multi.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    allv = {x["bvid"] for x in json.load(open("up_videos_login.json"))["videos"]}
    covered = len(set(bmap) & allv)
    print(f"\n完整映射 bvid={len(set(bmap))}，命中743清单 {covered}（{covered/743*100:.1f}%）；"
          f"跨合集重复 {len(multi)}")
finally:
    cdp.ws.close()
