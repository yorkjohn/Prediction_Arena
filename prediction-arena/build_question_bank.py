"""Build the final question bank from AUDITED real-market candidates.

Human curation (plan 3.4) lives in SELECTED below: market_id -> Chinese/English
wording. Every probability, outcome, snapshot timestamp and source URL is read
from seed/candidates_all.json (produced by the collectors). This script never
invents a number; if a selected market is missing from the candidate file it
aborts instead of guessing.

Usage:  python build_question_bank.py
Output: seed/arena_seed_questions.json  +  ../arena_seed_questions.json (backup)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "seed" / "candidates_all.json"
OUT = ROOT / "seed" / "arena_seed_questions.json"
BACKUP = ROOT.parent / "arena_seed_questions.json"

# Curated wording. `id` is assigned below from the category prefix.
SELECTED: dict[str, dict] = {
    # ---------------------------------------------------------------- sports
    "253619": {
        "cat": "sports",
        "title_zh": "第 58 届超级碗，堪萨斯城酋长是否夺冠？",
        "title_en": "Will the Kansas City Chiefs win Super Bowl LVIII?",
        "context_zh": "超级碗是美国职业橄榄球大联盟的年度总决赛。查看赛前预测市场在结算前一小时给出的概率。",
        "context_en": "The Super Bowl is the annual championship of the NFL. Here is the price the prediction market quoted one hour before resolution.",
        "yes_zh": "堪萨斯城酋长赢得第 58 届超级碗",
        "yes_en": "The Kansas City Chiefs win Super Bowl LVIII",
    },
    "253605": {
        "cat": "sports",
        "title_zh": "第 58 届超级碗，旧金山 49 人是否夺冠？",
        "title_en": "Will the San Francisco 49ers win Super Bowl LVIII?",
        "context_zh": "同一届赛事中另一支争冠球队的市场，可与酋长队的概率对照来看。",
        "context_en": "Another contender in the same event — compare its price with the Chiefs market.",
        "yes_zh": "旧金山 49 人赢得第 58 届超级碗",
        "yes_en": "The San Francisco 49ers win Super Bowl LVIII",
    },
    "pLdAn060OZ": {
        "cat": "sports",
        "title_zh": "欧冠比赛中，曼联是否以两球及以上优势击败罗马？",
        "title_en": "Will Manchester United beat AS Roma by 2 or more goals?",
        "context_zh": "欧洲冠军联赛的一场淘汰赛。注意 YES 的定义不是「获胜」，而是「净胜两球以上」。",
        "context_en": "A UEFA Champions League tie. YES means winning by a margin of at least two goals, not merely winning.",
        "yes_zh": "曼联净胜罗马至少两球",
        "yes_en": "Manchester United beat AS Roma by two or more goals",
    },
    "CSsCgSp5tS": {
        "cat": "sports",
        "title_zh": "2026 年世界杯首轮，挪威是否战胜塞内加尔？",
        "title_en": "Will Norway defeat Senegal in the first round of World Cup 2026?",
        "context_zh": "世界杯小组赛阶段的一场对决，结果并非广为人知的常识。",
        "context_en": "A group-stage World Cup fixture whose result is not common knowledge.",
        "yes_zh": "挪威在该场比赛中获胜",
        "yes_en": "Norway win that match",
    },
    "u0dqq0lZL5": {
        "cat": "sports",
        "title_zh": "2026 年世界杯首轮，西班牙是否战胜乌拉圭？",
        "title_en": "Will Spain defeat Uruguay in the opening round of World Cup 2026?",
        "context_zh": "两支传统强队的小组赛对话。赛前市场给出的概率接近五五开。",
        "context_en": "A group-stage meeting of two established sides; the pre-match market was close to even.",
        "yes_zh": "西班牙在该场比赛中获胜",
        "yes_en": "Spain win that match",
    },
    # --------------------------------------------------------------- esports
    "TDOOpFfDd46mZwVN79jD": {
        "cat": "esports",
        "title_zh": "T1 是否夺得英雄联盟全球总决赛冠军？",
        "title_en": "Will T1 win Worlds?",
        "context_zh": "英雄联盟全球总决赛是电竞领域关注度最高的赛事之一，T1 是历史成绩最突出的战队。",
        "context_en": "The League of Legends World Championship is one of esports' biggest events and T1 is its most decorated team.",
        "yes_zh": "T1 赢得该届全球总决赛",
        "yes_en": "T1 win that World Championship",
    },
    "s04n3e76g2": {
        "cat": "esports",
        "title_zh": "2024 全球总决赛的决赛对阵是否为 BLG 对 GEN？",
        "title_en": "Will it be BLG vs. GEN in the LoL Worlds 2024 final?",
        "context_zh": "这道题问的不是谁夺冠，而是决赛的两支队伍组合，比单纯猜冠军更难。",
        "context_en": "This asks about the final's pairing rather than the winner — a harder judgement.",
        "yes_zh": "决赛由 BLG 对阵 GEN",
        "yes_en": "The final is BLG versus GEN",
    },
    "qTrebkzDRxZytzUa76Fc": {
        "cat": "esports",
        "title_zh": "T1 是否战胜 BLG？",
        "title_en": "Will T1 beat BLG?",
        "context_zh": "国际赛事中两支热门战队的直接对话。",
        "context_en": "A head-to-head between two heavily followed teams at an international event.",
        "yes_zh": "T1 赢得该场比赛",
        "yes_en": "T1 win the match",
    },
    "hyHg87ZGpyHu1nLbF592": {
        "cat": "esports",
        "title_zh": "Gen.G 是否战胜 BLG？",
        "title_en": "Will Gen.G beat BLG?",
        "context_zh": "赛前概率接近 50%，是练习概率表达的好例子。",
        "context_en": "The market was near 50%, which makes it a useful case for expressing uncertainty.",
        "yes_zh": "Gen.G 赢得该场比赛",
        "yes_en": "Gen.G win the match",
    },
    "3lT3HSG98NHICgTWnE0P": {
        "cat": "esports",
        "title_zh": "2022 英雄联盟全球总决赛冠军是否为韩国战队？",
        "title_en": "Will a Korean team win League of Legends Worlds 2022?",
        "context_zh": "不猜具体战队，只判断夺冠队伍所属赛区。",
        "context_en": "Instead of naming a team, this asks about the winning region.",
        "yes_zh": "冠军是一支韩国战队",
        "yes_en": "The champion is a Korean team",
    },
    # --------------------------------------------------------------------- ai
    "f7YmjeD02abOV2mcpuJx": {
        "cat": "ai",
        "title_zh": "GPT-4 是否在 2023 年 3 月 21 日之前发布？",
        "title_en": "Will GPT-4 be released before March 21st, 2023?",
        "context_zh": "新一代大模型发布日期在当时众说纷纭，赛前市场几乎五五开。",
        "context_en": "The release date was hotly debated; the market was almost exactly even.",
        "yes_zh": "GPT-4 在 2023 年 3 月 21 日前发布",
        "yes_en": "GPT-4 is released before 21 March 2023",
    },
    "253315": {
        "cat": "ai",
        "title_zh": "Gemini Ultra 是否在 1 月 31 日前发布？",
        "title_en": "Will Gemini Ultra be released by January 31?",
        "context_zh": "谷歌对标 GPT-4 的旗舰模型，发布时间曾多次被猜测。",
        "context_en": "Google's flagship answer to GPT-4; its launch timing was widely speculated.",
        "yes_zh": "Gemini Ultra 在 1 月 31 日前发布",
        "yes_en": "Gemini Ultra is released by 31 January",
    },
    "lojolssz4n": {
        "cat": "ai",
        "title_zh": "iPhone 16 发售当天是否就能用上 Apple Intelligence？",
        "title_en": "Will Apple Intelligence be available on an iPhone 16 on launch day?",
        "context_zh": "功能随硬件同步上市，还是稍后通过系统更新推送？这是发布前的典型悬念。",
        "context_en": "Would the AI feature ship with the hardware or arrive later in a software update?",
        "yes_zh": "发售当天即可使用 Apple Intelligence",
        "yes_en": "Apple Intelligence is available on launch day",
    },
    "jv1r5jFfLfSjGKUB2Wp0": {
        "cat": "ai",
        "title_zh": "特斯拉 Cybertruck 是否在 2023 年内开始向客户交付？",
        "title_en": "Will Tesla Cybertruck start delivering to customers in 2023?",
        "context_zh": "这款车型从发布到量产经历多次延期，交付时间是当时的热门话题。",
        "context_en": "After several delays, the delivery date was a much-discussed question.",
        "yes_zh": "2023 年内开始交付",
        "yes_en": "Customer deliveries begin in 2023",
    },
    "IEKO8AnEQaT57ZYUMZ8Z": {
        "cat": "ai",
        "title_zh": "OpenAI 是否在当年 11 月底前向公众开放多模态 GPT-4？",
        "title_en": "Will OpenAI release multimodal GPT-4 for public use by the end of November?",
        "context_zh": "多模态能力何时向普通用户开放，是模型发布后的常见预测题。",
        "context_en": "When multimodal capabilities reach the public is a recurring forecasting question.",
        "yes_zh": "11 月底前面向公众开放",
        "yes_en": "Public access opens by the end of November",
    },
    # --------------------------------------------------------------- business
    "253961": {
        "cat": "business",
        "title_zh": "基里安·墨菲是否获得奥斯卡最佳男主角？",
        "title_en": "Will Cillian Murphy win the Oscar for Best Actor?",
        "context_zh": "颁奖季前市场已高度看好，但高概率不等于确定。",
        "context_en": "The market was strongly favourite before the ceremony — but a high price is not certainty.",
        "yes_zh": "墨菲获得该届奥斯卡最佳男主角",
        "yes_en": "Cillian Murphy wins Best Actor",
    },
    "253574": {
        "cat": "business",
        "title_zh": "派拉蒙是否在第一季度发生并购？",
        "title_en": "Will there be a Paramount merger or acquisition in Q1?",
        "context_zh": "传媒行业整合传闻持续了很久，是否能在一个季度内落地是典型的时限型问题。",
        "context_en": "A deadline-style question about whether long-running media consolidation talk would close in one quarter.",
        "yes_zh": "第一季度内达成并购交易",
        "yes_en": "A merger or acquisition closes in Q1",
    },
    "t2sCC598OP": {
        "cat": "business",
        "title_zh": "2026 年奥斯卡，同一部影片是否同时拿下最佳影片与最佳导演？",
        "title_en": "Will the same film win both Best Picture and Best Director at the 2026 Oscars?",
        "context_zh": "两个奖项常常一致，但偶尔分家；这是判断「联合事件」的好例子。",
        "context_en": "The two awards often agree but sometimes split — a useful joint-event judgement.",
        "yes_zh": "最佳影片与最佳导演归属同一部电影",
        "yes_en": "Both awards go to the same film",
    },
    "253830": {
        "cat": "business",
        "title_zh": "苹果在 1 月 31 日是否是全球市值最高的公司？",
        "title_en": "Will Apple be the largest company in the world on January 31?",
        "context_zh": "市值榜首会随股价波动易主，这是一道带具体时间点的判断题。",
        "context_en": "The top spot by market cap changes with share prices; this question has a fixed date.",
        "yes_zh": "1 月 31 日苹果市值全球第一",
        "yes_en": "Apple is the world's most valuable company on 31 January",
    },
    "Vkic4ShNxho2chqvopCI": {
        "cat": "business",
        "title_zh": "iPhone 16 是否具备生成式 AI 能力？",
        "title_en": "Will the iPhone 16 have generative AI capabilities?",
        "context_zh": "发布前关于新一代 iPhone 是否会主打 AI 功能的预测。",
        "context_en": "Before launch, would the new iPhone headline generative AI features?",
        "yes_zh": "至少一款 iPhone 16 具备生成式 AI 能力",
        "yes_en": "At least one iPhone 16 model has generative AI capabilities",
    },
    # ------------------------------------------------------------------ world
    "5fe3LCGodjIo5Z1bPvJm": {
        "cat": "world",
        "title_zh": "2024 巴黎奥运会，美国是否获得最多金牌？",
        "title_en": "Will the USA win the most gold medals at the 2024 Paris Olympics?",
        "context_zh": "奥运会奖牌榜是赛前最常被预测的国际公共事件之一。",
        "context_en": "The Olympic medal table is one of the most forecast public events.",
        "yes_zh": "美国位居金牌榜第一",
        "yes_en": "The USA tops the gold-medal table",
    },
    "OBMH2tBYb2dIriwo65GT": {
        "cat": "world",
        "title_zh": "2024 巴黎奥运会，是否至少有 90 个国家和地区获得奖牌？",
        "title_en": "Will at least 90 nations win a medal at the 2024 Summer Olympics?",
        "context_zh": "不是猜某个国家，而是判断奖牌分布的广度。",
        "context_en": "Not about one country but about how widely medals are distributed.",
        "yes_zh": "获奖国家和地区不少于 90 个",
        "yes_en": "At least 90 nations win a medal",
    },
    "NpXaV0tsqgr8wRtNcaf4": {
        "cat": "world",
        "title_zh": "2024 巴黎奥运会男子 100 米冠军是否来自美国？",
        "title_en": "Will a US athlete win the men's 100m at the 2024 Paris Olympics?",
        "context_zh": "短跑飞人大战悬念大，赛前概率接近五五开。",
        "context_en": "A marquee sprint with a genuinely uncertain outcome; the market was near even.",
        "yes_zh": "冠军是美国选手",
        "yes_en": "The winner represents the USA",
    },
    "FJhstqiqwWH2LmLFlSJK": {
        "cat": "world",
        "title_zh": "2024 巴黎奥运会羽毛球金牌是否由非亚洲国家获得？",
        "title_en": "Will a badminton gold medal be won by a non-Asian country at the 2024 Olympics?",
        "context_zh": "羽毛球长期由亚洲队伍主导，这是一道典型的「小概率事件」判断题。",
        "context_en": "Badminton has long been dominated by Asian nations — a classic low-probability question.",
        "yes_zh": "至少一枚羽毛球金牌由非亚洲国家获得",
        "yes_en": "At least one badminton gold goes to a non-Asian country",
    },
    "6Kdmdu55wAjCdUZW5woc": {
        "cat": "world",
        "title_zh": "2025 年全球平均气温是否超过 2023 年？",
        "title_en": "Will the average global temperature in 2025 exceed 2023?",
        "context_zh": "气候记录逐年刷新，但具体某一年的相对高低并非显而易见。",
        "context_en": "Records keep falling, yet the year-on-year comparison is not obvious in advance.",
        "yes_zh": "2025 年全球平均气温高于 2023 年",
        "yes_en": "The 2025 global average temperature exceeds 2023",
    },
}

WARMUP = [
    {
        "id": "W01", "title_zh": "2016 年，AlphaGo 是否在五番棋中击败李世石？",
        "title_en": "Did AlphaGo defeat Lee Sedol in 2016?",
        "context_zh": "赛前多数评论并不看好程序战胜顶级棋手。",
        "context_en": "Before the match, most commentators doubted a program could beat a top player.",
        "yes_zh": "AlphaGo 赢得五番棋", "yes_en": "AlphaGo wins the five-game match",
        "outcome": 1,
        "explain_zh": "低概率事件也会发生。概率表达的是把握，不是预言。",
        "explain_en": "Low-probability events do happen. A probability is a degree of belief, not a prophecy.",
    },
    {
        "id": "W02", "title_zh": "2020 年东京奥运会是否在 2020 年如期举行？",
        "title_en": "Did the Tokyo Olympics take place in 2020 as scheduled?",
        "context_zh": "赛事原定 2020 年夏季举行。",
        "context_en": "The Games were originally scheduled for summer 2020.",
        "yes_zh": "在 2020 年内举行", "yes_en": "Held within 2020",
        "outcome": 0,
        "explain_zh": "高概率也不代表一定发生。意外发生时 Brier Score 会明显变差。",
        "explain_en": "Even a high probability is not certainty; surprises cost Brier points.",
    },
    {
        "id": "W03", "title_zh": "2007 年，苹果是否发布第一代 iPhone？",
        "title_en": "Did Apple launch the first iPhone in 2007?",
        "context_zh": "这是消费电子史上被广泛记录的发布。",
        "context_en": "A well-documented launch in consumer-electronics history.",
        "yes_zh": "在 2007 年发布", "yes_en": "Released in 2007",
        "outcome": 1,
        "explain_zh": "高概率事件答对了，得分提升有限；这就是 Brier Score 的特点。",
        "explain_en": "Being right on a likely event earns little extra credit — that is how Brier scoring works.",
    },
]

PREFIX = {"sports": "SP", "esports": "ES", "ai": "AI",
          "business": "BU", "world": "WO"}


def main() -> int:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    by_id = {m["market_id"]: m for m in data["markets"]}

    missing = [mid for mid in SELECTED if mid not in by_id]
    if missing:
        print(f"ERROR: {len(missing)} selected markets missing from candidates:")
        for mid in missing:
            print("  ", mid)
        return 1

    questions = []
    for q in WARMUP:
        questions.append({
            "id": q["id"], "mode": "warmup", "category": "ai",
            "title_zh": q["title_zh"], "title_en": q["title_en"],
            "context_zh": q["context_zh"], "context_en": q["context_en"],
            "yes_zh": q["yes_zh"], "yes_en": q["yes_en"],
            "outcome": q["outcome"], "benchmark_probability": None,
            "benchmark_verified": False, "benchmark_source": None,
            "benchmark_snapshot_time": None, "benchmark_url": None,
            "source_api": None, "license_status": "TEACHING_EXAMPLE",
            "explain_zh": q["explain_zh"], "explain_en": q["explain_en"],
            "source_note": "WARMUP_TEACHING_EXAMPLE",
        })

    counters = Counter()
    for mid, meta in SELECTED.items():
        m = by_id[mid]
        cat = meta["cat"]
        counters[cat] += 1
        questions.append({
            "id": f"{PREFIX[cat]}{counters[cat]:02d}",
            "mode": "real", "category": cat,
            "title_zh": meta["title_zh"], "title_en": meta["title_en"],
            "context_zh": meta["context_zh"], "context_en": meta["context_en"],
            "yes_zh": meta["yes_zh"], "yes_en": meta["yes_en"],
            "outcome": int(m["outcome"]),
            "benchmark_probability": float(m["probability"]),
            "benchmark_verified": True,
            "benchmark_source": m["source_platform"],
            "benchmark_snapshot_time": m["snapshot_time"],
            "benchmark_url": m["market_url"],
            "source_api": m["source_api"],
            "license_status": m["license_status"],
            "explain_zh": "", "explain_en": "",
            "source_note": "REAL_MARKET_SNAPSHOT",
            "source_market_id": mid,
        })

    # ---- football-data.co.uk: free Betfair Exchange pre-match odds ----------
    # Questions are generated from the CSV (plan 5.3 conversion), not hand-written.
    fpath = ROOT / "seed" / "football_markets.json"
    if fpath.exists():
        fdata = json.loads(fpath.read_text(encoding="utf-8"))
        fc = Counter()
        for fm in fdata.get("markets", []):
            if not fm.get("selected"):
                continue
            fc["sports"] += 1
            questions.append({
                "id": f"FB{fc['sports']:02d}",
                "mode": "real", "category": "sports",
                "title_zh": fm["title_zh"], "title_en": fm["title_en"],
                "context_zh": fm["context_zh"], "context_en": fm["context_en"],
                "yes_zh": fm["yes_zh"], "yes_en": fm["yes_en"],
                "outcome": int(fm["outcome"]),
                "benchmark_probability": float(fm["probability"]),
                "benchmark_verified": True,
                "benchmark_source": "football-data.co.uk (Betfair Exchange)",
                "benchmark_snapshot_time": fm["match_date"],
                "benchmark_snapshot_method": fm["snapshot_method"],
                "benchmark_url": fm["source_url"],
                "source_api": fm["source_url"],
                "license_status": fm["license_status"],
                "explain_zh": "", "explain_en": "",
                "source_note": "BETFAIR_EXCHANGE_ODDS",
                "source_market_id": fm["market_id"],
            })

    bank = {
        "version": "REAL-2026-11-05",
        "warning": "25 real questions curated from Polymarket / Manifold. Probabilities are genuine pre-event snapshots (>=1h before resolution). API/display licensing is NOT yet verified (plan 10.3) — confirm before public presentation. Warm-up questions are teaching examples with no market probability.",
        "categories": [
            {"key": "sports", "zh": "体育", "en": "Sports"},
            {"key": "esports", "zh": "电竞", "en": "Esports"},
            {"key": "ai", "zh": "AI 与科技", "en": "AI & Tech"},
            {"key": "business", "zh": "商业与生活", "en": "Business & Life"},
            {"key": "world", "zh": "国际与社会", "en": "World & Society"},
        ],
        "questions": questions,
    }
    payload = json.dumps(bank, ensure_ascii=False, indent=2)
    OUT.write_text(payload, encoding="utf-8")
    BACKUP.write_text(payload, encoding="utf-8")

    real = [q for q in questions if q["mode"] == "real"]
    print("=" * 68)
    print(f"  wrote {len(questions)} questions ({len(real)} real + 3 warm-up)")
    print("  per category:", dict(Counter(q["category"] for q in real)))
    print("  outcome balance:", dict(Counter(q["outcome"] for q in real)))
    print("  sources:", dict(Counter(q["benchmark_source"] for q in real)))
    print(f"  -> {OUT}")
    print(f"  -> {BACKUP}")
    print("  NOTE: delete arena.db to re-import the new bank.")
    return 0


# ---------------------------------------------------------------------------
# Extension (2026-11-05): Kalshi markets + additional audited candidates.
# Kept here rather than folded into SELECTED so the original 25-row curation
# stays easy to audit. All numbers still come from the candidate pool.
# ---------------------------------------------------------------------------
CANDIDATES = ROOT / "seed" / "candidates_all_v2.json"

EXTRA: dict[str, dict] = {
    # ---- Kalshi, sports (previous-day close price) ----
    "KXNBAGAME-26NOV04MIALAC-MIA": {
        "cat": "sports",
        "title_zh": "2026 年 11 月 4 日 NBA 常规赛，迈阿密热火是否战胜洛杉矶快船？",
        "title_en": "Will Miami beat the Los Angeles Clippers on Nov 4, 2026?",
        "context_zh": "Kalshi 赛前一日收盘价给出的胜率。两支球队实力接近，市场并未一边倒。",
        "context_en": "Kalshi's previous-day close. The matchup was not one-sided.",
        "yes_zh": "热火赢下该场比赛", "yes_en": "Miami wins the game",
    },
    "KXUCLGAME-26NOV04FENLFC-LFC": {
        "cat": "sports",
        "title_zh": "欧冠小组赛，利物浦是否战胜费内巴切？",
        "title_en": "Will Liverpool beat Fenerbahce in the Champions League?",
        "context_zh": "赛前市场明显看好利物浦，但客场爆冷并不罕见。",
        "context_en": "The market favoured Liverpool, yet away upsets are never impossible.",
        "yes_zh": "利物浦赢下该场比赛", "yes_en": "Liverpool win the match",
    },
    "KXNBAGAME-26NOV04LALSAC-SAC": {
        "cat": "sports",
        "title_zh": "2026 年 11 月 4 日 NBA 常规赛，萨克拉门托国王是否战胜洛杉矶湖人？",
        "title_en": "Will Sacramento beat the Los Angeles Lakers on Nov 4, 2026?",
        "context_zh": "赛前市场只给了国王不到两成机会，这是一道典型的小概率判断题。",
        "context_en": "The market gave Sacramento under 20% — a classic low-probability call.",
        "yes_zh": "国王赢下该场比赛", "yes_en": "Sacramento win the game",
    },
    # ---- Kalshi, world (mutually exclusive temperature brackets) ----
    "KXHIGHNY-26NOV04-B72.5": {
        "cat": "world",
        "title_zh": "2026 年 11 月 4 日纽约最高气温是否落在 72–73°F 区间？",
        "title_en": "Will New York's high on Nov 4, 2026 be 72-73°F?",
        "context_zh": "气温区间市场把连续量切成互斥桶，是理解「概率加总」的好例子。",
        "context_en": "Temperature brackets split a continuous quantity into mutually exclusive buckets — useful for thinking about probabilities summing to one.",
        "yes_zh": "当日最高气温落在 72–73°F", "yes_en": "The daily high falls in 72-73°F",
    },
    "KXHIGHNY-26NOV04-B70.5": {
        "cat": "world",
        "title_zh": "2026 年 11 月 4 日纽约最高气温是否落在 70–71°F 区间？",
        "title_en": "Will New York's high on Nov 4, 2026 be 70-71°F?",
        "context_zh": "与上一题是同一天的互斥区间，两道题的概率不能同时成立。",
        "context_en": "A mutually exclusive bracket from the same day as the previous question; both cannot resolve YES.",
        "yes_zh": "当日最高气温落在 70–71°F", "yes_en": "The daily high falls in 70-71°F",
    },
    # ---- esports, additional audited markets ----
    "C70S1mnTZN8sUJB1lmYV": {
        "cat": "esports",
        "title_zh": "Fnatic 是否赢得 2023 年 Valorant 全球冠军赛？",
        "title_en": "Will Fnatic win Valorant Champions 2023?",
        "context_zh": "Valorant 最高级别赛事，与英雄联盟全球总决赛并列为电竞年度焦点。",
        "context_en": "Valorant's premier event, alongside LoL Worlds one of esports' annual highlights.",
        "yes_zh": "Fnatic 夺冠", "yes_en": "Fnatic win the championship",
    },
    "99peUJsYL5abIdpJb2J2": {
        "cat": "esports",
        "title_zh": "T1 是否战胜 Team Liquid？",
        "title_en": "Will T1 beat Team Liquid?",
        "context_zh": "国际赛事里中韩与欧美战队的一次对话，赛前市场明显偏向 T1。",
        "context_en": "An international matchup the market clearly favoured T1 to win.",
        "yes_zh": "T1 赢下该场比赛", "yes_en": "T1 win the match",
    },
    "DuwD7SqNH1XVlh00OVX5": {
        "cat": "esports",
        "title_zh": "BLG 是否战胜 KT Rolster？",
        "title_en": "Will BLG beat KT Rolster?",
        "context_zh": "中韩战队交锋，赛前概率接近五五开。",
        "context_en": "A China–Korea matchup the market priced close to even.",
        "yes_zh": "BLG 赢下该场比赛", "yes_en": "BLG win the match",
    },
    # ---- AI & tech, additional audited markets ----
    "TXq1oCXEMLqO8uTdR7dO": {
        "cat": "ai",
        "title_zh": "到 2024 年底，谷歌是否在大模型质量上基本追平 OpenAI？",
        "title_en": "Will Google mostly catch up to OpenAI in LLM quality by the end of 2024?",
        "context_zh": "模型能力追赶是当年最热门的行业判断之一，且没有唯一客观答案，很适合讨论概率的含义。",
        "context_en": "A heavily debated industry call with no single objective answer — good for discussing what a probability means.",
        "yes_zh": "市场按规则判定谷歌基本追平", "yes_en": "The market resolves YES on Google catching up",
    },
    "Sh9L8I2hcy": {
        "cat": "ai",
        "title_zh": "DeepSeek 是否在 2026 年 4 月发布 V4？",
        "title_en": "Will DeepSeek release V4 in April 2026?",
        "context_zh": "国产模型团队的发版节奏是近两年科技圈最常被预测的话题之一。",
        "context_en": "Release timing for a Chinese model lab has been one of the most forecast tech questions.",
        "yes_zh": "V4 在 2026 年 4 月发布", "yes_en": "V4 is released in April 2026",
    },
    "rJELHCYRcdnfrE07wmFM": {
        "cat": "ai",
        "title_zh": "xAI 是否在 2024 年底前发布 BIG-Bench 成绩追平 GPT-4 Turbo 的模型？",
        "title_en": "Will xAI release an LLM matching GPT-4 Turbo on BIG-Bench before the end of 2024?",
        "context_zh": "带明确基准和截止时间的「能力达标」题，比笼统猜进度更可核验。",
        "context_en": "A benchmark-and-deadline question, more verifiable than a vague progress guess.",
        "yes_zh": "期限内发布并达到该基准", "yes_en": "Such a model ships within the deadline",
    },
    # ---- business & life, additional audited markets ----
    "l0TCD6SnEAgJMdaCpq2a": {
        "cat": "business",
        "title_zh": "iPhone 16 上的 AirPods Pro 2（USB-C）是否支持无损音频？",
        "title_en": "Will AirPods Pro 2 USB-C support lossless audio on iPhone 16?",
        "context_zh": "发布前关于硬件功能组合的具体悬念，规则清晰、结果可核验。",
        "context_en": "A concrete pre-launch hardware question with a clear resolution rule.",
        "yes_zh": "支持无损音频", "yes_en": "Lossless audio is supported",
    },
    "07rw9uSiTclJfM3xV7c0": {
        "cat": "business",
        "title_zh": "2025 年底前 Apple Vision Pro 是否会有 Spotify 应用？",
        "title_en": "Will there be a Spotify app for Apple Vision Pro by the end of 2025?",
        "context_zh": "新平台能否吸引主流应用适配，是产品生态的典型预测题。",
        "context_en": "Whether a new platform attracts a major app is a classic ecosystem forecast.",
        "yes_zh": "期限内上架 Spotify 应用", "yes_en": "A Spotify app ships by the deadline",
    },
}

SELECTED.update(EXTRA)


# ---------------------------------------------------------------------------
# Second-pass expansion (2026-11-05): bring every category up to 20 questions.
# Same curation bar as before; only the Chinese wording is written here, every
# number still comes from the audited candidate pool.
# ---------------------------------------------------------------------------
CANDIDATES = ROOT / "seed" / "candidates_all_v3.json"

_AUTO: dict[str, tuple[str, str]] = {
    # esports (12)
    "w5DvkaKEotTuoVPKMpBu": ("esports", "全球总决赛，WBG 是否战胜 T1？"),
    "EAUuL9nluI": ("esports", "LoL 全球总决赛欧美对决，G2 是否战胜 FQ？"),
    "jIKfHZIwjhypYmN5CYaw": ("esports", "Gen.G 是否战胜 G2 Esports？"),
    "BWtPaHRgEpyat2QAZrKP": ("esports", "G2 是否战胜 Gen.G？"),
    "tZMqkyL8CC7akHsA89QE": ("esports", "T1 是否战胜 Gen.G？"),
    "kNWl2QRXRypgs3yCXElq": ("esports", "G2 对阵 BLG，G2 是否获胜？"),
    "8XpVvVHXcZgYJ1Lwc0GC": ("esports", "JDG 是否战胜 BLG？"),
    "FnwDttvtiMYBv8rzw0My": ("esports", "MSI 决赛，JDG 是否战胜 BLG？"),
    "lT9irMPZzga0d4xUeZVm": ("esports", "5 月 12 日，T1 是否战胜 BLG？"),
    "pO2MkXHQB688ROWBqFc3": ("esports", "LPL 决赛，BLG 是否战胜 TES？"),
    "txVHSHsYmClqBXvyp9sM": ("esports", "Fnatic 是否战胜 LNG？"),
    "BgUBs7wkxZ466HLj6lwi": ("esports", "T1 是否在全球总决赛决赛中全胜横扫对手？"),
    # AI & tech (12)
    "hIZh09US9R": ("ai", "GPT-5 是否在 2025 国际数学奥林匹克取得铜牌级成绩？"),
    "pQpzZZIuC5": ("ai", "Claude Opus 4.6 是否在当周发布？"),
    "uphA9gU6z0": ("ai", "GPT-5.4 在 METR 50% 时间跨度基准上是否超过 Claude Opus 4.6？"),
    "h69RtC62OI": ("ai", "Claude 4 是否在 EQ-Bench 创意写作 v3 榜单排名第一？"),
    "ANcugZ2g9C": ("ai", "是否至少有 100 篇学术论文论证 AGI 不可能实现？"),
    "Uhn8R00LRu": ("ai", "AGI 是否在 2026 年之前发布？"),
    "IZNy88CZ02": ("ai", "OpenAI Astra 在 Artificial Analysis 评测上是否击败 Opus 5？"),
    "R9PlhZhnny": ("ai", "Grok 4 在 SimpleBench 上是否取得超过 69% 的成绩？"),
    "gnlyuIP9c5": ("ai", "2027 年 1 月 1 日前是否出现能力超过 GPT-4 的新 AI 模型？"),
    "9SSquC8Rz0": ("ai", "2026 年主流 AI 模型是否通过「火柴人箭头命名」测试？"),
    "oKy2HP3wVVDUekN5QOHi": ("ai", "Sora 是否先于下一代 GPT（4.5 / 5）向公众开放？"),
    "6SZq0nsPSN": ("ai", "2026 年底前是否出现能力超过 Opus 4.5 的开源大模型？"),
    # Business & life (13)
    "2SnttQZty9": ("business", "《Sinners》是否获得 2026 年奥斯卡最佳影片？"),
    "lZLUlSgyNZ": ("business", "折叠屏 iPhone 在美国的首发起价是否至少 2400 美元？"),
    "QcEEQqt9Zc": ("business", "Netflix 是否成功收购华纳？"),
    "6cppPh0680": ("business", "《Peaky Blinders》电影是否成为 Netflix 首周冠军影片？"),
    "zCRqOt0O9C": ("business", "迈克尔·杰克逊《Billie Jean》是否在 5 月登上 Spotify 全球榜第一？"),
    "UUdnpQq2hI": ("business", "《i quit》是否获得 2026 年格莱美最佳摇滚专辑？"),
    "c8LAIZuQAh": ("business", "Jon Batiste《BIG MONEY》是否获得格莱美最佳美洲音乐专辑？"),
    "sRs6n0yZdy": ("business", "Playboi Carti 是否在当年再发行一张专辑？"),
    "6c09Lqh8OU": ("business", "真人版《海洋奇缘》北美票房是否超过《小黄人与怪兽》？"),
    "Zg6lUZ9ggC": ("business", "2026 款 Cybertruck 是否获得五星安全评级？"),
    "dhl9cuppUs": ("business", "Nintendo Switch 2 是否支持 USB-C DisplayPort 视频输出？"),
    "g0sUhuNUnR": ("business", "《GTA VI》是否再次延期？"),
    "boWTjNGvAamK6pOZoIhA": ("business", "2025 年底前是否宣布《光环》登陆 PS5？"),
    # World & society (13) — includes international fixtures misrouted by the
    # "World Cup" search term; they belong here, not under esports.
    "Jh0DZxJWZh0eFLlhKuvP": ("world", "2024 巴黎奥运会是否为巴黎带来超过 110 亿欧元旅游收入？"),
    "nmdr9vpe8m": ("world", "拜尔斯是否获得 2024 巴黎奥运会女子个人全能金牌？"),
    "1fi2cciidb": ("world", "拜尔斯是否获得 2024 巴黎奥运会自由体操金牌？"),
    "cQEsluQAOp": ("world", "洛杉矶当日官方最高气温是否达到或超过 91°F？"),
    "6Sp6dcSAyU": ("world", "德国在 2026 年是否创下历史最高气温纪录？"),
    "02NzILh82U": ("world", "纽约 11 月 12 日最高气温是否达到 45°F 以上？"),
    "90PPtSQ2yL": ("world", "2026 世界杯首轮，美国是否至少战平土耳其？"),
    "EyAqUUlsR9": ("world", "新西兰男足是否在 2026 世界杯赢下一场比赛？"),
    "NI0C9q2I2u": ("world", "2026 世界杯，美国是否战胜比利时？"),
    "t2OLqySq2y": ("world", "世界杯半决赛，西班牙是否战胜法国？"),
    "cEyLQIPLqn": ("world", "2026 世界杯四强是否出现欧足联与南美足联以外的球队？"),
    "IMq5RDhyPPhzPr303zVl": ("world", "2022 世界杯，克罗地亚是否进入四强？"),
    "sf5y4TswIrvMbTyjwPlN": ("world", "2022 世界杯，摩洛哥是否进入四强？"),
}

_CONTEXT = {
    "esports": (
        "国际电竞赛事的赛前预测市场概率。结果以该市场的结算规则为准。",
        "Pre-match prediction-market price for an international esports fixture.",
    ),
    "ai": (
        "AI / 科技事件的赛前预测市场概率，通常带明确时间点或可核验基准。",
        "Pre-event prediction-market price for an AI or technology question.",
    ),
    "business": (
        "影视、消费电子与商业事件的赛前预测市场概率，结果可公开核验。",
        "Pre-event prediction-market price for an entertainment or consumer-tech question.",
    ),
    "world": (
        "国际赛事与公共事件的赛前预测市场概率。",
        "Pre-event prediction-market price for an international event or public question.",
    ),
}

_pool = {
    m["market_id"]: m
    for m in json.loads(CANDIDATES.read_text(encoding="utf-8"))["markets"]
}
for _mid, (_cat, _zh) in _AUTO.items():
    _m = _pool.get(_mid)
    if _m is None:
        raise RuntimeError(f"expansion market missing from candidate pool: {_mid}")
    _cz, _ce = _CONTEXT[_cat]
    SELECTED[_mid] = {
        "cat": _cat,
        "title_zh": _zh,
        "title_en": _m["question_en"],
        "context_zh": _cz,
        "context_en": _ce,
        "yes_zh": _zh.replace("是否", "").rstrip("？").strip(),
        "yes_en": "The market resolves YES on this question.",
    }


# ---------------------------------------------------------------------------
# Third pass (2026-11-07): 50 more curated questions, 10 per category.
# Wording is produced by expand_bank_more.py -> seed/more_picks.json; every
# probability / outcome / timestamp / URL still comes from the merged pool.
# ---------------------------------------------------------------------------
CANDIDATES = ROOT / "seed" / "candidates_all_v4.json"
_MORE_PICKS = ROOT / "seed" / "more_picks.json"

if _MORE_PICKS.exists():
    _pool3 = {
        m["market_id"]: m
        for m in json.loads(CANDIDATES.read_text(encoding="utf-8"))["markets"]
    }
    _SPORTS_CONTEXT = (
        "体育赛事的赛前预测市场概率，结果以该市场的结算规则为准。",
        "Pre-event prediction-market price for a sports fixture.",
    )
    for _mid, _meta in json.loads(_MORE_PICKS.read_text(encoding="utf-8")).items():
        _m = _pool3.get(_mid)
        if _m is None:
            raise RuntimeError(f"third-pass market missing from pool: {_mid}")
        _cz, _ce = _CONTEXT.get(_meta["cat"], _SPORTS_CONTEXT)
        SELECTED[_mid] = {
            "cat": _meta["cat"],
            "title_zh": _meta["title_zh"],
            "title_en": _meta["title_en"],
            "context_zh": _cz,
            "context_en": _ce,
            "yes_zh": _meta["title_zh"].replace("是否", "").rstrip("？").strip(),
            "yes_en": "The market resolves YES on this question.",
        }


if __name__ == "__main__":
    raise SystemExit(main())
