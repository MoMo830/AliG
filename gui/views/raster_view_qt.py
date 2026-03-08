# -*- coding: utf-8 -*-
"""
A.L.I.G. - RasterViewQt

Corrections v2 :
  • Colorbar fixe (QWidget Qt natif) — non affectée par pan/zoom
  • Textes OVERSCAN trackés + supprimés à chaque redraw
  • Switch force_dim correctement connecté (lecture directe dans process_logic)
  • Bouton Reset View : plus de ligne noire (layout propre)
  • Auto-fit image à l'ouverture (reset_pan_zoom centré sur le contenu)
  • Histogramme : contours barres, abscisses par pas ronds, ylabel "Pixel count"
"""

import os
import sys
import time
import math
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QSlider, QScrollArea, QSplitter,
    QTextEdit, QSizePolicy, QFileDialog, QMessageBox, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QTransform, QPixmap, QImage, QIcon,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from gui.switch import Switch
from gui.utils_qt import (
    get_combo_stylesheet,
    show_loading_overlay,
    hide_loading_overlay,
    PanZoomMixin,
    translate_ui_widgets,
)
from core.translations import TRANSLATIONS
from engine.gcode_engine import GCodeEngine
from core.config_manager import save_json_file, load_json_file
from core.utils import get_app_paths
from gui.utils_qt import get_svg_pixmap

try:
    from utils.paths import SVG_ICONS
    _ARROW_PATH = SVG_ICONS.get("ARROW_DOWN", "")
except Exception:
    _ARROW_PATH = ""


# ═══════════════════════════════════════════════════════════════════
#  HISTOGRAMME WIDGET
# ═══════════════════════════════════════════════════════════════════

