"""
Risk Manager — Elder's 2% Rule, 6% Rule, Position Sizing, Circuit Breakers.
"""

from typing import Dict, List


def calculate_position_size(equity: float, risk_pct: float, entry: float,
                            sl: float, leverage: int = 15) -> int:
    """Calculate position size using Elder's 2% rule.
    
    Position Size = (Equity × Risk%) / |Entry - SL|
    
    Returns number of contracts (integer).
    """
    if entry == sl or entry == 0:
        return 0
    
    risk_amount = equity * risk_pct / 100
    sl_distance = abs(entry - sl)
    
    # Size in units
    size_units = risk_amount / sl_distance
    
    # Convert to contracts (notional = size * price / leverage)
    # For Bitget: contract_size = 1 unit for most pairs
    contracts = int(size_units)
    
    # Minimum 1 contract
    return max(contracts, 1)


def check_two_percent_rule(equity: float, risk_per_trade: float) -> bool:
    """Check if trade risk exceeds 2% of equity."""
    return risk_per_trade <= equity * 0.02


def check_six_percent_rule(equity: float, open_risks: List[float], realized_loss: float) -> bool:
    """Check if total risk exceeds 6% of equity.
    
    6% Rule: Total risk of all open positions + realized losses this month ≤ 6% of equity.
    """
    total_risk = sum(open_risks) + abs(min(realized_loss, 0))
    return total_risk <= equity * 0.06


def check_circuit_breaker(consecutive_losses: int, max_losses: int = 2) -> bool:
    """Check if circuit breaker should trigger.
    Returns True if trading should STOP."""
    return consecutive_losses >= max_losses


def calculate_sl_distance(entry: float, direction: str, pct: float = 3.0) -> float:
    """Calculate stop loss price."""
    if direction == "LONG":
        return entry * (1 - pct / 100)
    else:
        return entry * (1 + pct / 100)


def calculate_tp_levels(entry: float, sl: float, direction: str,
                        rr1: float = 2.5, rr2: float = 4.0) -> Dict:
    """Calculate take profit levels based on risk:reward."""
    sl_distance = abs(entry - sl)
    
    if direction == "LONG":
        tp1 = entry + sl_distance * rr1
        tp2 = entry + sl_distance * rr2
    else:
        tp1 = entry - sl_distance * rr1
        tp2 = entry - sl_distance * rr2
    
    return {"tp1": tp1, "tp2": tp2}


def calculate_risk_metrics(equity: float, positions: List[Dict]) -> Dict:
    """Calculate current risk metrics."""
    total_margin = sum(p.get("margin", 0) for p in positions)
    total_unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
    position_count = len(positions)
    
    margin_pct = (total_margin / equity * 100) if equity > 0 else 0
    
    return {
        "equity": equity,
        "total_margin": total_margin,
        "margin_pct": margin_pct,
        "unrealized_pnl": total_unrealized,
        "position_count": position_count,
        "available_balance": equity - total_margin + total_unrealized,
    }


class RiskManager:
    """Stateful risk manager that tracks daily P&L and consecutive losses."""
    
    def __init__(self, equity: float, max_daily_loss_pct: float = 6.0,
                 max_consecutive_losses: int = 2):
        self.equity = equity
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trades_today = 0
    
    def can_trade(self) -> tuple:
        """Check if trading is allowed. Returns (can_trade: bool, reason: str)."""
        # Check daily loss limit
        max_loss = self.equity * self.max_daily_loss_pct / 100
        if self.daily_pnl < -max_loss:
            return False, f"Daily loss limit hit (${self.daily_pnl:.2f} < -${max_loss:.2f})"
        
        # Check circuit breaker
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Circuit breaker: {self.consecutive_losses} consecutive losses"
        
        return True, "OK"
    
    def record_trade(self, pnl: float):
        """Record a trade result."""
        self.daily_pnl += pnl
        self.trades_today += 1
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
    
    def reset_daily(self):
        """Reset daily counters."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
    
    def status(self) -> Dict:
        """Get current risk status."""
        can, reason = self.can_trade()
        return {
            "equity": self.equity,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "trades_today": self.trades_today,
            "can_trade": can,
            "reason": reason,
        }
