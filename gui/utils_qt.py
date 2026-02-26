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