import numpy as np
import gc

class GCodeParser:
    def __init__(self, stats):
        self.stats = stats
        self.offX = stats.get("offX", 0)
        self.offY = stats.get("offY", 0)
        self.min_pwr = stats.get("min_power", 0)
        self.rect_h = stats.get("rect_h", 0)

    def parse(self, gcode_text):
        if not gcode_text:
<<<<<<< HEAD
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)
=======
            return None, 0.0
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8

        lines = gcode_text.splitlines()
        n_lines = len(lines)
        if n_lines == 0:
<<<<<<< HEAD
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)

        # Désactive le GC temporairement pour optimiser la boucle
        gc_was_enabled = gc.isenabled()
        gc.disable()

        # Pré-allocation (X, Y, Power, LineIndex, Feedrate)
=======
            return None, 0.0

        # Désactive le GC temporairement pour éviter les pauses
        gc_was_enabled = gc.isenabled()
        gc.disable()

        # Pré-allocation maximale
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
        points_array = np.zeros((n_lines, 5), dtype=np.float32)
        idx_point = 0

        curr_x = curr_y = 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

<<<<<<< HEAD
        # Initialisation des limites avec l'infini pour capturer les premières valeurs
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

=======
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
        for line_idx, line in enumerate(lines, start=1):
            line = line.strip().upper()
            if not line or line.startswith(('(', ';')):
                continue

            changed = False

<<<<<<< HEAD
            # --- Extraction puissance (S ou Q) ---
=======
            # --- Extraction puissance ---
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            for char_p in ('Q', 'S'):
                pos = line.find(char_p)
                if pos != -1:
                    start = pos + 1
                    end = start
                    while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                        end += 1
                    try:
                        curr_pwr = float(line[start:end])
                        break
<<<<<<< HEAD
                    except: pass

            # --- Extraction feedrate (F) ---
=======
                    except:
                        pass

            # --- Extraction feedrate ---
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            pos_f = line.find('F')
            if pos_f != -1:
                start = pos_f + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try:
                    curr_f = float(line[start:end])
<<<<<<< HEAD
                except: pass

            # --- Extraction X ---
=======
                except:
                    pass

            # --- Extraction X/Y ---
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            pos_x = line.find('X')
            if pos_x != -1:
                start = pos_x + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try:
                    curr_x = float(line[start:end])
                    changed = True
<<<<<<< HEAD
                except: pass

            # --- Extraction Y ---
=======
                except:
                    pass

>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            pos_y = line.find('Y')
            if pos_y != -1:
                start = pos_y + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try:
                    curr_y = float(line[start:end])
                    changed = True
<<<<<<< HEAD
                except: pass

            if changed:
                # MISE À JOUR DES BORNES RÉELLES (Indispensable pour la simulation)
                if curr_x < min_x: min_x = curr_x
                if curr_x > max_x: max_x = curr_x
                if curr_y < min_y: min_y = curr_y
                if curr_y > max_y: max_y = curr_y

                # Stockage des coordonnées relatives au projet
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                px = curr_x - self.offX
                py = curr_y - self.offY # Système cartésien pur
=======
                except:
                    pass

            if changed:
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                px = curr_x - self.offX
                py = self.rect_h - (curr_y - self.offY)
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8

                points_array[idx_point, :] = (px, py, pwr_to_store, float(line_idx), curr_f)
                idx_point += 1

        if gc_was_enabled:
            gc.enable()

        if idx_point == 0:
<<<<<<< HEAD
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)

        # On retourne le tuple des limites : (min_x, max_x, min_y, max_y)
        limits = (min_x, max_x, min_y, max_y)
        
        return points_array[:idx_point], 0.0, limits
=======
            return None, 0.0

        return points_array[:idx_point], 0.0
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8


    def parseScmd(self, gcode_text):
        """
        Parser pour mode S
        """
        lines = gcode_text.splitlines()
        n_lines = len(lines)
        points_array = np.zeros((n_lines, 5), dtype=np.float32)
        idx_point = 0

        curr_x = curr_y = 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

        for line_idx, line in enumerate(lines, start=1):
            line = line.strip().upper()
            if not line or line.startswith(('(', ';')):
                continue

            changed = False

            # S uniquement, mais on garde Q pour sécurité
            for char_p in ('S', 'Q'):
                pos = line.find(char_p)
                if pos != -1:
                    start = pos + 1
                    end = start
                    while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                        end += 1
                    try:
                        curr_pwr = float(line[start:end])
                        break
                    except: pass

            # Feedrate
            pos_f = line.find('F')
            if pos_f != -1:
                start = pos_f + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try: curr_f = float(line[start:end])
                except: pass

            # Coordonnées
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

            if changed:
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                px = curr_x - self.offX
                py = self.rect_h - (curr_y - self.offY)
                points_array[idx_point] = (px, py, pwr_to_store, float(line_idx), curr_f)
                idx_point += 1

        if idx_point == 0:
            return None, 0.0

        return points_array[:idx_point], 0.0
    
    def parseScmd(self, gcode_text):
        """
        Parser pour mode S
        """
        lines = gcode_text.splitlines()
        n_lines = len(lines)
        points_array = np.zeros((n_lines, 5), dtype=np.float32)
        idx_point = 0

        curr_x = curr_y = 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

        for line_idx, line in enumerate(lines, start=1):
            line = line.strip().upper()
            if not line or line.startswith(('(', ';')):
                continue

            changed = False

            # S ou Q pour sécurité
            for char_p in ('S', 'Q'):
                pos = line.find(char_p)
                if pos != -1:
                    start = pos + 1
                    end = start
                    while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                        end += 1
                    try:
                        curr_pwr = float(line[start:end])
                        break
                    except: pass

            # Feedrate
            pos_f = line.find('F')
            if pos_f != -1:
                start = pos_f + 1
                end = start
                while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                    end += 1
                try: curr_f = float(line[start:end])
                except: pass

            # Coordonnées
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

            if changed:
                # Mode Q: on ignore les S, on ne prend que la valeur Q
                if 'Q' in line:
                    pos_q = line.find('Q')
                    start = pos_q + 1
                    end = start
                    while end < len(line) and (line[end].isdigit() or line[end] in '.-+'):
                        end += 1
                    try:
                        curr_pwr = float(line[start:end])
                    except: pass
                else:
                    curr_pwr = 0.0

                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                px = curr_x - self.offX
                py = self.rect_h - (curr_y - self.offY)
                points_array[idx_point] = (px, py, pwr_to_store, float(line_idx), curr_f)
                idx_point += 1

        if idx_point == 0:
            return None, 0.0

        return points_array[:idx_point], 0.0
    

    def parse_auto(self, gcode_text, mode='S'):
        """
        Wrapper: détecte le mode et appelle le parser spécialisé.
        mode: 'S' ou 'Q'
        """
        if not gcode_text:
            return None, 0.0
        if mode.upper() == 'S':
            return self.parseScmd(gcode_text)
        else:
            return self.parseQcmd(gcode_text)