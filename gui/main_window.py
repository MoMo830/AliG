# -*- coding: utf-8 -*-
import os
import customtkinter as ctk
from tkinter import messagebox
from core.translations import TRANSLATIONS
import webbrowser
from PIL import Image, ImageTk
from utils import paths
import ctypes

class LaserGeneratorApp(ctk.CTk):
    def __init__(self, config_manager):
        super().__init__()

        # On cache la fenêtre immédiatement
        self.attributes('-alpha', 0)

        # 1. Ressources et Configuration
        self.config_manager = config_manager
        paths.load_all_images()

        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})

        self.version = "0.98b"
        self.title(f"A.L.I.G. - Advanced Laser Imaging Generator v{self.version}")
        self.current_view = None

        # 2. Configuration Système (Fenêtre & Icône)
        # load_window_config va définir la taille et le state('zoomed') si besoin
        self.load_window_config()
        self._setup_icon()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 3. Layout principal (préparation en arrière-plan)
        self.setup_top_bar()
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # 4. Charger la vue (le Dashboard se construit alors que la fenêtre est invisible)
        self.show_dashboard()

        # 5. RÉVÉLATION : On attend 200ms que tout soit stable avant de montrer
        self.after(200, self._reveal_window)

    def _reveal_window(self):
        """Affiche la fenêtre proprement en restaurant l'opacité."""
        # On s'assure qu'elle est bien là
        self.deiconify() 
        # On remet l'opacité à 1 (100% visible)
        self.attributes('-alpha', 1)
        self.focus_force()

    # --- Gestion de l'Interface Système ---

    def _setup_icon(self):
        """Configure l'icône de la fenêtre et force l'affichage en barre des tâches."""
        if not os.path.exists(paths.LOGO_ALIG):
            print(f"DEBUG: Icon not found at: {paths.LOGO_ALIG}")
            return

        try:
            # 1. Windows App ID (important pour barre des tâches)
            myappid = f'momo.alig.lasergenerator.{self.version}'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

            # 2. Icon fenêtre classique
            self.iconbitmap(paths.LOGO_ALIG)

            # 3. PIL load icon
            img = Image.open(paths.LOGO_ALIG)

            self.icon_photo = ImageTk.PhotoImage(img)

            self._icon_ref = self.icon_photo

            self.wm_iconphoto(True, self.icon_photo)

        except Exception as e:
            print(f"DEBUG: Icon error: {e}")

    def load_window_config(self):
        """Initialise la taille et la position de la fenêtre via le ConfigManager."""
        data = self.config_manager.get_section("window_settings")
        
        default_geom = "1300x900+50+50"
        geom = data.get("geometry", default_geom)
        
        # 1. On force Tkinter à lire les infos système (résolution, DPI)
        self.update_idletasks()
        
        # 2. On valide et on applique la géométrie
        valid_geom = self._validate_geometry(geom)
        self.geometry(valid_geom)
        
        # 3. On s'assure que la fenêtre est bien visible et non iconifiée
        self.deiconify()
        
        # 4. Application de l'état agrandi avec un délai légèrement plus long
        # Cela laisse le temps au gestionnaire de fenêtres Windows de stabiliser la position
        if data.get("is_maximized", False):
            self.after(200, lambda: self.state('zoomed'))

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
        """Empêche la fenêtre de s'ouvrir hors des limites de l'écran ou d'être invisible."""
        default_res = "1300x900+50+50"
        try:
            # Extraction des données
            parts = geom_string.replace('x', '+').split('+')
            if len(parts) < 4: return default_res
            
            w, h, x, y = map(int, parts)
            
            # On récupère la résolution actuelle
            # update_idletasks permet de rafraîchir les infos système de Tkinter
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()

            # --- SÉCURITÉS ---
            # 1. Si sw/sh sont trop petits (bug d'init), on accepte la géométrie sans valider
            if sw <= 100: return geom_string 
            
            # 2. Vérifier que la fenêtre n'est pas hors écran à droite ou en bas
            if x > sw - 100 or y > sh - 100: return default_res
            
            # 3. Vérifier que la fenêtre n'est pas perdue dans les coordonnées négatives 
            # (Sauf si x < -10 car Windows met parfois de petites marges négatives en plein écran)
            if x < -20 or y < -20: return default_res

            # 4. Vérifier que la taille n'est pas minuscule
            if w < 400 or h < 300: return default_res

            return geom_string
        except Exception as e:
            print(f"DEBUG: Erreur validation géométrie: {e}")
            return default_res

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
        # Sécurité : Si on est déjà sur le dashboard, on ne fait rien
        from gui.views.dashboard_view import DashboardView
        if isinstance(self.current_view, DashboardView):
            return

        self._clear_container()
        
        # Mise à jour du titre de la topbar
        self.view_title.configure(text=self.texts.get("dashboard", "DASHBOARD"))
        
        # Création de la vue (le __init__ de DashboardView appelle déjà load_thumbnails)
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
            light_image=paths.HOME_LIGHT,
            dark_image=paths.HOME_DARK,
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