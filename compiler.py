import os
import sys
import subprocess
import shutil

# --- CONFIGURATION ---
VERSION = "0.98b"
EXE_NAME = f"ALIG_v{VERSION}"
MAIN_SCRIPT = "main.py"

# Use absolute paths to prevent "File Not Found" errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "assets", "logo_alig.ico")

def run_compilation():
    # 1. Cleaning old builds to avoid conflicts
    print("Cleaning old build and dist folders...")
    for folder in ['build', 'dist']:
        full_path = os.path.join(BASE_DIR, folder)
        if os.path.exists(full_path):
            try:
                shutil.rmtree(full_path)
            except Exception as e:
                print(f"Warning: Could not delete {folder}. Ensure the folder or EXE is not open.")

    # 2. Icon verification
    if not os.path.exists(ICON_PATH):
        print(f"ERROR: Icon not found at: {ICON_PATH}")
        print("Verify that the 'assets' folder is in the same directory as this script.")
        return

    # 3. Parameters construction
    # Note: os.pathsep is used for portability (; on Windows)
    params = [
        'pyinstaller',
        '--name', EXE_NAME,
        '--onefile',       # Un seul fichier .exe
        '--clean',
        '--noconfirm',
        '--windowed',      # Pas de console noire en arrière-plan
        
        # On n'ajoute que les fichiers de ressources (images, icônes)
        '--add-data', f'{os.path.join(BASE_DIR, "assets")}{os.pathsep}assets',

        # CustomTkinter a besoin de collect-all pour ses fichiers json/thèmes
        '--collect-all', 'customtkinter',

        # PIL est souvent nécessaire en hidden-import pour certaines versions de PyInstaller
        '--hidden-import', 'PIL.Image',
        '--hidden-import', 'PIL.ImageTk',

        '--icon', ICON_PATH,
        MAIN_SCRIPT
    ]

    # 4. Execution
    try:
        print(f"Starting ALIG {VERSION} compilation...")
        # Force execution in the script directory
        subprocess.check_call(params, cwd=BASE_DIR)
        
        print("\n" + "="*30)
        print(f"SUCCESS: The executable is available in the 'dist' folder.")
        print(f"File: {EXE_NAME}.exe")
        print("="*30)
        
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    # RECOMMENDATION: If using Synology Drive, copy the project to Desktop before running.
    run_compilation()