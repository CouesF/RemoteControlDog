# RemoteControlDog/robot_dog_python/app/config.py
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Determine the project root directory assuming this file is in RemoteControlDog/robot_dog_python/app/
# PROJECT_ROOT_DIR will be RemoteControlDog/
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENV_PATH = os.path.join(PROJECT_ROOT_DIR, '.env')

# print(f"CONF: Attempting to load .env from: {ENV_PATH}")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    # logger.info(f"Successfully loaded .env from: {ENV_PATH}")
else:
    # logger.warning(f".env file not found at: {ENV_PATH}. Using default values.")
    print(f"CONF: .env file not found at: {ENV_PATH}. Using default values.")


RD_CLIENT_ID = os.getenv("RD_CLIENT_ID", "robot_dog_alpha")
CE_CLIENT_ID = os.getenv("CE_CLIENT_ID", "controller_main_default")
CS_HOST = os.getenv("TARGET_CS_HOST", "127.0.0.1")
CS_PORT = int(os.getenv("TARGET_CS_PORT", 9000))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", 70))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", 10))
STATUS_UPDATE_INTERVAL_S = float(os.getenv("STATUS_UPDATE_INTERVAL_S", 1.0))

# Unitree SDK specific (can be in .env too)
UNITREE_NETWORK_INTERFACE = os.getenv("UNITREE_NETWORK_INTERFACE", "enP8p1s0") # Default if not in .env

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = 'RDA:%(asctime)s - %(name)s - %(levelname)s - %(message)s' # RDA for Robot Dog App

def setup_logging():
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
    # Mute overly verbose libraries if necessary
    # logging.getLogger("some_library").setLevel(logging.WARNING)
    logger.info(f"Logging initialized with level {LOG_LEVEL}")

# Call setup_logging once when this module is imported if you want it globally configured early
# Or call it explicitly from your main application entry point.
# For now, let's assume it's called from the app.