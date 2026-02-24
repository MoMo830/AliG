
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
from tkinter import messagebox, filedialog
import cv2


from engine.gcode_parser import GCodeParser
from core.utils import save_dashboard_data, truncate_path


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
        self.points_list = None
        self.current_point_idx = 0
        self.last_mouse_coords = (0, 0)
        self.sim_speed = 1.0 
        self.last_drawn_idx = -1
        self.latence_switch = None
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
        self.grid_columnconfigure(0, weight=0, minsize=420)  # panneau stats + gcode
        self.grid_columnconfigure(1, weight=1)               # simulation prend tout
        self.grid_rowconfigure(0, weight=1)

        # 4. Construction des panneaux
        self._build_left_panel(self.payload)
        self._build_right_panel()


        # 5. OVERLAY DE CHARGEMENT
        self.loading_frame = ctk.CTkFrame(
            self,
            fg_color="#2b2b2b"
        )

        # Couvre toute la vue, indépendamment du grid
        self.loading_frame.place(
            relx=0,
            rely=0,
            relwidth=1,
            relheight=1
        )

        # Conteneur centré pour le popup
        self.loading_box = ctk.CTkFrame(
            self.loading_frame,
            fg_color="#3a3a3a",
            corner_radius=12
        )
        self.loading_box.place(relx=0.5, rely=0.5, anchor="center")

        self.loading_label = ctk.CTkLabel(
            self.loading_box,
            text="Generating G-Code & Trajectory...",
            font=("Arial", 14, "bold"),
            text_color="white"
        )
        self.loading_label.pack(padx=30, pady=(20, 10))

        self.gen_progress = ctk.CTkProgressBar(self.loading_box, width=280)
        self.gen_progress.pack(padx=30, pady=(5, 25))
        self.gen_progress.configure(mode="indeterminate")
        self.gen_progress.start()

        self.update_idletasks()
        # 6. LANCEMENT DU CALCUL DÉFÉRÉ
        self.after(100, self._start_thread)

    def _start_thread(self):
        import threading
        threading.Thread(target=self._async_generation, daemon=True).start()

    def _async_generation(self): 
        try: 
            import time
            import numpy as np
            start_global = time.perf_counter()

            # 1. PRÉPARATION DES PARAMÈTRES 
            params = self.payload['params'] 
            g_steps = params.get('gray_steps') 
            use_s_mode = params.get('use_s_mode') 
            raster_mode = params.get('raster_mode', 'horizontal') 
            
            # Récupération de la taille déjà estimée par la vue Raster
            est_size_str = self.payload.get('estimated_size', "N/A")


            # A. Génération du G-Code de Cadrage (Framing)
            t_start = time.perf_counter()
            self.framing_gcode = self.engine.prepare_framing( 
                self.payload['framing'],  
                (self.payload['metadata']['real_w'], self.payload['metadata']['real_h']),  
                self.payload['offsets'] 
            ) 
            print(f"[BENCH] A. Framing G-Code: {time.perf_counter() - t_start:.4f}s")

            # B. Métadonnées
            full_metadata = self.payload['metadata'].copy() 
            full_metadata.update({
                'framing_code': self.framing_gcode,
                'gray_steps': g_steps,
                'use_s_mode': use_s_mode,
                'raster_mode': raster_mode,
                'scan_axis': "X" if raster_mode == "horizontal" else "Y"
            })
            self.full_metadata = full_metadata 
            print(f"[DEBUG] scan_axis = {self.full_metadata.get('scan_axis')}")
            # C. Génération du G-Code Final
            t_start = time.perf_counter()
            
            # APPEL À L'ENGINE
            self.final_gcode, determined_latence_mm = self.engine.build_final_gcode( 
                self.payload['matrix'], 
                self.payload['dims'], 
                self.payload['offsets'], 
                params, 
                self.payload['text_blocks'], 
                full_metadata 
            ) 
            
            self.latence_mm = float(determined_latence_mm)
            
            # D. PARSING (Récupération des limites réelles)
            t_start = time.perf_counter()
            
            # Parsing du framing
            f_points_array, f_dur, f_limits = self.parser.parse(self.framing_gcode) 
            framing_end_idx = len(f_points_array) if f_points_array is not None else 0

            # Parsing du G-code final
            pts_array, _, limits = self.parser.parse(self.final_gcode) 
            
            # --- CALCUL DES BORNES GLOBALES ---
            valid_limits = []

            if f_limits is not None:
                if not all(abs(v) < 1e-9 for v in f_limits):
                    valid_limits.append(f_limits)

            if limits is not None:
                if not all(abs(v) < 1e-9 for v in limits):
                    valid_limits.append(limits)

            if valid_limits:
                all_min_x = min(l[0] for l in valid_limits)
                all_max_x = max(l[1] for l in valid_limits)
                all_min_y = min(l[2] for l in valid_limits)
                all_max_y = max(l[3] for l in valid_limits)
            else:
                all_min_x = all_max_x = all_min_y = all_max_y = 0.0
            
            print(f"[BENCH] D. Parsing G-Code ({len(pts_array) if pts_array is not None else 0} pts): {time.perf_counter() - t_start:.4f}s")
             
            # E. CALCUL DES TIMESTAMPS
            if pts_array is not None and len(pts_array) > 1:
                # 1. Calcul de la progression réelle via NumPy
                deltas = np.diff(pts_array[:, :2], axis=0) 
                distances = np.sqrt(np.sum(deltas**2, axis=1))
                f_rates_sec = pts_array[1:, 4] / 60.0
                durations = np.divide(distances, f_rates_sec, out=np.zeros_like(distances), where=f_rates_sec > 0)
                
                pts_array[0, 4] = 0.0
                pts_array[1:, 4] = np.cumsum(durations)

                # 2. Calcul théorique synchronisé
                m = self.payload.get('metadata', {})
                p = self.payload.get('params', {})
                dims = self.payload.get('dims', (0, 0, 0, 0)) # (H_px, W_px, ...)

                # Correction : On récupère H_px et W_px depuis le tuple dims
                h_px_real = dims[0]
                w_px_real = dims[1]

                if str(p.get('raster_mode', 'horizontal')).lower() == 'vertical':
                    nb_lignes = float(w_px_real)
                    dist_utile = float(m.get('real_h', 0.0))
                else:
                    nb_lignes = float(h_px_real)
                    dist_utile = float(m.get('real_w', 0.0))

                feedrate = float(p.get('feedrate', 3000.0))
                overscan = float(p.get('premove', 2.0))
                l_step = float(p.get('line_step', p.get('l_step', 0.1)))

                # Formule identique au moteur
                dist_ligne = dist_utile + (2 * overscan)
                dist_decalage_total = (nb_lignes - 1) * l_step
                total_dist = (nb_lignes * dist_ligne) + dist_decalage_total

                # Calcul en secondes
                total_engine_duration_sec = total_dist / (feedrate / 60.0)
                
                # On utilise le max pour être ultra-précis (inclut latences G-Code)
                final_dur = max(pts_array[-1, 4], total_engine_duration_sec)
                
                # Debug pour confirmer que nb_lignes n'est plus à 0
                print(f"[DEBUG SIM] Nb Lignes: {nb_lignes}, Dist: {total_dist:.2f}, Final: {final_dur/60:.2f}min")
            else:
                final_dur = 0.0



            # F. PRÉPARATION DU RETOUR 
            self.raw_sim_data = { 
                'points_list': pts_array, 
                'framing_end_idx': framing_end_idx, 
                'f_dur': f_dur, 
                'total_dur': final_dur, 
                'full_metadata': full_metadata,
                'latence_mm': self.latence_mm,
                'est_size_str': est_size_str, 
                'machine_bounds': (all_min_x, all_max_x, all_min_y, all_max_y)
            }
            
            if self.winfo_exists(): 
                self.after(0, self._on_gen_done)
             
        except Exception as e: 
            print(f"[DEBUG ERROR] Erreur thread: {e}") 
            import traceback
            traceback.print_exc()
            if self.winfo_exists(): 
                self.after(0, lambda: self._handle_gen_error(str(e)))

    def _handle_gen_error(self, msg):
        messagebox.showerror("Engine Error", f"Failed to generate G-code:\n{msg}")
        self.destroy()

    def _on_gen_done(self):
        if not self.raw_sim_data:
            return

        # 🔒 Stop loading flag
        self.is_loading = False

        # 1. Récupération des données du Parser et de l'Engine
        self.points_list = self.raw_sim_data['points_list']
        self.total_sim_seconds = self.raw_sim_data.get('total_dur', 0.0)
        self.latence_mm = self.raw_sim_data.get('latence_mm', 0.0)
        est_size_str = self.raw_sim_data.get('est_size_str', "N/A")

        # 2. Limites machine
        bounds = self.raw_sim_data.get('machine_bounds', (0, 0, 0, 0))
        self.min_x_machine, self.max_x_machine, self.min_y_machine, self.max_y_machine = bounds

        # 3. Dimensions mouvement
        self.total_mouvement_w = max(0.1, self.max_x_machine - self.min_x_machine)
        self.total_mouvement_h = max(0.1, self.max_y_machine - self.min_y_machine)

        # --- GESTION DYNAMIQUE DE L'INTERFACE ---
        
        # A. Mise à jour de la taille estimée

        # B. Affichage conditionnel du switch de latence
        if hasattr(self, 'latence_switch') and self.latence_switch is not None:
            # On vérifie si la latence est non-nulle (positive ou négative)
            if abs(self.latence_mm) > 1e-6: 
                # On ré-affiche le switch
                self.latence_switch.pack(pady=(5, 10), padx=10)
                # self.latence_switch.deselect() # Optionnel
            else:
                # On cache le switch car la latence est strictement nulle
                self.latence_switch.pack_forget()

        # 4. Injection G-Code
        if hasattr(self, 'final_gcode') and self.final_gcode:
            lines = self.final_gcode.splitlines()
            self.max_gcode_chars = max(len(l) for l in lines) if lines else 40

            self.gcode_view.configure(state="normal")
            self.gcode_view.delete("1.0", "end")
            self.gcode_view.insert("1.0", self.final_gcode)
            self.gcode_view.configure(state="disabled")

            self.update_idletasks()
            self._apply_dynamic_fonts(self.left_panel.winfo_width())
        else:
            print("[DEBUG WARNING] Aucun G-Code à afficher dans le widget")

        # 5. Nettoyage overlay (IMPORTANT : stop AVANT destroy)
        if hasattr(self, 'gen_progress'):
            self.gen_progress.stop()

        if hasattr(self, 'loading_frame'):
            self.loading_frame.place_forget()
            self.loading_frame.destroy()

        # DEBUG
        #self._debug_show_parser_matrix()
        
        # 6. Dessin initial
        self._prepare_and_draw()
        
        

    def _debug_show_parser_matrix(self):
        import matplotlib.pyplot as plt


        if not hasattr(self, "points_list") or self.points_list is None:
            print("[DEBUG] Pas de matrice parser disponible")
            return

        try:
            # Conversion en numpy array si ce n'est pas déjà le cas
            pts = np.asarray(self.points_list)

            # --- CORRECTION 1: Tolérance sur les arrondis ---
            # On arrondit à 4 décimales pour éviter que 1.0000001 != 1.0000000
            xs_rounded = np.round(pts[:, 0], 4)
            ys_rounded = np.round(pts[:, 1], 4)
            power = pts[:, 2]

            # Détection de la grille
            x_unique = np.sort(np.unique(xs_rounded))
            y_unique = np.sort(np.unique(ys_rounded))

            nx, ny = len(x_unique), len(y_unique)

            if nx < 2 or ny < 2:
                print(f"[DEBUG] Matrice trop petite: {nx}x{ny}")
                return

            # Création de la matrice (initialisée à 0 ou NaN selon ton besoin)
            matrix = np.zeros((ny, nx), dtype=np.float32)

            # Mapping indexé
            x_map = {v: i for i, v in enumerate(x_unique)}
            y_map = {v: i for i, v in enumerate(y_unique)}

            # Remplissage vectorisé (plus rapide que la boucle for)
            for i in range(len(pts)):
                xi = x_map[xs_rounded[i]]
                yi = y_map[ys_rounded[i]]
                matrix[yi, xi] = power[i]

            # --- CORRECTION 2: Cohérence d'affichage ---
            # Si tu veux que l'origine (0,0) soit en BAS à gauche (standard mathématique) :
            # On ne fait PAS de flipud, et on utilise origin="lower"
            
            fig, ax = plt.subplots(num="DEBUG PARSER MATRIX", figsize=(8, 6))
            
            im = ax.imshow(
                matrix,
                cmap="gray_r",
                interpolation="none",
                aspect="equal", # "equal" respecte le ratio réel de ton objet
                origin="lower",  # Le Y=0 est en bas
                extent=[x_unique.min(), x_unique.max(), y_unique.min(), y_unique.max()]
            )

            fig.colorbar(im, ax=ax, label="Laser Power (%)")
            ax.set_title(f"Reconstruction: {nx}x{ny} points")
            ax.set_xlabel("X (mm)")
            ax.set_ylabel("Y (mm)")

            plt.tight_layout()
            plt.show(block=False)
            plt.pause(0.1)

        except Exception as e:
            import traceback
            print(f"[DEBUG MATRIX SHOW ERROR] {e}")
            traceback.print_exc()

    def _build_left_panel(self, payload):
        self.left_panel = ctk.CTkFrame(self, corner_radius=0, width=300)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.left_panel.grid_propagate(False) 
        
        ctk.CTkLabel(self.left_panel, text="PATH SIMULATION", font=("Arial", 14, "bold")).pack(pady=15)
        
        # 1. Conteneur des infos techniques
        info_container = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        info_container.pack(fill="x", padx=10, pady=5)

        # --- RÉCUPÉRATION ET AFFICHAGE DES DONNÉES ---
        dims = payload.get('dims', (0, 0, 0, 0))
        h_px, w_px, step_y, step_x = dims
        w_mm = (w_px - 1) * step_x
        h_mm = (h_px - 1) * step_y
        
        self._add_stat(info_container, "Final Size (mm):", f"{w_mm:.2f}x{h_mm:.2f}")

        # --- CHEMIN DE SORTIE  ---

        # --- CHEMIN DE SORTIE (Calcul via Payload) ---
        meta = self.payload.get('metadata', {}) # Utilise self.payload
        out_dir = meta.get('output_dir', 'C:/')

        # 1. Récupération de l'extension
        # Si 'file_extension' n'existe pas dans le payload, on met ".nc" par défaut
        extension = meta.get('file_extension', '.nc')
        print(f"DEBUG: extension = {extension}")

        # 2. Récupération du nom
        raw_name = meta.get('file_name', 'export')

        # 3. Assemblage forcé (On ignore les vérifications de point pour tester)
        full_filename = f"{raw_name}{extension}"

        # 4. Construction du chemin complet
        full_path = os.path.join(out_dir, full_filename).replace("\\", "/")

        # IMPORTANT : On stocke pour le bouton QUICK EXPORT
        self.quick_export_full_path = full_path
        print(f"DEBUG: full_path = {full_path}")

        # 5. Envoi à l'affichage
        # On change le label pour "Output File:" pour être plus précis
        self.full_export_path = full_path # On le stocke ici
        self._add_stat(info_container, "Output File:", full_path, is_path=True)

        # --- ÉCHELLE DE PUISSANCE ---
        params = payload.get('params', {})
        p_min = float(params.get("min_power", 0))
        p_max = float(params.get("max_power", 100))
        power_scale_frame = ctk.CTkFrame(info_container, fg_color="transparent")
        power_scale_frame.pack(fill="x", pady=10, padx=5)
        
        ctk.CTkLabel(power_scale_frame, text="Power Range (%)", font=("Arial", 10, "bold")).pack(anchor="w")
        
        raw_color = self.left_panel.cget("fg_color")
        if isinstance(raw_color, (list, tuple)):
            bg_color = raw_color[1] if ctk.get_appearance_mode() == "Dark" else raw_color[0]
        else:
            bg_color = raw_color

        self.power_canvas = ctk.CTkCanvas(
            power_scale_frame, height=63, bg=bg_color, highlightthickness=0
        )
        self.power_canvas.pack(fill="x", pady=5)

        def draw_power_scale():
            if not self.winfo_exists(): return
            self.power_canvas.update()
            w = max(self.power_canvas.winfo_width(), 180)
            margin, bar_y, bar_h = 25, 35, 10
            bar_w = w - (2 * margin)
            
            for i in range(int(bar_w)):
                current_pct = (i / bar_w) * 100
                if current_pct < p_min: color_val = 255
                elif current_pct > p_max: color_val = 0
                else:
                    range_w = (p_max - p_min) if p_max > p_min else 1
                    color_val = int((1 - (current_pct - p_min) / range_w) * 255)
                self.power_canvas.create_line(margin + i, bar_y, margin + i, bar_y + bar_h, fill=f'#{color_val:02x}{color_val:02x}{color_val:02x}')
            
            self.power_canvas.create_rectangle(margin, bar_y, margin + bar_w, bar_y + bar_h, outline="#444")
            self.power_canvas.create_text(margin, bar_y + bar_h + 12, text="0%", fill="#888888", font=("Arial", 12))
            self.power_canvas.create_text(margin + bar_w, bar_y + bar_h + 12, text="100%", fill="#888888", font=("Arial", 12))

            for val, prefix in [(p_min, "Min: "), (p_max, "Max: ")]:
                x = margin + (val / 100 * bar_w)
                self.power_canvas.create_polygon([x, bar_y-2, x-6, bar_y-12, x+6, bar_y-12], fill="#ff9f43", outline="#1a1a1a")
                self.power_canvas.create_text(x, bar_y - 22, text=f"{prefix}{int(val)}%", fill="#ff9f43", font=("Arial", 14, "bold"))
        
        self.after(200, draw_power_scale)

       # --- BLOC CENTRAL (G-Code View) ---
        # On le place avant les boutons "bottom" pour qu'il occupe l'espace restant au milieu
        ctk.CTkLabel(self.left_panel, text="LIVE G-CODE", font=("Arial", 11, "bold")).pack(pady=(10, 0))
        
        self.gcode_view = ctk.CTkTextbox(
            self.left_panel, font=("Consolas", 11), fg_color="#1a1a1a", 
            text_color="#00ff00", state="disabled", wrap="none"
        )
        self.gcode_view.pack(expand=True, fill="both", padx=10, pady=5)

        # --- BLOC BAS (Boutons et Options) ---
        # 1. Conteneur des boutons d'action (CANCEL / EXPORT)
        # --- Dans setup_ui de SimulationView ---
        btn_act = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_act.pack(fill="x", side="bottom", pady=(0, 15)) 
        
        # Bouton CANCEL (tout en bas)
        ctk.CTkButton(
            btn_act, text="CANCEL", fg_color="#333", height=30, 
            command=self.on_cancel
        ).pack(fill="x", side="bottom", padx=10, pady=5)
        
        # Conteneur horizontal pour les exports
        export_row = ctk.CTkFrame(btn_act, fg_color="transparent")
        export_row.pack(fill="x", side="bottom", padx=10, pady=5)

        # QUICK EXPORT 
        # Couleur suggérée :
        self.btn_export = ctk.CTkButton(
            export_row, 
            text="QUICK EXPORT", 
            fg_color="#2ecc71",      # Vert plus clair et moderne
            hover_color="#27ae60",   # Teinte un peu plus sombre au survol
            height=40, 
            text_color="white",
            font=("Arial", 11, "bold"), 
            command=self.on_export
        )
        self.btn_export.pack(side="left", expand=True, fill="x", padx=(0, 5))

        # EXPORT AS... 
        self.btn_export_as = ctk.CTkButton(
            export_row, 
            text="Export As...", 
            command=self.on_export_as,
            fg_color="#7ac99b", 
            hover_color="#27ae60",
            border_width=1, 
            border_color="#555",
            height=40,
            width=100
        )
        self.btn_export_as.pack(side="right", expand=True, fill="x")
        # 2. Conteneur des options (Badges et Latence)
        self.options_group_frame = ctk.CTkFrame(self.left_panel, fg_color="#222222", border_width=1, border_color="#444444")
        self.options_group_frame.pack(side="bottom", pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(self.options_group_frame, text="Active Options", font=("Arial", 11, "bold")).pack(pady=(8, 2))
        
        badge_cont = ctk.CTkFrame(self.options_group_frame, fg_color="transparent")
        badge_cont.pack(fill="x", padx=10, pady=(0, 5))

        # Affichage des badges POINTING / FRAMING
        for key, text in [("is_pointing", "POINTING"), ("is_framing", "FRAMING")]:
            active = self.payload.get('framing', {}).get(key, False)
            color, bg = ("#ff9f43", "#3d2b1f") if active else ("#666666", "#282828")
            ctk.CTkLabel(badge_cont, text=text, font=("Arial", 9, "bold"), 
                         text_color=color, fg_color=bg, corner_radius=5).pack(side="left", expand=True, fill="x", padx=2)

        # 3. Gestion de la latence (Switch conditionnel)
        self.vis_corr_enabled = False
        self.latence_switch = None # Initialisation par défaut
        
        latence_val = float(self.payload.get('params', {}).get('m67_delay', 0))
        
        if latence_val != 0:
            self.latence_switch = ctk.CTkSwitch(
                self.options_group_frame, 
                text="SIMULATE LATENCY", 
                font=("Arial", 10, "bold"), 
                progress_color="#27ae60", 
                command=self.toggle_latency_sim
            )
            self.latence_switch.pack(pady=(5, 10), padx=10)

        # --- GESTION DYNAMIQUE ET BINDINGS ---
        self._resize_timer = None

        def on_resize(event):
            if event.widget == self.left_panel:
                if self._resize_timer:
                    self.after_cancel(self._resize_timer)
                self._resize_timer = self.after(50, lambda: self._apply_dynamic_fonts(event.width))

        self.left_panel.bind("<Configure>", on_resize)

        # Navigation clavier pour la vue G-Code
        self.gcode_view.bind("<Up>", lambda e: self._scroll_gcode(-1))
        self.gcode_view.bind("<Down>", lambda e: self._scroll_gcode(1))
        self.gcode_view.bind("<Left>", lambda e: self._scroll_gcode(-10))
        self.gcode_view.bind("<Right>", lambda e: self._scroll_gcode(10))

    def _apply_dynamic_fonts(self, width):
        if not self.winfo_exists():
            return

        if hasattr(self, 'path_label'):
            avail_width = width - 30
            min_font = 8
            max_font = 12

            # --- CORRECTION ICI ---
            # On utilise le chemin complet calculé au début (qui contient l'extension)
            # Si pour une raison X il n'existe pas, on met une chaîne vide
            full_path = getattr(self, 'full_export_path', "")
            if not full_path:
                return 
            # ----------------------

            # Test progressif de taille
            for size in range(max_font, min_font - 1, -1):
                self.path_label.configure(font=("Consolas", size))
                self.path_label.update_idletasks()

                # Calcul du ratio largeur/caractère pour estimer max_chars
                req_w = self.path_label.winfo_reqwidth()
                char_width = req_w / max(1, len(self.path_label.cget("text")))

                max_chars = int(avail_width / max(char_width, 1))
                
                # On tronque à partir du VRAI chemin complet
                truncated = truncate_path(full_path, max_length=max_chars)
                self.path_label.configure(text=truncated)

                self.path_label.update_idletasks()
                if self.path_label.winfo_reqwidth() <= avail_width:
                    break
        # -----------------------------
        # GCODE VIEW
        # -----------------------------
        if hasattr(self, "gcode_view") and hasattr(self, "max_gcode_chars"):

            usable_width = max(100, width - 20)

            # Largeur caractère réelle estimée (monospace Consolas)
            # 0.55 est plus réaliste que 0.6
            optimal_size = int(usable_width / (self.max_gcode_chars * 0.55))

            optimal_size = max(6, min(18, optimal_size))

            self.gcode_view.configure(font=("Consolas", optimal_size))


    def _add_stat(self, parent, label, value, is_path=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2)

        if is_path:
            # Titre du chemin (ex: Output File:)
            ctk.CTkLabel(
                frame,
                text=label,
                font=("Arial", 10, "bold"),
                text_color="gray",
                anchor="w"
            ).pack(side="top", fill="x")

            # Utilisation de truncate_path pour l'affichage initial propre
            # On importe ici si ce n'est pas fait en haut du fichier
            from core.utils import truncate_path
            display_path = truncate_path(value, max_length=40)

            self.path_label = ctk.CTkLabel(
                frame,
                text=display_path,  
                font=("Consolas", 10),
                text_color="#2ecc71",  # Vert clair pour matcher avec le bouton Export
                anchor="w",
                justify="left"
            )
            self.path_label.pack(side="top", fill="x", padx=5, expand=True)

            # Tooltip pour voir le chemin complet sans troncature au survol
            from ..widgets import ToolTip
            ToolTip(self.path_label, value)

            # Application de ta logique de redimensionnement dynamique
            self.after(10, lambda: self._apply_dynamic_fonts(self.left_panel.winfo_width()))

        else:
            # Affichage standard (Clé : Valeur)
            ctk.CTkLabel(
                frame,
                text=label,
                font=("Arial", 10, "bold"),
                text_color="gray",
                anchor="w"
            ).pack(side="left")

            ctk.CTkLabel(
                frame,
                text=str(value),
                font=("Consolas", 11),
                text_color="#ecf0f1",
                anchor="e"
            ).pack(side="right", fill="x", expand=True)
  

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
        if self.points_list is None or (isinstance(self.points_list, np.ndarray) and self.points_list.size == 0):
            return

        self.framing_end_idx = self.raw_sim_data.get('framing_end_idx', 0)
        self.total_sim_seconds = self.raw_sim_data.get('total_dur', 0.0)

        # --- 2. LIMITES MACHINE ---
        raw_x = [p[0] for p in self.points_list]
        raw_y = [p[1] for p in self.points_list]

        self.min_x_machine = min(raw_x)
        self.min_y_machine = min(raw_y)
        self.total_mouvement_w = max(raw_x) - self.min_x_machine
        self.total_mouvement_h = max(raw_y) - self.min_y_machine

        # --- 3. ÉCHELLE ET DIMENSIONS ---
        # On garde une marge de 15% pour laisser la place aux chiffres de la grille
        self.scale = min(
            (c_w * 0.80) / max(1, self.total_mouvement_w),
            (c_h * 0.75) / max(1, self.total_mouvement_h)
        )

        self.total_px_w = self.total_mouvement_w * self.scale
        self.total_px_h = self.total_mouvement_h * self.scale
        self.rect_w, self.rect_h = int(self.total_px_w), int(self.total_px_h)

        # Centrage sur le canvas
        self.x0 = (c_w - self.total_px_w) / 2
        self.y0 = (c_h - self.total_px_h) / 2

        # --- 4. CRÉATION DE LA MATRICE DE TRAVAIL ---
        self.display_data = np.full((max(1, self.rect_h), max(1, self.rect_w)), 255, dtype=np.uint8)
        
        l_step = self.payload.get('dims', [0, 0, 0.1])[2]
        self.laser_width_px = max(1, int(l_step * self.scale))

        # --- 5. INITIALISATION DU CANVAS ---
        self.preview_canvas.delete("all")

        # STYLE RASTER : Pas de vis_pad sur le rectangle de fond. 
        # On dessine le rectangle blanc aux dimensions EXACTES de l'image.
        self.preview_canvas.create_rectangle(
            self.x0, 
            self.y0, 
            self.x0 + self.total_px_w, 
            self.y0 + self.total_px_h, 
            fill="white", 
            outline="#cccccc", # Gris clair pour la bordure
            width=1,
            tags="bg_rect"
        )

        # Création du conteneur d'image dans le Canvas
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(self.display_data))
        self.img_container = self.preview_canvas.create_image(
            self.x0,
            self.y0,
            anchor="nw",
            image=self.tk_img,
            tags="main_image"
        )

        # Dessin de la grille (elle utilisera x0 et y0 avec overflow)
        self.draw_grid()

        # Recalage de la pile d'affichage : L'image par dessus le rectangle, mais sous le laser
        self.preview_canvas.tag_raise("main_image", "bg_rect")

        # Création graphique du laser
        self.laser_halo = self.preview_canvas.create_oval(0, 0, 0, 0, fill="#1a75ff", outline="#3385ff", width=1, tags="laser", stipple="gray50")
        self.laser_head = self.preview_canvas.create_oval(0, 0, 0, 0, fill="#00ffff", outline="white", width=1, tags="laser")
        
        # Éléments de la loupe
        self.loupe_container = self.preview_canvas.create_image(0, 0, anchor="center", state="hidden", tags="loupe")
        self.loupe_border = self.preview_canvas.create_oval(0, 0, 0, 0, outline="#ff9f43", width=2, state="hidden", tags="loupe")

        # --- 6. ÉTAT DE SIMULATION INITIAL ---
        self.current_point_idx = 0
        self.current_sim_time = 0.0
        self.last_frame_time = 0.0 # Important pour le prochain "Play"
        
        if self.points_list is not None and self.points_list.size > 0:
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

    def _scroll_gcode(self, delta):
        """Navigue dans le G-code et synchronise la simulation proprement"""
        new_idx = max(0, min(self.current_point_idx + delta, len(self.points_list) - 1))
        
        if new_idx != self.current_point_idx:
            # 1. On arrête TOUTE animation en cours
            self.sim_running = False
            if self.animation_job:
                self.after_cancel(self.animation_job)
                self.animation_job = None
                
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
            self.current_point_idx = new_idx
            self.current_sim_time = self.points_list[new_idx][4]
            
            # 2. Un SEUL appel pour reconstruire l'image
            # Cette fonction doit contenir le fill(255) au début
            self._redraw_up_to(new_idx)
            
            # 3. Mettre à jour les éléments UI (curseurs, texte) 
            # SANS redessiner de pixels sur l'image
            self.sync_sim_to_index(new_idx)
            
            # 4. On rafraîchit l'affichage final UNE SEULE FOIS
            self.update_graphics()
            
        return "break"
    
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
        if self.points_list is None or self.points_list.size == 0:
            return

        # 1. SI MODE REJOUER
        if self.btn_play_pause.cget("text") == "🔄":
            self.rewind_sim() 
            self.sim_running = True
            self.last_frame_time = time.time()
            self.btn_play_pause.configure(text="⏸", fg_color="#e67e22")
            
            # SÉCURITÉ : On n'appelle animate_loop que si aucun job n'existe
            if self.animation_job is None:
                self.animate_loop()
            return

        # 2. LOGIQUE PLAY / PAUSE CLASSIQUE
        if self.sim_running:
            # On demande l'arrêt
            self.sim_running = False
            # On nettoie immédiatement le job planifié pour éviter qu'il ne se relance
            if self.animation_job is not None:
                self.after_cancel(self.animation_job)
                self.animation_job = None
            self.btn_play_pause.configure(text="▶", fg_color="#27ae60")
        else:
            # On lance
            self.sim_running = True
            self.last_frame_time = time.time()
            self.btn_play_pause.configure(text="⏸", fg_color="#e67e22")
            
            # SÉCURITÉ : Double vérification avant de lancer
            if self.animation_job is None:
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
        if self.points_list is not None:
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
        if self.points_list is not None:
             self.update_gcode_highlight(0)
        
        # Rafraîchissement graphique
        self.update_graphics()




    def animate_loop(self):

        # --- SORTIE SÉCURISÉE ---
        if not self.winfo_exists() or not self.sim_running:
            self.animation_job = None
            return

        if self.points_list is None or len(self.points_list) < 2:
            self.sim_running = False
            self.animation_job = None
            return

        # --- GESTION DU TEMPS ---
        now = time.time()

        if not hasattr(self, "last_frame_time") or self.last_frame_time == 0:
            self.last_frame_time = now

        dt = (now - self.last_frame_time) * self.sim_speed
        self.last_frame_time = now
        self.current_sim_time += dt

        # 1. On vérifie d'abord si on a un état figé
        if hasattr(self, "active_latence"):
            is_switch_on = self.active_latence
        # 2. Sinon on vérifie si le switch existe et on prend sa valeur
        elif self.latence_switch is not None:
            is_switch_on = self.latence_switch.get()
        # 3. Par défaut, pas de latence
        else:
            is_switch_on = False

        latence_mm = getattr(
            self,
            "latence_mm",
            float(self.payload.get('params', {}).get('offset_latence', 0))
        )

        last_index = len(self.points_list) - 1

        # --- DESSIN INCRÉMENTAL STABLE ---
        while self.current_point_idx < last_index:
            # On récupère le point suivant (index 4 = timestamp)
            next_point = self.points_list[self.current_point_idx + 1]

            # On sort si le prochain point n'est pas encore atteint temporellement
            if next_point[4] > self.current_sim_time:
                break

            p1 = self.points_list[self.current_point_idx]
            p2 = next_point

            # On ne dessine que si on a fini le framing (cadrage)
            if self.current_point_idx >= self.framing_end_idx:
                # On passe bien is_switch_on et latence_mm récupérés plus haut dans animate_loop
                # _draw_segment s'occupe de vérifier si p1 != p2 et si p2[2] > 0
                self._draw_segment(p1, p2, is_switch_on, latence_mm)

            self.current_point_idx += 1

        # --- FIN DE SIMULATION ---
        if self.current_point_idx >= last_index:
            self.sim_running = False
            self.animation_job = None
            self.btn_play_pause.configure(text="🔄")
            self.sync_sim_to_index(last_index)
            self.update_graphics()
            return

        # --- INTERPOLATION CURSEUR ---
        p_curr = self.points_list[self.current_point_idx]
        p_next = self.points_list[self.current_point_idx + 1]

        t_diff = p_next[4] - p_curr[4]

        if t_diff > 0:
            ratio = (self.current_sim_time - p_curr[4]) / t_diff
            ratio = max(0.0, min(1.0, ratio))
        else:
            ratio = 0.0

        ix = p_curr[0] + (p_next[0] - p_curr[0]) * ratio
        iy = p_curr[1] + (p_next[1] - p_curr[1]) * ratio

        self.curr_x, self.curr_y = self.machine_to_screen(ix, iy)

        self.sync_sim_to_index(self.current_point_idx)
        self.update_graphics()

        # --- PLANIFICATION PROCHAINE FRAME ---
        self.animation_job = self.after(16, self.animate_loop)


    def sync_sim_to_index(self, target_idx):
        """Met à jour l'UI, le temps et le laser pour un index donné."""
        if self.points_list is None or target_idx >= len(self.points_list):
            return

        # 1. Mise à jour des coordonnées du laser (Position RÉELLE machine)
        # On ne touche SURTOUT PAS à display_data ici
        mx, my, pwr, line_idx, ts = self.points_list[target_idx]
        self.curr_x, self.curr_y = self.machine_to_screen(mx, my)

        # 2. Progression
        total_pts = len(self.points_list)
        progress = target_idx / max(1, total_pts)
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Progress: {int(progress*100)}%")

        # 3. Calcul du temps
        self.time_label.configure(
            text=f"Time: {self._format_seconds_to_hhmmss(ts)} / {self._format_seconds_to_hhmmss(self.total_sim_seconds)}"
        )
        
        # 4. Highlight G-code (Vérifie que cette fonction n'appelle pas de dessin !)
        self.update_gcode_highlight(target_idx)

    def update_gcode_highlight(self, target_idx):
        """Met à jour la ligne surlignée dans l'éditeur G-code en fonction de l'index du point."""
        if self.points_list is None or target_idx >= len(self.points_list):
            return
        
        # On évite de mettre à jour si la simulation est en pause et qu'on ne déplace pas le curseur manuellement
        if not self.sim_running and target_idx != self.current_point_idx:
            return

        try:
            # 1. RECUPERATION ET FORCE EN ENTIER (Crucial pour NumPy)
            # pts_array[:, 3] contient les numéros de ligne G-Code
            line_number = int(self.points_list[target_idx][3])
            
            # 2. MISE EN COULEUR
            self.gcode_view.tag_remove("active", "1.0", "end")
            
            # On construit l'index "Ligne.0" proprement
            start_idx = f"{line_number}.0"
            end_idx = f"{line_number}.end"
            
            self.gcode_view.tag_add("active", start_idx, end_idx)
            self.gcode_view.tag_config("active", background="#2c3e50", foreground="#ecf0f1")

            # 3. CENTRAGE VERTICAL
            # see() rend la ligne visible, mais elle est souvent en bas ou en haut.
            self.gcode_view.see(start_idx)
            
            # Pour un centrage plus précis, on utilise yview_scroll après un see
            # Ou plus simplement, on ajuste l'index de vue :
            self.gcode_view.yview(max(0, line_number - 10)) # -10 lignes pour centrer environ
            
        except Exception as e:
            # Affiche l'erreur en console sans bloquer le thread de simulation
            print(f"GCode highlight error: {e}")

    def _on_gcode_click(self, event):
        try:
            # 1. Trouver la ligne cliquée dans le widget texte
            index = self.gcode_view.index(f"@{event.x},{event.y}")
            line_clicked = int(index.split('.')[0])

            # 2. Recherche ultra-rapide avec NumPy
            # On cherche tous les indices où la colonne 3 (numéro de ligne) 
            # correspond à la ligne cliquée.
            indices = np.where(self.points_list[:, 3].astype(int) == line_clicked)[0]

            if indices.size > 0:
                # On prend le premier point trouvé pour cette ligne G-Code
                target_idx = int(indices[0])

                # 1. On fige la simulation
                self.sim_running = False
                self.btn_play_pause.configure(text="▶", fg_color="#27ae60")

                # 2. SYNCHRONISATION TEMPORELLE
                self.current_point_idx = target_idx
                # Récupération du timestamp (colonne 4)
                self.current_sim_time = float(self.points_list[target_idx][4])

                # 3. MISE À JOUR VISUELLE
                self.sync_sim_to_index(target_idx)
                self._redraw_up_to(target_idx)
                self.update_gcode_highlight(target_idx)
                
                # Mise à jour graphique immédiate
                self.update_graphics()
                
        except Exception as e:
            print(f"GCode selection error: {e}")

    def _on_progress_click(self, event):
        """Déplace la simulation sans freezer l'UI."""
        # Sécurité NumPy
        if self.points_list is None or self.total_sim_seconds <= 0:
            return

        try:
            # 1. Calcul du ratio
            bar_width = self.progress_bar.winfo_width()
            ratio = max(0, min(event.x / bar_width, 1.0))
            
            # 2. Suspension de l'animation
            was_running = self.sim_running
            self.sim_running = False 
            if self.animation_job:
                self.after_cancel(self.animation_job)
                self.animation_job = None
            
            # 3. Calcul du nouveau point (Ultra-rapide avec NumPy)
            self.current_sim_time = float(ratio * self.total_sim_seconds)
            
            # Recherche binaire sur la colonne 4 (timestamps)
            idx = np.searchsorted(self.points_list[:, 4], self.current_sim_time)
            self.current_point_idx = int(max(0, min(idx, len(self.points_list) - 1)))
            
            # 4. Rendu et Synchronisation
            self._redraw_up_to(self.current_point_idx)
            self.sync_sim_to_index(self.current_point_idx)
            
            # AJOUT : Synchroniser le surlignage du texte G-Code
            self.update_gcode_highlight(self.current_point_idx)
            
            # 5. Reprise ou rafraîchissement
            if was_running:
                self.sim_running = True
                self.last_frame_time = time.time()
                self.animation_job = self.after(10, self.animate_loop)
            else:
                self.update_graphics()
                
        except Exception as e:
            print(f"Progress click error: {e}")


    def _recalibrate_index_from_time(self):
        """Trouve l'index du point G-Code le plus proche du temps actuel via NumPy."""
        if self.points_list is None or self.points_list.size == 0:
            return
        
        # NumPy effectue la recherche binaire directement sur la colonne 4 (timestamps)
        # C'est instantané, même avec 2 millions de points.
        found_idx = np.searchsorted(self.points_list[:, 4], self.current_sim_time)
        
        self.current_point_idx = min(found_idx, len(self.points_list) - 1)
        
        self.sync_sim_to_index(self.current_point_idx)

    def _redraw_up_to(self, target_idx):
        if self.points_list is None or len(self.points_list) < 2:
            return

        last_idx = len(self.points_list) - 1
        target_idx = min(target_idx, last_idx)

        # 1. Reset de la matrice
        self.display_data.fill(255)

        # 2. CACHE LOCAL : C'est le secret de la vitesse en Python
        # Accéder à une variable locale est bcp plus rapide qu'un attribut d'objet (self)
        points = self.points_list
        draw_func = self._draw_segment
        is_switch_on = self.latence_switch.get() if self.latence_switch is not None else False
        lat_mm = self.latence_mm
        
        # 3. Boucle resserrée au maximum
        start_scan = self.framing_end_idx
        for i in range(start_scan, target_idx):
            # On passe directement les références locales
            draw_func(points[i], points[i + 1], is_switch_on, lat_mm)

        # 4. Mise à jour UI UNIQUE
        self.update_graphics()


    def _draw_segment(self, p1, p2, is_switch_on, latence_mm):
        scan_axis = self.full_metadata.get("scan_axis", "X")
        # Sortie ultra-rapide si puissance nulle (G0)
        p2_pow = p2[2]
        if p2_pow <= 0:
            return

        # Cache des coordonnées pour éviter les indexations multiples
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]

        # Correction latence
        if is_switch_on and scan_axis =="X":
            dx_m = x2 - x1
            if dx_m > 1e-6:
                x1 += latence_mm
                x2 += latence_mm
            elif dx_m < -1e-6:
                x1 -= latence_mm
                x2 -= latence_mm
        elif is_switch_on and scan_axis =="Y":
            dy_m = y2 - y1
            if dy_m > 1e-6:
                y1 += latence_mm
                y2 += latence_mm
            elif dy_m < -1e-6:
                y1 -= latence_mm
                y2 -= latence_mm

        # Inlining de screen_index (Calcul direct sans appel de fonction)
        # Gain énorme sur 200 000 appels
        sc = self.scale
        mx = self.min_x_machine
        my = self.min_y_machine
        th = self.total_px_h

        ix1 = (x1 - mx) * sc
        iy1 = th - (y1 - my) * sc
        ix2 = (x2 - mx) * sc
        iy2 = th - (y2 - my) * sc

        dx = ix2 - ix1
        dy = iy2 - iy1
        dist_sq = dx*dx + dy*dy

        # Si le segment est trop petit pour être visible, on ignore
        if dist_sq < 0.25: # Moins de 0.5 pixel
            return

        length = dist_sq**0.5
        
        # Calcul des normales
        half_th = max(1.0, self.laser_width_px) * 0.5
        nx = (-dy / length) * half_th
        ny = (dx / length) * half_th

        # On prépare les points pour fillPoly avec SHIFT 4 (précision sub-pixel)
        # On multiplie par 16 une seule fois ici
        pts = np.array([
            [(ix1 + nx) * 16, (iy1 + ny) * 16],
            [(ix1 - nx) * 16, (iy1 - ny) * 16],
            [(ix2 - nx) * 16, (iy2 - ny) * 16],
            [(ix2 + nx) * 16, (iy2 + ny) * 16]
        ], dtype=np.int32)

        # Calcul couleur
        c = int(255 * (1.0 - (p2_pow / self.ctrl_max)))
        
        # Appel OpenCV (Passer l'entier directement au lieu d'un tuple si c'est du grayscale)
        cv2.fillPoly(self.display_data, [pts], c, lineType=cv2.LINE_8, shift=4)
        
    #     thickness = int(round(max(1.0, self.laser_width_px)))

    #     # ---------------------------------------------------
    #     # OpenCV rendering
    #     # ---------------------------------------------------
    #     cv2.line(
    #         self.display_data,
    #         (ix1, iy1),
    #         (ix2, iy2),
    #         color_tuple,
    #         thickness=thickness,
    #         lineType=cv2.LINE_AA#cv2.LINE_8
    #     )

    def skip_to_end(self):
        """Termine instantanément la simulation avec un rendu optimisé."""
        if not self.winfo_exists() or self.points_list is None:
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

        except Exception as e:
            print(f"Erreur update_graphics: {e}")



    def update_laser_ui(self):
        if not hasattr(self, 'laser_head') or self.laser_head is None:
            return

        lx, ly = self.curr_x, self.curr_y
        laser_state = "normal"

        # LOGIQUE D'ÉVITEMENT DE LA LOUPE
        if self.loupe_active and hasattr(self, 'last_mouse_coords'):
            mx, my = self.last_mouse_coords
            distance = ((lx - mx)**2 + (ly - my)**2)**0.5
            if distance < (self.loupe_size / 2):
                laser_state = "hidden"



        r_halo = 3         # r_halo : rayon du halo 
        r_head = 6         # r_head : rayon du point central 

        # Mise à jour positions et visibilité
        if hasattr(self, 'laser_halo'):
            # On remplace 6 par r_halo
            self.preview_canvas.coords(self.laser_halo, lx - r_halo, ly - r_halo, lx + r_halo, ly + r_halo)
            self.preview_canvas.itemconfig(self.laser_halo, state=laser_state)

        # On remplace 3 par r_head
        self.preview_canvas.coords(self.laser_head, lx - r_head, ly - r_head, lx + r_head, ly + r_head)
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
        self.preview_canvas.delete("grid")
        step = 10 # mm
        
        # On boucle sur les multiples de 10 entre le min et le max REELS du Parser
        start_x = int(np.ceil(self.min_x_machine / step) * step)
        for mx in range(start_x, int(self.max_x_machine) + 1, step):
            sx, _ = self.machine_to_screen(mx, self.min_y_machine)
            
            self.preview_canvas.create_line(sx, self.y0, sx, self.y0 + self.total_px_h, fill="#e0e0e0", dash=(2,4), tags="grid")
            # Ici on affiche 'mx' : si le G-Code passe par 0, le 0 s'affichera au bon endroit
            self.preview_canvas.create_text(sx, self.y0 + self.total_px_h + 15, text=str(mx), fill="#888888", tags="grid")

        # Idem pour Y
        start_y = int(np.ceil(self.min_y_machine / step) * step)
        for my in range(start_y, int(self.max_y_machine) + 1, step):
            _, sy = self.machine_to_screen(self.min_x_machine, my)
            
            self.preview_canvas.create_line(self.x0, sy, self.x0 + self.total_px_w, sy, fill="#e0e0e0", dash=(2,4), tags="grid")
            self.preview_canvas.create_text(self.x0 - 25, sy, text=str(my), fill="#888888", tags="grid")



    def machine_to_screen(self, mx, my):
        """
        mx, my : Coordonnées brutes lues dans le G-Code.
        """
        # 1. On calcule la distance du point par rapport au bord minimum trouvé par le parser
        # Si le G-Code va de -50 à +50 (Center), min_x est -50.
        # Pour mx = -50 (bord gauche), dist_x = 0.
        # Pour mx = 0 (centre), dist_x = 50.
        dist_x = mx - self.min_x_machine
        dist_y = my - self.min_y_machine

        # 2. Conversion en pixels
        sx = self.x0 + (dist_x * self.scale)
        # 3. Inversion Y Tkinter (On part du bas du rectangle blanc et on remonte)
        sy = (self.y0 + self.total_px_h) - (dist_y * self.scale)

        return sx, sy


    def screen_index(self, mx, my):
        """mm machine -> pixels relatifs à la matrice display_data."""
        # On calcule la position par rapport au coin minimum du mouvement (incluant premove)
        px = (mx - self.min_x_machine) * self.scale
        py = (my - self.min_y_machine) * self.scale

        # Inversion Y pour la matrice Image (le 0 est en haut en mémoire)
        # On part du haut (rect_h) et on descend
        iy = self.rect_h - int(round(py))
        ix = int(round(px))
    
        return ix, iy
    


    def on_export(self):
        """EXPORT RAPIDE : Utilise le chemin par défaut sans ouvrir de fenêtre."""
        self.stop_processes()
        
        # Récupération des données du payload
        meta = self.payload.get('metadata', {})
        output_dir = meta.get('output_dir', '')
        pref_ext = self.controller.config_manager.get_item("machine_settings", "gcode_extension", ".nc")
        
        # Sécurisation du nom de fichier (on enlève l'extension proprement)
        raw_file = meta.get('file_name', 'output')
        clean_name = os.path.splitext(os.path.basename(str(raw_file)))[0]
        
        # Assemblage et normalisation forcée vers des slashs /
        full_path = os.path.join(output_dir, f"{clean_name}{pref_ext}").replace("\\", "/")
        
        self._execute_save(full_path)

    def on_export_as(self):
        """EXPORT VERS : Ouvre une fenêtre avec gestion intelligente des doublons d'extension."""
        self.stop_processes()
        self.update_idletasks() 
        
        meta = self.payload.get('metadata', {})
        pref_ext = meta.get('file_extension', '.nc').lower()
        if not pref_ext.startswith("."):
            pref_ext = f".{pref_ext}"
            
        raw_name = meta.get('file_name', 'output')
        clean_name = os.path.splitext(os.path.basename(str(raw_name)))[0]

        # 1. Liste des formats standards connus
        standards = [
            (".nc", "NC File"),
            (".gcode", "G-Code File"),
            (".gc", "GC File"),
            (".tap", "Tap File"),
            (".txt", "Text File")
        ]

        # 2. Construction dynamique de la liste
        file_types = []
        
        # On vérifie si notre extension préférée est dans les standards
        is_standard = any(ext == pref_ext for ext, label in standards)

        if is_standard:
            # Si c'est un standard, on réorganise pour mettre le standard correspondant en premier
            # On cherche le label associé pour l'afficher proprement
            current_label = next(label for ext, label in standards if ext == pref_ext)
            file_types.append((f"{current_label} (Default)", f"*{pref_ext}"))
            
            # On ajoute les autres standards (sans celui qu'on vient de mettre)
            for ext, label in standards:
                if ext != pref_ext:
                    file_types.append((label, f"*{ext}"))
        else:
            # Si l'extension est exotique/inconnue, on ajoute la ligne "Default format"
            file_types.append(("Default format", f"*{pref_ext}"))
            # Et on ajoute toute la liste des standards ensuite
            for ext, label in standards:
                file_types.append((label, f"*{ext}"))

        # On finit toujours par "All files"
        file_types.append(("All files", "*.*"))

        # 3. Ouverture du dialogue
        full_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export G-Code As...",
            initialdir=meta.get('output_dir', ''),
            initialfile=f"{clean_name}{pref_ext}",
            defaultextension=pref_ext,
            filetypes=file_types
        )

        if full_path:
            full_path = full_path.replace("\\", "/")
            self._execute_save(full_path)


    def _execute_save(self, full_path):
        """Logique interne finale pour écrire le fichier et mettre à jour le dashboard."""
        try:
            if hasattr(self, 'final_gcode') and self.final_gcode:
                # --- A. Sauvegarde physique du fichier ---
                with open(full_path, "w") as f:
                    f.write(self.final_gcode)

                # --- B. Enregistrement dans le Dashboard ---
                matrix = self.payload.get('matrix') 
                if matrix is not None:
                    from core.utils import save_dashboard_data
                    save_dashboard_data(
                        config_manager=self.controller.config_manager,
                        matrix=matrix,
                        gcode_content=self.final_gcode,
                        estimated_time=getattr(self, 'total_sim_seconds', 0)
                    )

                messagebox.showinfo("Success", f"G-Code saved to:\n{full_path}", parent=self.controller)
                self._navigate_back()
            else:
                messagebox.showerror("Error", "No G-Code data to save.", parent=self.controller)
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}", parent=self.controller)

    def toggle_latency_sim(self):
        """Bascule la correction et nettoie l'affichage immédiatement."""
        if self.latence_switch is None:
            return
        # On redessine tout : _redraw_up_to fait déjà le fill(255)
        # ce qui élimine les pixels "sans latence" accumulés.
        self._redraw_up_to(self.current_point_idx)
        
        # On force la mise à jour de l'image sur le canvas
        self.update_graphics()

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