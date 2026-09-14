#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录态列取（用户已在独立 Chrome 小号登录）：
- wbi 签名由 Python 完成（mixin key 全局、与账号无关，本地匿名 nav 即可取）；
- 数据请求在【已登录页面上下文】里 fetch，浏览器自动携带 SESSDATA(HttpOnly)+bili_ticket；
- ps=50，742 条约 15 页；温和间隔、实时落盘。另拉官方合集/系列。
用法：python3 login_list.py [--max-pages N] [--ps 50]
"""
import importlib.util, json, random, sys, time, argparse


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


cdpm = load("cdp_client", "cdp_client.py")
bl = load("bili_list", "bili_list.py")

FETCH_JS = r"""
(async () => {
  const r = await fetch(%s, {credentials:'include', headers:{'Accept':'application/json,text/plain,*/*'}});
  const t = await r.text();
  let j = null; try { j = JSON.parse(t); } catch(e) { j = null; }
  return {status:r.status, json:j, text:j?null:t.slice(0,200)};
})()
"""


def page_get(sid, cdp, url):
    js = FETCH_JS % json.dumps(url)
    return cdp.eval(sid, js, await_promise=True, timeout=30)


def signed_url(mixin, params):
    return "https://api.bilibili.com/x/space/wbi/arc/search?" + bl.sign(params, mixin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--ps", type=int, default=50)
    a = ap.parse_args()

    cdp = cdpm.CDP()
    try:
        t = cdpm.find_space_page(cdp, bl.UID)
        if not t: sys.exit("独立实例里没有空间页，请先在该 Chrome 打开投稿页并确认已登录")
        sid = cdp.attach(t["targetId"])

        print("取 wbi mixin key（本地匿名，账号无关）...")
        mixin = bl.get_mixin(); print("mixin =", mixin)
        time.sleep(1)

        out, pn = [], 1
        count = None
        while True:
            url = signed_url(mixin, {"mid": bl.UID, "ps": a.ps, "pn": pn, "order": "pubdate",
                                     "platform": "web", "web_location": "155010",
                                     "order_avoided": "true"})
            r = page_get(sid, cdp, url)
            j = (r or {}).get("json")
            if not j or j.get("code") != 0:
                print(f"[page {pn}] 失败 status={r and r.get('status')} "
                      f"code={j and j.get('code')} msg={j and j.get('message')} text={r and r.get('text')}")
                print("!! 停止，已得部分已存盘"); break
            data = j["data"]; vlist = data["list"]["vlist"]; page = data["page"]
            count = page.get("count")
            for v in vlist:
                out.append({"bvid": v.get("bvid"), "title": v.get("title"),
                            "created": v.get("created"), "length": v.get("length"),
                            "play": v.get("play"), "comment": v.get("comment"),
                            "typeid": v.get("typeid"), "typename": v.get("typename"),
                            "url": f"https://www.bilibili.com/video/{v.get('bvid')}"})
            print(f"[page {pn}] {len(vlist)} 条，累计 {len(out)}/{count}", flush=True)
            json.dump({"count": count, "total": len(out), "videos": out},
                      open("up_videos_login.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            if count and len(out) >= count: print("到达 count，全量完成"); break
            if not vlist: print("本页空，结束"); break
            if a.max_pages and pn >= a.max_pages: print("到达 --max-pages，小测停"); break
            time.sleep(random.uniform(2.5, 5.0)); pn += 1

        # 官方合集/系列（分类首选）
        if not a.max_pages:
            time.sleep(2)
            surl = "https://api.bilibili.com/x/polymer/web-space/seasons_series_list?" + \
                   bl.sign({"mid": bl.UID, "page_num": 1, "page_size": 20}, mixin)
            sr = page_get(sid, cdp, surl); sj = sr.get("json")
            seasons = []
            if sj and sj.get("code") == 0:
                dd = sj.get("data", {})
                for it in (dd.get("items_lists_seasons") or []):
                    m = it.get("meta", {}); seasons.append({"kind": "season", "id": m.get("season_id"),
                                                            "name": m.get("name"), "total": m.get("total")})
                for it in (dd.get("items_lists_series") or []):
                    m = it.get("meta", {}); seasons.append({"kind": "series", "id": m.get("series_id"),
                                                            "name": m.get("name"), "total": m.get("total")})
                json.dump(seasons, open("up_seasons.json", "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                print(f"合集/系列 {len(seasons)} 个 -> up_seasons.json")
                for s in seasons: print(f"  · [{s['kind']}] {s['total']:>4}  {s['name']}")
            else:
                print("合集接口 code=", sj and sj.get("code"), sj and sj.get("message"))
        print(f"\n最终投稿 {len(out)} / 官方count={count} -> up_videos_login.json")
    finally:
        cdp.ws.close()


if __name__ == "__main__":
    main()