class _HistogramWidget(QWidget):
    """
    Histogramme de distribution de puissance — rendu QPainter natif.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._matrix      = None
        self._v_min       = 0
        self._v_max       = 255
        self._label_power = "Power"
        self._label_count = "Pixel count"
        self._label_title = "Power Distribution"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def update_data(self, matrix, v_min, v_max,
                    label_title="Power Distribution",
                    label_power="Power",
                    label_count="Pixel count"):
        self._matrix      = matrix
        self._v_min       = float(v_min)
        self._v_max       = float(v_max)
        self._label_title = label_title
        self._label_power = label_power
        self._label_count = label_count
        self.update()

    @staticmethod
    def _nice_step(value_range, max_ticks=7):
        """Retourne un pas « rond » pour ~max_ticks graduations."""
        if value_range <= 0:
            return 1
        raw = value_range / max_ticks
        mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
        for m in (1, 2, 5, 10):
            step = m * mag
            if value_range / step <= max_ticks:
                return step
        return mag * 10

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        qp.fillRect(0, 0, W, H, QColor("#202020"))

        if self._matrix is None:
            qp.setPen(QColor("#555"))
            qp.setFont(QFont("Arial", 10))
            qp.drawText(0, 0, W, H, Qt.AlignmentFlag.AlignCenter, "—")
            qp.end()
            return

        flat  = self._matrix.ravel()[::8]
        total = max(flat.size, 1) # Le dénominateur pour le pourcentage
        v_min = self._v_min
        v_max = self._v_max

        data_off    = flat[flat == 0]
        data_active = flat[flat > 0]

        BINS = 64
        if len(data_active) > 0:
            lo_range = max(v_min, 1e-9)
            hi_range = max(v_max, lo_range + 1e-8)
            counts, edges = np.histogram(
                data_active,
                bins=BINS,
                range=(lo_range, hi_range),
                density=False
            )
            # Conversion des comptes en pourcentages
            counts_pct = (counts / total) * 100.0
        else:
            counts_pct = np.zeros(BINS, dtype=float)
            edges      = np.linspace(v_min, v_max, BINS + 1)

        # Pourcentage de pixels "éteints" (Laser OFF)
        count_off_pct = (data_off.size / total) * 100.0
        
        # Le y_max est maintenant le pourcentage le plus élevé trouvé (max 100)
        y_max = max(counts_pct.max() if counts_pct.size else 0, count_off_pct, 1.0)

        # ── Marges ─────────────────────────────────────────────────
        lm = 56   # axe Y + ylabel vertical
        rm = 10
        tm = 26   # titre
        bm = 28   # axe X + labels + xlabel
        plot_w = W - lm - rm
        zero_w = max(int(plot_w * 0.06), 8)
        act_w  = plot_w - zero_w
        plot_h = H - tm - bm
        base_y = H - bm

        if plot_w <= 0 or plot_h <= 0:
            qp.end()
            return

        # ── Titre ──────────────────────────────────────────────────
        qp.setPen(QColor("white"))
        qp.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        qp.drawText(0, 2, W, tm - 2, Qt.AlignmentFlag.AlignCenter, self._label_title)

        # ── Axes ───────────────────────────────────────────────────
        qp.setPen(QPen(QColor("#555"), 1))
        qp.drawLine(lm, base_y, W - rm, base_y)
        qp.drawLine(lm, tm,     lm,     base_y)

        # ── Mappings ───────────────────────────────────────────────
        def px_x(val):
            if v_max == v_min:
                return lm + zero_w
            return lm + zero_w + ((val - v_min) / (v_max - v_min)) * act_w

        def px_y(cnt):
            return base_y - min(cnt / y_max, 1.0) * plot_h

        # ── Barre OFF ──────────────────────────────────────────────
        if count_off_pct > 0:
            bh  = int(max(base_y - px_y(count_off_pct), 1))
            bx0 = lm + 2
            bx1 = lm + zero_w - 2
            bw  = max(bx1 - bx0, 1)
            by  = base_y - bh
            qp.fillRect(bx0, by, bw, bh, QColor("#c0724a"))
            qp.setPen(QPen(QColor("#e8956b"), 1))
            qp.drawRect(bx0, by, bw - 1, bh - 1)
            qp.setPen(QColor("#e8956b"))
            qp.setFont(QFont("Arial", 7, QFont.Weight.Bold))
            qp.drawText(bx0, base_y + 4, bw, 14, Qt.AlignmentFlag.AlignCenter, "OFF")

        # ── Barres actives ─────────────────────────────────────────
        fill_col    = QColor("#3a80b8")
        outline_col = QColor("#6ab0e0")
        for i, cnt in enumerate(counts_pct):
            if cnt <= 0:
                continue
            x0 = int(px_x(edges[i]))
            x1 = int(px_x(edges[i + 1]))
            bh = int(max(base_y - px_y(cnt), 1))
            bw = max(x1 - x0, 1)
            by = base_y - bh
            qp.fillRect(x0, by, bw, bh, fill_col)
            if bw >= 3:
                qp.setPen(QPen(outline_col, 1))
                qp.drawRect(x0, by, bw - 1, bh - 1)

        # ── Repères MIN / MAX ──────────────────────────────────────
        for val, col, txt in [(v_min, "#ffcc00", "MIN"), (v_max, "#ff4444", "MAX")]:
            px = int(px_x(val))
            qp.setPen(QPen(QColor(col), 1, Qt.PenStyle.DashLine))
            qp.drawLine(px, tm, px, base_y)
            qp.setPen(QColor(col))
            qp.setFont(QFont("Arial", 7, QFont.Weight.Bold))
            qp.drawText(px - 18, base_y + 18, 36, 13, Qt.AlignmentFlag.AlignCenter, txt)

        # ── Graduations Y ──────────────────────────────────────────
        step_y = self._nice_step(y_max, max_ticks=5)
        qp.setFont(QFont("Arial", 7))
        tick = 0
        while tick <= y_max:
            py = int(px_y(tick))
            qp.setPen(QPen(QColor("#2a2a2a"), 1, Qt.PenStyle.DotLine))
            qp.drawLine(lm + 1, py, W - rm, py)
            qp.setPen(QColor("#888"))
            lbl_str = f"{int(tick // 1000)}k" if tick >= 1000 else str(int(tick))
            qp.drawText(0, py - 7, lm - 4, 14,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lbl_str)
            tick += step_y

        # ── Graduations X par pas ronds ────────────────────────────
        v_range  = v_max - v_min
        step_x   = self._nice_step(v_range, max_ticks=6)
        x_start  = math.ceil(v_min / step_x) * step_x if step_x else v_min
        qp.setFont(QFont("Arial", 7))
        cur = x_start
        while cur <= v_max + 1e-9:
            px = int(px_x(cur))
            if lm <= px <= W - rm:
                qp.setPen(QPen(QColor("#555"), 1))
                qp.drawLine(px, base_y, px, base_y + 4)
                qp.setPen(QColor("#888"))
                lbl = f"{int(cur)}" if cur == int(cur) else f"{cur:.1f}"
                qp.drawText(px - 15, base_y + 5, 30, 13,
                            Qt.AlignmentFlag.AlignCenter, lbl)
            cur += step_x

        # ── Label X ────────────────────────────────────────────────
        qp.setPen(QColor("#777"))
        qp.setFont(QFont("Arial", 8))
        qp.drawText(lm, H - 12, int(act_w), 12,
                    Qt.AlignmentFlag.AlignCenter, self._label_power)

        # ── Label Y vertical ───────────────────────────────────────
        qp.save()
        qp.translate(10, tm + plot_h // 2)
        qp.rotate(-90)
        qp.setPen(QColor("#777"))
        qp.setFont(QFont("Arial", 8))
        qp.drawText(-40, -7, 80, 14, Qt.AlignmentFlag.AlignCenter, self._label_count)
        qp.restore()

        qp.end()


# ═══════════════════════════════════════════════════════════════════
#  COLORBAR WIDGET Qt (fixe, hors pan/zoom)
# ═══════════════════════════════════════════════════════════════════

class _ColorbarWidget(QWidget):
    """
    Colorbar affichée en Qt pur, côte à côte avec le canvas.
    Totalement indépendante du pan/zoom matplotlib.
    Dégradé gray_r : noir (haut/fort) → blanc (bas/faible).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._v_min  = 0.0
        self._v_max  = 255.0
        self._label  = "Laser Power"
        self.setFixedWidth(52)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_range(self, v_min, v_max, label="Laser Power"):
        self._v_min = float(v_min)
        self._v_max = float(v_max)
        self._label = label
        self.update()

    def paintEvent(self, _):
        qp = QPainter(self)
        W, H = self.width(), self.height()
        qp.fillRect(0, 0, W, H, QColor("#1e1e1e"))

        tm, bm = 12, 12
        bar_x  = 20
        bar_w  = 14
        bar_h  = H - tm - bm
        if bar_h <= 0:
            qp.end()
            return

        # Dégradé : haut = noir (valeur haute = laser fort) / bas = blanc
        grad = QLinearGradient(bar_x, tm, bar_x, tm + bar_h)
        grad.setColorAt(0.0, QColor("#000000"))
        grad.setColorAt(1.0, QColor("#ffffff"))
        qp.fillRect(bar_x, tm, bar_w, bar_h, QBrush(grad))

        qp.setPen(QPen(QColor("#555"), 1))
        qp.drawRect(bar_x, tm, bar_w - 1, bar_h - 1)

        # Ticks
        qp.setFont(QFont("Arial", 7))
        ticks = [(0.0, self._v_max), (0.5, (self._v_max + self._v_min) / 2), (1.0, self._v_min)]
        for ratio, val in ticks:
            py = int(tm + ratio * bar_h)
            qp.setPen(QPen(QColor("#888"), 1))
            qp.drawLine(bar_x - 3, py, bar_x, py)
            s = f"{int(val)}" if val == int(val) else f"{val:.1f}"
            qp.drawText(0, py - 7, bar_x - 4, 14,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, s)

        # Label vertical
        qp.save()
        qp.translate(W - 4, tm + bar_h // 2)
        qp.rotate(-90)
        qp.setPen(QColor("#888"))
        qp.setFont(QFont("Arial", 8))
        qp.drawText(-50, -6, 100, 13, Qt.AlignmentFlag.AlignCenter, self._label)
        qp.restore()
        qp.end()


# ═══════════════════════════════════════════════════════════════════
#  CANVAS IMAGE avec Pan / Zoom
# ═══════════════════════════════════════════════════════════════════

class _RasterCanvas(PanZoomMixin, QWidget):
    """
    Affiche le rendu matplotlib avec pan (clic-gauche) + zoom (molette).
    v2 : auto-fit à l'ouverture d'une image.
    """

    def __init__(self, fig, parent=None):
        super().__init__(parent)
        self.init_pan_zoom(zoom_min=0.10, zoom_max=30.0, zoom_step=1.15)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#1e1e1e;")

        self._fig        = fig
        self._pixmap     = None
        self._auto_fit   = False
        self._fit_next   = False

        self._mpl_canvas = FigureCanvas(fig)
        self._mpl_canvas.setParent(self)
        self._mpl_canvas.setVisible(False)

        # Overlay QPainter natif (toujours net au zoom)
        self._overlay      = None   # None ou dict
        self._after_draw_cb = None  # callable(pw, ph) appelé après draw()

    def set_overlay(self, ov):
        """
        ov = {
          'transform': callable (mx, my) -> (px, py)  # mm → pixels pixmap
          'overscan_rects': [(x, y, w, h), ...],       # mm
          'border_rect':    (x, y, w, h),              # mm
          'origin':         (ox, oy),                  # mm
          'grid_xs':        [float, ...],              # abscisses grille (mm)
          'grid_ys':        [float, ...],              # ordonnées grille (mm)
          'xlim':           (x0, x1),                  # mm, pour borner les lignes
          'ylim':           (y0, y1),
          'direction':      'horizontal'|'vertical',
        }
        """
        self._overlay = ov
        self.update()

    def request_auto_fit(self):
        self._auto_fit = True

    def redraw(self, fit=False):
        """Demande à matplotlib de redessiner et met à jour le pixmap.
        Si fit=True, ajuste automatiquement le zoom pour remplir la vue.
        """
        from PyQt6.QtCore import QTimer

        self._fig.tight_layout(pad=0.5)
        self._mpl_canvas.draw()

        # Capture du buffer matplotlib vers QPixmap
        buf = self._mpl_canvas.buffer_rgba()
        w, h = self._mpl_canvas.get_width_height()
        qi = QImage(bytes(buf), w, h, QImage.Format.Format_RGBA8888)
        self._pixmap = QPixmap.fromImage(qi)

        # Calcul du mapping mm → pixels pixmap via transData (valide après draw)
        # Appelé par set_overlay_from_ax() si fourni
        if self._after_draw_cb is not None:
            try:
                self._after_draw_cb(w, h)
            except Exception:
                pass

        do_fit = fit or self._fit_next
        self._fit_next = False

        if do_fit:
            self._needs_fit = True
            QTimer.singleShot(0, self.fit_to_view)
        else:
            self.update()

    def fit_to_view(self):
        """Calcule zoom + pan pour que le pixmap remplisse le widget (centré, sans déformation)."""
        if self._pixmap is None:
            self.reset_pan_zoom()
            return
        cw, ch = self.width(), self.height()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        margin = 0.96
        zoom = min(cw / pw, ch / ph) * margin
        pan_x = (cw - pw * zoom) / 2.0
        pan_y = (ch - ph * zoom) / 2.0
        self._pz_zoom = zoom
        self._pz_pan  = QPointF(pan_x, pan_y)


        self.update()
        self._on_pan_zoom_changed()

    def reset_view(self):
        self.fit_to_view()

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.fillRect(0, 0, self.width(), self.height(), QColor("#1e1e1e"))

        if self._pixmap is None:
            qp.setPen(QColor("#444"))
            qp.setFont(QFont("Arial", 11))
            qp.drawText(0, 0, self.width(), self.height(),
                        Qt.AlignmentFlag.AlignCenter, "Select an image…")
            qp.end()
            return

        # ── Pixmap matplotlib (image raster + ticks + labels) ───────
        self.apply_pan_zoom_transform(qp)
        qp.drawPixmap(0, 0, self._pixmap)

        # ── Overlay QPainter natif (toujours net au zoom) ────────────
        ov = self._overlay
        if ov is None:
            qp.end()
            return

        m2p = ov['transform']         # (mm_x, mm_y) → (px_x, px_y) dans pixmap
        x0, x1 = ov['xlim']
        y0, y1 = ov['ylim']
        horiz   = ov.get('direction', 'horizontal') == 'horizontal'

        def cosmetic_pen(hex_col, alpha=1.0, widthF=0.0,
                         style=Qt.PenStyle.SolidLine):
            c = QColor(hex_col); c.setAlphaF(alpha)
            p = QPen(c); p.setWidthF(widthF); p.setStyle(style)
            return p

        # ── 1. Grille ────────────────────────────────────────────────
        qp.setPen(cosmetic_pen("#00ffff", alpha=0.45))
        for gx in ov.get('grid_xs', []):
            ax1, ay1 = m2p(gx, y0)
            ax2, ay2 = m2p(gx, y1)
            qp.drawLine(QPointF(ax1, ay1), QPointF(ax2, ay2))
        for gy in ov.get('grid_ys', []):
            ax1, ay1 = m2p(x0, gy)
            ax2, ay2 = m2p(x1, gy)
            qp.drawLine(QPointF(ax1, ay1), QPointF(ax2, ay2))

        # ── 1b. Labels des ticks (Y gauche+droite, X haut+bas) ──────
        ax_left  = ov.get('ax_left',  0.0)
        ax_right = ov.get('ax_right', float(self._pixmap.width()))
        ax_top   = ov.get('ax_top',   0.0)
        ax_bot   = ov.get('ax_bot',   float(self._pixmap.height()))

        lbl_font = QFont("Arial", 8)
        qp.setFont(lbl_font)
        lbl_col = QColor("#888888")
        qp.setPen(QPen(lbl_col))
        lbl_w = 36; lbl_h = 14

        for (val, txt) in ov.get('yticks', []):
            _, py = m2p(x0, val)
            # gauche
            qp.drawText(QRectF(ax_left - lbl_w - 4, py - lbl_h / 2, lbl_w, lbl_h),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt)
            # droite
            qp.drawText(QRectF(ax_right + 4, py - lbl_h / 2, lbl_w, lbl_h),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)

        for (val, txt) in ov.get('xticks', []):
            px, _ = m2p(val, y0)
            # bas
            qp.drawText(QRectF(px - lbl_w / 2, ax_bot + 3, lbl_w, lbl_h),
                        Qt.AlignmentFlag.AlignCenter, txt)
            # haut
            qp.drawText(QRectF(px - lbl_w / 2, ax_top - lbl_h - 3, lbl_w, lbl_h),
                        Qt.AlignmentFlag.AlignCenter, txt)

        # ── 2. Hachures + texte OVERSCAN ────────────────────────────
        for (rx, ry, rw, rh) in ov.get('overscan_rects', []):
            # y inversé : coin haut = y+h, coin bas = y
            tlx, tly = m2p(rx,      ry + rh)   # top-left  pixel
            brx, bry = m2p(rx + rw, ry)        # bot-right pixel
            rpx = min(tlx, brx); rpy = min(tly, bry)
            rpw = max(1.0, abs(brx - tlx))
            rph = max(1.0, abs(bry - tly))

            fill = QColor("#3498db"); fill.setAlphaF(0.10)
            qp.fillRect(QRectF(rpx, rpy, rpw, rph), fill)

            # hachures manuelles 8 px réels
            # horizontal = lignes de gravure horizontales → overscan gauche/droite (zones hautes/étroites)
            # → hachures "---" = lignes HORIZONTALES dans la zone
            # vertical   = lignes de gravure verticales  → overscan haut/bas (zones larges/plates)
            # → hachures "|||" = lignes VERTICALES dans la zone
            qp.setPen(cosmetic_pen("#3498db", alpha=0.35))
            step = 8.0
            if horiz:
                # hachures horizontales (---) dans zones gauche/droite
                y = rpy
                while y <= rpy + rph:
                    qp.drawLine(QPointF(rpx, y), QPointF(rpx + rpw, y))
                    y += step
            else:
                # hachures verticales (|||) dans zones haut/bas
                x = rpx
                while x <= rpx + rpw:
                    qp.drawLine(QPointF(x, rpy), QPointF(x, rpy + rph))
                    x += step

            # texte "OVERSCAN"
            # horizontal → zones étroites et hautes → texte tourné 90°
            # vertical   → zones larges et plates  → texte droit
            qp.save()
            tc = QColor("#3498db"); tc.setAlphaF(0.9)
            qp.setPen(QPen(tc))
            qp.setFont(QFont("Arial", 7, QFont.Weight.Bold))
            cx = rpx + rpw / 2;  cy = rpy + rph / 2
            qp.translate(cx, cy)
            if horiz:
                qp.rotate(-90)
            qp.drawText(QRectF(-40, -8, 80, 16),
                        Qt.AlignmentFlag.AlignCenter, "OVERSCAN")
            qp.restore()

        # ── 3. Rectangle bordure pointillé ──────────────────────────
        br = ov.get('border_rect')
        if br:
            bx, by, bw, bh = br
            tlx, tly = m2p(bx,      by + bh)
            brx2, bry2 = m2p(bx + bw, by)
            pen = cosmetic_pen("#3498db", alpha=0.9, widthF=1.5,
                               style=Qt.PenStyle.DashLine)
            qp.setPen(pen)
            qp.setBrush(Qt.BrushStyle.NoBrush)
            rx_ = min(tlx, brx2); ry_ = min(tly, bry2)
            qp.drawRect(QRectF(rx_, ry_, abs(brx2 - tlx), abs(bry2 - tly)))

        # ── 4. Point d'origine (disque rouge) ────────────────────────
        orig = ov.get('origin')
        if orig:
            opx, opy = m2p(orig[0], orig[1])
            r = 5.0
            qp.setPen(QPen(QColor("#cc0000"), 1.5))
            qp.setBrush(QBrush(QColor("#ff3333")))
            qp.drawEllipse(QRectF(opx - r, opy - r, r * 2, r * 2))

        qp.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pixmap is not None:
            if self._needs_fit :
                self.fit_to_view()
            else:
                self.update()


# ═══════════════════════════════════════════════════════════════════
#  VUE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════

class RasterViewQt(QWidget):

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        lang = controller.config_manager.get_item("machine_settings", "language")
        if not lang or lang not in TRANSLATIONS:
            lang = "English"

        self._lang   = lang
        self.t       = TRANSLATIONS[lang]["common"]
        self.t_stats = TRANSLATIONS[lang]["stats"]
        self.t_orig  = TRANSLATIONS[lang]["origin_options"]

        self.engine   = GCodeEngine()
        self._loading = True

        self.input_image_path = ""
        self.output_dir       = ""
        _, self.application_path = get_app_paths()
        self.output_dir       = self.application_path
        self.version          = getattr(controller, "version", "1.0")

        self.controls        = {}
        self.translation_map = {}

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_update_preview)

        self._fig      = Figure(figsize=(5, 5), facecolor="#1e1e1e")
        self._ax       = None
        self._img_plot = None
        self._cbar     = None

        self._origin_marker    = None
        self._overscan_patches = []
        self._overscan_texts   = []
        self._rect_overscan    = None
        self._placeholder_text = None

        self._last_matrix        = None
        self._last_geom          = None
        self.estimated_file_size = "N/A"
        self._source_img_cache   = None
        self._source_img_path    = ""

        self._build_ui()
        self._loading = False
        self.load_settings()

        QTimer.singleShot(500, self._initial_render)

    # ── Construction de l'UI ─────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        sidebar = self._build_sidebar()
        right   = self._build_right_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 900])
        root.addWidget(splitter)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(390)
        sidebar.setStyleSheet(
            "QFrame{background:#1e1e1e;border-right:1px solid #333;}"
            "QLabel{border:none;background:transparent;color:#ddd;}"
        )
        lo = QVBoxLayout(sidebar)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)

        lo.addWidget(self._make_file_buttons())
        lo.addWidget(self._make_profile_buttons())

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #252525; }
            QTabBar::tab {
                background: #2b2b2b; color: #aaa; padding: 5px 12px;
                border: 1px solid #333; border-bottom: none; border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected { background: #1F6AA5; color: white; }
        """)

        self._tab_geom  = self._make_scrollable_tab()
        self._tab_img   = self._make_scrollable_tab()
        self._tab_laser = self._make_scrollable_tab()
        self._tab_gcode = self._make_scrollable_tab()

        self._tabs.addTab(self._tab_geom,  self.t.get("geometry", "Geometry"))
        self._tabs.addTab(self._tab_img,   self.t.get("image",    "Image"))
        self._tabs.addTab(self._tab_laser, self.t.get("laser",    "Laser"))
        self._tabs.addTab(self._tab_gcode, self.t.get("gcode",    "G-Code"))

        self._setup_tab_geom()
        self._setup_tab_img()
        self._setup_tab_laser()
        self._setup_tab_gcode()

        lo.addWidget(self._tabs, stretch=1)

        self.btn_gen = QPushButton(self.t.get("simulate_gcode", "Simulate / Export G-Code"))
        self.btn_gen.setFixedHeight(50)
        self.btn_gen.setStyleSheet(
            "QPushButton{background:#1f538d;color:white;border-radius:8px;"
            "font-size:13px;font-weight:bold;border:none;}"
            "QPushButton:hover{background:#2a6dbd;}"
        )
        self.btn_gen.clicked.connect(self.generate_gcode)
        self.translation_map[self.btn_gen] = "simulate_gcode"
        lo.addWidget(self.btn_gen)

        return sidebar

    def _make_scrollable_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent;")
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(container)
        lo.setAlignment(Qt.AlignmentFlag.AlignTop)
        lo.setContentsMargins(6, 6, 6, 6)
        lo.setSpacing(4)
        scroll.setWidget(container)
        scroll._inner = lo
        return scroll

    def _make_file_buttons(self):
        f = QFrame()
        f.setStyleSheet("QFrame{background:#333;border-radius:6px;}")
        lo = QVBoxLayout(f)
        lo.setContentsMargins(6, 6, 6, 6)
        lo.setSpacing(4)

        self.btn_input = QPushButton(self.t.get("select_image", "Select Image"))
        self.btn_input.setFixedHeight(32)
        self.btn_input.setStyleSheet(self._btn_style())
        self.btn_input.clicked.connect(self.select_input)
        self.translation_map[self.btn_input] = "select_image"

        self.btn_output = QPushButton(self.t.get("select_output", "Select Output Folder"))
        self.btn_output.setFixedHeight(32)
        self.btn_output.setStyleSheet(self._btn_style())
        self.btn_output.clicked.connect(self.select_output)
        self.translation_map[self.btn_output] = "select_output"

        lo.addWidget(self.btn_input)
        lo.addWidget(self.btn_output)
        return f

    def _make_profile_buttons(self):
        f = QFrame()
        f.setStyleSheet("QFrame{background:transparent;border:none;}")
        lo = QHBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(6)

        self.btn_load_prof = QPushButton(self.t.get("import_profile", "Import Profile"))
        self.btn_load_prof.setFixedHeight(28)
        self.btn_load_prof.setStyleSheet(self._btn_style(bg="#444"))
        self.btn_load_prof.clicked.connect(self.load_profile_from)
        self.translation_map[self.btn_load_prof] = "import_profile"

        self.btn_save_prof = QPushButton(self.t.get("export_profile", "Export Profile"))
        self.btn_save_prof.setFixedHeight(28)
        self.btn_save_prof.setStyleSheet(self._btn_style(bg="#444"))
        self.btn_save_prof.clicked.connect(self.export_profile)
        self.translation_map[self.btn_save_prof] = "export_profile"

        lo.addWidget(self.btn_load_prof, 1)
        lo.addWidget(self.btn_save_prof, 1)
        return f

    # ── Onglets ───────────────────────────────────────────────────────

    def _setup_tab_geom(self):
        lo = self._tab_geom._inner

        lbl_mode = QLabel(self.t.get("raster_mode", "Raster Mode"))
        lbl_mode.setStyleSheet("color:#ddd;font-size:12px;")
        lo.addWidget(lbl_mode)
        self.translation_map[lbl_mode] = "raster_mode"

        self._raster_map = {
            "horizontal": self.t.get("horizontal", "Horizontal"),
            "vertical":   self.t.get("vertical",   "Vertical"),
        }
        self._raster_map_inv = {v: k for k, v in self._raster_map.items()}
        self._raster_mode = "horizontal"

        mode_row = QHBoxLayout()
        self._btn_raster = {}
        for key, lbl in self._raster_map.items():
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setStyleSheet(self._seg_btn_style())
            b.clicked.connect(lambda _, k=key: self._on_raster_change(k))
            mode_row.addWidget(b)
            self._btn_raster[key] = b
        self._btn_raster["horizontal"].setChecked(True)
        lo.addLayout(mode_row)
        lo.addSpacing(6)

        self.width_label_widget, _ = self._add_slider_input(
            lo, self.t.get("target_width", "Target Width"), 5, 400, 30.0, "width")

        sw_row = QHBoxLayout()
        self.lbl_force_width = QLabel(self.t.get("force_width", "Force Exact Width"))
        self.lbl_force_width.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[self.lbl_force_width] = "force_width"
        self.sw_force_width = Switch()
        self.sw_force_width.toggled.connect(self._on_switch_with_delay)
        sw_row.addWidget(self.lbl_force_width)
        sw_row.addStretch()
        sw_row.addWidget(self.sw_force_width)
        lo.addLayout(sw_row)

        self._add_slider_input(lo, self.t.get("line_step", "Line Step"), 0.01, 1.0, 0.1307, "line_step", precision=4)
        self._add_slider_input(lo, self.t.get("dpi_resolution", "DPI"), 10, 1200, 254, "dpi", is_int=True)
        lo.addSpacing(6)

        ORIGIN_KEYS = ["Lower-Left","Upper-Left","Lower-Right","Upper-Right","Center","Custom"]
        origin_opts = [(k, self.t_orig.get(k, k)) for k in ORIGIN_KEYS]
        self._add_combo(lo, self.t.get("origin_point", "Origin Point"), origin_opts, "origin_mode",
                        callback=self._on_origin_change)
        self.custom_offset_frame = QFrame()
        self.custom_offset_frame.setVisible(False)
        cf_lo = QVBoxLayout(self.custom_offset_frame)
        cf_lo.setContentsMargins(0, 0, 0, 0)
        self._add_simple_input(cf_lo, self.t.get("custom_offset_x", "Custom X"), 0.0, "custom_x")
        self._add_simple_input(cf_lo, self.t.get("custom_offset_y", "Custom Y"), 0.0, "custom_y")
        lo.addWidget(self.custom_offset_frame)

    def _setup_tab_img(self):
        lo = self._tab_img._inner
        self._add_slider_input(lo, self.t.get("contrast", "Contrast"), -1.0, 1.0, 0.0, "contrast")
        self._add_slider_input(lo, self.t.get("gamma",    "Gamma"),     0.1, 6.0, 1.0, "gamma")
        self._add_slider_input(lo, self.t.get("thermal",  "Thermal"),   0.1, 3.0, 1.5, "thermal")

        sw_row = QHBoxLayout()
        lbl_inv = QLabel(self.t.get("invert_color", "Invert Colors"))
        lbl_inv.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[lbl_inv] = "invert_color"
        self.sw_invert = Switch()
        self.sw_invert.toggled.connect(self._on_switch_with_delay)
        sw_row.addWidget(lbl_inv)
        sw_row.addStretch()
        sw_row.addWidget(self.sw_invert)
        lo.addLayout(sw_row)

    def _setup_tab_laser(self):
        lo = self._tab_laser._inner
        self._add_slider_input(lo, self.t.get("feedrate", "Feedrate (mm/min)"), 500, 20000, 3000, "feedrate", is_int=True)
        self._add_slider_input(lo, self.t.get("overscan", "Overscan (mm)"),    0,   50,    10.0, "premove")

        pow_row = QHBoxLayout()
        left_p = QVBoxLayout()
        self._add_simple_input(left_p, self.t.get("max_power", "Max Power"), 40.0, "max_p")
        self._add_simple_input(left_p, self.t.get("min_power", "Min Power"), 10.0, "min_p")
        pow_row.addLayout(left_p)
        lo.addLayout(pow_row)

        self._add_slider_input(lo, self.t.get("laser_latency", "Laser Latency (ms)"), -20, 20, 0, "laser_latency")
        self._add_slider_input(lo, self.t.get("gray_steps", "Gray Steps"), 2, 256, 256, "gray_steps", is_int=True)

    def _setup_tab_gcode(self):
        lo = self._tab_gcode._inner

        sec_frame = QFrame()
        sec_frame.setStyleSheet(
            "QFrame{background:#2b2b2b;border:1px solid #555;border-radius:8px;}"
            "QLabel{border:none;background:transparent;}"
        )
        sec_lo = QVBoxLayout(sec_frame)
        sec_lo.setContentsMargins(10, 8, 10, 8)
        sec_lo.setSpacing(4)

        hdr_row = QHBoxLayout()
        lbl_glob = QLabel(self.t.get("global_machine_params", "Global Machine Parameters"))
        lbl_glob.setStyleSheet("color:#FF9500;font-weight:bold;font-size:11px;")
        self.lock_btn = QPushButton("🔒")
        self.lock_btn.setFixedSize(30, 26)
        self.lock_btn.setStyleSheet(
            "QPushButton{background:#444;color:white;border-radius:4px;border:none;font-size:13px;}"
            "QPushButton:hover{background:#666;}"
        )
        self.is_locked = True
        self.lock_btn.clicked.connect(self.toggle_machine_lock)
        hdr_row.addWidget(lbl_glob)
        hdr_row.addStretch()
        hdr_row.addWidget(self.lock_btn)
        sec_lo.addLayout(hdr_row)

        self._machine_container = QWidget()
        self._machine_container.setStyleSheet("background:transparent;")
        mc_lo = QVBoxLayout(self._machine_container)
        mc_lo.setContentsMargins(0, 0, 0, 0)
        mc_lo.setSpacing(4)

        self._add_combo(mc_lo, self.t.get("cmd_mode", "Command Mode"),
                        ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        row_em = QHBoxLayout()
        self._add_simple_input(row_em, self.t.get("m67_output", "M67 E#"), 0, "m67_e_num", precision=0, box_length=40)
        self._add_simple_input(row_em, self.t.get("ctrl_max_value", "Ctrl Max"), 100, "ctrl_max", precision=0)
        mc_lo.addLayout(row_em)
        self._add_combo(mc_lo, self.t.get("firing_mode", "Firing Mode"),
                        ["M3/M5", "M4/M5"], "firing_mode")

        sec_lo.addWidget(self._machine_container)
        lo.addWidget(sec_frame)
        self.apply_lock_state()
        lo.addSpacing(8)

        lbl_h = QLabel(self.t.get("gcode_header", "G-Code Header"))
        lbl_h.setStyleSheet("font-weight:bold;font-size:11px;color:#ddd;")
        self.translation_map[lbl_h] = "gcode_header"
        lo.addWidget(lbl_h)

        self.txt_global_header_preview = QTextEdit()
        self.txt_global_header_preview.setFixedHeight(28)
        self.txt_global_header_preview.setReadOnly(True)
        self.txt_global_header_preview.setStyleSheet(
            "QTextEdit{background:#222;color:#666;border:none;font-family:Consolas;font-size:9px;}")
        self.txt_global_header_preview.setPlainText("(Machine Settings Header…)")
        lo.addWidget(self.txt_global_header_preview)

        self.txt_header = QTextEdit()
        self.txt_header.setFixedHeight(50)
        self.txt_header.setStyleSheet(self._textedit_style())
        lo.addWidget(self.txt_header)

        lbl_f = QLabel(self.t.get("gcode_footer", "G-Code Footer"))
        lbl_f.setStyleSheet("font-weight:bold;font-size:11px;color:#ddd;")
        self.translation_map[lbl_f] = "gcode_footer"
        lo.addWidget(lbl_f)

        self.txt_global_footer_preview = QTextEdit()
        self.txt_global_footer_preview.setFixedHeight(28)
        self.txt_global_footer_preview.setReadOnly(True)
        self.txt_global_footer_preview.setStyleSheet(
            "QTextEdit{background:#222;color:#666;border:none;font-family:Consolas;font-size:9px;}")
        self.txt_global_footer_preview.setPlainText("(Machine Settings Footer…)")
        lo.addWidget(self.txt_global_footer_preview)

        self.txt_footer = QTextEdit()
        self.txt_footer.setFixedHeight(50)
        self.txt_footer.setStyleSheet(self._textedit_style())
        lo.addWidget(self.txt_footer)

        lo.addSpacing(8)

        lbl_fr = QLabel(self.t.get("point_fram_options", "Framing / Pointing"))
        lbl_fr.setStyleSheet("font-weight:bold;font-size:11px;color:#ddd;")
        lo.addWidget(lbl_fr)

        pause_row = QHBoxLayout()
        lbl_pause = QLabel(self.t.get("pause_command", "Pause Command"))
        lbl_pause.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[lbl_pause] = "pause_command"
        self.pause_cmd_entry = QLineEdit("M0")
        self.pause_cmd_entry.setFixedWidth(60)
        self.pause_cmd_entry.setStyleSheet(self._entry_style())
        pause_row.addWidget(lbl_pause)
        pause_row.addWidget(self.pause_cmd_entry)
        pause_row.addStretch()
        lo.addLayout(pause_row)

        self.origin_pointer_var = False
        sw_ptr_row = QHBoxLayout()
        lbl_ptr = QLabel(self.t.get("origin_pointing", "Origin Pointing"))
        lbl_ptr.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[lbl_ptr] = "origin_pointing"
        self.sw_pointer = Switch()
        self.sw_pointer.toggled.connect(self._on_framing_toggle)
        sw_ptr_row.addWidget(lbl_ptr)
        sw_ptr_row.addStretch()
        sw_ptr_row.addWidget(self.sw_pointer)
        lo.addLayout(sw_ptr_row)

        self.frame_var = False
        sw_frm_row = QHBoxLayout()
        lbl_frm = QLabel(self.t.get("framing_option", "Include Framing"))
        lbl_frm.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[lbl_frm] = "framing_option"
        self.sw_frame = Switch()
        self.sw_frame.toggled.connect(self._on_framing_toggle)
        sw_frm_row.addWidget(lbl_frm)
        sw_frm_row.addStretch()
        sw_frm_row.addWidget(self.sw_frame)
        lo.addLayout(sw_frm_row)

        pwr_row = QHBoxLayout()
        lbl_fpwr = QLabel(self.t.get("framing_power", "Framing Power"))
        lbl_fpwr.setStyleSheet("color:#ddd;font-size:12px;")
        self.translation_map[lbl_fpwr] = "framing_power"
        self.frame_power_entry = QLineEdit("0")
        self.frame_power_entry.setFixedWidth(60)
        self.frame_power_entry.setStyleSheet(self._entry_style())
        pwr_row.addWidget(lbl_fpwr)
        pwr_row.addWidget(self.frame_power_entry)
        pwr_row.addStretch()
        lo.addLayout(pwr_row)

        self._add_combo(lo, self.t.get("framing_ratio", "Framing Speed Ratio"),
                        ["5%","10%","20%","30%","50%","80%","100%"],
                        "frame_feed_ratio_menu")
        if "frame_feed_ratio_menu" in self.controls:
            self.controls["frame_feed_ratio_menu"]["combo"].setCurrentText("20%")

        self._update_framing_state()

    # ── Panneau droit ─────────────────────────────────────────────────

    def _build_right_panel(self):
        w = QWidget()
        w.setStyleSheet("background:#111;")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(2)

        # Canvas + colorbar fixe côte à côte
        canvas_row = QHBoxLayout()
        canvas_row.setSpacing(2)
        canvas_row.setContentsMargins(0, 0, 0, 0)

        self._canvas = _RasterCanvas(self._fig)
        self._setup_matplotlib()
        canvas_row.addWidget(self._canvas, stretch=1)

        self._cbar_widget = _ColorbarWidget()
        canvas_row.addWidget(self._cbar_widget)

        lo.addLayout(canvas_row, stretch=5)

        # Bouton Reset View — wrapper transparent pour éviter ligne noire
        # label_reset_view = self.t.get("reset_view", "⊞  Reset View")
        fit_pixmap = get_svg_pixmap(SVG_ICONS["FIT"], QSize(24, 24), "#ffffff")
        # self.btn_reset_view = QPushButton(label_reset_view, self._canvas)
        self.btn_reset_view = QPushButton(self._canvas)
        self.btn_reset_view.setIcon(QIcon(fit_pixmap))
        self.btn_reset_view.setFixedSize(30, 30)
        self.btn_reset_view.setStyleSheet(
            "QPushButton{background:#2c2c2c;color:#aaa;border:none;"
            "border-radius:4px;font-size:10px;}"
            "QPushButton:hover{background:#3a3a3a;color:white;}"
        )
        self.btn_reset_view.clicked.connect(self._canvas.reset_view)
        self.btn_reset_view.raise_()

        # Stats + Histogramme
        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            "QFrame{background:#202020;border:1px solid #333;border-radius:6px;}"
        )
        stats_frame.setFixedHeight(160)
        sf_lo = QHBoxLayout(stats_frame)
        sf_lo.setContentsMargins(8, 6, 8, 6)
        sf_lo.setSpacing(8)

        stats_text_w = QFrame()
        stats_text_w.setStyleSheet("QFrame{border:none;background:transparent;}")
        stats_text_lo = QVBoxLayout(stats_text_w)
        stats_text_lo.setContentsMargins(8, 6, 8, 6)
        stats_text_lo.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.stats_labels = []
        for _ in range(6):
            lbl = QLabel("")
            lbl.setFont(QFont("Consolas", 10))
            lbl.setStyleSheet("color:#aaaaaa;font-family:Consolas;font-size:12px;"
                              "background:transparent;border:none;")
            stats_text_lo.addWidget(lbl)
            self.stats_labels.append(lbl)
        sf_lo.addWidget(stats_text_w)

        self._hist_widget = _HistogramWidget()
        sf_lo.addWidget(self._hist_widget, 2)

        lo.addWidget(stats_frame, stretch=2)
        return w

    def _setup_matplotlib(self):
        """Un seul axe, sans colorbar matplotlib — gérée en Qt."""
        self._ax = self._fig.add_subplot(111)
        self._fig.subplots_adjust(left=0.10, right=0.90, top=0.90, bottom=0.10)

        self._ax.set_facecolor("#1e1e1e")
        self._ax.tick_params(axis="both", colors="#888888", labelsize=9)
        self._ax.set_axisbelow(False)
        self._ax.grid(True, color="#ffffff", linestyle=":", linewidth=0.5, alpha=0.3, zorder=10)
        for spine in self._ax.spines.values():
            spine.set_edgecolor("#333333")

        self._placeholder_text = self._ax.text(
            0.5, 0.5, self.t.get("choose_image", "Choose an image…"),
            color="#444444", fontsize=12, fontweight="bold",
            ha="center", va="center", transform=self._ax.transAxes
        )

    # ── Helpers construction ──────────────────────────────────────────

    def _add_slider_input(self, layout, label_text, vmin, vmax, default, key,
                          is_int=False, precision=2):
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color:#ddd;font-size:12px;")
        layout.addWidget(lbl)

        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(vmin * 100) if not is_int else int(vmin),
                        int(vmax * 100) if not is_int else int(vmax))
        slider.setValue(int(default * 100) if not is_int else int(default))

        entry = QLineEdit()
        entry.setFixedWidth(70)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setStyleSheet(self._entry_style())
        fmt = "{:d}" if is_int else f"{{:.{precision}f}}"
        entry.setText(fmt.format(int(default) if is_int else default))

        def on_slider(v):
            real = v if is_int else v / 100.0
            entry.setText(fmt.format(int(real) if is_int else real))

        def on_entry():
            try:
                v = float(entry.text().replace(",", "."))
                slider.setValue(int(v) if is_int else int(v * 100))
                self._schedule_preview()
            except ValueError:
                pass

        slider.valueChanged.connect(on_slider)
        slider.sliderReleased.connect(self._schedule_preview)
        entry.editingFinished.connect(on_entry)

        row.addWidget(slider)
        row.addWidget(entry)
        layout.addLayout(row)

        self.controls[key] = {
            "slider": slider, "entry": entry,
            "is_int": is_int, "precision": precision,
            "_vmin": vmin, "_vmax": vmax,
        }
        return lbl, entry

    def _add_simple_input(self, layout, label_text, default, key, precision=2, box_length=80):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color:#ddd;font-size:12px;")
        entry = QLineEdit()
        entry.setFixedWidth(box_length)
        entry.setStyleSheet(self._entry_style())
        fmt = "{:d}" if precision == 0 else f"{{:.{precision}f}}"
        entry.setText(fmt.format(int(default) if precision == 0 else default))
        entry.editingFinished.connect(self._schedule_preview)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(entry)
        layout.addLayout(row)
        self.controls[key] = {"slider": entry, "entry": entry,
                               "is_int": (precision == 0), "precision": precision}
        return lbl, entry

    def _add_combo(self, layout, label_text, options, key, callback=None):
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color:#ddd;font-size:12px;")
        layout.addWidget(lbl)

        combo = QComboBox()
        combo.setFixedHeight(30)
        combo.setStyleSheet(get_combo_stylesheet(_ARROW_PATH))

        is_tuple = options and isinstance(options[0], tuple)
        if is_tuple:
            for k, v in options:
                combo.addItem(v, userData=k)
        else:
            for o in options:
                combo.addItem(o)

        def on_change():
            if callback:
                ud = combo.currentData()
                callback(ud if ud is not None else combo.currentText())
            self._schedule_preview()

        combo.currentIndexChanged.connect(on_change)
        layout.addWidget(combo)
        self.controls[key] = {"combo": combo, "_is_tuple": is_tuple}
        return combo

    # ── Styles ────────────────────────────────────────────────────────

    @staticmethod
    def _btn_style(bg="#1F6AA5", hover="#2a6dbd"):
        return (f"QPushButton{{background:{bg};color:white;border-radius:6px;"
                f"border:none;font-weight:bold;}}"
                f"QPushButton:hover{{background:{hover};}}")

    @staticmethod
    def _seg_btn_style():
        return (
            "QPushButton{background:#333;color:#aaa;border:1px solid #555;"
            "border-radius:4px;padding:2px 8px;min-width:60px;font-size:11px;}"
            "QPushButton:checked{background:#1F6AA5;color:white;border-color:#2a6dbd;}"
            "QPushButton:hover:!checked{background:#444;color:white;}"
        )

    @staticmethod
    def _entry_style():
        return ("QLineEdit{background:#1e1e1e;border:1px solid #444;"
                "border-radius:4px;color:white;padding:2px;}")

    @staticmethod
    def _textedit_style():
        return ("QTextEdit{background:#1a1a1a;border:1px solid #444;"
                "border-radius:6px;color:#8fbdf0;font-family:Consolas;font-size:10px;padding:4px;}")

    # ── Handlers ──────────────────────────────────────────────────────

    def _on_raster_change(self, key):
        self._raster_mode = key
        for k, b in self._btn_raster.items():
            b.setChecked(k == key)
        if key == "vertical":
            self.width_label_widget.setText(self.t.get("target_height", "Target Height"))
            self.lbl_force_width.setText(self.t.get("force_height", "Force Exact Height"))
        else:
            self.width_label_widget.setText(self.t.get("target_width", "Target Width"))
            self.lbl_force_width.setText(self.t.get("force_width", "Force Exact Width"))
        self._schedule_preview()

    def _on_origin_change(self, value):
        self.custom_offset_frame.setVisible(value == "Custom")

    def _on_framing_toggle(self, _=None):
        self._update_framing_state()

    def _update_framing_state(self):
        is_pointing = self.sw_pointer.isChecked()
        is_framing  = self.sw_frame.isChecked()
        any_active  = is_pointing or is_framing
        self.pause_cmd_entry.setEnabled(any_active)
        self.frame_power_entry.setEnabled(any_active)
        if "frame_feed_ratio_menu" in self.controls:
            self.controls["frame_feed_ratio_menu"]["combo"].setEnabled(is_framing)

    def _on_switch_with_delay(self, _=None):
        QTimer.singleShot(120, self._schedule_preview)

    def _schedule_preview(self):
        if not self._loading:
            self._debounce_timer.start(80)

    # ── Loading Overlay ───────────────────────────────────────────────

    def _show_loading(self, msg=None):
        if hasattr(self, "_overlay"):
            return
        if msg is None:
            msg = self.t.get("loading", "Loading…")
        self._overlay = show_loading_overlay(self, msg)

    def _hide_loading(self):
        if hasattr(self, "_overlay"):
            hide_loading_overlay(self._overlay)
            del self._overlay

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_overlay"):
            self._overlay.resize(self.size())

    # ── Rendu / Preview ───────────────────────────────────────────────

    def _initial_render(self):
        # Overlay uniquement si une image est présente
        if self.input_image_path and os.path.exists(self.input_image_path):
            self._show_loading(self.t.get("loading", "Loading…"))
        try:
            self._do_update_preview(fit=True)
        finally:
            self._hide_loading()

    def _do_update_preview(self, fit=False):
        if self._loading:
            return
        if not self.input_image_path or not os.path.isfile(self.input_image_path):
            self._canvas._after_draw_cb = None
            self._canvas.set_overlay(None)
            self._canvas.redraw(fit=fit)
            return

        res = self.process_logic()

        if not res or res[0] is None:
            if self._img_plot:
                self._img_plot.set_visible(False)
            self._canvas._after_draw_cb = None
            self._canvas.set_overlay(None)
            self._canvas.redraw(fit=fit)
            return

        matrix, geom = res
        real_w = geom["real_w"]
        real_h = geom["real_h"]
        rf     = geom["rect_full"]
        offX, offY = self.calculate_offsets(real_w, real_h)
        v_min = self._get_val("min_p") or 0
        v_max = self._get_val("max_p") or 255

        # Nettoyage overscan patches + textes
        for p in self._overscan_patches:
            try: p.remove()
            except Exception: pass
        self._overscan_patches = []

        for t in self._overscan_texts:
            try: t.remove()
            except Exception: pass
        self._overscan_texts = []

        if self._rect_overscan is not None:
            try: self._rect_overscan.remove()
            except Exception: pass
            self._rect_overscan = None

        self._update_image_artist(matrix, offX, offY, real_w, real_h, v_min, v_max)

        # Colorbar Qt fixe
        self._cbar_widget.set_range(v_min, v_max,
                                    self.t.get("laser_power_level", "Laser Power"))

        # Overscan — calcul des rectangles (coordonnées mm exactes)
        direction = self._raster_mode
        ax = self._ax

        if direction == "horizontal":
            global_y = offY;  global_h = real_h
            ow_l = abs(rf[0]);  ow_r = rf[2] - real_w
            overscan_rects = []
            if ow_l > 0.1: overscan_rects.append((offX + rf[0], offY, ow_l, real_h))
            if ow_r > 0.1: overscan_rects.append((offX + real_w, offY, ow_r, real_h))
        else:
            oh_b = abs(rf[1]);  oh_t = rf[3] - real_h
            global_y = offY + rf[1];  global_h = rf[3] - rf[1]
            overscan_rects = []
            if oh_b > 0.1: overscan_rects.append((offX, offY + rf[1], real_w, oh_b))
            if oh_t > 0.1: overscan_rects.append((offX, offY + real_h, real_w, oh_t))

        border_rect = (offX + rf[0], global_y, rf[2] - rf[0], global_h)

        decal = 0.5
        ax.set_xlim(offX + rf[0] - decal, offX + rf[2] + decal)
        ax.set_ylim(global_y - decal, global_y + global_h + decal)
        ax.tick_params(top=True, right=True, which="both")
        # Labels masqués dans matplotlib → redessinés en QPainter natif (nets au zoom)
        ax.xaxis.set_tick_params(labelbottom=False, labeltop=False)
        ax.yaxis.set_tick_params(labelleft=False,   labelright=False)
        ax.tick_params(axis="both", colors="#888888", length=4, width=1)
        ax.set_axisbelow(False)
        ax.grid(False)   # grille redessinée en QPainter natif (nette au zoom)

        if self._origin_marker:
            try: self._origin_marker[0].remove()
            except Exception: pass
        self._origin_marker = None   # redessiné en QPainter natif

        # Callback appelé par redraw() après tight_layout+draw() — transData valide ici
        def _build_overlay(pw, ph):
            td  = ax.transData
            tax = ax.transAxes

            def m2p(mx, my):
                d = td.transform((mx, my))
                return float(d[0]), float(ph - d[1])

            xlim = tuple(ax.get_xlim())
            ylim = tuple(ax.get_ylim())

            # Ticks réels de matplotlib (filtrés dans les limites)
            yticks = [v for v in ax.get_yticks() if ylim[0] - 1e-9 <= v <= ylim[1] + 1e-9]
            xticks = [v for v in ax.get_xticks() if xlim[0] - 1e-9 <= v <= xlim[1] + 1e-9]

            # Bords de l'axe en pixels pixmap
            ax_x0d, ax_y0d = tax.transform((0, 0))
            ax_x1d, ax_y1d = tax.transform((1, 1))
            ax_left  = float(ax_x0d)
            ax_right = float(ax_x1d)
            ax_top   = float(ph - ax_y1d)
            ax_bot   = float(ph - ax_y0d)

            def fmt_val(v):
                if v == int(v):
                    return str(int(v))
                return f"{v:.1f}"

            self._canvas.set_overlay({
                'transform':      m2p,
                'xlim':           xlim,
                'ylim':           ylim,
                'overscan_rects': overscan_rects,
                'border_rect':    border_rect,
                'origin':         (0.0, 0.0),
                'grid_xs':        list(xticks),
                'grid_ys':        list(yticks),
                'yticks':         [(v, fmt_val(v)) for v in yticks],
                'xticks':         [(v, fmt_val(v)) for v in xticks],
                'ax_left':        ax_left,
                'ax_right':       ax_right,
                'ax_top':         ax_top,
                'ax_bot':         ax_bot,
                'direction':      direction,
            })

        self._canvas._after_draw_cb = _build_overlay

        est_min = geom.get("est_min", 0.0)
        ts = int(est_min * 60)
        hh, mm, ss = ts // 3600, (ts % 3600) // 60, ts % 60
        self._update_stats(geom["w_px"], geom["h_px"], real_w, real_h,
                           geom["scan_step"], geom["l_step"], hh, mm, ss)

        self._hist_widget.update_data(
            matrix, v_min, v_max,
            label_title=self.t_stats.get("power_distribution", "Power Distribution"),
            label_power=self.t_stats.get("power_value", "Power"),
            label_count=self.t_stats.get("pixel_count", "Pixel count"),
        )

        self._canvas.redraw(fit=fit)

    def _update_image_artist(self, matrix, offX, offY, real_w, real_h, v_min, v_max):
        if self._placeholder_text is not None:
            try: self._placeholder_text.remove()
            except Exception: pass
            self._placeholder_text = None

        img_extent = [offX, offX + real_w, offY, offY + real_h]

        if self._img_plot is None:
            self._img_plot = self._ax.imshow(
                matrix, cmap="gray_r", origin="upper",
                extent=img_extent, aspect="equal",
                vmin=v_min, vmax=v_max,
                interpolation="nearest", zorder=1
            )
        else:
            self._img_plot.set_data(matrix)
            self._img_plot.set_extent(img_extent)
            self._img_plot.set_clim(v_min, v_max)
            self._img_plot.set_visible(True)

    def _update_stats(self, w_px, h_px, real_w, real_h,
                      scan_step, line_step, hh, mm, ss):
        ts = self.t_stats
        lines = [
            f"{ts.get('real_dims','REAL DIMS'):<18}: {real_w:.2f} x {real_h:.2f} mm",
            f"{ts.get('est_time','EST. TIME'):<18}: {hh:02d}:{mm:02d}:{ss:02d}",
            f"{ts.get('file_size','FILE SIZE'):<18}: {self.estimated_file_size}",
            f"{ts.get('matrix_size','MATRIX'):<18}: {w_px} x {h_px} px",
            f"{ts.get('scan_step','SCAN STEP'):<18}: {scan_step:.4f} mm",
            f"{ts.get('line_step','LINE STEP'):<18}: {line_step:.4f} mm",
        ]
        for lbl, txt in zip(self.stats_labels, lines):
            lbl.setText(txt)

    # ── Logique moteur ────────────────────────────────────────────────

    def process_logic(self):
        if not self.input_image_path or not os.path.isfile(self.input_image_path):
            return None, None
        try:
            ui_dim      = self._get_val("width")
            raster_mode = self._raster_mode

            settings = {
                "line_step":    self._get_val("line_step"),
                "gamma":        self._get_val("gamma"),
                "contrast":     self._get_val("contrast"),
                "thermal":      self._get_val("thermal"),
                "min_p":        self._get_val("min_p"),
                "max_p":        self._get_val("max_p"),
                "dpi":          self._get_val("dpi"),
                "gray_steps":   self._get_val("gray_steps"),
                "premove":      self._get_val("premove"),
                "feedrate":     self._get_val("feedrate"),
                "speed":        self._get_val("feedrate"),
                "invert":       self.sw_invert.isChecked(),
                "ui_dimension": ui_dim,
                "raster_mode":  raster_mode,
                "force_dim":    self.sw_force_width.isChecked(),
            }
            if settings["force_dim"]:
                if raster_mode == "horizontal":
                    settings["width"]  = ui_dim
                else:
                    settings["height"] = ui_dim

            current_cache = None
            if self._source_img_path == self.input_image_path:
                current_cache = self._source_img_cache

            results = self.engine.process_image_logic(
                self.input_image_path, settings,
                source_img_cache=current_cache
            )
            matrix, img_obj, geom, mem_warn = results

            if raster_mode == "vertical":
                geom["machine_step_x"] = geom.get("y_step", 0.1)
                geom["machine_step_y"] = geom.get("x_step", 0.1)
            else:
                geom["machine_step_x"] = geom.get("x_step", 0.1)
                geom["machine_step_y"] = geom.get("y_step", 0.1)

            self._source_img_cache   = img_obj
            self._source_img_path    = self.input_image_path
            self._last_matrix        = matrix
            self._last_geom          = geom
            self.estimated_file_size = geom.get("file_size_str", "N/A")
            return matrix, geom

        except Exception as e:
            import traceback; traceback.print_exc()
            return None, None

    def calculate_offsets(self, real_w, real_h):
        origin_ctrl = self.controls.get("origin_mode")
        origin_key  = "Lower-Left"
        if origin_ctrl:
            combo = origin_ctrl["combo"]
            ud = combo.currentData()
            origin_key = ud if ud else combo.currentText()
        cx = self._get_val("custom_x") or 0.0
        cy = self._get_val("custom_y") or 0.0
        return self.engine.calculate_offsets(origin_key, real_w, real_h, cx, cy)

    def _get_val(self, key, default=0.0):
        ctrl = self.controls.get(key)
        if not ctrl: return default
        try:
            return float(ctrl["entry"].text().replace(",", "."))
        except (ValueError, AttributeError):
            return default

    # ── Génération G-Code ─────────────────────────────────────────────

    def generate_gcode(self):
        self.save_settings()
        res = self.process_logic()
        if not res or res[0] is None:
            QMessageBox.warning(self, "No image", "Please select a valid image first.")
            return

        matrix, geom = res
        real_w  = geom["real_w"]
        real_h  = geom["real_h"]
        offX, offY = self.calculate_offsets(real_w, real_h)

        raster_mode  = self._raster_mode
        cmd_mode_val = self.controls["cmd_mode"]["combo"].currentText() \
            if "cmd_mode" in self.controls else "M67 (Analog)"
        firing_val   = self.controls["firing_mode"]["combo"].currentText() \
            if "firing_mode" in self.controls else "M3/M5"
        origin_val   = (self.controls["origin_mode"]["combo"].currentData()
                        or self.controls["origin_mode"]["combo"].currentText()) \
            if "origin_mode" in self.controls else "Lower-Left"

        ratio_raw = "20%"
        if "frame_feed_ratio_menu" in self.controls:
            ratio_raw = self.controls["frame_feed_ratio_menu"]["combo"].currentText()

        global_h = self.controller.config_manager.get_item("machine_settings", "custom_header", "").strip()
        global_f = self.controller.config_manager.get_item("machine_settings", "custom_footer", "").strip()
        raster_h = self.txt_header.toPlainText().strip()
        raster_f = self.txt_footer.toPlainText().strip()
        full_header = f"{global_h}\n{raster_h}".strip() if global_h and raster_h else (global_h or raster_h)
        full_footer = f"{raster_f}\n{global_f}".strip() if global_f and raster_f else (global_f or raster_f)

        file_ext  = self.controller.config_manager.get_item("machine_settings", "gcode_extension", ".nc")
        file_name = (os.path.splitext(os.path.basename(self.input_image_path))[0]
                     if self.input_image_path else "export")

        payload = {
            "matrix": matrix,
            "dims":   (geom["h_px"], geom["w_px"], geom["y_step"], geom["x_step"]),
            "estimated_size": self.estimated_file_size,
            "offsets": (offX, offY),
            "params": {
                "e_num":       int(self._get_val("m67_e_num")),
                "use_s_mode":  "S (Spindle)" in cmd_mode_val,
                "ctrl_max":    self._get_val("ctrl_max"),
                "min_power":   self._get_val("min_p"),
                "max_power":   self._get_val("max_p"),
                "premove":     self._get_val("premove"),
                "feedrate":    self._get_val("feedrate"),
                "laser_latency":   self._get_val("laser_latency"),
                "gray_scales": int(self._get_val("gray_steps")),
                "gray_steps":  int(self._get_val("gray_steps")),
                "raster_mode": raster_mode,
            },
            "framing": {
                "is_pointing":   self.sw_pointer.isChecked(),
                "is_framing":    self.sw_frame.isChecked(),
                "f_pwr":         self.frame_power_entry.text(),
                "f_ratio":       ratio_raw.replace("%", ""),
                "f_pause":       self.pause_cmd_entry.text().strip() or None,
                "use_s_mode":    "S (Spindle)" in cmd_mode_val,
                "e_num":         int(self._get_val("m67_e_num")),
                "base_feedrate": self._get_val("feedrate"),
            },
            "text_blocks": {"header": full_header, "footer": full_footer},
            "metadata": {
                "version":          self.version,
                "mode":             cmd_mode_val.split(" ")[0],
                "firing_cmd":       firing_val.split("/")[0],
                "file_extension":   file_ext,
                "file_name":        file_name,
                "output_dir":       self.output_dir,
                "origin_mode":      origin_val,
                "real_w":           real_w,
                "real_h":           real_h,
                "est_sec":          int(geom.get("est_min", 0) * 60),
                "raster_direction": raster_mode,
            }
        }

        self.controller.show_simulation(self.engine, payload, return_view="raster")

    # ── Sélection fichiers ────────────────────────────────────────────

    def select_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Image files (*.jpg *.jpeg *.png *.bmp)"
        )
        if path:
            self.input_image_path = path
            self.btn_input.setText(os.path.basename(path).upper())
            self.btn_input.setStyleSheet(self._btn_style(bg="#2d5a27", hover="#367a31"))
            self._canvas.request_auto_fit()
            self._canvas._fit_next = True
            self._schedule_preview()

    def select_output(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if directory:
            self.output_dir = directory
            folder = os.path.basename(directory) or directory
            self.btn_output.setText(f"OUT: {folder.upper()}/")
            self.btn_output.setStyleSheet(self._btn_style(bg="#2d5a27", hover="#367a31"))

    # ── Profils ───────────────────────────────────────────────────────

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile",
            os.path.join(self.application_path, "alig_profile.json"),
            "JSON (*.json)"
        )
        if path:
            data = self._collect_settings()
            machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "laser_latency"]
            export = {
                "machine_settings": {k: data.pop(k) for k in machine_keys if k in data},
                "raster_settings": data
            }
            success, err = save_json_file(path, export)
            if success:
                QMessageBox.information(self, "Export", "Profile saved successfully.")
            else:
                QMessageBox.critical(self, "Error", f"Export failed:\n{err}")

    def load_profile_from(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Profile", self.application_path, "JSON (*.json)"
        )
        if path:
            data, err = load_json_file(path)
            if data:
                if "machine_settings" in data:
                    self._apply_settings(data.get("machine_settings", {}), is_machine=True)
                if "raster_settings" in data:
                    self._apply_settings(data.get("raster_settings", {}))
                else:
                    self._apply_settings(data)
                self._schedule_preview()
                QMessageBox.information(self, "Profile", f"Loaded:\n{os.path.basename(path)}")
            else:
                QMessageBox.critical(self, "Error", f"Could not load:\n{err}")

    # ── Save / Load settings ──────────────────────────────────────────

    def save_settings(self):
        all_data = self._collect_settings()
        machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "laser_latency"]
        machine_updates = {k: all_data.pop(k) for k in machine_keys if k in all_data}

        current_machine = self.controller.config_manager.get_section("machine_settings") or {}
        current_machine.update(machine_updates)
        self.controller.config_manager.set_section("machine_settings", current_machine)
        self.controller.config_manager.set_section("raster_settings", all_data)
        self.controller.config_manager.save()

    def load_settings(self):
        machine_data = self.controller.config_manager.get_section("machine_settings") or {}
        raster_data  = self.controller.config_manager.get_section("raster_settings")  or {}

        self._loading = True
        self._apply_settings(machine_data, is_machine=True)
        self._apply_settings(raster_data)
        self._loading = False

        self.refresh_global_previews()

    def _collect_settings(self):
        data = {}
        for k, ctrl in self.controls.items():
            if "combo" in ctrl:
                ud = ctrl["combo"].currentData()
                data[k] = ud if ud else ctrl["combo"].currentText()
            elif "entry" in ctrl:
                try:
                    data[k] = float(ctrl["entry"].text().replace(",", "."))
                except ValueError:
                    data[k] = ctrl["entry"].text()

        data["input_path"]      = self.input_image_path
        data["output_dir"]      = self.output_dir
        data["custom_header"]   = self.txt_header.toPlainText().strip()
        data["custom_footer"]   = self.txt_footer.toPlainText().strip()
        data["include_frame"]   = self.sw_frame.isChecked()
        data["include_pointer"] = self.sw_pointer.isChecked()
        data["force_width"]     = self.sw_force_width.isChecked()
        data["invert_relief"]   = self.sw_invert.isChecked()
        data["frame_power"]     = self.frame_power_entry.text()
        data["custom_pause_cmd"]= self.pause_cmd_entry.text()
        data["raster_mode"]     = self._raster_mode
        return data

    def _apply_settings(self, data, is_machine=False):
        if not data: return

        for k, v in data.items():
            if k not in self.controls: continue
            ctrl = self.controls[k]
            if "combo" in ctrl:
                combo = ctrl["combo"]
                for i in range(combo.count()):
                    if combo.itemData(i) == v or combo.itemText(i) == str(v):
                        combo.setCurrentIndex(i)
                        break
            elif "entry" in ctrl:
                try:
                    is_int = ctrl.get("is_int", False)
                    prec   = ctrl.get("precision", 2)
                    fmt = "{:d}" if is_int else f"{{:.{prec}f}}"
                    val = float(v)
                    ctrl["entry"].setText(fmt.format(int(val) if is_int else val))
                    sl = ctrl.get("slider")
                    if sl and sl is not ctrl["entry"]:
                        sl.setValue(int(val) if is_int else int(val * 100))
                except (ValueError, TypeError):
                    pass

        sw_map = {
            "invert_relief":   self.sw_invert,
            "include_frame":   self.sw_frame,
            "include_pointer": self.sw_pointer,
            "force_width":     self.sw_force_width,
        }
        for key, sw in sw_map.items():
            if key in data:
                sw.setChecked(bool(data[key]))

        if "raster_mode" in data:
            self._on_raster_change(data["raster_mode"])

        if not is_machine:
            raw_path = data.get("input_path", "")
            if raw_path and os.path.isfile(raw_path):
                self.input_image_path = raw_path
                self.btn_input.setText(os.path.basename(raw_path).upper())
                self.btn_input.setStyleSheet(self._btn_style(bg="#2d5a27", hover="#367a31"))

            out = data.get("output_dir", "")
            if out:
                self.output_dir = out
                folder = os.path.basename(out) or out
                self.btn_output.setText(f"OUT: {folder.upper()}/")
                self.btn_output.setStyleSheet(self._btn_style(bg="#2d5a27", hover="#367a31"))

            if "custom_header" in data:
                self.txt_header.setPlainText(data["custom_header"])
            if "custom_footer" in data:
                self.txt_footer.setPlainText(data["custom_footer"])
            if "frame_power" in data:
                self.frame_power_entry.setText(str(data["frame_power"]))
            if "custom_pause_cmd" in data:
                self.pause_cmd_entry.setText(str(data["custom_pause_cmd"]))
            if data.get("origin_mode") == "Custom":
                self.custom_offset_frame.setVisible(True)

            self._update_framing_state()

    # ── Lock machine params ───────────────────────────────────────────

    def toggle_machine_lock(self):
        self.is_locked = not self.is_locked
        self.apply_lock_state()

    def apply_lock_state(self):
        self.lock_btn.setText("🔒" if self.is_locked else "🔓")
        self._machine_container.setEnabled(not self.is_locked)
        style = ("background:#444;" if self.is_locked else "background:#D32F2F;")
        self.lock_btn.setStyleSheet(
            f"QPushButton{{{style}color:white;border-radius:4px;border:none;font-size:13px;}}"
            "QPushButton:hover{background:#666;}"
        )

    # ── Global previews ───────────────────────────────────────────────

    def refresh_global_previews(self):
        gh = self.controller.config_manager.get_item("machine_settings", "custom_header", "")
        gf = self.controller.config_manager.get_item("machine_settings", "custom_footer", "")
        self.txt_global_header_preview.setPlainText(
            gh if gh else self.t.get("no_global_header", "(Machine Settings Header…)"))
        self.txt_global_footer_preview.setPlainText(
            gf if gf else self.t.get("no_global_footer", "(Machine Settings Footer…)"))

    # ── Traduction dynamique ──────────────────────────────────────────

    def update_texts(self):
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        if not lang or lang not in TRANSLATIONS:
            lang = "English"
        self._lang   = lang
        self.t       = TRANSLATIONS[lang]["common"]
        self.t_stats = TRANSLATIONS[lang]["stats"]
        self.t_orig  = TRANSLATIONS[lang]["origin_options"]

        translate_ui_widgets(self.translation_map, self.t)

        self._tabs.setTabText(0, self.t.get("geometry", "Geometry"))
        self._tabs.setTabText(1, self.t.get("image",    "Image"))
        self._tabs.setTabText(2, self.t.get("laser",    "Laser"))
        self._tabs.setTabText(3, self.t.get("gcode",    "G-Code"))

        for key, btn in self._btn_raster.items():
            btn.setText(self.t.get(key, key.capitalize()))

        self.refresh_global_previews()