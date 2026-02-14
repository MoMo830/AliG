
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


class SimulationWindow(ctk.CTkToplevel):
    def __init__(self, parent, stats, matrix, premove_val=0, framing_data=None):
        super().__init__(parent)
        if hasattr(parent, 'icon_path') and os.path.exists(parent.icon_path):
            try:
                # Le délai de 200ms est crucial pour CTkToplevel
                self.after(200, lambda: self.iconbitmap(parent.icon_path))
            except Exception as e:
                print(f"Erreur icône SimulationWindow : {e}")
        # 1. Stockage des données reçues
        self.stats = stats  # Contient maintenant : offX, offY, pixel_size, min_power, etc.
        self.matrix = matrix 
        self.premove = premove_val
        self.confirmed = False
        self.framing_gcode = framing_data
        
        # --- FIX : Utilisation des nouvelles clés propres ---
        self.framing_info = {
            "active": stats.get("is_framing", False),
            "pointing": stats.get("is_pointing", False)
        }

        # 2. États de simulation
        self.sim_running = False
        self.animation_job = None
        self.points_list = [] 
        self.current_point_idx = 0
        # Paramètres de la loupe
        self.loupe_size = 300
        self.loupe_zoom = 3    
        self.loupe_active = True
        
        # --- NOUVEAUX PARAMÈTRES DE FLUIDITÉ ---
        self.last_frame_time = 0.0      # On l'initialise à 0
        self.accumulated_index = 0.0    # C'est notre curseur flottant
        self.sim_speed = 1.0  
        self.pts_per_sec = 60.0
        
        # On garde l'estimation brute, elle sera écrasée dans draw_simulation
        self.total_sim_seconds = float(stats.get("est_sec", 0))

        # 3. Configuration UI
        self.title("Simulation")
        self._setup_window(parent)
        
        self.grid_columnconfigure(0, weight=0, minsize=200) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)

        # 4. Construction des panneaux (Utilisera les nouvelles clés)
        self._build_left_panel(stats)
        self._build_right_panel()

        # 5. Lancement du dessin
        self.after(100, lambda: self.draw_simulation(stats))

    def _setup_window(self, parent):
        try:
            if hasattr(parent, 'icon_path') and os.path.exists(parent.icon_path):
                self.iconbitmap(parent.icon_path)
        except: pass
        
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        width, height = int(parent_w * 0.95), int(parent_h * 0.95)
        x = parent_x + (parent_w - width) // 2
        y = parent_y + (parent_h - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(800, 500) 
        self.attributes("-topmost", True)

    def _build_left_panel(self, stats):
        self.left_panel = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.left_panel.grid_propagate(False) 
        
        ctk.CTkLabel(self.left_panel, text="PATH SIMULATION", font=("Arial", 14, "bold")).pack(pady=15)
        
        # 1. Stats Scrollable
        info_scroll = ctk.CTkScrollableFrame(self.left_panel, fg_color="transparent")
        info_scroll.pack(fill="both", expand=True, padx=5)
        
        excluded = [
            "offX", "offY", "pixel_size", "min_power", "max_power", 
            "is_pointing", "is_framing", "file_name", "est_sec",
            "pixel_size_x", "pixel_size_y"
        ]
        
        for label, val in stats.items():
            if label not in excluded:
                row = ctk.CTkFrame(info_scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                clean_label = label.replace("_", " ").capitalize()
                ctk.CTkLabel(row, text=clean_label, font=("Arial", 10, "bold"), width=80, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=str(val), font=("Arial", 10), anchor="e", wraplength=100).pack(side="right", fill="x", expand=True)

        # Temps formaté
        t_sec = stats.get("est_sec", 0)
        time_str = f"{int(t_sec // 60)}:{int(t_sec % 60):02d}"

        time_frame = ctk.CTkFrame(info_scroll, fg_color="transparent")
        time_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(time_frame, text="Estimated Time:", font=("Arial", 10, "bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(time_frame, text=time_str, font=("Arial", 10), anchor="e").pack(side="right", fill="x", expand=True)

        # Échelle de Puissance
        p_min, p_max = float(stats.get("min_power", 0)), float(stats.get("max_power", 100))
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
        ctk.CTkLabel(fname_frame, text=stats.get("file_name", "N/A"), font=("Arial", 10), anchor="e", wraplength=120).pack(side="right", fill="x", expand=True)

        # Groupe OPTIONS (Badges)
        self.options_group_frame = ctk.CTkFrame(self.left_panel, fg_color="#222222", border_width=1, border_color="#444444")
        self.options_group_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(self.options_group_frame, text="Active Options", font=("Arial", 11, "bold")).pack(pady=(8, 2))
        badge_cont = ctk.CTkFrame(self.options_group_frame, fg_color="transparent")
        badge_cont.pack(fill="x", padx=10, pady=(0, 10))
        
        for key, text in [("is_pointing", "POINTING"), ("is_framing", "FRAMING")]:
            active = stats.get(key, False)
            color, bg = ("#ff9f43", "#3d2b1f") if active else ("#666666", "#282828")
            ctk.CTkLabel(badge_cont, text=text, font=("Arial", 9, "bold"), text_color=color, fg_color=bg, corner_radius=5).pack(side="left", expand=True, fill="x", padx=2)

        # Actions (Générer / Annuler)
        btn_act = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_act.pack(fill="x", side="bottom", pady=15)
        ctk.CTkButton(btn_act, text="GENERATE GCODE", fg_color="#27ae60", height=40, font=("Arial", 11, "bold"), command=self.on_confirm).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_act, text="CANCEL", fg_color="#333", height=30, command=self.on_cancel).pack(fill="x", padx=10, pady=5)
    
    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, fg_color="#111", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        
        # 1. Canvas de prévisualisation
        self.preview_canvas = ctk.CTkCanvas(self.right_panel, bg="#050505", highlightthickness=0)
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
        self.loupe_container = self.preview_canvas.create_image(0, 0, anchor="center", state="hidden")
        # Un petit cercle de bordure pour la finition
        self.loupe_border = self.preview_canvas.create_oval(0, 0, 0, 0, outline="#ff9f43", width=2, state="hidden")

        # Bind du mouvement de souris
        self.preview_canvas.bind("<ButtonPress-1>", self._on_click_loupe)   # Quand on clique
        self.preview_canvas.bind("<B1-Motion>", self._update_loupe)        # Quand on bouge en restant cliqué
        self.preview_canvas.bind("<ButtonRelease-1>", lambda e: self._hide_loupe()) # Quand on lâche


    def _on_click_loupe(self, event):
        self.loupe_active = True
        self._update_loupe(event)

    def _update_loupe(self, event):
        # Sécurités : image existante et loupe autorisée
        if not hasattr(self, 'display_data') or self.display_data is None:
            return
        if not self.loupe_active: 
            return

        # Coordonnées relatives à l'image (0,0 est le coin haut-gauche de l'image)
        ix = event.x - self.x0
        iy = event.y - self.y0

        # Si on est bien sur l'image
        if 0 <= ix < self.rect_w and 0 <= iy < self.rect_h:
            r = (self.loupe_size / 2) / self.loupe_zoom
            
            # Capture de la zone actuelle de simulation
            img_obj = Image.fromarray(self.display_data)
            
            # Découpe (Crop) avec protection des bords
            left = max(0, int(ix - r))
            top = max(0, int(iy - r))
            right = min(self.rect_w, int(ix + r))
            bottom = min(self.rect_h, int(iy + r))

            crop = img_obj.crop((left, top, right, bottom))

            zoom_img = crop.resize((self.loupe_size, self.loupe_size), Image.NEAREST)
            
            # --- Création masque circulaire ---
            mask = Image.new("L", (self.loupe_size, self.loupe_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, self.loupe_size, self.loupe_size), fill=255)

            # --- Zoom en RGBA ---
            zoom_img = zoom_img.convert("RGBA")

            # --- Image finale transparente ---
            final_img = Image.new("RGBA", (self.loupe_size, self.loupe_size), (0, 0, 0, 0))

            # --- Collage avec masque (transparence réelle) ---
            final_img.paste(zoom_img, (0, 0), mask)

            self.tk_loupe = ImageTk.PhotoImage(final_img)

            
            # Mise à jour de l'image (référence self.tk_loupe obligatoire)
            self.preview_canvas.itemconfig(self.loupe_container, image=self.tk_loupe, state="normal")
            self.preview_canvas.coords(self.loupe_container, event.x, event.y)
            
            # Mise à jour du cercle de bordure
            self.preview_canvas.itemconfig(self.loupe_border, state="normal")
            self.preview_canvas.coords(self.loupe_border, 
                                    event.x - self.loupe_size/2, event.y - self.loupe_size/2,
                                    event.x + self.loupe_size/2, event.y + self.loupe_size/2)
            
            # --- ORDRE D'AFFICHAGE (Z-INDEX) ---
            self.preview_canvas.tag_raise(self.loupe_container)
            self.preview_canvas.tag_raise(self.loupe_border)
            
            # Le laser doit rester visible même par-dessus la loupe
            if hasattr(self, 'laser_head'):
                self.preview_canvas.tag_raise(self.laser_halo)
                self.preview_canvas.tag_raise(self.laser_head)
        else:
            self._hide_loupe()

    def _hide_loupe(self):
        self.loupe_active = False # On désactive l'état
        self.preview_canvas.itemconfig(self.loupe_container, state="hidden")
        self.preview_canvas.itemconfig(self.loupe_border, state="hidden")

    def _apply_icon(self, parent):
        try:
            # On essaie d'abord de copier celle du parent, sinon on cherche le fichier
            if hasattr(parent, 'icon_path') and os.path.exists(parent.icon_path):
                self.iconbitmap(parent.icon_path)
            else:
                # Logique de secours si parent.icon_path n'est pas accessible
                if getattr(sys, 'frozen', False):
                    path = os.path.join(sys._MEIPASS, "icone_alig.ico")
                else:
                    path = os.path.join(os.path.dirname(__file__), "icone_alig.ico")
                
                if os.path.exists(path):
                    self.iconbitmap(path)
        except:
            pass # Évite de crash si l'icône est verrouillée

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


    def get_framing_points_count(self):
        """Compte les points réels dans le bloc de G-Code fourni."""
        if not self.framing_gcode: 
            return 0
        # On compte les lignes contenant un mouvement
        lines = self.framing_gcode.split('\n')
        return sum(1 for line in lines if "X" in line and "Y" in line)

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
        
        self.display_data.fill(255)
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.time_label.configure(text=f"Time: 00:00:00 / {self._format_seconds_to_hhmmss(self.total_sim_seconds)}")
        
        if self.points_list:
            self.curr_x, self.curr_y, _ = self.points_list[0]
        self.update_graphics()
        self.btn_play_pause.configure(text="▶", fg_color="#27ae60")

    def animate_loop(self):
        if not self.sim_running or self.current_point_idx >= len(self.points_list):
            if self.current_point_idx >= len(self.points_list):
                self.skip_to_end()
            return

        now = time.time()
        dt = now - self.last_frame_time
        self.last_frame_time = now

        # --- DÉTERMINATION DE LA PHASE ---
        is_framing = self.current_point_idx < self.framing_end_idx
        
        if is_framing:
            pps = self.pts_per_sec_framing
            current_sim_sec = self.current_point_idx / max(1, pps)
        else:
            pps = self.pts_per_sec_image
            img_idx = self.current_point_idx - self.framing_end_idx
            current_sim_sec = self.framing_duration + (img_idx / max(1, pps))

        step = dt * pps * self.sim_speed
        self.accumulated_index += step
        target_idx = min(int(self.accumulated_index), len(self.points_list) - 1)

        if target_idx >= self.current_point_idx:
            batch = self.points_list[self.current_point_idx : target_idx + 1]
            for tx, ty, pwr in batch:
                # Clamping de sécurité pour les bordures
                idx_x = min(max(0, int(tx)), self.rect_w - 1)
                idx_y = min(max(0, int(ty)), self.rect_h - 1)
                
                if is_framing:
                    # Phase framing : on dessine tout et on verrouille dans le masque
                    self.display_data[idx_y, idx_x] = pwr
                    if pwr < 250: # Si c'est un trait noir (pas un saut G0)
                        self.frame_mask[idx_y, idx_x] = True
                else:
                    # Phase image : ON N'ÉCRIT QUE SI LE MASQUE EST FALSE
                    if not self.frame_mask[idx_y, idx_x]:
                        self.display_data[idx_y, idx_x] = pwr
                
                self.curr_x, self.curr_y = tx, ty
            
            self.current_point_idx = target_idx + 1

        # MISE À JOUR UI
        progress = self.current_point_idx / max(1, len(self.points_list))
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Progress: {int(progress*100)}%")
        
        t_now = self._format_seconds_to_hhmmss(current_sim_sec)
        t_total = self._format_seconds_to_hhmmss(self.total_sim_seconds)
        self.time_label.configure(text=f"Time: {t_now} / {t_total}")

        self.update_graphics()
        self.animation_job = self.after(16, self.animate_loop)

    def skip_to_end(self):
        self.sim_running = False
        if self.animation_job: self.after_cancel(self.animation_job)
        self.animation_job = None
        self.display_data = self.full_data.copy()
        self.current_point_idx = len(self.points_list)
        
        t_str = self._format_seconds_to_hhmmss(self.total_sim_seconds)
        self.time_label.configure(text=f"Time: {t_str} / {t_str}")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="Progress: 100%")
        
        if self.points_list:
            self.curr_x, self.curr_y, _ = self.points_list[-1]
        self.update_graphics()
        self.btn_play_pause.configure(text="▶", fg_color="#27ae60")

    def update_graphics(self):
        if self.img_container is None: return
        try:
            self.tk_img = ImageTk.PhotoImage(Image.fromarray(self.display_data))
            self.preview_canvas.itemconfig(self.img_container, image=self.tk_img)
            self.update_laser_ui()
        except: pass

    def update_laser_ui(self):
        if self.laser_head is None: return
        lx, ly = self.x0 + self.curr_x, self.y0 + self.curr_y
        if hasattr(self, 'laser_halo'):
            self.preview_canvas.coords(self.laser_halo, lx-6, ly-6, lx+6, ly+6)
        self.preview_canvas.coords(self.laser_head, lx-3, ly-3, lx+3, ly+3)

    # --- HELPERS ---

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

    def _generate_image_only_points(self, scale):
        p = []
        OFF = 255 
        
        # Pour aller de BAS en HAUT : de (rect_h - 1) vers 0
        for y in range(self.rect_h - 1, -1, -1):
            # Bi-directionnel : 
            # Si on veut que la première ligne du bas aille de G à D :
            rev = (self.rect_h - 1 - y) % 2 != 0
            rng = range(self.rect_w - 1, -1, -1) if rev else range(self.rect_w)
            
            # --- Premove AVANT ---
            if not rev:
                for x in range(-self.pre_px, 0): p.append((float(x), float(y), OFF))
            else:
                for x in range(self.rect_w + self.pre_px, self.rect_w - 1, -1): p.append((float(x), float(y), OFF))
            
            # --- IMAGE ---
            for x in rng:
                # Protection des index
                safe_y = max(0, min(int(y), self.full_data.shape[0]-1))
                safe_x = max(0, min(int(x), self.full_data.shape[1]-1))
                p.append((float(x), float(y), self.full_data[safe_y, safe_x]))
            
            # --- Premove APRÈS ---
            if not rev:
                for x in range(self.rect_w, self.rect_w + self.pre_px): p.append((float(x), float(y), OFF))
            else:
                for x in range(-1, -self.pre_px - 1, -1): p.append((float(x), float(y), OFF))
                    
        return p

    def draw_simulation(self, stats):
        try:
            # 1. RÉCUPÉRATION DES DIMENSIONS
            w_mm = stats.get("real_w", 100)
            h_mm = stats.get("real_h", 100)
            total_w_mm = w_mm + (self.premove * 2)
            
            c_w = self.preview_canvas.winfo_width()
            c_h = self.preview_canvas.winfo_height()
            
            # 2. CALCUL DU SCALE ET OFFSET
            scale = min((c_w * 0.85) / total_w_mm, (c_h * 0.8) / h_mm)
            self.rect_w, self.rect_h = int(w_mm * scale), int(h_mm * scale)
            self.pre_px = int(self.premove * scale)
            self.x0 = int((c_w - (self.rect_w + 2*self.pre_px)) / 2 + self.pre_px)
            self.y0 = int((c_h - self.rect_h) / 2)

            # 3. MATRICE DE RENDU ET MASQUE DE PROTECTION
            p_min = float(stats.get("min_power", 0))
            p_max = float(stats.get("max_power", 100))
            render = np.clip((self.matrix - p_min) / max(1, p_max - p_min) * 255, 0, 255).astype('uint8')
            
            self.full_data = np.array(Image.fromarray(255 - render).resize((self.rect_w, self.rect_h), Image.NEAREST))
            self.display_data = np.full((self.rect_h, self.rect_w), 255, dtype=np.uint8)
            
            # --- INITIALISATION DU MASQUE ---
            # False = pixel libre, True = pixel du cadre protégé
            self.frame_mask = np.zeros((self.rect_h, self.rect_w), dtype=bool)
            
            # 4. GÉNÉRATION DES POINTS (HYBRIDE)
            f_points, f_dur = self._parse_framing_gcode(scale)
            img_points = self._generate_image_only_points(scale)
            
            self.points_list = f_points + img_points
            self.framing_end_idx = len(f_points)
            self.framing_duration = f_dur
            
            # --- CALCUL DES TEMPS ET DÉBITS ---
            img_est_sec = float(stats.get("est_sec", 0))
            self.total_sim_seconds = f_dur + img_est_sec
            
            self.pts_per_sec_framing = len(f_points) / max(0.1, f_dur)
            self.pts_per_sec_image = len(img_points) / max(0.1, img_est_sec)

            # 5. DESSIN DU CANVAS
            self.preview_canvas.delete("all")
            # --- RECRÉATION DE LA LOUPE ---
            self.loupe_container = self.preview_canvas.create_image(
                0, 0, anchor="center", state="hidden"
            )

            self.loupe_border = self.preview_canvas.create_oval(
                0, 0, 0, 0,
                outline="#00e0ff",
                width=3,
                state="hidden"
            )

            self.preview_canvas.create_rectangle(
                self.x0 - self.pre_px, self.y0, 
                self.x0 + self.rect_w + self.pre_px, self.y0 + self.rect_h, 
                fill="white", outline=""
            )
            self.tk_img = ImageTk.PhotoImage(Image.fromarray(self.display_data))
            self.img_container = self.preview_canvas.create_image(self.x0, self.y0, anchor="nw", image=self.tk_img)
            self.draw_grid(total_w_mm, h_mm, scale, stats.get("offX", 0) - self.premove, stats.get("offY", 0))

            self.laser_halo = self.preview_canvas.create_oval(0, 0, 0, 0, fill="#1a75ff", outline="#3385ff", width=1)
            self.laser_head = self.preview_canvas.create_oval(0, 0, 0, 0, fill="#00ffff", outline="white", width=1)

            self.rewind_sim()
            
        except Exception as e:
            print(f"Error in draw_simulation: {e}")

    def _parse_framing_gcode(self, scale):
        if not self.framing_gcode:
            return [], 0.0
            
        points = []
        framing_duration = 0.0
        offX = self.stats.get("offX", 0)
        offY = self.stats.get("offY", 0)
        ps_y = self.stats.get("pixel_size_y", 0.1)
        min_pwr = self.stats.get("min_power", 0) 
        img_h_mm = self.matrix.shape[0] * ps_y
        
        is_framing_block = False
        curr_x, curr_y = None, None 
        current_f = 1000.0   
        current_pwr = 0.0    
        
        for line in self.framing_gcode.split('\n'):
            line_u = line.strip().upper()
            if not line_u or line_u.startswith(';'): continue
            
            if "( --- FRAMING START --- )" in line_u:
                is_framing_block = True
                continue
            if "( --- FRAMING END --- )" in line_u:
                is_framing_block = False
                continue
            if not is_framing_block: continue

            match_f = re.search(r'F(\d+)', line_u)
            if match_f: current_f = float(match_f.group(1))
            match_p = re.search(r'[SQ]([-+]?\d*\.\d+|\d+)', line_u)
            if match_p: current_pwr = float(match_p.group(1))

            mx = re.search(r'X([-+]?\d*\.\d+|\d+)', line_u)
            my = re.search(r'Y([-+]?\d*\.\d+|\d+)', line_u)

            if mx or my:
                target_x_mm = float(mx.group(1)) if mx else curr_x
                target_y_mm = float(my.group(1)) if my else curr_y
                
                if curr_x is None:
                    curr_x, curr_y = target_x_mm, target_y_mm
                    continue

                s_px = (curr_x - offX) * scale
                t_px = (target_x_mm - offX) * scale
                s_py = self.rect_h - ((curr_y - offY) * scale)
                t_py = self.rect_h - ((target_y_mm - offY) * scale)
                
                color = 0 if current_pwr > min_pwr else 255
                dist = np.hypot(target_x_mm - curr_x, target_y_mm - curr_y)
                
                if dist > 0.001:
                    duration_sec = dist / (current_f / 60.0)
                    framing_duration += duration_sec
                    num_steps = max(2, int(duration_sec * 60)) 
                    
                    for i in range(1, num_steps): 
                        ratio = i / num_steps
                        points.append((s_px + (t_px - s_px) * ratio, s_py + (t_py - s_py) * ratio, color))
                
                # --- SÉCURITÉ : On force le point final du segment ---
                points.append((t_px, t_py, color))
                curr_x, curr_y = target_x_mm, target_y_mm
                    
        return points, framing_duration

    def draw_grid(self, tw, th, sc, sx, sy):
        col, txt_col, dash = "#d1d1d1", "#888888", (2, 4)
        gx0 = self.x0 - self.pre_px
        for vx in range(int(sx//10)*10, int((sx+tw)//10)*10+10, 10):
            x = gx0 + (vx-sx)*sc
            if gx0-1 <= x <= gx0+(tw*sc)+1:
                self.preview_canvas.create_line(x, self.y0, x, self.y0+self.rect_h, fill=col, dash=dash, tags="grid")
                self.preview_canvas.create_text(x, self.y0+self.rect_h+15, text=str(vx), fill=txt_col, font=("Arial", 8), tags="grid")
        for vy in range(int(sy//10)*10, int((sy+th)//10)*10+10, 10):
            y = (self.y0+self.rect_h) - (vy-sy)*sc
            if self.y0-1 <= y <= self.y0+self.rect_h+1:
                self.preview_canvas.create_line(gx0, y, gx0+(tw*sc), y, fill=col, dash=dash, tags="grid")
                self.preview_canvas.create_text(gx0-25, y, text=str(vy), fill=txt_col, font=("Arial", 8), tags="grid")
        self.preview_canvas.tag_raise("grid")

    def estimate_file_size(self, matrix):
        if matrix is None: return "0 KB"
        h, w = matrix.shape
        use_s = self.stats.get("use_s_mode", False)
        b_per_l = 22 if use_s else 28
        n_lines = 15 + (h * 2) # Header + G0/S0 par ligne
        for y in range(h):
            n_lines += np.count_nonzero(np.abs(np.diff(matrix[y])) > 0.01) + 1
        size = (n_lines * b_per_l) + 1024
        return f"{size/1024:.0f} KB" if size < 1048576 else f"{size/1048576:.2f} MB"

    def on_confirm(self):
        self.sim_running = False
        if self.animation_job: self.after_cancel(self.animation_job)
        self.confirmed = True
        self.destroy()

    def on_cancel(self):
        self.sim_running = False
        if self.animation_job: self.after_cancel(self.animation_job)
        self.confirmed = False
        self.destroy()