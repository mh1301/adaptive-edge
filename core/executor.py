"""
Executor — Paper Trading & Live Execution via Bitget API.
"""

import sys
import json
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from typing import Dict, List, Optional
from core import journal, risk_manager
from data import bitget_feed


STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "state.json")

class PaperTrader:
    """Paper trading executor — simulates trades using live market data."""
    
    def __init__(self, initial_balance: float = 1000.0, leverage: int = 15):
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.positions: List[Dict] = []
        self.balance = initial_balance
        self.risk_mgr = risk_manager.RiskManager(initial_balance)
        self._load_state()

    def _save_state(self):
        """Save state to file for persistence across restarts."""
        state = {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "leverage": self.leverage,
            "positions": self.positions,
            "daily_pnl": self.risk_mgr.daily_pnl,
            "consecutive_losses": self.risk_mgr.consecutive_losses,
            "trades_today": self.risk_mgr.trades_today,
        }
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load state from file if exists."""
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            self.balance = state.get("balance", self.initial_balance)
            self.positions = state.get("positions", [])
            self.risk_mgr.daily_pnl = state.get("daily_pnl", 0)
            self.risk_mgr.consecutive_losses = state.get("consecutive_losses", 0)
            self.risk_mgr.trades_today = state.get("trades_today", 0)
            print(f"[PaperTrader] Loaded state: balance=${self.balance:.2f}, {len(self.positions)} positions")
        except Exception as e:
            print(f"[PaperTrader] Failed to load state: {e}")


    def open_position(self, signal) -> Dict:
        """Open a paper position from a trade signal.
        
        Args:
            signal: TradeSignal object from decision.py
        
        Returns:
            Trade record dict.
        """
        # Check risk
        can_trade, reason = self.risk_mgr.can_trade()
        if not can_trade:
            return {"status": "REJECTED", "reason": reason}
        
        # Calculate margin
        margin = signal.entry_price * signal.size / self.leverage
        if margin > self.balance * 0.5:  # Don't use more than 50% of balance
            margin = self.balance * 0.3
            signal.size = int(margin * self.leverage / signal.entry_price)
            if signal.size < 1:
                return {"status": "REJECTED", "reason": "Insufficient balance for minimum contract"}
        
        balance_before = self.balance
        
        # Open position
        position = {
            "symbol": signal.symbol,
            "direction": signal.direction,
            "entry_price": signal.entry_price,
            "size": signal.size,
            "sl": signal.sl,
            "tp1": signal.tp1,
            "tp2": signal.tp2,
            "margin": margin,
            "leverage": self.leverage,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "setup": signal.setup_type,
            "score": signal.score,
        }
        
        self.positions.append(position)
        self._save_state()
        # Don't deduct margin from balance — track it separately
        
        # Log entry
        trade_record = {
            "timestamp": position["opened_at"],
            "pair": signal.symbol,
            "side": signal.direction,
            "price": signal.entry_price,
            "size": signal.size,
            "balance_before": balance_before,
            "balance_after": balance_before,  # Balance unchanged on entry
            "type": "ENTRY",
            "setup": signal.setup_type,
            "score": signal.score,
            "sl": signal.sl,
            "tp1": signal.tp1,
            "tp2": signal.tp2,
        }
        journal.log_trade(trade_record)
        
        return trade_record
    
    def check_exits(self, current_prices: Dict[str, float]) -> List[Dict]:
        """Check all positions for SL/TP hits.
        
        Args:
            current_prices: {symbol: price}
        
        Returns:
            List of exit trade records.
        """
        exits = []
        remaining = []
        
        for pos in self.positions:
            symbol = pos["symbol"]
            price = current_prices.get(symbol)
            if price is None:
                remaining.append(pos)
                continue
            
            exit_type = None
            
            if pos["direction"] == "LONG":
                if price <= pos["sl"]:
                    exit_type = "EXIT_SL"
                elif price >= pos["tp2"]:
                    exit_type = "EXIT_TP2"
                elif price >= pos["tp1"] and not pos.get("tp1_hit"):
                    exit_type = "EXIT_TP1"
            else:  # SHORT
                if price >= pos["sl"]:
                    exit_type = "EXIT_SL"
                elif price <= pos["tp2"]:
                    exit_type = "EXIT_TP2"
                elif price <= pos["tp1"] and not pos.get("tp1_hit"):
                    exit_type = "EXIT_TP1"
            
            if exit_type:
                # Calculate P&L
                if pos["direction"] == "LONG":
                    pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
                else:
                    pnl_pct = (pos["entry_price"] - price) / pos["entry_price"]
                
                pnl = pos["margin"] * self.leverage * pnl_pct
                
                # For TP1, only close 50%
                if exit_type == "EXIT_TP1":
                    pnl = pnl * 0.5
                    # Keep position but update SL to breakeven and halve size/margin
                    pos["sl"] = pos["entry_price"]
                    pos["margin"] = pos["margin"] * 0.5
                    pos["size"] = max(1, pos["size"] // 2)
                    pos["tp1_hit"] = True  # Mark TP1 as taken
                    remaining.append(pos)
                
                balance_before = self.balance
                self.balance += pnl  # Only add P&L (margin was never deducted)
                
                # Record
                exit_record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "pair": symbol,
                    "side": pos["direction"],
                    "price": price,
                    "size": pos["size"],
                    "balance_before": balance_before,
                    "balance_after": self.balance,
                    "type": exit_type,
                    "pnl": round(pnl, 2),
                    "entry_price": pos["entry_price"],
                }
                journal.log_trade(exit_record)
                self.risk_mgr.record_trade(pnl)
                exits.append(exit_record)
            else:
                remaining.append(pos)
        
        self.positions = remaining
        if exits:
            self._save_state()
        return exits
    

    def close_position(self, symbol: str, current_price: float) -> Dict:
        """Manually close a position at current price."""
        remaining = []
        closed = None
        
        for pos in self.positions:
            if pos["symbol"] == symbol:
                # Calculate P&L
                if pos["direction"] == "LONG":
                    pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                else:
                    pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"]
                
                pnl = pos["margin"] * self.leverage * pnl_pct
                balance_before = self.balance
                self.balance += pnl
                
                closed = {
                    "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "pair": symbol,
                    "side": pos["direction"],
                    "price": current_price,
                    "size": pos["size"],
                    "balance_before": balance_before,
                    "balance_after": self.balance,
                    "type": "EXIT_MANUAL",
                    "pnl": round(pnl, 2),
                    "entry_price": pos["entry_price"],
                }
                journal.log_trade(closed)
                self.risk_mgr.record_trade(pnl)
            else:
                remaining.append(pos)
        
        self.positions = remaining
        return closed
    
    def close_all(self, current_prices: Dict[str, float]) -> list:
        """Close all positions."""
        closed = []
        for symbol in list(current_prices.keys()):
            result = self.close_position(symbol, current_prices.get(symbol, 0))
            if result:
                closed.append(result)
        return closed

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate unrealized P&L from open positions."""
        total = 0
        for pos in self.positions:
            price = current_prices.get(pos["symbol"])
            if price is None:
                continue
            if pos["direction"] == "LONG":
                pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
            else:
                pnl_pct = (pos["entry_price"] - price) / pos["entry_price"]
            total += pos["margin"] * self.leverage * pnl_pct
        return total

    def get_status(self) -> Dict:
        """Get current paper trading status."""
        total_margin = sum(p["margin"] for p in self.positions)
        unrealized_pnl = 0  # Would need current prices to calculate
        
        return {
            "balance": round(self.balance, 2),
            "initial_balance": self.initial_balance,
            "total_pnl": round(self.balance - self.initial_balance, 2),
            "total_pnl_pct": round((self.balance - self.initial_balance) / self.initial_balance * 100, 2),
            "open_positions": len(self.positions),
            "total_margin": round(total_margin, 2),
            "leverage": self.leverage,
            "risk_status": self.risk_mgr.status(),
            "positions": self.positions,
        }


class LiveExecutor:
    """Live execution via Bitget API."""
    
    def __init__(self, leverage: int = 15, margin_mode: str = "crossed"):
        self.leverage = leverage
        self.margin_mode = margin_mode
        self._initialized = False
    
    def initialize(self):
        """Set position mode and leverage."""
        bitget_feed.set_position_mode("one_way_mode")
        self._initialized = True
    
    def open_position(self, signal) -> Dict:
        """Open a live position."""
        if not self._initialized:
            self.initialize()
        
        # Set leverage
        bitget_feed.set_leverage(signal.symbol, self.leverage, self.margin_mode)
        
        # Determine side
        side = "buy" if signal.direction == "LONG" else "sell"
        
        # Place order
        result = bitget_feed.place_market_order(
            symbol=signal.symbol,
            side=side,
            size=signal.size,
            leverage=self.leverage,
            margin_mode=self.margin_mode,
            sl_price=signal.sl,
            tp_price=signal.tp1,
        )
        
        return result
    
    def close_position(self, symbol: str, side: str = None) -> Dict:
        """Close a live position."""
        return bitget_feed.close_position(symbol, side)
