import os
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QSize

def get_svg_pixmap(svg_path, size=QSize(32, 32), color_hex=None):
    """Génère un Pixmap coloré à partir d'un SVG (Fonction universelle)"""
    if not svg_path or not os.path.exists(svg_path):
        return QPixmap()

    renderer = QSvgRenderer(svg_path)
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    renderer.render(painter)
    
    if color_hex:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color_hex))
    
    painter.end()
    return pixmap

def translate_ui_widgets(widgets_map, translations):
    """
    Parcourt un dictionnaire { widget: clé_traduction } 
    et applique les nouveaux textes.
    """
    for widget, key in widgets_map.items():
        # On cherche la traduction (on gère les variantes 'label_key' ou 'key')
        text = translations.get(key)
        if not text:
            alt_key = f"label_{key}"
            text = translations.get(alt_key)
            
        if text:
            # OPTIONNEL : Si c'est un titre de section (clé commençant par 'sec_'), on met en majuscules
            if key.startswith("sec_"):
                text = text.upper()
                
            # Application selon le type de widget
            if hasattr(widget, 'setText'):
                widget.setText(text)
            elif hasattr(widget, 'setPlaceholderText'):
                widget.setPlaceholderText(text)
            elif hasattr(widget, 'setToolTip'):
                widget.setToolTip(text)