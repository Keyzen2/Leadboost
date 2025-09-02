import streamlit as st
from supabase import create_client

# --- Inicializar Supabase ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- Funciones ---
def register(email, password, invite_code):
    # comprobar código de invitación
    if invite_code != st.secrets["INVITE_CODE"]:
        return {"error": "Código de invitación inválido"}

    result = supabase.table("users").insert({
        "email": email,
        "password": password,   # 👈 importante, lo tenías sin pasar
        "role": "freemium",
        "quota": 25
    }).execute()

    return result

def login(email, password):
    result = supabase.table("users").select("*").eq("email", email).eq("password", password).execute()
    if result.data:
        return result.data[0]
    return None

# --- UI ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    tabs = st.tabs(["🔑 Iniciar sesión", "📝 Registrarse"])

    with tabs[0]:
        st.subheader("Accede a tu cuenta")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Login"):
            user = login(email, password)
            if user:
                st.session_state.user = user
                st.success(f"Bienvenido {user['email']}")
                st.experimental_rerun()
            else:
                st.error("Credenciales inválidas")

    with tabs[1]:
        st.subheader("Crea tu cuenta con invitación")
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        invite = st.text_input("Código de invitación", key="invite")
        if st.button("Registrarse"):
            result = register(reg_email, reg_pass, invite)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success("Registro exitoso, ahora puedes iniciar sesión.")

else:
    st.success(f"Sesión iniciada como {st.session_state.user['email']}")
    if st.button("Cerrar sesión"):
        st.session_state.user = None
        st.experimental_rerun()

