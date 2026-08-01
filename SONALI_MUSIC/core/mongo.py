from SONALI_MUSIC.core.json_db import JSONDatabase
from ..logging import LOGGER

LOGGER(__name__).info("Connecting to your Local JSON Database...")
try:
    mongodb = JSONDatabase()
    LOGGER(__name__).info("Connected to your Local JSON Database.")
except Exception as e:
    LOGGER(__name__).error(f"Failed to connect to your Local JSON Database: {e}")
    exit()
