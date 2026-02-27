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
from gui.views.calibration_view_qt import CalibrationView
from utils.paths import SVG_ICONS
from gui.utils_qt import get_svg_pixmap


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

        # 2. Vérification des ressources
        from utils import paths
        paths.check_assets()

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
        self.update_ui_theme()

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
        layout.setSpacing(10)

        # 1. GAUCHE : Bouton HOME & Titre
        self.btn_home = QPushButton()
        
        # --- NOUVEAU SYSTÈME SVG POUR HOME ---
        home_pixmap = get_svg_pixmap(SVG_ICONS["HOME"], size=QSize(22, 22), color_hex="#FFFFFF")
        if not home_pixmap.isNull():
            self.btn_home.setIcon(QIcon(home_pixmap))
            self.btn_home.setIconSize(QSize(22, 22))
        
        self.btn_home.setFixedSize(40, 40)
        self.btn_home.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_home.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 5px; } 
            QPushButton:hover { background-color: #3d3d3d; }
        """)
        self.btn_home.clicked.connect(self.show_dashboard)
        layout.addWidget(self.btn_home)

        self.view_title = QLabel("")
        self.view_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-left: 5px;")
        layout.addWidget(self.view_title)

        # --- RESSORT (Pousse tout le reste à droite) ---
        layout.addStretch()

        # 2. DROITE : GitHub et Settings

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
        import webbrowser
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

        # 3. Bouton Settings (Remplacé par une icône SVG Gear)
        self.btn_settings = QPushButton()
        
        # --- NOUVEAU SYSTÈME SVG POUR SETTINGS ---
        # Si tu n'as pas encore de GEAR.SVG, tu peux utiliser une autre clé existante de SVG_ICONS
        settings_pixmap = get_svg_pixmap(SVG_ICONS.get("SETTINGS", SVG_ICONS["HOME"]), size=QSize(20, 20), color_hex="#FFFFFF")
        
        # if not settings_pixmap.isNull(): # a modifier pour utilisation futur svg
        #     self.btn_settings.setIcon(QIcon(settings_pixmap))
        #     self.btn_settings.setIconSize(QSize(20, 20))
        # else:
        self.btn_settings.setText("⚙️") # Fallback emoji
            
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; } 
            QPushButton:hover { background-color: #3d3d3d; border-radius: 5px; }
        """)
        self.btn_settings.clicked.connect(self.show_settings_mode)
        layout.addWidget(self.btn_settings)

        # Enfin, on ajoute la TopBar au layout principal de la fenêtre
        self.main_layout.addWidget(self.top_bar)

    def update_ui_language(self):
        """Met à jour les textes de la barre de titre et de la vue active"""
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})
        
        # Mettre à jour le titre de la vue (Dashboard / Calibration / etc.)
        # On peut imaginer une logique qui récupère le titre traduit selon la vue actuelle
        
        # Mettre à jour la vue active dans le StackedWidget
        current_view = self.content_area.currentWidget()
        
        # On vérifie les deux noms possibles de méthodes par sécurité
        if current_view:
            if hasattr(current_view, 'update_ui_language'):
                current_view.update_ui_language()
            elif hasattr(current_view, 'update_texts'):
                current_view.update_texts()

    def update_ui_theme(self):
        """Met à jour les couleurs et les icônes de l'interface globale"""
        colors = self.get_theme_colors()
        
        # 1. Mise à jour du fond de la fenêtre entière (Le conteneur principal)
        # C'est ce qui règle le problème du fond qui reste sombre
        self.central_widget.setStyleSheet(f"background-color: {colors['bg_card']};")
        
        # 2. Mise à jour de la zone de contenu pour qu'elle soit transparente
        self.content_area.setStyleSheet("background: transparent; border: none;")

        # 3. Mise à jour visuelle de la TopBar
        self.top_bar.setStyleSheet(f"""
            QFrame {{ 
                background-color: {colors['bg_card']}; 
                border-bottom: 1px solid {colors['border']}; 
            }}
        """)
        
        # 4. Mise à jour du titre et des séparateurs
        self.view_title.setStyleSheet(f"color: {colors['text']}; font-weight: bold; font-size: 14px; margin-left: 5px; border: none;")
        self.separator.setStyleSheet(f"color: {colors['border']}; font-weight: bold;")
        
        # 5. Re-génération des icônes SVG de la TopBar      
        home_pix = get_svg_pixmap(SVG_ICONS["HOME"], QSize(22, 22), colors['text'])
        self.btn_home.setIcon(QIcon(home_pix))
        
        #settings_pix = get_svg_pixmap(SVG_ICONS.get("SETTINGS", SVG_ICONS["HOME"]), QSize(20, 20), colors['text'])
        #self.btn_settings.setIcon(QIcon(settings_pix))
        
        # 6. Propager le changement à la vue ACTUELLEMENT visible
        current_view = self.content_area.currentWidget()
        if current_view and hasattr(current_view, 'apply_theme'):
            current_view.apply_theme(colors)

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
        """Affiche la vue de Calibration réelle"""
        # 1. Mise à jour du titre
        # On essaie de récupérer la traduction, sinon fallback sur "CALIBRATION"
        title = self.texts.get("calibration", "CALIBRATION")
        self.view_title.setText(title.upper())

        # 2. Gestion de l'instance de la vue (Lazy Loading)
        if not hasattr(self, 'calibration_view'):
            # On crée l'instance une seule fois
            # On passe self.controller (ton config_manager) à la vue
            self.calibration_view = CalibrationView(parent=self, controller=self.controller)
            self.content_area.addWidget(self.calibration_view)
        else:
            # Optionnel : Rafraîchir les textes si la langue a changé
            if hasattr(self.calibration_view, 'update_ui_language'):
                self.calibration_view.update_ui_language()

        # 3. Basculement sur la vue
        self.content_area.setCurrentWidget(self.calibration_view)

    def get_theme_colors(self):
        theme = self.config_manager.get_item("machine_settings", "theme", "Dark")
        if theme == "Light":
            return {
                "text": "#000000",
                "text_secondary": "#444444",
                "bg_card": "#F0F0F0",
                "border": "#CCCCCC",
                "suffix": "_LIGHT"
            }
        else: # Dark par défaut
            return {
                "text": "#FFFFFF",
                "text_secondary": "gray",
                "bg_card": "#2b2b2b",
                "border": "#3d3d3d",
                "suffix": "_DARK"
            }

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