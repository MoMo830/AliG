# -*- coding: utf-8 -*-
import os
import customtkinter as ctk
from tkinter import messagebox

class LaserGeneratorApp(ctk.CTk):
    def __init__(self, config_manager):
        super().__init__()
        
        # 1. Ressources et Configuration
        self.config_manager = config_manager
        self.version = "0.9782b"
        self.title(f"A.L.I.G. - Advanced Laser Imaging Generator v{self.version}")
        self.current_view = None
        
        # 2. Configuration Système (Fenêtre & Icône)
        self.load_window_config()
        self._setup_icon()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 3. Layout Principal
        # La barre supérieure reste fixe
        self.setup_top_bar()

        # Le conteneur qui accueillera dynamiquement les différentes vues
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # 4. Lancement de la vue initiale
        self.show_dashboard()

    # --- Gestion de l'Interface Système ---

    def _setup_icon(self):
        """Configure l'icône de la fenêtre principale."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Ajustez le chemin selon votre structure (ici remonte d'un cran vers assets)
        self.icon_path = os.path.normpath(os.path.join(current_dir, "..", "assets", "icone_alig.ico"))
        
        if os.path.exists(self.icon_path):
            try:
                # iconbitmap fonctionne principalement sur Windows
                self.iconbitmap(self.icon_path)
            except Exception as e:
                print(f"DEBUG: Icon error (non-critical): {e}")

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
        is_zoomed = (self.state() == "zoomed")
        
        window_data = {"is_maximized": is_zoomed}
        
        # On ne stocke la géométrie précise que si on n'est pas en plein écran
        if not is_zoomed and self.state() == "normal":
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
        self.view_title.configure(text="Home")
        from gui.views.dashboard_view import DashboardView
        self.current_view = DashboardView(self.container, self)
        self.current_view.pack(fill="both", expand=True)

    def show_raster_mode(self, image_to_load=None, reset_filters=False):
        self._clear_container()
        self.view_title.configure(text="Raster Engraving")
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

    def show_settings_mode(self):
        self._clear_container()
        self.view_title.configure(text="Machine Settings")
        from gui.views.settings_view import SettingsView 
        self.current_view = SettingsView(self.container, self)
        self.current_view.pack(expand=True, fill="both")

    def show_calibration_mode(self):
        self._clear_container()
        self.view_title.configure(text="Machine Calibration")
        from gui.views.calibration_view import CalibrationView
        self.current_view = CalibrationView(self.container, self)
        self.current_view.pack(expand=True, fill="both")

    def show_simulation(self, engine, payload, return_view="dashboard"):
        self._clear_container()
        self.view_title.configure(text="G-Code Simulation")
        from gui.views.simulation_view import SimulationView
        self.current_view = SimulationView(self.container, self, engine, payload, return_view)
        self.current_view.pack(fill="both", expand=True)

    # --- Composants UI Fixes ---

    def setup_top_bar(self):
        """Crée la barre supérieure permanente."""
        self.top_bar = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.top_bar.pack(side="top", fill="x")

        # Label Logo
        self.logo_label = ctk.CTkLabel(
            self.top_bar, text="A.L.I.G.", 
            font=("Arial", 18, "bold"), text_color="#e67e22"
        )
        self.logo_label.pack(side="left", padx=20)

        # Bouton Home
        self.home_btn = ctk.CTkButton(
            self.top_bar, text="🏠", width=40, fg_color="transparent", 
            hover_color=["#DCDCDC", "#323232"], command=self.show_dashboard
        )
        self.home_btn.pack(side="left", padx=5)

        # Indicateur de Titre de Vue
        self.view_title = ctk.CTkLabel(self.top_bar, text="DASHBOARD", font=("Arial", 13))
        self.view_title.pack(side="left", padx=20)

        # Bouton Settings (à droite)
        self.settings_btn = ctk.CTkButton(
            self.top_bar, text="⚙️", width=40, fg_color="transparent", 
            command=self.show_settings_mode
        )
        self.settings_btn.pack(side="right", padx=10)

    # --- Cycle de vie ---

    def on_closing(self):
        """Gère la fermeture propre de l'application."""
        try:
            # Sauvegarde de la fenêtre
            self.save_window_config()
            
            # Nettoyage des vues (timers, ports série ouverts, etc.)
            self._clear_container()
            
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"Error during closing: {e}")
            self.destroy()