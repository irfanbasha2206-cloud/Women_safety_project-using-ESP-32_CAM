"""
══════════════════════════════════════════════════════════════════════
  Women Safety Project v2 — Smart Auto-Discovery & Cloudflare Relay
  HIGH-PERFORMANCE ZERO-LAG FLASK STREAM ENGINE (DUAL PUSH/PULL)
══════════════════════════════════════════════════════════════════════
  Features:
  1. DUAL INGEST: Supports both TCP Push (Port 9000) & HTTP Pull (Port 80)
  2. Auto-Discovers ESP32-CAM via UDP 9001, UDP 4210, and Subnet Scan
  3. Integrated Cloudflare Quick Tunnel (Free, No Login Required)
  4. Auto-Publishes Public HTTPS Stream URL to https://iotcloud22.in/4902/
  5. Diagnostic Standby Canvas: Shows live status when camera is starting
══════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import socket
import struct
import re
import subprocess
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, Response, jsonify
import cv2
import numpy as np

# ── CONFIGURATION ───────────────────────────────────────────────────
LOCAL_FLASK_PORT = 8000
INGEST_PORT = 9000          # TCP Push port
DISCOVERY_PORT_PUSH = 9001  # UDP Beacon for Push mode
DISCOVERY_PORT_PULL = 4210  # UDP Beacon for Pull mode

IOT_CLOUD_ENDPOINT = "https://iotcloud22.in/4902/post_value1.php"
IOT_DASHBOARD_URL = "https://iotcloud22.in/4902/"

# Shared Stream State
app = Flask(__name__)
_lock = threading.Lock()
_cond = threading.Condition(_lock)

_latest_frame = None
_last_frame_time = 0.0
_frame_generation = 0

camera_connected = False
esp32_ip = None
esp32_stream_url = None
public_tunnel_url = None
BOUNDARY = b"frame"


# ── 1. DIAGNOSTIC STANDBY CANVAS GENERATOR ──────────────────────────
_cached_standby_frame = None
_last_standby_time = 0.0

def get_standby_frame(subtitle="Waiting for ESP32-CAM connection on NarenTech..."):
    """Generates an animated standby canvas to show in the IoT iframe while connecting."""
    global _cached_standby_frame, _last_standby_time
    now = time.time()
    if _cached_standby_frame and (now - _last_standby_time < 0.5):
        return _cached_standby_frame

    # 480x320 dark canvas
    canvas = np.zeros((320, 480, 3), dtype=np.uint8)
    canvas[:] = (12, 16, 28)

    # Subtle grid lines
    for x in range(0, 480, 30):
        cv2.line(canvas, (x, 0), (x, 320), (20, 28, 45), 1)
    for y in range(0, 320, 30):
        cv2.line(canvas, (0, y), (480, y), (20, 28, 45), 1)

    # Pulsing status indicator
    pulse = (int(now * 2) % 2) == 0
    dot_color = (0, 212, 255) if pulse else (0, 120, 180)
    cv2.circle(canvas, (240, 90), 20, (25, 35, 60), -1)
    cv2.circle(canvas, (240, 90), 20, (0, 212, 255), 1)
    cv2.circle(canvas, (240, 90), 8, dot_color, -1)

    # Header title
    cv2.putText(canvas, "WOMEN SAFETY LIVE SYSTEM", (85, 145),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    # Status text
    status_text = "STATUS: CAMERA INITIALIZING / OFFLINE"
    cv2.putText(canvas, status_text, (95, 180),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 212, 255), 1)

    # Subtitle
    cv2.putText(canvas, subtitle, (55, 215),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 195, 215), 1)

    # Instructions box
    cv2.rectangle(canvas, (40, 245), (440, 285), (20, 30, 50), -1)
    cv2.rectangle(canvas, (40, 245), (440, 285), (45, 65, 100), 1)
    cv2.putText(canvas, "Please ensure ESP32-CAM is powered ON and on 'NarenTech'", (52, 270),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 165, 195), 1)

    _, encoded = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    _cached_standby_frame = encoded.tobytes()
    _last_standby_time = now
    return _cached_standby_frame


# ── 2. NETWORK & DISCOVERY UTILITIES ────────────────────────────────
def get_local_ip():
    """Gets the active local IP of this machine on the Wi-Fi network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── 3. MODE A: TCP PORT 9000 PUSH INGEST SERVER ─────────────────────
