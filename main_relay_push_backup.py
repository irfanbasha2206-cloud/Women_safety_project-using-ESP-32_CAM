# ─────────────────────────────────────────────────────────────
#  ESP32-CAM MicroPython firmware  –  PUSH-TO-RELAY VERSION
#  Fixes: "stream visible on only one device at a time"
#  Fixes: "had to re-flash SSID / relay IP before every demo"
#
#  OLD: ESP32 itself was the HTTP server -> could really only
#       stream to one connected client at a time.
#  NEW: ESP32 is just a CLIENT. It pushes JPEG frames to
#       relay_server.py (running on your laptop) over ONE TCP
#       connection. The relay fans the stream out to unlimited
#       browsers, on any network, globally.
#
#  DEMO WORKFLOW (flash this ONCE, never touch it again):
#    1. Always carry YOUR OWN mobile hotspot to every demo -
#       SSID/PASSWORD below stay fixed forever, no client wifi
#       details ever needed, no re-flashing per site.
#    2. Your laptop's IP is never hardcoded either - this code
#       LISTENS for a UDP broadcast beacon from relay_server.py
#       and auto-connects to whoever sent it. Just make sure
#       your laptop is on the same hotspot before powering the cam.
#
#  You must run relay_server.py on your laptop BEFORE this boots.
# ─────────────────────────────────────────────────────────────
import camera
import network
import socket
import struct
import time
import machine

# ── 1. REDUCE CPU CLOCK (PREVENTS BROWNOUT) ────────────────
machine.freq(80_000_000)
print("[Power] CPU frequency throttled to 80 MHz (Brownout protection)")

# ── 2. WI-FI CREDENTIALS ────────────────────────────────────
#   YOUR OWN mobile hotspot - set once, same at every demo site.
SSID     = "ras"
PASSWORD = "12345678"

# ── 3. RELAY DISCOVERY (finds relay_server.py automatically) ─
#   No IP typed in here on purpose - see discover_relay() below.
#   Must match DISCOVERY_PORT / DISCOVERY_MAGIC in relay_server.py.
DISCOVERY_PORT  = 9001
DISCOVERY_MAGIC = b"WSAFETY_RELAY_V1"

# ── 4. CONNECT TO WI-FI WITH REDUCED TX POWER ──────────────
print("\n[WiFi] Connecting to", SSID, "...")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

try:
    wlan.config(txpower=8.5)
    print("[Power] Wi-Fi TX power set to 8.5 dBm")
except:
    try:
        wlan.config(txpower=10)
    except:
        pass

wlan.connect(SSID, PASSWORD)

attempts = 0
while not wlan.isconnected():
    time.sleep(0.5)
    attempts += 1
    if attempts > 40:
        print("[WiFi] FAILED to connect. Rebooting...")
        machine.reset()

print("[WiFi] Connected!")
print("[WiFi] ESP32 IP address :", wlan.ifconfig()[0])

# ── 5. INIT CAMERA (STABLE RESOLUTION TO AVOID CURRENT SPIKES)
time.sleep(0.5)  # Allow power to stabilize before turning on camera sensor
try:
    camera.deinit()
except:
    pass

_cam_ok = False
for _init_fn in [
    lambda: camera.init(0, format=camera.JPEG, framesize=camera.FRAME_QVGA, quality=15),
    lambda: camera.init(0, format=camera.JPEG, framesize=camera.FRAME_CIF, quality=15),
    lambda: camera.init(0, format=camera.JPEG),
    lambda: camera.init(0),
    lambda: camera.init(),
]:
    try:
        _init_fn()
        _cam_ok = True
        break
    except Exception:
        pass

if not _cam_ok:
    print("[Camera] ERROR: could not initialise camera")
else:
    for _fn in [
        lambda: camera.framesize(camera.FRAME_QVGA),
        lambda: camera.quality(15),
    ]:
        try:
            _fn()
        except:
            pass
    print("[Camera] Initialized OK (Stable QVGA Mode)")


# ── 6. AUTO-DISCOVER THE RELAY (no hardcoded IP) ────────────
def discover_relay(timeout=30):
    """
    Listens on UDP for relay_server.py's beacon (b"WSAFETY_RELAY_V1:<port>")
    and returns (relay_ip, relay_port) from whoever sent it - that's your
    laptop's CURRENT ip on this hotspot, learned automatically.
    """
    print("[Discover] Listening for relay beacon on UDP", DISCOVERY_PORT, "...")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', DISCOVERY_PORT))
    s.settimeout(timeout)
    try:
        while True:
            try:
                data, addr = s.recvfrom(128)
            except OSError:
                print("[Discover] No relay found in", timeout, "s - retrying...")
                return None, None
            if data.startswith(DISCOVERY_MAGIC):
                try:
                    port = int(data.split(b':')[1])
                except Exception:
                    continue
                print("[Discover] Found relay at", addr[0], ":", port)
                return addr[0], port
    finally:
        s.close()


# ── 7. PUSH FRAMES TO THE RELAY ─────────────────────────────
def push_frames(relay_host, relay_port):
    print("[Relay] Connecting to", relay_host, ":", relay_port, "...")
    s = socket.socket()
    s.settimeout(10)
    s.connect((relay_host, relay_port))
    s.settimeout(None)
    print("[Relay] Connected. Streaming frames...")
    try:
        while True:
            buf = camera.capture()
            if not buf:
                time.sleep(0.05)
                continue

            # 4-byte length header so the relay knows where each frame ends
            s.send(struct.pack(">I", len(buf)))

            view = memoryview(buf)
            for i in range(0, len(buf), 1024):
                s.send(view[i:i + 1024])

            time.sleep(0.04)  # ~25 FPS pacing, avoids power-supply crash
    finally:
        try:
            s.close()
        except:
            pass


# ── 8. MAIN LOOP — reconnect forever if wifi or relay drops ──
# Re-runs discovery every time, so it self-heals even if your
# laptop's IP changes mid-demo (new hotspot join, sleep/wake, etc).
while True:
    try:
        if not wlan.isconnected():
            print("[WiFi] Connection lost, reconnecting...")
            wlan.connect(SSID, PASSWORD)
            while not wlan.isconnected():
                time.sleep(0.5)
            print("[WiFi] Reconnected! IP:", wlan.ifconfig()[0])

        relay_ip, relay_port = discover_relay(timeout=30)
        if relay_ip is None:
            continue  # no beacon heard yet, loop back and listen again

        push_frames(relay_ip, relay_port)

    except Exception as e:
        print("[Relay] Disconnected/error:", e, "- retrying in 2s")
        time.sleep(2)
