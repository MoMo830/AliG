# -*- coding: utf-8 -*-
import os
import customtkinter as ctk
from tkinter import messagebox
from core.translations import TRANSLATIONS
import webbrowser
from PIL import Image

class LaserGeneratorApp(ctk.CTk):
    def __init__(self, config_manager):
        super().__init__()
        
        # 1. Ressources et Configuration
        self.config_manager = config_manager
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})
        self.version = "0.9783b"
        self.title(f"A.L.I.G. - Advanced Laser Imaging Generator v{self.version}")
        self.current_view = None
        #   Chemins
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = os.path.normpath(os.path.join(current_dir, "..", "assets"))
        self.icon_path = os.path.join(self.assets_dir, "icone_alig.ico")
        # 2. Configuration Système (Fenêtre & Icône)
        self.load_window_config()
        self._setup_icon()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 3. Layout Principal
        self.setup_top_bar()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # 4. Lancement de la vue initiale
        self.show_dashboard()


    # --- Gestion de l'Interface Système ---

    def _setup_icon(self):
        """Configure l'icône de la fenêtre principale."""
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception as e:
                print(f"DEBUG: Icon error: {e}")

    def load_window_config(self):
        """Initialise la taille et la position de la fenêtre via le ConfigManager."""
        data = self.config_manager.get_section("window_settings")
        
        default_geom = "1300x900+50+50"
        geom = data.get("geometry", default_geom)
        
        # Validation et application de la géométrie
        self.geometry(self._validate_geometry(geom))
        
        # Application de l'état agrandi si nécessaire
        if data.get("is_maximized", False):
            self.after(100, lambda: self.state('zoomed'))

    def save_window_config(self):
            """Récupère l'état actuel et le transmet au manager pour sauvegarde."""
            # On vérifie l'état 'zoomed' (Windows) ou l'attribut zoomed
            is_zoomed = self.state() == "zoomed"
            
            window_data = {"is_maximized": is_zoomed}
            
            if is_zoomed:
                old_geom = self.config_manager.get_item("window_settings", "geometry", "1300x900+50+50")
                window_data["geometry"] = old_geom
            else:
                # SI NORMAL : On sauvegarde la géométrie actuelle
                window_data["geometry"] = self.geometry()

            self.config_manager.set_section("window_settings", window_data)
            self.config_manager.save()

    def _validate_geometry(self, geom_string):
        """Empêche la fenêtre de s'ouvrir hors des limites de l'écran."""
        try:
            parts = geom_string.replace('x', '+').split('+')
            w, h, x, y = map(int, parts)
            
            # On vérifie si le coin haut-gauche est visible
            if x < 0 or y < 0 or x > self.winfo_screenwidth() - 100 or y > self.winfo_screenheight() - 100:
                return "1300x900+50+50"
            return geom_string
        except:
            return "1300x900+50+50"

    # --- Gestion du Routage (Vues) ---

    def _clear_container(self):
        """Nettoie proprement le conteneur avant de charger une nouvelle vue."""
        for widget in self.container.winfo_children():
            # Si la vue possède une méthode de nettoyage (ex: arrêt threads/timers)
            if hasattr(widget, "stop_processes"):
                try:
                    widget.stop_processes()
                except Exception as e:
                    print(f"DEBUG: Error stopping processes: {e}")
            
            widget.pack_forget()
            widget.destroy()

    def show_dashboard(self):
        self._clear_container()
        
        self.view_title.configure(text=self.texts.get("dashboard", "DASHBOARD"))
        
        from gui.views.dashboard_view import DashboardView
        self.current_view = DashboardView(self.container, self)
        self.current_view.pack(fill="both", expand=True)

    def show_raster_mode(self, image_to_load=None, reset_filters=False):
        self._clear_container()
        self.set_topbar_title(self.texts.get("raster", "Raster engraving"))

        from gui.views.raster_view import RasterView
        
        view = RasterView(self.container, self)
        view.pack(fill="both", expand=True)
        
        if image_to_load:
            view.input_image_path = image_to_load
            if reset_filters:
                # Accès direct aux sliders de la vue
                if "gamma" in view.controls: view.controls["gamma"]["slider"].set(1.0)
                if "thermal" in view.controls: view.controls["thermal"]["slider"].set(1.0)
            view.update_preview()
        
        self.current_view = view

    def show_settings_mode(self, just_saved=False):
        self._clear_container()
        
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})
        
        title_text = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["settings"]["title"]
        self.view_title.configure(text=title_text)
        
        # Mettre à jour les boutons de la top_bar si nécessaire (ex: Support)
        self.btn_support.configure(text=self.texts.get("support", "Support"))
        self.dev_label.configure(text=self.texts.get("credits", "By MoMo"))

        from gui.views.settings_view import SettingsView 
        self.current_view = SettingsView(self.container, self, just_saved=just_saved)
        self.current_view.pack(expand=True, fill="both")

    
    def show_calibration_mode(self):
        self._clear_container()
        self.set_topbar_title(self.texts.get("calibration", "Machine calibration"))
        from gui.views.calibration_view import CalibrationView
        self.current_view = CalibrationView(self.container, self)
        self.current_view.pack(expand=True, fill="both")

    def show_simulation(self, engine, payload, return_view="dashboard"):
        self._clear_container()
        self.set_topbar_title(self.texts.get("simulation", "G-Code Simulation"))
        from gui.views.simulation_view import SimulationView
        self.current_view = SimulationView(self.container, self, engine, payload, return_view)
        self.current_view.pack(fill="both", expand=True)

    # --- Composants UI Fixes ---



    def setup_top_bar(self):
        """Crée la barre supérieure permanente avec liens de support."""
        self.top_bar = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.top_bar.pack(side="top", fill="x")

        # Bouton Home
        home_image = ctk.CTkImage(
            light_image=Image.open(os.path.join(self.assets_dir, "home_black.png")),
            dark_image=Image.open(os.path.join(self.assets_dir, "home_white.png")),
            size=(20, 20) # Ajuste la taille selon tes besoins
        )
        self.home_btn = ctk.CTkButton(
            self.top_bar, image=home_image, text="", width=50, fg_color="transparent", 
            hover_color=["#DCDCDC", "#323232"], command=self.show_dashboard
        )
        self.home_btn.pack(side="left", padx=5)

        # UNIQUE INDICATEUR DE TITRE
        # On le crée ici et on ne le recréera JAMAIS ailleurs
        self.view_title = ctk.CTkLabel(
            self.top_bar, 
            text="", # Texte vide au départ
            font=("Arial", 13, "bold")
        )
        self.view_title.pack(side="left", padx=20)

        # --- PARTIE DROITE ---
        # Bouton Settings (le plus à droite)
        self.settings_btn = ctk.CTkButton(
            self.top_bar, text="⚙️", width=40, fg_color="transparent", 
            command=self.show_settings_mode
        )
        self.settings_btn.pack(side="right", padx=10)

        # Séparateur visuel vertical
        ctk.CTkLabel(self.top_bar, text="|", text_color="gray").pack(side="right", padx=5)

        # Lien GitHub
        self.btn_github = ctk.CTkButton(
            self.top_bar, text="🌐 GitHub", width=80, fg_color="transparent",
            font=("Arial", 11), text_color=["#3B8ED0", "#1F6AA5"],
            hover_color=["#DCDCDC", "#323232"], cursor="hand2",
            command=lambda: webbrowser.open("https://github.com/MoMo830/ALIG")
        )
        self.btn_github.pack(side="right", padx=5)

        # Bouton Support 
        self.btn_support = ctk.CTkButton(
            self.top_bar, text=self.texts.get("support", "Support"), width=90, height=28,
            fg_color="#FFDD00", text_color="black", font=("Arial", 11, "bold"),
            hover_color="#f7d000", cursor="hand2",
            command=lambda: webbrowser.open("https://buymeacoffee.com/momo830")
        )
        self.btn_support.pack(side="right", padx=5)

        # Crédit Développeur (Traduit et Discret)
        self.dev_label = ctk.CTkLabel(
            self.top_bar, 
            text=self.texts.get("credits", "By MoMo"), 
            font=("Arial", 9), 
            text_color="#666666"
        )
        self.dev_label.pack(side="right", padx=15)

    def set_topbar_title(self, title_text):
        # Si le label n'existe pas ou a été détruit par erreur
        if not hasattr(self, 'view_title') or not self.view_title.winfo_exists():
            self.view_title = ctk.CTkLabel(
                self.top_bar, 
                text=title_text,
                font=("Arial", 13, "bold")
            )
            # On le place après le bouton home (index 1 car home est à l'index 0)
            self.view_title.pack(side="left", padx=20, before=self.btn_support if hasattr(self, 'btn_support') else None)
        else:
            # S'il existe, on change juste le texte
            self.view_title.configure(text=title_text)

    def on_closing(self):
        """Gère la fermeture propre."""
        try:
            # 1. SAUVEGARDER D'ABORD (pendant que la fenêtre est encore active)
            self.save_window_config()
            
            # 2. Ensuite on cache et on nettoie
            self.withdraw()
            self._clear_container()
            
            self.quit()
            self.after(100, self.destroy)
        except Exception as e:
            print(f"Error during closing: {e}")
            self.destroy()

    def _final_destroy(self):
        """Action finale de destruction."""
        self.quit()
        self.destroy()