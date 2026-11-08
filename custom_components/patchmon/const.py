"""Constants for the PatchMon integration."""

from datetime import timedelta

DOMAIN = "patchmon"

CONF_TOKEN_KEY = "token_key"
CONF_TOKEN_SECRET = "token_secret"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
MIN_SCAN_INTERVAL_SECONDS = 60

CARD_URL_BASE = "/patchmon_static"
CARD_FILENAME = "patchmon-hosts-card.js"

# Keeps the sensor attribute a sensible size; the sensor state is still the full count.
MAX_PACKAGES_IN_ATTRIBUTES = 100
