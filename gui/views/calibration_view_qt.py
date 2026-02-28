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
        self.translation_map = {}
        self.test_cards = []  # Liste pour stocker les boutons de la sidebar
        self.current_test_id = None  # Pour savoir quel test est actif
        
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
        
        # Bouton d'action (on lui donne un objectName pour le retrouver)
        self.action_btn = QPushButton(self.texts.get("btn_prepare", "Prepare"))
        self.action_btn.setFixedHeight(52)
        self.action_btn.setStyleSheet("background-color: #e67e22; font-weight: bold; border-radius: 10px;")
        self.right_layout.addWidget(self.action_btn)

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
            {"id": "latency", "icon": SVG_ICONS["LATENCY"], "fixed": False},
            {"id": "linestep", "icon": SVG_ICONS["LINESTEP"], "fixed": False},
            {"id": "power", "icon": SVG_ICONS["POWER"], "fixed": True}
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
        """Crée un bouton stylisé pour la sidebar avec identification pour traduction et reset"""
        card = QPushButton()
        card.setCheckable(True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(80)
        
        # --- STOCKAGE DE L'ID ---
        # On stocke l'ID du test directement dans l'objet pour le retrouver facilement
        test_id = test_info.get("id")
        card.setProperty("test_id", test_id)
        
        # Ajout au groupe pour l'exclusivité
        if hasattr(self, 'button_group'):
            self.button_group.addButton(card)
        
        layout = QHBoxLayout(card)
        
        # --- LOGIQUE D'ICÔNE SVG ---
        # On attache icon_label à la card pour pouvoir changer sa couleur dynamiquement
        card.icon_label = QLabel() 
        card.icon_label.setObjectName("card_icon")
        
        icon_path = test_info.get("icon_path")
        keep_original = test_info.get("fixed_color", False)
        target_color = None if keep_original else "#EEEEEE"

        if icon_path and os.path.exists(icon_path):
            pixmap = get_svg_pixmap(icon_path, size=QSize(35, 35), color_hex=target_color)
            if not pixmap.isNull():
                card.icon_label.setPixmap(pixmap)
        
        card.icon_label.setFixedWidth(50)
        card.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- TEXTES (Avec ObjectName pour retranslate_ui) ---
        text_container = QVBoxLayout()
        
        title = QLabel(test_info.get("title", "Sans titre"))
        title.setObjectName("card_title") # Identifiant pour findChild()
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: white; border: none; background: transparent;")
        
        desc = QLabel(test_info.get("desc", ""))
        desc.setObjectName("card_desc")  # Identifiant pour findChild()
        desc.setStyleSheet("font-size: 11px; color: #aaaaaa; border: none; background: transparent;")
        desc.setWordWrap(True)
        
        text_container.addWidget(title)
        text_container.addWidget(desc)
        
        layout.addWidget(card.icon_label)
        layout.addLayout(text_container)
        
        # Style du bouton
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

        # On utilise une fonction intermédiaire pour capturer l'ID actuel
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
        # On boucle sur notre liste de cartes stockées
        for card in self.test_cards:
            # On utilise property() car nous avons fait setProperty dans create_test_card
            t_id = card.property("test_id")
            is_selected = (t_id == self.current_test_id)
            
            # Récupération des métadonnées du test pour cette carte
            test_meta = next((t for t in self.tests_data if t["id"] == t_id), {})
            
            # On ne recolore pas les icônes à couleurs fixes (ex: Power/Logo)
            if not test_meta.get("fixed_color", False):
                current_icon_color = color_active if is_selected else color_main
                
                # Mise à jour de l'icône via la référence directe stockée dans la carte
                if hasattr(card, 'icon_label'):
                    pix = get_svg_pixmap(
                        test_meta.get("icon_path"), 
                        size=QSize(35, 35), 
                        color_hex=current_icon_color
                    )
                    card.icon_label.setPixmap(pix)

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
        self.clear_dynamic_layout() # Nettoyage de la zone
        
        if self.current_test_id == "latency":
            self.setup_latency_params()
        elif self.current_test_id == "linestep":
            # self.setup_linestep_params()
            pass
        elif self.current_test_id == "power":
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


    def retranslate_ui(self):
        """Appelée lors d'un changement de langue"""
        # 1. Recharger les dictionnaires de texte depuis le contrôleur
        self.load_texts()
        
        # 2. Mise à jour des éléments statiques de l'interface
        if hasattr(self, 'sidebar_title_label'):
            self.sidebar_title_label.setText(self.texts.get("sidebar_title", "Tests"))
        
        if hasattr(self, 'action_btn'):
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
            
            # --- IMPORTANT : Mise à jour des labels dynamiques (Feedrate, Power, etc.) ---
            # On relance la construction des paramètres pour rafraîchir les labels traduits
            if self.current_test_id == "latency":
                self.setup_latency_params()
            elif self.current_test_id == "linestep":
                # self.setup_linestep_params()
                pass
            elif self.current_test_id == "power":
                # self.setup_power_params()
                pass
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
        
        # Vider les paramètres
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