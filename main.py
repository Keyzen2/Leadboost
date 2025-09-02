import streamlit as st
from supabase import create_client, Client
import pandas as pd
import altair as alt
import json

# --- Config ---
url = st.secrets["SUPABASE_URL"]
anon = st.secrets["SUPABASE_KEY"]  # ANON KEY
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

# --- Dashboard ---
if st.session_state.session:
    authed = get_authed_client()
    user_id = st.session_state.session.user.id

    st.sidebar.success(f"Conectado: {st.session_state.session.user.email}")
    if st.sidebar.button("Cerrar sesión"):
        supabase.auth.sign_out()
        st.session_state.session = None
        st.experimental_rerun()

    # --- Perfil ---
    profile = authed.table("profiles").select("*").eq("id", user_id).single().execute().data
    st.subheader(f"Tu plan: {profile['plan']} | Cuota usada: {profile['used_quota']}/{profile['monthly_quota']}")

    # --- Upgrade Plan ---
    if profile["role"]=="freemium":
        if st.button("Actualizar a Premium"):
            authed.rpc("upgrade_to_premium").execute()
            st.success("Ahora eres Premium con 500 búsquedas/mes")
            st.experimental_rerun()

    # --- Insert Lead Seguro ---
    st.subheader("Añadir Lead")
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

    # --- Ver Leads ---
    st.subheader("Tus Leads")
    leads = authed.table("leads").select("*").order("created_at", desc=True).limit(50).execute().data
    if leads:
        df = pd.DataFrame(leads)
        st.dataframe(df)
        # Grafico top empresas
        top_empresas = df['company'].value_counts().head(10).reset_index()
        chart_empresas = alt.Chart(top_empresas).mark_bar(color="#1f77b4").encode(
            x='index:N', y='company:Q'
        )
        st.altair_chart(chart_empresas, use_container_width=True)
    else:
        st.info("No tienes leads aún.")


