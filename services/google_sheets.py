"""Google Sheets service for the Expense Tracker.

Handles authentication, worksheet management, input validation,
and recording transactions month-wise in Google Sheets.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import uuid
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

# Fixed categories as per specification
VALID_CATEGORIES: list[str] = [
    "Beverages",
    "Food-Online",
    "Food-Offline",
    "Travelling",
    "Others",
]

# Fixed payment types as per specification
VALID_PAYMENT_TYPES: list[str] = [
    "Cash",
    "Online",
]

# Standard column headers in exact order
COLUMNS: list[str] = [
    "Transaction ID",
    "Transaction Date",
    "Created At",
    "Amount",
    "Payment Type",
    "Category",
    "Specific Reason",
    "Notes",
]

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class ExpenseTrackerError(Exception):
    """Base exception for expense tracker errors."""


class ConfigurationError(ExpenseTrackerError):
    """Raised when Google Sheets credentials or spreadsheet ID are missing/invalid."""


class ValidationError(ExpenseTrackerError):
    """Raised when expense entry validation fails."""


class GoogleSheetsError(ExpenseTrackerError):
    """Raised when an operation against Google Sheets API fails."""


def generate_transaction_id() -> str:
    """Generate a unique transaction ID.

    Format: TXN-YYYYMMDDHHMMSS-<SHORT_UUID>
    Example: TXN-20261021173000-9B2F8A
    """
    now = datetime.datetime.now()
    time_prefix = now.strftime("%Y%m%d%H%M%S")
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TXN-{time_prefix}-{random_suffix}"


def get_sheet_name_for_date(expense_date: datetime.date | datetime.datetime) -> str:
    """Determine the destination monthly worksheet title from the selected date.

    Format: '<Month Name> <YYYY>' (e.g., 'October 2026')
    """
    if isinstance(expense_date, str):
        try:
            expense_date = datetime.date.fromisoformat(expense_date)
        except ValueError:
            raise ValidationError(f"Invalid date format: {expense_date}. Expected YYYY-MM-DD.")

    if not isinstance(expense_date, (datetime.date, datetime.datetime)):
        raise ValidationError(f"Expected date or datetime object, got {type(expense_date).__name__}")

    return expense_date.strftime("%B %Y")


def validate_expense_data(
    expense_date: Any,
    amount: Any,
    payment_type: Any,
    category: Any,
    specific_reason: Any,
    notes: Any = "",
) -> tuple[bool, str | None]:
    """Validate all required fields for an expense entry.

    Returns:
        tuple[bool, str | None]: (True, None) if valid, or (False, error_message).
    """
    # 1. Validate Date
    if expense_date is None:
        return False, "Please select an expense date."

    if isinstance(expense_date, str):
        try:
            parsed_date = datetime.date.fromisoformat(expense_date)
        except ValueError:
            return False, "Invalid date format. Please provide a valid date."
    elif isinstance(expense_date, (datetime.date, datetime.datetime)):
        parsed_date = (
            expense_date.date() if isinstance(expense_date, datetime.datetime) else expense_date
        )
    else:
        return False, "Invalid date format."

    # Prevent unreasonable year ranges (e.g., accidental typo year 0001 or 9999)
    if parsed_date.year < 2000 or parsed_date.year > 2100:
        return False, f"Date year {parsed_date.year} is out of realistic range (2000-2100)."

    # 2. Validate Amount
    if amount is None:
        return False, "Please enter an expense amount."

    try:
        numeric_amount = float(amount)
    except (ValueError, TypeError):
        return False, "Amount must be a valid positive number."

    if numeric_amount <= 0:
        return False, "Amount must be greater than zero."

    if numeric_amount > 100_000_000:
        return False, "Amount exceeds the maximum allowed limit of ₹10,00,00,000."

    # 3. Validate Payment Type
    if not payment_type or payment_type not in VALID_PAYMENT_TYPES:
        return (
            False,
            f"Invalid payment type '{payment_type}'. Must be one of: {', '.join(VALID_PAYMENT_TYPES)}.",
        )

    # 4. Validate Category
    if not category or category not in VALID_CATEGORIES:
        return (
            False,
            f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}.",
        )

    # 5. Validate Specific Reason
    if not specific_reason or not str(specific_reason).strip():
        return False, "Specific reason is required. Please describe the expense."

    clean_reason = str(specific_reason).strip()
    if len(clean_reason) < 2:
        return False, "Specific reason must be at least 2 characters long."

    # For 'Others' category, require a meaningful description
    if category == "Others":
        if len(clean_reason) < 4:
            return (
                False,
                "For the 'Others' category, please provide a meaningful explanation (at least 4 characters).",
            )
        # Check against trivial entries like 'other', 'misc', 'na', 'none'
        if clean_reason.lower() in {"other", "others", "misc", "miscellaneous", "n/a", "na", "none", "etc", "xyz"}:
            return (
                False,
                "For the 'Others' category, please specify what this expense was actually for.",
            )

    return True, None


def format_transaction_row(
    transaction_id: str,
    expense_date: datetime.date | str,
    created_at: datetime.datetime | str,
    amount: float | int,
    payment_type: str,
    category: str,
    specific_reason: str,
    notes: str = "",
) -> list[Any]:
    """Format an expense entry into a standard row matching COLUMNS order.

    Order:
    1. Transaction ID
    2. Transaction Date (YYYY-MM-DD)
    3. Created At (YYYY-MM-DD HH:MM:SS)
    4. Amount (numeric float for sheet formulas/sorting)
    5. Payment Type
    6. Category
    7. Specific Reason
    8. Notes
    """
    # Date formatting
    if isinstance(expense_date, (datetime.date, datetime.datetime)):
        date_str = expense_date.strftime("%Y-%m-%d")
    else:
        date_str = str(expense_date)

    # Created at formatting
    if isinstance(created_at, datetime.datetime):
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(created_at, datetime.date):
        created_at_str = f"{created_at.strftime('%Y-%m-%d')} 00:00:00"
    else:
        created_at_str = str(created_at)

    # Amount as numeric float
    numeric_amount = round(float(amount), 2)

    return [
        str(transaction_id),
        date_str,
        created_at_str,
        numeric_amount,
        str(payment_type),
        str(category),
        str(specific_reason).strip(),
        str(notes or "").strip(),
    ]


def extract_spreadsheet_id(spreadsheet_input: str) -> str:
    """Extract a clean spreadsheet ID from either a raw ID or full Google Sheets URL.

    Example inputs:
    - '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
    - 'https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0'
    """
    clean_input = spreadsheet_input.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean_input)
    if match:
        return match.group(1)
    return clean_input


def load_credentials_and_spreadsheet_id(
    secrets_obj: Any = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load service account credentials dict and spreadsheet ID.

    Checks:
    1. secrets_obj (e.g. Streamlit secrets or custom dict)
    2. Environment variables: SPREADSHEET_ID / GOOGLE_SPREADSHEET_ID,
       GOOGLE_APPLICATION_CREDENTIALS / GCP_SERVICE_ACCOUNT_JSON
    """
    credentials_dict: dict[str, Any] | None = None
    spreadsheet_id: str | None = None

    # 1. Check secrets_obj (Streamlit secrets)
    if secrets_obj is not None:
        try:
            # Check for spreadsheet_id
            if "spreadsheet_id" in secrets_obj:
                spreadsheet_id = str(secrets_obj["spreadsheet_id"]).strip()
            elif "GOOGLE_SPREADSHEET_ID" in secrets_obj:
                spreadsheet_id = str(secrets_obj["GOOGLE_SPREADSHEET_ID"]).strip()

            # Check for service account
            if "gcp_service_account" in secrets_obj:
                sa_data = secrets_obj["gcp_service_account"]
                # Convert to regular dict if it's an AttrDict or Mapping
                credentials_dict = dict(sa_data)
            elif "service_account" in secrets_obj:
                credentials_dict = dict(secrets_obj["service_account"])
        except Exception:
            pass

    # 2. Check environment variables as fallback
    if not spreadsheet_id:
        env_id = os.environ.get("SPREADSHEET_ID") or os.environ.get("GOOGLE_SPREADSHEET_ID")
        if env_id:
            spreadsheet_id = env_id.strip()

    if not credentials_dict:
        # Check GCP_SERVICE_ACCOUNT_JSON env var
        sa_json_env = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if sa_json_env:
            try:
                credentials_dict = json.loads(sa_json_env)
            except Exception:
                pass

        # Check GOOGLE_APPLICATION_CREDENTIALS file
        cred_file_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_file_env and os.path.exists(cred_file_env):
            try:
                with open(cred_file_env, "r", encoding="utf-8") as f:
                    credentials_dict = json.load(f)
            except Exception:
                pass

    # Normalize private_key newlines if present in credentials dict
    if credentials_dict and "private_key" in credentials_dict:
        pk = credentials_dict["private_key"]
        if isinstance(pk, str) and "\\n" in pk and "\n" not in pk:
            credentials_dict["private_key"] = pk.replace("\\n", "\n")

    if spreadsheet_id:
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_id)

    return credentials_dict, spreadsheet_id


