import PyInstaller.__main__
import os

# Configuration
VERSION = "0.9782b"
EXE_NAME = f"ALIG_v{VERSION}"
ICON_PATH = os.path.join("assets", "icone_alig.ico")
MAIN_SCRIPT = "main.py"

PyInstaller.__main__.run([
    MAIN_SCRIPT,
    '--name=%s' % EXE_NAME,
    '--onefile',       # Un seul fichier .exe
    '--windowed',      # Pas de console noire au lancement
    f'--icon={ICON_PATH}',
    # On ajoute les dossiers importants (assets, gui, core, utils)
    '--add-data=assets;assets', 
    '--add-data=gui;gui',
    '--add-data=core;core',
    '--add-data=utils;utils',
    '--clean',
    '--noconfirm'
])