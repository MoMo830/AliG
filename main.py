# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.981b
Author: Alexandre "MoMo"
License: MIT
"""

import os
import sys
import traceback
import customtkinter as ctk
import ctypes

from gui.main_window import LaserGeneratorApp
from utils.gui_utils import setup_app_id
from utils.config_manager import ConfigManager
from utils.paths import load_all_images


def main():
    try:
        setup_app_id()
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(base_dir, "alig_config.json")
        config_manager = ConfigManager(config_path)

        theme = config_manager.get_item("machine_settings", "theme", "System")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")


        app = LaserGeneratorApp(config_manager=config_manager)


        app.mainloop()

    except Exception:
        error_message = traceback.format_exc()
        ctypes.windll.user32.MessageBoxW(
            0,
            error_message,
            "ALIG - Fatal Error",
            0x10
        )


if __name__ == "__main__":
    main()