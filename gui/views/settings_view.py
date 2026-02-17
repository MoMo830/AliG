import tkinter as tk
import customtkinter as ctk
from core.translations import TRANSLATIONS, THEMES

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app, just_saved=False):
        super().__init__(parent, fg_color="transparent")
        
        self.app = app  
        self.controls = {}
        # On commence en mode "chargement" pour éviter les déclenchements intempestifs
        self.loading = True 
        self.has_changes = False
        
        # --- CONFIGURATION COULEURS ---
        self.color_idle = ["#3B8ED0", "#1F6AA5"]
        self.color_idle_hover = ["#4D9EE0", "#2B7BB9"]
        self.color_saved = "#2d5a27"
        self.color_saved_hover = "#367a31"
        self.color_error = "#942121"

        # 1. Charger la langue
        lang_code = self.app.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang_code, TRANSLATIONS["English"])["settings"]
        
        # --- TITRE & BOUTON SAUVEGARDER ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=40, pady=(30, 0))
        
        self.header_label = ctk.CTkLabel(
            self.top_frame, text=self.texts["title"],
            font=("Arial", 28, "bold"), text_color=self.color_idle
        )
        self.header_label.pack(side="left")

        # Configuration initiale selon just_saved
        initial_color = self.color_saved if just_saved else self.color_idle
        initial_hover = self.color_saved_hover if just_saved else self.color_idle_hover
        initial_text = f"✓ {self.texts['btn_save']}" if just_saved else self.texts["btn_save"]

        self.btn_save = ctk.CTkButton(
            self.top_frame, text=initial_text, 
            fg_color=initial_color,
            hover_color=initial_hover,
            height=40, font=("Arial", 13, "bold"),
            command=self.save_all_settings
        )
        self.btn_save.pack(side="right")

        # --- CONTENEUR PRINCIPAL ---
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=30, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1, pad=20)
        self.main_container.grid_columnconfigure(1, weight=1, pad=20)

        self.setup_settings_ui()
        self.load_settings()
        
        # --- FINALISATION ---
        self.loading = False 
        
        if just_saved:
            self.has_changes = False
            # On utilise un léger délai (10ms) pour passer APRÈS 
            # le rendu initial du moteur CustomTkinter
            self.after(10, self._set_button_saved_state)

    def _set_button_saved_state(self):
        """Force l'état visuel vert 'Sauvegardé'"""
        self.btn_save.configure(
            fg_color=self.color_saved,
            hover_color=self.color_saved_hover,
            text=f"✓ {self.texts['btn_save']}",
            text_color="white" # Force le contraste sur le vert
        )
    # --- LOGIQUE D'ÉTAT ---

    def mark_as_changed(self, *args):
        # 1. Si on charge les données, on ne fait rien
        if self.loading: 
            return 
            
        # 2. Si le bouton est vert (just_saved) OU s'il n'est pas encore marqué comme changé
        # On vérifie la couleur actuelle pour savoir s'il faut repasser en bleu
        is_already_blue = (self.btn_save.cget("fg_color") == self.color_idle)
        
        if not self.has_changes or not is_already_blue:
            self.has_changes = True
            self.btn_save.configure(
                fg_color=self.color_idle,
                hover_color=self.color_idle_hover,
                text=self.texts["btn_save"],
                text_color="white" # ou la couleur par défaut de ton thème
            )

    # --- MÉTHODES DE CONSTRUCTION ---
    # (Tes méthodes create_section, create_simple_input, etc. restent identiques)
    # Assure-toi juste qu'elles utilisent bien self.mark_as_changed

    def setup_settings_ui(self):
        # COLONNE GAUCHE
        self.left_col = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew")

        self.create_section(self.left_col, self.texts["sec_gcode"])
        self.create_dropdown_pair(self.current_sec, self.texts["label_cmd_mode"], 
                                 ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        self.create_simple_input(self.current_sec, self.texts["label_output_e"], 0, "m67_e_num", precision=0)
        self.create_simple_input(self.current_sec, self.texts["label_ctrl_max"], 100, "ctrl_max", precision=0)
        self.create_dropdown_pair(self.current_sec, self.texts["label_firing"], ["M3/M5", "M4/M5"], "firing_mode")

        self.create_section(self.left_col, self.texts["sec_hardware"])
        self.create_input_pair(self.current_sec, self.texts["label_latency"], 0, 50, 11.5, "m67_delay")
        self.create_input_pair(self.current_sec, self.texts["label_overscan"], 0, 50, 10.0, "premove")

        self.create_section(self.left_col, self.texts["sec_scripts"])
        self.txt_header = self.create_textbox_block(self.current_sec, self.texts["label_header"], "custom_header")
        self.txt_footer = self.create_textbox_block(self.current_sec, self.texts["label_footer"], "custom_footer")

        # COLONNE DROITE
        self.right_col = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.right_col.grid(row=0, column=1, sticky="nsew")

        self.create_section(self.right_col, self.texts["sec_appearance"])
        self.create_dropdown_pair(self.current_sec, self.texts["label_theme"], THEMES, "appearance_mode")
        self.create_dropdown_pair(self.current_sec, self.texts["label_lang"], list(TRANSLATIONS.keys()), "app_language")

    # (Mettre ici tes méthodes utilitaires : create_section, create_simple_input, etc.)
    def create_section(self, container, title):
        self.current_sec = ctk.CTkFrame(container, fg_color=["#EBEBEB", "#2B2B2B"], border_width=1, border_color=["#DCE4EE", "#3E454A"])
        self.current_sec.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(self.current_sec, text=title.upper(), font=("Arial", 12, "bold"), text_color="#3a9ad9").pack(pady=5, padx=10, anchor="w")

    def create_textbox_block(self, parent, label, key):
        lbl_frame = ctk.CTkFrame(parent, fg_color="transparent")
        lbl_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(lbl_frame, text=label, font=("Arial", 11, "bold")).pack(side="left")
        txt = ctk.CTkTextbox(parent, font=("Consolas", 11), height=100, border_width=1, border_color="#444444")
        txt.pack(fill="x", padx=10, pady=(2, 10))
        txt.bind("<<Modified>>", self.mark_as_changed)
        return txt

    def create_simple_input(self, parent, label_text, default, key, precision=2):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        entry = ctk.CTkEntry(frame, width=80, height=28)
        entry.insert(0, str(default))
        entry.pack(side="right")
        entry.bind("<KeyRelease>", self.mark_as_changed)
        self.controls[key] = {"entry": entry, "precision": precision}

    def create_dropdown_pair(self, parent, label_text, options, attr_name):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        menu = ctk.CTkOptionMenu(frame, values=options, width=140, command=self.mark_as_changed)
        menu.pack(side="right")
        setattr(self, attr_name, menu)

    def create_input_pair(self, parent, label_text, start, end, default, key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        entry = ctk.CTkEntry(frame, width=60)
        entry.insert(0, str(default))
        entry.pack(side="right")
        slider = ctk.CTkSlider(frame, from_=start, to=end, width=150, command=lambda v: self._update_entry(v, key))
        slider.set(default)
        slider.pack(side="right", padx=10)
        
        entry.bind("<KeyRelease>", self.mark_as_changed)
        entry.bind("<Return>", lambda e: self._update_slider(key))
        entry.bind("<FocusOut>", lambda e: self._update_slider(key))
        self.controls[key] = {"slider": slider, "entry": entry, "precision": 2}

    def _update_entry(self, val, key):
        # Pas besoin de mark_as_changed ici si loading est géré dans mark_as_changed
        self.mark_as_changed()
        entry = self.controls[key]["entry"]
        entry.delete(0, tk.END)
        entry.insert(0, f"{val:.2f}")

    def _update_slider(self, key):
        try:
            val = float(self.controls[key]["entry"].get())
            self.controls[key]["slider"].set(val)
            self.mark_as_changed()
        except: pass

    # --- LOGIQUE DE DONNÉES ---
    
    def load_settings(self):
        data = self.app.config_manager.get_section("machine_settings")
        if not data: return
        
        # Le flag self.loading bloque déjà mark_as_changed
        
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
            for key in self.controls:
                if "slider" in self.controls[key]: self._update_slider(key)
            
            current_lang = self.app.config_manager.get_item("machine_settings", "language", "English")
            new_lang = self.app_language.get()
            
            machine_data = {
                "theme": self.appearance_mode.get(),
                "language": new_lang,
                "cmd_mode": self.cmd_mode.get(),
                "firing_mode": self.firing_mode.get(),
                "m67_e_num": int(self.controls["m67_e_num"]["entry"].get()),
                "ctrl_max": int(self.controls["ctrl_max"]["entry"].get()),
                "m67_delay": float(self.controls["m67_delay"]["slider"].get()),
                "premove": float(self.controls["premove"]["slider"].get()),
                "custom_header": self.txt_header.get("1.0", "end-1c"),
                "custom_footer": self.txt_footer.get("1.0", "end-1c"),
            }

            self.app.config_manager.set_section("machine_settings", machine_data)
            
            if self.app.config_manager.save():
                ctk.set_appearance_mode(self.appearance_mode.get())
                self.has_changes = False
                
                if new_lang != current_lang:
                    # RECHARGEMENT AVEC ARGUMENT
                    self.app.show_settings_mode(just_saved=True) 
                else:
                    # EFFET VERT SUR LA PAGE ACTUELLE
                    self.btn_save.configure(
                        fg_color=self.color_saved, 
                        hover_color=self.color_saved_hover,
                        text="✓ " + self.texts["btn_save"]
                    )
            else:
                self.btn_save.configure(fg_color=self.color_error)

        except Exception as e:
            print(f"Save error: {e}")
            self.btn_save.configure(fg_color=self.color_error)