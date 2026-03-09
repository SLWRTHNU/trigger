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
from trigger_ptpip    import PTPIPTrigger

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
def setup_adxl345():
    """ADXL345 via I2C.  Returns an ADXL345 helper object."""
    from adxl345 import ADXL345
    from machine import I2C
    i2c = I2C(0, sda=Pin(config.I2C_SDA_PIN), scl=Pin(config.I2C_SCL_PIN))
    return ADXL345(i2c)


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
    if config.TRIGGER_MODE == "ptpip":
        print("[trigger] Mode: ptpip")
        t = PTPIPTrigger()
        t.connect()
        return t
    elif config.TRIGGER_MODE == "wireless":
        print("[trigger] Mode: wireless")
        t = WirelessTrigger()
        t.connect()
        return t
    else:
        print("[trigger] Mode: wired")
        return WiredTrigger()


# ---------------------------------------------------------------------------
# IRQ loop — button / digital sensor
# Hardware interrupt fires the moment the pin goes LOW.
# The ISR just sets a flag; all real work happens in the main loop.
# ---------------------------------------------------------------------------
def _irq_loop(trigger, label):
    fired = [False]

    def _isr(_pin):
        fired[0] = True

    pin = Pin(config.SENSOR_PIN, Pin.IN, Pin.PULL_UP)
    pin.irq(trigger=Pin.IRQ_FALLING, handler=_isr)

    blink_led(3, on_ms=100, off_ms=100)
    print(f"[main] Ready (IRQ) — waiting for {label}...")

    last_ms = 0
    while True:
        if fired[0]:
            fired[0] = False
            now = time.ticks_ms()
            if time.ticks_diff(now, last_ms) >= config.COOLDOWN_MS:
                last_ms = now
                print(f"[main] {label} — firing shutter")
                led.on()
                trigger.fire()
                led.off()
        time.sleep_ms(1)


# ---------------------------------------------------------------------------
# Poll loop — ADXL345 (I2C can't use IRQ)
# ---------------------------------------------------------------------------
def _poll_loop(trigger, read_fn, label):
    blink_led(3, on_ms=100, off_ms=100)
    print(f"[main] Ready (poll 1ms) — waiting for {label}...")

    last_ms = 0
    prev = False
    while True:
        active = read_fn()
        if config.LED_ALWAYS_ON_WHEN_ACTIVE:
            led.value(active)
        if active and not prev:          # rising edge (went above threshold)
            now = time.ticks_ms()
            if time.ticks_diff(now, last_ms) >= config.COOLDOWN_MS:
                last_ms = now
                print(f"[main] {label} — firing shutter")
                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.on()
                trigger.fire()
                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.off()
        prev = active
        time.sleep_ms(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run():
    print("=== Vibration Camera Trigger ===")
    print(f"  Sensor  : {config.SENSOR_TYPE}")
    print(f"  Mode    : {config.TRIGGER_MODE}")
    print(f"  Cooldown: {config.COOLDOWN_MS} ms")

    trigger = setup_trigger()

    sensor_type = config.SENSOR_TYPE
    if sensor_type == "adxl345":
        sensor = setup_adxl345()
        _poll_loop(trigger, lambda: read_adxl345(sensor), "vibration")
    elif sensor_type == "button":
        _irq_loop(trigger, "button press")
    else:
        # "digital" — SW-420 / FC-28
        _irq_loop(trigger, "vibration")


if __name__ == "__main__":
    run()
