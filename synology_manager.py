import sqlite3
import requests
import json
from typing import Optional, Dict, List, Any
import urllib3
from datetime import datetime
import base64

# Désactiver les avertissements SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "nas.db"

# ============================================================================
# CLASSE: DatabaseManager - Gestion de la base de données SQLite
# ============================================================================

class DatabaseManager:
    """Gestionnaire de base de données SQLite pour la persistance"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialise la base de données avec les tables nécessaires"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des serveurs
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
        
        # Table des alertes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                nas_id              INTEGER NOT NULL,
                alert_type          TEXT NOT NULL,
                message             TEXT NOT NULL,
                severity            TEXT DEFAULT 'warning',
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                is_read             INTEGER DEFAULT 0,
                FOREIGN KEY (nas_id) REFERENCES nas(id)
            )
        ''')
        
        # Table de l'historique
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                nas_id              INTEGER NOT NULL,
                action              TEXT NOT NULL,
                status              TEXT,
                details             TEXT,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nas_id) REFERENCES nas(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def encrypt_password(self, password: str) -> str:
        """Chiffre un mot de passe"""
        encoded = base64.b64encode(password.encode()).decode()
        return encoded
    
    def decrypt_password(self, encrypted: str) -> str:
        """Déchiffre un mot de passe"""
        try:
            decoded = base64.b64decode(encrypted.encode()).decode()
            return decoded
        except:
            return encrypted
    
    def get_all_nas(self) -> list[dict]:
        """Récupère tous les serveurs"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM nas ORDER BY name")
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def add_nas(self, name, qc_id, user, password, location='', enable_alerts=True) -> bool:
        """Ajoute un nouveau serveur"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            encrypted_password = self.encrypt_password(password)
            c.execute("""
                INSERT INTO nas (name, qc_id, dsm_user, dsm_password_enc, location, enable_alerts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, qc_id, user, encrypted_password, location, 1 if enable_alerts else 0))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def delete_nas(self, nas_id: int):
        """Supprime un serveur"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM nas WHERE id = ?", (nas_id,))
        c.execute("DELETE FROM alerts WHERE nas_id = ?", (nas_id,))
        c.execute("DELETE FROM history WHERE nas_id = ?", (nas_id,))
        conn.commit()
        conn.close()
    
    def update_nas(self, nas_id, name, qc_id, user, password, location='', enable_alerts=True):
        """Met à jour un serveur"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        encrypted_password = self.encrypt_password(password)
        c.execute("""
            UPDATE nas SET
                name=?, qc_id=?, dsm_user=?, dsm_password_enc=?, location=?, enable_alerts=?, updated_at=?
            WHERE id=?
        """, (name, qc_id, user, encrypted_password, location, 1 if enable_alerts else 0, datetime.now().isoformat(), nas_id))
        conn.commit()
        conn.close()
    
    def add_alert(self, nas_id: int, alert_type: str, message: str, severity: str = 'warning') -> bool:
        """Ajoute une alerte"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO alerts (nas_id, alert_type, message, severity)
                VALUES (?, ?, ?, ?)
            ''', (nas_id, alert_type, message, severity))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur ajout alerte: {e}")
            return False
    
    def get_alerts(self, nas_id: Optional[int] = None, unread_only: bool = False) -> List[Dict]:
        """Récupère les alertes"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            if nas_id:
                if unread_only:
                    c.execute(
                        'SELECT * FROM alerts WHERE nas_id = ? AND is_read = 0 ORDER BY created_at DESC',
                        (nas_id,)
                    )
                else:
                    c.execute(
                        'SELECT * FROM alerts WHERE nas_id = ? ORDER BY created_at DESC',
                        (nas_id,)
                    )
            else:
                if unread_only:
                    c.execute('SELECT * FROM alerts WHERE is_read = 0 ORDER BY created_at DESC')
                else:
                    c.execute('SELECT * FROM alerts ORDER BY created_at DESC')
            
            rows = c.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Erreur récupération alertes: {e}")
            return []
    
    def mark_alert_read(self, alert_id: int) -> bool:
        """Marque une alerte comme lue"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('UPDATE alerts SET is_read = 1 WHERE id = ?', (alert_id,))
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def add_history(self, nas_id: int, action: str, status: str = 'pending', details: str = None) -> bool:
        """Ajoute une entrée à l'historique"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO history (nas_id, action, status, details)
                VALUES (?, ?, ?, ?)
            ''', (nas_id, action, status, details))
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def get_history(self, nas_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """Récupère l'historique"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            if nas_id:
                c.execute(
                    'SELECT * FROM history WHERE nas_id = ? ORDER BY created_at DESC LIMIT ?',
                    (nas_id, limit)
                )
            else:
                c.execute(
                    'SELECT * FROM history ORDER BY created_at DESC LIMIT ?',
                    (limit,)
                )
            
            rows = c.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except:
            return []
    
    def update_last_checked(self, nas_id: int) -> bool:
        """Met à jour la date de dernière vérification"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                'UPDATE nas SET last_checked = ? WHERE id = ?',
                (datetime.now().isoformat(), nas_id)
            )
            conn.commit()
            conn.close()
            return True
        except:
            return False


# ============================================================================
# CLASSE: SynologyManager - Gestion de l'API Synology
# ============================================================================

class SynologyManager:
    """Gestionnaire pour interagir avec les serveurs Synology via l'API"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.sessions = {}
        self.db = db_manager or DatabaseManager()
    
    def get_quickconnect_url(self, qc_id: str) -> str:
        """Obtient l'URL du serveur via Quick Connect"""
        # Support pour les IDs courts (SPS42) et longs (abc123def456)
        if len(qc_id) <= 6:
            return f"http://QuickConnect.to/{qc_id}"
        else:
            return f"https://{qc_id}.quickconnect.to"
    
    def verify_connection(self, qc_id: str, username: str, password: str) -> bool:
        """Vérifie la connexion à un serveur Synology"""
        try:
            base_url = self.get_quickconnect_url(qc_id)
            session = requests.Session()
            session.verify = False
            
            # Authentification
            auth_url = f"{base_url}/webapi/auth.cgi"
            params = {
                'api': 'SYNO.API.Auth',
                'version': '3',
                'method': 'login',
                'account': username,
                'passwd': password,
                'session': 'SynologyManager',
                'format': 'json'
            }
            
            response = session.get(auth_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('success'):
                sid_value = data.get('data', {}).get('sid')
                if sid_value:
                    self.sessions[qc_id] = {
                        'session': session,
                        'sid': sid_value,
                        'username': username,
                        'password': password,
                        'base_url': base_url
                    }
                    return True
            
            return False
        except Exception as e:
            print(f"Erreur de connexion: {e}")
            return False
    
    def check_server_status(self, qc_id: str, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Récupère le statut du serveur"""
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return {'is_online': False, 'error': 'Connexion échouée'}
            
            session_data = self.sessions.get(qc_id)
            if not session_data:
                return {'is_online': False}
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            # Récupérer les informations système
            info_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.DSM.Info',
                'version': '2',
                'method': 'getinfo',
                '_sid': session_id
            }
            
            response = session.get(info_url, params=params, timeout=10, verify=False)
            data = response.json()
            
            if data.get('success'):
                sys_info = data.get('data', {})
                return {
                    'is_online': True,
                    'dsm_version': sys_info.get('dsm_version'),
                    'hostname': sys_info.get('hostname'),
                    'system_status': sys_info.get('sys_status'),
                    'uptime': sys_info.get('uptime')
                }
            
            return {'is_online': False}
        
        except Exception as e:
            print(f"Erreur lors de la vérification du statut: {e}")
            return {'is_online': False, 'error': str(e)}
    
    def check_updates(self, qc_id: str, username: str, password: str) -> Optional[List[Dict]]:
        """Vérifie les mises à jour disponibles"""
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return None
            
            session_data = self.sessions.get(qc_id)
            if not session_data:
                return None
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            update_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.DSM.Software',
                'version': '3',
                'method': 'check',
                '_sid': session_id
            }
            
            response = session.get(update_url, params=params, timeout=10, verify=False)
            data = response.json()
            
            if data.get('success'):
                update_info = data.get('data', {})
                updates = []
                
                if update_info.get('update_available'):
                    updates.append({
                        'type': 'dsm',
                        'version': update_info.get('latest_version'),
                        'description': 'Mise à jour DSM',
                        'size': update_info.get('update_size')
                    })
                
                return updates if updates else None
            
            return None
        
        except Exception as e:
            print(f"Erreur lors de la vérification des mises à jour: {e}")
            return None
    
    def install_updates(self, qc_id: str, username: str, password: str) -> bool:
        """Lance l'installation des mises à jour"""
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return False
            
            session_data = self.sessions.get(qc_id)
            if not session_data:
                return False
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            install_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.DSM.Software',
                'version': '3',
                'method': 'install',
                '_sid': session_id
            }
            
            response = session.get(install_url, params=params, timeout=10, verify=False)
            data = response.json()
            
            return data.get('success', False)
        
        except Exception as e:
            print(f"Erreur lors de l'installation des mises à jour: {e}")
            return False
    
    def get_system_alerts(self, qc_id: str, username: str, password: str) -> List[Dict[str, Any]]:
        """Récupère les alertes système"""
        try:
            if qc_id not in self.sessions:
                if not self.verify_connection(qc_id, username, password):
                    return []
            
            session_data = self.sessions.get(qc_id)
            if not session_data:
                return []
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            alerts = []
            
            # Vérifier la santé du système
            try:
                health_url = f"{base_url}/webapi/query.cgi"
                params = {
                    'api': 'SYNO.System.Event.Service',
                    'version': '1',
                    'method': 'get',
                    '_sid': session_id
                }
                response = session.get(health_url, params=params, timeout=10, verify=False)
                data = response.json()
                
                if data.get('success'):
                    events = data.get('data', {}).get('events', [])
                    for event in events:
                        if event.get('severity') in ['critical', 'major']:
                            alerts.append({
                                'type': 'error' if event.get('severity') == 'critical' else 'warning',
                                'message': event.get('description', 'Alerte système'),
                                'timestamp': datetime.now().isoformat()
                            })
            except:
                pass
            
            return alerts
        
        except Exception as e:
            print(f"Erreur lors de la récupération des alertes: {e}")
            return []
    
    def logout(self, qc_id: str) -> bool:
        """Déconnecte une session"""
        try:
            if qc_id not in self.sessions:
                return True
            
            session_data = self.sessions.get(qc_id)
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            logout_url = f"{base_url}/webapi/auth.cgi"
            params = {
                'api': 'SYNO.API.Auth',
                'version': '1',
                'method': 'logout',
                '_sid': session_id
            }
            
            session.get(logout_url, params=params, timeout=10, verify=False)
            del self.sessions[qc_id]
            return True
        
        except Exception as e:
            print(f"Erreur lors de la déconnexion: {e}")
            return False


# ============================================================================
# Initialisation de la base de données au lancement
# ============================================================================

if __name__ == "__main__":
    db = DatabaseManager()
    print("✅ Base de données initialisée")