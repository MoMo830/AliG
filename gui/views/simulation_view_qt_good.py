# -*- coding: utf-8 -*-
"""
A.L.I.G. - SimulationViewQt
Migration PyQt6 — v2 optimisée

Améliorations vs CTk original :
  • Rendu batch vectorisé :
    - Tous les polygones du frame sont pré-calculés en NumPy
    - Une seule passe QPainter sur le QImage (zéro boucle Python dans le hot path)
    - Rasterisation directe dans le buffer uint8 via QPainter (pas de cv2 ni PIL)
  • Zoom molette (centré sur la souris) + pan clic gauche
  • Loupe supprimée
  • Génération G-Code dans un QThread (UI non bloquante)
  • QTimer fixe 16 ms (~60 fps) au lieu de after(16) Tkinter
"""

import os
import time
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QSizePolicy, QFileDialog, QMessageBox, QPlainTextEdit,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRect, QRectF, QPointF, QLineF,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QImage, QPixmap, QFont,
    QLinearGradient, QPainterPath, QPolygonF, QTransform,
)

from engine.gcode_parser import GCodeParser
from core.utils import save_dashboard_data, truncate_path
from core.translations import TRANSLATIONS


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER : génération G-Code hors thread UI
# ══════════════════════════════════════════════════════════════════════════════

