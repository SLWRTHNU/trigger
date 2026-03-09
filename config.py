# =============================================================================
# Vibration Camera Trigger - Configuration
# =============================================================================
# Edit this file to match your hardware setup before flashing.

# --- Trigger Mode ---
# "wired"    : GPIO pin drives an optocoupler wired to the camera shutter port
# "wireless" : Pico W sends an HTTP request over WiFi to trigger the camera
TRIGGER_MODE = "wireless"

# --- Sensor Type ---
# "button"   : Momentary push-button (good for testing without a real sensor)
# "digital"  : SW-420 / FC-28 vibration module with digital output
# "adxl345"  : ADXL345 I2C accelerometer
SENSOR_TYPE = "button"

# GPIO pin for "button" and "digital" sensor types.
# Button  : wire one leg to this pin, other leg to GND (uses internal pull-up).
# SW-420  : connect module DO pin here.
SENSOR_PIN = 15

# ADXL345 over I2C ("adxl345" sensor type only)
I2C_SDA_PIN     = 4
I2C_SCL_PIN     = 5
# Acceleration magnitude threshold (m/s²) above which a trigger fires.
# Earth gravity is ~9.81 m/s².  Start around 1.0 and tune.
ACCEL_THRESHOLD = 1.5

# --- Debounce & Cooldown ---
# Minimum milliseconds between consecutive triggers to prevent burst firing.
COOLDOWN_MS = 500

# How long to hold the shutter signal / wireless request open (milliseconds).
SHUTTER_HOLD_MS = 100

# --- Wired Trigger (TRIGGER_MODE = "wired") ---
# GPIO pin that drives the optocoupler / shutter release circuit.
# HIGH = trigger active.
SHUTTER_PIN = 16

# --- Wireless Trigger (TRIGGER_MODE = "wireless") ---
# WiFi credentials
WIFI_SSID     = "YourNetworkSSID"
WIFI_PASSWORD = "YourNetworkPassword"

# Target URL to GET when the shutter fires.
# Examples:
#   Sony   : "http://192.168.122.1:10000/sony/camera/actTakePicture"
#   CHDK   : "http://192.168.0.1/control?cmd=shoot"
#   Custom : "http://192.168.1.50/trigger"
WIRELESS_URL = "http://192.168.1.100/trigger"

# Seconds to wait for the HTTP response before giving up.
HTTP_TIMEOUT = 3

# --- LED Feedback ---
# The Pico W on-board LED gives visual feedback.
# True  = LED mirrors sensor state (ON when vibration detected)
# False = LED blinks once per trigger event
LED_ALWAYS_ON_WHEN_ACTIVE = False
