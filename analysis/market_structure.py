"""
Market Structure Analysis
Detect Swing Highs/Lows, HH/HL/LH/LL sequences, BMS (Break Market Structure), CHoCH (Change of Character).
"""

from typing import List, Dict, Tuple, Optional


def find_swing_points(candles: List[Dict], lookback: int = 2) -> Tuple[List[Dict], List[Dict]]:
    """Find swing highs and swing lows.
    
    Swing High: candle with high higher than `lookback` candles on each side.
    Swing Low: candle with low lower than `lookback` candles on each side.
    """
    highs = []
    lows = []
    
    for i in range(lookback, len(candles) - lookback):
        is_swing_high = True
        is_swing_low = True
        
        for j in range(1, lookback + 1):
            if candles[i]["high"] <= candles[i - j]["high"] or candles[i]["high"] <= candles[i + j]["high"]:
                is_swing_high = False
            if candles[i]["low"] >= candles[i - j]["low"] or candles[i]["low"] >= candles[i + j]["low"]:
                is_swing_low = False
        
        if is_swing_high:
            highs.append({
                "index": i,
                "price": candles[i]["high"],
                "time": candles[i]["time"],
            })
        if is_swing_low:
            lows.append({
                "index": i,
                "price": candles[i]["low"],
                "time": candles[i]["time"],
            })
    
    return highs, lows


