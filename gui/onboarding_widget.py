# -*- coding: utf-8 -*-
"""
A.L.I.G. - OnboardingWidget
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QStackedWidget,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QSize, pyqtSignal
import os
import re
import tempfile
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath, QPixmap, QIcon


# ═══════════════════════════════════════════════════════════════════
#  HIGHLIGHT OVERLAY
# ═══════════════════════════════════════════════════════════════════

class HighlightOverlay(QWidget):
    """
    Overlay plein-ecran pose sur la fenetre principale.
    - Assombrit tout sauf les zones cibles (interieur transparent)
    - Bordure orange fixe autour de chaque cible
    - Fleche droite depuis arrow_from vers le bord de la cible
    Pas d'animation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # WA_NoSystemBackground : Qt ne remplit pas le fond du widget avant paintEvent
        # WA_TransparentForMouseEvents : les clics passent au travers
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._targets = []
        self._active  = False

    def show_highlights(self, targets):
        """
        targets: list of dict
          { "rect": QRect, "arrow_from": QPoint or None }
        """
        self._targets = targets or []
        self._active  = True
        if self.parent():
            self.resize(self.parent().size())
        self.raise_()
        self.show()
        self.update()

    def hide_highlights(self):
        self._active  = False
        self._targets = []
        self.hide()
        self.update()

    def paintEvent(self, _):
        if not self._active or not self._targets:
            return
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Construire le path global = ecran entier MOINS les zones cibles
        # => le dim ne couvre que les zones hors cibles, les cibles restent
        #    completement transparentes (on ne dessine rien dessus)
        full = QPainterPath()
        full.addRect(float(0), float(0), float(W), float(H))

        cutouts = QPainterPath()
        for t in self._targets:
            # no_border = zone onboarding : pad nul, coupe exactement la zone
            if t.get("no_border"):
                pad = 0
            elif t.get("small_padding"):
                pad = 3
            else:
                pad = 8
            r = t["rect"].adjusted(-pad, -pad, pad, pad)
            hole = QPainterPath()
            hole.addRoundedRect(
                float(r.x()), float(r.y()),
                float(r.width()), float(r.height()),
                10.0, 10.0)
            cutouts = cutouts.united(hole)

        dim_path = full.subtracted(cutouts)

        qp.setPen(Qt.PenStyle.NoPen)
        qp.setBrush(QBrush(QColor(0, 0, 0, 160)))
        qp.drawPath(dim_path)

        # Bordure orange sur les cibles qui n'ont pas no_border=True
        qp.setPen(QPen(QColor("#FF9500"), 2))
        qp.setBrush(Qt.BrushStyle.NoBrush)
        for t in self._targets:
            if t.get("no_border"):
                continue
            pad = 3 if t.get("small_padding") else 8
            r = t["rect"].adjusted(-pad, -pad, pad, pad)
            qp.drawRoundedRect(r, 10, 10)

        qp.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.parent():
            self.resize(self.parent().size())


# ═══════════════════════════════════════════════════════════════════
#  STEP BASE
# ═══════════════════════════════════════════════════════════════════

