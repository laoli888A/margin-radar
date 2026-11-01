import akshare as ak
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import os

# 从云端的环境变量中读取你的飞书地址
WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

def get_margin_data():
    try:
        # 【核心替换】：改用新浪财经接口，海外服务器不会被拦截
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()
        
        # 提取日期和融资余额，并统一格式
        df_sh = df_sh[['日期', '融资余额']].copy()
        df_sz = df_sz[['日期', '融资余额']].copy()
        
        df = pd.concat([df_sh, df_sz]).groupby('日期').sum().reset_index()
        df = df.sort_values('日期').reset_index(drop=True)
        
        # 单位统一换算成亿元
        if df['融资余额'].max() > 1e8:
            df['融资余额'] = df['融资余额'] / 1e8
            
        # 计算每日变动
        df['变动'] = df['融资余额'].diff()
        return df
    except Exception as e:
        print(f"抓取失败: {e}")
        return None

def analyze_and_push(df):
    if df is None or len(df) < 20:
        print("数据不足或抓取失败，退出程序。")
        return

    # 计算 20 日均值和标准差
    recent_20 = df.tail(20)
    mean = recent_20['变动'].mean()
    std = recent_20['变动'].std()
    upper = mean + 2 * std
    lower = mean - 2 * std
    
    latest = df.iloc[-1]
    date_str = str(latest['日期'])
    balance = latest['融资余额']
    change = latest['变动']
    
    if change > upper:
        signal = "🔥 **情绪过热**：单日流入突破2倍标准差，警惕追高。"
    elif change < lower:
        signal = "⚠️ **恐慌极值**：单日流出突破2倍标准差，情绪极度低迷。"
    else:
        signal = "✅ **正常波动**：资金进出在合理范围内。"

    # 组装飞书卡片
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "📊 主力资金极值雷达"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**日期**：{date_str}\n**两融余额**：{balance:.2f} 亿元\n**较前日变动**：{change:+.2f} 亿元\n**信号**：{signal}"}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "本内容仅为盘面数据监控，不构成任何投资建议。"}]}
            ]
        }
    }

    # 推送到飞书
    resp = requests.post(WEBHOOK_URL, json=card)
    print(f"状态码: {resp.status_code}")
    print("推送完成")

if __name__ == "__main__":
    df = get_margin_data()
    analyze_and_push(df)
