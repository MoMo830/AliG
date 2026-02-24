"""
A.L.I.G. Project - Main window
------------------------------------
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image, ImageDraw
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import sys
import json
import os
import webbrowser

from ..widgets import ToolTip, PowerRangeVisualizer, LoadingOverlay
from .simulation_view import SimulationView
from core.engine import (
    process_image_logic, 
    calculate_offsets, 
    generate_gcode_list, 
    generate_framing_gcode,
    generate_pointing_gcode,
    assemble_gcode
)
from core.config_manager import save_json_file, load_json_file
from core.utils import get_app_paths
from engine.gcode_engine import GCodeEngine
from core.translations import TRANSLATIONS


class RasterView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)

        self.app = app
        lang = self.app.config_manager.get_item("machine_settings", "language")

        # Sécurité : si lang est None, vide ou n'est pas dans TRANSLATIONS
        if not lang or lang not in TRANSLATIONS:
            lang = "English" 

        self.common = TRANSLATIONS[lang]["common"]
        self.version = self.app.version
        
        self.after_id = None

        self.engine = GCodeEngine()


        # --- 1. GESTION DES CHEMINS  ---
        self.base_path, self.application_path = get_app_paths()
        self.config_file = os.path.join(self.application_path, "alig_config.json")
        self.input_image_path = ""
        self.output_dir = self.application_path
        
        # --- 3. INITIALISATION INTERFACE ---
        self.controls = {}
        self.setup_ui()
        self.load_settings() 
        
        # --- 4. CHARGEMENT DIFFÉRÉ (Pour éviter le bug de rendu) ---
        # On vérifie si une image est déjà chargée (via load_settings)
        if self.input_image_path and os.path.exists(self.input_image_path):
            # On affiche l'overlay
            self.loading_overlay = LoadingOverlay(self, text="Loading...")
            # On attend que la fenêtre soit prête avant de calculer les hachures
            self.after(250, self._initial_render)
        else:
            # Si pas d'image, on peut appeler update_preview normalement
            self.update_preview()

    def _initial_render(self):
        """Appelé 250ms après l'ouverture pour un rendu parfait."""
        try:
            self.update_preview()
        finally:
            if hasattr(self, 'loading_overlay'):
                self.loading_overlay.destroy()


    def on_closing(self):
        self.save_settings()
        plt.close('all')
        self.destroy()
        sys.exit()

    def setup_ui(self):

        # =========================================================
        # ROOT LAYOUT
        # =========================================================

        self.grid_columnconfigure(0, weight=0)   # Sidebar fixe
        self.grid_columnconfigure(1, weight=1)   # Viewport flexible
        self.grid_rowconfigure(0, weight=1)

        # =========================================================
        # SIDEBAR LEFT
        # =========================================================

        self.sidebar = ctk.CTkFrame(self, width=380)
        self.sidebar.grid_propagate(False)

        self.sidebar.grid(row=0,
                        column=0,
                        sticky="nsew",
                        padx=5,
                        pady=5)

        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # -------- File Frame --------

        file_frame = ctk.CTkFrame(self.sidebar, fg_color="#333333")
        file_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.btn_input = ctk.CTkButton(
            file_frame,
            text="SELECT IMAGE",
            height=32,
            command=self.select_input
        )
        self.btn_input.pack(fill="x", padx=5, pady=5)

        self.btn_output = ctk.CTkButton(
            file_frame,
            text="SELECT OUTPUT DIRECTORY",
            height=32,
            command=self.select_output
        )
        self.btn_output.pack(fill="x", padx=5, pady=(0, 5))

        # -------- Profile Frame --------

        profile_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        profile_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.btn_load_prof = ctk.CTkButton(
            profile_frame,
            text=self.common["import_profile"],
            width=140,
            height=28,
            fg_color="#444444",
            command=self.load_profile_from
        )

        self.btn_load_prof.pack(side="left", expand=True, padx=(0, 2))

        self.btn_save_prof = ctk.CTkButton(
            profile_frame,
            text=self.common["export_profile"],
            width=140,
            height=28,
            fg_color="#444444",
            command=self.export_profile
        )

        self.btn_save_prof.pack(side="right", expand=True, padx=(2, 0))

        # -------- TabView --------

        self.tabview = ctk.CTkTabview(self.sidebar)
        self.tabview.grid(row=2,
                        column=0,
                        sticky="nsew",
                        padx=10,
                        pady=5)

        self.tab_geom_name = self.common.get("geometry", "Geometry")
        self.tab_img_name = self.common.get("image", "Image")
        self.tab_laser_name = self.common.get("laser", "Laser")
        self.tab_gcode_name = self.common.get("gcode", "G-Code")

        self.tabview.add(self.tab_geom_name)
        self.tabview.add(self.tab_img_name)
        self.tabview.add(self.tab_laser_name)
        self.tabview.add(self.tab_gcode_name)

        self._setup_tabs_content()

        # -------- sim Button --------

        self.btn_gen = ctk.CTkButton(
            self.sidebar,
            text=self.common["simulate_gcode"],
            fg_color="#1f538d",
            hover_color="#2a6dbd",
            height=50,
            font=("Arial", 13, "bold"),
            command=self.generate_gcode
        )

        self.btn_gen.grid(row=3,
                        column=0,
                        sticky="ew",
                        padx=20,
                        pady=(5, 10))

        # =========================================================
        # VIEWPORT RIGHT
        # =========================================================

        self.view_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.view_frame.grid(row=0,
                            column=1,
                            sticky="nsew",
                            padx=5,
                            pady=5)

        self.view_frame.grid_columnconfigure(0, weight=1)
        self.view_frame.grid_rowconfigure(0, weight=10)
        self.view_frame.grid_rowconfigure(1, weight=1)

        # =========================================================
        # IMAGE PREVIEW TOP
        # =========================================================

        self.img_container = ctk.CTkFrame(
            self.view_frame,
            fg_color="#1e1e1e",
            border_width=1,
            border_color="#333333"
        )

        self.img_container.grid(row=0,
                                column=0,
                                sticky="nsew",
                                pady=(0, 5))

        self.fig_img = plt.figure(figsize=(5, 5),
                                facecolor='#1e1e1e')

        gs_img = self.fig_img.add_gridspec(
            1, 2,
            width_ratios=[25, 1],
            wspace=0.02,
            left=0.08,
            right=0.96,
            top=0.96,
            bottom=0.04
        )

        self.ax_img = self.fig_img.add_subplot(gs_img[0, 0])
        self.ax_cbar = self.fig_img.add_subplot(gs_img[0, 1])

        self.ax_img.set_facecolor('#1e1e1e')
        self.ax_cbar.set_visible(False)

        # 1. Configuration des unités (Chiffres des axes)
        self.ax_img.tick_params(
            axis='both',
            colors='#888888',     # Gris clair pour la lisibilité
            labelsize=9
        )

        # 2. FORCE LA GRILLE AU-DESSUS DE L'IMAGE
        # Par défaut, Matplotlib dessine la grille SOUS l'image (True). 
        # En mettant False, elle passe au premier plan.
        self.ax_img.set_axisbelow(False)

        # 3. GRILLE AUTO-ADAPTATIVE
        # Le blanc avec alpha faible crée un effet de contraste dynamique :
        # - Visible en gris sur les zones noires
        # - Discret sur les zones blanches
        self.ax_img.grid(
            True, 
            which='both', 
            color='#ffffff', 
            linestyle=':', 
            linewidth=0.5, 
            alpha=0.3,           # Opacité légère pour ne pas masquer le travail
            zorder=10            # Calque supérieur à l'image
        )

        # 4. Configuration des bordures du cadre (Spines)
        for spine in self.ax_img.spines.values():
            spine.set_edgecolor('#333333')
            spine.set_zorder(11) # Le cadre ferme la vue au-dessus de la grille

        # Placeholder preview
        self.placeholder_text = self.ax_img.text(
            0.5, 0.5,
            self.common["choose_image"],
            color='#444444',
            fontsize=12,
            fontweight='bold',
            ha='center',
            va='center',
            transform=self.ax_img.transAxes
        )

        self.canvas_img = FigureCanvasTkAgg(
            self.fig_img,
            master=self.img_container
        )

        self.canvas_img.get_tk_widget().pack(
            fill="both",
            expand=True
        )

        self.canvas_img.get_tk_widget().config(
            bg='#1e1e1e',
            highlightthickness=0
        )

        # =========================================================
        # STATS PANEL BOTTOM
        # =========================================================

        self.stats_container = ctk.CTkFrame(
            self.view_frame,
            fg_color="#202020",
            border_width=1,
            border_color="#333333"
        )
        self.stats_container.grid_propagate(False)

        self.stats_container.grid(row=1,
                                column=0,
                                sticky="nsew")

        self.stats_container.grid_columnconfigure(0, weight=1)
        self.stats_container.grid_columnconfigure(1, weight=6)
        self.stats_container.grid_rowconfigure(0, weight=1)

        # -------- Left stats text --------
        self.stats_left_frame = ctk.CTkFrame(
            self.stats_container,
            fg_color="#202020"
        )
        self.stats_left_frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # AJOUT : Un conteneur interne pour centrer les labels verticalement
        self.labels_inner_container = ctk.CTkFrame(self.stats_left_frame, fg_color="transparent")
        self.labels_inner_container.place(relx=0.5, rely=0.5, anchor="center", relwidth=1)

        self.stats_labels = []
        for _ in range(6):
            lbl = ctk.CTkLabel(
                self.labels_inner_container, # Changement de parent ici
                text="",
                font=("Consolas", 14),
                anchor="w",
                justify="left"
            )
            lbl.pack(fill="x", padx=8, pady=2)
            self.stats_labels.append(lbl)

        # -------- Histogram right --------

        self.stats_right_frame = ctk.CTkFrame(
            self.stats_container,
            fg_color="#202020"
        )
        self.stats_right_frame.grid_propagate(False)

        self.stats_right_frame.grid(row=0,
                                    column=1,
                                    sticky="nsew",
                                    padx=6,
                                    pady=6)

        self.hist_canvas = ctk.CTkCanvas(
            self.stats_right_frame,
            bg="#202020",
            highlightthickness=0
        )
        self.hist_canvas.bind("<Configure>", self.on_hist_resize)

        self.hist_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.hist_bins = None
        self.hist_rects = []

        # =========================================================
        # PREVIEW ELEMENTS
        # =========================================================

        self.bg_rect = plt.Rectangle((0, 0), 0, 0,
                                    color='white',
                                    zorder=-2)

        self.ax_img.add_patch(self.bg_rect)

        self.img_plot = None
        self.cbar = None
        self.origin_dot = None




    def _setup_tabs_content(self):
        """Organise le contenu des onglets de la sidebar"""
        
        # Helper pour créer l'onglet scrollable proprement
        def prepare_tab(name):
            tab = self.tabview.tab(name)
            
            # On force le padding du tab lui-même à 0 pour gagner de la place
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            scroll = ctk.CTkScrollableFrame(
                tab,
                fg_color="transparent",
                scrollbar_button_color="#444444",
                scrollbar_button_hover_color="#555555"
            )
            # On pack en fill both pour occuper tout l'onglet
            scroll.pack(fill="both", expand=True)

            # --- LA SOLUTION AU DÉBORDEMENT ---
            # On force la largeur du contenu interne à suivre le conteneur
            # On configure la colonne 0 du frame INTERNE du scroll
            scroll.grid_columnconfigure(0, weight=1)

            # Masquer la scrollbar par défaut
            scroll._scrollbar.grid_remove()

            def update_scrollbar_visibility(event=None):
                # 1. On force la largeur du contenu (votre code actuel)
                canvas_width = scroll._parent_canvas.winfo_width()
                scroll._parent_canvas.itemconfig(scroll._parent_canvas.find_withtag("all")[0], width=canvas_width)

                # 2. FORCE LA MISE À JOUR DE LA ZONE DE DÉFILEMENT
                # Sans cette ligne, la scrollbar croit que le contenu fait 0px de haut
                scroll._parent_canvas.configure(scrollregion=scroll._parent_canvas.bbox("all"))

                canvas = scroll._parent_canvas
                if canvas.bbox("all"):
                    content_height = canvas.bbox("all")[3]
                    visible_height = canvas.winfo_height()

                    if content_height > visible_height:
                        scroll._scrollbar.grid()
                    else:
                        scroll._scrollbar.grid_remove()

            # On lie l'événement de redimensionnement
            scroll.bind("<Configure>", update_scrollbar_visibility)
            return scroll


        # --- TAB 1: GEOMETRY ---
        t_geo = prepare_tab(self.tab_geom_name)
        
        # 1. Correction pour le label de largeur (on capture l'objet renvoyé)
        # Assure-toi que create_input_pair renvoie le widget label en premier ou seul.
        self.width_label_widget = self.create_input_pair(t_geo, self.common["target_width"], 5, 400, 30.0, "width")
        
        force_w_frame = ctk.CTkFrame(t_geo, fg_color="transparent")
        force_w_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # 2. Correction cruciale : Séparer la création du pack pour self.force_w_label
        self.force_w_label = ctk.CTkLabel(force_w_frame, text=self.common["force_width"], font=("Segoe UI", 11))
        self.force_w_label.pack(side="left") # On pack sur une ligne séparée
        
        self.force_width_var = ctk.BooleanVar(value=False)
        self.sw_force_width = ctk.CTkSwitch(
            force_w_frame, 
            text="", 
            variable=self.force_width_var, 
            width=45, 
            command=lambda: self.after(10, self.update_preview) 
        )
        self.sw_force_width.pack(side="right")

        self.create_input_pair(t_geo, self.common["line_step"], 0.01, 1.0, 0.1307, "line_step", precision=4)
        self.create_input_pair(t_geo, self.common["dpi_resolution"], 10, 1200, 254, "dpi", is_int=True)
        
        # --- AJOUT DU SENS DU RASTER (Intégré dans l'onglet Geometry) ---
        raster_frame = ctk.CTkFrame(t_geo, fg_color="transparent")
        raster_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(raster_frame, text=self.common["raster_mode"], font=("Segoe UI", 11)).pack(side="left")
        
        # 1. On définit le mapping (Technique -> Traduit)
        self.raster_map = {
            "horizontal": self.common["horizontal"],
            "vertical": self.common["vertical"]
        }

        # 2. On crée une liste inversée pour retrouver la clé technique lors du clic
        self.raster_map_inv = {v: k for k, v in self.raster_map.items()}

        # 3. Initialisation du bouton
        self.raster_dir_var = ctk.StringVar(value="horizontal") # TA VARIABLE TECHNIQUE

        self.raster_dir_btn = ctk.CTkSegmentedButton(
            t_geo, 
            values=list(self.raster_map.values()), # ON AFFICHE LES TEXTES TRADUITS
            command=self._on_raster_dir_change,     # FONCTION DE PONT
            height=28,
        )
        self.raster_dir_btn.pack(pady=(0, 10), padx=10, fill="x")

        # On définit la position visuelle initiale basée sur "Horizontal"
        self.raster_dir_btn.set(self.raster_map["horizontal"])
        #self.raster_dir_btn.configure(state="disabled")
        
        
        # --- SUITE DE LA GÉOMÉTRIE ---
        self.create_dropdown_pair(t_geo, self.common["origin_point"], ["Lower-Left", "Upper-Left", "Lower-Right", "Upper-Right", "Center", "Custom"], "origin_mode")
        
        self.custom_offset_frame = ctk.CTkFrame(t_geo, fg_color="transparent")
        self.create_simple_input(self.custom_offset_frame, self.common["custom_offset_x"], 0.0, "custom_x")
        self.create_simple_input(self.custom_offset_frame, self.common["custom_offset_y"], 0.0, "custom_y")

                # --- TAB 2: IMAGE ---
        t_img = prepare_tab(self.tab_img_name)

        self.create_input_pair(t_img, self.common["contrast"], -1.0, 1.0, 0.0, "contrast")
        self.create_input_pair(t_img, self.common["gamma"], 0.1, 6.0, 1.0, "gamma")
        self.create_input_pair(t_img, self.common["thermal"], 0.1, 3.0, 1.5, "thermal")
        
        self.invert_var = ctk.BooleanVar(value=False)
        invert_frame = ctk.CTkFrame(t_img, fg_color="transparent")
        invert_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(invert_frame, text=self.common["invert_color"], font=("Segoe UI", 11)).pack(side="left")
        self.switch_invert = ctk.CTkSwitch(invert_frame, text="", variable=self.invert_var, width=45, command=self.update_preview)
        self.switch_invert.pack(side="right")

        # --- TAB 3: LASER ---
        t_laser = prepare_tab(self.tab_laser_name)
        self.create_input_pair(t_laser, self.common["feedrate"], 500, 20000, 3000, "feedrate", is_int=True)
        self.create_input_pair(t_laser, self.common["overscan"], 0, 50, 10.0, "premove")
        
        
        p_cont = ctk.CTkFrame(t_laser, fg_color="transparent")
        p_cont.pack(fill="x", padx=10, pady=5)
        p_inputs = ctk.CTkFrame(p_cont, fg_color="transparent")
        p_inputs.pack(side="left", fill="x", expand=True)
        self.create_simple_input(p_inputs, self.common["max_power"], 40.0, "max_p")
        self.create_simple_input(p_inputs, self.common["min_power"], 10.0, "min_p")
        
        self.power_viz = PowerRangeVisualizer(p_cont, self.controls["min_p"]["entry"], self.controls["max_p"]["entry"], self.update_preview)
        self.power_viz.pack(side="right", padx=(5, 0))

        self.create_input_pair(t_laser, self.common["laser_latency"], -20, 20, 0, "m67_delay")
        self.create_input_pair(t_laser, self.common["gray_steps"], 2, 256, 256, "gray_steps", is_int=True)

        # --- TAB 4: G-CODE ---
        t_gc = prepare_tab(self.tab_gcode_name)
        
        # Initialisation des variables de contrôle
        self.origin_pointer_var = tk.BooleanVar(value=False)
        self.frame_var = tk.BooleanVar(value=False)

        # --- ENCADRÉ GLOBAL MACHINE PARAMETERS ---
        # On crée un cadre avec une bordure pour marquer la zone sensible
        global_frame = ctk.CTkFrame(t_gc, fg_color="transparent", border_width=1, border_color="#555555")
        global_frame.pack(fill="x", padx=10, pady=10)

        # Titre et Bouton Cadenas
        header_row = ctk.CTkFrame(global_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(header_row, text="⚠️ GLOBAL MACHINE PARAMETERS", 
                     font=("Arial", 11, "bold"), text_color="#FF9500").pack(side="left")
        
        # Le bouton cadenas (Toggle)
        self.is_locked = True
        self.lock_btn = ctk.CTkButton(
            header_row, 
            text="🔒", 
            width=30, 
            height=25, # Augmenter un peu la hauteur aide à l'alignement
            anchor="center", # Force le centrage du contenu
            fg_color="#444444", 
            hover_color="#666666",
            command=self.toggle_machine_lock
        )
        self.lock_btn.pack(side="right")

        # Conteneur pour les réglages (qu'on pourra griser)
        self.machine_controls_container = ctk.CTkFrame(global_frame, fg_color="transparent")
        self.machine_controls_container.pack(fill="x", padx=5, pady=5)

        # 1. Mode de commande (M67 / Spindle)
        self.create_dropdown_pair(self.machine_controls_container, self.common["cmd_mode"], 
                                  ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        
        # M67 E & Controller Max (Regroupés sur une ligne pour gagner de la place)
        row_e_max = ctk.CTkFrame(self.machine_controls_container, fg_color="transparent")
        row_e_max.pack(fill="x", padx=0, pady=2)
        self.create_simple_input(row_e_max, self.common["m67_output"], 0, "m67_e_num", precision=0)
        self.create_simple_input(row_e_max, self.common["ctrl_max_value"], 100, "ctrl_max", precision=0)

        # 2. Firing mode (M3/M4)
        self.create_dropdown_pair(self.machine_controls_container, self.common["firing_mode"], 
                                  ["M3/M5", "M4/M5"], "firing_mode")

        # Initialisation de l'état (verrouillé par défaut)
        self.apply_lock_state()

        # 3. Textboxes Header/Footer avec Labels descriptifs
        # --- HEADER SECTION ---
        h_label_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        h_label_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(h_label_frame, text=self.common["gcode_header"], font=("Arial", 11, "bold")).pack(side="left")
        
        # Petit indicateur "Machine Global" grisé (Preview seulement)
        self.txt_global_header_preview = ctk.CTkTextbox(t_gc, font=("Consolas", 10), height=30, 
                                                        fg_color="#222222", text_color="#666666",
                                                        border_width=0, activate_scrollbars=False)
        self.txt_global_header_preview.pack(fill="x", padx=10, pady=0)
        self.txt_global_header_preview.insert("1.0", "(Machine Settings Header...)")
        self.txt_global_header_preview.configure(state="disabled")

        # Ton champ spécifique au Raster (celui qui est éditable et sauvegardé)
        self.txt_header = ctk.CTkTextbox(t_gc, font=("Consolas", 11), height=40, border_width=1, border_color="#444444")
        self.txt_header.pack(fill="x", padx=10, pady=(2, 5))


        # --- FOOTER SECTION ---
        f_label_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        f_label_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(f_label_frame, text=self.common["gcode_footer"], font=("Arial", 11, "bold")).pack(side="left")

        # Petit indicateur "Machine Global" grisé
        self.txt_global_footer_preview = ctk.CTkTextbox(t_gc, font=("Consolas", 10), height=30, 
                                                        fg_color="#222222", text_color="#666666",
                                                        border_width=0, activate_scrollbars=False)
        self.txt_global_footer_preview.pack(fill="x", padx=10, pady=0)
        self.txt_global_footer_preview.insert("1.0", "(Machine Settings Footer...)")
        self.txt_global_footer_preview.configure(state="disabled")

        # Ton champ spécifique au Raster
        self.txt_footer = ctk.CTkTextbox(t_gc, font=("Consolas", 11), height=40, border_width=1, border_color="#444444")
        self.txt_footer.pack(fill="x", padx=10, pady=(2, 5))

        # --- SECTION FRAMING ---
        ctk.CTkLabel(t_gc, text=self.common["point_fram_options"], font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        
        # 1. Ligne Pause + Hint à droite
        pause_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        pause_frame.pack(fill="x", padx=10, pady=2)
        self.lbl_pause_cmd = ctk.CTkLabel(pause_frame, text=self.common["pause_command"], font=("Arial", 11))
        self.lbl_pause_cmd.pack(side="left")
        self.pause_cmd_entry = ctk.CTkEntry(pause_frame, width=60, height=25)
        self.pause_cmd_entry.insert(0, "M0")
        self.pause_cmd_entry.pack(side="left", padx=10)
        # Hint déplacé ici
        self.lbl_pause_hint = ctk.CTkLabel(pause_frame, text=self.common["void_pause"], font=("Arial", 10, "italic"), text_color="#888888")
        self.lbl_pause_hint.pack(side="right")

        # 2. Switch Pointer + Hint à droite
        ptr_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        ptr_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(ptr_frame, text=self.common["origin_pointing"], font=("Arial", 11)).pack(side="left")
        self.sw_pointer = ctk.CTkSwitch(ptr_frame, text="", variable=self.origin_pointer_var, width=45, progress_color="#1f538d", command=self.toggle_framing_options)
        self.sw_pointer.pack(side="right")
        # Note: Dans ce cas précis, le switch est déjà à droite, on peut ajouter un petit texte avant si besoin

        # 3. Switch Include Framing + Hint à droite
        frm_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        frm_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(frm_frame, text=self.common["framing_option"], font=("Arial", 11)).pack(side="left")
        self.sw_frame = ctk.CTkSwitch(frm_frame, text="", variable=self.frame_var, width=45, progress_color="#1f538d", command=self.toggle_framing_options)
        self.sw_frame.pack(side="right")

        # 4. Ligne Power seule + Hint à droite
        pwr_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        pwr_frame.pack(fill="x", padx=10, pady=2)

        top_row = ctk.CTkFrame(pwr_frame, fg_color="transparent")
        top_row.pack(fill="x")

        self.lbl_frame_p = ctk.CTkLabel(top_row, text=self.common["framing_power"], font=("Arial", 11))
        self.lbl_frame_p.pack(side="left")

        self.frame_power_entry = ctk.CTkEntry(top_row, width=60, height=25)
        self.frame_power_entry.insert(0, "0")
        self.frame_power_entry.pack(side="left", padx=10)

        self.lbl_plow_power_hint = ctk.CTkLabel(
            pwr_frame, 
            text=self.common["hint_power"], 
            font=("Arial", 12, "italic"), 
            text_color="#700000"
        )
        self.lbl_plow_power_hint.pack(side="top", anchor="center", pady=(2, 5))

        # 5. Speed Ratio seul (Utilisation de create_dropdown_pair)
        self.create_dropdown_pair(t_gc, self.common["framing_ratio"], ["5%", "10%", "20%", "30%", "50%", "80%", "100%"], "frame_feed_ratio_menu")
        self.frame_feed_ratio_menu.set("20%")
        # Pour le griser correctement dans toggle_framing_options, on récupère le label si besoin
        # Note: create_dropdown_pair pack déjà le label et le menu dans t_gc

        # Appel initial pour valider l'état
        self.toggle_framing_options()

    def create_dynamic_scroll(parent):
        # On crée le scrollable frame
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        
        # On accède à la scrollbar interne (canvas.v_scrollbar chez CTk)
        # On configure pour que la scrollbar ne s'affiche que si nécessaire
        # Note : Cela dépend de la version de CTk, mais voici l'astuce universelle :
        frame._scrollbar.configure(width=0) # Cache par défaut
        
        def check_scrollbar():
            # Si la hauteur du contenu > hauteur affichée
            if frame._parent_canvas.bbox("all")[3] > frame._parent_canvas.winfo_height():
                frame._scrollbar.configure(width=16) # Affiche
            else:
                frame._scrollbar.configure(width=0) # Cache
            frame.after(100, check_scrollbar)

        # Lancer la surveillance
        frame.after(500, check_scrollbar)
        return frame

        
    def delayed_update(self, delay=50):
        """ Attend 'delay' ms avant d'exécuter update_preview """
        if self.after_id:
            self.after_cancel(self.after_id)
        
        # Programme la mise à jour dans 300ms
        self.after_id = self.after(delay, self.update_preview)

    def create_input_pair(self, parent, label_text, start, end, default, key, is_int=False, precision=2, help_text=None):
        # Changement : on réduit le padx à droite pour laisser de la place à la scrollbar
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2, padx=(10, 15)) # (Gauche, Droite)
        
        lbl = ctk.CTkLabel(frame, text=label_text, font=("Arial", 11))
        lbl.pack(anchor="w")
        
        sub_frame = ctk.CTkFrame(frame, fg_color="transparent")
        sub_frame.pack(fill="x", expand=True)

        
        steps = (end - start) if is_int else 200
        
        # MODIFICATION : Le slider ne fait plus que synchroniser le texte de l'Entry en temps réel
        slider = ctk.CTkSlider(
            sub_frame, 
            from_=start, 
            to=end, 
            number_of_steps=steps, 
            command=lambda v: self.sync_from_slider(slider, entry, v, is_int, precision)
        )
        slider.set(default)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # AJOUT : On lance le calcul de l'image uniquement quand on relâche la souris
        slider.bind("<ButtonRelease-1>", lambda e: self.update_preview())
        
        entry = ctk.CTkEntry(sub_frame, width=65, height=22, font=("Arial", 10))
        format_str = f"{{:.{precision}f}}"
        entry.insert(0, str(int(default)) if is_int else format_str.format(default))
        entry.pack(side="right")
        
        self.controls[key] = {"slider": slider, "entry": entry, "is_int": is_int, "precision": precision}
        
        # Pour l'Entry, on garde l'update immédiat sur 'Entrée' car c'est une action volontaire
        entry.bind("<Return>", lambda e: [self.sync_from_entry(slider, entry, is_int, precision), self.update_preview()])
        entry.bind("<FocusOut>", lambda e: [self.sync_from_entry(slider, entry, is_int, precision), self.update_preview()])

        # --- AJOUT TOOLTIP ---
        if help_text:
            ToolTip(lbl, help_text)
            
        return lbl #return self.controls[key]

    def create_simple_input(self, parent, label_text, default, key, precision=2, help_text=None, compact=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        # Changement : Uniformisation des marges
        frame.pack(fill="x" if not compact else "none", side="left" if compact else "top", pady=2, padx=(10, 15))
        
        lbl = ctk.CTkLabel(frame, text=label_text, font=("Arial", 11))
        lbl.pack(side="left")
        
        width = 60 if compact else 80
        entry = ctk.CTkEntry(frame, width=width, height=22, font=("Arial", 10))
        
        if precision == 0:
            entry.insert(0, str(int(default)))
        else:
            format_str = f"{{:.{precision}f}}"
            entry.insert(0, format_str.format(default))
        
        # On colle l'entry à gauche si compact, sinon à droite comme avant
        entry.pack(side="left" if compact else "right", padx=5 if compact else 0)
        
        self.controls[key] = {
            "slider": entry, 
            "entry": entry, 
            "is_int": (precision == 0),
            "precision": precision
        }
        
        entry.bind("<Return>", lambda e: self.sync_from_entry(entry, entry, False, precision))
        entry.bind("<FocusOut>", lambda e: self.sync_from_entry(entry, entry, False, precision))

        if help_text:
            ToolTip(lbl, help_text)

        return self.controls[key]
    
    def create_dropdown_pair(self, parent, label_text, options, attr_name):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2, padx=10)
        
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(anchor="w")
        
        def on_change(choice):
            # Logique spécifique à l'Origin Point
            if attr_name == "origin_mode":
                if choice == "Custom":
                    self.custom_offset_frame.pack(fill="x", padx=10, pady=5)
                else:
                    self.custom_offset_frame.pack_forget()
            
            # Mise à jour de la simulation pour TOUS les menus
            self.delayed_update(100)

        dropdown = ctk.CTkOptionMenu(
            frame, 
            values=options,
            dynamic_resizing=False,
            height=28,
            fg_color="#444444",
            button_color="#555555",
            command=on_change 
        )
        dropdown.pack(fill="x", pady=(2, 5))
        
        setattr(self, attr_name, dropdown)
        return dropdown
        
    def get_val(self, ctrl):
        # 1. On récupère ce qu'il y a écrit dans la case texte
        txt = ctrl["entry"].get().replace(',', '.').strip()
        
        try:
            # 2. Si la case est vide, on prend la valeur du slider (si c'est un slider)
            if not txt:
                if isinstance(ctrl.get("slider"), ctk.CTkSlider):
                    return ctrl["slider"].get()
                return 0.0
            
            # 3. Conversion en nombre
            val = float(txt)
            
            # 4. LIBERTÉ TOTALE : On retourne la valeur saisie directement.
            # On ne vérifie PAS si c'est dans la "range" du slider.
            # Le slider se mettra à jour visuellement (s'il le peut) via update_preview
            return int(val) if ctrl.get("is_int", False) else val
            
        except (ValueError, TypeError):
            # 5. Si l'utilisateur a tapé n'importe quoi (ex: "abc")
            if isinstance(ctrl.get("slider"), ctk.CTkSlider):
                return ctrl["slider"].get()
            return 0.0

   
    def toggle_framing_options(self):
        """Gère l'activation et l'aspect visuel (grisage) des champs de réglage."""
        
        # États des switches
        pointing_active = self.origin_pointer_var.get()
        framing_active = self.frame_var.get()
        
        # Logique d'activation
        any_setup_active = pointing_active or framing_active
        setup_state = "normal" if any_setup_active else "disabled"
        framing_state = "normal" if framing_active else "disabled"

        # Définition des couleurs
        # Texte normal vs texte "grisé" pour l'intérieur des box
        entry_text_color = "#DCE4EE" if any_setup_active else "#666666" 
        label_color = "#DCE4EE" if any_setup_active else "#555555"
        hint_color = "#888888" if any_setup_active else "#444444"

        # --- 1. Application aux Entry (État + Couleur du texte interne) ---
        self.pause_cmd_entry.configure(state=setup_state, text_color=entry_text_color)
        self.frame_power_entry.configure(state=setup_state, text_color=entry_text_color)
        
        # --- 2. Application aux Labels ---
        self.lbl_pause_cmd.configure(text_color=label_color)
        self.lbl_frame_p.configure(text_color=label_color)
        self.lbl_pause_hint.configure(text_color=hint_color)
        self.lbl_plow_power_hint.configure(text_color=hint_color)

        # --- 3. Cas particulier de la vitesse (Framing uniquement) ---
        speed_text_color = "#DCE4EE" if framing_active else "#666666"
        self.frame_feed_ratio_menu.configure(state=framing_state)
        self.frame_feed_ratio_menu.configure(text_color="#DCE4EE" if framing_active else "#555555")




    def select_input(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
        if path:
            self.input_image_path = path
            
            # Récupération du nom du fichier uniquement
            file_name = os.path.basename(path)
            
            # Mise à jour visuelle du bouton
            self.btn_input.configure(
                text=f"{file_name.upper()}",
                fg_color="#2d5a27",      # Vert succès
                hover_color="#367a31"    # Survol vert
            )
            
            self.update_preview()

    def select_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir = directory
            
            # Récupération du nom du dossier (ex: "MesGravures")
            folder_name = os.path.basename(directory)
            # Gestion du cas où on choisit la racine d'un disque (ex: "C:/")
            display_path = folder_name if folder_name else directory
            
            # Mise à jour du bouton avec le label constant "OUT:"
            self.btn_output.configure(
                text=f"OUT: {display_path.upper()}/",
                fg_color="#2d5a27",      # Vert succès
                hover_color="#367a31"    # Survol vert
            )
            #print(f"Output directory set to: {directory}")

    def calculate_offsets(self, real_w, real_h):
      """Méthode passerelle qui lit l'UI et appelle le moteur"""
      return self.engine.calculate_offsets(
         self.origin_mode.get(),
         real_w,
         real_h,
         self.get_val(self.controls["custom_x"]),
         self.get_val(self.controls["custom_y"])
      )


    def process_logic(self):
        """
        Prépare les données pour la simulation et le G-code.
        Regroupe le traitement d'image et les calculs géométriques (moteur).
        """
        if not self.input_image_path or not os.path.isfile(self.input_image_path):
            print("DEBUG: Chargement / Image non disponible.")
            return None, None

        # 1. Préparation des paramètres consolidés
        # Note : 'width' contient la valeur de l'UI (qui est la Hauteur si Vertical)
        ui_dimension = self.get_val(self.controls["width"])
        raster_mode = self.raster_dir_var.get().lower()

        ui_dimension = self.get_val(self.controls["width"])
        raster_mode = self.raster_dir_var.get().lower()

        settings = {
            "line_step": self.get_val(self.controls["line_step"]),
            "gamma": self.get_val(self.controls["gamma"]),
            "contrast": self.get_val(self.controls["contrast"]),
            "thermal": self.get_val(self.controls["thermal"]),
            "min_p": self.get_val(self.controls["min_p"]),
            "max_p": self.get_val(self.controls["max_p"]),
            "dpi": self.get_val(self.controls["dpi"]),
            "gray_steps": self.get_val(self.controls["gray_steps"]),
            "premove": self.get_val(self.controls["premove"]),
            "feedrate": self.get_val(self.controls["feedrate"]),
            "speed": self.get_val(self.controls["feedrate"]),
            "invert": self.invert_var.get(),
            
            # --- C'est ici que la magie opère ---
            "ui_dimension": ui_dimension,      # La valeur numérique saisie
            "raster_mode": raster_mode,        # 'horizontal' ou 'vertical'
            "force_dim": self.force_width_var.get() # On transmet l'état du bouton Force
        }

        # On garde ces clés par sécurité si d'autres fonctions de l'engine les utilisent
        if raster_mode == "horizontal":
            settings["width"] = ui_dimension
        else:
            settings["height"] = ui_dimension

        # 2. Gestion du cache source
        current_cache = None
        if hasattr(self, '_source_img_path') and self._source_img_path == self.input_image_path:
            current_cache = getattr(self, '_source_img_cache', None)

        # 3. Appel unique au moteur (Engine)
        try:
            # On demande à l'engine de traiter l'image ET de calculer la géométrie
            # results doit retourner : (matrix, img_obj, geom_dict, mem_warn)
            results = self.engine.process_image_logic(
                self.input_image_path, 
                settings, 
                source_img_cache=current_cache
            )
            
            matrix, img_obj, geom, mem_warn = results

            # --- Normalisation des pixel pitch selon orientation machine ---
            raster_mode = settings["raster_mode"]

            x_step = geom.get("x_step", 0.1)
            y_step = geom.get("y_step", 0.1)

            if raster_mode == "vertical":
                geom["machine_step_x"] = y_step
                geom["machine_step_y"] = x_step
            else:
                geom["machine_step_x"] = x_step
                geom["machine_step_y"] = y_step

            # 4. Mise à jour du cache et des références de classe
            self._source_img_cache = img_obj
            self._source_img_path = self.input_image_path
            
            # On stocke les derniers résultats pour update_preview et generate_gcode
            self._last_matrix = matrix
            self._last_geom = geom 
            self.estimated_file_size = geom.get("file_size_str", "N/A")
            self._estimated_time = geom.get("est_min", 0)

            # 5. Mise à jour visuelle des alertes mémoire
            if hasattr(self, 'label_matrix_size'):
                color = "#e74c3c" if mem_warn else "#aaaaaa"
                self.label_matrix_size.configure(text_color=color)

            # 6. Mise à jour des labels de stats si présents
            if hasattr(self, 'label_file_size'):
                self.label_file_size.configure(text=f"FILE SIZE: {self.estimated_file_size}")

            # On retourne la matrice et le dictionnaire de géométrie complet
            return matrix, geom
        
        except Exception as e:
            import traceback
            print(f"Logic Error: {e}")
            traceback.print_exc()
            return None, None


    def update_preview(self):
        if not hasattr(self, 'controls') or 'width' not in self.controls:
            return
        if not hasattr(self, 'origin_mode'):
            return

        try:
            # 1. Récupération des données consolidées depuis l'Engine
            # process_logic() retourne maintenant (matrix, geom)
            res = self.process_logic()
            if not res or res[0] is None:
                if self.img_plot: self.img_plot.set_visible(False)
                self.canvas_img.draw_idle()
                return

            matrix, geom = res
            
            # 2. Extraction des paramètres géométriques calculés par l'engine
            real_w = geom["real_w"]
            real_h = geom["real_h"]
            rf = geom["rect_full"]  # [x_min, y_min, x_max, y_max] relatif à l'image
            
            # Calcul du décalage selon l'origine machine choisie
            offX, offY = self.calculate_offsets(real_w, real_h)
            
            v_min = self.get_val(self.controls.get("min_p")) if self.controls.get("min_p") else 0
            v_max = self.get_val(self.controls.get("max_p")) if self.controls.get("max_p") else 255

            # 3. Nettoyage des anciens éléments de dessin
            for attr in ['rect_overscan_patch', 'overscan_text_1', 'overscan_text_2']:
                if hasattr(self, attr):
                    try: getattr(self, attr).remove()
                    except: pass

            if hasattr(self, "overscan_hatch_patches"):
                for p in self.overscan_hatch_patches:
                    try: p.remove()
                    except: pass
            self.overscan_hatch_patches = []

            # 4. Mise à jour de l'image de fond
            self._update_image_artist(matrix, offX, offY, real_w, real_h, v_min, v_max)
            self.canvas_img.draw() 

            def draw_overscan_zone(x_min, y_min, width, height, label_side="left"):
                if width < 0.5 or height < 0.5: return None
                
                # Création du conteneur de hachures
                r_main = Rectangle((x_min, y_min), width, height, facecolor="none", 
                                  hatch=hatch_pattern, edgecolor="#3498db", 
                                  linewidth=0, alpha=0.3, zorder=5)
                self.ax_img.add_patch(r_main)
                self.overscan_hatch_patches.append(r_main)

                # Ajout du texte "OVERSCAN" au centre de la zone
                rotation = 90 if direction == "horizontal" else 0
                txt = self.ax_img.text(x_min + width/2, y_min + height/2, "OVERSCAN", 
                                       rotation=rotation, fontsize=7, va='center', ha='center',
                                       color='#3498db', weight='bold', zorder=20)
                return txt
            
            # 5. Logique de dessin de l'Overscan (Adaptée pour origin='upper')
            direction = self.raster_dir_var.get()
            hatch_pattern = "|||" if direction == "vertical" else "---"

            if direction == "horizontal":
                over_w_left = abs(rf[0])
                over_w_right = rf[2] - real_w
                
                # On force l'alignement sur les bords de l'image
                global_y = offY
                global_h = real_h
                
                if over_w_left > 0.1:
                    self.overscan_text_1 = draw_overscan_zone(offX + rf[0], offY, over_w_left, real_h)
                if over_w_right > 0.1:
                    self.overscan_text_2 = draw_overscan_zone(offX + real_w, offY, over_w_right, real_h)
            else:
                # Mode Vertical
                over_h_bottom = abs(rf[1])
                over_h_top = rf[3] - real_h
                
                global_y = offY + rf[1]
                global_h = rf[3] - rf[1]
                
                if over_h_bottom > 0.1:
                    self.overscan_text_1 = draw_overscan_zone(offX, offY + rf[1], real_w, over_h_bottom)
                if over_h_top > 0.1:
                    self.overscan_text_2 = draw_overscan_zone(offX, offY + real_h, real_w, over_h_top)

            # Rectangle global en pointillés
            self.rect_overscan_patch = Rectangle(
                (offX + rf[0], global_y), rf[2] - rf[0], global_h,
                linewidth=1.5,          # Un poil plus épais pour couvrir le bord du pixel
                edgecolor='#3498db', 
                facecolor='none', 
                linestyle='--', 
                alpha=0.9, 
                zorder=30,              # On passe BIEN au-dessus de l'image (zorder 2)
                snap=True               # Aligne le tracé sur la grille de l'écran
            )
            self.ax_img.add_patch(self.rect_overscan_patch)

            # 6. Configuration des limites des axes
            decal = 0.5
            rect_x_min = offX + rf[0]
            rect_x_max = offX + rf[2]
            self.ax_img.set_xlim(rect_x_min-decal, rect_x_max+decal)
            self.ax_img.set_ylim(global_y-decal, global_y + global_h+decal)

            # --- NOUVEAU : AFFICHAGE UNITÉS HAUT ET DROITE ---
            # On active les traits (ticks) en haut et à droite
            self.ax_img.tick_params(top=True, right=True, which='both')
            # On force l'affichage des chiffres (labels) sur tous les côtés
            self.ax_img.xaxis.set_tick_params(labelbottom=True, labeltop=True)
            self.ax_img.yaxis.set_tick_params(labelleft=True, labelright=True)
            # On s'assure que la couleur grise s'applique à tous ces nouveaux labels
            self.ax_img.tick_params(axis='both', colors='#888888', labelsize=9)

            # --- TA GRILLE CYAN ---
            self.ax_img.set_axisbelow(False)  
            self.ax_img.grid(False, which='both')

            self.ax_img.grid(
                True, 
                color='#00ffff', # Cyan
                linestyle='-', 
                linewidth=1, 
                alpha=0.5, 
                zorder=15
            )

            for line in self.ax_img.xaxis.get_gridlines() + self.ax_img.yaxis.get_gridlines():
                line.set_zorder(15)




            # 7. Dessin du point d'origine machine (0,0)
            if hasattr(self, 'origin_marker'):
                try: self.origin_marker[0].remove()
                except: pass
            self.origin_marker = self.ax_img.plot(0, 0, 'ro', markersize=6, zorder=25)

            # 8. Mise à jour des Stats et Histogramme
            # On utilise directement les données du dictionnaire geom
            est_min = geom.get("est_min", 0.0)

            total_seconds = int(est_min * 60)

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            self._update_dashboard_stats(
                geom["w_px"],
                geom["h_px"],
                real_w,
                real_h,
                geom["scan_step"],   # <-- toujours celui-ci
                geom["l_step"],      # <-- toujours celui-ci
                hours,
                minutes,
                seconds,
                self.estimated_file_size
            )
        

            self._update_histogram_async(matrix, v_min, v_max)
            
            self.canvas_img.draw_idle()

        except Exception as e:
            import traceback
            print(f"Preview Error: {e}")
            traceback.print_exc()


    def generate_gcode(self):
        """Prépare le payload complet (fusion Global + Raster) et lance la simulation."""
        self.save_settings() # Sauvegarde automatique des paramètres actuels
        
        # --- 0. CAPTURE SÉCURISÉE DES WIDGETS ---
        try:
            current_cmd_mode = self.cmd_mode.get()
            current_firing_mode = self.firing_mode.get()
            current_origin_mode = self.origin_mode.get()
            current_raster_mode = self.raster_dir_var.get() 
        except AttributeError: 
            return

        # --- 1. RÉCUPÉRATION DES DONNÉES DEPUIS L'ENGINE ---
        res = self.process_logic()
        if not res or res[0] is None:
            return

        matrix, geom = res

        # On extrait les valeurs calculées et VALIDÉES par l'Engine
        h_px = geom["h_px"]
        w_px = geom["w_px"]

        # IMPORTANT : On récupère les pas physiques réels (X et Y) 
        # calculés par l'Engine (qui a déjà géré le mode Horizontal/Vertical)
        x_step_final = geom["x_step"]
        y_step_final = geom["y_step"]
        est_min = geom["est_min"]

        real_w = geom["real_w"]
        real_h = geom["real_h"]
        estimated_file_size = geom.get("file_size_str", "N/A")

        # Calcul des offsets basé sur les dimensions réelles validées
        offX, offY = self.calculate_offsets(real_w, real_h)

        # --- 2. GESTION DES BLOCS DE TEXTE (FUSION GLOBAL + RASTER) ---
        global_h = self.app.config_manager.get_item("machine_settings", "custom_header", "").strip()
        global_f = self.app.config_manager.get_item("machine_settings", "custom_footer", "").strip()
        
        raster_h = self.txt_header.get("1.0", "end-1c").strip()
        raster_f = self.txt_footer.get("1.0", "end-1c").strip()

        full_header = f"{global_h}\n{raster_h}".strip() if global_h and raster_h else (global_h or raster_h)
        full_footer = f"{raster_f}\n{global_f}".strip() if global_f and raster_f else (global_f or raster_f)
        print(f"h:{h_px}, w_px:{w_px}, y_step_final:{y_step_final}, x_step_final{x_step_final}")
        # --- 3. PACKAGING DU PAYLOAD ---
        payload = {
            'matrix': matrix,
            'dims': (h_px, w_px, y_step_final, x_step_final),
            'estimated_size': estimated_file_size,
            'offsets': (offX, offY),
            'params': {
                'e_num': int(self.get_val(self.controls["m67_e_num"])),
                'use_s_mode': "S (Spindle)" in current_cmd_mode,
                'ctrl_max': self.get_val(self.controls["ctrl_max"]),
                'min_power': self.get_val(self.controls["min_p"]),
                'max_power': self.get_val(self.controls["max_p"]),
                'premove': self.get_val(self.controls["premove"]),
                'feedrate': self.get_val(self.controls["feedrate"]),
                'm67_delay': self.get_val(self.controls["m67_delay"]),
                'gray_scales': int(self.get_val(self.controls["gray_steps"])),
                'gray_steps': int(self.get_val(self.controls["gray_steps"])),
                'raster_mode': current_raster_mode 
            },
            'framing': {
                'is_pointing': self.origin_pointer_var.get(),
                'is_framing': self.frame_var.get(),
                'f_pwr': self.frame_power_entry.get(),
                'f_ratio': self.frame_feed_ratio_menu.get().replace('%', ''),
                'f_pause': self.pause_cmd_entry.get().strip() or None,
                'use_s_mode': "S (Spindle)" in current_cmd_mode,
                'e_num': int(self.get_val(self.controls["m67_e_num"])),
                'base_feedrate': self.get_val(self.controls["feedrate"])
            },
            'text_blocks': {
                'header': full_header,
                'footer': full_footer
            },
            'metadata': {
                'version': self.version,
                'mode': current_cmd_mode.split(' ')[0],
                'firing_cmd': current_firing_mode.split('/')[0],
                'file_extension': self.app.config_manager.get_item("machine_settings", "gcode_extension", ".nc"),
                'file_name': (os.path.basename(self.input_image_path).split('.')[0] if self.input_image_path else "export"),
                'output_dir': self.output_dir, 
                'origin_mode': current_origin_mode,
                'real_w': real_w, 
                'real_h': real_h,
                'est_sec': int(est_min * 60),
                'raster_direction': current_raster_mode 
            }
        }

        # --- 4. LANCEMENT ---
        self.app.show_simulation(
            self.engine, 
            payload, 
            return_view="raster"
        )

    def sync_from_slider(self, slider, entry, value, is_int, precision):
        """Met à jour uniquement le texte de l'Entry pendant le mouvement du slider."""
        val = int(float(value)) if is_int else float(value)
        entry.delete(0, tk.END)
        format_str = f"{{:.{precision}f}}"
        entry.insert(0, str(val) if is_int else format_str.format(val))
        
        if hasattr(self, 'power_viz'):
            self.power_viz.refresh_visuals()


    def sync_from_entry(self, slider, entry, is_int, precision):
        try:
            content = entry.get().replace(',', '.').strip()
            if not content: return 
            
            val = float(content)
            if isinstance(slider, ctk.CTkSlider):
                slider.set(val)

            # --- MISE À JOUR DIFFÉRÉE ---
            self.delayed_update(100) 

        except ValueError:
            if isinstance(slider, ctk.CTkSlider):
                self.sync_from_slider(slider, entry, slider.get(), is_int, precision)

    def get_all_settings_data(self):
        """Récupère l'intégralité des réglages de l'interface dans un dictionnaire."""
        data = {k: self.get_val(v) for k, v in self.controls.items()}
        
        # Chemins et Textes
        data["input_path"] = self.input_image_path
        data["output_dir"] = self.output_dir
        data["custom_header"] = self.txt_header.get("1.0", "end-1c").strip()
        data["custom_footer"] = self.txt_footer.get("1.0", "end-1c").strip()
        
        # Modes et Options
        data["origin_mode"] = self.origin_mode.get()
        data["cmd_mode"] = self.cmd_mode.get()
        data["firing_mode"] = self.firing_mode.get()
        
        # Framing & poiting
        data["include_frame"] = self.frame_var.get()
        data["include_pointer"] = self.origin_pointer_var.get()
        data["frame_power"] = self.frame_power_entry.get()
        data["custom_pause_cmd"] = self.pause_cmd_entry.get()
        data["framing_ratio"] = self.frame_feed_ratio_menu.get()
        
        
        # Géométrie spécifique
        data["force_width"] = self.force_width_var.get()
        data["invert_relief"] = self.invert_var.get()
        
        
        return data

    def save_settings(self):
        """Sauvegarde les réglages en respectant la séparation Machine/Raster."""
        # 1. On récupère le dictionnaire à plat (contient tout l'onglet Raster)
        all_data = self.get_all_settings_data()
        
        # 2. On définit les clés qui appartiennent à la configuration GLOBALE MACHINE
        machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "m67_delay"]
        
        # On extrait ces clés du dictionnaire (elles disparaissent de all_data)
        machine_updates = {}
        for k in machine_keys:
            if k in all_data:
                machine_updates[k] = all_data.pop(k)
        
        # 3. Ce qui reste dans all_data est le pur "raster_settings"
        # On y trouve : input_path, custom_header (spécifique), width, etc.
        raster_data = all_data 

        # 4. MISE À JOUR SÉCURISÉE (On ne touche pas au header global ici !)
        # On récupère l'existant pour ne pas supprimer theme/language/global_header
        current_machine = self.app.config_manager.get_section("machine_settings")
        current_machine.update(machine_updates) # On ne met à jour que les 5 clés de pilotage
        
        # 5. On renvoie les deux blocs au manager
        self.app.config_manager.set_section("machine_settings", current_machine)
        self.app.config_manager.set_section("raster_settings", raster_data)
        
        # 6. Sauvegarde sur disque
        if not self.app.config_manager.save():
            print("ERREUR : Impossible d'écrire le fichier de config.")
            
    def load_settings(self):
        machine_data = self.app.config_manager.get_section("machine_settings")
        raster_data = self.app.config_manager.get_section("raster_settings")
        
        if machine_data:
            # Correction du nom de l'argument ici
            self.apply_settings_data(machine_data, is_machine_config=True) 
            
        if raster_data:
            # Et ici (optionnel car False est la valeur par défaut)
            self.apply_settings_data(raster_data, is_machine_config=False)
            

    def export_profile(self):
        """Export manuel : On recrée la structure hiérarchique pour le fichier JSON."""
        file_path = filedialog.asksaveasfilename(
            initialdir=self.application_path,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="alig_full_profile.json"
        )
        if file_path:
            all_data = self.get_all_settings_data()
            
            # On structure le JSON d'export comme le fichier de config principal
            machine_keys = ["cmd_mode", "firing_mode", "m67_e_num", "ctrl_max", "m67_delay"]
            
            export_structure = {
                "machine_settings": {k: all_data.pop(k) for k in machine_keys if k in all_data},
                "raster_settings": all_data
            }
            
            success, err = save_json_file(file_path, export_structure)
            if success:
                messagebox.showinfo("Export Success", "Full profile saved!")

    def load_profile_from(self):
        """Import manuel depuis un fichier choisi."""
        file_path = filedialog.askopenfilename(
            initialdir=self.application_path,
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            data, err = load_json_file(file_path)
            if data:
                self.apply_settings_data(data)
                self.update_preview()
                messagebox.showinfo("Success", f"Profile loaded:\n{os.path.basename(file_path)}")
            else:
                messagebox.showerror("Error", f"Could not load profile: {err}")

    def apply_settings_data(self, data, is_machine_config=False):
        """
        Applique intelligemment les réglages à l'interface.
        Si is_machine_config est True, on ignore les headers/footers pour éviter les doublons.
        """
        # 1. BOUCLE AUTOMATIQUE (Sliders & Entries)
        for k, v in data.items():
            if k in self.controls:
                ctrl = self.controls[k]
                # Mise à jour du slider
                if isinstance(ctrl.get("slider"), ctk.CTkSlider):
                    ctrl["slider"].set(v)
                # Mise à jour de l'entrée texte
                if "entry" in ctrl:
                    ctrl["entry"].delete(0, tk.END)
                    fmt = "{}" if ctrl.get("is_int") else f"{{:.{ctrl.get('precision', 2)}f}}"
                    ctrl["entry"].insert(0, fmt.format(v))

        # 2. VARIABLES SIMPLES (Boolean/String)
        mapping = {
            "invert_relief": self.invert_var,
            "include_frame": self.frame_var,
            "include_pointer": self.origin_pointer_var,
            "force_width": self.force_width_var,
            "origin_mode": self.origin_mode,
            "cmd_mode": self.cmd_mode,
            "firing_mode": self.firing_mode,
            "framing_ratio": self.frame_feed_ratio_menu
        }
        for key, var in mapping.items():
            if key in data:
                var.set(data[key])

        # 3. ÉTATS DES WIDGETS ET CAS PARTICULIERS
        
        # Gestion de l'image d'entrée
        raw_path = data.get("input_path", "")
        self.input_image_path = self.app.config_manager.validate_image_path(raw_path)

        if self.input_image_path:
            file_name = os.path.basename(self.input_image_path).upper()
            self._update_button_style(self.btn_input, file_name, True)
        else:
            self._update_button_style(self.btn_input, "SELECT IMAGE", False)

        # Gestion du dossier de sortie
        self.output_dir = data.get("output_dir", self.application_path)
        is_custom_out = self.output_dir and self.output_dir != self.application_path
        out_text = f"OUT: {os.path.basename(self.output_dir).upper()}/" if is_custom_out else "SELECT OUTPUT DIRECTORY"
        self._update_button_style(self.btn_output, out_text, is_custom_out)

        # --- FILTRAGE DES TEXTBOXES ---
        # On ne met à jour les zones de texte blanches QUE si ce n'est PAS de la config machine
        if not is_machine_config:
            if "custom_header" in data:
                self._set_text_widget(self.txt_header, data.get("custom_header"))
            if "custom_footer" in data:
                self._set_text_widget(self.txt_footer, data.get("custom_footer"))

        # Champs spécifiques
        self._set_entry_val(self.frame_power_entry, data.get("frame_power"))
        self._set_entry_val(self.pause_cmd_entry, data.get("custom_pause_cmd"))

        # Rafraîchissement de l'affichage
        self.toggle_framing_options()
        
        # Forcer l'affichage du menu Custom si nécessaire
        if data.get("origin_mode") == "Custom":
            self.custom_offset_frame.pack(fill="x", padx=10, pady=5)
        else:
            self.custom_offset_frame.pack_forget()

        # Update les zones grisées (lecture directe depuis le manager)
        self.refresh_global_previews() 
        self.update_preview()

    def toggle_machine_lock(self):
        """Bascule l'état du verrouillage."""
        self.is_locked = not self.is_locked
        self.apply_lock_state()

    def apply_lock_state(self):
        """Applique l'état visuel complet (verrouillage + grisage des textes et chiffres)."""
        new_state = "disabled" if self.is_locked else "normal"
        new_text = "🔒" if self.is_locked else "🔓"
        
        # Couleurs
        btn_color = "#444444" if self.is_locked else "#D32F2F"
        label_color = "#666666" if self.is_locked else "#FFFFFF" 
        # Pour les entrées : on grise le chiffre lui-même
        entry_text_color = "#888888" if self.is_locked else "#FFFFFF" 

        self.lock_btn.configure(text=new_text, fg_color=btn_color)

        def walk_and_lock(parent):
            for child in parent.winfo_children():
                # 1. Gestion des Entrées (Chiffres dans create_simple_input)
                if isinstance(child, ctk.CTkEntry):
                    child.configure(state=new_state, text_color=entry_text_color)
                
                # 2. Gestion des Menus Déroulants
                elif isinstance(child, (ctk.CTkOptionMenu, ctk.CTkComboBox)):
                    child.configure(state=new_state)

                # 3. Gestion des Labels (Grisage du texte descriptif)
                elif isinstance(child, ctk.CTkLabel):
                    if "GLOBAL" not in child.cget("text").upper():
                        child.configure(text_color=label_color)

                # 4. On descend dans les sous-frames (Récursivité)
                if child.winfo_children():
                    walk_and_lock(child)

        walk_and_lock(self.machine_controls_container)

    def _update_button_style(self, btn, text, is_active):
        """Change la couleur d'un bouton selon s'il a une valeur ou non."""
        color = "#2d5a27" if is_active else ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        hover = "#367a31" if is_active else ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        btn.configure(text=text, fg_color=color, hover_color=hover)

    def refresh_global_previews(self):
        """Met à jour les zones grisées avec les valeurs de la config machine."""
        # Header
        h_glob = self.app.config_manager.get_item("machine_settings", "custom_header", "")
        self.txt_global_header_preview.configure(state="normal")
        self.txt_global_header_preview.delete("1.0", "end")
        self.txt_global_header_preview.insert("1.0", h_glob if h_glob else "(No Global Header)")
        self.txt_global_header_preview.configure(state="disabled")

        # Footer
        f_glob = self.app.config_manager.get_item("machine_settings", "custom_footer", "")
        self.txt_global_footer_preview.configure(state="normal")
        self.txt_global_footer_preview.delete("1.0", "end")
        self.txt_global_footer_preview.insert("1.0", f_glob if f_glob else "(No Global Footer)")
        self.txt_global_footer_preview.configure(state="disabled")

    def update_histogram_ctk(self, matrix, v_min, v_max):
        # --- STOCKAGE SYSTEMATIQUE POUR LE RESIZE ---
        self.last_hist_matrix = matrix
        self.last_hist_vmin = v_min
        self.last_hist_vmax = v_max

        if not hasattr(self, "hist_canvas") or matrix is None:
            return

        canvas = self.hist_canvas
        canvas.delete("all")
        canvas.update_idletasks()

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 50 or height <= 50: return

        # 1. PRÉPARATION DES DONNÉES
        flat_data = matrix.ravel()[::10]
        total_pixels = flat_data.size
        if total_pixels == 0: return

        data_zero = flat_data[flat_data == 0]
        data_active = flat_data[flat_data > 0]
        
        # 2. CALCUL DE L'HISTOGRAMME
        bins = 60
        counts, bin_edges = np.histogram(data_active, bins=bins, range=(v_min, v_max))
        
        # Conversion en POURCENTAGE
        counts_pct = (counts / total_pixels) * 100
        count_zero_pct = (data_zero.size / total_pixels) * 100
        
        # --- LOGIQUE D'ÉCHELLE Y OPTIMISÉE POUR ENTIERS ---
        real_max = np.max(counts_pct) if counts_pct.size > 0 else 0
        
        if real_max > 0:
            # On arrondit à l'entier supérieur (ex: 6.7 -> 7)
            # On s'assure que c'est au moins pair pour que le milieu (50%) soit propre
            y_limit = np.ceil(real_max)
            if y_limit % 2 != 0: y_limit += 1 # Force un nombre pair pour le milieu
        else:
            y_limit = 10

        # 3. LAYOUT ET MARGES
        left_margin = 75 
        right_margin = 40
        top_margin = 30 
        bottom_margin = 55

        total_plot_width = width - left_margin - right_margin
        zero_zone_width = total_plot_width * 0.05 
        active_plot_width = total_plot_width - zero_zone_width
        plot_height = height - top_margin - bottom_margin

        # TITRE
        canvas.create_text(width / 2, 20, text="POWER DISTRIBUTION", fill="white", font=("Arial", 11, "bold"))

        # AXES
        axis_color = "#555555"
        canvas.create_line(left_margin, height - bottom_margin, width - right_margin, height - bottom_margin, fill=axis_color)
        canvas.create_line(left_margin, top_margin, left_margin, height - bottom_margin, fill=axis_color)

        # 4. ZONE OFF
        if count_zero_pct > 0:
            h_ratio = min(count_zero_pct / y_limit, 1.0)
            bar_h = h_ratio * plot_height
            x0_z, x1_z = left_margin + 2, left_margin + zero_zone_width - 2
            canvas.create_rectangle(x0_z, height-bottom_margin, x1_z, height-bottom_margin-bar_h, fill="#EB984E", outline="#A0522D", width=1)
            canvas.create_text((x0_z + x1_z)/2, height-bottom_margin + 12, text="OFF", fill="#EB984E", font=("Arial", 8, "bold"))

        # 5. ZONE ACTIVE (Bleue)
        active_start_px = left_margin + zero_zone_width
        def scale_x_active(val):
            if v_max == v_min: return active_start_px
            return active_start_px + ((val - v_min) / (v_max - v_min)) * active_plot_width

        for i in range(len(counts_pct)):
            if counts_pct[i] <= 0: continue
            x0 = scale_x_active(bin_edges[i])
            x1 = scale_x_active(bin_edges[i+1])
            h_ratio = min(counts_pct[i] / y_limit, 1.0)
            canvas.create_rectangle(x0, height-bottom_margin, x1, height-bottom_margin-(h_ratio * plot_height), fill="#5dade2", outline="#2E86C1", width=1)

        # 6. REPERES MIN / MAX
        min_px = scale_x_active(v_min)
        max_px = scale_x_active(v_max)
        canvas.create_line(min_px, top_margin, min_px, height-bottom_margin, fill="#ffcc00", dash=(4,4))
        canvas.create_line(max_px, top_margin, max_px, height-bottom_margin, fill="#ff3333", dash=(4,4))
        canvas.create_text(min_px, height-bottom_margin + 32, text="MIN", fill="#ffcc00", font=("Arial", 8, "bold"))
        canvas.create_text(max_px, height-bottom_margin + 32, text="MAX", fill="#ff3333", font=("Arial", 8, "bold"))

        # 7. TITRES DES AXES
        canvas.create_text(left_margin + (total_plot_width / 2), height - 25, text="Power Value (%)", fill="#888888", font=("Arial", 9, "italic"))
        canvas.create_text(20, top_margin + (plot_height / 2), text="Distribution (%)", fill="#888888", font=("Arial", 9, "bold"), angle=90)

        # 8. GRADUATIONS X (Valeurs rondes)
        step = 10 if (v_max - v_min) > 40 else 5
        current_val = np.ceil(v_min / step) * step
        while current_val <= v_max:
            px = scale_x_active(current_val)
            if px <= width - right_margin:
                canvas.create_line(px, height-bottom_margin, px, height-bottom_margin + 5, fill=axis_color)
                canvas.create_text(px, height-bottom_margin + 15, text=f"{int(current_val)}", fill="#aaaaaa", font=("Arial", 8))
            current_val += step

        # 9. GRADUATIONS Y (FORCÉES EN ENTIERS)
        # On affiche 0, le milieu (entier ou .5) et le max entier
        for ratio in [0, 0.5, 1.0]:
            py = height - bottom_margin - ratio * plot_height
            val_y = y_limit * ratio
            # On affiche en entier si c'est un rond, sinon avec une décimale
            label_text = f"{int(val_y)}%" if val_y == int(val_y) else f"{val_y:.1f}%"
            canvas.create_text(left_margin - 10, py, text=label_text, fill="#888888", font=("Arial", 7), anchor="e")

    def on_hist_resize(self, event):

        if not hasattr(self, "hist_canvas"):
            return

        try:
            if hasattr(self, "last_hist_matrix"):

                self.update_histogram_ctk(
                    self.last_hist_matrix,
                    self.last_hist_vmin,
                    self.last_hist_vmax
                )

        except Exception:
            pass

    def _set_text_widget(self, widget, text):
        """Remplit un widget de texte CTkTextbox s'il y a une valeur."""
        if text is not None:
            widget.delete("1.0", tk.END)
            widget.insert("1.0", text)

    def _set_entry_val(self, entry, val):
        """Remplit un CTkEntry même s'il est désactivé."""
        if val is not None:
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, str(val))


    def _process_preview_geometry(self, matrix, geom):
        calc_w = geom["real_w"]
        calc_h = geom["real_h"]
        
        # Mise à jour auto de l'entrée Largeur seulement
        ctrl_w = self.controls.get("width")
        if self.force_width_var.get() in [1, True, "1"] and ctrl_w:
            ent_w = ctrl_w["entry"]
            ent_w.delete(0, "end")
            ent_w.insert(0, f"{calc_w:.2f}")

        # Pas de widget height à mettre à jour d'après vos explications, 
        # donc on utilise directement la valeur calculée par l'engine
        real_w = calc_w
        real_h = calc_h

        # Formatage du temps
        total_seconds = int(geom["est_min"] * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return real_w, real_h, geom["x_step"], geom["l_step"], hours, minutes, seconds
    
    def _update_image_artist(self, matrix, offX, offY, real_w, real_h, v_min, v_max):
        # Désactivation définitive du rectangle blanc redondant
        if hasattr(self, 'bg_rect'):
            self.bg_rect.set_visible(False)

        if self.placeholder_text is not None:
            try:
                self.placeholder_text.remove()
            except:
                pass
            self.placeholder_text = None

        # On utilise l'étendue exacte. 
        # Matplotlib avec 'nearest' centrera les pixels sur les coordonnées.
        dx = real_w / (matrix.shape[1] - 1) if matrix.shape[1] > 1 else 0
        dy = real_h / (matrix.shape[0] - 1) if matrix.shape[0] > 1 else 0
        img_extent = [
            offX,
            offX + real_w,
            offY,
            offY + real_h
        ]
        

        if self.img_plot is None:
            self.img_plot = self.ax_img.imshow(
                matrix,
                cmap="gray_r",
                origin='upper',
                extent=img_extent,
                aspect='equal',
                vmin=v_min,
                vmax=v_max,
                interpolation='nearest', # Garde les bords nets
                zorder=1 # Au-dessus de la grille, sous l'overscan
            )

            # Configuration Colorbar
            self.ax_cbar.set_visible(True)
            self.ax_cbar.set_axis_on()
            self.cbar = self.fig_img.colorbar(self.img_plot, cax=self.ax_cbar)
            self.cbar.set_label("Laser Power Level (%)", color='#888888', fontsize=14, labelpad=8)
            self.cbar.ax.tick_params(colors='#888888', labelsize=11)
            self.cbar.outline.set_visible(False)
        else:
            # Update
            self.img_plot.set_data(matrix)
            self.img_plot.set_extent(img_extent)
            self.img_plot.set_clim(v_min, v_max)
            self.img_plot.set_zorder(1)
            if self.cbar is not None:
                self.cbar.update_normal(self.img_plot)
            self.img_plot.set_visible(True)
        



    def _update_dashboard_stats(self, w_px, h_px, real_w, real_h,
                                scan_step, line_step,
                                hours, minutes, seconds, est_size="N/A"):

        if not hasattr(self, "stats_labels"):
            return

        try:
            self.stats_frame.update_idletasks()
            w_px_win = self.stats_frame.winfo_width()
            h_px_win = self.stats_frame.winfo_height()

            dynamic_size = (w_px_win + h_px_win) / 55
            final_font_size = max(8, min(dynamic_size, 22))
        except:
            final_font_size = 14

        stats_lines = [
            f"REAL DIMENSIONS:  {real_w:.2f} x {real_h:.2f} mm",
            f"ESTIMATED TIME:   {hours:02d}:{minutes:02d}:{seconds:02d}",
            f"FILE SIZE:        {est_size}",
            f"MATRIX SIZE:      {w_px} x {h_px} px",
            f"SCAN STEP:        {scan_step:.4f} mm",
            f"LINE STEP:        {line_step:.4f} mm"
        ]

        for lbl, txt in zip(self.stats_labels, stats_lines):
            lbl.configure(
                text=txt,
                font=("Consolas", int(final_font_size))
            )

    def _on_raster_dir_change(self, selected_translated_value):
        tech_value = self.raster_map_inv.get(selected_translated_value)
        self.raster_dir_var.set(tech_value)
        
        if tech_value == "vertical":
            w_text = self.common.get("target_height", "Target Height")
            f_text = self.common.get("force_height", "Force Exact Height")
        else:
            w_text = self.common.get("target_width", "Target Width")
            f_text = self.common.get("force_width", "Force Exact Width")
            
        # Ces appels ne planteront plus car les widgets sont bien référencés
        if hasattr(self, "width_label_widget"):
            self.width_label_widget.configure(text=w_text)
            
        if hasattr(self, "force_w_label"):
            self.force_w_label.configure(text=f_text)
        
        self.update_preview()

    def _update_histogram_async(self, matrix, v_min, v_max):

        if not hasattr(self, "hist_canvas"):
            return

        def delayed_hist():
            self.hist_canvas.update_idletasks()
            self.update_histogram_ctk(matrix, v_min, v_max)

        self.hist_canvas.after(50, delayed_hist)

    def get_ui_params(self):
        """Récupère les paramètres de l'UI pour l'Engine."""
        try:
            # 1. Récupération de la largeur
            ctrl_w = self.controls.get("width") or self.controls.get("w")
            width = float(ctrl_w["entry"].get().replace(',', '.')) if ctrl_w else 10.0
            
            # 2. Récupération de la vitesse (on change 'speed' en 'feedrate')
            ctrl_s = self.controls.get("speed")
            feedrate = float(ctrl_s["entry"].get().replace(',', '.')) if ctrl_s else 3000.0
            
            # 3. DPI et Pas de ligne
            dpi = int(self.get_val(self.controls.get("dpi"))) if self.controls.get("dpi") else 254
            l_step = float(self.get_val(self.controls.get("line_step", 0.1)))
            
            # 4. Overscan (premove)
            overscan = float(self.get_val(self.controls.get("premove"))) if "premove" in self.controls else 2.0
            
            # 5. Récupération du mode (Horizontal/Vertical)
            # On vérifie si vous utilisez une variable tkinter ou un attribut
            if hasattr(self, "raster_dir_var"):
                r_mode = self.raster_dir_var.get()
            else:
                r_mode = getattr(self, "raster_mode", "Horizontal")

            return {
                "width": width,
                "height": 0,       # Sera calculé via le ratio de l'image
                "dpi": dpi,
                "line_step": l_step,
                "feedrate": feedrate, 
                "premove": overscan,  
                "raster_mode": r_mode
            }
        except Exception as e:
            print(f"Erreur get_ui_params: {e}")
            return {
                "width": 10, "height": 0, "dpi": 254, 
                "line_step": 0.1, "feedrate": 3000, 
                "premove": 2.0, "raster_mode": "Horizontal"
            }