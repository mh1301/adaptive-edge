"""
Trade Journal — Logging, performance tracking, trade records.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional


TRADES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "trades.jsonl")
PERFORMANCE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "performance.json")


def log_trade(trade: Dict):
    """Append a trade record to trades.jsonl.
    
    Required fields:
        timestamp, pair, side, price, size, balance_before, balance_after, type
    """
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    
    # Ensure timestamp
    if "timestamp" not in trade:
        trade["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")


def get_trades(limit: int = 50) -> List[Dict]:
    """Read recent trades from log."""
    if not os.path.exists(TRADES_FILE):
        return []
    
    trades = []
    with open(TRADES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    trades.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    return trades[-limit:]


def calculate_performance(trades: List[Dict] = None) -> Dict:
    """Calculate performance metrics from trade log."""
    if trades is None:
        trades = get_trades(1000)
    
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "best_trade": 0,
            "worst_trade": 0,
        }
    
    # Group trades by entry/exit pairs
    entries = {}
    exits = []
    
    for t in trades:
        ttype = t.get("type", "")
        symbol = t.get("pair", "") or t.get("symbol", "")
        
        if ttype == "ENTRY":
            entries[symbol] = t
        elif ttype in ("EXIT_TP1", "EXIT_TP2", "EXIT_SL", "EXIT_MANUAL"):
            exits.append(t)
    
    # Calculate P&L per completed trade
    pnls = []
    for exit_trade in exits:
        pnl = exit_trade.get("pnl", 0)
        if pnl != 0:
            pnls.append(pnl)
        else:
            # Fallback: calculate from balance diff
            symbol = exit_trade.get("pair", "") or exit_trade.get("symbol", "")
            entry = entries.get(symbol)
            if entry:
                pnl = exit_trade.get("balance_after", 0) - entry.get("balance_after", entry.get("balance_before", 0))
                pnls.append(pnl)
    
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")
    
    # Max drawdown
    running = 0
    peak = 0
    max_dd = 0
    for pnl in pnls:
        running += pnl
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)
    
    return {
        "total_trades": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd, 2),
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
    }


def save_performance(performance: Dict):
    """Save performance summary to file."""
    os.makedirs(os.path.dirname(PERFORMANCE_FILE), exist_ok=True)
    performance["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(performance, f, indent=2)


def format_trade_log(trade: Dict) -> str:
    """Format a single trade for display."""
    ttype = trade.get("type", "UNKNOWN")
    symbol = trade.get("pair", trade.get("symbol", "?"))
    side = trade.get("side", "?")
    price = trade.get("price", 0)
    size = trade.get("size", 0)
    balance = trade.get("balance_after", 0)
    
    emoji = {"ENTRY": "🔵", "EXIT_TP1": "🎯", "EXIT_TP2": "🏆", "EXIT_SL": "❌", "EXIT_MANUAL": "⏹️"}.get(ttype, "⚪")
    
    return f"{emoji} {ttype} | {symbol} {side} @ ${price:.4f} | Size: {size} | Balance: ${balance:.2f}"


def format_performance(perf: Dict) -> str:
    """Format performance summary for display."""
    return (
        f"📊 PERFORMANCE SUMMARY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Trades: {perf['total_trades']}\n"
        f"Wins: {perf['wins']} | Losses: {perf['losses']}\n"
        f"Win Rate: {perf['win_rate']}%\n"
        f"Total P&L: ${perf['total_pnl']:+.2f}\n"
        f"Avg Win: ${perf['avg_win']:+.2f} | Avg Loss: ${perf['avg_loss']:+.2f}\n"
        f"Profit Factor: {perf['profit_factor']}\n"
        f"Max Drawdown: ${perf['max_drawdown']:.2f}\n"
        f"Best Trade: ${perf['best_trade']:+.2f}\n"
        f"Worst Trade: ${perf['worst_trade']:+.2f}"
    )
