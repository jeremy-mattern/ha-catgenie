"""Constants for the CatGenie A.I. integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "catgenie"

CONF_COUNTRY_CODE: Final = "country_code"
CONF_PHONE: Final = "phone"
CONF_CODE: Final = "code"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_USER_ID: Final = "user_id"

DEFAULT_COUNTRY_CODE: Final = 1

# The device shadow updates within seconds of a state change; a one-minute poll
# keeps cleaning progress useful without hammering the vendor's cloud.
UPDATE_INTERVAL: Final = timedelta(seconds=60)

MANUFACTURER: Final = "PetNovations"
MODEL: Final = "CatGenie A.I."
