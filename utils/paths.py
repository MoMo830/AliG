from pathlib import Path
from PIL import Image
import os

# On récupère le chemin de "utils", puis on remonte d'un cran (parent)
# pour atteindre la racine du projet ALIG
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")


LOGO_ALIG = os.path.join(ASSETS_DIR, "logo_alig.ico")

HOME_DARK = Image.open(os.path.join(ASSETS_DIR, "home_white.png"))
HOME_LIGHT = Image.open(os.path.join(ASSETS_DIR, "home_black.png"))


RASTER_DARK=Image.open(os.path.join(ASSETS_DIR, "raster_white.png"))
RASTER_LIGHT=Image.open(os.path.join(ASSETS_DIR, "raster_black.png"))


LATENCY_DARK=Image.open(os.path.join(ASSETS_DIR, "latency_calibration_white.png"))
LATENCY_LIGHT=Image.open(os.path.join(ASSETS_DIR, "latency_calibration_black.png"))

LATENCY_EXPLAIN_DARK=Image.open(os.path.join(ASSETS_DIR, "latency_calibration_explain_white.png"))
LATENCY_EXPLAIN_LIGHT=Image.open(os.path.join(ASSETS_DIR, "latency_calibration_explain_black.png"))