import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import altair as alt

# --- Config ---
url = st.secrets["SUPABASE_URL"]
anon = st.secrets["SUPABASE_KEY"]
invite_code_secret = st.secrets["INVITE_CODE"]

supabase: Client = create_client(url, anon)

# --- Funciones Auth ---
def signup(email, password, invite_code):
    if invite_code != invite_code_secret:
        return False, "Código de invitación inválido"
    res = supabase.auth.sign_up({"email": email, "password": password})
    if res.user is None:
        return False, "No se pudo crear el usuario"
    return True, "Registro correcto. Revisa tu email si está activada la confirmación."

def login(email, password):
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if res.session is None:
        return None, "Credenciales inválidas"
    return res.session, None

def get_authed_client():
    session = st.session_state.get("session")
    authed = create_client(url, anon)
    if session:
        authed.postgrest.auth(session.access_token)
    return authed

# --- Sesión ---
if "session" not in st.session_state:
    st.session_state.session = None

# --- UI Tabs ---
if st.session_state.session is None:
    tab_login, tab_signup = st.tabs(["🔑 Iniciar sesión", "📝 Registrarse"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar"):
            session, err = login(email, password)
            if err:
                st.error(err)
            else:
                st.session_state.session = session
                st.success("Sesión iniciada")
                st.experimental_rerun()

    with tab_signup:
        r_email = st.text_input("Email", key="reg_email")
        r_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        inv = st.text_input("Código de invitación", key="reg_code")
        if st.button("Crear cuenta"):
            ok, msg = signup(r_email, r_pass, inv)
            st.success(msg) if ok else st.error(msg)

else:
    # --- Usuario autenticado ---
    authed = get_authed_client()
    user_id = st.session_state.session.user.id

    st.sidebar.success(f"Conectado: {st.session_state.session.user.email}")
    if st.sidebar.button("Cerrar sesión"):
        supabase.auth.sign_out()
        st.session_state.session = None
        st.experimental_rerun()

    # --- Perfil y Upgrade ---
    profile = authed.table("profiles").select("*").eq("id", user_id).single().execute().data
    st.subheader(f"Tu plan: {profile['plan']} | Cuota usada: {profile['used_quota']}/{profile['monthly_quota']}")

    if profile["role"]=="freemium":
        if st.button("Actualizar a Premium"):
            authed.rpc("upgrade_to_premium").execute()
            st.success("Ahora eres Premium con 500 búsquedas/mes")
            st.experimental_rerun()

    # --- Tabs internos: Dashboard y CSV Upload ---
    tab_dashboard, tab_csv = st.tabs(["📋 Dashboard / Insert Lead", "📤 Subir CSV"])

    # --- Dashboard / Insert Lead individual ---
    with tab_dashboard:
        st.subheader("Añadir Lead Individual")
        lead_email = st.text_input("Email del lead")
        lead_company = st.text_input("Empresa")
        lead_position = st.text_input("Cargo")
        lead_verified = st.selectbox("Verificado", ["unknown","valid","invalid"])
        lead_source = st.text_area("Fuente (JSON array) ejemplo: ['hunter.io']")

        if st.button("Insertar Lead"):
            try:
                source_json = json.loads(lead_source) if lead_source else []
                lead_id = authed.rpc("consume_quota_and_insert_lead", {
                    "p_email": lead_email,
                    "p_company": lead_company,
                    "p_position": lead_position,
                    "p_verified": lead_verified,
                    "p_source": source_json
                }).execute()
                st.success(f"Lead insertado con ID: {lead_id.data}")
            except Exception as e:
                st.error(f"No se pudo insertar el lead: {e}")

    # --- Subida CSV ---
    with tab_csv:
        st.subheader("Subida de Leads desde CSV")
        uploaded_file = st.file_uploader("Selecciona un CSV", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
            except Exception as e:
                st.error(f"Error leyendo CSV: {e}")
                st.stop()

            expected_cols = ["email", "company", "position"]
            if not all(col in df.columns for col in expected_cols):
                st.error(f"El CSV debe contener estas columnas: {expected_cols}")
                st.stop()

            st.info(f"Archivo cargado: {len(df)} filas")

            if st.button("Insertar todos los leads"):
                inserted = 0
                errors = []
                for idx, row in df.iterrows():
                    try:
                        lead_id = authed.rpc("consume_quota_and_insert_lead", {
                            "p_email": row["email"],
                            "p_company": row["company"],
                            "p_position": row.get("position",""),
                            "p_verified": row.get("verified","unknown"),
                            "p_source": json.dumps(row.get("source",["csv"]))
                        }).execute()
                        inserted += 1
                    except Exception as e:
                        errors.append(f"Fila {idx+1}: {e}")

                st.success(f"Leads insertados correctamente: {inserted}")
                if errors:
                    st.warning("Errores durante la inserción:")
                    for err in errors:
                        st.text(err)

            st.subheader("Preview del CSV")
            st.dataframe(df.head(20))

    # --- Visualización Leads ---
    st.subheader("Tus Leads")
    leads = authed.table("leads").select("*").order("created_at", desc=True).limit(50).execute().data
    if leads:
        df_leads = pd.DataFrame(leads)
        st.dataframe(df_leads)
        top_empresas = df_leads['company'].value_counts().head(10).reset_index()
        chart_empresas = alt.Chart(top_empresas).mark_bar(color="#1f77b4").encode(
            x='index:N', y='company:Q'
        )
        st.altair_chart(chart_empresas, use_container_width=True)
    else:
        st.info("No tienes leads aún.")

