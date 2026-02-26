# -*- coding: utf-8 -*-
import os
import sys
import webbrowser
import ctypes
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QStackedWidget, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap

from core.translations import TRANSLATIONS
from utils import paths
from gui.views.dashboard_view_qt import DashboardViewQt
from gui.views.settings_view_qt import SettingsViewQt

class MainWindowQt(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller 
        self.config_manager = controller
        self.version = "0.99b (Qt)"

        # --- ÉTAPE 1 : INITIALISATION DES TEXTES PAR DÉFAUT ---
        # On crée l'attribut 'texts' immédiatement pour éviter l'AttributeError
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        print(f"DEBUG: {lang}")
        from core.translations import TRANSLATIONS
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})

        # 2. Chargement des ressources
        paths.load_all_images()

        # 3. Configuration de la fenêtre
        self.setWindowTitle(f"ALIG - Advanced Laser Imaging Generator v{self.version}")
        self._setup_window_init()
        self._setup_icon()

        # 4. Layout Principal
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 5. Création des composants (Maintenant self.texts existe !)
        self.setup_top_bar()
        
        self.content_area = QStackedWidget()
        self.main_layout.addWidget(self.content_area)

        # 6. MISE À JOUR FINALE (Optionnel si déjà fait en étape 1)
        self.update_ui_language()

        # 7. Affichage
        self.show_dashboard()

    def _setup_window_init(self):
        """Remplace load_window_config de Tkinter"""
        data = self.config_manager.get_section("window_settings")
        # Géométrie par défaut
        self.resize(1300, 900)
        
        # Si tu veux restaurer la position précise, Qt peut sauver/charger 
        # tout l'état de la fenêtre en une ligne de byte-array, 
        # mais on restera simple pour l'instant avec les chiffres.
        if data.get("is_maximized", False):
            self.showMaximized()

    def _setup_icon(self):
        """Configuration de l'icône (plus simple qu'avec Tkinter)"""
        if os.path.exists(paths.LOGO_ALIG):
            self.setWindowIcon(QIcon(paths.LOGO_ALIG))
            # Fix pour la barre des tâches Windows
            myappid = f'momo.alig.lasergenerator.{self.version}'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    def setup_top_bar(self):
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(50)
        self.top_bar.setStyleSheet("background-color: #2b2b2b; border-bottom: 1px solid #3d3d3d;")
        
        layout = QHBoxLayout(self.top_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10) # Un peu d'espace entre les éléments

        # 1. GAUCHE : Bouton HOME & Titre
        self.btn_home = QPushButton()
        home_icon_path = os.path.join(paths.ASSETS_DIR, "home_white.png")
        if os.path.exists(home_icon_path):
            self.btn_home.setIcon(QIcon(home_icon_path))
            self.btn_home.setIconSize(QSize(22, 22))
        
        self.btn_home.setFixedSize(40, 40)
        self.btn_home.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_home.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 5px; } QPushButton:hover { background-color: #3d3d3d; }")
        self.btn_home.clicked.connect(self.show_dashboard)
        layout.addWidget(self.btn_home)

        self.view_title = QLabel("")
        self.view_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-left: 5px;")
        layout.addWidget(self.view_title)

        # --- RESSORT (Pousse tout le reste à droite) ---
        layout.addStretch()

        # 2. DROITE : Support, GitHub et Settings


        # Bouton Support (Jaune)
        self.btn_support = QPushButton(self.texts.get("support", "Support"))
        self.btn_support.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_support.setMinimumHeight(30)
        self.btn_support.setStyleSheet("""
            QPushButton { 
                background-color: #FFDD00; 
                color: black; 
                font-weight: bold; 
                border-radius: 4px; 
                padding: 0px 15px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #f7d000; }
        """)
        self.btn_support.clicked.connect(lambda: webbrowser.open("https://buymeacoffee.com/momo830"))
        layout.addWidget(self.btn_support)

        # Bouton GitHub (Bleu ciel)
        self.btn_github = QPushButton("🌐 GitHub")
        self.btn_github.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_github.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                color: #1F6AA5; 
                border: none; 
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { color: #3B8ED0; text-decoration: underline; }
        """)
        self.btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/MoMo830/ALIG"))
        layout.addWidget(self.btn_github)

        # Petit séparateur vertical "|"
        self.separator = QLabel("|")
        self.separator.setStyleSheet("color: #444444; font-weight: bold;")
        layout.addWidget(self.separator)

        # Bouton Settings
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("QPushButton { background: transparent; color: white; border: none; font-size: 18px; } QPushButton:hover { background-color: #3d3d3d; border-radius: 5px; }")
        self.btn_settings.clicked.connect(self.show_settings_mode)
        layout.addWidget(self.btn_settings)

        # Enfin, on ajoute la TopBar au layout principal de la fenêtre
        self.main_layout.addWidget(self.top_bar)

    def update_ui_language(self):
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})
        
        # Mettre à jour les boutons de navigation ici
        # self.btn_dashboard.setText(self.texts.get("dashboard"))
        # self.btn_settings.setText(self.texts.get("settings"))
        
        # Mettre à jour la vue active dans le StackedWidget
        current_view = self.content_area.currentWidget()
        if current_view and hasattr(current_view, 'update_texts'):
            current_view.update_texts()

    # --- Routage ---
    def show_dashboard(self):
        self.view_title.setText(self.texts.get("dashboard", "DASHBOARD"))
        # Créer la vue
        self.current_view = DashboardViewQt(controller=self)
        # L'ajouter au StackedWidget
        self.content_area.addWidget(self.current_view)
        self.content_area.setCurrentWidget(self.current_view)

    def show_settings_mode(self):
        """Affiche et rafraîchit la vue des réglages"""
        
        # 1. On s'assure que les traductions sont à jour dans le controller
        # (Au cas où l'utilisateur vient de changer de langue)
        lang_code = self.controller.get_item("machine_settings", "language", "English")
        from core.translations import TRANSLATIONS
        self.controller.translations = TRANSLATIONS.get(lang_code, TRANSLATIONS["English"])

        # 2. Gestion de l'instance de la vue
        if not hasattr(self, 'settings_view'):

            self.settings_view = SettingsViewQt(self.controller)
            self.content_area.addWidget(self.settings_view)
        else:
            # OPTIONNEL : Si la vue existe déjà, on peut forcer un rafraîchissement 
            # des textes internes si nécessaire
            self.settings_view.texts = self.controller.translations["settings"]

        # 3. Mise à jour du titre de la zone de contenu
        self.view_title.setText(self.controller.translations["settings"]["title"].upper())
        
        # 4. Affichage
        self.content_area.setCurrentWidget(self.settings_view)


    def show_raster_mode(self, image_to_load=None):
        """Placeholder pour le futur mode Raster"""
        self.view_title.setText("RASTER MODE")
        temp_page = QLabel("Module Raster - En cours de migration...")
        temp_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_page.setStyleSheet("color: white; font-size: 18px;")
        
        # On ajoute et on affiche
        self.content_area.addWidget(temp_page)
        self.content_area.setCurrentWidget(temp_page)

    def show_calibration_mode(self):
        """Placeholder pour le futur mode Calibration"""
        self.view_title.setText("CALIBRATION")
        temp_page = QLabel("Module Calibration - En cours de migration...")
        temp_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_page.setStyleSheet("color: white; font-size: 18px;")
        
        self.content_area.addWidget(temp_page)
        self.content_area.setCurrentWidget(temp_page)

 

    def closeEvent(self, event):
        """Gère la fermeture (remplace on_closing)"""
        # Sauvegarde config...
        is_maximized = self.isMaximized()
        window_data = {
            "is_maximized": is_maximized,
            "geometry": f"{self.width()}x{self.height()}+{self.x()}+{self.y()}"
        }
        self.config_manager.set_section("window_settings", window_data)
        self.config_manager.save()
        event.accept()