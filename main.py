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

def load_user_theme():
    config_path = "alig_config.json" # Adaptez selon votre gestion de fichiers
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = json.load(f)
            return data.get("theme", "Dark") # "Dark" par défaut
    return "Dark"

def main():
    setup_app_id()
    theme = load_user_theme()
    ctk.set_appearance_mode(theme) 

    config_manager = ConfigManager("alig_config.json")    
    app = LaserGeneratorApp(config_manager=config_manager)
    app.mainloop()

if __name__ == "__main__":
    main()