"""
Camera WiFi connection & trigger test script — MicroPython (Pico 2 W)

Copy this file to the Pico alongside config.py, then run it from the
Thonny REPL or with:  mpremote run test_camera.py

It will:
  1. Connect to the NIKON WiFi hotspot
  2. Discover the camera's IP + port by scanning common Nikon ports
  3. Probe known Nikon HTTP API endpoints
  4. Fire a live test trigger (simulating a button press)
  5. Print the WIRELESS_URL to paste into config.py
"""

import time
import socket
import struct
import network
import urequests
import config

WIFI_SSID     = config.WIFI_SSID
WIFI_PASSWORD = config.WIFI_PASSWORD
TIMEOUT_S     = 4

# Ports that Nikon cameras are known to use for their HTTP API.
# 80    — Wireless Mobile Utility (older D-series)
# 8080  — WMU on some bodies
# 15740 — PTP/IP (Nikon / MTP-over-IP)
# 8888  — seen on some Z-series / SnapBridge builds
NIKON_PORTS = [80, 8080, 15740, 8888, 3000]

# HTTP API paths to probe once a responding port is found.
# (path, method)
API_PATHS = [
    ("/v1/shooting/action/capture", "POST"),
    ("/v1/shooting/action/af",      "POST"),
    ("/v1/photos",                  "GET"),
    ("/",                           "GET"),
]


# ------------------------------------------------------------------ #
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        ip, _, gateway, _ = wlan.ifconfig()
        print(f"[wifi] Already connected — IP={ip}  gateway={gateway}")
        return wlan

    print(f"[wifi] Connecting to '{WIFI_SSID}' ...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    deadline = time.time() + 20
    while not wlan.isconnected():
        if time.time() > deadline:
            raise RuntimeError("WiFi connect timed out after 20 s")
        time.sleep(0.5)
        print(".", end="")
    print()

    ip, _, gateway, _ = wlan.ifconfig()
    print(f"[wifi] Connected — IP={ip}  gateway={gateway}")
    return wlan


def get_gateway(wlan):
    _, _, gateway, _ = wlan.ifconfig()
    return gateway


# ------------------------------------------------------------------ #
def tcp_reachable(ip, port):
    """Return True if ip:port accepts a TCP connection."""
    try:
        s = socket.socket()
        s.settimeout(TIMEOUT_S)
        s.connect((ip, port))
        s.close()
        return True
    except OSError:
        return False


def find_camera(gateway):
    """Scan gateway + fallback IPs across all known Nikon ports.
    Returns (ip, port) of the first responding socket, or (None, None)."""
    candidates = [gateway, "192.168.1.1", "192.168.0.1", "192.168.122.1"]
    seen = set()
    ordered = [c for c in candidates if c and not (c in seen or seen.add(c))]

    print("\n[2] Scanning for camera HTTP server...")
    for ip in ordered:
        for port in NIKON_PORTS:
            print(f"    Probing {ip}:{port} ... ", end="")
            if tcp_reachable(ip, port):
                print("OPEN")
                return ip, port
            print("no response")
    return None, None


# ------------------------------------------------------------------ #
def probe_endpoints(ip, port):
    """Try each API path and return the first usable (url, method)."""
    host = f"{ip}:{port}" if port != 80 else ip
    print(f"\n[3] Probing Nikon API endpoints on {host} ...")
    found = None

    for path, method in API_PATHS:
        url = f"http://{host}{path}"
        print(f"    {method} {url} ... ", end="")
        try:
            if method == "POST":
                resp = urequests.post(url, data=b"", timeout=TIMEOUT_S)
            else:
                resp = urequests.get(url, timeout=TIMEOUT_S)

            status = resp.status_code
            preview = resp.text[:80] if resp.text else ""
            resp.close()
            print(f"HTTP {status}  <- {preview}")

            if found is None:
                found = (url, method, status)
        except OSError as e:
            print(f"error ({e})")

    return found


# ------------------------------------------------------------------ #
def simulate_button_press(url, method):
    print(f"\n[4] Simulating button press -> {method} {url}")
    try:
        if method == "POST":
            resp = urequests.post(url, data=b"", timeout=TIMEOUT_S)
        else:
            resp = urequests.get(url, timeout=TIMEOUT_S)

        status = resp.status_code
        body   = resp.text[:120] if resp.text else ""
        resp.close()

        print(f"    Response : HTTP {status}")
        if body:
            print(f"    Body     : {body}")

        if status < 500:
            print("\n    *** Trigger fired successfully! ***")
            return True
        else:
            print(f"\n    [!] Server returned {status} — check camera state")
            return False

    except OSError as e:
        print(f"    Failed: {e}")
        return False


# ------------------------------------------------------------------ #
def test_ptpip(ip):
    """Connect via PTP/IP and fire one test capture. Returns True on success."""
    print(f"\n[3] Testing PTP/IP connection to {ip}:15740 ...")
    from trigger_ptpip import PTPIPTrigger, PTPIP_PORT, _RC_OK
    t = PTPIPTrigger()
    # Override config host in case test is run before config is updated
    t._ip = ip
    try:
        t.connect()
        print("\n[4] Sending InitiateCapture ...")
        t.fire()
        t.disconnect()
        return True
    except OSError as e:
        print(f"    PTP/IP error: {e}")
        t.disconnect()
        return False


# ------------------------------------------------------------------ #
def main():
    print("=" * 50)
    print("  Vibration Trigger — Camera Connection Test")
    print("=" * 50)

    # Step 1 — WiFi
    wlan    = connect_wifi()
    gateway = get_gateway(wlan)

    # Step 2 — find camera IP + port
    camera_ip, camera_port = find_camera(gateway)
    if camera_ip is None:
        print("\n[!] No camera server found on any known port.")
        print("    Ports tried:", NIKON_PORTS)
        print("    Check the camera hotspot is active and in remote-shooting mode.")
        return

    # Step 3 — protocol branch
    if camera_port == 15740:
        # PTP/IP — skip HTTP probing, test the binary protocol directly
        ok = test_ptpip(camera_ip)
        if ok:
            print(f"\n[5] Paste this into config.py:")
            print(f'    TRIGGER_MODE = "ptpip"')
            print(f'    PTPIP_HOST   = "{camera_ip}"')
    else:
        result = probe_endpoints(camera_ip, camera_port)
        if result is None:
            print("\n[!] No responsive endpoint found.")
            print("    Your camera model may use a non-standard API path.")
            return
        trigger_url, trigger_method, _ = result
        ok = simulate_button_press(trigger_url, trigger_method)
        if ok:
            print(f"\n[5] Paste this into config.py:")
            print(f'    TRIGGER_MODE = "wireless"')
            print(f'    WIRELESS_URL = "{trigger_url}"')


main()
