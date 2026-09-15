import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread

# -----------------------------------------------------------------------------
# 1. SETUP & AUTHENTICATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Budget Goose", page_icon="🪿", layout="centered")

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

def append_to_section(ws, row_data_b_to_e, is_fixed=False, is_bold=False):
    """
    Inserts data into the correct section of the worksheet:
    - If is_fixed=True: Places entry under 'FIXED & RECURRING' before 'DAILY' starts.
    - If is_fixed=False: Places entry floating below 'DAILY'.
    Preserves Column A Excel formulas by writing strictly to Columns B:E.
    Applies default formatting: Roboto Mono, 10pt, and € currency formatting on Column C.
    """
    all_rows = ws.get_all_values()
    
    fixed_start_idx = None
    daily_start_idx = None
    
    # Locate section headers in Column B (index 1)
    for idx, row in enumerate(all_rows, start=1):
        col_b_text = row[1].upper().strip() if len(row) > 1 else ""
        if "FIXED" in col_b_text and "RECURRING" in col_b_text:
            fixed_start_idx = idx
        elif "DAILY" in col_b_text:
            daily_start_idx = idx

    target_row = None
    
    if is_fixed:
        # Route to FIXED & RECURRING section
        search_start = (fixed_start_idx + 1) if fixed_start_idx else 2
        search_end = daily_start_idx if daily_start_idx else len(all_rows) + 1
        
        for idx in range(search_start, search_end):
            row = all_rows[idx - 1] if idx <= len(all_rows) else []
            col_b = row[1].strip() if len(row) > 1 else ""
            col_c = row[2].strip() if len(row) > 2 else ""
            if not col_b and not col_c:
                target_row = idx
                break
                
        if target_row is None:
            target_row = daily_start_idx if daily_start_idx else len(all_rows) + 1
            ws.insert_row([""] + row_data_b_to_e, target_row)
            apply_row_formatting(ws, target_row, is_bold)
            return target_row

    else:
        # Route to DAILY section
        search_start = (daily_start_idx + 1) if daily_start_idx else 2
        
        for idx in range(search_start, len(all_rows) + 1):
            row = all_rows[idx - 1]
            col_b = row[1].strip() if len(row) > 1 else ""
            col_c = row[2].strip() if len(row) > 2 else ""
            if not col_b and not col_c:
                target_row = idx
                break
                
        if target_row is None:
            target_row = len(all_rows) + 1

    # Update range B:E for target row
    cell_range = f"B{target_row}:E{target_row}"
    ws.update(cell_range, [row_data_b_to_e])
    
    # Apply cell formatting (Roboto Mono, 10pt, Currency on Col C)
    apply_row_formatting(ws, target_row, is_bold)
            
    return target_row

def apply_row_formatting(ws, row_idx, is_bold=False):
    """
    Applies custom styling to newly added rows:
    - Columns B, C, E: Font Family Roboto Mono, Size 10
    - Column D (Category): Font Family Roboto Mono, Size 8
    - Column C (Amount): Currency formatting '€#,##0.00; -€#,##0.00; €0.00'
    - Optional: Bold text
    """
    try:
        # Format Columns B, C, E with Roboto Mono, 10pt
        ws.format(f"B{row_idx}:C{row_idx}", {
            "textFormat": {
                "fontFamily": "Roboto Mono",
                "fontSize": 10,
                #"bold": is_bold
            }
        })
        ws.format(f"E{row_idx}", {
            "textFormat": {
                "fontFamily": "Roboto Mono",
                "fontSize": 10,
                #"bold": is_bold
            }
        })

        # Format Column D (Category) specifically with Font Size 8
        ws.format(f"D{row_idx}", {
            "textFormat": {
                "fontFamily": "Roboto Mono",
                "fontSize": 8,
                #"bold": is_bold
            }
        })
        
        # Apply Currency formatting specifically to Column C (Amount)
        ws.format(f"C{row_idx}", {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "€#,##0.00; -€#,##0.00; €0.00"
            },
            "textFormat": {
                "fontFamily": "Roboto Mono",
                "fontSize": 10,
                #"bold": is_bold
            }
        })
    except Exception:
        pass

