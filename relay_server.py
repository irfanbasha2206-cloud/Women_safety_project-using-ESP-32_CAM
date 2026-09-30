"""
Women Safety Project - MJPEG RELAY SERVER
==========================================
THIS is the fix for "stream shown on only ONE device at a time".

Old design (broken):
    Browser 1 ----\
    Browser 2 -----> ESP32-CAM (single-threaded socket server)
    Browser 3 ----/           ^-- can only truly serve ONE client's
                                    infinite streaming loop at once.
    Every new viewer silently knocks the previous one off.

New design (this file):
    ESP32-CAM --(1 outbound TCP push)--> RELAY SERVER --(HTTP MJPEG)--> Browser 1
                                              (this file)  --------------> Browser 2
                                                            --------------> Browser 3
                                                            --------------> ...unlimited

    The ESP32 now only has to maintain ONE connection (to this relay).
    This relay keeps the latest frame in memory and hands a fresh copy
    to every browser that asks - so any number of devices, on any
    network in the world, can watch at the same time.

Run order:
    1. Run THIS file first, on your PC:   python relay_server.py
    2. Flash the updated main.py onto the ESP32-CAM (it pushes frames here).
    3. Run start_cloudflare_tunnel.py pointing at THIS relay (127.0.0.1:8000),
       NOT at the ESP32 anymore. That gives you the global HTTPS URL.

Install once:  pip install flask
"""

import socket
import struct
import threading
import time
from flask import Flask, Response, jsonify

# ---------------- Config ----------------
INGEST_HOST = "0.0.0.0"     # relay listens here for the ESP32-CAM
INGEST_PORT = 9000          # ESP32 connects here over the SAME wifi/hotspot
HTTP_HOST   = "0.0.0.0"     # relay serves browsers here
HTTP_PORT   = 8000          # <-- point cloudflared / the tunnel at THIS port
BOUNDARY    = b"frame"
STALE_FRAME_SECONDS = 5     # no new frame for this long -> treat camera as offline

# UDP auto-discovery: so the ESP32 never needs your laptop's IP hardcoded.
# This laptop shouts "I'm the relay, here's my ingest port" on the LAN
# broadcast address every second; the ESP32 listens for it and connects
# to whoever sent it - works even if your laptop's IP changes between
# demos (as long as it's the SAME hotspot / same LAN as the ESP32-CAM).
DISCOVERY_PORT  = 9001
DISCOVERY_MAGIC = b"WSAFETY_RELAY_V1"

# ---------------- Shared state ----------------
_lock = threading.Lock()
_cond = threading.Condition(_lock)   # notifies waiters on every new frame -
                                      # a Condition (vs the old Event set/clear
                                      # "pulse") can never miss a wakeup, so a
                                      # browser can never get randomly stuck
                                      # for up to 1s waiting on a dropped signal
_latest_frame = None
_last_frame_time = 0.0
_frame_generation = 0   # increments on every new frame; consumers compare
                         # this to know if they've already seen the latest one


def ingest_server():
    """
    Accepts the ESP32-CAM's connection and reads a continuous stream of
    length-prefixed JPEG frames:
        [4 bytes big-endian length][that many bytes of JPEG]  repeat forever
    If the camera drops, we just go back to accept() and wait for it to
    reconnect (the updated main.py auto-reconnects).

    Also prints the ACTUAL incoming fps every 5s - this tells you straight
    away whether the ESP32/wifi side is the bottleneck (low number here)
    or whether frames are arriving fine and the lag is downstream
    (tunnel/browser) instead.
    """
    global _latest_frame, _last_frame_time, _frame_generation
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((INGEST_HOST, INGEST_PORT))
    srv.listen(1)
    print(f"[Ingest] Waiting for ESP32-CAM on {INGEST_HOST}:{INGEST_PORT} ...")

    while True:
        conn, addr = srv.accept()
        print(f"[Ingest] ESP32-CAM connected from {addr}")
        conn.settimeout(15)
        buf = b""
        frames_since_log = 0
        window_start = time.time()
        avg_frame_kb = 0.0
        try:
            while True:
                while len(buf) < 4:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("camera closed the connection")
                    buf += chunk
                (frame_len,) = struct.unpack(">I", buf[:4])
                buf = buf[4:]

                while len(buf) < frame_len:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("camera closed the connection")
                    buf += chunk
                frame, buf = buf[:frame_len], buf[frame_len:]

                with _cond:
                    _latest_frame = frame
                    _last_frame_time = time.time()
                    _frame_generation += 1
                    _cond.notify_all()

                frames_since_log += 1
                avg_frame_kb += len(frame) / 1024
                now = time.time()
                elapsed = now - window_start
                if elapsed >= 5:
                    fps = frames_since_log / elapsed
                    avg_kb = avg_frame_kb / frames_since_log if frames_since_log else 0
                    print(f"[Ingest] ESP32-CAM sending ~{fps:.1f} fps, "
                          f"avg {avg_kb:.1f} KB/frame "
                          f"(~{fps * avg_kb:.0f} KB/s)")
                    frames_since_log = 0
                    avg_frame_kb = 0.0
                    window_start = now
        except Exception as e:
            print(f"[Ingest] ESP32-CAM disconnected: {e}")
        finally:
            conn.close()
        # loop back to srv.accept() and wait for the camera to reconnect


