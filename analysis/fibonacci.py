"""
Fibonacci Retracement Analysis
Key levels: 23.6%, 38.2%, 50%, 61.8% (OTE), 78.6%
"""

from typing import List, Dict, Optional


def calculate_retracement(swing_high: float, swing_low: float, current_price: float) -> Dict:
    """Calculate Fibonacci retracement levels and current position."""
    range_size = swing_high - swing_low
    
    levels = {
        "0.0": swing_low,
        "0.236": swing_low + range_size * 0.236,
        "0.382": swing_low + range_size * 0.382,
        "0.5": swing_low + range_size * 0.5,
        "0.618": swing_low + range_size * 0.618,
        "0.705": swing_low + range_size * 0.705,
        "0.786": swing_low + range_size * 0.786,
        "1.0": swing_high,
    }
    
    # OTE zone (Optimal Trade Entry)
    ote_low = levels["0.618"]
    ote_high = levels["0.705"]
    
    # Current position as percentage
    if range_size > 0:
        retracement_pct = (swing_high - current_price) / range_size
    else:
        retracement_pct = 0
    
    return {
        "levels": levels,
        "ote_zone": (ote_low, ote_high),
        "retracement_pct": retracement_pct,
        "in_ote": ote_low <= current_price <= ote_high,
        "in_382_618": levels["0.382"] <= current_price <= levels["0.618"],
    }


def find_swing_for_fib(candles: List[Dict]) -> Dict:
    """Find the most recent significant swing high and low for Fibonacci."""
    if len(candles) < 10:
        return {"swing_high": None, "swing_low": None}
    
    # Find highest high and lowest low in recent candles
    recent = candles[-50:] if len(candles) > 50 else candles
    
    high_idx = max(range(len(recent)), key=lambda i: recent[i]["high"])
    low_idx = min(range(len(recent)), key=lambda i: recent[i]["low"])
    
    swing_high = recent[high_idx]["high"]
    swing_low = recent[low_idx]["low"]
    
    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "high_index": high_idx,
        "low_index": low_idx,
        "range": swing_high - swing_low,
    }


def analyze(candles: List[Dict]) -> Dict:
    """Full Fibonacci analysis."""
    if len(candles) < 10:
        return {"score": 0, "direction": "NEUTRAL", "module": "fibonacci"}
    
    swings = find_swing_for_fib(candles)
    if not swings["swing_high"] or not swings["swing_low"]:
        return {"score": 0, "direction": "NEUTRAL", "module": "fibonacci"}
    
    current_price = candles[-1]["close"]
    fib = calculate_retracement(swings["swing_high"], swings["swing_low"], current_price)
    
    score = 0
    direction = "NEUTRAL"
    
    # Price in OTE zone = high probability entry
    if fib["in_ote"]:
        score = 12
        # Determine direction based on swing sequence
        if swings["high_index"] > swings["low_index"]:
            # High came after low → uptrend retracement → LONG
            direction = "LONG"
        else:
            # Low came after high → downtrend retracement → SHORT
            direction = "SHORT"
    elif fib["in_382_618"]:
        score = 8
        if swings["high_index"] > swings["low_index"]:
            direction = "LONG"
        else:
            direction = "SHORT"
    else:
        score = 3
    
    return {
        "swing_high": swings["swing_high"],
        "swing_low": swings["swing_low"],
        "levels": fib["levels"],
        "ote_zone": fib["ote_zone"],
        "retracement_pct": fib["retracement_pct"],
        "in_ote": fib["in_ote"],
        "score": min(score, 12),
        "direction": direction,
        "module": "fibonacci",
    }
