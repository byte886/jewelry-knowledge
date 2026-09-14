#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
零依赖最小 Chrome DevTools Protocol 客户端（仅连本机 127.0.0.1 调试端口）。
新版 Chrome 关闭了 /json/* HTTP 端点，只保留 DevToolsActivePort 里的 /devtools/browser/<id> WebSocket。
用法：
  python3 cdp_client.py targets   # 列出所有 page 标签
  python3 cdp_client.py probe     # 找到目标 UP 空间页，探测是否登录B站（不输出 cookie 明文）
"""
import socket, os, json, base64, struct, random, sys, time

CHROME_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome")


def read_browser_ws():
    # 允许直接指定 ws://127.0.0.1:<port>/devtools/browser/<id>（独立实例）
    ws = os.environ.get("CHROME_DEV_WS")
    if ws:
        from urllib.parse import urlparse
        u = urlparse(ws)
        return u.port, u.path
    # 允许通过环境变量指定其它 Chrome 实例（独立 --user-data-dir）的 DevToolsActivePort
    p = os.environ.get("CHROME_DEV_PORTFILE") or os.path.join(CHROME_DIR, "DevToolsActivePort")
    lines = open(p).read().splitlines()
    port, path = lines[0].strip(), lines[1].strip()
    return int(port), path


class WS:
    def __init__(self, port, path, retries=4):
        last = None
        for attempt in range(retries):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
                key = base64.b64encode(os.urandom(16)).decode()
                req = (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                       "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                       f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
                self.s.sendall(req.encode())
                buf = b""
                while b"\r\n\r\n" not in buf:
                    buf += self.s.recv(4096)
                if b"101" not in buf.split(b"\r\n", 1)[0]:
                    raise RuntimeError("WS 握手失败: " + buf.decode(errors="ignore")[:120])
                self.buf = b""
                return
            except Exception as e:
                last = e
                try: self.s.close()
                except Exception: pass
                time.sleep(2.0)
        raise RuntimeError(f"WS 连接重试{retries}次仍失败: {last}")

    def _recv_frame(self):
        def rd(n):
            while len(self.buf) < n:
                chunk = self.s.recv(65536)
                if not chunk: raise RuntimeError("连接关闭")
                self.buf += chunk
            out, self.buf = self.buf[:n], self.buf[n:]
            return out
        b0, b1 = rd(2)
        fin, op = b0 & 0x80, b0 & 0x0F
        ln = b1 & 0x7F
        if ln == 126: ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127: ln = struct.unpack(">Q", rd(8))[0]
        payload = rd(ln) if ln else b""
        if op == 9:  # ping -> pong
            self._send_frame(10, payload); return self._recv_frame()
        if op == 8: raise RuntimeError("WS close")
        return payload

    def _send_frame(self, op, payload: bytes):
        mk = os.urandom(4)
        masked = bytes(b ^ mk[i % 4] for i, b in enumerate(payload))
        n = len(payload)
        if n < 126: head = struct.pack(">BB", 0x80 | op, 0x80 | n)
        elif n < 65536: head = struct.pack(">BBH", 0x80 | op, 0x80 | 126, n)
        else: head = struct.pack(">BBQ", 0x80 | op, 0x80 | 127, n)
        self.s.sendall(head + mk + masked)

    def send(self, obj): self._send_frame(1, json.dumps(obj).encode())

    def recv_msg(self):
        data = b""
        while True:
            p = self._recv_frame()
            data += p
            # 简化：CDP 单条消息一般单帧；首字节 fin 在 _recv_frame 已剥，这里直接尝试解析
            try:
                return json.loads(data.decode())
            except Exception:
                continue

    def close(self):
        try:
            self._send_frame(8, b"")  # 发 close 帧
            self.s.settimeout(3)
            for _ in range(6):        # 等对端回 close，完成关闭握手
                try: self._recv_frame()
                except Exception: break
        except Exception:
            pass
        finally:
            try: self.s.close()
            except Exception: pass


class CDP:
    def __init__(self):
        port, path = read_browser_ws()
        self.ws = WS(port, path); self.i = 0

    def call(self, method, params=None, session_id=None, timeout=30):
        self.i += 1; mid = self.i
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id: msg["sessionId"] = session_id
        self.ws.send(msg)
        end = time.time() + timeout
        while time.time() < end:
            m = self.ws.recv_msg()
            if m.get("id") == mid:
                if "error" in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
        raise TimeoutError(method)

    def targets(self):
        r = self.call("Target.getTargets")
        return [t for t in r.get("targetInfos", []) if t.get("type") == "page"]

    def attach(self, target_id):
        r = self.call("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        return r["sessionId"]

    def eval(self, sid, expr, await_promise=False, timeout=60):
        r = self.call("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True,
                       "awaitPromise": await_promise, "timeout": timeout * 1000},
                      session_id=sid, timeout=timeout + 5)
        res = r.get("result", {})
        if "exceptionDetails" in r:
            raise RuntimeError("JS异常: " + json.dumps(r["exceptionDetails"], ensure_ascii=False)[:300])
        return res.get("value")


def find_space_page(cdp, uid="1841256325"):
    for t in cdp.targets():
        if f"space.bilibili.com/{uid}" in t.get("url", ""):
            return t
    return None


PROBE_EXPR = r"""
(async () => {
  const ck = document.cookie;
  const hasSess = /SESSDATA=([^;]+)/.test(ck);
  let isLogin = null, uname = null, mid = null;
  try {
    const r = await fetch('https://api.bilibili.com/x/web-interface/nav', {credentials:'include'});
    const j = await r.json();
    isLogin = !!(j && j.data && j.data.isLogin);
    uname = isLogin ? j.data.uname : null;
    mid = isLogin ? j.data.mid : null;
  } catch(e) { isLogin = 'nav请求失败:'+e; }
  return {href: location.href, cookieHasSESSDATA: hasSess, navIsLogin: isLogin, uname, mid};
})()
"""


if __name__ == "__main__":
    cdp = CDP()
    mode = sys.argv[1] if len(sys.argv) > 1 else "targets"
    if mode == "targets":
        ts = cdp.targets()
        print("page 标签数:", len(ts))
        for t in ts:
            print("-", t.get("title", "")[:40], "|", t.get("url", "")[:90])
    elif mode in ("probe", "open"):
        uid = "1841256325"
        t = find_space_page(cdp, uid)
        if mode == "open" and not t:
            r = cdp.call("Target.createTarget", {"url": f"https://space.bilibili.com/{uid}/dynamic"})
            print("已在调试实例新开空间页 tab:", r.get("targetId")); time.sleep(7)
            t = find_space_page(cdp, uid)
        if not t:
            print("未找到空间页标签"); sys.exit(2)
        print("空间页:", t.get("title"), "|", t.get("url"))
        sid = cdp.attach(t["targetId"])
        print("当前 href:", cdp.eval(sid, "location.href", timeout=15))
        print(json.dumps(cdp.eval(sid, PROBE_EXPR, await_promise=True, timeout=30),
                         ensure_ascii=False, indent=2))
    cdp.ws.close()
