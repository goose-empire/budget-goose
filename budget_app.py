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

def append_to_table(ws, row_data_b_to_e, is_bold=False):
    """
    Updates columns B through E directly (4 items: Position, Amount, Category, Notes),
    preserving any existing formulas in Column A. Option to apply bold formatting.
    """
    all_rows = ws.get_all_values()
    target_row = None
    
    # Iterate through existing rows starting from row 2 (skipping headers)
    for idx, row in enumerate(all_rows[1:], start=2):
        col_b = row[1].strip() if len(row) > 1 else ""
        col_c = row[2].strip() if len(row) > 2 else ""
        
        # Identify empty slots inside the table (checking Position and Amount)
        if not col_b and not col_c:
            target_row = idx
            break
            
    # If no empty slot exists inside the current table range, append right after the last content row
    if target_row is None:
        target_row = len(all_rows) + 1

    # Update ONLY columns B through E (Position, Amount, Category, Notes)
    cell_range = f"B{target_row}:E{target_row}"
    ws.update(cell_range, [row_data_b_to_e])
    
    # Apply bold formatting if requested (e.g., for Trip Banners)
    if is_bold:
        try:
            ws.format(f"B{target_row}", {"textFormat": {"bold": True}})
        except Exception:
            pass
            
    return target_row

def get_or_create_worksheet(sheet_name):
    """Fetches a monthly worksheet tab or creates it with default headers if missing."""
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=100, cols=10)
        # Pass 4 headers corresponding to Columns B, C, D, E
        append_to_table(ws, ["Position", "Amount", "Categorie", "Notes"])
    return ws

def format_month_tab(dt):
    return dt.strftime("%b %y")

# -----------------------------------------------------------------------------
# 2. MAIN LOGGING FORM
# -----------------------------------------------------------------------------
st.subheader("Add Log Entry")

entry_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
position = st.text_input("Position / Description", placeholder="e.g., Aldi, Bike24, Hotel Granada")

# UX Update: Amount input field starts blank using placeholder value=None
amount = st.number_input("Amount (€)", min_value=0.0, step=1.00, format="%.2f", value=None, placeholder="0.00")

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
    num_amount = amount if amount is not None else 0.0
    
    if num_amount <= 0 and not position and travel_action == "None":
        st.error("Please provide a valid description and amount.")
    else:
        current_dt = datetime.now()
        signed_amount = -abs(num_amount) if entry_type == "Expense" else abs(num_amount)
        tab_name = format_month_tab(current_dt)
        ws = get_or_create_worksheet(tab_name)

        # 1) Start Trip Banner (Logged BEFORE the expense)
        if travel_action == "Start Trip" and trip_name:
            banner_text = f"--- START {trip_name.upper()} ---"
            # Send data ONLY to Column B, formatted as BOLD
            append_to_table(ws, [banner_text, "", "", ""], is_bold=True)
            st.info(f"Added bold banner: '{banner_text}' to '{tab_name}'")

        # 2) Process Expense / Income / Installments
        if enable_installments and installments_count > 1 and num_amount > 0:
            split_amount = round(signed_amount / installments_count, 2)
            
            for i in range(installments_count):
                target_dt = current_dt + relativedelta(months=i)
                target_tab = format_month_tab(target_dt)
                target_ws = get_or_create_worksheet(target_tab)
                
                inst_note = f"{notes} ({i+1}/{installments_count})" if notes else f"{i+1}/{installments_count}"
                row_data_b_to_e = [position, split_amount, category, inst_note]
                append_to_table(target_ws, row_data_b_to_e)
                
            st.success(f"Successfully split {signed_amount:.2f}€ into {installments_count} monthly entries of {split_amount:.2f}€!")
        
        elif num_amount > 0 or position:
            row_data_b_to_e = [position, signed_amount if num_amount > 0 else "", category if num_amount > 0 else "", notes]
            append_to_table(ws, row_data_b_to_e)
            if num_amount > 0:
                st.success(f"Logged {signed_amount:.2f}€ for '{position}' in '{tab_name}'!")

        # 3) End Trip Banner (Logged AFTER the expense)
        if travel_action == "End Trip" and trip_name:
            banner_text = f"--- END {trip_name.upper()} ---"
            # Send data ONLY to Column B, formatted as BOLD
            append_to_table(ws, [banner_text, "", "", ""], is_bold=True)
            st.info(f"Added bold banner: '{banner_text}' to '{tab_name}'")
