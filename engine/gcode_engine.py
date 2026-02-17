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
        Pure image processing logic. 
        's' is a dictionary of settings.
        """
        x_step = 25.4 / max(1, s["dpi"])
        
        # Gestion du cache d'image
        if source_img_cache is None:
            img = Image.open(image_path).convert('L')
        else:
            img = source_img_cache
        
        orig_w, orig_h = img.size
        tw = min(s["width"], 2000) # Sécurité 2000mm

        w_px = max(2, int(tw / x_step))
        h_px = max(1, int((tw * orig_h / orig_w) / s["line_step"]))

        # Sécurité mémoire
        MAX_TOTAL_PIXELS = 10000000 
        current_pixels = w_px * h_px
        memory_warning = False

        if current_pixels > MAX_TOTAL_PIXELS:
            memory_warning = True
            scale_factor = np.sqrt(MAX_TOTAL_PIXELS / current_pixels)
            w_px = int(w_px * scale_factor)
            h_px = int(h_px * scale_factor)
            # Recalcul des pas si réduction
            x_step = tw / (w_px - 1) if w_px > 1 else x_step
            l_step_val = (tw * orig_h / orig_w) / h_px if h_px > 0 else s["line_step"]
        else:
            l_step_val = s["line_step"]

        # Option Force Exact Width
        if s.get("force_width"):
            x_step = tw / max(1, (w_px - 1))

        # Traitement image
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
        
        # Quantification
        if s["gray_steps"] < 256:
            range_p = s["max_p"] - s["min_p"]
            if range_p > 0:
                matrix = s["min_p"] + (np.round((matrix - s["min_p"]) / range_p * (s["gray_steps"] - 1)) / (s["gray_steps"] - 1) * range_p)

        matrix[arr < 0.005] = 0
        
        # Estimation temps
        total_dist = h_px * (tw + (2 * s["premove"]))
        est_min = total_dist / s["feedrate"]

        return matrix, h_px, w_px, l_step_val, x_step, est_min, memory_warning, img



    def generate_gcode_list(self, matrix, h_px, w_px, l_step, x_st, offX, offY, gc):
        """
        Génère les lignes de G-Code de mouvement.
        """
        gcode = []
        
        # Extraction des paramètres du dictionnaire
        e_num = gc['e_num']
        use_s_mode = gc['use_s_mode']
        ratio = gc['ratio']
        ctrl_max = gc['ctrl_max']
        pre = gc['premove']
        f_int = gc['feedrate']
        offset_latence = gc['offset_latence']

        # 1. Vitesse de travail initiale
        gcode.append(f"G1 F{f_int}")
        
        # 2. Synchronisation initiale pour le mode M67
        if not use_s_mode:
            gcode.append(f"M67 E{e_num} Q0.00")
            gcode.append("G4 P0.1 (Sync before first move)")

        real_w = (w_px - 1) * x_st

        for row_idx in range(h_px):
            y_pos = (row_idx * l_step) + offY
            py = (h_px - 1) - row_idx 
            is_fwd = (row_idx % 2 == 0)
            x_dir = 1 if is_fwd else -1
            corr = offset_latence * x_dir
            
            # Calcul des limites de ligne
            x_img_start = (offX if is_fwd else real_w + offX)
            x_img_end = (real_w + offX if is_fwd else offX)
            x_pre_start = x_img_start - (pre * x_dir)
            x_pre_end = x_img_end + (pre * x_dir)

            # --- ÉTAPE A : POSITIONNEMENT INITIAL (Saut de ligne) ---
            if not use_s_mode:
                gcode.append(f"M67 E{e_num} Q0.00 G1 X{x_pre_start:.3f} Y{y_pos:.4f}")
            else:
                gcode.append(f"G1 X{x_pre_start:.3f} Y{y_pos:.4f} S0")
            
            current_x = x_pre_start

            # --- ÉTAPE B : PRE-MOVE (OVERSCAN D'ENTRÉE) ---
            target_edge = x_img_start + corr
            if abs(target_edge - current_x) > 0.0001:
                if not use_s_mode:
                    gcode.append(f"M67 E{e_num} Q0.00 G1 X{target_edge:.4f}")
                else:
                    gcode.append(f"G1 X{target_edge:.4f} S0")
                current_x = target_edge

            # --- ÉTAPE C : GRAVURE DE L'IMAGE ---
            row_data = matrix[py, :]
            x_range = list(range(w_px)) if is_fwd else list(range(w_px - 1, -1, -1))
            
            # Valeur initiale du premier pixel de la ligne
            last_p = max(0, min(row_data[x_range[0]] * ratio, ctrl_max))

            for i in range(1, len(x_range)):
                px = x_range[i]
                p_val = max(0, min(row_data[px] * ratio, ctrl_max))
                
                # On ne génère une ligne que si la puissance change (Clustering)
                if abs(p_val - last_p) > 0.0001:
                    target_x = (x_range[i] * x_st) + offX + corr
                    
                    if abs(target_x - current_x) > 0.00001:
                        if not use_s_mode:
                            gcode.append(f"M67 E{e_num} Q{last_p:.2f} G1 X{target_x:.4f}")
                        else:
                            gcode.append(f"G1 X{target_x:.4f} S{last_p:.2f}")
                        
                        current_x = target_x
                        last_p = p_val

            # --- ÉTAPE D : FERMETURE BORD IMAGE ---
            final_img_x = x_img_end + corr
            if abs(final_img_x - current_x) > 0.00001:
                if not use_s_mode:
                    gcode.append(f"M67 E{e_num} Q{last_p:.2f} G1 X{final_img_x:.4f}")
                else:
                    gcode.append(f"G1 X{final_img_x:.4f} S{last_p:.2f}")
                current_x = final_img_x

            # --- ÉTAPE E : OVERSCAN FINAL HACHÉ ---
            overscan_step = x_st * 4
            dist_to_go = abs(x_pre_end - current_x)
            num_steps_overscan = int(dist_to_go / overscan_step)
            
            for _ in range(num_steps_overscan):
                current_x += (overscan_step * x_dir)
                if not use_s_mode:
                    gcode.append(f"M67 E{e_num} Q0.00 G1 X{current_x:.4f}")
                else:
                    gcode.append(f"G1 X{current_x:.4f} S0")

            # --- ÉTAPE F : POSITIONNEMENT FINAL RÉEL ---
            if abs(x_pre_end - current_x) > 0.0001:
                if not use_s_mode:
                    gcode.append(f"M67 E{e_num} Q0.00 G1 X{x_pre_end:.4f}")
                else:
                    gcode.append(f"G1 X{x_pre_end:.4f} S0")

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
        gc_settings = {
            'e_num': settings_raw['e_num'],
            'use_s_mode': settings_raw['use_s_mode'],
            'ratio': settings_raw['ctrl_max'] / 100.0,
            'ctrl_max': settings_raw['ctrl_max'],
            'premove': settings_raw['premove'],
            'feedrate': settings_raw['feedrate'],
            'offset_latence': (settings_raw['feedrate'] * settings_raw['m67_delay']) / 60000 
        }

        # 2. Génération du corps
        h_px, w_px, l_step, x_st = dims
        offX, offY = offsets
        gcode_body = self.generate_gcode_list(matrix, h_px, w_px, l_step, x_st, offX, offY, gc_settings)

        # 3. Assemblage avec Header/Footer
        return self.assemble_gcode(
            gcode_body, 
            text_blocks['header'],
            text_blocks['footer'],
            gc_settings,
            metadata_raw
        )

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
