"""
Supply & Demand Zone Detection
Formations: RBR, RBD, DBR, DBD
"""

from typing import List, Dict


def _is_base(candles: List[Dict], idx: int, lookback: int = 3) -> bool:
    """Check if candle at idx is in a base (consolidation) zone.
    Base = candle range < 50% of average range of surrounding candles."""
    if idx < lookback or idx >= len(candles) - lookback:
        return False
    
    avg_range = 0
    count = 0
    for j in range(max(0, idx - lookback), min(len(candles), idx + lookback + 1)):
        if j == idx:
            continue
        r = candles[j]["high"] - candles[j]["low"]
        if r > 0:
            avg_range += r
            count += 1
    
    if count == 0:
        return False
    
    avg_range /= count
    base_range = candles[idx]["high"] - candles[idx]["low"]
    
    return base_range < avg_range * 0.5


def detect_zones(candles: List[Dict]) -> List[Dict]:
    """Detect Supply & Demand zones.
    
    Returns list of zones:
    {
        "type": "supply" | "demand",
        "formation": "RBR" | "RBD" | "DBR" | "DBD",
        "zone_high": float,
        "zone_low": float,
        "fresh": bool,
        "strength": float,  # 0-1
        "index": int,
    }
    """
    zones = []
    
    if len(candles) < 5:
        return zones
    
    # Find base candles
    for i in range(2, len(candles) - 2):
        if not _is_base(candles, i):
            continue
        
        # Look at candles before and after base
        before = candles[i-1]
        after = candles[i+1]
        base = candles[i]
        
        before_bullish = before["close"] > before["open"]
        after_bullish = after["close"] > after["open"]
        before_move = abs(before["close"] - before["open"])
        after_move = abs(after["close"] - after["open"])
        avg_body = (before_move + after_move) / 2
        
        # Skip if moves are too small
        if avg_body < (base["high"] - base["low"]) * 0.3:
            continue
        
        # Classify formation
        if before_bullish and after_bullish:
            formation = "RBR"  # Rally Base Rally → Demand
            zone_type = "demand"
        elif before_bullish and not after_bullish:
            formation = "RBD"  # Rally Base Drop → Supply
            zone_type = "supply"
        elif not before_bullish and after_bullish:
            formation = "DBR"  # Drop Base Rally → Demand
            zone_type = "demand"
        else:
            formation = "DBD"  # Drop Base Drop → Supply
            zone_type = "supply"
        
        zone_high = base["high"]
        zone_low = base["low"]
        
        # Check if fresh (price hasn't returned to zone)
        fresh = True
        for j in range(i + 2, len(candles)):
            if zone_low <= candles[j]["low"] <= zone_high or zone_low <= candles[j]["high"] <= zone_high:
                fresh = False
                break
        
        # Strength based on move size relative to base
        strength = min(avg_body / max(zone_high - zone_low, 0.0001), 1.0)
        
        zones.append({
            "type": zone_type,
            "formation": formation,
            "zone_high": zone_high,
            "zone_low": zone_low,
            "fresh": fresh,
            "strength": strength,
            "index": i,
            "time": base["time"],
        })
    
    return zones


def find_demand_zones(candles: List[Dict]) -> List[Dict]:
    """Find all demand zones, sorted by freshness and strength."""
    zones = detect_zones(candles)
    demand = [z for z in zones if z["type"] == "demand"]
    demand.sort(key=lambda x: (x["fresh"], x["strength"]), reverse=True)
    return demand


def find_supply_zones(candles: List[Dict]) -> List[Dict]:
    """Find all supply zones, sorted by freshness and strength."""
    zones = detect_zones(candles)
    supply = [z for z in zones if z["type"] == "supply"]
    supply.sort(key=lambda x: (x["fresh"], x["strength"]), reverse=True)
    return supply


def price_in_zone(price: float, zone: Dict) -> bool:
    """Check if price is within a zone."""
    return zone["zone_low"] <= price <= zone["zone_high"]


def analyze(candles: List[Dict]) -> Dict:
    """Full S&D analysis."""
    zones = detect_zones(candles)
    demand = [z for z in zones if z["type"] == "demand"]
    supply = [z for z in zones if z["type"] == "supply"]
    
    fresh_demand = [z for z in demand if z["fresh"]]
    fresh_supply = [z for z in supply if z["fresh"]]
    
    current_price = candles[-1]["close"] if candles else 0
    
    # Score: fresh zones near price = higher score
    score = 0
    direction = "NEUTRAL"
    
    for z in fresh_demand:
        if z["zone_low"] <= current_price <= z["zone_high"] * 1.02:
            score = 12
            direction = "LONG"
            break
    
    for z in fresh_supply:
        if z["zone_low"] * 0.98 <= current_price <= z["zone_high"]:
            if score < 12:
                score = 12
                direction = "SHORT"
            break
    
    if score == 0:
        score = 5  # No zone proximity
    
    return {
        "zones": zones,
        "demand_zones": demand,
        "supply_zones": supply,
        "fresh_demand": fresh_demand,
        "fresh_supply": fresh_supply,
        "score": min(score, 12),
        "direction": direction,
        "module": "supply_demand",
    }
