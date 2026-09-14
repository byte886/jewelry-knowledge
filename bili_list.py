#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站 UP 投稿/合集 慢速列取（防风控加强版，纯 urllib 直连）。
通道 A（首选）: finger/spi 取 buvid3/4 设备指纹 + 首页 + nav 取 wbi key，
              wbi 签名慢速翻 x/space/wbi/arc/search（ps=50）。
通道 B（备用）: x/polymer/web-dynamic/v1/feed/space 动态流 offset 递归（免登录、不易被封）。
用法:
  python3 bili_list.py wbi --max-pages 1      # 最小验证一页
  python3 bili_list.py wbi                     # 拉全量+合集
  python3 bili_list.py dynamic                 # 动态流通道
"""
import argparse, hashlib, json, random, sys, time, urllib.parse, urllib.request, http.cookiejar

UID = "1841256325"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
MIXIN_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,
             14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,
             56,59,6,63,57,62,11,36,20,34,44,52]

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                 urllib.request.HTTPCookieProcessor(cj))
MANUAL_COOKIE = {}

def _cookie_header():
    parts = [f"{k}={v}" for k, v in MANUAL_COOKIE.items()]
    for c in cj:
        if c.name not in MANUAL_COOKIE:
            parts.append(f"{c.name}={c.value}")
    return "; ".join(parts)

def get(url, referer=None, origin=False):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer: h["Referer"] = referer
    if origin: h["Origin"] = "https://www.bilibili.com"
    ck = _cookie_header()
    if ck: h["Cookie"] = ck
    req = urllib.request.Request(url, headers=h)
    with op.open(req, timeout=20) as r:
        return json.loads(r.read().decode())

def warmup():
    # 1) 设备指纹接口拿 buvid3/4（比单纯访问首页更可靠）
    try:
        d = get("https://api.bilibili.com/x/frontend/finger/spi",
                referer="https://www.bilibili.com/", origin=True)
        data = d.get("data", {})
        if data.get("b_3"): MANUAL_COOKIE["buvid3"] = data["b_3"]
        if data.get("b_4"): MANUAL_COOKIE["buvid4"] = data["b_4"]
        MANUAL_COOKIE["b_nut"] = str(int(time.time()))
        print("[warm] finger/spi buvid3=", (MANUAL_COOKIE.get("buvid3") or "")[:18], "...")
    except Exception as e:
        print("[warm] finger/spi 失败:", e)
    # 2) 访问首页补全 cookie（首页是 HTML，只让 cookiejar 收 Set-Cookie，不解析）
    try:
        req = urllib.request.Request("https://www.bilibili.com/",
                                     headers={"User-Agent": UA})
        with op.open(req, timeout=20) as r:
            r.read(200)
    except Exception as e:
        print("[warm] 首页异常:", e)
    print("[warm] cookies:", sorted(set(list(MANUAL_COOKIE) + [c.name for c in cj])))

def get_mixin():
    d = get("https://api.bilibili.com/x/web-interface/nav",
            referer=f"https://space.bilibili.com/{UID}", origin=True)
    if d.get("code") != 0:
        print("[nav] code=", d.get("code"), d.get("message"))
    wbi = d["data"]["wbi_img"]
    img = wbi["img_url"].rsplit("/", 1)[1].split(".")[0]
    sub = wbi["sub_url"].rsplit("/", 1)[1].split(".")[0]
    raw = img + sub
    return "".join(raw[i] for i in MIXIN_TAB)[:32]

def sign(params, mixin):
    p = {k: str(v) for k, v in params.items()}
    p["wts"] = int(time.time())
    q = urllib.parse.urlencode(sorted(p.items()))
    p["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return urllib.parse.urlencode(sorted(p.items()))

def list_wbi(mixin, max_pages=None, sleep=(4.0, 7.0)):
    out, pn = [], 1
    while True:
        q = sign({"mid": UID, "ps": 50, "pn": pn, "order": "pubdate",
                  "platform": "web", "web_location": "155010", "order_avoided": "true"}, mixin)
        url = "https://api.bilibili.com/x/space/wbi/arc/search?" + q
        d = get(url, referer=f"https://space.bilibili.com/{UID}/video", origin=True)
        code = d.get("code")
        if code != 0:
            print(f"[page {pn}] code={code} msg={d.get('message')} -> 停止（可能触发风控，需冷却）")
            return out, False
        vlist = d["data"]["list"]["vlist"]; page = d["data"]["page"]
        for v in vlist:
            out.append({"bvid": v.get("bvid"), "title": v.get("title"),
                        "created": v.get("created"), "length": v.get("length"),
                        "play": v.get("play"), "typeid": v.get("typeid"),
                        "tid_name": None,
                        "url": f"https://www.bilibili.com/video/{v.get('bvid')}"})
        print(f"[page {pn}] {len(vlist)} 条，累计 {len(out)}/{page.get('count')}")
        if len(out) >= page.get("count", 0) or not vlist:
            return out, True
        if max_pages and pn >= max_pages:
            return out, True
        time.sleep(random.uniform(*sleep)); pn += 1

def list_dynamic(max_pages=None, sleep=(5.0, 8.0), mixin=None,
                 ckpt="up_dyn_checkpoint.json", resume=True):
    out, offset, pn, seen = [], "", 1, set()
    if resume:  # 断点续拉：载入上次进度，按 bvid 去重
        try:
            old = json.load(open(ckpt, encoding="utf-8"))
            offset = old.get("next_offset") or ""
            for x in old.get("videos", []):
                if x.get("bvid") and x["bvid"] not in seen:
                    seen.add(x["bvid"]); out.append(x)
            print(f"[resume] 已有 {len(out)} 个视频，从 offset={offset[:16]} 续拉")
        except FileNotFoundError:
            pass
    def save(nxt, has_more):
        json.dump({"next_offset": nxt, "has_more": has_more, "videos": out},
                  open(ckpt, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def fetch_once(off):
        params = {"host_mid": UID, "offset": off, "timezone_offset": -480,
                  "platform": "web",
                  "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,decorationCard,forwardListHidden,ugcDelete,onlyfansQaCard"}
        if off:
            # 仅翻页(offset非空)需要浏览器风控指纹参数；首页(offset空)带了反而返回空（2026-09 实测）
            params.update({"web_location": "333.999", "dm_img_list": "[]",
                           "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
                           "dm_cover_img_str": "Q2hyb21lV0VPUiBHTEMgTWV0YWxHbHVlIChJbnRlbCkp",
                           "dm_img_inter": '{"intersection":0,"src":0,"src_request":0}'})
        q = sign(params, mixin) if mixin else urllib.parse.urlencode(params)
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?" + q
        return get(url, referer=f"https://space.bilibili.com/{UID}/dynamic", origin=True)

    while True:
        d = None
        for attempt in range(3):  # 同一游标有界重试：应对瞬时软限流（code=0 却空 items）
            try:
                d = fetch_once(offset)
            except Exception as e:
                print(f"[dyn {pn}] 第{attempt+1}次请求异常 {e}"); d = None
            good = isinstance(d, dict) and d.get("code") == 0
            n_items = len(d.get("data", {}).get("items", [])) if good else -1
            if good and n_items > 0:
                break
            if attempt < 2:
                w = 10 + attempt * 8
                code = None if not isinstance(d, dict) else d.get("code")
                print(f"[dyn {pn}] 第{attempt+1}次空/异常(code={code},items={n_items})，{w}s 后重试同一游标")
                time.sleep(w)
        if not (isinstance(d, dict) and d.get("code") == 0):
            print(f"[dyn {pn}] 重试后仍失败 -> 保留断点，冷却后续拉"); save(offset, True); break
        data = d["data"]
        if not data.get("items"):
            if pn == 1 and not out:
                print("[dyn] !! 首屏连续空=软限流（非真到底），不覆盖断点，停止待冷却后重跑")
            else:
                print("[dyn] !! 该游标连续空（中途软限流），保留断点，冷却后续拉（按 bvid 去重）"); save(offset, True)
            break
        added = 0
        for it in data.get("items", []):
            if it.get("type") in ("DYNAMIC_TYPE_AV", "DYNAMIC_TYPE_VIDEO"):
                arc = (((it.get("modules") or {}).get("module_dynamic") or {})
                       .get("major") or {}).get("archive")
                if arc and arc.get("bvid") not in seen:
                    seen.add(arc["bvid"]); added += 1
                    out.append({"bvid": arc.get("bvid"), "title": arc.get("title"),
                                "length": arc.get("duration_text"), "desc": arc.get("desc"),
                                "url": f"https://www.bilibili.com/video/{arc.get('bvid')}"})
        nxt = data.get("offset"); more = bool(data.get("has_more"))
        save(nxt, more)
        print(f"[dyn {pn}] items={len(data.get('items', []))} 新增{added} 累计视频{len(out)} more={more}")
        if not more or not nxt:
            print("[dyn] 到达动态流底部，全量完成"); break
        offset = nxt
        if max_pages and pn >= max_pages: break
        time.sleep(random.uniform(6.0, 10.0)); pn += 1
    return out

def list_seasons(mixin, sleep=(3.0, 5.0)):
    res, pn = [], 1
    while True:
        q = sign({"mid": UID, "page_num": pn, "page_size": 20}, mixin)
        url = "https://api.bilibili.com/x/polymer/web-space/seasons_series_list?" + q
        d = get(url, referer=f"https://space.bilibili.com/{UID}/lists/series", origin=True)
        if d.get("code") != 0:
            print("[season] code=", d.get("code"), d.get("message")); break
        data = d.get("data", {})
        seas = data.get("items_lists_seasons") or []
        sers = data.get("items_lists_series") or []
        if not seas and not sers: break
        for it in seas:
            m = it.get("meta", {})
            res.append({"id": m.get("season_id"), "type": "season", "name": m.get("name"),
                        "total": m.get("total"), "desc": m.get("description")})
        for it in sers:
            m = it.get("meta", {})
            res.append({"id": m.get("series_id"), "type": "series", "name": m.get("name"),
                        "total": m.get("total"), "desc": m.get("description")})
        if len(seas) < 20 and len(sers) < 20: break
        pn += 1; time.sleep(random.uniform(*sleep))
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["wbi", "dynamic"], nargs="?", default="wbi")
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args()
    warmup(); time.sleep(1.2)
    if a.mode == "dynamic":
        mixin = get_mixin(); print("[wbi] mixin =", mixin)
        time.sleep(random.uniform(1.2, 2.0))
        v = list_dynamic(a.max_pages, mixin=mixin)
        json.dump(v, open("up_videos_dynamic.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("动态流累计视频:", len(v)); sys.exit()
    mixin = get_mixin(); print("[wbi] mixin =", mixin)
    time.sleep(random.uniform(1.5, 2.5))
    vids, ok = list_wbi(mixin, a.max_pages)
    json.dump(vids, open("up_videos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("投稿累计:", len(vids), "| 完整拉取:" , ok)
    if ok and not a.max_pages:
        time.sleep(random.uniform(2, 4))
        seas = list_seasons(mixin)
        json.dump(seas, open("up_seasons.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("合集/系列数:", len(seas))
        for s in seas: print(f"  · [{s['type']}] {s['total']}  {s['name']}")
