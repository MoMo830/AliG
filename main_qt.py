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

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPalette, QColor

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
        window.setWindowOpacity(0.0)
        
        def reveal_final():
            "fade-in / anti white flash"
            data = config_manager.get_section("window_settings")
            if data.get("is_maximized", False):
                window.showMaximized()
            else:
                window.show()
            
            window.setUpdatesEnabled(True)
            if hasattr(window, 'top_bar'):
                window.top_bar.setUpdatesEnabled(True)
            
            # Force le refresh de tous les widgets enfants
            for widget in window.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QWidget']).QWidget):
                widget.setUpdatesEnabled(True)
                widget.update()
            
            window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
            window.fade_anim.setDuration(150)          
            window.fade_anim.setStartValue(0.0)
            window.fade_anim.setEndValue(1.0)
            window.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic) 
            window.fade_anim.start()
            window.raise_()


        QTimer.singleShot(150, reveal_final)

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