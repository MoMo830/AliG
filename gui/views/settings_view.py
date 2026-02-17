import tkinter as tk
import customtkinter as ctk
import os
from tkinter import messagebox

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        # On appelle le constructeur parent
        super().__init__(parent, fg_color="transparent")
        
        # Initialisation des références
        self.app = app  # Stockage de l'instance LaserGeneratorApp
        self.controls = {}
        
        # --- TITRE ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=40, pady=(30, 0))
        
        self.header_label = ctk.CTkLabel(
            self.top_frame, text="MACHINE CONFIGURATION", 
            font=("Arial", 24, "bold"), text_color=["#3B8ED0", "#1F6AA5"]
        )
        self.header_label.pack(side="left", expand=True, padx=(0, 100))

        # --- CONTENEUR PRINCIPAL (SCROLLABLE) ---
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=40, pady=20)

        # Construction de l'interface
        self.setup_settings_ui()
        
        # --- CHARGEMENT DES DONNÉES VIA LE MANAGER ---
        self.load_settings()

    def setup_settings_ui(self):
        # 1. SECTION G-CODE & PROTOCOL
        self.create_section("G-CODE & PROTOCOL")
        self.create_dropdown_pair(self.current_sec, "Laser Command Mode:", 
                                 ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        self.create_simple_input(self.current_sec, "M67 Output Number (E):", 0, "m67_e_num", precision=0)
        self.create_simple_input(self.current_sec, "Controller Max Value:", 100, "ctrl_max", precision=0)
        self.create_dropdown_pair(self.current_sec, "Firing Mode:", ["M3/M5", "M4/M5"], "firing_mode")

        # 2. SECTION HARDWARE & DELAYS
        self.create_section("HARDWARE BEHAVIOR")
        self.create_input_pair(self.current_sec, "Laser Latency (ms)", 0, 50, 11.5, "m67_delay")
        self.create_input_pair(self.current_sec, "Default Overscan (mm)", 0, 50, 10.0, "premove")

        # 3. SECTION CUSTOM SCRIPTS
        self.create_section("SYSTEM SCRIPTS")
        self.txt_header = self.create_textbox_block("Global Header G-Code", "custom_header")
        self.txt_footer = self.create_textbox_block("Global Footer G-Code", "custom_footer")

        # BOUTON SAUVEGARDER
        self.btn_save = ctk.CTkButton(
            self, text="SAVE MACHINE CONFIGURATION", 
            fg_color="#2d5a27", hover_color="#367a31",
            height=45, font=("Arial", 14, "bold"),
            command=self.save_all_settings
        )
        self.btn_save.pack(pady=(0, 30))

    # --- MÉTHODES UTILITAIRES UI ---

    def create_section(self, title):
        self.current_sec = ctk.CTkFrame(self.main_container, fg_color=["#EBEBEB", "#2B2B2B"], border_width=1, border_color=["#DCE4EE", "#3E454A"])
        self.current_sec.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(self.current_sec, text=title, font=("Arial", 13, "bold"), text_color="#3a9ad9").pack(pady=5, padx=10, anchor="w")

    def create_textbox_block(self, label, key):
        lbl_frame = ctk.CTkFrame(self.current_sec, fg_color="transparent")
        lbl_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(lbl_frame, text=label, font=("Arial", 11, "bold")).pack(side="left")
        txt = ctk.CTkTextbox(self.current_sec, font=("Consolas", 11), height=80, border_width=1, border_color="#444444")
        txt.pack(fill="x", padx=10, pady=(2, 10))
        return txt

    def create_simple_input(self, parent, label_text, default, key, precision=2):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        entry = ctk.CTkEntry(frame, width=100, height=28)
        entry.insert(0, str(default))
        entry.pack(side="right")
        self.controls[key] = {"entry": entry, "precision": precision}

    def create_dropdown_pair(self, parent, label_text, options, attr_name):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        menu = ctk.CTkOptionMenu(frame, values=options, width=150)
        menu.pack(side="right")
        setattr(self, attr_name, menu)

    def create_input_pair(self, parent, label_text, start, end, default, key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(side="left")
        
        slider = ctk.CTkSlider(frame, from_=start, to=end, width=200, 
                               command=lambda v: self._update_entry(v, key))
        slider.set(default)
        slider.pack(side="left", padx=20)
        
        entry = ctk.CTkEntry(frame, width=60)
        entry.insert(0, str(default))
        entry.bind("<Return>", lambda e: self._update_slider(key))
        entry.pack(side="right")
        
        self.controls[key] = {"slider": slider, "entry": entry, "precision": 2}

    def _update_entry(self, val, key):
        entry = self.controls[key]["entry"]
        entry.delete(0, tk.END)
        entry.insert(0, f"{val:.2f}")

    def _update_slider(self, key):
        try:
            val = float(self.controls[key]["entry"].get())
            self.controls[key]["slider"].set(val)
        except: pass

    # --- LOGIQUE DE DONNÉES (Utilisant le Manager centralisé) ---

    def load_settings(self):
        """Charge les réglages machine depuis le gestionnaire de config via self.app."""
        data = self.app.config_manager.get_section("machine_settings")
        
        if data:
            # 1. Dropdowns
            if "cmd_mode" in data: self.cmd_mode.set(data["cmd_mode"])
            if "firing_mode" in data: self.firing_mode.set(data["firing_mode"])
            
            # 2. Entrées simples (Nombres entiers)
            for key in ["m67_e_num", "ctrl_max"]:
                if key in data and key in self.controls:
                    self.controls[key]["entry"].delete(0, tk.END)
                    self.controls[key]["entry"].insert(0, str(data[key]))
            
            # 3. Sliders + Entrées (Flottants)
            for key in ["m67_delay", "premove"]:
                if key in data and key in self.controls:
                    val = float(data[key])
                    self.controls[key]["slider"].set(val)
                    self.controls[key]["entry"].delete(0, tk.END)
                    self.controls[key]["entry"].insert(0, f"{val:.2f}")

            # 4. Blocs de texte (G-Code)
            if "custom_header" in data:
                self.txt_header.delete("1.0", tk.END)
                self.txt_header.insert("1.0", data["custom_header"])
            if "custom_footer" in data:
                self.txt_footer.delete("1.0", tk.END)
                self.txt_footer.insert("1.0", data["custom_footer"])

    def save_all_settings(self):
        """Récupère les données de l'UI et demande au manager de les sauvegarder."""
        try:
            machine_data = {
                "cmd_mode": self.cmd_mode.get(),
                "firing_mode": self.firing_mode.get(),
                "m67_e_num": int(self.controls["m67_e_num"]["entry"].get()),
                "ctrl_max": int(self.controls["ctrl_max"]["entry"].get()),
                "m67_delay": float(self.controls["m67_delay"]["slider"].get()),
                "premove": float(self.controls["premove"]["slider"].get()),
                "custom_header": self.txt_header.get("1.0", "end-1c"),
                "custom_footer": self.txt_footer.get("1.0", "end-1c"),
            }
            
            # Mise à jour de la section dans le manager
            self.app.config_manager.set_section("machine_settings", machine_data)
            
            # Sauvegarde physique sur le disque
            if self.app.config_manager.save():
                messagebox.showinfo("Success", "Machine configuration saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to write config file.")
                
        except ValueError:
            messagebox.showerror("Input Error", "Please verify that all numeric fields contain valid numbers.")