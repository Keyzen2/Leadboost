import streamlit as st
import pandas as pd
from utils import enrich_email, update_quota, supabase

def show_upload(user_email):
    st.header("Subida de Leads")
    uploaded_file = st.file_uploader("Sube tu CSV de emails", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        enriched_data = []
        for index, row in df.iterrows():
            if update_quota(user_email, 1) is not None:
                enriched = enrich_email(row['email'])
                enriched_data.append(enriched)
                supabase.table("leads").insert(enriched).execute()
            else:
                st.warning("Has alcanzado tu cuota mensual")
                break
        st.write(pd.DataFrame(enriched_data))
