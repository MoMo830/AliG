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

        l_step_val = s["line_step"]
        x_step = 25.4 / max(1, s["dpi"])
        raster_mode = s.get("raster_mode", "Horizontal")

        # -----------------------------
        # Load Image
        # -----------------------------
        img = source_img_cache if source_img_cache else Image.open(image_path).convert("L")

        orig_w, orig_h = img.size
        img_ratio = orig_h / orig_w

        # Target width
        tw = min(s["width"], 2000)

        w_px = max(2, int(tw / x_step))

        # Preserve physical raster ratio
        h_px_float = (w_px * x_step * img_ratio) / l_step_val
        h_px = max(2, int(round(h_px_float)))

        # Physical geometry
        real_w = (w_px - 1) * x_step
        real_h = (h_px - 1) * l_step_val

        # Memory safety
        MAX_TOTAL_PIXELS = 10_000_000

        if w_px * h_px > MAX_TOTAL_PIXELS:
            scale = np.sqrt(MAX_TOTAL_PIXELS / (w_px * h_px))
            w_px = max(2, int(w_px * scale))
            h_px = max(2, int(h_px * scale))

        # -----------------------------
        # Industrial Resize (Bicubic only)
        # -----------------------------
        img_resized = img.resize(
            (w_px, h_px),
            Image.Resampling.BICUBIC
        )

        arr = np.asarray(img_resized, dtype=np.float32) / 255.0

        # -----------------------------
        # Signal Conditioning
        # -----------------------------

        if not s.get("invert"):
            np.subtract(1.0, arr, out=arr)

        if s["contrast"] != 0:
            f = (259 * (s["contrast"] + 1.0)) / (255 * (259 - s["contrast"])) * 255
            arr = np.clip((arr - 0.5) * f + 0.5, 0, 1)

        combined_exp = s["gamma"] * s["thermal"]
        if combined_exp != 1.0:
            np.power(arr, combined_exp, out=arr)

        # -----------------------------
        # Physical Quantization Core
        # -----------------------------

        QUANT_LEVEL = max(32, int(s["gray_steps"]))

        norm = np.clip(arr, 0, 1)

        matrix = s["min_p"] + (
            np.round(norm * (QUANT_LEVEL - 1)) / (QUANT_LEVEL - 1)
        ) * (s["max_p"] - s["min_p"])

        # Secondary quantization layer
        if s["gray_steps"] < 256:

            range_p = s["max_p"] - s["min_p"]

            if range_p > 0:

                q_levels = max(2, int(s["gray_steps"]))

                matrix = s["min_p"] + (
                    np.round((matrix - s["min_p"]) / range_p * (q_levels - 1))
                    / (q_levels - 1)
                    * range_p
                )

        # Black region suppression
        matrix *= (arr >= 0.005).astype(np.float32)

        total_dist = (
            h_px * (real_w + 2 * s["premove"])
            if raster_mode == "Horizontal"
            else w_px * (real_h + 2 * s["premove"])
        )

        est_min = total_dist / max(1e-6, s["feedrate"])

        latency_mm = (
            s["feedrate"] * s.get("m67_delay", 0)
        ) / 60000

        # Préparer gc_params pour l'estimation
        gc_params_est = {
            "use_s_mode": s.get("use_s_mode", False),
            "raster_mode": raster_mode,
            "ctrl_max": s.get("max_p", 255) # ou votre variable de puissance max
        }
        
        est_size_str, n_lines = self.estimate_gcode_statistics(matrix, s, gc_params_est)
        
        # Vous pouvez maintenant retourner cette valeur aussi
        return matrix, h_px, w_px, l_step_val, x_step, est_min, False, img, latency_mm, est_size_str

    # =========================================================
    # INDUSTRIAL RASTER GCODE GENERATOR
    # =========================================================

    def generate_gcode_list(self, matrix, h_px, w_px, l_step, x_st, offX, offY, gc):

        buf = io.StringIO()

        e_num = gc["e_num"]
        use_s_mode = gc["use_s_mode"]
        ratio = gc["ratio"]
        ctrl_max = gc["ctrl_max"]

        pre = gc["premove"]
        feed = gc["feedrate"]
        offset_latence = gc["offset_latence"]

        raster_mode = gc.get("raster_mode", "Horizontal")

        # Physical stability constants
        HYST_THRESHOLD = max(0.02 * ctrl_max, 0.001)

        hyst_p = 0.0

        buf.write(f"G1 F{feed}\n")

        if not use_s_mode:
            buf.write(f"M67 E{e_num} Q0.00\nG4 P0.1\n")

        p_matrix = np.clip(matrix * ratio, 0, ctrl_max)

        # Raster geometry
        if raster_mode == "Horizontal":
            outer_range = h_px
            inner_count = w_px
            step_main = l_step
            step_scan = x_st
        else:
            outer_range = w_px
            inner_count = h_px
            step_main = x_st
            step_scan = l_step

        real_scan_dist = inner_count * step_scan

        # =====================================================
        # Raster scan loop (Industrial monotonic trajectory)
        # =====================================================

        for outer_idx in range(outer_range):
            is_fwd = (outer_idx % 2 == 0)
            scan_dir = 1 if is_fwd else -1
            corr = - offset_latence * scan_dir

            if raster_mode == "Horizontal":
                main_pos = outer_idx * step_main + offY
                row_data = p_matrix[(h_px - 1) - outer_idx, :]
                axis = "X"
                scan_offset = offX
            else:
                main_pos = outer_idx * step_main + offX
                row_data = p_matrix[::-1, outer_idx]
                axis = "Y"
                scan_offset = offY

            scan_start = (0 if is_fwd else real_scan_dist) + scan_offset
            scan_end = (real_scan_dist if is_fwd else 0) + scan_offset

            pre_start = scan_start - (pre * scan_dir)
            pre_end = scan_end + (pre * scan_dir)

            # Positioning
            # --- 1. POSITIONNEMENT INITIAL ---
            if raster_mode == "Horizontal":
                buf.write(f"G1 X{pre_start:.4f} Y{main_pos:.4f}\n")
            else:
                buf.write(f"G1 X{main_pos:.4f} Y{pre_start:.4f}\n")

            start_with_corr = scan_start + corr

            # --- GESTION DE L'OVERSCAN (Entrée) ---
            if abs(start_with_corr - pre_start) > 0.0001:
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q0.00 G1 {axis}{start_with_corr:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{start_with_corr:.4f} S0\n")

            # --- 2. INITIALISATION DE LA BOUCLE ---
            current_pos = start_with_corr
            current_p = None
            group_target = start_with_corr
            
            # On parcourt TOUS les pixels (inner_count)
            # segment_indices doit représenter l'index du pixel en cours de lecture
            pixel_indices = range(inner_count) if is_fwd else range(inner_count - 1, -1, -1)
            
            # --- 3. BOUCLE DE PIXELS ---
            for pix_idx in pixel_indices:
                p_val = max(0.0, min(row_data[pix_idx], ctrl_max))
                
                if abs(p_val - hyst_p) < HYST_THRESHOLD:
                    p_val = hyst_p
                else:
                    hyst_p = p_val

                # La cible est le BORD du pixel suivant dans la direction de marche
                # Si fwd: target est à pix_idx + 1
                # Si rev: target est à pix_idx (le bord gauche du pixel actuel)
                target_idx = (pix_idx + 1) if is_fwd else pix_idx
                target_scan = (target_idx * step_scan) + scan_offset + corr
                
                if current_p is None:
                    current_p = p_val

                # Si la puissance change, on flush le segment précédent
                if abs(p_val - current_p) > 0.001:
                    if abs(group_target - current_pos) > 0.0001:
                        if not use_s_mode:
                            buf.write(f"M67 E{e_num} Q{current_p:.3f} G1 {axis}{group_target:.4f}\n")
                        else:
                            buf.write(f"G1 {axis}{group_target:.4f} S{current_p:.3f}\n")
                        current_pos = group_target
                    current_p = p_val
                
                group_target = target_scan

            # --- 4. FERMETURE BORD IMAGE (MODIFIÉ : STYLE "STABLE") ---
            end_with_corr = scan_end + corr
            last_p = current_p if current_p is not None else 0.0

            # On valide le dernier segment de gravure jusqu'à la limite latence
            if abs(end_with_corr - current_pos) > 0.0001:
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q{last_p:.3f} G1 {axis}{end_with_corr:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{end_with_corr:.4f} S{last_p:.3f}\n")
            
            current_pos = end_with_corr

            # --- 5. OVERSCAN FINAL HACHÉ (Le secret de l'ancienne version) ---
            overscan_step = step_scan * 4
            dist_to_go = abs(pre_end - current_pos)
            num_steps_overscan = int(dist_to_go / overscan_step)
            
            for _ in range(num_steps_overscan):
                current_pos += (overscan_step * scan_dir)
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q0.00 G1 {axis}{current_pos:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{current_pos:.4f} S0\n")

            # --- 6. POSITIONNEMENT FINAL RÉEL ---
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

        lines.append(f"G0 X{offX:.3f} Y{offY:.3f} F3000")
        lines.append(f"G1 F{feedrate}")

        p_cmd = f"S{power:.2f}" if use_s_mode else f"M67 E{e_num} Q{power:.2f}"
        off_cmd = "S0" if use_s_mode else f"M67 E{e_num} Q0"

        if not use_s_mode:

            lines.append(f"{p_cmd} G1 X{offX+w:.3f} Y{offY:.3f}")
            lines.append(f"{p_cmd} G1 X{offX+w:.3f} Y{offY+h:.3f}")
            lines.append(f"{p_cmd} G1 X{offX:.3f} Y{offY+h:.3f}")
            lines.append(f"{p_cmd} G1 X{offX:.3f} Y{offY:.3f}")

            lines.append(f"{off_cmd} G1")

        else:

            lines.append(f"G1 X{offX+w:.3f} Y{offY:.3f} {p_cmd}")
            lines.append(f"G1 X{offX+w:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY:.3f} {p_cmd}")

            lines.append(f"G1 {off_cmd}")

        if pause_cmd:
            lines.append(f"{pause_cmd} (Press Cycle Start to continue)")

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

        latency_mm = (
            settings_raw["feedrate"] *
            settings_raw["m67_delay"]
        ) / 60000

        gc_settings = {
            "e_num": settings_raw["e_num"],
            "use_s_mode": settings_raw["use_s_mode"],
            "ratio": settings_raw["ctrl_max"] / 100.0,
            "ctrl_max": settings_raw["ctrl_max"],
            "premove": settings_raw["premove"],
            "feedrate": settings_raw["feedrate"],
            "offset_latence": latency_mm,
            "raster_mode": settings_raw.get("raster_mode", "Horizontal")
        }

        h_px, w_px, l_step, x_st = dims
        offX, offY = offsets

        gcode_body = self.generate_gcode_list(
            matrix,
            h_px,
            w_px,
            l_step,
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
        else:
            lines.append(f"M67 E{e_num} Q{power:.2f}")
            lines.append(f"G1 X{offX + 0.01:.3f} F100")

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
    
    def compute_geometry(self, s, matrix_shape=None):
        """
        Calcule les dimensions physiques, l'overscan et les statistiques temporelles.
        s : dictionnaire des paramètres (width, dpi, line_step, overscan_dist, speed, etc.)
        matrix_shape : (h_px, w_px) optionnel si la matrice est déjà générée.
        """
        # 1. Constantes de base
        x_step = 25.4 / max(1, s.get("dpi", 254))
        l_step = s.get("line_step", 0.1)
        raster_mode = s.get("raster_mode", "Horizontal")
        
        # 2. Détermination des dimensions en pixels
        # Si la matrice n'est pas fournie, on simule la taille basée sur la largeur cible
        if matrix_shape:
            h_px, w_px = matrix_shape
        else:
            w_px = max(2, int(s["width"] / x_step))
            # On simule la hauteur proportionnelle (ou fixe selon votre logique)
            h_px = max(2, int(s["height"] / l_step))

        # 3. Calcul des dimensions réelles (Zone de gravure)
        real_w = (w_px - 1) * x_step
        real_h = (h_px - 1) * l_step
        
        # 4. Calcul de l'Overscan
        # On peut utiliser une valeur fixe ou un calcul dynamique basé sur l'accélération
        overscan_dist = float(s.get("overscan_dist", 2.0))
        
        # 5. Définition des zones (Rectangles de simulation)
        # Format : (x_min, y_min, x_max, y_max)
        self.stats["rect_burn"] = (0, 0, real_w, real_h)
        
        if raster_mode == "Horizontal":
            # L'overscan s'ajoute à gauche et à droite de l'axe X
            self.stats["rect_full"] = (-overscan_dist, 0, real_w + overscan_dist, real_h)
        else:
            # Mode Vertical : l'overscan s'ajoute en haut et en bas de l'axe Y
            self.stats["rect_full"] = (0, -overscan_dist, real_w, real_h + overscan_dist)

        # 6. Estimation du temps (simplifiée)
        # On calcule la distance totale parcourue par la tête
        num_lines = h_px if raster_mode == "Horizontal" else w_px
        dist_per_line = (real_w if raster_mode == "Horizontal" else real_h) + (2 * overscan_dist)
        
        total_dist_mm = num_lines * dist_per_line
        speed_mm_min = s.get("speed", 3000)
        
        # Temps = distance / vitesse + temps de transition (estimé)
        est_min = total_dist_mm / max(1, speed_mm_min)
        est_min += (num_lines * 0.1) / 60 # Ajout de 100ms par changement de ligne
        
        self.stats["est_min"] = est_min

        # 7. Retour de l'objet complet pour la vue
        return {
            "w_px": w_px,
            "h_px": h_px,
            "real_w": real_w,
            "real_h": real_h,
            "x_step": x_step,
            "l_step": l_step,
            "overscan_dist": overscan_dist,
            "est_min": est_min,
            "rect_burn": self.stats["rect_burn"],
            "rect_full": self.stats["rect_full"]
        }

    def estimate_gcode_statistics(self, matrix, s_params, gc_params):
        if matrix is None:
            return "0 KB", 0

        h_px, w_px = matrix.shape
        use_s = gc_params.get("use_s_mode", False)
        raster_mode = gc_params.get("raster_mode", "Horizontal")
        ctrl_max = gc_params.get("ctrl_max", 255)
        
        # --- CALIBRATION SUR TON EXEMPLE ---
        # "M67 E0 Q15.000 G1 X0.2000" + \n = 27 octets
        # En mode S, c'est souvent un peu plus court (ex: G1 X0.200 S15)
        b_per_l = 22 if use_s else 27 
        
        HYST_THRESHOLD = max(0.02 * ctrl_max, 0.001)
        total_lines = 30 # Header court
        
        analysis_matrix = matrix if raster_mode == "Horizontal" else matrix.T
            
        for y in range(analysis_matrix.shape[0]):
            row = analysis_matrix[y]
            
            # Setup par trajet (M3, G1 F, G1 approche, etc.)
            # Ton exemple montre environ 6 lignes de setup/transition
            total_lines += 6 
            
            # Changements de puissance
            diffs = np.abs(np.diff(row))
            changes = np.count_nonzero(diffs > HYST_THRESHOLD)
            
            total_lines += changes + 1
            
            # Overscan (Ton exemple montre des G1 X hachés à la fin)
            # On compte le nombre de segments de 0.4mm (selon ton log)
            total_lines += 5

        # Calcul final
        size_bytes = total_lines * b_per_l
        
        if size_bytes < 1048576:
            size_str = f"{size_bytes/1024:.1f} KB"
        else:
            size_str = f"{size_bytes/1048576:.2f} MB"
            
        return size_str, total_lines