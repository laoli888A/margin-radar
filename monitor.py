import akshare as ak
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import os

WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

def get_margin_data():
    try:
        df_sse = ak.stock_margin_sse()
        df_szse = ak.stock_margin_szse()
        df_sse['日期'] = pd.to_datetime(df_sse['信用交易日期'])
        df_szse['日期'] = pd.to_datetime(df_szse['信用交易日期'])
        df_sse = df_sse[['日期', '融资余额', '融资买入额']].copy()
        df_szse = df_szse[['日期', '融资余额', '融资买入额']].copy()
        df = pd.concat([df_sse, df_szse]).groupby('日期').sum().reset_index()
        df = df.sort_values('日期').reset_index(drop=True)
        for col in ['融资余额', '融资买入额']:
            if df[col].max() > 1e8: df[col] = df[col] / 1e8
        df['变动'] = df['融资余额'].diff()
    except Exception as e:
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()
        df_sh = df_sh[['日期', '融资余额', '融资买入额']].copy()
        df_sz = df_sz[['日期', '融资余额', '融资买入额']].copy()
        df = pd.concat([df_sh, df_sz]).groupby('日期').sum().reset_index()
        df = df.sort_values('日期').reset_index(drop=True)
        for col in ['融资余额', '融资买入额']:
            if df[col].max() > 1e8: df[col] = df[col] / 1e8
        df['变动'] = df['融资余额'].diff()

    # 【终极修复】：改用日线接口抓成交额，绝不空缺
    try:
        df_sh_idx = ak.stock_zh_index_daily(symbol="sh000001")
        df_sz_idx = ak.stock_zh_index_daily(symbol="sz399106")
        amount_sh = df_sh_idx.iloc[-1]['amount'] / 1e8
        amount_sz = df_sz_idx.iloc[-1]['amount'] / 1e8
        df.loc[df.index[-1], '全市场成交额'] = amount_sh + amount_sz
    except:
        df.loc[df.index[-1], '全市场成交额'] = 0
        
    return df

def get_trend_data():
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        latest = df.iloc[-1]
        close, ma20, ma60 = latest['close'], latest['MA20'], latest['MA60']
        if close > ma20 and ma20 > ma60: return "🟢 **多头排列** (站上20日及60日线)"
        elif close < ma20 and close < ma60: return "🔴 **空头排列** (跌破20日及60日线，防守为主)"
        else: return "🟡 **震荡趋势** (均线交织，方向不明)"
    except Exception as e:
        return f"❌ 趋势抓取失败: {e}"

def get_etf_data():
    etfs = {'sh510300': '沪深300', 'sh510500': '中证500', 'sh588000': '科创50'}
    report = ""
    for code, name in etfs.items():
        try:
            df = ak.fund_etf_hist_sina(symbol=code)
            if len(df) >= 2:
                vol_change = df.iloc[-1]['volume'] - df.iloc[-2]['volume']
                signal = "放量申购" if vol_change > 0 else "缩量赎回"
                report += f"- {name}ETF：{vol_change/10000:+.2f}万份 ({signal})\n"
        except:
            continue
    return report if report else "⚠️ ETF数据获取失败\n"

def get_industry_data():
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        top3 = df.sort_values(by="今日主力净流入-净额", ascending=False).head(3)
        report = ""
        for _, row in top3.iterrows():
            name = row['名称']
            amount = float(row['今日主力净流入-净额']) / 1e8 
            report += f"- **{name}**：净流入 {amount:.2f} 亿\n"
        return report
    except Exception as e:
        return "⚠️ 行业资金接口被限流，今日跳过\n"

def analyze_and_push():
    df_margin = get_margin_data()
    if df_margin is None or len(df_margin) < 20:
        print("两融数据不足，退出。")
        return

    latest = df_margin.iloc[-1]
    date_str = str(latest['日期'])[:10]
    today_str = datetime.now().strftime('%Y-%m-%d')

    if date_str != today_str:
        data_status = f"⏳ **注意：两融数据暂未更新（当前显示为 {date_str} 结算数据），ETF及趋势为今日最新。**"
    else:
        data_status = f"✅ **数据已全部更新至今日。**"

    trend_text = get_trend_data()
    etf_text = get_etf_data()
    industry_text = get_industry_data()

    balance = latest['融资余额']
    change = latest['变动']
    buy_amount = latest['融资买入额']
    total_vol = latest.get('全市场成交额', 0)
    
    if total_vol > 0:
        buy_ratio = (buy_amount / total_vol) * 100
        if buy_ratio > 10: ratio_signal = "🔥 交易过热"
        elif buy_ratio < 7.5: ratio_signal = "❄️ 情绪低迷"
        else: ratio_signal = "⚖️ 情绪温和"
        ratio_text = f"{buy_ratio:.2f}% ({ratio_signal})"
    else:
        ratio_text = "数据缺失"

    vol_text = f"{total_vol / 10000:.2f} 万亿元" if total_vol >= 10000 else f"{total_vol:.2f} 亿元"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "🚀 全息作战指挥屏 (4.1)"}, "template": "purple"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📅 日期**：{date_str}\n{data_status}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📈 趋势**：{trend_text}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🌡️ 杠杆情绪**\n- 融资买入占比：{ratio_text}\n- 全市场成交额：{vol_text}\n- 两融余额：{balance:.2f} 亿元 ({change:+.2f} 亿)"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🛡️ 国家队底牌 (今日份额变动)**\n{etf_text}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🔥 主力资金主攻方向**\n{industry_text}"}},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "本内容仅为盘面数据监控，不构成任何投资建议。"}]}
            ]
        }
    }

    requests.post(WEBHOOK_URL, json=card)
    print(f"推送完成。当前两融数据日期：{date_str}")

if __name__ == "__main__":
    analyze_and_push()
