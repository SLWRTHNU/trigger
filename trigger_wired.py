"""
Wired shutter trigger module.

Drives a GPIO pin HIGH for SHUTTER_HOLD_MS milliseconds.
Connect that pin through a 4N35 / PC817 optocoupler to your camera's
remote shutter port (see README for wiring details).
"""

import time
from machine import Pin
import config


class WiredTrigger:
    def __init__(self):
        self._pin = Pin(config.SHUTTER_PIN, Pin.OUT, value=0)
        print(f"[wired] Shutter pin: GPIO{config.SHUTTER_PIN}")

    def fire(self):
        """Pulse the shutter pin HIGH for the configured hold time."""
        self._pin.on()
        time.sleep_ms(config.SHUTTER_HOLD_MS)
        self._pin.off()
        print(f"[wired] Shutter fired ({config.SHUTTER_HOLD_MS} ms pulse)")
