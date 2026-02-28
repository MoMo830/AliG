# -*- coding: utf-8 -*-
"""
A.L.I.G. - RasterView Qt Migration
Migré de CustomTkinter vers PyQt6
"""

import os
import sys
import json
import numpy as np
from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QComboBox,
    QCheckBox, QTabWidget, QScrollArea, QSplitter,
    QFileDialog, QMessageBox, QSizePolicy, QApplication,
    QPlainTextEdit, QButtonGroup
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QPoint, QPointF, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QImage, QPixmap,
    QLinearGradient, QPainterPath, QFontMetrics
)

from core.translations import TRANSLATIONS
from core.utils import get_app_paths
from core.config_manager import save_json_file, load_json_file
from engine.gcode_engine import GCodeEngine

from gui.switch import Switch


# ─────────────────────────────────────────────
#  WIDGETS UTILITAIRES 
# ─────────────────────────────────────────────

class ToolTip(QLabel):
    """Tooltip simple affiché au survol d'un widget."""
    def __init__(self, parent_widget, text):
        super().__init__(text)
        parent_widget.setToolTip(text)


class LoadingOverlay(QWidget):
    """Overlay de chargement semi-transparent."""
    def __init__(self, parent, text="Loading..."):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background-color: rgba(30,30,30,200);")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self.resize(parent.size())
        self.show()
        self.raise_()

    def resizeEvent(self, event):
        if self.parent():
            self.resize(self.parent().size())


class PowerRangeVisualizer(QWidget):
    """Visualiseur graphique de plage de puissance (remplace CTk version)."""
    def __init__(self, parent, entry_min, entry_max, update_callback):
        super().__init__(parent)
        self.entry_min = entry_min
        self.entry_max = entry_max
        self.update_callback = update_callback
        self.setFixedSize(80, 60)
        self.setToolTip("Power range visualizer")

    def refresh_visuals(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            v_min = float(self.entry_min.text() or 0)
            v_max = float(self.entry_max.text() or 100)
        except ValueError:
            v_min, v_max = 0, 100

        v_min = max(0, min(100, v_min))
        v_max = max(0, min(100, v_max))

        w, h = self.width(), self.height()
        bar_w = 20
        bar_h = h - 20
        y_base = h - 10

        # Fond
        painter.fillRect(0, 0, w, h, QColor("#1e1e1e"))

        # Barre min
        min_h = int((v_min / 100) * bar_h)
        min_x = w // 2 - bar_w - 5
        painter.fillRect(min_x, y_base - min_h, bar_w, min_h, QColor("#ffcc00"))

        # Barre max
        max_h = int((v_max / 100) * bar_h)
        max_x = w // 2 + 5
        painter.fillRect(max_x, y_base - max_h, bar_w, max_h, QColor("#ff4444"))

        # Labels
        painter.setPen(QColor("#888888"))
        font = QFont("Arial", 7)
        painter.setFont(font)
        painter.drawText(min_x, y_base + 12, "MIN")
        painter.drawText(max_x, y_base + 12, "MAX")


# class ToggleSwitch(QCheckBox):
#     """Switch on/off stylisé qui remplace CTkSwitch."""
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setStyleSheet("""
#             QCheckBox::indicator {
#                 width: 40px;
#                 height: 20px;
#                 border-radius: 10px;
#             }
#             QCheckBox::indicator:unchecked {
#                 background-color: #444444;
#                 border: 1px solid #555555;
#             }
#             QCheckBox::indicator:checked {
#                 background-color: #1f538d;
#                 border: 1px solid #2a6dbd;
#             }
#         """)


class SegmentedButton(QWidget):
    """Bouton segmenté (remplace CTkSegmentedButton)."""
    valueChanged = pyqtSignal(str)

    def __init__(self, values, parent=None):
        super().__init__(parent)
        self._values = values
        self._current = values[0] if values else ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._buttons = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for val in values:
            btn = QPushButton(val)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, v=val: self._on_clicked(v))
            self._group.addButton(btn)
            self._buttons[val] = btn
            layout.addWidget(btn)

        self._apply_styles()
        if values:
            self._buttons[values[0]].setChecked(True)

    def _apply_styles(self):
        base = """
            QPushButton {
                background-color: #3a3a3a;
                color: #aaaaaa;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #1f538d;
                color: white;
                border-color: #2a6dbd;
            }
            QPushButton:hover:!checked {
                background-color: #444444;
                color: white;
            }
        """
        for btn in self._buttons.values():
            btn.setStyleSheet(base)

    def _on_clicked(self, val):
        self._current = val
        self.valueChanged.emit(val)

    def set(self, val):
        if val in self._buttons:
            self._buttons[val].setChecked(True)
            self._current = val

    def get(self):
        return self._current


