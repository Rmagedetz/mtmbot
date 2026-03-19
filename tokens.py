import streamlit as st

production_mode = {"bot_tg_token": st.secrets["tg_bot"]["prod_token"],
                   "group_tg_id": -1001737766050,
                   "google_table_name": "Momentum"}

demo_mode = {"bot_tg_token": st.secrets["tg_bot"]["demo_token"],
             "group_tg_id": -5093583277,
             "google_table_name": "Momentum"}

gc_service_account = {"type": st.secrets["gs_credit_nails"]["type"],
                      "project_id": st.secrets["gs_credit_nails"]["project_id"],
                      "private_key_id": st.secrets["gs_credit_nails"]["private_key_id"],
                      "private_key": st.secrets["gs_credit_nails"]["private_key"],
                      "client_email": st.secrets["gs_credit_nails"]["client_email"],
                      "client_id": st.secrets["gs_credit_nails"]["client_id"],
                      "auth_uri": st.secrets["gs_credit_nails"]["auth_uri"],
                      "token_uri": st.secrets["gs_credit_nails"]["token_uri"],
                      "auth_provider_x509_cert_url": st.secrets["gs_credit_nails"]["auth_provider_x509_cert_url"],
                      "client_x509_cert_url": st.secrets["gs_credit_nails"]["client_x509_cert_url"],
                      "universe_domain": st.secrets["gs_credit_nails"]["universe_domain"]}
