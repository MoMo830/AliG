import os
import sys
import subprocess

# Configuration
VERSION = "0.98b"
EXE_NAME = f"ALIG_v{VERSION}"
ICON_PATH = os.path.join("assets", "icone_alig.ico")
MAIN_SCRIPT = "main.py"

# Vérification de l'existence de l'icône
if not os.path.exists(ICON_PATH):
    print(f"Alerte : L'icône n'a pas été trouvée à : {ICON_PATH}")
    # On continue sans icône ou on quitte ? 
    # ICON_PATH = None 

# Commande de compilation
params = [
    'pyinstaller',
    '--name', EXE_NAME,
    '--onefile',
    '--windowed',
    '--clean',
    '--noconfirm',
    # Ajout des données (Syntaxe Windows avec ;)
    '--add-data', 'assets;assets',
    '--add-data', 'gui;gui',
    '--add-data', 'core;core',
    '--add-data', 'utils;utils',
    '--add-data', 'engine;engine' # N'oublie pas le dossier engine !
]

if os.path.exists(ICON_PATH):
    params.extend(['--icon', ICON_PATH])

params.append(MAIN_SCRIPT)

try:
    print(f"Lancement de la compilation de la version {VERSION}...")
    subprocess.check_call(params)
    print(f"Compilation terminée ! Ton fichier est dans le dossier 'dist'.")
except Exception as e:
    print(f"Erreur lors de la compilation : {e}")