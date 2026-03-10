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
    
    def generate_linestep_calibration(self, settings):
        buf = io.StringIO()

        # --- Paramètres ---
        pwr          = float(settings.get("power", 10))
        feed         = float(settings.get("feedrate", 1000))
        min_step     = float(settings.get("min_step", 0.05))
        central_mult = float(settings.get("multiplier", 2.0))
        latency_ms   = float(settings.get("latency", 0.0))
        scan_mode    = settings.get("scan_mode", "Horizontal").lower()
        use_s        = settings.get("use_s_mode", True)
        e_num        = settings.get("e_num", 0)

        # M3 ou M4 selon le réglage machine (firing_mode = "M3/M5" ou "M4/M5")
        firing_mode = settings.get("firing_mode", "M3/M5")
        firing_cmd  = firing_mode.split("/")[0]   # "M3" ou "M4"

        dist_offset = (feed * latency_ms) / 60000.0
        multipliers = [max(0.01, central_mult + i * 0.5) for i in range(-2, 3)]

        def write_move(x, y, power, is_g1=True):
            cmd = "G1" if is_g1 else "G0"
            if use_s:
                buf.write(f"{cmd} X{x:.3f} Y{y:.3f} S{power:.2f}\n")
            else:
                buf.write(f"M67 E{e_num} Q{power:.2f} {cmd} X{x:.3f} Y{y:.3f}\n")

        # --- Entête ---
        buf.write(f"( --- ALIG LINESTEP : {scan_mode.upper()} --- )\n")
        buf.write("G21 G90 G17 G94\n")
        buf.write(f"G1 F{feed}\n")

        # Allumage laser une seule fois avant tous les blocs
        if use_s:
            buf.write(f"{firing_cmd} S0\n")
        else:
            buf.write(f"{firing_cmd}\n")
            buf.write(f"M67 E{e_num} Q0.00\n")

        offset_base = 0.0
        for m in multipliers:
            step = min_step * m
            buf.write(f"\n( Block Mult x{m:.2f} - Step {step:.3f}mm )\n")

            if "horizontal" in scan_mode:
                y = 0.0
                while y <= 4.0:
                    # Aller (gauche → droite)
                    buf.write(f"G0 X-2 Y{offset_base + y:.4f}\n")
                    write_move(0.0  - dist_offset, offset_base + y, 0)
                    write_move(10.0 - dist_offset, offset_base + y, pwr)
                    write_move(12.0,                offset_base + y, 0)
                    y += step
                    if y > 4.0:
                        break
                    # Retour (droite → gauche)
                    buf.write(f"G0 X12 Y{offset_base + y:.4f}\n")
                    write_move(10.0 + dist_offset,  offset_base + y, 0)
                    write_move(0.0  + dist_offset,  offset_base + y, pwr)
                    write_move(-2.0,                offset_base + y, 0)
                    y += step
                offset_base += 6.0

            elif "vertical" in scan_mode:
                x = 0.0
                while x <= 10.0:
                    # Monter
                    buf.write(f"G0 X{offset_base + x:.4f} Y-2\n")
                    write_move(offset_base + x, 0.0 - dist_offset, 0)
                    write_move(offset_base + x, 4.0 - dist_offset, pwr)
                    write_move(offset_base + x, 6.0,                0)
                    x += step
                    if x > 10.0:
                        break
                    # Descendre
                    buf.write(f"G0 X{offset_base + x:.4f} Y6\n")
                    write_move(offset_base + x, 4.0 + dist_offset, 0)
                    write_move(offset_base + x, 0.0 + dist_offset, pwr)
                    write_move(offset_base + x, -2.0,               0)
                    x += step
                offset_base += 12.0

        # Extinction laser une seule fois après tous les blocs
        buf.write("\nM5\n")
        if not use_s:
            buf.write(f"M67 E{e_num} Q0.00\n")
        buf.write("M30\n")

        return buf.getvalue()
