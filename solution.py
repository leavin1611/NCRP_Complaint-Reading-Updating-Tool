import os
import re
import sqlite3
import pdfplumber
import pandas as pd
import json
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
DB_FILE = 'ncrp_database.db'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- DATABASE SETUP ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            csr_no TEXT,
            ack_no TEXT UNIQUE,
            category TEXT,
            sub_category TEXT,
            incident_date TEXT,
            incident_time TEXT,
            complaint_date TEXT,
            complaint_name_address TEXT,
            complaint_phone TEXT,
            complaint_mail TEXT,
            suspect_phone TEXT,
            suspect_social TEXT,
            total_loss TEXT,
            additional_info TEXT,
            full_data_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_sql(data_dict):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # We store the combined Name and Detailed Address here
        name_addr = f"{data_dict.get('Complaint Name', '')}, {data_dict.get('Complaint Address', '')}".strip(', ')
        full_json = json.dumps(data_dict)

        c.execute('''
            INSERT INTO complaints (
                csr_no, ack_no, category, sub_category, 
                incident_date, incident_time, complaint_date, complaint_name_address, 
                complaint_phone, complaint_mail, suspect_phone, 
                suspect_social, total_loss, additional_info, full_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data_dict.get("CSR No"),
            data_dict.get("NCRP Acknowledgement No."),
            data_dict.get("Category"),
            data_dict.get("Sub Category"),
            data_dict.get("Incident Date"),
            data_dict.get("Incident Time"),
            data_dict.get("Complaint Date"),
            name_addr,
            data_dict.get("Complaint Phone No."),
            data_dict.get("Complaint Mail Id"),
            data_dict.get("Suspect phone No."),
            data_dict.get("Suspect social Media Id"),
            data_dict.get("Total Amount Loss"),
            data_dict.get("Additional details"),
            full_json
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Database Error: {e}")
        return False

def get_all_complaints():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT full_data_json FROM complaints ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [json.loads(row['full_data_json']) for row in rows]

init_db()

# --- SMART EXTRACTION LOGIC ---

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def find_date_smart(full_text, keywords):
    date_pattern = r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})"
    for keyword in keywords:
        regex = re.compile(re.escape(keyword) + r".{0,1500}?" + date_pattern, re.IGNORECASE | re.DOTALL)
        match = regex.search(full_text)
        if match: return match.group(1)
    return ""

def find_time_smart(full_text, keywords):
    time_pattern = r"(\d{1,2}:\d{2}(?::\d{2})?:?(?:\s?[APap][Mm])?)"
    for keyword in keywords:
        regex = re.compile(re.escape(keyword) + r".{0,2000}?" + time_pattern, re.IGNORECASE | re.DOTALL)
        match = regex.search(full_text)
        if match: return match.group(1).strip(":")
        
    combined_pattern = re.search(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\s+(\d{1,2}:\d{2}(?::\d{2})?:?)", full_text)
    if combined_pattern: return combined_pattern.group(1).strip(":")
    return ""

def find_amount_smart(full_text):
    strict_patterns = [
        r"Total Fraudulent Amount reported by complainant[:\s]*([\d,]+\.?\d*)",
        r"Total Amount Loss[:\s]*([\d,]+\.?\d*)",
        r"Loss Amount[:\s]*([\d,]+\.?\d*)",
    ]
    for pat in strict_patterns:
        match = re.search(pat, full_text, re.IGNORECASE)
        if match: return match.group(1)

    if "Total Fraudulent Amount" in full_text or "Total Amount" in full_text:
        start_idx = full_text.find("Total Fraudulent Amount")
        if start_idx == -1: start_idx = full_text.find("Total Amount")
        search_zone = full_text[start_idx : start_idx + 1000]
        matches = re.findall(r"(?:Rs\.?|INR)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", search_zone)
        
        valid_amounts = []
        for m in matches:
            raw_val = m.replace(',', '')
            try:
                val_float = float(raw_val)
                if val_float > 100 and val_float < 1000000000: 
                    valid_amounts.append((val_float, m))
            except:
                continue
        if valid_amounts:
            return max(valid_amounts, key=lambda x: x[0])[1]
    return ""

def find_additional_info_smart(full_text):
    pattern = re.compile(r"(?:Additional Info|Brief Facts|Gist of Complaint)[:\-\s]+(.*?)(?:Action Taken|Fraudulent Transaction|Debited Transaction|Complainant Details|$)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(full_text)
    candidate_text = clean_text(match.group(1)) if match else ""

    if not candidate_text or len(candidate_text) < 10:
        lines = full_text.split('\n')
        for line in lines:
            clean_line = line.strip()
            if len(clean_line) > 20 and clean_line.isupper() and "BANK" not in clean_line and "TABLE" not in clean_line:
                 return clean_line
    return candidate_text

def find_value_after_keyword(full_text, keywords):
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword) + r"[:\-\s]+([^\n\r]+)", re.IGNORECASE)
        match = pattern.search(full_text)
        if match:
            val = clean_text(match.group(1))
            if len(val) > 1 and val not in [":", "-", "."]:
                return val
    return ""

def extract_ncrp_data(pdf_path):
    full_text = ""
    data = {
        "CSR No": str(random.randint(1000, 9999)), 
        "NCRP Acknowledgement No.": "",
        "Category": "",
        "Sub Category": "",
        "Incident Date": "",
        "Incident Time": "",
        "Complaint Date": "",
        "Complaint Name": "",
        "Complaint Address": "",
        "Complaint Phone No.": "",
        "Complaint Mail Id": "",
        "Suspect phone No.": "",
        "Suspect social Media Id": "",
        "Total Amount Loss": "",
        "Additional details": ""
    }

    print(f"--- Processing: {os.path.basename(pdf_path)} ---")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: full_text += text + "\n"
            
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_str = str(row).lower()
                        if "bank" in row_str or "account" in row_str: continue 
                        for cell in row:
                            if cell:
                                cell_clean = clean_text(cell)
                                if re.match(r"^[6-9]\d{9}$", cell_clean):
                                    if cell_clean != data["Complaint Phone No."]:
                                        data["Suspect phone No."] = cell_clean
                                if "http" in cell_clean or "www." in cell_clean or ("@" in cell_clean and ".com" not in cell_clean):
                                    data["Suspect social Media Id"] = cell_clean
    except Exception as e:
        print(f"PDF Error: {e}")

    # --- METADATA EXTRACTION ---
    
    # 1. Standard Fields
    ack = find_value_after_keyword(full_text, ["Acknowledgement Number", "Acknowledgement No", "Ack No", "Complaint ID"])
    if not ack:
        ack_match = re.search(r"\b(3\d{12,15})\b", full_text)
        if ack_match: ack = ack_match.group(1)
    data["NCRP Acknowledgement No."] = ack

    data["Incident Date"] = find_date_smart(full_text, ["Incident Date", "Date of Incident"])
    data["Incident Time"] = find_time_smart(full_text, ["Incident Date", "Incident Time", "Time of Incident"])
    data["Complaint Date"] = find_date_smart(full_text, ["Complaint Date", "Date of Complaint"])
    
    data["Category"] = find_value_after_keyword(full_text, ["Category of complaint", "Category"])
    data["Sub Category"] = find_value_after_keyword(full_text, ["Sub Category of Complaint", "Sub Category"])

    data["Complaint Name"] = find_value_after_keyword(full_text, ["Complainant Name", "Name", "Victim Name"])
    data["Complaint Phone No."] = find_value_after_keyword(full_text, ["Mobile No", "Mobile", "Contact No"])
    data["Complaint Mail Id"] = find_value_after_keyword(full_text, ["Email", "Mail Id"])

    # 2. DETAILED ADDRESS EXTRACTION
    addr_parts = []
    
    house = find_value_after_keyword(full_text, ["House No", "House Number", "Door No", "Flat No"])
    street = find_value_after_keyword(full_text, ["Street Name", "Street", "Road", "Lane"])
    colony = find_value_after_keyword(full_text, ["Colony", "Locality", "Area", "Village", "Town"])
    tehsil = find_value_after_keyword(full_text, ["Tehsil", "Taluka"])
    dist = find_value_after_keyword(full_text, ["District", "City"])
    state = find_value_after_keyword(full_text, ["State"])
    pincode = find_value_after_keyword(full_text, ["Pincode", "Pin Code", "Pin"])

    if house: addr_parts.append(house)
    if street: addr_parts.append(street)
    if colony: addr_parts.append(colony)
    if tehsil: addr_parts.append(tehsil)
    if dist: addr_parts.append(dist)
    if state: addr_parts.append(state)
    if pincode: addr_parts.append(f"- {pincode}")

    if addr_parts:
        data["Complaint Address"] = ", ".join(addr_parts).replace(", -", " -")
    else:
        # Fallback to generic Block search
        addr = find_value_after_keyword(full_text, ["Address", "Correspondence Address"])
        data["Complaint Address"] = addr

    data["Total Amount Loss"] = find_amount_smart(full_text)
    data["Additional details"] = find_additional_info_smart(full_text)

    return data

# --- ROUTES ---

@app.route('/get_database', methods=['GET'])
def get_database():
    db_data = get_all_complaints()
    return jsonify({'status': 'success', 'data': db_data})

@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    if 'file' not in request.files: return jsonify({'status': 'error', 'message': 'No file'})
    file = request.files['file']
    if file.filename == '': return jsonify({'status': 'error', 'message': 'No selected file'})

    if file:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        try:
            extracted_data = extract_ncrp_data(file_path)
            success = save_to_sql(extracted_data)
            
            if not success:
                ack = extracted_data.get("NCRP Acknowledgement No.")
                return jsonify({'status': 'duplicate', 'message': f'ID {ack} already exists.'})

            return jsonify({'status': 'success', 'data': [extracted_data]})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    print("NCRP Server v6.0 (Detailed Address) Running...")
    app.run(debug=True, port=5000)
