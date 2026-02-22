import customtkinter as ctk
import os
from PIL import Image, ImageDraw
from core.utils import get_app_paths
from engine.calibrate_engine import CalibrateEngine
from core.translations import TRANSLATIONS
from utils.paths import LATENCY_LIGHT, LATENCY_DARK, LATENCY_EXPLAIN_LIGHT, LATENCY_EXPLAIN_DARK

class CalibrationView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.calibrate_engine = CalibrateEngine()
        self.base_path, self.application_path = get_app_paths()
        self.config_manager = controller.config_manager 
        
        # Maintenant cette ligne fonctionnera :
        ctrl_axis = self.config_manager.get_item("machine_settings", "controller_value_axis", "N/A")

        # --- GESTION DES TRADUCTIONS ---
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["calibration"]

        # Couleurs cohérentes
        self.color_selected = ["#DCE4EE", "#3E454A"] 
        self.color_hover = ["#E5E5E5", "#353535"]    
        self.color_normal = ["#F2F2F2", "#2B2B2B"]   
        self.border_normal = ["#DCE4EE", "#3E454A"]
        self.accent_color = "#e67e22" 
        
        # --- STRUCTURE PRINCIPALE ---
        self.main_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.main_grid.pack(expand=True, fill="both", padx=30, pady=20)
        
        self.main_grid.grid_columnconfigure(0, weight=0)
        self.main_grid.grid_columnconfigure(1, weight=1)
        self.main_grid.grid_rowconfigure(0, weight=1)

        # --- COLONNE GAUCHE ---
        self.left_column = ctk.CTkScrollableFrame(self.main_grid, fg_color="transparent", width=420)
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.left_column.grid_columnconfigure(0, weight=1)
        self.left_column._scrollbar.configure(width=0) 

        ctk.CTkLabel(self.left_column, text=self.texts["sidebar_title"], 
                     font=("Arial", 18, "bold"), text_color=self.accent_color, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=15)

        self.cards_container = ctk.CTkFrame(self.left_column, fg_color="transparent")
        self.cards_container.grid(row=1, column=0, sticky="nsew")
        self.cards_container.grid_columnconfigure(0, weight=1)

        # --- COLONNE DROITE (DÉTAILS) ---
        self.right_column = ctk.CTkFrame(self.main_grid, fg_color=["#EBEBEB", "#202020"], corner_radius=15)
        self.right_column.grid(row=0, column=1, sticky="nsew")
        
        self.desc_title = ctk.CTkLabel(self.right_column, text=self.texts["default_title"], font=("Arial", 30, "bold"), text_color=self.accent_color)
        self.desc_title.pack(pady=(40, 10), padx=40, anchor="w")

        # --- CONTAINER 1 : DESCRIPTION + IMAGE ---
        self.desc_info_row = ctk.CTkFrame(self.right_column, fg_color="transparent")
        self.desc_info_row.pack(fill="x", padx=40, pady=10)

        self.desc_text = ctk.CTkLabel(
            self.desc_info_row, 
            text=self.texts["default_desc"], 
            font=("Arial", 15), 
            justify="left", 
            anchor="nw"
        )
        self.desc_text.pack(side="left", fill="both", expand=True)
        self.desc_text.bind("<Configure>", lambda e: self.desc_text.configure(wraplength=self.desc_text.winfo_width() - 10))

        self.illustration_label = ctk.CTkLabel(self.desc_info_row, text="", width=150)
        self.illustration_label.pack(side="right", padx=(20, 0))

        # --- CONTAINER 2 : PARAMÈTRES INTERACTIFS ---
        self.settings_container = ctk.CTkFrame(self.right_column, fg_color=["#DCE4EE", "#2B2B2B"], corner_radius=10)
        self.settings_container.pack(fill="x", padx=40, pady=20)
        
        self.settings_header = ctk.CTkLabel(self.settings_container, text="G-Code Generation Settings:", font=("Arial", 13, "bold"), text_color=self.accent_color)
        self.settings_header.pack(padx=15, pady=(10, 10), anchor="w")

        # Frame pour aligner les champs de saisie
        self.params_grid = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        self.params_grid.pack(fill="x", padx=15, pady=(0, 10))

        # --- LIGNE 0 : VITESSE ET LATENCE ---
        # Champ Vitesse
        ctk.CTkLabel(self.params_grid, text="Feedrate (mm/min):", font=("Arial", 12)).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.speed_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.speed_entry.grid(row=0, column=1, padx=(0, 30), pady=5, sticky="w")

        # Champ Latence
        ctk.CTkLabel(self.params_grid, text="Latency (ms):", font=("Arial", 12)).grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")
        self.latency_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.latency_entry.grid(row=0, column=3, pady=5, sticky="w")

        # Infos latence in mm (à droite de la latence)
        self.mm_info_label = ctk.CTkLabel(self.params_grid, text="= 0.000 mm", 
                                          font=("Arial", 12, "bold"), text_color="#1f538d")
        self.mm_info_label.grid(row=0, column=4, padx=(15, 0), pady=5, sticky="w")

        # --- LIGNE 1 : PUISSANCE ---
        # Champ Power
        ctk.CTkLabel(self.params_grid, text="Power (%):", font=("Arial", 12)).grid(row=1, column=0, padx=(0, 10), pady=5, sticky="w")
        self.power_entry = ctk.CTkEntry(self.params_grid, width=100)
        self.power_entry.grid(row=1, column=1, padx=(0, 30), pady=5, sticky="w")

        # Bindings pour la mise à jour temps réel du décalage mm
        self.speed_entry.bind("<KeyRelease>", lambda e: self.update_mm_display())
        self.latency_entry.bind("<KeyRelease>", lambda e: self.update_mm_display())

        # --- INFORMATIONS BAS DE CADRE ---
        # Récupération de l'axe depuis la config (ex: "6" pour l'axe analogique)
        ctrl_axis = self.config_manager.get_item("machine_settings", "controller_value_axis", "N/A")

        # Information combinée : Mode de feu et Axe contrôleur
        info_text = f"Fire mode: Auto-detected | Controller Axis: Analog {ctrl_axis}"
        self.fire_mode_info = ctk.CTkLabel(self.settings_container, text=info_text, 
                                           font=("Arial", 11, "italic"), text_color="gray")
        self.fire_mode_info.pack(padx=15, pady=(0, 10), anchor="w")

        self.settings_container.pack_forget()

        # --- BOUTON D'ACTION ---
        self.action_btn = ctk.CTkButton(self.right_column, text=self.texts["btn_prepare"], font=("Arial", 16, "bold"),
                                        fg_color=self.accent_color, hover_color="#d35400", height=52,
                                        command=None, state="disabled")
        self.action_btn.pack(side="bottom", pady=40, padx=40, fill="x")

        self.setup_calibration_data()

    def create_calibration_card(self, test, index):
        card = ctk.CTkFrame(self.cards_container, corner_radius=15, border_width=2, 
                            fg_color=self.color_normal, border_color=self.border_normal)
        card.grid(row=index, column=0, padx=15, pady=8, sticky="ew")
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
        # Image plus grande pour la description
        latency_preview = ctk.CTkImage(light_image=LATENCY_EXPLAIN_LIGHT, dark_image=LATENCY_EXPLAIN_DARK, size=(600, 120))

        self.test_list = [
            {
                "title": self.texts["latency_title"],
                "short": self.texts["latency_short"],
                "long": self.texts["latency_long"],
                "params": "• Square Size: 20x10mm\n• Center Origin (G54)\n• Variable: m67_delay",
                "icon": latency_img,
                "preview": latency_preview,
                "is_image": True,
                "callback": self.run_latency_test
            },
            {
                "title": self.texts["power_title"],
                "short": self.texts["power_short"],
                "long": self.texts["power_long"],
                "params": "• Steps: 10 levels\n• Power Range: 0-100%\n• Variable: S-Mode / M67",
                "icon": "🔥",
                "preview": None,
                "is_image": False,
                "callback": self.run_power_test
            }
        ]

        for i, test in enumerate(self.test_list):
            self.create_calibration_card(test, i)

    def update_detail_view(self, test):
        # 1. Gestion visuelle de la sélection
        if hasattr(self, "selected_test"):
            self.selected_test["card_widget"].configure(
                fg_color=self.color_normal, 
                border_color=self.border_normal
            )

        self.selected_test = test
        test["card_widget"].configure(
            fg_color=self.color_selected,
            border_color=self.accent_color 
        )

        self.desc_title.configure(text=test["title"])
        self.desc_text.configure(text=test["long"])

        # 2. Logique spécifique au test de Latence
        if test["title"] == self.texts["latency_title"]:
            self.settings_container.pack(fill="x", padx=40, pady=20, after=self.desc_info_row)
            
            cfg = self.controller.config_manager
            
            # --- RÉCUPÉRATION STRICTE SANS FALLBACK ARBITRAIRE ---
            # On récupère None si la clé n'existe pas pour forcer une vérification
            max_val = cfg.get_item("machine_settings", "ctrl_max", None)
            m67_reg = cfg.get_item("machine_settings", "m67_e_num", None)
            cmd_mode = cfg.get_item("machine_settings", "cmd_mode", "Unknown")
            
            # Détection du mode S
            is_s_mode = "S (" in cmd_mode

            # Remplissage des champs Vitesse et Latence (Saisie utilisateur)
            default_speed = cfg.get_item("machine_settings", "base_feedrate", 3000)
            self.speed_entry.delete(0, "end")
            self.speed_entry.insert(0, str(default_speed))

            self.latency_entry.delete(0, "end")
            self.latency_entry.insert(0, "0.0")
            
            self.power_entry.delete(0, "end") 

            # --- CONSTRUCTION DU TEXTE D'INFO DYNAMIQUE ---
            # On n'affiche m67_reg que si on n'est PAS en mode S
            info_parts = [f"Mode: {cmd_mode}"]
            
            if not is_s_mode:
                info_parts.append(f"M67 Register: {m67_reg if m67_reg is not None else '??'}")
            
            info_parts.append(f"Max Res: {max_val if max_val is not None else '??'}")
            
            self.fire_mode_info.configure(text=" | ".join(info_parts))
            
            self.update_mm_display()
            
            # Configuration du bouton avec injection du booléen pour l'engine
            self.action_btn.configure(
                state="normal", 
                command=lambda: self.validate_and_generate(test)
            )
        else:
            self.settings_container.pack_forget()

        # 3. Illustration et Wraplength
        if test.get("preview"):
            self.illustration_label.configure(image=test["preview"], text="")
        else:
            self.illustration_label.configure(image=None, text="[No Preview]")

        self.update_idletasks()
        new_wrap = self.desc_text.winfo_width() - 10
        if new_wrap > 0:
            self.desc_text.configure(wraplength=new_wrap)

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
