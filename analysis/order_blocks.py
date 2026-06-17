"""
Order Block Detection
OB = last opposite candle before impulsive move that causes BOS.
"""

from typing import List, Dict


def _avg_body(candles: List[Dict], lookback: int = 20) -> float:
    """Average body size of recent candles."""
    if not candles:
        return 0
    bodies = [abs(c["close"] - c["open"]) for c in candles[-lookback:]]
    return sum(bodies) / len(bodies) if bodies else 0


def detect_order_blocks(candles: List[Dict], bms_events: List[Dict] = None) -> List[Dict]:
    """Detect Order Blocks.
    
    Bullish OB: last bearish candle before impulsive bullish move (BMS up).
    Bearish OB: last bullish candle before impulsive bearish move (BMS down).
    
    Must have:
    1. Impulse move > 2x average body
    2. OB candle is opposite color of the move
    3. Move causes BOS (if bms_events provided)
    """
    obs = []
    if len(candles) < 5:
        return obs
    
    avg_body = _avg_body(candles)
    if avg_body == 0:
        return obs
    
    # Find impulse moves
    for i in range(2, len(candles)):
        curr = candles[i]
        prev = candles[i-1]
        curr_body = abs(curr["close"] - curr["open"])
        
        # Check if this is an impulsive move (> 2x avg body)
        if curr_body < avg_body * 2:
            continue
        
        bullish_move = curr["close"] > curr["open"]
        
        # Find the OB candle (last opposite candle before this move)
        ob_candle = None
        for j in range(i-1, max(0, i-5), -1):
            c = candles[j]
            if bullish_move and c["close"] < c["open"]:  # Bearish candle before bullish move
                ob_candle = c
                ob_index = j
                break
            elif not bullish_move and c["close"] > c["open"]:  # Bullish candle before bearish move
                ob_candle = c
                ob_index = j
                break
        
        if not ob_candle:
            continue
        
        # Determine OB type
        if bullish_move:
            ob_type = "bullish_ob"
            zone_high = ob_candle["high"]
            zone_low = ob_candle["low"]
        else:
            ob_type = "bearish_ob"
            zone_high = ob_candle["high"]
            zone_low = ob_candle["low"]
        
        # Check if OB has been mitigated (price returned to zone)
        mitigated = False
        for j in range(i + 1, len(candles)):
            if candles[j]["low"] <= zone_high and candles[j]["high"] >= zone_low:
                mitigated = True
                break
        
        # Calculate strength based on impulse size
        strength = min(curr_body / (avg_body * 2), 1.0)
        
        obs.append({
            "type": ob_type,
            "zone_high": zone_high,
            "zone_low": zone_low,
            "index": ob_index,
            "impulse_index": i,
            "impulse_size": curr_body,
            "mitigated": mitigated,
            "strength": strength,
            "time": ob_candle["time"],
        })
    
    return obs


def find_bullish_obs(candles: List[Dict], bms_events: List[Dict] = None) -> List[Dict]:
    """Find bullish OBs, sorted by strength (unmitigated first)."""
    obs = detect_order_blocks(candles, bms_events)
    bullish = [o for o in obs if o["type"] == "bullish_ob"]
    bullish.sort(key=lambda x: (not x["mitigated"], x["strength"]), reverse=True)
    return bullish


def find_bearish_obs(candles: List[Dict], bms_events: List[Dict] = None) -> List[Dict]:
    """Find bearish OBs, sorted by strength (unmitigated first)."""
    obs = detect_order_blocks(candles, bms_events)
    bearish = [o for o in obs if o["type"] == "bearish_ob"]
    bearish.sort(key=lambda x: (not x["mitigated"], x["strength"]), reverse=True)
    return bearish


def analyze(candles: List[Dict], bms_events: List[Dict] = None) -> Dict:
    """Full Order Block analysis."""
    obs = detect_order_blocks(candles, bms_events)
    bullish = [o for o in obs if o["type"] == "bullish_ob"]
    bearish = [o for o in obs if o["type"] == "bearish_ob"]
    
    current_price = candles[-1]["close"] if candles else 0
    
    # Score: unmitigated OB near price = higher score
    score = 0
    direction = "NEUTRAL"
    
    for ob in bullish:
        if not ob["mitigated"] and ob["zone_low"] <= current_price <= ob["zone_high"] * 1.02:
            score = 10
            direction = "LONG"
            break
    
    for ob in bearish:
        if not ob["mitigated"] and ob["zone_low"] * 0.98 <= current_price <= ob["zone_high"]:
            if score < 10:
                score = 10
                direction = "SHORT"
            break
    
    if score == 0:
        score = 3
    
    return {
        "order_blocks": obs,
        "bullish_obs": bullish,
        "bearish_obs": bearish,
        "score": min(score, 10),
        "direction": direction,
        "module": "order_blocks",
    }
