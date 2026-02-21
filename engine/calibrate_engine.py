import io

class CalibrateEngine:
    def __init__(self):
        pass

    def generate_latency_calibration(self, settings):
        """
        Génère un G-Code de test de latence.
        M67 est placé avant le mouvement, S est placé sur la même ligne.
        """
        buf = io.StringIO()
        
        # Extraction des paramètres
        pwr = settings.get("power", 20)
        feed = settings.get("feedrate", 3000)
        use_s = settings.get("use_s_mode", True)
        e_num = settings.get("e_num", 0)
        
        def write_move(x=None, y=None, power_val=None, is_g1=True):
            """
            Gère l'écriture d'une ligne de mouvement en respectant 
            les spécificités M67 (avant) vs S (pendant).
            """
            cmd = "G1" if is_g1 else "G0"
            coords = ""
            if x is not None: coords += f" X{x}"
            if y is not None: coords += f" Y{y}"
            
            if power_val is not None:
                if use_s:
                    # Mode S : On l'ajoute sur la même ligne
                    buf.write(f"{cmd}{coords} S{power_val:.2f}\n")
                else:
                    # Mode M67 : On l'écrit AVANT le mouvement
                    buf.write(f"M67 E{e_num} Q{power_val:.2f}\n")
                    buf.write(f"{cmd}{coords}\n")
            else:
                # Mouvement simple sans changement de puissance
                buf.write(f"{cmd}{coords}\n")

        # --- DEBUT G-CODE ---
        buf.write("( --- LATENCY CALIBRATION START --- )\n")
        buf.write("G21 G90 G17 G94\n")
        buf.write(settings.get("header", "M3 S0") + "\n")
        buf.write("M3\n") 
        buf.write(f"G1 F{feed}\n\n")

        # 1. TRAIT VERTICAL CENTRAL
        buf.write("( Central Reference Line )\n")
        write_move(x=0, y=0, is_g1=False) # G0 X0 Y0
        buf.write("G4 P2\n") # Pause de 2 secondes pour éviter tremblements
        write_move(y=10, power_val=pwr)  # G1 Y10 avec gestion S/M67
        write_move(power_val=0)          # Extinction sur place

        # 2. PREMIER ÉTAGE (Mouvement vers la Droite)
        buf.write("\n( Stage 1: Left to Center - Rightward )\n")
        for y_off in range(0, 51, 10): 
            y_pos = y_off / 10.0
            write_move(x=-15, y=y_pos, is_g1=False) # Positionnement
            write_move(x=-10, power_val=0)          # Sécurité Off
            write_move(x=0, power_val=pwr)           # Allumage -> Centre
            write_move(x=0.1, power_val=0)           # Extinction

        # 3. SECOND ÉTAGE (Mouvement vers la Gauche)
        buf.write("\n( Stage 2: Right to Center - Leftward )\n")
        for y_off in range(50, 101, 10): 
            y_pos = y_off / 10.0
            write_move(x=15, y=y_pos, is_g1=False)
            write_move(x=10, power_val=0)
            write_move(x=0, power_val=pwr)
            write_move(x=-0.1, power_val=0)

        # --- FIN G-CODE ---
        buf.write("\n( Cleanup )\n")
        buf.write("M5\n")
        if not use_s: buf.write(f"M67 E{e_num} Q0\n")
        else: buf.write("S0\n")
        buf.write(settings.get("footer", "M30") + "\n")
        
        return buf.getvalue()