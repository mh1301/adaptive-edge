"""
Key Candlestick Pattern Detection
Focus on high-reliability patterns: Engulfing, Hammer, Doji, Morning/Evening Star.
"""

from typing import List, Dict


def _body(c: Dict) -> float:
    return abs(c["close"] - c["open"])

def _range(c: Dict) -> float:
    return c["high"] - c["low"]

def _is_bullish(c: Dict) -> bool:
    return c["close"] > c["open"]

def _is_bearish(c: Dict) -> bool:
    return c["close"] < c["open"]

def _upper_shadow(c: Dict) -> float:
    return c["high"] - max(c["open"], c["close"])

def _lower_shadow(c: Dict) -> float:
    return min(c["open"], c["close"]) - c["low"]


def detect_patterns(candles: List[Dict]) -> List[Dict]:
    """Detect key candlestick patterns in recent candles."""
    patterns = []
    
    for i in range(1, len(candles)):
        curr = candles[i]
        prev = candles[i-1]
        rng = _range(curr)
        if rng == 0:
            continue
        
        # Bullish Engulfing
        if _is_bearish(prev) and _is_bullish(curr):
            if curr["close"] > prev["open"] and curr["open"] < prev["close"]:
                patterns.append({"type": "bullish_engulfing", "index": i, "strength": 0.8, "direction": "LONG"})
        
        # Bearish Engulfing
        if _is_bullish(prev) and _is_bearish(curr):
            if curr["open"] > prev["close"] and curr["close"] < prev["open"]:
                patterns.append({"type": "bearish_engulfing", "index": i, "strength": 0.8, "direction": "SHORT"})
        
        # Hammer (bullish reversal)
        if _lower_shadow(curr) > _body(curr) * 2 and _upper_shadow(curr) < _body(curr) * 0.5:
            patterns.append({"type": "hammer", "index": i, "strength": 0.7, "direction": "LONG"})
        
        # Shooting Star (bearish reversal)
        if _upper_shadow(curr) > _body(curr) * 2 and _lower_shadow(curr) < _body(curr) * 0.5:
            patterns.append({"type": "shooting_star", "index": i, "strength": 0.7, "direction": "SHORT"})
        
        # Doji
        if _body(curr) < rng * 0.1:
            patterns.append({"type": "doji", "index": i, "strength": 0.5, "direction": "NEUTRAL"})
    
    # 3-candle patterns
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        
        # Morning Star
        if _is_bearish(c1) and _body(c2) < _body(c1) * 0.3 and _is_bullish(c3):
            if c3["close"] > (c1["open"] + c1["close"]) / 2:
                patterns.append({"type": "morning_star", "index": i, "strength": 0.9, "direction": "LONG"})
        
        # Evening Star
        if _is_bullish(c1) and _body(c2) < _body(c1) * 0.3 and _is_bearish(c3):
            if c3["close"] < (c1["open"] + c1["close"]) / 2:
                patterns.append({"type": "evening_star", "index": i, "strength": 0.9, "direction": "SHORT"})
    
    return patterns


def analyze(candles: List[Dict]) -> Dict:
    """Full candlestick analysis."""
    patterns = detect_patterns(candles)
    
    # Focus on recent patterns (last 5 candles)
    recent = [p for p in patterns if p["index"] >= len(candles) - 5]
    
    bullish_count = sum(1 for p in recent if p["direction"] == "LONG")
    bearish_count = sum(1 for p in recent if p["direction"] == "SHORT")
    
    score = 0
    direction = "NEUTRAL"
    
    if bullish_count > bearish_count:
        score = min(bullish_count * 4, 10)
        direction = "LONG"
    elif bearish_count > bullish_count:
        score = min(bearish_count * 4, 10)
        direction = "SHORT"
    else:
        score = 3
    
    return {
        "patterns": patterns,
        "recent_patterns": recent,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "score": min(score, 10),
        "direction": direction,
        "module": "candlestick",
    }