class _StepBase(QWidget):
    def __init__(self, t, colors, parent=None):
        super().__init__(parent)
        self.t = t
        self.c = colors
        self.setStyleSheet("background: transparent;")
        self._lo = QVBoxLayout(self)
        self._lo.setContentsMargins(24, 16, 24, 10)
        self._lo.setSpacing(10)
        self._lo.setAlignment(Qt.AlignmentFlag.AlignTop)

    # police sobre : titre en text (pas orange), 14px
    def _title(self, key):
        lbl = QLabel(self.t.get(key, key))
        col = self.c.get("text", "#dddddd")
        lbl.setStyleSheet(
            "color: " + col + "; font-weight: 700;"
            " border: none; background: transparent;")
        lbl.setWordWrap(True)
        return lbl

    def _body(self, key):
        lbl = QLabel(self.t.get(key, key))
        col = self.c.get("text_secondary", "#aaaaaa")
        lbl.setStyleSheet(
            "color: " + col + ";"
            " border: none; background: transparent;")
        lbl.setWordWrap(True)
        return lbl

    def _hint(self, key):
        lbl = QLabel(self.t.get(key, key))
        col = self.c.get("text_secondary", "#888888")
        lbl.setStyleSheet(
            "color: " + col + "; font-style: italic;"
            " border: none; background: transparent;")
        lbl.setWordWrap(True)
        return lbl

    def _sep(self):
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet("background: #333333; border: none;")
        return f

    @staticmethod
    def _arrow_path(color="#aaaaaa"):
        """Retourne le chemin d'un SVG de flèche recolorisé."""
        try:
            from utils.paths import SVG_ICONS
            src = SVG_ICONS.get("ARROW_DOWN", "")
            if src and os.path.isfile(src):
                with open(src, "r", encoding="utf-8") as f:
                    svg = f.read()
                svg = re.sub(r'fill\s*=\s*"[^"]*"',  f'fill="{color}"',  svg)
                svg = re.sub(r'fill\s*:\s*[^;}"]+',   f'fill:{color}',    svg)
                svg = re.sub(r'stroke\s*=\s*"[^"]*"', f'stroke="{color}"', svg)
                svg = re.sub(r'stroke\s*:\s*[^;}"]+', f'stroke:{color}',   svg)
                tmp = tempfile.NamedTemporaryFile(
                    suffix=f'_arrow_{color.strip("#")}.svg',
                    delete=False, mode='w', encoding='utf-8')
                tmp.write(svg)
                tmp.close()
                return tmp.name.replace("\\", "/")
        except Exception:
            pass
        return ""

    def _combo(self, options):
        cb = QComboBox()
        cb.addItems(options)
        cb.setFixedHeight(30)
        # Forcer la font en pixels via setFont — évite le warning
        # QFont::setPointSize <= 0 causé par font-size: Npx en CSS
        f = QFont()
        f.setPointSizeF(9.75)
        cb.setFont(f)
        bg  = self.c.get("bg_entry",      "#2b2b2b")
        brd = self.c.get("border_strong", "#555555")
        col = self.c.get("text",          "#dddddd")
        arr = self.c.get("arrow_color",   "#aaaaaa")
        arrow_path = self._arrow_path(arr)
        arrow_css = (
            "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right;"
            " width: 25px; border: none; background: transparent; }"
            " QComboBox::down-arrow { image: url(" + arrow_path + "); width: 12px; height: 8px; }"
        ) if arrow_path else "QComboBox::drop-down { border: none; }"
        cb.setStyleSheet(
            "QComboBox { background: " + bg + "; border: 1px solid " + brd + ";"
            " border-radius: 5px; color: " + col + "; padding: 3px 30px 3px 10px; }"
            + arrow_css +
            " QComboBox QAbstractItemView { background: " + bg + "; color: " + col + ";"
            " selection-background-color: " + self.c.get("combo_selection", "#1F6AA5") + "; }")
        return cb

    def _entry(self, placeholder="", default=""):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setText(default)
        e.setFixedHeight(30)
        bg  = self.c.get("bg_entry",      "#2b2b2b")
        brd = self.c.get("border_strong", "#555555")
        col = self.c.get("text",          "#dddddd")
        _f = QFont(); _f.setPointSizeF(9.75)
        e.setFont(_f)
        e.setStyleSheet(
            "QLineEdit { background: " + bg + "; border: 1px solid " + brd + ";"
            " border-radius: 5px; color: " + col + "; padding: 3px 8px; }")
        return e

    def _row(self, label_key, widget):
        row = QHBoxLayout()
        col = self.c.get("text", "#dddddd")
        lbl = QLabel(self.t.get(label_key, label_key))
        _fr = QFont(); _fr.setPointSizeF(9.75)
        lbl.setFont(_fr)
        lbl.setStyleSheet(
            "color: " + col + "; border: none;"
            " background: transparent; min-width: 160px;")
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        return row

    # Cadre sans fond (transparent) avec bordure coloree
    def _card_frame(self, border_color):
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background: transparent; border: 1px solid " + border_color + ";"
            " border-radius: 8px; }"
            " QLabel { border: none; background: transparent; }")
        return f

    def get_values(self):
        return {}