def tcp_push_ingest_server():
    """
    Accepts push connections from ESP32-CAM on TCP port 9000.
    Reads continuous stream of [4-byte big-endian length][JPEG bytes].
    """
    global _latest_frame, _last_frame_time, _frame_generation, camera_connected, esp32_ip
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", INGEST_PORT))
        srv.listen(2)
        print(f"[Ingest] TCP Push Server active on port {INGEST_PORT}")
    except Exception as e:
        print(f"[Ingest] TCP port {INGEST_PORT} bind notice: {e}")
        return

    while True:
        conn = None
        try:
            conn, addr = srv.accept()
            print(f"\n[+] [TCP 9000] ESP32-CAM Connected from {addr[0]}!")
            esp32_ip = addr[0]
            camera_connected = True
            conn.settimeout(12)
            buf = b""
            frames_count = 0
            start_t = time.time()

            while True:
                while len(buf) < 4:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("Camera closed socket")
                    buf += chunk
                (frame_len,) = struct.unpack(">I", buf[:4])
                buf = buf[4:]

                while len(buf) < frame_len:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("Camera closed socket")
                    buf += chunk
                frame, buf = buf[:frame_len], buf[frame_len:]

                with _cond:
                    _latest_frame = frame
                    _last_frame_time = time.time()
                    _frame_generation += 1
                    _cond.notify_all()

                frames_count += 1
                if frames_count % 50 == 0:
                    fps = frames_count / (time.time() - start_t)
                    print(f"[+] [STREAM PUSH] Ingesting ~{fps:.1f} FPS from {esp32_ip}")
                    frames_count = 0
                    start_t = time.time()

        except Exception as e:
            if camera_connected:
                print(f"[-] [TCP 9000] ESP32-CAM disconnected: {e}")
            camera_connected = False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            time.sleep(1.0)


def discovery_broadcaster():
    """Broadcasts UDP beacon on port 9001 every 1s so ESP32 knows our laptop IP."""
    local_ip = get_local_ip()
    parts = local_ip.split(".")
    directed_bcast = ".".join(parts[:3] + ["255"]) if len(parts) == 4 else "255.255.255.255"

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"WSAFETY_RELAY_V1:{INGEST_PORT}".encode()

    while True:
        for target in ["255.255.255.255", directed_bcast]:
            try:
                s.sendto(msg, (target, DISCOVERY_PORT_PUSH))
            except Exception:
                pass
        time.sleep(1.0)


