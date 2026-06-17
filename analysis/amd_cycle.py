"""
AMD Cycle Detection — Accumulation, Manipulation, Distribution.
"""

from typing import List, Dict


def analyze(candles: List[Dict]) -> Dict:
    """Detect AMD cycle phase."""
    if len(candles) < 20:
        return {"score": 0, "direction": "NEUTRAL", "phase": "unknown", "module": "amd"}
    
    recent = candles[-20:]
    
    # Calculate range compression
    ranges = [c["high"] - c["low"] for c in recent]
    avg_range = sum(ranges) / len(ranges)
    recent_range = sum(ranges[-5:]) / 5
    
    # Calculate volume trend
    volumes = [c["volume"] for c in recent]
    avg_vol = sum(volumes) / len(volumes)
    recent_vol = sum(volumes[-5:]) / 5
    
    # Detect phase
    range_compressed = recent_range < avg_range * 0.6
    vol_low = recent_vol < avg_vol * 0.7
    
    if range_compressed and vol_low:
        phase = "accumulation"
        score = 8
        direction = "NEUTRAL"  # Wait for breakout
    elif not range_compressed and recent_vol > avg_vol * 1.5:
        # Check if this is manipulation or distribution
        last_5_range = sum(ranges[-5:])
        first_5_range = sum(ranges[:5])
        
        if last_5_range > first_5_range * 1.5:
            phase = "distribution"
            score = 10
            # Direction based on recent price action
            if candles[-1]["close"] > candles[-5]["close"]:
                direction = "LONG"
            else:
                direction = "SHORT"
        else:
            phase = "manipulation"
            score = 5
            direction = "NEUTRAL"
    else:
        phase = "transitional"
        score = 3
        direction = "NEUTRAL"
    
    return {
        "phase": phase,
        "range_compressed": range_compressed,
        "volume_ratio": recent_vol / avg_vol if avg_vol > 0 else 1,
        "score": min(score, 10),
        "direction": direction,
        "module": "amd",
    }
