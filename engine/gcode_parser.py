import numpy as np
import gc


class GCodeParser:
    def __init__(self, stats):
        self.stats   = stats
        self.offX    = stats.get("offX", 0)
        self.offY    = stats.get("offY", 0)
        self.min_pwr = stats.get("min_power", 0)
        self.rect_h  = stats.get("rect_h", 0)

    @staticmethod
    def _extract(line, char):
        """Extrait la valeur numérique qui suit `char`. Retourne (valeur, True) ou (None, False)."""
        pos = line.find(char)
        if pos == -1:
            return None, False
        s = e = pos + 1
        while e < len(line) and (line[e].isdigit() or line[e] in '.-+'):
            e += 1
        if e > s:
            try:
                return float(line[s:e]), True
            except ValueError:
                pass
        return None, False

    @staticmethod
    def _is_g0(line):
        """True si la ligne contient un G0 (déplacement rapide, pas G0.x)."""
        idx = line.find('G0')
        if idx == -1:
            return False
        after = line[idx + 2] if idx + 2 < len(line) else ' '
        return after in (' ', '\t', '') or (after.isdigit() and after != '.')

    def parse(self, gcode_text):
        """Parse principal — retourne (points_array, 0.0, limits).

        Corrections vs version précédente :
          - G0 : position mémorisée, puissance forcée à 0, EXCLUS des bounds.
            Les overscan (ex: X=-2) ne gonflent plus le cadre de rendu.
          - parseScmd en double supprimé.
          - parseQcmd ajouté (alias propre).
        """
        if not gcode_text:
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)

        lines   = gcode_text.splitlines()
        n_lines = len(lines)
        if n_lines == 0:
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)

        gc_was_enabled = gc.isenabled()
        gc.disable()

        points_array = np.zeros((n_lines * 2, 5), dtype=np.float32)
        idx_point = 0

        curr_x = curr_y = 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        for line_idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip().upper()
            if not line or line.startswith(('(', ';')):
                continue

            is_rapid      = self._is_g0(line)
            changed       = False
            power_changed = False

            # ── puissance (Q prioritaire sur S) ───────────────────────────
            for char_p in ('Q', 'S'):
                val, found = self._extract(line, char_p)
                if found:
                    # G0 : on force la puissance à 0 même si Q/S est présent
                    effective = 0.0 if is_rapid else val
                    if effective != curr_pwr:
                        curr_pwr      = effective
                        power_changed = True
                    break

            # ── feedrate ──────────────────────────────────────────────────
            val_f, found_f = self._extract(line, 'F')
            if found_f:
                curr_f = val_f

            # ── coordonnées ───────────────────────────────────────────────
            val_x, found_x = self._extract(line, 'X')
            if found_x:
                curr_x  = val_x
                changed = True

            val_y, found_y = self._extract(line, 'Y')
            if found_y:
                curr_y  = val_y
                changed = True

            # ── enregistrement ────────────────────────────────────────────
            if changed or power_changed:
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0

                # Bounds : tous les mouvements G1 (pas les G0 d'overscan)
                # On inclut les Q=0 de début/fin de ligne car ils définissent
                # la vraie largeur du passage laser (nécessaire pour le buffer renderer)
                if changed and not is_rapid:
                    if curr_x < min_x: min_x = curr_x
                    if curr_x > max_x: max_x = curr_x
                    if curr_y < min_y: min_y = curr_y
                    if curr_y > max_y: max_y = curr_y
                px = curr_x - self.offX
                py = curr_y - self.offY

                if idx_point < points_array.shape[0]:
                    points_array[idx_point, :] = (px, py, pwr_to_store,
                                                   float(line_idx), curr_f)
                    idx_point += 1

        if gc_was_enabled:
            gc.enable()

        if idx_point == 0:
            return None, 0.0, (0.0, 0.0, 0.0, 0.0)

        # Fallback si aucun G1 trouvé (gcode sans laser)
        if min_x == float('inf'):
            pts  = points_array[:idx_point]
            min_x, max_x = float(pts[:, 0].min()), float(pts[:, 0].max())
            min_y, max_y = float(pts[:, 1].min()), float(pts[:, 1].max())

        return points_array[:idx_point], 0.0, (min_x, max_x, min_y, max_y)

    # ──────────────────────────────────────────────────────────────────────────

    def parseScmd(self, gcode_text):
        """Parser mode S — repère image (Y inversé via rect_h)."""
        lines        = gcode_text.splitlines()
        n_lines      = len(lines)
        points_array = np.zeros((n_lines, 5), dtype=np.float32)
        idx_point    = 0

        curr_x = curr_y = 0.0
        curr_f = 1000.0
        curr_pwr = 0.0

        for line_idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip().upper()
            if not line or line.startswith(('(', ';')):
                continue

            is_rapid = self._is_g0(line)
            changed  = False

            for char_p in ('S', 'Q'):
                val, found = self._extract(line, char_p)
                if found:
                    curr_pwr = 0.0 if is_rapid else val
                    break

            val_f, found_f = self._extract(line, 'F')
            if found_f:
                curr_f = val_f

            val_x, found_x = self._extract(line, 'X')
            if found_x:
                curr_x  = val_x
                changed = True

            val_y, found_y = self._extract(line, 'Y')
            if found_y:
                curr_y  = val_y
                changed = True

            if changed and not is_rapid:
                pwr_to_store = curr_pwr if curr_pwr > self.min_pwr else 0.0
                px = curr_x - self.offX
                py = self.rect_h - (curr_y - self.offY)
                points_array[idx_point] = (px, py, pwr_to_store,
                                            float(line_idx), curr_f)
                idx_point += 1

        if idx_point == 0:
            return None, 0.0
        return points_array[:idx_point], 0.0

    def parseQcmd(self, gcode_text):
        """Parser mode Q — alias propre de parseScmd (Q déjà géré dedans)."""
        return self.parseScmd(gcode_text)

    def parse_auto(self, gcode_text, mode='S'):
        """Wrapper de détection automatique. mode: 'S' ou 'Q'."""
        if not gcode_text:
            return None, 0.0
        if mode.upper() == 'Q':
            return self.parseQcmd(gcode_text)
        return self.parseScmd(gcode_text)
