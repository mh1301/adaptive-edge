"""
Decision Engine — Combines scanner output with risk management to generate trade signals.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from core import risk_manager


class TradeSignal:
    """Represents a trade signal with all necessary info for execution."""
    
    def __init__(self, symbol: str, direction: str, entry_price: float,
                 sl: float, tp1: float, tp2: float, score: int,
                 setup_type: str = "general", rr: float = 2.5):
        self.symbol = symbol
        self.direction = direction  # "LONG" or "SHORT"
        self.entry_price = entry_price
        self.sl = sl
        self.tp1 = tp1
        self.tp2 = tp2
        self.score = score
        self.setup_type = setup_type
        self.rr = rr
        self.valid = True
        self.reject_reason = None
    
    def __repr__(self):
        return (f"TradeSignal({self.symbol} {self.direction} @ {self.entry_price:.4f} | "
                f"SL:{self.sl:.4f} TP1:{self.tp1:.4f} TP2:{self.tp2:.4f} | "
                f"Score:{self.score} RR:1:{self.rr})")


def evaluate_signal(analysis: Dict, config: Dict, current_positions: List[Dict],
                    daily_pnl: float = 0) -> Optional[TradeSignal]:
    """Evaluate an analysis result and decide whether to trade.
    
    Args:
        analysis: output from scanner.analyze_single()
        config: trading config dict
        current_positions: list of open positions
        daily_pnl: today's realized P&L
    
    Returns:
        TradeSignal if valid, None if rejected.
    """
    score = analysis.get("score", 0)
    direction = analysis.get("direction", "NEUTRAL")
    symbol = analysis.get("symbol", "")
    current_price = analysis.get("current_price", 0)
    entry_zone = analysis.get("entry_zone", {})
    sl = analysis.get("sl", 0)
    tp1 = analysis.get("tp1", 0)
    tp2 = analysis.get("tp2", 0)
    rr = analysis.get("rr", 0)
    
    # ─── Rejection Checks ────────────────────────────
    
    # 1. Score threshold
    min_score = config.get("scanner", {}).get("min_score", 60)
    if score < min_score:
        return None
    
    # 2. Direction must be clear
    if direction == "NEUTRAL":
        return None
    
    # 3. Impulse system check (NEVER go against HTF impulse)
    impulse_dir = analysis.get("impulse_direction", "NEUTRAL")
    if impulse_dir != "NEUTRAL" and impulse_dir != direction:
        return None
    
    # 4. Max positions check
    max_positions = config.get("trading", {}).get("max_positions", 3)
    if len(current_positions) >= max_positions:
        return None
    
    # 5. Already have position in this symbol?
    for pos in current_positions:
        if pos.get("symbol", "").replace("USDT", "") == symbol.replace("USDT", ""):
            return None
    
    # 6. 6% rule check
    equity = config.get("_equity", 1000)
    max_daily_loss = equity * config.get("risk", {}).get("max_daily_loss_pct", 6) / 100
    if daily_pnl < -max_daily_loss:
        return None
    
    # 7. RR minimum check
    min_rr = config.get("trading", {}).get("min_rr", 2.5)
    if rr < min_rr:
        return None
    
    # ─── Create Signal ───────────────────────────────
    signal = TradeSignal(
        symbol=symbol,
        direction=direction,
        entry_price=current_price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        score=score,
        setup_type=_detect_setup(analysis),
        rr=rr,
    )
    
    # Calculate position size using risk manager
    risk_pct = config.get("risk", {}).get("two_percent_rule", 2.0)
    position_size = risk_manager.calculate_position_size(
        equity=equity,
        risk_pct=risk_pct,
        entry=current_price,
        sl=sl,
        leverage=config.get("trading", {}).get("leverage", 15),
    )
    
    signal.size = position_size
    signal.margin = position_size * current_price / config.get("trading", {}).get("leverage", 15)
    
    return signal


def _detect_setup(analysis: Dict) -> str:
    """Detect which setup type this trade matches."""
    modules = analysis.get("modules", {})
    
    # Check for specific setups
    ms = modules.get("market_structure", {})
    obs = modules.get("order_blocks", {})
    liquidity_data = modules.get("liquidity", {})
    
    # SH + BMS + RTO
    bms = ms.get("bms_events", [])
    if bms and obs.get("order_blocks"):
        return "SH+BMS+RTO"
    
    # SMS (Failure Swing)
    choch = ms.get("choch_events", [])
    if choch:
        return "SMS+BMS+RTO"
    
    # Turtle Soup (near liquidity pools)
    if liquidity_data.get("bsl_distance", 1) < 0.02 or liquidity_data.get("ssl_distance", 1) < 0.02:
        return "Turtle Soup"
    
    # AMD
    amd = modules.get("amd", {})
    if amd.get("phase") == "distribution":
        return "AMD Distribution"
    
    # S&D Zone
    snd = modules.get("supply_demand", {})
    if snd.get("direction") != "NEUTRAL":
        return "SnD Zone"
    
    return "Multi-Confluence"


def evaluate_batch(analyses: List[Dict], config: Dict, current_positions: List[Dict],
                   daily_pnl: float = 0, max_signals: int = 3) -> List[TradeSignal]:
    """Evaluate multiple analyses and return valid signals.
    
    Args:
        analyses: list of scanner outputs (sorted by score desc)
        config: trading config
        current_positions: open positions
        daily_pnl: today's P&L
        max_signals: max signals to return
    
    Returns:
        List of valid TradeSignals, sorted by score.
    """
    signals = []
    
    for analysis in analyses:
        if len(signals) >= max_signals:
            break
        
        signal = evaluate_signal(analysis, config, current_positions, daily_pnl)
        if signal:
            signals.append(signal)
    
    return signals


if __name__ == "__main__":
    print("=== Decision Engine Test ===")
    
    # Mock analysis result
    mock_analysis = {
        "symbol": "SOLUSDT",
        "score": 72,
        "direction": "LONG",
        "current_price": 145.50,
        "entry_zone": {"low": 144.00, "high": 146.00, "source": "ob"},
        "sl": 141.00,
        "tp1": 156.00,
        "tp2": 163.00,
        "rr": 2.5,
        "impulse_direction": "LONG",
        "modules": {
            "market_structure": {"bms_events": [{"type": "BMS_BULLISH"}], "choch_events": []},
            "order_blocks": {"order_blocks": [{"type": "bullish_ob"}]},
            "supply_demand": {"direction": "LONG"},
            "liquidity": {"bsl_distance": 0.01, "ssl_distance": 0.05},
            "amd": {"phase": "distribution"},
        },
    }
    
    mock_config = {
        "scanner": {"min_score": 60},
        "trading": {"max_positions": 3, "leverage": 15, "min_rr": 2.5},
        "risk": {"max_daily_loss_pct": 6, "two_percent_rule": 2.0},
        "_equity": 1000,
    }
    
    signal = evaluate_signal(mock_analysis, mock_config, [], 0)
    if signal:
        print(f"Signal: {signal}")
        print(f"Size: {signal.size} contracts")
        print(f"Margin: ${signal.margin:.2f}")
        print(f"Setup: {signal.setup_type}")
    else:
        print("No signal generated")
