from datetime import datetime, timedelta
import database



def get_dashboard_stats():
  
    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM equipement")
    total_hosts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM equipement WHERE etat = 'actif'")
    active_hosts = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT adresse_ip) FROM equipement e
        WHERE EXISTS (
            SELECT 1 FROM historique h WHERE h.action LIKE ('SNMP|' || e.adresse_ip || '|%')
        )
    """)
    snmp_hosts = cursor.fetchone()[0]

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT COUNT(*) FROM presence
        WHERE date_deconnexion IS NOT NULL AND date_deconnexion >= ?
    """, (yesterday,))
    alerts = cursor.fetchone()[0]

    conn.close()

    return {
        "total_hosts": total_hosts,
        "active_hosts": active_hosts,
        "snmp_hosts": snmp_hosts,
        "alerts": alerts
    }


def get_host_availability(ip):
  
    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT MIN(date_connexion) FROM presence WHERE adresse_ip = ?", (ip,))
    first_row = cursor.fetchone()
    first_time_str = first_row[0] if first_row and first_row[0] else None

    if not first_time_str:
        cursor.execute("SELECT etat FROM equipement WHERE adresse_ip = ?", (ip,))
        row = cursor.fetchone()
        conn.close()
        if row and row["etat"] == "actif":
            return 100.0
        return 0.0

    first_time = datetime.strptime(first_time_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    total_monitored_duration = (now - first_time).total_seconds()

    if total_monitored_duration <= 0:
        conn.close()
        return 100.0

    cursor.execute("""
        SELECT date_connexion, date_deconnexion FROM presence
        WHERE adresse_ip = ?
        ORDER BY date_connexion ASC
    """, (ip,))
    sessions = cursor.fetchall()
    conn.close()

    connected_seconds = 0.0
    for s in sessions:
        if not s["date_connexion"]:
            continue
        start = datetime.strptime(s["date_connexion"], "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(s["date_deconnexion"], "%Y-%m-%d %H:%M:%S") if s["date_deconnexion"] else now
        connected_seconds += max(0.0, (end - start).total_seconds())

    availability = (connected_seconds / total_monitored_duration) * 100.0
    availability = max(0.0, min(100.0, availability))

    return round(availability, 2)


def get_device_status_distribution():
  
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT etat, COUNT(*) FROM equipement GROUP BY etat")
    rows = cursor.fetchall()
    conn.close()

    dist = {"active": 0, "inactive": 0}
    for row in rows:
        etat = row[0]
        count = row[1]
        if etat == "actif":
            dist["active"] = count
        elif etat == "inactif":
            dist["inactive"] = count
    return dist


def get_event_timeline_data():

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m-%d %H:00:00', horodatage) as heure, COUNT(*) as compte
        FROM (
            SELECT date_connexion as horodatage FROM presence WHERE date_connexion IS NOT NULL
            UNION ALL
            SELECT date_deconnexion as horodatage FROM presence WHERE date_deconnexion IS NOT NULL
        )
        GROUP BY heure
        ORDER BY heure DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    rows = list(reversed(rows))

    labels = [datetime.strptime(r["heure"], "%Y-%m-%d %H:%M:%S").strftime("%H:00") for r in rows]
    values = [r["compte"] for r in rows]

    if not labels:
        labels = ["No Data"]
        values = [0]

    return labels, values
