import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp"])
    if isinstance(creds_dict.get("private_key"), str):
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def update_google_sheet(data_list):
    client = get_gspread_client()
    sheet = client.open("卡牌管理").sheet1
    df = pd.DataFrame(data_list).fillna('')
    sheet.clear()
    sheet.append_row(df.columns.values.tolist())
    sheet.append_rows(df.values.tolist())

def load_google_sheet():
    try:
        client = get_gspread_client()
        sheet = client.open("卡牌管理").sheet1
        return sheet.get_all_records()
    except:
        return []
