from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QFrame, QLineEdit, 
                             QSlider, QComboBox, QTextEdit, QCheckBox,
                             QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox
import os
import shutil
import tempfile
from utils.paths import SVG_ICONS
from core.themes import get_theme
#from utils.paths import ARROW_DOWN, CIRCLE
from gui.switch import Switch


class SettingsViewQt(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.translation_map = {}
        
        # 1. Chargement des traductions
        if hasattr(self.controller, 'translations'):
            self.texts = self.controller.translations["settings"]
        else:
            from core.translations import TRANSLATIONS
            self.texts = TRANSLATIONS["English"]["settings"]

        self.controls = {}
        self._section_frames = []  # Références directes aux frames de section
        self.loading = True

        # Couleurs du thème — initialisées dark, mises à jour par apply_theme
        self._theme_colors = get_theme('Dark')

        # 2. Configuration du Layout Principal
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 3. Construction de l'interface graphique
        self.setup_header()       # Titre et bouton Save
        self.setup_scroll_area()  # Colonnes et widgets

        # 4. Chargement des données du ConfigManager
        self.load_settings()
        
        # 5. Fin de l'initialisation
        self.loading = False      # Autorise maintenant le mark_as_changed

    # ── Helpers de style (lisent _theme_colors) ──────────────────────────

    def _c(self, key, dark_val, light_val):
        # Conservé pour compatibilité — préférer colors['key'] directement
        return dark_val if self._theme_colors.get('suffix', '_DARK') == '_DARK' else light_val

    def _entry_style(self):
        c = self._theme_colors
        return (f"QLineEdit{{background-color:{c['bg_entry']};border:1px solid {c['border_strong']};"
                f"border-radius:4px;color:{c['text']};padding:3px;}}")

    @staticmethod
    def _arrow_svg_path(color: str) -> str:
        """Retourne le chemin vers un SVG de flèche recolorisé (tempfile)."""
        src = SVG_ICONS.get("ARROW_DOWN", "")
        if not src or not os.path.isfile(src):
            return src.replace("\\", "/")
        try:
            with open(src, "r", encoding="utf-8") as f:
                svg = f.read()
            import re
            svg = re.sub(r'fill\s*=\s*"[^"]*"',   f'fill="{color}"',   svg)
            svg = re.sub(r'fill\s*:\s*[^;}"]+',    f'fill:{color}',     svg)
            svg = re.sub(r'stroke\s*=\s*"[^"]*"',  f'stroke="{color}"', svg)
            svg = re.sub(r'stroke\s*:\s*[^;}"]+',  f'stroke:{color}',   svg)
            tmp = tempfile.NamedTemporaryFile(
                suffix=f'_arrow_{color.strip("#")}.svg',
                delete=False, mode='w', encoding='utf-8'
            )
            tmp.write(svg)
            tmp.close()
            return tmp.name.replace("\\", "/")
        except Exception:
            return src.replace("\\", "/")

    def _combo_style(self):
        c = self._theme_colors
        arrow_path = self._arrow_svg_path(c['arrow_color'])
        return (
            f"QComboBox{{background-color:{c['bg_entry']};border:1px solid {c['border_strong']};"
            f"border-radius:5px;padding:3px 30px 3px 10px;color:{c['text']};}}"
            f"QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:top right;"
            f"width:25px;border:none;background:transparent;}}"
            f"QComboBox::down-arrow{{image:url({arrow_path});width:12px;height:8px;}}"
            f"QComboBox QAbstractItemView{{background-color:{c['bg_entry']};color:{c['text']};"
            f"selection-background-color:{c['combo_selection']};border:1px solid {c['border_strong']};}}"
        )

    def _textedit_style(self):
        c = self._theme_colors
        return (f"QTextEdit{{background-color:{c['bg_entry_alt']};border:1px solid {c['border_strong']};"
                f"border-radius:6px;color:#8fbdf0;padding:5px;}}")

    def _label_row_style(self):
        return f"color:{self._theme_colors['text']};font-size:13px;border:none;background:transparent;"

    def _section_frame_style(self):
        c = self._theme_colors
        return (f"QFrame{{background-color:{c['bg_card_alt']};border:1px solid {c['border_card']};"
                f"border-radius:12px;}}"
                f"QLabel{{border:none;background:transparent;color:{c['text']};}}")

    def setup_header(self):
        """Crée l'en-tête avec titre et bouton Sauvegarder"""
        header_layout = QHBoxLayout()
        
        # Initialisation du registre si absent
        if not hasattr(self, 'translation_map'): 
            self.translation_map = {}

        # Titre principal
        self.title_label = QLabel(self.texts.get("title", "Settings"))
        self.title_label.setObjectName("headerTitle")  # Identifiant pour le style CSS et thèmes
        self.title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #1F6AA5;")
        
        # Enregistrement pour la traduction automatique
        self.translation_map[self.title_label] = "title"
        
        # Bouton Sauvegarder
        self.btn_save = QPushButton(self.texts.get("btn_save", "Save"))
        self.btn_save.setFixedSize(150, 40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_all_settings)
        self.set_button_style("idle")
        
        # Enregistrement pour la traduction automatique
        self.translation_map[self.btn_save] = "btn_save"
        
        # Assemblage du layout
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_save)
        
        self.main_layout.addLayout(header_layout)

    def setup_scroll_area(self):
        """Zone défilante contenant les colonnes de réglages"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        self.content_layout = QHBoxLayout(container)
        self.content_layout.setSpacing(30)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Création des deux colonnes (Gauche & Droite)
        self.left_col = QVBoxLayout()
        self.right_col = QVBoxLayout()
        
        self.content_layout.addLayout(self.left_col, 1)
        self.content_layout.addLayout(self.right_col, 1)

        # --- COLONNE GAUCHE (G-Code & Hardware) ---
        self.setup_left_column()

        # --- COLONNE DROITE (Apparence & Maintenance) ---
        self.setup_right_column()

        scroll.setWidget(container)
        self.main_layout.addWidget(scroll)

    def setup_left_column(self):
        # --- SECTION G-CODE ---
        # On passe la CLÉ "sec_gcode" au lieu du texte traduit
        sec_gcode = self.create_section(self.left_col, "sec_gcode")
        
        # Mode de commande (M67 / S)
        self.create_dropdown(sec_gcode, "label_cmd_mode", 
                            ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        
        # Entrées simples
        self.create_simple_input(sec_gcode, "label_output_e", "m67_e_num", precision=0)
        self.create_simple_input(sec_gcode, "label_ctrl_max", "ctrl_max", precision=0)
        
        # Mode d'allumage (M3/M4)
        self.create_dropdown(sec_gcode, "label_firing", ["M3/M5", "M4/M5"], "firing_mode")
        
        # Extension de fichier
        self.create_simple_input(sec_gcode, "label_extension", "gcode_extension")

        # --- SECTION HARDWARE ---
        sec_hw = self.create_section(self.left_col, "sec_hardware")
        # Sliders
        self.create_slider_input(sec_hw, "label_latency", -20, 20, 0, "laser_latency")
        self.create_slider_input(sec_hw, "label_overscan", 0, 50, 10, "premove")
        self.create_slider_input(sec_hw, "hor_linestep", 0.01, 0.5, 0.1, "hor_linestep", decimals=4)
        self.create_slider_input(sec_hw, "ver_linestep", 0.01, 0.5, 0.1, "ver_linestep", decimals=4)

        # --- SECTION SCRIPTS ---
        sec_scripts = self.create_section(self.left_col, "sec_scripts")
        self.create_script_box(sec_scripts, "label_header", "custom_header")
        self.create_script_box(sec_scripts, "label_footer", "custom_footer")

        self.left_col.addStretch()

    def setup_right_column(self):
        # --- SECTION APPARENCE ---
        sec_app = self.create_section(self.right_col, "sec_appearance")
        
        # Thème et Langue
        self.create_dropdown(sec_app, "label_theme", ["Dark", "Light", "System"], "theme")
        if hasattr(self.controller, 'all_translations'):
            available_languages = sorted(list(self.controller.all_translations.keys()))
        else:
            # Fallback de sécurité si le controller n'est pas encore prêt
            available_languages = ["English", "Français", "Deutsch"]
        
        self.create_dropdown(sec_app, "label_lang", available_languages, "language")
        
        # Switch Vignettes
        self.create_switch(sec_app, "enable_thumbnails", "enable_thumbnails")

        # --- SECTION MAINTENANCE ---
        sec_maint = self.create_section(self.right_col, "maintenance_data")
        
        # Bouton Effacer Vignettes
        self.btn_clear_data = QPushButton(self.texts["erase_thumbnails"])
        self.translation_map[self.btn_clear_data] = "erase_thumbnails"
        self.btn_clear_data.setFixedHeight(35)
        self.btn_clear_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_data.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #942121; }
        """)
        self.btn_clear_data.clicked.connect(self.clear_thumbnails_and_stats)
        sec_maint.addWidget(self.btn_clear_data)

        # Bouton Reset Paramètres
        self.btn_reset_all = QPushButton(self.texts["reset_all_parameters"])
        self.translation_map[self.btn_reset_all] = "reset_all_parameters"
        self.btn_reset_all.setFixedHeight(35)
        self.btn_reset_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_all.setStyleSheet("""
            QPushButton { background-color: transparent; color: #ddd; border: 1px solid #8b0000; border-radius: 6px; }
            QPushButton:hover { background-color: #8b0000; color: white; }
        """)
        self.btn_reset_all.clicked.connect(self.reset_settings)
        sec_maint.addWidget(self.btn_reset_all)

        self.right_col.addStretch()

    # --- HELPERS DE CONSTRUCTION ---

    def create_section(self, layout, title_key):
        """Crée un bloc section et enregistre le label pour la traduction centralisée"""
        section_frame = QFrame()
        section_frame.setObjectName("sectionFrame")
        section_frame.setStyleSheet(self._section_frame_style())
        self._section_frames.append(section_frame)
        sec_layout = QVBoxLayout(section_frame)
        sec_layout.setContentsMargins(15, 15, 15, 15)
        sec_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- TRADUCTION INITIALE ---
        # On récupère le texte, si la clé n'existe pas, on affiche la clé
        title_text = self.texts.get(title_key, title_key).upper()
        
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("color: #3a9ad9; font-weight: bold; font-size: 12px; border: none;")
        sec_layout.addWidget(title_lbl)
        
        # --- ENREGISTREMENT CENTRALISÉ ---
        if not hasattr(self, 'translation_map'):
            self.translation_map = {}
        
        # On lie l'objet Label à sa clé pour update_texts()
        self.translation_map[title_lbl] = title_key
        
        layout.addWidget(section_frame)
        return sec_layout

    def create_input_row(self, layout, label_key, widget, key=None):
        row = QWidget()
        row.setStyleSheet("border: none; background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 5, 0, 5)
        
        # Initialisation de la map si elle n'existe pas
        if not hasattr(self, 'translation_map'): 
            self.translation_map = {}

        # --- LOGIQUE DE TRADUCTION AMÉLIORÉE ---
        if key:
            # 1. On vérifie si label_key est DIRECTEMENT une clé de traduction (ex: "enable_thumbnails")
            if label_key in self.texts:
                translation_key = label_key
            
            # 2. Sinon, est-ce qu'elle a déjà un préfixe connu ?
            elif label_key.startswith("label_") or label_key.startswith("sec_"):
                translation_key = label_key
            
            # 3. Sinon, on tente d'ajouter "label_" par défaut (ex: "extension" -> "label_extension")
            else:
                translation_key = f"label_{label_key}"
            
            # On récupère le texte final
            display_text = self.texts.get(translation_key, translation_key)
            lbl = QLabel(display_text)
            
            # On enregistre l'objet QLabel avec sa clé trouvée
            self.translation_map[lbl] = translation_key
        else:
            # Cas sans clé technique (juste du texte statique)
            lbl = QLabel(label_key)

        lbl.setStyleSheet(self._label_row_style())
        
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(widget)
        layout.addWidget(row)

    def create_simple_input(self, layout, label_text, key, precision=2):
        """Crée une ligne avec un Label et un QLineEdit sans valeur par défaut externe"""
        edit = QLineEdit()
        edit.setFixedWidth(100)
        edit.setStyleSheet(self._entry_style())

        # On initialise à 0 par défaut, formaté selon la précision
        initial_value = 0
        fmt = "{:d}" if precision == 0 else f"{{:.{precision}f}}"
        edit.setText(fmt.format(initial_value))
        
        edit.textChanged.connect(self.mark_as_changed)
        
        # On ajoute la ligne au layout via votre méthode parente
        self.create_input_row(layout, label_text, edit, key=key)
        
        # On stocke les infos dans le dictionnaire de contrôle
        self.controls[key] = {
            "entry": edit,
            "precision": precision,
            "is_int": (precision == 0)
        }

    # --- LOGIQUE DE STYLE DU BOUTON ---

    def set_button_style(self, state):
        if state == "idle":
            style = "background-color: #1F6AA5; color: white; border-radius: 8px; font-weight: bold;"
        elif state == "saved":
            style = "background-color: #2d5a27; color: white; border-radius: 8px; font-weight: bold;"
        elif state == "changed":
            style = "background-color: #3B8ED0; color: white; border-radius: 8px; font-weight: bold; border: 2px solid white;"
        
        self.btn_save.setStyleSheet(style)

    def mark_as_changed(self):
        if not self.loading:
            self.set_button_style("changed")

    # --- LOGIQUE DE SAUVEGARDE ---
    def save_all_settings(self):
        """Récupère toutes les valeurs de l'interface et les sauvegarde"""
        try:
            def get_float(key):
                try:
                    return float(self.controls[key]["entry"].text().replace(',', '.'))
                except:
                    return 0.0

            new_settings = {
                "theme": self.controls["theme"]["combo"].currentText(),
                "language": self.controls["language"]["combo"].currentText(),
                "enable_thumbnails": self.controls["enable_thumbnails"]["check"].isChecked(),
                "cmd_mode": self.controls["cmd_mode"]["combo"].currentText(),
                "firing_mode": self.controls["firing_mode"]["combo"].currentText(),
                "m67_e_num": int(float(self.controls["m67_e_num"]["entry"].text() or "0")),
                "ctrl_max":  int(float(self.controls["ctrl_max"]["entry"].text()  or "0")),
                "gcode_extension": self.controls["gcode_extension"]["entry"].text(),
                "laser_latency": get_float("laser_latency"),
                "premove": get_float("premove"),
                "hor_linestep": get_float("hor_linestep"),
                "ver_linestep": get_float("ver_linestep"),
                "custom_header": self.controls["custom_header"]["text"].toPlainText(),
                "custom_footer": self.controls["custom_footer"]["text"].toPlainText()
            }

            self.controller.set_section("machine_settings", new_settings)
            
            if self.controller.save():
                from core.translations import TRANSLATIONS
                new_lang = new_settings["language"]
                print(f"[SAVE] langue sauvée: {new_lang}")
                self.texts = TRANSLATIONS.get(new_lang, TRANSLATIONS["English"])["settings"]
                self.update_texts()

                self.set_button_style("saved")
                self.btn_save.setText(f"✓ {self.texts.get('btn_save', 'Save')}")

                main_window = (getattr(self, '_main_window', None)
                               or getattr(self.controller, '_main_window', None)
                               or self.window())
                print(f"[SAVE] main_window trouvé: {main_window}")
                print(f"[SAVE] has update_ui_language: {hasattr(main_window, 'update_ui_language')}")
                if main_window and hasattr(main_window, 'update_ui_language'):
                    main_window.update_ui_language()
                if main_window and hasattr(main_window, 'update_ui_theme'):
                    main_window.update_ui_theme()

                QTimer.singleShot(2000, self.reset_save_btn)
            else:
                raise Exception("Erreur d'écriture disque")

        except Exception as e:
            import traceback
            print(f"[SAVE] ERREUR: {e}")
            traceback.print_exc()
            self.btn_save.setStyleSheet("background-color: #942121; color: white; border-radius: 8px;")

    def _apply_language(self, lang: str, translations: dict):
        """Reçoit lang et translations directement — pas de relecture config."""
        from core.translations import TRANSLATIONS as _TR
        self.texts = _TR.get(lang, _TR["English"])["settings"]
        from gui.utils_qt import translate_ui_widgets
        translate_ui_widgets(self.translation_map, self.texts)

    def update_texts(self):
        """Met à jour dynamiquement tous les labels de la vue settings"""
        # 1. Recharger les textes
        lang = self.controller.get_item("machine_settings", "language", "English")
        from core.translations import TRANSLATIONS
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["settings"]
        
        # 2. Traduire TOUT d'un coup (Titre, bouton save, sections, labels)
        from gui.utils_qt import translate_ui_widgets
        translate_ui_widgets(self.translation_map, self.texts)
        
        # 3. Optionnel : Si vous avez d'autres boutons fixes (Reset, Clear data)
        # n'oubliez pas de les ajouter à la map dans leur setup respectif !

    def reset_save_btn(self):
        self.set_button_style("idle")
        self.btn_save.setText(self.texts["btn_save"])

    def create_slider_input(self, layout, label_text, min_v, max_v, default, key, decimals=2):
        """
        Crée une rangée avec Label + Slider + Entry.
        decimals : nombre de chiffres après la virgule (0 pour des entiers).
        """
        # 1. Calcul du facteur d'échelle pour le slider
        # 10^decimals (ex: 0 -> 1, 1 -> 10, 2 -> 100)
        multiplier = 10 ** decimals
        
        right_side_widget = QWidget()
        right_side_widget.setFixedWidth(180) 
        
        right_side_layout = QHBoxLayout(right_side_widget)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(10)

        # 2. Le Slider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_v * multiplier), int(max_v * multiplier))
        slider.setValue(int(default * multiplier))
        slider.setFixedWidth(120)
        
        # 3. Le champ de saisie (Entry)
        # Formatage initial selon decimals
        initial_val = int(default) if decimals == 0 else default
        entry = QLineEdit(str(initial_val))
        entry.setFixedWidth(50)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setStyleSheet(self._entry_style())

        # --- GESTION DES CONNEXIONS ---
        
        def on_slider_moved(v):
            val = v / multiplier
            # Formatage dynamique : entier si 0, sinon float
            text = str(int(val)) if decimals == 0 else f"{val:.{decimals}f}"
            entry.setText(text)
            self.mark_as_changed()

        def on_entry_finished():
            try:
                raw_text = entry.text().replace(',', '.')
                val = float(raw_text) if raw_text else 0.0
                slider.setValue(int(val * multiplier))
                self.mark_as_changed()
            except ValueError:
                # Optionnel : remettre la valeur du slider si la saisie est invalide
                on_slider_moved(slider.value())

        slider.valueChanged.connect(on_slider_moved)
        entry.editingFinished.connect(on_entry_finished)

        right_side_layout.addWidget(slider)
        right_side_layout.addWidget(entry)

        # 4. Intégration dans la ligne
        self.create_input_row(layout, label_text, right_side_widget, key=key)
        
        # Stockage
        self.controls[key] = {"slider": slider, "entry": entry, "decimals": decimals}

    def create_script_box(self, layout, label_key, key):
        """Crée un bloc de texte multi-lignes pour les scripts G-Code avec traduction"""
        container = QWidget()
        v_box = QVBoxLayout(container)
        v_box.setContentsMargins(0, 10, 0, 5)
        v_box.setSpacing(5)
        
        # --- TRADUCTION INITIALE ---
        # On va chercher la traduction de la clé (ex: "label_header")
        display_text = self.texts.get(label_key, label_key)
        lbl = QLabel(display_text)
        lbl.setStyleSheet(f"color:{self._theme_colors.get('text_secondary','#bbbbbb')};"
                          "font-size:11px;font-weight:bold;border:none;background:transparent;")
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # --- ENREGISTREMENT POUR LA TRADUCTION DYNAMIQUE ---
        if not hasattr(self, 'translation_map'):
            self.translation_map = {}
        self.translation_map[lbl] = label_key
        
        # Zone de texte
        text_edit = QTextEdit()
        text_edit.setFixedHeight(80)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setStyleSheet(self._textedit_style())
        text_edit.textChanged.connect(self.mark_as_changed)
        
        v_box.addWidget(lbl)
        v_box.addWidget(text_edit)
        
        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Stockage pour la sauvegarde (attention à utiliser la même structure que les autres)
        self.controls[key] = {"text": text_edit}

    def create_dropdown(self, layout, label_text, options, key):
        """Crée un menu déroulant et délègue la gestion du label à create_input_row"""
        combo = QComboBox()
        combo.addItems(options)
        combo.setFixedWidth(150)
        
        combo.setStyleSheet(self._combo_style())

        combo.currentIndexChanged.connect(self.mark_as_changed)

        self.create_input_row(layout, label_text, combo, key=key)
        
        # Stockage pour la récupération des données
        self.controls[key] = {"combo": combo}

    def create_switch(self, layout, label_key, key):
        """Crée une ligne avec un Label et un Switch"""
        check = Switch()
        
        #check.toggled.connect(lambda v: print(f"Switch {key}:", v))
        check.stateChanged.connect(self.mark_as_changed)
        self.create_input_row(layout, label_key, check, key=key)
        
        self.controls[key] = {"check": check}

    def ask_confirmation(self, title, message):
        """Affiche une boîte de dialogue de confirmation stylisée"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        # Boutons personnalisés
        yes_button = msg_box.addButton(self.texts.get("confirm_yes", "Confirmer"), QMessageBox.ButtonRole.YesRole)
        no_button = msg_box.addButton(self.texts.get("confirm_no", "Annuler"), QMessageBox.ButtonRole.NoRole)
        
        msg_box.setDefaultButton(no_button)
        
        # Style Dark pour la boîte
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #2b2b2b; }
            QLabel { color: white; font-size: 13px; }
            QPushButton { 
                background-color: #444; color: white; border-radius: 4px; 
                padding: 5px 15px; min-width: 80px; 
            }
            QPushButton:hover { background-color: #1F6AA5; }
        """)
        
        msg_box.exec()
        
        return msg_box.clickedButton() == yes_button

    def load_settings(self):
        self.loading = True
        data = self.controller.get_section("machine_settings")

        # --- LOGIQUE SÉCURISÉE ---
        
        # 1. ComboBox
        for key in ["theme", "language", "cmd_mode", "firing_mode"]:
            if key in self.controls:
                val = data.get(key, "") # Si None, on prend une chaîne vide
                index = self.controls[key]["combo"].findText(str(val))
                if index >= 0:
                    self.controls[key]["combo"].setCurrentIndex(index)

        # 2. LineEdits
        for key in ["m67_e_num", "ctrl_max"]:
            if key in self.controls:
                raw = data.get(key, 0)
                try:
                    val = int(float(str(raw)))  # gère "0", 0, 0.0, "1000.0"
                except (ValueError, TypeError):
                    val = 0
                self.controls[key]["entry"].setText(str(val))
        for key in ["gcode_extension"]:
            if key in self.controls:
                self.controls[key]["entry"].setText(str(data.get(key, "")))

        # 3. Sliders 
        for key in ["laser_latency", "premove"]:
            if key in self.controls:
                # On force une valeur de secours (0.0) si le manager renvoie None
                raw_val = data.get(key)
                val = float(raw_val) if raw_val is not None else 0.0
                
                self.controls[key]["slider"].setValue(int(val * 100))
                self.controls[key]["entry"].setText(f"{val:.2f}")

        for key in ["hor_linestep", "ver_linestep"]:
            if key in self.controls:

                raw_val = data.get(key)
                val = float(raw_val) if raw_val is not None else 0.1

                self.controls[key]["slider"].setValue(int(val * 10000))
                self.controls[key]["entry"].setText(f"{val:.4f}")

        # 4. Scripts & Switches
        if "custom_header" in self.controls:
            self.controls["custom_header"]["text"].setPlainText(data.get("custom_header", ""))
        if "custom_footer" in self.controls:
            self.controls["custom_footer"]["text"].setPlainText(data.get("custom_footer", ""))
        if "enable_thumbnails" in self.controls:
            self.controls["enable_thumbnails"]["check"].setChecked(bool(data.get("enable_thumbnails", True)))

        self.loading = False
        self.set_button_style("idle")

    def showEvent(self, event):
        """Recharge les valeurs depuis la config à chaque fois que la vue devient visible.
        Indispensable pour refléter les sauvegardes faites depuis d'autres vues (ex: calibration)."""
        super().showEvent(event)
        self.load_settings()


    def clear_thumbnails_and_stats(self):
        """Supprime les vignettes physiques et réinitialise les statistiques dans le JSON"""
        
        # 1. Demande de confirmation à l'utilisateur
        if not self.ask_confirmation(self.texts["erase_thumbnails"], self.texts["erase_thumbnails_confirm"]):
            return

        # 2. NETTOYAGE DES FICHIERS (Vignettes)
        # On définit le chemin vers le dossier des miniatures
        target_dir = os.path.join(os.getcwd(), "assets", "thumbnails") 
        files_purged = 0
        
        if os.path.exists(target_dir):
            try:
                for filename in os.listdir(target_dir):
                    # On préserve le fichier .gitkeep s'il existe
                    if filename == ".gitkeep": 
                        continue
                        
                    file_path = os.path.join(target_dir, filename)
                    
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path) # Suppression du fichier
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path) # Suppression du dossier si présent
                        files_purged += 1
                    except Exception as e:
                        print(f"Impossible de supprimer {filename}: {e}")
            except Exception as e:
                print(f"Erreur d'accès au dossier: {e}")

        # 3. NETTOYAGE DES STATISTIQUES (Dans le ConfigManager)
        try:
            # On définit les valeurs de remise à zéro
            empty_stats = {
                "total_lines": 0,
                "total_gcodes": 0,
                "total_time_seconds": 0.0,
                "last_project_time": 0.0
            }
            
            # Mise à jour de la section via le controller
            self.controller.set_section("stats", empty_stats)
            
            # Sauvegarde immédiate du fichier JSON
            if self.controller.save():
                # Feedback visuel : Succès
                self.btn_clear_data.setText("✓ " + self.texts["erase_thumbnails_done"])
                self.btn_clear_data.setStyleSheet("""
                    QPushButton {
                        background-color: #2d5a27; 
                        color: white; 
                        border-radius: 6px; 
                        font-weight: bold;
                    }
                """)
            else:
                raise Exception("Erreur de sauvegarde JSON")

        except Exception as e:
            print(f"Erreur lors de la remise à zéro des stats: {e}")
            self.btn_clear_data.setText("Erreur")
            self.btn_clear_data.setStyleSheet("background-color: #942121; color: white;")

        # 4. Retour à l'état initial du bouton après 2 secondes
        # On utilise un QTimer pour ne pas bloquer l'interface
        QTimer.singleShot(2000, self.restore_maintenance_buttons)

    def restore_maintenance_buttons(self):
        """Restitue le style original du bouton de maintenance"""
        self.btn_clear_data.setText(self.texts["erase_thumbnails"])
        self.btn_clear_data.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #942121; }
        """)

    def reset_settings(self):
        if self.ask_confirmation(self.texts["reset_all_parameters"], self.texts["reset_all_parameters_confirm"]):
            if self.controller.reset_all(): 
                self.load_settings()

    def apply_theme(self, colors):
        """Met à jour dynamiquement les couleurs de la vue Settings"""
        self._theme_colors = colors

        text     = colors['text']
        text_sec = colors['text_secondary']

        # ── Vue racine ────────────────────────────────────────────
        self.setStyleSheet("background-color: transparent;")

        # ── Sections ─────────────────────────────────────────────
        for frame in self._section_frames:
            frame.setStyleSheet(self._section_frame_style())

        # ── Labels ───────────────────────────────────────────────
        for lbl in self.findChildren(QLabel):
            if lbl.objectName() == "headerTitle":
                continue
            if lbl.styleSheet() and '#3a9ad9' in lbl.styleSheet():
                continue
            if lbl.styleSheet() and 'font-weight:bold' in lbl.styleSheet().replace(' ', ''):
                lbl.setStyleSheet(
                    f"color:{text_sec};font-size:11px;font-weight:bold;"
                    "border:none;background:transparent;"
                )
            else:
                lbl.setStyleSheet(self._label_row_style())

        # ── QLineEdit ─────────────────────────────────────────────
        for w in self.findChildren(QLineEdit):
            w.setStyleSheet(self._entry_style())

        # ── QComboBox ─────────────────────────────────────────────
        for w in self.findChildren(QComboBox):
            w.setStyleSheet(self._combo_style())

        # ── QTextEdit ─────────────────────────────────────────────
        for w in self.findChildren(QTextEdit):
            w.setStyleSheet(self._textedit_style())

        # ── Boutons maintenance ───────────────────────────────────
        if hasattr(self, 'btn_clear_data'):
            self.btn_clear_data.setStyleSheet(
                f"QPushButton{{background-color:{colors['btn_neutral']};color:{text};"
                f"border-radius:6px;font-weight:bold;}}"
                f"QPushButton:hover{{background-color:#942121;color:white;}}"
            )
        if hasattr(self, 'btn_reset_all'):
            self.btn_reset_all.setStyleSheet(
                f"QPushButton{{background-color:transparent;color:{text_sec};"
                f"border:1px solid #8b0000;border-radius:6px;}}"
                f"QPushButton:hover{{background-color:#8b0000;color:white;}}"
            )