# Adaptive Edge - AI Crypto Trading Agent

**Bitget Base Camp Hackathon S1 - Track 1: Trading Agent**

An AI trading agent that combines Smart Money Concepts (SMC), Elder's Triple Screen System, and an 11-module scoring engine to autonomously perceive market conditions, make trading decisions, and execute trades.

## Thesis

Traditional trading bots rely on lagging indicators (RSI, MACD crossovers) that react to price after the move. Adaptive Edge reads **institutional footprint** patterns - Order Blocks, Fair Value Gaps, Liquidity pools - to anticipate where institutions will trade, and enters alongside them.

### What Makes This Different

| Feature | Traditional Bot | Adaptive Edge |
|---------|----------------|---------------|
| Analysis | Single indicator | 11-module scoring system |
| Timeframe | Single TF | Multi-TF (HTF trend + LTF entry) |
| Entry Logic | Crossover signals | Institutional footprint (OB, FVG, S&D) |
| Risk Management | Fixed % | Elder 2% + 6% circuit breaker |
| Setups | Generic | Specific patterns (Turtle Soup, SH+BMS+RTO) |

## Architecture

```
Perceive (Market Data) -> Think (11 Modules) -> Decide (Scoring + Risk) -> Execute (Bitget API) -> Learn (Journal)
```

### 11 Analysis Modules

1. **Market Structure** - Swing H/L, HH/HL/LH/LL, BMS, CHoCH
2. **Supply & Demand** - RBR, RBD, DBR, DBD zone detection
3. **Order Blocks** - Institutional footprint (last opposite candle before impulse)
4. **Fair Value Gap** - Gap detection and POI marking
5. **Liquidity** - Equal H/L, BSL/SSL pool detection
6. **Fibonacci** - Retracement levels, OTE zone (0.618-0.705)
7. **Impulse System** - Elder's 13 EMA + MACD Histogram (GREEN/RED/BLUE)
8. **Candlestick Patterns** - Engulfing, Hammer, Doji, Morning/Evening Star
9. **Volume Analysis** - Spike detection, trend confirmation
10. **RSI + MACD** - Overbought/oversold, divergence
11. **AMD Cycle** - Accumulation-Manipulation-Distribution detection

### Trading Setups

- **Turtle Soup** - False breakout 5-20 pips above/below liquidity, reverse
- **SH + BMS + RTO** - Stop Hunt -> Break Market Structure -> Return to Order Block
- **SMS + BMS + RTO** - Failure Swing -> BMS -> Return to OB
- **AMD Distribution** - Entry during distribution phase

## Quick Start

### 1. Install Dependencies

```bash
cd adaptive-edge
pip install -r requirements.txt
```

### 2. Configure

Edit `.env` with your credentials:
```
BITGET_API_KEY=your_key
BITGET_API_SECRET=your_secret
BITGET_API_PASSPHRASE=your_passphrase
TELEGRAM_BOT_TOKEN=your_bot_token
```

Edit `config.yaml` for trading parameters.

### 3. Run Telegram Bot

```bash
python bot/bot.py
```

### 4. Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + status |
| `/scan` | Scan market for opportunities |
| `/analyze SOLUSDT` | Deep analysis of a coin |
| `/positions` | Open positions |
| `/balance` | Account balance |
| `/trades` | Recent trades |
| `/performance` | Performance stats |
| `/startbot` | Start auto-scanning |
| `/stopbot` | Stop auto-scanning |
| `/settings` | Current config |

### 5. Run Backtest

```bash
python backtest/engine.py
```

## Risk Management

Based on Dr. Alexander Elder's trading methodology:

- **2% Rule** - Max 2% equity risk per trade
- **6% Rule** - Total open risk + realized losses <= 6% equity
- **Circuit Breaker** - Stop after 2 consecutive losses
- **Position Sizing** - `(Equity x 2%) / |Entry - SL|`
- **Partial Close** - 50% at TP1, rest trails to TP2

## Project Structure

```
adaptive-edge/
+-- config.yaml          # Trading parameters
+-- .env                 # API credentials (not committed)
+-- core/
|   +-- scanner.py       # 11-module analysis engine
|   +-- decision.py      # Scoring + entry logic
|   +-- executor.py      # Paper/Live execution
|   +-- risk_manager.py  # Elder's risk rules
|   +-- journal.py       # Trade logging
+-- analysis/            # 11 analysis modules
+-- strategies/          # Trading setups
+-- data/                # Binance + Bitget feeds
+-- bot/                 # Telegram bot
+-- backtest/            # Backtesting engine
+-- logs/                # Trade logs (trades.jsonl)
```

## Paper Trading Logs

All trades are logged to `logs/trades.jsonl` with the format:

```json
{"timestamp": "2026-06-17T14:30:00Z", "pair": "SOLUSDT", "side": "LONG", "price": 145.50, "size": 1, "balance_before": 1000.00, "balance_after": 1000.00, "type": "ENTRY"}
{"timestamp": "2026-06-17T16:45:00Z", "pair": "SOLUSDT", "side": "LONG", "price": 152.00, "size": 1, "balance_before": 1000.00, "balance_after": 1002.50, "type": "EXIT_TP1", "pnl": 2.50}
```

## Tech Stack

- **Python 3.12**
- **Data**: Binance API (public) + Bitget API (authenticated)
- **Bot**: python-telegram-bot
- **Analysis**: Custom 11-module engine
- **Risk**: Elder's methodology
- **Storage**: JSON files

## Scoring System

Each module contributes 0-15 points. Total capped at 100.

| Module | Max Score | Weight |
|--------|-----------|--------|
| Market Structure | 18 | 15 |
| Supply & Demand | 12 | 12 |
| Fibonacci | 12 | 12 |
| Impulse System | 10 | 10 |
| RSI + MACD | 10 | 10 |
| AMD Cycle | 10 | 10 |
| Order Blocks | 10 | 10 |
| Candlestick | 10 | 10 |
| Volume | 8 | 8 |
| Liquidity | 8 | 8 |
| Fair Value Gap | 8 | 8 |

**Minimum score for entry: 60/100**
**Direction must be clear (LONG or SHORT) - NEUTRAL = skip**

## License

MIT
