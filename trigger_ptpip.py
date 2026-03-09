"""
PTP/IP shutter trigger for Nikon cameras.

Implements just enough of ISO 15740 (PTP over TCP/IP) to:
  1. Establish command + event connections on port 15740
  2. Open a PTP session
  3. Send InitiateCapture on every fire() call

The camera must be in "remote shooting / smart device" mode.
"""

import socket
import struct
import time
import network
import config

PTPIP_PORT = 15740

# Packet type codes
_PKT_INIT_CMD_REQ = 0x00000001
_PKT_INIT_CMD_ACK = 0x00000002
_PKT_INIT_EVT_REQ = 0x00000003
_PKT_INIT_EVT_ACK = 0x00000004
_PKT_INIT_FAIL    = 0x00000005
_PKT_CMD_REQUEST  = 0x00000006
_PKT_CMD_RESPONSE = 0x00000007

# PTP operation codes
_OP_OPEN_SESSION     = 0x1002
_OP_INITIATE_CAPTURE = 0x100E

# PTP response codes
_RC_OK = 0x2001


# ------------------------------------------------------------------ #
def _utf16le(s):
    """Encode a string as UTF-16LE with a null terminator."""
    out = bytearray()
    for ch in s:
        cp = ord(ch)
        out += bytes([cp & 0xFF, cp >> 8])
    out += b'\x00\x00'
    return bytes(out)


def _make_pkt(pkt_type, payload=b''):
    return struct.pack('<II', 8 + len(payload), pkt_type) + payload


def _recv_pkt(sock):
    hdr = b''
    while len(hdr) < 8:
        chunk = sock.recv(8 - len(hdr))
        if not chunk:
            raise OSError('Connection closed by camera')
        hdr += chunk
    length, pkt_type = struct.unpack('<II', hdr)
    payload = b''
    remaining = length - 8
    while remaining > 0:
        chunk = sock.recv(min(remaining, 512))
        if not chunk:
            raise OSError('Connection closed mid-packet')
        payload += chunk
        remaining -= len(chunk)
    return pkt_type, payload


# ------------------------------------------------------------------ #
class PTPIPTrigger:
    """Connect to a Nikon camera via PTP/IP and fire the shutter."""

    # Fixed GUID identifying this client to the camera.
    _GUID = b'\xde\xad\xbe\xef\xca\xfe\xba\xbe' \
            b'\xde\xad\xbe\xef\xca\xfe\xba\xbe'
    _NAME = 'PicoTrigger'

    def __init__(self):
        self._ip   = config.PTPIP_HOST
        self._cmd  = None   # command TCP socket
        self._evt  = None   # event TCP socket
        self._conn = 0      # connection number assigned by camera
        self._tid  = 1      # PTP transaction ID counter
        self._wlan = network.WLAN(network.STA_IF)

    # ------------------------------------------------------------------ #
    def _wifi_up(self, timeout_s=20):
        self._wlan.active(True)
        if self._wlan.isconnected():
            print(f"[ptpip] WiFi already connected: {self._wlan.ifconfig()[0]}")
            return
        print(f"[ptpip] Connecting to '{config.WIFI_SSID}' ...")
        self._wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        deadline = time.time() + timeout_s
        while not self._wlan.isconnected():
            if time.time() > deadline:
                raise RuntimeError('[ptpip] WiFi connect timed out')
            time.sleep(0.5)
        print(f"[ptpip] Connected — IP: {self._wlan.ifconfig()[0]}")

    # ------------------------------------------------------------------ #
    def connect(self):
        """Open PTP/IP command + event connections and start a PTP session."""
        self._wifi_up()

        # --- Command connection ---
        print(f"[ptpip] Connecting to {self._ip}:{PTPIP_PORT}")
        self._cmd = socket.socket()
        self._cmd.settimeout(10)
        self._cmd.connect((self._ip, PTPIP_PORT))

        payload = (self._GUID
                   + _utf16le(self._NAME)
                   + struct.pack('<I', 0x00010000))   # protocol v1.0
        self._cmd.send(_make_pkt(_PKT_INIT_CMD_REQ, payload))

        ptype, data = _recv_pkt(self._cmd)
        if ptype == _PKT_INIT_FAIL:
            raise OSError('[ptpip] Camera rejected command connection')
        if ptype != _PKT_INIT_CMD_ACK:
            raise OSError(f'[ptpip] Expected Init_Cmd_Ack, got 0x{ptype:08X}')
        self._conn = struct.unpack('<I', data[:4])[0]
        print(f"[ptpip] Command connection OK (conn={self._conn})")

        # --- Event connection (second socket, same port) ---
        self._evt = socket.socket()
        self._evt.settimeout(10)
        self._evt.connect((self._ip, PTPIP_PORT))
        self._evt.send(_make_pkt(_PKT_INIT_EVT_REQ,
                                  struct.pack('<I', self._conn)))

        ptype, _ = _recv_pkt(self._evt)
        if ptype != _PKT_INIT_EVT_ACK:
            raise OSError(f'[ptpip] Expected Init_Evt_Ack, got 0x{ptype:08X}')
        print("[ptpip] Event connection OK")

        # --- OpenSession ---
        rc = self._op(_OP_OPEN_SESSION, [1])
        if rc != _RC_OK:
            raise OSError(f'[ptpip] OpenSession failed: 0x{rc:04X}')
        print("[ptpip] PTP session open — ready")

    # ------------------------------------------------------------------ #
    def _op(self, op_code, params=None):
        """Send a PTP operation (no data phase) and return the response code."""
        tid = self._tid
        self._tid += 1
        payload = struct.pack('<IHI', 1, op_code, tid)
        for p in (params or []):
            payload += struct.pack('<I', p)
        self._cmd.send(_make_pkt(_PKT_CMD_REQUEST, payload))
        ptype, data = _recv_pkt(self._cmd)
        if ptype != _PKT_CMD_RESPONSE:
            raise OSError(f'[ptpip] Expected Cmd_Response, got 0x{ptype:08X}')
        return struct.unpack('<H', data[:2])[0]

    # ------------------------------------------------------------------ #
    def _ensure_connected(self):
        if self._cmd is None or not self._wlan.isconnected():
            print("[ptpip] Reconnecting...")
            self.disconnect()
            self.connect()

    def fire(self):
        """Send InitiateCapture to the camera."""
        self._ensure_connected()
        print("[ptpip] InitiateCapture →")
        try:
            # StorageID=0 (default), ObjectFormatCode=0 (default)
            rc = self._op(_OP_INITIATE_CAPTURE, [0x00000000, 0x00000000])
            if rc == _RC_OK:
                print("[ptpip] ← OK (shutter fired)")
            else:
                print(f"[ptpip] ← 0x{rc:04X}")
        except OSError as e:
            print(f"[ptpip] fire() failed: {e}")
            self._cmd = None
            self._evt = None

    # ------------------------------------------------------------------ #
    def disconnect(self):
        for s in (self._cmd, self._evt):
            if s:
                try:
                    s.close()
                except OSError:
                    pass
        self._cmd = None
        self._evt = None
