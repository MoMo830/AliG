
"""
A.L.I.G. Project - Custom UI Widgets
------------------------------------
Contains custom graphical components.
"""


import customtkinter as ctk
import tkinter as tk
import sys


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)

    def schedule(self, event=None):
        self.id = self.widget.after(700, self.show)

    def show(self):
        if self.tip_window or not self.text:
            return
            
        # 1. UTILISATION DE CTkToplevel (Crucial pour CustomTkinter)
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.withdraw() # On cache pendant la création pour éviter le flash blanc
        tw.wm_overrideredirect(True)
        
        # Sous Windows, pour que l'arrondi fonctionne sur une fenêtre sans bordure
        if sys.platform.startswith("win"):
            tw.attributes("-topmost", True)
            tw.attributes("-transparentcolor", tw._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"]))

        # 2. Le conteneur
        # fg_color="transparent" permet au CTkToplevel de gérer le fond
        container = ctk.CTkFrame(tw, 
                                 fg_color="#363D36", 
                                 border_color="#BB4141",
                                 border_width=2, 
                                 corner_radius=2)
        container.pack(padx=2, pady=2)
        
        label = ctk.CTkLabel(container, 
                             text=self.text, 
                             font=("Arial", 12),
                             padx=12, 
                             pady=6,
                             text_color="#FFFFFF")
        label.pack()
        
        # Force le rendu pour calculer la taille
        tw.update_idletasks()
        
        # Calcul de la position
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        tw.wm_geometry(f"+{x}+{y}")
        tw.deiconify() # On affiche enfin

    def hide(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except:
                pass
            self.tip_window = None


class PowerRangeVisualizer(ctk.CTkFrame):
    def __init__(self, parent, min_entry, max_entry, update_callback):
        # 1. On garde le frame CTK transparent
        super().__init__(parent, fg_color="transparent", width=40)
        
        self.min_entry = min_entry
        self.max_entry = max_entry
        self.update_callback = update_callback
        
        # 2. RÉCUPÉRATION DE LA COULEUR RÉELLE DE L'ONGLET
        bg_color = self._determine_real_bg_color(parent)
        
        # 3. Création du Canvas avec la couleur précise
        self.canvas = tk.Canvas(
            self, 
            width=30, 
            height=120, 
            bg=bg_color, 
            highlightthickness=0, 
            borderwidth=0
        )
        self.canvas.pack(pady=5)
        
        # ... Dessin du rail et des curseurs ...
        self.canvas.create_line(15, 10, 15, 110, fill="#555555", width=2)
        self.min_handle = self.canvas.create_polygon(5, 0, 15, 5, 5, 10, fill="#3a9ad9")
        self.max_handle = self.canvas.create_polygon(25, 0, 15, 5, 25, 10, fill="#e74c3c")
        
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-1>", self.on_drag)
        self.refresh_visuals()

    def _determine_real_bg_color(self, parent):
        """
        Méthode robuste pour extraire la couleur hexa réelle d'un composant CTk
        même s'il est niché dans un Tabview.
        """
        current_mode = 1 if ctk.get_appearance_mode() == "Dark" else 0
        
        # 1. On essaie de lire la propriété _fg_color interne (plus fiable que cget)
        # On remonte les parents si on trouve "transparent"
        target = parent
        while target:
            # Récupération de la couleur (souvent un tuple ('#light', '#dark'))
            color = getattr(target, "_fg_color", "transparent")
            
            if color == "transparent":
                target = target.master
                continue
                
            if isinstance(color, (list, tuple)):
                return color[current_mode]
            
            return color
            
        # 2. Secours : Si on n'a rien trouvé, on prend la couleur par défaut du Tabview dans le thème
        try:
            return ctk.ThemeManager.theme["CTkTabview"]["fg_color"][current_mode]
        except:
            return "#2b2b2b" if current_mode == 1 else "#dbdbdb"

    def val_to_y(self, val):
        # 0% est en bas (y=110), 100% en haut (y=10)
        return 110 - (float(val) * 1)

    def y_to_val(self, y):
        val = (110 - y) / 1.0
        return max(0, min(100, round(val, 1)))

    def refresh_visuals(self):
        try:
            # On récupère le texte du widget CTkEntry
            raw_min = self.min_entry.get()
            raw_max = self.max_entry.get()
            
            # Nettoyage (remplacement virgule par point)
            v_min = float(str(raw_min).replace(',', '.'))
            v_max = float(str(raw_max).replace(',', '.'))
            
            y_min = self.val_to_y(v_min)
            y_max = self.val_to_y(v_max)
            
            # Mise à jour des coordonnées des triangles
            # Min (Bleu) à gauche du rail (x=2 à 12)
            self.canvas.coords(self.min_handle, 2, y_min-5, 12, y_min, 2, y_min+5)
            # Max (Rouge) à droite du rail (x=18 à 28)
            self.canvas.coords(self.max_handle, 28, y_max-5, 18, y_max, 28, y_max+5)
        except (ValueError, TypeError, tk.TclError):
            # En cas d'erreur de saisie (case vide, etc.), on ne fait rien
            pass

    def on_drag(self, event):
        val = self.y_to_val(event.y)
        y_min = self.val_to_y(self.min_entry.get())
        y_max = self.val_to_y(self.max_entry.get())
        
        # On bouge le curseur le plus proche
        if abs(event.y - y_min) < abs(event.y - y_max):
            self.min_entry.delete(0, tk.END)
            self.min_entry.insert(0, str(val))
        else:
            self.max_entry.delete(0, tk.END)
            self.max_entry.insert(0, str(val))
        
        self.refresh_visuals()
        self.update_callback()


class LoadingOverlay:
    """Overlay de chargement réutilisable pour couvrir une vue pendant un calcul."""
    def __init__(self, parent, text="Génération en cours..."):
        self.frame = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        # On utilise place pour couvrir tout l'espace sans perturber le grid
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frame.lift() # Met l'overlay au premier plan

        # Boîte centrale
        self.box = ctk.CTkFrame(self.frame, fg_color="#3a3a3a", corner_radius=12)
        self.box.place(relx=0.5, rely=0.5, anchor="center")

        self.label = ctk.CTkLabel(
            self.box, text=text, 
            font=("Arial", 14, "bold"), text_color="white"
        )
        self.label.pack(padx=30, pady=(20, 10))

        self.progress = ctk.CTkProgressBar(self.box, width=280)
        self.progress.pack(padx=30, pady=(5, 25))
        self.progress.configure(mode="indeterminate")
        self.progress.start()

    def destroy(self):
        """Supprime l'overlay proprement."""
        try:
            self.frame.destroy()
        except:
            pass