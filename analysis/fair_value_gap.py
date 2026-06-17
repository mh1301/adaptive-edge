"""
Fair Value Gap (FVG) Detection
FVG = gap between candle[i-2].high and candle[i].low (bullish)
     = gap between candle[i].high and candle[i-2].low (bearish)
"""

from typing import List, Dict


def detect_fvgs(candles: List[Dict]) -> List[Dict]:
    """Detect Fair Value Gaps."""
    fvgs = []
    
    for i in range(2, len(candles)):
        c_prev2 = candles[i-2]
        c_curr = candles[i]
        
        # Bullish FVG: gap up (current low > prev2 high)
        if c_curr["low"] > c_prev2["high"]:
            fvgs.append({
                "type": "bullish_fvg",
                "gap_high": c_curr["low"],
                "gap_low": c_prev2["high"],
                "index": i,
                "time": candles[i-1]["time"],
                "filled": False,
            })
        
        # Bearish FVG: gap down (current high < prev2 low)
        if c_curr["high"] < c_prev2["low"]:
            fvgs.append({
                "type": "bearish_fvg",
                "gap_high": c_prev2["low"],
                "gap_low": c_curr["high"],
                "index": i,
                "time": candles[i-1]["time"],
                "filled": False,
            })
    
    # Check if FVGs have been filled
    for fvg in fvgs:
        for j in range(fvg["index"] + 1, len(candles)):
            if fvg["type"] == "bullish_fvg":
                if candles[j]["low"] <= fvg["gap_low"]:
                    fvg["filled"] = True
                    break
            else:
                if candles[j]["high"] >= fvg["gap_high"]:
                    fvg["filled"] = True
                    break
    
    return fvgs


def analyze(candles: List[Dict]) -> Dict:
    """Full FVG analysis."""
    fvgs = detect_fvgs(candles)
    
    bullish = [f for f in fvgs if f["type"] == "bullish_fvg"]
    bearish = [f for f in fvgs if f["type"] == "bearish_fvg"]
    unfilled_bullish = [f for f in bullish if not f["filled"]]
    unfilled_bearish = [f for f in bearish if not f["filled"]]
    
    current_price = candles[-1]["close"] if candles else 0
    
    score = 0
    direction = "NEUTRAL"
    
    for fvg in unfilled_bullish:
        if fvg["gap_low"] <= current_price <= fvg["gap_high"] * 1.01:
            score = 8
            direction = "LONG"
            break
    
    for fvg in unfilled_bearish:
        if fvg["gap_low"] * 0.99 <= current_price <= fvg["gap_high"]:
            if score < 8:
                score = 8
                direction = "SHORT"
            break
    
    if score == 0:
        score = 2
    
    return {
        "fvgs": fvgs,
        "bullish_fvgs": bullish,
        "bearish_fvgs": bearish,
        "unfilled_bullish": unfilled_bullish,
        "unfilled_bearish": unfilled_bearish,
        "score": min(score, 8),
        "direction": direction,
        "module": "fair_value_gap",
    }
