import streamlit as st
from utils import supabase
import pandas as pd
import altair as alt

def show_dashboard(user_email):
    st.header("Dashboard")
    leads = supabase.table("leads").select("*").execute().data
    df = pd.DataFrame(leads)
    if df.empty:
        st.info("No hay leads aún")
        return
    st.subheader("Leads por Empresa")
    chart = alt.Chart(df).mark_bar().encode(
        x='company:N', y='count()'
    )
    st.altair_chart(chart, use_container_width=True)

    st.subheader("Emails Verificados vs No Verificados")
    verificados = df['verified'].value_counts().reset_index()
    st.bar_chart(verificados.set_index('index'))

