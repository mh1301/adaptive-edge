"""
Liquidity Pool Detection
BSL (Buy Stops) = equal highs, swing highs
SSL (Sell Stops) = equal lows, swing lows
"""

from typing import List, Dict


def find_equal_levels(candles: List[Dict], tolerance: float = 0.005, lookback: int = 20) -> Dict:
    """Find equal highs/lows (liquidity pools)."""
    highs = []
    lows = []
    
    recent = candles[-lookback:] if len(candles) > lookback else candles
    
    for i in range(len(recent)):
        for j in range(i + 1, len(recent)):
            # Equal highs
            if recent[i]["high"] > 0:
                diff = abs(recent[i]["high"] - recent[j]["high"]) / recent[i]["high"]
                if diff < tolerance:
                    highs.append({
                        "price": (recent[i]["high"] + recent[j]["high"]) / 2,
                        "index_i": i,
                        "index_j": j,
                        "type": "BSL",
                    })
            
            # Equal lows
            if recent[i]["low"] > 0:
                diff = abs(recent[i]["low"] - recent[j]["low"]) / recent[i]["low"]
                if diff < tolerance:
                    lows.append({
                        "price": (recent[i]["low"] + recent[j]["low"]) / 2,
                        "index_i": i,
                        "index_j": j,
                        "type": "SSL",
                    })
    
    return {"bsl_pools": highs, "ssl_pools": lows}


def analyze(candles: List[Dict]) -> Dict:
    """Full liquidity analysis."""
    levels = find_equal_levels(candles)
    
    bsl = levels["bsl_pools"]
    ssl = levels["ssl_pools"]
    
    current_price = candles[-1]["close"] if candles else 0.0001  # Avoid zero division
    
    # Check proximity to liquidity pools
    nearest_bsl = None
    nearest_ssl = None
    bsl_dist = float("inf")
    ssl_dist = float("inf")
    
    for pool in bsl:
        dist = abs(pool["price"] - current_price) / current_price
        if dist < bsl_dist:
            bsl_dist = dist
            nearest_bsl = pool
    
    for pool in ssl:
        dist = abs(pool["price"] - current_price) / current_price
        if dist < ssl_dist:
            ssl_dist = dist
            nearest_ssl = pool
    
    # Score based on proximity
    score = 0
    direction = "NEUTRAL"
    
    # Close to SSL = potential bounce up (buy)
    if ssl_dist < 0.02:  # Within 2%
        score = 8
        direction = "LONG"
    
    # Close to BSL = potential reversal down (sell)
    if bsl_dist < 0.02:
        if score < 8:
            score = 8
            direction = "SHORT"
    
    if score == 0:
        score = 3
    
    return {
        "bsl_pools": bsl,
        "ssl_pools": ssl,
        "nearest_bsl": nearest_bsl,
        "nearest_ssl": nearest_ssl,
        "bsl_distance": bsl_dist,
        "ssl_distance": ssl_dist,
        "score": min(score, 8),
        "direction": direction,
        "module": "liquidity",
    }
