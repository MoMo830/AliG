"""
A.L.I.G. Project - Utils
------------------------------
"""

import os
import sys
from PIL import Image
import datetime
import customtkinter as ctk

from core.translations import TRANSLATIONS

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
        base_path, app_path = get_app_paths()
        thumb_dir = os.path.join(app_path, "assets", "thumbnails")
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
        

def ask_confirmation(parent, message, action_callback, danger_color="#8b0000"):
    """
    Crée une fenêtre de confirmation modale réutilisable.
    """
    # 1. RÉCUPÉRATION DE LA LANGUE
    # On essaie de récupérer le manager via le parent (app)
    # Si parent n'a pas de config_manager, on se rabat sur l'Anglais par défaut
    config = getattr(parent, "config_manager", None)
    if not config and hasattr(parent, "app"): # Si le parent est une View
        config = parent.app.config_manager
        
    lang = config.get_item("machine_settings", "language", "English") if config else "English"
    # On récupère les textes de la section 'common' ou 'settings' selon votre structure
    texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("common", {
        "confirm_title": "Confirmation",
        "confirm_subtitle": "This action is irreversible.",
        "btn_cancel": "Cancel",
        "btn_confirm": "Confirm"
    })

    dialog = ctk.CTkToplevel(parent)
    dialog.title(texts.get("confirm_title", "Confirmation"))
    
    # ... (code de géométrie inchangé) ...
    width, height = 300, 160
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    dialog.attributes("-topmost", True)
    dialog.grab_set()
    dialog.resizable(False, False)

    # 2. APPLICATION DES TEXTES TRADUITS
    lbl_title = ctk.CTkLabel(dialog, text=message, font=("Arial", 14, "bold"), wraplength=250)
    lbl_title.pack(pady=(20, 5))
    
    lbl_subtitle = ctk.CTkLabel(dialog, text=texts.get("confirm_subtitle"), font=("Arial", 11), text_color="gray")
    lbl_subtitle.pack(pady=(0, 20))
    
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=10)
    
    btn_cancel = ctk.CTkButton(
        btn_frame, text=texts.get("btn_cancel"), width=100, fg_color="gray", 
        command=dialog.destroy
    )
    btn_cancel.pack(side="left", padx=10)
    
    btn_confirm = ctk.CTkButton(
        btn_frame, text=texts.get("btn_confirm"), width=100, fg_color=danger_color,
        command=lambda: [action_callback(), dialog.destroy()]
    )
    btn_confirm.pack(side="left", padx=10)