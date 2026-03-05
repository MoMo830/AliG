import os
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QFrame, QProgressBar
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QSize, QPointF, QTimer


# ══════════════════════════════════════════════════════════════════
#  SVG / ICÔNES
# ══════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════
#  TRADUCTIONS
# ══════════════════════════════════════════════════════════════════

def translate_ui_widgets(widgets_map, translations):
    """
    Parcourt un dictionnaire { widget: clé_traduction }
    et applique les nouveaux textes.
    """
    for widget, key in widgets_map.items():
        text = translations.get(key)
        if not text:
            alt_key = f"label_{key}"
            text = translations.get(alt_key)

        if text:
            if key.startswith("sec_"):
                text = text.upper()

            if hasattr(widget, 'setText'):
                widget.setText(text)
            elif hasattr(widget, 'setPlaceholderText'):
                widget.setPlaceholderText(text)
            elif hasattr(widget, 'setToolTip'):
                widget.setToolTip(text)


# ══════════════════════════════════════════════════════════════════
#  LOADING OVERLAY (partagé Raster + Simulation)
# ══════════════════════════════════════════════════════════════════

def show_loading_overlay(parent_widget, message="Loading…"):
    """
    Affiche un overlay de chargement semi-transparent sur parent_widget.
    Retourne l'overlay (QWidget) — appeler overlay.hide() + deleteLater() pour l'effacer.
    """
    ov = QWidget(parent_widget)
    ov.setStyleSheet("background: rgba(20,20,20,210);")
    ov.resize(parent_widget.size())
    ov.show()
    ov.raise_()

    lo = QVBoxLayout(ov)
    lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

    box = QFrame()
    box.setFixedWidth(320)
    box.setStyleSheet(
        "QFrame{background:#3a3a3a;border-radius:12px;border:1px solid #555;}"
    )
    bl = QVBoxLayout(box)
    bl.setContentsMargins(30, 20, 30, 25)
    bl.setSpacing(12)

    lbl = QLabel(message)
    lbl.setStyleSheet(
        "color:white;font-size:14px;font-weight:bold;border:none;background:transparent;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bl.addWidget(lbl)

    pb = QProgressBar()
    pb.setFixedHeight(10)
    pb.setRange(0, 0)   # indéterminé
    pb.setStyleSheet(
        "QProgressBar{background:#555;border-radius:5px;border:none;}"
        "QProgressBar::chunk{background:#1F6AA5;border-radius:5px;}"
    )
    bl.addWidget(pb)
    lo.addWidget(box)

    # Référence interne pour le texte (pour pouvoir le changer plus tard si besoin)
    ov._message_label = lbl
    return ov


def hide_loading_overlay(overlay):
    """Masque et détruit l'overlay retourné par show_loading_overlay."""
    if overlay is not None:
        try:
            overlay.hide()
            overlay.deleteLater()
        except RuntimeError:
            pass


# ══════════════════════════════════════════════════════════════════
#  PAN / ZOOM MIXIN  (partagé Raster + Simulation)
# ══════════════════════════════════════════════════════════════════

class PanZoomMixin:
    """
    Mixin pour QWidget offrant zoom molette + pan clic-gauche/molette.

    Utilisation dans une sous-classe :
        class MyCanvas(PanZoomMixin, QWidget):
            def __init__(self):
                super().__init__()
                self.init_pan_zoom()          # initialiser l'état

            def paintEvent(self, e):
                qp = QPainter(self)
                self.apply_pan_zoom_transform(qp)
                # … dessiner …
                qp.end()

    Méthodes à surcharger pour hooks personnalisés :
        _on_pan_zoom_changed(self)  → appelé après chaque changement de vue
    """

    def init_pan_zoom(self, zoom_min=0.10, zoom_max=60.0, zoom_step=1.18):
        self._pz_zoom     = 1.0
        self._pz_pan      = QPointF(0.0, 0.0)
        self._pz_p0       = None          # point de départ du drag
        self._pz_p0_pan   = None
        self._pz_zoom_min = zoom_min
        self._pz_zoom_max = zoom_max
        self._pz_zoom_step = zoom_step

    # ── Applique la transformation au QPainter ──────────────────────────────

    def apply_pan_zoom_transform(self, painter):
        from PyQt6.QtGui import QTransform
        t = QTransform()
        t.translate(self._pz_pan.x(), self._pz_pan.y())
        t.scale(self._pz_zoom, self._pz_zoom)
        painter.setTransform(t)

    # ── Réinitialiser la vue ────────────────────────────────────────────────

    def reset_pan_zoom(self):
        self._pz_zoom = 1.0
        self._pz_pan  = QPointF(0.0, 0.0)
        self.update()
        self._on_pan_zoom_changed()

    # ── Zoom centré sur un point écran ─────────────────────────────────────

    def zoom_at(self, cx, cy, factor):
        wx = (cx - self._pz_pan.x()) / self._pz_zoom
        wy = (cy - self._pz_pan.y()) / self._pz_zoom
        self._pz_zoom = max(self._pz_zoom_min,
                            min(self._pz_zoom_max, self._pz_zoom * factor))
        self._pz_pan = QPointF(cx - wx * self._pz_zoom,
                               cy - wy * self._pz_zoom)
        self.update()
        self._on_pan_zoom_changed()

    # ── Événements Qt ──────────────────────────────────────────────────────

    def wheelEvent(self, e):
        factor = self._pz_zoom_step if e.angleDelta().y() > 0 else 1.0 / self._pz_zoom_step
        pos = e.position()
        self.zoom_at(pos.x(), pos.y(), factor)

    def mousePressEvent(self, e):
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._pz_p0     = e.pos()
            self._pz_p0_pan = QPointF(self._pz_pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._pz_p0 is not None:
            d = e.pos() - self._pz_p0
            self._pz_pan = self._pz_p0_pan + QPointF(d.x(), d.y())
            self.update()
            self._on_pan_zoom_changed()

    def mouseReleaseEvent(self, e):
        self._pz_p0 = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ── Hook optionnel ────────────────────────────────────────────────────

    def _on_pan_zoom_changed(self):
        """Surcharger dans la classe pour réagir aux changements de vue."""
        pass

    # ── Utilitaire : convertir coordonnées écran → monde ──────────────────

    def screen_to_world(self, sx, sy):
        """Retourne (wx, wy) en coordonnées monde (avant zoom/pan)."""
        wx = (sx - self._pz_pan.x()) / self._pz_zoom
        wy = (sy - self._pz_pan.y()) / self._pz_zoom
        return wx, wy

    def world_to_screen(self, wx, wy):
        """Retourne (sx, sy) en coordonnées écran."""
        sx = wx * self._pz_zoom + self._pz_pan.x()
        sy = wy * self._pz_zoom + self._pz_pan.y()
        return sx, sy


# ══════════════════════════════════════════════════════════════════
#  STYLE COMMUN DES DROPDOWNS  (partagé Settings + Raster)
# ══════════════════════════════════════════════════════════════════

def get_combo_stylesheet(arrow_path: str) -> str:
    """
    Retourne le stylesheet QComboBox standard du projet.
    arrow_path : chemin vers l'icône SVG de la flèche (peut être None pour le défaut Qt).
    """
    arrow_str = ""
    if arrow_path:
        safe = arrow_path.replace("\\", "/")
        arrow_str = f"""
            QComboBox::down-arrow {{
                image: url({safe});
                width: 12px;
                height: 8px;
            }}
        """
    return f"""
        QComboBox {{
            background-color: #1e1e1e;
            border: 1px solid #444;
            border-radius: 5px;
            padding: 3px 30px 3px 10px;
            color: white;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border: none;
            background: transparent;
        }}
        {arrow_str}
        QComboBox QAbstractItemView {{
            background-color: #1e1e1e;
            color: white;
            selection-background-color: #444;
            border: 1px solid #444;
        }}
    """