# ── Flag rendering ───────────────────────────────────────────────

def _make_flag_bands(bands, vertical=False, size=28):
    """
    Génère un QPixmap circulaire à bandes.
    vertical=True : bandes verticales (ex: France)
    vertical=False : bandes horizontales (ex: Allemagne)
    """
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    qp = QPainter(pix)
    qp.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, size, size))
    qp.setClipPath(clip)
    pos = 0.0
    for color, frac in bands:
        dim = size * frac
        if vertical:
            qp.fillRect(QRectF(pos, 0, dim + 1, size), QColor(color))
        else:
            qp.fillRect(QRectF(0, pos, size, dim + 1), QColor(color))
        pos += dim
    qp.end()
    return pix


def _make_flag_from_image(path, size=28):
    """Charge un PNG/JPG et le découpe en cercle."""
    src = QPixmap(path)
    if src.isNull():
        return None
    src = src.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    # Centrer si nécessaire
    if src.width() > size or src.height() > size:
        x = (src.width()  - size) // 2
        y = (src.height() - size) // 2
        src = src.copy(x, y, size, size)
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    qp = QPainter(pix)
    qp.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, size, size))
    qp.setClipPath(clip)
    qp.drawPixmap(0, 0, src)
    qp.end()
    return pix


# Mapping langue -> nom de fichier SVG dans assets/flags/
_FLAG_SVG = {
    "English":  "us.svg",
    "Français": "fr.svg",
    "Deutsch":  "de.svg",
}


def _build_flag_pixmap(lang, size=28):
    """
    Charge le SVG du drapeau depuis assets/flags/ et le rasterise
    en cercle via QSvgRenderer. Fallback bandes colorées si absent.
    """
    try:
        from utils.paths import ASSETS_DIR
        import os
        from PyQt6.QtSvg import QSvgRenderer
        fname = _FLAG_SVG.get(lang)
        if fname:
            svg_path = os.path.join(ASSETS_DIR, "flags", fname)
            if os.path.isfile(svg_path):
                pix = QPixmap(size, size)
                pix.fill(QColor(0, 0, 0, 0))
                qp = QPainter(pix)
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                # Clip circulaire
                clip = QPainterPath()
                clip.addEllipse(QRectF(0, 0, size, size))
                qp.setClipPath(clip)
                renderer = QSvgRenderer(svg_path)
                renderer.render(qp, QRectF(0, 0, size, size))
                qp.end()
                return pix
    except Exception:
        pass
    # Fallback dessiné si SVG absent ou erreur
    if lang == "Français":
        return _make_flag_bands(
            [("#002395", 1/3), ("#FFFFFF", 1/3), ("#ED2939", 1/3)],
            vertical=True, size=size)
    elif lang == "Deutsch":
        return _make_flag_bands(
            [("#000000", 1/3), ("#DD0000", 1/3), ("#FFCE00", 1/3)],
            vertical=False, size=size)
    else:
        return _make_flag_bands(
            [("#B22234", 1/13), ("#FFFFFF", 1/13)] * 6 + [("#B22234", 1/13)],
            vertical=False, size=size)


# Langues disponibles (ordre d'affichage)
_FLAGS = ["English", "Français", "Deutsch"]


