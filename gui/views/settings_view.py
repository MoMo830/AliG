import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from core.translations import TRANSLATIONS, THEMES

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        
        self.app = app  
        self.controls = {}
        
        # 1. Charger la langue
        lang_code = self.app.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang_code, TRANSLATIONS["English"])["settings"]
        
        # --- TITRE & BOUTON SAUVEGARDER ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=40, pady=(30, 0))
        
        self.header_label = ctk.CTkLabel(
            self.top_frame, text=self.texts["title"],
            font=("Arial", 28, "bold"), text_color=["#3B8ED0", "#1F6AA5"]
        )
        self.header_label.pack(side="left")

        self.btn_save = ctk.CTkButton(
            self.top_frame, text=self.texts["btn_save"], 
            fg_color="#2d5a27", hover_color="#367a31",
            height=40, font=("Arial", 13, "bold"),
            command=self.save_all_settings
        )
        self.btn_save.pack(side="right")

        # --- CONTENEUR PRINCIPAL (SCROLLABLE) ---
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=30, pady=20)

        # Grille pour les deux colonnes
        self.main_container.grid_columnconfigure(0, weight=1, pad=20)
        self.main_container.grid_columnconfigure(1, weight=1, pad=20)

        self.setup_settings_ui()
        self.load_settings()

    def setup_settings_ui(self):
        # --- COLONNE GAUCHE (Machine) ---
        self.left_col = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew")

        # 1. SECTION G-CODE
        self.create_section(self.left_col, self.texts["sec_gcode"])
        self.create_dropdown_pair(self.current_sec, self.texts["label_cmd_mode"], 
                                 ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        self.create_simple_input(self.current_sec, self.texts["label_output_e"], 0, "m67_e_num", precision=0)
        self.create_simple_input(self.current_sec, self.texts["label_ctrl_max"], 100, "ctrl_max", precision=0)
        self.create_dropdown_pair(self.current_sec, self.texts["label_firing"], ["M3/M5", "M4/M5"], "firing_mode")

        # 2. SECTION HARDWARE
        self.create_section(self.left_col, self.texts["sec_hardware"])
        self.create_input_pair(self.current_sec, self.texts["label_latency"], 0, 50, 11.5, "m67_delay")
        self.create_input_pair(self.current_sec, self.texts["label_overscan"], 0, 50, 10.0, "premove")

        # 3. SECTION SCRIPTS
        self.create_section(self.left_col, self.texts["sec_scripts"])
        self.txt_header = self.create_textbox_block(self.current_sec, self.texts["label_header"], "custom_header")
        self.txt_footer = self.create_textbox_block(self.current_sec, self.texts["label_footer"], "custom_footer")

        # --- COLONNE DROITE (Logiciel) ---
        self.right_col = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.right_col.grid(row=0, column=1, sticky="nsew")

        # 0. SECTION APPEARANCE
        self.create_section(self.right_col, self.texts["sec_appearance"])
        self.create_dropdown_pair(self.current_sec, self.texts["label_theme"], 
                                  THEMES, "appearance_mode")
        self.create_dropdown_pair(self.current_sec, self.texts["label_lang"], 
                                  list(TRANSLATIONS.keys()), "app_language")

    # --- MÉTHODES UTILITAIRES ---

    def create_section(self, container, title):
        """Crée une boîte de section dans le container spécifié"""
        self.current_sec = ctk.CTkFrame(container, fg_color=["#EBEBEB", "#2B2B2B"], border_width=1, border_color=["#DCE4EE", "#3E454A"])
        self.current_sec.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(self.current_sec, text=title.upper(), font=("Arial", 12, "bold"), text_color="#3a9ad9").pack(pady=5, padx=10, anchor="w")

    def create_textbox_block(self, parent, label, key):
        lbl_frame = ctk.CTkFrame(parent, fg_color="transparent")
        lbl_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(lbl_frame, text=label, font=("Arial", 11, "bold")).pack(side="left")
        txt = ctk.CTkTextbox(parent, font=("Consolas", 11), height=100, border_width=1, border_color="#444444")
        txt.pack(fill="x", padx=10, pady=(2, 10))
        return txt

    def create_simple_input(self, parent, label_text, default, key, precision=2):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        entry = ctk.CTkEntry(frame, width=80, height=28)
        entry.insert(0, str(default))
        entry.pack(side="right")
        self.controls[key] = {"entry": entry, "precision": precision}

    def create_dropdown_pair(self, parent, label_text, options, attr_name):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        menu = ctk.CTkOptionMenu(frame, values=options, width=140)
        menu.pack(side="right")
        setattr(self, attr_name, menu)

    def create_input_pair(self, parent, label_text, start, end, default, key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        
        entry = ctk.CTkEntry(frame, width=60)
        entry.insert(0, str(default))
        entry.pack(side="right")

        slider = ctk.CTkSlider(frame, from_=start, to=end, width=150, 
                               command=lambda v: self._update_entry(v, key))
        slider.set(default)
        slider.pack(side="right", padx=10)
        
        # --- LES LIAISONS (BINDS) ---
        # 1. Validation par la touche Entrée
        entry.bind("<Return>", lambda e: self._update_slider(key))
        
        # 2. Validation automatique quand on clique ailleurs (Focus Perdu)
        entry.bind("<FocusOut>", lambda e: self._update_slider(key))
        
        self.controls[key] = {"slider": slider, "entry": entry, "precision": 2}

    def _update_entry(self, val, key):
        entry = self.controls[key]["entry"]
        entry.delete(0, tk.END)
        entry.insert(0, f"{val:.2f}")

    def _update_slider(self, key):
        try:
            val = float(self.controls[key]["entry"].get())
            slider = self.controls[key]["slider"]
            # Optionnel : Brider la valeur entre les limites du slider
            #val = max(slider.cget("from_"), min(slider.cget("to_"), val))
            slider.set(val)
        except: 
            pass

    # --- LOGIQUE DE DONNÉES ---
    # Garde tes méthodes load_settings() et save_all_settings() telles quelles, 
    # elles fonctionneront parfaitement avec cette nouvelle structure.
    
    def load_settings(self):
        data = self.app.config_manager.get_section("machine_settings")
        if data:
            if "theme" in data: self.appearance_mode.set(data["theme"])
            if "language" in data: self.app_language.set(data["language"])
            if "cmd_mode" in data: self.cmd_mode.set(data["cmd_mode"])
            if "firing_mode" in data: self.firing_mode.set(data["firing_mode"])
            for key in ["m67_e_num", "ctrl_max"]:
                if key in data and key in self.controls:
                    self.controls[key]["entry"].delete(0, tk.END)
                    self.controls[key]["entry"].insert(0, str(data[key]))
            for key in ["m67_delay", "premove"]:
                if key in data and key in self.controls:
                    val = float(data[key])
                    self.controls[key]["slider"].set(val)
                    self.controls[key]["entry"].delete(0, tk.END)
                    self.controls[key]["entry"].insert(0, f"{val:.2f}")
            if "custom_header" in data:
                self.txt_header.delete("1.0", tk.END); self.txt_header.insert("1.0", data["custom_header"])
            if "custom_footer" in data:
                self.txt_footer.delete("1.0", tk.END); self.txt_footer.insert("1.0", data["custom_footer"])

    def save_all_settings(self):
            try:
                # --- ÉTAPE PRÉALABLE : SYNCHRONISATION ---
                # On s'assure que tout ce qui est écrit dans les Entry est envoyé 
                # vers les Sliders avant de lire les valeurs finales.
                for key in self.controls:
                    if "slider" in self.controls[key]:
                        self._update_slider(key)
                
                # 1. Appliquer le thème immédiatement
                ctk.set_appearance_mode(self.appearance_mode.get())

                # 2. Préparer les données
                # On extrait les valeurs des Entry pour les champs simples 
                # et des Sliders pour les champs synchronisés.
                new_lang = self.app_language.get()
                
                machine_data = {
                    "theme": self.appearance_mode.get(),
                    "language": new_lang,
                    "cmd_mode": self.cmd_mode.get(),
                    "firing_mode": self.firing_mode.get(),
                    
                    # Champs simples : lecture directe de l'Entry
                    "m67_e_num": int(self.controls["m67_e_num"]["entry"].get()),
                    "ctrl_max": int(self.controls["ctrl_max"]["entry"].get()),
                    
                    # Champs avec curseur : lecture du Slider (mis à jour juste au-dessus)
                    "m67_delay": float(self.controls["m67_delay"]["slider"].get()),
                    "premove": float(self.controls["premove"]["slider"].get()),
                    
                    "custom_header": self.txt_header.get("1.0", "end-1c"),
                    "custom_footer": self.txt_footer.get("1.0", "end-1c"),
                }

                # 3. Sauvegarder via le manager
                self.app.config_manager.set_section("machine_settings", machine_data)
                
                if self.app.config_manager.save():
                    messagebox.showinfo("Success", self.texts["msg_success"])
                    
                    # RECHARGEMENT : On relance la vue pour appliquer les changements (langue, etc.)
                    self.app.show_settings_mode() 
                    
                else:
                    messagebox.showerror("Error", "Failed to write config file.")

            except ValueError:
                # Se déclenche si int() ou float() échoue (ex: texte dans un champ numérique)
                messagebox.showerror(self.texts.get("msg_error_num", "Error"), "Please verify numeric fields.")