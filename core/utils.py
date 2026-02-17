"""
A.L.I.G. Project - Utils
------------------------------
"""

import os
import sys
from PIL import Image
import datetime

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

def save_dashboard_data(config_manager, matrix, gcode_content, estimated_time=0):
    """
    Gère la miniature et les stats (incluant le temps de simulation)
    """
    try:
        thumb_dir = "assets/thumbnails"
        os.makedirs(thumb_dir, exist_ok=True)

        # 1. Normalisation et Inversion
        mat = matrix.astype('float32')
        min_val, max_val = mat.min(), mat.max()
        if max_val > min_val:
            mat = (mat - min_val) / (max_val - min_val) * 255
        
        inverted_matrix = (255 - mat).astype('uint8')
        img_gray = Image.fromarray(inverted_matrix).convert("L")

        # 2. Redimensionnement proportionnel
        target_size = 150
        img_gray.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

        # 3. CRÉATION DU CANEVAS TRANSPARENT
        square_img = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
        img_rgba = img_gray.convert("RGBA")
        
        # 4. Centrage
        offset = ((target_size - img_rgba.size[0]) // 2, (target_size - img_rgba.size[1]) // 2)
        square_img.paste(img_rgba, offset)

        # 5. Sauvegarde en PNG
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        thumb_path = os.path.join(thumb_dir, f"thumb_{timestamp}.png")
        square_img.save(thumb_path, "PNG")

        # --- 6. MISE À JOUR DES STATISTIQUES (Correction ici) ---
        # On récupère les valeurs actuelles
        current_lines = int(config_manager.get_item("stats", "total_lines", 0))
        current_gcodes = int(config_manager.get_item("stats", "total_gcodes", 0))
        current_time = float(config_manager.get_item("stats", "total_time_seconds", 0.0))
        
        # Calcul des nouvelles valeurs
        new_lines = len(gcode_content.splitlines())
        
        # Enregistrement des données cumulées
        config_manager.set_item("stats", "total_lines", current_lines + new_lines)
        config_manager.set_item("stats", "total_gcodes", current_gcodes + 1)
        config_manager.set_item("stats", "total_time_seconds", current_time + estimated_time) # <--- AJOUT
        
        # Optionnel : Enregistrer aussi le temps du DERNIER projet pour le dashboard
        config_manager.set_item("stats", "last_project_time", estimated_time)
        
        config_manager.save()
        
        return thumb_path

    except Exception as e:
        print(f"Error saving dashboard data: {e}")
        return None
        