# ── 4. MODE B: HTTP PORT 80 PULL STREAM WORKER ──────────────────────
def test_esp32_http_ip(target_ip):
    """Probes port 80 /health on a target IP in <0.3s."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        if s.connect_ex((target_ip, 80)) == 0:
            s.close()
            with urllib.request.urlopen(f"http://{target_ip}/health", timeout=0.6) as resp:
                body = resp.read().decode("utf-8", "ignore")
                if "ok" in body or "ESP32" in body or "wifi" in body:
                    return target_ip
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    return None


def probe_local_subnet():
    """Scans all IPs on the local subnet using 50 threads."""
    local_ip = get_local_ip()
    parts = local_ip.split(".")
    if len(parts) != 4:
        return None
    base = f"{parts[0]}.{parts[1]}.{parts[2]}."

    priority_ips = [f"{base}{i}" for i in [28, 23, 24, 25, 22, 50, 100, 101, 10, 15]]
    for p_ip in priority_ips:
        found = test_esp32_http_ip(p_ip)
        if found:
            return found

    all_ips = [f"{base}{i}" for i in range(2, 255)]
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(test_esp32_http_ip, all_ips)
        for r in results:
            if r:
                return r
    return None


def udp_pull_listener():
    """Listens on UDP port 4210 for ESP32 pull beacons."""
    global esp32_ip, esp32_stream_url
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass
    try:
        s.bind(("", DISCOVERY_PORT_PULL))
        s.settimeout(2.0)
    except Exception:
        return

    while True:
        try:
            data, addr = s.recvfrom(1024)
            if data:
                text = data.decode("utf-8", "ignore").strip()
                if "AEGISRX" in text or "ESP32CAM" in text:
                    parts = text.split("|")
                    disc_ip = parts[1] if len(parts) > 1 else addr[0]
                    if esp32_ip != disc_ip:
                        esp32_ip = disc_ip
                        esp32_stream_url = f"http://{esp32_ip}/stream"
                        print(f"\n[+] [UDP 4210] Found ESP32-CAM at {esp32_ip}")
        except socket.timeout:
            pass
        except Exception:
            time.sleep(0.5)


def http_pull_worker():
    """Connects to ESP32 /stream if detected via HTTP."""
    global _latest_frame, _last_frame_time, _frame_generation, camera_connected

    while True:
        if camera_connected or not esp32_stream_url:
            time.sleep(1.0)
            continue

        print(f"[*] Trying HTTP Pull from: {esp32_stream_url} ...")
        try:
            req = urllib.request.Request(esp32_stream_url, headers={"User-Agent": "WomenSafetyRelay/2.0"})
            stream = urllib.request.urlopen(req, timeout=5.0)
            print(f"[+] [HTTP PULL] Connected to {esp32_stream_url}!")
            camera_connected = True

            buf = b""
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buf += chunk

                while True:
                    start = buf.find(b"\xff\xd8")
                    if start == -1:
                        if len(buf) > 4096:
                            buf = buf[-1024:]
                        break
                    end = buf.find(b"\xff\xd9", start + 2)
                    if end == -1:
                        break

                    jpg = buf[start:end + 2]
                    buf = buf[end + 2:]

                    with _cond:
                        _latest_frame = jpg
                        _last_frame_time = time.time()
                        _frame_generation += 1
                        _cond.notify_all()

        except Exception as e:
            time.sleep(2.0)


# ── 5. CLOUDFLARE QUICK TUNNEL & AUTO IOT UPLOADER ──────────────────
def upload_to_iot_cloud(public_url):
    """Publishes the live stream URL to https://iotcloud22.in/4902/post_value1.php."""
    print(f"\n[Cloud] Auto-Publishing Stream URL to IoT Dashboard...")
    print(f"[Cloud] Endpoint   : {IOT_CLOUD_ENDPOINT}")
    print(f"[Cloud] Stream URL : {public_url}")

    data = urllib.parse.urlencode({"value1": public_url}).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "WomenSafety-TunnelUploader/2.0"
    }
    req = urllib.request.Request(IOT_CLOUD_ENDPOINT, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", "ignore").strip()
            print(f"[Cloud] Server Response: {body}")
            print(f"[SUCCESS] Stream URL successfully published to IoT Dashboard!")
            print(f"[SUCCESS] Open dashboard: {IOT_DASHBOARD_URL}\n")
            return True
    except Exception as e:
        print(f"[-] Error uploading to cloud: {e}")
        return False


def cloudflare_tunnel_worker():
    """Starts cloudflared.exe and automatically extracts the HTTPS tunnel URL."""
    global public_tunnel_url
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cloudflared_path = os.path.join(script_dir, "cloudflared.exe")

    if not os.path.exists(cloudflared_path):
        print(f"[ERROR] cloudflared.exe not found at {cloudflared_path}!")
        return

    time.sleep(1.5)
    target_local_url = f"http://127.0.0.1:{LOCAL_FLASK_PORT}"
    print(f"[*] Starting Cloudflare Quick Tunnel for {target_local_url} ...")

    cmd = [cloudflared_path, "tunnel", "--url", target_local_url]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    tunnel_regex = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
    while True:
        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break
        if line:
            match = tunnel_regex.search(line)
            if match and not public_tunnel_url:
                base_url = match.group(0)
                public_tunnel_url = f"{base_url}/view"

                print("═" * 70)
                print("  [SUCCESS] CLOUDFLARE HTTPS TUNNEL ESTABLISHED!  ")
                print("═" * 70)
                print(f"[*] Public Stream URL : {public_tunnel_url}")
                print(f"[*] IoT Dashboard URL : {IOT_DASHBOARD_URL}")
                print("═" * 70)

                upload_to_iot_cloud(public_tunnel_url)
                break


# ── 6. FLASK WEB SERVER (MJPEG STREAMING & VIEW) ─────────────────────
def _mjpeg_generator():
    last_seen_gen = -1
    while True:
        frame_to_send = None

        with _cond:
            age = time.time() - _last_frame_time
            if _latest_frame and age < 3.5:
                if _frame_generation == last_seen_gen:
                    _cond.wait(timeout=0.2)
                frame_to_send = _latest_frame
                last_seen_gen = _frame_generation
            else:
                # Camera not delivering frames -> send diagnostic standby frame
                frame_to_send = get_standby_frame()
                time.sleep(0.1)

        if frame_to_send:
            yield (
                b"--" + BOUNDARY + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame_to_send)).encode() + b"\r\n\r\n" +
                frame_to_send + b"\r\n"
            )


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    resp.headers["Cache-Control"] = "no-cache, private, max-age=0, must-revalidate"
    return resp


