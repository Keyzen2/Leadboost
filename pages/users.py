import streamlit as st
import pandas as pd
from utils import supabase

st.title("Gestión de Usuarios (Admin)")

data = supabase.table("users").select("*").execute()
df = pd.DataFrame(data.data)

st.dataframe(df)

# Botón para cambiar plan
for i, row in df.iterrows():
    if st.button(f"Hacer Premium: {row['email']}"):
        supabase.table("users").update({"plan":"Premium","role":"premium","monthly_quota":500}).eq("email", row['email']).execute()
        st.success(f"{row['email']} ahora es Premium")
