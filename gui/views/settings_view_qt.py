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
        
        # Titre
        self.title_label = QLabel(self.texts["title"])
        self.title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #1F6AA5;")
        
        # Bouton Sauvegarder (Look ALIG)
        self.btn_save = QPushButton(self.texts["btn_save"])
        self.btn_save.setFixedSize(150, 40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_all_settings)
        self.set_button_style("idle")
        
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
        sec_gcode = self.create_section(self.left_col, self.texts["sec_gcode"])
        
        # Mode de commande (M67 / S)
        self.create_dropdown(sec_gcode, self.texts["label_cmd_mode"], 
                            ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        
        # Entrées simples (E-Num et Max Control)
        self.create_simple_input(sec_gcode, self.texts["label_output_e"], "m67_e_num")
        self.create_simple_input(sec_gcode, self.texts["label_ctrl_max"], "ctrl_max")
        
        # Mode d'allumage (M3/M4)
        self.create_dropdown(sec_gcode, self.texts["label_firing"], ["M3/M5", "M4/M5"], "firing_mode")
        
        # Extension de fichier
        self.create_simple_input(sec_gcode, self.texts.get("label_extension", "Extension"), "gcode_extension")

        # --- SECTION HARDWARE ---
        sec_hw = self.create_section(self.left_col, self.texts["sec_hardware"])
        # Sliders avec entrées numériques
        self.create_slider_input(sec_hw, self.texts["label_latency"], -20, 20, 0, "laser_latency")
        self.create_slider_input(sec_hw, self.texts["label_overscan"], 0, 50, 10, "premove")

        # --- SECTION SCRIPTS ---
        sec_scripts = self.create_section(self.left_col, self.texts["sec_scripts"])
        self.create_script_box(sec_scripts, self.texts["label_header"], "custom_header")
        self.create_script_box(sec_scripts, self.texts["label_footer"], "custom_footer")

        self.left_col.addStretch()

    def setup_right_column(self):
        # --- SECTION APPARENCE ---
        sec_app = self.create_section(self.right_col, self.texts["sec_appearance"])
        
        # Thème et Langue (Remplacent les segmented_pair)
        self.create_dropdown(sec_app, self.texts["label_theme"], ["Dark", "Light", "System"], "theme")
        self.create_dropdown(sec_app, self.texts["label_lang"], ["Français", "English"], "language")
        
        # Switch Vignettes
        self.create_switch(sec_app, self.texts["enable_thumbnails"], "enable_thumbnails")

        # --- SECTION MAINTENANCE ---
        sec_maint = self.create_section(self.right_col, self.texts["maintenance_data"])
        
        # Bouton Effacer Vignettes (Style Rouge au hover)
        self.btn_clear_data = QPushButton(self.texts["erase_thumbnails"])
        self.btn_clear_data.setFixedHeight(35)
        self.btn_clear_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_data.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #942121; }
        """)
        self.btn_clear_data.clicked.connect(self.clear_thumbnails_and_stats)
        sec_maint.addWidget(self.btn_clear_data)

        # Bouton Reset Paramètres (Bordure rouge)
        self.btn_reset_all = QPushButton(self.texts["reset_all_parameters"])
        self.btn_reset_all.setFixedHeight(35)
        self.btn_reset_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_all.setStyleSheet("""
            QPushButton { background-color: transparent; color: #ddd; border: 1px solid #8b0000; border-radius: 6px; }
            QPushButton:hover { background-color: #8b0000; color: white; }
        """)
        self.btn_reset_all.clicked.connect(self.reset_settings)
        sec_maint.addWidget(self.btn_reset_all)

        # Ajout d'un espace vide en bas pour caler le tout vers le haut
        self.right_col.addStretch()

    # --- HELPERS DE CONSTRUCTION ---

    def create_section(self, layout, title_key):
        """Crée un bloc section et stocke le label pour la traduction future"""
        section_frame = QFrame()
        section_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 12px;
            }
            QLabel { border: none; background: transparent; } 
        """)
        sec_layout = QVBoxLayout(section_frame)
        sec_layout.setContentsMargins(15, 15, 15, 15)
        sec_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Pour éviter l'étirement interne
        
        # Récupération du texte via la clé
        title_text = self.texts.get(title_key, title_key).upper()
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("color: #3a9ad9; font-weight: bold; font-size: 12px; border: none;")
        sec_layout.addWidget(title_lbl)
        
        # --- STOCKAGE DE LA RÉFÉRENCE ---
        if not hasattr(self, 'section_labels'):
            self.section_labels = {}
        self.section_labels[title_key] = title_lbl
        
        layout.addWidget(section_frame)
        return sec_layout

    def create_input_row(self, layout, label_text, widget, key=None): # Ajout de key
        row = QWidget()
        row.setStyleSheet("border: none; background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 5, 0, 5)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        
        # --- AJOUT : Stocker le label pour traduction ---
        if key:
            if not hasattr(self, 'option_labels'): self.option_labels = {}
            self.option_labels[key] = lbl

        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(widget)
        layout.addWidget(row)

    def create_simple_input(self, layout, label_text, key):
        """Crée une ligne avec un Label et un QLineEdit"""
        edit = QLineEdit()
        edit.setFixedWidth(100)
        edit.setStyleSheet("""
            QLineEdit { background-color: #1e1e1e; border: 1px solid #444; 
                        border-radius: 4px; color: white; padding: 3px; }
        """)
        edit.textChanged.connect(self.mark_as_changed)
        
        self.create_input_row(layout, label_text, edit)
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
                self.set_button_style("saved")
                self.btn_save.setText(f"✓ {self.texts['btn_save']}")
                
                # --- MISE À JOUR DYNAMIQUE DE L'INTERFACE ---
                main_window = self.window()
                
                # 1. Mise à jour de la langue
                if hasattr(main_window, 'update_ui_language'):
                    main_window.update_ui_language() 
                
                # 2. Mise à jour du thème (Couleurs et Icônes SVG)
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
        lang = self.controller.get_item("machine_settings", "language", "English")
        from core.translations import TRANSLATIONS
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["settings"]
        
        # 1. Éléments fixes
        self.title_label.setText(self.texts["title"])
        self.btn_save.setText(self.texts["btn_save"])
        self.btn_clear_data.setText(self.texts["erase_thumbnails"])
        self.btn_reset_all.setText(self.texts["reset_all_parameters"])
        
        # 2. Titres de sections (G-CODE, HARDWARE, etc.)
        if hasattr(self, 'section_labels'):
            for key, label in self.section_labels.items():
                if key in self.texts:
                    label.setText(self.texts[key].upper())

        # 3. Labels des options (Thème, Langue, Mode de commande, etc.)
        if hasattr(self, 'option_labels'):
            for key, label in self.option_labels.items():
                # On cherche la clé correspondante (ex: label_theme)
                translation_key = f"label_{key}" if not key.startswith("label_") else key
                if translation_key in self.texts:
                    label.setText(self.texts[translation_key])

    def reset_save_btn(self):
        self.set_button_style("idle")
        self.btn_save.setText(self.texts["btn_save"])

    def create_slider_input(self, layout, label_text, min_v, max_v, default, key):
        """Crée une rangée avec Label + Slider + Entry"""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 5, 0, 5)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #ddd; font-size: 12px; border: none; background: transparent;")
        
        # Le Slider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v * 100, max_v * 100) # On multiplie par 100 pour gérer les décimales
        slider.setValue(int(default * 100))
        slider.setFixedWidth(120)
        
        # Le champ de saisie
        entry = QLineEdit(str(default))
        entry.setFixedWidth(50)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 4px;
                color: white;
            }
        """)

        # Connexions (Sync Slider <-> Entry)
        slider.valueChanged.connect(lambda v: [
            entry.setText(f"{v/100:.2f}"),
            self.mark_as_changed()
        ])
        entry.editingFinished.connect(lambda: [
            slider.setValue(int(float(entry.text() or 0) * 100)),
            self.mark_as_changed()
        ])

        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(slider)
        row_layout.addWidget(entry)
        
        layout.addWidget(row)
        self.controls[key] = {"slider": slider, "entry": entry}

    def create_script_box(self, layout, label_text, key):
        """Crée un bloc de texte multi-lignes pour les scripts G-Code"""
        container = QWidget()
        v_box = QVBoxLayout(container)
        v_box.setContentsMargins(0, 10, 0, 5)
        v_box.setSpacing(5)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #bbb; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        text_edit = QTextEdit()
        text_edit.setFixedHeight(80)
        text_edit.setFont(QFont("Consolas", 10)) # Police de code
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #444;
                border-radius: 6px;
                color: #8fbdf0; /* Bleu clair pour le code */
                padding: 5px;
            }
        """)
        text_edit.textChanged.connect(self.mark_as_changed)
        
        v_box.addWidget(lbl)
        v_box.addWidget(text_edit)
        
        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignTop)
        self.controls[key] = {"text": text_edit}

    def create_dropdown(self, layout, label_text, options, key):
        combo = QComboBox()
        combo.addItems(options)
        combo.setFixedWidth(150)
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
        self.create_input_row(layout, label_text, combo, key=key) # On passe la clé ici
        self.controls[key] = {"combo": combo}

    def create_switch(self, layout, label_text, key):
        check = Switch()
        check.toggled.connect(lambda v: print("Switch:", v))
        check.stateChanged.connect(self.mark_as_changed)
        self.create_input_row(layout, label_text, check)
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