class _LangButton(QPushButton):
    """Petit bouton drapeau circulaire avec indicateur actif."""
    SIZE = 28

    def __init__(self, lang, is_active, parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setFixedSize(self.SIZE + 4, self.SIZE + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(lang)
        pix = _build_flag_pixmap(lang, self.SIZE)
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(self.SIZE, self.SIZE))
        self._active = is_active
        self._apply_style()

    def set_active(self, active):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                "QPushButton { background: transparent; border: 2px solid #FF9500;"
                " border-radius: " + str((self.SIZE + 4) // 2) + "px; padding: 0px; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background: transparent; border: 2px solid transparent;"
                " border-radius: " + str((self.SIZE + 4) // 2) + "px; padding: 0px; }"
                " QPushButton:hover { border-color: #666666; }"
            )


# ── Step 1 : Bienvenue ────────────────────────────────────────────

class _Step1Welcome(_StepBase):
    highlight_names = ['onboarding_area']

    def __init__(self, t, colors, current_lang="English", parent=None):
        super().__init__(t, colors, parent)
        self._lang_btns = {}

        # ── Ligne titre + drapeaux ────────────────────────────
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        title_lbl = QLabel(t.get("step1_title", "Welcome"))
        col_t = colors.get("text", "#dddddd")
        title_lbl.setStyleSheet(
            "color: " + col_t + "; font-weight: 700;"
            " border: none; background: transparent;")
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)
        # Drapeaux
        flags_row = QHBoxLayout()
        flags_row.setSpacing(4)
        flags_row.setContentsMargins(0, 0, 0, 0)
        for lang in _FLAGS:  # _FLAGS est une liste
            btn = _LangButton(lang, lang == current_lang)
            btn.clicked.connect(lambda checked, l=lang: self._on_lang(l))
            flags_row.addWidget(btn)
            self._lang_btns[lang] = btn
        top_row.addLayout(flags_row)
        self._lo.addLayout(top_row)

        self._lo.addSpacing(4)
        self._lo.addWidget(self._body("step1_body"))
        self._lo.addSpacing(8)
        col = colors.get("text_secondary", "#aaaaaa")
        for key in ("step11_body", "step12_body", "step13_body", "step14_body"):
            row = QHBoxLayout()
            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet("background: #ffffff; border-radius: 3px; border: none;")
            lbl = QLabel(t.get(key, ""))
            lbl.setStyleSheet(
                "color: " + col + "; border: none; background: transparent;")
            lbl.setWordWrap(True)
            row.addWidget(dot)
            row.addSpacing(8)
            row.addWidget(lbl, 1)
            self._lo.addLayout(row)
        self._lo.addStretch()

    def _on_lang(self, lang):
        for l, btn in self._lang_btns.items():
            btn.set_active(l == lang)
        # Remonter au OnboardingWidget via le parent
        p = self.parent()
        while p and not isinstance(p, OnboardingWidget):
            p = p.parent()
        if p:
            p.language_changed.emit(lang)


# ── Step 2 : Config machine ───────────────────────────────────────

class _Step2Config(_StepBase):
    highlight_names = ['onboarding_area']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        # Forcer la font sur tout le step pour éviter le warning pixelSize
        _base_font = QFont(); _base_font.setPointSizeF(9.75)
        self.setFont(_base_font)
        self._lo.addWidget(self._title("step2_title"))
        self._lo.addWidget(self._body("step2_body"))
        # Ligne unique : combo réduit + M67 output inline
        col = colors.get("text", "#dddddd")
        cmd_row = QHBoxLayout()
        cmd_lbl = QLabel(t.get("cmd_mode_lbl", "Command mode:"))
        _fc = QFont(); _fc.setPointSizeF(9.75)
        cmd_lbl.setFont(_fc)
        cmd_lbl.setStyleSheet(
            "color: " + col + "; border: none;"
            " background: transparent; min-width: 120px;")
        self.cmd_combo = self._combo(["S (Spindle)", "M67 (Analog)"])
        self.cmd_combo.setFixedWidth(160)
        cmd_row.addWidget(cmd_lbl)
        cmd_row.addWidget(self.cmd_combo)
        cmd_row.addSpacing(10)
        # M67 output inline (masqué par défaut)
        self._m67_lbl = QLabel(t.get("m67_output_lbl", "Output:"))
        self._m67_lbl.setStyleSheet(
            "color: " + col + "; border: none; background: transparent;")
        _f13 = QFont(); _f13.setPointSizeF(9.75)
        self._m67_lbl.setFont(_f13)
        self.m67_entry = self._entry("0-3", "0")
        self.m67_entry.setFont(_f13)
        self.m67_entry.setFixedWidth(50)
        cmd_row.addWidget(self._m67_lbl)
        cmd_row.addWidget(self.m67_entry)
        cmd_row.addStretch()
        self._m67_lbl.setVisible(False)
        self.m67_entry.setVisible(False)
        self._lo.addLayout(cmd_row)
        def _on_cmd(i):
            self._m67_lbl.setVisible(i == 1)
            self.m67_entry.setVisible(i == 1)
        self.cmd_combo.currentIndexChanged.connect(_on_cmd)
        self._lo.addWidget(self._sep())
        self.firing_combo = self._combo(["M3/M5  (constant)", "M4/M5  (dynamic)"])
        self._lo.addLayout(self._row("firing_lbl", self.firing_combo))
        self._lo.addWidget(self._hint("firing_hint"))
        self._lo.addWidget(self._sep())
        self.ctrl_entry = self._entry("100 or 1000", "1000")
        self.ctrl_entry.setFixedWidth(90)
        self._lo.addLayout(self._row("ctrl_max_lbl", self.ctrl_entry))
        self._lo.addWidget(self._hint("ctrl_max_hint"))
        self._lo.addStretch()

    def get_values(self):
        cmd  = "S (Spindle)" if self.cmd_combo.currentIndex() == 0 else "M67 (Analog)"
        fire = "M3/M5" if self.firing_combo.currentIndex() == 0 else "M4/M5"
        try:    m67  = int(self.m67_entry.text())
        except ValueError: m67 = 0
        try:    ctrl = int(self.ctrl_entry.text())
        except ValueError: ctrl = 1000
        return {"cmd_mode": cmd, "firing_mode": fire, "m67_e_num": m67, "ctrl_max": ctrl}


# ── Step 3a : Settings ────────────────────────────────────────────

class _Step3Settings(_StepBase):
    # highlight_names expose les cibles pour le dashboard
    highlight_names = ['onboarding_area', 'settings_card', 'settings_topbar_btn']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        self._lo.addWidget(self._title("step3_title"))
        self._lo.addWidget(self._body("step3_body"))
        self._lo.addSpacing(4)
        col = colors.get("text_secondary", "#aaaaaa")
        col_accent = "#1F6AA5"
        for k in ("ptr_settings_topbar", "ptr_settings_card"):
            row = QHBoxLayout()
            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(
                "background: #ffffff; border-radius: 3px; border: none;")
            lbl = QLabel(t.get(k, k))
            lbl.setStyleSheet(
                "color: " + col + "; border: none; background: transparent;")
            row.addWidget(dot)
            row.addSpacing(8)
            row.addWidget(lbl, 1)
            self._lo.addLayout(row)
        self._lo.addStretch()


# ── Step 3b : Calibration ─────────────────────────────────────────

class _Step3Calib(_StepBase):
    highlight_names = ['onboarding_area', 'calibration_card']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        self._lo.addWidget(self._title("ptr_calib_title"
                           if "ptr_calib_title" in t else "step3_title"))
        self._lo.addSpacing(4)
        col = colors.get("text_secondary", "#aaaaaa")
        col_accent = "#FF9500"
        b2 = QLabel(t.get("ptr_calib_body", ""))
        b2.setStyleSheet(
            "color: " + col + "; border: none; background: transparent;")
        b2.setWordWrap(True)
        self._lo.addWidget(b2)
        row = QHBoxLayout()
        dot = QFrame()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(
            "background: #ffffff; border-radius: 3px; border: none;")
        b3 = QLabel(t.get("ptr_calib_card", ""))
        b3.setStyleSheet(
            "color: " + col + "; border: none; background: transparent;")
        row.addWidget(dot)
        row.addSpacing(8)
        row.addWidget(b3, 1)
        self._lo.addLayout(row)
        self._lo.addStretch()


# ── Step 4 : Modes ────────────────────────────────────────────────

# ── Step 3c : Home & Github ─────────────────────────────────────

class _StepHome(_StepBase):
    highlight_names = ['onboarding_area', 'home_btn', 'github_btn']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        self._lo.addWidget(self._title("step_home_title"))
        self._lo.addWidget(self._body("step_home_body"))
        self._lo.addSpacing(8)
        col = colors.get("text_secondary", "#aaaaaa")
        for k in ("ptr_home_desc", "ptr_github_desc"):
            row = QHBoxLayout()
            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet("background: #ffffff; border-radius: 3px; border: none;")
            lbl = QLabel(t.get(k, k))
            lbl.setStyleSheet(
                "color: " + col + "; border: none; background: transparent;")
            lbl.setWordWrap(True)
            row.addWidget(dot)
            row.addSpacing(8)
            row.addWidget(lbl, 1)
            self._lo.addLayout(row)
        self._lo.addStretch()


# ── Step 4 : G-Code Checker ─────────────────────────────────────

class _StepChecker(_StepBase):
    highlight_names = ['onboarding_area', 'parser_card']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        self._lo.addWidget(self._title("step_checker_title"))
        self._lo.addSpacing(4)
        self._lo.addWidget(self._body("step_checker_body"))
        self._lo.addSpacing(8)
        col = colors.get("text_secondary", "#aaaaaa")
        row = QHBoxLayout()
        dot = QFrame()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet("background: #ffffff; border-radius: 3px; border: none;")
        lbl = QLabel(t.get("step_checker_card", ""))
        lbl.setStyleSheet(
            "color: " + col + "; border: none; background: transparent;")
        row.addWidget(dot)
        row.addSpacing(8)
        row.addWidget(lbl, 1)
        self._lo.addLayout(row)
        self._lo.addStretch()


# ── Step 5 : Modes ───────────────────────────────────────────────

class _Step4Modes(_StepBase):
    highlight_names = ['onboarding_area', 'modes_column']

    def __init__(self, t, colors, parent=None):
        super().__init__(t, colors, parent)
        self._lo.addWidget(self._title("step4_title"))
        self._lo.addWidget(self._body("step4_body"))
        for key, color, enabled in [
            ("mode_raster", "#1F6AA5", True),
            ("mode_dither", "#555555", False),
            ("mode_infill", "#555555", False),
        ]:
            row = QHBoxLayout()
            dot = QFrame()
            dot.setFixedSize(7, 7)
            dot.setStyleSheet(
                "background: " + ("#ffffff" if enabled else "#555555") + "; border-radius: 3px; border: none;")
            col = colors.get(
                "text" if enabled else "text_secondary",
                "#dddddd" if enabled else "#666666")
            lbl = QLabel(t.get(key, key))
            lbl.setStyleSheet(
                "color: " + col + ";"
                " border: none; background: transparent;")
            lbl.setWordWrap(True)
            row.addWidget(dot)
            row.addSpacing(6)
            row.addWidget(lbl, 1)
            self._lo.addLayout(row)
        self._lo.addSpacing(6)
        note = QLabel(t.get("finish_note", "All set — click Finish."))
        col_ok = colors.get("text_secondary", "#888888")
        note.setStyleSheet(
            "color: " + col_ok + ";"
            " border: none; background: transparent;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lo.addWidget(note)
        self._lo.addStretch()


# ═══════════════════════════════════════════════════════════════════
#  ONBOARDING WIDGET
# ═══════════════════════════════════════════════════════════════════

class OnboardingWidget(QWidget):
    finished          = pyqtSignal(dict)
    request_highlight = pyqtSignal(list)
    clear_highlight   = pyqtSignal()
    language_changed  = pyqtSignal(str)   # émet la langue choisie

    TOTAL = 7   # Welcome / Config / Settings / Calib / Home+Github / Checker / Modes

    def __init__(self, colors: dict, translations: dict = None,
                 current_lang: str = "English",
                 emit_initial_highlight: bool = True, parent=None):
        super().__init__(parent)
        self.colors       = colors
        self._step        = 0
        self._vals        = {}
        self.t            = translations or {}
        self._current_lang = current_lang
        self._emit_initial_highlight = emit_initial_highlight
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        self._steps = [
            _Step1Welcome(self.t, colors, current_lang=self._current_lang),   # 0
            _Step2Config(self.t, colors),    # 1
            _Step3Settings(self.t, colors),  # 2  -> highlight settings
            _Step3Calib(self.t, colors),     # 3  -> highlight calibration
            _StepHome(self.t, colors),       # 4  -> highlight home + github
            _StepChecker(self.t, colors),    # 5  -> highlight parser_card
            _Step4Modes(self.t, colors),     # 5  -> highlight modes_column
        ]
        for s in self._steps:
            self._stack.addWidget(s)
        root.addWidget(self._stack, 1)
        root.addWidget(self._build_dots())
        self._nav = self._build_nav()
        root.addWidget(self._nav)
        # Refresh UI sans émettre highlight — le premier highlight
        # sera déclenché par showEvent une fois la géométrie connue
        self._refresh(emit_highlight=False)

    # ── UI ────────────────────────────────────────────────────────

    def _build_dots(self):
        w = QWidget()
        w.setFixedHeight(20)
        w.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(20, 2, 20, 0)
        lo.setSpacing(6)
        self._dots = []
        for _ in range(self.TOTAL):
            d = QFrame()
            d.setFixedSize(7, 7)
            d.setStyleSheet("border-radius: 3px; background: #333333; border: none;")
            lo.addWidget(d)
            self._dots.append(d)
        lo.addStretch()
        return w

    def _build_nav(self):
        bar = QWidget()
        bar.setFixedHeight(46)
        bg = self.colors.get("bg_card_alt", "#222222")
        bar.setStyleSheet("background: " + bg + "; border-top: 1px solid #333333;")
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(16, 7, 16, 7)
        lo.setSpacing(8)
        col_sec = self.colors.get("text_secondary", "#888888")
        col_txt = self.colors.get("text",           "#dddddd")
        bg_e    = self.colors.get("bg_entry",       "#2b2b2b")

        self._btn_skip = QPushButton(self.t.get("btn_skip", "Skip"))
        self._btn_skip.setFixedHeight(30)
        self._btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_skip.setStyleSheet(
            "QPushButton { background: transparent; color: " + col_sec + ";"
            " border: 1px solid #444444; border-radius: 5px; padding: 0 12px; }"
            " QPushButton:hover { color: #dddddd; border-color: #666666; }")
        self._btn_skip.clicked.connect(self._on_skip)
        lo.addWidget(self._btn_skip)
        lo.addStretch()

        self._btn_prev = QPushButton(self.t.get("btn_prev", "Previous"))
        self._btn_prev.setFixedHeight(30)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.setStyleSheet(
            "QPushButton { background: " + bg_e + "; color: " + col_txt + ";"
            " border: 1px solid #555555; border-radius: 5px; padding: 0 14px; }"
            " QPushButton:hover { border-color: #888888; }")
        self._btn_prev.clicked.connect(self._on_prev)
        lo.addWidget(self._btn_prev)

        self._btn_next = QPushButton(self.t.get("btn_next", "Next"))
        self._btn_next.setFixedHeight(30)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.setStyleSheet(
            "QPushButton { background: #1F6AA5; color: white;"
            " border: none; border-radius: 5px; padding: 0 16px;"
            " font-weight: 700; }"
            " QPushButton:hover { background: #2a7fc5; }")
        self._btn_next.clicked.connect(self._on_next)
        lo.addWidget(self._btn_next)
        return bar

    # ── Refresh ───────────────────────────────────────────────────

    def _refresh(self, emit_highlight=True):
        brd = self.colors.get("border", "#333333")
        for i, d in enumerate(self._dots):
            if i < self._step:
                d.setStyleSheet("border-radius: 3px; background: #1F6AA5; border: none;")
            elif i == self._step:
                d.setStyleSheet("border-radius: 3px; background: #FF9500; border: none;")
            else:
                d.setStyleSheet("border-radius: 3px; background: " + brd + "; border: none;")

        self._btn_prev.setVisible(self._step > 0)

        is_last = self._step == self.TOTAL - 1
        lbl = self.t.get("btn_finish", "Finish") if is_last else self.t.get("btn_next", "Next")
        self._btn_next.setText(lbl)
        if is_last:
            self._btn_next.setStyleSheet(
                "QPushButton { background: #27ae60; color: white;"
                " border: none; border-radius: 5px; padding: 0 16px;"
                " font-weight: 700; }"
                " QPushButton:hover { background: #2ecc71; }")
        else:
            self._btn_next.setStyleSheet(
                "QPushButton { background: #1F6AA5; color: white;"
                " border: none; border-radius: 5px; padding: 0 16px;"
                " font-weight: 700; }"
                " QPushButton:hover { background: #2a7fc5; }")

        # L'émission du highlight est déléguée à _emit_highlight
        if emit_highlight:
            self._emit_highlight()

    def _emit_highlight(self):
        # Ne pas émettre si le widget n'est plus visible (onboarding terminé)
        if not self.isVisible():
            return
        current_step = self._steps[self._step]
        names = getattr(current_step, 'highlight_names', [])
        if names:
            self.request_highlight.emit(names)
        else:
            self.clear_highlight.emit()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._emit_initial_highlight:
            return
        # La fenêtre peut être maximisée au démarrage — la géométrie
        # est instable pendant quelques cycles d'événements.
        # On surveille la stabilité via _wait_geometry_stable.
        self._geom_attempts = 0
        self._last_win_size = None
        from PyQt6.QtCore import QTimer
        self._geom_timer = QTimer(self)
        self._geom_timer.timeout.connect(self._wait_geometry_stable)
        self._geom_timer.start(60)   # vérifie toutes les 60 ms

    def _wait_geometry_stable(self):
        """Émet le highlight une fois la taille de la fenêtre principale stable."""
        win = self.window()
        current_size = win.size()
        self._geom_attempts += 1
        if current_size == self._last_win_size or self._geom_attempts >= 15:
            # Taille stable ou timeout (15 × 60 ms = 900 ms max)
            self._geom_timer.stop()
            self._emit_highlight()
        else:
            self._last_win_size = current_size

    # ── Navigation ────────────────────────────────────────────────

    def _stop_geom_timer(self):
        """Stoppe le timer de stabilité géométrique s'il tourne encore."""
        timer = getattr(self, '_geom_timer', None)
        if timer and timer.isActive():
            timer.stop()

    def _collect(self):
        if self._step == 1:
            self._vals = self._steps[1].get_values()

    def _on_next(self):
        self._collect()
        if self._step < self.TOTAL - 1:
            self._step += 1
            self._stack.setCurrentIndex(self._step)
            self._refresh()
        else:
            self._stop_geom_timer()
            self.clear_highlight.emit()
            self.finished.emit(self._vals)

    def _on_prev(self):
        if self._step > 0:
            self._step -= 1
            self._stack.setCurrentIndex(self._step)
            self._refresh()

    def _on_skip(self):
        self._stop_geom_timer()
        self._collect()
        self.clear_highlight.emit()
        self.finished.emit(self._vals)

    # ── Theme ─────────────────────────────────────────────────────

    def apply_theme(self, colors):
        self.colors = colors
        bg = colors.get("bg_card_alt", "#222222")
        self._nav.setStyleSheet("background: " + bg + "; border-top: 1px solid #333333;")
