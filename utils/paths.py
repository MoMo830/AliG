import os
import sys
import ctypes
from PIL import Image

# ==========================================================
#  Gestion universelle des chemins (Python + PyInstaller)
# ==========================================================

def get_base_path() -> str:
    """ Retourne la racine du projet (ALIG_Project) """
    if getattr(sys, 'frozen', False):
        # Chemin temporaire lors de l'exécution du .exe
        return sys._MEIPASS
    
    # paths.py est dans ALIG_Project/utils/
    # dirname(__file__) -> ALIG_Project/utils/
    # dirname(dirname(...)) -> ALIG_Project/ (Racine)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Racine du projet
BASE_DIR = get_base_path()

# Dossier source des icônes
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Dossier des miniatures (Gestion de l'écriture hors du .exe si besoin)
if getattr(sys, 'frozen', False):
    # En mode .exe, on crée Thumbnails à côté de l'exécutable pour qu'il persiste
    EXE_DIR = os.path.dirname(sys.executable)
    THUMBNAILS_DIR = os.path.join(EXE_DIR, "assets", "Thumbnails")
else:
    # En mode développement
    THUMBNAILS_DIR = os.path.join(ASSETS_DIR, "Thumbnails")

# Création automatique du répertoire Thumbnails si absent
if not os.path.exists(THUMBNAILS_DIR):
    try:
        os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    except Exception as e:
        print(f"Impossible de créer le dossier Thumbnails : {e}")

# ==========================================================
#  Chargement images sécurisé
# ==========================================================

def load_image(name: str):
    """ Charge une image depuis le dossier assets """
    image_path = os.path.join(ASSETS_DIR, name)

    if not os.path.exists(image_path):
        # Debug : affiche où il cherche exactement en cas d'erreur
        error_msg = f"Fichier introuvable : {image_path}"
        print(error_msg)
        raise FileNotFoundError(error_msg)

    return Image.open(image_path)

# ==========================================================
#  Variables globales (initialisées par load_all_images)
# ==========================================================

LOGO_ALIG = os.path.join(ASSETS_DIR, "logo_alig.ico")

HOME_DARK = None
HOME_LIGHT = None
RASTER_DARK = None
RASTER_LIGHT = None
LATENCY_DARK = None
LATENCY_LIGHT = None
LATENCY_EXPLAIN_DARK = None
LATENCY_EXPLAIN_LIGHT = None
LINESTEP_DARK = None
LINESTEP_LIGHT = None
POWER_COM = None


def load_all_images():
    global HOME_DARK, HOME_LIGHT, RASTER_DARK, RASTER_LIGHT
    global LATENCY_DARK, LATENCY_LIGHT, LATENCY_EXPLAIN_DARK, LATENCY_EXPLAIN_LIGHT
    global LINESTEP_DARK, LINESTEP_LIGHT, POWER_COM

    try:
        HOME_DARK = load_image("home_white.png")
        HOME_LIGHT = load_image("home_black.png")
        RASTER_DARK = load_image("raster_white.png")
        RASTER_LIGHT = load_image("raster_black.png")
        LATENCY_DARK = load_image("latency_calibration_white.png")
        LATENCY_LIGHT = load_image("latency_calibration_black.png")
        LATENCY_EXPLAIN_DARK = load_image("latency_calibration_explain_white.png")
        LATENCY_EXPLAIN_LIGHT = load_image("latency_calibration_explain_black.png")
        LINESTEP_DARK = load_image("linestep_calibration_white.png")
        LINESTEP_LIGHT = load_image("linestep_calibration_black.png")
        POWER_COM = load_image("power_calibration.png")


    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Erreur critique lors du chargement des ressources :\n\n{str(e)}",
            "Erreur Fatale ALIG",
            0x10
        )
        sys.exit(1)