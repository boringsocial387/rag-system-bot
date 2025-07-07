from fastapi import FastAPI, Request
import requests
import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('g-drive-notifica-d6f73e166404.json', scope)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SHEET_ID)
creator_ref_sheet = spreadsheet.worksheet('Creator Reference')
weekly_rag_sheet = spreadsheet.worksheet('Weekly RAG')
historical_log_sheet = spreadsheet.worksheet('Historical Log')

app = FastAPI()

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    if "message" in data and "document" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        file_id = data["message"]["document"]["file_id"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)
        with open("latest_infloww.xlsx", "wb") as f:
            f.write(response.content)

        df = pd.read_excel("latest_infloww.xlsx", sheet_name='Creator Statistics')
        creator_map = {row[0]: row[1] for row in creator_ref_sheet.get_all_values()[1:] if row[0]}
        summary = []
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        week = datetime.utcnow().strftime('%Y-%m-%d')
        weekly_rag_sheet.clear()
        weekly_rag_sheet.append_row(['Week', 'Creator Name', 'Type', 'Metric', 'RAG Status', 'Timestamp'])
        for _, row in df.iterrows():
            creator = row['Creator']
            if creator not in creator_map:
                continue
            creator_type = creator_map[creator]
            sub_rev = float(str(row['Subscription Net']).replace('$','').replace(',',''))
            tips_rev = float(str(row['Tips Net']).replace('$','').replace(',',''))
            msg_rev = float(str(row['Message Net']).replace('$','').replace(',',''))
            following = float(row['Following']) if row['Following'] else 0
            total_rev = float(str(row['Total earnings Net']).replace('$','').replace(',',''))
            if creator_type.lower() == 'paid':
                chat_rev = tips_rev + msg_rev
                metric = chat_rev / sub_rev if sub_rev > 0 else 0
                rag = 'Green' if metric >= 7 else 'Amber' if metric >= 4 else 'Red'
            else:
                metric = total_rev / following if following > 0 else 0
                rag = 'Green' if metric > 3 else 'Amber' if metric >= 1.5 else 'Red'
            weekly_rag_sheet.append_row([week, creator, creator_type, round(metric,2), rag, now])
            historical_log_sheet.append_row([week, creator, creator_type, round(metric,2), rag, now])
            summary.append(rag)
        green = summary.count('Green')
        amber = summary.count('Amber')
        red = summary.count('Red')
        send_message(chat_id, f"✅ Infloww RAG Update:\n🟢 {green} Green | 🟠 {amber} Amber | 🔴 {red} Red\nCheck Google Sheet for details.")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
