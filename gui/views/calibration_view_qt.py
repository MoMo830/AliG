import os
import tempfile
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout, QFrame, 
                             QLabel, QScrollArea, QStackedWidget, QPushButton, 
                             QLineEdit, QGridLayout, QButtonGroup, QFileDialog,
                             QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap

from utils.paths import SVG_ICONS, EXPLAIN_PNG
from core.themes import get_theme
from gui.switch import Switch
from core.translations import TRANSLATIONS
from gui.utils_qt import get_svg_pixmap
from engine.calibrate_engine import CalibrateEngine



class CalibrationView(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.translation_map = {}
        self.test_cards = []
        self.current_test_id = None
        self.calibrate_engine = CalibrateEngine()
        self._last_calc_ms   = None

        # Couleurs thème — dark par défaut, mis à jour par apply_theme
        self._theme_colors = get_theme('Dark')
        
        # 1. Chargement initial des textes
        self.load_texts()
        
        # 2. Layout principal
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 20)
        self.main_layout.setSpacing(20)

        # --- Sidebar & Colonne de droite ---
        self.setup_sidebar()
        
        self.right_column = QFrame()
        self.right_column.setObjectName("RightColumn")
        self.right_column.setStyleSheet("QFrame#RightColumn { background-color: #202020; border-radius: 15px; }")
        self.right_layout = QVBoxLayout(self.right_column)
        self.main_layout.addWidget(self.right_column, stretch=1)

        self.setup_detail_header()
        
        self.dynamic_params_widget = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_params_widget)
        self.right_layout.addWidget(self.dynamic_params_widget)
        self.action_btn = None  # créé dynamiquement par chaque setup_*_params

    # ══════════════════════════════════════════════════════════════
    #  THEME
    # ══════════════════════════════════════════════════════════════

    def _c(self, dark_val, light_val):
        # Conservé pour compatibilité — préférer colors['key'] directement
        return dark_val if self._theme_colors.get('suffix', '_DARK') == '_DARK' else light_val

    def _container_style(self):
        c = self._theme_colors
        return (
            f"QFrame#ParamsContainer{{background-color:{c['bg_card_alt']};border-radius:10px;padding:8px;}}"
            f"QLabel{{color:{c['text']};font-size:13px;}}"
            f"QLineEdit{{background-color:{c['bg_entry_alt']};border:1px solid {c['border_light']};"
            f"border-radius:4px;color:{c['text']};padding:5px;}}"
        )

    def _calc_style(self):
        c = self._theme_colors
        return (
            f"QFrame#CalcContainer{{background-color:{c['bg_card_alt']};border-radius:10px;padding:15px;}}"
            f"QLabel{{color:{c['text']};font-size:13px;}}"
            f"QLineEdit{{background-color:{c['bg_entry_alt']};border:1px solid {c['border_light']};"
            f"border-radius:4px;color:{c['text']};padding:5px;}}"
        )

    def _select_style(self):
        c = self._theme_colors
        return (
            f"QFrame#SelectContainer{{background-color:{c['bg_select']};"
            f"border-radius:10px;padding:12px;margin-top:8px;}}"
        )

    def _btn_style_step(self):
        c = self._theme_colors
        return (
            f"QPushButton{{background:{c['bg_card']};color:{c['text_secondary']};font-size:10px;"
            f"border:1px solid {c['border_strong']};border-radius:6px;text-align:left;"
            f"padding-top:2px;padding-bottom:5px;}}"
            f"QPushButton:hover{{background:#1f538d;border-color:#3a8fd4;color:white;}}"
        )

    def apply_theme(self, colors: dict):
        self._theme_colors = colors
        text     = colors['text']
        text_sec = colors['text_secondary']
        bg_right = colors['bg_scroll']
        card_bg  = colors['bg_card_alt']
        card_brd = colors['border_card']
        card_hov = colors['hover_card_alt']

        # ── Colonne droite ────────────────────────────────────────
        if hasattr(self, 'right_column'):
            self.right_column.setStyleSheet(
                f"QFrame#RightColumn{{background-color:{bg_right};border-radius:15px;}}")

        # ── Titre sidebar ─────────────────────────────────────────
        if hasattr(self, 'sidebar_title_label'):
            self.sidebar_title_label.setStyleSheet(
                "font-size:18px;font-weight:bold;color:#e67e22;")

        # ── Cartes test ───────────────────────────────────────────
        checked_bg = colors['bg_card']
        for card in self.test_cards:
            card._bg_normal = card_bg
            card._bg_hover  = card_hov
            card._bd_normal = card_brd
            card._bd_hover  = '#e67e22'
            # Appliquer le style en respectant l'état checked courant
            card.setStyleSheet(
                f"QPushButton{{background-color:{card_bg};border:1px solid {card_brd};"
                f"border-radius:8px;text-align:left;padding:10px;}}"
                f"QPushButton:checked{{background-color:{checked_bg};border:2px solid #e67e22;}}"
            )
            title_lbl = card.findChild(QLabel, "card_title")
            desc_lbl  = card.findChild(QLabel, "card_desc")
            if title_lbl:
                title_lbl.setStyleSheet(
                    f"font-weight:bold;font-size:13px;color:{text};"
                    "border:none;background:transparent;")
            if desc_lbl:
                desc_lbl.setStyleSheet(
                    f"font-size:11px;color:{text_sec};"
                    "border:none;background:transparent;")

        # ── Titre et description détail ───────────────────────────
        if hasattr(self, 'detail_title'):
            self.detail_title.setStyleSheet(
                "font-size:20px;font-weight:bold;color:#e67e22;")
        if hasattr(self, 'detail_desc'):
            self.detail_desc.setStyleSheet(f"font-size:13px;color:{text};line-height:1.4;")

        # ── Bouton action ─────────────────────────────────────────
        if hasattr(self, 'action_btn') and self.action_btn and getattr(self, 'current_test_id', None) != 'overscan':
            self.action_btn.setStyleSheet(
                "background-color:#e67e22;font-weight:bold;border-radius:10px;color:white;")

        # ── Icônes des cartes (latency/linestep) selon thème ─────────
        color_main   = colors['text']
        color_active = "#e67e22"
        current_id   = getattr(self, 'current_test_id', None)
        for card in getattr(self, 'test_cards', []):
            t_id      = card.property("test_id")
            test_meta = next((t for t in self.tests_data if t["id"] == t_id), {})
            if not test_meta.get("fixed", False):
                is_selected        = (t_id == current_id)
                current_icon_color = color_active if is_selected else color_main
                icon_path          = test_meta.get("icon")   # clé correcte
                if icon_path and os.path.exists(icon_path):
                    pix = get_svg_pixmap(icon_path, size=QSize(35, 35), color_hex=current_icon_color)
                    if pix and not pix.isNull():
                        card.setIcon(QIcon(pix))

        # ── Widgets dynamiques (si déjà créés) ────────────────────
        self._restyle_dynamic()

    def _restyle_dynamic(self):
        """Restyles les containers dynamiques s'ils existent."""
        for w in self.findChildren(QFrame):
            if w.objectName() == "ParamsContainer":
                w.setStyleSheet(self._container_style())
            elif w.objectName() == "CalcContainer":
                w.setStyleSheet(self._calc_style())
            elif w.objectName() == "SelectContainer":
                w.setStyleSheet(self._select_style())

        c = self._theme_colors
        entry_s = (f"QLineEdit{{background:{c['bg_entry_alt']};border:1px solid {c['border_light']};"
                   f"border-radius:4px;color:{c['text']};padding:5px;}}")
        for w in self.dynamic_params_widget.findChildren(QLineEdit):
            w.setStyleSheet(entry_s)

        for w in self.dynamic_params_widget.findChildren(QComboBox):
            w.setStyleSheet(self._combo_style())

        step_s = self._btn_style_step()
        for btn in getattr(self, '_step_buttons', []):
            btn.setStyleSheet(step_s)
            for lbl in btn.findChildren(QLabel):
                lbl.setStyleSheet(
                    f"color:{c['text_secondary']};font-size:10px;border:none;background:transparent;")

    # ══════════════════════════════════════════════════════════════

    def load_texts(self):
        """Met à jour les dictionnaires de textes depuis le controller"""
        if hasattr(self.controller, 'translations'):
            current_repo = self.controller.translations
        else:
            lang = self.controller.get_item("machine_settings", "language", "English")
            from core.translations import TRANSLATIONS
            current_repo = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
            
        self.texts = current_repo.get("calibration", {})
        self.common_texts = current_repo.get("common", {})

    def setup_sidebar(self):
        """Crée la liste des tests à gauche."""
        sidebar_container = QVBoxLayout()
        
        # MODIFICATION ICI : on utilise self.sidebar_title_label au lieu de title
        self.sidebar_title_label = QLabel(self.texts.get("sidebar_title", "Tests"))
        self.sidebar_title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e67e22;")
        sidebar_container.addWidget(self.sidebar_title_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(420)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.scroll_area.setWidget(self.scroll_content)
        sidebar_container.addWidget(self.scroll_area)
        self.main_layout.addLayout(sidebar_container)

        self.add_test_cards()


    def add_test_cards(self):
        """Définit et ajoute les cartes de test à la sidebar"""
        # 1. On vide la liste pour éviter les doublons en cas de rappel de la fonction
        self.test_cards = [] 
        
        # 2. Configuration des données de base
        self.tests_data = [
            {"id": "latency",  "icon": SVG_ICONS["LATENCY"],  "fixed": False},
            {"id": "linestep", "icon": SVG_ICONS["LINESTEP"], "fixed": False},
            {"id": "overscan", "icon": SVG_ICONS["OVERSCAN"],  "fixed": True},
            {"id": "power",    "icon": SVG_ICONS["POWER"],    "fixed": True}
        ]

        for data in self.tests_data:
            # 3. On prépare le dictionnaire complet pour create_test_card
            test_info = {
                "id": data["id"],
                "title": self.texts.get(f"{data['id']}_title", "Sans titre"),
                "desc": self.texts.get(f"{data['id']}_short", ""),
                "icon_path": data["icon"],
                "fixed_color": data["fixed"]
            }
            
            # 4. Création et stockage
            card = self.create_test_card(test_info)
            self.test_cards.append(card) 
            self.scroll_layout.addWidget(card)



    def create_test_card(self, test_info):
        """Crée un bouton stylisé pour la sidebar."""
        card = QPushButton()
        card.setCheckable(True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(80)

        test_id = test_info.get("id")
        card.setProperty("test_id", test_id)
        card._test_info = test_info

        if hasattr(self, 'button_group'):
            self.button_group.addButton(card)

        # ── Icône via QIcon — résiste aux state changes (checked/hover/repaint) ──
        icon_path     = test_info.get("icon_path")
        keep_original = test_info.get("fixed_color", False)
        if keep_original:
            target_color = None
        else:
            _theme = self.controller.get_item("machine_settings", "theme", "Dark")
            target_color = "#000000" if _theme == "Light" else "#EEEEEE"

        if icon_path and os.path.exists(icon_path):
            pix = get_svg_pixmap(icon_path, size=QSize(35, 35), color_hex=target_color)
            if not pix.isNull():
                card.setIcon(QIcon(pix))
                card.setIconSize(QSize(35, 35))

        # ── Textes dans un layout interne ───────────────────────────────────────
        card.setText("")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        layout.addSpacing(42)   # réserve la place de l'icône Qt (gérée nativement)

        text_container = QVBoxLayout()
        text_container.setSpacing(2)

        title = QLabel(test_info.get("title", ""))
        title.setObjectName("card_title")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: white; "
                            "border: none; background: transparent;")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        desc = QLabel(test_info.get("desc", ""))
        desc.setObjectName("card_desc")
        desc.setStyleSheet("font-size: 11px; color: #aaaaaa; "
                           "border: none; background: transparent;")
        desc.setWordWrap(True)
        desc.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_container.addWidget(title)
        text_container.addWidget(desc)
        layout.addLayout(text_container)

        # ── Style (sans :hover CSS) ─────────────────────────────────────────────
        card.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                text-align: left;
                padding: 10px;
            }
            QPushButton:checked {
                background-color: #3d3d3d;
                border: 2px solid #e67e22;
            }
        """)

        card._bg_normal = "#2b2b2b"
        card._bg_hover  = "#353535"
        card._bd_normal = "#3d3d3d"
        card._bd_hover  = "#e67e22"

        def _reset_style(c):
            """Remet le style normal ou checked selon l'état de la carte."""
            if c.isChecked():
                c.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c._bg_normal};
                        border: 1px solid {c._bd_normal};
                        border-radius: 8px; text-align: left; padding: 10px;
                    }}
                    QPushButton:checked {{
                        background-color: #3d3d3d; border: 2px solid #e67e22;
                    }}
                """)
            else:
                c.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c._bg_normal};
                        border: 1px solid {c._bd_normal};
                        border-radius: 8px; text-align: left; padding: 10px;
                    }}
                    QPushButton:checked {{
                        background-color: #3d3d3d; border: 2px solid #e67e22;
                    }}
                """)

        def _enter(e, c=card):
            # Remettre le style normal sur toutes les cartes non survolées
            for other in self.test_cards:
                if other is not c and not other.underMouse():
                    _reset_style(other)
            # Appliquer le hover uniquement si la carte n'est pas sélectionnée
            if not c.isChecked():
                c.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c._bg_hover};
                        border: 1px solid {c._bd_hover};
                        border-radius: 8px; text-align: left; padding: 10px;
                    }}
                    QPushButton:checked {{
                        background-color: #3d3d3d; border: 2px solid #e67e22;
                    }}
                """)

        def _leave(e, c=card):
            _reset_style(c)

        card.enterEvent = _enter
        card.leaveEvent = _leave
        card.clicked.connect(lambda: self.on_test_selected(test_info))
        return card
    
    def on_test_selected(self, test_info):
        """
        Gère la mise à jour de la vue détaillée lorsqu'un test est sélectionné.
        Adapte les couleurs et les images selon le thème (Dark/Light).
        """
        # --- 0. MISE À JOUR DE L'ÉTAT ---
        # Crucial pour que retranslate_ui sache quel test traduire
        self.current_test_id = test_info.get("id")

        # Récupération du thème actuel pour adapter les icônes
        theme = self.controller.get_item("machine_settings", "theme", "Dark")
        is_light = (theme == "Light")
        
        color_main = "#000000" if is_light else "#EEEEEE"
        color_active = "#e67e22"  # Orange pour le highlight
        theme_suffix = "_LIGHT" if is_light else "_DARK"

        # --- 1. TEXTES (Détails à droite) ---
        # Titre et description longue chargée depuis le dictionnaire de langue
        self.detail_title.setText(test_info.get("title", ""))
        self.detail_desc.setText(self.texts.get(f"{self.current_test_id}_long", ""))

        # --- 2. SIDEBAR (Icônes dynamiques) ---
        for card in self.test_cards:
            t_id = card.property("test_id")
            is_selected = (t_id == self.current_test_id)
            test_meta = next((t for t in self.tests_data if t["id"] == t_id), {})

            # Recoloriage via setIcon — ne provoque pas de repaint des enfants
            if not test_meta.get("fixed", False):
                current_icon_color = color_active if is_selected else color_main
                pix = get_svg_pixmap(
                    test_meta.get("icon"),
                    size=QSize(35, 35),
                    color_hex=current_icon_color
                )
                if pix and not pix.isNull():
                    card.setIcon(QIcon(pix))

        # --- 3. ILLUSTRATION (Preview PNG) ---
        if hasattr(self, 'preview_image_label'):
            img_key = f"{self.current_test_id.upper()}{theme_suffix}"
            explain_img_path = EXPLAIN_PNG.get(img_key)

            if explain_img_path and os.path.exists(explain_img_path):
                pixmap = QPixmap(explain_img_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        500, 250, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.preview_image_label.setPixmap(scaled_pixmap)
                else:
                    self.preview_image_label.clear()
            else:
                self.preview_image_label.clear()

        # --- 4. PARAMÈTRES DYNAMIQUES ---
        self.clear_dynamic_layout()

        if self.current_test_id == "latency":
            self.setup_latency_params()
            self._make_action_btn(
                self.texts.get("btn_generate", "Generate G-Code..."),
                self.validate_and_generate_latency)

        elif self.current_test_id == "linestep":
            self.setup_linestep_params()
            self._make_action_btn(
                self.texts.get("btn_generate", "Generate G-Code..."),
                self.validate_and_generate_linestep)

        elif self.current_test_id == "overscan":
            self.setup_overscan_params()
            # Pas de bouton generate pour l'overscan

        elif self.current_test_id == "power":
            self._make_action_btn(
                self.texts.get("btn_prepare", "Prepare"),
                lambda: None)

    def clear_dynamic_layout(self):
        """Supprime tous les widgets de la zone de paramètres dynamique"""
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.action_btn = None

    def _make_action_btn(self, label: str, callback) -> QPushButton:
        """Crée et ajoute un bouton action en bas du dynamic_layout."""
        btn = QPushButton(label)
        btn.setFixedHeight(52)
        btn.setStyleSheet(
            "background-color:#e67e22;font-weight:bold;border-radius:10px;color:white;")
        btn.clicked.connect(callback)
        self.dynamic_layout.addWidget(btn)
        self.action_btn = btn
        return btn

    def setup_detail_header(self):
        """Prépare la zone de texte en haut de la colonne de droite"""
        header_widget = QWidget()
        header_widget.setMaximumHeight(320)  # cap pour éviter mintrack trop grand
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)

        # Titre du test
        self.detail_title = QLabel(self.texts.get("default_title", "Select a test"))
        self.detail_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e67e22;")
        self.detail_title.setWordWrap(True)
        self.detail_title.setMaximumHeight(60)
        header_layout.addWidget(self.detail_title)

        # Description longue
        self.detail_desc = QLabel(self.texts.get("default_desc", ""))
        self.detail_desc.setStyleSheet("font-size: 13px; color: #DCE4EE; line-height: 1.4;")
        self.detail_desc.setWordWrap(True)
        self.detail_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.detail_desc.setMaximumHeight(100)
        header_layout.addWidget(self.detail_desc)

        # Image d'illustration
        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setFixedHeight(130)
        header_layout.addWidget(self.preview_image_label)

        self.right_layout.addWidget(header_widget)



    def setup_latency_params(self):
        """Construit les champs de saisie pour le test de Latence + calculatrice"""
        self.clear_dynamic_layout()

        # ── Conteneur paramètres ─────────────────────────────────────
        container = QFrame()
        container.setObjectName("ParamsContainer")
        container.setStyleSheet(self._container_style())
        grid = QGridLayout(container)
        grid.setSpacing(12)

        # Ligne 0 : Feedrate
        grid.addWidget(QLabel(self.texts.get("feedrate_calc", "Feedrate (mm/min):")), 0, 0)
        self.speed_entry = QLineEdit()
        self.speed_entry.setPlaceholderText("ex: 1000")
        current_speed = self.controller.get_item("machine_settings", "feedrate", "1000")
        self.speed_entry.setText(str(current_speed))
        grid.addWidget(self.speed_entry, 0, 1)

        # Ligne 0 col 2 : Latency
        grid.addWidget(QLabel(self.texts.get("latency_calc", "Latency (ms):")), 0, 2)
        self.latency_entry = QLineEdit()
        self.latency_entry.setPlaceholderText("ex: 0")
        current_lat = self.controller.get_item("machine_settings", "laser_latency", "0")
        self.latency_entry.setText(str(current_lat))
        grid.addWidget(self.latency_entry, 0, 3)

        # Ligne 0 col 4 : mm info (calculé dynamiquement)
        self.mm_info_label = QLabel("= 0.000 mm")
        self.mm_info_label.setStyleSheet("color: #1f538d; font-weight: bold; border: none;")
        grid.addWidget(self.mm_info_label, 0, 4)

        # Ligne 1 : Power
        grid.addWidget(QLabel(self.texts.get("power_pct", "Power (%):")), 1, 0)
        self.power_entry = QLineEdit()
        self.power_entry.setText("10")
        grid.addWidget(self.power_entry, 1, 1)

        self.dynamic_layout.addWidget(container)

        # ── Calculatrice ──────────────────────────────────────────────
        calc_frame = QFrame()
        calc_frame.setObjectName("CalcContainer")
        calc_frame.setStyleSheet(self._calc_style())
        calc_vbox = QVBoxLayout(calc_frame)
        calc_vbox.setSpacing(8)

        calc_title = QLabel(self.texts.get("latency_calculator", "Latency Calculator (from measurement):"))
        calc_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e67e22; border: none;")
        calc_vbox.addWidget(calc_title)

        calc_grid = QGridLayout()
        calc_grid.setSpacing(10)

        calc_grid.addWidget(QLabel(self.texts.get("measured_offset", "Measured Offset (mm):")), 0, 0)
        self.measured_mm_entry = QLineEdit()
        self.measured_mm_entry.setPlaceholderText("ex: 0.25")
        calc_grid.addWidget(self.measured_mm_entry, 0, 1)

        self.calc_result_label = QLabel(f"{self.texts.get('latency_results', 'Result:')} -- ms")
        self.calc_result_label.setStyleSheet("font-weight: bold; color: #e67e22; border: none;")
        calc_grid.addWidget(self.calc_result_label, 0, 2)

        save_lat_btn = QPushButton(self.texts.get("apply_save", "Apply & Save"))
        save_lat_btn.setFixedHeight(30)
        save_lat_btn.setStyleSheet("""
            QPushButton { background-color: #1f538d; color: white; border-radius: 6px;
                          font-size: 12px; border: none; padding: 0 10px; }
            QPushButton:hover { background-color: #2a6dbd; }
        """)
        save_lat_btn.clicked.connect(self.apply_calculated_latency)
        calc_grid.addWidget(save_lat_btn, 0, 3)

        self.calc_hint_label = QLabel("")
        self.calc_hint_label.setStyleSheet("font-size: 11px; font-style: italic; color: gray; border: none;")
        calc_grid.addWidget(self.calc_hint_label, 1, 0, 1, 4)

        calc_vbox.addLayout(calc_grid)
        self.dynamic_layout.addWidget(calc_frame)

        # ── Bindings ─────────────────────────────────────────────────
        self.measured_mm_entry.textChanged.connect(self.update_latency_calculation)
        self.speed_entry.textChanged.connect(lambda: (self.update_latency_calculation(), self.update_mm_display()))
        self.latency_entry.textChanged.connect(self.update_mm_display)

        self.dynamic_layout.addStretch()
        self.update_mm_display()

    def setup_linestep_params(self):
        """Construit les champs pour le test de résolution (LineStep)"""
        self.clear_dynamic_layout()

        # ── Conteneur paramètres ─────────────────────────────────────
        container = QFrame()
        container.setObjectName("ParamsContainer")
        container.setStyleSheet(self._container_style())
        grid = QGridLayout(container)
        grid.setSpacing(6)

        # Ligne 0 : Pas Minimum & Multiplicateur
        grid.addWidget(QLabel(self.texts.get("min_step", "Min. Machine Step (mm):")), 0, 0)
        self.min_step_entry = QLineEdit()
        self.min_step_entry.setPlaceholderText("ex: 0.05")
        current_step = self.controller.get_item("machine_settings", "min_step", "0.05")
        self.min_step_entry.setText(str(current_step))
        grid.addWidget(self.min_step_entry, 0, 1)

        grid.addWidget(QLabel(self.texts.get("multiplier", "Multiplier:")), 0, 2)
        self.multiplier_entry = QLineEdit()
        self.multiplier_entry.setText("2")
        grid.addWidget(self.multiplier_entry, 0, 3)

        # Ligne 1 : Mode de balayage & Feedrate
        grid.addWidget(QLabel(self.texts.get("scan_mode", "Scan Mode:")), 1, 0)
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItems(["Horizontal", "Vertical"])
        self.scan_mode_combo.setStyleSheet(self._combo_style())
        grid.addWidget(self.scan_mode_combo, 1, 1)

        grid.addWidget(QLabel(self.texts.get("feedrate", "Feedrate (mm/min):")), 1, 2)
        self.speed_entry = QLineEdit()
        current_speed = self.controller.get_item("machine_settings", "feedrate", "1000")
        self.speed_entry.setText(str(current_speed))
        grid.addWidget(self.speed_entry, 1, 3)

        # Ligne 2 : PUISSANCE (%) et LATENCE (ms)
        grid.addWidget(QLabel(self.texts.get("power_pct", "Power (%):")), 2, 0)
        self.power_entry = QLineEdit()
        self.power_entry.setText("10")
        grid.addWidget(self.power_entry, 2, 1)

        grid.addWidget(QLabel(self.texts.get("latency_calc", "Latency (ms):")), 2, 2)
        self.latency_entry = QLineEdit()
        # Récupération de la latence sauvegardée dans les paramètres machine
        current_lat = self.controller.get_item("machine_settings", "laser_latency", "0")
        self.latency_entry.setText(str(current_lat))
        grid.addWidget(self.latency_entry, 2, 3)


        self.dynamic_layout.addWidget(container)

        self.dynamic_layout.addStretch()

        # ── Zone de sélection du résultat — 5 boutons visuels ──────────
        select_frame = QFrame()
        select_frame.setObjectName("SelectContainer")
        select_frame.setStyleSheet(self._select_style())
        select_layout = QVBoxLayout(select_frame)
        select_layout.setSpacing(8)

        title_select = QLabel("Select the sharpest block and save:")
        title_select.setStyleSheet("font-weight: bold; color: #3498db; font-size: 12px;")
        select_layout.addWidget(title_select)

        # Rangée de 5 boutons visuels (un par bloc généré)
        self._step_btn_row = QHBoxLayout()
        self._step_btn_row.setSpacing(6)
        self._step_buttons = []   # liste pour pouvoir les recréer
        select_layout.addLayout(self._step_btn_row)

        self.multiplier_entry.textChanged.connect(self.update_step_buttons)
        self.min_step_entry.textChanged.connect(self.update_step_buttons)
        self.scan_mode_combo.currentIndexChanged.connect(self.update_step_buttons)
        self.update_step_buttons()   # premier rendu

        self.dynamic_layout.addWidget(select_frame)

    def update_step_buttons(self):
        """Recrée les 5 boutons visuels de sélection de line_step."""
        try:
            center = float(self.multiplier_entry.text().replace(',', '.'))
            min_s  = float(self.min_step_entry.text().replace(',', '.'))
        except ValueError:
            return

        mode = self.scan_mode_combo.currentText()
        is_vertical = "Vertical" in mode

        # 1. Nettoyage
        for btn in self._step_buttons:
            self._step_btn_row.removeWidget(btn)
            btn.deleteLater()
        self._step_buttons.clear()

        # 2. Logique de direction et d'ordre
        if not is_vertical:
            # Mode Horizontal : boutons l'un au dessus de l'autre
            self._step_btn_row.setDirection(QBoxLayout.Direction.TopToBottom)
            range_iterator = range(2, -3, -1) # Plus grand en haut, plus petit en bas
        else:
            # Mode Vertical : boutons côte à côte
            self._step_btn_row.setDirection(QBoxLayout.Direction.LeftToRight)
            range_iterator = range(-2, 3)

        for i in range_iterator:
            m = max(0.01, center + i * 0.5)
            step = round(m * min_s, 4)
            block_num = i + 3 
            
            btn = QPushButton()
            pix = self._make_step_icon(step, is_vertical, color="#3a8fd4")
            
            if not is_vertical:
                # --- MODE HORIZONTAL (Boutons empilés, Icône à gauche du texte) ---
                btn.setFixedSize(110, 40)
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(30, 30))
                btn.setText(f" {step:.4f} mm")
                btn.setStyleSheet(self._get_btn_style("left", padding_top="0px"))
            else:
                # --- MODE VERTICAL (Icône EN HAUT, Texte EN BAS) ---
                btn.setFixedSize(75, 90)
                
                # On crée un layout interne au bouton pour forcer l'empilement
                layout = QVBoxLayout(btn)
                layout.setContentsMargins(2, 8, 2, 8)
                layout.setSpacing(4) # Espace entre le carré et le texte
                
                # 1. Label pour le carré (icône)
                icon_lbl = QLabel()
                icon_lbl.setPixmap(pix)
                icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Important : pour que le clic passe à travers le label vers le bouton
                icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                
                # 2. Label pour la valeur numérique
                text_lbl = QLabel(f"{step:.4f} mm")
                text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                text_lbl_col = self._c('#cccccc', '#333333')
                text_lbl.setStyleSheet(
                    f"color:{text_lbl_col};font-size:10px;"
                    "border:none;background:transparent;")
                text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                
                layout.addWidget(icon_lbl)
                layout.addWidget(text_lbl)
                
                # On applique le style au bouton vide
                btn.setStyleSheet(self._get_btn_style("center"))
                
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{'Col' if is_vertical else 'Blk'} {block_num} — {step:.4f} mm")

            def make_save(s):
                return lambda: self._save_linestep(s, is_vertical)

            btn.clicked.connect(make_save(step))
            self._step_btn_row.addWidget(btn)
            self._step_buttons.append(btn)

    @staticmethod
    def _arrow_svg_path(color: str) -> str:
        """Retourne le chemin vers un SVG de flèche recolorisé (tempfile)."""
        src = SVG_ICONS.get("ARROW_DOWN", "")
        if not src or not os.path.isfile(src):
            return src.replace("\\", "/")
        try:
            import re
            with open(src, "r", encoding="utf-8") as f:
                svg = f.read()
            svg = re.sub(r'fill\s*=\s*"[^"]*"',   f'fill="{color}"',   svg)
            svg = re.sub(r'fill\s*:\s*[^;}"]+',    f'fill:{color}',     svg)
            svg = re.sub(r'stroke\s*=\s*"[^"]*"',  f'stroke="{color}"', svg)
            svg = re.sub(r'stroke\s*:\s*[^;}"]+',  f'stroke:{color}',   svg)
            tmp = tempfile.NamedTemporaryFile(
                suffix=f'_arrow_{color.strip("#")}.svg',
                delete=False, mode='w', encoding='utf-8')
            tmp.write(svg); tmp.close()
            return tmp.name.replace("\\", "/")
        except Exception:
            return src.replace("\\", "/")

    def _combo_style(self):
        c = self._theme_colors
        arrow_path = self._arrow_svg_path(c['arrow_color'])
        return (
            f"QComboBox{{background-color:{c['bg_entry_alt']};border:1px solid {c['border_light']};"
            f"border-radius:5px;padding:3px 30px 3px 10px;color:{c['text']};}}"
            f"QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:top right;"
            f"width:25px;border:none;background:transparent;}}"
            f"QComboBox::down-arrow{{image:url({arrow_path});width:12px;height:8px;}}"
            f"QComboBox QAbstractItemView{{background-color:{c['bg_entry_alt']};color:{c['text']};"
            f"selection-background-color:{c['combo_selection']};border:1px solid {c['border_light']};}}"
        )

    def _get_btn_style(self, align, padding_top="2px"):
        """Génère le style CSS des boutons avec alignement et padding variables."""
        c = self._theme_colors
        return (
            f"QPushButton{{background:{c['bg_card']};color:{c['text_secondary']};font-size:10px;"
            f"border:1px solid {c['border_strong']};border-radius:6px;text-align:{align};"
            f"padding-top:{padding_top};padding-bottom:5px;}}"
            f"QPushButton:hover{{background:#1f538d;border-color:#3a8fd4;color:white;}}"
        )

    def _make_step_icon(self, step_mm, is_vertical, color="#3a8fd4"):
        """Génère une icône miniature représentant les lignes avec une couleur unique."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
        from PyQt6.QtCore import Qt
        
        w, h = 44, 38
        pix = QPixmap(w, h)
        # On peut mettre transparent ou garder le fond sombre
        pix.fill(QColor(self._theme_colors.get('bg_select', '#1a1a1a')))
        
        qp = QPainter(pix)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)

        # On utilise la couleur passée en argument (ou celle par défaut)
        # L'épaisseur 2 rend les traits plus lisibles
        pen = QPen(QColor(color), 2)
        qp.setPen(pen)

        # Dessiner 5 lignes avec l'espacement relatif
        n_lines = 5
        margin = 6
        
        if is_vertical:
            total_w = w - 2 * margin
            for k in range(n_lines):
                x = margin + int(k * total_w / (n_lines - 1))
                qp.drawLine(x, margin, x, h - margin)
        else:
            total_h = h - 2 * margin
            for k in range(n_lines):
                y = margin + int(k * total_h / (n_lines - 1))
                qp.drawLine(margin, y, w - margin, y)

        qp.end()
        return pix

    def _save_linestep(self, step_mm, is_vertical):
        """Sauvegarde la valeur dans hor_linestep ou ver_linestep."""
        try:
            # Détermination de la clé en fonction du mode
            key = "ver_linestep" if is_vertical else "hor_linestep"
            
            # Sauvegarde dans "machine_settings" comme demandé
            self.controller.set_item(
                "machine_settings", key, round(step_mm, 4)
            )
            self.controller.save()

            mode_str = "Vertical" if is_vertical else "Horizontal"
            QMessageBox.information(
                self, "Sauvegarde",
                f"Pas {mode_str} enregistré : {step_mm:.4f} mm\n(Clé: {key})"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de sauvegarde :\n{e}")


    # ── OVERSCAN ──────────────────────────────────────────────────────────

    def setup_overscan_params(self):
        """Calcule l'overscan minimal selon vitesse et accélération machine."""
        self.clear_dynamic_layout()

        # ── Champs d'entrée ───────────────────────────────────────────
        container = QFrame()
        container.setObjectName("ParamsContainer")
        container.setStyleSheet(self._container_style())
        grid = QGridLayout(container)
        grid.setSpacing(12)

        # Feedrate
        grid.addWidget(QLabel(self.texts.get("feedrate_calc", "Feedrate (mm/min):")), 0, 0)
        self.overscan_feed_entry = QLineEdit()
        self.overscan_feed_entry.setPlaceholderText("ex: 3000")
        current_feed = self.controller.get_item("machine_settings", "feedrate", "3000")
        self.overscan_feed_entry.setText(str(current_feed))
        grid.addWidget(self.overscan_feed_entry, 0, 1)

        # Accélération max
        grid.addWidget(QLabel(self.texts.get("max_accel", "Max Acceleration (mm/s²):")), 1, 0)
        self.overscan_accel_entry = QLineEdit()
        self.overscan_accel_entry.setPlaceholderText("ex: 500")
        self.overscan_accel_entry.setText("500")
        grid.addWidget(self.overscan_accel_entry, 1, 1)

        # Latence laser (pré-remplie depuis la config, peut être négative)
        grid.addWidget(QLabel(self.texts.get("latency_calc", "Latency (ms):")), 2, 0)
        self.overscan_lat_entry = QLineEdit()
        self.overscan_lat_entry.setPlaceholderText("ex: -11.5")
        current_lat = self.controller.get_item("machine_settings", "laser_latency", "0")
        self.overscan_lat_entry.setText(str(current_lat))
        grid.addWidget(self.overscan_lat_entry, 2, 1)

        self.dynamic_layout.addWidget(container)

        # ── Zone résultat ─────────────────────────────────────────────
        calc_frame = QFrame()
        calc_frame.setObjectName("CalcContainer")
        calc_frame.setStyleSheet(self._calc_style())
        calc_vbox = QVBoxLayout(calc_frame)
        calc_vbox.setSpacing(10)

        title_lbl = QLabel(self.texts.get("overscan_calculator", "Overscan Calculator:"))
        title_lbl.setStyleSheet("font-weight:bold;font-size:13px;color:#e67e22;border:none;")
        calc_vbox.addWidget(title_lbl)

        # TODO : ajouter le SVG explicatif ici quand disponible
        # svg_lbl = QLabel()
        # svg_lbl.setPixmap(get_svg_pixmap(SVG_ICONS["OVERSCAN"], QSize(300, 120)))
        # calc_vbox.addWidget(svg_lbl)

        formula_lbl = QLabel(self.texts.get("overscan_formula", "Formula: overscan = v² / (2 × a)"))
        formula_lbl.setStyleSheet("font-size:11px;font-style:italic;color:#888;border:none;")
        calc_vbox.addWidget(formula_lbl)

        # Résultat
        res_row = QHBoxLayout()
        res_lbl = QLabel(self.texts.get("overscan_result", "Recommended overscan:"))
        res_lbl.setStyleSheet("font-size:13px;border:none;")
        self.overscan_result_label = QLabel("-- mm")
        self.overscan_result_label.setStyleSheet(
            "font-weight:bold;font-size:16px;color:#2ecc71;border:none;")
        res_row.addWidget(res_lbl)
        res_row.addStretch()
        res_row.addWidget(self.overscan_result_label)
        calc_vbox.addLayout(res_row)

        # Premove actuel
        current_premove = self.controller.get_item("machine_settings", "premove", "10.0")
        self.overscan_current_lbl = QLabel(
            f"{self.texts.get('overscan_current', 'Current premove:')} {current_premove} mm")
        self.overscan_current_lbl.setStyleSheet("font-size:11px;color:#888;border:none;")
        calc_vbox.addWidget(self.overscan_current_lbl)

        # Bouton Sauvegarder (caché jusqu'au premier calcul valide)
        self.overscan_save_btn = QPushButton(
            self.texts.get("overscan_save_btn", "Save as Premove"))
        self.overscan_save_btn.setFixedHeight(34)
        self.overscan_save_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; border-radius: 6px;
                          font-size: 12px; border: none; padding: 0 10px; }
            QPushButton:hover { background-color: #1e8449; }
        """)
        self.overscan_save_btn.hide()
        self.overscan_save_btn.clicked.connect(self._save_overscan)
        calc_vbox.addWidget(self.overscan_save_btn)

        self.dynamic_layout.addWidget(calc_frame)
        self.dynamic_layout.addStretch()

        # Recalcul automatique à la saisie
        self.overscan_feed_entry.textChanged.connect(self._calc_overscan)
        self.overscan_accel_entry.textChanged.connect(self._calc_overscan)
        self.overscan_lat_entry.textChanged.connect(self._calc_overscan)
        self._calc_overscan()   # calcul initial avec les valeurs pré-remplies

    def _calc_overscan(self):
        """Calcule overscan = (v²/(2a) + |latency_mm|) × 1.2"""
        try:
            feed_mm_min = float(
                self.overscan_feed_entry.text().strip().replace(',', '.'))
            accel_mm_s2 = float(
                self.overscan_accel_entry.text().strip().replace(',', '.'))
            if accel_mm_s2 <= 0:
                raise ValueError("Accel must be > 0")
            # Latence : optionnelle, 0 si vide ou invalide
            try:
                lat_ms = float(
                    self.overscan_lat_entry.text().strip().replace(',', '.'))
            except (ValueError, AttributeError):
                lat_ms = 0.0

            v_mm_s = feed_mm_min / 60.0
            accel_mm   = (v_mm_s ** 2) / (2.0 * accel_mm_s2)
            lat_mm     = abs(lat_ms) * v_mm_s / 1000.0
            raw_mm     = accel_mm + lat_mm
            # +20% de marge de sécurité
            overscan_mm = round(raw_mm * 1.2 + 0.05, 1)
            self._last_overscan_mm = overscan_mm
            self.overscan_result_label.setText(f"{overscan_mm:.1f} mm")
            self.overscan_result_label.setStyleSheet(
                "font-weight:bold;font-size:16px;color:#2ecc71;border:none;")
            self.overscan_save_btn.show()
        except (ValueError, AttributeError):
            self._last_overscan_mm = None
            if hasattr(self, 'overscan_result_label'):
                self.overscan_result_label.setText("-- mm")
                self.overscan_result_label.setStyleSheet(
                    "font-weight:bold;font-size:16px;color:#888;border:none;")
            if hasattr(self, 'overscan_save_btn'):
                self.overscan_save_btn.hide()

    def _save_overscan(self):
        """Sauvegarde la valeur calculée dans machine_settings.premove."""
        val = getattr(self, '_last_overscan_mm', None)
        if val is None:
            return
        try:
            self.controller.set_item("machine_settings", "premove", round(val, 1))
            self.controller.save()
            # Mettre à jour le label "premove actuel"
            if hasattr(self, 'overscan_current_lbl'):
                self.overscan_current_lbl.setText(
                    f"{self.texts.get('overscan_current', 'Current premove:')} {val:.1f} mm")
            # Feedback visuel temporaire sur le bouton
            orig_text  = self.overscan_save_btn.text()
            orig_style = self.overscan_save_btn.styleSheet()
            saved_text = "✅ " + self.texts.get("overscan_saved", "Saved!")
            self.overscan_save_btn.setText(saved_text)
            self.overscan_save_btn.setStyleSheet("""
                QPushButton { background-color: #1e8449; color: white; border-radius: 6px;
                              font-size: 12px; border: none; padding: 0 10px; }
            """)
            QTimer.singleShot(2000, lambda: (
                self.overscan_save_btn.setText(orig_text),
                self.overscan_save_btn.setStyleSheet(orig_style)
            ))
        except Exception as e:
            QMessageBox.critical(
                self, self.texts.get("error_title", "Error"), str(e))

    # ── FIN OVERSCAN ───────────────────────────────────────────────────────

    def update_mm_display(self):
        """Calcule et affiche le décalage en mm depuis speed + latency."""
        try:
            speed   = float(self.speed_entry.text().strip()   or 0)
            latency = float(self.latency_entry.text().strip()  or 0)
            offset  = (speed * latency) / 60000.0
            self.mm_info_label.setText(f"= {offset:.3f} mm")
            color = "#e74c3c" if abs(offset) > 2.0 else "#1f538d"
            self.mm_info_label.setStyleSheet(f"color: {color}; font-weight: bold; border: none;")
        except (ValueError, AttributeError):
            if hasattr(self, 'mm_info_label'):
                self.mm_info_label.setText("= --- mm")
                self.mm_info_label.setStyleSheet("color: gray; font-weight: bold; border: none;")

    def update_latency_calculation(self):
        """Calcule la latence depuis offset mesuré + vitesse."""
        try:
            speed   = float(self.speed_entry.text().strip()      or 0)
            dist_mm = float(self.measured_mm_entry.text().strip() or 0)

            if speed > 0 and dist_mm != 0:
                calc_ms = (dist_mm * 60000.0) / speed
                self._last_calc_ms = calc_ms
                if dist_mm > 0:
                    status = f"(+) {calc_ms:.2f} ms"
                    hint   = self.texts.get("latency_hint_late", "Late firing: Increase latency (+)")
                    color  = "#e67e22"
                else:
                    status = f"(-) {abs(calc_ms):.2f} ms"
                    hint   = self.texts.get("latency_hint_early", "Early firing: Decrease latency (-)")
                    color  = "#3498db"
                self.calc_result_label.setText(f"{self.texts.get('latency_results', 'Result:')} {status}")
                self.calc_result_label.setStyleSheet(f"font-weight: bold; color: {color}; border: none;")
                self.calc_hint_label.setText(f"ℹ️ {hint}")
            elif dist_mm == 0:
                self._last_calc_ms = 0.0
                self.calc_result_label.setText(f"{self.texts.get('latency_results', 'Result:')} 0.00 ms")
                self.calc_result_label.setStyleSheet("font-weight: bold; color: gray; border: none;")
                self.calc_hint_label.setText(self.texts.get("latency_perfect", "Perfectly aligned"))
            else:
                self.calc_result_label.setText(f"{self.texts.get('latency_results', 'Result:')} -- ms")
                self.calc_result_label.setStyleSheet("font-weight: bold; color: gray; border: none;")
                self.calc_hint_label.setText("")
        except (ValueError, AttributeError):
            if hasattr(self, 'calc_result_label'):
                self.calc_result_label.setText("Result: Error")
                self.calc_result_label.setStyleSheet("font-weight: bold; color: #e74c3c; border: none;")

    def apply_calculated_latency(self):
        """Injecte la valeur calculée dans le champ latency et sauvegarde."""
        val_ms = getattr(self, "_last_calc_ms", None)
        if val_ms is not None:
            self.latency_entry.setText(f"{val_ms:.2f}")
            self.update_mm_display()
            # On utilise la même API que settings_view_qt pour être sûr
            # d'écrire dans la même couche (set_section + save)
            try:
                current = self.controller.get_section("machine_settings") or {}
                current["laser_latency"] = round(val_ms, 3)
                self.controller.set_section("machine_settings", current)
                self.controller.save()
            except Exception as e:
                print(f"[calibration] save laser_latency failed: {e}")

    def validate_and_generate_latency(self):
        """Valide les champs, génère le G-Code de test de latence et propose l'enregistrement."""
        power_raw = self.power_entry.text().strip() if hasattr(self, 'power_entry') else ""
        if not power_raw:
            QMessageBox.warning(self, "Missing field", "⚠️ Please enter a power value.")
            return
        try:
            cfg          = self.controller.config_manager if hasattr(self.controller, 'config_manager') else None
            cmd_mode     = cfg.get_item("machine_settings", "cmd_mode", "") if cfg else ""
            use_s_mode   = "S (" in cmd_mode

            settings = {
                "power":     float(self.power_entry.text().strip()),
                "max_value": float(cfg.get_item("machine_settings", "ctrl_max", 255)) if cfg else 255,
                "feedrate":  float(self.speed_entry.text().strip()),
                "latency":   float(self.latency_entry.text().strip() or 0),
                "e_num":     int(cfg.get_item("machine_settings", "m67_e_num", 0)) if cfg else 0,
                "use_s_mode": use_s_mode,
                "header":    cfg.get_item("gcode_options", "header", "") if cfg else "",
                "footer":    cfg.get_item("gcode_options", "footer", "M30") if cfg else "M30",
            }

            gcode_content = self.calibrate_engine.generate_latency_calibration(settings)

            lat_val = settings["latency"]
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.texts.get("save_dialog_title", "Save Calibration G-Code"),
                f"latency_test_{lat_val}ms.nc",
                "G-Code (*.nc *.gcode);;All files (*)"
            )
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(gcode_content)
                # Feedback visuel temporaire sur le bouton
                if self.action_btn:
                    orig_text = self.action_btn.text()
                    orig_style = self.action_btn.styleSheet()
                    self.action_btn.setText("✅ G-Code Saved!")
                    self.action_btn.setStyleSheet(
                        "background-color: #27AE60; font-weight: bold; border-radius: 10px;")
                    QTimer.singleShot(2000, lambda: (
                        self.action_btn.setText(orig_text),
                        self.action_btn.setStyleSheet(orig_style)
                    ))

        except ValueError:
            QMessageBox.warning(self, "Invalid input", "⚠️ Please enter valid numbers in all fields.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed:\n{e}")

    def validate_and_generate_linestep(self):
        """Valide les champs pour le LineStep et génère le G-Code multi-blocs."""
        if not self.power_entry.text().strip() or not self.min_step_entry.text().strip():
            QMessageBox.warning(self, "Missing field", "⚠️ Please enter Power and Minimum Step values.")
            return

        try:
            cfg = self.controller.config_manager if hasattr(self.controller, 'config_manager') else None
            cmd_mode = cfg.get_item("machine_settings", "cmd_mode", "") if cfg else ""
            use_s_mode = "S (" in cmd_mode

            # 2. Préparation des settings complets
            settings = {
                "power":        float(self.power_entry.text().strip()),
                "max_value":    float(cfg.get_item("machine_settings", "ctrl_max", 1000)) if cfg else 1000,
                "feedrate":     float(self.speed_entry.text().strip()),
                "min_step":     float(self.min_step_entry.text().strip().replace(',', '.')),
                "multiplier":   float(self.multiplier_entry.text().strip().replace(',', '.')),
                "latency":      float(self.latency_entry.text().strip().replace(',', '.') or 0),
                "scan_mode":    self.scan_mode_combo.currentText(),
                "e_num":        int(cfg.get_item("machine_settings", "m67_e_num", 0)) if cfg else 0,
                "use_s_mode":   use_s_mode,
                "firing_mode":  cfg.get_item("machine_settings", "firing_mode", "M3/M5") if cfg else "M3/M5",
            }

            # 3. Appel du moteur (Version GRID/Multi-blocs)
            gcode_content = self.calibrate_engine.generate_linestep_calibration(settings)

            # 4. Dialogue de sauvegarde
            mode_name = settings["scan_mode"].split()[0].lower()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save LineStep Test", f"linestep_grid_{mode_name}.nc", "G-Code (*.nc *.gcode)"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(gcode_content)
                
                # Feedback visuel
                if self.action_btn:
                    orig_text = self.action_btn.text()
                    orig_style = self.action_btn.styleSheet()
                    self.action_btn.setText("Grid Test Saved!")
                    self.action_btn.setStyleSheet("background-color: #27AE60; font-weight: bold; border-radius: 10px; color: white;")
                    QTimer.singleShot(2000, lambda: (self.action_btn.setText(orig_text), self.action_btn.setStyleSheet(orig_style)))

        except ValueError:
            QMessageBox.warning(self, "Invalid input", "⚠️ Please enter valid numbers.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed:\n{e}")

    def create_switch(self, layout, label_text, key, row):
        """Ajoute une ligne avec un label et Switch animé"""
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 5, 0, 5)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 14px; color: #DCE4EE;")
        

        switch_btn = Switch()
        
        # Si tu as besoin de régler l'état initial depuis la config
        initial_state = self.config_manager.get_item("calibration", key, False)
        switch_btn.setChecked(initial_state)

        # Connexion au signal (ton switch émet 'toggled' comme une QCheckBox)
        switch_btn.toggled.connect(lambda checked: self.on_switch_changed(key, checked))

        h_layout.addWidget(label)
        h_layout.addStretch() # Pousse le switch vers la droite
        h_layout.addWidget(switch_btn)
        
        # On l'ajoute à la grille de la zone dynamique
        layout.addWidget(container, row, 0, 1, 2) # Prend 2 colonnes
        
        # On stocke la référence pour pouvoir lire la valeur plus tard
        self.controls[key] = {"switch": switch_btn}


    def _apply_language(self, lang: str, translations: dict):
        """Appelée par update_ui_language de main_window avec lang et translations déjà à jour."""
        from core.translations import TRANSLATIONS as _TR
        repo = translations if translations else _TR.get(lang, _TR["English"])
        self.texts       = repo.get("calibration", {})
        self.common_texts = repo.get("common", {})
        # Déléguer la mise à jour des widgets à retranslate_ui
        # (sans rappeler load_texts qui relirait la config)
        self._retranslate_widgets()

    def retranslate_ui(self):
        """Appelée lors d'un changement de langue — recharge les textes puis met à jour les widgets."""
        self.load_texts()
        self._retranslate_widgets()

    def _retranslate_widgets(self):
        """Met à jour tous les widgets avec self.texts déjà chargé."""
        if hasattr(self, 'sidebar_title_label'):
            self.sidebar_title_label.setText(self.texts.get("sidebar_title", "Tests"))
        
        if hasattr(self, 'action_btn') and self.action_btn:
            self.action_btn.setText(self.texts.get("btn_prepare", "Prepare"))
        
        # 3. Mise à jour des cartes de test dans la sidebar
        for card in self.test_cards:
            # Récupération de l'ID stocké via setProperty
            t_id = card.property("test_id")
            
            # Recherche des labels enfants par leur ObjectName
            title_label = card.findChild(QLabel, "card_title")
            desc_label = card.findChild(QLabel, "card_desc")
            
            if title_label: 
                title_label.setText(self.texts.get(f"{t_id}_title", "Sans titre"))
            if desc_label: 
                desc_label.setText(self.texts.get(f"{t_id}_short", ""))

        # 4. Rafraîchissement de la zone de détails (partie droite)
        if self.current_test_id:
            # Traduction du titre et de la description longue
            self.detail_title.setText(self.texts.get(f"{self.current_test_id}_title", ""))
            self.detail_desc.setText(self.texts.get(f"{self.current_test_id}_long", ""))

            # Relancer on_test_selected pour reconstruire params + bouton traduit
            test_info = next((t for t in self.tests_data if t["id"] == self.current_test_id), {})
            if test_info:
                self.on_test_selected(test_info)
        else:
            # Retour à l'état par défaut si aucun test n'est sélectionné
            self.detail_title.setText(self.texts.get("default_title", "Select a test"))
            self.detail_desc.setText(self.texts.get("default_desc", ""))

    def reset_view(self):
        """Remet la vue à zéro"""
        self.current_test_id = None
        
        # Décocher les boutons
        self.button_group.setExclusive(False)
        for card in self.test_cards:
            card.setChecked(False)
        self.button_group.setExclusive(True)
        
        # Remettre l'en-tête par défaut
        self.detail_title.setText(self.texts.get("default_title", "Select a test"))
        self.detail_desc.setText(self.texts.get("default_desc", ""))
        self.preview_image_label.clear()
        
        # Vider les paramètres (détruit aussi le bouton action)
        self.clear_dynamic_layout()

    def showEvent(self, event):
        """
        Déclenché automatiquement par Qt chaque fois que 
        la vue de calibration devient visible.
        """
        super().showEvent(event) 
        self.reset_view()

    def get_txt(self, key, default=""):
        """Cherche d'abord dans calibration, puis dans common"""
        return self.texts.get(key, self.common_texts.get(key, default))

# # Utilisation ultra simple :
# self.btn_prepare.setText(self.get_txt("btn_prepare"))
# self.label_f.setText(self.get_txt("feedrate"))