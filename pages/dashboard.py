import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_leads

st.title("Dashboard de Leads")

leads = load_leads()
if not leads.empty:
    st.metric("Total Leads", len(leads))
    st.metric("Leads recientes", leads['created_at'].max())
    
    fig_company = px.bar(leads.groupby("company").size().reset_index(name="count"), x="company", y="count", title="Leads por Empresa")
    st.plotly_chart(fig_company)

    fig_title = px.bar(leads.groupby("title").size().reset_index(name="count"), x="title", y="count", title="Leads por Cargo")
    st.plotly_chart(fig_title)

    st.write("Últimos Leads:")
    st.dataframe(leads.sort_values("created_at", ascending=False).head(10))
else:
    st.info("No hay leads aún.")
