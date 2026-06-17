"""
Scanner Engine — Combines all 11 analysis modules into a single scoring system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from data import bitget_market
from analysis import (
    market_structure,
    supply_demand,
    order_blocks,
    fair_value_gap,
    liquidity,
    fibonacci,
    impulse_system,
    candlestick,
    volume_analysis,
    rsi_macd,
    amd_cycle,
)


# Module weights for scoring
MODULE_WEIGHTS = {
    "market_structure": 15,
    "supply_demand": 12,
    "order_blocks": 10,
    "fair_value_gap": 8,
    "liquidity": 8,
    "fibonacci": 12,
    "impulse_system": 10,
    "candlestick": 10,
    "volume": 8,
    "rsi_macd": 10,
    "amd": 10,
}


def analyze_single(symbol: str, timeframes: Dict[str, int] = None) -> Dict:
    """Run full analysis on a single symbol.
    
    Args:
        symbol: e.g. "SOLUSDT"
        timeframes: {"4h": 50, "1h": 100, "15m": 50}
    
    Returns:
        {
            "symbol": str,
            "score": int (0-100, capped),
            "direction": "LONG" | "SHORT" | "NEUTRAL",
            "modules": dict,
            "entry_zone": dict,
            "sl": float,
            "tp1": float,
            "tp2": float,
            "rr": float,
        }
    """
    if timeframes is None:
        timeframes = {"4h": 50, "1h": 100, "15m": 50}
    
    # Fetch multi-timeframe data
    multi_tf = bitget_market.get_multi_tf_data(symbol, timeframes)
    
    # Use 1h for main analysis (most balanced)
    candles_1h = multi_tf.get("1h", [])
    candles_4h = multi_tf.get("4h", [])
    candles_15m = multi_tf.get("15m", [])
    
    if not candles_1h or len(candles_1h) < 20:
        return {"symbol": symbol, "score": 0, "direction": "NEUTRAL", "error": "Insufficient data"}
    
    # Run all 11 modules
    results = {}
    
    # 1. Market Structure (on 1h)
    results["market_structure"] = market_structure.analyze(candles_1h)
    
    # 2. Supply & Demand (on 1h)
    results["supply_demand"] = supply_demand.analyze(candles_1h)
    
    # 3. Order Blocks (on 1h)
    bms_events = results["market_structure"].get("bms_events", [])
    results["order_blocks"] = order_blocks.analyze(candles_1h, bms_events)
    
    # 4. Fair Value Gap (on 1h)
    results["fair_value_gap"] = fair_value_gap.analyze(candles_1h)
    
    # 5. Liquidity (on 1h)
    results["liquidity"] = liquidity.analyze(candles_1h)
    
    # 6. Fibonacci (on 1h)
    results["fibonacci"] = fibonacci.analyze(candles_1h)
    
    # 7. Impulse System (multi-TF)
    results["impulse_system"] = impulse_system.analyze(candles_1h, multi_tf)
    
    # 8. Candlestick (on 15m for entry timing)
    results["candlestick"] = candlestick.analyze(candles_15m if candles_15m else candles_1h)
    
    # 9. Volume (on 1h)
    results["volume"] = volume_analysis.analyze(candles_1h)
    
    # 10. RSI + MACD (on 1h)
    results["rsi_macd"] = rsi_macd.analyze(candles_1h)
    
    # 11. AMD Cycle (on 1h)
    results["amd"] = amd_cycle.analyze(candles_1h)
    
    # ─── Calculate Total Score ────────────────────────
    total_score = 0
    directions = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
    
    for module_name, result in results.items():
        module_score = result.get("score", 0)
        max_weight = MODULE_WEIGHTS.get(module_name, 10)
        
        # Normalize: module_score is 0-max_weight, we scale to 0-100 contribution
        contribution = (module_score / max(max_weight, 1)) * max_weight
        total_score += contribution
        
        dir = result.get("direction", "NEUTRAL")
        if dir in directions:
            directions[dir] += 1
    
    # Cap at 100
    total_score = min(int(total_score), 100)
    
    # ─── Determine Direction ─────────────────────────
    # Majority vote from modules, with impulse system having veto power
    impulse_dir = results["impulse_system"].get("combined_direction", "NEUTRAL")
    
    if impulse_dir != "NEUTRAL":
        # Impulse system overrides if strong signal
        direction = impulse_dir
    elif directions["LONG"] > directions["SHORT"]:
        direction = "LONG"
    elif directions["SHORT"] > directions["LONG"]:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"
    
    # ─── Calculate Entry/SL/TP ──────────────────────
    current_price = candles_1h[-1]["close"]
    entry_zone = _calculate_entry_zone(results, current_price, direction)
    sl_tp = _calculate_sl_tp(results, current_price, direction)
    
    return {
        "symbol": symbol,
        "score": total_score,
        "direction": direction,
        "current_price": current_price,
        "modules": results,
        "entry_zone": entry_zone,
        "sl": sl_tp["sl"],
        "tp1": sl_tp["tp1"],
        "tp2": sl_tp["tp2"],
        "rr": sl_tp["rr"],
        "direction_votes": directions,
        "impulse_direction": impulse_dir,
    }


def _calculate_entry_zone(results: Dict, current_price: float, direction: str) -> Dict:
    """Calculate optimal entry zone from OB/FVG/S&D zones."""
    zones = []
    
    # Collect zones from relevant modules
    for module_name in ["order_blocks", "fair_value_gap", "supply_demand"]:
        module_data = results.get(module_name, {})
        
        if module_name == "order_blocks":
            obs = module_data.get("bullish_obs" if direction == "LONG" else "bearish_obs", [])
            for ob in obs[:2]:
                zones.append({"low": ob["zone_low"], "high": ob["zone_high"], "source": "ob"})
        
        elif module_name == "fair_value_gap":
            fvgs = module_data.get("unfilled_bullish" if direction == "LONG" else "unfilled_bearish", [])
            for fvg in fvgs[:2]:
                zones.append({"low": fvg["gap_low"], "high": fvg["gap_high"], "source": "fvg"})
        
        elif module_name == "supply_demand":
            z = module_data.get("demand_zones" if direction == "LONG" else "supply_zones", [])
            for zone in z[:2]:
                zones.append({"low": zone["zone_low"], "high": zone["zone_high"], "source": "snd"})
    
    if not zones:
        # Fallback: use current price ± 0.5%
        return {
            "low": current_price * 0.995,
            "high": current_price * 1.005,
            "source": "fallback",
        }
    
    # Find zone closest to current price
    best = min(zones, key=lambda z: abs((z["low"] + z["high"]) / 2 - current_price))
    return best


def _calculate_sl_tp(results: Dict, current_price: float, direction: str) -> Dict:
    """Calculate SL, TP1, TP2 based on structure and zones."""
    # Use ATR-like calculation from recent range
    ms = results.get("market_structure", {})
    swing_high = ms.get("swing_highs", [{}])
    swing_low = ms.get("swing_lows", [{}])
    
    # Estimate SL distance (2-4% of price)
    sl_distance = current_price * 0.03  # 3% default
    
    if direction == "LONG":
        sl = current_price - sl_distance
        tp1 = current_price + sl_distance * 2.5  # RR 1:2.5
        tp2 = current_price + sl_distance * 4.0  # RR 1:4
    elif direction == "SHORT":
        sl = current_price + sl_distance
        tp1 = current_price - sl_distance * 2.5
        tp2 = current_price - sl_distance * 4.0
    else:
        sl = current_price
        tp1 = current_price
        tp2 = current_price
    
    rr = 2.5 if direction != "NEUTRAL" else 0
    
    return {"sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr}


def scan_multiple(symbols: List[str], timeframes: Dict[str, int] = None,
                  min_score: int = 60) -> List[Dict]:
    """Scan multiple symbols and return sorted by score.
    
    Args:
        symbols: list of symbol strings
        timeframes: timeframe config
        min_score: minimum score threshold
    
    Returns:
        List of analysis results, sorted by score descending, filtered by min_score and clear direction.
    """
    import time as _time
    
    results = []
    total = len(symbols)
    
    for i, symbol in enumerate(symbols):
        print(f"[Scanner] ({i+1}/{total}) Analyzing {symbol}...")
        try:
            result = analyze_single(symbol, timeframes)
            if result.get("score", 0) >= min_score and result.get("direction") != "NEUTRAL":
                results.append(result)
                print(f"  → Score: {result['score']}/100 | Direction: {result['direction']}")
            else:
                print(f"  → Score: {result.get('score', 0)}/100 | Direction: {result.get('direction', 'NEUTRAL')} — SKIP")
        except Exception as e:
            print(f"  → Error: {e}")
        
        _time.sleep(0.3)  # Rate limit
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


if __name__ == "__main__":
    import yaml
    
    # Load config
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Test single analysis
    print("=== Scanner Test ===")
    result = analyze_single("SOLUSDT", config["scanner"]["candle_limits"])
    
    print(f"\nSymbol: {result['symbol']}")
    print(f"Score: {result['score']}/100")
    print(f"Direction: {result['direction']}")
    print(f"Current Price: ${result['current_price']:.2f}")
    print(f"Entry Zone: ${result['entry_zone']['low']:.2f} - ${result['entry_zone']['high']:.2f}")
    print(f"SL: ${result['sl']:.2f}")
    print(f"TP1: ${result['tp1']:.2f} | TP2: ${result['tp2']:.2f}")
    print(f"RR: 1:{result['rr']}")
    print(f"\nModule Scores:")
    for name, data in result["modules"].items():
        print(f"  {name}: {data.get('score', 0)} | {data.get('direction', 'N/A')}")
