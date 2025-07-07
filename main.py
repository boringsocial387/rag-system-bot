```python
from fastapi import FastAPI, Request
import uvicorn
import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, Bot
from telegram.ext import Dispatcher, MessageHandler, filters, Application
from datetime import datetime

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('g-drive-notifica-d6f73e166404.json', scope)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SHEET_ID)
creator_ref_sheet = spreadsheet.worksheet('Creator Reference')
weekly_rag_sheet = spreadsheet.worksheet('Weekly RAG')
historical_log_sheet = spreadsheet.worksheet('Historical Log')

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot=bot)

async def handle_document(update: Update, context):
    file = await context.bot.get_file(update.message.document.file_id)
    file.download('latest_infloww.xlsx')
    df = pd.read_excel('latest_infloww.xlsx', sheet_name='Creator Statistics')
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
    await update.message.reply_text(f"✅ Infloww RAG Update:\n🟢 {green} Green | 🟠 {amber} Amber | 🔴 {red} Red\nCheck Google Sheet for details.")

dispatcher.add_handler(MessageHandler(filters.Document.ALL, handle_document))

@app.post("/")
async def process_webhook(req: Request):
    json_update = await req.json()
    update = Update.de_json(json_update, bot)
    await dispatcher.process_update(update)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```
