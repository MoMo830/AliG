
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
import bisect

from engine.gcode_parser import GCodeParser
from core.utils import save_dashboard_data

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
        self.sim_speed = 1.0 
        # --- ÉTATS DE TEMPS POUR LA SIMULATION ---
        self.current_sim_time = 0.0  # Temps écoulé dans la simulation (secondes)
        self.total_sim_dur = 0.0     # Durée totale calculée dans _async_generation
        self.last_frame_time = 0.0   # Timestamp système de la dernière frame affichée
        self.framing_end_idx = 0
        

        self.framing_duration = 0.0 
        self.total_sim_seconds = 0.0
        self.loupe_active = False
        self.loupe_size = 150        
        self.loupe_zoom = 3.0    
        self.raw_sim_data = None    
        self.origin_mode = payload["metadata"].get("origin_mode", "Lower-Left")
        self.full_metadata = {}


        # 3. Configuration UI
        self.grid_columnconfigure(0, weight=0, minsize=500) 
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

            # A. Génération du G-Code de Cadrage
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
            self.full_metadata = full_metadata # Stockage pour _on_gen_done

            # C. Génération du G-Code Final (Framing + Image)
            self.final_gcode = self.engine.build_final_gcode(
                self.payload['matrix'], self.payload['dims'],
                self.payload['offsets'], params,
                self.payload['text_blocks'], full_metadata
            )

            # D. PARSING ET CALCUL DU TEMPS (Logique temporelle)
            # 1. On parse pour avoir la liste de points brute
            f_points_tmp, f_dur = self.parser.parse(self.framing_gcode)
            framing_end_idx = len(f_points_tmp)

            all_points_raw, total_dur_estimated = self.parser.parse(self.final_gcode)
            
            # 2. INJECTION DES TIMESTAMPS
            # On recalcule le temps cumulé pour chaque point pour l'interpolation
            points_with_time = []
            cumulative_time = 0.0
            
            for i in range(len(all_points_raw)):
                p = list(all_points_raw[i]) # (x, y, pwr, line_idx, f_rate)
                
                if i > 0:
                    prev = all_points_raw[i-1]
                    # Distance entre les deux points (X, Y)
                    dist = ((p[0]-prev[0])**2 + (p[1]-prev[1])**2)**0.5
                    
                    # RÉCUPÉRATION DE LA VITESSE DU PARSER (p[4])
                    # Si le parser n'a pas trouvé de F, on utilise base_feed par sécurité
                    f_rate = p[4] if len(p) > 4 else params.get('feedrate', 3000)
                    f_sec = f_rate / 60.0
                    
                    # Temps pour parcourir cette distance à la vitesse G-Code
                    duration = dist / f_sec if f_sec > 0 else 0
                    cumulative_time += duration
                
                # On garde la structure : (x, y, pwr, line_idx, timestamp)
                # On remplace l'élement de vitesse par le temps cumulé
                points_with_time.append((p[0], p[1], p[2], p[3], cumulative_time))

            # E. PRÉPARATION DU RETOUR
            self.raw_sim_data = {
                'points_list': points_with_time,
                'framing_end_idx': framing_end_idx,
                'f_dur': f_dur,
                'total_dur': cumulative_time,
                'full_metadata': full_metadata 
            }
            
            if self.winfo_exists():
                self.after(0, self._on_gen_done)
            
        except Exception as e:
            print(f"[DEBUG ERROR] Erreur thread: {e}")
            if self.winfo_exists():
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._handle_gen_error(msg))

    def _handle_gen_error(self, msg):
        messagebox.showerror("Engine Error", f"Failed to generate G-code:\n{msg}")
        self.destroy()

    def _on_gen_done(self):
        if not self.raw_sim_data:
            return

        self.points_list = self.raw_sim_data['points_list']
        self.total_sim_seconds = self.raw_sim_data.get('total_dur', 0.0)
        
        # Injection du texte dans le widget
        if hasattr(self, 'final_gcode') and self.final_gcode:
            self.gcode_view.configure(state="normal")
            self.gcode_view.delete("1.0", "end")
            self.gcode_view.insert("1.0", self.final_gcode)
            self.gcode_view.configure(state="disabled")
        else:
            print("[DEBUG WARNING] Aucun G-Code à afficher dans le widget")

        if hasattr(self, 'loading_frame'):
            self.loading_frame.destroy()

        self._prepare_and_draw()


    def _prepare_and_draw(self):
        """Initialise les dimensions, la matrice de pixels et les objets du Canvas."""
        # 1. On récupère la taille RÉELLE du canvas
        c_w = self.preview_canvas.winfo_width()
        c_h = self.preview_canvas.winfo_height()

        # SÉCURITÉ : Si le canvas n'est pas encore rendu, on reporte
        if c_w <= 1:
            self.after(50, self._prepare_and_draw)
            return

        # --- 1. RÉCUPÉRATION DES DONNÉES ---
        self.points_list = self.raw_sim_data.get('points_list', [])
        if not self.points_list:
            return

        # On récupère les infos essentielles via .get pour éviter les KeyError
        self.framing_end_idx = self.raw_sim_data.get('framing_end_idx', 0)
        self.total_sim_seconds = self.raw_sim_data.get('total_dur', 0.0)
        self.total_sim_dur = self.total_sim_seconds 
        
        # Préparation des timestamps pour la recherche rapide (bisect)
        self.timestamps = [p[4] for p in self.points_list]

        # --- 2. LIMITES MACHINE ---
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

        # Centrage sur le canvas
        self.x0 = (c_w - self.total_px_w) / 2
        self.y0 = (c_h - self.total_px_h) / 2

        # --- 4. CRÉATION DE LA MATRICE DE TRAVAIL ---
        # On crée une matrice NumPy remplie de 255 (blanc) aux dimensions réelles de l'image
        self.display_data = np.full((max(1, self.rect_h), max(1, self.rect_w)), 255, dtype=np.uint8)
        
        # Épaisseur du laser scalée
        l_step = self.payload.get('dims', [0, 0, 0.1])[2]
        self.laser_width_px = max(1, int(l_step * self.scale))

        # --- 5. INITIALISATION DU CANVAS ---
        self.preview_canvas.delete("all")
        vis_pad = 10

        # Le fond blanc de la zone de travail
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

        # Coordonnées de l'origine de l'image pour screen_index()
        # On se cale sur x0, y0 car l'image commence là
        self.img_sx = self.x0
        self.img_sy = self.y0

        # Création du conteneur d'image dans le Canvas
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(self.display_data))
        self.img_container = self.preview_canvas.create_image(
            self.img_sx,
            self.img_sy,
            anchor="nw",
            image=self.tk_img,
            tags="main_image"
        )

        # Dessin de la grille (mm)
        self.draw_grid()

        # Création graphique du laser (Halo + Tête)
        self.laser_halo = self.preview_canvas.create_oval(
            0, 0, 0, 0, fill="#1a75ff", outline="#3385ff", width=1, tags="laser", stipple="gray50"
        )
        self.laser_head = self.preview_canvas.create_oval(
            0, 0, 0, 0, fill="#00ffff", outline="white", width=1, tags="laser"
        )
        
        # Éléments de la loupe
        self.loupe_container = self.preview_canvas.create_image(0, 0, anchor="center", state="hidden", tags="loupe")
        self.loupe_border = self.preview_canvas.create_oval(0, 0, 0, 0, outline="#ff9f43", width=2, state="hidden", tags="loupe")

        # --- 6. ÉTAT DE SIMULATION INITIAL ---
        self.current_point_idx = 0
        self.current_sim_time = 0.0
        self.last_frame_time = 0.0 # Important pour le prochain "Play"
        
        if self.points_list:
            mx, my = self.points_list[0][0], self.points_list[0][1]
            self.curr_x, self.curr_y = self.machine_to_screen(mx, my)
            # Pour éviter un trait fantôme au début
            self.prev_matrix_coords = self.screen_index(mx, my)

        # Mise à jour de l'UI (Labels de temps)
        t_total = self._format_seconds_to_hhmmss(self.total_sim_seconds)
        self.time_label.configure(text=f"Time: 00:00:00 / {t_total}")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")

        # Premier rendu visuel
        self.update_graphics()


    def _build_left_panel(self, payload):
        self.left_panel = ctk.CTkFrame(self, corner_radius=0, width=300)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.left_panel.grid_propagate(False) 
        
        ctk.CTkLabel(self.left_panel, text="PATH SIMULATION", font=("Arial", 14, "bold")).pack(pady=15)
        
        
        # 1. Conteneur des infos techniques (Remplace la boucle for)
        info_container = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        info_container.pack(fill="x", padx=10, pady=5)

        # --- RÉCUPÉRATION ET AFFICHAGE DES DONNÉES CIBLÉES ---
        
        # 1. Extraction des données depuis le tuple 'dims'
        # Structure : (0: h_px, 1: w_px, 2: l_step, 3: x_st)
        dims = payload.get('dims', (0, 0, 0, 0))
        h_px, w_px, step_y, step_x = dims

        # 2. Calcul et affichage de la taille finale en mm
        # (Largeur = pixels * pas)
        w_mm = w_px * step_x
        h_mm = h_px * step_y
        self._add_stat(info_container, "Final Size (mm):", f"{w_mm:.1f}x{h_mm:.1f}")

        # --- CHEMIN DE SORTIE FORMATÉ ---
        out_dir = payload.get('metadata', {}).get('output_dir', 'C:/')
        out_name = payload.get('metadata', {}).get('file_name', 'output.nc')
        full_path = os.path.join(out_dir, out_name).replace("\\", "/")
        
        self._add_stat(info_container, "Output Path:", full_path, is_path=True)

        # Échelle de Puissance
        params = payload.get('params', {})
        p_min = float(params.get("min_power", 0))
        p_max = float(params.get("max_power", 100))
        power_scale_frame = ctk.CTkFrame(info_container, fg_color="transparent")
        power_scale_frame.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(power_scale_frame, text="Power Range (%)", font=("Arial", 10, "bold")).pack(anchor="w")
        raw_color = self.left_panel.cget("fg_color")
        
        if isinstance(raw_color, (list, tuple)):
            appearance_mode = ctk.get_appearance_mode() # "Light" ou "Dark"
            bg_color = raw_color[1] if appearance_mode == "Dark" else raw_color[0]
        else:
            bg_color = raw_color
        self.power_canvas = ctk.CTkCanvas(
            power_scale_frame, 
            height=63, 
            bg=bg_color,
            highlightthickness=0
        )
        self.power_canvas.pack(fill="x", pady=5)

        def draw_power_scale():
            if not self.winfo_exists(): return
            self.power_canvas.update()
            w = max(self.power_canvas.winfo_width(), 180)
            
            # Ajustement des marges pour laisser de la place au texte plus grand
            margin = 25
            bar_y = 35  # Descendu pour laisser de la place aux labels Min/Max en 14pt
            bar_h = 10  # Barre un peu plus épaisse pour l'équilibre visuel
            bar_w = w - (2 * margin)
            
            # --- 1. DESSIN DU DÉGRADÉ DYNAMIQUE ---
            for i in range(int(bar_w)):
                current_pct = (i / bar_w) * 100
                if current_pct < p_min:
                    color_val = 255 # Blanc
                elif current_pct > p_max:
                    color_val = 0   # Noir
                else:
                    range_width = (p_max - p_min) if p_max > p_min else 1
                    local_ratio = (current_pct - p_min) / range_width
                    color_val = int((1 - local_ratio) * 255)
                
                color_hex = f'#{color_val:02x}{color_val:02x}{color_val:02x}'
                self.power_canvas.create_line(margin + i, bar_y, margin + i, bar_y + bar_h, fill=color_hex)
            
            self.power_canvas.create_rectangle(margin, bar_y, margin + bar_w, bar_y + bar_h, outline="#444")

            # --- 2. LIMITES 0% ET 100% (Police 12) ---
            # Positionnés sous la barre
            self.power_canvas.create_text(margin, bar_y + bar_h + 12, 
                                          text="0%", fill="#888888", font=("Arial", 12))
            self.power_canvas.create_text(margin + bar_w, bar_y + bar_h + 12, 
                                          text="100%", fill="#888888", font=("Arial", 12))

            # --- 3. CURSEURS ET VALEURS MIN/MAX (Police 14) ---
            for val, prefix in [(p_min, "Min: "), (p_max, "Max: ")]:
                x = margin + (val / 100 * bar_w)
                
                # Triangle orange
                self.power_canvas.create_polygon([x, bar_y-2, x-6, bar_y-12, x+6, bar_y-12], 
                                                  fill="#ff9f43", outline="#1a1a1a")
                
                # Texte Min/Max en gras et taille 14
                self.power_canvas.create_text(x, bar_y - 22, 
                                              text=f"{prefix}{int(val)}%", 
                                              fill="#ff9f43", 
                                              font=("Arial", 14, "bold"))
        
        self.after(200, draw_power_scale)

        # # File Name
        # fname_frame = ctk.CTkFrame(info_container, fg_color="transparent")
        # fname_frame.pack(fill="x", pady=2)
        # ctk.CTkLabel(fname_frame, text="File:", font=("Arial", 10, "bold"), width=40, anchor="w").pack(side="left")
        # ctk.CTkLabel(fname_frame, text=payload.get("file_name", "N/A"), font=("Arial", 10), anchor="e", wraplength=120).pack(side="right", fill="x", expand=True)

        #Gcode visualizer

        ctk.CTkLabel(self.left_panel, text="LIVE G-CODE", font=("Arial", 11, "bold")).pack(pady=(10, 0))

        # --- BLOC BAS (Déclaré en premier avec side="bottom" pour réserver le bas) ---

        # 1. Les boutons (Tout en bas)
        btn_act = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_act.pack(fill="x", side="bottom", pady=(0, 15)) 
        
        ctk.CTkButton(btn_act, text="CANCEL", fg_color="#333", height=30, 
                      command=self.on_cancel).pack(fill="x", side="bottom", padx=10, pady=5)
        
        ctk.CTkButton(btn_act, text="EXPORT GCODE", fg_color="#27ae60", height=40, 
                      font=("Arial", 11, "bold"), command=self.on_confirm).pack(fill="x", side="bottom", padx=10, pady=5)

        # 2. Groupe OPTIONS (Juste au-dessus des boutons)
        self.options_group_frame = ctk.CTkFrame(self.left_panel, fg_color="#222222", border_width=1, border_color="#444444")
        self.options_group_frame.pack(side="bottom", pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(self.options_group_frame, text="Active Options", font=("Arial", 11, "bold")).pack(pady=(8, 2))
        badge_cont = ctk.CTkFrame(self.options_group_frame, fg_color="transparent")
        badge_cont.pack(fill="x", padx=10, pady=(0, 10))

        for key, text in [("is_pointing", "POINTING"), ("is_framing", "FRAMING")]:
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

        # --- BLOC CENTRAL (Prend tout l'espace restant) ---

        self.gcode_view = ctk.CTkTextbox(
            self.left_panel, 
            font=("Consolas", 10), 
            fg_color="#1a1a1a", 
            text_color="#00ff00", 
            state="disabled"
        )

        self.gcode_view.pack(expand=True, fill="both", padx=10, pady=5)
    
        self.gcode_view.bind("<Up>", lambda e: self._scroll_gcode(-1))
        self.gcode_view.bind("<Down>", lambda e: self._scroll_gcode(1))
        self.gcode_view.bind("<Left>", lambda e: self._scroll_gcode(-5)) # Saut plus grand
        self.gcode_view.bind("<Right>", lambda e: self._scroll_gcode(5))

    def _scroll_gcode(self, delta):
        """Permet de naviguer dans le G-code et de synchroniser la simulation"""
        new_idx = max(0, min(self.current_point_idx + delta, len(self.points_list) - 1))
        if new_idx != self.current_point_idx:
            self.sim_running = False
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
            self.current_point_idx = new_idx
            self.current_sim_time = self.points_list[new_idx][4]
            self._redraw_up_to(new_idx)
            self.sync_sim_to_index(new_idx)
        return "break" # Empêche le comportement par défaut du widget texte

    def _add_stat(self, parent, label, value, is_path=False):
        """Helper pour afficher une ligne d'information propre"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        
        if is_path:
            # Pour le chemin : Label en haut, Valeur en bas (car trop long)
            ctk.CTkLabel(frame, text=label, font=("Arial", 10, "bold"), anchor="w").pack(side="top", fill="x")
            val_label = ctk.CTkLabel(
                frame, 
                text=value, 
                font=("Consolas", 9), 
                text_color="#3498db",
                anchor="w", 
                justify="left",
                wraplength=190
            )
            val_label.pack(side="top", fill="x", padx=5)
        else:
            ctk.CTkLabel(frame, text=label, font=("Arial", 10, "bold"), anchor="w").pack(side="left")
            ctk.CTkLabel(
                frame, 
                text=value, 
                font=("Consolas", 11), 
                text_color="#ecf0f1",
                anchor="e"
            ) .pack(side="right", fill="x", expand=True)

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

        self.btn_rewind = ctk.CTkButton(playback_cont, text="⏮", width=60, height=40, 
                                        font=("Arial", 20), fg_color="#444", hover_color="#555", 
                                        command=self.rewind_sim)
        self.btn_rewind.pack(side="left", padx=5)
        
        self.btn_play_pause = ctk.CTkButton(playback_cont, text="▶", width=100, height=40, font=("Arial", 20), fg_color="#27ae60", command=self.toggle_pause)
        self.btn_play_pause.pack(side="left", padx=5)
        
        self.btn_end = ctk.CTkButton(playback_cont, text="⏭", width=60, height=40, 
                             font=("Arial", 20), fg_color="#444", hover_color="#555", 
                             command=self.skip_to_end)
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
        self.progress_bar.bind("<Button-1>", self._on_progress_click)

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
         self.last_frame_time = time.time()
                  
      except ValueError:
         pass
      

    def toggle_pause(self):
        if not self.points_list:
            return

        # SI LE BOUTON EST EN MODE "REJOUER"
        if self.btn_play_pause.cget("text") == "🔄":
            self.rewind_sim()  # On remet tout à zéro (temps, points, matrice)
            # Pas besoin de faire plus, rewind_sim remet le bouton en mode "▶"
            # Si vous voulez qu'il se lance direct après le clic :
            self.sim_running = True
            self.last_frame_time = time.time()
            self.btn_play_pause.configure(text="⏸", fg_color="#e67e22")
            self.animate_loop()
            return

        # LOGIQUE PLAY / PAUSE CLASSIQUE
        if self.sim_running:
            self.sim_running = False
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
        else:
            self.sim_running = True
            self.last_frame_time = time.time()
            self.btn_play_pause.configure(text="⏸", fg_color="#e67e22")
            self.animate_loop()

    def rewind_sim(self):
        """Réinitialise la simulation au début."""
        self.sim_running = False
        if self.animation_job: 
            try:
                self.after_cancel(self.animation_job)
            except:
                pass
        self.animation_job = None
        
        # 1. Reset des compteurs
        self.current_point_idx = 0
        self.current_sim_time = 0.0  
        self.last_frame_time = 0.0   
        
        # 2. Reset de la matrice de dessin
        if hasattr(self, 'display_data'):
            self.display_data.fill(255)
        
        # 3. Reset de la position du laser
        if self.points_list:
            p0 = self.points_list[0]
            self.curr_x, self.curr_y = self.machine_to_screen(p0[0], p0[1])
            
        # 4. Mise à jour de l'UI
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        
        t_tot_str = self._format_seconds_to_hhmmss(self.total_sim_seconds)
        self.time_label.configure(text=f"Time: 00:00:00 / {t_tot_str}")
        
        # Remet le bouton en mode PLAY standard
        self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
        
        # 5. Reset de la vue G-code
        self.gcode_view.see("1.0")
        self.gcode_view.tag_remove("active", "1.0", "end")
        # Ajout : On surligne la première ligne si elle existe
        if self.points_list:
             self.update_gcode_highlight(0)
        
        # Rafraîchissement graphique
        self.update_graphics()

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
        if not self.winfo_exists() or not self.sim_running:
            return

        # 1. Gestion du temps réel
        now = time.time()
        if not hasattr(self, 'last_frame_time') or self.last_frame_time == 0:
            self.last_frame_time = now
        
        dt = (now - self.last_frame_time) * self.sim_speed
        self.last_frame_time = now
        self.current_sim_time += dt

        # 2. Rattrapage des points et dessin sur la matrice
        while (self.current_point_idx < len(self.points_list) - 1 and 
               self.points_list[self.current_point_idx + 1][4] < self.current_sim_time):
            
            idx = self.current_point_idx
            p1 = self.points_list[idx]
            p2 = self.points_list[idx + 1]
            
            if idx >= self.framing_end_idx and p2[2] > 0:
                ix1, iy1 = self.screen_index(p1[0], p1[1])
                ix2, iy2 = self.screen_index(p2[0], p2[1])
                
                # Calcul de la couleur (0=noir, 255=blanc)
                pwr = p2[2]
                ratio = max(0.0, min(1.0, float(pwr) / self.ctrl_max))
                color = int(255 * (1.0 - ratio))
                
                cv2.line(self.display_data, (ix1, iy1), (ix2, iy2), color, 
                         thickness=max(1, self.laser_width_px))
            
            self.current_point_idx += 1

        # 3. Vérification de la fin ou Interpolation
        if self.current_point_idx >= len(self.points_list) - 1:
            # --- CAS : FIN DE SIMULATION ---
            self.sim_running = False
            self.animation_job = None
            # On s'assure d'être exactement à 100%
            self.current_sim_time = self.total_sim_seconds
            self.sync_sim_to_index(len(self.points_list) - 1)
            # Bouton en mode REJOUER
            self.btn_play_pause.configure(text="🔄", fg_color="#2980b9")
            self.update_graphics()
            return
        else:
            # --- CAS : CONTINUATION (Interpolation Laser Bleu) ---
            p_prev = self.points_list[self.current_point_idx]
            p_next = self.points_list[self.current_point_idx + 1]
            
            t_start, t_end = p_prev[4], p_next[4]
            ratio_interp = (self.current_sim_time - t_start) / (t_end - t_start) if (t_end - t_start) > 0 else 1.0
            
            interp_x = p_prev[0] + (p_next[0] - p_prev[0]) * ratio_interp
            interp_y = p_prev[1] + (p_next[1] - p_prev[1]) * ratio_interp
            
            self.curr_x, self.curr_y = self.machine_to_screen(interp_x, interp_y)
            self.sync_sim_to_index(self.current_point_idx)

        # 4. Rendu et planification
        self.update_graphics()
        self.animation_job = self.after(16, self.animate_loop)  

    def sync_sim_to_index(self, target_idx):
        """Met à jour l'UI, le temps et le laser pour un index donné."""
        if not self.points_list or target_idx >= len(self.points_list):
            return

        # 1. Mise à jour des coordonnées du laser
        mx, my, pwr, line_idx, ts = self.points_list[target_idx]
        self.curr_x, self.curr_y = self.machine_to_screen(mx, my)

        # 2. Progression
        total_pts = len(self.points_list)
        progress = target_idx / max(1, total_pts)
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Progress: {int(progress*100)}%")

        # 3. Calcul du temps
        c_sec = self.points_list[target_idx][4]

        self.time_label.configure(
            text=f"Time: {self._format_seconds_to_hhmmss(c_sec)} / {self._format_seconds_to_hhmmss(self.total_sim_seconds)}"
        )

        # 4. Refresh graphique
        self.update_graphics()
        
        # 5. Highlight G-code
        self.update_gcode_highlight(target_idx)

    def update_gcode_highlight(self, target_idx):
            """Met à jour la ligne surlignée dans l'éditeur G-code en fonction de l'index du point."""
            if not self.sim_running and target_idx != self.current_point_idx:
                return
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
            # Trouver la ligne cliquée dans le widget texte
            index = self.gcode_view.index(f"@{event.x},{event.y}")
            line_clicked = int(index.split('.')[0])

            # Chercher le point correspondant
            target_idx = None
            for i, p in enumerate(self.points_list):
                # p[3] est l'index de ligne G-Code
                if p[3] == line_clicked:
                    target_idx = i
                    break
            
            if target_idx is not None:
                # 1. On fige la simulation
                self.sim_running = False
                self.btn_play_pause.configure(text="▶", fg_color="#27ae60")

                # 2. SYNCHRONISATION TEMPORELLE (Crucial !)
                # On récupère le timestamp (p[4]) associé à ce point
                self.current_point_idx = target_idx
                self.current_sim_time = self.points_list[target_idx][4]

                # 3. MISE À JOUR VISUELLE
                self.sync_sim_to_index(target_idx) # Met à jour labels et barre
                self._redraw_up_to(target_idx)      # Redessine la matrice jusqu'à ce point
                self.update_gcode_highlight(target_idx)
                
        except Exception as e:
            print(f"GCode selection error: {e}")

    def _on_progress_click(self, event):
        """Déplace la simulation sans freezer l'UI."""
        if not self.points_list or self.total_sim_seconds <= 0:
            return

        try:
            # 1. Calcul du ratio
            bar_width = self.progress_bar.winfo_width()
            ratio = max(0, min(event.x / bar_width, 1.0))
            
            # 2. Suspension de l'animation pour éviter les conflits
            was_running = self.sim_running
            self.sim_running = False 
            if self.animation_job:
                self.after_cancel(self.animation_job)
                self.animation_job = None
            
            # 3. Calcul du nouveau point (Temporel)
            self.current_sim_time = ratio * self.total_sim_seconds
            self.current_point_idx = bisect.bisect_left(self.timestamps, self.current_sim_time)
            self.current_point_idx = max(0, min(self.current_point_idx, len(self.points_list) - 1))
            
            # 4. Rendu (La partie qui peut prendre du temps)
            self._redraw_up_to(self.current_point_idx)
            self.sync_sim_to_index(self.current_point_idx)
            
            # 5. Reprise après un court délai pour laisser l'UI respirer
            if was_running:
                self.sim_running = True
                self.last_frame_time = time.time()
                self.animation_job = self.after(10, self.animate_loop)
            else:
                self.update_graphics()
                
        except Exception as e:
            print(f"Progress click error: {e}")


    def _recalibrate_index_from_time(self):
        """Trouve l'index du point G-Code le plus proche du temps actuel via recherche binaire."""
        if not self.points_list:
            return
        
        # On crée ou récupère la liste des timestamps (le 5ème élément de chaque point)
        # Note : pour optimiser encore plus, tu peux stocker cette liste de timestamps 
        # une fois pour toutes dans _on_gen_done
        timestamps = [p[4] for p in self.points_list]
        
        # Trouve l'index d'insertion pour maintenir l'ordre
        # C'est l'équivalent ultra-rapide de ta boucle for
        found_idx = bisect.bisect_left(timestamps, self.current_sim_time)
        
        # Sécurité pour ne pas dépasser la liste
        self.current_point_idx = min(found_idx, len(self.points_list) - 1)
        
        # Synchronisation UI
        self.sync_sim_to_index(self.current_point_idx)

    def _redraw_up_to(self, target_idx):
        """
        Version optimisée du rendu de masse.
        Optimisation : réduction des accès aux attributs et suppression des appels UI.
        """
        if not self.points_list:
            return

        # 1. On efface tout (fond blanc)
        self.display_data.fill(255)

        # 2. CACHING : On extrait les variables de l'objet vers des variables locales
        # Accéder à 'self.xxx' dans une boucle de 100k itérations ralentit Python
        points = self.points_list
        ctrl_max = float(self.ctrl_max)
        laser_width = max(1, self.laser_width_px)
        # On récupère les fonctions comme variables locales
        screen_index = self.screen_index
        cv2_line = cv2.line
        
        # 3. Boucle de dessin optimisée
        # On commence après le framing
        start_idx = self.framing_end_idx + 1
        
        # On limite l'index cible pour éviter les débordements
        limit = min(target_idx + 1, len(points))

        for i in range(start_idx, limit):
            p1 = points[i-1]
            p2 = points[i]
            
            # p2[2] est la puissance (S)
            pwr = p2[2]
            if pwr > 0:
                # Conversion coordonnées machine -> pixels écran
                ix1, iy1 = screen_index(p1[0], p1[1])
                ix2, iy2 = screen_index(p2[0], p2[1])
                
                # Calcul de la couleur (0=noir, 255=blanc)
                # On évite les fonctions complexes, on utilise l'arithmétique pure
                ratio = pwr / ctrl_max
                if ratio > 1.0: ratio = 1.0
                color = int(255 * (1.0 - ratio))
                
                # Dessin sur la matrice en mémoire
                cv2_line(self.display_data, (ix1, iy1), (ix2, iy2), 
                         color, thickness=laser_width, lineType=cv2.LINE_8)

        # 4. Mise à jour finale du curseur bleu (en dehors de la boucle)
        last_p = points[target_idx]
        self.curr_x, self.curr_y = self.machine_to_screen(last_p[0], last_p[1])
        
        # On ne rafraîchit l'UI qu'UNE seule fois ici
        # L'appel à update_graphics() se chargera de convertir display_data en image Tkinter

    def skip_to_end(self):
        """Termine instantanément la simulation avec un rendu optimisé."""
        if not self.winfo_exists() or not self.points_list:
            return

        # 1. Arrêt immédiat de l'animation
        self.sim_running = False
        if self.animation_job:
            try: self.after_cancel(self.animation_job)
            except: pass
        self.animation_job = None

        # 2. On saute directement à la fin du temps et des points
        self.current_sim_time = self.total_sim_seconds
        self.current_point_idx = len(self.points_list) - 1
        
        # 3. Dessin massif (Optimisé : pas d'appels UI dans la boucle)
        self._redraw_up_to(self.current_point_idx)

        # 4. Une SEULE mise à jour UI finale (très important pour la vitesse)
        try:
            t_str = self._format_seconds_to_hhmmss(self.total_sim_seconds)
            self.time_label.configure(text=f"Time: {t_str} / {t_str}")
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="Progress: 100%")
            
            # On ne fait défiler le G-Code qu'une fois
            self.update_gcode_highlight(self.current_point_idx)
            self.btn_play_pause.configure(text="🔄", fg_color="#2980b9")
            self.update_graphics()
        except Exception as e:
            print(f"Erreur UI skip_to_end: {e}")

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

   

    def draw_grid(self):
        """Dessine la grille millimétrée (tous les 10mm) basée sur les coordonnées machine."""
        col, txt_col, dash = "#e0e0e0", "#888888", (2, 4)
        self.preview_canvas.delete("grid")

        vis_pad = 10

        # 1. DÉFINITION DES BORNES RÉELLES (en mm)
        
        x_start_mm = self.min_x_machine - (vis_pad / self.scale)
        x_end_mm = self.min_x_machine + self.total_mouvement_w + (vis_pad / self.scale)
        y_start_mm = self.min_y_machine - (vis_pad / self.scale)
        y_end_mm = self.min_y_machine + self.total_mouvement_h + (vis_pad / self.scale)

        step = 10

        # 2. LIGNES VERTICALES (Axe X)
        for vx in range(int(np.floor(x_start_mm/step)*step), int(np.ceil(x_end_mm/step)*step) + step, step):
            sx, _ = self.machine_to_screen(vx, self.min_y_machine)
            # Ligne de haut en bas du canvas (ou limites du rect)
            self.preview_canvas.create_line(sx, self.y0 - vis_pad, sx, self.y0 + self.total_px_h + vis_pad, 
                                            fill=col, dash=dash, tags="grid")
            self.preview_canvas.create_text(sx, self.y0 + self.total_px_h + vis_pad + 15, 
                                            text=str(vx), fill=txt_col, font=("Arial", 14), tags="grid")

        for vy in range(int(np.floor(y_start_mm/step)*step), int(np.ceil(y_end_mm/step)*step) + step, step):
            _, sy = self.machine_to_screen(self.min_x_machine, vy)
            self.preview_canvas.create_line(self.x0 - vis_pad, sy, self.x0 + self.total_px_w + vis_pad, sy, 
                                            fill=col, dash=dash, tags="grid")
            self.preview_canvas.create_text(self.x0 - vis_pad - 20, sy, 
                                            text=str(vy), fill=txt_col, font=("Arial", 14), tags="grid")

            #self.preview_canvas.tag_raise("grid", "bg_rect") # Juste au dessus du fond blanc



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
        """Action déclenchée par le bouton 'Confirm' (Save G-Code + Stats + Thumbnail via Utils)"""
        self.stop_processes()
        
        # 1. Préparation du chemin de sortie du G-Code
        output_dir = self.payload['metadata'].get('output_dir', '')
        file_name = self.payload['metadata'].get('file_name', 'output.nc')
        full_path = os.path.join(output_dir, file_name)

        # 2. Sauvegarde du fichier et mise à jour des données
        try:
            if hasattr(self, 'final_gcode') and self.final_gcode:
                # --- A. Sauvegarde du G-Code ---
                with open(full_path, "w") as f:
                    f.write(self.final_gcode)

                # --- B. Appel de la fonction centralisée dans utils.py ---
                matrix = self.payload.get('matrix') 
                if matrix is not None:
                    # On appelle directement la fonction importée de utils
                    from core.utils import save_dashboard_data
                    save_dashboard_data(
                        config_manager=self.controller.config_manager,
                        matrix=matrix,
                        gcode_content=self.final_gcode,
                        estimated_time=getattr(self, 'total_sim_seconds', 0)
                    )

                messagebox.showinfo("Success", f"G-Code saved to:\n{full_path}", parent=self.controller)
                
                # 3. Retour à la vue précédente
                self._navigate_back()
            else:
                messagebox.showerror("Error", "No G-Code data to save.", parent=self.controller)
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}", parent=self.controller)

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