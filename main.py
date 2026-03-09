"""
Vibration Camera Trigger — main entry point
Raspberry Pi Pico 2 W  |  MicroPython

Reads a sensor (button, SW-420 digital, or ADXL345 accelerometer) and fires
a camera shutter via a wired optocoupler or a WiFi HTTP request.

Sensor types (set SENSOR_TYPE in config.py):
  "button"   — momentary push-button, fires once per press (edge-triggered)
  "digital"  — SW-420 / FC-28 vibration module digital output
  "adxl345"  — ADXL345 I2C accelerometer with configurable threshold

Edit config.py to configure your setup, then copy all .py files to the Pico.
"""

import time
import config

from machine import Pin
from trigger_wired    import WiredTrigger
from trigger_wireless import WirelessTrigger

# ---------------------------------------------------------------------------
# On-board LED  (Pico W uses 'LED' string, not a GPIO number)
# ---------------------------------------------------------------------------
try:
    led = Pin("LED", Pin.OUT)
except TypeError:
    led = Pin(25, Pin.OUT)


def blink_led(times=1, on_ms=80, off_ms=80):
    for _ in range(times):
        led.on()
        time.sleep_ms(on_ms)
        led.off()
        time.sleep_ms(off_ms)


# ---------------------------------------------------------------------------
# Sensor setup
# ---------------------------------------------------------------------------
def setup_digital_pin():
    """SW-420 / FC-28 or button: active-LOW with internal pull-up."""
    return Pin(config.SENSOR_PIN, Pin.IN, Pin.PULL_UP)


def setup_adxl345():
    """ADXL345 via I2C.  Returns an ADXL345 helper object."""
    from adxl345 import ADXL345
    from machine import I2C
    i2c = I2C(0, sda=Pin(config.I2C_SDA_PIN), scl=Pin(config.I2C_SCL_PIN))
    return ADXL345(i2c)


def read_digital_sensor(pin):
    """Return True when active (active-LOW: LOW = triggered)."""
    return pin.value() == 0


def read_adxl345(sensor):
    """Return True when resultant acceleration exceeds the threshold."""
    import math
    x, y, z = sensor.acceleration
    magnitude = math.sqrt(x*x + y*y + z*z)
    return abs(magnitude - 9.81) > config.ACCEL_THRESHOLD


# ---------------------------------------------------------------------------
# Trigger setup
# ---------------------------------------------------------------------------
def setup_trigger():
    if config.TRIGGER_MODE == "wireless":
        print("[trigger] Mode: wireless")
        t = WirelessTrigger()
        t.connect()
        return t
    else:
        print("[trigger] Mode: wired")
        return WiredTrigger()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run():
    print("=== Vibration Camera Trigger ===")
    print(f"  Sensor : {config.SENSOR_TYPE}")
    print(f"  Mode   : {config.TRIGGER_MODE}")
    print(f"  Cooldown: {config.COOLDOWN_MS} ms")

    # Sensor init
    sensor_type = config.SENSOR_TYPE

    if sensor_type == "adxl345":
        sensor = setup_adxl345()
        read_fn = lambda: read_adxl345(sensor)
        # Level-triggered: fires whenever above threshold
        edge_mode = False
    elif sensor_type == "button":
        pin = setup_digital_pin()
        read_fn = lambda: read_digital_sensor(pin)
        # Edge-triggered: fires once per press, not while held
        edge_mode = True
    else:
        # "digital" — SW-420 / FC-28
        pin = setup_digital_pin()
        read_fn = lambda: read_digital_sensor(pin)
        edge_mode = False

    # Trigger init
    trigger = setup_trigger()

    last_trigger_ms = 0
    prev_active = False

    # Ready indicator
    blink_led(3, on_ms=100, off_ms=100)
    ready_msg = "button press" if sensor_type == "button" else "vibration"
    print(f"[main] Ready — waiting for {ready_msg}...")

    while True:
        active = read_fn()

        if config.LED_ALWAYS_ON_WHEN_ACTIVE:
            led.value(active)

        # For button: only fire on the falling edge (press, not hold).
        # For digital/adxl345: fire whenever the condition is True.
        should_fire = (active and not prev_active) if edge_mode else active
        prev_active = active

        if should_fire:
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, last_trigger_ms)

            if elapsed >= config.COOLDOWN_MS:
                last_trigger_ms = now
                event = "Button pressed" if sensor_type == "button" else "Vibration detected"
                print(f"[main] {event} — firing shutter")

                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.on()

                trigger.fire()

                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.off()

        # Small sleep keeps the loop CPU-friendly without missing fast events.
        time.sleep_ms(10)


if __name__ == "__main__":
    run()
