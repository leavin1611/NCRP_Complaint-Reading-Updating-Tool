from fpdf import FPDF

class NCRPReport(FPDF):
    def header(self):
        # bold font 14
        self.set_font('Arial', 'B', 14)
        # Title
        self.cell(0, 10, 'National Cyber Crime Reporting Portal (NCRP)', 0, 1, 'C')
        self.ln(5)

    def section_header(self, title):
        # Arial 10 Bold, No background color, Underlined for distinction
        self.set_font('Arial', 'BU', 10)
        self.cell(0, 8, title, 0, 1, 'L')
        self.ln(1)

    def field(self, label, value):
        # Field Label (Bold)
        self.set_font('Arial', 'B', 9)
        self.cell(60, 5, label, 0, 0)
        # Field Value (Normal)
        self.set_font('Arial', '', 9)
        self.multi_cell(0, 5, str(value)) # Use multi_cell to handle long text wrapping

    def add_table(self, header, data, col_widths):
        # Table Header - Bold, Black text, White background
        self.set_font('Arial', 'B', 8)
        for i, h in enumerate(header):
            self.cell(col_widths[i], 8, h, 1, 0, 'C')
        self.ln()
        
        # Table Data - Normal, Black text
        self.set_font('Arial', '', 7)
        for row in data:
            # Save current Y position
            y_before = self.get_y()
            max_height = 0
            
            # Calculate max height of the row (for text wrapping)
            for i, datum in enumerate(row):
                # Calculate number of lines this cell will take
                lines = self.get_string_width(str(datum)) / col_widths[i]
                height = 6 * (int(lines) + 1)
                if height > max_height:
                    max_height = height
            
            # Print cells
            for i, datum in enumerate(row):
                x_curr = self.get_x()
                y_curr = self.get_y()
                self.multi_cell(col_widths[i], 6, str(datum), 1, 'C')
                # Move to next cell position
                self.set_xy(x_curr + col_widths[i], y_curr)
            
            # Move to next line based on max height
            self.ln(max_height) # Simple line break approximation
            # Note: For perfect complex grid alignment in FPDF with multi-line, 
            # we force a standard height here for simplicity to avoid breaking layouts:
            self.set_xy(10, y_before + 8) 
        self.ln(5)

# Create PDF object
pdf = NCRPReport()
pdf.set_auto_page_break(auto=True, margin=15)

# --- COMPLAINT 1 ---
pdf.add_page()

# Header Details
pdf.field('Acknowledgement Number:', '3998123456781')
pdf.field('Category of complaint:', 'Online Financial Fraud')
pdf.field('Sub Category of Complaint:', 'Internet Banking Related Fraud')
pdf.field('Additional Information:', 'N/A')
pdf.field('UserId:', '88123912312')
pdf.field('Incident Date/Time:', '15/05/2025 10:30 AM')
pdf.field('Complaint Date:', '16/05/2025')
pdf.ln(3)

# Complainant Section
pdf.section_header('Complainant Details')
pdf.field('Name:', 'Rajesh Kumar')
pdf.field('Mobile:', '9876543210')
pdf.field('Email:', 'rajesh.dummy@email.com')
pdf.field('Address:', 'Flat 101, Sunshine Apts')
pdf.field('District/State:', 'Pune, Maharashtra')
pdf.ln(3)

# Transaction Section
pdf.section_header('Fraudulent Transaction Details')
pdf.field('Total Fraudulent Amount:', '250,000.00')
pdf.ln(2)

header_trans = ['S No.', 'Bank/Merchant', 'Account No.', 'Trans Id', 'Amount', 'Date']
data_trans = [
    ['1', 'HDFC Bank', 'XXXXXX1234', '772901234567', '100000', '15/05/2025'],
    ['2', 'HDFC Bank', 'XXXXXX1234', '772901234568', '150000', '15/05/2025'],
]
# Widths adjusted to fit A4 width (~190mm usable)
col_widths_trans = [12, 35, 35, 40, 30, 30]

