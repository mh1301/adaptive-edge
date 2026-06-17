"""
Telegram Bot - Monitoring, notifications, and command interface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
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
        
        # Scan
        results = scanner.scan_multiple(
            symbols,
            config["scanner"]["candle_limits"],
            config["scanner"]["min_score"],
        )
        
        if not results:
            await update.message.reply_text("❌ No high-score opportunities found.")
            return
        
        # Format results
        msg = f"📊 **SCAN RESULTS** - {len(results)} opportunities\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, r in enumerate(results[:5], 1):
            msg += (
                f"**{i}. {r['symbol']}** - Score: {r['score']}/100\n"
                f"   Direction: {r['direction']} | Price: ${r['current_price']:.4f}\n"
                f"   Entry: ${r['entry_zone']['low']:.4f} - ${r['entry_zone']['high']:.4f}\n"
                f"   SL: ${r['sl']:.4f} | TP1: ${r['tp1']:.4f}\n"
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
        
        msg += (
            f"\n**Setup:**\n"
            f"Entry: ${result['entry_zone']['low']:.4f} - ${result['entry_zone']['high']:.4f}\n"
            f"SL: ${result['sl']:.4f}\n"
            f"TP1: ${result['tp1']:.4f} | TP2: ${result['tp2']:.4f}\n"
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
    
    for pos in status["positions"]:
        msg += (
            f"**{pos['symbol']}** {pos['direction']}\n"
            f"Entry: ${pos['entry_price']:.4f} | Size: {pos['size']}\n"
            f"SL: ${pos['sl']:.4f} | TP1: ${pos['tp1']:.4f}\n"
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
        symbols = pairs.get("majors", []) + pairs.get("midcaps", [])[:5]
        
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
                    msg = (
                        f"✅ **ORDER FILLED** - {signal.symbol} {signal.direction}\n"
                        f"Entry: ${signal.entry_price:.4f}\n"
                        f"SL: ${signal.sl:.4f} | TP1: ${signal.tp1:.4f} | TP2: ${signal.tp2:.4f}\n"
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
    app.add_handler(CommandHandler("startbot", cmd_startbot))
    app.add_handler(CommandHandler("stopbot", cmd_stopbot))
    
    print("🤖 Adaptive Edge Bot started!")
    print(f"   Paper Balance: ${paper_trader.balance:.2f}")
    print(f"   Leverage: {paper_trader.leverage}x")
    
    app.run_polling()


if __name__ == "__main__":
    main()
