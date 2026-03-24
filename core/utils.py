"""
A.L.I.G. Project - Utils
------------------------------
"""

import os
import sys
from PIL import Image
import datetime
from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton, QFrame, QHBoxLayout, QVBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

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

        # --- 6. MISE À JOUR DES STATISTIQUES ---
        current_lines = int(config_manager.get_item("stats", "total_lines", 0))
        current_gcodes = int(config_manager.get_item("stats", "total_gcodes", 0))
        current_time = float(config_manager.get_item("stats", "total_time_seconds", 0.0))

        # Calcul des nouvelles valeurs
        new_lines = len(gcode_content.splitlines())
        
        # Conversion forcée en types Python natifs
        total_lines_updated = int(current_lines + new_lines)
        total_gcodes_updated = int(current_gcodes + 1)
        total_time_updated = float(current_time + float(estimated_time))
        
        # Enregistrement des données cumulées
        config_manager.set_item("stats", "total_lines", total_lines_updated)
        config_manager.set_item("stats", "total_gcodes", total_gcodes_updated)
        config_manager.set_item("stats", "total_time_seconds", total_time_updated)
        
        # Enregistrement du dernier projet
        config_manager.set_item("stats", "last_project_time", float(estimated_time))
        
        config_manager.save()
        
        return thumb_path

    except Exception as e:
        print(f"Error saving dashboard data: {e}")
        import traceback
        traceback.print_exc()
        return None


def ask_confirmation(parent, message, action_callback, danger_color="#8b0000"):
    """
    Crée une fenêtre de confirmation modale réutilisable.
    """
    # 1. RÉCUPÉRATION DE LA LANGUE
    config = getattr(parent, "config_manager", None)
    if not config and hasattr(parent, "app"):  # Si le parent est une View
        config = parent.app.config_manager

    lang = config.get_item("machine_settings", "language", "English") if config else "English"
    texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("common", {
        "confirm_title": "Confirmation",
        "confirm_subtitle": "This action is irreversible.",
        "btn_cancel": "Cancel",
        "btn_confirm": "Confirm"
    })

    # 2. CRÉATION DE LA DIALOG PYQT6
    dialog = QDialog(parent)
    dialog.setWindowTitle(texts.get("confirm_title", "Confirmation"))
    dialog.setFixedSize(300, 160)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

    # Centrage par rapport au parent
    parent_geo = parent.geometry()
    x = parent_geo.x() + (parent_geo.width() // 2) - 150
    y = parent_geo.y() + (parent_geo.height() // 2) - 80
    dialog.move(x, y)

    # 3. LAYOUT PRINCIPAL
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 20, 20, 15)
    layout.setSpacing(5)

    # Label message principal
    lbl_title = QLabel(message)
    font_title = QFont("Arial", 12)
    font_title.setBold(True)
    lbl_title.setFont(font_title)
    lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl_title.setWordWrap(True)
    layout.addWidget(lbl_title)

    # Label sous-titre
    lbl_subtitle = QLabel(texts.get("confirm_subtitle", "This action is irreversible."))
    lbl_subtitle.setFont(QFont("Arial", 10))
    lbl_subtitle.setStyleSheet("color: gray;")
    lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl_subtitle)

    layout.addSpacing(10)

    # 4. BOUTONS
    btn_frame = QFrame()
    btn_layout = QHBoxLayout(btn_frame)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.setSpacing(10)

    btn_cancel = QPushButton(texts.get("btn_cancel", "Cancel"))
    btn_cancel.setFixedWidth(100)
    btn_cancel.setStyleSheet("background-color: gray; color: white; border-radius: 4px; padding: 5px;")
    btn_cancel.clicked.connect(dialog.reject)

    btn_confirm = QPushButton(texts.get("btn_confirm", "Confirm"))
    btn_confirm.setFixedWidth(100)
    btn_confirm.setStyleSheet(
        f"background-color: {danger_color}; color: white; border-radius: 4px; padding: 5px;"
    )
    btn_confirm.clicked.connect(lambda: [action_callback(), dialog.accept()])

    btn_layout.addWidget(btn_cancel)
    btn_layout.addWidget(btn_confirm)
    layout.addWidget(btn_frame, alignment=Qt.AlignmentFlag.AlignCenter)

    dialog.exec()


def truncate_path(path, max_length=60):
    if not path or len(path) <= max_length:
        return path
    
    path = path.replace("\\", "/")
    
    # Gestion des chemins réseau (commençant par //)
    prefix = ""
    if path.startswith("//"):
        prefix = "//"
        path = path[2:]
    
    parts = path.split("/")
    filename = parts[-1]
    
    # On définit le début (Drive ou premier dossier)
    start_part = prefix + parts[0]
    
    # Si le nom de fichier lui-même est plus long que la limite
    if len(filename) >= max_length - 5:
        name_part, ext_part = (filename.rsplit('.', 1) + [""])[:2]
        if ext_part:
            ext_part = "." + ext_part
        
        remaining_space = max_length - len(start_part) - len(ext_part) - 5
        return f"{start_part}/...{name_part[-remaining_space:]}{ext_part}"

    # Tentative d'inclure le dossier parent si possible
    if len(parts) > 2:
        parent = parts[-2]
        if len(start_part) + len(parent) + len(filename) + 5 <= max_length:
            return f"{start_part}/.../{parent}/{filename}"
    
    # Sinon, simple Debut + ... + Fichier
    return f"{start_part}/.../{filename}"