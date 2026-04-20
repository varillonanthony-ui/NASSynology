import sqlite3
import requests
import json
from typing import Optional, Dict, List, Any
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
        self.sessions = {}
        self.db = db_manager or DatabaseManager()

    def get_quickconnect_url(self, qc_id: str) -> str:
        """Support IDs courts (SPS42) et longs (abc123def456)"""
        if len(qc_id) <= 6:
            return f"http://QuickConnect.to/{qc_id}"
        else:
            return f"https://{qc_id}.quickconnect.to"

    def verify_connection_debug(self, qc_id: str, username: str, password: str) -> dict:
        """
        Connexion avec logs détaillés pour déboguer.
        Retourne un dict avec: success (bool), logs (list), error (str)
        """
        logs = []
        try:
            # Étape 1 : URL
            base_url = self.get_quickconnect_url(qc_id)
            logs.append(f"✅ URL construite : `{base_url}`")

            # Étape 2 : Session
            session = requests.Session()
            session.verify = False
            logs.append("✅ Session HTTP créée")

            # Étape 3 : Résolution QuickConnect
            auth_url = f"{base_url}/webapi/auth.cgi"
            logs.append(f"🔗 Tentative de connexion à : `{auth_url}`")

            params = {
                'api':     'SYNO.API.Auth',
                'version': '3',
                'method':  'login',
                'account': username,
                'passwd':  password,
                'session': 'SynologyManager',
                'format':  'json'
            }

            # Étape 4 : Requête HTTP
            try:
                response = session.get(auth_url, params=params, timeout=15)
                logs.append(f"✅ Réponse reçue — HTTP {response.status_code}")
            except requests.exceptions.ConnectionError as e:
                logs.append(f"❌ Erreur de connexion réseau : `{e}`")
                return {"success": False, "logs": logs, "error": "ConnectionError"}
            except requests.exceptions.Timeout:
                logs.append("❌ Timeout — le serveur ne répond pas (>15s)")
                return {"success": False, "logs": logs, "error": "Timeout"}

            # Étape 5 : Parse JSON
            try:
                data = response.json()
                logs.append(f"✅ JSON reçu : `{json.dumps(data)[:200]}`")
            except Exception as e:
                logs.append(f"❌ La réponse n'est pas du JSON valide")
                logs.append(f"   Contenu brut : `{response.text[:300]}`")
                return {"success": False, "logs": logs, "error": "InvalidJSON"}

            # Étape 6 : Vérification succès
            if data.get('success'):
                sid_value = data.get('data', {}).get('sid')
                if sid_value:
                    self.sessions[qc_id] = {
                        'session':  session,
                        'sid':      sid_value,
                        'username': username,
                        'password': password,
                        'base_url': base_url
                    }
                    logs.append("✅ Authentification réussie!")
                    return {"success": True, "logs": logs, "error": None}
                else:
                    logs.append("❌ Pas de SID retourné malgré succès=True")
                    return {"success": False, "logs": logs, "error": "NoSID"}
            else:
                error_code = data.get('error', {}).get('code', '?')
                error_msg  = {
                    400: "Données d'authentification invalides",
                    401: "Compte désactivé",
                    402: "Permission refusée",
                    403: "Code 2FA requis",
                    404: "Code 2FA expiré ou invalide",
                    406: "Authentification à deux facteurs non configurée",
                    407: "IP bloquée",
                }.get(error_code, f"Code d'erreur inconnu : {error_code}")
                logs.append(f"❌ Authentification refusée — {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}

        except Exception as e:
            logs.append(f"❌ Erreur inattendue : `{type(e).__name__}: {e}`")
            return {"success": False, "logs": logs, "error": str(e)}

    def verify_connection(self, qc_id: str, username: str, password: str) -> bool:
        result = self.verify_connection_debug(qc_id, username, password)
        return result["success"]

    def check_server_status(self, qc_id, username, password):
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return {'is_online': False, 'error': 'Connexion échouée'}
            session_data = self.sessions.get(qc_id)
            if not session_data:
                return {'is_online': False}
            session    = session_data['session']
            base_url   = session_data['base_url']
            session_id = session_data['sid']
            response = session.get(
                f"{base_url}/webapi/query.cgi",
                params={'api': 'SYNO.DSM.Info', 'version': '2',
                        'method': 'getinfo', '_sid': session_id},
                timeout=10, verify=False
            )
            data = response.json()
            if data.get('success'):
                info = data.get('data', {})
                return {
                    'is_online':     True,
                    'dsm_version':   info.get('dsm_version'),
                    'hostname':      info.get('hostname'),
                    'system_status': info.get('sys_status'),
                    'uptime':        info.get('uptime')
                }
            return {'is_online': False}
        except Exception as e:
            return {'is_online': False, 'error': str(e)}

    def check_updates(self, qc_id, username, password):
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return None
            sd = self.sessions.get(qc_id)
            if not sd:
                return None
            response = sd['session'].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={'api': 'SYNO.DSM.Software', 'version': '3',
                        'method': 'check', '_sid': sd['sid']},
                timeout=10, verify=False
            )
            data = response.json()
            if data.get('success') and data.get('data', {}).get('update_available'):
                return [{'type': 'dsm',
                         'version': data['data'].get('latest_version'),
                         'description': 'Mise à jour DSM'}]
            return None
        except:
            return None

    def install_updates(self, qc_id, username, password) -> bool:
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return False
            sd = self.sessions.get(qc_id)
            response = sd['session'].get(
                f"{sd['base_url']}/webapi/query.cgi",
                params={'api': 'SYNO.DSM.Software', 'version': '3',
                        'method': 'install', '_sid': sd['sid']},
                timeout=10, verify=False
            )
            return response.json().get('success', False)
        except:
            return False

    def get_system_alerts(self, qc_id, username, password):
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return []
            sd = self.sessions.get(qc_id)
            if not sd:
                return []
            alerts = []
            try:
                r = sd['session'].get(
                    f"{sd['base_url']}/webapi/query.cgi",
                    params={'api': 'SYNO.System.Event.Service', 'version': '1',
                            'method': 'get', '_sid': sd['sid']},
                    timeout=10, verify=False
                )
                data = r.json()
                if data.get('success'):
                    for event in data.get('data', {}).get('events', []):
                        if event.get('severity') in ['critical', 'major']:
                            alerts.append({
                                'type':    'error' if event['severity'] == 'critical' else 'warning',
                                'message': event.get('description', 'Alerte système'),
                            })
            except:
                pass
            return alerts
        except:
            return []

    def logout(self, qc_id: str) -> bool:
        try:
            if qc_id not in self.sessions:
                return True
            sd = self.sessions[qc_id]
            sd['session'].get(
                f"{sd['base_url']}/webapi/auth.cgi",
                params={'api': 'SYNO.API.Auth', 'version': '1',
                        'method': 'logout', '_sid': sd['sid']},
                timeout=10, verify=False
            )
            del self.sessions[qc_id]
            return True
        except:
            return False