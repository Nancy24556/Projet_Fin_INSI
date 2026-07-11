import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime

import config
import database
import scanner
import snmp
import statistics

# Import de Matplotlib avec repli si non installé
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    pass

# Styling Palette (Modern Dark Theme)
COLOR_BG = "#121212"          # Deep Charcoal background
COLOR_CARD = "#1E1E1E"        # Card & Sidebar background
COLOR_HOVER = "#2C2C2C"       # Couleur au survol des boutons
COLOR_TEXT = "#FFFFFF"        # Texte principal (blanc)
COLOR_TEXT_MUTED = "#A0A0A0"  # Texte atténué (gris)
COLOR_ACCENT = "#00ADB5"      # Turquoise accent
COLOR_SUCCESS = "#2ECA7F"     # Active green
COLOR_DANGER = "#FF2E93"      # Offline red/pink
COLOR_WARNING = "#FFBE0B"     # Alert yellow

class ModernProgressBar(tk.Canvas):
    """A beautiful flat canvas-based progress bar that fits our design language."""
    def __init__(self, parent, width=300, height=12, bg="#2C2C2C", fill_color=COLOR_ACCENT, **kwargs):
        super().__init__(parent, width=width, height=height, bg=COLOR_BG, highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.fill_color = fill_color
        
        # Background track
        self.bg_rect = self.create_rectangle(0, 0, width, height, fill=bg, width=0)
        # Indicateur de progression (premier plan)
        self.fill_rect = self.create_rectangle(0, 0, 0, height, fill=fill_color, width=0)
        
    def set(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        self.coords(self.fill_rect, 0, 0, int(self.width * fraction), self.height)

class NetworkSupervisionApp:
    def __init__(self, root, utilisateur_connecte=None):
        self.root = root
        self.root.title("SNMP NetSupervisor")
        self.root.geometry("1100x700")
        self.root.minsize(1000, 650)
        self.root.configure(bg=COLOR_BG)

        # Utilisateur actuellement connecte (dict issu de la table 'utilisateur')
        self.utilisateur_connecte = utilisateur_connecte or {}
        # Devient True si l'utilisateur clique sur "Deconnexion" (pour que
        # main.py sache qu'il faut rouvrir l'ecran de connexion au lieu de
        # fermer completement l'application)
        self.demande_deconnexion = False

        # Variables d'état de l'application
        self.current_tab = "dashboard"
        self.scan_in_progress = False
        self.active_kpi_labels = {}
        self.last_selected_snmp_ip = None
        
        # Configuration du style moderne des tableaux et barres de défilement
        self.setup_styles()
        
        # Construction de la structure de la mise en page
        self.create_layout()
        
        # Démarrage de la boucle de rafraîchissement périodique de l'interface
        self.gui_refresh_loop()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Treeview styling
        style.configure("Treeview", 
                        background=COLOR_CARD, 
                        foreground=COLOR_TEXT, 
                        fieldbackground=COLOR_CARD, 
                        rowheight=32,
                        font=("Segoe UI", 10),
                        borderwidth=0)
        
        style.configure("Treeview.Heading", 
                        background="#262626", 
                        foreground=COLOR_TEXT_MUTED, 
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        
        # Couleurs de sélection dans les tableaux
        style.map("Treeview", 
                  background=[("selected", COLOR_ACCENT)], 
                  foreground=[("selected", "#000000")])
        
        # Scrollbar styling
        style.configure("TScrollbar", 
                        background="#262626", 
                        troughcolor=COLOR_BG,
                        borderwidth=0, 
                        arrowsize=12)

    def create_layout(self):
        # --- SIDEBAR PANEL ---
        self.sidebar = tk.Frame(self.root, bg=COLOR_CARD, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo / Title
        logo_frame = tk.Frame(self.sidebar, bg=COLOR_CARD, pady=25)
        logo_frame.pack(fill="x")
        
        lbl_logo = tk.Label(logo_frame, text="⚡ NetSupervisor", fg=COLOR_ACCENT, bg=COLOR_CARD, font=("Segoe UI", 16, "bold"))
        lbl_logo.pack()
        
        lbl_subtitle = tk.Label(logo_frame, text="SNMP ET SURVEILLANCE IP", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 8, "bold"))
        lbl_subtitle.pack(pady=2)
        
        # Sidebar Navigation Buttons
        self.nav_buttons = {}
        tabs = [
            ("dashboard", "📊  Tableau de bord"),
            ("scanner", "🔍  Scanner Réseau"),
            ("snmp", "🔌  Moniteur SNMP"),
            ("events", "📜  Journal Wi-Fi"),
            ("analytics", "📈  Statistiques"),
            ("settings", "⚙️  Paramètres")
        ]
        
        for tab_id, label in tabs:
            btn = tk.Button(
                self.sidebar, 
                text=label, 
                fg=COLOR_TEXT_MUTED, 
                bg=COLOR_CARD, 
                activeforeground=COLOR_TEXT,
                activebackground=COLOR_HOVER,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
                padx=20,
                pady=12,
                bd=0,
                cursor="hand2",
                command=lambda tid=tab_id: self.switch_tab(tid)
            )
            btn.pack(fill="x", pady=2)
            btn.bind("<Enter>", lambda e, b=btn: self.on_nav_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self.on_nav_hover(b, False))
            self.nav_buttons[tab_id] = btn
            
        # Version Indicator at the bottom
        lbl_version = tk.Label(self.sidebar, text="v1.0.0 (SQLite + Socket)", fg="#555555", bg=COLOR_CARD, font=("Segoe UI", 8))
        lbl_version.pack(side="bottom", pady=(0, 10))

        # --- Bloc utilisateur connecte + bouton de deconnexion ---
        user_frame = tk.Frame(self.sidebar, bg=COLOR_CARD)
        user_frame.pack(side="bottom", fill="x", pady=(5, 5))

        tk.Frame(user_frame, bg="#2C2C2C", height=1).pack(fill="x", pady=(0, 10))

        nom_utilisateur = self.utilisateur_connecte.get("nom") or "Utilisateur"
        lbl_user = tk.Label(user_frame, text=f"👤 {nom_utilisateur}", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"))
        lbl_user.pack(anchor="w", padx=20)

        btn_logout = tk.Button(
            user_frame,
            text="🚪  Déconnexion",
            fg=COLOR_DANGER,
            bg=COLOR_CARD,
            activeforeground=COLOR_TEXT,
            activebackground=COLOR_HOVER,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            padx=20,
            pady=8,
            bd=0,
            cursor="hand2",
            command=self.se_deconnecter
        )
        btn_logout.pack(fill="x", pady=(5, 0))
        
        # --- MAIN CONTAINER ---
        self.main_container = tk.Frame(self.root, bg=COLOR_BG, padx=25, pady=25)
        self.main_container.pack(side="right", fill="both", expand=True)
        
        # Initialisation des différentes pages
        self.frames = {
            "dashboard": self.build_dashboard_page(),
            "scanner": self.build_scanner_page(),
            "snmp": self.build_snmp_page(),
            "events": self.build_events_page(),
            "analytics": self.build_analytics_page(),
            "settings": self.build_settings_page()
        }
        
        # Affichage de l'onglet par défaut
        self.switch_tab("dashboard")

    def on_nav_hover(self, button, is_hover):
        # Ne pas changer la couleur si c'est l'onglet actif
        for tab_id, btn in self.nav_buttons.items():
            if btn == button and self.current_tab == tab_id:
                return
        if is_hover:
            button.config(bg=COLOR_HOVER, fg=COLOR_TEXT)
        else:
            button.config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)

    def switch_tab(self, tab_id):
        # Masquer la page actuelle
        if self.current_tab in self.frames:
            self.frames[self.current_tab].pack_forget()
            self.nav_buttons[self.current_tab].config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)
            
        # Afficher la nouvelle page
        self.current_tab = tab_id
        self.frames[tab_id].pack(fill="both", expand=True)
        self.nav_buttons[tab_id].config(bg=COLOR_HOVER, fg=COLOR_ACCENT)
        
        # Déclencher le rafraîchissement propre à chaque page
        if tab_id == "dashboard":
            self.refresh_dashboard_data()
        elif tab_id == "scanner":
            self.refresh_scanner_table()
        elif tab_id == "snmp":
            self.refresh_snmp_page()
        elif tab_id == "events":
            self.refresh_events_table()
        elif tab_id == "analytics":
            self.refresh_analytics_page()

    # ==========================================
    # 📊 PAGE: DASHBOARD
    # ==========================================
    def build_dashboard_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 20))
        lbl_title = tk.Label(header, text="Vue d'ensemble du réseau", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        # KPI Grid Frame
        kpi_frame = tk.Frame(page, bg=COLOR_BG)
        kpi_frame.pack(fill="x", pady=10)
        kpi_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="equal")
        
        self.kpi_cards = {}
        kpis = [
            ("total_hosts", "Équipements totaux", COLOR_ACCENT),
            ("active_hosts", "Équipements actifs", COLOR_SUCCESS),
            ("snmp_hosts", "Surveillés en SNMP", COLOR_WARNING),
            ("alerts", "Alertes (24h)", COLOR_DANGER)
        ]
        
        for i, (kpi_key, title, color) in enumerate(kpis):
            card = tk.Frame(kpi_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground="#2C2C2C")
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            
            # Bande de couleur d'accentuation à gauche
            accent = tk.Frame(card, bg=color, width=4)
            accent.pack(side="left", fill="y")
            
            inner = tk.Frame(card, bg=COLOR_CARD, padx=15, pady=15)
            inner.pack(side="left", fill="both", expand=True)
            
            lbl_title = tk.Label(inner, text=title.upper(), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"))
            lbl_title.pack(anchor="w")
            
            lbl_val = tk.Label(inner, text="0", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 22, "bold"))
            lbl_val.pack(anchor="w", pady=(5, 0))
            
            self.kpi_cards[kpi_key] = lbl_val
            
        # Section : équipements actuellement connectés
        alerts_frame = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C")
        alerts_frame.pack(fill="both", expand=True, pady=(20, 0))
        
        lbl_alert_title = tk.Label(alerts_frame, text="🟢 Équipements actuellement connectés au réseau", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 12, "bold"), padx=15, pady=15)
        lbl_alert_title.pack(anchor="w")
        
        # Tableau des équipements connectés en ce moment (sans distinction de type de machine)
        table_frame = tk.Frame(alerts_frame, bg=COLOR_CARD, padx=15, pady=5)
        table_frame.pack(fill="both", expand=True)
        
        columns = ("ip", "nom", "connexion", "duree")
        self.dash_events_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        self.dash_events_tree.heading("ip", text="Adresse IP")
        self.dash_events_tree.heading("nom", text="Nom de l'équipement")
        self.dash_events_tree.heading("connexion", text="Connecté depuis")
        self.dash_events_tree.heading("duree", text="Durée de connexion")
        
        self.dash_events_tree.column("ip", width=150, anchor="center")
        self.dash_events_tree.column("nom", width=220, anchor="w")
        self.dash_events_tree.column("connexion", width=180, anchor="center")
        self.dash_events_tree.column("duree", width=180, anchor="center")
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.dash_events_tree.yview, style="TScrollbar")
        self.dash_events_tree.configure(yscrollcommand=scrollbar.set)
        
        self.dash_events_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return page

    def refresh_dashboard_data(self):
        stats = statistics.get_dashboard_stats()
        for key, value in stats.items():
            if key in self.kpi_cards:
                self.kpi_cards[key].config(text=str(value))
                
        # Rafraîchir la liste des équipements connectés en ce moment
        # (uniquement "Connecté", jamais les équipements déconnectés)
        for item in self.dash_events_tree.get_children():
            self.dash_events_tree.delete(item)
            
        connectes = database.get_connected_now(limit=20)
        for c in connectes:
            self.dash_events_tree.insert("", "end", values=(c["ip"], c["nom"], c["date_connexion"], c["duree"]))

    # ==========================================
    # 🔍 PAGE: NETWORK SCANNER
    # ==========================================
    def build_scanner_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 15))
        lbl_title = tk.Label(header, text="Scanner de présence réseau", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        # Controls card
        controls_card = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=20, pady=15)
        controls_card.pack(fill="x", pady=(0, 15))
        
        lbl_subnet = tk.Label(controls_card, text="Plage du sous-réseau :", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"))
        lbl_subnet.pack(side="left", padx=(0, 10))
        
        self.subnet_var = tk.StringVar(value=config.DEFAULT_SUBNET)
        self.txt_subnet = tk.Entry(controls_card, textvariable=self.subnet_var, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT, highlightbackground="#444444", font=("Segoe UI", 10), width=20, justify="center")
        self.txt_subnet.pack(side="left", padx=(0, 20), ipady=4)
        
        self.btn_scan = tk.Button(
            controls_card,
            text="⚡ Lancer le scan",
            fg="#000000",
            bg=COLOR_ACCENT,
            activeforeground="#000000",
            activebackground="#00D2D9",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=4,
            bd=0,
            cursor="hand2",
            command=self.start_subnet_scan
        )
        self.btn_scan.pack(side="left")
        
        # Statut et progression du scan
        self.lbl_scan_status = tk.Label(controls_card, text="Système au repos", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9))
        self.lbl_scan_status.pack(side="right", padx=(10, 0))
        
        self.prog_bar = ModernProgressBar(controls_card, width=200)
        self.prog_bar.pack(side="right", pady=5)
        
        # Tableau des équipements
        table_card = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=15, pady=15)
        table_card.pack(fill="both", expand=True)
        
        columns = ("ip", "hostname", "status", "last_seen", "snmp")
        self.hosts_tree = ttk.Treeview(table_card, columns=columns, show="headings")
        
        self.hosts_tree.heading("ip", text="Adresse IP")
        self.hosts_tree.heading("hostname", text="Nom / MAC")
        self.hosts_tree.heading("status", text="Statut de disponibilité")
        self.hosts_tree.heading("last_seen", text="Dernière détection")
        self.hosts_tree.heading("snmp", text="Support SNMP")
        
        self.hosts_tree.column("ip", width=120, anchor="center")
        self.hosts_tree.column("hostname", width=200, anchor="w")
        self.hosts_tree.column("status", width=130, anchor="center")
        self.hosts_tree.column("last_seen", width=180, anchor="center")
        self.hosts_tree.column("snmp", width=120, anchor="center")
        
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.hosts_tree.yview, style="TScrollbar")
        self.hosts_tree.configure(yscrollcommand=scrollbar.set)
        
        self.hosts_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return page

    def refresh_scanner_table(self):
        for item in self.hosts_tree.get_children():
            self.hosts_tree.delete(item)
            
        hosts = database.get_hosts()
        for h in hosts:
            status_str = "🟢 Actif" if h["status"] == "active" else "🔴 Inactif"
            snmp_str = "⚡ Activé" if h["is_snmp_enabled"] == 1 else "❌ Désactivé"
            last_seen = h["last_seen"] if h["last_seen"] else "Jamais"
            self.hosts_tree.insert("", "end", values=(h["ip"], h["hostname"] or "Inconnu", status_str, last_seen, snmp_str))

    def start_subnet_scan(self):
        if self.scan_in_progress:
            return
        
        self.scan_in_progress = True
        self.btn_scan.config(state="disabled", text="Scan en cours...", bg=COLOR_HOVER, fg=COLOR_TEXT_MUTED)
        self.prog_bar.set(0)
        self.lbl_scan_status.config(text="Initialisation du scan...", fg=COLOR_ACCENT)
        
        def run_thread():
            subnet = self.subnet_var.get().strip()
            
            # Fonction de rappel pour suivre la progression du scan
            def progress_cb(current, total):
                fraction = current / total
                # Use after() to schedule updates safely on the Tkinter main thread
                self.root.after(0, lambda: self.prog_bar.set(fraction))
                self.root.after(0, lambda: self.lbl_scan_status.config(text=f"Scanning: {current}/{total} hosts"))
            
            # En mode simulation, injecter les équipements simulés dans la base pour une démo immédiate
            if config.SIMULATOR_ENABLED:
                for sim_ip in snmp.SIMULATED_DEVICES.keys():
                    database.register_host(sim_ip, snmp.SIMULATED_DEVICES[sim_ip]["sysName"], "active")
                    
            # Run scan
            scanner.scan_subnet(subnet, progress_callback=progress_cb)
            
            # Fonction de rappel à la fin du scan
            self.root.after(0, self.on_scan_complete)
            
        threading.Thread(target=run_thread, daemon=True).start()

    def on_scan_complete(self):
        self.scan_in_progress = False
        self.btn_scan.config(state="normal", text="⚡ Lancer le scan", bg=COLOR_ACCENT, fg="#000000")
        self.prog_bar.set(1.0)
        self.lbl_scan_status.config(text="Scan terminé avec succès", fg=COLOR_SUCCESS)
        self.refresh_scanner_table()
        self.refresh_dashboard_data()

    # ==========================================
    # 🔌 PAGE: SNMP MONITOR
    # ==========================================
    def build_snmp_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 15))
        lbl_title = tk.Label(header, text="Gestionnaire de télémétrie SNMP", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        # Panneau principal divisé en deux
        split_pane = tk.Frame(page, bg=COLOR_BG)
        split_pane.pack(fill="both", expand=True)
        
        # Left Panel - SNMP Enabled Hosts list
        left_panel = tk.Frame(split_pane, bg=COLOR_CARD, width=280, highlightthickness=1, highlightbackground="#2C2C2C", padx=10, pady=10)
        left_panel.pack(side="left", fill="y", padx=(0, 15))
        left_panel.pack_propagate(False)
        
        lbl_list_title = tk.Label(left_panel, text="Équipements à interroger", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"))
        lbl_list_title.pack(anchor="w", pady=(0, 8))
        
        self.snmp_listbox = tk.Listbox(left_panel, bg=COLOR_BG, fg=COLOR_TEXT, selectbackground=COLOR_ACCENT, selectforeground="#000000", bd=0, highlightthickness=0, font=("Segoe UI", 10), cursor="hand2")
        self.snmp_listbox.pack(fill="both", expand=True)
        self.snmp_listbox.bind("<<ListboxSelect>>", self.on_snmp_host_select)
        
        # Right Panel - Detailed SNMP MIBs
        self.right_panel = tk.Frame(split_pane, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=20, pady=20)
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # Message affiché si aucun équipement n'est sélectionné
        self.snmp_placeholder = tk.Label(
            self.right_panel, 
            text="Sélectionnez un équipement dans la liste pour récupérer ses statistiques SNMP.\nSi la liste est vide, lancez un scan réseau ou activez le simulateur.", 
            fg=COLOR_TEXT_MUTED, 
            bg=COLOR_CARD, 
            font=("Segoe UI", 10, "italic"),
            justify="center"
        )
        self.snmp_placeholder.pack(expand=True)
        
        # Conteneur des détails (masqué au départ)
        self.snmp_details_frame = tk.Frame(self.right_panel, bg=COLOR_CARD)
        
        # Detail header
        self.lbl_snmp_ip = tk.Label(self.snmp_details_frame, text="IP : 192.168.1.1", fg=COLOR_ACCENT, bg=COLOR_CARD, font=("Segoe UI", 14, "bold"))
        self.lbl_snmp_ip.pack(anchor="w", pady=(0, 15))
        
        # Création de la grille des champs
        fields_frame = tk.Frame(self.snmp_details_frame, bg=COLOR_CARD)
        fields_frame.pack(fill="x", pady=10)
        fields_frame.columnconfigure(1, weight=1)
        
        self.snmp_fields = {}
        fields_to_create = [
            ("sysName", "Nom système (sysName) :"),
            ("sysUpTime", "Temps de fonctionnement (sysUpTime) :"),
            ("sysLocation", "Emplacement (sysLocation) :"),
            ("sysContact", "Contact (sysContact) :"),
            ("sysDescr", "Description (sysDescr) :")
        ]
        
        for idx, (field_key, label_text) in enumerate(fields_to_create):
            lbl_field = tk.Label(fields_frame, text=label_text, fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"), anchor="e", width=22)
            lbl_field.grid(row=idx, column=0, padx=(0, 10), pady=8, sticky="ne")
            
            # Utiliser un widget Message pour le retour à la ligne si c'est la description
            if field_key == "sysDescr":
                val_widget = tk.Message(fields_frame, text="-", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10), width=450, anchor="w")
            else:
                val_widget = tk.Label(fields_frame, text="-", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10), anchor="w")
                
            val_widget.grid(row=idx, column=1, pady=8, sticky="nw")
            self.snmp_fields[field_key] = val_widget
            
        # Action controls
        ctrl_frame = tk.Frame(self.snmp_details_frame, bg=COLOR_CARD, pady=15)
        ctrl_frame.pack(fill="x")
        
        self.btn_poll_snmp = tk.Button(
            ctrl_frame,
            text="🔌 Interroger maintenant",
            fg="#000000",
            bg=COLOR_SUCCESS,
            activeforeground="#000000",
            activebackground="#26B26E",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=5,
            bd=0,
            cursor="hand2",
            command=self.poll_selected_snmp
        )
        self.btn_poll_snmp.pack(side="left")
        
        self.lbl_snmp_poll_status = tk.Label(ctrl_frame, text="Au repos", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9, "italic"), padx=15)
        self.lbl_snmp_poll_status.pack(side="left")
        
        # Tableau de l'historique des relevés
        lbl_history_title = tk.Label(self.snmp_details_frame, text="📊 Historique des relevés", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 11, "bold"), pady=10)
        lbl_history_title.pack(anchor="w")
        
        hist_table_frame = tk.Frame(self.snmp_details_frame, bg=COLOR_CARD)
        hist_table_frame.pack(fill="both", expand=True)
        
        self.snmp_hist_tree = ttk.Treeview(hist_table_frame, columns=("time", "uptime", "location"), show="headings", height=5)
        self.snmp_hist_tree.heading("time", text="Horodatage du relevé")
        self.snmp_hist_tree.heading("uptime", text="Temps de fonctionnement")
        self.snmp_hist_tree.heading("location", text="Emplacement")
        
        self.snmp_hist_tree.column("time", width=150, anchor="center")
        self.snmp_hist_tree.column("uptime", width=200, anchor="w")
        self.snmp_hist_tree.column("location", width=150, anchor="w")
        
        hist_scrollbar = ttk.Scrollbar(hist_table_frame, orient="vertical", command=self.snmp_hist_tree.yview, style="TScrollbar")
        self.snmp_hist_tree.configure(yscrollcommand=hist_scrollbar.set)
        self.snmp_hist_tree.pack(side="left", fill="both", expand=True)
        hist_scrollbar.pack(side="right", fill="y")
        
        return page

    def refresh_snmp_page(self):
        # Rafraîchir la liste des équipements actifs interrogeables
        self.snmp_listbox.delete(0, tk.END)
        hosts = database.get_hosts()
        
        # Remplir la liste avec les équipements actifs
        active_hosts = [h for h in hosts if h["status"] == "active"]
        
        for h in active_hosts:
            name_suffix = f" ({h['hostname']})" if h["hostname"] and h["hostname"] != "Hôte inconnu" else ""
            self.snmp_listbox.insert(tk.END, f"{h['ip']}{name_suffix}")
            
        # Re-select the last active IP if it is still present
        if self.last_selected_snmp_ip:
            for idx, text in enumerate(self.snmp_listbox.get(0, tk.END)):
                if text.startswith(self.last_selected_snmp_ip):
                    self.snmp_listbox.selection_set(idx)
                    self.on_snmp_host_select(None)
                    break
        else:
            self.snmp_placeholder.pack(expand=True)
            self.snmp_details_frame.pack_forget()

    def on_snmp_host_select(self, event):
        selection = self.snmp_listbox.curselection()
        if not selection:
            return
            
        selected_text = self.snmp_listbox.get(selection[0])
        # Parse IP (it's the first word)
        ip = selected_text.split(" ")[0]
        self.last_selected_snmp_ip = ip
        
        # Basculer la visibilité des panneaux
        self.snmp_placeholder.pack_forget()
        self.snmp_details_frame.pack(fill="both", expand=True)
        
        # Mettre à jour les libellés avec les dernières valeurs connues
        self.lbl_snmp_ip.config(text=f"🔌 Adresse IP : {ip}")
        self.lbl_snmp_poll_status.config(text="Affichage des données en cache", fg=COLOR_TEXT_MUTED)
        
        history = database.get_snmp_history(ip, limit=1)
        if history:
            last = history[0]
            self.snmp_fields["sysName"].config(text=last["sys_name"] or "-")
            self.snmp_fields["sysUpTime"].config(text=last["sys_uptime"] or "-")
            self.snmp_fields["sysLocation"].config(text=last["sys_location"] or "-")
            self.snmp_fields["sysContact"].config(text=last["sys_contact"] or "-")
            self.snmp_fields["sysDescr"].config(text=last["sys_descr"] or "-")
        else:
            # No SNMP record found in DB yet
            for widget in self.snmp_fields.values():
                widget.config(text="-")
                
        # Load SNMP history log
        for item in self.snmp_hist_tree.get_children():
            self.snmp_hist_tree.delete(item)
            
        full_history = database.get_snmp_history(ip, limit=5)
        for h in full_history:
            self.snmp_hist_tree.insert("", "end", values=(h["timestamp"], h["sys_uptime"], h["sys_location"]))

    def poll_selected_snmp(self):
        ip = self.last_selected_snmp_ip
        if not ip:
            return
            
        self.btn_poll_snmp.config(state="disabled", text="Interrogation...", bg=COLOR_HOVER, fg=COLOR_TEXT_MUTED)
        self.lbl_snmp_poll_status.config(text="Envoi de la requête SNMP...", fg=COLOR_ACCENT)
        
        def run_poll():
            # Query SNMP device
            snmp_res = snmp.query_snmp_device(ip)
            
            def update_gui():
                if snmp_res:
                    # Analyser le dictionnaire d'OID retourné
                    sys_name = snmp_res.get(config.OIDS["sysName"], "Inconnu")
                    sys_descr = snmp_res.get(config.OIDS["sysDescr"], "Inconnu")
                    sys_uptime = snmp_res.get(config.OIDS["sysUpTime"], "Inconnu")
                    sys_location = snmp_res.get(config.OIDS["sysLocation"], "Inconnu")
                    sys_contact = snmp_res.get(config.OIDS["sysContact"], "Inconnu")
                    
                    # Enregistrer en base de données
                    database.add_snmp_record(ip, sys_name, sys_descr, sys_uptime, sys_location, sys_contact)
                    
                    # Refresh fields
                    self.snmp_fields["sysName"].config(text=sys_name)
                    self.snmp_fields["sysUpTime"].config(text=sys_uptime)
                    self.snmp_fields["sysLocation"].config(text=sys_location)
                    self.snmp_fields["sysContact"].config(text=sys_contact)
                    self.snmp_fields["sysDescr"].config(text=sys_descr)
                    
                    self.lbl_snmp_poll_status.config(text="Succès ! Données enregistrées.", fg=COLOR_SUCCESS)
                    
                    # Mettre à jour les listes et graphiques actifs
                    self.refresh_scanner_table()
                    self.on_snmp_host_select(None)
                else:
                    self.lbl_snmp_poll_status.config(text="Erreur : la requête SNMP a échoué ou expiré.", fg=COLOR_DANGER)
                    
                self.btn_poll_snmp.config(state="normal", text="🔌 Interroger maintenant", bg=COLOR_SUCCESS, fg="#000000")
                
            self.root.after(0, update_gui)
            
        threading.Thread(target=run_poll, daemon=True).start()

    # ==========================================
    # 📜 PAGE: EVENTS LOG
    # ==========================================
    def build_events_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 15))
        lbl_title = tk.Label(header, text="Journal de connexion Wi-Fi", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        btn_clear = tk.Button(
            header,
            text="🗑️ Effacer le journal",
            fg=COLOR_TEXT,
            bg=COLOR_HOVER,
            activeforeground=COLOR_TEXT,
            activebackground="#444444",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=3,
            bd=0,
            cursor="hand2",
            command=self.clear_logs
        )
        btn_clear.pack(side="right")
        
        # Sous-titre explicatif
        lbl_subtitle = tk.Label(page, text="Liste des utilisateurs Wi-Fi connectés et déconnectés, avec la durée de leur connexion.", fg=COLOR_TEXT_MUTED, bg=COLOR_BG, font=("Segoe UI", 9, "italic"))
        lbl_subtitle.pack(anchor="w", pady=(0, 10))
        
        # Table du journal Wi-Fi
        table_card = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=15, pady=15)
        table_card.pack(fill="both", expand=True)
        
        columns = ("ip", "nom", "connexion", "deconnexion", "duree", "statut")
        self.events_tree = ttk.Treeview(table_card, columns=columns, show="headings")
        
        self.events_tree.heading("ip", text="Adresse IP")
        self.events_tree.heading("nom", text="Utilisateur / Équipement")
        self.events_tree.heading("connexion", text="Date de connexion")
        self.events_tree.heading("deconnexion", text="Date de déconnexion")
        self.events_tree.heading("duree", text="Durée de connexion")
        self.events_tree.heading("statut", text="Statut")
        
        self.events_tree.column("ip", width=110, anchor="center")
        self.events_tree.column("nom", width=170, anchor="w")
        self.events_tree.column("connexion", width=150, anchor="center")
        self.events_tree.column("deconnexion", width=150, anchor="center")
        self.events_tree.column("duree", width=130, anchor="center")
        self.events_tree.column("statut", width=110, anchor="center")
        
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.events_tree.yview, style="TScrollbar")
        self.events_tree.configure(yscrollcommand=scrollbar.set)
        
        self.events_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return page

    def refresh_events_table(self):
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)
            
        # Journal Wi-Fi : uniquement les utilisateurs/équipements ayant
        # une session de présence (connectés ou déconnectés), avec la
        # durée exacte de leur connexion.
        journal = database.get_presence_log()
        for entree in journal:
            statut_formatte = "🟢 Connecté" if entree["statut"] == "Connecte" else "🔴 Déconnecté"
            self.events_tree.insert("", "end", values=(
                entree["ip"],
                entree["nom"],
                entree["date_connexion"],
                entree["date_deconnexion"],
                entree["duree"],
                statut_formatte,
            ))

    def clear_logs(self):
        if messagebox.askyesno("Confirmer la réinitialisation", "Voulez-vous vraiment effacer toute la base de données (équipements, relevés SNMP, journal) ?"):
            database.clear_database()
            self.refresh_events_table()
            self.refresh_dashboard_data()
            self.refresh_scanner_table()
            self.refresh_snmp_page()

    # ==========================================
    # 📈 PAGE: ANALYTICS
    # ==========================================
    def build_analytics_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 15))
        lbl_title = tk.Label(header, text="Statistiques du réseau", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        # Analytics body
        self.chart_container = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=15, pady=15)
        self.chart_container.pack(fill="both", expand=True)
        
        return page

    def refresh_analytics_page(self):
        # Clear container
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
        if MATPLOTLIB_AVAILABLE:
            self.draw_matplotlib_charts()
        else:
            self.draw_canvas_fallback_charts()

    def draw_matplotlib_charts(self):
        # Fetch stats
        dist = statistics.get_device_status_distribution()
        timeline_labels, timeline_values = statistics.get_event_timeline_data()
        
        hosts = database.get_hosts()
        avail_labels = []
        avail_values = []
        
        for h in hosts[:5]: # Prendre les 5 premiers équipements
            ip = h["ip"]
            name = h["hostname"] or ip
            avail_labels.append(name[:12]) # limit length
            avail_values.append(statistics.get_host_availability(ip))

        # Setup figure
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=COLOR_CARD)
        
        # Plot 1: Device Status Pie Chart
        ax_pie = fig.add_subplot(121)
        ax_pie.set_facecolor(COLOR_CARD)
        labels = ['Actif', 'Inactif']
        sizes = [dist['active'], dist['inactive']]
        colors = [COLOR_SUCCESS, COLOR_DANGER]
        
        if sum(sizes) == 0:
            sizes = [1, 0] # default representation
            labels = ['Aucun équipement', '']
            colors = [COLOR_HOVER, COLOR_HOVER]
            
        wedges, texts, autotexts = ax_pie.pie(
            sizes, 
            labels=labels, 
            colors=colors, 
            autopct=lambda p: '{:.1f}%'.format(p) if p > 0 else '', 
            startangle=90,
            textprops=dict(color=COLOR_TEXT)
        )
        ax_pie.set_title("Répartition Actifs / Inactifs", color=COLOR_TEXT, fontsize=10, fontweight="bold")
        
        # Plot 2: Availability of Monitored hosts
        ax_bar = fig.add_subplot(122)
        ax_bar.set_facecolor(COLOR_CARD)
        
        if not avail_values:
            avail_labels = ["Aucune donnée"]
            avail_values = [0]
            
        bars = ax_bar.bar(avail_labels, avail_values, color=COLOR_ACCENT, width=0.5)
        ax_bar.set_title("Disponibilité des équipements (%)", color=COLOR_TEXT, fontsize=10, fontweight="bold")
        ax_bar.set_ylim(0, 105)
        ax_bar.tick_params(colors=COLOR_TEXT_MUTED, labelsize=8)
        
        # Style spines
        for spine in ax_bar.spines.values():
            spine.set_color("#444444")
            
        for bar in bars:
            height = bar.get_height()
            ax_bar.annotate(f'{height}%',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom', color=COLOR_TEXT, fontsize=8)

        fig.tight_layout()
        
        # Affichage dans Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def draw_canvas_fallback_charts(self):
        """Native Tkinter drawing fallback for charts if Matplotlib is not present."""
        lbl_info = tk.Label(self.chart_container, text="Matplotlib n'est pas installé. Affichage des graphiques natifs...", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9, "italic"))
        lbl_info.pack(anchor="nw", pady=(0, 10))
        
        canvas = tk.Canvas(self.chart_container, bg=COLOR_CARD, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        # Fetch stats
        dist = statistics.get_device_status_distribution()
        active = dist["active"]
        inactive = dist["inactive"]
        total = active + inactive
        
        # Draw Pie Chart Fallback
        cx, cy, r = 200, 150, 80
        canvas.create_text(cx, cy - r - 20, text="Répartition Actifs / Inactifs", fill=COLOR_TEXT, font=("Segoe UI", 10, "bold"))
        
        if total == 0:
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLOR_HOVER, outline="#444444")
            canvas.create_text(cx, cy, text="Aucun équipement scanné", fill=COLOR_TEXT_MUTED, font=("Segoe UI", 9))
        else:
            active_angle = (active / total) * 360
            inactive_angle = 360 - active_angle
            
            # Active slice
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=active_angle, fill=COLOR_SUCCESS, outline=COLOR_CARD)
            # Inactive slice
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=90 + active_angle, extent=inactive_angle, fill=COLOR_DANGER, outline=COLOR_CARD)
            
            # Legend
            canvas.create_rectangle(cx + r + 20, cy - 20, cx + r + 35, cy - 5, fill=COLOR_SUCCESS, width=0)
            canvas.create_text(cx + r + 45, cy - 12, text=f"Active ({active})", fill=COLOR_TEXT, font=("Segoe UI", 9), anchor="w")
            
            canvas.create_rectangle(cx + r + 20, cy + 5, cx + r + 35, cy + 20, fill=COLOR_DANGER, width=0)
            canvas.create_text(cx + r + 45, cy + 13, text=f"Inactive ({inactive})", fill=COLOR_TEXT, font=("Segoe UI", 9), anchor="w")

        # Draw Availability Bar Chart Fallback
        bx, by = 480, 240
        b_width, b_height = 350, 180
        canvas.create_text(bx + b_width/2, by - b_height - 20, text="Disponibilité des équipements (%)", fill=COLOR_TEXT, font=("Segoe UI", 10, "bold"))
        
        # Grid lines
        canvas.create_line(bx, by, bx + b_width, by, fill="#444444")
        canvas.create_line(bx, by, bx, by - b_height, fill="#444444")
        
        hosts = database.get_hosts()
        active_hosts = [h for h in hosts if h["status"] == "active"][:4]
        
        if not active_hosts:
            canvas.create_text(bx + b_width/2, by - b_height/2, text="Aucun équipement actif à afficher", fill=COLOR_TEXT_MUTED, font=("Segoe UI", 9))
        else:
            bar_w = 40
            spacing = (b_width - (len(active_hosts) * bar_w)) / (len(active_hosts) + 1)
            
            for idx, h in enumerate(active_hosts):
                ip = h["ip"]
                avail = statistics.get_host_availability(ip)
                bar_h = int((avail / 100.0) * b_height)
                
                x0 = bx + spacing + idx * (bar_w + spacing)
                y0 = by - bar_h
                x1 = x0 + bar_w
                y1 = by
                
                # Draw bar
                canvas.create_rectangle(x0, y0, x1, y1, fill=COLOR_ACCENT, outline="", width=0)
                # Value label
                canvas.create_text((x0+x1)/2, y0 - 10, text=f"{avail}%", fill=COLOR_TEXT, font=("Segoe UI", 8, "bold"))
                # Host label
                name = h["hostname"] or ip
                canvas.create_text((x0+x1)/2, by + 12, text=name[:10], fill=COLOR_TEXT_MUTED, font=("Segoe UI", 8))

    # ==========================================
    # ⚙️ PAGE: SETTINGS
    # ==========================================
    def build_settings_page(self):
        page = tk.Frame(self.main_container, bg=COLOR_BG)
        
        # Header
        header = tk.Frame(page, bg=COLOR_BG)
        header.pack(fill="x", pady=(0, 15))
        lbl_title = tk.Label(header, text="Configuration du système", fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 18, "bold"))
        lbl_title.pack(side="left")
        
        # Settings Card
        settings_card = tk.Frame(page, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#2C2C2C", padx=25, pady=25)
        settings_card.pack(fill="both", expand=True)
        
        # Settings Grid Layout
        grid_frame = tk.Frame(settings_card, bg=COLOR_CARD)
        grid_frame.pack(anchor="nw", fill="x")
        grid_frame.columnconfigure(1, weight=1)
        
        # Simulator setting
        lbl_sim = tk.Label(grid_frame, text="Activer le simulateur d'agent SNMP :", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_sim.grid(row=0, column=0, pady=15, sticky="w")
        
        self.sim_enabled_var = tk.BooleanVar(value=config.SIMULATOR_ENABLED)
        cb_sim = tk.Checkbutton(
            grid_frame, 
            variable=self.sim_enabled_var, 
            bg=COLOR_CARD, 
            activebackground=COLOR_CARD, 
            selectcolor="#000000", 
            fg=COLOR_TEXT,
            activeforeground=COLOR_TEXT,
            bd=0,
            command=self.save_settings
        )
        cb_sim.grid(row=0, column=1, padx=20, pady=15, sticky="w")
        
        # Scan settings
        lbl_interval = tk.Label(grid_frame, text="Intervalle de scan du sous-réseau (secondes) :", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_interval.grid(row=1, column=0, pady=15, sticky="w")
        
        self.scan_interval_var = tk.StringVar(value=str(config.SCAN_INTERVAL_SECONDS))
        txt_interval = tk.Entry(grid_frame, textvariable=self.scan_interval_var, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT, highlightbackground="#444444", font=("Segoe UI", 10), width=10, justify="center")
        txt_interval.grid(row=1, column=1, padx=20, pady=15, sticky="w", ipady=3)
        
        # SNMP settings
        lbl_snmp_port = tk.Label(grid_frame, text="Port SNMP (agents réels) :", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_snmp_port.grid(row=2, column=0, pady=15, sticky="w")
        
        self.snmp_port_var = tk.StringVar(value=str(config.SNMP_PORT))
        txt_snmp_port = tk.Entry(grid_frame, textvariable=self.snmp_port_var, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT, highlightbackground="#444444", font=("Segoe UI", 10), width=10, justify="center")
        txt_snmp_port.grid(row=2, column=1, padx=20, pady=15, sticky="w", ipady=3)
        
        # Simulator SNMP port setting
        lbl_sim_port = tk.Label(grid_frame, text="Port UDP du simulateur SNMP :", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_sim_port.grid(row=3, column=0, pady=15, sticky="w")
        
        self.sim_port_var = tk.StringVar(value=str(config.SIMULATOR_PORT))
        txt_sim_port = tk.Entry(grid_frame, textvariable=self.sim_port_var, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT, highlightbackground="#444444", font=("Segoe UI", 10), width=10, justify="center")
        txt_sim_port.grid(row=3, column=1, padx=20, pady=15, sticky="w", ipady=3)
        
        # Save button
        btn_save = tk.Button(
            settings_card,
            text="💾 Enregistrer la configuration",
            fg="#000000",
            bg=COLOR_SUCCESS,
            activeforeground="#000000",
            activebackground="#26B26E",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self.save_settings
        )
        btn_save.pack(anchor="sw", pady=(30, 0))
        
        return page

    def save_settings(self):
        try:
            config.SIMULATOR_ENABLED = self.sim_enabled_var.get()
            config.SCAN_INTERVAL_SECONDS = int(self.scan_interval_var.get().strip())
            config.SNMP_PORT = int(self.snmp_port_var.get().strip())
            config.SIMULATOR_PORT = int(self.sim_port_var.get().strip())
            
            # Application des changements de configuration
            messagebox.showinfo("Succès", "Paramètres système enregistrés avec succès !")
            self.refresh_dashboard_data()
        except ValueError:
            messagebox.showerror("Erreur", "Veuillez saisir des valeurs numériques valides pour les ports et intervalles.")

    # ==========================================
    # 🚪 DÉCONNEXION (changement d'utilisateur)
    # ==========================================
    def se_deconnecter(self):
        """
        Ferme la fenêtre actuelle et signale à main.py qu'il faut
        revenir à l'écran de connexion, afin qu'un autre utilisateur
        puisse se connecter sur ce même poste sans relancer tout le
        programme (les threads de scan/SNMP en arrière-plan continuent
        de tourner).
        """
        if messagebox.askyesno("Déconnexion", "Voulez-vous vraiment vous déconnecter ?\nUn autre utilisateur pourra alors se connecter."):
            self.demande_deconnexion = True
            self.root.destroy()

    # ==========================================
    # BACKGROUND REFRESH LOOP
    # ==========================================
    def gui_refresh_loop(self):
        """Rafraîchit périodiquement les données de l'onglet actif."""
        try:
            if self.current_tab == "dashboard":
                self.refresh_dashboard_data()
            elif self.current_tab == "snmp" and self.last_selected_snmp_ip:
                self.on_snmp_host_select(None)
        except Exception as e:
            print(f"Error in gui_refresh_loop: {e}")
            
        # Exécution toutes les 5 secondes
        self.root.after(5000, self.gui_refresh_loop)
