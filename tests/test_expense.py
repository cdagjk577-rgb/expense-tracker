"""Unit tests for Expense Tracker validation, formatting, and Google Sheets integration."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.google_sheets import (
    COLUMNS,
    VALID_CATEGORIES,
    VALID_PAYMENT_TYPES,
    ConfigurationError,
    GoogleSheetsError,
    ValidationError,
    extract_spreadsheet_id,
    format_transaction_row,
    generate_transaction_id,
    get_sheet_name_for_date,
    load_credentials_and_spreadsheet_id,
    save_expense_to_sheets,
    validate_expense_data,
)


class TestValidation:
    """Test validation of all form inputs."""

    def test_valid_expense_data(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=250.50,
            payment_type="Online",
            category="Food-Online",
            specific_reason="Swiggy dinner order",
            notes="Order #12345",
        )
        assert is_valid is True
        assert error is None

    def test_valid_cash_payment(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=20,
            payment_type="Cash",
            category="Beverages",
            specific_reason="Masala tea from stall",
        )
        assert is_valid is True
        assert error is None

    def test_reject_zero_amount(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=0,
            payment_type="Cash",
            category="Beverages",
            specific_reason="Free tea",
        )
        assert is_valid is False
        assert "greater than zero" in error

    def test_reject_negative_amount(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=-100,
            payment_type="Online",
            category="Travelling",
            specific_reason="Refund",
        )
        assert is_valid is False
        assert "greater than zero" in error

    def test_reject_none_amount(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=None,
            payment_type="Online",
            category="Travelling",
            specific_reason="Metro ticket",
        )
        assert is_valid is False
        assert "enter an expense amount" in error

    def test_reject_invalid_amount_string(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount="abc",
            payment_type="Online",
            category="Travelling",
            specific_reason="Metro ticket",
        )
        assert is_valid is False
        assert "valid positive number" in error

    def test_reject_invalid_category(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=500,
            payment_type="Cash",
            category="Groceries",  # Not in the allowed 5 categories
            specific_reason="Vegetables",
        )
        assert is_valid is False
        assert "Invalid category" in error

    def test_reject_invalid_payment_type(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=500,
            payment_type="Credit Card",  # Only Cash and Online allowed
            category="Travelling",
            specific_reason="Fuel",
        )
        assert is_valid is False
        assert "Invalid payment type" in error

    def test_reject_empty_specific_reason(self):
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=500,
            payment_type="Cash",
            category="Travelling",
            specific_reason="   ",
        )
        assert is_valid is False
        assert "Specific reason is required" in error

    def test_others_category_requires_meaningful_reason(self):
        # Trivial reason like 'other' or 'misc' should be rejected
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=150,
            payment_type="Online",
            category="Others",
            specific_reason="misc",
        )
        assert is_valid is False
        assert "what this expense was actually for" in error

        # Short reason (<4 chars) should be rejected for Others
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=150,
            payment_type="Online",
            category="Others",
            specific_reason="box",
        )
        assert is_valid is False
        assert "meaningful explanation" in error

        # Meaningful explanation should pass
        is_valid, error = validate_expense_data(
            expense_date=datetime.date(2026, 10, 21),
            amount=150,
            payment_type="Online",
            category="Others",
            specific_reason="Mobile screen guard replacement",
        )
        assert is_valid is True
        assert error is None

    def test_reject_missing_date(self):
        is_valid, error = validate_expense_data(
            expense_date=None,
            amount=100,
            payment_type="Cash",
            category="Beverages",
            specific_reason="Coffee",
        )
        assert is_valid is False
        assert "select an expense date" in error


class TestWorksheetNaming:
    """Test date-based worksheet naming."""

    def test_october_2026(self):
        d = datetime.date(2026, 10, 15)
        assert get_sheet_name_for_date(d) == "October 2026"

    def test_november_2026(self):
        d = datetime.date(2026, 11, 1)
        assert get_sheet_name_for_date(d) == "November 2026"

    def test_december_2026(self):
        d = datetime.date(2026, 12, 31)
        assert get_sheet_name_for_date(d) == "December 2026"

    def test_string_date_parsing(self):
        assert get_sheet_name_for_date("2026-10-15") == "October 2026"

    def test_invalid_date_type_raises(self):
        with pytest.raises(ValidationError):
            get_sheet_name_for_date(12345)  # type: ignore


class TestTransactionFormatting:
    """Test transaction row formatting and transaction ID generation."""

    def test_transaction_id_format(self):
        txn_id = generate_transaction_id()
        assert txn_id.startswith("TXN-")
        # Ensure successive IDs are unique
        txn_id_2 = generate_transaction_id()
        assert txn_id != txn_id_2

    def test_format_row_columns_and_types(self):
        row = format_transaction_row(
            transaction_id="TXN-20261021-0001",
            expense_date=datetime.date(2026, 10, 21),
            created_at=datetime.datetime(2026, 10, 21, 17, 30, 0),
            amount="250.75",
            payment_type="Online",
            category="Food-Online",
            specific_reason="Dinner biryani",
            notes="Paid via UPI",
        )
        assert len(row) == len(COLUMNS)
        assert row[0] == "TXN-20261021-0001"
        assert row[1] == "2026-10-21"
        assert row[2] == "2026-10-21 17:30:00"
        # Amount MUST be float numeric for Google Sheets calculations
        assert isinstance(row[3], float)
        assert row[3] == 250.75
        assert row[4] == "Online"
        assert row[5] == "Food-Online"
        assert row[6] == "Dinner biryani"
        assert row[7] == "Paid via UPI"

    def test_format_row_without_notes(self):
        row = format_transaction_row(
            transaction_id="TXN-20261021-0002",
            expense_date="2026-10-21",
            created_at="2026-10-21 17:30:00",
            amount=15,
            payment_type="Cash",
            category="Beverages",
            specific_reason="Chai",
            notes="",
        )
        assert row[7] == ""
        assert row[3] == 15.0


class TestSpreadsheetIdExtraction:
    """Test extracting spreadsheet ID from URL or raw ID."""

    def test_raw_id(self):
        raw_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        assert extract_spreadsheet_id(raw_id) == raw_id

    def test_full_google_sheets_url(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
        assert extract_spreadsheet_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"


class TestGoogleSheetsSaveFlow:
    """Test end-to-end saving flow with mocked gspread."""

    @patch("services.google_sheets.get_gspread_client")
    def test_save_expense_creates_sheet_if_missing(self, mock_get_client):
        import gspread.exceptions

        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        # Worksheet does not exist on first call, then gets created
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("Not found")
        mock_spreadsheet.add_worksheet.return_value = mock_worksheet
        mock_spreadsheet.title = "My Expense Tracker"
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        mock_worksheet.append_row.return_value = {"updates": {"updatedRows": 1}}

        creds = {"type": "service_account", "client_email": "test@example.com"}
        data = {
            "date": datetime.date(2026, 10, 21),
            "amount": 100.0,
            "payment_type": "Cash",
            "category": "Travelling",
            "specific_reason": "Metro fare",
            "notes": "Office commute",
        }

        result = save_expense_to_sheets(
            credentials_dict=creds,
            spreadsheet_id="test_sheet_id",
            expense_data=data,
        )

        assert result["success"] is True
        assert result["sheet_name"] == "October 2026"
        assert result["amount"] == 100.0

        # Verify add_worksheet was called with title="October 2026"
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="October 2026",
            rows=1000,
            cols=len(COLUMNS),
        )

        # Verify append_row was called twice: once for header, once for row
        assert mock_worksheet.append_row.call_count == 2
        # First call is headers
        first_call_args = mock_worksheet.append_row.call_args_list[0]
        assert first_call_args[0][0] == COLUMNS
        # Second call is expense data
        second_call_args = mock_worksheet.append_row.call_args_list[1]
        assert second_call_args[0][0][3] == 100.0
        assert second_call_args[0][0][5] == "Travelling"

    @patch("services.google_sheets.get_gspread_client")
    def test_save_expense_appends_to_existing_sheet(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_worksheet.row_values.return_value = COLUMNS  # Headers exist
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        mock_worksheet.append_row.return_value = {"updates": {"updatedRows": 1}}

        creds = {"type": "service_account", "client_email": "test@example.com"}
        data = {
            "date": datetime.date(2026, 11, 5),
            "amount": 450.0,
            "payment_type": "Online",
            "category": "Food-Offline",
            "specific_reason": "Lunch with team",
        }

        result = save_expense_to_sheets(
            credentials_dict=creds,
            spreadsheet_id="test_sheet_id",
            expense_data=data,
        )

        assert result["success"] is True
        assert result["sheet_name"] == "November 2026"
        # Only row append called, no add_worksheet
        mock_spreadsheet.add_worksheet.assert_not_called()
        assert mock_worksheet.append_row.call_count == 1
