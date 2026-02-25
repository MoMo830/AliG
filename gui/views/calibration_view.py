import customtkinter as ctk
import os
from PIL import Image, ImageDraw
from core.utils import get_app_paths
from engine.calibrate_engine import CalibrateEngine
from core.translations import TRANSLATIONS
from utils.paths import LATENCY_LIGHT, LATENCY_DARK, LATENCY_EXPLAIN_LIGHT, LATENCY_EXPLAIN_DARK, POWER_EXPLAIN_DARK, POWER_EXPLAIN_LIGHT
from utils.paths import LINESTEP_DARK, LINESTEP_LIGHT, POWER_COM, LINESTEP_EXPLAIN_DARK, LINESTEP_EXPLAIN_LIGHT

class CalibrationView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.calibrate_engine = CalibrateEngine()
        self.base_path, self.application_path = get_app_paths()
        self.config_manager = controller.config_manager 
        
        # --- 1. DÉFINITION DES STYLES ---
        self.accent_color = "#e67e22" 
        self.color_selected = ["#DCE4EE", "#3E454A"] 
        self.color_hover = ["#E5E5E5", "#353535"]    
        self.color_normal = ["#F2F2F2", "#2B2B2B"]   
        self.border_normal = ["#DCE4EE", "#3E454A"]
        self._last_calc_ms = 0.0

        # --- 2. GESTION DES TRADUCTIONS ---
        lang = self.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["calibration"]
        
        # --- 3. STRUCTURE PRINCIPALE ---
        self.main_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.main_grid.pack(expand=True, fill="both", padx=30, pady=20)
        
        self.main_grid.grid_columnconfigure(0, weight=0)
        self.main_grid.grid_columnconfigure(1, weight=1)
        self.main_grid.grid_rowconfigure(0, weight=1)

        # Sidebar (Gauche) - Utilisation de couleurs assorties au fond pour "cacher" la scrollbar
        self.left_column = ctk.CTkScrollableFrame(self.main_grid, fg_color="transparent", width=420)
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.left_column.grid_columnconfigure(0, weight=1)

        # Ajoutez cette sécurité pour être sûr que la barre ne prend pas de place
        try:
            self.left_column._scrollbar.configure(width=0)
        except:
            pass
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        # Tentative sécurisée de réduction de la largeur de la scrollbar
        try:
            if hasattr(self.left_column, "_scrollbar"):
                self.left_column._scrollbar.configure(width=0)
        except:
            pass

        ctk.CTkLabel(self.left_column, text=self.texts["sidebar_title"], 
                     font=("Arial", 18, "bold"), text_color=self.accent_color, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=15)

        # Conteneur des cartes avec configuration de colonne pour l'extension
        self.cards_container = ctk.CTkFrame(self.left_column, fg_color="transparent")
        self.cards_container.grid(row=1, column=0, sticky="nsew")
        self.cards_container.grid_columnconfigure(0, weight=1)

        # Zone de test (Droite)
        self.right_column = ctk.CTkFrame(self.main_grid, fg_color=["#EBEBEB", "#202020"], corner_radius=15)
        self.right_column.grid(row=0, column=1, sticky="nsew")

        self.desc_title = ctk.CTkLabel(self.right_column, font=("Arial", 30, "bold"), text_color=self.accent_color)
        self.desc_title.pack(pady=(40, 10), padx=40, anchor="w")

        # --- BLOC DESCRIPTION & ILLUSTRATION ---
        self.desc_info_row = ctk.CTkFrame(self.right_column, fg_color="transparent")
        self.desc_info_row.pack(fill="x", padx=40, pady=10)

        # Ratio 
        self.desc_info_row.grid_columnconfigure(0, weight=5)
        self.desc_info_row.grid_columnconfigure(1, weight=5, minsize=180)

        # TEXTE
        self.desc_text = ctk.CTkLabel(
            self.desc_info_row,
            font=("Arial", 15),
            justify="left",
            anchor="nw"
        )
        self.desc_text.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        # IMAGE
        self.illustration_label = ctk.CTkLabel(self.desc_info_row, text="")
        self.illustration_label.grid(row=0, column=1, sticky="nsew")

        # Wrap auto du texte
        self.desc_text.bind(
            "<Configure>",
            lambda e: self.desc_text.configure(
                wraplength=self.desc_text.winfo_width() - 15
            )
        )

        # Resize global du bloc
        self.desc_info_row.bind("<Configure>", self._on_desc_row_resize)

        # --- ZONE DYNAMIQUE (C'est elle qu'on vide) ---
        self.dynamic_params_frame = ctk.CTkFrame(self.right_column, fg_color="transparent")
        self.dynamic_params_frame.pack(fill="both", expand=True, padx=40)

        # Bouton d'action fixe en bas
        self.create_action_button()

        # --- 4. CHARGEMENT DES DONNÉES ---
        self.selected_test = None
        self.setup_calibration_data()
        self.show_default_message()

    def show_default_message(self):
        """Affiche le titre par défaut et invite à choisir un test."""
        self.clear_dynamic_zone()
        
        # On utilise le message du dictionnaire
        self.desc_title.configure(text=self.texts.get("sidebar_title", "Calibration"))
        self.desc_text.configure(text=self.texts.get("default_title", "Select a test to begin"))
        
        # On cache l'image et le bouton d'action tant qu'aucun test n'est choisi
        self.illustration_label.configure(image=None, text="")
        if hasattr(self, "action_btn"):
            self.action_btn.pack_forget()
        

    def clear_dynamic_zone(self):
        """Nettoie la zone des paramètres et réinitialise l'image d'illustration."""
        for widget in self.dynamic_params_frame.winfo_children():
            widget.destroy()
        
        # Réinitialisation propre pour CTk
        if hasattr(self, "illustration_label") and self.illustration_label.winfo_exists():
            # On retire l'image et le texte
            self.illustration_label.configure(image=None, text="")
            # On force le widget à oublier l'image précédente en mémoire
            self.illustration_label.image = None


    def latency_test_window(self):
        """Isole et construit les paramètres spécifiques au test de Latence."""
        # On nettoie uniquement la zone dynamique pour éviter de casser les labels de titre/desc
        self.clear_dynamic_zone()

        self.action_btn.pack(side="bottom", pady=40, padx=40, fill="x")

        # --- CONTAINER DES PARAMÈTRES (Saisie) ---
        self.settings_container = ctk.CTkFrame(self.dynamic_params_frame, fg_color=["#DCE4EE", "#2B2B2B"], corner_radius=10)
        self.settings_container.pack(fill="x", pady=10)
        
        self.params_grid = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        self.params_grid.pack(fill="x", padx=15, pady=15)

        # Ligne 0 : Feedrate & Latency  
        ctk.CTkLabel(self.params_grid, text=self.texts.get("feedrate_calc", "Feedrate (mm/min):")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.speed_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.speed_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ctk.CTkLabel(self.params_grid, text=self.texts.get("latency_calc", "Latency (ms):")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.latency_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.latency_entry.grid(row=0, column=3, pady=5)

        # Info calculée mm
        self.mm_info_label = ctk.CTkLabel(self.params_grid, text="= 0.000 mm", font=("Arial", 12, "bold"), text_color="#1f538d")
        self.mm_info_label.grid(row=0, column=4, padx=(10, 0), sticky="w")

        # Ligne 1 : Power & Info Mode  
        ctk.CTkLabel(self.params_grid, text=self.texts.get("power_pct", "Power (%):")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.power_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.power_entry.grid(row=1, column=1, padx=5, pady=5)

        # Label d'information sur le mode de tir (S ou M67)
        self.fire_mode_info = ctk.CTkLabel(self.params_grid, text="", font=("Arial", 11), text_color="gray")
        self.fire_mode_info.grid(row=1, column=2, columnspan=3, padx=10, sticky="w")

        # --- CALCULATRICE (Aide au réglage) ---
        self.calc_container = ctk.CTkFrame(self.dynamic_params_frame, fg_color=["#DCE4EE", "#2B2B2B"], corner_radius=10)
        self.calc_container.pack(fill="x", pady=10)
        
        self.calc_header = ctk.CTkLabel(
            self.calc_container, 
            text=self.texts.get("latency_calculator", "Latency Calculator (from measurement):"),
            font=("Arial", 13, "bold"), 
            text_color=self.accent_color
        )
        self.calc_header.pack(padx=15, pady=(10, 5), anchor="w")

        self.calc_grid = ctk.CTkFrame(self.calc_container, fg_color="transparent")
        self.calc_grid.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(self.calc_grid, text=self.texts.get("measured_offset", "Measured Offset (mm):")).grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.measured_mm_entry = ctk.CTkEntry(self.calc_grid, width=100, placeholder_text="ex: 0.25")
        self.measured_mm_entry.grid(row=0, column=1, sticky="w")

        self.calc_result_label = ctk.CTkLabel(
            self.calc_grid, 
            text=f"{self.texts.get('latency_results', 'Result:')} -- ms", 
            font=("Arial", 12, "bold"), 
            text_color=self.accent_color
        )
        self.calc_result_label.grid(row=0, column=2, padx=(15, 0), sticky="w")

        self.save_latency_btn = ctk.CTkButton(self.calc_grid, text=self.texts.get("apply_save", "Apply & Save"), width=120, height=28, command=self.apply_calculated_latency)
        self.save_latency_btn.grid(row=0, column=3, padx=(20, 0), sticky="w")

        self.calc_hint_label = ctk.CTkLabel(self.calc_container, text="", font=("Arial", 11, "italic"), text_color="gray")
        self.calc_hint_label.pack(padx=15, pady=(0, 10), anchor="w")

        # --- BINDINGS ---
        self.measured_mm_entry.bind("<KeyRelease>", lambda e: self.update_latency_calculation())
        self.speed_entry.bind("<KeyRelease>", lambda e: (self.update_latency_calculation(), self.update_mm_display()), add="+")
        self.latency_entry.bind("<KeyRelease>", lambda e: self.update_mm_display())

 

    def power_test_window(self):
        """Construit les éléments du test de Puissance."""
        self.clear_dynamic_zone()

        
        self.power_container = ctk.CTkFrame(self.dynamic_params_frame, fg_color=["#DCE4EE", "#2B2B2B"], corner_radius=10)
        self.power_container.pack(fill="x", pady=20)
        
        ctk.CTkLabel(self.power_container, text="Power test specific settings...").pack(pady=20)

    def linestep_window(self):
        """Construit les éléments du test de Line Step."""
        self.clear_dynamic_zone()

        
        self.ls_container = ctk.CTkFrame(self.dynamic_params_frame, fg_color=["#DCE4EE", "#2B2B2B"], corner_radius=10)
        self.ls_container.pack(fill="x", pady=20)
        
        ctk.CTkLabel(self.ls_container, text="Line step test specific settings...").pack(pady=20)
        


    def create_action_button(self):
        """Crée le bouton d'action commun en bas de la colonne droite."""
        self.action_btn = ctk.CTkButton(self.right_column, text=self.texts["btn_prepare"], font=("Arial", 16, "bold"),
                                        fg_color=self.accent_color, hover_color="#d35400", height=52)
        self.action_btn.pack(side="bottom", pady=40, padx=40, fill="x")

    def create_calibration_card(self, test, index):
        self.cards_container.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self.cards_container, corner_radius=15, border_width=2, 
                            fg_color=self.color_normal, border_color=self.border_normal)

        card.grid(row=index, column=0, padx=(15, 32), pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        test["card_widget"] = card

        # --- LOGIQUE D'AFFICHAGE DE L'ICÔNE ---
        if test.get("is_image"):
            # Si c'est une image (notre PNG d'Inkscape)
            icon_lbl = ctk.CTkLabel(card, text="", image=test["icon"])
        else:
            # Si c'est encore un emoji
            icon_lbl = ctk.CTkLabel(card, text=test["icon"], font=("Arial", 35))

        icon_lbl.grid(row=0, column=0, padx=20, pady=20)

        txt_frame = ctk.CTkFrame(card, fg_color="transparent")
        txt_frame.grid(row=0, column=1, padx=(0, 20), pady=15, sticky="w")
        
        t_lbl = ctk.CTkLabel(txt_frame, text=test["title"], font=("Arial", 15, "bold"), anchor="w")
        t_lbl.pack(fill="x")
        
        d_lbl = ctk.CTkLabel(txt_frame, text=test["short"], font=("Arial", 12), text_color="gray", anchor="w")
        d_lbl.pack(fill="x")

        widgets = [card, icon_lbl, txt_frame, t_lbl, d_lbl]
        
        def on_enter(e):
            if getattr(self, "selected_test", None) != test:
                card.configure(fg_color=self.color_hover, border_color=self.accent_color)

        def on_leave(e):
            if getattr(self, "selected_test", None) != test:
                card.configure(fg_color=self.color_normal, border_color=self.border_normal)
            else:
                card.configure(fg_color=self.color_selected, border_color=self.accent_color)

        for w in widgets:
            w.configure(cursor="hand2")
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e, t=test: self.update_detail_view(t))

    def setup_calibration_data(self):
        latency_img = ctk.CTkImage(light_image=LATENCY_LIGHT, dark_image=LATENCY_DARK, size=(35, 35))
        linestep_img = ctk.CTkImage(light_image=LINESTEP_LIGHT, dark_image=LINESTEP_DARK, size=(35, 35))
        power_img = ctk.CTkImage(light_image=POWER_COM, dark_image=POWER_COM, size=(35, 35))
        # Images plus grandes pour la description
        latency_explain = ctk.CTkImage(light_image=LATENCY_EXPLAIN_LIGHT, dark_image=LATENCY_EXPLAIN_DARK, size=(500, 100))
        linestep_explain = ctk.CTkImage(light_image=LINESTEP_EXPLAIN_LIGHT, dark_image=LINESTEP_EXPLAIN_DARK, size=(500, 100))
        power_explain = ctk.CTkImage(light_image=POWER_EXPLAIN_LIGHT, dark_image=POWER_EXPLAIN_DARK, size=(500, 100))

        self.test_list = [
            {
                "title": self.texts["latency_title"],
                "short": self.texts["latency_short"],
                "long": self.texts["latency_long"],
                "params": "",
                "icon": latency_img,
                "preview": latency_explain,
                "img_ratio": 5.0,
                "is_image": True,
                "callback": self.run_latency_test
            },
            {
                "title": self.texts["linestep_title"],
                "short": self.texts["linestep_short"],
                "long": self.texts["linestep_long"],
                "icon": linestep_img,
                "preview": linestep_explain,
                "img_ratio": 5.0,
                "is_image": True,
                "callback": self.linestep_window
            },
            {
                "title": self.texts["power_title"],
                "short": self.texts["power_short"],
                "long": self.texts["power_long"],
                "params": "• Steps: 10 levels\n• Power Range: 0-100%\n• Variable: S-Mode / M67",
                "icon": power_img,
                "preview": power_explain,
                "img_ratio": 5.0,
                "is_image": True,
                "callback": self.power_test_window
            }
        ]

        for i, test in enumerate(self.test_list):
            self.create_calibration_card(test, i)

    def update_detail_view(self, test):
        """Sélectionne le test et délègue la configuration selon le type."""
        # 1. Visuel de la sidebar
        self._update_sidebar_selection(test)

        # 2. Reset du bouton d'action
        self.action_btn.configure(text=self.texts["btn_prepare"], fg_color=self.accent_color)

        # 3. DÉLÉGATION PAR TEST
        title = test["title"]
        
        if title == self.texts["latency_title"]:
            self._setup_latency_test_logic()
            
        elif title == self.texts.get("power_title", "Power Test"):
            self._setup_power_test_logic()

        elif title == self.texts.get("linestep_title", "Line Step"):
            self._setup_linestep_test_logic()

        # 4. Mise à jour des textes et images communs
        self._update_description_zone(test)



    def _setup_latency_test_logic(self):
        """Regroupe toute la logique spécifique au test de latence."""
        # Affichage des widgets de calcul/champs
        self.latency_test_window() 
        
        # Liaison de l'action de génération
        self.action_btn.configure(command=self.validate_and_generate)
        
        # Chargement des données de configuration (Vitesse, Mode, etc.)
        cfg = self.config_manager
        cmd_mode = cfg.get_item("machine_settings", "cmd_mode", "Unknown")
        is_s_mode = "S (" in cmd_mode
        
        if hasattr(self, "speed_entry") and self.speed_entry.winfo_exists():
            self.speed_entry.delete(0, "end")
            self.speed_entry.insert(0, str(cfg.get_item("machine_settings", "base_feedrate", 3000)))
        
        if hasattr(self, "latency_entry") and self.latency_entry.winfo_exists():
            self.latency_entry.delete(0, "end")
            self.latency_entry.insert(0, "0.0")

        # Mise à jour des infos dynamiques sur le mode de tir
        info = f"Mode: {cmd_mode} | Max: {cfg.get_item('machine_settings', 'ctrl_max', '??')}"
        if not is_s_mode:
            info += f" | M67 Reg: {cfg.get_item('machine_settings', 'm67_e_num', '??')}"
        
        if hasattr(self, "fire_mode_info") and self.fire_mode_info.winfo_exists():
            self.fire_mode_info.configure(text=info)

        self.update_mm_display()

    def _setup_power_test_logic(self):
        """Logique pour le test de puissance."""
        self.power_test_window()
        self.action_btn.configure(command=self.run_power_test)

    def _setup_linestep_test_logic(self):
        """Logique pour le test d'intervalle de lignes."""
        self.linestep_window()
        # self.action_btn.configure(command=self.votre_methode)

    def _update_sidebar_selection(self, test):
        """Gère l'apparence visuelle des cartes lors du changement de sélection."""
        # Désélection de l'ancienne carte (si elle existe)
        if hasattr(self, "selected_test") and self.selected_test:
            try:
                if self.selected_test["card_widget"].winfo_exists():
                    self.selected_test["card_widget"].configure(
                        fg_color=self.color_normal, 
                        border_color=self.border_normal
                    )
            except Exception: 
                pass

        # Mise à jour de la référence et sélection visuelle de la nouvelle
        self.selected_test = test
        if "card_widget" in test and test["card_widget"].winfo_exists():
            test["card_widget"].configure(
                fg_color=self.color_selected,
                border_color=self.accent_color 
            )

    def _update_description_zone(self, test):
        """Met à jour le titre, le texte et l'image."""
        self.desc_title.configure(text=test.get("title", ""))
        self.desc_text.configure(text=test.get("long", ""))

        preview = test.get("preview")

        if preview:
            self.illustration_label.configure(image=preview, text="")
        else:
            self.illustration_label.configure(image=None, text="")

        # Force un resize immédiat propre
        self.after(10, self._on_desc_row_resize)

    def run_latency_test(self):
        try:
            # 1. Récupération des valeurs saisies par l'utilisateur
            user_speed = float(self.speed_entry.get())
            user_latency = float(self.latency_entry.get())
            
            # 2. Récupération automatique du mode de feu (Settings)
            cfg = self.controller.config_manager
            use_s_mode = cfg.get_item("machine_settings", "use_s_mode", False)
            
            settings = {
                "power": cfg.get_item("calibration", "test_power", 30.0),
                "feedrate": user_speed, # Valeur choisie par l'user
                "latency": user_latency, # Valeur choisie par l'user
                "use_s_mode": use_s_mode, # Pris dans les settings auto
                "e_num": cfg.get_item("machine_settings", "e_num", 0),
                "header": cfg.get_item("gcode_options", "header", ""),
                "footer": cfg.get_item("gcode_options", "footer", "M30")
            }

            # 3. Génération (Engine)
            gcode_content = self.calibrate_engine.generate_latency_calibration(settings)

            # 4. Sauvegarde
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".nc",
                initialfile=f"test_latence_{user_latency}ms.nc",
                title="Enregistrer le G-Code"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(gcode_content)
                
        except ValueError:
            # Si l'utilisateur a tapé des lettres au lieu de chiffres
            print("Erreur : Veuillez entrer des nombres valides pour la vitesse et la latence.")
        except Exception as e:
            print(f"Erreur lors de la génération : {e}")
            
    def update_mm_display(self):
        """Calcule et affiche dynamiquement le décalage en mm."""
        try:
            # On récupère les valeurs, défaut à 0.0 si vide ou invalide
            raw_speed = self.speed_entry.get().strip()
            raw_latency = self.latency_entry.get().strip()
            
            speed = float(raw_speed) if raw_speed else 0.0
            latency = float(raw_latency) if raw_latency else 0.0
            
            # Formule : (Feed * Latency) / 60000
            offset_mm = (speed * latency) / 60000.0
            
            # Mise à jour du texte avec 3 décimales
            self.mm_info_label.configure(text=f"= {offset_mm:.3f} mm")
            
            # Optionnel : changer la couleur si l'offset est très grand (alerte)
            if abs(offset_mm) > 2.0:
                self.mm_info_label.configure(text_color="#e74c3c") # Rouge
            else:
                self.mm_info_label.configure(text_color="#1f538d") # Bleu standard
                
        except ValueError:
            # En cas d'erreur de saisie (ex: "12.5.2")
            self.mm_info_label.configure(text="= --- mm", text_color="gray")

    def run_power_test(self):
        block_size, num_steps = 50, 10
        img = Image.new('L', (block_size * num_steps, block_size), color=255)
        draw = ImageDraw.Draw(img)
        for i in range(num_steps):
            gray_level = int(255 - (i * (255 / (num_steps - 1))))
            draw.rectangle([(i * block_size) + 5, 0, ((i + 1) * block_size) - 5, block_size], fill=gray_level)
        temp_path = os.path.join(self.application_path, "ALIG_POWER_TEST.png")
        img.save(temp_path)
        self.controller.show_raster_mode(image_to_load=temp_path, reset_filters=True)

    def validate_and_generate(self, test):
        """Valide, génère et propose l'enregistrement direct du G-Code."""
        power_raw = self.power_entry.get().strip()
        
        # 1. Validation : Champ puissance vide
        if not power_raw:
            self.show_error_feedback("⚠️ Power Required!")
            return

        try:
            cfg = self.controller.config_manager
            cmd_mode = cfg.get_item("machine_settings", "cmd_mode", "")
            
            # Détection identique pour l'engine
            use_s_mode_bool = "S (" in cmd_mode

            settings = {
                "power": float(self.power_entry.get().strip()),
                "max_value": float(cfg.get_item("machine_settings", "ctrl_max", None)),
                "feedrate": float(self.speed_entry.get()),
                "latency": float(self.latency_entry.get()),
                "e_num": int(cfg.get_item("machine_settings", "m67_e_num", None)),
                "use_s_mode": use_s_mode_bool, # Envoie True ou False
                "header": cfg.get_item("gcode_options", "header", None),
                "footer": cfg.get_item("gcode_options", "footer", None)
            }

            # 3. Génération directe via le moteur local
            gcode_content = self.calibrate_engine.generate_latency_calibration(settings)
            
            # 4. Ouverture de la boîte de dialogue de sauvegarde (Directe)
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".nc",
                initialfile=f"latency_test_{settings['latency']}ms.nc",
                title="Save Calibration G-Code"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(gcode_content)
                # Optionnel : petit feedback de succès sur le bouton
                self.action_btn.configure(text="✅ G-Code Saved!", fg_color="#27AE60")
                self.after(2000, lambda: self.action_btn.configure(
                    text=self.texts["btn_prepare"], 
                    fg_color=self.accent_color
                ))

        except ValueError:
            self.show_error_feedback("⚠️ Invalid Numbers!")
        except Exception as e:
            print(f"Error during generation: {e}")
            self.show_error_feedback("⚠️ Generation Error")

    def update_latency_calculation(self):
        """Calculates latency and indicates whether to increase (+) or decrease (-) the value."""
        try:
            raw_speed = self.speed_entry.get().strip()
            raw_mm = self.measured_mm_entry.get().strip()
            
            speed = float(raw_speed) if raw_speed else 0.0
            dist_mm = float(raw_mm) if raw_mm else 0.0
            
            if speed > 0 and dist_mm != 0:
                # Formula: ms = (mm * 60000) / speed
                calculated_ms = (dist_mm * 60000.0) / speed
                self._last_calc_ms = calculated_ms

                if dist_mm > 0:
                    # Trait is too far to the right
                    status = f"(+) {calculated_ms:.2f} ms"
                    hint = "Late firing: Increase latency (+)"
                    color = "#e67e22" # Orange
                else:
                    # Trait is too far to the left
                    status = f"(-) {abs(calculated_ms):.2f} ms"
                    hint = "Early firing: Decrease latency (-)"
                    color = "#3498db" # Blue

                self.calc_result_label.configure(text=f"{self.texts.get('latency_results', 'Result:')} {status}", text_color=color)
                self.calc_hint_label.configure(text=f"ℹ️ {hint}")
            
            elif dist_mm == 0:
                # Affiche "Result: 0.00 ms" en utilisant la traduction
                self.calc_result_label.configure(
                    text=f"{self.texts.get('latency_results', 'Result:')} 0.00 ms", 
                    text_color="gray"
                )
                # Affiche "Perfectly aligned" traduit
                self.calc_hint_label.configure(
                    text=self.texts.get("latency_perfect", "Perfectly aligned")
                )
            else:
                # Réinitialisation si la valeur est invalide
                self.calc_result_label.configure(
                    text=f"{self.texts.get('latency_results', 'Result:')} -- ms", 
                    text_color="gray"
                )
                self.calc_hint_label.configure(text="")
                
        except ValueError:
            self.calc_result_label.configure(text="Result: Error", text_color="#e74c3c")
            self.calc_hint_label.configure(text="⚠️ Please enter a valid number (use dots, not commas)")

    def apply_calculated_latency(self):
        """Injecte la valeur calculée dans le champ principal et sauvegarde dans la config."""
        try:
            val_ms = getattr(self, "_last_calc_ms", None)
            if val_ms is not None:
                # 1. Mise à jour de l'UI
                self.latency_entry.delete(0, "end")
                self.latency_entry.insert(0, f"{val_ms:.2f}")
                self.update_mm_display() # Rafraîchit l'affichage du haut
                
                # 2. Sauvegarde persistante dans le config_manager
                self.config_manager.set_item("machine_settings", "m67_delay", round(val_ms, 3))
                self.config_manager.save_config()
                
                # Feedback visuel
                self.save_latency_btn.configure(text="Saved!", fg_color="#27AE60")
                self.after(1500, lambda: self.save_latency_btn.configure(text="Apply & Save", fg_color=self.accent_color))
        except Exception as e:
            print(f"Error saving latency: {e}")

    def _on_desc_row_resize(self, event=None):
        """Resize dynamique avec une part plus large pour l'image."""
        if not getattr(self, "selected_test", None):
            return

        preview = self.selected_test.get("preview")
        if not preview:
            return

        total_width = self.desc_info_row.winfo_width()
        if total_width <= 1:
            return

        # --- MODIFICATIONS ICI ---
        # On passe à 45% de la largeur totale
        # On augmente la limite max à 600px (au lieu des 350-400 précédents)
        target_width = min(int(total_width * 0.45), 600) 

        ratio = self.selected_test.get("img_ratio", 5.0)
        target_height = int(target_width / ratio)

        new_size = (target_width, target_height)

        # Mise à jour uniquement si la taille a réellement changé
        if preview._size != new_size:
            preview.configure(size=new_size)


    
    def _on_desc_row_resize(self, event=None):
        if not getattr(self, "selected_test", None):
            return

        preview = self.selected_test.get("preview")
        if not preview:
            return

        total_width = self.desc_info_row.winfo_width()
        if total_width <= 1:
            return

        ratio = self.selected_test.get("img_ratio", 5.0)

        # 30% strict pour l'image
        target_width = int(total_width * 0.30)
        target_height = int(target_width / ratio)

        new_size = (target_width, target_height)

        if preview._size != new_size:
            preview.configure(size=new_size)

    def show_error_feedback(self, message="⚠️ Check Parameters"):
        """Animation visuelle du bouton en cas d'erreur."""
        # Sauvegarde des états actuels
        old_text = self.action_btn.cget("text")
        old_fg = self.action_btn.cget("fg_color")
        old_hover = self.action_btn.cget("hover_color")
        
        # Affichage de l'erreur
        self.action_btn.configure(
            text=message, 
            fg_color="#E74C3C", 
            hover_color="#C0392B"
        )
        
        # Retour à la normale après 2s
        self.after(2000, lambda: self.action_btn.configure(
            text=old_text, 
            fg_color=old_fg,
            hover_color=old_hover
        ))
