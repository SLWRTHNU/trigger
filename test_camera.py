"""
Camera WiFi connection & trigger test script
Run this on your laptop/PC (not the Pico) while connected to the NIKON hotspot.

Usage:
    python3 test_camera.py

Requirements:
    pip install requests
"""

import sys
import time
import socket
import urllib.request
import urllib.error

# ------------------------------------------------------------------ #
# Known Nikon HTTP API endpoints (Wireless Mobile Utility / SnapBridge)
# The script will probe these automatically.
# ------------------------------------------------------------------ #
NIKON_CANDIDATE_IPS = [
    "192.168.1.1",
    "192.168.0.1",
    "192.168.122.1",
]

NIKON_API_PATHS = [
    # Nikon WMU / MTP-over-HTTP style
    ("/v1/shooting/action/capture",   "POST", b""),
    ("/v1/shooting/action/af",        "POST", b""),
    ("/v1/photos",                    "GET",  None),
    # Generic probe
    ("/",                             "GET",  None),
]

TIMEOUT = 4   # seconds per probe


# ------------------------------------------------------------------ #
def check_current_network():
    """Print the current default gateway — should be the camera IP."""
    print("\n[1] Checking current network...")
    try:
        # Works on Linux and macOS
        import subprocess
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"    Route info : {result.stdout.strip()}")
        else:
            # macOS fallback
            result = subprocess.run(
                ["netstat", "-nr"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if line.startswith("0.0.0.0") or line.startswith("default"):
                    print(f"    Route info : {line}")
                    break
    except Exception as e:
        print(f"    Could not read routing table: {e}")

    # Resolve our own IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"    My IP      : {local_ip}")
        # Camera is usually the .1 address on the same /24
        prefix = ".".join(local_ip.split(".")[:3])
        guessed = prefix + ".1"
        print(f"    Camera likely at: {guessed}")
        return guessed
    except Exception:
        return None


# ------------------------------------------------------------------ #
def ping_host(ip):
    """Return True if the host responds on port 80."""
    try:
        s = socket.create_connection((ip, 80), timeout=TIMEOUT)
        s.close()
        return True
    except (OSError, socket.timeout):
        return False


def find_camera_ip(hint=None):
    """Try candidate IPs and return the first one that answers on port 80."""
    print("\n[2] Scanning for camera HTTP server...")
    candidates = ([hint] if hint else []) + NIKON_CANDIDATE_IPS
    # Deduplicate while preserving order
    seen = set()
    ordered = [c for c in candidates if not (c in seen or seen.add(c))]

    for ip in ordered:
        sys.stdout.write(f"    Probing {ip}:80 ... ")
        sys.stdout.flush()
        if ping_host(ip):
            print("OPEN")
            return ip
        else:
            print("no response")
    return None


# ------------------------------------------------------------------ #
def probe_endpoints(ip):
    """Try known Nikon API paths and return the first successful one."""
    print(f"\n[3] Probing Nikon API endpoints on {ip}...")
    found = None

    for path, method, body in NIKON_API_PATHS:
        url = f"http://{ip}{path}"
        sys.stdout.write(f"    {method} {url} ... ")
        sys.stdout.flush()
        try:
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                status = resp.status
                body_preview = resp.read(200)
                print(f"HTTP {status}  ← {body_preview[:80]}")
                if found is None:
                    found = (url, method, status)
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}")
            if found is None and e.code < 500:
                found = (url, method, e.code)
        except Exception as e:
            print(f"error ({type(e).__name__}: {e})")

    return found


# ------------------------------------------------------------------ #
def simulate_button_press(url, method="POST"):
    """Fire the trigger once, just like the Pico button press will."""
    print(f"\n[4] Simulating button press → {method} {url}")
    try:
        body = b"" if method == "POST" else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            print(f"    Response: HTTP {resp.status}")
            print(f"    Body    : {resp.read(200)}")
            print("\n  *** Trigger fired successfully! ***")
            return True
    except urllib.error.HTTPError as e:
        print(f"    Response: HTTP {e.code} — {e.reason}")
        if e.code < 500:
            print("\n  *** Endpoint reached (non-5xx) — camera may have fired ***")
            return True
        return False
    except Exception as e:
        print(f"    Failed: {e}")
        return False


# ------------------------------------------------------------------ #
def main():
    print("=" * 55)
    print("  Vibration Trigger — Camera Connection Test")
    print("=" * 55)
    print("Make sure your laptop is connected to the NIKON WiFi")
    print("hotspot before running this script.")

    guessed_ip = check_current_network()
    camera_ip  = find_camera_ip(hint=guessed_ip)

    if camera_ip is None:
        print("\n[!] No camera HTTP server found.")
        print("    Check that you are connected to the NIKON WiFi network.")
        sys.exit(1)

    result = probe_endpoints(camera_ip)

    if result is None:
        print("\n[!] No responsive endpoint found.")
        print("    Your camera model may use a different API.")
        print("    Try capturing with the Nikon app while watching traffic")
        print("    with: sudo tcpdump -i <wifi-iface> -A port 80")
        sys.exit(1)

    trigger_url, trigger_method, _ = result
    ok = simulate_button_press(trigger_url, trigger_method)

    if ok:
        print(f"\n[5] Update config.py with:")
        print(f'    WIRELESS_URL = "{trigger_url}"')
        print(f"    (TRIGGER_MODE is already set to \"wireless\")")


if __name__ == "__main__":
    main()
