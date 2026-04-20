import streamlit as st
import pandas as pd
from datetime import datetime
from synology_manager import DatabaseManager, SynologyManager

st.set_page_config(
    page_title="Synology Manager",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .status-online  { color: #27ae60; font-weight: bold; }
    .status-offline { color: #e74c3c; font-weight: bold; }
    div[data-testid="metric-container"] {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── Initialisation (une seule fois par session) ────────────────────────────
if "db" not in st.session_state:
    st.session_state.db = DatabaseManager()
if "mgr" not in st.session_state:
    st.session_state.mgr = SynologyManager(st.session_state.db)

db  = st.session_state.db
mgr = st.session_state.mgr

# ─── Sidebar ───────────────────────────────────────────────────────────────
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

# ─── Récupérer la liste des NAS ────────────────────────────────────────────
nas_list = db.get_all_nas()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1 : Tableau de bord
# ═══════════════════════════════════════════════════════════════════════════
if page == "📊 Tableau de bord":
    st.title("📊 Tableau de bord")

    if not nas_list:
        st.info("Aucun serveur configuré. Allez sur **➕ Ajouter un serveur** pour commencer.")
        st.stop()

    # Métriques globales
    total  = len(nas_list)
    unread = len(db.get_alerts(unread_only=True))
    col1, col2, col3 = st.columns(3)
    col1.metric("Serveurs configurés", total)
    col2.metric("Alertes non lues",    unread)
    col3.metric("Dernière vérification", "Maintenant")

    st.markdown("---")

    for nas in nas_list:
        password = db.decrypt_password(nas["dsm_password_enc"])

        with st.expander(f"🖥️  {nas['name']}  —  {nas.get('location','')}", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

            # ── Statut ──────────────────────────────────────────────────
            with c1:
                st.write("**Statut**")
                if st.button("🔄 Vérifier", key=f"status_{nas['id']}"):
                    with st.spinner("Connexion…"):
                        status = mgr.check_server_status(
                            nas["qc_id"], nas["dsm_user"], password
                        )
                        db.update_last_checked(nas["id"])
                        db.add_history(
                            nas["id"], "check_status",
                            "success" if status and status.get("is_online") else "failed"
                        )
                    if status and status.get("is_online"):
                        st.markdown("<span class='status-online'>✅ En ligne</span>",
                                    unsafe_allow_html=True)
                        if status.get("dsm_version"):
                            st.caption(f"DSM {status['dsm_version']}")
                    else:
                        st.markdown("<span class='status-offline'>❌ Hors ligne</span>",
                                    unsafe_allow_html=True)

                last = nas.get("last_checked")
                if last:
                    st.caption(f"Vérifié: {last[:16]}")

            # ── Mises à jour ────────────────────────────────────────────
            with c2:
                st.write("**Mises à jour**")
                if st.button("🔍 Vérifier MAJ", key=f"upd_{nas['id']}"):
                    with st.spinner("Vérification…"):
                        updates = mgr.check_updates(
                            nas["qc_id"], nas["dsm_user"], password
                        )
                    if updates:
                        st.warning(f"⬆️ {len(updates)} mise(s) à jour")
                        if st.button("⬆️ Installer", key=f"install_{nas['id']}"):
                            mgr.install_updates(nas["qc_id"], nas["dsm_user"], password)
                            db.add_history(nas["id"], "install_updates", "success")
                            st.success("Mise à jour lancée!")
                    else:
                        st.success("✅ À jour")

            # ── Alertes système ─────────────────────────────────────────
            with c3:
                st.write("**Alertes système**")
                if st.button("🔔 Scanner", key=f"alert_{nas['id']}"):
                    with st.spinner("Scan…"):
                        system_alerts = mgr.get_system_alerts(
                            nas["qc_id"], nas["dsm_user"], password
                        )
                    if system_alerts:
                        for a in system_alerts:
                            db.add_alert(nas["id"], "system", a["message"],
                                         a.get("type", "warning"))
                        st.error(f"🔴 {len(system_alerts)} alerte(s) détectée(s)!")
                    else:
                        st.success("✅ Aucune alerte")

            # ── Infos rapides ────────────────────────────────────────────
            with c4:
                st.write("**Infos**")
                st.caption(f"ID: `{nas['qc_id']}`")
                st.caption(f"User: {nas['dsm_user']}")
                alerts_count = len(db.get_alerts(nas_id=nas["id"], unread_only=True))
                if alerts_count:
                    st.error(f"🔴 {alerts_count} alerte(s)")

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2 : Ajouter un serveur
# ═══════════════════════════════════════════════════════════════════════════
elif page == "➕ Ajouter un serveur":
    st.title("➕ Ajouter un serveur Synology")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name      = st.text_input("Nom du serveur *",    placeholder="SPS")
            qc_id     = st.text_input("Quick Connect ID *",   placeholder="SPS42")
            location  = st.text_input("Localisation",         placeholder="Andrezieux")
        with c2:
            user      = st.text_input("Nom d'utilisateur *",  placeholder="Varanet")
            password  = st.text_input("Mot de passe *",       type="password")
            alerts_on = st.checkbox("Activer les alertes",    value=True)

        submitted = st.form_submit_button("➕ Ajouter le serveur", use_container_width=True)

    if submitted:
        if not all([name, qc_id, user, password]):
            st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
        else:
            with st.spinner("Vérification de la connexion…"):
                ok = mgr.verify_connection(qc_id, user, password)

            if ok:
                added = db.add_nas(name, qc_id, user, password, location, alerts_on)
                if added:
                    st.success(f"✅ Serveur **{name}** ajouté avec succès!")
                    st.balloons()
                else:
                    st.error("❌ Ce Quick Connect ID existe déjà.")
            else:
                st.error("❌ Connexion impossible. Vérifiez l'ID QuickConnect et vos identifiants.")

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3 : Gérer les serveurs
# ═══════════════════════════════════════════════════════════════════════════
elif page == "✏️ Gérer les serveurs":
    st.title("✏️ Gérer les serveurs")

    if not nas_list:
        st.info("Aucun serveur configuré.")
        st.stop()

    # Tableau récapitulatif
    rows = [{
        "Nom":         n["name"],
        "QC ID":       n["qc_id"],
        "Utilisateur": n["dsm_user"],
        "Localisation":n.get("location", ""),
        "Alertes":     "✅" if n.get("enable_alerts") else "❌",
        "Ajouté":      n["created_at"][:10],
    } for n in nas_list]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("---")

    # Modifier un serveur
    st.subheader("✏️ Modifier")
    names    = [n["name"] for n in nas_list]
    selected = st.selectbox("Choisir un serveur", names, key="edit_sel")
    nas      = next(n for n in nas_list if n["name"] == selected)
    pwd_dec  = db.decrypt_password(nas["dsm_password_enc"])

    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        with c1:
            new_name   = st.text_input("Nom",              value=nas["name"])
            new_qcid   = st.text_input("Quick Connect ID", value=nas["qc_id"])
            new_loc    = st.text_input("Localisation",     value=nas.get("location", ""))
        with c2:
            new_user   = st.text_input("Utilisateur",      value=nas["dsm_user"])
            new_pwd    = st.text_input("Mot de passe",     value=pwd_dec, type="password")
            new_alerts = st.checkbox("Alertes activées",   value=bool(nas.get("enable_alerts", 1)))

        if st.form_submit_button("💾 Enregistrer", use_container_width=True):
            db.update_nas(nas["id"], new_name, new_qcid, new_user, new_pwd, new_loc, new_alerts)
            st.success("✅ Serveur mis à jour!")
            st.rerun()

    st.markdown("---")

    # Supprimer
    st.subheader("🗑️ Supprimer un serveur")
    del_name = st.selectbox("Choisir", names, key="del_sel")
    if st.button("🗑️ Supprimer définitivement", type="primary"):
        nas_to_del = next(n for n in nas_list if n["name"] == del_name)
        db.delete_nas(nas_to_del["id"])
        st.success(f"✅ Serveur **{del_name}** supprimé.")
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 4 : Alertes
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🚨 Alertes":
    st.title("🚨 Alertes")

    c1, c2 = st.columns([3, 1])
    with c1:
        filter_opts = ["Tous les serveurs"] + [n["name"] for n in nas_list]
        filter_sel  = st.selectbox("Filtrer", filter_opts)
    with c2:
        unread_only = st.checkbox("Non lues uniquement", value=True)

    nas_id_filter = None
    if filter_sel != "Tous les serveurs":
        nas_id_filter = next(n["id"] for n in nas_list if n["name"] == filter_sel)

    alerts = db.get_alerts(nas_id=nas_id_filter, unread_only=unread_only)

    if not alerts:
        st.success("✅ Aucune alerte.")
    else:
        for a in alerts:
            icon     = "🔴" if a.get("severity") == "error" else "🟡"
            nas_name = next((n["name"] for n in nas_list if n["id"] == a["nas_id"]), "?")
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                st.write(f"{icon} **[{nas_name}]** {a['message']}")
                st.caption(a["created_at"][:16])
            with c2:
                st.caption("Lue" if a["is_read"] else "**Non lue**")
            with c3:
                if not a["is_read"]:
                    if st.button("✓ Lu", key=f"read_{a['id']}"):
                        db.mark_alert_read(a["id"])
                        st.rerun()
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 5 : Historique
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📋 Historique":
    st.title("📋 Historique")

    filter_opts = ["Tous les serveurs"] + [n["name"] for n in nas_list]
    filter_sel  = st.selectbox("Filtrer", filter_opts)

    nas_id_filter = None
    if filter_sel != "Tous les serveurs":
        nas_id_filter = next(n["id"] for n in nas_list if n["name"] == filter_sel)

    history = db.get_history(nas_id=nas_id_filter, limit=100)

    if not history:
        st.info("Aucun historique.")
    else:
        rows = []
        for h in history:
            nas_name = next((n["name"] for n in nas_list if n["id"] == h["nas_id"]), "?")
            rows.append({
                "Serveur": nas_name,
                "Action":  h["action"],
                "Statut":  h["status"],
                "Détails": h.get("details") or "",
                "Date":    h["created_at"][:16],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)