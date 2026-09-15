import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="centered")

st.title("💸 Quick Expense Tracker")

# Form Inputs
entry_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
position = st.text_input("Position / Description (e.g., Aldi, Bike24)")
amount = st.number_input("Amount (€)", min_value=0.0, step=1.00, format="%.2f")
category = st.selectbox("Category", [
    "Household", "Food", "Sport", "Travel", "Car & Transport", 
    "Shopping", "Party & Cafe", "Invest", "Donat", "Work"
])
notes = st.text_input("Notes (optional, e.g., PP 30 days)")

if st.button("Log Entry", type="primary"):
    if amount > 0 and position:
        val = -amount if entry_type == "Expense" else amount
        new_data = {
            "Date": [datetime.now().strftime("%Y-%m-%d %H:%M")],
            "Type": [entry_type],
            "Position": [position],
            "Amount": [val],
            "Category": [category],
            "Notes": [notes]
        }
        df_new = pd.DataFrame(new_data)
        
        # Save locally or append to Google Sheets / CSV
        df_new.to_csv("expenses_log.csv", mode='a', header=False, index=False)
        st.success(f"Logged {val:.2f}€ for '{position}' under {category}!")
    else:
        st.error("Please enter a valid amount and description.")