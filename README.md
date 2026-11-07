# Prediction Arena

[English →](README.en.md) · 中文

面向 **ICDM 2026 · Shenyang, China** 现场的二元预测科普互动 Demo。

参与者对已发生的历史事件给出 YES 概率，与真实预测市场的事前快照对照，用 Brier Score 检验自己的判断把握，并理解概率校准。

## 运行

```bash
cd prediction-arena
pip install -r requirements.txt
python app.py          # Windows 也可双击 start_arena.bat
```

- 手机端：连同一 WiFi，打开 `http://<笔记本IP>:5000/`
- 组织者看板：`http://127.0.0.1:5000/dashboard`
- 换网络后重生成二维码：`python make_qrcode.py --print`
- 出发前自检：`python preflight.py`

## 内容

- 150 道正式题 + 3 道练手，五类各 30 道；中英双语界面
- 数据来自 Polymarket / Manifold / Kalshi / Betfair Exchange 的公开历史快照
- 纯本地 Flask + SQLite：不需要服务器、域名、备案或外网
- 详细文档见 [prediction-arena/README.md](prediction-arena/README.md)

> 仅用于教学展示，不涉及交易、下注或支付；各平台数据展示许可仍待人工核实。
