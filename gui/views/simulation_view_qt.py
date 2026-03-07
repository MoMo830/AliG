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
      1. _compute_polys()  vectorise TOUS les segments éligibles en une fois
         via NumPy  →  tableau de QPolygonF groupés par couleur.
      2. _rasterize()  ouvre UN QPainter sur le QImage et dessine tous les
         polygones en une seule boucle Python sans calcul dans la boucle.
      3. Résultat copié dans display_data uint8.
    """

    def __init__(self, rect_w, rect_h, scale, total_px_h,
                 min_x, min_y, laser_width_px, ctrl_max):
        self.rect_w         = rect_w
        self.rect_h         = rect_h
        self.scale          = scale
        self.total_px_h     = total_px_h
        self.min_x          = min_x
        self.min_y          = min_y
        self.laser_width_px = max(1.0, float(laser_width_px))
        self.ctrl_max       = ctrl_max
        self.display_data   = np.full((rect_h, rect_w), 255, dtype=np.uint8)
        self._qi_ref        = None   # référence QImage pour éviter le GC
        
    def reset(self):
        self.display_data.fill(255)

    # ─── Calcul vectorisé des polygones ─────────────────────────────────────

    def _compute_polys(self, pts_arr, start, end,
                       use_lat, lat_mm, scan_axis):
        if pts_arr is None or len(pts_arr) < 2:
            return None
        
        # Sécurité sur les index pour éviter les tableaux vides
        # start+1 doit être < len(pts_arr)
        if start >= end or start >= len(pts_arr) - 1:
            return None

        # Ajustement de l'index de fin pour ne pas déborder
        safe_end = min(end, len(pts_arr) - 1)

        # Slices source (départ) / dest (arrivée)
        # On s'assure que p1 et p2 ont EXACTEMENT la même longueur
        p1 = pts_arr[start : safe_end]
        p2 = pts_arr[start + 1 : safe_end + 1]

        if len(p1) == 0:
            return None

        # --- FILTRE PUISSANCE ---
        # On utilise p2 pour la puissance (état à l'arrivée du segment)
        mask = p2[:, 2] > 0
        
        if not mask.any():
            return None
            
        # On applique le masque aux deux simultanément pour garder la cohérence
        p1 = p1[mask]
        p2 = p2[mask]
        
        # Extraction des coordonnées après filtrage
        x1 = p1[:, 0];  y1 = p1[:, 1]
        x2 = p2[:, 0];  y2 = p2[:, 1]

        # --- CORRECTION LATENCE ---
        if use_lat and lat_mm != 0:
            # On travaille sur des copies pour ne pas modifier pts_arr original
            x1 = x1.copy(); x2 = x2.copy()
            y1 = y1.copy(); y2 = y2.copy()
            
            if scan_axis == 'X':
                dx_raw = x2 - x1
                pos_m = dx_raw > 1e-6
                neg_m = dx_raw < -1e-6
                x1[pos_m] += lat_mm; x2[pos_m] += lat_mm
                x1[neg_m] -= lat_mm; x2[neg_m] -= lat_mm
            else:
                dy_raw = y2 - y1
                pos_m = dy_raw > 1e-6
                neg_m = dy_raw < -1e-6
                y1[pos_m] += lat_mm; y2[pos_m] += lat_mm
                y1[neg_m] -= lat_mm; y2[neg_m] -= lat_mm

        # --- CONVERSION MM -> PIXELS ---
        sc = self.scale; mnx = self.min_x; mny = self.min_y; th = self.total_px_h
        ix1 = (x1 - mnx) * sc; iy1 = th - (y1 - mny) * sc
        ix2 = (x2 - mnx) * sc; iy2 = th - (y2 - mny) * sc

        dx = ix2 - ix1; dy = iy2 - iy1
        dist_sq = dx*dx + dy*dy

        # --- FILTRE LONGUEUR MINIMALE ---
        vis = dist_sq >= 0.25
        if not vis.any():
            return None
            
        ix1, iy1 = ix1[vis], iy1[vis]
        ix2, iy2 = ix2[vis], iy2[vis]
        dx, dy, dist_sq = dx[vis], dy[vis], dist_sq[vis]
        
        # IMPORTANT : On filtre aussi la puissance pour les couleurs
        # On prend la puissance de p2 (point d'arrivée)
        pwr = p2[:, 2][vis]

        # --- CALCUL GÉOMÉTRIQUE DES QUADS ---
        length = np.sqrt(dist_sq)
        half = self.laser_width_px * 0.5
        # Normales (perpendiculaires au segment)
        nx = (-dy / length) * half
        ny = ( dx / length) * half

        colors = np.clip(255.0 * (1.0 - pwr / self.ctrl_max), 0, 255).astype(np.uint8)

        p_tl = np.stack([ix1 + nx, iy1 + ny], axis=1)
        p_bl = np.stack([ix1 - nx, iy1 - ny], axis=1)
        p_br = np.stack([ix2 - nx, iy2 - ny], axis=1)
        p_tr = np.stack([ix2 + nx, iy2 + ny], axis=1)

        # --- REGROUPEMENT PAR COULEUR ---
        result = {}
        for i in range(len(colors)):
            c = int(colors[i])
            poly = QPolygonF([
                QPointF(p_tl[i, 0], p_tl[i, 1]),
                QPointF(p_bl[i, 0], p_bl[i, 1]),
                QPointF(p_br[i, 0], p_br[i, 1]),
                QPointF(p_tr[i, 0], p_tr[i, 1]),
            ])
            if c not in result:
                result[c] = []
            result[c].append(poly)
            
        return result

    # ─── Une passe QPainter ──────────────────────────────────────────────────

    def _rasterize(self, polys_by_color):
        """Dessine tous les polygones sur self.display_data en une seule passe."""
        if not polys_by_color:
            return
        h, w = self.display_data.shape

        # QImage Grayscale8 wrappant une copie contiguë de display_data
        buf = self.display_data.tobytes()
        qi  = QImage(buf, w, h, w, QImage.Format.Format_Grayscale8)
        # Détacher pour que Qt possède sa propre copie modifiable
        qi  = qi.copy()

        qp = QPainter(qi)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        qp.setPen(Qt.PenStyle.NoPen)

        for c, polys in polys_by_color.items():
            qp.setBrush(QBrush(QColor(c, c, c)))
            for poly in polys:
                qp.drawPolygon(poly)
        qp.end()

        # 1. Récupérer les dimensions et le saut de ligne (stride)
        h, w = qi.height(), qi.width()
        bpl = qi.bytesPerLine() # Nombre d'octets réels par ligne (avec padding)

        # 2. Récupérer le pointeur et fixer la taille sur le buffer RÉEL (total)
        ptr = qi.bits()
        ptr.setsize(bpl * h)

        # 3. Créer le tableau NumPy avec la largeur RÉELLE (incluant le padding)
        # On utilise bpl au lieu de w pour le reshape initial
        full_arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)

        # 4. Découper (slicing) pour enlever le padding inutile et ne garder que l'image
        arr = full_arr[:, :w]

        # 5. Copie vers display_data
        np.copyto(self.display_data, arr)
        self._qi_ref = qi


    # ─── API publique ────────────────────────────────────────────────────────

    def redraw_range(self, pts_arr, start, end, use_lat, lat_mm, scan_axis):
        """Repart d'un fond blanc et dessine [start, end)."""
        self.display_data.fill(255)
        polys = self._compute_polys(pts_arr, start, end, use_lat, lat_mm, scan_axis)
        self._rasterize(polys)

    def draw_incremental(self, pts_arr, start, end, use_lat, lat_mm, scan_axis):
        """Ajoute les segments [start, end) sur l'état existant (animation)."""
        polys = self._compute_polys(pts_arr, start, end, use_lat, lat_mm, scan_axis)
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
        self._img_buf   = None   # référence numpy externe
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
        # Coord mm
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
        self.left.setFixedWidth(420)
        self.left.setStyleSheet(
            'QFrame{background:#1e1e1e; border-right:1px solid #333;}')
        lo = QVBoxLayout(self.left)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)

        title = QLabel(self.t.get('path_sim', 'G-Code Trajectory'))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            'color:white;font-size:14px;font-weight:bold;border:none;')
        lo.addWidget(title)

        lo.addWidget(self._make_stats_widget())

        gl = QLabel(self.t.get('live_gcode', 'Live G-Code'))
        gl.setStyleSheet('color:white;font-weight:bold;font-size:11px;border:none;')
        lo.addWidget(gl)

        self.gcode_view = QPlainTextEdit()
        self.gcode_view.setReadOnly(True)
        self.gcode_view.setStyleSheet(
            'QPlainTextEdit{background:#1a1a1a;color:#00ff00;'
            'font-family:Consolas;font-size:10px;'
            'border:1px solid #333;border-radius:3px;}')
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

        add_row(self.t.get('final_size','Size'), f'{w_mm:.2f} x {h_mm:.2f} mm')
        add_row(self.t.get('output_file','Output'),
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
        for key, txt in [('is_pointing', self.t.get('pointing_opt','POINTING')),
                         ('is_framing',  self.t.get('framing_opt', 'FRAMING'))]:
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

        self.lat_btn = None
        lat_val = float(self.payload.get('params', {}).get('laser_latency', 0))
        if lat_val != 0:
            self.lat_btn = QPushButton('SIMULATE LATENCY  ○')
            self.lat_btn.setCheckable(True)
            self.lat_btn.setStyleSheet(
                'QPushButton{background:#333;color:#888;border:1px solid #555;'
                'border-radius:4px;padding:4px 10px;font-size:10px;font-weight:bold;}'
                'QPushButton:checked{background:#1a4a2a;color:#2ecc71;'
                'border-color:#2ecc71;}')
            self.lat_btn.toggled.connect(self._on_lat_toggle)
            lo.addWidget(self.lat_btn)
        return f

    def _make_action_buttons(self):
        f = QFrame()
        f.setStyleSheet('QFrame{border:none;background:transparent;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(4)

        er = QHBoxLayout()
        self.btn_export = QPushButton(self.t.get('quick_export','Quick Export'))
        self.btn_export.setFixedHeight(40)
        self.btn_export.setStyleSheet(self._gbtn('#2ecc71','#27ae60'))
        self.btn_export.clicked.connect(self.on_export)

        self.btn_export_as = QPushButton(self.t.get('export_as','Export As…'))
        self.btn_export_as.setFixedSize(110, 40)
        self.btn_export_as.setStyleSheet(self._gbtn('#7ac99b','#27ae60'))
        self.btn_export_as.clicked.connect(self.on_export_as)

        er.addWidget(self.btn_export)
        er.addWidget(self.btn_export_as)
        lo.addLayout(er)

        self.btn_cancel = QPushButton(self.t.get('cancel','Cancel'))
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setStyleSheet(self._gbtn('#333','#444'))
        self.btn_cancel.clicked.connect(self.on_cancel)
        lo.addWidget(self.btn_cancel)
        return f

    # ─── Panneau droit ───────────────────────────────────────────

    def _make_right_panel(self):
        w = QWidget()
        w.setStyleSheet('background:#111;')
        lo = QVBoxLayout(w)
        lo.setContentsMargins(10, 10, 10, 10)
        lo.setSpacing(6)

        self.canvas = _SimCanvas()
        lo.addWidget(self.canvas, stretch=1)
        lo.addWidget(self._make_playback_bar())
        lo.addWidget(self._make_progress_bar())
        return w

    def _make_playback_bar(self):
        f = QFrame()
        f.setStyleSheet('QFrame{background:transparent;border:none;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(5)

        # Transport
        tr = QHBoxLayout()
        tr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_rew  = QPushButton('⏮')
        self.btn_rew.setFixedSize(60, 40)
        self.btn_rew.setFont(QFont('Arial', 16))
        self.btn_rew.setStyleSheet(self._gbtn('#444','#555'))
        self.btn_rew.clicked.connect(self.rewind_sim)

        self.btn_play = QPushButton('▶')
        self.btn_play.setFixedSize(100, 40)
        self.btn_play.setFont(QFont('Arial', 16))
        self.btn_play.setStyleSheet(self._gbtn('#27ae60','#1e8449'))
        self.btn_play.clicked.connect(self.toggle_pause)

        btn_end = QPushButton('⏭')
        btn_end.setFixedSize(60, 40)
        btn_end.setFont(QFont('Arial', 16))
        btn_end.setStyleSheet(self._gbtn('#444','#555'))
        btn_end.clicked.connect(self.skip_to_end)

        btn_fit = QPushButton('⊞')
        btn_fit.setFixedSize(40, 40)
        btn_fit.setFont(QFont('Arial', 16))
        btn_fit.setToolTip('Reset zoom / pan')
        btn_fit.setStyleSheet(self._gbtn('#333','#444'))
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
        for v in ['0.5','1','3','10','20','50']:
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
        f.setStyleSheet('QFrame{background:transparent;border:none;}')
        lo = QVBoxLayout(f)
        lo.setContentsMargins(30, 0, 30, 8)
        lo.setSpacing(3)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setRange(0, 10000)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet(
            'QProgressBar{background:#333;border-radius:4px;border:none;}'
            'QProgressBar::chunk{background:#27ae60;border-radius:4px;}')
        self.prog_bar.mousePressEvent = self._on_prog_click
        lo.addWidget(self.prog_bar)

        tr = QHBoxLayout()
        self.lbl_prog = QLabel(f'{self.t.get("progress","Progress")} 0%')
        self.lbl_prog.setStyleSheet('color:#aaa;font-size:11px;')
        self.lbl_time = QLabel('00:00:00 / 00:00:00')
        self.lbl_time.setStyleSheet('color:#aaa;font-size:11px;font-style:italic;')
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        tr.addWidget(self.lbl_prog)
        tr.addWidget(self.lbl_time)
        lo.addLayout(tr)
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

        lbl = QLabel('Generating G-Code & Trajectory…')
        lbl.setStyleSheet('color:white;font-size:14px;font-weight:bold;border:none;')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(lbl)

        pb = QProgressBar()
        pb.setFixedHeight(10)
        pb.setRange(0, 0)   # indéterminé
        pb.setStyleSheet('QProgressBar{background:#555;border-radius:5px;border:none;}'
                         'QProgressBar::chunk{background:#27ae60;border-radius:5px;}')
        bl.addWidget(pb)
        lo.addWidget(box)

    def _hide_loading(self):
        if hasattr(self, '_ov'):
            self._ov.hide()
            self._ov.deleteLater()
            del self._ov

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, '_ov'):
            self._ov.resize(self.size())

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
        self._last_drawn_idx = self.framing_end - 1
        bx0, bx1, by0, by1 = d.get('bounds', (0, 0, 0, 0))
        self._mnx, self._mxx = bx0, bx1
        self._mny, self._mxy = by0, by1

        if self.lat_btn:
            self.lat_btn.setVisible(abs(self.latence_mm) > 1e-6)

        if self.final_gcode:
            self.gcode_view.setPlainText(self.final_gcode)
            lines = self.final_gcode.splitlines()
            if lines:
                mc  = max(len(l) for l in lines)
                uw  = max(100, self.left.width() - 20)
                fs  = max(6, min(18, int(uw / (mc * 0.55))))
                fnt = self.gcode_view.font()
                fnt.setPointSize(fs)
                self.gcode_view.setFont(fnt)

        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        QTimer.singleShot(60, self._init_canvas)

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

        # ─────────────────────────────
        # Dimensions réelles pièce (mm)
        # ─────────────────────────────
        tw = max(0.1, self._mxx - self._mnx)
        th = max(0.1, self._mxy - self._mny)

        # Scale écran
        sc = min((cw * 0.80) / tw, (ch * 0.75) / th)

        # Dimensions projetées écran
        pw = tw * sc
        ph = th * sc

        # Dimensions buffer image (entiers)
        rw = max(1, int(round(pw)))
        rh = max(1, int(round(ph)))

        # Position centrée
        x0 = (cw - pw) / 2.0
        y0 = (ch - ph) / 2.0

        # ─────────────────────────────
        # Line step exact depuis payload
        # ─────────────────────────────
        dims = self.payload.get('dims', (0, 0, 0.1, 0.1))
        raster_mode = self.payload.get('params', {}).get('raster_mode', 'horizontal')

        if len(dims) >= 4:
            l_step = float(dims[2]) if raster_mode == 'horizontal' else float(dims[3])
        else:
            l_step = 0.1

        # Largeur laser en pixels (float conservé)
        lw_px = max(1.0, l_step * sc)

        # ─────────────────────────────
        # Initialisation renderer
        # IMPORTANT : total_px_h = rh (hauteur buffer réelle)
        # ─────────────────────────────
        self._renderer = _Renderer(
            rw,
            rh,
            sc,
            rh,              # ← hauteur réelle buffer
            self._mnx,
            self._mny,
            lw_px,
            self.ctrl_max
        )

        # Stockage géométrie
        self._px_w, self._px_h = pw, ph
        self._x0, self._y0 = x0, y0
        self._scale = sc

        # Index sécurisé
        self._last_drawn_idx = max(0, self.framing_end - 1)

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
        # Avancement index via searchsorted (beaucoup plus sûr)
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

            start_idx = max(0, self.framing_end - 1)

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

        # Clamp sécurisé de l’index cible
        target_idx = max(0, min(int(target_idx), total_pts - 1))

        # Index de départ sécurisé (évite -1 si framing_end == 0)
        start_idx = max(0, self.framing_end - 1)

        # Si target est avant le début utile → reset propre
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

        # Marquer l’image comme dirty pour rebuild pixmap
        self.canvas.notify_dirty()

        # Positionner le laser proprement
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
        self.btn_play.setStyleSheet(self._gbtn('#e67e22','#ca6f1e'))
        self._anim_timer.start()

    def _stop_play(self):
        self.sim_running = False
        self._anim_timer.stop()
        self.btn_play.setText('▶')
        self.btn_play.setStyleSheet(self._gbtn('#27ae60','#1e8449'))

    def _finish_anim(self):
        self.sim_running = False
        self._anim_timer.stop()
        self.btn_play.setText('🔄')
        self.btn_play.setStyleSheet(self._gbtn('#2980b9','#1a6090'))
        self._update_ui(len(self.points_list) - 1)

    def rewind_sim(self):
        self._stop_play()
        self.current_idx      = 0
        self.current_sim_time = 0.0
        self.last_frame_time  = 0.0
        self._last_drawn_idx  = self.framing_end - 1
        if self._renderer:
            self._renderer.reset()
            self.canvas.notify_dirty()
        self.prog_bar.setValue(0)
        self.lbl_prog.setText(f'{self.t.get("progress","Progress")} 0%')
        self.lbl_time.setText(f'00:00:00 / {self._fmt(self.total_sec)}')
        self.btn_play.setText('▶')
        self.btn_play.setStyleSheet(self._gbtn('#27ae60','#1e8449'))
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
                f'SIMULATE LATENCY  {"●" if checked else "○"}')
        self._redraw_to(self.current_idx)

    def _on_prog_click(self, e):

        if self.points_list is None:
            return

        if self.total_sec <= 0:
            return

        total_pts = len(self.points_list)
        if total_pts == 0:
            return

        # Ratio sécurisé
        width = max(1, self.prog_bar.width())
        pos_x = e.position().x()
        ratio = max(0.0, min(1.0, pos_x / width))

        was_running = self.sim_running
        self._stop_play()

        # Nouveau temps
        self.current_sim_time = ratio * self.total_sec

        # Recherche index stable
        idx = np.searchsorted(
            self.points_list[:, 4],
            self.current_sim_time,
            side='right'
        ) - 1

        idx = max(0, min(int(idx), total_pts - 1))

        self.current_idx = idx

        # Redraw complet sécurisé
        self._redraw_to(self.current_idx)

        # UI update
        self._update_ui(self.current_idx)

        # Reprendre si nécessaire
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
        self.lbl_prog.setText(
            f'{self.t.get("progress","Progress")} {int(pct*100)}%')
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
        self._save(os.path.join(meta.get('output_dir',''), f'{name}{ext}')
                   .replace('\\','/'))

    def on_export_as(self):
        self._stop_all()
        meta = self.payload.get('metadata', {})
        ext  = meta.get('file_extension', '.nc').lower()
        if not ext.startswith('.'): ext = f'.{ext}'
        name = os.path.splitext(
            os.path.basename(str(meta.get('file_name','output'))))[0]
        stds = [('.nc','NC'),('.gcode','G-Code'),('.gc','GC'),
                ('.tap','Tap'),('.txt','Text')]
        parts = [f'{l} (Default) (*{e})' if e==ext else f'{l} (*{e})'
                 for e,l in stds]
        parts.append('All files (*.*)')
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export G-Code As…',
            os.path.join(meta.get('output_dir',''), f'{name}{ext}'),
            ';;'.join(parts))
        if path: self._save(path.replace('\\','/'))

    def _save(self, path):
        """Sauvegarde le G-Code physiquement et met à jour les statistiques du dashboard."""
        try:
            # 1. Vérification de l'existence du G-Code
            if not hasattr(self, 'final_gcode') or not self.final_gcode:
                QMessageBox.critical(self, 'Error', 'No G-Code to save.')
                return

            # 2. Sauvegarde physique du fichier
            with open(path, 'w') as f:
                f.write(self.final_gcode)

            # 3. Logique de mise à jour du Dashboard
            matrix = self.payload.get('matrix')
            if matrix is not None:
                from core.utils import save_dashboard_data
                
                # On récupère le temps (total_sim_seconds ou total_sec selon votre modèle)
                estimated_time = getattr(self, 'total_sec', 0)

                save_dashboard_data(
                    config_manager=self.controller.config_manager,
                    matrix=matrix,
                    gcode_content=self.final_gcode,
                    estimated_time=estimated_time
                )
                print(estimated_time)
            # 4. Feedback utilisateur et navigation
            QMessageBox.information(self, 'Success', f'G-Code saved successfully:\n{path}')
            self._navigate_back()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Save failed:\n{str(e)}')

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
        if hasattr(self,'_worker') and self._worker.isRunning():
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
