import sqlite3
import requests
import json
from typing import Optional, List, Tuple
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
                direct_url          TEXT DEFAULT '',
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

    def add_nas(self, name, qc_id, user, password, location='',
                direct_url='', enable_alerts=True) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            enc = self.encrypt_password(password)
            c.execute("""
                INSERT INTO nas (name, qc_id, dsm_user, dsm_password_enc,
                                 location, direct_url, enable_alerts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, qc_id, user, enc, location, direct_url,
                  1 if enable_alerts else 0))
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

    def update_nas(self, nas_id, name, qc_id, user, password,
                   location='', direct_url='', enable_alerts=True):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        enc = self.encrypt_password(password)
        c.execute("""
            UPDATE nas SET name=?, qc_id=?, dsm_user=?, dsm_password_enc=?,
                           location=?, direct_url=?, enable_alerts=?, updated_at=?
            WHERE id=?
        """, (name, qc_id, user, enc, location, direct_url,
              1 if enable_alerts else 0, datetime.now().isoformat(), nas_id))
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
            c.execute('UPDATE nas SET last_checked=? WHERE id=?',
                      (datetime.now().isoformat(), nas_id))
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
        self.sessions = {}
        self.db       = db_manager or DatabaseManager()

    def _clean_qc_id(self, qc_id: str) -> str:
        qc_id = qc_id.strip()
        for p in ["https://", "http://"]:
            qc_id = qc_id.replace(p, "")
        qc_id = qc_id.replace("QuickConnect.to/", "")
        qc_id = qc_id.replace("quickconnect.to", "")
        return qc_id.strip("/")

    def _build_candidate_urls(self, direct_url: str, qc_id: str, logs: list) -> List[str]:
        """
        Construit la liste des URLs à tester dans l'ordre:
        1. URL directe fournie par l'utilisateur (la plus fiable)
        2. Relay QuickConnect Synology
        """
        urls = []

        # ── 1. URL directe ────────────────────────────────────────────────
        if direct_url and direct_url.strip():
            raw = direct_url.strip().rstrip("/")
            # Ajouter le schéma si absent
            if not raw.startswith("http"):
                urls.append(f"http://{raw}:5000")
                urls.append(f"https://{raw}:5001")
                urls.append(f"http://{raw}")
            else:
                urls.append(raw)
                # Essayer aussi le port DSM standard si pas de port
                if ":" not in raw.split("//")[-1]:
                    base = raw.rstrip("/")
                    urls.append(f"{base}:5000")
                    urls.append(f"{base}:5001")
            logs.append(f"🏠 URL directe : `{direct_url}`")

        # ── 2. Relay QuickConnect ─────────────────────────────────────────
        logs.append(f"🔍 Interrogation du relay Synology pour `{qc_id}`…")
        try:
            relay = "https://global.quickconnect.to/Serv.php"
            payload = {
                "version": 1,
                "command": "get_server_info",
                "stop_when_error": False,
                "stop_when_success": False,
                "id": "qc_direct",
                "serverID": qc_id,
                "is_gofile": False,
            }
            r = requests.post(relay, json=payload, timeout=10, verify=False)
            data = r.json()

            # ── Log de la réponse brute (utile pour déboguer) ─────────────
            logs.append(f"📨 Réponse relay brute : `{json.dumps(data)[:400]}`")

            server = data.get("server", {})
            env    = data.get("env",    {})

            # IP externe
            ext_ip = server.get("external", {}).get("ip", "")
            if ext_ip:
                logs.append(f"📡 IP externe : `{ext_ip}`")
                urls += [f"https://{ext_ip}:5001", f"http://{ext_ip}:5000"]

            # DDNS Synology (.synology.me)
            ddns = server.get("ddns", "")
            if ddns and ddns not in ("NULL", "", "null"):
                logs.append(f"🌐 DDNS : `{ddns}`")
                urls += [f"https://{ddns}:5001", f"http://{ddns}:5000"]

            # FQDN custom
            fqdn = server.get("fqdn", "")
            if fqdn and fqdn not in ("NULL", "", "null"):
                logs.append(f"🌐 FQDN : `{fqdn}`")
                urls += [f"https://{fqdn}:5001", f"http://{fqdn}:5000"]

            # IPs LAN
            for iface in server.get("interface", []):
                ip = iface.get("ip", "")
                if ip:
                    logs.append(f"🏠 IP LAN : `{ip}`")
                    urls += [f"http://{ip}:5000", f"https://{ip}:5001"]

            # Relay tunnel Synology (dernier recours)
            relay_ip = env.get("relay_ip", "")
            relay_port = env.get("relay_port", "")
            if relay_ip and relay_port:
                logs.append(f"🔀 Relay tunnel : `{relay_ip}:{relay_port}`")
                urls.append(f"http://{relay_ip}:{relay_port}")

        except Exception as e:
            logs.append(f"⚠️ Erreur relay : `{e}`")

        # Dédupliquer en gardant l'ordre
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)

        if not unique:
            logs.append("❌ Aucune URL candidate trouvée")
        else:
            logs.append(f"✅ {len(unique)} URL(s) à tester")

        return unique

    def _try_auth(self, base_url: str, username: str,
                  password: str, logs: list) -> Tuple[bool, object, str]:
        """Tente une auth DSM. Retourne (ok, session, sid)."""
        try:
            session = requests.Session()
            session.verify = False
            url = f"{base_url}/webapi/auth.cgi"
            params = {
                "api": "SYNO.API.Auth", "version": "3", "method": "login",
                "account": username, "passwd": password,
                "session": "NASManager", "format": "json",
            }
            logs.append(f"   🔗 `{base_url}`")
            resp = session.get(url, params=params, timeout=8, verify=False)

            # Rejeter HTML
            ct = resp.headers.get("Content-Type", "")
            if "html" in ct or resp.text.strip().startswith("<!"):
                logs.append("      ↳ ❌ HTML reçu (mauvais endpoint)")
                return False, None, None

            data = resp.json()
            if data.get("success"):
                sid = data.get("data", {}).get("sid", "")
                if sid:
                    logs.append("      ↳ ✅ Authentification réussie!")
                    return True, session, sid

            code = data.get("error", {}).get("code", "?")
            msg  = {400: "Identifiants invalides", 401: "Compte désactivé",
                    402: "Permission refusée",    403: "2FA requis",
                    407: "IP bloquée"}.get(code, f"Code DSM {code}")
            logs.append(f"      ↳ ❌ {msg}")
            return False, None, None

        except requests.exceptions.ConnectionError:
            logs.append("      ↳ ❌ Injoignable")
            return False, None, None
        except requests.exceptions.Timeout:
            logs.append("      ↳ ❌ Timeout (8s)")
            return False, None, None
        except Exception as e:
            logs.append(f"      ↳ ❌ `{e}`")
            return False, None, None

    # ── API publique ──────────────────────────────────────────────────────

    def verify_connection_debug(self, qc_id: str, username: str,
                                password: str, direct_url: str = "") -> dict:
        logs  = []
        qc_id = self._clean_qc_id(qc_id)
        logs.append(f"✅ ID nettoyé : `{qc_id}`")

        urls = self._build_candidate_urls(direct_url, qc_id, logs)
        if not urls:
            return {"success": False, "logs": logs, "error": "Aucune URL candidate"}

        logs.append("--- Tentatives de connexion ---")
        for url in urls:
            ok, session, sid = self._try_auth(url, username, password, logs)
            if ok:
                self.sessions[qc_id] = {
                    "session": session, "sid": sid,
                    "username": username, "password": password,
                    "base_url": url,
                }
                logs.append(f"✅ Connexion établie via `{url}`")
                return {"success": True, "logs": logs, "error": None}

        return {"success": False, "logs": logs,
                "error": "Toutes les URLs ont échoué"}

    def verify_connection(self, qc_id: str, username: str,
                          password: str, direct_url: str = "") -> bool:
        return self.verify_connection_debug(qc_id, username, password, direct_url)["success"]

    def _get_session(self, qc_id, username, password, direct_url=""):
        qc_id = self._clean_qc_id(qc_id)
        if qc_id not in self.sessions:
            self.verify_connection(qc_id, username, password, direct_url)
        return self.sessions.get(qc_id)

    def check_server_status(self, qc_id, username, password, direct_url=""):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password, direct_url)
            if not sd:
                return {"is_online": False}
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Info", "version": "2",
                        "method": "getinfo", "_sid": sd["sid"]},
                timeout=10, verify=False)
            data = resp.json()
            if data.get("success"):
                info = data.get("data", {})
                return {"is_online": True,
                        "dsm_version": info.get("dsm_version"),
                        "hostname":    info.get("hostname"),
                        "uptime":      info.get("uptime")}
            return {"is_online": False}
        except Exception as e:
            return {"is_online": False, "error": str(e)}

    def check_updates(self, qc_id, username, password, direct_url=""):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password, direct_url)
            if not sd:
                return None
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Software", "version": "3",
                        "method": "check", "_sid": sd["sid"]},
                timeout=10, verify=False)
            data = resp.json()
            if data.get("success") and data.get("data", {}).get("update_available"):
                return [{"type": "dsm",
                         "version": data["data"].get("latest_version"),
                         "description": "Mise à jour DSM"}]
            return None
        except:
            return None

    def install_updates(self, qc_id, username, password, direct_url="") -> bool:
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password, direct_url)
            if not sd:
                return False
            resp = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.DSM.Software", "version": "3",
                        "method": "install", "_sid": sd["sid"]},
                timeout=10, verify=False)
            return resp.json().get("success", False)
        except:
            return False

    def get_system_alerts(self, qc_id, username, password, direct_url=""):
        try:
            qc_id = self._clean_qc_id(qc_id)
            sd = self._get_session(qc_id, username, password, direct_url)
            if not sd:
                return []
            alerts = []
            r = sd["session"].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={"api": "SYNO.System.Event.Service", "version": "1",
                        "method": "get", "_sid": sd["sid"]},
                timeout=10, verify=False)
            data = r.json()
            if data.get("success"):
                for event in data.get("data", {}).get("events", []):
                    if event.get("severity") in ["critical", "major"]:
                        alerts.append({
                            "type":    "error" if event["severity"] == "critical" else "warning",
                            "message": event.get("description", "Alerte système"),
                        })
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
                timeout=10, verify=False)
            del self.sessions[qc_id]
            return True
        except:
            return False