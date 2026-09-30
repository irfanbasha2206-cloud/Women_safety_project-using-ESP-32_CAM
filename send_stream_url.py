"""
Women Safety Project - Live Stream URL Uploader (manual test tool)
Sends a stream URL to https://iotcloud22.in/4902/post_value1.php

UPDATED: default now points at the RELAY SERVER's /view (see
relay_server.py), not the ESP32 directly - the relay is what's reachable
globally once tunnelled. Normally start_cloudflare_tunnel.py calls the
upload for you automatically; use this script only for manual testing.
"""

import urllib.request
import urllib.parse
import sys

CLOUD_URL = "https://iotcloud22.in/4902/post_value1.php"
DEFAULT_STREAM_URL = "http://127.0.0.1:8000/view"

def upload_stream_url(stream_url):
    print(f"[*] Target Cloud Endpoint : {CLOUD_URL}")
    print(f"[*] Stream URL to send   : {stream_url}")
    
    # post_value1.php expects 'value1' as the form-data key
    data = urllib.parse.urlencode({"value1": stream_url}).encode("utf-8")
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "ESP32-CAM-Uploader/1.0"
    }
    
    req = urllib.request.Request(CLOUD_URL, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8").strip()
            print(f"[+] Status Code: {status_code}")
            print(f"[+] Response   : {response_body}")
            print("\n[SUCCESS] Stream URL uploaded successfully!")
            print("[INFO] Open https://iotcloud22.in/4902/ to view the live camera feed.")
            print("[NOTE] If browser blocks video in Chrome/Edge, click Padlock icon -> Site Settings -> Insecure Content -> Allow.")
    except Exception as e:
        print(f"[-] Error uploading URL: {e}", file=sys.stderr)

if __name__ == "__main__":
    url_to_send = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STREAM_URL
    upload_stream_url(url_to_send)
