# Vibration Camera Trigger

A MicroPython firmware for the **Raspberry Pi Pico 2 W** that fires a camera
shutter whenever a connected vibration sensor detects movement.

Supports two trigger modes:

| Mode | How it works |
|------|--------------|
| **Wired** | GPIO → optocoupler → camera 2.5 mm / 3.5 mm remote shutter port |
| **Wireless** | Pico W WiFi → HTTP GET → WiFi-enabled camera or relay |

And two sensor types:

| Sensor | Notes |
|--------|-------|
| **SW-420 / FC-28** | Simple digital output, cheap, plug-and-play |
| **ADXL345** | I2C accelerometer, adjustable threshold, more control |

---

## File Overview

```
main.py             — Entry point, sensor read loop
config.py           — All user-configurable settings (edit this first!)
trigger_wired.py    — Wired optocoupler trigger
trigger_wireless.py — WiFi HTTP trigger
adxl345.py          — Lightweight ADXL345 I2C driver
```

---

## Hardware

### Vibration Sensor Option 1 — SW-420 (Recommended for simplicity)

```
SW-420 Module    Pico 2 W
─────────────    ─────────────────────────
VCC          →   3V3OUT  (pin 36)
GND          →   GND     (pin 38)
DO           →   GP15    (configurable via VIBRATION_PIN)
```

The SW-420 module includes an onboard potentiometer to set vibration
sensitivity. The DO pin goes LOW when vibration is detected.

### Vibration Sensor Option 2 — ADXL345 (I2C accelerometer)

Set `USE_ADXL345 = True` in `config.py`.

```
ADXL345      Pico 2 W
─────────    ─────────────────────────
VCC      →   3V3OUT  (pin 36)
GND      →   GND     (pin 38)
SDA      →   GP4     (configurable via I2C_SDA_PIN)
SCL      →   GP5     (configurable via I2C_SCL_PIN)
CS       →   3V3OUT  (selects I2C mode)
SDO/ALT  →   GND     (I2C address 0x53)
```

Tune `ACCEL_THRESHOLD` in `config.py` — start at `1.5` (m/s²) and lower
it for more sensitivity or raise it to ignore small bumps.

---

## Wired Trigger Wiring

A 4N35 or PC817 optocoupler provides electrical isolation between the Pico
and the camera body, protecting both devices.

```
Pico GP16 ──[330 Ω]── Pin 1 (Anode)  ┐
                                       │ 4N35 / PC817
                       Pin 2 (Cathode)─┘
                       Pin 4 (Emitter) ── Camera GND (sleeve)
                       Pin 5 (Collector) ── Camera Focus/Shutter (tip/ring)
```

### Common camera remote pinouts (2.5 mm / 3.5 mm TRS jack)

| Camera brand | Connector | Tip | Ring | Sleeve |
|---|---|---|---|---|
| Canon (older) | 2.5 mm TRS | Shutter | Focus | GND |
| Nikon (most)  | 2.5 mm TRS | Focus | Shutter | GND |
| Sony Multi    | Sony Multi | — | — | — |
| Fujifilm      | 2.5 mm TRS | Shutter | Focus | GND |
| Olympus/OM    | 2.5 mm TRS | Shutter | Focus | GND |

To trigger a full shutter press, short **both** Tip and Ring to Sleeve.
Wire both through separate optocoupler outputs driven by the same GPIO, or
use a single optocoupler with the camera's combined focus+shutter line if
your camera supports it.

> **Tip:** Test with a cheap aftermarket remote cable first to identify the
> correct pinout for your specific camera model before making a custom cable.

---

## Wireless Trigger Setup

Set `TRIGGER_MODE = "wireless"` and fill in `WIFI_SSID`, `WIFI_PASSWORD`,
and `WIRELESS_URL` in `config.py`.

### Sony cameras (built-in WiFi)

1. Enable **Smart Remote Control** on the camera.
2. Connect the Pico W to the camera's WiFi hotspot.
3. Set `WIRELESS_URL = "http://192.168.122.1:10000/sony/camera/actTakePicture"`.

### Canon with CHDK

1. Load CHDK and enable the remote shooting script.
2. Set `WIRELESS_URL = "http://192.168.0.1/control?cmd=shoot"`.

### Custom relay (any WiFi camera or smart plug)

Use any device that accepts an HTTP GET to trigger an action.
An ESP8266/ESP32 running a simple web server works well as a wireless
intermediary for cameras without built-in WiFi.

---

## Installation

1. Flash **MicroPython** on to the Pico 2 W.
   Download the latest `.uf2` from https://micropython.org/download/RPI_PICO2_W/

2. Copy all `.py` files to the Pico root using **Thonny**, **mpremote**, or
   **rshell**:

   ```bash
   # Using mpremote
   mpremote cp config.py main.py trigger_wired.py trigger_wireless.py adxl345.py :
   ```

3. Edit `config.py` on the device to match your wiring and camera.

4. Reset the Pico — `main.py` runs automatically on boot.

---

## Tuning Tips

| Setting | Effect |
|---------|--------|
| `COOLDOWN_MS` | Raise to ignore repeated vibration bursts; lower for rapid-fire |
| `SHUTTER_HOLD_MS` | Raise if camera doesn't register the trigger; 100 ms is safe |
| SW-420 potentiometer | Turn clockwise to increase sensitivity |
| `ACCEL_THRESHOLD` | Lower value = more sensitive (ADXL345 only) |

---

## Schematic Summary

```
                ┌─────────────────┐
   SW-420 DO ───┤ GP15            │
                │                 │
                │  Pico 2 W       │
                │                 │───── WiFi (wireless mode)
                │         GP16 ───┼──[330Ω]──[Optocoupler]──▶ Camera jack
                └─────────────────┘
```

---

## License

MIT — use freely, no warranty.
