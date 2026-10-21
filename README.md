# Expense Tracker

A lightweight, clean, and reliable single-page web application built with **Python**, **Streamlit**, and **Google Sheets** for fast daily expense recording.

Expenses are saved directly into your Google Spreadsheet, automatically organized into **month-wise worksheet tabs** (e.g., `October 2026`, `November 2026`).

---

## 🎯 Features

- **Pure Recording Focus:** No dashboards, charts, summaries, or reports cluttering the UI. All data analysis is done directly in Google Sheets.
- **Automatic Monthly Tabs:** Determines the monthly tab from the expense date (e.g., `October 2026`) and automatically creates the tab with standard headers if it doesn't already exist.
- **Consistent Data Structure:** Standardized 8-column format with dates as `YYYY-MM-DD` and amounts as numeric values so formulas (`=SUM`, `=AVERAGE`), filters, and pivot tables work seamlessly.
- **Fast & Mobile-Friendly:** Designed with touch targets, responsive layout, and quick entry for both desktop and mobile browsers.
- **Strict Validation:** Rejects negative or zero amounts, enforces standard categories, and requires meaningful explanations for the `Others` category.
- **Reliable & Resilient:** Generates unique transaction IDs, confirms Google Sheets API persistence before displaying success, and preserves form inputs if an error occurs.
- **Secure Credentials:** Service account credentials and spreadsheet ID are kept strictly out of source code using Streamlit secrets (`secrets.toml`).

---

## 📁 Project Structure

```
expense-tracker/
├── app.py                      # Main Streamlit web application
├── requirements.txt            # Python dependencies
├── README.md                   # Setup guide and documentation
├── .gitignore                  # Git ignore rules (secrets, venv, keys)
├── .streamlit/
│   └── secrets.toml.example    # Configuration template for secrets
├── services/
│   ├── __init__.py
│   └── google_sheets.py        # Google Sheets API & validation logic
└── tests/
    ├── __init__.py
    └── test_expense.py         # Unit tests (validation, formatting, mocks)
```

---

## 📋 Data Schema

Every monthly worksheet tab uses the following 8 columns in exact order:

| # | Column Name | Type | Example |
|---|---|---|---|
| 1 | `Transaction ID` | Text | `TXN-20261021173000-8F3A1C` |
| 2 | `Transaction Date` | Date (`YYYY-MM-DD`) | `2026-10-21` |
| 3 | `Created At` | Timestamp (`YYYY-MM-DD HH:MM:SS`) | `2026-10-21 17:30:15` |
| 4 | `Amount` | Numeric (₹) | `250.50` |
| 5 | `Payment Type` | Text (`Cash` / `Online`) | `Online` |
| 6 | `Category` | Text | `Food-Online` |
| 7 | `Specific Reason` | Text | `Swiggy dinner order` |
| 8 | `Notes` | Text (Optional) | `Order #12345` |

### Allowed Categories (Fixed 5):
1. `Beverages`
2. `Food-Online`
3. `Food-Offline`
4. `Travelling`
5. `Others` *(requires a meaningful explanation)*

### Allowed Payment Types (Fixed 2):
1. `Cash`
2. `Online`

---

## 🚀 Setup & Installation

### Step 1: Clone or Navigate to the Workspace

```bash
cd /Users/chiragdua/expense_tracker
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Google Cloud & Google Sheets Configuration

To allow the application to read and write to your Google Spreadsheet, set up a Google Cloud Service Account:

### 1. Enable Google APIs
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `Expense-Tracker`) or select an existing one.
3. In the sidebar, navigate to **APIs & Services > Library**.
4. Search for and **Enable** both:
   - **Google Sheets API**
   - **Google Drive API**

### 2. Create a Service Account & Download Credentials
1. In Google Cloud Console, navigate to **IAM & Admin > Service Accounts**.
2. Click **+ Create Service Account**.
3. Name it (e.g., `expense-tracker-service`) and click **Create and Continue**.
4. You can skip the optional role assignments and click **Done**.
5. In the Service Accounts list, click on the newly created service account.
6. Open the **Keys** tab, click **Add Key > Create new key**.
7. Choose **JSON** format and click **Create**. The key file will download to your computer.

### 3. Create & Share Your Google Spreadsheet
1. Go to [Google Sheets](https://sheets.google.com) and create a **Blank spreadsheet** (e.g., named `My Expenses 2026`).
2. Copy the **Spreadsheet ID** from the browser URL:
   ```
   https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                      SPREADSHEET ID
   ```
3. Click the **Share** button in the top-right corner of the spreadsheet.
4. Paste the `client_email` address found in your downloaded service account JSON (e.g., `expense-tracker-service@your-project.iam.gserviceaccount.com`).
5. Select the role as **Editor** and uncheck "Notify people", then click **Share**.

### 4. Configure Streamlit Secrets

1. In the project root, copy the template:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Open `.streamlit/secrets.toml` in your editor.
3. Fill in your `spreadsheet_id` and paste the fields from your downloaded JSON key:

```toml
spreadsheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

[gcp_service_account]
type = "service_account"
project_id = "your-gcp-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-gcp-project-id.iam.gserviceaccount.com"
client_id = "123456789012345678901"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project-id.iam.gserviceaccount.com"
```

> **Note:** The `.gitignore` file is pre-configured to ensure `.streamlit/secrets.toml` and any `*.json` key files are never committed to Git.

---

## ▶️ Running the Application

Launch the Streamlit app:

```bash
streamlit run app.py
```

The application will open in your default browser at:
`http://localhost:8501`

---

## 🧪 Running Unit Tests

The test suite validates:
- Form field input validations (amount > 0, category matching, payment types)
- Meaningful reason rules for the `Others` category
- Date-to-worksheet name calculation (e.g., `October 2026`)
- Column ordering and numeric formatting
- Google Sheets tab creation and row append logic with mocks

Run the tests using `pytest`:

```bash
python3 -m pytest tests/ -v
```

---

## 🛠️ Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| **"⚠️ Google Sheets Setup Required"** | Missing `.streamlit/secrets.toml` | Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter your credentials. |
| **"Permission denied (403)"** | Service account does not have access | Share the Google Spreadsheet with your service account's `client_email` as **Editor**. |
| **"Spreadsheet not found"** | Incorrect Spreadsheet ID | Check the ID extracted from `https://docs.google.com/spreadsheets/d/<ID>/edit`. |
| **"Failed to authenticate"** | Invalid Private Key | Ensure `private_key` includes the `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` lines. If newlines are escaped (`\n`), the app automatically handles them. |
