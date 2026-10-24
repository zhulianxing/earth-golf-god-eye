#!/usr/bin/env python3
"""EARTH GOLF 一体化服务器：静态文件 + 手机挥杆传感器 API（无第三方依赖）"""
import http.server, socketserver, json, socket, os, threading

PORT = 8321
ROOT = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()
_latest_swing = None   # 最近一次挥杆 ShotSpec

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        global _latest_swing
        if self.path == "/api/swing":          # 游戏端轮询：取走并清空
            with _lock:
                s, _latest_swing = _latest_swing, None
            self._json({"swing": s})
        elif self.path == "/api/ip":
            self._json({"ip": lan_ip(), "port": PORT})
        else:
            super().do_GET()

    def do_POST(self):
        global _latest_swing
        if self.path == "/api/swing":          # 手机端上报：挥杆 or 瞄准调整
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                with _lock:
                    if "aimDelta" in d:        # 纯瞄准调整（不挥杆）
                        _latest_swing = {"aimDelta": max(-5, min(5, float(d["aimDelta"])))}
                        self._json({"ok": True, "aimDelta": _latest_swing["aimDelta"]})
                        return
                    cs = max(5, min(60, float(d.get("clubSpeed", 0))))
                    fa = max(-15, min(15, float(d.get("faceAngle", 0))))
                    _latest_swing = {"clubSpeed": round(cs, 1), "faceAngle": round(fa, 1),
                                     "pathAngle": 0, "attackAngle": 2}
                self._json({"ok": True, "clubSpeed": cs})
            except Exception as e:
                self._json({"ok": False, "err": str(e)}, 400)
        else:
            self._json({"ok": False}, 404)

    def log_message(self, fmt, *args):
        pass   # 静音

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print("EARTH GOLF server: http://%s:%d  (手机传感器页: http://%s:%d/sensor.html)" % (lan_ip(), PORT, lan_ip(), PORT))
    httpd.serve_forever()
