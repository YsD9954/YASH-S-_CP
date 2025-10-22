# CardIQ — Credit Card Statement Parser

## Overview
CardIQ is a locally hosted web application developed as part of an engineering project to automate the extraction of essential financial details from credit card statements. The system intelligently identifies and displays information such as the card type, billing cycle, payment due date, and total balance due.

The backend is built using FastAPI (Python) for efficient parsing and data processing, while the frontend is developed with React.js to provide a clean, user-friendly interface. The entire solution runs locally, ensuring complete data privacy and eliminating dependence on external servers.

This project demonstrates the integration of machine learning–ready text extraction techniques, API handling, and modern frontend design principles — reflecting practical application of software development and data processing skills acquired during engineering studies. 

## Extracted Fields
- **Card Type** (Platinum, Gold, Regalia, etc.)  
- **Last 4 Digits of Card**  
- **Billing Cycle** (start and end dates)  
- **Payment Due Date**  
- **Total Balance Due**  

## Project Structure

CardIQ/
├─ backend/
│ ├─ app.py # FastAPI backend
│ ├─ extractor.py # Parser logic
│ ├─ banks.yaml # Bank identifiers (optional if need can add)
│ └─ requirements.txt # Python dependencies
├─ frontend/
│ ├─ src/
│ │ ├─ App.js # React frontend
│ │ └─ styles.css # Styling
│ ├─ package.json
│ └─ package-lock.json
├─ sample_statements/
│ └─ Axis_Bank_statement.pdf
| └─ HDFC_Bank_statement.pdf
| └─ ICICI_Bank_statement.pdf
| └─ Kotak_Mahindra_statement.pdf
| └─ SBI_Card_statement.pdf
└─ README.md

## Setup & Usage

### 1. Backend
1. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux / macOS
   source venv/bin/activate
Install dependencies:
pip install -r requirements.txt

Run the backend server:
uvicorn app:app --reload
Backend runs at: http://127.0.0.1:8000/

2. Frontend
Install dependencies:
npm install

Start the React app:
npm start
Open the app in your browser: http://localhost:3000

3. Usage
Open the frontend in your browser.
Upload a PDF credit card statement.
Click Upload & Parse.

View extracted fields:
Card Type
Last 4 Digits
Billing Cycle
Payment Due Date
Total Balance