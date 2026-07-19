import sqlite3
import hashlib
import secrets
import uuid
from datetime import datetime
import config


def get_connection():
    
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
   
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipement (
        id TEXT PRIMARY KEY,
        nom TEXT,
        adresse_ip TEXT UNIQUE,
        type TEXT,
        etat TEXT,
        cpu TEXT,
        memoire TEXT,
        temps_fonctionment INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historique (
        id TEXT PRIMARY KEY,
        date DATETIME,
        action TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS presence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adresse_ip TEXT,
        date_connexion DATETIME,
        date_deconnexion DATETIME,
        statut TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateur (
        id TEXT PRIMARY KEY,
        nom TEXT,
        email TEXT UNIQUE,
        mot_de_passe TEXT
    )
    """)

    conn.commit()
    conn.close()
    _seed_default_admin()



def _hash_password(password, salt=None):
   
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password, stored_hash):
    try:
        salt, _ = stored_hash.split("$", 1)
    except (ValueError, AttributeError):
        return False
    return secrets.compare_digest(_hash_password(password, salt), stored_hash)


def _seed_default_admin():
   
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM utilisateur")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute(
            "INSERT INTO utilisateur (id, nom, email, mot_de_passe) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "Administrateur", "admin@local", _hash_password("admin123"))
        )
        conn.commit()
        print("[*] Compte administrateur par defaut cree -> email: admin@local | mot de passe: admin123")
    conn.close()


def create_user(nom, email, password):
    
    if not nom or not email or not password:
        return False, "Tous les champs sont obligatoires."
    if len(password) < 4:
        return False, "Le mot de passe doit contenir au moins 4 caracteres."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO utilisateur (id, nom, email, mot_de_passe) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), nom, email.strip().lower(), _hash_password(password))
        )
        _insert_historique(cursor, f"COMPTE|{email}|cree")
        conn.commit()
        return True, "Compte cree avec succes."
    except sqlite3.IntegrityError:
        return False, "Cet email est deja utilise."
    finally:
        conn.close()


def verify_login(email, password):
   
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM utilisateur WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()

    if row is not None and _verify_password(password, row["mot_de_passe"]):
        _insert_historique(cursor, f"LOGIN|{email}|succes")
        conn.commit()
        conn.close()
        return True, dict(row)

    _insert_historique(cursor, f"LOGIN|{email}|echec")
    conn.commit()
    conn.close()
    return False, None



def _insert_historique(cursor, action_text):
    
    cursor.execute(
        "INSERT INTO historique (id, date, action) VALUES (?, ?, ?)",
        (str(uuid.uuid4()), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action_text)
    )



def register_host(ip, hostname, status, mac_address=""):
   
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    etat = "actif" if status == "active" else "inactif"

    cursor.execute("SELECT etat, nom FROM equipement WHERE adresse_ip = ?", (ip,))
    row = cursor.fetchone()

    status_changed = False

    if row is None:
        status_changed = True
        cursor.execute("""
            INSERT INTO equipement (id, nom, adresse_ip, type, etat, cpu, memoire, temps_fonctionment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), hostname, ip, "Equipement reseau", etat, None, None, None))

        if status == "active":
            cursor.execute("""
                INSERT INTO presence (adresse_ip, date_connexion, date_deconnexion, statut)
                VALUES (?, ?, NULL, ?)
            """, (ip, now_str, "connecte"))

        _insert_historique(cursor, f"DECOUVERTE|{ip}|{hostname or 'Inconnu'}|{etat}")
    else:
        old_etat = row["etat"]
        old_nom = row["nom"]

        if old_etat != etat:
            status_changed = True
            if status == "active":
                cursor.execute("""
                    INSERT INTO presence (adresse_ip, date_connexion, date_deconnexion, statut)
                    VALUES (?, ?, NULL, ?)
                """, (ip, now_str, "connecte"))
                _insert_historique(cursor, f"CONNEXION|{ip}|{hostname or old_nom or 'Inconnu'}")
            else:
                cursor.execute("""
                    UPDATE presence SET date_deconnexion = ?, statut = ?
                    WHERE adresse_ip = ? AND date_deconnexion IS NULL
                """, (now_str, "deconnecte", ip))
                _insert_historique(cursor, f"DECONNEXION|{ip}|{old_nom or 'Inconnu'}")

        cursor.execute("""
            UPDATE equipement SET nom = ?, etat = ? WHERE adresse_ip = ?
        """, (hostname or old_nom, etat, ip))

    conn.commit()
    conn.close()
    return status_changed


def add_snmp_record(ip, sys_name, sys_descr, sys_uptime, sys_location, sys_contact):
   
    conn = get_connection()
    cursor = conn.cursor()

    temps_fonctionment = None
    try:
        digits = "".join(ch for ch in str(sys_uptime).split("(")[0] if ch.isdigit())
        if digits:
            temps_fonctionment = int(digits)
    except Exception:
        temps_fonctionment = None

    cursor.execute("""
        UPDATE equipement
        SET nom = COALESCE(?, nom), type = ?, temps_fonctionment = ?
        WHERE adresse_ip = ?
    """, (sys_name, sys_descr, temps_fonctionment, ip))

    _insert_historique(
        cursor,
        f"SNMP|{ip}|{sys_name}|{sys_descr}|{sys_uptime}|{sys_location}|{sys_contact}"
    )

    conn.commit()
    conn.close()


