# -*- coding: utf-8 -*-
import sys
import os
import traceback
import ctypes

# Importations PyQt6
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


from utils.config_manager import ConfigManager
from utils.gui_utils import setup_app_id
from gui.main_window_qt import MainWindowQt

def main():
    try:
        # 1. Configuration initiale
        setup_app_id()
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(base_dir, "alig_config.json")
        config_manager = ConfigManager(config_path)

        # 2. Initialisation de l'application Qt
        app = QApplication(sys.argv)
        
        # 3. Lancement de la VRAIE fenêtre principale
        # On passe le config_manager pour qu'elle puisse charger la langue et la taille
        window = MainWindowQt(config_manager=config_manager)
        window.show()

        # 4. Boucle d'événements
        sys.exit(app.exec())

    except Exception:
        # 1. On récupère la trace complète de l'erreur
        error_message = traceback.format_exc()
        
        # 2. ON AJOUTE CECI : Affichage dans le terminal
        print("\n" + "="*50)
        print("SÉCURITÉ ALIG - ERREUR DÉTECTÉE")
        print("="*50)
        print(error_message)
        print("="*50 + "\n")

        # 3. Garde le message graphique pour ne pas que l'app disparaisse sans rien dire
        ctypes.windll.user32.MessageBoxW(0, error_message, "ALIG Qt - Fatal Error", 0x10)

if __name__ == "__main__":
    main()