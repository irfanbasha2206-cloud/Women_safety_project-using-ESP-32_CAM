"""
===================================================================================
Women Safety Project - Cloudflare Tunnel & Auto Cloud Uploader
===================================================================================
UPDATED: now tunnels the RELAY SERVER (relay_server.py), not the ESP32-CAM
directly. The relay fans the stream out to unlimited global viewers - the
ESP32 itself could only ever really serve one client at a time.

Run order:
  1. python relay_server.py            (on this same PC)
  2. Power on the ESP32-CAM (updated main.py pushes frames to the relay)
  3. python start_cloudflare_tunnel.py  <-- this file, run AFTER step 1

1. Starts free Cloudflare Quick Tunnel to the relay: http://127.0.0.1:8000
2. Automatically gets public HTTPS URL (e.g. https://xxxx.trycloudflare.com)
3. Appends '/stream' -> https://xxxx.trycloudflare.com/stream
4. Sends POST request to https://iotcloud22.in/4902/post_value1.php with value1
5. Live stream is instantly viewable on https://iotcloud22.in/4902/ from ANY
   device, on ANY network, all at the same time - without ANY browser blocks!
===================================================================================
"""

import subprocess
import re
import sys
import os
import time
import urllib.request
import urllib.parse

CLOUD_ENDPOINT = "https://iotcloud22.in/4902/post_value1.php"
DEFAULT_ESP32_IP = "127.0.0.1"   # now points at the relay server, not the camera
DEFAULT_ESP32_PORT = "8000"      # must match HTTP_PORT in relay_server.py

def upload_to_cloud(stream_url):
    print(f"\n[CLOUD] Uploading public stream URL to: {CLOUD_ENDPOINT}", flush=True)
    print(f"[CLOUD] URL: {stream_url}", flush=True)
    data = urllib.parse.urlencode({"value1": stream_url}).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "ESP32-Cloudflare-Tunnel"
    }
    req = urllib.request.Request(CLOUD_ENDPOINT, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8").strip()
            print(f"[CLOUD] Server Response: {body}", flush=True)
            return True
    except Exception as e:
        print(f"[ERROR] Failed to upload to cloud: {e}", flush=True)
        return False

def run_tunnel(esp_ip, esp_port):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cloudflared_path = os.path.join(script_dir, "cloudflared.exe")

    if not os.path.exists(cloudflared_path):
        print(f"[ERROR] cloudflared.exe not found at {cloudflared_path}", flush=True)
        print("Please ensure cloudflared.exe is in the same folder.", flush=True)
        sys.exit(1)

    target_local_url = f"http://{esp_ip}:{esp_port}"
    print("=" * 70, flush=True)
    print("   WOMEN SAFETY PROJECT - CLOUDFLARE LIVE STREAM TUNNEL   ", flush=True)
    print("=" * 70, flush=True)
    print(f"[*] Target (relay server): {target_local_url}", flush=True)
    print("[*] Starting Cloudflare Quick Tunnel (Free, No Login Required)...", flush=True)
    print("[*] Connecting to Cloudflare edge network...", flush=True)

    cmd = [cloudflared_path, "tunnel", "--url", target_local_url]

    # Cloudflare outputs tunnel URL to stderr
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    tunnel_url = None
    tunnel_regex = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")

    try:
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                match = tunnel_regex.search(line)
                if match and not tunnel_url:
                    tunnel_url = match.group(0)
                    # Use /view for responsive full-screen auto-fit inside iframe
                    stream_url = f"{tunnel_url}/view"

                    print("\n" + "=" * 70, flush=True)
                    print(" [SUCCESS] CLOUDFLARE HTTPS TUNNEL ESTABLISHED! ", flush=True)
                    print("=" * 70, flush=True)
                    print(f"[*] Public Stream URL : {stream_url}", flush=True)
                    
                    # Upload to IoT Cloud
                    upload_to_cloud(stream_url)

                    print("\n" + "=" * 70, flush=True)
                    print(" [DASHBOARD READY] Open your browser and go to:", flush=True)
                    print(" https://iotcloud22.in/4902/", flush=True)
                    print("=" * 70, flush=True)
                    print("[+] Zero browser security blocks (Full HTTPS!)", flush=True)
                    print("[+] Works on Mobile Data (4G/5G) & Any PC globally!", flush=True)
                    print("[+] Perfect for College Project Demonstration/Viva!", flush=True)
                    print("-" * 70, flush=True)
                    print("IMPORTANT: Keep this black window OPEN while streaming!", flush=True)
                    print("If you close this window, the stream will stop.", flush=True)
                    print("Press Ctrl+C to stop the tunnel.", flush=True)
                    print("-" * 70 + "\n", flush=True)

    except KeyboardInterrupt:
        print("\n[*] Stopping Cloudflare Tunnel...", flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[*] Tunnel closed. Thank you!", flush=True)

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ESP32_IP
    port = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ESP32_PORT
    run_tunnel(ip, port)
