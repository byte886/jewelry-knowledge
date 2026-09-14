#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读：定位 Chrome 哪个 Profile 登录过 bilibili（只看 SESSDATA 记录是否存在与过期时间，不读加密值、不联网）。"""
import os, glob, shutil, sqlite3, tempfile, time

BASE = os.path.expanduser("~/Library/Application Support/Google/Chrome")
now_chrome = int(time.time()) * 1_000_000 + 11644473600_000_000  # 转 Chrome 时间基准


def check_profile(pdir):
    cands = [os.path.join(pdir, "Network", "Cookies"), os.path.join(pdir, "Cookies")]
    src = next((c for c in cands if os.path.exists(c)), None)
    if not src: return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    try:
        shutil.copy(src, tmp.name)
        wal = src + "-wal"
        if os.path.exists(wal):
            try: shutil.copy(wal, tmp.name + "-wal")
            except Exception: pass
        con = sqlite3.connect(tmp.name)
        cur = con.cursor()
        cur.execute("SELECT name, host_key, expires_utc, is_httponly FROM cookies "
                    "WHERE host_key LIKE '%bilibili.com%' AND name='SESSDATA'")
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%bilibili.com%'")
        total = cur.fetchone()[0]
        con.close()
        if not rows: return {"sess": 0, "bili_cookies": total}
        name, host, exp, httponly = rows[0]
        alive = exp == 0 or exp > now_chrome
        return {"sess": 1, "host": host, "expired": not alive, "httponly": bool(httponly),
                "bili_cookies": total}
    except Exception as e:
        return {"error": str(e)}
    finally:
        for f in (tmp.name, tmp.name + "-wal"):
            try: os.remove(f)
            except Exception: pass


profiles = [d for d in glob.glob(os.path.join(BASE, "*"))
            if os.path.isdir(d) and (os.path.basename(d) == "Default" or os.path.basename(d).startswith("Profile"))]
if not profiles:
    print("没找到 Chrome Profile 目录:", BASE)
for p in sorted(profiles):
    r = check_profile(p)
    print(os.path.basename(p), "->", r)
