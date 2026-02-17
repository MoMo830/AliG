"""
A.L.I.G. Project - config manager
------------------------------------
"""

import json
import os

def save_json_file(file_path, data):
    """Sauvegarde les données dans un fichier JSON."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True, None
    except Exception as e:
        return False, str(e)

def load_json_file(file_path):
    """Charge les données depuis un fichier JSON."""
    if not os.path.exists(file_path):
        return None, "File not found"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, str(e)