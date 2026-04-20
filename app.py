import streamlit as st
import pandas as pd
from datetime import datetime
from synology_manager import DatabaseManager, SynologyManager

st.set_page_config(page_title="Synology Manager", page_icon="🗄️", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .status-online  { color: #27ae60; font-weight: bold; }
    .status-offline { color: #e74c3c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if "db"  not in st.session_state:
    st.session_state.db  = DatabaseManager()
if "mgr" not in st.session_state:
    st.session_state.mgr = SynologyManager(st.session_state.db)

db  = st.session_state.db
mgr = st.session_state.mgr

with st.sidebar:
    st.title("🗄️ Synology Manager")
    st.markdown("---")
    page = st.radio("Navigation", [
        "📊 Tableau de bord",
        "➕ Ajouter un serveur",
        "✏️ Gérer les serveurs",
        "🚨 Alertes",
        "📋 Historique",
    ])
    st.markdown("---")
    st.caption(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")

nas_list = db.get_all_nas()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1 : Tableau de bord
# ═══════════════════════════════════════════════════════════════════════════
if page == "📊 Tableau de bord":
    st.title("📊 Tableau de bord")
    if not nas_list:
        st.info("Aucun serveur configuré. Allez sur **➕ Ajouter un serveur**.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Serveurs",         len(nas_list))
    col2.metric("Alertes non lues", len(db.get_alerts(unread_only=True)))
    col3.metric("Vérifié",          datetime.now().strftime("%H:%M"))
    st.markdown("---")

    for nas in nas_list:
        pwd        = db.decrypt_password(nas["dsm_password_enc"])
        direct_url = nas.get("direct_url", "")

        with st.expander(f"🖥️  {nas['name']}  —  {nas.get('location','')}", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

            with c1:
                st.write("**Statut**")
                if st.button("🔄 Vérifier", key=f"st_{nas['id']}"):
                    with st.spinner("Connexion…"):
                        status = mgr.check_server_status(
                            nas["qc_id"], nas["dsm_user"], pwd, direct_url)
                        db.update_last_checked(nas["id"])
                        db.add_history(nas["id"], "check_status",
                            "success" if status and status.get("is_online") else "failed")
                    if status and status.get("is_online"):
                        st.markdown("<span class='status-online'>✅ En ligne</span>",
                                    unsafe_allow_html=True)
                        if status.get("dsm_version"):
                            st.caption(f"DSM {status['dsm_version']}")
                    else:
                        st.markdown("<span class='status-offline'>❌ Hors ligne</span>",
                                    unsafe_allow_html=True)
                if nas.get("last_checked"):
                    st.caption(f"Vérifié: {nas['last_checked'][:16]}")

            with c2:
                st.write("**Mises à jour**")
                if st.button("🔍 Vérifier MAJ", key=f"upd_{nas['id']}"):
                    with st.spinner("Vérification…"):
                        updates = mgr.check_updates(
                            nas["qc_id"], nas["dsm_user"], pwd, direct_url)
                    if updates:
                        st.warning(f"⬆️ {len(updates)} mise(s) à jour")
                        if st.button("⬆️ Installer", key=f"inst_{nas['id']}"):
                            mgr.install_updates(nas["qc_id"], nas["dsm_user"], pwd, direct_url)
                            db.add_history(nas["id"], "install_updates", "success")
                            st.success("Lancé!")
                    else:
                        st.success("✅ À jour")

            with c3:
                st.write("**Alertes système**")
                if st.button("🔔 Scanner", key=f"al_{nas['id']}"):
                    with st.spinner("Scan…"):
                        sys_alerts = mgr.get_system_alerts(
                            nas["qc_id"], nas["dsm_user"], pwd, direct_url)
                    if sys_alerts:
                        for a in sys_alerts:
                            db.add_alert(nas["id"], "system", a["message"],
                                         a.get("type", "warning"))
                        st.error(f"🔴 {len(sys_alerts)} alerte(s)!")
                    else:
                        st.success("✅ Aucune alerte")

            with c4:
                st.write("**Infos**")
                st.caption(f"ID: `{nas['qc_id']}`")
                if direct_url:
                    st.caption(f"URL: `{direct_url}`")
                n = len(db.get_alerts(nas_id=nas["id"], unread_only=True))
                if n:
                    st.error(f"🔴 {n} alerte(s)")

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2 : Ajouter un serveur
# ═══════════════════════════════════════════════════════════════════════════
elif page == "➕ Ajouter un serveur":
    st.title("➕ Ajouter un serveur Synology")

    st.info("""
**Comment remplir le formulaire ?**
- **Quick Connect ID** : votre identifiant QuickConnect (ex: `SPS42`)
- **URL directe** *(recommandé)* : l'adresse IP de votre NAS sur votre réseau (ex: `192.168.1.100`) ou son adresse publique. Si renseignée, la connexion sera plus rapide et fiable.
    """)

    with st.form("add_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            name       = st.text_input("Nom du serveur *",       placeholder="SPS")
            qc_id      = st.text_input("Quick Connect ID *",      placeholder="SPS42")
            location   = st.text_input("Localisation",            placeholder="Andrezieux")
        with c2:
            user       = st.text_input("Nom d'utilisateur *",     placeholder="Varanet")
            password   = st.text_input("Mot de passe *",          type="password")
            direct_url = st.text_input("URL directe (optionnel)", placeholder="192.168.1.100 ou https://monnas.fr")
            alerts_on  = st.checkbox("Activer les alertes",       value=True)

        submitted = st.form_submit_button("🔌 Tester la connexion & Ajouter",
                                          use_container_width=True)

    if submitted:
        if not all([name, qc_id, user, password]):
            st.error("⚠️ Remplissez les champs obligatoires (*)")
        else:
            st.markdown("---")
            st.subheader("🔍 Logs de connexion")

            with st.spinner("Connexion en cours…"):
                result = mgr.verify_connection_debug(qc_id, user, password, direct_url)

            for log in result["logs"]:
                if log.startswith("✅"):
                    st.success(log)
                elif log.startswith("❌"):
                    st.error(log)
                elif log.startswith("⚠️"):
                    st.warning(log)
                else:
                    st.info(log)

            st.markdown("---")
            if result["success"]:
                added = db.add_nas(name, qc_id, user, password,
                                   location, direct_url, alerts_on)
                if added:
                    st.success(f"✅ Serveur **{name}** ajouté!")
                    st.balloons()
                else:
                    st.error("❌ Ce Quick Connect ID existe déjà.")
            else:
                st.error(f"❌ Échec : **{result['error']}**")

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3 : Gérer les serveurs
# ═══════════════════════════════════════════════════════════════════════════
elif page == "✏️ Gérer les serveurs":
    st.title("✏️ Gérer les serveurs")
    if not nas_list:
        st.info("Aucun serveur.")
        st.stop()

    rows = [{
        "Nom": n["name"], "QC ID": n["qc_id"],
        "URL directe": n.get("direct_url","") or "—",
        "Localisation": n.get("location",""),
        "Alertes": "✅" if n.get("enable_alerts") else "❌",
        "Ajouté": n["created_at"][:10],
    } for n in nas_list]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.markdown("---")

    st.subheader("✏️ Modifier")
    names    = [n["name"] for n in nas_list]
    selected = st.selectbox("Choisir", names, key="edit_sel")
    nas      = next(n for n in nas_list if n["name"] == selected)
    pwd_dec  = db.decrypt_password(nas["dsm_password_enc"])

    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        with c1:
            nn  = st.text_input("Nom",              value=nas["name"])
            nq  = st.text_input("Quick Connect ID", value=nas["qc_id"])
            nl  = st.text_input("Localisation",     value=nas.get("location",""))
        with c2:
            nu  = st.text_input("Utilisateur",      value=nas["dsm_user"])
            np  = st.text_input("Mot de passe",     value=pwd_dec, type="password")
            nd  = st.text_input("URL directe",      value=nas.get("direct_url",""))
            na  = st.checkbox("Alertes",            value=bool(nas.get("enable_alerts",1)))
        if st.form_submit_button("💾 Enregistrer", use_container_width=True):
            db.update_nas(nas["id"], nn, nq, nu, np, nl, nd, na)
            st.success("✅ Mis à jour!")
            st.rerun()

    st.markdown("---")
    st.subheader("🗑️ Supprimer")
    del_name = st.selectbox("Choisir", names, key="del_sel")
    if st.button("🗑️ Supprimer définitivement", type="primary"):
        db.delete_nas(next(n["id"] for n in nas_list if n["name"] == del_name))
        st.success("✅ Supprimé.")
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 4 : Alertes
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🚨 Alertes":
    st.title("🚨 Alertes")
    c1, c2 = st.columns([3,1])
    with c1:
        fsel = st.selectbox("Filtrer", ["Tous"] + [n["name"] for n in nas_list])
    with c2:
        unread = st.checkbox("Non lues", value=True)

    nid = None
    if fsel != "Tous":
        nid = next(n["id"] for n in nas_list if n["name"] == fsel)

    alerts = db.get_alerts(nas_id=nid, unread_only=unread)
    if not alerts:
        st.success("✅ Aucune alerte.")
    else:
        for a in alerts:
            icon     = "🔴" if a.get("severity") == "error" else "🟡"
            nas_name = next((n["name"] for n in nas_list if n["id"] == a["nas_id"]), "?")
            c1, c2, c3 = st.columns([5,1,1])
            with c1:
                st.write(f"{icon} **[{nas_name}]** {a['message']}")
                st.caption(a["created_at"][:16])
            with c2:
                st.caption("Lue" if a["is_read"] else "**Non lue**")
            with c3:
                if not a["is_read"] and st.button("✓", key=f"r_{a['id']}"):
                    db.mark_alert_read(a["id"])
                    st.rerun()
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 5 : Historique
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📋 Historique":
    st.title("📋 Historique")
    fsel = st.selectbox("Filtrer", ["Tous"] + [n["name"] for n in nas_list])
    nid  = None
    if fsel != "Tous":
        nid = next(n["id"] for n in nas_list if n["name"] == fsel)

    history = db.get_history(nas_id=nid, limit=100)
    if not history:
        st.info("Aucun historique.")
    else:
        rows = [{
            "Serveur": next((n["name"] for n in nas_list if n["id"] == h["nas_id"]), "?"),
            "Action": h["action"], "Statut": h["status"],
            "Détails": h.get("details") or "", "Date": h["created_at"][:16],
        } for h in history]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)