"""
Camera WiFi connection & trigger test script — MicroPython (Pico 2 W)

Copy this file to the Pico alongside config.py, then run it from the
Thonny REPL or with:  mpremote run test_camera.py

It will:
  1. Connect to the NIKON WiFi hotspot
  2. Discover the camera's IP from the DHCP gateway
  3. Probe known Nikon HTTP API endpoints
  4. Fire a live test trigger (simulating a button press)
  5. Print the WIRELESS_URL to paste into config.py
"""

import time
import socket
import network
import urequests
import config

WIFI_SSID     = config.WIFI_SSID
WIFI_PASSWORD = config.WIFI_PASSWORD
TIMEOUT_S     = 4

# Nikon Wireless Mobile Utility / SnapBridge HTTP API candidates.
# (ip, path, method)  — ip filled in at runtime from DHCP gateway.
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
def tcp_reachable(ip, port=80):
    """Return True if the host has port 80 open."""
    try:
        s = socket.socket()
        s.settimeout(TIMEOUT_S)
        s.connect((ip, port))
        s.close()
        return True
    except OSError:
        return False


def find_camera_ip(gateway):
    """Try the DHCP gateway, then common fallbacks."""
    candidates = [gateway, "192.168.1.1", "192.168.0.1", "192.168.122.1"]
    # deduplicate, preserve order
    seen = set()
    ordered = [c for c in candidates if c and not (c in seen or seen.add(c))]

    print("\n[2] Scanning for camera HTTP server...")
    for ip in ordered:
        print(f"    Probing {ip}:80 ... ", end="")
        if tcp_reachable(ip):
            print("OPEN")
            return ip
        print("no response")
    return None


# ------------------------------------------------------------------ #
def probe_endpoints(ip):
    """Try each API path and return the first usable (url, method)."""
    print(f"\n[3] Probing Nikon API endpoints on {ip} ...")
    found = None

    for path, method in API_PATHS:
        url = f"http://{ip}{path}"
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
def main():
    print("=" * 50)
    print("  Vibration Trigger — Camera Connection Test")
    print("=" * 50)

    # Step 1 — WiFi
    wlan      = connect_wifi()
    gateway   = get_gateway(wlan)

    # Step 2 — find camera IP
    camera_ip = find_camera_ip(gateway)
    if camera_ip is None:
        print("\n[!] No camera HTTP server found.")
        print("    Ensure the camera WiFi hotspot is active.")
        return

    # Step 3 — probe API
    result = probe_endpoints(camera_ip)
    if result is None:
        print("\n[!] No responsive endpoint found.")
        print("    Your camera model may use a non-standard API path.")
        return

    trigger_url, trigger_method, _ = result

    # Step 4 — fire
    ok = simulate_button_press(trigger_url, trigger_method)

    # Step 5 — report
    if ok:
        print(f"\n[5] Paste this into config.py:")
        print(f'    WIRELESS_URL = "{trigger_url}"')


main()
