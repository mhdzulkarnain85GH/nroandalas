import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from playwright.sync_api import sync_playwright

# Konfigurasi dari Environment Variables
SUPERSET_SQL_LAB_URL = os.getenv("SUPERSET_SQL_LAB_URL")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = "ASTRI_Data"  # Nama tab di Google Sheet kamu


def extract_csv_from_superset():
  """Ekstraksi CSV dari Superset menggunakan Playwright Headless."""
  print("[INFO] Memulai ekstraksi data dari Superset...")

  # Load session state dari environment secret
  with open("state.json", "w") as f:
    f.write(os.getenv("SESSION_STATE_JSON"))

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        storage_state="state.json", accept_downloads=True
    )
    page = context.new_page()

    page.goto(SUPERSET_SQL_LAB_URL)

    # Tunggu dan klik tombol Run
    print("[INFO] Menjalankan SQL query...")
    page.wait_for_selector("button:has-text('Run')")
    page.click("button:has-text('Run')")

    # Tunggu tombol Download to CSV dan unduh file
    download_button = page.wait_for_selector(
        "button:has-text('Download to CSV')"
    )

    with page.expect_download() as download_info:
      download_button.click()

    download = download_info.value
    csv_path = "latest_astri.csv"
    download.save_as(csv_path)

    browser.close()
    print("[SUCCESS] CSV Superset berhasil terunduh!")
    return csv_path


def update_google_sheets(csv_file_path):
  """Update tab Google Sheets dengan isi CSV terbaru."""
  print("[INFO] Memperbarui Google Sheets...")

  # Setup Google Sheets Credentials dari Secret JSON
  creds_json = json.loads(os.getenv("GCP_SERVICE_ACCOUNT_JSON"))
  scope = [
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/drive",
  ]
  creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
  client = gspread.authorize(creds)

  # Buka Spreadsheet & Worksheet
  spreadsheet = client.open_by_key(SPREADSHEET_ID)

  try:
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
  except gspread.exceptions.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(
        title=WORKSHEET_NAME, rows="1000", cols="30"
    )

  # Baca CSV dengan Pandas dan bersihkan nilai NaN/Null
  df = pd.read_csv(csv_file_path).fillna("")

  # Menimpa seluruh data di tab Google Sheet dengan data terbaru
  worksheet.clear()
  data_to_upload = [df.columns.values.tolist()] + df.values.tolist()
  worksheet.update("A1", data_to_upload)

  print(
      f"[SUCCESS] {len(df)} baris data ASTRI berhasil ter-sync ke Google"
      " Sheets!"
  )


if __name__ == "__main__":
  try:
    csv_file = extract_csv_from_superset()
    update_google_sheets(csv_file)
  except Exception as e:
    print(f"[ERROR] Sync gagal: {e}")
    exit(1)
