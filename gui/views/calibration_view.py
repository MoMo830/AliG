import customtkinter as ctk
import os
from PIL import Image, ImageDraw
from core.utils import get_app_paths
from core.translations import TRANSLATIONS

class CalibrationView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.base_path, self.application_path = get_app_paths()

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

        # Titre de la colonne (Traduit)
        ctk.CTkLabel(self.left_column, text=self.texts["sidebar_title"], 
                     font=("Arial", 18, "bold"), text_color=self.accent_color, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=15)

        self.cards_container = ctk.CTkFrame(self.left_column, fg_color="transparent")
        self.cards_container.grid(row=1, column=0, sticky="nsew")
        self.cards_container.grid_columnconfigure(0, weight=1)

        # --- COLONNE DROITE ---
        self.right_column = ctk.CTkFrame(self.main_grid, fg_color=["#EBEBEB", "#202020"], corner_radius=15)
        self.right_column.grid(row=0, column=1, sticky="nsew")
        
        # Titre dynamique (Traduit par défaut)
        self.desc_title = ctk.CTkLabel(self.right_column, text=self.texts["default_title"], font=("Arial", 30, "bold"), text_color=self.accent_color)
        self.desc_title.pack(pady=(40, 10), padx=40, anchor="w")

        # Description dynamique (Traduite par défaut)
        self.desc_text = ctk.CTkLabel(
            self.right_column, 
            text=self.texts["default_desc"], 
            font=("Arial", 15), 
            wraplength=500, 
            justify="left", 
            anchor="nw"
        )
        self.desc_text.pack(fill="both", expand=True, padx=40, pady=10)
        #self.desc_text.bind("<Configure>", lambda e: self.desc_text.configure(wraplength=e.width - 10))

        # Bouton (Traduit)
        self.action_btn = ctk.CTkButton(self.right_column, text=self.texts["btn_prepare"], font=("Arial", 16, "bold"),
                                        fg_color=self.accent_color, hover_color="#d35400", height=52,
                                        command=None, state="disabled")
        self.action_btn.pack(side="bottom", pady=40, padx=40, fill="x")

        self.setup_calibration_data()

    def setup_calibration_data(self):
        """Initialise les données en utilisant les clés du fichier de traduction"""
        self.test_list = [
            {
                "title": self.texts["latency_title"],
                "short": self.texts["latency_short"],
                "long": self.texts["latency_long"],
                "icon": "⏱️",
                "callback": self.run_latency_test
            },
            {
                "title": self.texts["power_title"],
                "short": self.texts["power_short"],
                "long": self.texts["power_long"],
                "icon": "🔥",
                "callback": self.run_power_test
            }
        ]

        for i, test in enumerate(self.test_list):
            self.create_calibration_card(test, i)

    def create_calibration_card(self, test, index):
        card = ctk.CTkFrame(self.cards_container, corner_radius=15, border_width=2, 
                            fg_color=self.color_normal, border_color=self.border_normal)
        card.grid(row=index, column=0, padx=15, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        test["card_widget"] = card

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

    def update_detail_view(self, test):
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
        self.action_btn.configure(state="normal", command=test["callback"])

    def run_latency_test(self):
        img = Image.new('L', (30, 30), color=0)
        temp_path = os.path.join(self.application_path, "ALIG_LATENCY_TEST.png")
        img.save(temp_path)
        self.controller.show_raster_mode(image_to_load=temp_path, reset_filters=True)

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


