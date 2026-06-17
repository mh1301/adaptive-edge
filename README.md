# Adaptive Edge — AI Crypto Trading Agent

**Bitget Base Camp Hackathon S1 — Track 1: Trading Agent**

An AI trading agent that combines Smart Money Concepts (SMC), Elder's Triple Screen System, and an 11-module scoring engine to autonomously perceive market conditions, make trading decisions, and execute trades on Bitget.

## Thesis

Traditional trading bots rely on lagging indicators (RSI, MACD crossovers) that react to price after the move. Adaptive Edge reads **institutional footprint** patterns — Order Blocks, Fair Value Gaps, Liquidity pools — to anticipate where institutions will trade, and enters alongside them.

| Feature | Traditional Bot | Adaptive Edge |
|---------|----------------|---------------|
| Analysis | Single indicator | 11-module scoring system |
| Timeframe | Single TF | Multi-TF (HTF trend + LTF entry) |
| Entry Logic | Crossover signals | Institutional footprint (OB, FVG, S&D) |
| Risk Management | Fixed % | Elder 2% + 6% circuit breaker |
| Setups | Generic | 4 specific patterns |

## Architecture

```
Perceive (Bitget Market Data)
    → Think (11 Analysis Modules)
        → Decide (Scoring + Risk Check)
            → Execute (Paper/Live Trading)
                → Learn (Journal + Performance)
```

### 11 Analysis Modules

1. **Market Structure** — Swing H/L, HH/HL/LH/LL, BMS, CHoCH
2. **Supply & Demand** — RBR, RBD, DBR, DBD zone detection
3. **Order Blocks** — Institutional footprint (last opposite candle before impulse)
4. **Fair Value Gap** — Gap detection and POI marking
5. **Liquidity** — Equal H/L, BSL/SSL pool detection
6. **Fibonacci** — Retracement levels, OTE zone (0.618-0.705)
7. **Impulse System** — Elder's 13 EMA + MACD Histogram (GREEN/RED/BLUE)
8. **Candlestick Patterns** — Engulfing, Hammer, Doji, Morning/Evening Star
9. **Volume Analysis** — Spike detection, trend confirmation
10. **RSI + MACD** — Overbought/oversold, divergence
11. **AMD Cycle** — Accumulation-Manipulation-Distribution detection

### Trading Setups

- **Turtle Soup** — False breakout 5-20 pips above/below liquidity, reverse
- **SH + BMS + RTO** — Stop Hunt -> Break Market Structure -> Return to Order Block
- **SMS + BMS + RTO** — Failure Swing -> BMS -> Return to OB
- **AMD Distribution** — Entry during distribution phase

## Quick Start

### 1. Install

```bash
cd adaptive-edge
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Bitget API keys and Telegram bot token
```

### 3. Run

```bash
python bot/bot.py
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + overview |
| `/scan` | Scan 100 pairs for opportunities |
| `/analyze <COIN>` | Deep analysis of a coin |
| `/positions` | Open positions |
| `/balance` | Account balance |
| `/trades` | Recent trades |
| `/performance` | Win rate & P&L stats |
| `/daily` | Today's summary |
| `/pnl` | P&L breakdown (realized vs unrealized) |
| `/risk` | Risk exposure |
| `/top` | Top coins by score |
| `/close <COIN>` | Close a position |
| `/closeall` | Close all positions |
| `/status` | Bot status |
| `/settings` | Current config |
| `/startbot` | Start auto-scanning |
| `/stopbot` | Stop auto-scanning |
| `/help` | List all commands |

## Risk Management

Based on Dr. Alexander Elder's trading methodology:

- **2% Rule** — Max 2% equity risk per trade
- **6% Rule** — Total open risk + realized losses <= 6% equity
- **Circuit Breaker** — Stop after 2 consecutive losses
- **Position Sizing** — `(Equity x 2%) / |Entry - SL|`
- **Partial Close** — 50% at TP1, rest trails to TP2

## Data Source

All market data and trading via **Bitget API** (USDT-Futures):
- Public endpoints for market data (no auth)
- Authenticated endpoints for trading
- 100 pairs scanned per cycle

## Paper Trading Logs

All trades logged to `logs/trades.jsonl`:

```json
{"timestamp": "2026-06-17T14:30:00Z", "pair": "SOLUSDT", "side": "LONG", "price": 73.50, "size": 4, "balance_before": 1000.0, "balance_after": 1000.0, "type": "ENTRY"}
{"timestamp": "2026-06-17T16:45:00Z", "pair": "SOLUSDT", "side": "LONG", "price": 80.00, "size": 2, "balance_before": 1000.0, "balance_after": 1014.0, "type": "EXIT_TP1", "pnl": 14.0}
```

## State Persistence

Bot state (positions, balance, risk) saved to `logs/state.json`. Positions survive restarts.

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
|   +-- binance_feed.py  # Bitget public market data
|   +-- bitget_feed.py   # Bitget authenticated API
+-- bot/
|   +-- bot.py           # Telegram bot (18 commands)
+-- strategies/          # Trading setups
+-- backtest/            # Backtesting engine
+-- logs/                # Trade logs + state (not in repo)
```

## Scoring System

Each module contributes 0-18 points. Total capped at 100.

| Module | Max Score | Module | Max Score |
|--------|-----------|--------|-----------|
| Market Structure | 18 | Fibonacci | 12 |
| Supply & Demand | 12 | Impulse System | 10 |
| Order Blocks | 10 | RSI + MACD | 10 |
| Fair Value Gap | 8 | AMD Cycle | 10 |
| Liquidity | 8 | Candlestick | 10 |
| Volume | 8 | | |

**Minimum score for entry: 60/100**
**Direction must be clear (LONG or SHORT) — NEUTRAL = skip**

## Tech Stack

- **Python 3.12**
- **Data + Trading**: Bitget API (USDT-Futures)
- **Bot**: python-telegram-bot
- **Analysis**: Custom 11-module engine
- **Risk**: Elder's methodology
- **Storage**: JSON files + state persistence

## License

MIT
