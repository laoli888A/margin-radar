import akshare as ak
import pandas as pd
import requests
import os
from datetime import datetime

# 获取飞书地址
WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

def get_shebao_data():
    """获取最新季度的社保基金重仓股变动"""
    try:
        # 20263 代表2026年三季报
        quarter = "20263" 
        df = ak.stock_institute_hold(quarter=quarter)
        
        # 筛选出社保基金重仓的数据
        shebao_df = df[df['机构名称'].str.contains('社保', na=False)]
        
        if len(shebao_df) == 0:
            return "⚠️ 未查询到最新的社保基金重仓明细，可能财报尚未更新。"
            
        # 按持股数降序排列，取前5
        top_holdings = shebao_df.sort_values(by='持股数', ascending=False).head(5)
        
        report = "### 🏦 社保基金最新底牌（前5大重仓）\n"
        for _, row in top_holdings.iterrows():
            report += f"- **{row.get('股票简称', '未知')}**：持股约 {row.get('持股数', 0) / 10000:.2f} 万股\n"
        return report
        
    except Exception as e:
        return f"❌ 社保数据抓取失败（接口可能需更新）: {e}"

def get_etf_data():
    """获取汇金最爱买的宽基ETF份额变动"""
    try:
        # 抓取华泰柏瑞沪深300ETF（510300）的数据
        df = ak.fund_etf_hist_em(symbol="510300", period="daily", start_date="20260901", end_date="20261025")
        
        if len(df) < 2:
            return "⚠️ ETF数据不足。"
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        vol_change = latest['成交量'] - prev['成交量']
        
        report = "### 🛡️ 国家队阵地（510300 沪深300ETF）\n"
        report += f"- **最新交易日**：{latest['日期']}\n"
        report += f"- **近期成交变动**：{vol_change:.2f}\n"
        
        if vol_change > 0:
            report += "- **盘面信号**：放量增加，疑似有大资金进场托底。\n"
        else:
            report += "- **盘面信号**：缩量，大资金可能在观望或撤退。\n"
            
        return report
        
    except Exception as e:
        return f"❌ ETF数据抓取失败: {e}"

def push_to_feishu(content):
    """将底牌报告推送到飞书"""
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "🔍 大资金底牌检测仪"}, "template": "red"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "本内容仅为盘面数据监控，不构成任何投资建议。股市有风险。"}]}
            ]
        }
    }
    requests.post(WEBHOOK_URL, json=card)
    print("底牌报告推送完成")

if __name__ == "__main__":
    print(f"[{datetime.now()}] 开始抓取大资金底牌...")
    sb_report = get_shebao_data()
    etf_report = get_etf_data()
    
    full_report = sb_report + "\n\n" + etf_report
    push_to_feishu(full_report)
