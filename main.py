# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.9782b
Author: Alexandre "MoMo"
License: MIT
Description: 
    Specialized G-Code generator for grayscale laser engraving. 
    Optimized for Mach4 and PoKeys57CNC using M67 analog commands.
    Features: Constant velocity pre-moves (overscan), Gamma & Thermal 
    correction, and real-time power distribution preview.

GitHub: https://github.com/MoMo830/ALIG
"""

import json
import os
import customtkinter as ctk
from gui.main_window import LaserGeneratorApp
from utils.gui_utils import setup_app_id
from utils.config_manager import ConfigManager


def main():
    setup_app_id()
    
    config_manager = ConfigManager("alig_config.json")
    
    theme = config_manager.get_item("machine_settings", "theme", "System")
    ctk.set_appearance_mode(theme)
    
    # On définit le thème de couleur (Blue, Green, etc. - optionnel)
    ctk.set_default_color_theme("blue")

    app = LaserGeneratorApp(config_manager=config_manager)
    app.mainloop()

if __name__ == "__main__":
    main()