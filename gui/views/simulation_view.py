
"""
A.L.I.G. Project - Simulation window
------------------------------------
"""

import customtkinter as ctk
import numpy as np
import sys
import os
import time
import re
from PIL import Image,ImageTk, ImageDraw
from tkinter import messagebox
import cv2

from engine.gcode_parser import GCodeParser
from utils.gui_utils import apply_window_icon, setup_toplevel_window, bind_minimize_sync

class SimulationView(ctk.CTkFrame):
    def __init__(self, parent, controller, engine, payload, return_view="dashboard"):
        super().__init__(parent)
        self.controller = controller
        self.return_view = return_view
        self.parent = parent
        
        # 1. Stockage
        self.engine = engine
        self.payload = payload
        #self.stats = payload['metadata']
        self.matrix = payload['matrix']
        #self.premove = payload['params']['premove']

        self.ctrl_max = float(self.payload.get('params', {}).get('ctrl_max', 255))  
        
        self.confirmed = False
        self.final_gcode = ""
        self.framing_gcode = ""

        # --- INITIALISATION DU PARSER ---
        self.parser = GCodeParser(self.payload)

        # 2. États
        self.sim_running = False
        self.animation_job = None
        self.points_list = [] 
        self.current_point_idx = 0
        self.last_mouse_coords = (0, 0)
        self.last_frame_time = 0.0 
        self.accumulated_index = 0.0
        self.sim_speed = 1.0 
        

        self.framing_duration = 0.0 
        self.total_sim_seconds = 0.0
        self.loupe_active = False
        self.loupe_size = 150        
        self.loupe_zoom = 3.0    
        self.raw_sim_data = None    
        self.origin_mode = payload["metadata"].get("origin_mode", "Lower-Left")


        # 3. Configuration UI
        self.grid_columnconfigure(0, weight=0, minsize=200) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)

        # 4. Construction des panneaux
        self._build_left_panel(self.payload)
        self._build_right_panel()


        # 5. OVERLAY DE CHARGEMENT
        self.loading_frame = ctk.CTkFrame(self.preview_canvas, fg_color="#2b2b2b", corner_radius=10)
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")

        self.loading_label = ctk.CTkLabel(
            self.loading_frame, 
            text="Generating G-Code & Trajectory...",
            font=("Arial", 14, "bold"),
            text_color="white"
        )
        self.loading_label.pack(padx=20, pady=(15, 5))

        self.gen_progress = ctk.CTkProgressBar(self.loading_frame, width=250)
        self.gen_progress.pack(padx=20, pady=(5, 20))
        self.gen_progress.configure(mode="indeterminate")
        self.gen_progress.start()

        if self.winfo_exists():
            self.update_idletasks() # Force l'UI à dessiner l'overlay maintenant
        # 6. LANCEMENT DU CALCUL DÉFÉRÉ
        self.after(100, self._start_thread)

    def _start_thread(self):
        import threading
        threading.Thread(target=self._async_generation, daemon=True).start()

    def _async_generation(self):
        try:
            # 1. PRÉPARATION DES PARAMÈTRES
            params = self.payload['params']
            g_steps = params.get('gray_steps')
            use_s_mode = params.get('use_s_mode')

            self.payload['framing']['gray_steps'] = g_steps
            self.payload['framing']['use_s_mode'] = use_s_mode

            # A. Génération du G-Code de Cadrage (indépendant pour référence)
            self.framing_gcode = self.engine.prepare_framing(
                self.payload['framing'], 
                (self.payload['metadata']['real_w'], self.payload['metadata']['real_h']), 
                self.payload['offsets']
            )

            # B. Métadonnées complètes
            full_metadata = self.payload['metadata'].copy()
            full_metadata['framing_code'] = self.framing_gcode
            full_metadata['gray_steps'] = g_steps
            full_metadata['use_s_mode'] = use_s_mode

            # C. Génération du G-Code Final 
            # Note : On suppose que build_final_gcode inclut déjà le framing_code au début
            self.final_gcode = self.engine.build_final_gcode(
                self.payload['matrix'], self.payload['dims'],
                self.payload['offsets'], params,
                self.payload['text_blocks'], full_metadata
            )

            # D. PARSING STRATÉGIQUE
            # 1. On parse le framing seul uniquement pour connaître sa durée et son volume de points
            f_points_tmp, f_dur = self.parser.parse(self.framing_gcode)
            framing_end_idx = len(f_points_tmp)

            # 2. On parse le G-Code FINAL complet (qui contient Framing + Image)
            all_points, total_dur = self.parser.parse(self.final_gcode)

            # 2. PRÉPARATION DU RETOUR
            # On envoie une structure propre : une seule liste de points et l'index de transition
            self.raw_sim_data = {
                'points_list': all_points,          # La séquence continue (sans rupture)
                'framing_end_idx': framing_end_idx, # Pour savoir quand arrêter de dessiner
                'f_dur': f_dur,                     # Pour l'affichage du temps
                'i_dur': total_dur - f_dur,         # Durée de l'image seule
                'total_dur': total_dur,
                'full_metadata': full_metadata 
            }

            self.after(0, self._on_gen_done)
            if self.winfo_exists():
                self.after(0, self._on_gen_done)
            
        except Exception as e:
            if self.winfo_exists():
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._handle_gen_error(msg))

    def _handle_gen_error(self, msg):
        messagebox.showerror("Engine Error", f"Failed to generate G-code:\n{msg}")
        self.destroy()

    def _on_gen_done(self):
        # On récupère les stats calculées
        self.stats = self.raw_sim_data['full_metadata']
        
        # On détruit la barre de chargement
        if hasattr(self, 'loading_frame'):
            self.loading_frame.destroy()

        # CGcode text loading
        self.gcode_view.configure(state="normal")
        self.gcode_view.delete("1.0", "end")
        self.gcode_view.insert("1.0", self.final_gcode)
        self.gcode_view.configure(state="disabled")
        # On lance l'affichage final
        self._prepare_and_draw()


    def _prepare_and_draw(self):
        # 1. On force la mise à jour pour que le Canvas ait sa taille finale 
        # définie par setup_toplevel_window
        #self.update_idletasks()

        # 2. On récupère la taille RÉELLE du canvas à cet instant précis
        c_w = self.preview_canvas.winfo_width()
        c_h = self.preview_canvas.winfo_height()

        # SÉCURITÉ : Si vraiment le canvas n'est pas encore rendu (winfo = 1)
        # On ne dessine rien et on recommence un peu plus tard
        if c_w <= 1:
            self.after(50, self._prepare_and_draw)
            return

        # --- 1. RÉCUPÉRATION DES DONNÉES ---
        self.points_list = self.raw_sim_data.get('points_list', [])
        if not self.points_list:
            return

        # On récupère l'index de coupure et les durées pré-calculées
        self.framing_end_idx = self.raw_sim_data['framing_end_idx']
        self.framing_duration = self.raw_sim_data['f_dur']
        self.total_sim_seconds = self.raw_sim_data['total_dur']
        self.image_duration = self.raw_sim_data['i_dur']

        # --- 2. LIMITES MACHINE ---
        # On calcule les limites sur la liste complète pour le centrage
        raw_x = [p[0] for p in self.points_list]
        raw_y = [p[1] for p in self.points_list]

        self.min_x_machine = min(raw_x)
        self.min_y_machine = min(raw_y)
        self.total_mouvement_w = max(raw_x) - self.min_x_machine
        self.total_mouvement_h = max(raw_y) - self.min_y_machine

        # --- 3. ÉCHELLE ET DIMENSIONS ---
        self.scale = min(
            (c_w * 0.85) / max(1, self.total_mouvement_w),
            (c_h * 0.8) / max(1, self.total_mouvement_h)
        )

        self.total_px_w = self.total_mouvement_w * self.scale
        self.total_px_h = self.total_mouvement_h * self.scale
        self.rect_w, self.rect_h = int(self.total_px_w), int(self.total_px_h)

        self.x0 = (c_w - self.total_px_w) / 2
        self.y0 = (c_h - self.total_px_h) / 2

        # Épaisseur du laser
        self.l_step = self.payload['dims'][2]
        self.laser_width_px = max(1, int(self.l_step * self.scale))

        # --- 4. CALCUL DU DÉBIT (PPS) ---
        # Nombre de points pour chaque phase
        n_pts_framing = self.framing_end_idx
        n_pts_image = len(self.points_list) - n_pts_framing

        self.pts_per_sec_framing = n_pts_framing / max(0.1, self.framing_duration)
        self.pts_per_sec_image = n_pts_image / max(0.1, self.image_duration)

        # --- 5. INITIALISATION GRAPHIQUE ---
        self.draw_simulation(self.stats)

        # Position initiale du laser
        mx, my, _, _ = self.points_list[0]
        sx, sy = self.machine_to_screen(mx, my)
        self.curr_x, self.curr_y = sx, sy
        
        # --- ANTI-FANTÔME ---
        # On initialise avec None pour forcer le premier point de l'image 
        # à se positionner sans tracer de ligne depuis le framing.
        self.prev_matrix_coords = None 
        self.current_point_idx = 0
        self.accumulated_index = 0.0

        # Mise à jour de l'UI
        t_total = self._format_seconds_to_hhmmss(self.total_sim_seconds)
        self.time_label.configure(text=f"Time: 00:00:00 / {t_total}")



    def _build_left_panel(self, payload):
        self.left_panel = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.left_panel.grid_propagate(False) 
        
        ctk.CTkLabel(self.left_panel, text="PATH SIMULATION", font=("Arial", 14, "bold")).pack(pady=15)
        
        # 1. Stats Scrollable
        info_scroll = ctk.CTkScrollableFrame(self.left_panel, fg_color="transparent")
        info_scroll.pack(fill="both", expand=True, padx=5)
        
        excluded = [
            "pixel_size", "min_power", "max_power", 
            "is_pointing", "is_framing", "est_sec",
            "pixel_size_x", "pixel_size_y"
        ]
        
        for label, val in payload.items():
            if label not in excluded:
                row = ctk.CTkFrame(info_scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                clean_label = label.replace("_", " ").capitalize()
                ctk.CTkLabel(row, text=clean_label, font=("Arial", 10, "bold"), width=80, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=str(val), font=("Arial", 10), anchor="e", wraplength=100).pack(side="right", fill="x", expand=True)

        # Temps formaté
        t_sec = payload.get("est_sec", 0)
        time_str = f"{int(t_sec // 60)}:{int(t_sec % 60):02d}"

        time_frame = ctk.CTkFrame(info_scroll, fg_color="transparent")
        time_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(time_frame, text="Estimated Time:", font=("Arial", 10, "bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(time_frame, text=time_str, font=("Arial", 10), anchor="e").pack(side="right", fill="x", expand=True)

        # Échelle de Puissance
        p_min, p_max = float(payload.get("min_power", 0)), float(payload.get("max_power", 100))
        power_scale_frame = ctk.CTkFrame(info_scroll, fg_color="transparent")
        power_scale_frame.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(power_scale_frame, text="Power Range (0-100%)", font=("Arial", 10, "bold")).pack(anchor="w")

        self.power_canvas = ctk.CTkCanvas(power_scale_frame, height=45, bg="#1a1a1a", highlightthickness=0)
        self.power_canvas.pack(fill="x", pady=5)

        def draw_power_scale():
            self.power_canvas.update()
            w = max(self.power_canvas.winfo_width(), 180)
            margin, bar_y, bar_h = 15, 22, 8
            bar_w = w - (2 * margin)
            for i in range(int(bar_w)):
                cv = int((1 - (i / bar_w)) * 255)
                self.power_canvas.create_line(margin + i, bar_y, margin + i, bar_y + bar_h, fill=f'#{cv:02x}{cv:02x}{cv:02x}')
            self.power_canvas.create_rectangle(margin, bar_y, margin + bar_w, bar_y + bar_h, outline="#444")
            for val, prefix in [(p_min, "Min: "), (p_max, "Max: ")]:
                x = margin + (val / 100 * bar_w)
                self.power_canvas.create_polygon([x, bar_y-2, x-5, bar_y-9, x+5, bar_y-9], fill="#ff9f43", outline="#1a1a1a")
                self.power_canvas.create_text(x, bar_y-16, text=f"{prefix}{int(val)}%", fill="#ff9f43", font=("Arial", 8, "bold"))

        self.after(200, draw_power_scale)

        # File Name
        fname_frame = ctk.CTkFrame(info_scroll, fg_color="transparent")
        fname_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(fname_frame, text="File:", font=("Arial", 10, "bold"), width=40, anchor="w").pack(side="left")
        ctk.CTkLabel(fname_frame, text=payload.get("file_name", "N/A"), font=("Arial", 10), anchor="e", wraplength=120).pack(side="right", fill="x", expand=True)

        #Gcode visualizer
        ctk.CTkLabel(self.left_panel, text="LIVE G-CODE", font=("Arial", 11, "bold")).pack(pady=(10, 0))
        self.gcode_view = ctk.CTkTextbox(
            self.left_panel, 
            height=200, 
            font=("Consolas", 10), 
            fg_color="#1a1a1a", 
            text_color="#00ff00", 
            state="disabled"
        )

        self.gcode_view.pack(fill="x", padx=10, pady=5)
        # Groupe OPTIONS (Badges)
        self.options_group_frame = ctk.CTkFrame(self.left_panel, fg_color="#222222", border_width=1, border_color="#444444")
        self.options_group_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(self.options_group_frame, text="Active Options", font=("Arial", 11, "bold")).pack(pady=(8, 2))
        badge_cont = ctk.CTkFrame(self.options_group_frame, fg_color="transparent")
        badge_cont.pack(fill="x", padx=10, pady=(0, 10))

        for key, text in [("is_pointing", "POINTING"), ("is_framing", "FRAMING")]:
            # --- MODIFICATION ICI ---
            # On va chercher dans le sous-dictionnaire 'framing'
            # Si 'framing' n'existe pas, on prend un dictionnaire vide {} par sécurité
            active = payload.get('framing', {}).get(key, False)
            
            color, bg = ("#ff9f43", "#3d2b1f") if active else ("#666666", "#282828")
            ctk.CTkLabel(
                badge_cont, 
                text=text, 
                font=("Arial", 9, "bold"), 
                text_color=color, 
                fg_color=bg, 
                corner_radius=5
            ).pack(side="left", expand=True, fill="x", padx=2)
        # Actions (Générer / Annuler)
        btn_act = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_act.pack(fill="x", side="bottom", pady=15)
        ctk.CTkButton(btn_act, text="EXPORT GCODE", fg_color="#27ae60", height=40, font=("Arial", 11, "bold"), command=self.on_confirm).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_act, text="CANCEL", fg_color="#333", height=30, command=self.on_cancel).pack(fill="x", padx=10, pady=5)
    
    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, fg_color="#111", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        
        # 1. Canvas de prévisualisation
        self.preview_canvas = ctk.CTkCanvas(
            self.right_panel, 
            bg="#050505", 
            highlightthickness=0,
            width=1, height=1  
        )
        self.preview_canvas.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        # --- CONTENEUR DES COMMANDES (CENTRÉ) ---
        self.controls_bar = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.controls_bar.pack(fill="x", padx=20, pady=5)

        # LIGNE 1 : Boutons de transport (⏮, ▶, ⏭)
        playback_cont = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        playback_cont.pack(pady=(0, 10)) # Centré par défaut dans un pack() sans side

        self.btn_rewind = ctk.CTkButton(playback_cont, text="⏮", width=60, height=40, font=("Arial", 20), command=self.rewind_sim)
        self.btn_rewind.pack(side="left", padx=5)
        
        self.btn_play_pause = ctk.CTkButton(playback_cont, text="▶", width=100, height=40, font=("Arial", 20), fg_color="#27ae60", command=self.toggle_pause)
        self.btn_play_pause.pack(side="left", padx=5)
        
        self.btn_end = ctk.CTkButton(playback_cont, text="⏭", width=60, height=40, font=("Arial", 20), fg_color="#555", command=self.skip_to_end)
        self.btn_end.pack(side="left", padx=5)

        # LIGNE 2 : Sélection de vitesse
        speed_cont = ctk.CTkFrame(self.controls_bar, fg_color="#222", corner_radius=8, border_width=1, border_color="#444")
        speed_cont.pack(pady=5) # Centré par défaut

        # Petit label discret pour la vitesse actuelle
        self.speed_title_label = ctk.CTkLabel(speed_cont, text="Speed:", font=("Arial", 11, "bold"))
        self.speed_title_label.pack(side="left", padx=(15, 10))

        self.speed_selector = ctk.CTkSegmentedButton(
            speed_cont, 
            values=["0.5", "1", "3", "10", "20", "50"],
            command=self._update_speed_from_segmented, 
            font=("Arial", 10), 
            height=30,
            width=300
        )
        self.speed_selector.pack(side="left", padx=5, pady=5)
        self.speed_selector.set("1")

        # 3. Zone de Progression (Barre + Temps)
        self.progress_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.progress_container.pack(fill="x", padx=40, pady=(10, 20))

        self.progress_bar = ctk.CTkProgressBar(self.progress_container, height=8, progress_color="#27ae60")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 5))

        text_row = ctk.CTkFrame(self.progress_container, fg_color="transparent")
        text_row.pack(fill="x")

        self.progress_label = ctk.CTkLabel(text_row, text="Progress: 0%", font=("Arial", 11))
        self.progress_label.pack(side="left")

        self.time_label = ctk.CTkLabel(text_row, text="Time: 00:00:00 / 00:00:00", font=("Arial", 11, "italic"))
        self.time_label.pack(side="right")

        # Création de l'élément image pour la loupe sur le canvas
        self.loupe_container = self.preview_canvas.create_image(
            0, 0, anchor="center", state="hidden", tags="loupe"
        )
        self.loupe_border = self.preview_canvas.create_oval(
            0, 0, 0, 0, outline="#ff9f43", width=2, state="hidden", tags="loupe"
        )

        # Bind du mouvement de souris
        self.preview_canvas.bind("<ButtonPress-1>", self._on_click_loupe)
        self.preview_canvas.bind("<B1-Motion>", self._update_loupe)
        self.preview_canvas.bind("<ButtonRelease-1>", lambda e: self._hide_loupe())

        self.gcode_view.bind("<ButtonRelease-1>", self._on_gcode_click)


    def _on_click_loupe(self, event):
        self.loupe_active = True
        self._update_loupe(event)

    def _update_loupe(self, event=None):
        if not hasattr(self, 'display_data') or self.display_data is None:
            return
        if not self.loupe_active: 
            return

        if event:
            self.last_mouse_coords = (event.x, event.y)
        
        # On récupère les coordonnées réelles sur le canvas
        ex = self.preview_canvas.canvasx(self.last_mouse_coords[0])
        ey = self.preview_canvas.canvasy(self.last_mouse_coords[1])
        
        # 1. CALCUL DES INDEX MATRICE (ix, iy)
        if "Right" in self.origin_mode:
            ix = (self.x0 + self.total_px_w) - ex
        else:
            ix = ex - self.x0
        iy = ey - self.y0

        # 2. VÉRIFICATION DE COLLISION
        if 0 <= ix < self.rect_w and 0 <= iy < self.rect_h:
            # Rayon de la zone à capturer
            crop_r = (self.loupe_size / 2) / self.loupe_zoom
            
            # On utilise l'image brute (non-inversée pour le moment)
            img_obj = Image.fromarray(self.display_data).convert("RGB")
            
            # Ajout d'une bordure de sécurité (pad)
            pad = int(crop_r + 10)
            bg = Image.new("RGB", (self.rect_w + 2*pad, self.rect_h + 2*pad), (255, 255, 255))
            bg.paste(img_obj, (pad, pad))
            
            # --- DESSIN DE LA GRILLE DANS LA LOUPE ---
            draw = ImageDraw.Draw(bg)
            grid_col = (220, 220, 220) # Gris clair
            step_px = 10 * self.scale  # 10mm convertis en pixels
            
            # Calcul du décalage pour aligner sur les millimètres machine ronds (10, 20...)
            offset_x = (self.min_x_machine % 10) * self.scale
            offset_y = (self.min_y_machine % 10) * self.scale
            
            # Lignes verticales
            for x in np.arange(pad - offset_x, bg.width, step_px):
                # Correction du TypeError : on sépare (x,0) et (x,h)
                self._draw_dashed_line(draw, (x, 0), (x, bg.height), grid_col, dash=4, gap=4)
                
            # Lignes horizontales
            for y in np.arange(pad - offset_y, bg.height, step_px):
                # Correction du TypeError : on sépare (0,y) et (w,y)
                self._draw_dashed_line(draw, (0, y), (bg.width, y), grid_col, dash=4, gap=4)

            # 3. DÉCOUPE (CROP)
            cx, cy = ix + pad, iy + pad
            left, top = cx - crop_r, cy - crop_r
            right, bottom = cx + crop_r, cy + crop_r
            
            try:
                crop = bg.crop((int(left), int(top), int(right), int(bottom)))
                
                # --- GESTION DU MODE RIGHT ---
                # On inverse l'image de la loupe seulement si on est en mode Right
                if "Right" in self.origin_mode:
                    crop = crop.transpose(Image.FLIP_LEFT_RIGHT)

                zoom_img = crop.resize((self.loupe_size, self.loupe_size), Image.NEAREST)
                
                # Masque circulaire
                mask = Image.new("L", (self.loupe_size, self.loupe_size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, self.loupe_size, self.loupe_size), fill=255)
                
                final_img = Image.new("RGBA", (self.loupe_size, self.loupe_size), (0, 0, 0, 0))
                final_img.paste(zoom_img.convert("RGBA"), (0, 0), mask)

                # 4. AFFICHAGE
                self.tk_loupe = ImageTk.PhotoImage(final_img)
                self.preview_canvas.itemconfig(self.loupe_container, image=self.tk_loupe, state="normal")
                self.preview_canvas.coords(self.loupe_container, ex, ey)
                
                self.preview_canvas.itemconfig(self.loupe_border, state="normal")
                self.preview_canvas.coords(self.loupe_border, 
                                            ex - self.loupe_size/2, ey - self.loupe_size/2,
                                            ex + self.loupe_size/2, ey + self.loupe_size/2)
                
                self.preview_canvas.tag_raise("loupe")
                
            except Exception as e:
                print(f"Loupe error: {e}")
                self._hide_loupe()
        else:
            self._hide_loupe()

    def _draw_dashed_line(self, draw, start, end, fill, dash=2, gap=4):
        """Utilitaire pour dessiner les pointillés sur l'image PIL de la loupe"""
        x1, y1 = start
        x2, y2 = end
        length = ((x2-x1)**2 + (y2-y1)**2)**0.5
        if length == 0: return
        dx, dy = (x2-x1)/length, (y2-y1)/length
        curr = 0
        while curr < length:
            block = min(curr + dash, length)
            draw.line([(x1 + dx*curr, y1 + dy*curr), (x1 + dx*block, y1 + dy*block)], fill=fill, width=1)
            curr += dash + gap

    def _hide_loupe(self):
        self.loupe_active = False # On désactive l'état
        self.preview_canvas.itemconfig(self.loupe_container, state="hidden")
        self.preview_canvas.itemconfig(self.loupe_border, state="hidden")


    def _update_speed_from_segmented(self, value):
      try:
         self.sim_speed = float(value)
         self.speed_title_label.configure(text=f"Speed:")
         
         # TRÈS IMPORTANT : On synchronise le marqueur de temps
         # pour que la boucle animate_loop ne calcule pas un "bond" temporel
         self.last_frame_time = time.time()
                  
      except ValueError:
         pass

    def _update_speed_label(self, value):
      """Met à jour le texte au-dessus du slider en temps réel"""
      multiplier = float(value)
      self.sim_speed = multiplier # On applique la vitesse en direct si c'est un slider
      self.last_frame_time = time.time() # Fluidité immédiate

      # Ton calcul de durée réelle de la simulation (ex: 10min à 2x = 5min devant l'écran)
      sim_duration_sec = self.total_sim_seconds / max(0.1, multiplier)
      duration_str = self._format_seconds_to_hhmmss(sim_duration_sec)
      
      # self.speed_title_label.configure(
      #    text=f"Speed: {multiplier:.1f}x (Real duration: {duration_str})"
      # )




    def toggle_pause(self):
        self.sim_running = not self.sim_running
        
        if self.sim_running:
            # On cale l'horloge sur "maintenant" pour que le premier saut soit de 0ms
            now = time.time()
            self.last_frame_time = now
            
            # On synchronise l'index flottant sur l'index entier actuel
            self.accumulated_index = float(self.current_point_idx)
            
            self.btn_play_pause.configure(text="⏸", fg_color="#e67e22")
            self.animate_loop()
        else:
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")

    def rewind_sim(self):
        self.sim_running = False
        if self.animation_job: 
            self.after_cancel(self.animation_job)
        self.animation_job = None
        
        self.current_point_idx = 0
        self.accumulated_index = 0.0 # Reset impératif
        self.last_frame_time = time.time()
        
        self.display_data.fill(255) # On efface le tracé
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.time_label.configure(text=f"Time: 00:00:00 / {self._format_seconds_to_hhmmss(self.total_sim_seconds)}")
        
        if self.points_list:
            # On déballe les 4 valeurs (le _ ignore la puissance et l'index de ligne)
            mx, my, _, _ = self.points_list[0]
            # On convertit en coordonnées écran pour le laser bleu
            self.curr_x, self.curr_y = self.machine_to_screen(mx, my)
            
        self.update_graphics()
        self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
        
        # Reset de la vue G-code
        self.gcode_view.see("1.0")
        self.gcode_view.tag_remove("active", "1.0", "end")

    def screen_index(self, mx, my):
        # 1. On récupère la position EXACTE du laser sur le Canvas (en pixels)
        sx, sy = self.machine_to_screen(mx, my)
        
        # 2. On calcule la position relative au coin haut-gauche de l'image
        # (Coordonnée Canvas - Origine de l'image)
        ix = int(sx - self.img_sx)
        iy = int(sy - self.img_sy)

        # 3. Sécurité pour ne pas sortir de la matrice OpenCV
        h, w = self.display_data.shape
        ix = max(0, min(ix, w - 1))
        iy = max(0, min(iy, h - 1))

        return ix, iy


    def animate_loop(self):
        # 1. Sécurité immédiate : on vérifie si le widget existe encore
        if not self.winfo_exists():
            return

        # 2. Si on a demandé l'arrêt ou si c'est fini
        if not self.sim_running or self.current_point_idx >= len(self.points_list):
            if self.sim_running and self.current_point_idx >= len(self.points_list):
                self.skip_to_end()
            return

        # Gestion du temps (Delta Time)
        now = time.time()
        if not hasattr(self, 'last_frame_time') or self.last_frame_time <= 0:
            self.last_frame_time = now
        dt = now - self.last_frame_time
        self.last_frame_time = now

        # Calcul du bond d'index (Step)
        is_framing = self.current_point_idx < self.framing_end_idx
        pps = self.pts_per_sec_framing if is_framing else self.pts_per_sec_image
        step = dt * pps * self.sim_speed
        self.accumulated_index += step
        
        target_idx = min(int(self.accumulated_index), len(self.points_list) - 1)

        if target_idx >= self.current_point_idx:
            # --- LOGIQUE DE DESSIN OPENCV ---
            # On traite tous les points entre l'ancien et le nouveau pour ne pas avoir de trous
            batch = self.points_list[self.current_point_idx : target_idx + 1]

            for i, point_data in enumerate(batch):
                mx, my, pwr, _ = point_data
                actual_idx = self.current_point_idx + i
                ix, iy = self.screen_index(mx, my)

                if actual_idx < self.framing_end_idx:
                    self.prev_matrix_coords = None # Pas de dessin en framing
                else:
                    if self.prev_matrix_coords is not None:
                        old_ix, old_iy = self.prev_matrix_coords
                        if (old_ix, old_iy) != (ix, iy) and pwr > 0:
                            self._draw_line_on_matrix(
                                self.display_data, old_ix, old_iy,
                                ix, iy, pwr, thickness=self.laser_width_px
                            )
                    self.prev_matrix_coords = (ix, iy)

            # Mise à jour de l'index de progression
            self.current_point_idx = target_idx + 1

            # --- APPEL À LA SYNCHRONISATION UI ---
            # On met à jour l'affichage une seule fois pour tout le batch
            self.sync_sim_to_index(target_idx)

        try:
            if self.winfo_exists() and self.sim_running:
                self.animation_job = self.after(16, self.animate_loop)
        except:
            # Si l'app est fermée pile à ce moment, on ignore l'erreur proprement
            self.sim_running = False
            self.animation_job = None

    def sync_sim_to_index(self, target_idx):
        """Met à jour l'UI, le temps et le laser pour un index donné."""
        if not self.points_list or target_idx >= len(self.points_list):
            return

        # 1. Mise à jour des coordonnées du laser
        mx, my, pwr, line_idx = self.points_list[target_idx]
        self.curr_x, self.curr_y = self.machine_to_screen(mx, my)

        # 2. Progression
        total_pts = len(self.points_list)
        progress = target_idx / max(1, total_pts)
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Progress: {int(progress*100)}%")

        # 3. Calcul du temps (identique à votre logique actuelle)
        if target_idx < self.framing_end_idx:
            c_sec = target_idx / max(1, self.pts_per_sec_framing)
        else:
            pts_image = target_idx - self.framing_end_idx
            c_sec = self.framing_duration + (pts_image / max(1, self.pts_per_sec_image))

        self.time_label.configure(
            text=f"Time: {self._format_seconds_to_hhmmss(c_sec)} / {self._format_seconds_to_hhmmss(self.total_sim_seconds)}"
        )

        # 4. Refresh graphique
        self.update_graphics()
        
        # 5. Highlight G-code
        self.update_gcode_highlight(target_idx)

    def update_gcode_highlight(self, target_idx):
            """Met à jour la ligne surlignée dans l'éditeur G-code en fonction de l'index du point."""
            if not self.points_list or target_idx >= len(self.points_list):
                return

            try:
                # Récupérer l'index de la ligne G-code stocké dans le point
                point_data = self.points_list[target_idx]
                
                # Sécurité : on vérifie que le tuple contient bien 4 éléments
                if len(point_data) < 4:
                    return
                    
                line_number = point_data[3]

                line_number = self.points_list[target_idx][3]
    
                # 1. Mise en couleur
                self.gcode_view.tag_remove("active", "1.0", "end")
                start_idx = f"{line_number}.0"
                self.gcode_view.tag_add("active", start_idx, f"{line_number}.end")
                self.gcode_view.tag_config("active", background="#2c3e50", foreground="#ecf0f1")

                # 2. Centrage vertical parfait
                # '0.5' indique qu'on veut placer la ligne à 50% de la hauteur du widget
                self.gcode_view.yview_moveto(0) # Reset scroll pour le calcul
                self.gcode_view.see(start_idx)  # On rend la ligne visible
                
                # On ajuste pour que la ligne soit au centre
                # On déplace la vue de sorte que la ligne 'line_number' soit au milieu
                self.gcode_view.yview_scroll(0, 'units') # Force update
                # Approche simple : scroller pour que la ligne soit au milieu
                # On calcule l'offset pour 50% de la hauteur
                self.gcode_view.yview(int(line_number) - 10) # 10 est environ la moitié des lignes visibles
                
            except Exception as e:
                # On évite de crash la simulation pour une erreur d'affichage de texte
                print(f"GCode highlight error: {e}")

    def _on_gcode_click(self, event):
        try:
            # Trouver la ligne cliquée
            index = self.gcode_view.index(f"@{event.x},{event.y}")
            line_clicked = int(index.split('.')[0])

            # Chercher le point correspondant (point_data[3] est le line_number)
            target_idx = None
            for i, p in enumerate(self.points_list):
                if len(p) >= 4 and p[3] == line_clicked:
                    target_idx = i
                    break
            
            if target_idx is not None:
                # ICI : Appelez la fonction qui déplace votre simulateur
                # (Par exemple celle liée à votre slider : self._on_slider_move(target_idx))
                self.sync_sim_to_index(target_idx)
                
                # On force le highlight et le centrage immédiat
                self.update_gcode_highlight(target_idx)
                
        except Exception as e:
            print(f"GCode selection error: {e}")
            
    def skip_to_end(self):
        # Sécurité : si la fenêtre est fermée, on sort
        if not self.winfo_exists():
            return

        self.sim_running = False
        if self.animation_job: 
            try:
                self.after_cancel(self.animation_job)
            except:
                pass
        self.animation_job = None
        
        # --- RÉCUPÉRATION DES DIMENSIONS ---
        # Au lieu de self.rect_h qui n'existe pas, on prend la taille de l'image actuelle
        h, w = self.display_data.shape
        
        # 1. Utiliser une feuille BLANCHE (255)
        import numpy as np
        final_view = np.full((h, w), 255, dtype=np.uint8)
        
        if len(self.points_list) > 0:
            temp_prev_coords = None 
            
            for i in range(len(self.points_list)):
                mx, my, pwr, _ = self.points_list[i]
                
                if pwr > 0:
                    ix, iy = self.screen_index(mx, my)
                    
                    if temp_prev_coords:
                        old_x, old_y = temp_prev_coords
                        self._draw_line_on_matrix(
                            final_view, old_x, old_y,
                            ix, iy, pwr,
                            thickness=self.laser_width_px
                        )
                    else:
                        # Sécurité pour ne pas dessiner hors matrice
                        if 0 <= iy < h and 0 <= ix < w:
                            ratio = max(0.0, min(1.0, float(pwr) / self.ctrl_max))
                            color = int(255 * (1.0 - ratio))
                            final_view[iy, ix] = color
                        
                    temp_prev_coords = (ix, iy)
                else:
                    temp_prev_coords = None

        self.display_data = final_view
        self.current_point_idx = len(self.points_list)
        
        # Mise à jour UI (on vérifie l'existence des widgets avant)
        try:
            t_str = self._format_seconds_to_hhmmss(self.total_sim_seconds)
            self.time_label.configure(text=f"Time: {t_str} / {t_str}")
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="Progress: 100%")
            
            if self.points_list:
                last_mx, last_my, _, last_line = self.points_list[-1]
                self.curr_x, self.curr_y = self.machine_to_screen(last_mx, last_my)
                self.update_gcode_highlight(len(self.points_list) - 1)
                
            self.update_graphics()
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
        except:
            pass # L'UI est peut-être déjà en train de se fermer

    def _draw_line_on_matrix(self, matrix, x0, y0, x1, y1, pwr, thickness=1):
        #print(f"DEBUG DRAW: pwr_brute={pwr}, ctrl_max={self.ctrl_max}")
        # 1. Normalisation : on ramène pwr (0 à ctrl_max) vers une échelle 0.0 à 1.0
        # pwr / self.ctrl_max donne 1.0 pour la puissance max
        ratio = max(0.0, min(1.0, float(pwr) / self.ctrl_max))
        
        # 2. Inversion pour l'affichage : 
        # ratio 1.0 (max) -> couleur 0 (Noir)
        # ratio 0.0 (min) -> couleur 255 (Blanc)
        color = int(255 * (1.0 - ratio))
        #print(f"DEBUG COLOR: ratio={ratio:.2f} -> color_result={color} | coords=({int(x0)},{int(y0)}) to ({int(x1)},{int(y1)})")

        cv2.line(
            matrix,
            (int(x0), int(y0)),
            (int(x1), int(y1)),
            color,
            thickness=max(1, int(thickness)),
            lineType=cv2.LINE_8
        )


    def update_graphics(self):
        if self.img_container is None or self.display_data is None:
            return
        try:
            # 1. Mise à jour de l'image principale
            pil_img = Image.fromarray(self.display_data).convert("RGB")
            self.tk_img = ImageTk.PhotoImage(pil_img)
            self.preview_canvas.itemconfig(self.img_container, image=self.tk_img)

            # 2. Gestion de l'ordre des calques (Z-Index)
            # On s'assure que le fond reste en bas et les éléments utiles en haut
            self.preview_canvas.tag_lower("bg_rect")
            self.preview_canvas.tag_raise(self.img_container)
            self.preview_canvas.tag_raise("grid")
            self.preview_canvas.tag_raise("laser")

            # 3. Mise à jour visuelle du laser (croix ou cercle)
            self.update_laser_ui()

            # 4. Rafraîchissement de la loupe
            # Elle doit être traitée EN DERNIER pour rester au-dessus de tout
            if getattr(self, 'loupe_active', False):
                self._update_loupe()
                # On force la remontée des objets ayant le tag "loupe"
                self.preview_canvas.tag_raise("loupe")
            
            # Force la mise à jour immédiate du Canvas
            #self.preview_canvas.update_idletasks()

        except Exception as e:
            # En cas d'erreur (ex: image corrompue), on l'affiche en console
            # sans stopper la simulation
            print(f"Erreur update_graphics: {e}")



    def update_laser_ui(self):
        if not hasattr(self, 'laser_head') or self.laser_head is None:
            return

        # 1Coordonnées cibles : curr_x / curr_y sont déjà en pixels
        lx, ly = self.curr_x, self.curr_y

        laser_state = "normal"

        # LOGIQUE D'ÉVITEMENT DE LA LOUPE
        if self.loupe_active and hasattr(self, 'last_mouse_coords'):
            mx, my = self.last_mouse_coords
            distance = ((lx - mx)**2 + (ly - my)**2)**0.5
            if distance < (self.loupe_size / 2):
                laser_state = "hidden"

        # Mise à jour positions et visibilité
        if hasattr(self, 'laser_halo'):
            self.preview_canvas.coords(self.laser_halo, lx-6, ly-6, lx+6, ly+6)
            self.preview_canvas.itemconfig(self.laser_halo, state=laser_state)

        self.preview_canvas.coords(self.laser_head, lx-3, ly-3, lx+3, ly+3)
        self.preview_canvas.itemconfig(self.laser_head, state=laser_state)



    def _parse_time_to_seconds(self, t_str):
        try:
            t_str = str(t_str).lower().replace(" ", "")
            parts = re.findall(r'(\d+)([hms])', t_str)
            total = 0
            for val, unit in parts:
                if unit == 'h': total += int(val) * 3600
                elif unit == 'm': total += int(val) * 60
                elif unit == 's': total += int(val)
            return max(1, total)
        except: return 1

    def _format_seconds_to_hhmmss(self, s):
        return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

    

    def draw_simulation(self, payload):
        try:
            #self.update_idletasks()

            w_mm = max(1, payload.get("real_w", 100))
            h_mm = max(1, payload.get("real_h", 100))

            # --- 1. MATRICE IMAGE DE RÉFÉRENCE (Pour la loupe) ---
            p_min = float(payload.get("min_power", 0))
            p_max = float(payload.get("max_power", 100))

            # On crée un rendu visuel de la matrice originale
            render = np.clip(
                (self.matrix - p_min) / max(1, p_max - p_min) * 255,
                0, 255
            ).astype('uint8')

            pil_img = Image.fromarray(255 - render).resize(
                (self.rect_w, self.rect_h),
                Image.NEAREST
            )

            # ON REPREND FULL_DATA ICI (Indispensable pour la loupe)
            self.full_data = np.array(pil_img)

            # --- 2. MATRICE DE DESSIN (display_data) ---
            # C'est celle-ci qu'OpenCV va modifier pendant l'animation
            self.display_data = np.full(
                (self.rect_h, self.rect_w), 
                255, 
                dtype=np.uint8
            )

            #self.frame_mask = np.zeros((self.rect_h, self.rect_w), dtype=bool)

            # --- 3. NETTOYAGE CANVAS ---
            self.preview_canvas.delete("all")
            vis_pad = 10

            self.preview_canvas.create_rectangle(
                self.x0 - vis_pad, 
                self.y0 - vis_pad, 
                self.x0 + self.total_px_w + vis_pad, 
                self.y0 + self.total_px_h + vis_pad, 
                fill="white", 
                outline="#d1d1d1", 
                width=1,
                tags="bg_rect"
            )

            # --- 4. POSITION IMAGE (ALIGNEE SUR LA GRILLE) ---
            # On aligne l'image sur les limites minimales de la machine
            # pour que (ix, iy) = (0, 0) corresponde au premier pixel.
            tl_mx = self.min_x_machine
            tl_my = self.min_y_machine

            # On calcule les coordonnées Canvas du point (min_x, min_y)
            self.img_sx, self.img_sy = self.machine_to_screen(tl_mx, tl_my)

            # On crée l'image et on l'affiche
            self.tk_img = ImageTk.PhotoImage(Image.fromarray(self.display_data))
            self.img_container = self.preview_canvas.create_image(
                self.img_sx,
                self.img_sy,
                anchor="nw",  # Indispensable
                image=self.tk_img,
                tags="main_image"
            )

            # --- 5. GRILLE ET LASER ---
            self.draw_grid()

            self.laser_halo = self.preview_canvas.create_oval(
                0, 0, 0, 0, fill="#1a75ff", outline="#3385ff", width=1, tags="laser", stipple="gray50"
            )
            self.laser_head = self.preview_canvas.create_oval(
                0, 0, 0, 0, fill="#00ffff", outline="white", width=1, tags="laser"
            )

            # --- 6. ORDRE DES CALQUES ---
            self.preview_canvas.tag_lower("bg_rect")
            self.preview_canvas.tag_raise("main_image")
            self.preview_canvas.tag_raise("grid")
            self.preview_canvas.tag_raise("laser")

            # --- 6b. RECREATION DES ELEMENTS DE LA LOUPE ---
            # Puisque "delete('all')" a tout supprimé, on doit les recréer
            # pour qu'ils soient au-dessus de tout le reste.
            self.loupe_container = self.preview_canvas.create_image(
                0, 0, anchor="center", state="hidden", tags="loupe"
            )
            self.loupe_border = self.preview_canvas.create_oval(
                0, 0, 0, 0, outline="#ff9f43", width=2, state="hidden", tags="loupe"
            )
            
            # On s'assure qu'ils sont au sommet absolu
            self.preview_canvas.tag_raise("loupe")

            # --- 7. RESET ---
            self.rewind_sim()

        except Exception as e:
            print(f"Error in draw_simulation: {e}")

   

    def draw_grid(self):
        """Dessine la grille millimétrée (tous les 10mm) basée sur les coordonnées machine."""
        col, txt_col, dash = "#e0e0e0", "#888888", (2, 4)
        
        self.preview_canvas.delete("grid")

        # 1. DÉFINITION DES BORNES RÉELLES (en mm)
        total_w_mm = self.total_mouvement_w
        total_h_mm = self.total_mouvement_h
        
        x_start = self.min_x_machine
        x_end = self.min_x_machine + total_w_mm
        y_start = self.min_y_machine
        y_end = self.min_y_machine + total_h_mm

        # On arrondit pour caler les lignes sur des multiples de 10
        step = 10
        first_x = int(np.ceil(x_start / step) * step)
        last_x = int(np.floor(x_end / step) * step)
        first_y = int(np.ceil(y_start / step) * step)
        last_y = int(np.floor(y_end / step) * step)

        # 2. LIGNES VERTICALES (Axe X)
        for vx in range(first_x, last_x + step, step):
            # On projette le point machine sur le canvas
            sx, sy_top = self.machine_to_screen(vx, y_start)
            _, sy_bottom = self.machine_to_screen(vx, y_end)

            self.preview_canvas.create_line(
                sx, sy_top, sx, sy_bottom, 
                fill=col, dash=dash, tags="grid"
            )

            # Labels X
            self.preview_canvas.create_text(
                sx, max(sy_top, sy_bottom) + 15,
                text=str(vx), fill=txt_col, font=("Arial", 8), tags="grid"
            )

        # 3. LIGNES HORIZONTALES (Axe Y)
        for vy in range(first_y, last_y + step, step):
            sx_left, sy = self.machine_to_screen(x_start, vy)
            sx_right, _ = self.machine_to_screen(x_end, vy)

            self.preview_canvas.create_line(
                sx_left, sy, sx_right, sy, 
                fill=col, dash=dash, tags="grid"
            )

            # Labels Y
            self.preview_canvas.create_text(
                sx_left - 20, sy,
                text=str(vy), fill=txt_col, font=("Arial", 8), tags="grid"
            )

        self.preview_canvas.tag_raise("grid", "bg_rect") # Juste au dessus du fond blanc



    def machine_to_screen(self, mx, my):
        px = (mx - self.min_x_machine) * self.scale
        py = (my - self.min_y_machine) * self.scale

        if "Right" in self.origin_mode:
            sx = self.x0 + self.total_px_w - px
        else:
            sx = self.x0 + px

        sy = self.y0 + py

        return sx, sy





    def estimate_file_size(self, matrix):
        if matrix is None: return "0 KB"
        h, w = matrix.shape
        use_s = self.payload.get("use_s_mode", False)
        b_per_l = 22 if use_s else 28
        n_lines = 15 + (h * 2) # Header + G0/S0 par ligne
        for y in range(h):
            n_lines += np.count_nonzero(np.abs(np.diff(matrix[y])) > 0.01) + 1
        size = (n_lines * b_per_l) + 1024
        return f"{size/1024:.0f} KB" if size < 1048576 else f"{size/1048576:.2f} MB"

    def on_confirm(self):
        """Action déclenchée par le bouton 'Confirm' (Save G-Code)"""
        self.stop_processes()
        
        # 1. Préparation du chemin de sortie
        output_dir = self.payload['metadata'].get('output_dir', '')
        file_name = self.payload['metadata'].get('file_name', 'output.nc')
        full_path = os.path.join(output_dir, file_name)

        # 2. Sauvegarde du fichier
        try:
            # On utilise self.final_gcode qui a été généré durant l'init de la simulation
            if hasattr(self, 'final_gcode') and self.final_gcode:
                with open(full_path, "w") as f:
                    f.write(self.final_gcode)
                messagebox.showinfo("Success", f"G-Code saved to:\n{full_path}", parent=self.controller)
            else:
                messagebox.showerror("Error", "No G-Code data to save.", parent=self.controller)
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}", parent=self.controller)

        # 3. Retour à la vue précédente
        self._navigate_back()

    def on_cancel(self):
        self.stop_processes()
        self._navigate_back()

    def _navigate_back(self):
        """Navigue vers la vue spécifiée lors de l'initialisation."""
        if self.return_view == "raster":
            self.controller.show_raster_mode()
        elif self.return_view == "infill":
            self.controller.show_infill_mode() # futur mode
        else:
            self.controller.show_dashboard()

    def stop_processes(self):
        """Arrête proprement l'animation avant la destruction du Frame."""
        self.sim_running = False
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None