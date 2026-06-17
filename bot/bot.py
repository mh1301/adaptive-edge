"""
Telegram Bot - Monitoring, notifications, and command interface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import threading
import json
from datetime import datetime, timezone
from typing import Dict, List

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

from core import scanner, decision, journal, risk_manager
from core.executor import PaperTrader
from data import binance_feed

load_dotenv()

# Global state
paper_trader: PaperTrader = None
config: Dict = {}
running_scan: bool = False


def load_config() -> Dict:
    """Load config from config.yaml."""
    import yaml
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


# ─── Command Handlers ────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    status = paper_trader.get_status()
    msg = (
        f"🤖 **ADAPTIVE EDGE** - AI Crypto Trading Agent\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance: ${status['balance']:.2f}\n"
        f"📈 Total P&L: ${status['total_pnl']:+.2f} ({status['total_pnl_pct']:+.1f}%)\n"
        f"📊 Open Positions: {status['open_positions']}\n"
        f"⚡ Leverage: {status['leverage']}x\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Commands:\n"
        f"/scan - Scan market for opportunities\n"
        f"/analyze <SYMBOL> - Deep analysis\n"
        f"/positions - Open positions\n"
        f"/balance - Account balance\n"
        f"/trades - Recent trades\n"
        f"/performance - Performance stats\n"
        f"/startbot - Start auto-scanning\n"
        f"/stopbot - Stop auto-scanning\n"
        f"/settings - Current config"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scan market for top opportunities."""
    await update.message.reply_text("🔍 Scanning market... This may take a minute.")
    
    try:
        # Get top pairs
        pairs = config.get("pairs", {})
        symbols = pairs.get("majors", []) + pairs.get("midcaps", []) + pairs.get("memes", [])
        
        # Scan in thread to avoid blocking
        def do_scan():
            return scanner.scan_multiple(
                symbols,
                config["scanner"]["candle_limits"],
                config["scanner"]["min_score"],
            )
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, do_scan)
        
        if not results:
            await update.message.reply_text("❌ No high-score opportunities found.")
            return
        
        # Format results
        msg = f"📊 **SCAN RESULTS** - {len(results)} opportunities\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, r in enumerate(results[:10], 1):
            # Adaptive decimal places based on price magnitude
            def fmt(p):
                if p == 0: return "$0.00"
                if p < 0.0001: return f"${p:.8f}"
                if p < 0.01: return f"${p:.6f}"
                if p < 1: return f"${p:.4f}"
                return f"${p:.2f}"
            msg += (
                f"**{i}. {r['symbol']}** - Score: {r['score']}/100\n"
                f"   Direction: {r['direction']} | Price: {fmt(r['current_price'])}\n"
                f"   Entry: {fmt(r['entry_zone']['low'])} - {fmt(r['entry_zone']['high'])}\n"
                f"   SL: {fmt(r['sl'])} | TP1: {fmt(r['tp1'])}\n"
                f"   RR: 1:{r['rr']} | Impulse: {r.get('impulse_direction', 'N/A')}\n\n"
            )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Scan error: {e}")


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deep analysis of a specific symbol."""
    if not context.args:
        await update.message.reply_text("Usage: /analyze SOLUSDT")
        return
    
    symbol = context.args[0].upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"
    
    await update.message.reply_text(f"🔍 Analyzing {symbol}...")
    
    try:
        result = scanner.analyze_single(symbol, config["scanner"]["candle_limits"])
        
        modules = result.get("modules", {})
        msg = (
            f"📊 **{symbol}** - Deep Analysis\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${result['current_price']:.4f}\n"
            f"📈 Score: {result['score']}/100\n"
            f"➡️ Direction: {result['direction']}\n"
            f"⚡ Impulse: {result.get('impulse_direction', 'N/A')}\n\n"
            f"**Module Scores:**\n"
        )
        
        for name, data in modules.items():
            score = data.get('score', 0)
            direction = data.get('direction', 'N/A')
            msg += f"• {name}: {score} | {direction}\n"
        
        def fmt(p):
            if p == 0: return "$0.00"
            if p < 0.0001: return f"${p:.8f}"
            if p < 0.01: return f"${p:.6f}"
            if p < 1: return f"${p:.4f}"
            return f"${p:.2f}"
        msg += (
            f"\n**Setup:**\n"
            f"Entry: {fmt(result['entry_zone']['low'])} - {fmt(result['entry_zone']['high'])}\n"
            f"SL: {fmt(result['sl'])}\n"
            f"TP1: {fmt(result['tp1'])} | TP2: {fmt(result['tp2'])}\n"
            f"RR: 1:{result['rr']}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Analysis error: {e}")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open positions."""
    status = paper_trader.get_status()
    
    if not status["positions"]:
        await update.message.reply_text("📭 No open positions.")
        return
    
    msg = f"📊 **OPEN POSITIONS** - {len(status['positions'])}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    def _fmt(p):
        if p == 0: return "$0.00"
        if p < 0.0001: return f"${p:.8f}"
        if p < 0.01: return f"${p:.6f}"
        if p < 1: return f"${p:.4f}"
        return f"${p:.2f}"
    for pos in status["positions"]:
        msg += (
            f"**{pos['symbol']}** {pos['direction']}\n"
            f"Entry: {_fmt(pos['entry_price'])} | Size: {pos['size']}\n"
            f"SL: {_fmt(pos['sl'])} | TP1: {_fmt(pos['tp1'])}\n"
            f"Score: {pos['score']} | Setup: {pos['setup']}\n\n"
        )
    
    msg += f"💰 Balance: ${status['balance']:.2f} | Margin Used: ${status['total_margin']:.2f}"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show account balance."""
    status = paper_trader.get_status()
    risk = status["risk_status"]
    
    msg = (
        f"💰 **ACCOUNT BALANCE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Balance: ${status['balance']:.2f}\n"
        f"Initial: ${status['initial_balance']:.2f}\n"
        f"P&L: ${status['total_pnl']:+.2f} ({status['total_pnl_pct']:+.1f}%)\n"
        f"Open Positions: {status['open_positions']}\n"
        f"Margin Used: ${status['total_margin']:.2f}\n"
        f"Leverage: {status['leverage']}x\n\n"
        f"**Risk Status:**\n"
        f"Daily P&L: ${risk['daily_pnl']:+.2f}\n"
        f"Consecutive Losses: {risk['consecutive_losses']}\n"
        f"Can Trade: {'✅' if risk['can_trade'] else '❌'} {risk['reason']}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent trades."""
    trades = journal.get_trades(10)
    
    if not trades:
        await update.message.reply_text("📭 No trades yet.")
        return
    
    msg = "📋 **RECENT TRADES**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in trades[-10:]:
        msg += journal.format_trade_log(t) + "\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show performance stats."""
    perf = journal.calculate_performance()
    msg = journal.format_performance(perf)
    await update.message.reply_text(f"```\n{msg}\n```", parse_mode="Markdown")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current config."""
    trading = config.get("trading", {})
    risk = config.get("risk", {})
    scanner_cfg = config.get("scanner", {})
    
    msg = (
        f"⚙️ **SETTINGS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Leverage: {trading.get('leverage', 15)}x\n"
        f"Entry per trade: {trading.get('entry_per_trade_pct', 2)}%\n"
        f"Max positions: {trading.get('max_positions', 3)}\n"
        f"Min RR: 1:{trading.get('min_rr', 2.5)}\n"
        f"Max daily loss: {risk.get('max_daily_loss_pct', 6)}%\n"
        f"Min score: {scanner_cfg.get('min_score', 60)}/100\n"
        f"Scan interval: {scanner_cfg.get('scan_interval_seconds', 300)}s\n"
        f"Paper balance: ${trading.get('paper_balance', 1000)}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ─── Auto-Scan Background Task ───────────────────────

async def auto_scan_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task for auto-scanning."""
    global running_scan
    
    if not running_scan:
        return
    
    chat_id = context.job.chat_id
    
    try:
        pairs = config.get("pairs", {})
        symbols = pairs.get("majors", []) + pairs.get("midcaps", []) + pairs.get("memes", [])
        
        results = scanner.scan_multiple(symbols, config["scanner"]["candle_limits"], config["scanner"]["min_score"])
        
        if results:
            # Evaluate signals
            signals = decision.evaluate_batch(
                results, config,
                paper_trader.positions,
                paper_trader.risk_mgr.daily_pnl,
            )
            
            for signal in signals:
                # Open paper trade
                trade = paper_trader.open_position(signal)
                
                if trade.get("status") != "REJECTED":
                    def _fmt(p):
                        if p == 0: return "$0.00"
                        if p < 0.0001: return f"${p:.8f}"
                        if p < 0.01: return f"${p:.6f}"
                        if p < 1: return f"${p:.4f}"
                        return f"${p:.2f}"
                    msg = (
                        f"✅ **ORDER FILLED** - {signal.symbol} {signal.direction}\n"
                        f"Entry: {_fmt(signal.entry_price)}\n"
                        f"SL: {_fmt(signal.sl)} | TP1: {_fmt(signal.tp1)} | TP2: {_fmt(signal.tp2)}\n"
                        f"RR: 1:{signal.rr} | Score: {signal.score}/100\n"
                        f"Size: {signal.size} | Setup: {signal.setup_type}\n"
                        f"Balance: ${paper_trader.balance:.2f}"
                    )
                    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        
        # Check exits
        if paper_trader.positions:
            prices = {}
            for pos in paper_trader.positions:
                price = binance_feed.get_price(pos["symbol"])
                if price:
                    prices[pos["symbol"]] = price
            
            exits = paper_trader.check_exits(prices)
            for exit_trade in exits:
                emoji = "🎯" if "TP" in exit_trade["type"] else "❌"
                msg = (
                    f"{emoji} **{exit_trade['type']}** - {exit_trade['pair']} {exit_trade['side']}\n"
                    f"Entry: ${exit_trade.get('entry_price', 0):.4f} → Exit: ${exit_trade['price']:.4f}\n"
                    f"P&L: ${exit_trade.get('pnl', 0):+.2f}\n"
                    f"Balance: ${exit_trade['balance_after']:.2f}"
                )
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
    
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Auto-scan error: {e}")


