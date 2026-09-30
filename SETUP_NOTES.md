# Fix for "stream visible on only one device at a time"

## Root cause (from your zip)
`main.py` runs a single-threaded socket server. Inside `handle_stream()` there's
an infinite `while True` loop pushing frames to whichever ONE client connected -
`srv.accept()` never gets called again until that client disconnects. So no
matter how many devices open the IoT page, the ESP32 can genuinely stream to
only one of them; a second viewer silently knocks the first one off. This is
true even through the Cloudflare tunnel, because the tunnel just forwards
connections to that same single-threaded ESP32 server.

Separately, `send_stream_url.py`'s default URL was a raw LAN IP
(`http://172.20.99.110/view`) - that only works for devices on your hotspot,
never "global network, global devices," unless a tunnel is layered on top.

## The fix: a relay server in the middle
```
ESP32-CAM --(1 push connection)--> relay_server.py --(HTTP)--> unlimited browsers
                                         |
                                    cloudflared tunnel --> public HTTPS URL
```
The ESP32 now only maintains ONE outbound connection (to the relay). The relay
keeps the latest JPEG frame in memory and serves it to as many browsers as
connect - each on its own thread, no camera contention. That relay is what you
tunnel, so it's reachable by any device, on any network, at the same time.

## Files changed
- **relay_server.py** - run this on your laptop. `pip install flask` first.
  Also broadcasts a UDP "I'm here" beacon every second so the ESP32 finds it
  automatically - no IP typed in anywhere.
- **main.py** (ESP32) - now *pushes* frames to the relay instead of serving
  HTTP itself, and *listens* for the relay's beacon instead of a hardcoded IP.
  `SSID`/`PASSWORD` are meant to be YOUR OWN mobile hotspot, set once.
- **start_cloudflare_tunnel.py** - now tunnels `127.0.0.1:8000` (the relay)
  instead of the ESP32's IP.
- **send_stream_url.py** - default test URL now points at the relay.

## One-time setup (do this once, at home)
1. Decide on a mobile hotspot you'll carry to every demo (phone hotspot is
   fine). Set its name/password into `SSID` / `PASSWORD` in `main.py`.
2. Flash `main.py` onto the ESP32-CAM via Thonny. **You never touch Thonny
   or this code again for future demos** - client wifi, client laptop,
   client location don't matter anymore.

## Every demo, from now on (no laptop code edits, no reflashing)
1. Turn on your mobile hotspot.
2. On your laptop (connected to that same hotspot): `python relay_server.py`
   - leave the window open; it prints `[Ingest] Waiting for ESP32-CAM on ...`
     and `[Discover] Broadcasting relay beacon ...`
3. Power on the ESP32-CAM. It auto-joins your hotspot, hears the beacon,
   and connects - you'll see `[Discover] Found relay at ...` then
   `[Relay] Connected. Streaming frames...` in the serial log.
4. `python start_cloudflare_tunnel.py` on your laptop - tunnels the relay
   and auto-uploads the public URL to `iotcloud22.in/4902/`.
5. Client just opens `https://iotcloud22.in/4902/` in their own browser, on
   their own network (office wifi, 4G, anything) - nothing to install, no
   need to be on your hotspot. Any number of devices work simultaneously.

## Note on hotspot broadcast
Discovery relies on UDP broadcast reaching both devices on the hotspot.
Almost all phone hotspots allow this between connected devices. If your
particular hotspot has "client/AP isolation" enabled and discovery never
finds the relay (`[Discover] No relay found in 30s`), turn that isolation
setting off in the hotspot's options, or fall back to hardcoding the IP
(ask and I'll add that fallback path back in).

Sanity check anytime: open `<tunnel-url>/health` - it tells you if the ESP32
is currently pushing frames (`camera_connected: true/false`).
