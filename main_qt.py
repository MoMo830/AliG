# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.99b
Author: Alexandre "MoMo"
License: MIT
"""

import sys
import os
import traceback
import ctypes

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPalette, QColor

from core.config_manager import ConfigManager
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
        window.setWindowOpacity(0.0)

        # show() dès que ui_ready est émis (dashboard construit + thémé)
        def reveal_final():
            data = config_manager.get_section("window_settings")
            if data.get("is_maximized", False):
                window.showMaximized()
            else:
                window.show()
            window.setUpdatesEnabled(True)
            window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
            window.fade_anim.setDuration(250)
            window.fade_anim.setStartValue(0.0)
            window.fade_anim.setEndValue(1.0)
            window.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            window.fade_anim.start()
            window.raise_()
            # Précharger raster_view après l'animation — aucun impact visuel
            window.fade_anim.finished.connect(
                lambda: QTimer.singleShot(200, window._preload_raster_view))

        window.ui_ready.connect(reveal_final)

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