# Women Safety Project v2 — Client Handover & Demo Guide

This guide explains how to deliver and run the project smoothly on the client's laptop without any manual setup or debugging during the demo.

---

## 📦 What to Deliver to the Client

### 1. Hardware
- **ESP32-CAM Board** (Pre-flashed with `main.py`).
- **Power Supply**: 5V 2A Phone Charger / Power Bank + Micro-USB / 5V jumper wires.
  > **Note:** The jumper between GPIO 0 and GND must be **DISCONNECTED** during normal use.

### 2. Software Folder (`Women_safety_project_v2`)
Copy the complete project folder to the client's laptop (e.g. `C:\Women_safety_project_v2` or `Desktop`):
- `START_SYSTEM.bat` — One-click launcher for the client.
- `app.py` — Flask stream engine & Cloudflare tunnel auto-publisher.
- `cloudflared.exe` — Standalone Cloudflare tunnel binary (no login/install needed).
- `requirements.txt` — Python library dependencies (`flask`, `opencv-python`, `numpy`, `requests`).
- `main.py` — ESP32-CAM MicroPython firmware (already saved on the board).

---

## 💻 Client Laptop Requirements (5-Minute One-Time Setup)

1. **Install Python 3.9, 3.10, 3.11, or 3.12** (if not already installed).
   - Download: [python.org/downloads](https://www.python.org/downloads/)
   - ⚠️ **VERY IMPORTANT:** Check the box **"Add Python to PATH"** at the bottom of the installer window!
2. **No Thonny Needed:** The client **NEVER** needs to install or open Thonny!
3. **No Cloudflare Login Needed:** `cloudflared.exe` is completely free and requires zero login or configuration.

---

## 📶 Wi-Fi / Hotspot Setup

The ESP32-CAM connects to either of these networks automatically:
- **Hotspot 1:** Name: `NarenTech` | Password: `9994119444`
- **Hotspot 2:** Name: `ras` | Password: `12345678`

### Recommended for Demo:
- Turn on your mobile hotspot with:
  - **SSID:** `NarenTech`
  - **Password:** `9994119444`
  - **Band:** 2.4 GHz (ESP32-CAM requires 2.4 GHz).
- Connect both the **Client Laptop** and the **ESP32-CAM** to this hotspot.

---

## 🚀 How to Run the Demo (Step-by-Step for Client)

1. **Step 1:** Turn ON the Mobile Hotspot (`NarenTech` / `9994119444`).
2. **Step 2:** Connect the Client Laptop to the `NarenTech` Wi-Fi.
3. **Step 3:** Power ON the ESP32-CAM board (connect to power bank / 5V adapter).
4. **Step 4:** On the laptop, **Double-Click `START_SYSTEM.bat`**.
   - It automatically verifies libraries.
   - It finds the ESP32-CAM on the Wi-Fi.
   - It starts the Cloudflare HTTPS tunnel.
   - It automatically publishes the live link to `https://iotcloud22.in/4902/`.
5. **Step 5:** Open the IoT Cloud Dashboard in any browser (laptop, mobile, projector):
   👉 **[https://iotcloud22.in/4902/](https://iotcloud22.in/4902/)**
   - The live video stream will play smoothly at 25+ FPS without lag or browser security warnings!

---

## 🛑 How to Stop the System
Simply close the `START_SYSTEM.bat` Command Prompt window when the demo is finished.
