#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2-0b 登录态全量盘点 UP 动态类型（只统计、不下载正文，防风控）。
- 在已登录小号 Chrome 的空间页上下文里 fetch feed/space（浏览器自动带 SESSDATA/bili_ticket）；
- 慢速翻页（4-7s/页，每6页多停一会），实时落盘断点，撞限流立即停；
- 统计各 DYNAMIC_TYPE_*，重点抽取图文 DRAW/ARTICLE(opus) 的 id/时间/图数/摘要，
  以及 AV 的 bvid（用于和已采743视频交叉核对）。
连接：环境变量 CHROME_DEV_WS=ws://127.0.0.1:9223/devtools/browser/<id>
"""
import importlib.util, json, random, sys, time, urllib.parse, collections


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


cdpm = load("cdp_client", "cdp_client.py")
UID = "1841256325"
OUT = "library/00_manifest/articles_dynamic_scan.json"

FETCH_JS = r"""
(async () => {
  const r = await fetch(%s, {credentials:'include', headers:{'Accept':'application/json,text/plain,*/*'}});
  const t = await r.text(); let j=null; try{j=JSON.parse(t);}catch(e){j=null;}
  return {status:r.status, json:j, text:j?null:t.slice(0,160)};
})()
"""

DM = {"web_location": "333.999", "dm_img_list": "[]",
      "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
      "dm_cover_img_str": "Q2hyb21lV0VPUiBHTEMgTWV0YWxHbHVlIChJbnRlbCkp",
      "dm_img_inter": '{"intersection":0,"src":0,"src_request":0}'}


def page_get(sid, cdp, url):
    return cdp.eval(sid, FETCH_JS % json.dumps(url), await_promise=True, timeout=30)


def pic_count(major):
    if not isinstance(major, dict): return 0, None
    d = major.get("draw")
    if isinstance(d, dict):
        return (d.get("count") or len(d.get("items") or [])), "draw"
    op = major.get("opus")
    if isinstance(op, dict):
        return len(op.get("pics") or []), "opus"
    art = major.get("article")
    if isinstance(art, dict):
        return len(art.get("image_urls") or []), "article"
    return 0, (list(major.keys())[0] if major else None)


def main():
    cdp = cdpm.CDP()
    try:
        t = cdpm.find_space_page(cdp, UID)
        if not t:
            sys.exit("未找到空间动态页标签")
        sid = cdp.attach(t["targetId"])

        recs, seen, offset, pn = [], set(), "", 1
        type_cnt = collections.Counter()
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            if old.get("next_offset"):
                offset = old["next_offset"]; pn = old.get("next_page", 1)
                for r in old.get("items", []):
                    if r.get("id") not in seen: seen.add(r["id"]); recs.append(r)
                type_cnt.update(r["type"] for r in recs)
                print(f"[resume] 续上断点，已有 {len(recs)} 条，offset={offset[:14]}")
        except FileNotFoundError:
            pass

        empty_streak = 0
        draw_gap = 0
        STOP_GAP = 20  # 连续 N 页无图文则判定已早于图文起点，提前停止（登录态实测接口宽松，阈值放宽防早期稀疏误停）
        while True:
            params = {"host_mid": UID, "offset": offset, "timezone_offset": -480,
                      "platform": "web",
                      "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote"}
            if offset: params.update(DM)
            url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?" + \
                  urllib.parse.urlencode(params)
            r = page_get(sid, cdp, url)
            j = (r or {}).get("json")
            code = j.get("code") if j else None
            if not j or code not in (0,):
                print(f"[p{pn}] 异常 status={r and r.get('status')} code={code} "
                      f"msg={j and j.get('message')} text={r and r.get('text')} → 立即停手保断点")
                break
            data = j["data"]; items = data.get("items", [])
            if not items:
                empty_streak += 1
                if empty_streak >= 2:
                    print("[p%d] 连续空页=软限流/到底，停手保断点" % pn); break
                time.sleep(8); continue
            empty_streak = 0
            added = 0
            draw_added = 0
            for it in items:
                iid = it.get("id_str")
                if not iid or iid in seen: continue
                seen.add(iid); added += 1; typ = it.get("type"); type_cnt[typ] += 1
                mods = it.get("modules") or {}
                au = mods.get("module_author") or {}
                md = mods.get("module_dynamic") or {}
                major = md.get("major") or {}
                npic, kind = pic_count(major)
                bvid = ((major.get("archive") or {}).get("bvid")) if isinstance(major, dict) else None
                desc = ((md.get("desc") or {}).get("text") or "").strip().replace("\n", " ")
                title = None
                if isinstance(major, dict):
                    title = ((major.get("archive") or {}).get("title")
                             or (major.get("opus") or {}).get("title")
                             or (major.get("draw") or {}).get("title"))
                recs.append({"id": iid, "type": typ, "major": kind, "bvid": bvid,
                             "pics": npic, "pub_ts": au.get("pub_ts"),
                             "pub_time": au.get("pub_time"), "title": title,
                             "desc": desc[:120]})
                if "DRAW" in typ or "ARTICLE" in typ:
                    draw_added += 1
            nxt, more = data.get("offset"), bool(data.get("has_more"))
            json.dump({"next_offset": nxt, "next_page": pn + 1, "has_more": more,
                       "type_count": dict(type_cnt), "items": recs},
                      open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[p{pn}] items={len(items)} 新增{added} 累计{len(recs)} more={more} "
                  f"| 图文DRAW/ART={sum(v for k,v in type_cnt.items() if 'DRAW' in k or 'ARTICLE' in k)}",
                  flush=True)
            if not more or not nxt:
                print("has_more=false，到达动态流底部，全量盘点完成"); break
            if draw_added:
                draw_gap = 0
            else:
                draw_gap += 1
                if draw_gap >= STOP_GAP:
                    print(f"[p{pn}] 连续{STOP_GAP}页无图文，判定已早于图文起点，提前停止（更早动态不再翻）")
                    break
            offset = nxt; pn += 1
            gap = random.uniform(2.0, 3.5)  # 已连续342页零风控，登录态只读较宽松，适度提速
            if pn % 8 == 0: gap += random.uniform(2.0, 4.0)  # 每8页多歇一会
            time.sleep(gap)

        # 汇总
        img = [r for r in recs if "DRAW" in r["type"] or "ARTICLE" in r["type"]]
        av = [r for r in recs if r["type"] == "DYNAMIC_TYPE_AV"]
        print("\n===== 盘点汇总 =====")
        for k, v in type_cnt.most_common(): print(f"  {v:>4}  {k}")
        print(f"动态总计 {len(recs)}；视频AV {len(av)}；图文(DRAW/ARTICLE) {len(img)}")
        tot_pic = sum(r['pics'] for r in img)
        print(f"图文内嵌图合计 {tot_pic}，平均 {tot_pic/len(img):.1f}/条" if img else "图文0条")
    finally:
        cdp.ws.close()


if __name__ == "__main__":
    main()
