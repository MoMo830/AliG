import io

class CalibrateEngine:
    def __init__(self):
        pass

    def generate_latency_calibration(self, settings):
        """
        Génère un G-Code de test de latence compatible Mach4.
        Format M67 : M67 E{num} Q{pwr} G1 X{x} Y{y}
        """
        buf = io.StringIO()
        
        # Extraction des paramètres
        pwr = settings.get("power", 20)
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
            
            # 1. Cas sans mouvement (changement de puissance seule)
            if not coords:
                if power_val is not None:
                    if use_s:
                        buf.write(f"S{power_val:.2f}\n")
                    else:
                        buf.write(f"M67 E{e_num} Q{power_val:.2f}\n")
                return # Sécurité : évite d'écrire un G1 seul

            # 2. Cas avec mouvement
            if power_val is not None:
                if use_s:
                    # Format standard S-Mode : G1 X.. Y.. S..
                    buf.write(f"{cmd}{coords} S{power_val:.2f}\n")
                else:
                    # Format demandé pour Mach4 : M67 E.. Q.. G1 X.. Y..
                    buf.write(f"M67 E{e_num} Q{power_val:.2f} {cmd}{coords}\n")
            else:
                # Mouvement simple
                buf.write(f"{cmd}{coords}\n")

        # --- DEBUT G-CODE ---
        # Nettoyage des commentaires pour Mach4 (pas de caractère '|')
        buf.write(f"( --- LATENCY CALIBRATION START - Offset: {dist_offset:.4f}mm --- )\n")
        buf.write("G21 G90 G17 G94\n")
        buf.write(settings.get("header", "M3 S0").replace("|", "-") + "\n")
        buf.write("M3\n") 
        buf.write(f"G1 F{feed}\n\n")

        # On utilise une valeur absolue pour éviter les doubles signes '--'
        abs_offset = abs(dist_offset)

        # 1. TRAIT VERTICAL CENTRAL
        buf.write("( Central Reference Line )\n")
        write_move(x=0, y=-2, is_g1=False) 
        buf.write("G4 P1.0\n") 
        write_move(y=12, power_val=pwr)  
        write_move(power_val=0)

        # 2. PREMIER ÉTAGE (Aller : Gauche -> Droite | scan_dir = 1)
        corr_fwd = -dist_offset 
        buf.write(f"\n( Stage 1: Left to Center - Target X0 - Corr: {corr_fwd:.3f} )\n")
        for y_off in range(0, 51, 10): 
            y_pos = y_off / 10.0
            
            # Positionnement initial loin à gauche
            # On part de X-25 pour avoir 10mm de zone morte + 15mm de stabilisation
            write_move(x=-25, y=y_pos, is_g1=False)
            
            # --- PHASE DE STABILISATION (Premove) ---
            # On lance le mouvement à vitesse constante bien avant le point d'intérêt
            write_move(x=-10, power_val=0) # S'assure que le laser est éteint
            
            # --- ZONE DE TEST (Vitesse stabilisée) ---
            # On traverse X0 avec la correction appliquée
            write_move(x=(0.0 + corr_fwd), power_val=pwr) 
            
            # On continue après le trait pour simuler la fin du pixel
            write_move(x=0.5 + corr_fwd, power_val=0)
            
            # Overscan de sortie pour freiner en douceur
            write_move(x=5, power_val=0)

        # 3. SECOND ÉTAGE (Retour : Droite -> Gauche | scan_dir = -1)
        corr_rev = dist_offset
        buf.write(f"\n( Stage 2: Right to Center - Target X0 - Corr: {corr_rev:.3f} )\n")
        for y_off in range(60, 111, 10): 
            y_pos = y_off / 10.0
            
            # Positionnement initial loin à droite
            write_move(x=25, y=y_pos, is_g1=False)
            
            # --- PHASE DE STABILISATION (Premove) ---
            write_move(x=10, power_val=0)
            
            # --- ZONE DE TEST ---
            write_move(x=(0.0 + corr_rev), power_val=pwr) 
            
            write_move(x=-0.5 + corr_rev, power_val=0)
            
            # Overscan de sortie
            write_move(x=-5, power_val=0)

        # --- FIN G-CODE ---
        buf.write("\n( Cleanup )\n")
        buf.write("M5\n")
        if not use_s: 
            buf.write(f"M67 E{e_num} Q0\n")
        else: 
            buf.write("S0\n")
        buf.write(settings.get("footer", "M30").replace("|", "-") + "\n")
        
        return buf.getvalue()