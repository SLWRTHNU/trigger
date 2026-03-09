"""
Vibration Camera Trigger — main entry point
Raspberry Pi Pico 2 W  |  MicroPython

Reads a vibration sensor (digital SW-420 style OR I2C ADXL345 accelerometer)
and fires a camera shutter via a wired optocoupler or a WiFi HTTP request.

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
def setup_digital_sensor():
    """SW-420 / FC-28 type: digital output LOW when vibration detected."""
    pin = Pin(config.VIBRATION_PIN, Pin.IN, Pin.PULL_UP)
    return pin


def setup_adxl345():
    """ADXL345 via I2C.  Returns an ADXL345 helper object."""
    from adxl345 import ADXL345
    from machine import I2C
    i2c = I2C(0, sda=Pin(config.I2C_SDA_PIN), scl=Pin(config.I2C_SCL_PIN))
    return ADXL345(i2c)


def read_digital_sensor(pin):
    """Return True when vibration is detected (active-LOW sensor)."""
    return pin.value() == 0


def read_adxl345(sensor):
    """Return True when resultant acceleration exceeds the threshold."""
    import math
    x, y, z = sensor.acceleration
    # Subtract 1 g on whichever axis is vertical — approximate tilt-free delta
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
    print(f"  Sensor : {'ADXL345 (I2C)' if config.USE_ADXL345 else 'Digital (SW-420)'}")
    print(f"  Mode   : {config.TRIGGER_MODE}")
    print(f"  Cooldown: {config.COOLDOWN_MS} ms")

    # Sensor init
    if config.USE_ADXL345:
        sensor = setup_adxl345()
        read_fn = lambda: read_adxl345(sensor)
    else:
        sensor_pin = setup_digital_sensor()
        read_fn = lambda: read_digital_sensor(sensor_pin)

    # Trigger init
    trigger = setup_trigger()

    last_trigger_ms = 0

    # Ready indicator
    blink_led(3, on_ms=100, off_ms=100)
    print("[main] Ready — waiting for vibration...")

    while True:
        vibrating = read_fn()

        if config.LED_ALWAYS_ON_WHEN_ACTIVE:
            led.value(vibrating)

        if vibrating:
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, last_trigger_ms)

            if elapsed >= config.COOLDOWN_MS:
                last_trigger_ms = now
                print(f"[main] Vibration detected — firing shutter")

                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.on()

                trigger.fire()

                if not config.LED_ALWAYS_ON_WHEN_ACTIVE:
                    led.off()

        # Small sleep keeps the loop CPU-friendly without missing fast events.
        time.sleep_ms(10)


if __name__ == "__main__":
    run()
