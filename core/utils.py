"""
A.L.I.G. Project - Utils
------------------------------
"""

import os
import sys

def get_app_paths():
    """Détermine le chemin de base et le chemin d'exécution."""
    if getattr(sys, 'frozen', False):
        # Mode compilé (.exe)
        base_path = sys._MEIPASS
        app_path = os.path.dirname(sys.executable)
    else:
        # Mode script (.py)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = base_path
    
    return base_path, app_path