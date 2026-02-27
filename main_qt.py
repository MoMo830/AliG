# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.981b
Author: Alexandre "MoMo"
License: MIT
"""

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
        setup_app_id()
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(base_dir, "alig_config.json")
        config_manager = ConfigManager(config_path)

        app = QApplication(sys.argv)
        
        window = MainWindowQt(controller=config_manager) 
        window.show()

        sys.exit(app.exec())

    except Exception:
        error_message = traceback.format_exc()
        print("\n" + "="*50)
        print("SÉCURITÉ ALIG - ERREUR DÉTECTÉE")
        print("="*50)
        print(error_message)
        print("="*50 + "\n")
        ctypes.windll.user32.MessageBoxW(0, error_message, "ALIG Qt - Fatal Error", 0x10)

if __name__ == "__main__":
    main()