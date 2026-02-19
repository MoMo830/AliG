"""
A.L.I.G. Project - Core Engine
------------------------------
Image processing and G-Code logic.
"""

import numpy as np
from PIL import Image
import os

class GCodeEngine:
    def __init__(self):
        # On stocke les résultats pour y accéder facilement sans recalculer
        self.matrix = None
        self.stats = {}
        self.last_gcode_body = []


    def process_image_logic(self, image_path, s, source_img_cache=None):
        """
        Traitement d'image avec support du sens de raster.
        """
        # 1. Init et calculs de base
        x_step = 25.4 / max(1, s["dpi"])
        raster_mode = s.get('raster_mode', "Horizontal")
        
        if source_img_cache is None:
            img = Image.open(image_path).convert('L')
        else:
            img = source_img_cache
        
        orig_w, orig_h = img.size
        tw = min(s["width"], 2000)
        th = (tw * orig_h / orig_w)

        # Pixels théoriques
        w_px = max(2, int(tw / x_step))
        h_px = max(1, int(th / s["line_step"]))

        # 2. Sécurité mémoire
        MAX_TOTAL_PIXELS = 10000000 
        current_pixels = w_px * h_px
        memory_warning = False

        l_step_val = s["line_step"]

        if current_pixels > MAX_TOTAL_PIXELS:
            memory_warning = True
            scale_factor = np.sqrt(MAX_TOTAL_PIXELS / current_pixels)
            w_px = int(w_px * scale_factor)
            h_px = int(h_px * scale_factor)
            
            # Correction des pas pour maintenir la taille physique (tw x th)
            if raster_mode == "Horizontal":
                # On ajuste le pas horizontal, on garde le line_step vertical fixe
                x_step = tw / (w_px - 1) if w_px > 1 else x_step
            else:
                # En vertical, le "line_step" devient l'axe de balayage, on l'ajuste
                l_step_val = th / (h_px - 1) if h_px > 1 else s["line_step"]
                # Le x_step (écart entre colonnes) reste celui du DPI
        
        if s.get("force_width") and raster_mode == "Horizontal":
            x_step = tw / max(1, (w_px - 1))

        # 3. Traitement matriciel
        img_resized = img.resize((w_px, h_px), Image.Resampling.LANCZOS)
        arr = np.asarray(img_resized, dtype=np.float32) / 255.0

        if not s.get("invert"):
            np.subtract(1.0, arr, out=arr) 

        if s["contrast"] != 0:
            f = (259 * (s["contrast"] + 1.0)) / (255 * (259 - s["contrast"])) * 255
            arr = np.clip((arr - 0.5) * f + 0.5, 0, 1)
                
        combined_exp = s["gamma"] * s["thermal"]
        if combined_exp != 1.0:
            np.power(arr, combined_exp, out=arr)
        
        matrix = s["min_p"] + (arr * (s["max_p"] - s["min_p"]))
        
        if s["gray_steps"] < 256:
            range_p = s["max_p"] - s["min_p"]
            if range_p > 0:
                matrix = s["min_p"] + (np.round((matrix - s["min_p"]) / range_p * (s["gray_steps"] - 1)) / (s["gray_steps"] - 1) * range_p)

        matrix[arr < 0.005] = 0
        
        # 4. Estimation temps adaptée au sens
        if raster_mode == "Horizontal":
            total_dist = h_px * (tw + (2 * s["premove"]))
        else:
            total_dist = w_px * (th + (2 * s["premove"]))
            
        est_min = total_dist / s["feedrate"]
        m67_delay = s.get('m67_delay', 0)
        latency_mm = (s['feedrate'] * m67_delay) / 60000

        return matrix, h_px, w_px, l_step_val, x_step, est_min, memory_warning, img, latency_mm



    def generate_gcode_list(self, matrix, h_px, w_px, l_step, x_st, offX, offY, gc):
        gcode = []
        
        # Extraction rapide des paramètres
        e_num = gc['e_num']
        use_s_mode = gc['use_s_mode']
        ratio = gc['ratio']
        ctrl_max = gc['ctrl_max']
        pre = gc['premove']
        offset_latence = gc['offset_latence']
        raster_mode = gc.get('raster_mode', "Horizontal")

        gcode.append(f"G1 F{gc['feedrate']}")
        if not use_s_mode:
            gcode.append(f"M67 E{e_num} Q0.00\nG4 P0.1")

        # Pré-formatage des commandes pour éviter de reconstruire les strings complexes
        if not use_s_mode:
            cmd_template = f"M67 E{e_num} Q{{:.2f}} G1 {{}}{{:.4f}}"
            move_template = f"M67 E{e_num} Q0.00 G1 {{}}{{:.4f}}"
        else:
            cmd_template = "G1 {0}{1:.4f} S{2:.2f}"
            move_template = "G1 {0}{1:.4f} S0"

        # Pré-calcul de la matrice de puissance (ratio + clip) pour toute l'image d'un coup
        # C'est BEAUCOUP plus rapide que de le faire dans la boucle
        p_matrix = np.clip(matrix * ratio, 0, ctrl_max)

        if raster_mode == "Horizontal":
            outer_range, step_main, step_scan = h_px, l_step, x_st
            axis = "X"
            main_offset, scan_offset = offY, offX
        else:
            outer_range, step_main, step_scan = w_px, x_st, l_step
            axis = "Y"
            main_offset, scan_offset = offX, offY

        real_scan_dist = ( (w_px if raster_mode == "Horizontal" else h_px) - 1) * step_scan

        for outer_idx in range(outer_range):
            main_pos = (outer_idx * step_main) + main_offset
            is_fwd = (outer_idx % 2 == 0)
            scan_dir = 1 if is_fwd else -1
            corr = offset_latence * scan_dir
            
            # Extraction de la ligne de puissance
            if raster_mode == "Horizontal":
                row = p_matrix[(h_px - 1) - outer_idx, :]
            else:
                row = p_matrix[::-1, outer_idx]

            if not is_fwd:
                row = row[::-1]

            # --- DÉTECTION DES CHANGEMENTS (Le coeur de l'optimisation) ---
            # On ne garde que les indices où la puissance change
            changes = np.where(np.abs(np.diff(row)) > 0.0001)[0] + 1
            # On ajoute le premier et le dernier point
            indices = np.unique(np.concatenate(([0], changes, [len(row) - 1])))
            
            # Calcul des positions de balayage pré-move
            scan_start = (0 if is_fwd else real_scan_dist) + scan_offset
            pre_start = scan_start - (pre * scan_dir)
            
            # 1. Positionnement initial
            if raster_mode == "Horizontal":
                gcode.append(move_template.format(f"X{pre_start:.3f} Y", main_pos))
            else:
                gcode.append(move_template.format(f"X{main_pos:.4f} Y", pre_start))

            # 2. Pre-move vers bord image
            current_scan = scan_start + corr
            gcode.append(move_template.format(axis, current_scan))

            # 3. Gravure (Boucle uniquement sur les points de changement)
            for idx in indices:
                p_val = row[idx]
                # Calcul de la position X ou Y réelle sur la grille
                grid_idx = idx if is_fwd else (len(row) - 1 - idx)
                target_scan = (grid_idx * step_scan) + scan_offset + corr
                
                if not use_s_mode:
                    gcode.append(cmd_template.format(p_val, axis, target_scan))
                else:
                    gcode.append(cmd_template.format(axis, target_scan, p_val))

            # 4. Overscan final
            pre_end = (real_scan_dist if is_fwd else 0) + scan_offset + (pre * scan_dir)
            gcode.append(move_template.format(axis, pre_end))

        return gcode

    def assemble_gcode(self, body, header_custom, footer_custom, settings, metadata):
        """Assemble toutes les parties du G-code en un seul bloc de texte."""
        e_num = settings['e_num']
        use_s_mode = settings['use_s_mode']
        firing_cmd = metadata['firing_cmd']
        
        # Sécurité initiale
        if use_s_mode:
            init_safety = "M5 S0\nG4 P0.5"
        else:
            init_safety = f"M67 E{e_num} Q0.00\nG4 P0.2\nM5\nG4 P0.3"

        # Construction de la liste
        lines = [
            f"( A.L.I.G. v{metadata['version']} )",
            f"( Mode: {metadata['mode']} )",
            f"( Firing Mode: {metadata['firing_cmd']} )",
            f"( Grayscale Levels: {metadata['gray_steps']} )",
            "G21 G90 G17 G94", 
            header_custom,
            init_safety,
            ""
        ]

        # Ajout du framing s'il existe
        if metadata.get('framing_code'):
            lines.append(metadata['framing_code'])
            lines.append(f"{firing_cmd} ( Re-arming laser )")
        else:
            lines.append(firing_cmd)

        # Corps (mouvements image)
        lines.extend(body)

        # Pied de page
        if not use_s_mode:
            lines.append(f"M67 E{e_num} Q0.00")
        
        lines.append("\nM5 S0 ( Ensure laser is off )")
        
        if footer_custom:
            lines.append(f"\n{footer_custom}")
            
        lines.append("M30")
        
        return "\n".join(lines)
    
    def build_final_gcode(self, matrix, dims, offsets, settings_raw, text_blocks, metadata_raw):
        """
        Centralise la génération finale du fichier G-Code.
        """
        # 1. Préparation des réglages G-Code
        latency_mm = (settings_raw['feedrate'] * settings_raw['m67_delay']) / 60000 

        gc_settings = {
            'e_num': settings_raw['e_num'],
            'use_s_mode': settings_raw['use_s_mode'],
            'ratio': settings_raw['ctrl_max'] / 100.0,
            'ctrl_max': settings_raw['ctrl_max'],
            'premove': settings_raw['premove'],
            'feedrate': settings_raw['feedrate'],
            'offset_latence': latency_mm,
            # On récupère le sens (par défaut Horizontal si non défini)
            'raster_mode': settings_raw.get('raster_mode', "Horizontal")
        }

        # 2. Génération du corps
        h_px, w_px, l_step, x_st = dims
        offX, offY = offsets
        gcode_body = self.generate_gcode_list(matrix, h_px, w_px, l_step, x_st, offX, offY, gc_settings)

        # 3. Assemblage avec Header/Footer
        final_text = self.assemble_gcode(
            gcode_body, 
            text_blocks['header'],
            text_blocks['footer'],
            gc_settings,
            metadata_raw
        )

        return final_text, latency_mm

    def calculate_offsets(self, selected_origin, real_w, real_h, custom_x=0, custom_y=0):
        offX, offY = 0, 0
        if selected_origin == "Upper-Left": offY = -real_h
        elif selected_origin == "Lower-Right": offX = -real_w
        elif selected_origin == "Upper-Right": offX, offY = -real_w, -real_h
        elif selected_origin == "Center": offX, offY = -real_w / 2, -real_h / 2
        elif selected_origin == "Custom":
            offX, offY = -custom_x, -custom_y
        return offX, offY
    
    def prepare_framing(self, config, dims, offsets):
        """Calcule et génère le G-Code de pointage et de cadrage"""
        framing_gcode = ""
        real_w, real_h = dims
        offX, offY = offsets
        
        if config['is_pointing'] or config['is_framing']:
            # Logique de calcul sécurisée déplacée de l'UI vers le moteur
            try:
                pwr = float(config['f_pwr'])
                ratio = float(config['f_ratio']) / 100.0
                f_feed = int(config['base_feedrate'] * ratio)
            except:
                pwr, f_feed = 0.0, 600

            # A. Génération Pointing
            if config['is_pointing']:
                framing_gcode += self.generate_pointing_gcode(
                    offX, offY, pwr,
                    pause_cmd=config['f_pause'],
                    use_s_mode=config['use_s_mode'],
                    e_num=config['e_num']
                ) + "\n"

            # B. Génération Framing
            if config['is_framing']:
                framing_gcode += self.generate_framing_gcode(
                    real_w, real_h, offX, offY,
                    power=pwr,
                    feedrate=f_feed,
                    pause_cmd=config['f_pause'],
                    use_s_mode=config['use_s_mode'],
                    e_num=config['e_num']
                )
        return framing_gcode

    def generate_framing_gcode(self, w, h, offX, offY, power, feedrate, pause_cmd=None, use_s_mode=True, e_num=0):
        lines = ["( --- FRAMING START --- )"]
        
        # Positionnement rapide au point de départ
        lines.append(f"G0 X{offX:.3f} Y{offY:.3f} F3000")
        lines.append(f"G1 F{feedrate}")
        
        # Préparation des commandes
        p_cmd = f"S{power:.2f}" if use_s_mode else f"M67 E{e_num} Q{power:.2f}"
        off_cmd = "S0" if use_s_mode else f"M67 E{e_num} Q0"

        # Tracé du rectangle de cadrage
        # Si M67, on met la puissance AVANT le G1 pour la synchro temps réel
        if not use_s_mode:
            lines.append(f"{p_cmd} G1 X{offX+w:.3f} Y{offY:.3f}")
            lines.append(f"{p_cmd} G1 X{offX+w:.3f} Y{offY+h:.3f}")
            lines.append(f"{p_cmd} G1 X{offX:.3f} Y{offY+h:.3f}")
            lines.append(f"{p_cmd} G1 X{offX:.3f} Y{offY:.3f}")
            lines.append(f"{off_cmd} G1")
        else:
            # Mode S standard (plus tolérant sur l'ordre)
            lines.append(f"G1 X{offX+w:.3f} Y{offY:.3f} {p_cmd}")
            lines.append(f"G1 X{offX+w:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY+h:.3f} {p_cmd}")
            lines.append(f"G1 X{offX:.3f} Y{offY:.3f} {p_cmd}")
            lines.append(f"G1 {off_cmd}")
        
        # Pause avec message explicite
        if pause_cmd:
            lines.append(f"{pause_cmd} (Press Cycle Start to continue)")
            
        lines.append("( --- FRAMING END --- )")
        return "\n".join(lines) + "\n"

    def generate_pointing_gcode(self, offX, offY, power, pause_cmd=None, use_s_mode=True, e_num=0):
        """Génère la séquence de pointage d'origine avec micro-mouvement pour le registre."""
        lines = ["( --- POINTING START --- )"]
        
        # Reset initial et sécurité
        if not use_s_mode:
            lines.append(f"M67 E{e_num} Q0")
        lines.append("G4 P0.1")
        lines.append("M5")
        
        # Positionnement
        lines.append(f"G0 X{offX:.3f} Y{offY:.3f} F3000")
        lines.append("M3")
        
        # Allumage et micro-mouvement (G1 X+0.01) pour forcer l'actualisation
        if use_s_mode:
            lines.append(f"G1 X{offX + 0.01:.3f} F100 S{power:.1f}")
        else:
            lines.append(f"M67 E{e_num} Q{power:.2f}")
            lines.append(f"G1 X{offX + 0.01:.3f} F100")
        
        # Retour au point exact et stabilisation
        lines.append(f"G1 X{offX:.3f}")
        lines.append("G4 P0.1")
        
        # Pause avec ton message personnalisé
        if pause_cmd:
            lines.append(f"{pause_cmd} (Press Cycle Start to continue)")
            
        lines.append("( --- POINTING END --- )")
        return "\n".join(lines) + "\n"
