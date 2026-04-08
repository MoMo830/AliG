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

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPalette, QColor

from core.config_manager import ConfigManager
from utils.gui_utils import setup_app_id
from gui.main_window_qt import MainWindowQt

IS_WINDOWS = sys.platform == "win32"


def show_fatal_error(message: str) -> None:
    """Affiche une erreur fatale de manière cross-platform."""
    if IS_WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "ALIG Qt - Fatal Error", 0x10)
    else:
        app = QApplication.instance() or QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("ALIG Qt - Fatal Error")
        msg.setText("Une erreur fatale s'est produite.")
        msg.setDetailedText(message)
        msg.exec()


def supports_window_opacity() -> bool:
    """
    Vérifie si le backend Qt supporte la transparence des fenêtres.

    - XCB (Linux X11) : non supporté sans composite manager → False
    - Wayland, Windows, macOS : supporté → True

    IMPORTANT : doit être appelé APRÈS QApplication.__init__().
    """
    app = QApplication.instance()
    if app is None:
        return False
    platform = app.platformName()
    # XCB = X11 classique. Wayland expose "wayland", Windows "windows", macOS "cocoa".
    return platform not in ("xcb",)


def main():
    try:
        setup_app_id()
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(base_dir, "alig_config.json")
        config_manager = ConfigManager(config_path)

        app = QApplication(sys.argv)

        # Détection APRÈS création de QApplication — platformName() est alors fiable.
        use_opacity = supports_window_opacity()

        window = MainWindowQt(controller=config_manager)

        # setUpdatesEnabled(False) masque le rendu initial sans toucher à l'opacité.
        # On ne touche JAMAIS à windowOpacity avant show() — cela génère des warnings
        # sur XCB (Linux) même quand use_opacity est False.
        window.setUpdatesEnabled(False)

        def reveal_final():
            data = config_manager.get_section("window_settings")
            if data.get("is_maximized", False):
                window.showMaximized()
            else:
                window.show()

            if use_opacity:
                # Opacité initialisée à 0 APRÈS show() — XCB ne se plaint plus
                window.setWindowOpacity(0.0)

            window.setUpdatesEnabled(True)

            if use_opacity:
                window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
                window.fade_anim.setDuration(250)
                window.fade_anim.setStartValue(0.0)
                window.fade_anim.setEndValue(1.0)
                window.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                window.fade_anim.start()
                window.raise_()
                window.fade_anim.finished.connect(
                    lambda: QTimer.singleShot(200, window._preload_raster_view))
            else:
                # Linux XCB ou tout backend sans opacity : affichage direct
                window.raise_()
                QTimer.singleShot(200, window._preload_raster_view)

        window.ui_ready.connect(reveal_final)

        sys.exit(app.exec())

    except Exception:
        error_message = traceback.format_exc()
        print("\n" + "="*50)
        print("SÉCURITÉ ALIG - ERREUR DÉTECTÉE")
        print("="*50)
        print(error_message)
        print("="*50 + "\n")
        show_fatal_error(error_message)


if __name__ == "__main__":
    main()