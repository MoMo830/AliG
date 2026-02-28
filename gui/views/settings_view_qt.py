from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QFrame, QLineEdit, 
                             QSlider, QComboBox, QTextEdit, QCheckBox,
                             QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox
import os
import shutil
from utils.paths import SVG_ICONS
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
        self.loading = True  # Bloque les événements durant la création

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
        self.create_simple_input(sec_gcode, "label_output_e", "m67_e_num")
        self.create_simple_input(sec_gcode, "label_ctrl_max", "ctrl_max")
        
        # Mode d'allumage (M3/M4)
        self.create_dropdown(sec_gcode, "label_firing", ["M3/M5", "M4/M5"], "firing_mode")
        
        # Extension de fichier
        self.create_simple_input(sec_gcode, "label_extension", "gcode_extension")

        # --- SECTION HARDWARE ---
        sec_hw = self.create_section(self.left_col, "sec_hardware")
        # Sliders
        self.create_slider_input(sec_hw, "label_latency", -20, 20, 0, "laser_latency")
        self.create_slider_input(sec_hw, "label_overscan", 0, 50, 10, "premove")

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
        self.create_dropdown(sec_app, "label_lang", ["Français", "English"], "language")
        
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
        section_frame.setStyleSheet("""
            QFrame { background-color: #2b2b2b; border: 1px solid #3d3d3d; border-radius: 12px; }
            QLabel { border: none; background: transparent; } 
        """)
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

        lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(widget)
        layout.addWidget(row)

    def create_simple_input(self, layout, label_text, key):
        """Crée une ligne avec un Label et un QLineEdit"""
        edit = QLineEdit()
        edit.setFixedWidth(100)
        edit.setStyleSheet("""
            QLineEdit { 
                background-color: #1e1e1e; 
                border: 1px solid #444; 
                border-radius: 4px; 
                color: white; 
                padding: 3px; 
            }
        """)
        edit.textChanged.connect(self.mark_as_changed)
        
        # MODIFICATION ICI : On ajoute 'key=key'
        self.create_input_row(layout, label_text, edit, key=key)
        
        self.controls[key] = {"entry": edit}

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
                "m67_e_num": self.controls["m67_e_num"]["entry"].text(),
                "ctrl_max": self.controls["ctrl_max"]["entry"].text(),
                "gcode_extension": self.controls["gcode_extension"]["entry"].text(),
                "laser_latency": get_float("laser_latency"),
                "premove": get_float("premove"),
                "custom_header": self.controls["custom_header"]["text"].toPlainText(),
                "custom_footer": self.controls["custom_footer"]["text"].toPlainText()
            }

            self.controller.set_section("machine_settings", new_settings)
            
            if self.controller.save():
                # 1. On récupère immédiatement les nouvelles traductions pour cette vue
                from core.translations import TRANSLATIONS
                new_lang = new_settings["language"]
                self.texts = TRANSLATIONS.get(new_lang, TRANSLATIONS["English"])["settings"]
                
                # 2. Mise à jour visuelle du bouton de sauvegarde
                self.set_button_style("saved")
                self.btn_save.setText(f"✓ {self.texts.get('btn_save', 'Save')}")
                
                # --- MISE À JOUR DYNAMIQUE DE L'INTERFACE GLOBALE ---
                main_window = self.window()
                if main_window:
                    # A. Notifier la MainWindow de changer la langue (TopBar, etc.)
                    if hasattr(main_window, 'update_ui_language'):
                        main_window.update_ui_language() 
                    
                    # B. Forcer la mise à jour du titre de la vue dans la TopBar
                    # (Nécessaire car ce label n'est souvent pas dans la translation_map)
                    if hasattr(main_window, 'view_title'):
                        topbar_texts = TRANSLATIONS.get(new_lang, TRANSLATIONS["English"]).get("topbar", {})
                        main_window.view_title.setText(topbar_texts.get("settings", "SETTINGS").upper())
                    
                    # C. Mise à jour du thème (Couleurs et Icônes SVG)
                    if hasattr(main_window, 'update_ui_theme'):
                        main_window.update_ui_theme()
                
                QTimer.singleShot(2000, self.reset_save_btn)
            else:
                raise Exception("Erreur d'écriture disque")

        except Exception as e:
            print(f"Erreur de sauvegarde : {e}")
            self.btn_save.setStyleSheet("background-color: #942121; color: white; border-radius: 8px;")

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

    def create_slider_input(self, layout, label_text, min_v, max_v, default, key):
        """Crée une rangée avec Label + Slider + Entry via create_input_row (Solution 2)"""
        
        # 1. Création du container pour les widgets de droite (Slider + Entry)
        right_side_widget = QWidget()
        
        # --- SOLUTION 2 : LARGEUR FIXE DU BLOC DE DROITE ---
        # On fixe la largeur totale du bloc pour qu'il soit identique partout.
        # 120 (slider) + 10 (spacing) + 50 (entry) = 180px
        right_side_widget.setFixedWidth(180) 
        
        right_side_layout = QHBoxLayout(right_side_widget)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(10)

        # 2. Le Slider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_v * 100), int(max_v * 100))
        slider.setValue(int(default * 100))
        slider.setFixedWidth(120) # Taille fixe pour le slider
        
        # 3. Le champ de saisie (Entry)
        entry = QLineEdit(str(default))
        entry.setFixedWidth(50) # Taille fixe pour l'entrée
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setStyleSheet("""
            QLineEdit { 
                background-color: #1e1e1e; 
                border: 1px solid #444; 
                border-radius: 4px; 
                color: white; 
            }
        """)

        # Connexions (Slider <-> Entry)
        slider.valueChanged.connect(lambda v: [entry.setText(f"{v/100:.2f}"), self.mark_as_changed()])
        entry.editingFinished.connect(lambda: [
            slider.setValue(int(float(entry.text().replace(',', '.') or 0) * 100)), 
            self.mark_as_changed()
        ])

        # Ajout des widgets au layout interne du bloc de droite
        right_side_layout.addWidget(slider)
        right_side_layout.addWidget(entry)

        # 4. --- UTILISATION DE LA MÉTHODE COMMUNE ---
        # Le label sera à gauche, le 'right_side_widget' sera poussé à droite
        self.create_input_row(layout, label_text, right_side_widget, key=key)
        
        # Stockage pour la sauvegarde
        self.controls[key] = {"slider": slider, "entry": entry}

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
        lbl.setStyleSheet("color: #bbb; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # --- ENREGISTREMENT POUR LA TRADUCTION DYNAMIQUE ---
        if not hasattr(self, 'translation_map'):
            self.translation_map = {}
        self.translation_map[lbl] = label_key
        
        # Zone de texte
        text_edit = QTextEdit()
        text_edit.setFixedHeight(80)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #444;
                border-radius: 6px;
                color: #8fbdf0;
                padding: 5px;
            }
        """)
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
        
        # Correction du chemin de l'icône pour Windows/Linux
        arrow_path = SVG_ICONS["ARROW_DOWN"].replace("\\", "/")
        
        combo.setStyleSheet(f"""
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
            QComboBox::down-arrow {{
                image: url({arrow_path});
                width: 12px;
                height: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1e1e1e;
                color: white;
                selection-background-color: #444;
                border: 1px solid #444;
            }}
        """)

        combo.currentIndexChanged.connect(self.mark_as_changed)

        self.create_input_row(layout, label_text, combo, key=key)
        
        # Stockage pour la récupération des données
        self.controls[key] = {"combo": combo}

    def create_switch(self, layout, label_key, key):
        """Crée une ligne avec un Label et un Switch"""
        check = Switch()
        
        check.toggled.connect(lambda v: print(f"Switch {key}:", v))
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
        for key in ["m67_e_num", "ctrl_max", "gcode_extension"]:
            if key in self.controls:
                self.controls[key]["entry"].setText(str(data.get(key, "")))

        # 3. Sliders (LÀ OÙ ÇA PLANTAIT)
        for key in ["laser_latency", "premove"]:
            if key in self.controls:
                # On force une valeur de secours (0.0) si le manager renvoie None
                raw_val = data.get(key)
                val = float(raw_val) if raw_val is not None else 0.0
                
                self.controls[key]["slider"].setValue(int(val * 100))
                self.controls[key]["entry"].setText(f"{val:.2f}")

        # 4. Scripts & Switches
        if "custom_header" in self.controls:
            self.controls["custom_header"]["text"].setPlainText(data.get("custom_header", ""))
        if "custom_footer" in self.controls:
            self.controls["custom_footer"]["text"].setPlainText(data.get("custom_footer", ""))
        if "enable_thumbnails" in self.controls:
            self.controls["enable_thumbnails"]["check"].setChecked(bool(data.get("enable_thumbnails", True)))

        self.loading = False
        self.set_button_style("idle")

 


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
        # 1. Mise à jour du style des sections (les cadres)
        # On utilise le sélecteur QFrame pour ne pas impacter les enfants
        section_style = f"""
            QFrame {{
                background-color: {colors['bg_card']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QLabel {{ border: none; background: transparent; color: {colors['text']}; }}
        """

        # On parcourt tous les widgets pour trouver nos sections
        # (Ou plus simplement, on réapplique le style aux frames stockées)
        for widget in self.findChildren(QFrame):
            if widget.objectName() == "sectionFrame":
                widget.setStyleSheet(section_style)

        # 2. Mise à jour des labels de texte (Headers, Sliders, etc.)
        # On force la couleur du texte et on enlève les bordures
        label_style = f"color: {colors['text']}; border: none; background: transparent;"
        for lbl in self.findChildren(QLabel):
            # On évite de toucher au titre principal s'il a un style spécifique
            if lbl.objectName() != "headerTitle":
                lbl.setStyleSheet(label_style)
        
        # 3. Mise à jour du fond de la vue elle-même (si besoin)
        self.setStyleSheet(f"background-color: transparent;")