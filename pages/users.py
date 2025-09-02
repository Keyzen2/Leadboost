import streamlit as st
from utils import supabase

def show_users():
    st.header("Usuarios")
    users = supabase.table("users").select("*").execute().data
    st.write(users)

