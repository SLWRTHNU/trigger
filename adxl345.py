"""
Minimal ADXL345 I2C driver for MicroPython.

Only the features needed for vibration detection are implemented:
  - Full-resolution ±2 g / ±4 g / ±8 g / ±16 g range selection
  - Reading X, Y, Z acceleration in m/s²

Datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL345.pdf

Typical wiring to Pico 2 W (3.3 V logic):
  ADXL345  →  Pico 2 W
  VCC      →  3V3 (pin 36)
  GND      →  GND (pin 38)
  SDA      →  GP4  (or as set in config.py I2C_SDA_PIN)
  SCL      →  GP5  (or as set in config.py I2C_SCL_PIN)
  CS       →  3V3  (pull HIGH to select I2C mode)
  SDO/ALT  →  GND  (sets I2C address to 0x53)
              3V3  (sets I2C address to 0x1D)
"""

import struct

_ADDR_LOW  = 0x53   # SDO/ALT pulled LOW
_ADDR_HIGH = 0x1D   # SDO/ALT pulled HIGH

# Register addresses
_REG_DEVID      = 0x00
_REG_BW_RATE    = 0x2C
_REG_POWER_CTL  = 0x2D
_REG_DATA_FORMAT= 0x31
_REG_DATAX0     = 0x32

# Scale factors  (mg per LSB at full resolution)
_SCALE_MG = {2: 3.9, 4: 7.8, 8: 15.6, 16: 31.2}
_G_TO_MS2 = 9.80665


class ADXL345:
    """
    Simple ADXL345 driver.

    Parameters
    ----------
    i2c   : machine.I2C instance
    addr  : I2C address — 0x53 (default, SDO LOW) or 0x1D (SDO HIGH)
    range_g : measurement range in g — 2, 4, 8, or 16
    """

    def __init__(self, i2c, addr=_ADDR_LOW, range_g=2):
        self._i2c  = i2c
        self._addr = addr

        # Verify device ID
        devid = self._read_byte(_REG_DEVID)
        if devid != 0xE5:
            raise RuntimeError(
                f"ADXL345 not found at 0x{addr:02X} (got devid=0x{devid:02X})"
            )

        # Output data rate: 100 Hz (0x0A)
        self._write_byte(_REG_BW_RATE, 0x0A)

        # Set measurement range
        self.set_range(range_g)

        # Enable measurement mode
        self._write_byte(_REG_POWER_CTL, 0x08)

    # ------------------------------------------------------------------
    def set_range(self, range_g):
        """Set the measurement range: 2, 4, 8, or 16 g."""
        if range_g not in _SCALE_MG:
            raise ValueError(f"range_g must be 2, 4, 8, or 16 — got {range_g}")
        self._scale = _SCALE_MG[range_g] * _G_TO_MS2 / 1000.0
        bits = {2: 0x00, 4: 0x01, 8: 0x02, 16: 0x03}[range_g]
        # Full-resolution bit (3) set, plus range bits
        self._write_byte(_REG_DATA_FORMAT, 0x08 | bits)

    # ------------------------------------------------------------------
    @property
    def acceleration(self):
        """Return (ax, ay, az) in m/s²."""
        data = self._i2c.readfrom_mem(self._addr, _REG_DATAX0, 6)
        x, y, z = struct.unpack_from("<hhh", data)
        s = self._scale
        return x * s, y * s, z * s

    # ------------------------------------------------------------------
    def _read_byte(self, reg):
        return self._i2c.readfrom_mem(self._addr, reg, 1)[0]

    def _write_byte(self, reg, value):
        self._i2c.writeto_mem(self._addr, reg, bytes([value]))