async def cmd_startbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start auto-scanning."""
    global running_scan
    
    # Prevent duplicate jobs
    existing = context.job_queue.get_jobs_by_name("auto_scan")
    if existing:
        await update.message.reply_text("⚠️ Auto-scan already running! Use /stopbot first.")
        return
    
    running_scan = True
    
    interval = config.get("scanner", {}).get("scan_interval_seconds", 300)
    context.job_queue.run_repeating(
        auto_scan_task,
        interval=interval,
        first=5,
        chat_id=update.effective_chat.id,
        name="auto_scan",
    )
    
    await update.message.reply_text(f"🤖 Auto-scan started! Interval: {interval}s")




async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close a specific position."""
    if not context.args:
        await update.message.reply_text("Usage: /close SOLUSDT")
        return
    symbol = context.args[0].upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"
    found = any(p["symbol"] == symbol for p in paper_trader.positions)
    if not found:
        await update.message.reply_text(f"No open position for {symbol}")
        return
    price = binance_feed.get_price(symbol)
    if not price:
        await update.message.reply_text(f"Can't get price for {symbol}")
        return
    result = paper_trader.close_position(symbol, price)
    if result:
        emoji = "TP" in result["type"] and "🎯" or "❌"
        msg = (
            f"{emoji} **CLOSED** - {symbol} {result['side']}\n"
            f"Entry: ${result['entry_price']:.4f} -> Exit: ${result['price']:.4f}\n"
            f"P&L: ${result['pnl']:+.2f}\n"
            f"Balance: ${result['balance_after']:.2f}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Failed to close {symbol}")

