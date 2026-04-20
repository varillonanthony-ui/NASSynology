import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings()

def get_dsm_session(base_url, user, password, timeout=15):
    """Retourne (session, sid) ou lève une exception"""
    session = requests.Session()
    session.verify = False

    r = session.get(
        f"{base_url}/webapi/auth.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "login",
            "account": user,
            "passwd": password,
            "session": "monitoring",
            "format": "sid"
        },
        timeout=timeout
    )
    data = r.json()
    if not data.get("success"):
        raise Exception(f"Login échoué: {data.get('error', {}).get('code')}")

    return session, data["data"]["sid"]

def logout(session, base_url, sid):
    try:
        session.get(
            f"{base_url}/webapi/auth.cgi",
            params={
                "api": "SYNO.API.Auth",
                "version": "1",
                "method": "logout",
                "_sid": sid
            },
            timeout=5
        )
    except:
        pass

def get_nas_status(nas) -> dict:
    """Récupère toutes les infos d'un NAS. Accepte dict ou frozenset."""
    if isinstance(nas, frozenset):
        nas = dict(nas)

    base_url = f"https://global.quickconnect.to/{nas['qc_id']}"

    result = {
        **nas,
        "online": False,
        "dsm_version": None,
        "model": None,
        "hostname": None,
        "updates_available": 0,
        "updates_list": [],
        "error": None,
        "last_check": datetime.now().strftime("%H:%M:%S")
    }

    try:
        session, sid = get_dsm_session(base_url, nas["dsm_user"], nas["dsm_password"])
        result["online"] = True

        # Infos système
        r = session.get(f"{base_url}/webapi/entry.cgi", params={
            "api": "SYNO.Core.System", "version": "1",
            "method": "info", "_sid": sid
        }, timeout=10)
        if r.json().get("success"):
            d = r.json()["data"]
            result["model"]       = d.get("model")
            result["hostname"]    = d.get("hostname")
            result["dsm_version"] = d.get("firmware_ver")

        # MAJ DSM
        r = session.get(f"{base_url}/webapi/entry.cgi", params={
            "api": "SYNO.Core.Upgrade.Server", "version": "1",
            "method": "check", "_sid": sid
        }, timeout=15)
        if r.json().get("success") and r.json()["data"].get("available"):
            result["updates_available"] += 1
            result["updates_list"].append({
                "type": "DSM",
                "name": "DSM",
                "version": r.json()["data"].get("version", "?")
            })

        # MAJ Packages
        r = session.get(f"{base_url}/webapi/entry.cgi", params={
            "api": "SYNO.Core.Package", "version": "2",
            "method": "list",
            "additional": '["update_available"]',
            "_sid": sid
        }, timeout=15)
        if r.json().get("success"):
            for pkg in r.json()["data"].get("packages", []):
                if pkg.get("update_available"):
                    result["updates_available"] += 1
                    result["updates_list"].append({
                        "type": "Package",
                        "name": pkg.get("name", "?"),
                        "version": pkg.get("version", "?")
                    })

        logout(session, base_url, sid)

    except requests.exceptions.ConnectionError:
        result["error"] = "Connexion impossible"
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def push_dsm_update(nas: dict) -> dict:
    """Lance la mise à jour DSM"""
    if isinstance(nas, frozenset):
        nas = dict(nas)
    base_url = f"https://global.quickconnect.to/{nas['qc_id']}"
    try:
        session, sid = get_dsm_session(base_url, nas["dsm_user"], nas["dsm_password"])
        r = session.get(f"{base_url}/webapi/entry.cgi", params={
            "api": "SYNO.Core.Upgrade.Server",
            "version": "1",
            "method": "install",
            "_sid": sid
        }, timeout=30)
        logout(session, base_url, sid)
        if r.json().get("success"):
            return {"success": True, "message": "Mise à jour DSM lancée ✅"}
        return {"success": False, "message": f"Erreur: {r.json()}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def push_package_update(nas: dict, package_id: str) -> dict:
    """Met à jour un package spécifique"""
    if isinstance(nas, frozenset):
        nas = dict(nas)
    base_url = f"https://global.quickconnect.to/{nas['qc_id']}"
    try:
        session, sid = get_dsm_session(base_url, nas["dsm_user"], nas["dsm_password"])
        r = session.get(f"{base_url}/webapi/entry.cgi", params={
            "api": "SYNO.Core.Package",
            "version": "2",
            "method": "install",
            "name": package_id,
            "_sid": sid
        }, timeout=30)
        logout(session, base_url, sid)
        if r.json().get("success"):
            return {"success": True, "message": f"{package_id} mis à jour ✅"}
        return {"success": False, "message": f"Erreur: {r.json()}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
