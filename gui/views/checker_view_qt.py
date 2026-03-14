# -*- coding: utf-8 -*-
"""
A.L.I.G. - CheckerViewQt
Lecteur / visualiseur de G-Code existant.
Ouvre un fichier .nc/.gcode, le parse et lance la simulation de trajectoire.
Aucune génération d'image — uniquement lecture + rendu.
"""

import os
import time
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QSizePolicy, QFileDialog, QMessageBox, QPlainTextEdit,
    QDoubleSpinBox,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRect, QRectF, QPointF, QLineF, QSize
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QImage, QPixmap, QFont,
    QLinearGradient, QPainterPath, QPolygonF, QTransform, QIcon
)

from engine.gcode_parser import GCodeParser
from core.utils import truncate_path
from core.translations import TRANSLATIONS
from utils.paths import SVG_ICONS
from gui.utils_qt import get_svg_pixmap
from gui.switch import Switch


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER : génération G-Code hors thread UI
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#  RENDERER  —  logique de rasterisation batch (100 % NumPy + une passe QPainter)
# ══════════════════════════════════════════════════════════════════════════════

class _Renderer:
    """
    Stratégie haute perf :
      1. _compute_segments()  vectorise TOUS les segments éligibles en une fois
         via NumPy  →  tableau de QPolygonF groupés par couleur.
      2. _rasterize()  ouvre UN QPainter sur le QImage et dessine tous les
         polygones en une seule boucle Python sans calcul dans la boucle.
      3. Résultat copié dans display_data uint8.
    """

    def __init__(self, rect_w, rect_h, scale, total_px_h,
                 min_x, min_y, laser_width_px, ctrl_max,
                 pwr_min=0.0, pwr_max=None, l_step_mm=None, draw_step_mm=None):
        self.rect_w         = rect_w
        self.rect_h         = rect_h
        self.scale          = scale
        self.total_px_h     = total_px_h
        self.min_x          = min_x
        self.min_y          = min_y
        self.laser_width_px = max(1, int(round(float(laser_width_px))))
        self.ctrl_max       = float(ctrl_max)
        self.pwr_min        = float(pwr_min)
        self.pwr_max        = float(pwr_max) if pwr_max is not None else self.ctrl_max
        # l_step_mm : espacement réel inter-lignes → snap Y (pas de gaps)
        self.l_step_mm      = float(l_step_mm) if l_step_mm else None
        self.l_step_px      = float(l_step_mm) * scale if l_step_mm else None
        # draw_step_mm : épaisseur du trait laser (valeur utilisateur)
        # Si None, utilise l_step_mm (comportement identique à avant)
        _draw = draw_step_mm if draw_step_mm else l_step_mm
        self.draw_step_px   = float(_draw) * scale if _draw else None
        self.display_data   = np.full((rect_h, rect_w), 255, dtype=np.uint8)
        self._qi_ref        = None

    def reset(self):
        self.display_data.fill(255)

    # ─── Calcul des segments à rasteriser ───────────────────────────────────

    def _compute_segments(self, pts_arr, start, end, use_lat, lat_mm, scan_axis):
        """
        Retourne {gray: [(x1,y1,x2,y2)...]} en coordonnées pixels flottantes.
        Les lignes raster horizontales sont stabilisées par index de ligne.
        """

        if pts_arr is None or len(pts_arr) < 2:
            return None
        if start >= end or start >= len(pts_arr) - 1:
            return None

        safe_end = min(end, len(pts_arr) - 1)

        p1 = pts_arr[start:safe_end].copy()
        p2 = pts_arr[start+1:safe_end+1].copy()
        if len(p1) == 0:
            return None

        # ── filtre puissance
        laser_threshold = max(self.pwr_min, self.ctrl_max * 0.001)
        mask = p2[:,2] > laser_threshold
        if not mask.any():
            return None

        p1 = p1[mask]
        p2 = p2[mask]

        x1 = p1[:,0].copy()
        y1_mm = p1[:,1].copy()
        x2 = p2[:,0].copy()
        y2_mm = p2[:,1].copy()

        # ── correction latence
        if use_lat and lat_mm != 0:
            if scan_axis == 'X':
                d = x2 - x1
                x1[d>1e-6] += lat_mm
                x2[d>1e-6] += lat_mm
                x1[d<-1e-6] -= lat_mm
                x2[d<-1e-6] -= lat_mm
            else:
                d = y2_mm - y1_mm
                y1_mm[d>1e-6] += lat_mm
                y2_mm[d>1e-6] += lat_mm
                y1_mm[d<-1e-6] -= lat_mm
                y2_mm[d<-1e-6] -= lat_mm

        # ── conversion mm → pixels
        sc  = self.scale
        mnx = self.min_x
        mny = self.min_y
        th  = self.total_px_h

        fx1 = (x1 - mnx) * sc
        fy1 = th - (y1_mm - mny) * sc

        fx2 = (x2 - mnx) * sc
        fy2 = th - (y2_mm - mny) * sc

        # ── rejet hors buffer
        lw = self.laser_width_px
        bw = float(self.rect_w)
        bh = float(self.rect_h)

        ok = (
            (np.maximum(fx1,fx2) >= -lw) &
            (np.minimum(fx1,fx2) < bw+lw) &
            (np.maximum(fy1,fy2) >= -lw) &
            (np.minimum(fy1,fy2) < bh+lw)
        )

        if not ok.any():
            return None

        fx1=fx1[ok]; fy1=fy1[ok]
        fx2=fx2[ok]; fy2=fy2[ok]
        pwr=p2[:,2][ok]
        y1_mm=y1_mm[ok]; y2_mm=y2_mm[ok]

        # ── filtre longueur : ne rejeter que les segments strictement nuls
        dx = fx2 - fx1
        dy = fy2 - fy1

        vis = (dx*dx + dy*dy) > 0.0
        if not vis.any():
            return None

        fx1=fx1[vis]; fy1=fy1[vis]
        fx2=fx2[vis]; fy2=fy2[vis]
        pwr=pwr[vis]
        y1_mm=y1_mm[vis]; y2_mm=y2_mm[vis]

        # ── couleur
        pwr_range = max(self.pwr_max - self.pwr_min,1.0)
        t = np.clip((pwr - self.pwr_min)/pwr_range,0.0,1.0)
        gray = (200.0*(1.0-t)).astype(np.uint8)

        # ─────────────────────────────
        # SNAP RASTER HORIZONTAL STABLE
        # ─────────────────────────────

        is_horiz = np.abs(fx2-fx1) >= np.abs(fy2-fy1)

        if self.l_step_mm and self.l_step_px:

            step_mm = self.l_step_mm
            step_px = self.l_step_px

            yc_mm = (y1_mm + y2_mm) * 0.5

            # index stable (pas de round)
            row_idx = np.floor((yc_mm - mny)/step_mm + 0.5).astype(np.int32)
            row_idx = np.maximum(row_idx,0)

            # centre exact de ligne
            fy_center = th - (row_idx + 0.5) * step_px

            fy1 = np.where(is_horiz, fy_center, fy1)
            fy2 = np.where(is_horiz, fy_center, fy2)

        else:

            fy_center = np.floor((fy1+fy2)*0.5)+0.5
            fy1 = np.where(is_horiz,fy_center,fy1)
            fy2 = np.where(is_horiz,fy_center,fy2)

        # ── snap X pour segments verticaux
        fx_center = np.floor((fx1+fx2)*0.5)+0.5

        fx1 = np.where(~is_horiz,fx_center,fx1)
        fx2 = np.where(~is_horiz,fx_center,fx2)

        # ── regroupement par gris
        result={}

        for i in range(len(gray)):
            c=int(gray[i])
            if c not in result:
                result[c]=[]
            result[c].append((fx1[i],fy1[i],fx2[i],fy2[i]))

        return result

    # ─── Rasterisation via fillRect (pixel-perfect) ──────────────────────────

    def _rasterize(self, segs_by_color):
        """Dessine les segments sous forme de rectangles pixel-parfaits."""
        if not segs_by_color:
            return

        h, w = self.display_data.shape

        # draw_step_px : épaisseur du trait (valeur utilisateur)
        # l_step_px : espacement inter-lignes (snap Y) — peut être différent
        step = self.draw_step_px if self.draw_step_px else (self.l_step_px if self.l_step_px else float(self.laser_width_px))
        half = step / 2.0

        qi = QImage(w, h, QImage.Format.Format_Grayscale8)
        qi.fill(QColor(255, 255, 255))

        qp = QPainter(qi)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        qp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        qp.setPen(Qt.PenStyle.NoPen)

        for c, segs in segs_by_color.items():

            qp.setBrush(QBrush(QColor(c, c, c)))

            for (x1, y1, x2, y2) in segs:

                # segment horizontal
                if abs(y2 - y1) < abs(x2 - x1):

                    left  = int(np.floor(min(x1, x2)))
                    right = int(np.ceil(max(x1, x2)))

                    top = int(np.floor(y1 - half))

                    qp.fillRect(
                        left,
                        top,
                        max(1, right - left),
                        int(round(step)),
                        QColor(c, c, c)
                    )

                # segment vertical
                else:

                    top    = int(np.floor(min(y1, y2)))
                    bottom = int(np.ceil(max(y1, y2)))

                    left = int(np.floor(x1 - half))

                    qp.fillRect(
                        left,
                        top,
                        int(round(step)),
                        max(1, bottom - top),
                        QColor(c, c, c)
                    )

        qp.end()

        bpl = qi.bytesPerLine()
        ptr = qi.bits()
        ptr.setsize(bpl * h)

        new_arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)[:, :w]
        np.minimum(self.display_data, new_arr, out=self.display_data)

        self._qi_ref = qi

    # ─── API publique ────────────────────────────────────────────────────────

    def redraw_range(self, pts_arr, start, end, use_lat, lat_mm, scan_axis):
        """Repart d'un fond blanc et dessine [start, end)."""
        self.display_data.fill(255)
        polys = self._compute_segments(pts_arr, start, end, use_lat, lat_mm, scan_axis)
        self._rasterize(polys)

    def draw_incremental(self, pts_arr, start, end, use_lat, lat_mm, scan_axis):
        """Ajoute les segments [start, end) sur l'état existant (animation)."""
        polys = self._compute_segments(pts_arr, start, end, use_lat, lat_mm, scan_axis)
        self._rasterize(polys)


