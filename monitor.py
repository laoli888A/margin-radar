import akshare as ak
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import os

# 获取飞书地址
WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

def get_margin_and_volume_data():
    try:
        # 1. 抓取沪深两融数据（新浪接口）
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()
        
        # 提取日期、融资余额、融资买入额
        df_sh = df_sh[['日期', '融资余额', '融资买入额']].copy()
        df_sz = df_sz[['日期', '融资余额', '融资买入额']].copy()
        
        df = pd.concat([df_sh, df_sz]).groupby('日期').sum().reset_index()
        df = df.sort_values('日期').reset_index(drop=True)
        
        # 单位转成亿元
        for col in ['融资余额', '融资买入额']:
            if df[col].max() > 1e8:
                df[col] = df[col] / 1e8
                
        df['变动'] = df['融资余额'].diff()
        
        # 2. 抓取全市场成交额（用上证指数和深证成指的成交量近似代替）
        # 新浪接口 sh000001, sz399001
        df_sh_idx = ak.stock_zh_index_daily(symbol="sh000001")
        df_sz_idx = ak.stock_zh_index_daily(symbol="sz399001")
        
        # 取最后一天的成交量（单位：股/手，通常需除以1e8转亿）
        vol_sh = df_sh_idx.iloc[-1]['volume'] / 1e8
        vol_sz = df_sz_idx.iloc[-1]['volume'] / 1e8
        total_volume = vol_sh + vol_sz
        
        # 把成交额拼接到 df 的最新行
        df.loc[df.index[-1], '全市场成交额'] = total_volume
        
        return df
    except Exception as e:
        print(f"抓取失败: {e}")
        return None

def analyze_and_push(df):
    if df is None or len(df) < 20:
        print("数据不足或抓取失败，退出程序。")
        return

    recent_20 = df.tail(20)
    mean = recent_20['变动'].mean()
    std = recent_20['变动'].std()
    upper = mean + 2 * std
    lower = mean - 2 * std
    
    latest = df.iloc[-1]
    date_str = str(latest['日期'])
    balance = latest['融资余额']
    change = latest['变动']
    
    # 计算融资买入占比
    buy_amount = latest['融资买入额']
    total_vol = latest.get('全市场成交额', 0)
    
    if total_vol > 0:
        buy_ratio = (buy_amount / total_vol) * 100
        if buy_ratio > 10:
            ratio_signal = "🔥 交易过热（杠杆资金极度活跃）"
        elif buy_ratio < 7.5:
            ratio_signal = "❄️ 情绪低迷（杠杆资金装死中）"
        else:
            ratio_signal = "⚖️ 情绪温和"
        ratio_text = f"{buy_ratio:.2f}% ({ratio_signal})"
    else:
        ratio_text = "数据缺失"

    # 判断两融信号
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
            "header": {"title": {"tag": "plain_text", "content": "📊 两融与情绪温度计 (3.0)"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**日期**：{date_str}\n**两融余额**：{balance:.2f} 亿元\n**较前日变动**：{change:+.2f} 亿元\n**信号**：{signal}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🌡️ 融资买入占比**：{ratio_text}\n*(注：占比>10%过热，<7.5%低迷)*"}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "本内容仅为盘面数据监控，不构成任何投资建议。"}]}
            ]
        }
    }

    requests.post(WEBHOOK_URL, json=card)
    print("推送完成")

if __name__ == "__main__":
    df = get_margin_and_volume_data()
    analyze_and_push(df)
