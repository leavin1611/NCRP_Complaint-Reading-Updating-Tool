# NCRP Automation Tool

A local offline tool to extract data from NCRP (National Cyber Crime Reporting Portal) PDF complaints, store them in a database, and generate automated Request Letters for banks and social media platforms.

## Features
* **Bulk Upload:** Upload multiple PDF complaints at once.
* **Smart Extraction:** Automatically extracts Ack No, CSR No, Suspect Details, and Amounts.
* **Search & Filter:** Search by CSR/Ack Number and filter by Solved/Unsolved status.
* **Request Letter Generator:** One-click generation of formal letters to Banks or Social Media platforms.
* **Offline Database:** Stores all data locally in a SQLite database.
* **Download As Excel:** You can Download the complaints as a excel sheet.

## How to Run (No Prior Technical Knowledge Required)

1.  Download this repository as a ZIP file and extract it.
2.  Double-click **`start_app.bat`**.
3.  Wait for the setup (first run takes a minute to download portable Python).
4.  The tool will open in your browser automatically.

*Note: Requires an internet connection only on the very first run to download dependencies.*
