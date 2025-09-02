import streamlit as st
import pandas as pd
import json
import altair as alt
from supabase import create_client, Client

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
    if res.session is None or res.user is None:
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

# --- Login / Registro ---
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
                if session and session.user:
                    st.session_state.session = session
                    st.success("Sesión iniciada")
                    st.experimental_rerun()
                else:
                    st.error("No se pudo iniciar sesión correctamente")

    with tab_signup:
        r_email = st.text_input("Email", key="reg_email")
        r_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        inv = st.text_input("Código de invitación", key="reg_code")
        if st.button("Crear cuenta"):
            ok, msg = signup(r_email, r_pass, inv)
            st.success(msg) if ok else st.error(msg)

else:
    authed = get_authed_client()
    user_id = st.session_state.session.user.id
    profile = authed.table("profiles").select("*").eq("id", user_id).single().execute().data

    # --- Sidebar ---
    st.sidebar.success(f"Conectado: {st.session_state.session.user.email}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.session = None
        st.success("Sesión cerrada")
        st.experimental_rerun()

    menu = st.sidebar.radio("Menú", ["Main", "Análisis", "Dashboard", "Upload", "Users"])

    # --- Mensaje bienvenida ---
    st.write(f"👋 Bienvenido {st.session_state.session.user.email}!")
    st.write(f"Tu plan: {profile['plan']} | Cuota usada: {profile['used_quota']}/{profile['monthly_quota']} búsquedas")

    # --- Main ---
    if menu == "Main":
        st.subheader("Resumen Principal")
        leads = authed.table("leads").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute().data
        if leads:
            df = pd.DataFrame(leads)
            st.write("Últimos 5 leads:")
            st.dataframe(df)
            chart = alt.Chart(df).mark_bar().encode(
                x='verified:N', y='count()', color='verified:N'
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No tienes leads aún.")

        if profile['role'] == 'freemium':
            if st.button("Actualizar a Premium"):
                authed.rpc("upgrade_to_premium").execute()
                st.success("Ahora eres Premium con 500 búsquedas/mes")
                st.experimental_rerun()

    # --- Análisis ---
    elif menu == "Análisis":
        st.subheader("Análisis de Leads")
        leads = authed.table("leads").select("*").eq("user_id", user_id).execute().data
        if leads:
            df = pd.DataFrame(leads)
            st.write("📊 Top empresas")
            top_empresas = df['company'].value_counts().head(10).reset_index().rename(columns={"index":"Empresa","company":"Cantidad"})
            st.altair_chart(alt.Chart(top_empresas).mark_bar(color="#1f77b4").encode(
                x='Empresa:N', y='Cantidad:Q'
            ), use_container_width=True)

            st.write("✅ Leads verificados")
            verified_chart = alt.Chart(df).mark_bar(color="#2ca02c").encode(
                x='verified:N', y='count()'
            )
            st.altair_chart(verified_chart, use_container_width=True)

            st.write("📅 Evolución mensual")
            df['month'] = pd.to_datetime(df['created_at']).dt.to_period('M')
            monthly = df.groupby('month').size().reset_index(name='Cantidad')
            monthly_chart = alt.Chart(monthly).mark_line(point=True).encode(
                x='month:T', y='Cantidad:Q'
            )
            st.altair_chart(monthly_chart, use_container_width=True)
        else:
            st.info("No hay leads para analizar.")

    # --- Dashboard ---
    elif menu == "Dashboard":
        st.subheader("Añadir Lead Individual")
        st.info("Tip: Indica de dónde obtuviste el lead, se guardará automáticamente.")
        lead_email = st.text_input("Email del lead")
        lead_company = st.text_input("Empresa")
        lead_position = st.text_input("Cargo")
        lead_verified = st.selectbox("Verificado", ["unknown","valid","invalid"])
        lead_source_text = st.text_input("¿De dónde obtuviste el lead?", value="Manual")
        lead_source = [lead_source_text.strip()] if lead_source_text else ["Manual"]
        if st.button("Insertar Lead"):
            try:
                lead_id = authed.rpc("consume_quota_and_insert_lead", {
                    "p_email": lead_email,
                    "p_company": lead_company,
                    "p_position": lead_position,
                    "p_verified": lead_verified,
                    "p_source": lead_source
                }).execute()
                st.success(f"Lead insertado con ID: {lead_id.data}")
            except Exception as e:
                st.error(f"No se pudo insertar el lead: {e}")

    # --- Upload CSV ---
    elif menu == "Upload":
        st.subheader("Subida de Leads desde CSV")
        st.info("Tip: El CSV debe contener columnas obligatorias: 'email', 'company', 'position'. Opcionales: 'verified', 'source'.")
        uploaded_file = st.file_uploader("Selecciona un CSV", type=["csv"])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            expected_cols = ["email", "company", "position"]
            if not all(col in df.columns for col in expected_cols):
                st.error(f"El CSV debe contener columnas: {expected_cols}")
                st.stop()
            st.dataframe(df.head(10))
            if st.button("Insertar todos los leads"):
                inserted, errors = 0, []
                for idx, row in df.iterrows():
                    try:
                        source = row.get("source", "CSV")
                        if not isinstance(source, list):
                            source = [str(source)]
                        authed.rpc("consume_quota_and_insert_lead", {
                            "p_email": row["email"],
                            "p_company": row["company"],
                            "p_position": row.get("position",""),
                            "p_verified": row.get("verified","unknown"),
                            "p_source": source
                        }).execute()
                        inserted += 1
                    except Exception as e:
                        errors.append(f"Fila {idx+1}: {e}")
                st.success(f"Leads insertados correctamente: {inserted}")
                if errors:
                    st.warning("Errores durante la inserción:")
                    for err in errors:
                        st.text(err)

    # --- Users (solo admin) ---
    elif menu == "Users":
        st.subheader("Gestión de Usuarios (Admin)")
        if profile["role"] == "admin":
            users = authed.table("profiles").select("*").execute().data
            df_users = pd.DataFrame(users)
            st.dataframe(df_users)
            st.info("Aquí puedes modificar campos y actualizar directamente en la base de datos con un botón de ejemplo.")
            # Ejemplo: cambiar rol de un usuario
            selected_email = st.selectbox("Selecciona usuario para cambiar rol", df_users['email'])
            new_role = st.selectbox("Nuevo rol", ["freemium", "premium", "admin"])
            if st.button("Actualizar rol"):
                authed.table("profiles").update({"role": new_role}).eq("email", selected_email).execute()
                st.success(f"Rol actualizado a {new_role} para {selected_email}")
                st.experimental_rerun()
        else:
            st.warning("No tienes permisos para ver esta sección.")