@app.route("/stream")
def stream():
    return Response(
        _mjpeg_generator(),
        mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}"
    )


@app.route("/view")
@app.route("/")
def view():
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Women Safety Live Stream</title>"
        "<style>*{margin:0;padding:0;box-sizing:border-box;}"
        "html,body{width:100%;height:100%;background:#02060c;overflow:hidden;"
        "display:flex;align-items:center;justify-content:center;}"
        "img{width:100%;height:100%;object-fit:cover;display:block;}</style></head>"
        '<body><img src="/stream" onerror="setTimeout(()=>location.reload(),2000)"></body></html>'
    )
    return html


@app.route("/health")
def health():
    with _lock:
        last = _last_frame_time
    age = (time.time() - last) if last else None
    online = age is not None and age < 3.5
    return jsonify({
        "status": "ok" if online else "camera_offline",
        "camera_connected": online,
        "esp32_ip": esp32_ip,
        "seconds_since_last_frame": age,
        "public_tunnel_url": public_tunnel_url
    })


from flask import request

@app.route("/set_ip")
def set_ip():
    global esp32_ip, esp32_stream_url
    new_ip = request.args.get("ip", "").strip()
    if new_ip:
        esp32_ip = new_ip
        esp32_stream_url = f"http://{esp32_ip}/stream" if not new_ip.startswith("http") else new_ip
        print(f"\n[+] Manually set ESP32-CAM stream target: {esp32_stream_url}")
        return jsonify({"status": "ok", "stream_url": esp32_stream_url})
    return jsonify({"status": "error", "message": "Usage: /set_ip?ip=192.168.x.x"})


def subnet_scanner_worker():
    """Continuously probes the local subnet until ESP32-CAM is located."""
    global esp32_ip, esp32_stream_url
    time.sleep(2.0)
    while True:
        if not camera_connected:
            found = probe_local_subnet()
            if found and esp32_ip != found:
                esp32_ip = found
                esp32_stream_url = f"http://{esp32_ip}/stream"
                print(f"\n[+] [SUBNET SCAN] Located ESP32-CAM at {esp32_ip}!")
        time.sleep(3.0)


# ── 7. MAIN ENTRY POINT ──────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 70)
    print("   WOMEN SAFETY PROJECT v2 — DUAL RELAY & CLOUD STREAM ENGINE   ")
    print("═" * 70)
    print(f"[*] Local PC IP         : {get_local_ip()}")
    print(f"[*] Mode A (Push)       : Listening on TCP 9000 & UDP 9001 beacon")
    print(f"[*] Mode B (Pull)       : Listening on UDP 4210 & Subnet scan")
    print(f"[*] Relay Web Server    : http://127.0.0.1:{LOCAL_FLASK_PORT}/view")
    print("═" * 70)

    # 1. Start Mode A: TCP Port 9000 Ingest + UDP 9001 Broadcaster
    threading.Thread(target=tcp_push_ingest_server, daemon=True).start()
    threading.Thread(target=discovery_broadcaster, daemon=True).start()

    # 2. Start Mode B: UDP 4210 Listener + HTTP Pull Worker + Subnet Prober
    threading.Thread(target=udp_pull_listener, daemon=True).start()
    threading.Thread(target=http_pull_worker, daemon=True).start()
    threading.Thread(target=subnet_scanner_worker, daemon=True).start()

    # 3. Start Cloudflare Tunnel & IoT Auto-Uploader
    threading.Thread(target=cloudflare_tunnel_worker, daemon=True).start()

    # 4. Start Flask Multi-threaded Web Server
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=LOCAL_FLASK_PORT, threaded=True)
