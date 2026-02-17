import customtkinter as ctk
from core.translations import TRANSLATIONS

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        # parent = le conteneur dans main_window
        # controller = l'instance de LaserGeneratorApp
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["dashboard"]

        # --- EN-TÊTE (Header) ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(60, 40))

        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="A.L.I.G.", 
            font=("Arial", 48, "bold"),
            text_color=["#3B8ED0", "#1F6AA5"] # Dégradé bleu selon le thème
        )
        self.title_label.pack()

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Advanced Laser Imaging Generator", 
            font=("Arial", 18, "italic"),
            text_color="gray"
        )
        self.subtitle_label.pack()

        # --- CONTENEUR DES MODES (Grille) ---
        self.modes_container = ctk.CTkFrame(self, fg_color="transparent")
        self.modes_container.pack(expand=True, fill="both", padx=50)

        # On configure la grille pour centrer les cartes
        self.modes_container.grid_columnconfigure((0, 1), weight=1)

        # 1. CARTE RASTER (Le mode actuel)
        self.create_mode_card(
            row=0, col=0,
            title=self.texts["raster_title"],
            description=self.texts["raster_desc"],
            callback=self.controller.show_raster_mode,
            icon_char="📷" 
        )

        self.create_mode_card(
            row=1, col=0,
            title=self.texts["parser_title"],
            description=self.texts["parser_desc"],
            callback=None,
            state="disabled",
            icon_char="📐"
        )
        self.create_mode_card(
            row=2, col=0,
            title="VECTOR INFILL",
            description="Fill vector paths.",
            callback=None,
            state="disabled",
            icon_char="📐"
        )
        self.create_mode_card(
            row=0, col=1, # Par exemple sur la deuxième ligne
            title=self.texts["calibration_title"],
            description=self.texts["calibration_desc"],
            callback=self.controller.show_calibration_mode,
            icon_char="🔧"
        )
        self.create_mode_card(
            row=1, col=1,
            title=self.texts["settings_title"],
            description=self.texts["settings_desc"],
            callback=self.controller.show_settings_mode,
            icon_char="⚙️"
        )

        # --- FOOTER (Info version) ---
        self.version_label = ctk.CTkLabel(
            self, 
            text="v0.9781b - Stable Build", 
            font=("Arial", 11),
            text_color="gray"
        )
        self.version_label.pack(side="bottom", pady=20)

    def create_mode_card(self, row, col, title, description, callback, icon_char, state="normal"):
        """
        Crée une carte stylisée où tout le cadre agit comme un bouton.
        """
        
        # Configuration des couleurs (Support thèmes clair/sombre)
        base_color = ["#F2F2F2", "#2B2B2B"]   # Gris très clair / Anthracite
        hover_color = ["#EBEBEB", "#333333"]  # Changement subtil au survol
        border_color = ["#DCE4EE", "#3E454A"]
        accent_color = ["#3B8ED0", "#1F6AA5"] # Bleu ALIG pour le survol actif

        # 1. Le cadre principal (la carte)
        card = ctk.CTkFrame(
            self.modes_container, 
            corner_radius=15, 
            border_width=2, 
            border_color=border_color,
            fg_color=base_color
        )
        card.grid(row=row, column=col, padx=20, pady=20, sticky="nsew")
        card.configure(width=350, height=300)
        card.grid_propagate(False) # Garde la taille fixe

        # 2. Conteneur interne pour le centrage vertical
        content_container = ctk.CTkFrame(card, fg_color="transparent")
        content_container.pack(expand=True)
        self.modes_container.grid_rowconfigure(row, weight=1)

        icon_lbl = ctk.CTkLabel(content_container, text=icon_char, font=("Arial", 50))
        icon_lbl.pack(pady=(0, 10))

        t_lbl = ctk.CTkLabel(content_container, text=title, font=("Arial", 22, "bold"))
        t_lbl.pack(pady=5)

        d_lbl = ctk.CTkLabel(content_container, text=description, font=("Arial", 14), wraplength=280)
        d_lbl.pack(pady=10, padx=20)

        # --- LOGIQUE D'INTERACTION ---
        if state == "normal" and callback is not None:
            clickable_widgets = [card, content_container, icon_lbl, t_lbl, d_lbl]
            
            for widget in clickable_widgets:
                widget.configure(cursor="hand2")
            
            # Fonctions de survol
            def on_enter(event):
                card.configure(fg_color=hover_color, border_color=accent_color)
            
            def on_leave(event):
                # Correction cruciale : on vérifie si la souris est réellement sortie de la zone de la carte
                # ou si elle est juste passée sur un enfant.
                x, y = card.winfo_pointerxy()
                widget_under_mouse = card.winfo_containing(x, y)
                
                # Si le widget sous la souris est la carte elle-même ou un de ses enfants, on ne quitte pas
                if widget_under_mouse in clickable_widgets:
                    return
                
                card.configure(fg_color=base_color, border_color=border_color)

            def handle_click(event):
                if callback:
                    callback()
            # Liaison des événements de survol à TOUS les widgets de la carte
            # Comme ça, passer de l'un à l'autre ne déclenche pas de "Leave" non géré
            for widget in clickable_widgets:
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
                widget.bind("<Button-1>", handle_click)

        
        else:
            # État désactivé (Coming Soon)
            dim_color = "#707070"
            icon_lbl.configure(text_color=dim_color)
            t_lbl.configure(text_color=dim_color)
            d_lbl.configure(text_color=dim_color)
            card.configure(border_color=["#D1D1D1", "#2A2A2A"])