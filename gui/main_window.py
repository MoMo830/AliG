import os
import customtkinter as ctk
import json


from gui.views.settings_view import SettingsView

class LaserGeneratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.version = "0.9782b"
        self.title(f"A.L.I.G. - Advanced Laser Imaging Generator v{self.version}")
        self.current_view = None
        self.config_file = "alig_config.json" 
        
        # 1. Configuration système (Icône, fenêtre, etc.)
        self.load_window_config()
        self._setup_icon()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 2. APPEL DE LA TOP BAR EN PREMIER
        # Elle sera tout en haut car c'est le premier .pack()
        self.setup_top_bar()

        # 3. LE CONTENEUR PRINCIPAL (UNE SEULE FOIS)
        # Il prendra tout l'espace restant sous la Top Bar
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # 4. Lancer le Dashboard
        self.show_dashboard()

    def _setup_icon(self):
        """Configure l'icône de la fenêtre principale."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.normpath(os.path.join(current_dir, "..", "assets", "icone_alig.ico"))
        
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception as e:
                print(f"Icon error: {e}")

    def show_dashboard(self):
        """Affiche l'écran d'accueil."""
        self._clear_container()
        self.view_title.configure(text="Home")
        from gui.views.dashboard_view import DashboardView
        view = DashboardView(self.container, self)
        view.pack(fill="both", expand=True)

    def show_raster_mode(self, image_to_load=None, reset_filters=False):
        """Affiche le Raster Mode avec optionnellement une image de calibration."""
        self._clear_container()
        self.view_title.configure(text="Raster Engraving")
        from gui.views.raster_view import RasterView
        
        view = RasterView(self.container, self)
        view.pack(fill="both", expand=True)
        
        if image_to_load:
            view.input_image_path = image_to_load
            
            # Si c'est un test de puissance, on met Gamma/Thermal à 1.0
            if reset_filters:
                if "gamma" in view.controls: view.controls["gamma"]["slider"].set(1.0)
                if "thermal" in view.controls: view.controls["thermal"]["slider"].set(1.0)
                # Ajoute ici les sync_from_slider si nécessaire
                
            view.update_preview()

    def show_simulation(self, engine, payload, return_view="dashboard"):
        """Affiche la simulation G-Code en recevant la vue de retour."""
        self._clear_container()
        self.view_title.configure(text="Simulation")
        from gui.views.simulation_view import SimulationView
        
        # On passe bien return_view à l'instanciation de la classe
        view = SimulationView(self.container, self, engine, payload, return_view)
        view.pack(fill="both", expand=True)

    def show_calibration_mode(self):
        """Bascule l'affichage vers les tests de calibration machine."""
        # 1. Nettoyer le conteneur actuel
        self._clear_container()
        self.view_title.configure(text="Machine Calibration")
        
        # 2. Import local pour éviter les imports circulaires
        from gui.views.calibration_view import CalibrationView
        
        # 3. Créer et afficher la vue
        # On utilise self.container comme défini dans ton __init__
        self.current_view = CalibrationView(self.container, self)
        self.current_view.pack(expand=True, fill="both")

    def show_settings_mode(self):
        """Bascule l'affichage vers les réglages machine."""
        # On utilise la méthode de nettoyage commune à toutes les vues
        self._clear_container()
        self.view_title.configure(text="Machine Settings")
        
        # Import local pour éviter les imports circulaires
        from gui.views.settings_view import SettingsView 
        
        # ATTENTION : Utilisez self.container (pas main_container)
        view = SettingsView(self.container, self)
        view.pack(expand=True, fill="both")
        
        # Optionnel : mettre à jour current_view si vous en avez besoin ailleurs
        self.current_view = view

    def setup_top_bar(self):
        """Crée la barre supérieure permanente"""
        self.top_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=["#EBEBEB", "#242424"])
        self.top_bar.pack(side="top", fill="x")

        # Logo / Nom à gauche
        self.logo_label = ctk.CTkLabel(self.top_bar, text="A.L.I.G.", font=("Arial", 18, "bold"), text_color="#e67e22")
        self.logo_label.pack(side="left", padx=20)

        # Bouton Home (Toujours disponible)
        self.home_btn = ctk.CTkButton(self.top_bar, text="🏠", width=40, fg_color="transparent", 
                                    hover_color=["#DCDCDC", "#323232"], command=self.show_dashboard)
        self.home_btn.pack(side="left", padx=5)

        # Indicateur de Vue Actuelle (Dynamique)
        self.view_title = ctk.CTkLabel(self.top_bar, text="DASHBOARD", font=("Arial", 13))
        self.view_title.pack(side="left", padx=20)

        # Boutons de droite
        self.settings_btn = ctk.CTkButton(self.top_bar, text="⚙️", width=40, fg_color="transparent", 
                                        command=self.show_settings_mode)
        self.settings_btn.pack(side="right", padx=10)

    def _clear_container(self):
        """Nettoie le conteneur et arrête les processus des vues si nécessaire."""
        for widget in self.container.winfo_children():
            # 1. Arrêter les timers et threads (after_cancel, etc.)
            if hasattr(widget, "stop_processes"):
                try:
                    widget.stop_processes()
                except Exception as e:
                    print(f"Error during stop_processes: {e}")
            
            # 2. Retirer immédiatement du gestionnaire de géométrie
            # Cela évite les erreurs de type 'check_dpi_scaling'
            widget.pack_forget() 
            
            # 3. Détruire l'objet
            widget.destroy()

    def load_window_config(self):
        """Lit la géométrie et l'état agrandi."""
        default_geom = "1300x900+50+50"
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    
                    # 1. On applique la géométrie fenêtrée
                    geom = data.get("window_geometry", default_geom)
                    valid_geom = self._validate_geometry(geom)
                    self.geometry(valid_geom)
                    
                    # 2. On applique l'état agrandi AVEC un léger délai
                    # C'est ce délai qui empêche la fenêtre de "sauter" en arrière
                    if data.get("is_maximized", False):
                        self.after(100, lambda: self.state('zoomed'))
                        
            except Exception as e:
                print(f"Erreur lecture config: {e}")
                self.geometry(default_geom)
        else:
            self.geometry(default_geom)

    def save_window_config(self):
        """Sauvegarde propre de l'état actuel."""
        data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
            except: pass

        # On détecte l'état
        is_zoomed = (self.state() == "zoomed")
        data["is_maximized"] = is_zoomed

        # CRUCIAL : On ne sauvegarde la géométrie que si on n'est PAS agrandi
        # Ainsi, si on réouvre l'app et qu'on quitte le mode agrandi, 
        # elle retrouvera sa taille fenêtrée d'origine.
        if not is_zoomed and self.state() == "normal":
            data["window_geometry"] = self.geometry()

        try:
            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Erreur sauvegarde config: {e}")

    def _validate_geometry(self, geom_string):
        """Vérifie si la géométrie tient dans l'écran actuel."""
        try:
            # Format attendu : "1300x900+100+100"
            parts = geom_string.replace('x', '+').split('+')
            w, h, x, y = map(int, parts)
            
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            # Si la fenêtre est hors écran ou plus grande que l'écran, on reset
            if x < 0 or y < 0 or x + 100 > screen_w or y + 100 > screen_h:
                return "1300x900+50+50"
            return geom_string
        except:
            return "1300x900+50+50"

    def on_closing(self):
        """Action à la fermeture de l'application."""
        # On sauvegarde AVANT de détruire quoi que ce soit
        self.save_window_config()
        
        # On nettoie les processus (simulation, threads, timers)
        self._clear_container()
        
        self.quit()
        self.destroy()