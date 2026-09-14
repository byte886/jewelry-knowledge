#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录态取官方合集/系列，正确结构 data.items_lists.seasons_list/series_list；
产出 up_seasons.json（合集元信息）与 season_map.json（bvid -> 合集名，分类首选）。"""
import importlib.util, json


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


cdpm = load("cdp_client", "cdp_client.py"); bl = load("bili_list", "bili_list.py")
FETCH = r"""
(async () => {
  const r = await fetch(%s, {credentials:'include', headers:{'Accept':'application/json'}});
  return await r.json();
})()
"""
cdp = cdpm.CDP()
try:
    t = cdpm.find_space_page(cdp, bl.UID); sid = cdp.attach(t["targetId"])
    mixin = bl.get_mixin()
    url = "https://api.bilibili.com/x/polymer/web-space/seasons_series_list?" + \
          bl.sign({"mid": bl.UID, "page_num": 1, "page_size": 20}, mixin)
    j = cdp.eval(sid, FETCH % json.dumps(url), await_promise=True, timeout=30)
    il = (j.get("data") or {}).get("items_lists") or {}
    seasons, bmap = [], {}
    for grp, kind, idkey in (("seasons_list", "season", "season_id"),
                             ("series_list", "series", "series_id")):
        for it in il.get(grp) or []:
            m = it.get("meta", {}) or {}
            arcs = it.get("archives") or []
            name = m.get("name"); total = m.get("total")
            seasons.append({"kind": kind, "id": m.get(idkey), "name": name,
                            "meta_total": total, "archives_returned": len(arcs)})
            for a in arcs:
                if a.get("bvid"):
                    bmap[a["bvid"]] = name
            flag = "" if len(arcs) >= (total or 0) else "  <-- archives 少于 total，需补拉详情"
            print(f"[{kind}] {name}  meta.total={total} 本次archives={len(arcs)}{flag}")
    json.dump(seasons, open("up_seasons.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(bmap, open("season_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    allv = {x["bvid"] for x in json.load(open("up_videos_login.json"))["videos"]}
    covered = len(set(bmap) & allv)
    print(f"\n合集/系列共 {len(seasons)} 个；映射 bvid {len(set(bmap))} 个；"
          f"命中本UP 743 清单的 {covered} 个（覆盖率 {covered/743*100:.1f}%）")
finally:
    cdp.ws.close()
