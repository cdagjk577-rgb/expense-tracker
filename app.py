"""Expense Tracker - Simple, fast, and reliable expense recording with Google Sheets."""

from __future__ import annotations

import datetime
from typing import Any

import streamlit as st

from services.google_sheets import (
    COLUMNS,
    VALID_CATEGORIES,
    VALID_PAYMENT_TYPES,
    ConfigurationError,
    GoogleSheetsError,
    ValidationError,
    generate_transaction_id,
    get_sheet_name_for_date,
    load_credentials_and_spreadsheet_id,
    save_expense_to_sheets,
    validate_expense_data,
)

# Page configuration - Clean, single-page, centered layout
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom styling for high aesthetic, mobile-friendly interface
CUSTOM_CSS = """
<style>
/* Hide Streamlit sidebar and main menu clutter */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}
[data-testid="collapsedControl"] {display: none;}

/* Global fonts and background */
body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
}

/* Center container and limit max width for mobile and desktop */
.block-container {
    max-width: 580px;
    padding-top: 2rem;
    padding-bottom: 3rem;
    padding-left: 1.25rem;
    padding-right: 1.25rem;
}

/* Header styling */
.header-container {
    text-align: center;
    margin-bottom: 1.5rem;
}

.header-title {
    font-size: 1.85rem;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.025em;
    margin-bottom: 0.25rem;
}

.header-subtitle {
    font-size: 0.95rem;
    color: #64748b;
    margin-top: 0;
}

/* Sheet destination badge */
.sheet-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background-color: #f1f5f9;
    color: #334155;
    padding: 0.3rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    margin-bottom: 1rem;
}

/* Success Card */
.success-banner {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
    color: #065f46;
}

.success-banner h4 {
    margin: 0 0 0.35rem 0;
    font-size: 1rem;
    color: #047857;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.success-details {
    font-size: 0.85rem;
    color: #065f46;
    margin: 0;
    line-height: 1.5;
}

/* Setup Warning Card */
.config-warning {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
    color: #92400e;
}

.config-warning h4 {
    margin: 0 0 0.4rem 0;
    color: #b45309;
    font-size: 1rem;
}

/* Button enhancement */
div.stButton > button:first-child {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
    font-size: 1rem;
    border-radius: 8px;
    border: none;
    padding: 0.65rem 1.25rem;
    transition: all 0.2s ease-in-out;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

div.stButton > button:first-child:hover {
    background-color: #1d4ed8;
    box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
}

/* Input label styling */
label {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: #334155 !important;
}

/* Radio button horizontal layout enhancement */
div[role="radiogroup"] {
    gap: 1.5rem;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_secrets_safe() -> Any:
    """Safely access Streamlit secrets without crashing if file is missing."""
    try:
        return st.secrets
    except Exception:
        return None


def init_session_state() -> None:
    """Initialize session state keys for form reset and status tracking."""
    if "form_reset_counter" not in st.session_state:
        st.session_state.form_reset_counter = 0
    if "last_success_transaction" not in st.session_state:
        st.session_state.last_success_transaction = None
    if "last_error" not in st.session_state:
        st.session_state.last_error = None


def main() -> None:
    init_session_state()

    # App Header
    st.markdown(
        """
        <div class="header-container">
            <h1 class="header-title">Expense Tracker</h1>
            <p class="header-subtitle">Record and save your daily expenses directly to Google Sheets</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Load credentials & spreadsheet configuration
    secrets_obj = get_secrets_safe()
    credentials_dict, spreadsheet_id = load_credentials_and_spreadsheet_id(secrets_obj)
    is_configured = bool(credentials_dict and spreadsheet_id)

    # Show configuration notice if setup is incomplete
    if not is_configured:
        st.markdown(
            """
            <div class="config-warning">
                <h4>⚠️ Google Sheets Setup Required</h4>
                <p style="font-size: 0.9rem; margin-bottom: 0.5rem;">
                    Google Sheets credentials or Spreadsheet ID are not configured yet.
                </p>
                <p style="font-size: 0.85rem; margin-bottom: 0;">
                    Please add your credentials to <code>.streamlit/secrets.toml</code> as shown in the Setup Guide below.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Show previous success message if available
    if st.session_state.last_success_transaction:
        txn = st.session_state.last_success_transaction
        st.markdown(
            f"""
            <div class="success-banner">
                <h4>✅ Expense saved successfully!</h4>
                <p class="success-details">
                    <strong>Transaction ID:</strong> <code>{txn['transaction_id']}</code><br>
                    <strong>Worksheet:</strong> <code>{txn['sheet_name']}</code><br>
                    <strong>Recorded:</strong> ₹{txn['amount']:.2f} &bull; {txn['payment_type']} &bull; {txn['category']}<br>
                    <strong>Reason:</strong> {txn['specific_reason']}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Clear after displaying so it doesn't linger forever
        # but keep it visible for this render
        st.session_state.last_success_transaction = None

    # Show previous error message if available
    if st.session_state.last_error:
        st.error(st.session_state.last_error)
        st.session_state.last_error = None

    # Dynamic form key allows resetting all widgets upon successful submission
    # while preserving user's typed entries when validation or saving fails
    counter = st.session_state.form_reset_counter

    with st.form(key=f"expense_form_{counter}", clear_on_submit=False):
        # A. Date Picker
        expense_date = st.date_input(
            "Date",
            value=datetime.date.today(),
            help="Select the date when the expense occurred. Determines the monthly worksheet.",
            key=f"input_date_{counter}",
        )

        # Worksheet name preview based on selected date
        try:
            target_sheet_name = get_sheet_name_for_date(expense_date)
            st.caption(f"📁 Destination tab: **{target_sheet_name}**")
        except Exception:
            target_sheet_name = "Monthly Tab"

        # B. Amount Input (Indian Rupees)
        amount = st.number_input(
            "Amount (₹)",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            help="Enter positive amount in Indian Rupees (₹).",
            key=f"input_amount_{counter}",
        )

        # C. Payment Type (Exactly 2 options: Cash, Online)
        payment_type = st.radio(
            "Payment Type",
            options=VALID_PAYMENT_TYPES,
            index=0,
            horizontal=True,
            help="Choose how the expense was paid.",
            key=f"input_payment_type_{counter}",
        )

        # D. Category (Exactly 5 options)
        category = st.selectbox(
            "Category",
            options=VALID_CATEGORIES,
            index=0,
            help="Select the expense category.",
            key=f"input_category_{counter}",
        )

        # E. Specific Reason (Required text description)
        reason_help = (
            "Explain specifically what this expense was for (required)."
            if category != "Others"
            else "Please provide a meaningful explanation for this expense (required for Others)."
        )
        specific_reason = st.text_input(
            "Specific Reason",
            placeholder=(
                "e.g., Masala tea, Swiggy dinner, Metro card recharge, Auto fare"
                if category != "Others"
                else "e.g., Mobile screen guard replacement, Book purchase"
            ),
            help=reason_help,
            key=f"input_reason_{counter}",
        )

        # F. Notes (Optional)
        notes = st.text_input(
            "Notes (Optional)",
            placeholder="Any extra details, bill #, person, etc.",
            help="Optional notes or memo.",
            key=f"input_notes_{counter}",
        )

        # Submit button
        submit_button = st.form_submit_button(
            "Save Expense",
            use_container_width=True,
            type="primary",
        )

    # Form Submission Handling
    if submit_button:
        # 1. Validate fields on the server side
        is_valid, validation_error = validate_expense_data(
            expense_date=expense_date,
            amount=amount,
            payment_type=payment_type,
            category=category,
            specific_reason=specific_reason,
            notes=notes,
        )

        if not is_valid:
            st.error(f"⚠️ {validation_error}")
            return

        # 2. Check credentials configuration
        if not is_configured:
            st.error(
                "❌ Cannot save expense: Google Sheets is not configured yet. "
                "Please configure your service account credentials and spreadsheet_id in `.streamlit/secrets.toml`."
            )
            return

        # 3. Process submission
        with st.spinner("Connecting to Google Sheets and saving transaction..."):
            expense_payload = {
                "date": expense_date,
                "amount": amount,
                "payment_type": payment_type,
                "category": category,
                "specific_reason": specific_reason,
                "notes": notes,
                "transaction_id": generate_transaction_id(),
                "created_at": datetime.datetime.now(),
            }

            try:
                save_result = save_expense_to_sheets(
                    credentials_dict=credentials_dict,  # type: ignore[arg-type]
                    spreadsheet_id=spreadsheet_id,  # type: ignore[arg-type]
                    expense_data=expense_payload,
                )
            except (ValidationError, ConfigurationError, GoogleSheetsError) as exc:
                # Keep user input preserved on error
                st.error(f"❌ Failed to save expense: {exc}")
                return
            except Exception as exc:
                # Catch-all unexpected errors
                st.error(f"❌ An unexpected error occurred while saving: {exc}")
                return

        # 4. Success handling: store summary, advance form counter to reset form, and rerun
        st.session_state.last_success_transaction = save_result
        st.session_state.form_reset_counter += 1
        st.rerun()

    # Collapsible Setup Instructions (shown if unconfigured or user expands)
    with st.expander("ℹ️ Google Sheets Setup Guide", expanded=not is_configured):
        st.markdown(
            """
            ### How to Connect Your Google Spreadsheet

            Follow these steps to connect this app to your Google Sheet:

            1. **Enable Google Cloud APIs:**
               - Go to [Google Cloud Console](https://console.cloud.google.com/).
               - Create a new project (e.g., `Expense Tracker`).
               - In **APIs & Services > Library**, enable:
                 - **Google Sheets API**
                 - **Google Drive API**

            2. **Create a Service Account:**
               - Go to **IAM & Admin > Service Accounts**.
               - Click **Create Service Account**.
               - Give it a name (e.g., `expense-tracker-bot`) and click **Done**.

            3. **Download Service Account Key:**
               - Click on your newly created service account.
               - Go to the **Keys** tab > **Add Key** > **Create new key**.
               - Select **JSON** format and download the key file.

            4. **Create a Google Spreadsheet:**
               - Create a new Google Spreadsheet at [sheets.google.com](https://sheets.google.com).
               - Copy the Spreadsheet ID from the URL:
                 `https://docs.google.com/spreadsheets/d/`**`<SPREADSHEET_ID>`**`/edit`
               - Click **Share** on the top right, paste your service account's `client_email` (e.g., `expense-tracker-bot@project.iam.gserviceaccount.com`), and grant **Editor** access.

            5. **Configure Streamlit Secrets:**
               - In your project root, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`:
                 ```bash
                 cp .streamlit/secrets.toml.example .streamlit/secrets.toml
                 ```
               - Open `.streamlit/secrets.toml` and set:
                 - `spreadsheet_id = "YOUR_SPREADSHEET_ID"`
                 - Paste the fields from your downloaded service account JSON into the `[gcp_service_account]` section.

            6. **Run the App:**
               ```bash
               streamlit run app.py
               ```
               Worksheet tabs like **October 2026** and column headers will be created automatically!
            """
        )


if __name__ == "__main__":
    main()
