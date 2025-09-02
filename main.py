import streamlit as st
from utils import get_user, update_quota

st.set_page_config(page_title="LeadBoost Hunter", layout="wide")

st.title("LeadBoost Hunter.io")

# Login o registro con código de invitación
email = st.text_input("Email")
password = st.text_input("Password", type="password")
invite = st.text_input("Código de invitación")

if st.button("Login / Registro"):
    if invite != st.secrets["INVITE_CODE"]:
        st.error("Código de invitación incorrecto")
    else:
        user = get_user(email)
        if not user:
            # Crear usuario Freemium con cuota inicial 25
            supabase.table("users").insert({"email": email, "role":"freemium","quota":25}).execute()
            st.success("Usuario registrado como Freemium")
        else:
            st.success(f"Bienvenido {email}")
        st.session_state["user"] = email

if "user" in st.session_state:
    st.sidebar.title("Menú")
    page = st.sidebar.radio("Navegación", ["Dashboard", "Subida de Leads", "Usuarios (Admin)"])

    if page == "Dashboard":
        import pages.dashboard as dashboard
        dashboard.show_dashboard(st.session_state["user"])
    elif page == "Subida de Leads":
        import pages.upload as upload
        upload.show_upload(st.session_state["user"])
    elif page == "Usuarios (Admin)":
        import pages.users as users
        users.show_users()
