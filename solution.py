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
            social_platform TEXT,
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
        name_addr = f"{data_dict.get('Complaint Name', '')}, {data_dict.get('Complaint Address', '')}".strip(', ')
        full_json = json.dumps(data_dict)
        c.execute('''
            INSERT INTO complaints (
                csr_no, ack_no, category, sub_category, social_platform,
                incident_date, incident_time, complaint_date, complaint_name_address, 
                complaint_phone, complaint_mail, suspect_phone, 
                suspect_social, total_loss, additional_info, full_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data_dict.get("CSR No"), data_dict.get("NCRP Acknowledgement No."),
            data_dict.get("Category"), data_dict.get("Sub Category"),
            data_dict.get("Social Media Platform"), data_dict.get("Incident Date"),
            data_dict.get("Incident Time"), data_dict.get("Complaint Date"),
            name_addr, data_dict.get("Complaint Phone No."),
            data_dict.get("Complaint Mail Id"), data_dict.get("Suspect phone No."),
            data_dict.get("Suspect social Media Id"), data_dict.get("Total Amount Loss"),
            data_dict.get("Additional details"), full_json
        ))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"Database Error: {e}")
        return None

def get_all_complaints():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, full_data_json FROM complaints ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        try:
            d = json.loads(row['full_data_json'])
            d['db_id'] = row['id']
            results.append(d)
        except: pass
    return results

init_db()

# --- UTILS ---
def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def find_all_dates(full_text):
    date_pattern = r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})\b"
    matches = re.findall(date_pattern, full_text)
    return matches

def find_date_smart(full_text, keywords, fallback_dates=None):
    date_pattern = r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})"
    for keyword in keywords:
        regex = re.compile(re.escape(keyword) + r".{0,5000}?" + date_pattern, re.IGNORECASE | re.DOTALL)
        match = regex.search(full_text)
        if match: return match.group(1)
    if fallback_dates and len(fallback_dates) > 0:
        return fallback_dates[0]
    return ""

def find_time_smart(full_text, keywords):
    time_pattern = r"(\d{1,2}:\d{2}(?::\d{2})?:?(?:\s?[APap][Mm])?)"
    for keyword in keywords:
        regex = re.compile(re.escape(keyword) + r".{0,5000}?" + time_pattern, re.IGNORECASE | re.DOTALL)
        match = regex.search(full_text)
        if match: return match.group(1).strip(":")
    match = re.search(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\s+(\d{1,2}:\d{2}(?::\d{2})?:?)", full_text)
    if match: return match.group(1).strip(":")
    return ""

def find_amount_smart(full_text):
    for pat in [r"Total Fraudulent Amount reported by complainant[:\s]*([\d,]+\.?\d*)", r"Total Amount Loss[:\s]*([\d,]+\.?\d*)"]:
        match = re.search(pat, full_text, re.IGNORECASE)
        if match: return match.group(1)
    if "Financial" in full_text and "Total" in full_text:
        matches = re.findall(r"(?:Rs\.?|INR)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", full_text)
        valid = [float(m.replace(',','')) for m in matches if 100 < float(m.replace(',','')) < 1000000000 and float(m.replace(',','')) not in [2024,2025,2026]]
        if valid: return str(max(valid))
    return ""

def find_value_after_keyword(full_text, keywords):
    for k in keywords:
        m = re.search(re.escape(k) + r"[:\-\s]+([^\n\r]+)", full_text, re.IGNORECASE)
        if m: return clean_text(m.group(1))
    return ""

# --- LAYOUT SEARCH (Column & Strip Logic) ---
def find_value_from_layout(layout_text, keywords):
    for k in keywords:
        pattern = re.compile(re.escape(k) + r"\s{2,}(.+)", re.IGNORECASE)
        match = pattern.search(layout_text)
        if match: return clean_text(match.group(1))
        pattern_loose = re.compile(re.escape(k) + r"[:\s]+([^\n\r]+)", re.IGNORECASE)
        match_loose = pattern_loose.search(layout_text)
        if match_loose: return clean_text(match_loose.group(1))
    return ""

def find_value_in_columns(pdf_page, label_text):
    try:
        words = pdf_page.extract_words()
        label_matches = [w for w in words if label_text.lower() in w['text'].lower()]
        if not label_matches: return ""
        label = label_matches[0]
        # Look to the right with wide tolerance
        same_line_words = [w['text'] for w in words if abs(w['top'] - label['top']) < 15 and w['x0'] > label['x1'] + 5]
        if same_line_words: return " ".join(same_line_words)
    except: return ""
    return ""

def find_platform_smart(layout_text, pages_list, suspect_id):
    val = find_value_from_layout(layout_text, ["Social Media Platform", "Platform", "Domain Name"])
    if val: return val
    if suspect_id:
        s = suspect_id.lower()
        if "instagram" in s: return "Instagram"
        if "facebook" in s: return "Facebook"
        if "youtube" in s: return "YouTube"
        if "whatsapp" in s: return "WhatsApp"
        if "telegram" in s: return "Telegram"
        if "x.com" in s or "twitter" in s: return "X (Twitter)"
    return ""

# --- REFINED SUSPECT ID LOGIC (Strict Filtering) ---
def extract_suspect_id_refined(pages_list, layout_text, complaint_email):
    # 1. Try Labels
    val = find_value_from_layout(layout_text, ["Username", "Suspect ID", "URL", "Profile URL"])
    if val and len(val) > 2 and val.lower() != "n/a" and val != complaint_email:
        return val

    # 2. Table Scanning
    blocklist_words = ["merchant", "paid", "amount", "order id", "reference", "assist", "glad to", "refund", "reversal", "transaction"]
    blocklist_emails = ["cybercell", "nodal", "help", "support", "care", "merchant", "info", "contact"]

    for page in pages_list:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                row_str = str(row).lower()
                if "evidence" in row_str or "bank" in row_str: continue 
                for cell in row:
                    if not cell: continue
                    cl = clean_text(cell)
                    cl_lower = cl.lower()

                    if len(cl) > 60: continue
                    if " " in cl and len(cl.split()) > 3: continue 
                    if any(bad in cl_lower for bad in blocklist_words): continue
                    
                    if ("http" in cl or "www." in cl or "@" in cl) and len(cl) > 3:
                        if cl != complaint_email and not any(bad in cl_lower for bad in blocklist_emails):
                             return cl
    return ""

def extract_additional_info_refined(full_text):
    start_pattern = r"(?:Complaint Additional Info|Brief Facts|Gist of Complaint)[:\-\s]+"
    end_pattern = r"(?:Platform|Suspect|Evidence|Fraudulent Transaction|Transaction Details|Action Taken|F\.I\.R|Court|$)"
    info_match = re.search(f"{start_pattern}(.*?)\s+{end_pattern}", full_text, re.DOTALL | re.IGNORECASE)
    if info_match:
        extracted = clean_text(info_match.group(1))
        if len(extracted) > 10: return extracted
    
    paragraphs = full_text.split('\n')
    longest_para = ""
    for p in paragraphs:
        clean_p = p.strip()
        if "National Cyber Crime" in clean_p or "Acknowledgement" in clean_p: continue
        if len(clean_p) > len(longest_para): longest_para = clean_p
    if len(longest_para) > 50: return longest_para
    return ""

def extract_ncrp_data(pdf_path):
    full_text = ""
    layout_text = "" 
    pages_list = []
    
    data = {"CSR No": str(random.randint(1000,9999)), "NCRP Acknowledgement No.": "", "Category":"", "Sub Category":"", "Social Media Platform":"", "Incident Date":"", "Incident Time":"", "Complaint Date":"", "Complaint Name":"", "Complaint Address":"", "Complaint Phone No.":"", "Complaint Mail Id":"", "Suspect phone No.":"", "Suspect social Media Id":"", "Total Amount Loss":"", "Additional details":""}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_list = pdf.pages
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
                layout_text += (page.extract_text(layout=True) or "") + "\n"
    except: pass

    all_dates = find_all_dates(full_text)
    
    # Ack No
    ack = find_value_from_layout(layout_text, ["Acknowledgement Number"])
    if not ack: 
        m = re.search(r"\b(\d{12,17})\b", full_text)
        if m: ack = m.group(1)
    data["NCRP Acknowledgement No."] = ack
    
    # Dates
    data["Incident Date"] = find_date_smart(full_text, ["Incident Date", "Date of Incident"], fallback_dates=all_dates)
    complaint_fallback = [all_dates[1]] if len(all_dates) > 1 else ([all_dates[0]] if all_dates else None)
    data["Complaint Date"] = find_date_smart(full_text, ["Complaint Date"], fallback_dates=complaint_fallback)
    data["Incident Time"] = find_time_smart(full_text, ["Incident Date", "Incident Time"])
    
    # --- CATEGORY / SUB CATEGORY (SEQUENTIAL LOGIC) ---
    # 1. Try Layout Mode (Best if aligned)
    data["Category"] = find_value_from_layout(layout_text, ["Category of complaint", "Category"])
    data["Sub Category"] = find_value_from_layout(layout_text, ["Sub Category of Complaint", "Sub Category"])
    
    # 2. Fallback: Determine Category from keywords
    if not data["Category"]: 
        data["Category"] = "Non Financial Fraud" if "Non Financial" in full_text else "Online Financial Fraud" if "Financial" in full_text else ""

    # 3. Fallback: Sequential Scan for Sub Category (THE FIX)
    # If Sub Category is still empty, find the Category Value and grab the NEXT line.
    if not data["Sub Category"] and data["Category"]:
        cat_val = data["Category"]
        # Find category value + newline + capture group
        # This handles the "Column Dump" format where values are listed sequentially
        seq_pattern = re.compile(re.escape(cat_val) + r"\s*\n\s*([^\n]+)", re.IGNORECASE)
        match = seq_pattern.search(full_text)
        if match:
            candidate = clean_text(match.group(1))
            # Validate it's not a boolean or date
            if len(candidate) > 3 and candidate.lower() not in ["yes", "no"] and not re.search(r"\d{4}", candidate):
                data["Sub Category"] = candidate

    # Personal Info
    data["Complaint Name"] = find_value_from_layout(layout_text, ["Name"]) or find_value_after_keyword(full_text, ["Name"])
    data["Complaint Phone No."] = find_value_from_layout(layout_text, ["Mobile"]) or find_value_after_keyword(full_text, ["Mobile"])
    data["Complaint Mail Id"] = find_value_from_layout(layout_text, ["Email"]) or find_value_after_keyword(full_text, ["Email"])
    
    # Address
    addr_parts = []
    for k in ["House No", "Street Name", "Colony", "District", "State"]:
        val = find_value_from_layout(layout_text, [k])
        if val: addr_parts.append(val)
    data["Complaint Address"] = ", ".join(addr_parts) if addr_parts else find_value_after_keyword(full_text, ["Address"])
    
    # Suspect Phone
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        row_str = str(row).lower()
                        if "bank" in row_str or "evidence" in row_str or "transaction" in row_str: continue 
                        for cell in row:
                            if not cell: continue
                            cl = clean_text(cell)
                            if re.match(r"^[6-9]\d{9}$", cl) and cl != data["Complaint Phone No."]: 
                                data["Suspect phone No."] = cl
    except: pass

    data["Suspect social Media Id"] = extract_suspect_id_refined(pages_list, layout_text, data["Complaint Mail Id"])
    data["Additional details"] = extract_additional_info_refined(full_text)
    data["Social Media Platform"] = find_platform_smart(layout_text, pages_list, data["Suspect social Media Id"])
    data["Total Amount Loss"] = find_amount_smart(full_text)
    
    return data

@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    if 'file' not in request.files: return jsonify({'status': 'error'})
    file = request.files['file']
    if file.filename == '': return jsonify({'status': 'error'})
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    try:
        data = extract_ncrp_data(file_path)
        new_id = save_to_sql(data)
        if new_id is None: return jsonify({'status': 'duplicate', 'message': f"ID {data['NCRP Acknowledgement No.']} exists"})
        data['db_id'] = new_id 
        return jsonify({'status': 'success', 'data': [data]})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get_database', methods=['GET'])
def get_database():
    db_data = get_all_complaints()
    return jsonify({'status': 'success', 'data': db_data})

@app.route('/delete_complaint', methods=['POST'])
def delete_complaint():
    try:
        data = request.get_json()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM complaints WHERE id=?", (data.get('id'),))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'status': 'error'})

if __name__ == '__main__':
    print("NCRP Server v19.0 (Sequential SubCat + Strict ID) Running...")
    app.run(debug=True, port=5000)