def get_hosts():
   
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipement ORDER BY adresse_ip")
    equipements = cursor.fetchall()

    results = []
    for eq in equipements:
        ip = eq["adresse_ip"]

        cursor.execute("""
            SELECT date_connexion, date_deconnexion FROM presence
            WHERE adresse_ip = ?
            ORDER BY id DESC LIMIT 1
        """, (ip,))
        p = cursor.fetchone()
        if p is None:
            last_seen = None
        else:
            last_seen = p["date_deconnexion"] or p["date_connexion"]

        cursor.execute("SELECT COUNT(*) FROM historique WHERE action LIKE ?", (f"SNMP|{ip}|%",))
        is_snmp_enabled = 1 if cursor.fetchone()[0] > 0 else 0

        results.append({
            "ip": ip,
            "hostname": eq["nom"],
            "status": "active" if eq["etat"] == "actif" else "inactive",
            "last_seen": last_seen,
            "is_snmp_enabled": is_snmp_enabled,
            "mac_address": "",
        })

    conn.close()
    return results


def get_events(limit=100):
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT adresse_ip, date_connexion, date_deconnexion FROM presence
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()

    cursor.execute("SELECT adresse_ip, nom FROM equipement")
    noms = {r["adresse_ip"]: r["nom"] for r in cursor.fetchall()}
    conn.close()

    events = []
    for r in rows:
        ip = r["adresse_ip"]
        nom = noms.get(ip) or "Inconnu"
        if r["date_deconnexion"]:
            events.append({
                "timestamp": r["date_deconnexion"],
                "ip": ip,
                "event_type": "disconnection",
                "details": f"Equipement hors ligne : {nom} ({ip})",
            })
        if r["date_connexion"]:
            events.append({
                "timestamp": r["date_connexion"],
                "ip": ip,
                "event_type": "connection",
                "details": f"Equipement en ligne : {nom} ({ip})",
            })

    events.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    return events[:limit]


def get_presence_log(limit=200):
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT adresse_ip, date_connexion, date_deconnexion, statut FROM presence
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()

    cursor.execute("SELECT adresse_ip, nom FROM equipement")
    noms = {r["adresse_ip"]: r["nom"] for r in cursor.fetchall()}
    conn.close()

    now = datetime.now()
    log = []
    for r in rows:
        ip = r["adresse_ip"]
        nom = noms.get(ip) or "Inconnu"
        debut_str = r["date_connexion"]
        fin_str = r["date_deconnexion"]
        connecte = fin_str is None

        try:
            debut_dt = datetime.strptime(debut_str, "%Y-%m-%d %H:%M:%S") if debut_str else None
        except ValueError:
            debut_dt = None

        try:
            fin_dt = datetime.strptime(fin_str, "%Y-%m-%d %H:%M:%S") if fin_str else now
        except ValueError:
            fin_dt = now

        duree_secondes = int((fin_dt - debut_dt).total_seconds()) if debut_dt else 0
        duree_secondes = max(0, duree_secondes)

        heures, reste = divmod(duree_secondes, 3600)
        minutes, secondes = divmod(reste, 60)
        duree_str = f"{heures}h {minutes}m {secondes}s"

        log.append({
            "ip": ip,
            "nom": nom,
            "date_connexion": debut_str or "-",
            "date_deconnexion": fin_str or "-",
            "statut": "Connecte" if connecte else "Deconnecte",
            "duree_secondes": duree_secondes,
            "duree": duree_str,
        })

    return log


def get_connected_now(limit=100):
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT adresse_ip, date_connexion FROM presence
        WHERE date_deconnexion IS NULL
        ORDER BY date_connexion DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()

    cursor.execute("SELECT adresse_ip, nom FROM equipement")
    noms = {r["adresse_ip"]: r["nom"] for r in cursor.fetchall()}
    conn.close()

    now = datetime.now()
    connectes = []
    for r in rows:
        ip = r["adresse_ip"]
        nom = noms.get(ip) or "Inconnu"
        debut_str = r["date_connexion"]

        try:
            debut_dt = datetime.strptime(debut_str, "%Y-%m-%d %H:%M:%S") if debut_str else None
        except ValueError:
            debut_dt = None

        duree_secondes = max(0, int((now - debut_dt).total_seconds())) if debut_dt else 0
        heures, reste = divmod(duree_secondes, 3600)
        minutes, secondes = divmod(reste, 60)

        connectes.append({
            "ip": ip,
            "nom": nom,
            "date_connexion": debut_str or "-",
            "duree": f"{heures}h {minutes}m {secondes}s",
            "duree_secondes": duree_secondes,
        })

    return connectes


def get_snmp_history(ip, limit=50):
   
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, action FROM historique
        WHERE action LIKE ?
        ORDER BY date DESC LIMIT ?
    """, (f"SNMP|{ip}|%", limit))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        parts = r["action"].split("|")
        if len(parts) < 7:
            continue
        history.append({
            "timestamp": r["date"],
            "ip": parts[1],
            "sys_name": parts[2],
            "sys_descr": parts[3],
            "sys_uptime": parts[4],
            "sys_location": parts[5],
            "sys_contact": parts[6],
        })
    return history


def clear_database():
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM equipement")
    cursor.execute("DELETE FROM historique")
    cursor.execute("DELETE FROM presence")
    conn.commit()
    conn.close()
