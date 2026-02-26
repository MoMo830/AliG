import os
import sys
import ctypes

# ==========================================================
#  Gestion universelle des chemins (Python + PyInstaller)
# ==========================================================

def get_base_path() -> str:
    """ Retourne la racine du projet (ALIG_Project) """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_path()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# ==========================================================
#  GESTION DU DOSSIER THUMBNAILS (Ecriture)
# ==========================================================
if getattr(sys, 'frozen', False):
    # En mode .exe, on crée Thumbnails à côté de l'exécutable (et pas dans le dossier temporaire)
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
#  CHEMINS DES RESSOURCES (Strings uniquement)
# ==========================================================

LOGO_ALIG = os.path.join(ASSETS_DIR, "logo_alig.ico")

# --- SVG (Icônes UI) ---
# On utilise un dictionnaire pour centraliser, c'est plus propre
SVG_ICONS = {
    "HOME": os.path.join(ASSETS_DIR, "home.svg"),
    "RASTER": os.path.join(ASSETS_DIR, "raster.svg"),
    "LATENCY": os.path.join(ASSETS_DIR, "latency_calibration.svg"),
    "LINESTEP": os.path.join(ASSETS_DIR, "linestep_calibration.svg"),
    "POWER": os.path.join(ASSETS_DIR, "power_calibration.svg"),
    "ARROW_DOWN": os.path.join(ASSETS_DIR, "arrow_down.svg"), # Ajouté ici
    "CIRCLE": os.path.join(ASSETS_DIR, "circle.svg"),
}

# --- PNG (Images d'explications / Previews) ---
EXPLAIN_PNG = {
    "LATENCY_DARK": os.path.join(ASSETS_DIR, "latency_calibration_explain_white.png"),
    "LINESTEP_DARK": os.path.join(ASSETS_DIR, "linestep_explain_white.png"),
    "POWER_DARK": os.path.join(ASSETS_DIR, "power_explain_white.png"),
    "LATENCY_LIGHT": os.path.join(ASSETS_DIR, "latency_calibration_explain_black.png"),
    "LINESTEP_LIGHT": os.path.join(ASSETS_DIR, "linestep_explain_black.png"),
    "POWER_LIGHT": os.path.join(ASSETS_DIR, "power_explain_black.png"),
}

# ==========================================================
#  VÉRIFICATION DES ASSETS
# ==========================================================
def check_assets():
    """ Vérifie la présence des fichiers critiques au démarrage """
    missing = []
    
    # 1. Vérifier tous les SVG
    for name, path in SVG_ICONS.items():
        if not os.path.exists(path):
            missing.append(f"Icône SVG: {name} ({os.path.basename(path)})")
            
    # 2. Vérifier tous les PNG d'explication
    for name, path in EXPLAIN_PNG.items():
        if not os.path.exists(path):
            missing.append(f"Image PNG: {name} ({os.path.basename(path)})")
            
    # 3. Vérifier les ressources isolées (Logo, etc.)
    if not os.path.exists(LOGO_ALIG):
        missing.append("Icône de l'application (logo_alig.ico)")

    if missing:
        msg = "Certains fichiers ressources sont introuvables :\n\n" + "\n".join(missing)
        # MessageBoxW pour une alerte Windows native avant même que l'interface ne charge
        ctypes.windll.user32.MessageBoxW(0, msg, "Erreur de Ressources", 0x10)