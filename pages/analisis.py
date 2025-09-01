import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_leads

st.title("Análisis Avanzado de Leads")

leads = load_leads()
if not leads.empty:
    filtro_empresa = st.selectbox("Filtrar por empresa", ["Todas"] + list(leads['company'].dropna().unique()))
    if filtro_empresa != "Todas":
        leads = leads[leads['company'] == filtro_empresa]

    fig = px.bar(leads.groupby("title").size().reset_index(name="count"), x="title", y="count", title="Leads por Cargo")
    st.plotly_chart(fig)

    st.download_button("Exportar CSV", leads.to_csv(index=False), "leads.csv")
else:
    st.info("No hay datos para analizar")
