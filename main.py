# main.py v3.1 - LeadBoost (integrado, seguro y con mejoras UX)
import streamlit as st
import pandas as pd
import json
import re
import io
import altair as alt
from supabase import create_client, Client
from datetime import datetime

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="LeadBoost", layout="wide")
URL = st.secrets["SUPABASE_URL"]
ANON_KEY = st.secrets["SUPABASE_KEY"]
INVITE_CODE = st.secrets["INVITE_CODE"]
supabase: Client = create_client(URL, ANON_KEY)

# -----------------------
# Helpers
# -----------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(e: str):
    return bool(e and EMAIL_RE.match(e.strip()))

def log_action(user_id: str, action: str, details: dict = None):
    """Intenta insertar un log en la tabla audit_logs (si existe). No falla si no existe."""
    try:
        supabase.table("audit_logs").insert({
            "user_id": user_id,
            "action": action,
            "details": json.dumps(details or {}),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass  # silencioso

def get_authed_client():
    session = st.session_state.get("session")
    client = create_client(URL, ANON_KEY)
    if session:
        # attach jwt so RLS works
        client.postgrest.auth(session.access_token)
    return client

# -----------------------
# Auth functions (signup/login/logout)
# -----------------------
def signup(email, password, invite_code):
    email = (email or "").strip().lower()
    if invite_code != INVITE_CODE:
        return False, "Código de invitación inválido"
    if not is_valid_email(email):
        return False, "Email inválido"
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if getattr(res, "user", None):
            # profile created by auth trigger in DB earlier (if you have one)
            log_action(res.user.id, "signup", {"email": email})
            return True, "Registro correcto. Revisa tu email si está activada la confirmación."
        return False, "No se pudo crear el usuario (verifica consola de Supabase)."
    except Exception as e:
        return False, f"Error al registrar: {e}"

def login(email, password):
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return None, "Email inválido"
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        # res.session y res.user usados en tus versiones previas
        if getattr(res, "session", None) and getattr(res, "user", None):
            log_action(res.session.user.id, "login", {"email": email})
            return res.session, None
        return None, "Credenciales inválidas"
    except Exception as e:
        return None, f"Error al iniciar sesión: {e}"

def logout():
    # limpiar sesión local; no dependemos del sign_out remoto para evitar issues de contexto
    st.session_state.session = None
    st.success("Sesión cerrada correctamente")
    st.experimental_rerun()

# -----------------------
# DB helpers (profiles / leads)
# -----------------------
def fetch_profile(authed, user_id):
    try:
        res = authed.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception:
        return None

def fetch_recent_leads(authed, user_id, limit=5):
    try:
        res = authed.table("leads").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []

def insert_lead_rpc(authed, email, company, position, verified, source_list):
    """Llama a la RPC consume_quota_and_insert_lead y devuelve (ok, mensaje)."""
    try:
        payload = {
            "p_email": email,
            "p_company": company,
            "p_position": position,
            "p_verified": verified,
            "p_source": source_list
        }
        res = authed.rpc("consume_quota_and_insert_lead", payload).execute()
        return True, res.data
    except Exception as e:
        # Postgrest devuelve dict parecido a {'message':..., 'code':...}
        return False, str(e)

# -----------------------
# Utility: ejemplo CSV y descarga
# -----------------------
def ejemplo_csv_bytes():
    sample = pd.DataFrame([{
        "company": "TechCorp",
        "contact_name": "Juan Pérez",
        "email": "juan.perez@techcorp.com",
        "phone": "+34123456789",
        "source": "hunter.io",
        "verified": "valid",
        "date_added": datetime.utcnow().date().isoformat()
    }])
    buf = io.StringIO()
    sample.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# -----------------------
# Session init
# -----------------------
if "session" not in st.session_state:
    st.session_state.session = None

# -----------------------
# UI: Login / Signup
# -----------------------
if st.session_state.session is None:
    st.title("🔐 LeadBoost — Iniciar sesión / Registrarse")
    col1, col2 = st.columns(2)

    with col1:
        st.header("🔑 Iniciar sesión")
        login_email = st.text_input("Email", key="login_email")
        login_pass = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar"):
            session, err = login(login_email, login_pass)
            if err:
                st.error(err)
            else:
                if session and getattr(session, "user", None):
                    st.session_state.session = session
                    st.success("Sesión iniciada")
                    st.experimental_rerun()
                else:
                    st.error("No se pudo iniciar sesión correctamente")

    with col2:
        st.header("📝 Registrarse (con código de invitación)")
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        reg_invite = st.text_input("Código de invitación", key="reg_invite")
        if st.button("Crear cuenta"):
            ok, msg = signup(reg_email, reg_pass, reg_invite)
            if ok:
                st.success(msg)
                st.info("Ahora puedes iniciar sesión con tus credenciales.")
            else:
                st.error(msg)

    st.markdown("---")
    st.info("Si tienes problemas con el login, revisa la consola de Supabase o contacta con soporte.")
    st.stop()

# -----------------------
# Usuario autenticado: main app
# -----------------------
authed = get_authed_client()
user_id = st.session_state.session.user.id
profile = fetch_profile(authed, user_id) or {}

# Bienvenida y sidebar
st.sidebar.success(f"Conectado: {st.session_state.session.user.email}")
if st.sidebar.button("Cerrar sesión"):
    # cerrar sesión localmente y recargar
    st.session_state.session = None
    st.success("Sesión cerrada")
    st.experimental_rerun()

# Menu lateral funcional
menu = st.sidebar.radio("Menú", ["Main", "Análisis", "Dashboard", "Upload", "Users"])

# Mensaje de bienvenida con tip según plan
st.write(f"👋 Bienvenido, {st.session_state.session.user.email}!")
plan = profile.get("plan", "Freemium")
used = profile.get("used_quota", 0)
monthly = profile.get("monthly_quota", 25)
st.write(f"Plan: **{plan}** — Cuota usada: **{used}/{monthly}** búsquedas")

if plan.lower().startswith("freemium"):
    st.info("Estás en Freemium. Considera actualizar a Premium para más cuota y funciones.")

# -----------------------
# MAIN
# -----------------------
if menu == "Main":
    st.header("📋 Resumen principal")
    recent = fetch_recent_leads(authed, user_id, limit=5)
    if recent:
        df_recent = pd.DataFrame(recent)
        st.subheader("Últimos leads")
        st.dataframe(df_recent)
        # mini gráfico verificados
        if "verified" in df_recent.columns:
            chart = alt.Chart(df_recent).mark_bar().encode(
                x='verified:N', y='count()', color='verified:N'
            )
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aún no tienes leads. Empieza subiendo un CSV o creando un lead individual.")

    # Upgrade quick button
    if profile.get("role") == "freemium":
        if st.button("🔼 Actualizar a Premium (500 búsquedas/mes)"):
            try:
                authed.rpc("upgrade_to_premium").execute()
                log_action(user_id, "upgrade_to_premium", {"from": "freemium", "to": "premium"})
                st.success("Actualizado a Premium. Recargando...")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"No se pudo actualizar: {e}")

# -----------------------
# ANALISIS
# -----------------------
elif menu == "Análisis":
    st.header("📈 Análisis de Leads")
    leads = authed.table("leads").select("*").eq("user_id", user_id).execute().data or []
    if not leads:
        st.info("No hay leads para analizar.")
    else:
        df = pd.DataFrame(leads)
        st.subheader("Top empresas")
        if "company" in df.columns:
            top_empresas = df['company'].value_counts().head(10).reset_index().rename(columns={"index": "Empresa", "company": "Cantidad"})
            st.altair_chart(alt.Chart(top_empresas).mark_bar(color="#1f77b4").encode(x='Empresa:N', y='Cantidad:Q'), use_container_width=True)
        st.subheader("Estado de verificación")
        if "verified" in df.columns:
            st.altair_chart(alt.Chart(df).mark_bar(color="#2ca02c").encode(x='verified:N', y='count()'), use_container_width=True)
        st.subheader("Evolución mensual")
        if "created_at" in df.columns:
            df['month'] = pd.to_datetime(df['created_at']).dt.to_period('M')
            monthly = df.groupby('month').size().reset_index(name='Cantidad')
            # convert period to string for plotting
            monthly['month'] = monthly['month'].astype(str)
            st.altair_chart(alt.Chart(monthly).mark_line(point=True).encode(x='month:T', y='Cantidad:Q'), use_container_width=True)

# -----------------------
# DASHBOARD - crear lead individual (usa RPC)
# -----------------------
elif menu == "Dashboard":
    st.header("➕ Añadir Lead Individual")
    st.info("Tip: indica el origen del lead y el sistema lo guardará internamente.")
    with st.form("lead_form", clear_on_submit=True):
        lead_email = st.text_input("Email del lead")
        lead_company = st.text_input("Empresa")
        lead_position = st.text_input("Cargo")
        lead_verified = st.selectbox("Verificado", ["unknown", "valid", "invalid"])
        lead_source_text = st.text_input("¿De dónde obtuviste el lead?", value="Manual")
        submitted = st.form_submit_button("Insertar Lead")
    if submitted:
        if not is_valid_email(lead_email):
            st.error("Email inválido")
        else:
            source_list = [lead_source_text.strip()] if lead_source_text else ["Manual"]
            ok, res = insert_lead_rpc(authed, lead_email.strip().lower(), lead_company.strip(), lead_position.strip(), lead_verified, source_list)
            if ok:
                log_action(user_id, "insert_lead", {"email": lead_email, "company": lead_company, "source": source_list})
                st.success(f"Lead insertado (id: {res})")
            else:
                st.error(f"No se pudo insertar el lead: {res}")

# -----------------------
# UPLOAD CSV - con descarga de ejemplo
# -----------------------
elif menu == "Upload":
    st.header("📤 Subida de Leads desde CSV")
    st.info("Tip: el CSV debe contener columnas mínimas: 'company', 'contact_name', 'email'. Opcionales: 'phone', 'source', 'verified'.")
    # botón para descargar CSV de ejemplo
    csv_bytes = ejemplo_csv_bytes()
    st.download_button("⬇️ Descargar CSV de ejemplo", data=csv_bytes, file_name="ejemplo_leads.csv", mime="text/csv")
    uploaded = st.file_uploader("Selecciona un CSV", type=["csv"])
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Error leyendo CSV: {e}")
            st.stop()

        # Normalizar nombres de columnas aceptadas
        df_columns = [c.strip() for c in df.columns]
        df.columns = df_columns

        required = {"company", "contact_name", "email"}
        if not required.issubset(set(df.columns)):
            st.error(f"El CSV debe contener al menos las columnas: {sorted(required)}")
            st.stop()

        st.subheader("Preview (primeras 10 filas)")
        st.dataframe(df.head(10))

        if st.button("📥 Insertar todos los leads"):
            inserted = 0
            errors = []
            for idx, row in df.iterrows():
                e = str(row.get("email", "")).strip().lower()
                if not is_valid_email(e):
                    errors.append(f"Fila {idx+1}: email inválido ({e})")
                    continue
                company = str(row.get("company", "")).strip()
                name = str(row.get("contact_name", "")).strip()
                phone = str(row.get("phone", "")).strip() if "phone" in row else ""
                source = row.get("source", "CSV")
                if isinstance(source, str):
                    source_list = [source.strip()] if source.strip() else ["CSV"]
                elif isinstance(source, list):
                    source_list = source
                else:
                    source_list = ["CSV"]
                verified = row.get("verified", "unknown")
                ok, res = insert_lead_rpc(authed, e, company, name, verified, source_list)
                if ok:
                    inserted += 1
                else:
                    errors.append(f"Fila {idx+1}: {res}")
            log_action(user_id, "bulk_insert", {"inserted": inserted, "errors": len(errors)})
            st.success(f"Leads insertados: {inserted}")
            if errors:
                st.warning("Errores durante la inserción:")
                for err in errors[:20]:
                    st.text(err)

# -----------------------
# USERS - Admin management
# -----------------------
elif menu == "Users":
    st.header("🛠️ Gestión de Usuarios (Admin)")
    # comprobar rol
    if profile.get("role") != "admin":
        st.warning("No tienes permisos para ver esta sección.")
    else:
        # cargar usuarios
        try:
            users = authed.table("profiles").select("*").order("created_at", desc=True).execute().data or []
            if not users:
                st.info("No hay usuarios registrados.")
            else:
                df_users = pd.DataFrame(users)
                st.subheader("Usuarios registrados")
                st.dataframe(df_users)

                st.markdown("---")
                st.markdown("### ✏️ Editar usuario")
                selected_email = st.selectbox("Selecciona usuario", df_users["email"])
                sel = df_users[df_users["email"] == selected_email].iloc[0]

                st.write(f"**Email:** {sel['email']}")
                new_role = st.selectbox("Nuevo rol", ["freemium", "premium", "admin"], index=["freemium","premium","admin"].index(sel.get("role","freemium")))
                new_active = st.checkbox("Activo", value=sel.get("active", True))
                new_quota = st.number_input("Cuota mensual", min_value=0, value=int(sel.get("monthly_quota", 25)), step=25)

                st.markdown("**Confirmar cambios**")
                confirm = st.checkbox("Marcar para confirmar los cambios")
                if st.button("Guardar cambios") and confirm:
                    try:
                        authed.table("profiles").update({
                            "role": new_role,
                            "active": new_active,
                            "monthly_quota": int(new_quota)
                        }).eq("email", selected_email).execute()
                        log_action(user_id, "admin_update_user", {"target": selected_email, "role": new_role, "active": new_active, "quota": new_quota})
                        st.success("Cambios guardados correctamente.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")

                st.markdown("---")
                st.markdown("### ⚠️ Acciones rápidas")
                col1, col2 = st.columns(2)
                with col1:
                    email_quick = st.text_input("Email para rol rápido (ej: cambiar a admin)")
                    role_quick = st.selectbox("Rol rápido", ["freemium","premium","admin"], key="role_quick")
                    if st.button("Aplicar rol rápido"):
                        if email_quick:
                            try:
                                authed.table("profiles").update({"role": role_quick}).eq("email", email_quick).execute()
                                log_action(user_id, "admin_quick_role", {"target": email_quick, "role": role_quick})
                                st.success(f"Rol actualizado a {role_quick} para {email_quick}")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"No se pudo actualizar rol: {e}")
                        else:
                            st.warning("Introduce un email válido.")
                with col2:
                    email_del = st.text_input("Email para desactivar")
                    if st.button("Desactivar usuario"):
                        if email_del:
                            confirm_del = st.checkbox("Confirmar desactivación", key="confirm_del")
                            if confirm_del:
                                try:
                                    authed.table("profiles").update({"active": False}).eq("email", email_del).execute()
                                    log_action(user_id, "admin_deactivate", {"target": email_del})
                                    st.success(f"Usuario {email_del} desactivado.")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"No se pudo desactivar: {e}")
                            else:
                                st.warning("Marca confirmar desactivación antes de proceder.")
