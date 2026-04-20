import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime
import json
from pathlib import Path

class NotificationManager:
    """Gestionnaire des notifications et alertes"""
    
    def __init__(self):
        self.email = None
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = None
        self.sender_password = None
        self.load_notification_config()
    
    def load_notification_config(self):
        """Charge la configuration des notifications"""
        config_file = Path("notification_config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    self.email = config.get('email')
                    self.sender_email = config.get('sender_email')
                    self.sender_password = config.get('sender_password')
            except:
                pass
    
    def save_notification_config(self):
        """Sauvegarde la configuration des notifications"""
        config = {
            'email': self.email,
            'sender_email': self.sender_email,
            'sender_password': self.sender_password
        }
        with open("notification_config.json", 'w') as f:
            json.dump(config, f, indent=2)
    
    def set_email(self, email: str):
        """Définit l'adresse email pour les notifications"""
        self.email = email
    
    def set_smtp_credentials(self, sender_email: str, sender_password: str):
        """Définit les identifiants SMTP pour l'envoi d'emails"""
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.save_notification_config()
    
    def send_alert(self, subject: str, alerts: List[Dict], enabled: bool = True) -> bool:
        """Envoie une notification d'alerte"""
        if not enabled or not self.email:
            return False
        
        try:
            # Créer le message HTML
            html_content = self._create_alert_html(alerts)
            
            # Envoyer via email si configuré
            if self.sender_email and self.sender_password:
                return self._send_email(subject, html_content)
            
            # Sinon, sauvegarder dans un fichier d'alertes
            return self._save_alert_log(subject, alerts)
        
        except Exception as e:
            print(f"Erreur lors de l'envoi d'alerte: {e}")
            return False
    
    def _create_alert_html(self, alerts: List[Dict]) -> str:
        """Crée le contenu HTML de l'alerte"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    border-bottom: 3px solid #e74c3c;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                .header h2 {{
                    color: #e74c3c;
                    margin: 0;
                }}
                .timestamp {{
                    color: #888;
                    font-size: 12px;
                    margin-top: 5px;
                }}
                .alert {{
                    margin: 15px 0;
                    padding: 15px;
                    border-left: 4px solid;
                    border-radius: 4px;
                    background-color: #f9f9f9;
                }}
                .alert-error {{
                    border-left-color: #e74c3c;
                    background-color: #fadbd8;
                }}
                .alert-warning {{
                    border-left-color: #f39c12;
                    background-color: #fde8c8;
                }}
                .alert-info {{
                    border-left-color: #3498db;
                    background-color: #d6eaf8;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px solid #ddd;
                    color: #888;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🚨 Alerte Synology Manager</h2>
                    <div class="timestamp">{timestamp}</div>
                </div>
                
                <div class="content">
        """
        
        for alert in alerts:
            alert_type = alert.get('type', 'info')
            message = alert.get('message', 'Alerte système')
            
            css_class = f'alert alert-{alert_type}'
            html += f'<div class="{css_class}">{message}</div>'
        
        html += """
                </div>
                
                <div class="footer">
                    <p>Cet email a été généré automatiquement par Synology Manager.</p>
                    <p>Veuillez ne pas répondre à cet email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _send_email(self, subject: str, html_content: str) -> bool:
        """Envoie un email via SMTP"""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = f"[Synology Manager] {subject}"
            message["From"] = self.sender_email
            message["To"] = self.email
            
            part = MIMEText(html_content, "html")
            message.attach(part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.email, message.as_string())
            
            return True
        
        except Exception as e:
            print(f"Erreur lors de l'envoi d'email: {e}")
            return False
    
    def _save_alert_log(self, subject: str, alerts: List[Dict]) -> bool:
        """Sauvegarde l'alerte dans un fichier journal"""
        try:
            log_file = Path("alerts.log")
            
            with open(log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().isoformat()
                f.write(f"\n{'='*60}\n")
                f.write(f"[{timestamp}] {subject}\n")
                f.write(f"{'='*60}\n")
                
                for alert in alerts:
                    f.write(f"[{alert.get('type', 'info').upper()}] {alert.get('message', 'Alerte')}\n")
            
            return True
        
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du journal d'alertes: {e}")
            return False
    
    def send_test_notification(self) -> bool:
        """Envoie une notification de test"""
        test_alerts = [
            {
                'type': 'info',
                'message': '✅ Ceci est une notification de test'
            }
        ]
        
        return self.send_alert("Notification de test", test_alerts, enabled=True)
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Récupère l'historique des alertes"""
        try:
            log_file = Path("alerts.log")
            
            if not log_file.exists():
                return []
            
            alerts = []
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Parsage basique du fichier log
            i = 0
            while i < len(lines) and len(alerts) < limit:
                if lines[i].strip().startswith('['):
                    alert_line = lines[i].strip()
                    # Extraire le type et le message
                    try:
                        # Format: [TIMESTAMP] message
                        # ou [TYPE] message
                        parts = alert_line.split('] ', 1)
                        if len(parts) == 2:
                            alert_type = 'info'
                            if parts[0].startswith('['):
                                type_part = parts[0][1:]
                                if type_part in ['ERROR', 'WARNING', 'INFO']:
                                    alert_type = type_part.lower()
                            
                            alerts.append({
                                'type': alert_type,
                                'message': parts[1],
                                'timestamp': datetime.now().isoformat()
                            })
                    except:
                        pass
                
                i += 1
            
            return alerts[:limit]
        
        except Exception as e:
            print(f"Erreur lors de la lecture de l'historique: {e}")
            return []
    
    def clear_alert_history(self) -> bool:
        """Efface l'historique des alertes"""
        try:
            log_file = Path("alerts.log")
            
            if log_file.exists():
                log_file.unlink()
            
            return True
        
        except Exception as e:
            print(f"Erreur lors de l'effacement de l'historique: {e}")
            return False