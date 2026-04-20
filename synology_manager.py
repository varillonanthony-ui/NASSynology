import sqlite3
import requests
import json
from typing import Optional, Dict, List, Any, Tuple
import urllib3
from datetime import datetime
import base64

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "nas.db"

# ============================================================================
# CLASSE: DatabaseManager
# ============================================================================

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nas (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                qc_id               TEXT NOT NULL UNIQUE,
                dsm_user            TEXT NOT NULL,
                dsm_password_enc    TEXT NOT NULL,
                location            TEXT DEFAULT '',
                enable_alerts       INTEGER DEFAULT 1,
                check_interval      INTEGER DEFAULT 6,
                last_checked        TEXT,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nas_id      INTEGER NOT NULL,
                alert_type  TEXT NOT NULL,
                message     TEXT NOT NULL,
                severity    TEXT DEFAULT 'warning',
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                is_read     INTEGER DEFAULT 0,
                FOREIGN KEY (nas_id) REFERENCES nas(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nas_id      INTEGER NOT NULL,
                action      TEXT NOT NULL,
                status      TEXT,
                details     TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nas_id) REFERENCES nas(id)
            )
        ''')
        conn.commit()
        conn.close()

    def encrypt_password(self, password: str) -> str:
        return base64.b64encode(password.encode()).decode()

    def decrypt_password(self, encrypted: str) -> str:
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except:
            return encrypted

    def get_all_nas(self) -> list:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM nas ORDER BY name")
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_nas(self, name, qc_id, user, password, location='', enable_alerts=True) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            enc = self.encrypt_password(password)
            c.execute("""
                INSERT INTO nas (name, qc_id, dsm_user, dsm_password_enc, location, enable_alerts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, qc_id, user, enc, location, 1 if enable_alerts else 0))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_nas(self, nas_id: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM nas WHERE id = ?", (nas_id,))
        c.execute("DELETE FROM alerts WHERE nas_id = ?", (nas_id,))
        c.execute("DELETE FROM history WHERE nas_id = ?", (nas_id,))
        conn.commit()
        conn.close()

    def update_nas(self, nas_id, name, qc_id, user, password, location='', enable_alerts=True):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        enc = self.encrypt_password(password)
        c.execute("""
            UPDATE nas SET name=?, qc_id=?, dsm_user=?, dsm_password_enc=?,
                           location=?, enable_alerts=?, updated_at=?
            WHERE id=?
        """, (name, qc_id, user, enc, location, 1 if enable_alerts else 0,
              datetime.now().isoformat(), nas_id))
        conn.commit()
        conn.close()

    def add_alert(self, nas_id, alert_type, message, severity='warning') -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('INSERT INTO alerts (nas_id, alert_type, message, severity) VALUES (?,?,?,?)',
                      (nas_id, alert_type, message, severity))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def get_alerts(self, nas_id=None, unread_only=False) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if nas_id and unread_only:
                c.execute('SELECT * FROM alerts WHERE nas_id=? AND is_read=0 ORDER BY created_at DESC', (nas_id,))
            elif nas_id:
                c.execute('SELECT * FROM alerts WHERE nas_id=? ORDER BY created_at DESC', (nas_id,))
            elif unread_only:
                c.execute('SELECT * FROM alerts WHERE is_read=0 ORDER BY created_at DESC')
            else:
                c.execute('SELECT * FROM alerts ORDER BY created_at DESC')
            rows = c.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except:
            return []

    def mark_alert_read(self, alert_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('UPDATE alerts SET is_read=1 WHERE id=?', (alert_id,))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def add_history(self, nas_id, action, status='pending', details=None) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('INSERT INTO history (nas_id, action, status, details) VALUES (?,?,?,?)',
                      (nas_id, action, status, details))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def get_history(self, nas_id=None, limit=100) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if nas_id:
                c.execute('SELECT * FROM history WHERE nas_id=? ORDER BY created_at DESC LIMIT ?', (nas_id, limit))
            else:
                c.execute('SELECT * FROM history ORDER BY created_at DESC LIMIT ?', (limit,))
            rows = c.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except:
            return []

    def update_last_checked(self, nas_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('UPDATE nas SET last_checked=? WHERE id=?', (datetime.now().isoformat(), nas_id))
            conn.commit()
            conn.close()
            return True
        except:
            return False


# ============================================================================
# CLASSE: SynologyManager
# ============================================================================

class SynologyManager:
    def __init__(self, db_manager=None):
        self.sessions  = {}   # qc_id -> session info
        self.base_urls = {}   # qc_id -> URL réelle résolue
        self.db        = db_manager or DatabaseManager()

    # ─────────────────────────────────────────────────────────────────────
    # Résolution QuickConnect → IP/URL réelle du NAS
    # ─────────────────────────────────────────────────────────────────────

    def _clean_qc_id(self, qc_id: str) -> str:
        """Extrait l'ID pur depuis une URL ou un ID brut"""
        qc_id = qc_id.strip()
        for prefix in ["https://", "http://"]:
            qc_id = qc_id.replace(prefix, "")
        qc_id = qc_id.replace("QuickConnect.to/", "")
        qc_id = qc_id.replace("quickconnect.to", "")
        return qc_id.strip("/")

    def _resolve_quickconnect(self, qc_id: str, logs: list) -> List[str]:
        """
        Appelle l'API relay Synology pour obtenir les URLs directes du NAS.
        Retourne une liste d'URLs à essayer dans l'ordre.
        """
        urls = []
        try:
            logs.append(f"🔍 Résolution QuickConnect pour `{qc_id}` via relay Synology…")
            relay = "https://global.quickconnect.to/Serv.php"
            payload = {
                "version": 1,
                "command": "get_server_info",
                "stop_when_error": False,
                "stop_when_success": False,
                "id": "qc_direct",
                "serverID": qc_id,
                "is_gofile": False
            }
            r = requests.post(relay, json=payload, timeout=10, verify=False)
            data = r.json()
            server = data.get("server", {})

            if not server:
                logs.append("⚠️ Relay n'a pas retourné d'infos serveur")
                return urls

            # 1. IP externe
            ext_ip = server.get("external", {}).get("ip", "")
            if ext_ip:
                logs.append(f"📡 IP externe trouvée : `{ext_ip}`")
                urls.append(f"https://{ext_ip}:5001")
                urls.append(f"http://{ext_ip}:5000")

            # 2. DDNS Synology
            ddns = server.get("ddns", "")
            if ddns and ddns not in ("NULL", ""):
                logs.append(f"🌐 DDNS trouvé : `{ddns}`")
                urls.append(f"https://{ddns}:5001")
                urls.append(f"http://{ddns}:5000")

            # 3. FQDN personnalisé
            fqdn = server.get("fqdn", "")
            if fqdn and fqdn not in ("NULL", ""):
                logs.append(f"🌐 FQDN trouvé : `{fqdn}`")
                urls.append(f"https://{fqdn}:5001")
                urls.append(f"http://{fqdn}:5000")

            # 4. IPs LAN (utile si même réseau)
            for iface in server.get("interface", []):
                lan_ip = iface.get("ip", "")
                if lan_ip:
                    logs.append(f"🏠 IP LAN trouvée : `{lan_ip}`")
                    urls.append(f"http://{lan_ip}:5000")
                    urls.append(f"https://{lan_ip}:5001")

        except Exception as e:
            logs.append(f"⚠️ Erreur relay : `{e}`")

        return urls

    def _try_auth(self, base_url: str, username: str, password: str,
                  logs: list) -> Tuple[bool, Optional[requests.Session], Optional[str]]:
        """
        Tente une authentification DSM sur base_url.
        Retourne (succès, session, sid).
        """
        try:
            session = requests.Session()
            session.verify = False
            auth_url = f"{base_url}/webapi/auth.cgi"
            params = {
                "api":     "SYNO.API.Auth",
                "version": "3",
                "method":  "login",
                "account": username,
                "passwd":  password,
                "session": "SynologyManager",
                "format":  "json",
            }
            logs.append(f"🔗 Essai : `{auth_url}`")
            resp = session.get(auth_url, params=params, timeout=8, verify=False)

            # Vérifie que c'est bien du JSON (pas du HTML)
            ct = resp.headers.get("Content-Type", "")
            if "html" in ct or resp.text.strip().startswith("<!"):
                logs.append(f"   ↳ ❌ Réponse HTML (pas le bon endpoint)")
                return False, None, None

            data = resp.json()
            if data.get("success"):
                sid = data.get("data", {}).get("sid")
                if sid:
                    logs.append(f"   ↳ ✅ Authentification réussie!")
                    return True, session, sid

            code = data.get("error", {}).get("code", "?")
            msg = {
                400: "Identifiants invalides",
                401: "Compte désactivé",
                402: "Permission refusée",
                403: "2FA requis",
                407: "IP bloquée",
            }.get(code, f"Erreur DSM code {code}")
            logs.append(f"   ↳ ❌ {msg}")
            return False, None, None

        except requests.exceptions.ConnectionError:
            logs.append(f"   ↳ ❌ Injoignable")
            return False, None, None
        except requests.exceptions.Timeout:
            logs.append(f"   ↳ ❌ Timeout")
            return False, None, None
        except Exception as e:
            logs.append(f"   ↳ ❌ Erreur : `{e}`")
            return False, None, None

    # ─────────────────────────────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────────────────────────────

    def verify_connection_debug(self, qc_id: str, username: str, password: str) -> dict:
        """Connexion avec logs détaillés. Retourne {success, logs, error}."""
        logs = []
        qc_id = self._clean_qc_id(qc_id)
        logs.append(f"✅ Quick Connect ID nettoyé : `{qc_id}`")

        # Résoudre les URLs via relay
        urls = self._resolve_quickconnect(qc_id, logs)

        if not urls:
            logs.append("❌ Aucune URL trouvée via le relay Synology")
            return {"success": False, "logs": logs, "error": "Aucune URL résolue"}

        logs.append(f"✅ {len(urls)} URL(s) à tester")

        # Tester chaque URL dans l'ordre
        for url in urls:
            ok, session, sid = self._try_auth(url, username, password, logs)
            if ok:
                self.sessions[qc_id] = {
                    "session":  session,
                    "sid":      sid,
                    "username": username,
                    "password": password,
                    "base_url": url,
                }
                self.base_urls[qc_id] = url
                logs.append(f"✅ Connexion établie via `{url}`")
                return {"success": True, "logs": logs, "error": None}

        logs.append("❌ Aucune URL n'a fonctionné")
        return {"success": False, "logs": logs, "error": "Toutes les URLs ont échoué"}

    def verify_connection(self, qc_id: str, username: str, password: str) -> bool:
        return self.verify_connection_debug(qc_id, username, password)["success"]

    def _get_session(self, qc_id: str, username: str, password: str):
        """Retourne la session active ou en crée une nouvelle."""
        qc_id = self._clean_qc_id(qc_id)
        if qc_id not in self.sessions:
            self.verify_connection(qc_id, username, password)
        return self.sessions.get(qc_id)

    def check_server_status(self, qc_id, username, password):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password)
            if not sd:
                return {"is_online": False, "error": "Connexion échouée"}
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Info", "version": "2",
                        "method": "getinfo", "_sid": sd["sid"]},
                timeout=10, verify=False
            )
            data = resp.json()
            if data.get("success"):
                info = data.get("data", {})
                return {
                    "is_online":   True,
                    "dsm_version": info.get("dsm_version"),
                    "hostname":    info.get("hostname"),
                    "uptime":      info.get("uptime"),
                }
            return {"is_online": False}
        except Exception as e:
            return {"is_online": False, "error": str(e)}

    def check_updates(self, qc_id, username, password):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password)
            if not sd:
                return None
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Software", "version": "3",
                        "method": "check", "_sid": sd["sid"]},
                timeout=10, verify=False
            )
            data = resp.json()
            if data.get("success") and data.get("data", {}).get("update_available"):
                return [{"type": "dsm",
                         "version": data["data"].get("latest_version"),
                         "description": "Mise à jour DSM"}]
            return None
        except:
            return None

    def install_updates(self, qc_id, username, password) -> bool:
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password)
            if not sd:
                return False
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Software", "version": "3",
                        "method": "install", "_sid": sd["sid"]},
                timeout=10, verify=False
            )
            return resp.json().get("success", False)
        except:
            return False

    def get_system_alerts(self, qc_id, username, password):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password)
            if not sd:
                return []
            alerts = []
            try:
                r = sd["session"].get(
                    f"{sd['base_url']}/webapi/query.cgi",
                    params={"api": "SYNO.System.Event.Service", "version": "1",
                            "method": "get", "_sid": sd["sid"]},
                    timeout=10, verify=False
                )
                data = r.json()
                if data.get("success"):
                    for event in data.get("data", {}).get("events", []):
                        if event.get("severity") in ["critical", "major"]:
                            alerts.append({
                                "type":    "error" if event["severity"] == "critical" else "warning",
                                "message": event.get("description", "Alerte système"),
                            })
            except:
                pass
            return alerts
        except:
            return []

    def logout(self, qc_id: str) -> bool:
        try:
            qc_id = self._clean_qc_id(qc_id)
            if qc_id not in self.sessions:
                return True
            sd = self.sessions[qc_id]
            sd["session"].get(
                f"{sd['base_url']}/webapi/auth.cgi",
                params={"api": "SYNO.API.Auth", "version": "1",
                        "method": "logout", "_sid": sd["sid"]},
                timeout=10, verify=False
            )
            del self.sessions[qc_id]
            return True
        except:
            return False