def get_gspread_client(credentials_dict: dict[str, Any]) -> gspread.Client:
    """Create an authorized gspread Client from a service account dictionary."""
    try:
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES,
        )
        return gspread.authorize(credentials)
    except Exception as exc:
        raise ConfigurationError(f"Failed to authenticate with Google service account: {exc}") from exc


def ensure_worksheet_exists(
    spreadsheet: gspread.Spreadsheet,
    sheet_name: str,
) -> gspread.Worksheet:
    """Find the monthly worksheet, or create it automatically with standard headers if it does not exist."""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # Create the worksheet with standard dimensions
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=1000,
            cols=len(COLUMNS),
        )
        # Add header row
        worksheet.append_row(COLUMNS, value_input_option="USER_ENTERED")
        return worksheet

    # If worksheet exists, ensure header row is present
    try:
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(COLUMNS, value_input_option="USER_ENTERED")
    except Exception:
        # If unable to check row_values, proceed to allow append
        pass

    return worksheet


def save_expense_to_sheets(
    credentials_dict: dict[str, Any],
    spreadsheet_id: str,
    expense_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate, authenticate, find/create monthly tab, and append expense transaction.

    Args:
        credentials_dict: Google Cloud service account JSON dictionary.
        spreadsheet_id: ID or URL of Google Spreadsheet.
        expense_data: Dictionary containing:
            - date: datetime.date or str
            - amount: numeric
            - payment_type: 'Cash' or 'Online'
            - category: one of VALID_CATEGORIES
            - specific_reason: str
            - notes: str (optional)
            - transaction_id: str (optional; generated if not provided)
            - created_at: datetime.datetime (optional; generated if not provided)

    Returns:
        dict: Summary of saved transaction including transaction_id, sheet_name, row.

    Raises:
        ValidationError: If any field fails validation.
        ConfigurationError: If credentials or spreadsheet ID are invalid.
        GoogleSheetsError: If API call fails.
    """
    # 1. Validate inputs
    is_valid, error_msg = validate_expense_data(
        expense_date=expense_data.get("date"),
        amount=expense_data.get("amount"),
        payment_type=expense_data.get("payment_type"),
        category=expense_data.get("category"),
        specific_reason=expense_data.get("specific_reason"),
        notes=expense_data.get("notes", ""),
    )
    if not is_valid:
        raise ValidationError(error_msg or "Validation failed.")

    # 2. Validate configuration
    if not credentials_dict:
        raise ConfigurationError(
            "Google service account credentials not found. Please configure secrets.toml or environment variables."
        )

    if not spreadsheet_id or not spreadsheet_id.strip():
        raise ConfigurationError(
            "Spreadsheet ID not found. Please configure spreadsheet_id in secrets.toml or environment variables."
        )

    clean_sheet_id = extract_spreadsheet_id(spreadsheet_id)

    # 3. Prepare transaction metadata
    transaction_id = expense_data.get("transaction_id") or generate_transaction_id()
    created_at = expense_data.get("created_at") or datetime.datetime.now()
    expense_date = expense_data["date"]
    sheet_name = get_sheet_name_for_date(expense_date)

    row_data = format_transaction_row(
        transaction_id=transaction_id,
        expense_date=expense_date,
        created_at=created_at,
        amount=expense_data["amount"],
        payment_type=expense_data["payment_type"],
        category=expense_data["category"],
        specific_reason=expense_data["specific_reason"],
        notes=expense_data.get("notes", ""),
    )

    # 4. Connect to Google Sheets
    try:
        client = get_gspread_client(credentials_dict)
    except Exception as exc:
        raise ConfigurationError(f"Authentication error: {exc}") from exc

    try:
        spreadsheet = client.open_by_key(clean_sheet_id)
    except gspread.exceptions.SpreadsheetNotFound as exc:
        raise GoogleSheetsError(
            f"Spreadsheet with ID '{clean_sheet_id}' was not found. "
            "Please check that the ID is correct and that the spreadsheet has been shared "
            f"with your service account email ({credentials_dict.get('client_email', 'service account')}) with 'Editor' permissions."
        ) from exc
    except gspread.exceptions.APIError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            raise GoogleSheetsError(
                "Permission denied (403). Make sure the Google Spreadsheet is shared with your service account "
                f"email: {credentials_dict.get('client_email', 'service account')} as 'Editor'."
            ) from exc
        raise GoogleSheetsError(f"Google Sheets API error: {exc}") from exc
    except Exception as exc:
        raise GoogleSheetsError(f"Failed to open spreadsheet: {exc}") from exc

    # 5. Find or create monthly worksheet
    try:
        worksheet = ensure_worksheet_exists(spreadsheet, sheet_name)
    except Exception as exc:
        raise GoogleSheetsError(
            f"Failed to open or create monthly worksheet '{sheet_name}': {exc}"
        ) from exc

    # 6. Append transaction row
    try:
        result = worksheet.append_row(
            row_data,
            value_input_option="USER_ENTERED",
        )
    except Exception as exc:
        raise GoogleSheetsError(
            f"Failed to save expense row to worksheet '{sheet_name}': {exc}"
        ) from exc

    return {
        "success": True,
        "transaction_id": transaction_id,
        "sheet_name": sheet_name,
        "spreadsheet_title": getattr(spreadsheet, "title", "Spreadsheet"),
        "date": row_data[1],
        "created_at": row_data[2],
        "amount": row_data[3],
        "payment_type": row_data[4],
        "category": row_data[5],
        "specific_reason": row_data[6],
        "notes": row_data[7],
        "raw_response": result,
    }
