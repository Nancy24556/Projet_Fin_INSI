import os


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

DEFAULT_SUBNET = "192.168.1.0/24"
SCAN_INTERVAL_SECONDS = 30
PING_TIMEOUT_MS = 300
MAX_SCAN_THREADS = 50

SNMP_COMMUNITY = "public"
SNMP_PORT = 161
SNMP_POLLING_INTERVAL_SECONDS = 60
SNMP_TIMEOUT_SECONDS = 3

SIMULATOR_ENABLED = True
SIMULATOR_HOST = "127.0.0.1"
SIMULATOR_PORT = 1161

OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
}
