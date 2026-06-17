"""
Executor — Paper Trading & Live Execution via Bitget API.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from typing import Dict, List, Optional
from core import journal, risk_manager
from data import bitget_feed


class PaperTrader:
    """Paper trading executor — simulates trades using live market data."""
    
    def __init__(self, initial_balance: float = 1000.0, leverage: int = 15):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.positions: List[Dict] = []
        self.risk_mgr = risk_manager.RiskManager(initial_balance)
    
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
                elif price >= pos["tp1"]:
                    exit_type = "EXIT_TP1"
            else:  # SHORT
                if price >= pos["sl"]:
                    exit_type = "EXIT_SL"
                elif price <= pos["tp2"]:
                    exit_type = "EXIT_TP2"
                elif price <= pos["tp1"]:
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
                    # Keep position but update SL to breakeven
                    pos["sl"] = pos["entry_price"]
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
        return exits
    
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