class _GenWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, engine, payload, parser):
        super().__init__()
        self.engine  = engine
        self.payload = payload
        self.parser  = parser

    def run(self):
        try:
            p            = self.payload['params']
            raster_mode  = p.get('raster_mode', 'horizontal')
            est_size_str = self.payload.get('estimated_size', 'N/A')

            # A — Framing
            framing_gcode = self.engine.prepare_framing(
                self.payload['framing'],
                (self.payload['metadata']['real_w'],
                 self.payload['metadata']['real_h']),
                self.payload['offsets'],
            )

            # B — Métadonnées enrichies
            meta = self.payload['metadata'].copy()
            meta.update({
                'framing_code': framing_gcode,
                'gray_steps':   p.get('gray_steps'),
                'use_s_mode':   p.get('use_s_mode'),
                'raster_mode':  raster_mode,
                'scan_axis':    'X' if raster_mode == 'horizontal' else 'Y',
            })

            # C — G-Code final
            final_gcode, latence_mm = self.engine.build_final_gcode(
                self.payload['matrix'],
                self.payload['dims'],
                self.payload['offsets'],
                p,
                self.payload['text_blocks'],
                meta,
            )
            latence_mm = float(latence_mm)

            # D — Parsing
            f_pts, f_dur, f_lim = self.parser.parse(framing_gcode)
            framing_end = len(f_pts) if f_pts is not None else 0
            pts, _, lim  = self.parser.parse(final_gcode)

            valid = [l for l in [f_lim, lim]
                     if l is not None and not all(abs(v) < 1e-9 for v in l)]
            if valid:
                bx0 = min(l[0] for l in valid)
                bx1 = max(l[1] for l in valid)
                by0 = min(l[2] for l in valid)
                by1 = max(l[3] for l in valid)
            else:
                bx0 = bx1 = by0 = by1 = 0.0

            # E — Timestamps cumulés
            dur = 0.0
            if pts is not None and len(pts) > 1:
                deltas    = np.diff(pts[:, :2], axis=0)
                distances = np.hypot(deltas[:, 0], deltas[:, 1])
                rates     = pts[1:, 4] / 60.0
                times     = np.divide(distances, rates,
                                      out=np.zeros_like(distances),
                                      where=rates > 0)
                pts[0, 4]  = 0.0
                pts[1:, 4] = np.cumsum(times)

                m      = self.payload.get('metadata', {})
                dims   = self.payload.get('dims', (0, 0, 0, 0))
                h_px, w_px = dims[0], dims[1]
                if raster_mode == 'vertical':
                    nb = float(w_px);  dist = float(m.get('real_h', 0))
                else:
                    nb = float(h_px);  dist = float(m.get('real_w', 0))
                feedrate = float(p.get('feedrate', 3000))
                overscan = float(p.get('premove', 2.0))
                lstep    = float(p.get('line_step', p.get('l_step', 0.1)))
                theo     = (nb * (dist + 2*overscan) + (nb-1)*lstep) / (feedrate/60)
                dur      = max(pts[-1, 4], theo)

            self.done.emit({
                'pts':           pts,
                'framing_end':   framing_end,
                'total_dur':     dur,
                'meta':          meta,
                'latence_mm':    latence_mm,
                'est_size':      est_size_str,
                'bounds':        (bx0, bx1, by0, by1),
                'final_gcode':   final_gcode,
                'framing_gcode': framing_gcode,
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            self.error.emit(str(e))


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
                 pwr_min=0.0, pwr_max=None, l_step_mm=None):
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
        # l_step en mm — pour calculer top par index et éviter l'accumulation d'erreurs
        self.l_step_mm      = float(l_step_mm) if l_step_mm else None
        self.l_step_px      = float(l_step_mm) * scale if l_step_mm else None
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

        # ── filtre longueur
        dx = fx2 - fx1
        dy = fy2 - fy1

        vis = (dx*dx + dy*dy) >= 0.25
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

            # Index stable (utilisation de round au lieu de floor + 0.5)
            row_idx = np.round((yc_mm - mny) / step_mm).astype(np.int32)
            row_idx = np.maximum(row_idx, 0)

            # Centre exact (suppression du + 0.5 pour que Y=0 straddle bien la ligne de référence)
            fy_center = th - (row_idx * step_px)

            fy1 = np.where(is_horiz, fy_center, fy1)
            fy2 = np.where(is_horiz, fy_center, fy2)

        else:
            # Remplacement de floor par round ici aussi
            fy_center = np.round((fy1+fy2)*0.5)
            fy1 = np.where(is_horiz, fy_center, fy1)
            fy2 = np.where(is_horiz, fy_center, fy2)

        # ── snap X pour segments verticaux
        fx_center = np.round((fx1+fx2)*0.5)

        fx1 = np.where(~is_horiz, fx_center, fx1)
        fx2 = np.where(~is_horiz, fx_center, fx2)

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

        # épaisseur réelle du raster = line_step
        step = self.l_step_px if self.l_step_px else self.laser_width_px
        half = step / 2.0

        buf = self.display_data.tobytes()
        qi = QImage(buf, w, h, w, QImage.Format.Format_Grayscale8)
        qi = qi.copy()

        qp = QPainter(qi)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        qp.setPen(Qt.PenStyle.NoPen)

        # On fige l'épaisseur en entier
        step_int = max(1, int(round(self.l_step_px))) if self.l_step_px else self.laser_width_px
        half = step_int / 2.0

        for c, segs in segs_by_color.items():

            qp.setBrush(QBrush(QColor(c, c, c)))

            for (x1, y1, x2, y2) in segs:

                # segment horizontal
                if abs(y2 - y1) < abs(x2 - x1):

                    left  = int(np.floor(min(x1, x2)))
                    right = int(np.ceil(max(x1, x2)))
                    
                    # Seul le haut est calculé, la hauteur est garantie par step_int
                    top_px = int(np.floor(y1 - half))

                    qp.fillRect(
                        left,
                        top_px,
                        max(1, right - left),
                        step_int,  # <-- HAUTEUR FIXE
                        QColor(c, c, c)
                    )

                # segment vertical
                else:

                    top_px    = int(np.floor(min(y1, y2)))
                    bottom_px = int(np.ceil(max(y1, y2)))

                    # Seule la gauche est calculée, la largeur est garantie par step_int
                    left_px = int(np.floor(x1 - half))

                    qp.fillRect(
                        left_px,
                        top_px,
                        step_int,  # <-- LARGEUR FIXE
                        max(1, bottom_px - top_px),
                        QColor(c, c, c)
                    )

        qp.end()

        bpl = qi.bytesPerLine()
        ptr = qi.bits()
        ptr.setsize(bpl * h)

        full_arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)
        np.copyto(self.display_data, full_arr[:, :w])

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

    # ─── API ─────────────────────────────

    def setup(self, img_buf, x0, y0, pw, ph, sc, mnx, mxx, mny, mxy):
        self._img_buf = img_buf
        self._x0, self._y0 = x0, y0
        self._pw, self._ph = pw, ph
        self._sc = sc
        self._mnx, self._mxx = mnx, mxx
        self._mny, self._mxy = mny, mxy
        self._zoom = 1.0
        self._pan  = QPointF(0, 0)
        self._rebuild()
        self._dirty = False
        self.update()

    def notify_dirty(self):
        self._dirty = True
        self.update()

    def set_laser(self, sx, sy):
        self._lx, self._ly = sx, sy
        self.update()

    def reset_view(self):
        self._zoom = 1.0
        self._pan  = QPointF(0, 0)
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
        qp.fillRect(0, 0, w, h, QColor('#050505'))

        if self._img_buf is None:
            qp.setPen(QColor('#444'))
            qp.setFont(QFont('Arial', 13))
            qp.drawText(QRect(0, 0, w, h),
                        Qt.AlignmentFlag.AlignCenter, 'Generating…')
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
        factor = 1.15 if e.angleDelta().y() > 0 else 1/1.15
        pos = e.position()
        cx, cy = pos.x(), pos.y()
        wx = (cx - self._pan.x()) / self._zoom
        wy = (cy - self._pan.y()) / self._zoom
        self._zoom = max(0.15, min(40.0, self._zoom * factor))
        self._pan  = QPointF(cx - wx*self._zoom, cy - wy*self._zoom)
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

