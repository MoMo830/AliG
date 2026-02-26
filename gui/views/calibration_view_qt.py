import os
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame, 
                             QLabel, QScrollArea, QStackedWidget, QPushButton, 
                             QLineEdit, QGridLayout, QButtonGroup)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap

from utils.paths import SVG_ICONS, EXPLAIN_PNG
from gui.switch import Switch
from core.translations import TRANSLATIONS
from gui.utils_qt import get_svg_pixmap




class CalibrationView(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        
        if hasattr(self.controller, 'translations'):
            current_repo = self.controller.translations
        else:
            # Fallback de sécurité
            lang = self.controller.get_item("machine_settings", "language", "English")
            current_repo = TRANSLATIONS.get(lang, TRANSLATIONS["English"])

        # 2. Extraction des sections nécessaires
        self.texts = current_repo.get("calibration", {})
        self.common_texts = current_repo.get("common", {})
        
        # --- Layout Principal (Horizontal : Sidebar | Détails) ---
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 20)
        self.main_layout.setSpacing(20)

        # --- 1. SIDEBAR (Gauche) ---
        self.setup_sidebar()
        
        # --- 2. ZONE DE DÉTAILS (Droite) ---
        self.right_column = QFrame()
        self.right_column.setObjectName("RightColumn")
        self.right_column.setStyleSheet("""
            QFrame#RightColumn {
                background-color: #202020;
                border-radius: 15px;
            }
        """)
        self.right_layout = QVBoxLayout(self.right_column)
        self.main_layout.addWidget(self.right_column, stretch=1)

        # Composants de la zone de droite
        self.setup_detail_header()
        
        # Zone dynamique (équivalent de dynamic_params_frame)
        self.dynamic_params_widget = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_params_widget)
        self.right_layout.addWidget(self.dynamic_params_widget)
        
        # Bouton d'action fixe en bas
        self.action_btn = QPushButton(self.texts["btn_prepare"])
        self.action_btn.setFixedHeight(52)
        self.action_btn.setStyleSheet("background-color: #e67e22; font-weight: bold; border-radius: 10px;")
        self.right_layout.addWidget(self.action_btn)

    def setup_sidebar(self):
        """Crée la liste des tests à gauche."""
        sidebar_container = QVBoxLayout()
        
        title = QLabel(self.texts["sidebar_title"])
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e67e22;")
        sidebar_container.addWidget(title)

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
        # On définit les données des tests (en utilisant nos dictionnaires de textes)
        self.tests_data = [
            {
                "id": "latency",
                "title": self.texts.get("latency_title"),
                "desc": self.texts.get("latency_short"),
                "icon_path": SVG_ICONS["LATENCY"], 
                "fixed_color": False,
            },
            {
                "id": "linestep",
                "title": self.texts.get("linestep_title"),
                "desc": self.texts.get("linestep_short"),
                "icon_path": SVG_ICONS["LINESTEP"],
                "fixed_color": False,
            },
            {
                "id": "power",
                "title": self.texts.get("power_title"),
                "desc": self.texts.get("power_short"),
                "icon_path": SVG_ICONS["POWER"],
                "fixed_color": True,
            }
        ]

        # On crée les widgets pour chaque test
        for test in self.tests_data:
            card = self.create_test_card(test)
            self.scroll_layout.addWidget(card)



    def create_test_card(self, test_info):
        """Crée un bouton stylisé pour la sidebar avec rendu SVG intelligent"""
        card = QPushButton()
        card.setCheckable(True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(80)
        
        # Ajout au groupe pour l'exclusivité (Highlight unique)
        if hasattr(self, 'button_group'):
            self.button_group.addButton(card)
        
        layout = QHBoxLayout(card)
        
        # --- LOGIQUE D'ICÔNE SVG DYNAMIQUE ---
        icon_label = QLabel()
        icon_path = test_info.get("icon_path")
        
        # On vérifie si on doit garder les couleurs d'origine ou colorer en blanc
        keep_original = test_info.get("fixed_color", False)
        target_color = None if keep_original else "#EEEEEE"

        if icon_path and isinstance(icon_path, str) and os.path.exists(icon_path):
            # Utilisation de la fonction de rendu SVG (on suppose qu'elle est dans self)
            pixmap = get_svg_pixmap(
                icon_path, 
                size=QSize(35, 35), 
                color_hex=target_color
            )
            
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
            else:
                print(f"DEBUG CARD: Erreur de rendu SVG pour {icon_path}")
        else:
            print(f"DEBUG CARD: Chemin SVG invalide -> {icon_path}")
            
        icon_label.setFixedWidth(50)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- TEXTES ---
        text_container = QVBoxLayout()
        title = QLabel(test_info.get("title", "Sans titre"))
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: white; border: none; background: transparent;")
        
        desc = QLabel(test_info.get("desc", ""))
        desc.setStyleSheet("font-size: 11px; color: #aaaaaa; border: none; background: transparent;")
        desc.setWordWrap(True)
        
        text_container.addWidget(title)
        text_container.addWidget(desc)
        
        layout.addWidget(icon_label)
        layout.addLayout(text_container)
        
        # Style du bouton (Hover et Sélection orange)
        card.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                text-align: left;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #e67e22;
            }
            QPushButton:checked {
                background-color: #3d3d3d;
                border: 2px solid #e67e22;
            }
        """)

        # Connecter le clic
        card.clicked.connect(lambda: self.on_test_selected(test_info))
        
        return card
    
    def on_test_selected(self, test_info):
        """
        Gère la mise à jour de la vue détaillée lorsqu'un test est sélectionné.
        Adapte les couleurs et les images selon le thème (Dark/Light).
        """


        # 0. Récupération du thème actuel
        theme = self.controller.config_manager.get_item("machine_settings", "theme", "Dark")
        is_light = (theme == "Light")
        
        # Définition des couleurs selon le thème
        color_main = "#000000" if is_light else "#EEEEEE"
        color_active = "#e67e22"  # Orange reste identique pour le highlight
        theme_suffix = "_LIGHT" if is_light else "_DARK"

        # 1. Mise à jour des textes (Titre et Description longue)
        self.detail_title.setText(test_info.get("title", ""))
        
        long_desc_key = f"{test_info['id']}_long"
        self.detail_desc.setText(self.texts.get(long_desc_key, ""))

        # 2. MISE À JOUR VISUELLE DE LA SIDEBAR
        if hasattr(self, 'scroll_layout'):
            for i in range(self.scroll_layout.count()):
                item = self.scroll_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    # Vérification si la carte est celle sélectionnée
                    is_selected = (getattr(card, 'test_id', None) == test_info['id'])
                    
                    # On ne recolore que si l'icône n'est pas "fixed_color"
                    if not test_info.get("fixed_color", False):
                        current_icon_color = color_active if is_selected else color_main
                        
                        if hasattr(card, 'icon_label'):
                            pix = get_svg_pixmap(
                                test_info.get("icon_path"), 
                                size=QSize(35, 35), 
                                color_hex=current_icon_color
                            )
                            card.icon_label.setPixmap(pix)

        # 3. Gestion de l'image d'illustration (Preview PNG)
        if hasattr(self, 'preview_image_label'):
            from utils.paths import EXPLAIN_PNG
            
            # Construction de la clé selon le test et le thème (ex: "LATENCY_DARK" ou "LATENCY_LIGHT")
            img_key = f"{test_info['id'].upper()}{theme_suffix}"
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
                # Fallback : si l'image spécifique au thème n'existe pas, on tente sans le suffixe
                print(f"DEBUG: Preview non trouvée pour {img_key}")
                self.preview_image_label.clear()

        # 4. Nettoyage et chargement des paramètres spécifiques
        self.clear_dynamic_layout()
        
        test_id = test_info.get("id")
        if test_id == "latency":
            self.setup_latency_params()
        elif test_id == "linestep":
            # self.setup_linestep_params()
            pass
        elif test_id == "power":
            # self.setup_power_params()
            pass

    def clear_dynamic_layout(self):
        """Supprime tous les widgets de la zone de paramètres dynamique"""
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def setup_detail_header(self):
        """Prépare la zone de texte en haut de la colonne de droite"""
        # Conteneur pour le texte
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)

        # Titre du test (ex: LASER LATENCY TEST)
        self.detail_title = QLabel(self.texts.get("default_title", "Select a test"))
        self.detail_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e67e22;")
        self.detail_title.setWordWrap(True)
        header_layout.addWidget(self.detail_title)

        # Description longue (Instructions)
        self.detail_desc = QLabel(self.texts.get("default_desc", ""))
        self.detail_desc.setStyleSheet("font-size: 13px; color: #DCE4EE; line-height: 1.4;")
        self.detail_desc.setWordWrap(True)
        # On permet au texte d'occuper l'espace nécessaire
        self.detail_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        header_layout.addWidget(self.detail_desc)
        # Création du label pour l'image d'illustration à droite
        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setMinimumHeight(150) # Réserve l'espace
        header_layout.addWidget(self.preview_image_label)

        # Ajout au layout principal de droite
        self.right_layout.addWidget(header_widget)



    def setup_latency_params(self):
        """Construit les champs de saisie pour le test de Latence"""
        # 1. On nettoie la zone avant d'ajouter les nouveaux widgets
        self.clear_dynamic_layout()

        # 2. Création du conteneur stylisé
        container = QFrame()
        container.setObjectName("ParamsContainer")
        container.setStyleSheet("""
            QFrame#ParamsContainer {
                background-color: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
            QLabel { color: #DCE4EE; font-size: 13px; }
            QLineEdit { 
                background-color: #3d3d3d; 
                border: 1px solid #555555; 
                border-radius: 4px; 
                color: white; 
                padding: 5px; 
            }
        """)
        
        grid = QGridLayout(container)
        grid.setSpacing(15)

        # --- Ligne 1 : Feedrate ---
        grid.addWidget(QLabel(self.texts.get("feedrate_calc", "Feedrate:")), 0, 0)
        self.speed_entry = QLineEdit()
        self.speed_entry.setPlaceholderText("ex: 1000")
        # On récupère la valeur actuelle depuis la config
        current_speed = self.controller.get_item("machine_settings", "feedrate", "1000")
        self.speed_entry.setText(str(current_speed))
        grid.addWidget(self.speed_entry, 0, 1)

        # --- Ligne 2 : Mode S (Utilisation de votre Switch) ---
        grid.addWidget(QLabel("Use S-Mode Command:"), 1, 0)
        self.s_mode_switch = Switch()
        # On centre le switch à droite
        grid.addWidget(self.s_mode_switch, 1, 1, Qt.AlignmentFlag.AlignRight)

        # --- Ligne 3 : Puissance ---
        grid.addWidget(QLabel(self.texts.get("power_pct", "Power (%):")), 2, 0)
        self.power_entry = QLineEdit()
        self.power_entry.setText("10")
        grid.addWidget(self.power_entry, 2, 1)

        # Ajout du container au layout dynamique
        self.dynamic_layout.addWidget(container)
        
        # On ajoute un ressort en bas pour que tout reste groupé en haut
        self.dynamic_layout.addStretch()

    def create_switch(self, layout, label_text, key, row):
        """Ajoute une ligne avec un label et ton Switch animé"""
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 5, 0, 5)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 14px; color: #DCE4EE;")
        
        # Utilisation de ton composant personnalisé
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




    def get_txt(self, key, default=""):
        """Cherche d'abord dans calibration, puis dans common"""
        return self.texts.get(key, self.common_texts.get(key, default))

# # Utilisation ultra simple :
# self.btn_prepare.setText(self.get_txt("btn_prepare"))
# self.label_f.setText(self.get_txt("feedrate"))