def map_structure(swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict:
    """Map market structure from swing points.
    
    Returns:
        {
            "trend": "bullish" | "bearish" | "neutral",
            "sequence": ["HH", "HL", "HH", ...],
            "last_high": {...},
            "last_low": {...},
            "hh_count": int,
            "hl_count": int,
            "lh_count": int,
            "ll_count": int,
        }
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {
            "trend": "neutral",
            "sequence": [],
            "last_high": swing_highs[-1] if swing_highs else None,
            "last_low": swing_lows[-1] if swing_lows else None,
            "hh_count": 0, "hl_count": 0, "lh_count": 0, "ll_count": 0,
        }
    
    # Sort by index
    sorted_highs = sorted(swing_highs, key=lambda x: x["index"])
    sorted_lows = sorted(swing_lows, key=lambda x: x["index"])
    
    # Determine HH/LH for highs
    high_labels = []
    hh_count = 0
    lh_count = 0
    for i in range(1, len(sorted_highs)):
        if sorted_highs[i]["price"] > sorted_highs[i-1]["price"]:
            high_labels.append("HH")
            hh_count += 1
        else:
            high_labels.append("LH")
            lh_count += 1
    
    # Determine HL/LL for lows
    low_labels = []
    hl_count = 0
    ll_count = 0
    for i in range(1, len(sorted_lows)):
        if sorted_lows[i]["price"] > sorted_lows[i-1]["price"]:
            low_labels.append("HL")
            hl_count += 1
        else:
            low_labels.append("LL")
            ll_count += 1
    
    # Interleave into sequence
    sequence = []
    hi_idx = 0
    lo_idx = 0
    all_points = []
    for h in sorted_highs:
        all_points.append(("H", h))
    for l in sorted_lows:
        all_points.append(("L", l))
    all_points.sort(key=lambda x: x[1]["index"])
    
    prev_h_price = None
    prev_l_price = None
    for ptype, point in all_points:
        if ptype == "H":
            if prev_h_price is not None:
                sequence.append("HH" if point["price"] > prev_h_price else "LH")
            prev_h_price = point["price"]
        else:
            if prev_l_price is not None:
                sequence.append("HL" if point["price"] > prev_l_price else "LL")
            prev_l_price = point["price"]
    
    # Determine trend
    if hh_count > lh_count and hl_count > ll_count:
        trend = "bullish"
    elif lh_count > hh_count and ll_count > hl_count:
        trend = "bearish"
    else:
        trend = "neutral"
    
    return {
        "trend": trend,
        "sequence": sequence,
        "last_high": sorted_highs[-1],
        "last_low": sorted_lows[-1],
        "hh_count": hh_count,
        "hl_count": hl_count,
        "lh_count": lh_count,
        "ll_count": ll_count,
    }


def detect_bms(candles: List[Dict], swing_highs: List[Dict], swing_lows: List[Dict]) -> List[Dict]:
    """Detect Break of Market Structure (BMS) events.
    
    BMS Bullish: candle closes above last swing high.
    BMS Bearish: candle closes below last swing low.
    """
    events = []
    
    if not swing_highs or not swing_lows:
        return events
    
    sorted_highs = sorted(swing_highs, key=lambda x: x["index"])
    sorted_lows = sorted(swing_lows, key=lambda x: x["index"])
    
    # Check each candle after the last swing points
    last_sh = sorted_highs[-1]
    last_sl = sorted_lows[-1]
    
    for i in range(max(last_sh["index"], last_sl["index"]) + 1, len(candles)):
        c = candles[i]
        
        # Bullish BMS: close above last swing high
        if c["close"] > last_sh["price"]:
            events.append({
                "type": "BMS_BULLISH",
                "index": i,
                "price": c["close"],
                "broken_level": last_sh["price"],
                "time": c["time"],
            })
            # Update last_sh for subsequent detection
            last_sh = {"index": i, "price": c["high"], "time": c["time"]}
        
        # Bearish BMS: close below last swing low
        if c["close"] < last_sl["price"]:
            events.append({
                "type": "BMS_BEARISH",
                "index": i,
                "price": c["close"],
                "broken_level": last_sl["price"],
                "time": c["time"],
            })
            last_sl = {"index": i, "price": c["low"], "time": c["time"]}
    
    return events


def detect_choch(candles: List[Dict], structure: Dict) -> List[Dict]:
    """Detect Change of Character (CHoCH).
    
    CHoCH Bullish: In downtrend (LH+LL), candle closes above last LH.
    CHoCH Bearish: In uptrend (HH+HL), candle closes below last HL.
    """
    events = []
    trend = structure["trend"]
    
    if trend == "neutral":
        return events
    
    sorted_highs = sorted(
        [h for h in ([structure["last_high"]] if structure["last_high"] else [])],
        key=lambda x: x["index"]
    )
    sorted_lows = sorted(
        [l for l in ([structure["last_low"]] if structure["last_low"] else [])],
        key=lambda x: x["index"]
    )
    
    if not sorted_highs or not sorted_lows:
        return events
    
    last_h = sorted_highs[-1]
    last_l = sorted_lows[-1]
    
    # Find the start point for checking
    start_idx = max(last_h["index"], last_l["index"]) + 1
    
    for i in range(start_idx, len(candles)):
        c = candles[i]
        
        # CHoCH Bullish (breaking bearish structure)
        if trend == "bearish" and c["close"] > last_h["price"]:
            events.append({
                "type": "CHOCH_BULLISH",
                "index": i,
                "price": c["close"],
                "broken_level": last_h["price"],
                "time": c["time"],
            })
        
        # CHoCH Bearish (breaking bullish structure)
        if trend == "bullish" and c["close"] < last_l["price"]:
            events.append({
                "type": "CHOCH_BEARISH",
                "index": i,
                "price": c["close"],
                "broken_level": last_l["price"],
                "time": c["time"],
            })
    
    return events


def analyze(candles: List[Dict]) -> Dict:
    """Full market structure analysis.
    
    Returns:
        {
            "trend": str,
            "swing_highs": list,
            "swing_lows": list,
            "structure": dict,
            "bms_events": list,
            "choch_events": list,
            "score": int (0-15),
            "direction": "LONG" | "SHORT" | "NEUTRAL",
        }
    """
    if len(candles) < 10:
        return {
            "trend": "neutral", "swing_highs": [], "swing_lows": [],
            "structure": {"trend": "neutral", "sequence": [], "last_high": None, "last_low": None,
                          "hh_count": 0, "hl_count": 0, "lh_count": 0, "ll_count": 0},
            "bms_events": [], "choch_events": [],
            "score": 0, "direction": "NEUTRAL",
        }
    
    swing_highs, swing_lows = find_swing_points(candles, lookback=2)
    structure = map_structure(swing_highs, swing_lows)
    bms_events = detect_bms(candles, swing_highs, swing_lows)
    choch_events = detect_choch(candles, structure)
    
    # Score: HH+HL = bullish, LH+LL = bearish
    score = 0
    direction = "NEUTRAL"
    
    if structure["trend"] == "bullish":
        score = 15
        direction = "LONG"
    elif structure["trend"] == "bearish":
        score = 15
        direction = "SHORT"
    else:
        score = 5
        direction = "NEUTRAL"
    
    # Bonus for recent BMS
    if bms_events:
        last_bms = bms_events[-1]
        if last_bms["type"] == "BMS_BULLISH" and direction == "LONG":
            score = min(score + 3, 18)
        elif last_bms["type"] == "BMS_BEARISH" and direction == "SHORT":
            score = min(score + 3, 18)
    
    return {
        "trend": structure["trend"],
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "structure": structure,
        "bms_events": bms_events,
        "choch_events": choch_events,
        "score": min(score, 18),
        "direction": direction,
    }
