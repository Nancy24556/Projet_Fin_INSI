"""
agent.py
========
Implementation d'un AGENT SNMP simplifie qui communique avec le
GESTIONNAIRE (voir snmp.py) exclusivement via des Sockets UDP.

Cela repond a l'exigence du sujet :
    "Communication entre un gestionnaire SNMP et un ou plusieurs
     agents SNMP"

Principe
--------
- L'agent ouvre un Socket UDP et reste a l'ecoute sur (hote, port).
- Le gestionnaire lui envoie une petite requete JSON : {"commande": "GET"}
- L'agent repond avec un JSON contenant ses informations :
    nom de l'equipement, description, temps de fonctionnement
    (uptime), emplacement, contact, adresse IP.

Ce protocole "maison" simule le comportement d'un agent SNMP (qui, en
realite, repond aussi a des requetes UDP - le vrai protocole SNMP
tourne lui-meme au-dessus de sockets UDP sur le port 161). Pour les
vrais equipements SNMP du reseau (routeurs, switches...), le
gestionnaire (snmp.py) utilise en complement la librairie pysnmp,
qui parle le protocole SNMP standard.

Utilisation en mode autonome (agent installe sur une autre machine
reelle du reseau) :
    python agent.py --host 0.0.0.0 --port 1161 --nom "PC-Salle2"

Utilisation interne (agents simules) :
    Le fichier main.py demarre automatiquement un agent (dans un
    thread) pour chaque equipement simule defini dans snmp.py, afin
    que le gestionnaire puisse dialoguer avec de "vrais" sockets
    meme sans materiel reseau reel.
"""

import argparse
import json
import socket
import threading
import time


class AgentSNMP:
    """
    Un agent SNMP simplifie. Ecoute en UDP et repond aux requetes du
    gestionnaire avec ses informations systeme (equivalent des OID
    MIB-II : sysName, sysDescr, sysUpTime, sysLocation, sysContact).
    """

    def __init__(self, host, port, nom, description="Agent SNMP", emplacement="Inconnu", contact="admin@local"):
        self.host = host
        self.port = port
        self.nom = nom
        self.description = description
        self.emplacement = emplacement
        self.contact = contact
        self.heure_demarrage = time.time()

        self._socket = None
        self._en_marche = False
        self._thread = None

    # --------------------------------------------------------
    # Cycle de vie
    # --------------------------------------------------------
    def demarrer(self):
        """Ouvre le socket UDP et lance la boucle d'ecoute dans un thread demon."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(1.0)
        self._en_marche = True

        self._thread = threading.Thread(target=self._boucle_ecoute, daemon=True)
        self._thread.start()
        print(f"[agent] {self.nom} en ecoute sur {self.host}:{self.port} (Socket UDP)")

    def arreter(self):
        self._en_marche = False
        if self._socket:
            self._socket.close()

    # --------------------------------------------------------
    # Boucle principale : reception des requetes du gestionnaire
    # --------------------------------------------------------
    def _boucle_ecoute(self):
        while self._en_marche:
            try:
                donnees, adresse_gestionnaire = self._socket.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                requete = json.loads(donnees.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue

            reponse = self._traiter_requete(requete)
            try:
                self._socket.sendto(json.dumps(reponse).encode("utf-8"), adresse_gestionnaire)
            except OSError:
                pass

    def _traiter_requete(self, requete):
        """Construit la reponse envoyee au gestionnaire selon la commande recue."""
        commande = requete.get("commande", "GET")

        if commande != "GET":
            return {"erreur": "commande inconnue"}

        uptime_secondes = int(time.time() - self.heure_demarrage)
        heures, reste = divmod(uptime_secondes, 3600)
        minutes, secondes = divmod(reste, 60)
        uptime_str = f"{heures}h {minutes}m {secondes}s"

        return {
            "sysName": self.nom,
            "sysDescr": self.description,
            "sysUpTime": uptime_str,
            "sysLocation": self.emplacement,
            "sysContact": self.contact,
            "adresse_ip": self.host,
            "horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def demarrer_agent_local(port, nom, description="Agent simule", emplacement="Reseau local", contact="admin@local", host="127.0.0.1"):
    """
    Petite fonction utilitaire utilisee par main.py pour lancer un agent
    simule en arriere-plan (dans le meme processus, via un thread demon).
    Retourne l'instance AgentSNMP (pour pouvoir l'arreter si besoin).
    """
    agent = AgentSNMP(host, port, nom, description, emplacement, contact)
    agent.demarrer()
    return agent


# ============================================================
# Point d'entree : permet de lancer un agent en mode autonome,
# par exemple sur un poste distant reel du reseau.
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent SNMP (communication par Socket UDP)")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'ecoute de l'agent")
    parser.add_argument("--port", type=int, default=1161, help="Port UDP d'ecoute de l'agent")
    parser.add_argument("--nom", default=socket.gethostname(), help="Nom systeme (sysName) annonce par l'agent")
    parser.add_argument("--emplacement", default="Non specifie", help="Emplacement (sysLocation)")
    parser.add_argument("--contact", default="admin@local", help="Contact (sysContact)")
    args = parser.parse_args()

    agent = AgentSNMP(args.host, args.port, args.nom, f"Agent SNMP sur {socket.gethostname()}", args.emplacement, args.contact)
    agent.demarrer()

    print("[agent] Appuyez sur Ctrl+C pour arreter l'agent.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[agent] Arret de l'agent.")
        agent.arreter()
