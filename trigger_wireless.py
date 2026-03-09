"""
Wireless shutter trigger module.

Connects the Pico 2 W to a WiFi network, then sends an HTTP GET request
to WIRELESS_URL whenever the shutter fires.

Compatible targets:
  - Sony cameras with built-in WiFi (Smart Remote Control app API)
  - Canon cameras running CHDK with the remote shooting script
  - Any custom HTTP relay (e.g., ESP8266/ESP32 dongle, smart plug, etc.)
"""

import time
import network
import urequests
import config


class WirelessTrigger:
    def __init__(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._connected = False

    # ------------------------------------------------------------------
    def connect(self, timeout_s=20):
        """Connect to the configured WiFi network.  Blocks until connected
        or timeout_s seconds have elapsed."""
        self._wlan.active(True)

        if self._wlan.isconnected():
            self._connected = True
            print(f"[wireless] Already connected: {self._wlan.ifconfig()[0]}")
            return

        print(f"[wireless] Connecting to '{config.WIFI_SSID}' ...")
        self._wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        deadline = time.time() + timeout_s
        while not self._wlan.isconnected():
            if time.time() > deadline:
                raise RuntimeError(
                    f"[wireless] WiFi connection timed out after {timeout_s}s"
                )
            time.sleep(0.5)

        self._connected = True
        ip = self._wlan.ifconfig()[0]
        print(f"[wireless] Connected — IP: {ip}")

    # ------------------------------------------------------------------
    def _ensure_connected(self):
        if not self._wlan.isconnected():
            print("[wireless] Connection lost — reconnecting...")
            self.connect()

    # ------------------------------------------------------------------
    def fire(self):
        """Send HTTP GET to WIRELESS_URL to trigger the camera shutter."""
        self._ensure_connected()

        url = config.WIRELESS_URL
        print(f"[wireless] GET {url}")
        try:
            resp = urequests.get(url, timeout=config.HTTP_TIMEOUT)
            print(f"[wireless] Response: {resp.status_code}")
            resp.close()
        except OSError as exc:
            # Network errors (timeout, unreachable host) should not crash
            # the firmware — log and continue.
            print(f"[wireless] Request failed: {exc}")
