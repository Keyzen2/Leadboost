import streamlit as st
from utils import get_user, create_user, update_plan, INVITE_CODE

st.set_page_config(page_title="Enriquecimiento de Leads", layout="wide")

# --- Layout: sidebar ---
st.sidebar.title("Menú")
menu = st.sidebar.radio("Navegación", ["Dashboard", "Subida de Leads", "Análisis", "Usuarios (Admin)"])

# --- Login / Registro ---
st.title("Login o Registro")
option = st.radio("Elige:", ["Login", "Registro"])
email = st.text_input("Email")
password = st.text_input("Contraseña", type="password")

if option == "Registro":
    code = st.text_input("Código de invitación")
    if st.button("Registrarse"):
        if code == INVITE_CODE:
            create_user(email)
            st.success("Usuario creado. Comprueba tu email.")
        else:
            st.error("Código de invitación inválido")

elif option == "Login":
    # Para simplificar usamos solo validación básica
    user = get_user(email)
    if st.button("Acceder"):
        if user:
            st.success(f"Bienvenido {email} - Plan: {user['plan']}")
            
            # Botón de upgrade
            if user['plan'].lower() == "freemium":
                if st.button("Actualizar a Premium"):
                    update_plan(email, "Premium")
                    st.success("Ahora eres Premium!")

            # Redirigir al menú
            st.session_state['user'] = user
            st.session_state['email'] = email
        else:
            st.error("Usuario no encontrado")
