import webbrowser
import customtkinter as ctk
import os
from PIL import Image
from core.translations import TRANSLATIONS

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["dashboard"]

        # --- CONTENEUR PRINCIPAL (Grille 2 Colonnes) ---
        # On utilise pack ici pour que le conteneur prenne TOUT l'espace de DashboardView
        self.main_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.main_grid.pack(expand=True, fill="both", padx=30, pady=20)
        
        self.main_grid.grid_columnconfigure(0, weight=0)
        self.main_grid.grid_columnconfigure(1, weight=1)
        self.main_grid.grid_rowconfigure(0, weight=1)

        # --- COLONNE GAUCHE : MODES DÉFILANTS ---
        self.modes_container = ctk.CTkScrollableFrame(
            self.main_grid, 
            fg_color="transparent",
            width=420,
            label_font=("Arial", 12, "bold")
        )
        self.modes_container.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.modes_container.grid_columnconfigure(0, weight=1)

        modes_list = [
            (self.texts["raster_title"], self.texts["raster_desc"], self.controller.show_raster_mode, "📷", "normal"),
            (self.texts["dithering_title"], self.texts["dithering_desc"], None, "🏁", "normal"),
            (self.texts["infill_title"], self.texts["infill_desc"], None, "📐", "disabled"),
            (self.texts["parser_title"], self.texts["parser_desc"], None, "📐", "disabled"),
            (self.texts["calibration_title"], self.texts["calibration_desc"], self.controller.show_calibration_mode, "🔧", "normal"),
            (self.texts["settings_title"], self.texts["settings_desc"], self.controller.show_settings_mode, "⚙️", "normal"),
        ]

        for i, m in enumerate(modes_list):
            self.create_mode_card(i, 0, m[0], m[1], m[2], m[3], m[4])

        # --- COLONNE DROITE : TITRE + THUMBNAILS + STATS ---
        self.right_column = ctk.CTkFrame(self.main_grid, fg_color="transparent")
        self.right_column.grid(row=0, column=1, sticky="nsew")
        self.right_column.grid_rowconfigure(1, weight=1) # Le scroll_thumbs prend l'espace restant

        # 0. TITRE A.L.I.G. (Déplacé ici)
        self.title_label = ctk.CTkLabel(
            self.right_column, 
            text="A.L.I.G.", 
            font=("Arial", 38, "bold"),
            text_color=["#3B8ED0", "#1F6AA5"],
            anchor="center"
        )
        self.title_label.pack(fill="x", pady=(0, 20))

        # 1. Thumbnails Dynamiques
        self.thumb_label = ctk.CTkLabel(self.right_column, text=self.texts.get("history", "History"), font=("Arial", 14, "bold"), text_color="gray")
        self.thumb_label.pack(anchor="w", pady=(0, 5))
        
        self.scroll_thumbs = ctk.CTkScrollableFrame(
            self.right_column, 
            fg_color=["#EBEBEB", "#202020"], 
            corner_radius=10,
            orientation="vertical"
        )
        self.scroll_thumbs.pack(fill="both", expand=True, pady=(0, 20))
        
        self.load_thumbnails() 

        # 2. Statistiques Réelles (En bas)
        self.create_stats_card()


    def load_thumbnails(self):
        """Affiche les images de manière compacte sur la gauche"""
        thumb_dir = "assets/thumbnails"
        no_history_text = self.texts.get("no_history", "No projects yet")
        
        for widget in self.scroll_thumbs.winfo_children():
            widget.destroy()

        if os.path.exists(thumb_dir):
            files = [f for f in os.listdir(thumb_dir) if f.endswith(".png")]
            files.sort(reverse=True) 

            if not files:
                lbl = ctk.CTkLabel(self.scroll_thumbs, text=no_history_text, text_color="gray")
                lbl.grid(row=0, column=0, columnspan=5, pady=50, sticky="ew")
            else:
                for i, file in enumerate(files):
                    path = os.path.join(thumb_dir, file)
                    try:
                        row = i // 5 
                        col = i % 5 

                        img_data = Image.open(path)
                        # On peut se permettre d'augmenter un peu la taille si on réduit les marges
                        ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(130, 130))
                        
                        btn = ctk.CTkLabel(self.scroll_thumbs, image=ctk_img, text="", cursor="hand2")
                        
                        # padx et pady réduits à 2 ou 5 pour "coller" les images
                        btn.grid(row=row, column=col, padx=4, pady=4)
                        
                    except Exception as e:
                        print(f"Error loading {file}: {e}")

    def create_stats_card(self):
        stats_frame = ctk.CTkFrame(self.right_column, corner_radius=15, border_width=1, border_color=["#DCE4EE", "#3E454A"])
        stats_frame.pack(side="bottom", fill="x", pady=10)
        
        title = ctk.CTkLabel(stats_frame, text=self.texts["machine_stats"], font=("Arial", 15, "bold"))
        title.pack(pady=10)

        grid_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        grid_inner.pack(fill="x", padx=20, pady=(0, 15))
        grid_inner.grid_columnconfigure((0, 1, 2), weight=1)

        # 1. Récupération des valeurs depuis le config_manager
        cfg = self.controller.config_manager
        total_l = cfg.get_item("stats", "total_lines", 0)
        total_g = cfg.get_item("stats", "total_gcodes", 0)
        total_s = cfg.get_item("stats", "total_time_seconds", 0) # On récupère les secondes

        # 2. Conversion des secondes en format lisible (HHh MMm)
        total_s = float(total_s)
        hours = int(total_s // 3600)
        minutes = int((total_s % 3600) // 60)
        
        time_str = f"{hours}h {minutes:02d}m" if hours > 0 else f"{minutes}m"
        if hours == 0 and minutes == 0 and total_s > 0:
            time_str = "< 1m"

        # 3. Affichage avec formatage
        self.add_stat_item(grid_inner, 0, self.texts["lines_generated"], f"{int(total_l):,}")
        self.add_stat_item(grid_inner, 1, self.texts["gcode_saved"], str(total_g))
        self.add_stat_item(grid_inner, 2, self.texts["total_engraving_time"], time_str)

    def add_stat_item(self, parent, col, label, value):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col)
        ctk.CTkLabel(f, text=value, font=("Arial", 18, "bold"), text_color=["#3B8ED0", "#1F6AA5"]).pack()
        ctk.CTkLabel(f, text=label, font=("Arial", 11), text_color="gray").pack()

    def create_mode_card(self, row, col, title, description, callback, icon_char, state="normal"):
        base_color = ["#F2F2F2", "#2B2B2B"]
        hover_color = ["#EBEBEB", "#333333"]
        border_color = ["#DCE4EE", "#3E454A"]
        accent_color = ["#3B8ED0", "#1F6AA5"]

        card = ctk.CTkFrame(
            self.modes_container, 
            corner_radius=15, 
            border_width=2, 
            border_color=border_color,
            fg_color=base_color
        )
        card.grid(row=row, column=col, padx=10, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(card, text=icon_char, font=("Arial", 35))
        icon_lbl.grid(row=0, column=0, padx=20, pady=20)

        text_container = ctk.CTkFrame(card, fg_color="transparent")
        text_container.grid(row=0, column=1, padx=(0, 20), pady=15, sticky="w")

        t_lbl = ctk.CTkLabel(text_container, text=title, font=("Arial", 16, "bold"), anchor="w")
        t_lbl.pack(fill="x")

        d_lbl = ctk.CTkLabel(
            text_container, text=description, font=("Arial", 12), 
            wraplength=230, justify="left", text_color="gray"
        )
        d_lbl.pack(fill="x", pady=(2, 0))

        if state == "normal" and callback is not None:
            widgets = [card, icon_lbl, text_container, t_lbl, d_lbl]
            
            # Fonctions de changement d'état
            def on_enter(e):
                card.configure(fg_color=hover_color, border_color=accent_color)
            
            def on_leave(e):
                card.configure(fg_color=base_color, border_color=border_color)

            for w in widgets: 
                w.configure(cursor="hand2")
                # On bind l'entrée et la sortie sur CHAQUE widget
                # pour que le highlight de la 'card' reste actif
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", lambda e: callback())
        else:
            for w in [icon_lbl, t_lbl, d_lbl]:
                w.configure(text_color="#707070")