async def cmd_closeall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close all open positions."""
    if not paper_trader.positions:
        await update.message.reply_text("No open positions to close.")
        return
    prices = {}
    for pos in paper_trader.positions:
        p = binance_feed.get_price(pos["symbol"])
        if p:
            prices[pos["symbol"]] = p
    closed = paper_trader.close_all(prices)
    if closed:
        total_pnl = sum(c["pnl"] for c in closed)
        msg = f"**CLOSED ALL** - {len(closed)} positions\n\n"
        for c in closed:
            msg += f"{c['pair']}: ${c['pnl']:+.2f}\n"
        msg += f"\n**Total P&L: ${total_pnl:+.2f}**\nBalance: ${paper_trader.balance:.2f}"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("Failed to close positions.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot status overview."""
    status = paper_trader.get_status()
    perf = journal.calculate_performance()
    risk = status["risk_status"]
    scan_status = "Running" if running_scan else "Stopped"
    interval = config.get("scanner", {}).get("scan_interval_seconds", 300)
    pairs = sum(len(v) for v in config.get("pairs", {}).values())
    msg = (
        f"**BOT STATUS**\n"
        f"Scanner: {scan_status} ({interval//60}min)\n"
        f"Pairs: {pairs} | Min Score: {config['scanner']['min_score']}\n\n"
        f"Balance: ${status['balance']:.2f}\n"
        f"Positions: {status['open_positions']}/{config['trading']['max_positions']}\n"
        f"Margin: ${status['total_margin']:.2f}\n\n"
        f"Trades: {perf['total_trades']} | WR: {perf['win_rate']}%\n"
        f"Total P&L: ${perf['total_pnl']:+.2f}\n\n"
        f"Risk: {'OK' if risk['can_trade'] else 'BLOCKED - ' + risk['reason']}\n"
        f"Daily P&L: ${risk['daily_pnl']:+.2f} | Losses: {risk['consecutive_losses']}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all commands."""
    msg = (
        f"**COMMANDS**\n"
        f"/start - Overview\n"
        f"/scan - Scan market\n"
        f"/analyze COIN - Deep analysis\n"
        f"/positions - Open positions\n"
        f"/balance - Account balance\n"
        f"/trades - Recent trades\n"
        f"/performance - Stats\n"
        f"/daily - Today summary\n"
        f"/pnl - P&L breakdown\n"
        f"/risk - Risk exposure\n"
        f"/top - Top coins\n"
        f"/close COIN - Close position\n"
        f"/closeall - Close all\n"
        f"/status - Bot status\n"
        f"/settings - Config\n"
        f"/startbot - Start auto-scan\n"
        f"/stopbot - Stop auto-scan\n"
        f"/help - This message"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily summary."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trades = journal.get_trades(1000)
    today_trades = [t for t in trades if t.get("timestamp", "").startswith(today)]
    entries = [t for t in today_trades if t["type"] == "ENTRY"]
    exits = [t for t in today_trades if "EXIT" in t["type"]]
    wins = sum(1 for t in exits if t.get("pnl", 0) > 0)
    losses = sum(1 for t in exits if t.get("pnl", 0) < 0)
    total_pnl = sum(t.get("pnl", 0) for t in exits)
    wr = (wins / len(exits) * 100) if exits else 0
    msg = (
        f"**DAILY - {today}**\n"
        f"Entries: {len(entries)}\n"
        f"Exits: {len(exits)} ({wins}W / {losses}L)\n"
        f"Win Rate: {wr:.1f}%\n"
        f"Realized P&L: ${total_pnl:+.2f}\n"
        f"Open: {len(paper_trader.positions)}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """P&L breakdown."""
    perf = journal.calculate_performance()
    status = paper_trader.get_status()
    prices = {}
    for pos in paper_trader.positions:
        p = binance_feed.get_price(pos["symbol"])
        if p:
            prices[pos["symbol"]] = p
    unrealized = paper_trader.get_unrealized_pnl(prices)
    total = perf["total_pnl"] + unrealized
    msg = (
        f"**P&L BREAKDOWN**\n"
        f"Realized: ${perf['total_pnl']:+.2f} ({perf['total_trades']} trades)\n"
        f"Unrealized: ${unrealized:+.2f} ({len(paper_trader.positions)} pos)\n"
        f"\n**Total: ${total:+.2f}**\n"
        f"Balance: ${status['balance']:.2f} | Margin: ${status['total_margin']:.2f}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risk exposure."""
    status = paper_trader.get_status()
    risk = status["risk_status"]
    max_pos = config["trading"]["max_positions"]
    max_loss_pct = config["risk"]["max_daily_loss_pct"]
    margin_pct = (status["total_margin"] / status["balance"] * 100) if status["balance"] > 0 else 0
    msg = (
        f"**RISK EXPOSURE**\n"
        f"Positions: {status['open_positions']}/{max_pos}\n"
        f"Margin: ${status['total_margin']:.2f} ({margin_pct:.1f}%)\n"
        f"Leverage: {config['trading']['leverage']}x\n"
        f"Daily Limit: {max_loss_pct}% (${status['balance'] * max_loss_pct / 100:.2f})\n"
        f"Daily P&L: ${risk['daily_pnl']:+.2f}\n"
        f"Losses: {risk['consecutive_losses']}/{config['risk']['circuit_breaker_losses']}\n"
        f"Can Trade: {'YES' if risk['can_trade'] else 'NO - ' + risk['reason']}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top coins by score."""
    await update.message.reply_text("Scanning top coins...")
    try:
        pairs = config.get("pairs", {})
        symbols = pairs.get("majors", []) + pairs.get("midcaps", []) + pairs.get("memes", [])
        def do_scan():
            return scanner.scan_multiple(symbols, config["scanner"]["candle_limits"], 50)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, do_scan)
        if not results:
            await update.message.reply_text("No coins scored above 50.")
            return
        def fmt(p):
            if p == 0: return "$0.00"
            if p < 0.0001: return f"${p:.8f}"
            if p < 0.01: return f"${p:.6f}"
            if p < 1: return f"${p:.4f}"
            return f"${p:.2f}"
        msg = f"**TOP COINS** - {len(results)} above 50\n\n"
        for i, r in enumerate(results[:5], 1):
            msg += f"**{i}. {r['symbol']}** - {r['score']}/100 {r['direction']} | {fmt(r['current_price'])}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_stopbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop auto-scanning."""
    global running_scan
    running_scan = False
    
    current_jobs = context.job_queue.get_jobs_by_name("auto_scan")
    for job in current_jobs:
        job.schedule_removal()
    
    await update.message.reply_text("⏹️ Auto-scan stopped.")


# ─── Main ────────────────────────────────────────────

def main():
    """Start the bot."""
    global paper_trader, config
    
    config = load_config()
    paper_trader = PaperTrader(
        initial_balance=config["trading"]["paper_balance"],
        leverage=config["trading"]["leverage"],
    )
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    # Build application
    app = Application.builder().token(token).build()
    
    # Register commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("performance", cmd_performance))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("closeall", cmd_closeall))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("startbot", cmd_startbot))
    app.add_handler(CommandHandler("stopbot", cmd_stopbot))
    
    print("🤖 Adaptive Edge Bot started!")
    print(f"   Paper Balance: ${paper_trader.balance:.2f}")
    print(f"   Leverage: {paper_trader.leverage}x")
    
    app.run_polling()


if __name__ == "__main__":
    main()
