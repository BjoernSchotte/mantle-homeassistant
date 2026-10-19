"""Constants of the Mantle integration."""

DOMAIN = "mantle"
CONF_URL = "url"
CONF_TOKEN = "token"
#: Hub events (`/api/live` topic `events:*`) are fired on the HA bus under this name.
EVENT = "mantle_event"
#: Dispatcher signals: one device's state changed / the hub connection came or went / a new TV appeared.
SIGNAL_STATE = "mantle_state_{}"
SIGNAL_AVAILABLE = "mantle_available_{}"
SIGNAL_NEW_DEVICE = "mantle_new_device_{}"
STATE_PREFIX = "hub.device."
