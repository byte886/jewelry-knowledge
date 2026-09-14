#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 CDP 从已登录的独立 Chrome 导出 bilibili cookie 为 Netscape 格式（yt-dlp 可用）。
仅本地落盘、chmod 600、只打印 cookie 名，绝不打印 SESSDATA 等凭据值；任务结束可删。"""
import importlib.util, os, time, http.cookiejar  # noqa


def load(n, f):
    s = importlib.util.spec_from_file_location(n, f); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


cdpm = load("cdp_client", "cdp_client.py")
OUT = "secrets/bili.netscape.txt"
os.makedirs("secrets", exist_ok=True)

cdp = cdpm.CDP()
try:
    t = cdpm.find_space_page(cdp, "1841256325"); sid = cdp.attach(t["targetId"])
    r = cdp.call(sid, "Network.getAllCookies", {})
    cookies = (r or {}).get("cookies", [])
    bili = [c for c in cookies if "bilibili.com" in (c.get("domain") or "")]
    lines = ["# Netscape HTTP Cookie File", "# generated for local yt-dlp only, do not share"]
    for c in sorted(bili, key=lambda x: x.get("name", "")):
        dom = c.get("domain", "")
        flag = "TRUE" if dom.startswith(".") else "FALSE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        exp = int(c.get("expires", -1))
        if exp < 0: exp = 0
        lines.append("\t".join([dom, flag, c.get("path", "/"), secure, str(exp),
                                c.get("name", ""), c.get("value", "")]))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    os.chmod(OUT, 0o600)
    names = sorted({c.get("name") for c in bili})
    print(f"bilibili cookie {len(bili)} 枚 -> {OUT}（权限600）")
    print("cookie 名（不显示值）：", ", ".join(names))
    print("含 SESSDATA：", any(c.get("name") == "SESSDATA" and c.get("value") for c in bili))
finally:
    cdp.ws.close()
