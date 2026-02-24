"""
A.L.I.G. Project - Core Engine
Industrial Raster Engine Version
"""
# TO DO : improve file siez estimation
import numpy as np
from PIL import Image
import io


class GCodeEngine:

    def __init__(self):
        self.matrix = None
        self.stats = {}
        self.last_gcode_body = []

    # =========================================================
    # IMAGE PROCESSING PIPELINE (Industrial Stable Raster Core)
    # =========================================================

    def process_image_logic(self, image_path, s, source_img_cache=None):
        """
        Traite l'image et calcule toute la géométrie.
        Force EXACTEMENT la dimension choisie par l'utilisateur.
        """

        # -------------------------------------------------
        # 1) PARAMÈTRES SÉCURISÉS
        # -------------------------------------------------
        l_step_val = max(0.0001, float(s.get("line_step", 0.1)))
        dpi_val = max(1, int(s.get("dpi", 254)))
        
        # Pas théorique basé sur le DPI
        theoretical_scan_step = 25.4 / dpi_val
        
        raster_mode = str(s.get("raster_mode", "horizontal")).strip().lower()
        feedrate = max(1.0, float(s.get("feedrate", 3000)))
        force_dim = s.get("force_dim", False)
        target_dim = float(s.get("ui_dimension", 10.0))

        # -------------------------------------------------
        # 2) CHARGEMENT IMAGE
        # -------------------------------------------------
        try:
            img = source_img_cache if source_img_cache else Image.open(image_path).convert("L")
        except Exception as e:
            print(f"Erreur chargement image: {e}")
            return None, None, None, False

        orig_w, orig_h = img.size
        img_ratio = orig_h / orig_w if orig_w != 0 else 1.0

        # -------------------------------------------------
        # 3) CALCUL GÉOMÉTRIE (FORCE EXACT DIMENSION)
        # -------------------------------------------------
        if raster_mode == "horizontal":
            # 1. Calcul du nombre de pixels pour la largeur
            w_px = max(2, int(round(target_dim / theoretical_scan_step)) + 1)
            
            # 2. Détermination du scan_step (ajusté si force_dim)
            if force_dim:
                scan_step = target_dim / (w_px - 1)
                real_w = target_dim
            else:
                scan_step = theoretical_scan_step
                real_w = (w_px - 1) * scan_step

            # 3. La hauteur reste dictée par le ratio et le line_step
            real_h = real_w * img_ratio
            h_px = max(2, int(round(real_h / l_step_val)) + 1)
            real_h = (h_px - 1) * l_step_val
            
        else:  # Mode Vertical
            # 1. Calcul du nombre de pixels pour la hauteur
            h_px = max(2, int(round(target_dim / theoretical_scan_step)) + 1)
            
            # 2. Détermination du scan_step (ajusté si force_dim)
            if force_dim:
                scan_step = target_dim / (h_px - 1)
                real_h = target_dim
            else:
                scan_step = theoretical_scan_step
                real_h = (h_px - 1) * scan_step

            # 3. La largeur reste dictée par le ratio et le line_step
            real_w = real_h / img_ratio if img_ratio != 0 else real_h
            w_px = max(2, int(round(real_w / l_step_val)) + 1)
            real_w = (w_px - 1) * l_step_val

        # -------------------------------------------------
        # 4) LIMITE MÉMOIRE (10MP) - RECALCUL SÉCURISÉ
        # -------------------------------------------------
        MAX_TOTAL_PIXELS = 10_000_000
        current_pixels = w_px * h_px
        mem_warn = current_pixels > 2_000_000

        if current_pixels > MAX_TOTAL_PIXELS:
            scale = np.sqrt(MAX_TOTAL_PIXELS / current_pixels)
            w_px = max(2, int(w_px * scale))
            h_px = max(2, int(h_px * scale))

            # Mise à jour des dimensions réelles avec le scan_step calculé au point 3
            if raster_mode == "horizontal":
                real_w = (w_px - 1) * scan_step
                real_h = (h_px - 1) * l_step_val
            else:
                real_w = (w_px - 1) * l_step_val
                real_h = (h_px - 1) * scan_step



        # -------------------------------------------------
        # 5) REDIMENSIONNEMENT IMAGE
        # -------------------------------------------------
        img_resized = img.resize((w_px, h_px), Image.Resampling.BICUBIC)
        arr = np.asarray(img_resized, dtype=np.float32) / 255.0

        # Inversion laser
        if not s.get("invert"):
            arr = 1.0 - arr

        # Contraste
        contrast = float(s.get("contrast", 0))
        if contrast != 0:
            f = (259 * (contrast + 1.0)) / (255 * (259 - contrast)) * 255
            arr = np.clip((arr - 0.5) * f + 0.5, 0, 1)

        # Gamma + thermique
        gamma = float(s.get("gamma", 1.0))
        thermal = float(s.get("thermal", 1.0))
        combined_exp = gamma * thermal
        if combined_exp != 1.0:
            arr = np.power(arr, combined_exp)

        # -------------------------------------------------
        # 6) QUANTIFICATION
        # -------------------------------------------------
        QUANT_LEVEL = max(2, int(s.get("gray_steps", 255)))
        min_p = float(s.get("min_p", 0))
        max_p = float(s.get("max_p", 255))

        norm = np.clip(arr, 0, 1)
        quant = np.round(norm * (QUANT_LEVEL - 1)) / (QUANT_LEVEL - 1)
        matrix = min_p + quant * (max_p - min_p)

        matrix *= (arr >= 0.005).astype(np.float32)

        # -------------------------------------------------
        # 7) OVERSCAN + RECTANGLES
        # -------------------------------------------------
        overscan_dist = float(s.get("premove", 2.0))

        if raster_mode == "horizontal":
            num_lines = h_px
            dist_per_line = real_w + (2 * overscan_dist)
            rect_full = (-overscan_dist, 0, real_w + overscan_dist, real_h)
            x_step = scan_step
            y_step = l_step_val
        else:
            num_lines = w_px
            dist_per_line = real_h + (2 * overscan_dist)
            rect_full = (0, -overscan_dist, real_w, real_h + overscan_dist)
            x_step = l_step_val
            y_step = scan_step

        dist_decalage_total = (num_lines - 1) * l_step_val
        # -------------------------------------------------
        # 8) ESTIMATION TEMPS (FIABLE)
        # -------------------------------------------------
        dist_gravure = num_lines * dist_per_line
        total_dist = dist_gravure + dist_decalage_total
        est_min = (total_dist / feedrate) 

        # -------------------------------------------------
        # 9) ESTIMATION TAILLE GCODE
        # -------------------------------------------------
        gc_params_est = {
            "use_s_mode": s.get("use_s_mode", False),
            "raster_mode": raster_mode,
            "ctrl_max": max_p
        }

        est_size_str, _ = self.get_gcode_statistics(matrix, s, gc_params_est)

        # -------------------------------------------------
        # 10) GEOM FINAL CONSOLIDÉ
        # -------------------------------------------------
        geom = {
            "w_px": w_px,
            "h_px": h_px,
            "real_w": real_w,
            "real_h": real_h,
            "x_step": x_step,
            "y_step": y_step,
            "l_step": l_step_val,
            "scan_step": scan_step,
            "overscan_dist": overscan_dist,
            "est_min": est_min,
            "rect_burn": (0, 0, real_w, real_h),
            "rect_full": rect_full,
            "file_size_str": est_size_str,
            "raster_mode": raster_mode
        }

        return matrix, img, geom, mem_warn

    # =========================================================
    # INDUSTRIAL RASTER GCODE GENERATOR
    # =========================================================

    def generate_gcode_list(self, matrix, h_px, w_px, l_step, x_st, offX, offY, gc):
        buf = io.StringIO()

        # Extraction des paramètres avec valeurs de sécurité
        e_num = gc.get("e_num", 0)
        use_s_mode = gc.get("use_s_mode", False)
        ratio = gc.get("ratio", 1.0)
        ctrl_max = gc.get("ctrl_max", 255)
        pre = gc.get("premove", 2.0)
        feed = gc.get("feedrate", 3000)
        offset_latence = gc.get("offset_latence", 0.0)

        raster_mode = str(gc.get("raster_mode", "horizontal")).lower().strip()

        # Constantes de stabilité physique
        HYST_THRESHOLD = max(0.02 * ctrl_max, 0.001)
        hyst_p = 0.0

        buf.write(f"G1 F{feed}\n")

        if not use_s_mode:
            buf.write(f"M67 E{e_num} Q0.00\nG4 P0.1\n")

        p_matrix = np.clip(matrix * ratio, 0, ctrl_max)

        # Détermination de la géométrie selon le mode
        if raster_mode == "horizontal":
            outer_range = h_px
            inner_count = w_px
            step_main = l_step
            step_scan = x_st
        else:
            # Mode vertical (par défaut si non horizontal)
            outer_range = w_px
            inner_count = h_px
            step_main = x_st
            step_scan = l_step

        # La distance réelle de scan est basée sur les intervalles entre pixels
        real_scan_dist = (inner_count - 1) * step_scan

        # =====================================================
        # Boucle de balayage Raster
        # =====================================================
        for outer_idx in range(outer_range):
            is_fwd = (outer_idx % 2 == 0)
            scan_dir = 1 if is_fwd else -1
            corr = - offset_latence * scan_dir

            if raster_mode == "horizontal":
                main_pos = outer_idx * step_main + offY
                # Inversion de l'index pour graver de bas en haut (standard CNC)
                row_data = p_matrix[(h_px - 1) - outer_idx, :]
                axis = "X"
                scan_offset = offX
            else:
                main_pos = outer_idx * step_main + offX
                # Extraction de colonne et inversion pour graver de bas en haut
                row_data = p_matrix[::-1, outer_idx]
                axis = "Y"
                scan_offset = offY

            scan_start = (0 if is_fwd else real_scan_dist) + scan_offset
            scan_end = (real_scan_dist if is_fwd else 0) + scan_offset

            pre_start = scan_start - (pre * scan_dir)
            pre_end = scan_end + (pre * scan_dir)

            # 1. Positionnement initial sur la ligne
            if raster_mode == "horizontal":
                buf.write(f"G1 X{pre_start:.4f} Y{main_pos:.4f}\n")
            else:
                buf.write(f"G1 X{main_pos:.4f} Y{pre_start:.4f}\n")

            start_with_corr = scan_start + corr

            # Gestion de l'entrée dans l'image (Overscan de sécurité)
            if abs(start_with_corr - pre_start) > 0.0001:
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q0.00 G1 {axis}{start_with_corr:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{start_with_corr:.4f} S0\n")

            # 2. Boucle de traitement des pixels par segments
            current_pos = start_with_corr
            current_p = None
            group_target = start_with_corr
            
            pixel_indices = range(inner_count) if is_fwd else range(inner_count - 1, -1, -1)
            
            for pix_idx in pixel_indices:
                p_val = max(0.0, min(row_data[pix_idx], ctrl_max))
                
                # Application de l'hystérésis pour éviter les micro-variations de puissance
                if abs(p_val - hyst_p) < HYST_THRESHOLD:
                    p_val = hyst_p
                else:
                    hyst_p = p_val

                target_idx = (pix_idx + 1) if is_fwd else pix_idx
                target_scan = (target_idx * step_scan) + scan_offset + corr
                
                if current_p is None:
                    current_p = p_val

                # Si la puissance change, on écrit le segment parcouru
                if abs(p_val - current_p) > 0.001:
                    if abs(group_target - current_pos) > 0.0001:
                        if not use_s_mode:
                            buf.write(f"M67 E{e_num} Q{current_p:.3f} G1 {axis}{group_target:.4f}\n")
                        else:
                            buf.write(f"G1 {axis}{group_target:.4f} S{current_p:.3f}\n")
                        current_pos = group_target
                    current_p = p_val
                
                group_target = target_scan

            # 3. Finalisation du dernier segment de l'image
            end_with_corr = scan_end + corr
            last_p = current_p if current_p is not None else 0.0

            if abs(end_with_corr - current_pos) > 0.0001:
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q{last_p:.3f} G1 {axis}{end_with_corr:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{end_with_corr:.4f} S{last_p:.3f}\n")
            
            current_pos = end_with_corr

            # 4. Overscan de sortie haché (pour maintenir la stabilité de la vitesse)
            overscan_step = step_scan * 4
            dist_to_go = abs(pre_end - current_pos)
            num_steps_overscan = int(dist_to_go / overscan_step)
            
            for _ in range(num_steps_overscan):
                current_pos += (overscan_step * scan_dir)
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q0.00 G1 {axis}{current_pos:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{current_pos:.4f} S0\n")

            # Positionnement final de sécurité en bout de ligne
            if abs(pre_end - current_pos) > 0.0001:
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q0.00 G1 {axis}{pre_end:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{pre_end:.4f} S0\n")

        return buf.getvalue()
    
    def generate_framing_gcode(self, w, h, offX, offY, power,
                            feedrate, pause_cmd=None,
                            use_s_mode=True, e_num=0):

        lines = ["( --- FRAMING START --- )"]

        # 1. Sécurité : S'assurer que le laser est éteint avant de se déplacer
        off_cmd = "S0" if use_s_mode else f"M67 E{e_num} Q0"
        lines.append(f"{off_cmd} (Laser OFF)")
        
        # 2. Approche à vide vers le point de départ (Bas-Gauche)
        lines.append(f"G0 X{offX:.3f} Y{offY:.3f} F3000")
        
        # 3. Définition de la vitesse de travail
        lines.append(f"G1 F{feedrate}")

        p_cmd = f"S{power:.2f}" if use_s_mode else f"M67 E{e_num} Q{power:.2f}"

        # 4. Dessin du rectangle
        # On utilise une syntaxe standard : Mouvement puis Puissance (ou l'inverse selon machine)
        # Ici, on place la puissance sur chaque segment pour plus de sécurité
        if not use_s_mode:
            # Syntaxe M67 : La commande E doit précéder ou accompagner le G1
            lines.append(f"G1 X{offX+w:.3f} Y{offY:.3f} {p_cmd}")
            lines.append(f"G1 X{offX+w:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY:.3f} {p_cmd}")
        else:
            # Syntaxe Spindle (S)
            lines.append(f"G1 X{offX+w:.3f} Y{offY:.3f} {p_cmd}")
            lines.append(f"G1 X{offX+w:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY:.3f} {p_cmd}")

        # 5. Extinction finale
        lines.append(f"{off_cmd} (Laser OFF)")

        # 6. Pause optionnelle
        if pause_cmd:
            # On ajoute souvent un message pour l'utilisateur sur l'écran CNC
            lines.append(f"{pause_cmd} (Framing done, check position)")

        lines.append("( --- FRAMING END --- )")

        return "\n".join(lines) + "\n"
    
    
    def assemble_gcode(self, body, header_custom,
                   footer_custom, settings, metadata):

        e_num = settings["e_num"]
        use_s_mode = settings["use_s_mode"]

        firing_cmd = metadata["firing_cmd"]

        init_safety = (
            "M5 S0\nG4 P0.5"
            if use_s_mode
            else f"M67 E{e_num} Q0.00\nG4 P0.2\nM5\nG4 P0.3"
        )

        buf = io.StringIO()

        buf.write(f"( A.L.I.G. v{metadata['version']} )\n")
        buf.write(f"( Mode: {metadata['mode']} )\n")
        buf.write(f"( Firing Mode: {metadata['firing_cmd']} )\n")
        buf.write(f"( Grayscale Levels: {metadata['gray_steps']} )\n")

        buf.write("G21 G90 G17 G94\n")

        buf.write(header_custom + "\n")
        buf.write(init_safety + "\n\n")

        if metadata.get("framing_code"):
            buf.write(metadata["framing_code"] + "\n")
            buf.write(f"{firing_cmd} ( Re-arming laser )\n")
        else:
            buf.write(f"{firing_cmd}\n")

        buf.write(body)

        if not use_s_mode:
            buf.write(f"M67 E{e_num} Q0.00\n")

        buf.write("\nM5 S0 ( Ensure laser is off )\n")

        if footer_custom:
            buf.write("\n" + footer_custom + "\n")

        buf.write("M30\n")

        return buf.getvalue()

    def build_final_gcode(self,
                        matrix,
                        dims,
                        offsets,
                        settings_raw,
                        text_blocks,
                        metadata_raw):

        # Calcul de la latence (compensation matérielle)
        latency_mm = (
            settings_raw["feedrate"] *
            settings_raw["m67_delay"]
        ) / 60000

        gc_settings = {
            "e_num": settings_raw["e_num"],
            "use_s_mode": settings_raw["use_s_mode"],
            "ratio": settings_raw["ctrl_max"] / 100.0, # À vérifier selon ton calcul de puissance
            "ctrl_max": settings_raw["ctrl_max"],
            "premove": settings_raw["premove"],
            "feedrate": settings_raw["feedrate"],
            "offset_latence": latency_mm,
            "raster_mode": settings_raw.get("raster_mode", "horizontal")
        }

        # Désassemblage du tuple dims (envoyé par generate_gcode)
        # Rappel : dims = (h_px, w_px, y_step, x_step)
        h_px, w_px, y_st, x_st = dims
        offX, offY = offsets

        # Appel au générateur de liste de lignes
        # On s'assure de passer y_st et x_st dans le bon ordre
        gcode_body = self.generate_gcode_list(
            matrix,
            h_px,
            w_px,
            y_st,  # Anciennement l_step
            x_st,
            offX,
            offY,
            gc_settings
        )

        final_text = self.assemble_gcode(
            gcode_body,
            text_blocks["header"],
            text_blocks["footer"],
            gc_settings,
            metadata_raw
        )

        return final_text, latency_mm
    
    def generate_pointing_gcode(self, offX, offY, power,
                                pause_cmd=None,
                                use_s_mode=True,
                                e_num=0):

        lines = ["( --- POINTING START --- )"]

        if not use_s_mode:
            lines.append(f"M67 E{e_num} Q0")

        lines.append("G4 P0.1")
        lines.append("M5")

        lines.append(f"G0 X{offX:.3f} Y{offY:.3f} F3000")
        lines.append("M3")

        if use_s_mode:
            lines.append(f"G1 X{offX + 0.01:.3f} F100 S{power:.1f}")
            lines.append(f"G1 X{offX:.3f} F100")
        else:
            lines.append(f"M67 E{e_num} Q{power:.2f}")
            lines.append(f"G1 X{offX + 0.01:.3f} F100")
            lines.append(f"G1 X{offX:.3f} F100")

        lines.append(f"G1 X{offX:.3f}")
        lines.append("G4 P0.1")

        if pause_cmd:
            lines.append(f"{pause_cmd} (Press Cycle Start to continue)")

        lines.append("( --- POINTING END --- )")

        return "\n".join(lines) + "\n"
    

    
    def prepare_framing(self, config, dims, offsets):
        framing_gcode = ""
        real_w, real_h = dims
        offX, offY = offsets

        if config['is_pointing'] or config['is_framing']:
            try:
                pwr = float(config['f_pwr'])
                ratio = float(config['f_ratio']) / 100.0
                f_feed = int(config['base_feedrate'] * ratio)
            except:
                pwr, f_feed = 0.0, 600

            # Pointing laser test position
            if config['is_pointing']:
                framing_gcode += self.generate_pointing_gcode(
                    offX, offY, pwr,
                    pause_cmd=config['f_pause'],
                    use_s_mode=config['use_s_mode'],
                    e_num=config['e_num']
                ) + "\n"

            # Rectangle framing contour preview
            if config['is_framing']:
                framing_gcode += self.generate_framing_gcode(
                    real_w, real_h,
                    offX, offY,
                    power=pwr,
                    feedrate=f_feed,
                    pause_cmd=config['f_pause'],
                    use_s_mode=config['use_s_mode'],
                    e_num=config['e_num']
                )

        return framing_gcode

    def calculate_offsets(self,
                      selected_origin,
                      real_w,
                      real_h,
                      custom_x=0,
                      custom_y=0):

        offX, offY = 0, 0

        if selected_origin == "Upper-Left":
            offY = -real_h

        elif selected_origin == "Lower-Right":
            offX = -real_w

        elif selected_origin == "Upper-Right":
            offX, offY = -real_w, -real_h

        elif selected_origin == "Center":
            offX, offY = -real_w / 2, -real_h / 2

        elif selected_origin == "Custom":
            offX, offY = -custom_x, -custom_y

        return offX, offY
    
    # def compute_geometry(self, s, matrix_shape=None):
    #     self.stats = {} 
        
    #     # 1. Constantes de base
    #     scan_step = 25.4 / max(1, float(s.get("dpi", 254)))
    #     l_step = float(s.get("line_step", 0.1))
    #     # On force la casse pour la comparaison
    #     raster_mode = str(s.get("raster_mode", "horizontal")).lower().strip()
        
    #     target_w = float(s.get("width", 10.0))

    #     # 2. Détermination des dimensions en pixels (Logique "Force Exact")
    #     if matrix_shape:
    #         img_h, img_w = matrix_shape
    #         aspect_ratio = img_h / img_w
            
    #         if raster_mode == "horizontal":
    #             # Pour faire exactement target_w, il faut (target_w / step) + 1 pixels
    #             w_px = max(2, int(round(target_w / scan_step)) + 1)
    #             # On ajuste h_px selon le ratio de l'image
    #             real_w_tmp = (w_px - 1) * scan_step
    #             h_px = max(2, int(round((real_w_tmp * aspect_ratio) / l_step)) + 1)
    #         else: # Vertical
    #             # En vertical, target_w est la longueur de scan (axe Y)
    #             h_px = max(2, int(round(target_w / scan_step)) + 1)
    #             real_h_tmp = (h_px - 1) * scan_step
    #             w_px = max(2, int(round((real_h_tmp / aspect_ratio) / l_step)) + 1)
    #     else:
    #         # Valeurs par défaut si pas d'image
    #         w_px = max(2, int(target_w / scan_step))
    #         h_px = max(2, int(10.0 / l_step))

    #     # 3. Calcul des dimensions physiques finales
    #     if raster_mode == "Horizontal":
    #         real_w = (w_px - 1) * scan_step
    #         real_h = (h_px - 1) * l_step
    #     else:
    #         real_w = (w_px - 1) * l_step
    #         real_h = (h_px - 1) * scan_step
        
    #     # 4. Calcul de l'Overscan
    #     overscan_dist = float(s.get("premove", 2.0)) 
        
    #     # 5. Définition des zones
    #     rect_burn = (0, 0, real_w, real_h)
    #     if raster_mode == "horizontal":
    #         rect_full = (-overscan_dist, 0, real_w + overscan_dist, real_h)
    #     else:
    #         rect_full = (0, -overscan_dist, real_w, real_h + overscan_dist)

    #     # 6. Estimation du temps (Correction de la clé speed -> feedrate)
    #     num_passes = h_px if raster_mode == "horizontal" else w_px
    #     dist_per_pass = (real_w if raster_mode == "horizontal" else real_h) + (2 * overscan_dist)
        
    #     total_dist_mm = num_passes * dist_per_pass
    #     speed_mm_min = float(s.get("feedrate", 3000))
        
    #     # Calcul temps
    #     est_min = total_dist_mm / max(1.0, speed_mm_min)
    #     # Ajout temps de latence accélération (0.1s par ligne est plus réaliste)
    #     est_min += (num_passes * 0.1) / 60 

    #     return {
    #         "w_px": w_px,
    #         "h_px": h_px,
    #         "real_w": real_w,
    #         "real_h": real_h,
    #         "x_step": scan_step if raster_mode == "horizontal" else l_step,
    #         "y_step": l_step if raster_mode == "horizontal" else scan_step,
    #         "scan_step": scan_step,
    #         "l_step": l_step,
    #         "overscan_dist": overscan_dist,
    #         "est_min": est_min,
    #         "rect_burn": rect_burn,
    #         "rect_full": rect_full,
    #         "raster_mode": raster_mode
    #     }
    def simulate_gcode_size(self, matrix, raster_mode, g_steps):
        """
        Version NumPy ultra-rapide pour estimer le nombre de lignes G-Code.
        """
        # On s'assure que la matrice est en entiers pour des comparaisons exactes
        m = matrix.astype(np.int16)
        
        if raster_mode == "horizontal":
            # Différence entre chaque pixel et son voisin de gauche
            # np.diff renvoie une matrice de taille (H, W-1)
            diffs = np.diff(m, axis=1)
            # Un changement survient si la différence est non nulle
            changes = np.count_nonzero(diffs)
            # On ajoute le premier pixel de chaque ligne s'il n'est pas blanc
            starts = np.count_nonzero(m[:, 0] > 0)
        else:
            # Idem pour le mode vertical (axis=0)
            diffs = np.diff(m, axis=0)
            changes = np.count_nonzero(diffs)
            starts = np.count_nonzero(m[0, :] > 0)

        # Calcul des lignes :
        # Chaque 'change' est une nouvelle commande G1 ou S
        # On ajoute les retours à la ligne (H ou W selon le mode)
        n_gcode_lines = changes + starts + (m.shape[0] if raster_mode == "horizontal" else m.shape[1])
        
        # Estimation du poids :
        # 16 octets est une moyenne réaliste pour "G1X123.45S255\n"
        total_chars = n_gcode_lines * 16
        
        return total_chars, n_gcode_lines
    
    def get_gcode_statistics(self, matrix, s, gc_params):
        try:
            h_px, w_px = matrix.shape
            raster_mode = str(gc_params.get("raster_mode", "horizontal")).lower().strip()
            g_steps = int(s.get("grayscale_steps", 256))
            
            # Quantification Vectorisée (Ultra rapide)
            if g_steps < 256:
                factor = 255 / (g_steps - 1)
                sim_matrix = np.round(matrix / factor) * factor
            else:
                sim_matrix = matrix

            # Simulation NumPy
            total_bytes, n_gcode_lines = self.simulate_gcode_size(sim_matrix, raster_mode, g_steps)

            # Header/Footer forfaitaire
            total_bytes += 1500 

            if total_bytes < 1024 * 1024:
                est_size_str = f"{total_bytes / 1024:.1f} KB"
            else:
                est_size_str = f"{total_bytes / (1024 * 1024):.2f} MB"

            return est_size_str, int(n_gcode_lines)

        except Exception as e:
            print(f"Estimation error: {e}")
            return "0 KB", 0