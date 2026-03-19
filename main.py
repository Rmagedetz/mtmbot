import streamlit as st
from bot import run
import threading

st.write("Test app")

bot_thread = threading.Thread(target=run, daemon=True)
bot_thread.start()

st.write("Processing")