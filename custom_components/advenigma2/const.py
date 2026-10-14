"""Constants for the Adv Enigma2 platform."""

DOMAIN = "advenigma2"

CONF_USE_CHANNEL_ICON = "use_channel_icon"
CONF_DEEP_STANDBY = "deep_standby"
CONF_SOURCE_BOUQUET = "source_bouquet"
CONF_MAC_ADDRESS = "mac_address"
CONF_SCREENSHOT_MODE = "screenshot_mode"
CONF_SCREENSHOT_FORMAT = "screenshot_format"
CONF_SCREENSHOT_RESOLUTION = "screenshot_resolution"

DEFAULT_NAME = "Adv Enigma2 Media Player"
DEFAULT_PORT = 80
DEFAULT_SSL = False
DEFAULT_USE_CHANNEL_ICON = False
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "dreambox"
DEFAULT_DEEP_STANDBY = False
DEFAULT_SOURCE_BOUQUET = ""
DEFAULT_MAC_ADDRESS = ""
DEFAULT_VERIFY_SSL = False
DEFAULT_SCREENSHOT_MODE = "all"
DEFAULT_SCREENSHOT_FORMAT = "jpg"
# 0 means the native resolution of the box
DEFAULT_SCREENSHOT_RESOLUTION = 720

# afterevent values of a timer
AFTEREVENT_STANDBY = 1
AFTEREVENT_DEEP_STANDBY = 2
AFTEREVENT_AUTO = 3

# sleep timer actions
SLEEP_TIMER_ACTIONS = ["standby", "shutdown"]

# screenshot modes and formats of OpenWebif
SCREENSHOT_MODES = ["all", "osd", "video", "pip", "lcd"]
SCREENSHOT_FORMATS = ["jpg", "png", "bmp"]
