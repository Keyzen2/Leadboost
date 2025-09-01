import streamlit as st
import pandas as pd
from utils import enrich_email, save_lead, get_user, increment_quota

st.title("Subida de Leads")

uploaded_file = st.file_uploader("Sube un CSV con correos", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.dataframe(df.head())

    if st.button("Enriquecer Leads"):
        user = get_user(st.session_state['email'])
        results = []
        for email_row in df['email']:
            if user['used_quota'] >= user['monthly_quota']:
                st.warning("Has alcanzado tu límite mensual")
                break
            enriched = enrich_email(email_row)
            enriched['email'] = email_row
            save_lead(enriched)
            increment_quota(user['email'])
            results.append(enriched)
        st.success("Leads enriquecidos y guardados")
        st.dataframe(pd.DataFrame(results))
