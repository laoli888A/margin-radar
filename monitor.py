import akshare as ak
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import os
import time

WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

def get_margin_data():
    # 抓取两融数据
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
    return df

def get_total_volume():
    """抓取全市场成交额，三重保险"""
    total_amount = 0
    try:
        df_idx = ak.stock_zh_index_spot_sina()
        target_idx = df_idx[df_idx['代码'].isin(['sh000001', 'sz399001'])]
        total_amount = target_idx['成交额'].sum() / 1e8
        if total_amount > 5000: return total_amount
    except: pass
    try:
        df_idx = ak.stock_zh_index_spot_em()
        target_idx = df_idx[df_idx['名称'].isin(['上证指数', '深证成指'])]
        total_amount = target_idx['成交额'].sum() / 1e8
        if total_amount > 5000: return total_amount
    except: pass
    try:
        df_sh = ak.stock_zh_index_daily_em(symbol="sh000001")
        df_sz = ak.stock_zh_index_daily_em(symbol="sz399106")
        total_amount = (float(df_sh.iloc[-1]['amount']) + float(df_sz.iloc[-1]['amount'])) / 1e8
        return total_amount
    except: pass
    return total_amount

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
        except: continue
    return report if report else "⚠️ ETF数据获取失败\n"

def get_lhb_data():
    """【新增】：获取龙虎榜机构净买入（硬数据，绝对真实）"""
    try:
        # 获取今日龙虎榜
        today_str = datetime.now().strftime('%Y%m%d')
        df = ak.stock_lhb_detail_em(start_date=today_str, end_date=today_str)
        
        # 提取机构专用席位的净买入额
        if df is None or len(df) == 0:
            return "暂无龙虎榜数据（可能未到披露时间）"
            
        # 按机构净买入金额降序排列（这里用'机构买入净额'字段）
        if '机构买入净额' in df.columns:
            df['机构买入净额'] = pd.to_numeric(df['机构买入净额'], errors='coerce').fillna(0)
            top3 = df.sort_values(by='机构买入净额', ascending=False).head(3)
            report = ""
            for _, row in top3.iterrows():
                name = row['名称']
                amt = row['机构买入净额'] / 1e8 # 转亿
                if amt > 0:
                    report += f"- **{name}**：机构净买 {amt:.2f} 亿\n"
            return report if report else "今日机构席位未现明显大额净买入"
        return "龙虎榜字段解析失败"
    except Exception as e:
        return f"⚠️ 龙虎榜数据抓取失败: {e}\n"

def get_industry_data():
    """保留大单参考：东财+同花顺双保险"""
    report = ""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        top3 = df.sort_values(by="今日主力净流入-净额", ascending=False).head(3)
        for _, row in top3.iterrows():
            name = row['名称']
            amount = float(row['今日主力净流入-净额']) / 1e8 
            report += f"- **{name}**：净流入 {amount:.2f} 亿\n"
        return report
    except Exception as e:
        pass
    try:
        time.sleep(1)
        df_ths = ak.stock_fund_flow_industry(symbol="即时")
        if '净额' in df_ths.columns:
            df_ths['净额_num'] = pd.to_numeric(df_ths['净额'], errors='coerce')
            top3_ths = df_ths.sort_values(by='净额_num', ascending=False).head(3)
            for _, row in top3_ths.iterrows():
                name = row['行业']
                raw_amt = row['净额_num']
                amount = raw_amt / 1e8 if raw_amt > 1000 else raw_amt
                report += f"- **{name}**：净流入 {amount:.2f} 亿 (同花顺)\n"
            return report
    except Exception as e2:
        pass
    return "⚠️ 行业资金接口均被限流，今日跳过\n"

def analyze_and_push():
    df_margin = get_margin_data()
    if df_margin is None or len(df_margin) < 20:
        print("两融数据不足，退出。")
        return

    latest = df_margin.iloc[-1]
    date_str = str(latest['日期'])[:10]
    
    # 强制北京时间
    today_str = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d')

    if date_str != today_str:
        data_status = f"⏳ **注意：两融数据暂未更新（当前显示为 {date_str} 结算数据），ETF及趋势为最新。**"
    else:
        data_status = f"✅ **数据已全部更新至今日。**"

    trend_text = get_trend_data()
    etf_text = get_etf_data()
    lhb_text = get_lhb_data() # 获取龙虎榜硬数据
    industry_text = get_industry_data()
    total_vol = get_total_volume()

    balance = latest['融资余额']
    change = latest['变动']
    buy_amount = latest['融资买入额']
    
    # 【格式优化】：把两融余额变成万亿元
    if balance >= 10000:
        balance_text = f"{balance/10000:.2f} 万亿元"
    else:
        balance_text = f"{balance:.2f} 亿元"
        
    if abs(change) >= 10000:
        change_text = f"{change/10000:+.2f} 万亿"
    else:
        change_text = f"{change:+.2f} 亿"

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
            "header": {"title": {"tag": "plain_text", "content": "🚀 全息作战指挥屏 (5.0 硬数据版)"}, "template": "purple"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📅 日期**：{date_str}\n{data_status}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📈 趋势**：{trend_text}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🌡️ 杠杆情绪**\n- 融资买入占比：{ratio_text}\n- 全市场成交额：{vol_text}\n- 两融余额：{balance_text} ({change_text})"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🛡️ 国家队底牌 (今日份额变动)**\n{etf_text}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🏆 龙虎榜机构净买入 (绝对硬数据)**\n{lhb_text}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**🔥 游资/量化大单偏好 (参考)**\n{industry_text}"}},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "本内容仅为盘面数据监控，不构成任何投资建议。"}]}
            ]
        }
    }

    requests.post(WEBHOOK_URL, json=card)
    print(f"推送完成。当前两融数据日期：{date_str}")

if __name__ == "__main__":
    analyze_and_push()
