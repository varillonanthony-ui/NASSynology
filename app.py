import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from database import init_db, get_all_nas, add_nas, delete_nas, update_nas
from nas_api import get_nas_status, push_dsm_update, push_package_update

# ============================================
# INIT
# ============================================
st.set_page_config(
    page_title="Monitoring NAS",
    page_icon="🖥️",
    layout="wide"
)

init_db()

# ============================================
# SIDEBAR — GESTION DES NAS
# ============================================
with st.sidebar:
    st.header("⚙️ Gestion des NAS")

    with st.expander("➕ Ajouter un NAS", expanded=False):
        with st.form("add_nas_form"):
            new_name     = st.text_input("Nom du client *")
            new_qc       = st.text_input("QuickConnect ID *", placeholder="client-nas123")
            new_location = st.text_input("Localisation", placeholder="Paris")
            new_user     = st.text_input("Utilisateur DSM *", value="admin")
            new_password = st.text_input("Mot de passe *", type="password")

            submitted = st.form_submit_button("✅ Ajouter", use_container_width=True)
            if submitted:
                if not all([new_name, new_qc, new_user, new_password]):
                    st.error("Champs obligatoires manquants !")
                else:
                    ok = add_nas(new_name, new_qc, new_user, new_password, new_location)
                    if ok:
                        st.success(f"✅ {new_name} ajouté !")
                        st.rerun()
                    else:
                        st.error("❌ QuickConnect ID déjà existant !")

    st.divider()

    st.subheader("📋 NAS enregistrés")
    all_nas_sidebar = get_all_nas()

    if not all_nas_sidebar:
        st.info("Aucun NAS enregistré")
    else:
        for nas in all_nas_sidebar:
            with st.expander(f"🖥️ {nas['name']}"):
                with st.form(f"edit_{nas['id']}"):
                    e_name     = st.text_input("Nom",           value=nas["name"])
                    e_qc       = st.text_input("QuickConnect ID", value=nas["qc_id"])
                    e_location = st.text_input("Localisation",  value=nas["location"])
                    e_user     = st.text_input("Utilisateur",   value=nas["dsm_user"])
                    e_password = st.text_input("Mot de passe",  type="password",
                                               value=nas["dsm_password"])

                    col1, col2 = st.columns(2)
                    save   = col1.form_submit_button("💾 Modifier",   use_container_width=True)
                    delete = col2.form_submit_button("🗑️ Supprimer", use_container_width=True)

                    if save:
                        update_nas(nas["id"], e_name, e_qc, e_user, e_password, e_location)
                        st.success("Modifié !")
                        st.rerun()

                    if delete:
                        delete_nas(nas["id"])
                        st.warning(f"{nas['name']} supprimé")
                        st.rerun()

# ============================================
# MAIN — DASHBOARD
# ============================================
st.title("🖥️ Monitoring NAS Synology")

col_t, col_r = st.columns([4, 1])
with col_r:
    if st.button("🔄 Actualiser", use_container_width=True):
        st.rerun()

all_nas = get_all_nas()

if not all_nas:
    st.warning("⚠️ Aucun NAS configuré. Ajoutez-en un dans le menu à gauche !")
    st.stop()

# ============================================
# CHARGEMENT STATUTS
# ============================================
with st.spinner("🔍 Vérification des NAS en cours..."):
    with ThreadPoolExecutor(max_workers=10) as ex:
        statuses = list(ex.map(get_nas_status, all_nas))

# ============================================
# MÉTRIQUES GLOBALES
# ============================================
online        = [n for n in statuses if n["online"]]
offline       = [n for n in statuses if not n["online"]]
total_updates = sum(n["updates_available"] for n in statuses)

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Total NAS",       len(statuses))
c2.metric("🟢 En ligne",        len(online))
c3.metric("🔴 Hors ligne",      len(offline))
c4.metric("⚠️ MAJ disponibles", total_updates)

st.divider()

# ============================================
# CARDS NAS
# ============================================
cols = st.columns(3)

for i, nas in enumerate(statuses):
    with cols[i % 3]:
        if nas["online"]:
            st.success(f"🟢 **{nas['name']}**")
        else:
            st.error(f"🔴 **{nas['name']}**")

        if nas.get("location"):
            st.caption(f"📍 {nas['location']}")

        if nas["online"]:
            st.write(f"🖥️ **Modèle :** {nas.get('model') or 'N/A'}")
            st.write(f"💿 **DSM :** {nas.get('dsm_version') or 'N/A'}")
            st.write(f"🌐 **Hostname :** {nas.get('hostname') or 'N/A'}")

            if nas["updates_available"] > 0:
                st.warning(f"⚠️ **{nas['updates_available']} mise(s) à jour disponible(s)**")

                for upd in nas["updates_list"]:
                    col_pkg, col_btn = st.columns([3, 1])
                    icon = "💿" if upd["type"] == "DSM" else "📦"
                    col_pkg.write(f"{icon} {upd['name']} → v{upd['version']}")

                    btn_key = f"upd_{nas['id']}_{upd['name']}"
                    if col_btn.button("⬆️ MAJ", key=btn_key, use_container_width=True):
                        with st.spinner(f"Mise à jour de {upd['name']}..."):
                            if upd["type"] == "DSM":
                                result = push_dsm_update(nas)
                            else:
                                result = push_package_update(nas, upd["name"])
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["message"])

                if nas["updates_available"] > 1:
                    if st.button(
                        f"⬆️ Tout mettre à jour ({nas['updates_available']})",
                        key=f"all_{nas['id']}",
                        use_container_width=True
                    ):
                        with st.spinner("Mise à jour en cours..."):
                            errors = []
                            for upd in nas["updates_list"]:
                                if upd["type"] == "DSM":
                                    r = push_dsm_update(nas)
                                else:
                                    r = push_package_update(nas, upd["name"])
                                if not r["success"]:
                                    errors.append(r["message"])
                        if errors:
                            st.error("\n".join(errors))
                        else:
                            st.success("✅ Toutes les MAJ lancées !")
            else:
                st.success("✅ Système à jour")

        else:
            st.write(f"❌ {nas.get('error') or 'Inaccessible'}")

        st.caption(f"🕐 Vérifié à {nas['last_check']}")
        st.divider()
