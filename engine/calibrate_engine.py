import io


class CalibrateEngine:
    def __init__(self):
        pass

    def generate_latency_calibration(self, settings):
        """
        Génère un G-Code de test de latence compatible Mach4.
        Prend en compte la résolution Max du contrôleur.
        """
        buf = io.StringIO()
        
        # --- EXTRACTION ET CALCULS ---
        # On récupère la puissance choisie et la résolution max configurée
        pwr = settings.get("power", 100)
        max_res = settings.get("max_value", 1000)
        
        # Sécurité : on s'assure de ne pas dépasser la valeur max configurée
        pwr = min(float(pwr), float(max_res))
        
        feed = settings.get("feedrate", 3000)
        use_s = settings.get("use_s_mode", True)
        e_num = settings.get("e_num", 0)
        latency_ms = settings.get("latency", 0.0)
        
        # Calcul du décalage (vitesse mm/min -> mm/ms)
        dist_offset = (feed * latency_ms) / 60000.0

        def write_move(x=None, y=None, power_val=None, is_g1=True):
            cmd = "G1" if is_g1 else "G0"
            coords = ""
            if x is not None: coords += f" X{x:.3f}"
            if y is not None: coords += f" Y{y:.3f}"
            
            if not coords:
                if power_val is not None:
                    if use_s:
                        buf.write(f"S{power_val:.2f}\n")
                    else:
                        buf.write(f"M67 E{e_num} Q{power_val:.2f}\n")
                return

            if power_val is not None:
                if use_s:
                    buf.write(f"{cmd}{coords} S{power_val:.2f}\n")
                else:
                    buf.write(f"M67 E{e_num} Q{power_val:.2f} {cmd}{coords}\n")
            else:
                buf.write(f"{cmd}{coords}\n")

        # --- DEBUT G-CODE ---
        buf.write(f"( --- ALIG LATENCY TEST --- )\n")
        buf.write(f"( Power: {pwr} )\n")
        buf.write(f"( Feedrate: {feed} mm-min | Offset: {dist_offset:.4f}mm )\n")
        
        buf.write("G21 G90 G17 G94\n")
        # On remplace le header par un S0 initial sécurisé
        buf.write("M3 S0\n") 
        buf.write(f"G1 F{feed}\n\n")

        # 1. TRAIT VERTICAL CENTRAL
        buf.write("( Central Reference Line )\n")
        write_move(x=0, y=-2, is_g1=False) 
        buf.write("G4 P0.5\n") # Petite pause pour marquer le début
        write_move(y=12, power_val=pwr)  
        write_move(power_val=0)

        # 2. ÉTAGE ALLER (Gauche -> Droite)
        corr_fwd = -dist_offset 
        buf.write(f"\n( Stage 1: Left to Center - Corr: {corr_fwd:.3f} )\n")
        for y_off in range(0, 51, 10): 
            y_pos = y_off / 10.0
            write_move(x=-25, y=y_pos, is_g1=False)
            write_move(x=-10, power_val=0)
            write_move(x=(0.0 + corr_fwd), power_val=pwr) 
            write_move(x=0.5 + corr_fwd, power_val=0)
            write_move(x=5, power_val=0)

        # 3. ÉTAGE RETOUR (Droite -> Gauche)
        corr_rev = dist_offset
        buf.write(f"\n( Stage 2: Right to Center - Corr: {corr_rev:.3f} )\n")
        for y_off in range(60, 111, 10): 
            y_pos = y_off / 10.0
            write_move(x=25, y=y_pos, is_g1=False)
            write_move(x=10, power_val=0)
            write_move(x=(0.0 + corr_rev), power_val=pwr) 
            write_move(x=-0.5 + corr_rev, power_val=0)
            write_move(x=-5, power_val=0)

        # --- FIN G-CODE ---
        buf.write("\n( Cleanup )\n")
        buf.write("M5\n")
        if not use_s: buf.write(f"M67 E{e_num} Q0\n")
        else: buf.write("S0\n")
        buf.write("M30\n")
        
        return buf.getvalue()