# Custom table function for simple 1-line rows
pdf.set_font('Arial', 'B', 8)
for i, h in enumerate(header_trans):
    pdf.cell(col_widths_trans[i], 8, h, 1, 0, 'C')
pdf.ln()
pdf.set_font('Arial', '', 8)
for row in data_trans:
    for i, d in enumerate(row):
        pdf.cell(col_widths_trans[i], 8, str(d), 1, 0, 'C')
    pdf.ln()
pdf.ln(5)

# Action Taken Section
pdf.section_header('Action Taken by bank')
header_action = ['S No.', 'Action Taken', 'Bank', 'Account No', 'Amount', 'Remarks']
data_action = [
    ['1', 'Money Transfer to', 'ICICI Bank', '001234567890', '100000', '-'],
    ['2', 'Txn on hold', 'SBI', '009876543211', '150000', 'Frozen'],
]
col_widths_action = [12, 30, 30, 40, 30, 40]

pdf.set_font('Arial', 'B', 8)
for i, h in enumerate(header_action):
    pdf.cell(col_widths_action[i], 8, h, 1, 0, 'C')
pdf.ln()
pdf.set_font('Arial', '', 8)
for row in data_action:
    for i, d in enumerate(row):
        pdf.cell(col_widths_action[i], 8, str(d), 1, 0, 'C')
    pdf.ln()


# --- COMPLAINT 2 ---
pdf.add_page()

# Header Details
pdf.field('Acknowledgement Number:', '4112345678999')
pdf.field('Category of complaint:', 'Online Financial Fraud')
pdf.field('Sub Category of Complaint:', 'UPI Fraud')
pdf.field('Additional Information:', 'Suspect used OLX QR Scam')
pdf.field('UserId:', '998877665544')
pdf.field('Incident Date/Time:', '22/08/2025 02:15 PM')
pdf.field('Complaint Date:', '22/08/2025')
pdf.ln(3)

# Complainant Section
pdf.section_header('Complainant Details')
pdf.field('Name:', 'Priya Sharma')
pdf.field('Mobile:', '9123456789')
pdf.field('Email:', 'priya.test@email.com')
pdf.field('Address:', '12th Cross, Indiranagar')
pdf.field('District/State:', 'Bangalore Urban, Karnataka')
pdf.ln(3)

# Transaction Section
pdf.section_header('Fraudulent Transaction Details')
pdf.field('Total Fraudulent Amount:', '45,000.00')
pdf.ln(2)

data_trans_2 = [
    ['1', 'PhonePe', '9123456789@ybl', 'T230822141512', '20000', '22/08/2025'],
    ['2', 'PhonePe', '9123456789@ybl', 'T230822141655', '25000', '22/08/2025'],
]

pdf.set_font('Arial', 'B', 8)
for i, h in enumerate(header_trans):
    pdf.cell(col_widths_trans[i], 8, h, 1, 0, 'C')
pdf.ln()
pdf.set_font('Arial', '', 8)
for row in data_trans_2:
    for i, d in enumerate(row):
        pdf.cell(col_widths_trans[i], 8, str(d), 1, 0, 'C')
    pdf.ln()
pdf.ln(5)

# Action Taken Section
pdf.section_header('Action Taken by bank')
data_action_2 = [
    ['1', 'Money Transfer to', 'Paytm', '919876543210', '20000', 'Wallet'],
    ['2', 'Money Transfer to', 'Axis Bank', '92301120099999', '25000', '-'],
]

pdf.set_font('Arial', 'B', 8)
for i, h in enumerate(header_action):
    pdf.cell(col_widths_action[i], 8, h, 1, 0, 'C')
pdf.ln()
pdf.set_font('Arial', '', 8)
for row in data_action_2:
    for i, d in enumerate(row):
        pdf.cell(col_widths_action[i], 8, str(d), 1, 0, 'C')
    pdf.ln()

# Output
pdf.output("NCRP_Dummy_Complaints_BW.pdf")
print("PDF generated successfully: NCRP_Dummy_Complaints_BW.pdf")
