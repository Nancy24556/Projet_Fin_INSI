import os

# ============================================================
# Fichier de configuration central de l'application
# ============================================================

# --- Base de données ---
# Base SQLite locale, alignee sur le schema gestion__snmp.sql
# (tables : equipement, historique, presence, utilisateur)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

# --- Scanner reseau (detection de presence) ---
DEFAULT_SUBNET = "192.168.1.0/24"   # Sous-reseau scanne par defaut (modifiable dans l'interface)
SCAN_INTERVAL_SECONDS = 30          # Intervalle entre deux scans de presence
PING_TIMEOUT_MS = 300               # Delai d'attente du ping (millisecondes)
MAX_SCAN_THREADS = 50               # Nombre de threads paralleles pour le scan

# --- Gestionnaire / Agents SNMP (communication par Socket) ---
# Le "gestionnaire" (manager.py / snmp.py) interroge des "agents" via
# une connexion Socket UDP avec un petit protocole texte/JSON maison,
# puis se rabat sur le vrai protocole SNMP (librairie pysnmp) si
# l'equipement est un vrai agent SNMP (routeur, switch, etc.).
SNMP_COMMUNITY = "public"
SNMP_PORT = 161                     # Port SNMP standard (agents reels)
SNMP_POLLING_INTERVAL_SECONDS = 60  # Intervalle d'interrogation des agents
SNMP_TIMEOUT_SECONDS = 3            # Delai d'attente d'une reponse d'agent

# --- Simulateur d'agents (utile en l'absence d'un vrai reseau SNMP) ---
# Chaque equipement simule tourne comme un veritable agent Socket,
# sur sa propre adresse/port, dans un thread demarre par main.py.
SIMULATOR_ENABLED = True
SIMULATOR_HOST = "127.0.0.1"
SIMULATOR_PORT = 1161               # Port de base ; chaque agent simule prend PORT, PORT+1, PORT+2...

# --- OID standards MIB-II (utilises pour les vrais agents SNMP) ---
OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
}
