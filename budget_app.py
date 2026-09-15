import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread

# -----------------------------------------------------------------------------
# 1. SETUP & AUTHENTICATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="centered")

st.title("🪿 Budget Goose")

# Connect to Google Sheets via Streamlit Secrets
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

try:
    gc = get_gspread_client()
    sh = gc.open("BUDGET-2026") 
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

def append_to_table(ws, row_data):
    """
    Inserts data cleanly inside a formatted Google Sheets Table object
    by scanning all rows for the first available empty slot or inserting a row.
    """
    # Fetch all data values across columns A to E
    all_rows = ws.get_all_values()
    
    target_row = None
    
    # Iterate through existing rows starting from row 2 (skipping headers)
    for idx, row in enumerate(all_rows[1:], start=2):
        # Read Column A (Type) and Column B (Position)
        col_a = row[0].strip() if len(row) > 0 else ""
        col_b = row[1].strip() if len(row) > 1 else ""
        
        # Identify empty slots inside the table (ignoring banner titles like '--- MILAN ---')
        if not col_a and not col_b:
            target_row = idx
            break
            
    # If no empty slot exists inside the current table range, append right after the last content row
    if target_row is None:
        target_row = len(all_rows) + 1

    # Update range A{target_row}:E{target_row} to keep entries inside the table boundaries
    cell_range = f"A{target_row}:E{target_row}"
    ws.update(cell_range, [row_data])


def get_or_create_worksheet(sheet_name):
    """Fetches a monthly worksheet tab or creates it with default headers if missing."""
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=100, cols=10)
        # Default header row matching your Excel layout
        append_to_table(ws, ["Type", "Position", "Amount", "Categorie", "Notes"])
    return ws

def format_month_tab(dt):
    return dt.strftime("%b %y")

# -----------------------------------------------------------------------------
# 2. MAIN LOGGING FORM
# -----------------------------------------------------------------------------
st.subheader("Add Log Entry")

entry_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
position = st.text_input("Position / Description", placeholder="e.g., Aldi, Bike24, Hotel Granada")
amount = st.number_input("Amount (€)", min_value=0.0, step=1.00, format="%.2f")
category = st.selectbox("Category", [
    "Household", "Food", "Sport", "Travel", "Car & Transport", 
    "Shopping", "Party & Cafe", "Invest", "Donat", "Work"
])
notes = st.text_input("Notes", placeholder="e.g., PP 30 days, refund")

# -----------------------------------------------------------------------------
# 3. ADVANCED FEATURES (ACCORDION)
# -----------------------------------------------------------------------------
with st.expander("⚙️ Advanced Options (Travel Mode & Installments)"):
    
    enable_installments = st.checkbox("Split into Monthly Installments")
    if enable_installments:
        installments_count = st.number_input("Number of Months (N)", min_value=2, max_value=24, value=3, step=1)
    else:
        installments_count = 1

    st.markdown("---")
    travel_action = st.radio("Trip Banner", ["None", "Start Trip", "End Trip"], horizontal=True)
    trip_name = st.text_input("Trip Name", placeholder="e.g., MALAGA, BADLANDS 🏜️")

# -----------------------------------------------------------------------------
# 4. SUBMIT & EXECUTE GOOGLE SHEETS WRITE
# -----------------------------------------------------------------------------
if st.button("Submit to Budget", type="primary", use_container_width=True):
    if amount <= 0 and not position and travel_action == "None":
        st.error("Please provide a valid description and amount.")
    else:
        current_dt = datetime.now()
        signed_amount = -amount if entry_type == "Expense" else amount
        
        # A) Process Installments
        if enable_installments and installments_count > 1:
            split_amount = round(signed_amount / installments_count, 2)
            
            for i in range(installments_count):
                target_dt = current_dt + relativedelta(months=i)
                tab_name = format_month_tab(target_dt)
                ws = get_or_create_worksheet(tab_name)
                
                inst_note = f"{notes} ({i+1}/{installments_count})" if notes else f"{i+1}/{installments_count}"
                row_data = [entry_type, position, split_amount, category, inst_note]
                append_to_table(ws, row_data)
                
            st.success(f"Successfully split {signed_amount:.2f}€ into {installments_count} monthly entries of {split_amount:.2f}€!")
        
        # B) Single Entry Logging
        elif amount > 0:
            tab_name = format_month_tab(current_dt)
            ws = get_or_create_worksheet(tab_name)
            row_data = [entry_type, position, signed_amount, category, notes]
            append_to_table(ws, row_data)
            st.success(f"Logged {signed_amount:.2f}€ for '{position}' in '{tab_name}'!")

        # C) Process Travel Banner (Start/End Trip)
        if travel_action != "None" and trip_name:
            tab_name = format_month_tab(current_dt)
            ws = get_or_create_worksheet(tab_name)
            
            if travel_action == "Start Trip":
                banner_text = f"--- START {trip_name.upper()} ---"
            else:
                banner_text = f"--- END {trip_name.upper()} ---"
                
            append_to_table(ws, ["", banner_text, "", "", ""])
            st.info(f"Added banner: '{banner_text}' to '{tab_name}'")