# ══════════════════════════════════════════════════════════════════════════════
#  CANVAS DE SIMULATION — rendu + zoom/pan
# ══════════════════════════════════════════════════════════════════════════════

class _SimCanvas(QWidget):
    """
    Affiche display_data (QPixmap mis à jour si dirty) + couche vectorielle
    (grille, laser). Zoom molette, pan clic-gauche.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setStyleSheet('background:#050505;')
        self._bg_color = '#050505'
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        self._pixmap    = None
        self._dirty     = False
        self._img_buf   = None
        self._x0 = self._y0 = 0.0
        self._pw = self._ph  = 0.0
        self._sc = 1.0
        self._mnx = self._mxx = 0.0
        self._mny = self._mxy = 0.0
        self._lx = self._ly = 0.0
        self._zoom   = 1.0
        self._pan    = QPointF(0, 0)
        self._p0     = None
        self._p0_pan = None
        self._mouse_mm = None
        self._overlay_h = 150
        self._placeholder_text = 'Open a G-Code file to start'

    # ─── API ─────────────────────────────

    def setup(self, img_buf, x0, y0, pw, ph, sc, mnx, mxx, mny, mxy, l_step=0.1, overlay_h=150):
        self._img_buf = img_buf
        self._x0, self._y0 = x0, y0
        self._pw, self._ph = pw, ph
        self._sc = sc
        self._mnx, self._mxx = mnx, mxx
        self._mny, self._mxy = mny, mxy
        self._l_step = l_step
        self._overlay_h = overlay_h
        self._rebuild()
        self._dirty = False
        # Fit-to-view automatique après setup
        self.reset_view()

    def notify_dirty(self):
        self._dirty = True
        self.update()

    def set_theme(self, bg: str):
        self._bg_color = bg
        self.setStyleSheet(f'background:{bg};')
        self.update()

    def set_placeholder(self, text: str):
        self._placeholder_text = text
        if self._img_buf is None:
            self.update()

    def set_laser(self, sx, sy):
        self._lx, self._ly = sx, sy
        self.update()

    def reset_view(self):
        """Fit-to-view : zoom et pan pour que l'image remplisse la zone utile."""
        if self._pw <= 0 or self._ph <= 0:
            self._zoom = 1.0
            self._pan  = QPointF(0, 0)
            self.update()
            return

        cw, ch = self.width(), self.height()
        if cw <= 1 or ch <= 1:
            return

        # Zone utile : toute la largeur, hauteur sans overlay (stockée dans _overlay_h)
        overlay_h = getattr(self, '_overlay_h', 150)
        usable_w = cw
        usable_h = max(ch - overlay_h, int(ch * 0.5))

        margin = 12  # px de marge autour de l'image

        # Zoom pour que l'image tienne dans la zone utile avec marge
        zoom_x = (usable_w - 2 * margin) / self._pw
        zoom_y = (usable_h - 2 * margin) / self._ph
        self._zoom = min(zoom_x, zoom_y)

        # Pan pour centrer l'image dans la zone utile
        img_screen_w = self._pw * self._zoom
        img_screen_h = self._ph * self._zoom

        pan_x = (usable_w - img_screen_w) / 2.0 - self._x0 * self._zoom
        pan_y = margin - self._y0 * self._zoom  # calé en haut avec marge

        self._pan = QPointF(pan_x, pan_y)
        self.update()

    # ─── Rendu ───────────────────────────

    def _rebuild(self):
        if self._img_buf is None:
            self._pixmap = None; return
        h, w = self._img_buf.shape
        qi = QImage(self._img_buf.tobytes(), w, h, w,
                    QImage.Format.Format_Grayscale8)
        self._pixmap = QPixmap.fromImage(qi)

    def paintEvent(self, _):
        if self._dirty:
            self._rebuild()
            self._dirty = False

        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        qp.fillRect(0, 0, w, h, QColor(self._bg_color))

        if self._img_buf is None:
            qp.setPen(QColor('#888888'))
            qp.setFont(QFont('Arial', 13))
            qp.drawText(QRect(0, 0, w, h),
                        Qt.AlignmentFlag.AlignCenter, self._placeholder_text)
            qp.end(); return

        # Zoom / pan
        t = QTransform()
        t.translate(self._pan.x(), self._pan.y())
        t.scale(self._zoom, self._zoom)
        qp.setTransform(t)

        # Fond blanc
        qp.fillRect(QRectF(self._x0, self._y0, self._pw, self._ph),
                    QColor('white'))

        # Image simulation
        if self._pixmap:
            qp.drawPixmap(int(self._x0), int(self._y0), self._pixmap)

        # Grille
        pen_g = QPen(QColor(180, 180, 180, 140), 0.5, Qt.PenStyle.DashLine)
        pen_g.setDashPattern([4, 6])
        qp.setFont(QFont('Arial', 7))
        step = 10
        sx0 = int(np.ceil(self._mnx / step) * step)
        for mx in range(sx0, int(self._mxx) + 1, step):
            sx = self._x0 + (mx - self._mnx) * self._sc
            qp.setPen(pen_g)
            qp.drawLine(QLineF(sx, self._y0, sx, self._y0 + self._ph))
            qp.setPen(QColor('#777'))
            qp.drawText(QRectF(sx-15, self._y0+self._ph+1, 30, 13),
                        Qt.AlignmentFlag.AlignCenter, str(mx))
        sy0 = int(np.ceil(self._mny / step) * step)
        for my in range(sy0, int(self._mxy) + 1, step):
            sy = self._y0 + self._ph - (my - self._mny) * self._sc
            qp.setPen(pen_g)
            qp.drawLine(QLineF(self._x0, sy, self._x0 + self._pw, sy))
            qp.setPen(QColor('#777'))
            qp.drawText(QRectF(self._x0-33, sy-7, 30, 13),
                        Qt.AlignmentFlag.AlignRight |
                        Qt.AlignmentFlag.AlignVCenter, str(my))

        # Laser
        lx, ly = self._lx, self._ly
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        qp.setPen(QPen(QColor('#3385ff'), 1))
        qp.setBrush(QBrush(QColor(26, 117, 255, 100)))
        qp.drawEllipse(QPointF(lx, ly), 9, 9)
        qp.setPen(QPen(QColor('white'), 1))
        qp.setBrush(QBrush(QColor('#00ffff')))
        qp.drawEllipse(QPointF(lx, ly), 4, 4)

        # Coordonnées souris
        if self._mouse_mm:
            qp.resetTransform()
            qp.setPen(QColor('#666'))
            qp.setFont(QFont('Consolas', 9))
            mx_mm, my_mm = self._mouse_mm
            qp.drawText(QRect(6, h-18, 220, 15),
                        Qt.AlignmentFlag.AlignLeft,
                        f'X={mx_mm:.2f}  Y={my_mm:.2f} mm')
        qp.end()

    # ─── Zoom / Pan ──────────────────────

    def wheelEvent(self, e):
        if self._img_buf is None:
            return
        factor   = 1.15 if e.angleDelta().y() > 0 else (1.0 / 1.15)
        new_zoom = max(0.05, min(200.0, self._zoom * factor))
        pos = e.position()
        cx, cy = pos.x(), pos.y()
        wx = (cx - self._pan.x()) / self._zoom
        wy = (cy - self._pan.y()) / self._zoom
        self._zoom = new_zoom
        self._pan  = QPointF(cx - wx * self._zoom, cy - wy * self._zoom)
        self.update()

    def mousePressEvent(self, e):
        if e.button() in (Qt.MouseButton.LeftButton,
                          Qt.MouseButton.MiddleButton):
            self._p0 = e.pos()
            self._p0_pan = QPointF(self._pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._p0 is not None:
            d = e.pos() - self._p0
            self._pan = self._p0_pan + QPointF(d.x(), d.y())
            self.update()
        pos = e.position()
        cx, cy = pos.x(), pos.y()
        if self._sc > 0 and self._ph > 0:
            ix = (cx - self._pan.x()) / self._zoom - self._x0
            iy = (cy - self._pan.y()) / self._zoom - self._y0
            self._mouse_mm = (ix/self._sc + self._mnx,
                              self._mny + (self._ph - iy)/self._sc)
            self.update()

    def mouseReleaseEvent(self, e):
        self._p0 = None
        self.setCursor(Qt.CursorShape.ArrowCursor)


# ══════════════════════════════════════════════════════════════════════════════
#  VUE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER : parsing G-Code hors thread UI
# ══════════════════════════════════════════════════════════════════════════════

class _ParseWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, gcode: str):
        super().__init__()
        self.gcode = gcode

    def run(self):
        try:
            parser = GCodeParser({})
            pts, dur, lim = parser.parse(self.gcode)

            if lim is not None and not all(abs(v) < 1e-9 for v in lim):
                bx0, bx1, by0, by1 = lim
            else:
                if pts is not None and len(pts):
                    bx0, bx1 = float(pts[:,0].min()), float(pts[:,0].max())
                    by0, by1 = float(pts[:,1].min()), float(pts[:,1].max())
                else:
                    bx0 = bx1 = by0 = by1 = 0.0

            # Timestamps cumulés
            if pts is not None and len(pts) > 1:
                deltas    = np.diff(pts[:, :2], axis=0)
                distances = np.hypot(deltas[:, 0], deltas[:, 1])
                rates     = pts[1:, 4] / 60.0
                # Feedrate moyen (col 4 avant écrasement) — pour la latence
                feedrate_mmmin = float(np.median(pts[pts[:, 4] > 0, 4])) if (pts[:, 4] > 0).any() else 3000.0
                times     = np.divide(distances, rates,
                                      out=np.zeros_like(distances),
                                      where=rates > 0)
                pts[0, 4]  = 0.0
                pts[1:, 4] = np.cumsum(times)
                total_dur  = float(pts[-1, 4])
            else:
                total_dur = 0.0
                feedrate_mmmin = 3000.0

            self.done.emit({
                'gcode':          self.gcode,
                'pts':            pts,
                'total_dur':      total_dur,
                'bounds':         (bx0, bx1, by0, by1),
                'feedrate_mmmin': feedrate_mmmin,
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            self.error.emit(str(e))


class CheckerViewQt(QWidget):

    def __init__(self, parent, controller, return_view='dashboard'):
        super().__init__(parent)
        self.controller  = controller
        self.return_view = return_view

        lang = controller.config_manager.get_item('machine_settings', 'language')
        if not lang or lang not in TRANSLATIONS:
            lang = 'English'
        self.t = TRANSLATIONS[lang].get('simulation', {})

        # ── état ──────────────────────────────────────────────────
        self.final_gcode     = ''
        self.framing_gcode   = ''
        self.full_metadata   = {}
        self.points_list     = None
        self.framing_end     = 0
        self.total_sec       = 0.0
        self.latence_mm      = 0.0
        self.latence_enabled = False
        self._loaded_path    = ''

        # ── animation ─────────────────────────────────────────────
        self.sim_running      = False
        self.current_idx      = 0
        self.current_sim_time = 0.0
        self.last_frame_time  = 0.0
        self.sim_speed        = 1.0
        self._last_drawn_idx  = -1

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick)

        # ── renderer ──────────────────────────────────────────────
        self._renderer: _Renderer | None = None
        self._px_w = self._px_h = 0.0
        self._x0 = self._y0 = 0.0
        self._scale = 1.0
        self._mnx = self._mxx = 0.0
        self._mny = self._mxy = 0.0

        self.setStyleSheet('background:#2b2b2b; color:white;')
        self._build_ui()

    # ══════════════════════════════════════════════════════════════
    #  CONSTRUCTION UI
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)
        root.addWidget(self._make_left_panel())
        root.addWidget(self._make_right_panel(), stretch=1)

    # ─── Panneau gauche ──────────────────────────────────────────

    def _make_left_panel(self):
        self.left = QFrame()
        self.left.setObjectName('checkerLeft')
        self.left.setFixedWidth(336)
        self.left.setStyleSheet(
            'QFrame#checkerLeft{background:#1e1e1e; border-right:1px solid #333;}')
        lo = QVBoxLayout(self.left)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)

        lo.addWidget(self._make_file_widget())

        self.gl_lbl = QLabel(self.t.get('live_gcode', 'Live G-Code'))
        self.gl_lbl.setStyleSheet('color:white;font-weight:bold;font-size:11px;border:none;')
        lo.addWidget(self.gl_lbl)

        self.gcode_view = QPlainTextEdit()
        self.gcode_view.setReadOnly(True)
        self.gcode_view.setStyleSheet(
            'QPlainTextEdit{background:#1a1a1a;color:#00ff00;'
            'font-family:Consolas;'
            'border:1px solid #333;border-radius:3px;}')
        self._update_gcode_font()
        self.gcode_view.mousePressEvent = self._on_gcode_click
        self.gcode_view.keyPressEvent   = self._on_gcode_key
        lo.addWidget(self.gcode_view, stretch=1)

        lo.addWidget(self._make_action_buttons())
        return self.left

    def _make_file_widget(self):
        """Bouton d'ouverture de fichier + infos du fichier chargé."""
        f = QFrame()
        self._file_frame = f
        f.setStyleSheet('QFrame{background:#252525;border-radius:6px;'
                        'border:1px solid #333;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)

        self.btn_open = QPushButton(self.t.get('open_file', 'Open G-Code file…'))
        self.btn_open.setFixedHeight(38)
        self.btn_open.setStyleSheet(self._gbtn('#1f538d', '#2a6dbd'))
        self.btn_open.clicked.connect(self._on_open_file)
        lo.addWidget(self.btn_open)

        self.lbl_file = QLabel(self.t.get('no_file', 'No file loaded'))
        self.lbl_file.setStyleSheet('color:#888;font-size:10px;border:none;')
        self.lbl_file.setWordWrap(True)
        lo.addWidget(self.lbl_file)

        row = QHBoxLayout()
        self.lbl_size = QLabel('')
        self.lbl_size.setStyleSheet('color:#2ecc71;font-size:10px;'
                                    'font-family:Consolas;border:none;')
        self.lbl_dur = QLabel('')
        self.lbl_dur.setStyleSheet('color:#f39c12;font-size:10px;'
                                   'font-family:Consolas;border:none;')
        self.lbl_dur.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self.lbl_size)
        row.addWidget(self.lbl_dur)
        lo.addLayout(row)

        # ── Champ line_step éditable (non sauvegardé) ──────────────
        step_row = QHBoxLayout()
        self.lbl_lstep = QLabel(self.t.get('line_step_lbl', 'Line step (mm):'))
        self.lbl_lstep.setStyleSheet('color:#aaa;font-size:10px;border:none;')
        step_row.addWidget(self.lbl_lstep)

        self.spin_lstep = QDoubleSpinBox()
        self.spin_lstep.setRange(0.001, 50.0)
        self.spin_lstep.setDecimals(4)
        self.spin_lstep.setSingleStep(0.01)
        self.spin_lstep.setFixedHeight(24)
        self.spin_lstep.setStyleSheet(
            'QDoubleSpinBox{background:#1a1a1a;color:white;border:1px solid #555;'
            'border-radius:3px;font-size:10px;padding:1px 4px;}'
            'QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{width:14px;}'
        )
        # Pré-remplir depuis config (hor_linestep par défaut)
        try:
            default_step = float(
                self.controller.config_manager.get_item('machine_settings', 'hor_linestep', 0.1) or 0.1
            )
        except Exception:
            default_step = 0.1
        self.spin_lstep.setValue(default_step)
        self.spin_lstep.valueChanged.connect(self._on_lstep_changed)
        step_row.addWidget(self.spin_lstep)
        lo.addLayout(step_row)

        return f


    def _make_action_buttons(self):
        f = QFrame()
        f.setStyleSheet('QFrame{border:none;background:transparent;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(6)

        # ── Switch compensation délai laser ───────────────────────
        lat_row = QHBoxLayout()
        self.lbl_lat = QLabel(self.t.get('simulate_latency', 'Simulate latency'))
        self.lbl_lat.setStyleSheet('color:#aaa;font-size:10px;border:none;')
        lat_row.addWidget(self.lbl_lat)
        lat_row.addStretch()
        self.sw_latency = Switch()
        self.sw_latency.setChecked(False)
        self.sw_latency.toggled.connect(self._on_lat_toggle)
        lat_row.addWidget(self.sw_latency)
        lo.addLayout(lat_row)

        self.btn_cancel = QPushButton(self.t.get('cancel', 'Close'))
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setStyleSheet(self._gbtn('#333', '#444'))
        self.btn_cancel.clicked.connect(self.on_cancel)
        lo.addWidget(self.btn_cancel)
        return f


    # ─── Panneau droit ───────────────────────────────────────────

    def _make_right_panel(self):
        self._right_widget = QWidget()
        self._right_widget.setStyleSheet('background:#111;')
        lo = QVBoxLayout(self._right_widget)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Canvas occupe tout l'espace
        self.canvas = _SimCanvas()
        self.canvas.set_placeholder(self.t.get('open_gcode_hint', 'Open a G-Code file to start'))
        lo.addWidget(self.canvas, stretch=1)

        # Les contrôles de lecture et la barre de progression sont créés
        # mais restent hors du layout — ils seront positionnés en overlay
        self._playback_frame = self._make_playback_bar()
        self._playback_frame.setParent(self._right_widget)
        self._playback_frame.setStyleSheet(
            'QFrame{background:transparent;border:none;}')

        self._progress_frame = self._make_progress_bar()
        self._progress_frame.setParent(self._right_widget)
        self._progress_frame.setStyleSheet(
            'QFrame{background:transparent;border:none;}')

        return self._right_widget

    def _make_playback_bar(self):
        f = QFrame()
        lo = QVBoxLayout(f)
        lo.setContentsMargins(8, 6, 8, 6)
        lo.setSpacing(5)

        # Transport
        tr = QHBoxLayout()
        tr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_rew = QPushButton()
        rewind_pixmap = get_svg_pixmap(SVG_ICONS["REWIND"], QSize(24, 24), "#ffffff")
        btn_rew.setIcon(QIcon(rewind_pixmap))
        btn_rew.setFixedSize(60, 40)
        btn_rew.setStyleSheet(self._gbtn('#444', '#555'))
        btn_rew.clicked.connect(self.rewind_sim)

        self.btn_play = QPushButton() # '▶'
        self.play_pixmap = get_svg_pixmap(SVG_ICONS["PLAY"], QSize(24, 24), "#ffffff")
        self.pause_pixmap = get_svg_pixmap(SVG_ICONS["PAUSE"], QSize(24, 24), "#ffffff")
        self.rerun_pixmap = get_svg_pixmap(SVG_ICONS["RERUN"], QSize(24, 24), "#ffffff")
        self.btn_play.setIcon(QIcon(self.play_pixmap))
        self.btn_play.setFixedSize(100, 40)
        # self.btn_play.setFont(QFont('Arial', 16))
        self.btn_play.setStyleSheet(self._gbtn('#27ae60', '#1e8449'))
        self.btn_play.clicked.connect(self.toggle_pause)

        btn_end = QPushButton() # '⏭'
        skiptoend_pixmap = get_svg_pixmap(SVG_ICONS["SKIPTOEND"], QSize(24, 24), "#ffffff")
        btn_end.setIcon(QIcon(skiptoend_pixmap))
        btn_end.setFixedSize(60, 40)
        # btn_end.setFont(QFont('Arial', 16))
        btn_end.setStyleSheet(self._gbtn('#444', '#555'))
        btn_end.clicked.connect(self.skip_to_end)

        btn_fit = QPushButton() # '⊞'
        fit_pixmap = get_svg_pixmap(SVG_ICONS["FIT"], QSize(50, 50), "#ffffff")
        btn_fit.setIcon(QIcon(fit_pixmap))
        btn_fit.setFixedSize(40, 40)
        # btn_fit.setFont(QFont('Arial', 20))
        btn_fit.setToolTip(self.t.get('reset_zoom', 'Reset zoom / pan'))
        btn_fit.setStyleSheet(self._gbtn('#333', '#444'))
        btn_fit.clicked.connect(self.canvas.reset_view)

        for b in [btn_rew, self.btn_play, btn_end, btn_fit]:
            tr.addWidget(b)
        lo.addLayout(tr)

        # Sélecteur vitesse
        sf = QFrame()
        sf.setStyleSheet('QFrame{background:#222;border:1px solid #444;'
                         'border-radius:5px;}')
        sr = QHBoxLayout(sf)
        sr.setContentsMargins(5, 2, 5, 2)
        sr.setSpacing(2)

        spd_lbl = QLabel(self.t.get('speed', 'Speed:'))
        spd_lbl.setStyleSheet('color:white;font-weight:bold;font-size:9px;border:none;')
        sr.addWidget(spd_lbl)

        self._spd_btns: dict[str, QPushButton] = {}
        spd_style = ('QPushButton{background:#3a3a3a;color:#aaa;'
                     'border:1px solid #555;border-radius:3px;'
                     'padding:0px 4px;font-size:8px;min-width:18px;max-width:30px;}'
                     'QPushButton:checked{background:#1f538d;color:white;'
                     'border-color:#2a6dbd;}'
                     'QPushButton:hover:!checked{background:#444;color:white;}')
        for v in ['0.5', '1', '5', '10', '50']:
            b = QPushButton(v)
            b.setCheckable(True)
            b.setFixedHeight(14)
            b.setStyleSheet(spd_style)
            b.clicked.connect(lambda _, val=v: self._set_speed(val))
            sr.addWidget(b)
            self._spd_btns[v] = b
        self._spd_btns['1'].setChecked(True)

        lo.addWidget(sf, alignment=Qt.AlignmentFlag.AlignHCenter)
        return f

    def _make_progress_bar(self):
        f = QFrame()
        lo = QVBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0) # On laisse le resizeEvent gérer les bords
        lo.setSpacing(0)

        container = QWidget()
        container.setFixedHeight(30) # Un peu plus haut pour faciliter le clic
        container.setStyleSheet('background:transparent;')

        self.prog_bar = QProgressBar(container)
        # Supprimez le setGeometry fixe ici, ou mettez une valeur bidon
        self.prog_bar.setRange(0, 10000)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet(
            'QProgressBar{background:#333;border-radius:7px;border:none;}'
            'QProgressBar::chunk{background:#27ae60;border-radius:7px;}')
        
        # IMPORTANT : On lie le clic
        self.prog_bar.mousePressEvent = self._on_prog_click

        self.lbl_time = QLabel('00:00:00 / 00:00:00', container)
        self.lbl_time.setStyleSheet(
            'color:white;font-size:9px;font-weight:bold;'
            'background:transparent;border:none;')
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lo.addWidget(container)

        self.lbl_prog = QLabel('')
        self.lbl_prog.hide()
        lo.addWidget(self.lbl_prog)

        self._prog_container = container
        return f

    # ══════════════════════════════════════════════════════════════
    #  LOADING OVERLAY
    # ══════════════════════════════════════════════════════════════

    def _show_loading(self):
        self._ov = QWidget(self)
        self._ov.setStyleSheet('background:rgba(20,20,20,220);')
        self._ov.resize(self.size())
        self._ov.show()
        self._ov.raise_()

        lo = QVBoxLayout(self._ov)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        box = QFrame()
        box.setFixedWidth(340)
        box.setStyleSheet('QFrame{background:#3a3a3a;border-radius:12px;'
                          'border:1px solid #555;}')
        bl = QVBoxLayout(box)
        bl.setContentsMargins(30, 20, 30, 25)
        bl.setSpacing(12)

        lbl = QLabel(self.t.get('parsing', 'Parsing G-Code…'))
        lbl.setStyleSheet('color:white;font-size:14px;font-weight:bold;border:none;')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(lbl)

        pb = QProgressBar()
        pb.setFixedHeight(10)
        pb.setRange(0, 0)
        pb.setStyleSheet('QProgressBar{background:#555;border-radius:5px;border:none;}'
                         'QProgressBar::chunk{background:#27ae60;border-radius:5px;}')
        bl.addWidget(pb)
        lo.addWidget(box)

    def _hide_loading(self):
        if hasattr(self, '_ov'):
            self._ov.hide()
            self._ov.deleteLater()
            del self._ov

    def _update_gcode_font(self):
        """Adapte la taille de la police du G-Code à la largeur du panneau gauche."""
        if not hasattr(self, 'gcode_view'):
            return
        panel_w = self.left.width() if hasattr(self, 'left') else 336
        # Viser ~55 caractères lisibles — Consolas ratio ≈ 0.55
        usable = max(1, panel_w - 24)
        pt = max(8, min(16, int(usable / (55 * 0.55))))
        fnt = QFont('Consolas', pt)
        self.gcode_view.setFont(fnt)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_gcode_font()

        if hasattr(self, '_ov'):
            self._ov.resize(self.size())

        # Repositionnement des blocs (Playback et Progress)
        if hasattr(self, '_playback_frame') and hasattr(self, '_progress_frame'):
            rw = self._right_widget
            rw_w = rw.width()
            rw_h = rw.height()

            margin_side = 40
            margin_bottom = 2   # px depuis le bas

            pb_hint = self._playback_frame.sizeHint()
            pr_hint = self._progress_frame.sizeHint()
            pb_h = max(pb_hint.height(), 70)
            pr_h = max(pr_hint.height(), 26)

            total_h  = pb_h + pr_h + 2
            bottom_y = rw_h - total_h - margin_bottom

            # 1. On donne d'abord sa position au cadre transparent global
            prog_frame_w = rw_w - 2 * margin_side
            self._progress_frame.setGeometry(margin_side, bottom_y,
                                             prog_frame_w, pr_h)
            
            self._playback_frame.setGeometry(margin_side, bottom_y + pr_h + 2,
                                             rw_w - 2 * margin_side, pb_h)

            # 2. On dimensionne la barre ET le texte immédiatement 
            # (Plus aucun décalage temporel)
            if hasattr(self, 'prog_bar'):
                bar_w = int(prog_frame_w * 0.8)
                bar_x = (prog_frame_w - bar_w) // 2
                self.prog_bar.setGeometry(bar_x, 3, bar_w, 14)
                # Le label prend toute la largeur, Qt le centrera parfaitement au-dessus de la barre
                self.lbl_time.setGeometry(0, 3, prog_frame_w, 14)

            self._playback_frame.raise_()
            self._progress_frame.raise_()

            # Mémoriser la hauteur occupée par les overlays pour _init_canvas
            self._overlay_h = rw_h - bottom_y + 8

    # ══════════════════════════════════════════════════════════════
    #  GÉNÉRATION (QThread)
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    #  CHARGEMENT FICHIER G-CODE
    # ══════════════════════════════════════════════════════════════

    def _on_open_file(self):
        """Ouvre un QFileDialog et charge le fichier sélectionné."""
        stds = 'G-Code (*.nc *.gcode *.gc *.tap *.txt);;All files (*.*)'
        path, _ = QFileDialog.getOpenFileName(
            self, self.t.get('open_file', 'Open G-Code file'), '', stds)
        if path:
            self._load_file(path)

    def _load_file(self, path):
        """Parse le fichier G-Code et lance la simulation."""
        self._stop_all()
        self._loaded_path = path
        self.lbl_file.setText(truncate_path(path, 38))
        self.lbl_size.setText('')
        self.lbl_dur.setText('')

        self._show_loading()

        # Lecture
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                gcode = f.read()
        except Exception as e:
            self._hide_loading()
            QMessageBox.critical(self,
                self.t.get('error_title', 'Error'),
                f"{self.t.get('error_read_file', 'Cannot read file:')}\n{e}")
            return

        # Parsing dans un thread pour ne pas bloquer l'UI
        self._parse_worker = _ParseWorker(gcode)
        self._parse_worker.done.connect(self._on_parse_done)
        self._parse_worker.error.connect(self._on_parse_error)
        self._parse_worker.start()

    def _on_parse_error(self, msg):
        self._hide_loading()
        QMessageBox.critical(self, self.t.get('parse_error_title', 'Parse Error'), msg)

    def _on_parse_done(self, d):
        self._hide_loading()

        self.final_gcode   = d['gcode']
        self.points_list   = d['pts']
        self.total_sec     = d.get('total_dur', 0.0)
        self.framing_end   = 0
        self._last_drawn_idx = -1

        # Calculer latence_mm depuis le feedrate réel et la config
        try:
            lat_ms = float(
                self.controller.config_manager.get_item('machine_settings', 'laser_latency', 0.0) or 0.0
            )
            feedrate_mmmin = d.get('feedrate_mmmin', 3000.0)
            # lat_ms * feedrate (mm/min) / 60000 = mm  (signe inversé)
            self.latence_mm = -abs(lat_ms) * feedrate_mmmin / 60000.0
        except Exception:
            self.latence_mm = 0.0

        # Bounds = tous les points parsés (G0 + G1 Q=0 + G1 Q>0)
        # On veut voir l'intégralité des déplacements, overscan inclus
        pts = self.points_list
        if pts is not None and len(pts):
            self._mnx = float(pts[:, 0].min())
            self._mxx = float(pts[:, 0].max())
            self._mny = float(pts[:, 1].min())
            self._mxy = float(pts[:, 1].max())
        else:
            self._mnx = self._mxx = self._mny = self._mxy = 0.0

        # Infos affichées
        nb_lines = self.final_gcode.count('\n')
        self.lbl_size.setText(f'{nb_lines} lines')
        self.lbl_dur.setText(self._fmt(self.total_sec))

        if self.final_gcode:
            self.gcode_view.setPlainText(self.final_gcode)
            self._update_gcode_font()

        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        self._right_widget.updateGeometry()

        # Détecter l'axe dominant du raster pour pré-remplir le line_step
        if pts is not None and len(pts) > 1:
            dx_total = float(np.sum(np.abs(np.diff(pts[:, 0]))))
            dy_total = float(np.sum(np.abs(np.diff(pts[:, 1]))))
            is_horizontal = dx_total >= dy_total
            try:
                key = 'hor_linestep' if is_horizontal else 'ver_linestep'
                step_val = float(
                    self.controller.config_manager.get_item('machine_settings', key, 0.1) or 0.1
                )
                self.spin_lstep.blockSignals(True)
                self.spin_lstep.setValue(step_val)
                self.spin_lstep.blockSignals(False)
            except Exception:
                pass

        self._init_canvas()


    # ══════════════════════════════════════════════════════════════
    #  INITIALISATION CANVAS
    # ══════════════════════════════════════════════════════════════

    def _init_canvas(self):
        cw, ch = self.canvas.width(), self.canvas.height()

        # Attendre que le widget soit réellement dimensionné
        if cw <= 1 or ch <= 1:
            QTimer.singleShot(60, self._init_canvas)
            return

        if self.points_list is None or len(self.points_list) == 0:
            return

        # 1. ctrl_max : lu depuis la config
        self.ctrl_max = float(
            self.controller.config_manager.get_item('machine_settings', 'ctrl_max', 255) or 255
        )

        pts = self.points_list

        # 2. l_step (épaisseur trait laser) : champ éditable UI — non sauvegardé
        try:
            l_step = float(self.spin_lstep.value())
            if l_step <= 0:
                l_step = 0.1
        except Exception:
            l_step = 0.1

        # 3. scan_step (espacement réel entre lignes) : détecté depuis le G-Code
        #    Sert au snap d'échelle et au snap Y — indépendant de l_step utilisateur
        scan_step = self._detect_scan_step(pts)
        if scan_step is None or scan_step <= 0:
            scan_step = l_step  # fallback : utiliser l_step si pas de raster détecté

        # ─────────────────────────────
        # Dimensions réelles pièce (mm)
        # ─────────────────────────────
        tw = max(0.1, self._mxx - self._mnx)
        th = max(0.1, self._mxy - self._mny)

        # Espace utile
        overlay_h = getattr(self, '_overlay_h', 150)
        ch_usable = max(ch - overlay_h, int(ch * 0.5))

        # Scale pour tenir dans la vue
        sc = min((cw * 0.90) / tw, (ch_usable * 0.90) / th)

        # SNAP ÉCHELLE sur scan_step (pas inter-lignes réel)
        # → les lignes tombent exactement sur des pixels entiers → aucun gap
        snap_px = max(1, int(np.round(scan_step * sc)))
        sc = snap_px / scan_step  # échelle recalculée

        # lw_px pour les marges du buffer (basé sur l_step affiché)
        lw_px = max(1, int(np.round(l_step * sc)))

        # Dimensions projetées écran
        pw = tw * sc
        ph = th * sc

        # Dimensions buffer image — marge d'une ligne pour la première et dernière
        rw = max(1, int(round(pw)) + lw_px * 2)
        rh = max(1, int(round(ph)) + lw_px * 2)

        # Position : centré horizontalement, marge en haut
        x0 = (cw - pw) / 2.0
        y0 = max(8.0, (ch_usable - ph) * 0.10)

        # ─────────────────────────────
        # Initialisation renderer
        # ─────────────────────────────
        # pwr_min_s = 0 toujours : si on utilisait le min des valeurs actives
        # (ex: 40), laser_threshold = max(40, ctrl_max*0.001) = 40, et la
        # condition pwr > threshold serait False pour Q=40 → rien dessiné.
        # pwr_max_s = valeur max trouvée dans le fichier (ou ctrl_max par défaut).
        pwr_col = pts[:, 2]
        pwr_active = pwr_col[pwr_col > 0]
        if len(pwr_active):
            pwr_min_s = 0.0
            pwr_max_s = float(pwr_active.max())
        else:
            pwr_min_s = 0.0
            pwr_max_s = float(self.ctrl_max)

        self._renderer = _Renderer(
            rw,
            rh,
            sc,
            rh,
            self._mnx,
            self._mny,
            int(lw_px),
            self.ctrl_max,
            pwr_min=pwr_min_s,
            pwr_max=pwr_max_s,
            l_step_mm=scan_step,   # snap Y basé sur espacement réel
            draw_step_mm=l_step    # épaisseur du trait (valeur utilisateur)
        )

        # Stockage géométrie
        self._px_w, self._px_h = pw, ph
        self._x0, self._y0 = x0, y0
        self._scale = sc

        # Index sécurisé
        # self._last_drawn_idx = max(0, self.framing_end - 1)
        self._last_drawn_idx = -1

        # ─────────────────────────────
        # Position initiale laser
        # ─────────────────────────────
        p0 = self.points_list[0]
        lx = x0 + (p0[0] - self._mnx) * sc
        ly = y0 + ph - (p0[1] - self._mny) * sc

        # ─────────────────────────────
        # Setup canvas (AVEC l_step en dernier argument)
        # ─────────────────────────────
        self.canvas.setup(
            self._renderer.display_data,
            x0, y0, pw, ph, sc,
            self._mnx, self._mxx,
            self._mny, self._mxy,
            l_step if l_step > 0 else 1.0,
            overlay_h
        )

        self.canvas.set_laser(lx, ly)

        # Forcer le repositionnement des overlays
        self.resizeEvent(None)

        # Afficher l'image complète immédiatement au chargement
        QTimer.singleShot(0, lambda: (
            self._redraw_to(len(self.points_list) - 1),
            self._update_ui(len(self.points_list) - 1)
        ))

    # ══════════════════════════════════════════════════════════════
    #  ANIMATION — hot path
    # ══════════════════════════════════════════════════════════════

    def _tick(self):
        """
        Boucle animation (16 ms).
        Rasterisation incrémentale sécurisée.
        """

        if not self.sim_running:
            return

        if self.points_list is None or len(self.points_list) < 2:
            return

        pts = self.points_list
        total_pts = len(pts)
        last_idx = total_pts - 1

        # ───────────────────────────────
        # Temps simulation
        # ───────────────────────────────
        now = time.perf_counter()

        if self.last_frame_time == 0:
            self.last_frame_time = now

        dt = (now - self.last_frame_time) * self.sim_speed
        self.last_frame_time = now
        self.current_sim_time += dt

        # Clamp temps
        if self.current_sim_time >= self.total_sec:
            self.current_sim_time = self.total_sec

        # ───────────────────────────────
        # Avancement index via searchsorted
        # ───────────────────────────────
        idx = np.searchsorted(
            pts[:, 4],
            self.current_sim_time,
            side='right'
        ) - 1

        idx = max(0, min(int(idx), last_idx))
        self.current_idx = idx

        # ───────────────────────────────
        # Rasterisation incrémentale
        # ───────────────────────────────
        if self._renderer is not None:

            # start_idx = max(0, self.framing_end - 1)
            start_idx = 0

            if self.current_idx > self._last_drawn_idx:

                seg_start = max(self._last_drawn_idx, start_idx)

                if seg_start < self.current_idx:
                    self._renderer.draw_incremental(
                        pts,
                        seg_start,
                        self.current_idx,
                        self.latence_enabled,
                        self.latence_mm,
                        self.full_metadata.get('scan_axis', 'X')
                    )

                    self._last_drawn_idx = self.current_idx
                    self.canvas.notify_dirty()

        # ───────────────────────────────
        # Fin animation
        # ───────────────────────────────
        if self.current_idx >= last_idx:
            self._finish_anim()
            return

        # ───────────────────────────────
        # Interpolation laser fluide
        # ───────────────────────────────
        pc = pts[self.current_idx]
        pn = pts[self.current_idx + 1]

        td = pn[4] - pc[4]

        if td > 0:
            r = (self.current_sim_time - pc[4]) / td
            r = max(0.0, min(1.0, r))
        else:
            r = 0.0

        lx_mm = pc[0] + (pn[0] - pc[0]) * r
        ly_mm = pc[1] + (pn[1] - pc[1]) * r

        self.canvas.set_laser(*self._mm_to_screen(lx_mm, ly_mm))

        # ───────────────────────────────
        # UI sync
        # ───────────────────────────────
        self._update_ui(self.current_idx)

    # ══════════════════════════════════════════════════════════════
    #  REDRAW COMPLET (scrub / seek / latence toggle)
    # ══════════════════════════════════════════════════════════════

    def _redraw_to(self, target_idx):
        """
        Redessine complètement la simulation jusqu'à target_idx.
        Utilisé pour :
            - scrub barre de progression
            - skip_to_end
            - toggle latence
        """

        if self._renderer is None:
            return

        if self.points_list is None or len(self.points_list) == 0:
            return

        total_pts = len(self.points_list)

        target_idx = max(0, min(int(target_idx), total_pts - 1))
        # start_idx  = max(0, self.framing_end - 1)
        start_idx = 0

        if target_idx <= start_idx:
            self._renderer.reset()
            self._last_drawn_idx = start_idx
        else:
            # Fond blanc
            self._renderer.display_data.fill(255)
            scan_axis = self.full_metadata.get('scan_axis', 'X')
            # Dessiner le framing en premier (il sera le plus foncé si puissance forte)
            if self.framing_end > 0:
                polys = self._renderer._compute_segments(
                    self.points_list, 0, self.framing_end, False, 0.0, scan_axis)
                self._renderer._rasterize(polys)
            # Dessiner le raster — np.minimum protège les pixels du framing
            if target_idx > self.framing_end:
                polys = self._renderer._compute_segments(
                    self.points_list, self.framing_end, target_idx,
                    self.latence_enabled, self.latence_mm, scan_axis)
                self._renderer._rasterize(polys)
            self._last_drawn_idx = target_idx

        self.canvas.notify_dirty()

        mx = float(self.points_list[target_idx][0])
        my = float(self.points_list[target_idx][1])
        self.canvas.set_laser(*self._mm_to_screen(mx, my))

    # ══════════════════════════════════════════════════════════════
    #  CONTRÔLES PLAYBACK
    # ══════════════════════════════════════════════════════════════

    def _detect_scan_step(self, pts):
        """Détecte l'espacement réel entre lignes de scan depuis les points parsés."""
        if pts is None or len(pts) < 2:
            return None
        try:
            # Chercher les transitions laser actif → inactif (fin de ligne)
            pwr = pts[:, 2]
            starts = np.where((pwr[:-1] == 0) & (pwr[1:] > 0))[0] + 1
            if len(starts) < 2:
                # Fallback : diffs Y uniques pour raster horizontal
                y_unique = np.unique(np.round(pts[:, 1], 6))
                if len(y_unique) > 1:
                    diffs = np.diff(y_unique)
                    diffs = diffs[diffs > 1e-6]
                    if len(diffs):
                        return float(np.median(diffs))
                return None
            # Distance entre débuts de passes consécutives
            n = min(len(starts) - 1, 30)
            dists = []
            for i in range(n):
                p1 = pts[starts[i], :2]
                p2 = pts[starts[i + 1], :2]
                d = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
                if 1e-4 < d < 10.0:
                    dists.append(d)
            if dists:
                return float(np.median(dists))
        except Exception:
            pass
        return None

    def _on_lstep_changed(self, value):
        """Recalcule le canvas quand l'utilisateur change le line_step."""
        if self.points_list is not None and len(self.points_list) > 0:
            self._stop_play()
            self._init_canvas()

    def toggle_pause(self):
        if self.points_list is None or self.points_list.size == 0:
            return
        if self.current_idx >= self.points_list.shape[0] - 1:   # fin atteinte → replay
            self.rewind_sim(); self._start_play(); return
        if self.sim_running:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        # Effacer l'image si déjà dessinée, pour repartir de zéro
        if self._last_drawn_idx > 0:
            if self._renderer:
                self._renderer.reset()
                self.canvas.notify_dirty()
            self._last_drawn_idx  = -1
            self.current_idx      = 0
            self.current_sim_time = 0.0
            self.last_frame_time  = 0.0
            self.prog_bar.setValue(0)
            self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
            if self.points_list is not None and self.points_list.size > 0:
                lx, ly = self._mm_to_screen(self.points_list[0][0], self.points_list[0][1])
                self.canvas.set_laser(lx, ly)
        self.sim_running     = True
        self.last_frame_time = time.perf_counter()
        self.btn_play.setIcon(QIcon(self.pause_pixmap))
        self.btn_play.setStyleSheet(self._gbtn('#e67e22', '#ca6f1e'))
        self._anim_timer.start()

    def _stop_play(self):
        self.sim_running = False
        self._anim_timer.stop()
        self.btn_play.setIcon(QIcon(self.play_pixmap))
        self.btn_play.setStyleSheet(self._gbtn('#27ae60', '#1e8449'))

    def _finish_anim(self):
        self.sim_running = False
        self._anim_timer.stop() 
        self.btn_play.setIcon(QIcon(self.rerun_pixmap ))
        # self.btn_play.setText('🔄')
        self.btn_play.setStyleSheet(self._gbtn('#2980b9', '#1a6090'))
        self._update_ui(len(self.points_list) - 1)

    def rewind_sim(self):
        self._stop_play()
        self.current_idx      = 0
        self.current_sim_time = 0.0
        self.last_frame_time  = 0.0
        self._last_drawn_idx  = -1
        if self._renderer:
            self._renderer.reset()
            self.canvas.notify_dirty()
        self.prog_bar.setValue(0)
        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        self.btn_play.setIcon(QIcon(self.play_pixmap))
        self.btn_play.setStyleSheet(self._gbtn('#27ae60', '#1e8449'))
        self._highlight_gcode(0)
        if self.points_list is not None and self.points_list.size > 0:
            lx, ly = self._mm_to_screen(
                self.points_list[0][0], self.points_list[0][1])
            self.canvas.set_laser(lx, ly)

    def skip_to_end(self):
        if self.points_list is None: return
        self._stop_play()
        self.current_idx      = len(self.points_list) - 1
        self.current_sim_time = self.total_sec
        self._redraw_to(self.current_idx)
        self._update_ui(self.current_idx)
        self._finish_anim()

    def _set_speed(self, val):
        try:
            self.sim_speed = float(val)
            self.last_frame_time = time.perf_counter()
        except ValueError: pass
        for v, b in self._spd_btns.items():
            b.setChecked(v == val)

    def _on_lat_toggle(self, checked):
        self.latence_enabled = checked
        if self.points_list is not None and len(self.points_list) > 0:
            target = len(self.points_list) - 1 if self._last_drawn_idx >= len(self.points_list) - 1 else self.current_idx
            self._redraw_to(target)

    def _on_prog_click(self, e):
        # Sécurités de base
        if self.points_list is None or self.total_sec <= 0:
            return

        total_pts = len(self.points_list)
        if total_pts == 0:
            return

        # 1. RÉCUPÉRATION DE LA GÉOMÉTRIE RÉELLE
        # On récupère la largeur actuelle de la barre (celle affichée à l'écran)
        bar_w = self.prog_bar.width()
        if bar_w <= 1:
            return

        # 2. CALCUL DU RATIO (Pixel-Perfect)
        # mapFromGlobal convertit la position absolue de la souris sur l'écran 
        # vers le référentiel interne de la prog_bar (0 = bord gauche exact).
        # Cela élimine tout décalage du aux marges ou au centrage (le bar_x).
        local_pos = self.prog_bar.mapFromGlobal(e.globalPosition().toPoint())
        pos_x = local_pos.x()
        
        # On sature le ratio entre 0.0 (début) et 1.0 (fin)
        ratio = max(0.0, min(1.0, pos_x / bar_w))

        # 3. LOGIQUE DE SAUT DANS LA SIMULATION
        # On mémorise si la lecture était en cours pour la reprendre après
        was_running = self.sim_running
        if was_running:
            self._stop_play()

        # Calcul du nouveau temps cible basé sur le ratio cliqué
        self.current_sim_time = ratio * self.total_sec

        # Recherche de l'index correspondant au temps dans les données NumPy
        # (on suppose que self.points_list[:, 4] contient les timestamps cumulés)
        idx = np.searchsorted(
            self.points_list[:, 4],
            self.current_sim_time,
            side='right'
        ) - 1

        # Sécurisation de l'index
        idx = max(0, min(int(idx), total_pts - 1))
        self.current_idx = idx

        # 4. MISE À JOUR VISUELLE IMMÉDIATE
        # Redessine le canvas jusqu'à ce point
        self._redraw_to(self.current_idx)
        # Met à jour les labels, le curseur laser et la valeur de la barre
        self._update_ui(self.current_idx)

        # 5. REPRISE DE LA LECTURE
        if was_running:
            # On réinitialise le timer de frame pour éviter un bond temporel
            self.last_frame_time = time.perf_counter()
            self._start_play()

    # ══════════════════════════════════════════════════════════════
    #  UI SYNC
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    #  NAVIGATION G-CODE (click + clavier)
    # ══════════════════════════════════════════════════════════════

    def _seek_to_gcode_line(self, line_num):
        """Seek la simulation au premier point dont la ligne G-Code == line_num."""
        if self.points_list is None or len(self.points_list) == 0:
            return
        pts = self.points_list
        # pts[:,3] contient le numéro de ligne G-Code
        matches = np.where(pts[:, 3].astype(int) >= line_num)[0]
        if len(matches) == 0:
            idx = len(pts) - 1
        else:
            idx = int(matches[0])
        was_running = self.sim_running
        self._stop_play()
        self.current_idx      = idx
        self.current_sim_time = float(pts[idx][4])
        self._redraw_to(idx)
        self._update_ui(idx)
        if was_running:
            self.last_frame_time = time.perf_counter()
            self._start_play()

    def _on_gcode_click(self, e):
        """Click sur le G-Code : positionne le curseur ET seek la simulation."""
        # Laisser le comportement normal de QPlainTextEdit (déplace le curseur)
        QPlainTextEdit.mousePressEvent(self.gcode_view, e)
        line_num = self.gcode_view.textCursor().blockNumber() + 1
        self._seek_to_gcode_line(line_num)

    def _on_gcode_key(self, e):
        """Flèches clavier sur le G-Code : navigation ±1 ligne ou ±20 lignes."""
        from PyQt6.QtCore import Qt as _Qt
        key = e.key()
        if key in (_Qt.Key.Key_Left, _Qt.Key.Key_Right,
                   _Qt.Key.Key_Up, _Qt.Key.Key_Down):
            cur_line = self.gcode_view.textCursor().blockNumber() + 1
            if key == _Qt.Key.Key_Left:
                new_line = max(1, cur_line - 1)
            elif key == _Qt.Key.Key_Right:
                doc_lines = self.gcode_view.document().blockCount()
                new_line = min(doc_lines, cur_line + 1)
            elif key == _Qt.Key.Key_Up:
                new_line = max(1, cur_line - 20)
            else:  # Down
                doc_lines = self.gcode_view.document().blockCount()
                new_line = min(doc_lines, cur_line + 20)
            # Déplacer le curseur du gcode_view
            block = self.gcode_view.document().findBlockByLineNumber(new_line - 1)
            if block.isValid():
                cur = self.gcode_view.textCursor()
                cur.setPosition(block.position())
                cur.select(cur.SelectionType.LineUnderCursor)
                self.gcode_view.setTextCursor(cur)
                self.gcode_view.ensureCursorVisible()
            self._seek_to_gcode_line(new_line)
        else:
            # Comportement normal pour toutes les autres touches
            QPlainTextEdit.keyPressEvent(self.gcode_view, e)

    def _update_ui(self, idx):
        if self.points_list is None or idx >= len(self.points_list): return
        
        ts  = float(self.points_list[idx][4])
        
        # On base le rendu visuel sur l'écoulement du TEMPS, pas sur l'index des points
        pct = ts / max(0.001, self.total_sec) 
        pct = max(0.0, min(1.0, pct))
        
        self.prog_bar.setValue(int(pct * 10000))
        self.lbl_time.setText(
            f'{self._fmt(ts)} / {self._fmt(self.total_sec)}')
        self._highlight_gcode(idx)

    def _highlight_gcode(self, idx):
        if self.points_list is None or idx >= len(self.points_list): return
        try:
            line_num = int(self.points_list[idx][3])
            block    = self.gcode_view.document().findBlockByLineNumber(line_num-1)
            if block.isValid():
                cur = self.gcode_view.textCursor()
                cur.setPosition(block.position())
                cur.select(cur.SelectionType.LineUnderCursor)
                self.gcode_view.setTextCursor(cur)
                self.gcode_view.ensureCursorVisible()
        except Exception: pass

    # ══════════════════════════════════════════════════════════════
    #  EXPORT
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    #  LANGUE
    # ══════════════════════════════════════════════════════════════

    def _apply_language(self, lang: str, translations: dict):
        """Appelée par update_ui_language — recharge self.t et met à jour les widgets."""
        from core.translations import TRANSLATIONS as _TR
        repo = translations if translations else _TR.get(lang, _TR['English'])
        self.t = repo.get('simulation', {})

        if hasattr(self, 'btn_open'):
            self.btn_open.setText(self.t.get('open_file', 'Open G-Code file…'))
        if hasattr(self, 'lbl_file') and not self._loaded_path:
            self.lbl_file.setText(self.t.get('no_file', 'No file loaded'))
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.setText(self.t.get('cancel', 'Close'))
        if hasattr(self, 'lbl_lstep'):
            self.lbl_lstep.setText(self.t.get('line_step_lbl', 'Line step (mm):'))
        if hasattr(self, 'lbl_lat'):
            self.lbl_lat.setText(self.t.get('simulate_latency', 'Simulate latency'))
        if hasattr(self, 'canvas') and self.canvas._img_buf is None:
            self.canvas.set_placeholder(self.t.get('open_gcode_hint', 'Open a G-Code file to start'))

    # ══════════════════════════════════════════════════════════════
    #  THÈME
    # ══════════════════════════════════════════════════════════════

    def apply_theme(self, colors: dict):
        text       = colors['text']
        text_sec   = colors['text_secondary']
        bg_main    = colors['bg_main']
        bg_card    = colors['bg_card']
        bg_right   = colors['bg_deep']
        bg_entry   = colors['bg_entry']
        bg_spd     = colors['bg_speed']
        border     = colors['border']
        border_spd = colors['border_strong']
        gcode_col  = colors['text_code']
        btn_dark_bg  = colors['btn_dark']
        btn_dark_hov = colors['btn_dark_hover']

        # Scopé pour ne pas cascader sur _SimCanvas
        self.setStyleSheet(
            f'CheckerViewQt {{ background:{bg_main}; color:{text}; }}'
        )

        if hasattr(self, 'left'):
            self.left.setStyleSheet(
                f'QFrame#checkerLeft{{background:{bg_main};border-right:1px solid {border};}}'
            )
        if hasattr(self, '_file_frame'):
            self._file_frame.setStyleSheet(
                f'QFrame{{background:{bg_card};border-radius:6px;border:1px solid {border};}}'
            )
        if hasattr(self, 'gl_lbl'):
            self.gl_lbl.setStyleSheet(f'color:{text};font-weight:bold;font-size:11px;border:none;')
        if hasattr(self, 'lbl_file'):
            self.lbl_file.setStyleSheet(f'color:{text_sec};font-size:10px;border:none;')
        if hasattr(self, 'lbl_lstep'):
            self.lbl_lstep.setStyleSheet(f'color:{text_sec};font-size:10px;border:none;')
        if hasattr(self, 'spin_lstep'):
            self.spin_lstep.setStyleSheet(
                f'QDoubleSpinBox{{background:{bg_entry};color:{text};border:1px solid {border_spd};'
                f'border-radius:3px;font-size:10px;padding:1px 4px;}}'
                f'QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{{width:14px;}}'
            )
        if hasattr(self, 'lbl_lat'):
            self.lbl_lat.setStyleSheet(f'color:{text_sec};font-size:10px;border:none;')
        if hasattr(self, 'lbl_time'):
            self.lbl_time.setStyleSheet(
                f'color:{text};font-size:9px;font-weight:bold;background:transparent;border:none;'
            )
        if hasattr(self, 'gcode_view'):
            self.gcode_view.setStyleSheet(
                f'QPlainTextEdit{{background:{bg_entry};color:{gcode_col};'
                f'font-family:Consolas;border:1px solid {border};border-radius:3px;}}'
            )
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.setStyleSheet(self._gbtn(colors['btn_cancel'], colors['btn_cancel_hover']))
        if hasattr(self, '_spd_frame') and self._spd_frame:
            self._spd_frame.setStyleSheet(
                f'QFrame{{background:{bg_spd};border:1px solid {border_spd};border-radius:5px;}}'
            )
            for lbl in self._spd_frame.findChildren(QLabel):
                lbl.setStyleSheet(f'color:{text};font-weight:bold;font-size:9px;border:none;')
        if hasattr(self, '_spd_btns'):
            spd_style = (
                f'QPushButton{{background:{bg_card};color:{text_sec};'
                f'border:1px solid {border_spd};border-radius:3px;'
                f'padding:0px 4px;font-size:8px;min-width:18px;max-width:30px;}}'
                f'QPushButton:checked{{background:{colors["btn_speed_checked"]};color:white;'
                f'border-color:{colors["btn_speed_checked_hov"]};}}'
                f'QPushButton:hover:!checked{{background:{btn_dark_bg};color:{text};}}'
            )
            for b in self._spd_btns.values():
                b.setStyleSheet(spd_style)
        if hasattr(self, 'prog_bar'):
            self.prog_bar.setStyleSheet(
                f'QProgressBar{{background:{colors["progress_bg"]};border-radius:7px;border:none;}}'
                f'QProgressBar::chunk{{background:#27ae60;border-radius:7px;}}'
            )
        if hasattr(self, '_right_widget'):
            self._right_widget.setStyleSheet(f'background:{bg_right};')
        if hasattr(self, 'canvas'):
            self.canvas.set_theme(bg_right)

    # ══════════════════════════════════════════════════════════════
    #  EXPORT
    # ══════════════════════════════════════════════════════════════

    def on_cancel(self):
        self._stop_all()
        if   self.return_view == 'raster': self.controller.show_raster_mode()
        elif self.return_view == 'infill': self.controller.show_infill_mode()
        else:                              self.controller.show_dashboard()

    def _stop_all(self):
        self.sim_running = False
        self._anim_timer.stop()
        if hasattr(self, '_worker') and self._worker.isRunning():
            self._worker.quit(); self._worker.wait(500)

    def closeEvent(self, e):
        self._stop_all(); super().closeEvent(e)

    # ══════════════════════════════════════════════════════════════
    #  UTILITAIRES
    # ══════════════════════════════════════════════════════════════

    def _mm_to_screen(self, mx, my):
        sx = self._x0 + (mx - self._mnx) * self._scale
        sy = self._y0 + self._px_h - (my - self._mny) * self._scale
        return sx, sy

    @staticmethod
    def _fmt(s):
        s = float(s)
        return f'{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}'

    @staticmethod
    def _gbtn(bg, hov):
        return (f'QPushButton{{background:{bg};color:white;border-radius:6px;'
                f'border:none;}}'
                f'QPushButton:hover{{background:{hov};}}')