class HistogramWidget(QWidget):
    """Histogramme de distribution de puissance — remplace CTkCanvas."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._data = None
        self._v_min = 0
        self._v_max = 255
        self._title = "Power Distribution"
        self._label_power = "Power"
        self._label_dist = "%"

    def set_labels(self, title, power_label, dist_label):
        self._title = title
        self._label_power = power_label
        self._label_dist = dist_label

    def update_histogram(self, matrix, v_min, v_max):
        self._data = matrix
        self._v_min = v_min
        self._v_max = v_max
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#202020"))

        if self._data is None:
            painter.setPen(QColor("#444444"))
            painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # Marges
        left_m, right_m, top_m, bottom_m = 55, 30, 25, 45
        plot_w = w - left_m - right_m
        plot_h = h - top_m - bottom_m

        if plot_w < 10 or plot_h < 10:
            return

        # Titre
        painter.setPen(QColor("#ffffff"))
        font_title = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.drawText(QRect(0, 5, w, top_m - 5), Qt.AlignmentFlag.AlignCenter, self._title)

        # Axes
        axis_color = QColor("#555555")
        painter.setPen(QPen(axis_color, 1))
        painter.drawLine(left_m, top_m, left_m, top_m + plot_h)
        painter.drawLine(left_m, top_m + plot_h, left_m + plot_w, top_m + plot_h)

        # Calcul histogramme
        flat = self._data.ravel()[::10]
        total = flat.size
        if total == 0:
            return

        data_zero = flat[flat == 0]
        data_active = flat[flat > 0]

        bins = 60
        v_min, v_max = self._v_min, self._v_max
        counts, bin_edges = np.histogram(data_active, bins=bins, range=(v_min, v_max))
        counts_pct = (counts / total) * 100
        count_zero_pct = (data_zero.size / total) * 100

        real_max = np.max(counts_pct) if counts_pct.size > 0 else 0
        y_limit = max(10.0, float(np.ceil(real_max)))
        if y_limit % 2 != 0:
            y_limit += 1

        zero_zone_w = int(plot_w * 0.05)
        active_w = plot_w - zero_zone_w

        def scale_x(val):
            if v_max == v_min:
                return left_m + zero_zone_w
            return int(left_m + zero_zone_w + ((val - v_min) / (v_max - v_min)) * active_w)

        def scale_y(pct):
            ratio = min(pct / y_limit, 1.0)
            return int(top_m + plot_h - ratio * plot_h)

        # Barre OFF (orange)
        if count_zero_pct > 0:
            bar_h_off = scale_y(0) - scale_y(count_zero_pct)
            painter.fillRect(left_m + 2, scale_y(count_zero_pct), zero_zone_w - 4, bar_h_off, QColor("#EB984E"))
            painter.setPen(QColor("#EB984E"))
            font_s = QFont("Arial", 7, QFont.Weight.Bold)
            painter.setFont(font_s)
            painter.drawText(left_m + 2, top_m + plot_h + 12, "OFF")

        # Barres actives (bleues)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(len(counts_pct)):
            if counts_pct[i] <= 0:
                continue
            x0 = scale_x(bin_edges[i])
            x1 = scale_x(bin_edges[i + 1])
            y0 = scale_y(counts_pct[i])
            y_base = top_m + plot_h
            bar_w_px = max(1, x1 - x0 - 1)
            painter.fillRect(x0, y0, bar_w_px, y_base - y0, QColor("#5dade2"))

        # Lignes MIN / MAX
        min_px = scale_x(v_min)
        max_px = scale_x(v_max)
        pen_min = QPen(QColor("#ffcc00"), 1, Qt.PenStyle.DashLine)
        pen_max = QPen(QColor("#ff3333"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_min)
        painter.drawLine(min_px, top_m, min_px, top_m + plot_h)
        painter.setPen(pen_max)
        painter.drawLine(max_px, top_m, max_px, top_m + plot_h)

        font_xs = QFont("Arial", 7, QFont.Weight.Bold)
        painter.setFont(font_xs)
        painter.setPen(QColor("#ffcc00"))
        painter.drawText(min_px - 8, top_m + plot_h + 22, "MIN")
        painter.setPen(QColor("#ff3333"))
        painter.drawText(max_px - 8, top_m + plot_h + 22, "MAX")

        # Graduations Y
        painter.setFont(QFont("Arial", 7))
        painter.setPen(QColor("#888888"))
        for ratio in [0, 0.5, 1.0]:
            py = int(top_m + plot_h - ratio * plot_h)
            val_y = y_limit * ratio
            label = f"{int(val_y)}%" if val_y == int(val_y) else f"{val_y:.1f}%"
            painter.drawText(0, py + 4, left_m - 5, 12, Qt.AlignmentFlag.AlignRight, label)

        # Axe X label
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            QRect(left_m, h - 14, plot_w, 14),
            Qt.AlignmentFlag.AlignCenter,
            self._label_power
        )


class ImagePreviewWidget(QWidget):
    """Preview image avec QPainter — remplace Matplotlib imshow."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #1e1e1e;")

        self._pixmap = None
        self._matrix = None
        self._v_min = 0
        self._v_max = 255
        self._off_x = 0.0
        self._off_y = 0.0
        self._real_w = 0.0
        self._real_h = 0.0
        self._overscan_rects = []   # list of (x, y, w, h, label)
        self._origin_dot = None     # (x, y) en coordonnées mm
        self._placeholder = "Select an image to preview"
        self._show_colorbar = True

        # Transformation vue (zoom/pan)
        self._view_scale = 1.0
        self._view_offset = QPointF(0, 0)
        self._panning = False
        self._pan_start = QPoint()
        self.setMouseTracking(True)

    def set_placeholder(self, text):
        self._placeholder = text
        self.update()

    def update_image(self, matrix, off_x, off_y, real_w, real_h, v_min, v_max):
        self._matrix = matrix
        self._off_x = off_x
        self._off_y = off_y
        self._real_w = real_w
        self._real_h = real_h
        self._v_min = v_min
        self._v_max = v_max
        self._pixmap = self._matrix_to_pixmap(matrix, v_min, v_max)
        self.update()

    def set_overscan_rects(self, rects):
        """rects: list of (x_mm, y_mm, w_mm, h_mm, label)"""
        self._overscan_rects = rects
        self.update()

    def set_origin_dot(self, x_mm, y_mm):
        self._origin_dot = (x_mm, y_mm)
        self.update()

    def clear(self):
        self._pixmap = None
        self._matrix = None
        self._overscan_rects = []
        self._origin_dot = None
        self.update()

    def _matrix_to_pixmap(self, matrix, v_min, v_max):
        """Convertit numpy matrix en QPixmap niveaux de gris inversés."""
        if matrix is None:
            return None
        h, w = matrix.shape
        # Normalisation et inversion (gravure laser : 0=laser off = blanc)
        rng = v_max - v_min if v_max != v_min else 1
        normalized = np.clip((matrix.astype(np.float32) - v_min) / rng, 0, 1)
        gray = (normalized * 255).astype(np.uint8)
        # Inversion pour affichage cohérent
        gray_inv = 255 - gray
        # Créer QImage RGB
        rgb = np.stack([gray_inv, gray_inv, gray_inv], axis=2)
        h_, w_, ch = rgb.shape
        bytes_per_line = ch * w_
        qimg = QImage(rgb.tobytes(), w_, h_, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _mm_to_pixel(self, x_mm, y_mm, painter_rect):
        """Convertit coordonnées mm en pixels écran."""
        if self._real_w <= 0 or self._real_h <= 0:
            return QPointF(0, 0)

        # Zone de dessin (avec marges pour colorbar et axes)
        margin_left = 50
        margin_right = 60 if self._show_colorbar else 10
        margin_top = 10
        margin_bottom = 30

        draw_w = painter_rect.width() - margin_left - margin_right
        draw_h = painter_rect.height() - margin_top - margin_bottom

        # Étendue mm totale visible (image + overscan)
        x_min_mm = self._off_x + min(0, min((r[0] for r in self._overscan_rects), default=0))
        y_min_mm = self._off_y
        total_w_mm = self._real_w + abs(x_min_mm - self._off_x) + max(0, max(
            (r[0] + r[2] - (self._off_x + self._real_w) for r in self._overscan_rects), default=0))
        total_h_mm = self._real_h

        if total_w_mm <= 0 or total_h_mm <= 0:
            total_w_mm = self._real_w
            total_h_mm = self._real_h

        scale_x = draw_w / total_w_mm
        scale_y = draw_h / total_h_mm

        scale = min(scale_x, scale_y)

        # Centrage
        offset_x = margin_left + (draw_w - total_w_mm * scale) / 2
        offset_y = margin_top + (draw_h - total_h_mm * scale) / 2

        px = offset_x + (x_mm - x_min_mm) * scale
        py = offset_y + (self._real_h - (y_mm - y_min_mm)) * scale  # Y inversé
        return QPointF(px, py), scale

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#1e1e1e"))

        # Marges
        margin_left = 50
        margin_right = 60 if self._show_colorbar else 10
        margin_top = 10
        margin_bottom = 30
        draw_w = w - margin_left - margin_right
        draw_h = h - margin_top - margin_bottom

        # Placeholder si pas d'image
        if self._pixmap is None:
            painter.setPen(QColor("#444444"))
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            painter.drawText(
                QRect(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                self._placeholder
            )
            return

        # Calcul de l'échelle
        if self._real_w <= 0 or self._real_h <= 0:
            return

        # Étendue totale incluant overscan
        x_ranges = [self._off_x, self._off_x + self._real_w]
        y_ranges = [self._off_y, self._off_y + self._real_h]
        for rx, ry, rw, rh, _ in self._overscan_rects:
            x_ranges.extend([rx, rx + rw])
            y_ranges.extend([ry, ry + rh])

        x_min_mm = min(x_ranges)
        x_max_mm = max(x_ranges)
        y_min_mm = min(y_ranges)
        y_max_mm = max(y_ranges)

        total_w_mm = x_max_mm - x_min_mm
        total_h_mm = y_max_mm - y_min_mm

        if total_w_mm <= 0:
            total_w_mm = 1
        if total_h_mm <= 0:
            total_h_mm = 1

        # Padding visuel
        pad = 0.5
        x_min_mm -= pad
        x_max_mm += pad
        y_min_mm -= pad
        y_max_mm += pad
        total_w_mm = x_max_mm - x_min_mm
        total_h_mm = y_max_mm - y_min_mm

        scale_x = draw_w / total_w_mm
        scale_y = draw_h / total_h_mm
        scale = min(scale_x, scale_y)

        # Centrage dans la zone de dessin
        off_draw_x = margin_left + (draw_w - total_w_mm * scale) / 2
        off_draw_y = margin_top + (draw_h - total_h_mm * scale) / 2

        def to_px(x_mm, y_mm):
            px = off_draw_x + (x_mm - x_min_mm) * scale
            py = off_draw_y + (y_max_mm - y_mm) * scale  # Y inversé
            return QPointF(px, py)

        # ── Dessin de l'image ──
        img_tl = to_px(self._off_x, self._off_y + self._real_h)
        img_br = to_px(self._off_x + self._real_w, self._off_y)
        img_rect = QRect(
            int(img_tl.x()), int(img_tl.y()),
            int(img_br.x() - img_tl.x()), int(img_br.y() - img_tl.y())
        )
        painter.drawPixmap(img_rect, self._pixmap)

        # ── Grille cyan ──
        grid_pen = QPen(QColor(0, 255, 255, 80), 0.5)
        painter.setPen(grid_pen)
        n_lines = 8
        for i in range(n_lines + 1):
            frac = i / n_lines
            # Lignes verticales
            x_mm = x_min_mm + frac * total_w_mm
            p1 = to_px(x_mm, y_min_mm)
            p2 = to_px(x_mm, y_max_mm)
            painter.drawLine(p1, p2)
            # Lignes horizontales
            y_mm = y_min_mm + frac * total_h_mm
            p1 = to_px(x_min_mm, y_mm)
            p2 = to_px(x_max_mm, y_mm)
            painter.drawLine(p1, p2)

        # ── Zones overscan ──
        for rx, ry, rw, rh, label in self._overscan_rects:
            tl = to_px(rx, ry + rh)
            br = to_px(rx + rw, ry)
            
            # Calcul du rectangle en pixels
            px_x = int(tl.x())
            px_y = int(tl.y())
            px_w = int(br.x() - tl.x())
            px_h = int(br.y() - tl.y())
            rect_px = QRect(px_x, px_y, px_w, px_h)

            # 1. Dessin du fond et de la bordure (inchangé)
            painter.fillRect(rect_px, QColor(52, 152, 219, 40))
            pen_dashed = QPen(QColor("#3498db"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_dashed)
            painter.drawRect(rect_px)

            # 2. Dessin du Label avec Rotation
            painter.save() # Indispensable pour ne pas faire pivoter toute l'interface
            
            painter.setPen(QColor("#3498db"))
            font = QFont("Arial", 7, QFont.Weight.Bold)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            
            # On se place au centre du rectangle
            cx = px_x + px_w / 2
            cy = px_y + px_h / 2
            painter.translate(cx, cy)

            # Logique de rotation selon le label
            # (On suppose que tu as utilisé "OVERSCAN_90" et "OVERSCAN_-90" dans l'étape précédente)
            if label == "OVERSCAN_90":
                painter.rotate(90)
            elif label == "OVERSCAN_-90":
                painter.rotate(-90)
            # Si c'est juste "OVERSCAN" (mode vertical), on ne pivote pas ou peu
            
            # Dessin du texte "OVERSCAN" (ou la valeur de label) centré sur (0,0)
            # On nettoie le nom pour l'affichage si besoin
            display_text = "OVERSCAN" 
            
            tw = metrics.horizontalAdvance(display_text)
            th = metrics.ascent()
            
            # On centre le texte : -largeur/2 et hauteur/2
            painter.drawText(-tw // 2, th // 2 - 2, display_text)
            
            painter.restore() # On revient à l'état normal

        # ── Rectangle overscan global pointillé ──
        all_x_min = min((r[0] for r in self._overscan_rects), default=self._off_x)
        all_y_min = min((r[1] for r in self._overscan_rects), default=self._off_y)
        all_x_max = max((r[0] + r[2] for r in self._overscan_rects), default=self._off_x + self._real_w)
        all_y_max = max((r[1] + r[3] for r in self._overscan_rects), default=self._off_y + self._real_h)

        if self._overscan_rects:
            tl_g = to_px(all_x_min, all_y_max)
            br_g = to_px(all_x_max, all_y_min)
            global_rect = QRect(int(tl_g.x()), int(tl_g.y()), int(br_g.x() - tl_g.x()), int(br_g.y() - tl_g.y()))
            pen_global = QPen(QColor("#3498db"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen_global)
            painter.drawRect(global_rect)

        # ── Point d'origine (0,0) ──
        origin_px = to_px(0, 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ff0000")))
        painter.drawEllipse(origin_px, 5, 5)

        # ── Axes graduations ──
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Arial", 8))
        n_ticks = 5
        for i in range(n_ticks + 1):
            frac = i / n_ticks
            # X
            x_mm_val = x_min_mm + frac * total_w_mm
            px_pos = to_px(x_mm_val, y_min_mm)
            painter.drawText(
                QRect(int(px_pos.x()) - 20, int(off_draw_y + draw_h + 2), 40, 14),
                Qt.AlignmentFlag.AlignCenter,
                f"{x_mm_val:.1f}"
            )
            # Y
            y_mm_val = y_min_mm + frac * total_h_mm
            py_pos = to_px(x_min_mm, y_mm_val)
            painter.drawText(
                QRect(0, int(py_pos.y()) - 6, margin_left - 4, 12),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{y_mm_val:.1f}"
            )

        # ── Colorbar Intégrée ──
        if self._show_colorbar:
            # Récupérer la largeur réelle du widget pour rester relatif au bord droit
            w = self.width()
            
            # Paramètres ajustables
            cbar_w = 40  # On élargit encore un peu pour la 4K
            margin_right = 80 # Espace réservé depuis le bord droit de la fenêtre
            
            cbar_x = w - margin_right
            cbar_y = margin_top
            cbar_h = draw_h

            # 1. Dégradé (Bas = Blanc, Haut = Noir)
            grad = QLinearGradient(0, cbar_y + cbar_h, 0, cbar_y)
            grad.setColorAt(0.0, QColor(255, 255, 255)) 
            grad.setColorAt(1.0, QColor(0, 0, 0))

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor("#444444"), 2)) # Bordure plus épaisse en 4K
            painter.drawRoundedRect(cbar_x, cbar_y, cbar_w, cbar_h, 5, 5)

            # 2. Textes Min/Max (Placés à GAUCHE de la barre)
            # On augmente la taille de la police pour la 4K
            font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            
            painter.setPen(QColor("#AAAAAA"))
            txt_max = f"{int(self._v_max)}"
            txt_min = f"{int(self._v_min)}"
            
            # Positionnement à gauche de la barre avec une marge de 10px
            painter.drawText(cbar_x - metrics.horizontalAdvance(txt_max) - 10, 
                             cbar_y + metrics.ascent(), txt_max)
            painter.drawText(cbar_x - metrics.horizontalAdvance(txt_min) - 10, 
                             cbar_y + cbar_h, txt_min)

            # 3. TEXTE "POWER" AU CENTRE (Correction de visibilité)
            common_dict = getattr(self.parent(), 'common', {})
            label_text = common_dict.get("power_pct", "POWER (%)")
            painter.save()
            painter.setPen(QColor(255, 255, 255))
            
            # Centre exact de la barre
            cx = cbar_x + (cbar_w / 2)
            cy = cbar_y + (cbar_h / 2)
            
            painter.translate(cx, cy)
            painter.rotate(-90)
            
            # Couleur contrastée pour être visible sur le dégradé
            # On utilise un gris qui tranche (150, 150, 150)
            painter.setPen(QColor(250, 150, 150))
            
            tw = metrics.horizontalAdvance(label_text)
            th = metrics.ascent()
            
            # Dessin centré : -largeur/2 et hauteur/2
            # th // 2 permet d'équilibrer le texte sur la ligne de base
            painter.drawText(-tw // 2, th // 2, label_text)
            
            painter.restore()

        painter.end()


    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._view_scale *= (1.1 if delta > 0 else 0.9)
        self._view_scale = max(0.5, min(10.0, self._view_scale))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._view_offset += QPointF(delta.x(), delta.y())
            self._pan_start = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False


# ─────────────────────────────────────────────
#  RASTER VIEW PRINCIPALE
# ─────────────────────────────────────────────

class RasterViewQt(QWidget):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller   # MainWindowQt
        self.app = controller          # Alias de compatibilité

        lang = self.controller.config_manager.get_item("machine_settings", "language")
        if not lang or lang not in TRANSLATIONS:
            lang = "English"

        self.common = TRANSLATIONS[lang]["common"]
        self.stats_texts = TRANSLATIONS[lang]["stats"]
        self.origin_translations = TRANSLATIONS[lang]["origin_options"]

        self.version = getattr(self.controller, "version", "Qt")

        self._after_id = None   # QTimer handle
        self.engine = GCodeEngine()

        self.base_path, self.application_path = get_app_paths()
        self.input_image_path = ""
        self.output_dir = self.application_path

        self.controls = {}
        self._last_matrix = None
        self._last_geom = None
        self.estimated_file_size = "N/A"
        self._estimated_time = 0

        self.is_locked = True

        # Variables état
        self._raster_dir = "horizontal"
        self._invert = False
        self._force_width = False
        self._origin_pointer = False
        self._include_frame = False

        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        self._setup_ui()
        self._load_settings()

        # Rendu initial
        if self.input_image_path and os.path.exists(self.input_image_path):
            self.loading_overlay = LoadingOverlay(self, text="Loading...")
            QTimer.singleShot(250, self._initial_render)
        else:
            QTimer.singleShot(0, self.update_preview)

    def _initial_render(self):
        try:
            self.update_preview()
        finally:
            if hasattr(self, "loading_overlay"):
                self.loading_overlay.hide()
                self.loading_overlay.deleteLater()

    # ─────────────────────────────────────────
    #  SETUP UI PRINCIPAL
    # ─────────────────────────────────────────

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ── SIDEBAR GAUCHE ──
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(390)
        self.sidebar.setStyleSheet("QFrame { background-color: #2b2b2b; }")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_layout.setSpacing(5)

        # Fichiers
        self._build_file_frame(sidebar_layout)
        # Profils
        self._build_profile_frame(sidebar_layout)
        # Onglets
        self._build_tabs(sidebar_layout)
        # Bouton simuler
        self.btn_gen = QPushButton(self.common.get("simulate_gcode", "Simulate G-Code"))
        self.btn_gen.setFixedHeight(50)
        self.btn_gen.setStyleSheet("""
            QPushButton {
                background-color: #1f538d;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2a6dbd; }
            QPushButton:pressed { background-color: #17406e; }
        """)
        self.btn_gen.clicked.connect(self.generate_gcode)
        sidebar_layout.addWidget(self.btn_gen)

        main_layout.addWidget(self.sidebar)

        # ── VIEWPORT DROIT ──
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        # Preview image
        self.image_preview = ImagePreviewWidget()
        self.image_preview.set_placeholder(self.common.get("choose_image", "Select an image to preview"))
        right_layout.addWidget(self.image_preview, stretch=3)

        # Stats + Histogramme
        self._build_stats_panel(right_layout)

        main_layout.addWidget(right_widget, stretch=1)

    # ─────────────────────────────────────────
    #  FICHIERS
    # ─────────────────────────────────────────

    def _build_file_frame(self, parent_layout):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #333333; border-radius: 6px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        self.btn_input = QPushButton(self.common.get("select_image", "Select Image"))
        self.btn_input.setFixedHeight(32)
        self.btn_input.setStyleSheet(self._btn_style())
        self.btn_input.clicked.connect(self.select_input)
        layout.addWidget(self.btn_input)

        self.btn_output = QPushButton(self.common.get("select_output", "Select Output"))
        self.btn_output.setFixedHeight(32)
        self.btn_output.setStyleSheet(self._btn_style())
        self.btn_output.clicked.connect(self.select_output)
        layout.addWidget(self.btn_output)

        parent_layout.addWidget(frame)

    def _build_profile_frame(self, parent_layout):
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        btn_load = QPushButton(self.common.get("import_profile", "Import Profile"))
        btn_load.setFixedHeight(28)
        btn_load.setStyleSheet(self._btn_style(color="#444444"))
        btn_load.clicked.connect(self.load_profile_from)
        layout.addWidget(btn_load)

        btn_save = QPushButton(self.common.get("export_profile", "Export Profile"))
        btn_save.setFixedHeight(28)
        btn_save.setStyleSheet(self._btn_style(color="#444444"))
        btn_save.clicked.connect(self.export_profile)
        layout.addWidget(btn_save)

        parent_layout.addWidget(frame)

    # ─────────────────────────────────────────
    #  ONGLETS
    # ─────────────────────────────────────────

    def _build_tabs(self, parent_layout):
        self.tabview = QTabWidget()
        self.tabview.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #3a3a3a;
                color: #aaaaaa;
                padding: 5px 12px;
                border: none;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #1f538d;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #444444;
                color: white;
            }
        """)

        self.tab_geom_name = self.common.get("geometry", "Geometry")
        self.tab_img_name = self.common.get("image", "Image")
        self.tab_laser_name = self.common.get("laser", "Laser")
        self.tab_gcode_name = self.common.get("gcode", "G-Code")

        tab_geom = self._make_scroll_tab()
        tab_img = self._make_scroll_tab()
        tab_laser = self._make_scroll_tab()
        tab_gcode = self._make_scroll_tab()

        self.tabview.addTab(tab_geom["widget"], self.tab_geom_name)
        self.tabview.addTab(tab_img["widget"], self.tab_img_name)
        self.tabview.addTab(tab_laser["widget"], self.tab_laser_name)
        self.tabview.addTab(tab_gcode["widget"], self.tab_gcode_name)

        self._setup_tab_geometry(tab_geom["layout"])
        self._setup_tab_image(tab_img["layout"])
        self._setup_tab_laser(tab_laser["layout"])
        self._setup_tab_gcode(tab_gcode["layout"])

        parent_layout.addWidget(self.tabview, stretch=1)

    def _make_scroll_tab(self):
        """Crée un onglet avec QScrollArea interne."""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { width: 8px; background: #2b2b2b; }
            QScrollBar::handle:vertical { background: #555555; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #1f538d; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        return {"widget": container, "layout": layout}

    # ─────────────────────────────────────────
    #  TAB GÉOMÉTRIE
    # ─────────────────────────────────────────

    def _setup_tab_geometry(self, layout):
        # Insérer avant le stretch final
        layout.insertWidget(layout.count() - 1, self._make_label(self.common.get("raster_mode", "Raster Mode")))

        self._raster_map = {
            "horizontal": self.common.get("horizontal", "Horizontal"),
            "vertical": self.common.get("vertical", "Vertical")
        }
        self._raster_map_inv = {v: k for k, v in self._raster_map.items()}

        self.raster_dir_btn = SegmentedButton(list(self._raster_map.values()))
        self.raster_dir_btn.set(self._raster_map["horizontal"])
        self.raster_dir_btn.valueChanged.connect(self._on_raster_dir_change)
        layout.insertWidget(layout.count() - 1, self.raster_dir_btn)

        self.width_label_widget = self._insert_input_pair(
            layout, self.common.get("target_width", "Target Width"), 5, 400, 30.0, "width"
        )

        # Force width
        self.sw_force_width = self.create_switch(
            layout=layout, 
            label_key=self.common.get("force_width", "Force Width"), 
            key="force_width"
        )
        
        self.sw_force_width.stateChanged.connect(lambda: QTimer.singleShot(10, self.update_preview))
        
        row_widget = layout.itemAt(layout.count() - 2).widget() 
        self.force_w_label = row_widget.findChild(QLabel)

        self._insert_input_pair(layout, self.common.get("line_step", "Line Step"), 0.01, 1.0, 0.1307, "line_step", precision=4)
        self._insert_input_pair(layout, self.common.get("dpi_resolution", "DPI"), 10, 1200, 254, "dpi", is_int=True)

        # Origin mode
        ORIGIN_KEYS = ["Lower-Left", "Upper-Left", "Lower-Right", "Upper-Right", "Center", "Custom"]
        options = [(k, self.origin_translations.get(k, k)) for k in ORIGIN_KEYS]
        self._insert_dropdown(layout, self.common.get("origin_point", "Origin"), options, "origin_mode")

        # Custom offset
        self.custom_offset_frame = QFrame()
        co_layout = QHBoxLayout(self.custom_offset_frame)
        co_layout.setContentsMargins(0, 0, 0, 0)
        self._insert_simple_input_into(co_layout, self.common.get("custom_offset_x", "X"), 0.0, "custom_x")
        self._insert_simple_input_into(co_layout, self.common.get("custom_offset_y", "Y"), 0.0, "custom_y")
        self.custom_offset_frame.setVisible(False)
        layout.insertWidget(layout.count() - 1, self.custom_offset_frame)

    # ─────────────────────────────────────────
    #  TAB IMAGE
    # ─────────────────────────────────────────

    def _setup_tab_image(self, layout):
        self._insert_input_pair(layout, self.common.get("contrast", "Contrast"), -1.0, 1.0, 0.0, "contrast")
        self._insert_input_pair(layout, self.common.get("gamma", "Gamma"), 0.1, 6.0, 1.0, "gamma")
        self._insert_input_pair(layout, self.common.get("thermal", "Thermal"), 0.1, 3.0, 1.5, "thermal")

        # Utilisation de la méthode centralisée pour l'inversion des couleurs
        self.sw_invert = self.create_switch(
            layout=layout, 
            label_key=self.common.get("invert_color", "Invert Colors"), 
            key="invert"
        )
        
        # Connexion directe pour rafraîchir la preview lors du basculement
        self.sw_invert.stateChanged.connect(self.update_preview)

    # ─────────────────────────────────────────
    #  TAB LASER
    # ─────────────────────────────────────────

    def _setup_tab_laser(self, layout):
        self._insert_input_pair(layout, self.common.get("feedrate", "Feedrate"), 500, 20000, 3000, "feedrate", is_int=True)
        self._insert_input_pair(layout, self.common.get("overscan", "Overscan"), 0, 50, 10.0, "premove")

        # Min/Max power + visualiseur
        p_frame = QFrame()
        p_frame.setStyleSheet("background: transparent;")
        p_outer = QHBoxLayout(p_frame)
        p_outer.setContentsMargins(0, 0, 0, 0)

        p_inputs_widget = QWidget()
        p_inputs_layout = QVBoxLayout(p_inputs_widget)
        p_inputs_layout.setContentsMargins(0, 0, 0, 0)
        p_inputs_layout.setSpacing(4)
        self._insert_simple_input_into(p_inputs_layout, self.common.get("max_power", "Max Power"), 40.0, "max_p")
        self._insert_simple_input_into(p_inputs_layout, self.common.get("min_power", "Min Power"), 10.0, "min_p")
        p_outer.addWidget(p_inputs_widget)

        self.power_viz = PowerRangeVisualizer(
            p_frame,
            self.controls.get("min_p", {}).get("entry"),
            self.controls.get("max_p", {}).get("entry"),
            self.update_preview
        )
        p_outer.addWidget(self.power_viz)
        layout.insertWidget(layout.count() - 1, p_frame)

        self._insert_input_pair(layout, self.common.get("laser_latency", "Laser Latency"), -20, 20, 0, "m67_delay")
        self._insert_input_pair(layout, self.common.get("gray_steps", "Gray Steps"), 2, 256, 256, "gray_steps", is_int=True)

    # ─────────────────────────────────────────
    #  TAB G-CODE
    # ─────────────────────────────────────────

    def _setup_tab_gcode(self, layout):
        # Machine params (verrouillés)
        global_frame = QFrame()
        global_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: transparent;
            }
        """)
        gf_layout = QVBoxLayout(global_frame)
        gf_layout.setContentsMargins(8, 6, 8, 6)
        gf_layout.setSpacing(5)

        # Header verrou
        header_row = QWidget()
        header_row.setStyleSheet("border: none; background: transparent;")
        header_row_layout = QHBoxLayout(header_row)
        header_row_layout.setContentsMargins(0, 0, 0, 0)
        lbl_global = QLabel(self.common.get("global_machine_params", "Machine Parameters"))
        lbl_global.setStyleSheet("color: #FF9500; font-weight: bold; font-size: 11px; border: none;")
        header_row_layout.addWidget(lbl_global)
        header_row_layout.addStretch()
        self.lock_btn = QPushButton("🔒")
        self.lock_btn.setFixedSize(30, 25)
        self.lock_btn.setStyleSheet("""
            QPushButton { background-color: #444444; border-radius: 4px; font-size: 13px; border: none; }
            QPushButton:hover { background-color: #666666; }
        """)
        self.lock_btn.clicked.connect(self.toggle_machine_lock)
        header_row_layout.addWidget(self.lock_btn)
        gf_layout.addWidget(header_row)

        # Container paramètres machine
        self.machine_controls_container = QWidget()
        self.machine_controls_container.setStyleSheet("background: transparent; border: none;")
        mc_layout = QVBoxLayout(self.machine_controls_container)
        mc_layout.setContentsMargins(0, 0, 0, 0)
        mc_layout.setSpacing(4)

        self._insert_dropdown_into(mc_layout, self.common.get("cmd_mode", "Command Mode"),
                                   ["M67 (Analog)", "S (Spindle)"], "cmd_mode")

        em_row = QHBoxLayout()
        self._insert_simple_input_into(em_row, self.common.get("m67_output", "M67 Output E"), 0, "m67_e_num", precision=0)
        self._insert_simple_input_into(em_row, self.common.get("ctrl_max_value", "Controller Max"), 100, "ctrl_max", precision=0)
        mc_layout.addLayout(em_row)

        self._insert_dropdown_into(mc_layout, self.common.get("firing_mode", "Firing Mode"),
                                   ["M3/M5", "M4/M5"], "firing_mode")

        gf_layout.addWidget(self.machine_controls_container)
        layout.insertWidget(layout.count() - 1, global_frame)

        self.apply_lock_state()

        # Header preview (lecture seule)
        h_lbl = QLabel(self.common.get("gcode_header", "G-Code Header"))
        h_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        layout.insertWidget(layout.count() - 1, h_lbl)

        self.txt_global_header_preview = QPlainTextEdit()
        self.txt_global_header_preview.setFixedHeight(30)
        self.txt_global_header_preview.setPlainText("(Machine Settings Header...)")
        self.txt_global_header_preview.setReadOnly(True)
        self.txt_global_header_preview.setStyleSheet("""
            QPlainTextEdit { background: #222222; color: #666666; border: none;
                             font-family: Consolas; font-size: 10px; }
        """)
        layout.insertWidget(layout.count() - 1, self.txt_global_header_preview)

        self.txt_header = QPlainTextEdit()
        self.txt_header.setFixedHeight(50)
        self.txt_header.setStyleSheet("""
            QPlainTextEdit { background: #333333; color: white; border: 1px solid #444444;
                             font-family: Consolas; font-size: 11px; border-radius: 4px; }
        """)
        layout.insertWidget(layout.count() - 1, self.txt_header)

        # Footer preview
        f_lbl = QLabel(self.common.get("gcode_footer", "G-Code Footer"))
        f_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        layout.insertWidget(layout.count() - 1, f_lbl)

        self.txt_global_footer_preview = QPlainTextEdit()
        self.txt_global_footer_preview.setFixedHeight(30)
        self.txt_global_footer_preview.setPlainText("(Machine Settings Footer...)")
        self.txt_global_footer_preview.setReadOnly(True)
        self.txt_global_footer_preview.setStyleSheet("""
            QPlainTextEdit { background: #222222; color: #666666; border: none;
                             font-family: Consolas; font-size: 10px; }
        """)
        layout.insertWidget(layout.count() - 1, self.txt_global_footer_preview)

        self.txt_footer = QPlainTextEdit()
        self.txt_footer.setFixedHeight(50)
        self.txt_footer.setStyleSheet("""
            QPlainTextEdit { background: #333333; color: white; border: 1px solid #444444;
                             font-family: Consolas; font-size: 11px; border-radius: 4px; }
        """)
        layout.insertWidget(layout.count() - 1, self.txt_footer)

        # Section framing
        frm_title = QLabel(self.common.get("point_fram_options", "Pointing & Framing"))
        frm_title.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        layout.insertWidget(layout.count() - 1, frm_title)

        # Pause command
        pause_frame, pause_layout = self._make_row_frame()
        self.lbl_pause_cmd = QLabel(self.common.get("pause_command", "Pause Command"))
        self.lbl_pause_cmd.setStyleSheet("color: #DCE4EE; font-size: 11px;")
        pause_layout.addWidget(self.lbl_pause_cmd)
        self.pause_cmd_entry = QLineEdit("M0")
        self.pause_cmd_entry.setFixedWidth(60)
        self.pause_cmd_entry.setFixedHeight(24)
        self.pause_cmd_entry.setStyleSheet(self._entry_style())
        pause_layout.addWidget(self.pause_cmd_entry)
        pause_layout.addStretch()
        hint_pause = QLabel(self.common.get("void_pause", "(empty = no pause)"))
        hint_pause.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        self.lbl_pause_hint = hint_pause
        pause_layout.addWidget(hint_pause)
        layout.insertWidget(layout.count() - 1, pause_frame)

        # --- Origin pointer switch ---
        self.sw_pointer = self.create_switch(
            layout=layout,
            label_key=self.common.get("origin_pointing", "Origin Pointing"),
            key="origin_pointing"
        )
        self.sw_pointer.stateChanged.connect(self.toggle_framing_options)

        # --- Include framing switch ---
        self.sw_frame = self.create_switch(
            layout=layout,
            label_key=self.common.get("framing_option", "Include Framing"),
            key="include_framing"
        )
        self.sw_frame.stateChanged.connect(self.toggle_framing_options)

        # Framing power
        fp_frame, fp_layout = self._make_row_frame()
        self.lbl_frame_p = QLabel(self.common.get("framing_power", "Framing Power"))
        self.lbl_frame_p.setStyleSheet("color: #DCE4EE; font-size: 11px;")
        fp_layout.addWidget(self.lbl_frame_p)
        self.frame_power_entry = QLineEdit("0")
        self.frame_power_entry.setFixedWidth(60)
        self.frame_power_entry.setFixedHeight(24)
        self.frame_power_entry.setStyleSheet(self._entry_style())
        fp_layout.addWidget(self.frame_power_entry)
        fp_layout.addStretch()
        layout.insertWidget(layout.count() - 1, fp_frame)

        # Hint power
        self.lbl_plow_power_hint = QLabel(self.common.get("hint_power", "⚠ Low power recommended"))
        self.lbl_plow_power_hint.setStyleSheet("color: #700000; font-size: 11px; font-style: italic;")
        self.lbl_plow_power_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.insertWidget(layout.count() - 1, self.lbl_plow_power_hint)

        # Framing ratio
        self._insert_dropdown_into(
            layout, self.common.get("framing_ratio", "Speed Ratio"),
            ["5%", "10%", "20%", "30%", "50%", "80%", "100%"],
            "frame_feed_ratio_menu",
            default="20%"
        )

        self.toggle_framing_options()

    # ─────────────────────────────────────────
    #  STATS + HISTOGRAMME
    # ─────────────────────────────────────────

    def _build_stats_panel(self, parent_layout):
        stats_widget = QWidget()
        stats_widget.setFixedHeight(160)
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(5)

        # Texte stats gauche
        stats_left = QFrame()
        stats_left.setStyleSheet("QFrame { background-color: #202020; border-radius: 6px; border: 1px solid #333333; }")
        sl_layout = QVBoxLayout(stats_left)
        sl_layout.setContentsMargins(8, 6, 8, 6)
        sl_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.stats_labels = []
        for _ in range(6):
            lbl = QLabel("")
            lbl.setStyleSheet("color: #aaaaaa; font-family: Consolas; font-size: 12px; background: transparent; border: none;")
            sl_layout.addWidget(lbl)
            self.stats_labels.append(lbl)

        stats_layout.addWidget(stats_left, stretch=1)

        # Histogramme droit
        self.histogram = HistogramWidget()
        self.histogram.setStyleSheet("background-color: #202020; border-radius: 6px; border: 1px solid #333333;")
        self.histogram.set_labels(
            self.common.get("power_distribution", "Power Distribution"),
            self.common.get("power_value", "Power"),
            self.common.get("Distribution_label", "%")
        )
        stats_layout.addWidget(self.histogram, stretch=2)

        parent_layout.addWidget(stats_widget, stretch=1)

    # ─────────────────────────────────────────
    #  WIDGETS HELPERS
    # ─────────────────────────────────────────

    def _make_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #cccccc; font-size: 11px; background: transparent;")
        return lbl

    def _make_row_frame(self):
        frame = QFrame()
        frame.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        return frame, layout

    def _btn_style(self, color="#1f538d"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border-radius: 4px;
                border: none;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #555555; }}
        """

    def _entry_style(self):
        return """
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 10px;
            }
            QLineEdit:focus { border-color: #1f538d; }
        """

    def _insert_input_pair(self, layout, label_text, start, end, default, key,
                           is_int=False, precision=2):
        """Insère label + slider + entry dans un layout QVBoxLayout (avant le stretch)."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 2, 0, 2)
        c_layout.setSpacing(3)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #cccccc; font-size: 11px;")
        c_layout.addWidget(lbl)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Slider Qt (int uniquement → on multiplie pour float)
        precision_mult = 10 ** precision if not is_int else 1
        slider_min = int(start * precision_mult)
        slider_max = int(end * precision_mult)
        slider_default = int(default * precision_mult)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(slider_min)
        slider.setMaximum(slider_max)
        slider.setValue(slider_default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #444444; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px; height: 12px; margin: -4px 0;
                background: #1f538d; border-radius: 6px;
            }
            QSlider::handle:horizontal:hover { background: #2a6dbd; }
            QSlider::sub-page:horizontal { background: #1f538d; border-radius: 2px; }
        """)

        entry = QLineEdit()
        entry.setFixedWidth(65)
        entry.setFixedHeight(22)
        entry.setStyleSheet(self._entry_style())
        fmt = "{:d}" if is_int else f"{{:.{precision}f}}"
        entry.setText(fmt.format(int(default) if is_int else default))

        # Connexions slider → entry (live) + update_preview (release)
        slider.valueChanged.connect(
            lambda v, e=entry, im=is_int, p=precision, pm=precision_mult:
            self._sync_slider_to_entry(v, e, im, p, pm)
        )
        slider.sliderReleased.connect(self.update_preview)

        # Connexions entry → slider + update
        entry.returnPressed.connect(
            lambda s=slider, e=entry, im=is_int, p=precision, pm=precision_mult:
            self._sync_entry_to_slider(s, e, im, p, pm)
        )
        entry.editingFinished.connect(
            lambda s=slider, e=entry, im=is_int, p=precision, pm=precision_mult:
            self._sync_entry_to_slider(s, e, im, p, pm)
        )

        row_layout.addWidget(slider)
        row_layout.addWidget(entry)
        c_layout.addWidget(row)

        self.controls[key] = {
            "slider": slider,
            "entry": entry,
            "is_int": is_int,
            "precision": precision,
            "precision_mult": precision_mult
        }

        layout.insertWidget(layout.count() - 1, container)
        return lbl

    def _insert_simple_input_into(self, layout, label_text, default, key, precision=2):
        """Insère label + entry dans un layout HBox ou VBox."""
        if isinstance(layout, QHBoxLayout):
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            inner = QHBoxLayout(container)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #cccccc; font-size: 11px;")
            inner.addWidget(lbl)
            entry = QLineEdit()
            entry.setFixedWidth(65)
            entry.setFixedHeight(22)
            entry.setStyleSheet(self._entry_style())
            fmt = "{:d}" if precision == 0 else f"{{:.{precision}f}}"
            entry.setText(fmt.format(int(default) if precision == 0 else default))
            inner.addWidget(entry)
            layout.addWidget(container)
        else:
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            inner = QHBoxLayout(container)
            inner.setContentsMargins(0, 2, 0, 2)
            inner.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #cccccc; font-size: 11px;")
            inner.addWidget(lbl)
            inner.addStretch()
            entry = QLineEdit()
            entry.setFixedWidth(80)
            entry.setFixedHeight(22)
            entry.setStyleSheet(self._entry_style())
            fmt = "{:d}" if precision == 0 else f"{{:.{precision}f}}"
            entry.setText(fmt.format(int(default) if precision == 0 else default))
            inner.addWidget(entry)
            layout.insertWidget(layout.count() - 1, container)

        entry.editingFinished.connect(self.update_preview)
        self.controls[key] = {
            "slider": entry,
            "entry": entry,
            "is_int": (precision == 0),
            "precision": precision,
            "precision_mult": 1
        }
        return self.controls[key]

    def _insert_dropdown(self, layout, label_text, options, attr_name, default=None):
        """Insère label + QComboBox dans un QVBoxLayout (avant le stretch)."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 2, 0, 2)
        c_layout.setSpacing(3)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #cccccc; font-size: 11px;")
        c_layout.addWidget(lbl)

        combo = self._make_combo(options, attr_name, default)
        c_layout.addWidget(combo)
        layout.insertWidget(layout.count() - 1, container)
        setattr(self, attr_name, combo)
        return combo

    def _insert_dropdown_into(self, layout, label_text, options, attr_name, default=None):
        """Idem mais pour layout quelconque."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 2, 0, 2)
        c_layout.setSpacing(3)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #cccccc; font-size: 11px;")
        c_layout.addWidget(lbl)

        combo = self._make_combo(options, attr_name, default)
        c_layout.addWidget(combo)

        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(layout.count() - 1, container)
        else:
            layout.addWidget(container)
        setattr(self, attr_name, combo)
        return combo

    def _make_combo(self, options, attr_name, default=None):
        combo = QComboBox()
        combo.setFixedHeight(28)
        combo.setStyleSheet("""
            QComboBox {
                background-color: #444444;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: white;
                selection-background-color: #1f538d;
            }
        """)

        is_tuple = options and isinstance(options[0], tuple)
        self._combo_maps = getattr(self, "_combo_maps", {})
        if is_tuple:
            key_to_label = dict(options)
            label_to_key = {v: k for k, v in options}
            self._combo_maps[attr_name] = label_to_key
            for k, v in options:
                combo.addItem(v, userData=k)
        else:
            for opt in options:
                combo.addItem(opt)

        if default:
            idx = combo.findText(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        def on_change(idx, a=attr_name, c=combo):
            self._on_combo_change(a, c)
        combo.currentIndexChanged.connect(on_change)
        return combo

    def _on_combo_change(self, attr_name, combo):
        if attr_name == "origin_mode":
            internal = combo.currentData() or combo.currentText()
            self.custom_offset_frame.setVisible(internal == "Custom")
        QTimer.singleShot(100, self.update_preview)

    # ─────────────────────────────────────────
    #  HELPER SWITCH
    # ─────────────────────────────────────────
    def create_switch(self, layout, label_key, key):
        """Crée une ligne avec un Label et un Switch"""
        check = Switch()
        
        # Connexions de base
        if hasattr(self, 'mark_as_changed'):
            check.stateChanged.connect(self.mark_as_changed)
            
        # Intégration dans le layout via ta méthode existante
        self.create_input_row(layout, label_key, check, key=key)
        
        # Stockage pour accès via self.controls["force_width"]["check"]
        self.controls[key] = {"check": check}
        
        return check

    def mark_as_changed(self):
        """Indique que les paramètres ont été modifiés"""

        self.update_preview()


    def create_input_row(self, layout, label_text, widget, key=None):
        """Crée une ligne standard avec Label + Widget"""
        frame = QFrame()
        # Correction : on définit le layout sur le frame
        row_layout = QHBoxLayout(frame) 
        row_layout.setContentsMargins(0, 5, 0, 5)

        label = self._make_label(label_text)
        row_layout.addWidget(label)
        row_layout.addStretch()
        row_layout.addWidget(widget)

        # On insère le frame dans le layout principal de la section
        layout.insertWidget(layout.count() - 1, frame)

    # ─────────────────────────────────────────
    #  SYNCHRONISATION SLIDERS / ENTRIES
    # ─────────────────────────────────────────

    def _sync_slider_to_entry(self, val, entry, is_int, precision, mult):
        real_val = int(val) if is_int else val / mult
        fmt = "{:d}" if is_int else f"{{:.{precision}f}}"
        entry.setText(fmt.format(real_val))
        if hasattr(self, "power_viz"):
            self.power_viz.refresh_visuals()

    def _sync_entry_to_slider(self, slider, entry, is_int, precision, mult):
        try:
            val = float(entry.text().replace(",", ".").strip())
            slider_val = int(val) if is_int else int(val * mult)
            slider.blockSignals(True)
            slider.setValue(slider_val)
            slider.blockSignals(False)
            QTimer.singleShot(50, self.update_preview)
        except ValueError:
            pass

    def get_val(self, ctrl):
        if ctrl is None:
            return 0.0
        try:
            txt = ctrl["entry"].text().replace(",", ".").strip()
            if not txt:
                return 0.0
            val = float(txt)
            return int(val) if ctrl.get("is_int", False) else val
        except (ValueError, TypeError):
            return 0.0

    def _delayed_update(self, delay=50):
        if hasattr(self, "_update_timer"):
            self._update_timer.stop()
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self.update_preview)
        self._update_timer.start(delay)

    # ─────────────────────────────────────────
    #  FICHIERS INPUT / OUTPUT
    # ─────────────────────────────────────────

    def select_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Image files (*.jpg *.jpeg *.png *.bmp)"
        )
        if path:
            self.input_image_path = path
            name = os.path.basename(path).upper()
            self.btn_input.setText(name)
            self.btn_input.setStyleSheet(self._btn_style(color="#2d5a27"))
            self.update_preview()

    def select_output(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = directory
            folder_name = os.path.basename(directory) or directory
            self.btn_output.setText(f"OUT: {folder_name.upper()}/")
            self.btn_output.setStyleSheet(self._btn_style(color="#2d5a27"))

    # ─────────────────────────────────────────
    #  LOGIQUE CALCUL / PREVIEW
    # ─────────────────────────────────────────

    def calculate_offsets(self, real_w, real_h):
        origin_combo = getattr(self, "origin_mode", None)
        if origin_combo is None:
            return 0, 0
        internal = origin_combo.currentData() or origin_combo.currentText()
        return self.engine.calculate_offsets(
            internal,
            real_w,
            real_h,
            self.get_val(self.controls.get("custom_x")),
            self.get_val(self.controls.get("custom_y"))
        )

    def process_logic(self):
        if not self.input_image_path or not os.path.isfile(self.input_image_path):
            return None, None

        ui_dimension = self.get_val(self.controls.get("width", {}))
        raster_mode = self._raster_dir

        settings = {
            "line_step": self.get_val(self.controls.get("line_step")),
            "gamma": self.get_val(self.controls.get("gamma")),
            "contrast": self.get_val(self.controls.get("contrast")),
            "thermal": self.get_val(self.controls.get("thermal")),
            "min_p": self.get_val(self.controls.get("min_p")),
            "max_p": self.get_val(self.controls.get("max_p")),
            "dpi": self.get_val(self.controls.get("dpi")),
            "gray_steps": self.get_val(self.controls.get("gray_steps")),
            "premove": self.get_val(self.controls.get("premove")),
            "feedrate": self.get_val(self.controls.get("feedrate")),
            "speed": self.get_val(self.controls.get("feedrate")),
            "invert": self.sw_invert.isChecked() if hasattr(self, "sw_invert") else False,
            "ui_dimension": ui_dimension,
            "raster_mode": raster_mode,
            "force_dim": self.sw_force_width.isChecked() if hasattr(self, "sw_force_width") else False
        }
        if raster_mode == "horizontal":
            settings["width"] = ui_dimension
        else:
            settings["height"] = ui_dimension

        current_cache = None
        if hasattr(self, "_source_img_path") and self._source_img_path == self.input_image_path:
            current_cache = getattr(self, "_source_img_cache", None)

        try:
            results = self.engine.process_image_logic(
                self.input_image_path, settings, source_img_cache=current_cache
            )
            matrix, img_obj, geom, mem_warn = results

            if raster_mode == "vertical":
                geom["machine_step_x"] = geom.get("y_step", 0.1)
                geom["machine_step_y"] = geom.get("x_step", 0.1)
            else:
                geom["machine_step_x"] = geom.get("x_step", 0.1)
                geom["machine_step_y"] = geom.get("y_step", 0.1)

            self._source_img_cache = img_obj
            self._source_img_path = self.input_image_path
            self._last_matrix = matrix
            self._last_geom = geom
            self.estimated_file_size = geom.get("file_size_str", "N/A")
            self._estimated_time = geom.get("est_min", 0)

            return matrix, geom

        except Exception as e:
            import traceback
            print(f"Logic Error: {e}")
            traceback.print_exc()
            return None, None

    def update_preview(self):
        if not self.controls or "width" not in self.controls:
            return
        if not hasattr(self, "origin_mode"):
            return

        try:
            res = self.process_logic()
            if not res or res[0] is None:
                self.image_preview.clear()
                return

            matrix, geom = res
            real_w = geom["real_w"]
            real_h = geom["real_h"]
            rf = geom["rect_full"]

            offX, offY = self.calculate_offsets(real_w, real_h)
            v_min = self.get_val(self.controls.get("min_p")) if self.controls.get("min_p") else 0
            v_max = self.get_val(self.controls.get("max_p")) if self.controls.get("max_p") else 255

            # Mise à jour preview image
            self.image_preview.update_image(matrix, offX, offY, real_w, real_h, v_min, v_max)

            # Calcul zones overscan
            direction = self._raster_dir
            overscan_rects = []

            if direction == "horizontal":
                over_w_left = abs(rf[0])
                over_w_right = rf[2] - real_w
                if over_w_left > 0.1:
                    overscan_rects.append((offX + rf[0], offY, over_w_left, real_h, "OVERSCAN_90"))
                if over_w_right > 0.1:
                    overscan_rects.append((offX + real_w, offY, over_w_right, real_h, "OVERSCAN_-90"))
            else:
                over_h_bottom = abs(rf[1])
                over_h_top = rf[3] - real_h
                if over_h_bottom > 0.1:
                    overscan_rects.append((offX, offY + rf[1], real_w, over_h_bottom, "OVERSCAN"))
                if over_h_top > 0.1:
                    overscan_rects.append((offX, offY + real_h, real_w, over_h_top, "OVERSCAN"))

            self.image_preview.set_overscan_rects(overscan_rects)
            self.image_preview.set_origin_dot(0, 0)

            # Stats
            est_min = geom.get("est_min", 0.0)
            total_sec = int(est_min * 60)
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            seconds = total_sec % 60

            self._update_dashboard_stats(
                geom["w_px"], geom["h_px"],
                real_w, real_h,
                geom["scan_step"], geom["l_step"],
                hours, minutes, seconds,
                self.estimated_file_size
            )

            # Histogramme
            QTimer.singleShot(50, lambda: self.histogram.update_histogram(matrix, v_min, v_max))

        except Exception as e:
            import traceback
            print(f"Preview Error: {e}")
            traceback.print_exc()

    # ─────────────────────────────────────────
    #  STATS
    # ─────────────────────────────────────────

    def _update_dashboard_stats(self, w_px, h_px, real_w, real_h,
                                scan_step, line_step,
                                hours, minutes, seconds, est_size="N/A"):
        if not hasattr(self, "stats_labels"):
            return

        lines = [
            f"{self.stats_texts.get('real_dims', 'REAL DIMS'):<20}: {real_w:.2f} x {real_h:.2f} mm",
            f"{self.stats_texts.get('est_time', 'EST TIME'):<20}: {hours:02d}:{minutes:02d}:{seconds:02d}",
            f"{self.stats_texts.get('file_size', 'FILE SIZE'):<20}: {est_size}",
            f"{self.stats_texts.get('matrix_size', 'MATRIX'):<20}: {w_px} x {h_px} px",
            f"{self.stats_texts.get('scan_step', 'SCAN STEP'):<20}: {scan_step:.4f} mm",
            f"{self.stats_texts.get('line_step', 'LINE STEP'):<20}: {line_step:.4f} mm"
        ]
        for lbl, txt in zip(self.stats_labels, lines):
            lbl.setText(txt)

    # ─────────────────────────────────────────
    #  RASTER DIRECTION
    # ─────────────────────────────────────────

    def _on_raster_dir_change(self, selected_label):
        tech = self._raster_map_inv.get(selected_label, "horizontal")
        self._raster_dir = tech

        if tech == "vertical":
            w_text = self.common.get("target_height", "Target Height")
            f_text = self.common.get("force_height", "Force Exact Height")
        else:
            w_text = self.common.get("target_width", "Target Width")
            f_text = self.common.get("force_width", "Force Exact Width")

        if hasattr(self, "width_label_widget") and self.width_label_widget:
            self.width_label_widget.setText(w_text)
        if hasattr(self, "force_w_label") and self.force_w_label:
            self.force_w_label.setText(f_text)

        self.update_preview()

    # ─────────────────────────────────────────
    #  FRAMING / POINTING
    # ─────────────────────────────────────────

    def toggle_framing_options(self):
        pointing = self.sw_pointer.isChecked() if hasattr(self, "sw_pointer") else False
        framing = self.sw_frame.isChecked() if hasattr(self, "sw_frame") else False

        any_active = pointing or framing
        label_color = "#DCE4EE" if any_active else "#555555"
        entry_enabled = any_active

        widgets_to_toggle = []
        if hasattr(self, "pause_cmd_entry"):
            self.pause_cmd_entry.setEnabled(entry_enabled)
        if hasattr(self, "frame_power_entry"):
            self.frame_power_entry.setEnabled(entry_enabled)
        if hasattr(self, "frame_feed_ratio_menu"):
            self.frame_feed_ratio_menu.setEnabled(framing)

        for attr in ["lbl_pause_cmd", "lbl_frame_p"]:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {label_color}; font-size: 11px;")

        hint_color = "#888888" if any_active else "#444444"
        for attr in ["lbl_pause_hint", "lbl_plow_power_hint"]:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {hint_color}; font-size: 10px; font-style: italic;")

    # ─────────────────────────────────────────
    #  VERROU MACHINE
    # ─────────────────────────────────────────

    def toggle_machine_lock(self):
        self.is_locked = not self.is_locked
        self.apply_lock_state()

    def apply_lock_state(self):
        new_text = "🔒" if self.is_locked else "🔓"
        btn_color = "#444444" if self.is_locked else "#D32F2F"
        self.lock_btn.setText(new_text)
        self.lock_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {btn_color}; border-radius: 4px;
                          font-size: 13px; border: none; }}
            QPushButton:hover {{ background-color: {'#666666' if self.is_locked else '#f44336'}; }}
        """)

        if not hasattr(self, "machine_controls_container"):
            return

        label_color = "#666666" if self.is_locked else "#FFFFFF"
        entry_style_locked = self._entry_style().replace("color: white", "color: #888888")
        entry_style_normal = self._entry_style()

        def walk(widget):
            for child in widget.findChildren(QLineEdit):
                child.setEnabled(not self.is_locked)
                child.setStyleSheet(entry_style_locked if self.is_locked else entry_style_normal)
            for child in widget.findChildren(QComboBox):
                child.setEnabled(not self.is_locked)
            for child in widget.findChildren(QLabel):
                if "GLOBAL" not in child.text().upper():
                    child.setStyleSheet(f"color: {label_color}; font-size: 11px;")

        walk(self.machine_controls_container)

    # ─────────────────────────────────────────
    #  GÉNÉRATION G-CODE
    # ─────────────────────────────────────────

    def generate_gcode(self):
        self._save_settings()

        try:
            current_cmd_mode = self.cmd_mode.currentText() if hasattr(self, "cmd_mode") else "M67 (Analog)"
            current_firing_mode = self.firing_mode.currentText() if hasattr(self, "firing_mode") else "M3/M5"
            current_origin_mode = (self.origin_mode.currentData() or self.origin_mode.currentText()) if hasattr(self, "origin_mode") else "Lower-Left"
            current_raster_mode = self._raster_dir
        except AttributeError:
            return

        res = self.process_logic()
        if not res or res[0] is None:
            return

        matrix, geom = res
        x_step_final = geom["x_step"]
        y_step_final = geom["y_step"]
        offX, offY = self.calculate_offsets(geom["real_w"], geom["real_h"])

        global_h = self.controller.config_manager.get_item("machine_settings", "custom_header", "").strip()
        global_f = self.controller.config_manager.get_item("machine_settings", "custom_footer", "").strip()
        raster_h = self.txt_header.toPlainText().strip()
        raster_f = self.txt_footer.toPlainText().strip()

        full_header = f"{global_h}\n{raster_h}".strip() if global_h and raster_h else (global_h or raster_h)
        full_footer = f"{raster_f}\n{global_f}".strip() if global_f and raster_f else (global_f or raster_f)

        payload = {
            "matrix": matrix,
            "dims": (geom["h_px"], geom["w_px"], y_step_final, x_step_final),
            "estimated_size": self.estimated_file_size,
            "offsets": (offX, offY),
            "params": {
                "e_num": int(self.get_val(self.controls.get("m67_e_num"))),
                "use_s_mode": "S (Spindle)" in current_cmd_mode,
                "ctrl_max": self.get_val(self.controls.get("ctrl_max")),
                "min_power": self.get_val(self.controls.get("min_p")),
                "max_power": self.get_val(self.controls.get("max_p")),
                "premove": self.get_val(self.controls.get("premove")),
                "feedrate": self.get_val(self.controls.get("feedrate")),
                "m67_delay": self.get_val(self.controls.get("m67_delay")),
                "gray_scales": int(self.get_val(self.controls.get("gray_steps"))),
                "gray_steps": int(self.get_val(self.controls.get("gray_steps"))),
                "raster_mode": current_raster_mode
            },
            "framing": {
                "is_pointing": self.sw_pointer.isChecked() if hasattr(self, "sw_pointer") else False,
                "is_framing": self.sw_frame.isChecked() if hasattr(self, "sw_frame") else False,
                "f_pwr": self.frame_power_entry.text() if hasattr(self, "frame_power_entry") else "0",
                "f_ratio": self.frame_feed_ratio_menu.currentText().replace("%", "") if hasattr(self, "frame_feed_ratio_menu") else "20",
                "f_pause": self.pause_cmd_entry.text().strip() or None if hasattr(self, "pause_cmd_entry") else None,
                "use_s_mode": "S (Spindle)" in current_cmd_mode,
                "e_num": int(self.get_val(self.controls.get("m67_e_num"))),
                "base_feedrate": self.get_val(self.controls.get("feedrate"))
            },
            "text_blocks": {"header": full_header, "footer": full_footer},
            "metadata": {
                "version": self.version,
                "mode": current_cmd_mode.split(" ")[0],
                "firing_cmd": current_firing_mode.split("/")[0],
                "file_extension": self.controller.config_manager.get_item("machine_settings", "gcode_extension", ".nc"),
                "file_name": os.path.basename(self.input_image_path).split(".")[0] if self.input_image_path else "export",
                "output_dir": self.output_dir,
                "origin_mode": current_origin_mode,
                "real_w": geom["real_w"],
                "real_h": geom["real_h"],
                "est_sec": int(geom.get("est_min", 0) * 60),
                "raster_direction": current_raster_mode
            }
        }

        self.controller.show_simulation(self.engine, payload, return_view="raster")

    # ─────────────────────────────────────────
    #  SAUVEGARDE / CHARGEMENT SETTINGS
    # ─────────────────────────────────────────

    def _get_all_settings_data(self):
        data = {k: self.get_val(v) for k, v in self.controls.items()}
        data["input_path"] = self.input_image_path
        data["output_dir"] = self.output_dir
        data["custom_header"] = self.txt_header.toPlainText().strip() if hasattr(self, "txt_header") else ""
        data["custom_footer"] = self.txt_footer.toPlainText().strip() if hasattr(self, "txt_footer") else ""
        data["origin_mode"] = (self.origin_mode.currentData() or self.origin_mode.currentText()) if hasattr(self, "origin_mode") else "Lower-Left"
        data["cmd_mode"] = self.cmd_mode.currentText() if hasattr(self, "cmd_mode") else "M67 (Analog)"
        data["firing_mode"] = self.firing_mode.currentText() if hasattr(self, "firing_mode") else "M3/M5"
        data["include_frame"] = self.sw_frame.isChecked() if hasattr(self, "sw_frame") else False
        data["include_pointer"] = self.sw_pointer.isChecked() if hasattr(self, "sw_pointer") else False
        data["frame_power"] = self.frame_power_entry.text() if hasattr(self, "frame_power_entry") else "0"
        data["custom_pause_cmd"] = self.pause_cmd_entry.text() if hasattr(self, "pause_cmd_entry") else "M0"
        data["framing_ratio"] = self.frame_feed_ratio_menu.currentText() if hasattr(self, "frame_feed_ratio_menu") else "20%"
        data["force_width"] = self.sw_force_width.isChecked() if hasattr(self, "sw_force_width") else False
        data["invert_relief"] = self.sw_invert.isChecked() if hasattr(self, "sw_invert") else False
        data["raster_dir"] = self._raster_dir
        return data

    def _save_settings(self):
        all_data = self._get_all_settings_data()
        machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "m67_delay"]
        machine_updates = {k: all_data.pop(k) for k in machine_keys if k in all_data}
        current_machine = self.controller.config_manager.get_section("machine_settings")
        current_machine.update(machine_updates)
        self.controller.config_manager.set_section("machine_settings", current_machine)
        self.controller.config_manager.set_section("raster_settings", all_data)
        if not self.controller.config_manager.save():
            print("ERREUR : Impossible d'écrire le fichier de config.")

    def _load_settings(self):
        machine_data = self.controller.config_manager.get_section("machine_settings")
        raster_data = self.controller.config_manager.get_section("raster_settings")
        if machine_data:
            self._apply_settings_data(machine_data, is_machine_config=True)
        if raster_data:
            self._apply_settings_data(raster_data, is_machine_config=False)

    def _apply_settings_data(self, data, is_machine_config=False):
        # Sliders & entries
        for k, v in data.items():
            if k in self.controls:
                ctrl = self.controls[k]
                entry = ctrl.get("entry")
                slider = ctrl.get("slider")
                if entry and entry != slider:
                    is_int = ctrl.get("is_int", False)
                    prec = ctrl.get("precision", 2)
                    mult = ctrl.get("precision_mult", 1)
                    fmt = "{:d}" if is_int else f"{{:.{prec}f}}"
                    try:
                        entry.setText(fmt.format(int(v) if is_int else float(v)))
                        if hasattr(slider, "setValue"):
                            sv = int(v) if is_int else int(float(v) * mult)
                            slider.blockSignals(True)
                            slider.setValue(sv)
                            slider.blockSignals(False)
                    except Exception:
                        pass
                elif entry:
                    is_int = ctrl.get("is_int", False)
                    prec = ctrl.get("precision", 2)
                    fmt = "{:d}" if is_int else f"{{:.{prec}f}}"
                    try:
                        entry.setText(fmt.format(int(v) if is_int else float(v)))
                    except Exception:
                        pass

        # Combos
        combo_map = {
            "origin_mode": "origin_mode",
            "cmd_mode": "cmd_mode",
            "firing_mode": "firing_mode",
            "framing_ratio": "frame_feed_ratio_menu"
        }
        for key, attr in combo_map.items():
            if key in data and hasattr(self, attr):
                combo = getattr(self, attr)
                idx = combo.findText(str(data[key]))
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        # Switches
        switch_map = {
            "invert_relief": "sw_invert",
            "include_frame": "sw_frame",
            "include_pointer": "sw_pointer",
            "force_width": "sw_force_width"
        }
        for key, attr in switch_map.items():
            if key in data and hasattr(self, attr):
                getattr(self, attr).setChecked(bool(data[key]))

        # Raster direction
        if "raster_dir" in data and hasattr(self, "raster_dir_btn"):
            tech = data["raster_dir"]
            self._raster_dir = tech
            label = self._raster_map.get(tech, self._raster_map["horizontal"])
            self.raster_dir_btn.set(label)

        # Image path
        raw_path = data.get("input_path", "")
        validated = self.controller.config_manager.validate_image_path(raw_path) if hasattr(self.controller.config_manager, "validate_image_path") else (raw_path if os.path.exists(raw_path) else "")
        self.input_image_path = validated
        if self.input_image_path:
            name = os.path.basename(self.input_image_path).upper()
            self.btn_input.setText(name)
            self.btn_input.setStyleSheet(self._btn_style(color="#2d5a27"))

        # Output dir
        out = data.get("output_dir", self.application_path)
        self.output_dir = out
        if out and out != self.application_path:
            folder = os.path.basename(out) or out
            self.btn_output.setText(f"OUT: {folder.upper()}/")
            self.btn_output.setStyleSheet(self._btn_style(color="#2d5a27"))

        if not is_machine_config:
            if "custom_header" in data and hasattr(self, "txt_header"):
                self.txt_header.setPlainText(data["custom_header"])
            if "custom_footer" in data and hasattr(self, "txt_footer"):
                self.txt_footer.setPlainText(data["custom_footer"])

        if hasattr(self, "frame_power_entry") and "frame_power" in data:
            self.frame_power_entry.setText(str(data["frame_power"]))
        if hasattr(self, "pause_cmd_entry") and "custom_pause_cmd" in data:
            self.pause_cmd_entry.setText(str(data["custom_pause_cmd"]))

        # Custom offset visibility
        origin_mode_val = data.get("origin_mode", "")
        if hasattr(self, "custom_offset_frame"):
            self.custom_offset_frame.setVisible(origin_mode_val == "Custom")

        self.toggle_framing_options()
        self._refresh_global_previews()

    def _refresh_global_previews(self):
        if hasattr(self, "txt_global_header_preview"):
            h = self.controller.config_manager.get_item("machine_settings", "custom_header", "")
            self.txt_global_header_preview.setPlainText(h or self.common.get("no_global_header", "(no global header)"))

        if hasattr(self, "txt_global_footer_preview"):
            f = self.controller.config_manager.get_item("machine_settings", "custom_footer", "")
            self.txt_global_footer_preview.setPlainText(f or self.common.get("no_global_footer", "(no global footer)"))

    # ─────────────────────────────────────────
    #  PROFILS IMPORT / EXPORT
    # ─────────────────────────────────────────

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile", os.path.join(self.application_path, "alig_full_profile.json"),
            "JSON files (*.json)"
        )
        if path:
            all_data = self._get_all_settings_data()
            machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "m67_delay"]
            export_struct = {
                "machine_settings": {k: all_data.pop(k) for k in machine_keys if k in all_data},
                "raster_settings": all_data
            }
            success, err = save_json_file(path, export_struct)
            if success:
                QMessageBox.information(self, "Export Success", "Full profile saved!")

    def load_profile_from(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile", self.application_path, "JSON files (*.json)"
        )
        if path:
            data, err = load_json_file(path)
            if data:
                self._apply_settings_data(data)
                self.update_preview()
                QMessageBox.information(self, "Success", f"Profile loaded:\n{os.path.basename(path)}")
            else:
                QMessageBox.critical(self, "Error", f"Could not load profile:\n{err}")

    # ─────────────────────────────────────────
    #  FERMETURE
    # ─────────────────────────────────────────

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)
