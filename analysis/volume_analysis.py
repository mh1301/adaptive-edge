"""
Volume Analysis — Spike detection, trend confirmation.
"""

from typing import List, Dict


def analyze(candles: List[Dict]) -> Dict:
    """Volume analysis."""
    if len(candles) < 20:
        return {"score": 0, "direction": "NEUTRAL", "module": "volume"}
    
    volumes = [c["volume"] for c in candles]
    avg_vol_20 = sum(volumes[-20:]) / 20
    avg_vol_5 = sum(volumes[-5:]) / 5
    current_vol = volumes[-1]
    
    # Volume spike detection
    vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
    
    # Volume trend (5 vs 20)
    vol_trend = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1
    
    # Check if volume confirms price direction
    last_candle = candles[-1]
    bullish_candle = last_candle["close"] > last_candle["open"]
    
    score = 0
    direction = "NEUTRAL"
    
    # High volume + bullish candle = strong buy signal
    if vol_ratio > 1.5 and bullish_candle:
        score = 8
        direction = "LONG"
    elif vol_ratio > 1.5 and not bullish_candle:
        score = 8
        direction = "SHORT"
    elif vol_ratio > 1.2:
        score = 5
    else:
        score = 2
    
    return {
        "current_volume": current_vol,
        "avg_volume_20": avg_vol_20,
        "volume_ratio": vol_ratio,
        "volume_trend": vol_trend,
        "score": min(score, 8),
        "direction": direction,
        "module": "volume",
    }
