
"""
A.L.I.G. Project - Core Engine
------------------------------
Image processing and G-Code logic.
"""

import numpy as np
from PIL import Image
import io


class GCodeEngine:
    def __init__(self):
        self.matrix = None
        self.stats = {}
        self.last_gcode_body = []

    def process_image_logic(self, image_path, s, source_img_cache=None):
        x_step = 25.4 / max(1, s["dpi"])
        raster_mode = s.get('raster_mode', "Horizontal")
        img = source_img_cache if source_img_cache else Image.open(image_path).convert('L')
        orig_w, orig_h = img.size
        tw = min(s["width"], 2000)
        th = (tw * orig_h / orig_w)
        w_px = max(2, int(tw / x_step))
        h_px = max(1, int(th / s["line_step"]))
        MAX_TOTAL_PIXELS = 10_000_000
        memory_warning = False
        l_step_val = s["line_step"]

        if w_px * h_px > MAX_TOTAL_PIXELS:
            memory_warning = True
            scale_factor = np.sqrt(MAX_TOTAL_PIXELS / (w_px * h_px))
            w_px = int(w_px * scale_factor)
            h_px = int(h_px * scale_factor)
            if raster_mode == "Horizontal":
                x_step = tw / (w_px - 1) if w_px > 1 else x_step
            else:
                l_step_val = th / (h_px - 1) if h_px > 1 else s["line_step"]

        if s.get("force_width") and raster_mode == "Horizontal":
            x_step = tw / max(1, w_px - 1)

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

        total_dist = h_px * (tw + 2 * s["premove"]) if raster_mode == "Horizontal" else w_px * (th + 2 * s["premove"])
        est_min = total_dist / s["feedrate"]
        latency_mm = (s['feedrate'] * s.get('m67_delay', 0)) / 60000

        return matrix, h_px, w_px, l_step_val, x_step, est_min, memory_warning, img, latency_mm



    def generate_gcode_list(self, matrix, h_px, w_px, l_step, x_st, offX, offY, gc):
        buf = io.StringIO()
        e_num = gc['e_num']
        use_s_mode = gc['use_s_mode']
        ratio = gc['ratio']
        ctrl_max = gc['ctrl_max']
        pre = gc['premove']
        offset_latence = gc['offset_latence']
        raster_mode = gc.get('raster_mode', "Horizontal")

        buf.write(f"G1 F{gc['feedrate']}\n")
        if not use_s_mode:
            buf.write(f"M67 E{e_num} Q0.00\nG4 P0.1\n")

        p_matrix = np.clip(matrix * ratio, 0, ctrl_max)
        len_h, len_w = h_px, w_px
        if raster_mode == "Horizontal":
            outer_range, step_main, step_scan = len_h, l_step, x_st
            axis = "X"
            main_offset, scan_offset = offY, offX
        else:
            outer_range, step_main, step_scan = len_w, x_st, l_step
            axis = "Y"
            main_offset, scan_offset = offX, offY

        real_scan_dist = ((len_w if raster_mode == "Horizontal" else len_h) - 1) * step_scan
        len_row = len_w if raster_mode == "Horizontal" else len_h

        for outer_idx in range(outer_range):
            main_pos = outer_idx * step_main + main_offset
            is_fwd = (outer_idx % 2 == 0)
            scan_dir = 1 if is_fwd else -1
            corr = offset_latence * scan_dir

            if raster_mode == "Horizontal":
                # Accès ligne correctement
                row = p_matrix[len_h - 1 - outer_idx, :]
            else:
                row = p_matrix[:, outer_idx]



            indices_changes = np.where(np.diff(row) != 0)[0] + 1
            indices = np.empty(len(indices_changes) + 2, dtype=np.int32)
            indices[0] = 0
            indices[-1] = len_row - 1
            indices[1:-1] = indices_changes

            scan_start = (0 if is_fwd else real_scan_dist) + scan_offset
            pre_start = scan_start - (pre * scan_dir)

            buf.write(f"{'M67 E' + str(e_num) + ' Q0.00 G1 ' if not use_s_mode else 'G1 '}{'X' if raster_mode=='Horizontal' else 'X'}{pre_start:.4f} {'Y' if raster_mode=='Horizontal' else 'Y'}{main_pos:.4f}\n")
            buf.write(f"{'M67 E' + str(e_num) + ' Q0.00 G1 ' if not use_s_mode else 'G1 '}{axis}{scan_start + corr:.4f}\n")

            for idx in indices:
                grid_idx = idx if is_fwd else (len_row - 1 - idx)
                p_val = row[grid_idx]
                target_scan = grid_idx * step_scan + scan_offset + corr
                if not use_s_mode:
                    buf.write(f"M67 E{e_num} Q{p_val:.2f} G1 {axis}{target_scan:.4f}\n")
                else:
                    buf.write(f"G1 {axis}{target_scan:.4f} S{p_val:.2f}\n")

            pre_end = (real_scan_dist if is_fwd else 0) + scan_offset + (pre * scan_dir)
            buf.write(f"{'M67 E' + str(e_num) + ' Q0.00 G1 ' if not use_s_mode else 'G1 '}{axis}{pre_end:.4f}\n")

        return buf.getvalue()

    def assemble_gcode(self, body, header_custom, footer_custom, settings, metadata):
        e_num = settings['e_num']
        use_s_mode = settings['use_s_mode']
        firing_cmd = metadata['firing_cmd']
        init_safety = "M5 S0\nG4 P0.5" if use_s_mode else f"M67 E{e_num} Q0.00\nG4 P0.2\nM5\nG4 P0.3"

        buf = io.StringIO()
        buf.write(f"( A.L.I.G. v{metadata['version']} )\n")
        buf.write(f"( Mode: {metadata['mode']} )\n")
        buf.write(f"( Firing Mode: {metadata['firing_cmd']} )\n")
        buf.write(f"( Grayscale Levels: {metadata['gray_steps']} )\n")
        buf.write("G21 G90 G17 G94\n")
        buf.write(header_custom + "\n")
        buf.write(init_safety + "\n\n")

        if metadata.get('framing_code'):
            buf.write(metadata['framing_code'] + "\n")
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

    def build_final_gcode(self, matrix, dims, offsets, settings_raw, text_blocks, metadata_raw):
        latency_mm = (settings_raw['feedrate'] * settings_raw['m67_delay']) / 60000

        gc_settings = {
            'e_num': settings_raw['e_num'],
            'use_s_mode': settings_raw['use_s_mode'],
            'ratio': settings_raw['ctrl_max'] / 100.0,
            'ctrl_max': settings_raw['ctrl_max'],
            'premove': settings_raw['premove'],
            'feedrate': settings_raw['feedrate'],
            'offset_latence': latency_mm,
            'raster_mode': settings_raw.get('raster_mode', "Horizontal")
        }

        h_px, w_px, l_step, x_st = dims
        offX, offY = offsets
        gcode_body = self.generate_gcode_list(matrix, h_px, w_px, l_step, x_st, offX, offY, gc_settings)

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
        elif selected_origin == "Custom": offX, offY = -custom_x, -custom_y
        return offX, offY

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

            if config['is_pointing']:
                framing_gcode += self.generate_pointing_gcode(
                    offX, offY, pwr,
                    pause_cmd=config['f_pause'],
                    use_s_mode=config['use_s_mode'],
                    e_num=config['e_num']
                ) + "\n"

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

    def generate_pointing_gcode(self, offX, offY, power, pause_cmd=None, use_s_mode=True, e_num=0):
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
