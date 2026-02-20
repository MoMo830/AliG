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
import sys
import json
import os
import webbrowser

from ..widgets import ToolTip, PowerRangeVisualizer
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
        self.update_preview()


    def on_closing(self):
        self.save_settings()
        plt.close('all')
        self.destroy()
        sys.exit()

    def setup_ui(self):

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR (PANNEAU GAUCHE) ---
        self.sidebar = ctk.CTkFrame(self, width=380)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.sidebar.grid_rowconfigure(0, weight=0)  # File frame
        self.sidebar.grid_rowconfigure(1, weight=0)  # Profile frame
        self.sidebar.grid_rowconfigure(2, weight=1)  # TABVIEW (PREND TOUT)
        self.sidebar.grid_rowconfigure(3, weight=0)  # GENERATE
        self.sidebar.grid_rowconfigure(4, weight=0)  # LINKS
        self.sidebar.grid_columnconfigure(0, weight=1)

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


        profile_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        profile_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.btn_load_prof = ctk.CTkButton(profile_frame, text=self.common["import_profile"], width=140, height=28, fg_color="#444444", command=self.load_profile_from)
        self.btn_load_prof.pack(side="left", expand=True, padx=(0, 2))

        self.btn_save_prof = ctk.CTkButton(profile_frame, text=self.common["export_profile"], width=140, height=28, fg_color="#444444", command=self.export_profile)
        self.btn_save_prof.pack(side="right", expand=True, padx=(2, 0))
        # --- ONGLETS  ---
        self.tabview = ctk.CTkTabview(self.sidebar)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=(10, 10), pady=5)



        # --- PIED DE PAGE SIDEBAR (A FAIRE EN PREMIER POUR LE BAS) ---
        self.btn_gen = ctk.CTkButton(
            self.sidebar, 
            text=self.common["generate_gcode"],
            fg_color="#1f538d",
            hover_color="#2a6dbd",
            height=50,
            font=("Arial", 13, "bold"),
            command=self.generate_gcode
        )
        self.btn_gen.grid(row=3, column=0, sticky="ew", padx=20, pady=(5,10))

        # --- 4. CONFIGURATION DU CONTENU ---
        self.tab_geom_name = self.common.get("geometry", "Geometry")
        self.tab_img_name  = self.common.get("image", "Image")
        self.tab_laser_name = self.common.get("laser", "Laser")
        self.tab_gcode_name = self.common.get("gcode", "G-Code")

        # 2. On ajoute les onglets (SANS le paramètre 'text=')
        self.tabview.add(self.tab_geom_name)
        self.tabview.add(self.tab_img_name)
        self.tabview.add(self.tab_laser_name)
        self.tabview.add(self.tab_gcode_name)

        self._setup_tabs_content()  

        # --- VIEWPORT (ZONE DE DROITE) ---
        self.view_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.view_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.view_frame.grid_columnconfigure(0, weight=1)
        self.view_frame.grid_rowconfigure(0, weight=4) # Zone Image
        self.view_frame.grid_rowconfigure(1, weight=1) # Zone Stats

        # --- 1. FIGURE IMAGE (HAUT) ---
        # On utilise une frame CTk pour faire une bordure propre
        self.img_container = ctk.CTkFrame(self.view_frame, fg_color="#1e1e1e", border_width=1, border_color="#333333")
        self.img_container.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        self.fig_img = plt.figure(figsize=(5, 5), facecolor='#1e1e1e')
        # GridSpec pour Image (95%) et Colorbar (5%)
        gs_img = self.fig_img.add_gridspec(1, 2, width_ratios=[25, 1], wspace=0.02, left=0.08, right=0.92, top=0.92, bottom=0.08)
        self.ax_img = self.fig_img.add_subplot(gs_img[0, 0])
        self.ax_cbar = self.fig_img.add_subplot(gs_img[0, 1])
        
        self.ax_img.set_facecolor('#1e1e1e')
        self.ax_cbar.set_visible(False)
        
        self.canvas_img = FigureCanvasTkAgg(self.fig_img, master=self.img_container)
        self.canvas_img.get_tk_widget().pack(fill="both", expand=True)
        self.canvas_img.get_tk_widget().config(bg='#1e1e1e', highlightthickness=0)

        # --- 2. FIGURE STATS (BAS) ---
        self.stats_container = ctk.CTkFrame(self.view_frame, fg_color="#202020", border_width=1, border_color="#333333")
        self.stats_container.grid(row=1, column=0, sticky="nsew")
        
        self.fig_stats = plt.figure(figsize=(5, 1.5), facecolor='#202020')

        # Utilisation de self. pour permettre la modification dynamique plus tard
        # On initialise avec des valeurs par défaut (33% / 67%)
        self.gs_left = self.fig_stats.add_gridspec(1, 1, left=0.0, right=0.33, top=1.0, bottom=0.0)
        self.gs_right = self.fig_stats.add_gridspec(1, 1, left=0.42, right=0.96, top=0.82, bottom=0.28)

        self.ax_info = self.fig_stats.add_subplot(self.gs_left[0, 0])
        self.ax_hist = self.fig_stats.add_subplot(self.gs_right[0, 0])

        self.ax_hist.set_facecolor('#202020')
        self.ax_info.set_facecolor('#202020')
        
        self.ax_hist.set_visible(False)
        self.ax_info.set_visible(False)
        
        self.canvas_stats = FigureCanvasTkAgg(self.fig_stats, master=self.stats_container)
        self.canvas_stats.get_tk_widget().pack(fill="both", expand=True)
        self.canvas_stats.get_tk_widget().config(bg='#202020', highlightthickness=0)


        # Initialisation des éléments graphiques persistants
        self.bg_rect = plt.Rectangle((0, 0), 0, 0, color='white', zorder=-2)
        self.ax_img.add_patch(self.bg_rect)
        self.img_plot = None
        self.origin_dot = None
        
        # Placeholder
        self.placeholder_text = self.ax_img.text(0.5, 0.5, self.common["choose_image"], 
                                              color='#444444', fontsize=12, fontweight='bold',
                                              ha='center', va='center', transform=self.ax_img.transAxes)

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
        self.create_input_pair(t_geo, self.common["target_width"], 5, 400, 30.0, "width")
        
        force_w_frame = ctk.CTkFrame(t_geo, fg_color="transparent")
        force_w_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(force_w_frame, text=self.common["force_width"], font=("Segoe UI", 11)).pack(side="left")
        self.force_width_var = ctk.BooleanVar(value=False)
        self.sw_force_width = ctk.CTkSwitch(force_w_frame, text="", variable=self.force_width_var, width=45, command=self.update_preview)
        self.sw_force_width.pack(side="right")

        self.create_input_pair(t_geo, self.common["line_step"], 0.01, 1.0, 0.1307, "line_step", precision=4)
        self.create_input_pair(t_geo, self.common["dpi_resolution"], 10, 1200, 254, "dpi", is_int=True)
        
        # --- AJOUT DU SENS DU RASTER (Intégré dans l'onglet Geometry) ---
        raster_frame = ctk.CTkFrame(t_geo, fg_color="transparent")
        raster_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(raster_frame, text=self.common["raster_mode"], font=("Segoe UI", 11)).pack(side="left")
        
        self.raster_dir_var = ctk.StringVar(value="Horizontal")
        self.raster_dir_btn = ctk.CTkSegmentedButton(
            t_geo, 
            values=["Horizontal", "Vertical"],
            variable=self.raster_dir_var,
            command=lambda _: self.update_preview(),
            height=28,
        )
        self.raster_dir_btn.pack(pady=(0, 10), padx=10, fill="x")
        
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

        self.create_input_pair(t_laser, self.common["laser_latency"], 0, 50, 11.5, "m67_delay")
        self.create_input_pair(t_laser, self.common["gray_steps"], 2, 256, 256, "gray_steps", is_int=True)

        # --- TAB 4: G-CODE ---
        t_gc = prepare_tab(self.tab_gcode_name)
        
        # Initialisation des variables de contrôle
        self.origin_pointer_var = tk.BooleanVar(value=False)
        self.frame_var = tk.BooleanVar(value=False)

        # 1. Mode de commande (M67 / Spindle) avec style unifié
        self.create_dropdown_pair(t_gc, self.common["cmd_mode"], ["M67 (Analog)", "S (Spindle)"], "cmd_mode")
        self.cmd_mode.set("M67 (Analog)")

        # M67 E 
        row_e = ctk.CTkFrame(t_gc, fg_color="transparent")
        row_e.pack(fill="x", padx=10, pady=2)
        self.create_simple_input(row_e, self.common["m67_output"], 0, "m67_e_num", precision=0)

        # Controller Max 
        row_max = ctk.CTkFrame(t_gc, fg_color="transparent")
        row_max.pack(fill="x", padx=10, pady=2)
        self.create_simple_input(row_max, self.common["ctrl_max_value"], 100, "ctrl_max", precision=0)

        # 2. Firing mode (M3/M4)
        self.create_dropdown_pair(t_gc, self.common["firing_mode"], ["M3/M5", "M4/M5"], "firing_mode")
        self.firing_mode.set("M3/M5")

        # 3. Textboxes Header/Footer avec Labels descriptifs
        # Header
        h_label_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        h_label_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(h_label_frame, text=self.common["gcode_header"], font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(h_label_frame, text=self.common["at_start"], font=("Arial", 10, "italic"), text_color="#888888").pack(side="left")
        
        self.txt_header = ctk.CTkTextbox(t_gc, font=("Consolas", 11), height=40, border_width=1, border_color="#444444")
        self.txt_header.pack(fill="x", padx=10, pady=(2, 5))

        # Footer
        f_label_frame = ctk.CTkFrame(t_gc, fg_color="transparent")
        f_label_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(f_label_frame, text=self.common["gcode_footer"], font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(f_label_frame, text=self.common["before_m30"], font=("Arial", 10, "italic"), text_color="#888888").pack(side="left")
        
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
            
        return self.controls[key]

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
        if not self.input_image_path or not os.path.isfile(self.input_image_path):
            print(f"DEBUG: Chemin invalide détecté -> {self.input_image_path}")
            return None, 0, 0, 0, 0, 0

        # 1. On prépare les réglages dans un dictionnaire
        settings = {
            "width": self.get_val(self.controls["width"]),
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
            "invert": self.invert_var.get(),
            "force_width": self.force_width_var.get(),
            "raster_mode": self.raster_dir_var.get() 
        }

        # 2. GESTION DU CACHE
        current_cache = None
        if hasattr(self, '_source_img_path') and self._source_img_path == self.input_image_path:
            current_cache = getattr(self, '_source_img_cache', None)

        # 3. APPEL DU MOTEUR
        try:
            results = self.engine.process_image_logic(
                  self.input_image_path, 
                  settings, 
                  source_img_cache=current_cache
            )
            
            # Récupération des 9 valeurs (incluant latency_mm à la fin)
            # matrix, h_px, w_px, l_step_val, x_step, est_min, mem_warn, img_obj, lat = results
            matrix, h_px, w_px, l_step, x_st, est_min, mem_warn, img_obj, _ = results
            
            if hasattr(self, 'label_matrix_size'):
                color = "#e74c3c" if mem_warn else "#aaaaaa"
                self.label_matrix_size.configure(text_color=color)

            # 4. MISE À JOUR DU CACHE
            self._source_img_cache = img_obj
            self._source_img_path = self.input_image_path

            # Stockage du résultat pour generate_gcode
            self._last_result = (matrix, h_px, w_px, l_step, x_st, est_min)

            return matrix, h_px, w_px, l_step, x_st, est_min

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Preview Error: {e}")
            return None, 0, 0, 0, 0, 0

    def update_preview(self):
        if not hasattr(self, 'controls') or 'width' not in self.controls:
            return
        if not hasattr(self, 'origin_mode'):
            return

        try:
            matrix, h_px, w_px, l_step, x_st, est_min = self.process_logic()
            
            if matrix is None: 
                # On ne met plus à jour les labels de la sidebar, on rafraîchit juste le canvas
                self.canvas_img.draw_idle()
                return
            
            # --- 1. ACTIVATION DES AXES ---
            self.ax_cbar.set_visible(True)
            self.ax_hist.set_visible(True)
            self.ax_info.set_visible(True)
            self.ax_img.set_axis_on() 

            if hasattr(self, 'placeholder_text') and self.placeholder_text is not None:
                self.placeholder_text.remove()
                self.placeholder_text = None  
                
            # --- 2. CALCULS DES DONNÉES ---
            real_w = (w_px - 1) * x_st
            real_h = (h_px - 1) * l_step
            total_seconds = int(est_min * 60)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # (Anciens labels Tkinter de la Sidebar supprimés ici)

            premove = self.get_val(self.controls["premove"])
            offX, offY = self.calculate_offsets(real_w, real_h)
            v_min, v_max = self.get_val(self.controls["min_p"]), self.get_val(self.controls["max_p"])

            # --- 3. RECTANGLE DE ZONE (ZORDER -1) ---
            self.bg_rect.set_xy((offX - premove, offY))
            self.bg_rect.set_width(real_w + (2 * premove))
            self.bg_rect.set_height(real_h)
            self.bg_rect.set_visible(True)

            # --- 4. AFFICHAGE DE L'IMAGE (CANVAS DU HAUT) ---
            if self.img_plot is None:
                self.img_plot = self.ax_img.imshow(matrix, cmap="gray_r", origin='upper', 
                                            extent=[offX, offX + real_w, offY, offY + real_h], 
                                            aspect='equal', vmin=v_min, vmax=v_max, zorder=0)
                self.cbar = self.fig_img.colorbar(self.img_plot, cax=self.ax_cbar) 
                self.cbar.set_label("Power Intensity (%)", color='#888888', fontsize=16, labelpad=10)
                self.cbar.ax.tick_params(labelcolor='#888888', labelsize=12)
                self.cbar.outline.set_visible(False)
            else:
                self.img_plot.set_data(matrix)
                self.img_plot.set_extent([offX, offX + real_w, offY, offY + real_h])
                self.img_plot.set_clim(v_min, v_max)

            # --- 5. GRILLE ET ESTHÉTIQUE IMAGE ---
            self.ax_img.tick_params(axis='both', colors='#888888', labelsize=12)
            self.ax_img.grid(True, color='#444444', linestyle=':', linewidth=0.5, alpha=0.6, zorder=10)
            
            self.ax_img.set_xlim(offX - premove - 2, offX + real_w + premove + 2)
            self.ax_img.set_ylim(offY - 2, offY + real_h + 2)

            if hasattr(self, 'origin_dot') and self.origin_dot:
                for line in self.origin_dot: line.remove()
            self.origin_dot = self.ax_img.plot(0, 0, 'ro', markersize=6, zorder=20)
            self.ax_img.set_title("PATH PREVIEW", color='white', fontsize=20, fontweight='bold')

            # --- 6. HISTOGRAMME (À DROITE) ---
            self.ax_hist.clear() 
            self.ax_hist.set_facecolor('#1a1a1a') 
            
            flat_data = matrix.ravel()[::10]
            if flat_data.size > 0:
                r_min = min(flat_data.min(), v_min-5)
                r_max = max(flat_data.max(), v_max+5)
                
                self.ax_hist.hist(flat_data, bins=100, 
                                range=(r_min, r_max), 
                                color='#5dade2', alpha=0.9)
                
                self.ax_hist.axvline(v_min, color='#ffcc00', linestyle='--', linewidth=1.5, label="Min")
                self.ax_hist.axvline(v_max, color='#ff3333', linestyle='--', linewidth=1.5, label="Max")

            self.ax_hist.set_title("POWER DISTRIBUTION", color='white', fontsize=20, fontweight='bold', pad=10)
            self.ax_hist.set_xlabel("Laser Power Level", color='#aaaaaa', fontsize=14)
            self.ax_hist.set_ylabel("Pixel Count", color='#aaaaaa', fontsize=14)
            self.ax_hist.tick_params(colors='#888888', labelsize=14)
            
            for spine in self.ax_hist.spines.values():
                spine.set_edgecolor('#333333')

            # --- 7. PANNEAU D'INFORMATIONS (DYNAMIQUE) ---
            self.ax_info.clear()
            self.ax_info.set_facecolor('#202020')
            self.ax_info.set_xticks([]); self.ax_info.set_yticks([])

            lines = [
                f"ESTIMATED TIME:  {hours:02d}:{minutes:02d}:{seconds:02d}",
                f"MATRIX SIZE:     {w_px} x {h_px} px",
                f"REAL DIMENSIONS: {real_w:.2f} x {real_h:.2f} mm",
                f"PIXEL PITCH X:   {x_st:.4f} mm",
                f"PIXEL PITCH Y:   {l_step:.4f} mm"
            ]
            info_text = "\n".join(lines)

            # --- CALCUL DE LA LARGEUR NÉCESSAIRE ---
            # On prend la ligne la plus longue et on estime la place (environ 0.008 par caractère monospace)
            max_chars = max(len(l) for l in lines)
            # Ratio de la largeur de la figure (ajuste 0.0085 selon tes tests)
            needed_width = max_chars * 0.0085 
            
            # Sécurité : entre 20% et 45% de la largeur totale
            final_ratio = min(max(needed_width, 0.20), 0.45)

            # Mise à jour des grilles
            self.gs_left.update(right=final_ratio)
            self.gs_right.update(left=final_ratio + 0.08) # Marge de 8% entre les deux

            self.ax_info.text(0.05, 0.5, info_text, color='#aaaaaa', 
                            fontfamily='monospace', fontsize=20, 
                            ha='left', va='center', linespacing=1.6, 
                            transform=self.ax_info.transAxes)
            
            # --- 8. FINALISATION ---
            self.canvas_img.draw_idle()
            self.canvas_stats.draw_idle()

            if hasattr(self, 'power_viz'):
                self.power_viz.refresh_visuals()

        except MemoryError:
            messagebox.showerror("Memory Error", "Resolution too high for RAM.")
        except Exception as e:
            print(f"Preview Error: {e}")


    def generate_gcode(self):
        self.save_settings() # Sauvegarde paramètres
        # --- 0. CAPTURE SÉCURISÉE DES WIDGETS ---
        try:
            current_cmd_mode = self.cmd_mode.get()
            current_firing_mode = self.firing_mode.get()
            current_origin_mode = self.origin_mode.get()
            # Capture du nouveau paramètre de sens
            current_raster_mode = self.raster_dir_var.get() 
        except AttributeError: return

        # --- 1. RÉCUPÉRATION / CALCUL DES DONNÉES DE BASE ---
        if hasattr(self, '_last_result'):
            # Note : assurez-vous que process_logic() a été appelé avec le bon raster_mode
            # pour que l'estimation de temps (est_min) soit déjà correcte ici.
            matrix, h_px, w_px, l_step, x_st, est_min = self._last_result[0:6]
        else:
            res = self.process_logic()
            if not res: return
            matrix, h_px, w_px, l_step, x_st, est_min = res[0:6]
        
        if matrix is None: return

        real_w = (w_px - 1) * x_st
        real_h = (h_px - 1) * l_step
        offX, offY = self.calculate_offsets(real_w, real_h)

        # --- 2. PACKAGING DU PAYLOAD ---
        payload = {
            'matrix': matrix,
            'dims': (h_px, w_px, l_step, x_st),
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
                'header': self.txt_header.get("1.0", "end-1c").strip(),
                'footer': self.txt_footer.get("1.0", "end-1c").strip()
            },
            'metadata': {
                'version': self.version,
                'mode': current_cmd_mode.split(' ')[0],
                'firing_cmd': current_firing_mode.split('/')[0],
                'file_name': os.path.basename(self.input_image_path).split('.')[0] + ".nc",
                'output_dir': self.output_dir, 
                'origin_mode': current_origin_mode,
                'real_w': real_w, 'real_h': real_h,
                'est_sec': int(est_min * 60),
                # Optionnel : pour info dans les logs
                'raster_direction': current_raster_mode 
            }
        }

        # --- 3. LANCEMENT DE LA VUE SIMULATION ---
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
        """Sauvegarde automatique via le gestionnaire de configuration global."""
        # 1. On récupère toutes les données de l'interface
        data = self.get_all_settings_data()
        
        # 2. On met à jour la section dédiée dans le manager central
        self.app.config_manager.set_section("raster_settings", data)
        
        # 3. On demande au manager de sauvegarder physiquement le fichier
        if not self.app.config_manager.save():
            print("Auto-save error: Failed to write global config file.")
            
    def load_settings(self):
        """Chargement automatique depuis le manager centralisé au démarrage."""
        # On récupère la section "raster_settings" depuis le manager
        data = self.app.config_manager.get_section("raster_settings")
        
        if data:
            # On applique les données à l'interface
            self.apply_settings_data(data)
            


    def export_profile(self):
        """Export manuel vers un fichier choisi."""
        file_path = filedialog.asksaveasfilename(
            initialdir=self.application_path,
            title="Export Profile As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="my_laser_settings.json"
        )
        if file_path:
            data = self.get_all_settings_data()
            success, err = save_json_file(file_path, data)
            if success:
                messagebox.showinfo("Export Success", "Profile saved!")
            else:
                messagebox.showerror("Export Error", f"Failed: {err}")

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

    def apply_settings_data(self, data):
        """Applique intelligemment les réglages à l'interface."""
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

        # 3. ÉTATS DES WIDGETS ET COULEURS (Les cas particuliers)
        
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

        # Champs textes libres
        self._set_text_widget(self.txt_header, data.get("custom_header"))
        self._set_text_widget(self.txt_footer, data.get("custom_footer"))
        self._set_entry_val(self.frame_power_entry, data.get("frame_power"))
        self._set_entry_val(self.pause_cmd_entry, data.get("custom_pause_cmd"))

        # Rafraîchissement de l'affichage
        self.toggle_framing_options()
        # Forcer l'affichage du menu Custom si nécessaire
        if data.get("origin_mode") == "Custom":
            self.custom_offset_frame.pack(fill="x", padx=10, pady=5)
        else:
            self.custom_offset_frame.pack_forget()
            
        self.update_preview()

    def _update_button_style(self, btn, text, is_active):
        """Change la couleur d'un bouton selon s'il a une valeur ou non."""
        color = "#2d5a27" if is_active else ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        hover = "#367a31" if is_active else ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        btn.configure(text=text, fg_color=color, hover_color=hover)

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