def get_local_ip():
    """
    Best-effort local IP of the interface Windows would use to reach the
    internet - on a laptop tethered to a phone hotspot, this is normally
    the hotspot's IP range. Printed at startup so you can visually confirm
    it matches the ESP32's subnet (see its serial log IP).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def discovery_broadcaster():
    """
    Every second, blast a small UDP packet announcing "I'm the relay,
    connect to me on INGEST_PORT". The ESP32 just listens for this - no
    IP ever needs to be typed into its code.

    Binds the send socket to the hotspot-facing local IP explicitly and
    also sends to that subnet's directed broadcast address (X.Y.Z.255),
    not just 255.255.255.255 - on Windows machines with more than one
    network adapter, a plain global broadcast can pick the wrong adapter
    and fail with "socket operation attempted to an unreachable host".
    """
    local_ip = get_local_ip()
    parts = local_ip.split(".")
    directed_broadcast = ".".join(parts[:3] + ["255"]) if len(parts) == 4 else "255.255.255.255"

    print(f"[Discover] Local IP looks like: {local_ip}")
    print(f"[Discover] Make sure this matches the ESP32's subnet (same first 3 numbers)!")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind((local_ip, 0))
    except Exception as e:
        print("[Discover] could not bind to", local_ip, "-", e)

    msg = DISCOVERY_MAGIC + b":" + str(INGEST_PORT).encode()
    print(f"[Discover] Broadcasting relay beacon on UDP {DISCOVERY_PORT} every 1s")
    while True:
        for target in ("255.255.255.255", directed_broadcast):
            try:
                s.sendto(msg, (target, DISCOVERY_PORT))
            except Exception as e:
                print(f"[Discover] broadcast to {target} failed:", e)
        time.sleep(1)


app = Flask(__name__)


def _mjpeg_generator():
    last_seen_generation = -1
    while True:
        with _cond:
            if _frame_generation == last_seen_generation:
                _cond.wait(timeout=1.0)  # sleeps until notify_all() - no missed wakeups
            frame = _latest_frame
            last_seen_generation = _frame_generation
        if frame is None:
            time.sleep(0.1)
            continue
        yield (
            b"--" + BOUNDARY + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" +
            frame + b"\r\n"
        )


@app.after_request
def add_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    resp.headers["Cache-Control"] = "no-cache, private, max-age=0, must-revalidate"
    return resp


@app.route("/stream")
def stream():
    # threaded=True (see bottom) means every one of these is its own thread -
    # any number of browsers can hit this at once, globally.
    return Response(
        _mjpeg_generator(),
        mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}",
    )


@app.route("/view")
@app.route("/")
def view():
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{width:100%;height:100%;background:#000;overflow:hidden;"
        "display:flex;align-items:center;justify-content:center}"
        "img{width:100%;height:100%;object-fit:cover;display:block}</style></head>"
        '<body><img src="/stream"></body></html>'
    )
    return html


@app.route("/health")
def health():
    with _lock:
        last = _last_frame_time
    age = (time.time() - last) if last else None
    online = age is not None and age < STALE_FRAME_SECONDS
    return jsonify({
        "status": "ok" if online else "camera_offline",
        "camera_connected": online,
        "seconds_since_last_frame": age,
    })


if __name__ == "__main__":
    threading.Thread(target=ingest_server, daemon=True).start()
    threading.Thread(target=discovery_broadcaster, daemon=True).start()
    print(f"[HTTP] Serving /stream /view /health on {HTTP_HOST}:{HTTP_PORT}")
    print("[HTTP] Point your cloudflared tunnel at THIS port (not the ESP32).")
    app.run(host=HTTP_HOST, port=HTTP_PORT, threaded=True)