def get_or_create_worksheet(sheet_name):
    """Fetches a monthly worksheet tab or creates it with default headers if missing."""
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=100, cols=10)
        append_to_section(ws, ["Position", "Amount", "Categorie", "Notes"], is_fixed=False)
    return ws

def format_month_tab(dt):
    return dt.strftime("%b %y")

# -----------------------------------------------------------------------------
# 2. MAIN LOGGING FORM
# -----------------------------------------------------------------------------
st.subheader("Add Log Entry")

entry_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
position = st.text_input("Position / Description", placeholder="e.g., Aldi, Rent, Bike24")

amount = st.number_input("Amount (€)", min_value=0.0, step=1.00, format="%.2f", value=None, placeholder="0.00")

category = st.selectbox("Category", [
    "Household", "Food", "Sport", "Travel", "Car & Transport", 
    "Shopping", "Party & Cafe", "Invest", "Donat", "Work"
])
notes = st.text_input("Notes", placeholder="e.g., PP 30 days, refund")

# -----------------------------------------------------------------------------
# 3. ADVANCED FEATURES (ACCORDION)
# -----------------------------------------------------------------------------
with st.expander("⚙️ Advanced Options (Fixed, Travel Mode & Installments)"):
    
    is_fixed_entry = st.checkbox("FIXED & RECURRING (Rent, Utilities, Fixed Subscriptions)")

    # st.markdown("---")

    enable_installments = st.checkbox("Split into Monthly Installments")
    if enable_installments:
        installments_count = st.number_input("Number of Months (N)", min_value=2, max_value=12, value=3, step=1)
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

        # 1) Start Trip Banner (Logged BEFORE the expense in DAILY section)
        if travel_action == "Start Trip" and trip_name:
            banner_text = f"--- START {trip_name.upper()} ---"
            append_to_section(ws, [banner_text, "", "", ""], is_fixed=False, is_bold=True)
            st.info(f"Added bold banner: '{banner_text}' under DAILY in '{tab_name}'")

        # 2) Process Expense / Income / Instalments
        if enable_installments and installments_count > 1 and num_amount > 0:
            split_amount = round(signed_amount / installments_count, 2)
            
            for i in range(installments_count):
                target_dt = current_dt + relativedelta(months=i)
                target_tab = format_month_tab(target_dt)
                target_ws = get_or_create_worksheet(target_tab)
                
                inst_note = f"{notes} ({i+1}/{installments_count})" if notes else f"{i+1}/{installments_count}"
                row_data_b_to_e = [position, split_amount, category, inst_note]
                append_to_section(target_ws, row_data_b_to_e, is_fixed=True)
                
            st.success(f"Successfully split {signed_amount:.2f}€ into {installments_count} monthly entries under FIXED & RECURRING!")
        
        elif num_amount > 0 or position:
            row_data_b_to_e = [position, signed_amount if num_amount > 0 else "", category if num_amount > 0 else "", notes]
            append_to_section(ws, row_data_b_to_e, is_fixed=is_fixed_entry)
            section_name = "FIXED & RECURRING" if is_fixed_entry else "DAILY"
            if num_amount > 0:
                st.success(f"Logged {signed_amount:.2f}€ for '{position}' under {section_name} in '{tab_name}'!")

        # 3) End Trip Banner (Logged AFTER the expense in DAILY section)
        if travel_action == "End Trip" and trip_name:
            banner_text = f"--- END {trip_name.upper()} ---"
            append_to_section(ws, [banner_text, "", "", ""], is_fixed=False, is_bold=True)
            st.info(f"Added bold banner: '{banner_text}' under DAILY in '{tab_name}'")
