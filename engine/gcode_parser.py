import re
import numpy as np

class GCodeParser: 
    def __init__(self, stats): 
        """ 
        :param stats: Dictionnaire contenant offX, offY, min_power, rect_h 
        """ 
        self.stats = stats 
        self.offX = stats.get("offX", 0) 
        self.offY = stats.get("offY", 0) 
        self.min_pwr = stats.get("min_power", 0) 
        self.rect_h = stats.get("rect_h", 0) 

    def parse(self, gcode_text): 
        if not gcode_text: 
            return [], 0.0 
             
        points = [] 
        duration_total = 0.0 
         
        curr_x, curr_y = None, None  
        current_f = 1000.0    
        current_pwr = 0.0     

        lines = gcode_text.split('\n') 
         
        for line_idx, line in enumerate(lines, start=1): 
            line_u = line.strip().upper() 
             
            if not line_u or line_u.startswith(';') or line_u.startswith('('): 
                continue 

            # 1. Extraction des paramètres 
            match_f = re.search(r'F(\d+)', line_u) 
            if match_f:  
                current_f = float(match_f.group(1)) 

            match_p = re.search(r'[SQ]([-+]?\d*\.\d+|\d+)', line_u) 
            if match_p:  
                current_pwr = float(match_p.group(1)) 

            # 2. Extraction des coordonnées 
            mx = re.search(r'X([-+]?\d*\.\d+|\d+)', line_u) 
            my = re.search(r'Y([-+]?\d*\.\d+|\d+)', line_u) 

            if mx or my: 
                target_x = float(mx.group(1)) if mx else (curr_x if curr_x is not None else 0.0) 
                target_y = float(my.group(1)) if my else (curr_y if curr_y is not None else 0.0) 
                 
                if curr_x is None: 
                    curr_x, curr_y = target_x, target_y 
                    continue 

                pwr_to_store = current_pwr if current_pwr > self.min_pwr else 0.0 

                # Logique conservée sans le multiplicateur scale
                s_px = (curr_x - self.offX)
                t_px = (target_x - self.offX)
                s_py = self.rect_h - (curr_y - self.offY)
                t_py = self.rect_h - (target_y - self.offY)
                 
                dist = np.hypot(target_x - curr_x, target_y - curr_y) 
                 
                if dist > 0.001: 
                    seg_duration = dist / (current_f / 60.0) 
                    duration_total += seg_duration 
                     
                    num_steps = max(2, int(seg_duration * 60))  
                    for j in range(num_steps): 
                        ratio = j / num_steps 
                        points.append((s_px + (t_px - s_px) * ratio,  
                                       s_py + (t_py - s_py) * ratio,  
                                       pwr_to_store, 
                                       line_idx))  
                 
                points.append((t_px, t_py, pwr_to_store, line_idx)) 
                curr_x, curr_y = target_x, target_y 

        return points, duration_total