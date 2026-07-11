"""
snmp.py
=======
Cote GESTIONNAIRE (manager) de la supervision SNMP.

Communique avec les agents (voir agent.py) via un Socket UDP :
    1. Le gestionnaire envoie {"commande": "GET"} a l'agent (ip, port).
    2. L'agent repond avec ses informations systeme en JSON.

Pour les equipements qui ne sont pas des agents "maison" (ex: un vrai
routeur/switch qui parle le protocole SNMP standard sur le port 161),
le gestionnaire se rabat sur la librairie pysnmp si elle est
installee.
"""

import json
import socket
import time
import platform

import config

# La librairie pysnmp est optionnelle : si elle n'est pas installee,
# on peut quand meme interroger nos agents "maison" via Socket.
PYSNMP_AVAILABLE = False
try:
    from pysnmp.hlapi import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, getCmd
    PYSNMP_AVAILABLE = True
except ImportError:
    pass

# Heure de demarrage de l'application (utile pour un uptime de secours)
HEURE_DEMARRAGE_APP = time.time()

# ============================================================
# Equipements simules : chacun tourne comme un veritable agent
# Socket (voir agent.py), demarre automatiquement par main.py sur
# son propre port (SIMULATOR_PORT, SIMULATOR_PORT+1, ...).
# Cela permet de demontrer une vraie communication gestionnaire/
# agents par Socket meme sans materiel reseau reel.
# ============================================================
SIMULATED_DEVICES = {
    "127.0.0.1": {
        "port": config.SIMULATOR_PORT,
        "sysName": "Poste-Superviseur",
        "sysDescr": f"Poste de travail - Python {platform.python_version()} - Noeud de supervision",
        "sysLocation": "Bureau operateur",
        "sysContact": "net-operator@local",
    },
    "192.168.1.50": {
        "port": config.SIMULATOR_PORT + 1,
        "sysName": "Imprimante-HP-50",
        "sysDescr": "HP LaserJet Pro MFP M227fdw",
        "sysLocation": "Salle de reprographie",
        "sysContact": "it-support@entreprise.com",
    },
    "192.168.1.100": {
        "port": config.SIMULATOR_PORT + 2,
        "sysName": "Switch-Central-100",
        "sysDescr": "Commutateur reseau 48 ports",
        "sysLocation": "Baie principale - Salle serveur",
        "sysContact": "net-admin@entreprise.com",
    },
    "192.168.1.150": {
        "port": config.SIMULATOR_PORT + 3,
        "sysName": "Serveur-Linux-150",
        "sysDescr": "Serveur Linux (supervision de test)",
        "sysLocation": "Baie C-12 - Datacenter",
        "sysContact": "sys-team@entreprise.com",
    },
}


def is_simulated_ip(ip):
    """Indique si l'IP correspond a un agent simule connu."""
    return ip in SIMULATED_DEVICES


def get_agent_port(ip):
    """Retourne le port UDP de l'agent simule associe a cette IP (ou le port SNMP par defaut)."""
    if is_simulated_ip(ip):
        return SIMULATED_DEVICES[ip]["port"]
    return config.SNMP_PORT


# ============================================================
# GESTIONNAIRE : requete via Socket UDP vers un agent "maison"
# ============================================================
def _interroger_agent_par_socket(ip, port, timeout=config.SNMP_TIMEOUT_SECONDS):
    """
    Envoie une requete GET a l'agent (ip, port) via un Socket UDP et
    attend sa reponse JSON. Retourne un dict d'OID -> valeur, ou None
    si l'agent ne repond pas (hors ligne, mauvais port, etc.).
    """
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(timeout)
    try:
        requete = json.dumps({"commande": "GET"}).encode("utf-8")
        client.sendto(requete, (ip, port))

        donnees, _ = client.recvfrom(2048)
        reponse = json.loads(donnees.decode("utf-8"))

        if "erreur" in reponse:
            return None

        return {
            config.OIDS["sysName"]: reponse.get("sysName", "Inconnu"),
            config.OIDS["sysDescr"]: reponse.get("sysDescr", "Inconnu"),
            config.OIDS["sysUpTime"]: reponse.get("sysUpTime", "Inconnu"),
            config.OIDS["sysLocation"]: reponse.get("sysLocation", "Inconnu"),
            config.OIDS["sysContact"]: reponse.get("sysContact", "Inconnu"),
        }
    except (socket.timeout, OSError, ValueError):
        return None
    finally:
        client.close()


# ============================================================
# GESTIONNAIRE : requete SNMP standard (pysnmp) pour un vrai agent
# ============================================================
def _interroger_agent_snmp_reel(ip, community=config.SNMP_COMMUNITY, port=config.SNMP_PORT):
    """Interroge un vrai agent SNMP (protocole standard) via pysnmp."""
    if not PYSNMP_AVAILABLE:
        return None

    oids_a_lire = list(config.OIDS.values())

    try:
        iterateur = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, port), timeout=config.SNMP_TIMEOUT_SECONDS, retries=1),
            ContextData(),
            *[ObjectType(ObjectIdentity(oid)) for oid in oids_a_lire]
        )

        erreur_indication, erreur_statut, erreur_index, variables = next(iterateur)

        if erreur_indication or erreur_statut:
            return None

        resultats = {}
        for variable in variables:
            resultats[str(variable[0])] = str(variable[1])
        return resultats

    except Exception as e:
        print(f"[gestionnaire] Erreur SNMP reelle vers {ip} : {e}")
        return None


# ============================================================
# Point d'entree public utilise par main.py / interface.py :
# le "gestionnaire" essaie d'abord la communication Socket avec un
# agent "maison", puis se rabat sur un vrai agent SNMP (pysnmp).
# ============================================================
def query_snmp_device(ip, community=config.SNMP_COMMUNITY, port=None):
    """
    Interroge un equipement et retourne ses informations
    (sysName, sysDescr, sysUpTime, sysLocation, sysContact) sous
    forme de dict indexe par OID, ou None si l'equipement ne repond
    par aucun des deux moyens de communication.
    """
    port_agent = port if port is not None else get_agent_port(ip)

    # 1. Communication par Socket avec notre agent "maison"
    resultat = _interroger_agent_par_socket(ip, port_agent)
    if resultat is not None:
        return resultat

    # 2. Repli sur un vrai agent SNMP standard (materiel reseau reel)
    return _interroger_agent_snmp_reel(ip, community, config.SNMP_PORT)
