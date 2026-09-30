# Women Safety Project v2

This project provides a live ESP32-CAM video feed that can be viewed by many people at once, including viewers on different networks. It uses a laptop-hosted relay server to receive camera frames, distribute them as an MJPEG stream, and expose the stream securely through a Cloudflare Quick Tunnel.

## How it works

```text
ESP32-CAM --TCP JPEG frames--> Python relay server --MJPEG--> viewers
                                  |
                                  +--Cloudflare Quick Tunnel--> public HTTPS URL
```

The ESP32-CAM connects to the relay through Wi-Fi and sends JPEG frames over one TCP connection. The relay stores the latest frame and serves it to any number of browser clients. UDP discovery lets the camera find the relay automatically, so the laptop IP does not need to be hardcoded.

## Project files

- `main.py` — MicroPython firmware for the ESP32-CAM. Configure your Wi-Fi credentials before flashing it to the device.
- `relay_server.py` — Flask-based relay that receives frames, broadcasts its availability over UDP, and provides `/`, `/view`, `/stream`, and `/health` endpoints.
- `start_cloudflare_tunnel.py` — Starts a Cloudflare Quick Tunnel for the relay and publishes the public stream URL to the IoT dashboard.
- `send_stream_url.py` — Manually sends a stream URL to the IoT dashboard for testing.
- `SETUP_NOTES.md` — Detailed explanation of the relay architecture and demo procedure.

## Requirements

- ESP32-CAM flashed with MicroPython and the `camera` module
- Python 3 on the relay laptop
- A shared Wi-Fi network or mobile hotspot for the ESP32-CAM and laptop
- Flask (`pip install flask`)
- `cloudflared.exe` in this project folder

## Setup

1. In `main.py`, set `SSID` and `PASSWORD` to the Wi-Fi or mobile hotspot the ESP32-CAM will use.
2. Flash `main.py` to the ESP32-CAM using Thonny or another MicroPython uploader.
3. Connect the laptop running this project to the same network as the camera.

## Run a demo

1. Start the relay:

   ```powershell
   python relay_server.py
   ```

2. Power on the ESP32-CAM. It discovers the relay by UDP broadcast and begins sending frames.

3. Check camera status locally, if needed:

   ```text
   http://127.0.0.1:8000/health
   ```

4. Start the public tunnel:

   ```powershell
   python start_cloudflare_tunnel.py
   ```

5. Keep both terminal windows open. The tunnel script publishes the generated HTTPS `/view` URL to the configured IoT dashboard, where the live feed can be opened from any network.

## Local endpoints

- `/` or `/view` — Full-screen live camera view
- `/stream` — Raw MJPEG stream
- `/health` — JSON health status, including whether fresh camera frames are arriving

## Notes

- The relay must start before the ESP32-CAM.
- The camera and relay laptop must be on the same local network for UDP discovery and TCP frame delivery.
- A Cloudflare Quick Tunnel URL is temporary and remains available only while the tunnel script is running.
- If hotspot client isolation prevents UDP broadcast, disable that setting or add a suitable static-relay fallback.