class SimulationViewQt(QWidget):

    def __init__(self, parent, controller, engine, payload,
                 return_view='dashboard'):
        super().__init__(parent)
        self.controller  = controller
        self.engine      = engine
        self.payload     = payload
        self.return_view = return_view

        lang = controller.config_manager.get_item('machine_settings', 'language')
        if not lang or lang not in TRANSLATIONS:
            lang = 'English'
        self.t = TRANSLATIONS[lang]['simulation']

        # ── état ──────────────────────────────────────────────────
        self.final_gcode     = ''
        self.framing_gcode   = ''
        self.full_metadata   = {}
        self.points_list     = None
        self.framing_end     = 0
        self.total_sec       = 0.0
        self.latence_mm      = 0.0
        self.latence_enabled = False
        self.ctrl_max        = float(payload.get('params', {}).get('ctrl_max', 255))

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
        self._show_loading()
        QTimer.singleShot(80, self._start_gen)

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
        # Largeur réduite de 20% (420 → 336)
        self.left.setFixedWidth(336)
        self.left.setStyleSheet(
            'QFrame{background:#1e1e1e; border-right:1px solid #333;}')
        lo = QVBoxLayout(self.left)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)

        # Titre supprimé — la topbar l'écrit déjà

        lo.addWidget(self._make_stats_widget())

        gl = QLabel(self.t.get('live_gcode', 'Live G-Code'))
        gl.setStyleSheet('color:white;font-weight:bold;font-size:11px;border:none;')
        lo.addWidget(gl)

        self.gcode_view = QPlainTextEdit()
        self.gcode_view.setReadOnly(True)
        self.gcode_view.setStyleSheet(
            'QPlainTextEdit{background:#1a1a1a;color:#00ff00;'
            'font-family:Consolas;'
            'border:1px solid #333;border-radius:3px;}')
        self._update_gcode_font()
        lo.addWidget(self.gcode_view, stretch=1)

        lo.addWidget(self._make_options_widget())
        lo.addWidget(self._make_action_buttons())
        return self.left

    def _make_stats_widget(self):
        dims = self.payload.get('dims', (0, 0, 0, 0))
        h_px, w_px, sy, sx = dims
        w_mm = (w_px-1)*sx;  h_mm = (h_px-1)*sy
        meta = self.payload.get('metadata', {})
        path = os.path.join(
            meta.get('output_dir', ''),
            f'{meta.get("file_name","export")}{meta.get("file_extension",".nc")}'
        ).replace('\\', '/')
        self.quick_export_path = path
        self.full_export_path  = path

        f = QFrame()
        f.setStyleSheet('QFrame{background:#252525;border-radius:6px;'
                        'border:1px solid #333;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(8, 6, 8, 6)
        lo.setSpacing(4)

        def add_row(lbl_txt, val_txt, color='#ecf0f1'):
            r = QHBoxLayout()
            l = QLabel(lbl_txt)
            l.setStyleSheet('color:gray;font-size:10px;font-weight:bold;border:none;')
            v = QLabel(val_txt)
            v.setStyleSheet(f'color:{color};font-family:Consolas;'
                            f'font-size:11px;border:none;')
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(l); r.addWidget(v)
            lo.addLayout(r)

        add_row(self.t.get('final_size', 'Size'), f'{w_mm:.2f} x {h_mm:.2f} mm')
        add_row(self.t.get('output_file', 'Output'),
                truncate_path(path, 38), color='#2ecc71')

        lo.addWidget(self._make_power_bar())
        return f

    def _make_power_bar(self):
        p     = self.payload.get('params', {})
        p_min = float(p.get('min_power', 0))
        p_max = float(p.get('max_power', 100))

        class _PBar(QWidget):
            def __init__(s, mn, mx):
                super().__init__()
                s._mn = mn;  s._mx = mx
                s.setFixedHeight(55)

            def paintEvent(s, _):
                qp = QPainter(s)
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = s.width(), s.height()
                qp.fillRect(0, 0, w, h, QColor('#252525'))
                m, by, bh = 20, 25, 10
                bw = w - 2*m

                # --- Gradient qui reflète exactement l'échelle de rendu ---
                # 0%→min_power : blanc pur
                # min_power→max_power : gris 200 → noir 0
                # on dessine deux segments
                x_min = int(m + s._mn / 100.0 * bw)
                x_max = int(m + s._mx / 100.0 * bw)

                # Segment 0% → min_power : blanc uni
                if x_min > m:
                    qp.fillRect(m, by, x_min - m, bh, QColor(255, 255, 255))

                # Segment min_power → max_power : gris 200 → noir
                if x_max > x_min:
                    g = QLinearGradient(x_min, 0, x_max, 0)
                    g.setColorAt(0, QColor(200, 200, 200))
                    g.setColorAt(1, QColor(0, 0, 0))
                    qp.fillRect(x_min, by, x_max - x_min, bh, QBrush(g))

                # Segment max_power → 100% : noir uni
                if x_max < m + bw:
                    qp.fillRect(x_max, by, m + bw - x_max, bh, QColor(0, 0, 0))

                qp.setPen(QPen(QColor('#555'), 1))
                qp.drawRect(m, by, bw, bh)
                qp.setPen(QColor('#777'))
                qp.setFont(QFont('Arial', 8))
                qp.drawText(m, by+bh+12, '0%')
                qp.drawText(m+bw-22, by+bh+12, '100%')

                for val, lbl in [(s._mn, f'Min:{int(s._mn)}%'),
                                 (s._mx, f'Max:{int(s._mx)}%')]:
                    x = int(m + val/100*bw)
                    tri = QPolygonF([QPointF(x, by-1),
                                     QPointF(x-5, by-9),
                                     QPointF(x+5, by-9)])
                    qp.setBrush(QBrush(QColor('#ff9f43')))
                    qp.setPen(Qt.PenStyle.NoPen)
                    qp.drawPolygon(tri)
                    qp.setPen(QColor('#ff9f43'))
                    qp.setFont(QFont('Arial', 8, QFont.Weight.Bold))
                    qp.drawText(x-20, by-10, lbl)
                qp.end()

        return _PBar(p_min, p_max)
        p_min = float(p.get('min_power', 0))
        p_max = float(p.get('max_power', 100))

        class _PBar(QWidget):
            def __init__(s, mn, mx):
                super().__init__()
                s._mn = mn;  s._mx = mx
                s.setFixedHeight(55)

            def paintEvent(s, _):
                qp = QPainter(s)
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = s.width(), s.height()
                qp.fillRect(0, 0, w, h, QColor('#252525'))
                m, by, bh = 20, 25, 10
                bw = w - 2*m
                g = QLinearGradient(m, 0, m+bw, 0)
                g.setColorAt(0, QColor('white'))
                g.setColorAt(1, QColor('black'))
                qp.fillRect(m, by, bw, bh, QBrush(g))
                qp.setPen(QPen(QColor('#555'), 1))
                qp.drawRect(m, by, bw, bh)
                qp.setPen(QColor('#777'))
                qp.setFont(QFont('Arial', 8))
                qp.drawText(m, by+bh+12, '0%')
                qp.drawText(m+bw-22, by+bh+12, '100%')
                for val, lbl in [(s._mn, f'Min:{int(s._mn)}%'),
                                 (s._mx, f'Max:{int(s._mx)}%')]:
                    x = int(m + val/100*bw)
                    tri = QPolygonF([QPointF(x, by-1),
                                     QPointF(x-5, by-9),
                                     QPointF(x+5, by-9)])
                    qp.setBrush(QBrush(QColor('#ff9f43')))
                    qp.setPen(Qt.PenStyle.NoPen)
                    qp.drawPolygon(tri)
                    qp.setPen(QColor('#ff9f43'))
                    qp.setFont(QFont('Arial', 8, QFont.Weight.Bold))
                    qp.drawText(x-20, by-10, lbl)
                qp.end()

        return _PBar(p_min, p_max)

    def _make_options_widget(self):
        f = QFrame()
        f.setStyleSheet('QFrame{background:#222;border:1px solid #444;'
                        'border-radius:6px;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(8, 6, 8, 6)
        lo.setSpacing(4)

        lbl = QLabel(self.t.get('active_options', 'Active Options'))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet('color:white;font-weight:bold;font-size:11px;border:none;')
        lo.addWidget(lbl)

        br = QHBoxLayout()
        for key, txt in [('is_pointing', self.t.get('pointing_opt', 'POINTING')),
                         ('is_framing',  self.t.get('framing_opt',  'FRAMING'))]:
            active = self.payload.get('framing', {}).get(key, False)
            col = '#ff9f43' if active else '#555'
            bg  = '#3d2b1f' if active else '#282828'
            b   = QLabel(txt)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.setStyleSheet(f'color:{col};background:{bg};border-radius:5px;'
                            f'font-size:9px;font-weight:bold;'
                            f'padding:3px 6px;border:none;')
            br.addWidget(b)
        lo.addLayout(br)

        # lat_btn retiré d'ici — déplacé dans _make_action_buttons
        self.lat_btn = None
        return f

    def _make_action_buttons(self):
        f = QFrame()
        f.setStyleSheet('QFrame{border:none;background:transparent;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(4)

        # Bouton Simulate Latency — sorti du panneau Active Options
        self.lat_btn = None
        lat_val = float(self.payload.get('params', {}).get('laser_latency', 0))
        if lat_val != 0:
            self.lat_btn = QPushButton(
                self.t.get('simulate_latency', 'SIMULATE LATENCY') + '  ○')
            self.lat_btn.setCheckable(True)
            self.lat_btn.setStyleSheet(
                'QPushButton{background:#333;color:#888;border:1px solid #555;'
                'border-radius:4px;padding:4px 10px;font-size:10px;font-weight:bold;}'
                'QPushButton:checked{background:#1a4a2a;color:#2ecc71;'
                'border-color:#2ecc71;}')
            self.lat_btn.toggled.connect(self._on_lat_toggle)
            lo.addWidget(self.lat_btn)

        er = QHBoxLayout()
        self.btn_export = QPushButton(self.t.get('quick_export', 'Quick Export'))
        self.btn_export.setFixedHeight(40)
        self.btn_export.setStyleSheet(self._gbtn('#2ecc71', '#27ae60'))
        self.btn_export.clicked.connect(self.on_export)

        self.btn_export_as = QPushButton(self.t.get('export_as', 'Export As…'))
        self.btn_export_as.setFixedSize(110, 40)
        self.btn_export_as.setStyleSheet(self._gbtn('#7ac99b', '#27ae60'))
        self.btn_export_as.clicked.connect(self.on_export_as)

        er.addWidget(self.btn_export)
        er.addWidget(self.btn_export_as)
        lo.addLayout(er)

        self.btn_cancel = QPushButton(self.t.get('cancel', 'Cancel'))
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

        self.btn_rew  = QPushButton('⏮')
        self.btn_rew.setFixedSize(60, 40)
        self.btn_rew.setFont(QFont('Arial', 16))
        self.btn_rew.setStyleSheet(self._gbtn('#444', '#555'))
        self.btn_rew.clicked.connect(self.rewind_sim)

        self.btn_play = QPushButton('▶')
        self.btn_play.setFixedSize(100, 40)
        self.btn_play.setFont(QFont('Arial', 16))
        self.btn_play.setStyleSheet(self._gbtn('#27ae60', '#1e8449'))
        self.btn_play.clicked.connect(self.toggle_pause)

        btn_end = QPushButton('⏭')
        btn_end.setFixedSize(60, 40)
        btn_end.setFont(QFont('Arial', 16))
        btn_end.setStyleSheet(self._gbtn('#444', '#555'))
        btn_end.clicked.connect(self.skip_to_end)

        btn_fit = QPushButton('⊞')
        btn_fit.setFixedSize(40, 40)
        btn_fit.setFont(QFont('Arial', 16))
        btn_fit.setToolTip(self.t.get('reset_zoom', 'Reset zoom / pan'))
        btn_fit.setStyleSheet(self._gbtn('#333', '#444'))
        btn_fit.clicked.connect(self.canvas.reset_view)

        for b in [self.btn_rew, self.btn_play, btn_end, btn_fit]:
            tr.addWidget(b)
        lo.addLayout(tr)

        # Sélecteur vitesse
        sf = QFrame()
        sf.setStyleSheet('QFrame{background:#222;border:1px solid #444;'
                         'border-radius:8px;}')
        sr = QHBoxLayout(sf)
        sr.setContentsMargins(10, 4, 10, 4)

        spd_lbl = QLabel(self.t.get('speed', 'Speed:'))
        spd_lbl.setStyleSheet('color:white;font-weight:bold;font-size:11px;border:none;')
        sr.addWidget(spd_lbl)

        self._spd_btns: dict[str, QPushButton] = {}
        spd_style = ('QPushButton{background:#3a3a3a;color:#aaa;'
                     'border:1px solid #555;border-radius:4px;'
                     'padding:2px 8px;font-size:10px;min-width:36px;}'
                     'QPushButton:checked{background:#1f538d;color:white;'
                     'border-color:#2a6dbd;}'
                     'QPushButton:hover:!checked{background:#444;color:white;}')
        for v in ['0.5', '1', '3', '10', '20', '50']:
            b = QPushButton(v)
            b.setCheckable(True)
            b.setFixedHeight(28)
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
        lo.setContentsMargins(16, 0, 16, 6)
        lo.setSpacing(0)

        # Conteneur qui accueille la barre + le label centré par-dessus
        container = QWidget()
        container.setFixedHeight(20)
        container.setStyleSheet('background:transparent;')

        self.prog_bar = QProgressBar(container)
        self.prog_bar.setGeometry(0, 5, 1, 10)   # sera redimensionné dans resizeEvent
        self.prog_bar.setRange(0, 10000)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet(
            'QProgressBar{background:#333;border-radius:5px;border:none;}'
            'QProgressBar::chunk{background:#27ae60;border-radius:5px;}')
        self.prog_bar.mousePressEvent = self._on_prog_click

        # Label de temps centré par-dessus la barre
        self.lbl_time = QLabel('00:00:00 / 00:00:00', container)
        self.lbl_time.setStyleSheet(
            'color:white;font-size:9px;font-weight:bold;'
            'background:transparent;border:none;')
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lo.addWidget(container)

        # lbl_prog conservé caché pour éviter les AttributeError ailleurs
        self.lbl_prog = QLabel('')
        self.lbl_prog.hide()
        lo.addWidget(self.lbl_prog)

        # Garder une référence au container pour le resize
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

        lbl = QLabel(self.t.get('generating', 'Generating G-Code & Trajectory…'))
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
        # Redimensionner la barre de progression et le label superposé
        if hasattr(self, '_prog_container'):
            cw = self._prog_container.width()
            if cw > 0:
                self.prog_bar.setGeometry(0, 5, cw, 10)
                self.lbl_time.setGeometry(0, 0, cw, 20)
        if hasattr(self, '_ov'):
            self._ov.resize(self.size())
        # Repositionnement des overlays flottants sur le panneau droit
        if hasattr(self, '_playback_frame') and hasattr(self, '_progress_frame'):
            rw = self._right_widget
            rw_w = rw.width()
            rw_h = rw.height()
            margin = 16

            pb_hint = self._playback_frame.sizeHint()
            pr_hint = self._progress_frame.sizeHint()
            pb_h = max(pb_hint.height(), 110)
            pr_h = max(pr_hint.height(), 38)

            total_h = pb_h + pr_h + 4
            bottom_y = rw_h - total_h - margin

            self._playback_frame.setGeometry(margin, bottom_y, rw_w - 2*margin, pb_h)
            self._progress_frame.setGeometry(margin, bottom_y + pb_h + 4,
                                             rw_w - 2*margin, pr_h)
            self._playback_frame.raise_()
            self._progress_frame.raise_()

    # ══════════════════════════════════════════════════════════════
    #  GÉNÉRATION (QThread)
    # ══════════════════════════════════════════════════════════════

    def _start_gen(self):
        self._parser = GCodeParser(self.payload)
        self._worker = _GenWorker(self.engine, self.payload, self._parser)
        print(self.payload)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_error(self, msg):
        self._hide_loading()
        QMessageBox.critical(self, 'Engine Error',
                             f'Failed to generate G-code:\n{msg}')

    def _on_done(self, d):
        self._hide_loading()
        self.points_list   = d['pts']
        self.total_sec     = d.get('total_dur', 0.0)
        self.latence_mm    = d.get('latence_mm', 0.0)
        self.final_gcode   = d.get('final_gcode', '')
        self.framing_gcode = d.get('framing_gcode', '')
        self.full_metadata = d.get('meta', {})
        self.framing_end   = d.get('framing_end', 0)
        #self._last_drawn_idx = self.framing_end - 1
        self._last_drawn_idx = -1
        bx0, bx1, by0, by1 = d.get('bounds', (0, 0, 0, 0))
        self._mnx, self._mxx = bx0, bx1
        self._mny, self._mxy = by0, by1

        if self.lat_btn:
            self.lat_btn.setVisible(abs(self.latence_mm) > 1e-6)

        if self.final_gcode:
            self.gcode_view.setPlainText(self.final_gcode)
            self._update_gcode_font()

        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        QTimer.singleShot(60, self._init_canvas)

    # ══════════════════════════════════════════════════════════════
    #  INITIALISATION CANVAS
    # ══════════════════════════════════════════════════════════════

    def _init_canvas(self):
        cw, ch = self.canvas.width(), self.canvas.height()

        if cw <= 1 or ch <= 1:
            QTimer.singleShot(60, self._init_canvas)
            return

        if self.points_list is None or len(self.points_list) == 0:
            return

        # ─────────────────────────────
        # Line step exact depuis payload
        # ─────────────────────────────
        dims = self.payload.get('dims', (0, 0, 0.1, 0.1))
        raster_mode = self.payload.get('params', {}).get('raster_mode', 'horizontal')

        if len(dims) >= 4:
            l_step = float(dims[2]) if raster_mode == 'horizontal' else float(dims[3])
        else:
            l_step = 0.1

        # ─────────────────────────────
        # Dimensions & Échelle (Snapping)
        # ─────────────────────────────
        tw = max(0.1, self._mxx - self._mnx)
        th = max(0.1, self._mxy - self._mny)

        overlay_h = 120
        ch_usable = max(ch - overlay_h, int(ch * 0.6))

        # Scale théorique pour s'adapter à l'écran
        sc = min((cw * 0.80) / tw, (ch_usable * 0.80) / th)

        # NOUVEAU : On "snap" l'échelle pour que l_step fasse un nombre ENTIER de pixels
        # Cela garantit une épaisseur strictement constante sans créer de décalage
        if l_step > 0:
            step_px_int = max(1.0, np.floor(l_step * sc))
            sc = step_px_int / l_step

        pw = tw * sc
        ph = th * sc

        rw = max(1, int(round(pw)))
        rh = max(1, int(round(ph)))

        x0 = (cw - pw) / 2.0
        y0 = (ch_usable - ph) * 0.20
        

        # ─────────────────────────────
        # Line step exact depuis payload
        # ─────────────────────────────
        dims = self.payload.get('dims', (0, 0, 0.1, 0.1))
        raster_mode = self.payload.get('params', {}).get('raster_mode', 'horizontal')

        if len(dims) >= 4:
            l_step = float(dims[2]) if raster_mode == 'horizontal' else float(dims[3])
        else:
            l_step = 0.1

        # Largeur laser en pixels — forcée à l'entier pour des lignes régulières
        lw_px = max(1, round(l_step * sc))

        # ─────────────────────────────
        # Initialisation renderer
        # ─────────────────────────────
        p_params  = self.payload.get('params', {})
        p_min_pct = float(p_params.get('min_power', 0))
        p_max_pct = float(p_params.get('max_power', 100))
        # Convertir les % en valeurs S dans l'échelle ctrl_max
        pwr_min_s = self.ctrl_max * p_min_pct / 100.0
        pwr_max_s = self.ctrl_max * p_max_pct / 100.0

        self._renderer = _Renderer(
            rw,
            rh,
            sc,
            rh,
            self._mnx,
            self._mny,
            lw_px,
            self.ctrl_max,
            pwr_min=pwr_min_s,
            pwr_max=pwr_max_s,
            l_step_mm=l_step
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
        # Setup canvas
        # ─────────────────────────────
        self.canvas.setup(
            self._renderer.display_data,
            x0, y0, pw, ph, sc,
            self._mnx, self._mxx,
            self._mny, self._mxy
        )

        self.canvas.set_laser(lx, ly)

        # Forcer le repositionnement des overlays maintenant que les tailles sont connues
        self.resizeEvent(None)

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
        #start_idx  = max(0, self.framing_end - 1)
        start_idx = 0

        if target_idx <= start_idx:
            self._renderer.reset()
            self._last_drawn_idx = start_idx
        else:
            self._renderer.redraw_range(
                self.points_list,
                start_idx,
                target_idx,
                self.latence_enabled,
                self.latence_mm,
                self.full_metadata.get('scan_axis', 'X')
            )
            self._last_drawn_idx = target_idx

        self.canvas.notify_dirty()

        mx = float(self.points_list[target_idx][0])
        my = float(self.points_list[target_idx][1])
        self.canvas.set_laser(*self._mm_to_screen(mx, my))

    # ══════════════════════════════════════════════════════════════
    #  CONTRÔLES PLAYBACK
    # ══════════════════════════════════════════════════════════════

    def toggle_pause(self):
        if self.points_list is None or self.points_list.size == 0:
            return
        if self.btn_play.text() == '🔄':
            self.rewind_sim(); self._start_play(); return
        if self.sim_running:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        self.sim_running     = True
        self.last_frame_time = time.perf_counter()
        self.btn_play.setText('⏸')
        self.btn_play.setStyleSheet(self._gbtn('#e67e22', '#ca6f1e'))
        self._anim_timer.start()

    def _stop_play(self):
        self.sim_running = False
        self._anim_timer.stop()
        self.btn_play.setText('▶')
        self.btn_play.setStyleSheet(self._gbtn('#27ae60', '#1e8449'))

    def _finish_anim(self):
        self.sim_running = False
        self._anim_timer.stop()
        self.btn_play.setText('🔄')
        self.btn_play.setStyleSheet(self._gbtn('#2980b9', '#1a6090'))
        self._update_ui(len(self.points_list) - 1)

    def rewind_sim(self):
        self._stop_play()
        self.current_idx      = 0
        self.current_sim_time = 0.0
        self.last_frame_time  = 0.0
        # self._last_drawn_idx  = self.framing_end - 1
        self._last_drawn_idx = -1

        if self._renderer:
            self._renderer.reset()
            self.canvas.notify_dirty()
        self.prog_bar.setValue(0)
        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        self.btn_play.setText('▶')
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
        if self.lat_btn:
            self.lat_btn.setText(
                self.t.get('simulate_latency', 'SIMULATE LATENCY') +
                f'  {"●" if checked else "○"}')
        self._redraw_to(self.current_idx)

    def _on_prog_click(self, e):

        if self.points_list is None:
            return

        if self.total_sec <= 0:
            return

        total_pts = len(self.points_list)
        if total_pts == 0:
            return

        width = max(1, self.prog_bar.width())
        pos_x = e.position().x()
        ratio = max(0.0, min(1.0, pos_x / width))

        was_running = self.sim_running
        self._stop_play()

        self.current_sim_time = ratio * self.total_sec

        idx = np.searchsorted(
            self.points_list[:, 4],
            self.current_sim_time,
            side='right'
        ) - 1

        idx = max(0, min(int(idx), total_pts - 1))

        self.current_idx = idx

        self._redraw_to(self.current_idx)
        self._update_ui(self.current_idx)

        if was_running:
            self.last_frame_time = time.perf_counter()
            self._start_play()

    # ══════════════════════════════════════════════════════════════
    #  UI SYNC
    # ══════════════════════════════════════════════════════════════

    def _update_ui(self, idx):
        if self.points_list is None or idx >= len(self.points_list): return
        ts  = float(self.points_list[idx][4])
        pct = idx / max(1, len(self.points_list))
        self.prog_bar.setValue(int(pct * 10000))
        # lbl_prog supprimé de l'affichage (caché)
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

    def on_export(self):
        self._stop_all()
        meta = self.payload.get('metadata', {})
        ext  = self.controller.config_manager.get_item(
            'machine_settings', 'gcode_extension', '.nc')
        name = os.path.splitext(
            os.path.basename(str(meta.get('file_name', 'output'))))[0]
        self._save(os.path.join(meta.get('output_dir', ''), f'{name}{ext}')
                   .replace('\\', '/'))

    def on_export_as(self):
        self._stop_all()
        meta = self.payload.get('metadata', {})
        ext  = meta.get('file_extension', '.nc').lower()
        if not ext.startswith('.'): ext = f'.{ext}'
        name = os.path.splitext(
            os.path.basename(str(meta.get('file_name', 'output'))))[0]
        stds = [('.nc', 'NC'), ('.gcode', 'G-Code'), ('.gc', 'GC'),
                ('.tap', 'Tap'), ('.txt', 'Text')]
        parts = [f'{l} (Default) (*{e})' if e == ext else f'{l} (*{e})'
                 for e, l in stds]
        parts.append('All files (*.*)')
        path, _ = QFileDialog.getSaveFileName(
            self, self.t.get('export_as', 'Export G-Code As…'),
            os.path.join(meta.get('output_dir', ''), f'{name}{ext}'),
            ';;'.join(parts))
        if path: self._save(path.replace('\\', '/'))

    def _save(self, path):
        """Sauvegarde le G-Code physiquement et met à jour les statistiques du dashboard."""
        try:
            if not hasattr(self, 'final_gcode') or not self.final_gcode:
                QMessageBox.critical(self, 'Error',
                                     self.t.get('no_gcode', 'No G-Code to save.'))
                return

            with open(path, 'w') as f:
                f.write(self.final_gcode)

            matrix = self.payload.get('matrix')
            if matrix is not None:
                from core.utils import save_dashboard_data
                estimated_time = getattr(self, 'total_sec', 0)
                save_dashboard_data(
                    config_manager=self.controller.config_manager,
                    matrix=matrix,
                    gcode_content=self.final_gcode,
                    estimated_time=estimated_time
                )
                print(estimated_time)

            QMessageBox.information(self, 'Success',
                                    f'{self.t.get("save_success", "G-Code saved successfully:")}\n{path}')
            self._navigate_back()

        except Exception as e:
            QMessageBox.critical(self, 'Error',
                                 f'{self.t.get("save_failed", "Save failed:")}\n{str(e)}')

    # ══════════════════════════════════════════════════════════════
    #  NAVIGATION / FERMETURE
    # ══════════════════════════════════════════════════════════════

    def on_cancel(self):
        self._stop_all(); self._navigate_back()

    def _navigate_back(self):
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
