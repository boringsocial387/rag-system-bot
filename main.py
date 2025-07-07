# main.py

import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from datetime import datetime

# Environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
TIMEZONE = os.environ.get("TIMEZONE", "UTC")

# Authenticate Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('g-drive-notifica-d6f73e166404.json', scope)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SHEET_ID)

# Sheet references
creator_ref_sheet = spreadsheet.worksheet('Creator Reference')
weekly_rag_sheet = spreadsheet.worksheet('Weekly RAG')
historical_log_sheet = spreadsheet.worksheet('Historical Log')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.document.file_id)
    file.download_to_drive('latest_infloww.xlsx')

    df = pd.read_excel('latest_infloww.xlsx', sheet_name='Creator Statistics')
    creator_map = {row[0]: row[1] for row in creator_ref_sheet.get_all_values()[1:] if row[0]}

    summary = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    week = datetime.now().strftime('%Y-%m-%d')

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
            if metric >= 7:
                rag = 'Green'
            elif metric >= 4:
                rag = 'Amber'
            else:
                rag = 'Red'
        elif creator_type.lower() == 'free':
            metric = total_rev / following if following > 0 else 0
            if metric > 3:
                rag = 'Green'
            elif metric >= 1.5:
                rag = 'Amber'
            else:
                rag = 'Red'
        else:
            continue

        weekly_rag_sheet.append_row([week, creator, creator_type, round(metric, 2), rag, now])
        historical_log_sheet.append_row([week, creator, creator_type, round(metric, 2), rag, now])
        summary.append(rag)

    green = summary.count('Green')
    amber = summary.count('Amber')
    red = summary.count('Red')
    msg = f"✅ Infloww RAG Update Completed:\n🟢 {green} Green | 🟠 {amber} Amber | 🔴 {red} Red\nCheck the Google Sheet for full details."

    await update.message.reply_text(msg)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.run_polling()
