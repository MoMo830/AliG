# -*- coding: utf-8 -*-
import os
import sys
import webbrowser
import ctypes
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QStackedWidget, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPalette
from PyQt6.QtWidgets import QApplication

from core.translations import TRANSLATIONS
from utils import paths
from gui.views.dashboard_view_qt import DashboardViewQt
from gui.views.settings_view_qt import SettingsViewQt
from gui.views.calibration_view_qt import CalibrationView
from utils.paths import SVG_ICONS, ASSETS_DIR
from gui.utils_qt import get_svg_pixmap



class MainWindowQt(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        # 1. PROTECTION RADICALE (Imports déjà faits en haut du fichier)
        self.setBackgroundRole(QPalette.ColorRole.Window)
        self.setAutoFillBackground(True)
        self.all_translations = TRANSLATIONS
        
        # On définit la couleur de la palette immédiatement
        pal = self.palette()
        dark_color = QColor("#2b2b2b")
        pal.setColor(QPalette.ColorRole.Window, dark_color)
        pal.setColor(QPalette.ColorRole.Base, dark_color)
        pal.setColor(QPalette.ColorRole.Button, dark_color)
        self.setPalette(pal)
        self.setUpdatesEnabled(False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
        
        # On force le style CSS sur la Window ET le CentralWidget
        self.setStyleSheet("QWidget#CentralWidget { background-color: #2b2b2b; color: white; }")

        self.controller = controller 
        self.config_manager = controller
        self.controller._main_window = self   # ref pour que les vues remontent jusqu'ici
        self.version = "0.99b"

        # 2. CHARGEMENT DES TEXTES
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})

        # 3. Configuration fenêtre (Géométrie uniquement, PAS DE SHOW)
        self.setWindowTitle(f"ALIG - Advanced Laser Imaging Generator v{self.version}")
        self._setup_window_init() 
        self._setup_icon()

        # 4. Layout Principal
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 5. Composants
        self.setup_top_bar()
        self.content_area = QStackedWidget()
        self.main_layout.addWidget(self.content_area)

        # 6. Contenu (On charge TOUT maintenant)
        QTimer.singleShot(0, self._post_init_ui)

    def _post_init_ui(self):
        self.show_dashboard()
        self.update_ui_theme()
        # Pré-créer raster_view en arrière-plan pendant que l'utilisateur
        # regarde le dashboard — au clic le basculement sera instantané
        QTimer.singleShot(300, self._preload_raster_view)

    def _preload_raster_view(self):
        """Crée raster_view en avance pour un basculement immédiat au clic."""
        if not hasattr(self, 'raster_view'):
            from gui.views.raster_view_qt import RasterViewQt
            self.raster_view = RasterViewQt(parent=self, controller=self)
            self.raster_view._main_window = self
            self.content_area.addWidget(self.raster_view)
            self.raster_view.apply_theme(self.get_theme_colors())
        


    def _setup_window_init(self):
        data = self.config_manager.get_section("window_settings")

        self.resize(1300, 900)



    def _setup_icon(self):
        """Configuration de l'icône de fenêtre et de la barre des tâches"""
        icon_path = paths.LOGO_ALIG

        if os.path.exists(icon_path):
            # 1. Définir l'icône de la fenêtre principale
            self.setWindowIcon(QIcon(icon_path))

            # 2. Fix pour la barre des tâches Windows (AppUserModelID)
            # On utilise une chaîne unique pour que Windows identifie l'app
            try:
                myappid = f'momo.alig.lasergenerator.{self.version}'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                print(f"Erreur lors du réglage de l'AppUserModelID : {e}")
        else:
            print(f"Alerte : Icône introuvable à l'emplacement {icon_path}")

    def setup_top_bar(self):
        self.top_bar = QFrame()
        #self.top_bar.setUpdatesEnabled(False)
        self.top_bar.setAutoFillBackground(True)
        self.top_bar.setObjectName("topBar")
        self.top_bar.setFixedHeight(50)
        self.top_bar.setStyleSheet("""
            /* On cible la barre elle-même */
            #topBar { 
                background-color: #2b2b2b; 
                border-bottom: 1px solid #3d3d3d; 
            }
            
            /* On force tous les widgets à l'intérieur à ne pas avoir de bordure 
               et un fond transparent */
            #topBar QWidget {
                border: none;
                background-color: transparent;
            }
        """)
        layout = QHBoxLayout(self.top_bar)
        layout.setContentsMargins(10, 0, 10, 1)
        layout.setSpacing(10)

        # --- INITIALISATION MAP DE TRADUCTION ---
        if not hasattr(self, 'translation_map'):
            self.translation_map = {}

        # 1. GAUCHE : Bouton HOME & Titre
        self.btn_home = QPushButton()
    

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

        # Label pour le titre de la vue (Dashboard / Settings / etc.)
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
        
        # ENREGISTREMENT TRADUCTION SUPPORT
        self.translation_map[self.btn_support] = "support"

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

        # 3. Bouton Settings (Icône SVG Gear)
        self.btn_settings = QPushButton()
        settings_pixmap = get_svg_pixmap(SVG_ICONS.get("SETTINGS", SVG_ICONS["GEAR"]), size=QSize(20, 20), color_hex="#FFFFFF")
        
        if not settings_pixmap.isNull():
            self.btn_settings.setIcon(QIcon(settings_pixmap))
            self.btn_settings.setIconSize(QSize(20, 20))
        else:
            self.btn_settings.setText("⚙️")
            
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setToolTip(self.texts.get("settings", "Settings")) # Tooltip traduit
        self.btn_settings.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; } 
            QPushButton:hover { background-color: #3d3d3d; border-radius: 5px; }
        """)
        self.btn_settings.clicked.connect(self.show_settings_mode)
        layout.addWidget(self.btn_settings)
        # btn_settings a une icône — pas de setText, on met à jour le tooltip dans update_ui_language

        # Enfin, on ajoute la TopBar au layout principal de la fenêtre
        self.main_layout.addWidget(self.top_bar)

    def update_ui_language(self):
        """Met à jour les textes de toute l'interface après un changement de langue."""
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        from core.translations import TRANSLATIONS

        self.translations = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
        self.texts = self.translations.get("topbar", {})

        if hasattr(self, 'translation_map'):
            from gui.utils_qt import translate_ui_widgets
            translate_ui_widgets(self.translation_map, self.texts)

        # Tooltip du bouton settings (icône — pas de setText)
        if hasattr(self, 'btn_settings'):
            self.btn_settings.setToolTip(self.texts.get("settings", "Settings"))

        # Propager à TOUTES les vues instanciées
        for attr in ("dashboard_view", "raster_view", "settings_view",
                     "calibration_view", "checker_view"):
            view = getattr(self, attr, None)
            if view is None:
                continue
            if hasattr(view, '_apply_language'):
                view._apply_language(lang, self.translations)
            elif hasattr(view, 'update_ui_language'):
                view.update_ui_language()
            elif hasattr(view, 'update_texts'):
                view.update_texts()

        current_view = self.content_area.currentWidget()
        if current_view and not any(
            current_view is getattr(self, a, None)
            for a in ("dashboard_view", "raster_view", "settings_view",
                      "calibration_view", "checker_view")
        ):
            if hasattr(current_view, 'update_ui_language'):
                current_view.update_ui_language()
            elif hasattr(current_view, 'update_texts'):
                current_view.update_texts()

        # view_title EN DERNIER — après toute propagation pour ne pas être écrasé
        if current_view:
            from gui.views.settings_view_qt import SettingsViewQt
            from gui.views.calibration_view_qt import CalibrationView
            title_key = "dashboard"
            if isinstance(current_view, SettingsViewQt):
                title_key = "settings"
            elif isinstance(current_view, CalibrationView):
                title_key = "calibration"
            self.view_title.setText(self.texts.get(title_key, title_key).upper())

    def update_ui_theme(self):
        """Met à jour les couleurs et les icônes de l'interface globale"""
        colors = self.get_theme_colors()
        
        bg_style = f"QWidget#CentralWidget {{ background-color: {colors['bg_card']}; }}"
        self.central_widget.setStyleSheet(bg_style)
        
        self.content_area.setStyleSheet("background: transparent; border: none;")
        
        self.top_bar.setStyleSheet(f"""
            QFrame#topBar {{ 
                background-color: {colors['bg_card']}; 
                border-bottom: 1px solid {colors['border']}; 
            }}
            QFrame#topBar QWidget {{
                border: none;
                background-color: transparent;
            }}
        """)
        
        # 4. Mise à jour du titre et des séparateurs
        self.view_title.setStyleSheet(f"""
            color: {colors['text']}; 
            font-weight: bold; 
            font-size: 14px; 
            margin-left: 5px; 
            border: none; 
            background: transparent;
        """)
        self.separator.setStyleSheet(f"color: {colors['border']}; font-weight: bold; background: transparent;")
        
        # 5. Re-génération des icônes SVG de la TopBar      
        home_pix = get_svg_pixmap(SVG_ICONS["HOME"], QSize(22, 22), colors['text'])
        self.btn_home.setIcon(QIcon(home_pix))

        settings_pix = get_svg_pixmap(SVG_ICONS.get("SETTINGS", SVG_ICONS["GEAR"]), QSize(20, 20), colors['text'])
        if not settings_pix.isNull():
            self.btn_settings.setIcon(QIcon(settings_pix))
        
        # 6. Propager le changement à TOUTES les vues instanciées
        for attr in ("dashboard_view", "raster_view", "settings_view",
                     "calibration_view", "checker_view"):
            view = getattr(self, attr, None)
            if view and hasattr(view, 'apply_theme'):
                view.apply_theme(colors)
        # checker est recréé à chaque appel — propager aussi à la vue courante si non couverte
        current_view = self.content_area.currentWidget()
        if current_view and hasattr(current_view, 'apply_theme'):
            if not any(current_view is getattr(self, a, None)
                       for a in ("dashboard_view", "raster_view", "settings_view",
                                 "calibration_view", "checker_view")):
                current_view.apply_theme(colors)

    # --- Routage ---
    def show_dashboard(self):
        self.view_title.setText(self.texts.get("dashboard", "DASHBOARD").upper())
        
        if not hasattr(self, 'dashboard_view'):
            self.dashboard_view = DashboardViewQt(controller=self)
            self.dashboard_view._main_window = self
            self.content_area.addWidget(self.dashboard_view)
            self.dashboard_view.apply_theme(self.get_theme_colors())
        else:
            self.dashboard_view.refresh()
        
        self.current_view = self.dashboard_view
        self.content_area.setCurrentWidget(self.dashboard_view)

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
            self.settings_view._main_window = self
            self.content_area.addWidget(self.settings_view)
            self.settings_view.apply_theme(self.get_theme_colors())
        else:
            # OPTIONNEL : Si la vue existe déjà, on peut forcer un rafraîchissement 
            # des textes internes si nécessaire
            self.settings_view.texts = self.controller.translations["settings"]

        # 3. Mise à jour du titre de la zone de contenu
        self.view_title.setText(self.texts.get("settings", "SETTINGS").upper())
        
        # 4. Affichage
        self.content_area.setCurrentWidget(self.settings_view)


    def show_raster_mode(self, image_to_load=None):
        """Affiche la vue Raster Qt — pré-créée au démarrage pour un basculement immédiat."""
        self.view_title.setText(self.texts.get("raster", "RASTER MODE").upper())

        if not hasattr(self, "raster_view"):
            # Fallback si _preload_raster_view n'a pas encore tourné
            from gui.views.raster_view_qt import RasterViewQt
            self.raster_view = RasterViewQt(parent=self, controller=self)
            self.raster_view._main_window = self
            self.content_area.addWidget(self.raster_view)
            self.raster_view.apply_theme(self.get_theme_colors())
        else:
            self.raster_view.load_settings()

        self.current_view = self.raster_view
        self.content_area.setCurrentWidget(self.raster_view)

    def show_simulation(self, engine, payload, return_view="dashboard"):
        """Lance la vue de simulation Qt migrée."""
        self.view_title.setText("SIMULATION")
        from gui.views.simulation_view_qt import SimulationViewQt
        sim_view = SimulationViewQt(
            parent=self,
            controller=self,
            engine=engine,
            payload=payload,
            return_view=return_view
        )
        self.content_area.addWidget(sim_view)
        self.content_area.setCurrentWidget(sim_view)
        self.current_view = sim_view
        sim_view.apply_theme(self.get_theme_colors())

    def show_calibration_mode(self):
        """Affiche la vue de Calibration réelle"""
        # 1. Mise à jour du titre
        # On essaie de récupérer la traduction, sinon fallback sur "CALIBRATION"
        title = self.texts.get("calibration", "CALIBRATION")
        self.view_title.setText(title.upper())

        # 2. Gestion de l'instance de la vue (Lazy Loading)
        if not hasattr(self, 'calibration_view'):
            self.calibration_view = CalibrationView(parent=self, controller=self.controller)
            self.calibration_view._main_window = self
            self.content_area.addWidget(self.calibration_view)
            self.calibration_view.apply_theme(self.get_theme_colors())
        else:
            # Optionnel : Rafraîchir les textes si la langue a changé
            if hasattr(self.calibration_view, 'update_ui_language'):
                self.calibration_view.update_ui_language()

        # 3. Basculement sur la vue
        self.content_area.setCurrentWidget(self.calibration_view)

    def show_checker_mode(self, gcode_path=None):
        """Affiche la vue Checker (lecteur / visualiseur de G-Code existant).
        Crée une nouvelle instance à chaque appel, comme show_simulation.
        Optionnellement, ouvre directement un fichier si gcode_path est fourni."""
        self.view_title.setText("G-CODE CHECKER")

        from gui.views.checker_view_qt import CheckerViewQt
        checker_view = CheckerViewQt(
            parent=self,
            controller=self,
            return_view='dashboard'
        )
        self.checker_view = checker_view          # stocké pour _apply_language
        self.content_area.addWidget(checker_view)
        self.content_area.setCurrentWidget(checker_view)
        self.current_view = checker_view
        checker_view.apply_theme(self.get_theme_colors())

        # Ouverture directe si un chemin est passé (ex: depuis l'historique)
        if gcode_path and os.path.isfile(gcode_path):
            checker_view._load_file(gcode_path)

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