import numpy as np

class GCodeParser: 
    def __init__(self, stats): 
        self.stats = stats 
        self.offX = stats.get("offX", 0) 
        self.offY = stats.get("offY", 0) 
        self.min_pwr = stats.get("min_power", 0) 
        self.rect_h = stats.get("rect_h", 0) 

    def parse(self, gcode_text): 
        if not gcode_text: 
            return None, 0.0 
             
        lines = gcode_text.splitlines()
        points = []
        
        # États persistants
        curr_x, curr_y = 0.0, 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

        for line_idx, line in enumerate(lines, start=1):
            line = line.strip().upper()
            if not line or line.startswith(('(', ';')): continue

            changed = False
            
            # --- 1. Extraction de la PUISSANCE (S ou Q) ---
            # On cherche Q (M67) ou S (Standard)
            for char_p in ('Q', 'S'):
                pos = line.find(char_p)
                if pos != -1:
                    start = pos + 1
                    end = start
                    while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                        end += 1
                    try:
                        curr_pwr = float(line[start:end])
                        break # On a trouvé la puissance
                    except: pass

            # --- 2. Extraction du FEEDRATE (F) ---
            pos_f = line.find('F')
            if pos_f != -1:
                start = pos_f + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try: curr_f = float(line[start:end])
                except: pass

            # --- 3. Extraction des COORDONNÉES (X et Y) ---
            # Extraction X
            pos_x = line.find('X')
            if pos_x != -1:
                start = pos_x + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try:
                    curr_x = float(line[start:end])
                    changed = True
                except: pass

            # Extraction Y
            pos_y = line.find('Y')
            if pos_y != -1:
                start = pos_y + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try:
                    curr_y = float(line[start:end])
                    changed = True
                except: pass
            
            # On n'ajoute un point que si un mouvement (X ou Y) est détecté
            if changed:
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                
                # Conversion directe en coordonnées écran (Pixel)
                px = curr_x - self.offX
                py = self.rect_h - (curr_y - self.offY)
                
                points.append((px, py, pwr_to_store, float(line_idx), curr_f))

        if not points:
            return None, 0.0

        # Conversion unique en NumPy array (le secret de la performance)
        return np.array(points, dtype=np.float32), 0.0