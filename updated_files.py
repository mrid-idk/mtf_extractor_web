import os
import csv
import requests
from datetime import datetime

BASE_URL = "https://raw.githubusercontent.com/mrid-idk/mtf_extractor_web/main/data/extracted"
EXISTING_FILE = 'mtf_data.csv'

# Add your GitHub token here
GITHUB_TOKEN = "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"

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

def get_github_directory_contents(url):
    api_url = url.replace('https://raw.githubusercontent.com/', 'https://api.github.com/repos/').replace('/main/', '/contents/')
    try:
        response = requests.get(api_url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch directory contents: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error fetching directory: {e}")
    return []

def read_csv_from_github(file_url):
    try:
        response = requests.get(file_url)
        if response.status_code == 200:
            return response.text.splitlines()
        else:
            print(f"Failed to fetch file {file_url}: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error reading file from {file_url}: {e}")
    return []

def parse_date_from_filename(filename):
    try:
        date_str = filename.split("_")[-1].replace(".csv", "")
        if len(date_str) == 8 and date_str.isdigit():
            date_obj = datetime.strptime(date_str, "%d%m%Y")
            return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing date from {filename}: {e}")
    return ""

def clean_numeric_value(value_str):
    if not value_str or str(value_str).strip() in ('', '-'):
        return None
    try:
        cleaned = str(value_str).replace(",", "").strip()
        value_in_lakhs = float(cleaned)
        return round(value_in_lakhs / 100, 2)
    except (ValueError, TypeError):
        return None

def process_csv_content(csv_lines, formatted_date):
    standard_metrics = {
        'beginning': 'Scripwise Total Outstanding on the beginning of the day',
        'fresh': 'Fresh Exposure taken during the day',
        'liquidated': 'Exposure liquidated during the day',
        'end': 'Net scripwise outstanding at the end of the day',
    }

    try:
        reader = [line.split(',') for line in csv_lines]
        if len(reader) < 8:
            return None

        table_locations = []
        for row_idx, row in enumerate(reader):
            for col_idx, cell in enumerate(row):
                cell_lower = cell.lower().strip()
                if "particulars" in cell_lower:
                    amount_col = next((amt_col_idx for amt_col_idx, amt_cell in enumerate(row) if any(term in amt_cell.lower().strip() for term in ["rs.", "lakhs", "amount", "value"])), -1)
                    if amount_col >= 0:
                        table_locations.append({'row': row_idx, 'particulars_col': col_idx, 'amount_col': amount_col})

        if not table_locations:
            return None

        found_metrics = {}

        for table_info in table_locations:
            table_start_row = table_info['row']
            particulars_col = table_info['particulars_col']
            amount_col = table_info['amount_col']

            search_range = min(50, len(reader) - table_start_row - 1)

            for offset in range(1, search_range):
                row_idx = table_start_row + offset
                if row_idx >= len(reader):
                    break

                row = reader[row_idx]
                if len(row) <= max(particulars_col, amount_col):
                    continue

                particular = row[particulars_col].strip()
                amount_str = row[amount_col].strip()

                if not particular or not amount_str:
                    continue

                particular_lower = particular.lower()

                standard_metric = (
                    next((value for key, value in standard_metrics.items() if key in particular_lower), None)
                )

                if standard_metric and standard_metric not in found_metrics:
                    amount = clean_numeric_value(amount_str)
                    if amount is not None and amount > 0:
                        found_metrics[standard_metric] = amount
                        if len(found_metrics) >= 4:
                            break

            if len(found_metrics) >= 4:
                break

        if found_metrics:
            row_data = [formatted_date]
            metric_order = [
                'Scripwise Total Outstanding on the beginning of the day',
                'Fresh Exposure taken during the day', 
                'Exposure liquidated during the day',
                'Net scripwise outstanding at the end of the day'
            ]
            for metric in metric_order:
                row_data.append(found_metrics.get(metric, ''))
            return row_data
    except Exception as e:
        print(f"Error processing CSV content: {e}")
    return None

def load_existing_dates(filepath):
    existing_dates = set()
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row and row[0]:
                    existing_dates.add(row[0])
    return existing_dates

def load_existing_filenames(filepath):
    existing_files = set()
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row and row[0]:
                    try:
                        date_part = datetime.strptime(row[0], "%Y-%m-%d").strftime("%d%m%Y")
                        existing_files.add(f"mrg_trading_{date_part}.csv")
                    except:
                        continue
    return existing_files

def generate_csv_for_github_pages():
    print("🚀 Generating CSV from GitHub repository data")
    print("=" * 50)

    existing_dates = load_existing_dates(EXISTING_FILE)
    existing_files = load_existing_filenames(EXISTING_FILE)
    all_data = []

    years_data = get_github_directory_contents(BASE_URL)
    for year_item in sorted(years_data, key=lambda x: x['name']):
        if year_item['type'] != 'dir':
            continue

        year_url = f"{BASE_URL}/{year_item['name']}"
        months_data = get_github_directory_contents(year_url)

        for month_item in sorted(months_data, key=lambda x: x['name']):
            if month_item['type'] != 'dir':
                continue

            month_url = f"{year_url}/{month_item['name']}"
            files_data = get_github_directory_contents(month_url)

            for file_item in files_data:
                if file_item['type'] == 'file' and file_item['name'].startswith("mrg_trading_") and file_item['name'].endswith(".csv"):
                    filename = file_item['name']
                    file_url = file_item['download_url']
                    formatted_date = parse_date_from_filename(filename)

                    if not formatted_date or formatted_date in existing_dates or filename in existing_files:
                        continue

                    print(f"📊 Processing {filename}")

                    csv_content = read_csv_from_github(file_url)
                    if csv_content:
                        row_data = process_csv_content(csv_content, formatted_date)
                        if row_data:
                            all_data.append(row_data)
                            print(f"✓ Extracted data for {formatted_date}")

    # Sort new data
    all_data.sort(key=lambda x: datetime.strptime(x[0], '%Y-%m-%d'))

    if all_data:
        file_exists = os.path.exists(EXISTING_FILE)
        with open(EXISTING_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow([
                    "Date", 
                    "Scripwise Total Outstanding on the beginning of the day",
                    "Fresh Exposure taken during the day", 
                    "Exposure liquidated during the day",
                    "Net scripwise outstanding at the end of the day"
                ])
            writer.writerows(all_data)

    print(f"\n🎉 CSV updated: {EXISTING_FILE}")
    print(f"➕ New rows added: {len(all_data)}")
    print(f"📋 Use this in Google Sheets:\n=IMPORTDATA(\"https://yourusername.github.io/mtf_data.csv\")")
    return EXISTING_FILE

if __name__ == "__main__":
    try:
        generate_csv_for_github_pages()
    except KeyboardInterrupt:
        print("\n⚠ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
