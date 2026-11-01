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
        df = ak.stock_report_fund_hold(symbol="社保持仓", date="20260630")
        
        if df is None or len(df) == 0:
            return "⚠️ 未查询到最新的社保基金重仓明细，可能该季度财报尚未更新。"
            
        col_name = '股票简称'
        col_share = '持股总数'
        
        if col_name not in df.columns or col_share not in df.columns:
             return f"⚠️ 社保接口字段再次变化，当前包含的字段有：{list(df.columns)}"

        top_holdings = df.sort_values(by=col_share, ascending=False).head(5)
        
        # 优化排版：把 ### 换成了加粗，飞书渲染更好看
        report = "**🏦 社保基金最新底牌（前5大重仓）**\n"
        for _, row in top_holdings.iterrows():
            stock_name = str(row[col_name])
            try:
                hold_num = float(row[col_share])
                report += f"- {stock_name}：持股约 {hold_num / 10000:.2f} 万股\n"
            except:
                report += f"- {stock_name}：持股数 {row[col_share]}\n"
        return report
        
    except Exception as e:
        return f"❌ 社保数据抓取失败: {e}"

def get_etf_data():
    """获取汇金核心宽基ETF份额变动"""
    try:
        df = ak.fund_etf_hist_sina(symbol="sh510300")
        
        if df is None or len(df) < 2:
            return "⚠️ ETF数据不足。"
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        vol_change = latest['volume'] - prev['volume']
        date_str = str(latest['date'])
        
        # 优化排版：加粗标题，数字除以 10000 变成万，看起来更直观
        report = "**🛡️ 国家队阵地（510300 沪深300ETF）**\n"
        report += f"- 最新交易日：{date_str}\n"
        report += f"- 成交变动：{vol_change / 10000:+.2f} 万份\n"
        
        if vol_change > 0:
            report += "- 盘面信号：放量增加，疑似有大资金进场托底。\n"
        else:
            report += "- 盘面信号：缩量，大资金可能在观望或撤退。\n"
            
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
