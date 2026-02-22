# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.9783b
Author: Alexandre "MoMo"
License: MIT
Description: 
    Specialized G-Code generator for grayscale laser engraving. 
    Optimized for Mach4 and PoKeys57CNC using M67 analog commands.
    Features: Constant velocity pre-moves (overscan), Gamma & Thermal 
    correction, and real-time power distribution preview.

GitHub: https://github.com/MoMo830/ALIG
"""

import os
import customtkinter as ctk
from gui.main_window import LaserGeneratorApp
from utils.gui_utils import setup_app_id
from utils.config_manager import ConfigManager
import ctypes


def main():
    setup_app_id()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "alig_config.json")
    config_manager = ConfigManager(config_path)
    
    theme = config_manager.get_item("machine_settings", "theme", "System")
    ctk.set_appearance_mode(theme)
    
    ctk.set_default_color_theme("blue")

    app = LaserGeneratorApp(config_manager=config_manager)
    app.mainloop()

if __name__ == "__main__":
    main()