import requests
import json
from typing import Optional, Dict, List, Any
import urllib3
from datetime import datetime
import sqlite3
from pathlib import Path
import hashlib
import base64

# Désactiver les avertissements SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DatabaseManager:
    """Gestionnaire de base de données SQLite pour la persistance"""
    
    def __init__(self, db_path: str = "synology_manager.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialise la base de données avec les tables nécessaires"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des serveurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sid TEXT NOT NULL,
                username TEXT NOT NULL,
                password_encrypted TEXT NOT NULL,
                enable_alerts INTEGER DEFAULT 1,
                check_interval INTEGER DEFAULT 6,
                added_date TEXT NOT NULL,
                last_checked TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des alertes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'warning',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
        ''')
        
        # Table de l'historique
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def encrypt_password(self, password: str) -> str:
        """Chiffre un mot de passe (chiffrement simple, améliorer pour production)"""
        # Pour la production, utiliser cryptography.fernet
        encoded = base64.b64encode(password.encode()).decode()
        return encoded
    
    def decrypt_password(self, encrypted: str) -> str:
        """Déchiffre un mot de passe"""
        try:
            decoded = base64.b64decode(encrypted.encode()).decode()
            return decoded
        except:
            return encrypted
    
    def add_server(self, server_id: str, server_data: Dict) -> bool:
        """Ajoute un serveur à la base de données"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            encrypted_password = self.encrypt_password(server_data['password'])
            
            cursor.execute('''
                INSERT OR REPLACE INTO servers 
                (id, name, sid, username, password_encrypted, enable_alerts, check_interval, added_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                server_id,
                server_data['name'],
                server_data['sid'],
                server_data['username'],
                encrypted_password,
                1 if server_data.get('enable_alerts', True) else 0,
                server_data.get('check_interval', 6),
                server_data.get('added_date', datetime.now().isoformat())
            ))
            
            # Ajouter à l'historique
            cursor.execute('''
                INSERT INTO history (server_id, action, status)
                VALUES (?, ?, ?)
            ''', (server_id, 'added', 'success'))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de l'ajout du serveur: {e}")
            return False
    
    def get_servers(self) -> Dict[str, Dict]:
        """Récupère tous les serveurs"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM servers')
            rows = cursor.fetchall()
            
            servers = {}
            for row in rows:
                server_id = row[0]
                servers[server_id] = {
                    'name': row[1],
                    'sid': row[2],
                    'username': row[3],
                    'password': self.decrypt_password(row[4]),
                    'enable_alerts': bool(row[5]),
                    'check_interval': row[6],
                    'added_date': row[7],
                    'last_checked': row[8]
                }
            
            conn.close()
            return servers
        except Exception as e:
            print(f"Erreur lors de la récupération des serveurs: {e}")
            return {}
    
    def delete_server(self, server_id: str) -> bool:
        """Supprime un serveur"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM servers WHERE id = ?', (server_id,))
            cursor.execute('DELETE FROM alerts WHERE server_id = ?', (server_id,))
            cursor.execute('DELETE FROM history WHERE server_id = ?', (server_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du serveur: {e}")
            return False
    
    def add_alert(self, server_id: str, alert_type: str, message: str, severity: str = 'warning') -> bool:
        """Ajoute une alerte à la base de données"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO alerts (server_id, alert_type, message, severity)
                VALUES (?, ?, ?, ?)
            ''', (server_id, alert_type, message, severity))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de l'ajout de l'alerte: {e}")
            return False
    
    def get_alerts(self, server_id: Optional[str] = None, unread_only: bool = False) -> List[Dict]:
        """Récupère les alertes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if server_id:
                if unread_only:
                    cursor.execute(
                        'SELECT * FROM alerts WHERE server_id = ? AND is_read = 0 ORDER BY created_at DESC',
                        (server_id,)
                    )
                else:
                    cursor.execute(
                        'SELECT * FROM alerts WHERE server_id = ? ORDER BY created_at DESC',
                        (server_id,)
                    )
            else:
                if unread_only:
                    cursor.execute('SELECT * FROM alerts WHERE is_read = 0 ORDER BY created_at DESC')
                else:
                    cursor.execute('SELECT * FROM alerts ORDER BY created_at DESC')
            
            rows = cursor.fetchall()
            alerts = []
            
            for row in rows:
                alerts.append({
                    'id': row[0],
                    'server_id': row[1],
                    'type': row[2],
                    'message': row[3],
                    'severity': row[4],
                    'created_at': row[5],
                    'is_read': bool(row[6])
                })
            
            conn.close()
            return alerts
        except Exception as e:
            print(f"Erreur lors de la récupération des alertes: {e}")
            return []
    
    def mark_alert_read(self, alert_id: int) -> bool:
        """Marque une alerte comme lue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('UPDATE alerts SET is_read = 1 WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de la mise à jour de l'alerte: {e}")
            return False
    
    def get_history(self, server_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Récupère l'historique des actions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if server_id:
                cursor.execute(
                    'SELECT * FROM history WHERE server_id = ? ORDER BY created_at DESC LIMIT ?',
                    (server_id, limit)
                )
            else:
                cursor.execute(
                    'SELECT * FROM history ORDER BY created_at DESC LIMIT ?',
                    (limit,)
                )
            
            rows = cursor.fetchall()
            history = []
            
            for row in rows:
                history.append({
                    'id': row[0],
                    'server_id': row[1],
                    'action': row[2],
                    'status': row[3],
                    'details': row[4],
                    'created_at': row[5]
                })
            
            conn.close()
            return history
        except Exception as e:
            print(f"Erreur lors de la récupération de l'historique: {e}")
            return []
    
    def add_history(self, server_id: str, action: str, status: str = 'pending', details: str = None) -> bool:
        """Ajoute une entrée à l'historique"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO history (server_id, action, status, details)
                VALUES (?, ?, ?, ?)
            ''', (server_id, action, status, details))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de l'ajout à l'historique: {e}")
            return False
    
    def update_last_checked(self, server_id: str) -> bool:
        """Met à jour la date de dernière vérification"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE servers SET last_checked = ? WHERE id = ?',
                (datetime.now().isoformat(), server_id)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de la mise à jour de last_checked: {e}")
            return False

class SynologyManager:
    """Gestionnaire pour interagir avec les serveurs Synology via l'API"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.sessions = {}  # Stockage des sessions par server_id
        self.db = db_manager or DatabaseManager()
        
    def get_quickconnect_url(self, sid: str) -> str:
        """Obtient l'URL du serveur via Quick Connect"""
        return f"https://{sid}.quickconnect.to"
    
    def verify_connection(self, sid: str, username: str, password: str) -> bool:
        """Vérifie la connexion à un serveur Synology"""
        try:
            base_url = self.get_quickconnect_url(sid)
            
            # Tentative de connexion
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
                    self.sessions[sid] = {
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
    
    def check_server_status(self, sid: str, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Récupère le statut du serveur"""
        try:
            if sid not in self.sessions:
                if not self.verify_connection(sid, username, password):
                    return {'is_online': False, 'error': 'Connexion échouée'}
            
            session_data = self.sessions.get(sid)
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
    
    def check_updates(self, sid: str, username: str, password: str) -> Optional[List[Dict]]:
        """Vérifie les mises à jour disponibles"""
        try:
            if sid not in self.sessions:
                if not self.verify_connection(sid, username, password):
                    return None
            
            session_data = self.sessions.get(sid)
            if not session_data:
                return None
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            # Vérifier les mises à jour disponibles
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
    
    def install_updates(self, sid: str, username: str, password: str) -> bool:
        """Lance l'installation des mises à jour"""
        try:
            if sid not in self.sessions:
                if not self.verify_connection(sid, username, password):
                    return False
            
            session_data = self.sessions.get(sid)
            if not session_data:
                return False
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            # Lancer l'installation des mises à jour
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
    
    def get_system_alerts(self, sid: str, username: str, password: str) -> List[Dict[str, Any]]:
        """Récupère les alertes système (disque, ventilateur, etc.)"""
        try:
            if sid not in self.sessions:
                if not self.verify_connection(sid, username, password):
                    return []
            
            session_data = self.sessions.get(sid)
            if not session_data:
                return []
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            alerts = []
            
            # Vérifier la santé du système
            health_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.System.Event.Service',
                'version': '1',
                'method': 'get',
                '_sid': session_id
            }
            
            try:
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
            
            # Vérifier l'état des disques
            disk_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.Storage.CGI.HddMan',
                'version': '1',
                'method': 'get',
                '_sid': session_id
            }
            
            try:
                response = session.get(disk_url, params=params, timeout=10, verify=False)
                data = response.json()
                
                if data.get('success'):
                    disks = data.get('data', {}).get('disks', [])
                    for disk in disks:
                        if disk.get('status') != 'normal':
                            alerts.append({
                                'type': 'error',
                                'message': f"⚠️ Disque {disk.get('name', 'inconnu')}: {disk.get('status', 'Erreur')}",
                                'timestamp': datetime.now().isoformat()
                            })
            except:
                pass
            
            # Vérifier les ventilateurs
            fan_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.System.HardwareInfo',
                'version': '1',
                'method': 'getFan',
                '_sid': session_id
            }
            
            try:
                response = session.get(fan_url, params=params, timeout=10, verify=False)
                data = response.json()
                
                if data.get('success'):
                    fans = data.get('data', {}).get('fans', [])
                    for fan in fans:
                        if not fan.get('status', True):
                            alerts.append({
                                'type': 'error',
                                'message': f"🔴 Ventilateur {fan.get('name', 'inconnu')} HS",
                                'timestamp': datetime.now().isoformat()
                            })
            except:
                pass
            
            return alerts
        
        except Exception as e:
            print(f"Erreur lors de la récupération des alertes: {e}")
            return []
    
    def get_disk_info(self, sid: str, username: str, password: str) -> Optional[List[Dict]]:
        """Récupère les informations sur les disques"""
        try:
            if sid not in self.sessions:
                if not self.verify_connection(sid, username, password):
                    return None
            
            session_data = self.sessions.get(sid)
            if not session_data:
                return None
            
            session = session_data['session']
            base_url = session_data['base_url']
            session_id = session_data['sid']
            
            disk_url = f"{base_url}/webapi/query.cgi"
            params = {
                'api': 'SYNO.Storage.CGI.HddMan',
                'version': '1',
                'method': 'get',
                '_sid': session_id
            }
            
            response = session.get(disk_url, params=params, timeout=10, verify=False)
            data = response.json()
            
            if data.get('success'):
                return data.get('data', {}).get('disks', [])
            
            return None
        
        except Exception as e:
            print(f"Erreur lors de la récupération des informations disque: {e}")
            return None
    
    def logout(self, sid: str) -> bool:
        """Déconnecte une session"""
        try:
            if sid not in self.sessions:
                return True
            
            session_data = self.sessions.get(sid)
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
            del self.sessions[sid]
            return True
        
        except Exception as e:
            print(f"Erreur lors de la déconnexion: {e}")
            return False