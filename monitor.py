import requests
import os

# 获取飞书地址
WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK')

# 发一条最简单纯文本消息测试
data = {
    "msg_type": "text",
    "content": {
        "text": "🔔 测试成功！云端已连接飞书，主力资金极值雷达准备就绪！"
    }
}

resp = requests.post(WEBHOOK_URL, json=data)
print("推送完成")
