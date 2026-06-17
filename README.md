# Adaptive Edge — AI Crypto Trading Agent

**Bitget Base Camp Hackathon S1 — Track 1: Trading Agent**

## Quick Start

### Prerequisites
- Python 3.10+
- Bitget account (https://www.bitget.com)
- Telegram bot token (from @BotFather)

### Step 1: Clone & Install
```bash
git clone https://github.com/mh1301/adaptive-edge.git
cd adaptive-edge
pip install -r requirements.txt
```

### Step 2: Get Bitget API Keys
1. Go to https://www.bitget.com -> Log in
2. Go to API Management (Settings -> API)
3. Create API key with **Trade** permission
4. Save the API Key, Secret Key, and Passphrase

### Step 3: Get Telegram Bot Token
1. Open Telegram, search @BotFather
2. Send `/newbot`, follow prompts
3. Copy the bot token (format: `123456:ABC-DEF...`)

### Step 4: Configure .env
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
BITGET_API_KEY=your_api_key_here
BITGET_API_SECRET=your_secret_key_here
BITGET_API_PASSPHRASE=your_passphrase_here
DRY_RUN=true
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

To find your Telegram Chat ID: send any message to @userinfobot on Telegram.

### Step 5: Run
```bash
python bot/bot.py
```

You should see:
```
Adaptive Edge Bot started!
Paper Balance: $1000.00
Leverage: 15x
Auto-scan started (300s interval)
```

### Step 6: Use the Bot
Open your Telegram bot and send `/help` to see all commands.
Send `/scan` to manually scan the market.
The bot auto-scans every 5 minutes and opens positions automatically.

### Notes
- `DRY_RUN=true` = paper trading (no real money)
- Set `DRY_RUN=false` for live trading (real money!)
- Logs are saved to `logs/trades.jsonl`
- State (positions, balance) saved to `logs/state.json`


---

## Architecture

```
                    +------------------+
                    |  Bitget API      |
                    |  (100 pairs)     |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Data Feed        |
                    |  (OHLCV 1H/4H/15M)|
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | Market      |  | Order       |  | Fibonacci   |
     | Structure   |  | Blocks      |  | Levels      |
     +--------+---+  +------+------+  +----+--------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | Supply &    |  | Fair Value  |  | Liquidity   |
     | Demand      |  | Gaps        |  | Pools       |
     +--------+---+  +------+------+  +----+--------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | Impulse     |  | RSI + MACD  |  | Volume      |
     | System      |  |             |  | Analysis    |
     +--------+---+  +------+------+  +----+--------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | Candlestick |  | AMD         |  | Scoring     |
     | Patterns    |  | Cycle       |  | Engine      |
     +--------+---+  +------+------+  +----+--------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v---------+
                    |  Decision Engine  |
                    |  (Score >= 60?)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Risk Manager     |
                    |  (2% + 6% rule)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Executor         |
                    |  (Paper/Live)     |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v---+               +--------v---+
     | Journal     |               | Telegram    |
     | (trades.jsonl)|             | Bot (19 cmds)|
     +-------------+               +-------------+

     11 Modules Score 0-100 -> Min 60 -> Risk Check -> Entry
```


---

## 1. Idea — Why We Built This

### The Problem

Retail traders lose money because they trade against institutions. Traditional bots use lagging indicators (RSI, MACD crossovers) that react after price moves. By the time a crossover signals, institutions have already entered and taken profit.

### The Core Assumption

**Institutions leave footprints in the market before major moves.** These footprints appear as:
- **Order Blocks** — the last opposite candle before an impulsive move (where institutions placed their orders)
- **Fair Value Gaps** — price imbalances that institutions will return to fill
- **Liquidity Pools** — clusters of stop losses that institutions hunt before reversing

By reading these footprints, we can trade alongside institutions instead of against them.

### Why Only AI Can Do This

A human trader can analyze 1-3 charts at a time. An AI Agent can:
- Scan 100 pairs simultaneously every 5 minutes
- Run 11 analysis modules per pair (1,100 analyses per cycle)
- Execute in seconds when conditions align
- Never get tired, emotional, or FOMO

This is genuinely impossible for a human to replicate manually.

### Market Microstructure — Why Institutional Footprint Works

Traditional technical analysis assumes price is random. Market microstructure theory says otherwise.

**How markets actually work:**

1. **Institutions can't hide.** A $100M order can't be filled in one trade. They must accumulate over time, leaving footprints (Order Blocks).

2. **Liquidity is required.** To sell $100M, institutions need $100M in buy orders. Where are those? At stop losses (Liquidity Pools). So institutions push price TO the stops first.

3. **Price returns to imbalance.** When institutions buy aggressively, they create Fair Value Gaps (price jumps). Price almost always returns to fill these gaps.

**The chain of events:**
```
Institution wants to BUY $100M
    -> Pushes price DOWN (to trigger retail stop losses)
    -> Stop losses become THEIR buy orders (liquidity)
    -> Creates Order Block (last sell candle before reversal)
    -> Price reverses UP (their true direction)
    -> Returns to Order Block (mitigation) = OUR entry
```

### Signals Used

| Signal Type | Source | What It Tells Us |
|-------------|--------|------------------|
| Market Structure | Price action (HH/HL/LH/LL) | Trend direction |
| Order Blocks | Last candle before impulse | Where institutions placed orders |
| Fair Value Gaps | Price gaps between candles | Where price will return |
| Liquidity Pools | Equal highs/lows | Where stop losses cluster |
| Fibonacci | Swing retracement levels | Optimal entry zones |
| Elder Impulse | 13 EMA + MACD Histogram | Momentum direction |
| RSI + MACD | Standard indicators | Overbought/oversold |
| Volume | Spike detection | Confirmation of moves |
| Candlestick | Pattern recognition | Entry timing |
| S&D Zones | RBR/RBD/DBR/DBD | Supply/demand areas |
| AMD Cycle | Accumulation-Manipulation-Distribution | Market phase |

### How Decisions Are Made

```
1. Scanner fetches 100 pairs from Bitget (1H/4H/15M candles)
2. 11 modules score each pair 0-100
3. Score >= 60 + clear direction (LONG/SHORT) = candidate
4. Elder Impulse system has veto power (NEVER against HTF impulse)
5. 4 setup patterns evaluated: Turtle Soup, SH+BMS+RTO, SMS+BMS+RTO, AMD
6. Risk check: 2% per trade, 6% total, circuit breaker
7. Entry with SL + TP1 (50% partial close) + TP2 (trail)
```

### Risk Management (Elder's Methodology)

- **2% Rule** — Max 2% equity risk per trade ($20 on $1000)
- **6% Rule** — Total open risk + realized losses <= 6% equity
- **Circuit Breaker** — Stop after 2 consecutive losses
- **Partial Close** — 50% at TP1, rest trails to TP2
- **Float Sizing** — Supports fractional contracts (0.001 BTC minimum)

## 2. Progress

### What's Completed

- 11 analysis modules fully implemented
- Multi-pair scanner (100 pairs per cycle)
- Telegram bot with 19 commands
- Paper trading engine with state persistence
- Risk management (Elder 2% + 6% + circuit breaker)
- Trade journal with hackathon-compliant logging
- Float contract sizing (supports BTC, PEPE, all price ranges)
- Background auto-scan (starts on boot, stops with /stopbot)
- Live P&L tracking per position

### Development Challenges

1. **Bot blocking during scan** — Scanning 100 pairs takes 3-4 minutes, blocking all commands. Solved by running scan in background thread.

2. **TP1 repeat firing** — After TP1 hit, price staying above TP1 triggered it again. Solved by adding `tp1_hit` flag per position.

3. **State persistence** — Positions lost on bot restart. Solved by saving state to `logs/state.json` on every change.

4. **Price formatting** — PEPE ($0.00000298) displayed as $0.0000. Solved with adaptive decimal formatting.

### What's Missing / Next Steps

- Backtest engine (code exists, not yet populated with historical data)
- Live trading mode (paper trading only for hackathon)
- Dashboard visualization
- Multi-exchange support

### Tools & APIs Used

- **Bitget API** — USDT-Futures for market data + trading
- **python-telegram-bot** — Bot interface
- **Python 3.12** — Core language
- **Bitget Agent Hub** — Reference for API patterns

## 3. AI Trading Thoughts

### What We Learned

1. **AI Agents can scan infinitely** — 100 pairs x 11 modules = 1,100 analyses every 5 minutes. No human can do this.

2. **Risk management matters more than signals** — Elder's 2% + 6% rules saved us from blowing up during losing streaks.

3. **Institutional footprint > lagging indicators** — Order Blocks and FVGs give earlier entries than RSI/MACD crossovers.

### Future of Agentic Trading

AI Agents will replace manual chart analysis. The edge is in:
- Speed (scan 100 pairs in 3 minutes)
- Consistency (never deviates from rules)
- Scale (monitor 24/7 without fatigue)
- Data processing (11 modules x 100 pairs = 1,100 data points per cycle)

The human role shifts from "chart reader" to "strategy designer" — define the rules, let the Agent execute.


---

## Adaptive Edge vs Traditional Trading Bots

| Feature | Traditional Bot | Adaptive Edge |
|---------|----------------|---------------|
| **Analysis** | 1-3 indicators (RSI, MACD, EMA) | 11 modules (SMC, S&D, OB, FVG, Fib, Elder, etc.) |
| **Timeframe** | Single TF (usually 1H) | Multi-TF (4H trend + 1H structure + 15M entry) |
| **Entry Logic** | Indicator crossover (lagging) | Institutional footprint (leading) |
| **Pairs Scanned** | 5-20 hardcoded | 100 dynamic (top by volume) |
| **Risk Management** | Fixed % per trade | Elder 2% + 6% circuit breaker + partial close |
| **Exit Strategy** | Fixed TP/SL | TP1 partial (50%) + trail to TP2 |
| **Position Sizing** | Fixed amount | Formula: (Equity x 2%) / Entry - SL |
| **State Persistence** | None (lost on restart) | JSON state file (survives restarts) |
| **Monitoring** | Manual check | Telegram bot (19 commands, auto-notifications) |
| **Scoring** | Binary (buy/sell) | 0-100 composite score from 11 modules |
| **Setup Patterns** | Generic | 4 specific: Turtle Soup, SH+BMS+RTO, SMS+BMS+RTO, AMD |
| **Data Source** | Single exchange | Bitget API (USDT-Futures, 100 pairs) |
| **Automation** | Script-based | Background thread + auto-restart on boot |
| **Transparency** | Black box | Full logging (timestamp, pair, side, price, qty, balance) |

**Key differentiator:** Traditional bots react to price AFTER it moves. Adaptive Edge reads institutional footprints BEFORE the move completes.


---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| /start | Welcome + overview |
| /scan | Scan 100 pairs |
| /analyze COIN | Deep analysis |
| /positions | Open positions |
| /balance | Account balance |
| /trades | Recent trades |
| /performance | Win rate & P&L |
| /daily | Today summary |
| /pnl | P&L breakdown |
| /risk | Risk exposure |
| /top | Top coins by score |
| /live | Live P&L per position |
| /close COIN | Close position |
| /closeall | Close all |
| /status | Bot status |
| /settings | Config |
| /startbot | Start auto-scan |
| /stopbot | Stop auto-scan |
| /help | All commands |

## Risk Management

- 2% Rule — Max 2% equity per trade
- 6% Rule — Total risk + losses <= 6% equity
- Circuit Breaker — Stop after 2 consecutive losses
- Partial Close — 50% at TP1, trail to TP2
- Float Sizing — 0.001 minimum contract

## Data Source

All via **Bitget API** (USDT-Futures):
- Public endpoints for market data (no auth)
- Authenticated endpoints for trading
- 100 pairs scanned per cycle

## Paper Trading Logs

Logged to `logs/trades.jsonl`:
- timestamp, pair, side, price, size, balance_before, balance_after
- type: ENTRY / EXIT_TP1 / EXIT_TP2 / EXIT_SL

## State Persistence

Bot state saved to `logs/state.json`. Positions survive restarts.

## Scoring System

Each module: 0-18 points. Total capped at 100. Min 60 for entry.

| Module | Max Score | Module | Max Score |
|--------|-----------|--------|-----------|
| Market Structure | 18 | Fibonacci | 12 |
| Supply & Demand | 12 | Impulse System | 10 |
| Order Blocks | 10 | RSI + MACD | 10 |
| Fair Value Gap | 8 | AMD Cycle | 10 |
| Liquidity | 8 | Candlestick | 10 |
| Volume | 8 | | |

## Project Structure

```
adaptive-edge/
+-- config.yaml          # Trading parameters
+-- .env.example         # API credentials template
+-- core/
|   +-- scanner.py       # 11-module analysis engine
|   +-- decision.py      # Scoring + entry logic
|   +-- executor.py      # Paper/Live execution + state persistence
|   +-- risk_manager.py  # Elder's risk rules
|   +-- journal.py       # Trade logging + performance
+-- analysis/            # 11 analysis modules
+-- data/
|   +-- bitget_market.py # Bitget public market data
|   +-- bitget_feed.py   # Bitget authenticated API
+-- bot/
|   +-- bot.py           # Telegram bot (19 commands)
+-- strategies/          # Trading setups
+-- backtest/            # Backtesting engine
+-- logs/                # Trade logs + state (not in repo)
```

## Tech Stack

- **Python 3.12**
- **Bitget API** (USDT-Futures)
- **python-telegram-bot**
- **Custom 11-module analysis engine**
- **Elder's risk methodology**
- **JSON state persistence**

## License

MIT
