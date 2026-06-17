"""
Elder's Impulse System (13 EMA + MACD Histogram)
GREEN = bullish momentum (LONG only)
RED = bearish momentum (SHORT only)
BLUE = divergence (watch for reversal)
"""

from typing import List, Dict


def _ema(data: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if not data:
        return []
    k = 2 / (period + 1)
    result = [data[0]]
    for i in range(1, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result


def _macd_histogram(closes: List[float]) -> List[float]:
    """Calculate MACD Histogram (MACD Line - Signal Line)."""
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
    signal = _ema(macd_line, 9)
    return [macd_line[i] - signal[i] for i in range(len(closes))]


def get_signal(candles: List[Dict]) -> Dict:
    """Get impulse signal for a set of candles.
    
    Returns:
        {
            "signal": "GREEN" | "RED" | "BLUE",
            "ema13_slope": float,
            "macd_hist_slope": float,
            "direction": "LONG" | "SHORT" | "NEUTRAL",
            "score": int (0-10),
        }
    """
    if len(candles) < 30:
        return {"signal": "BLUE", "direction": "NEUTRAL", "score": 0}
    
    closes = [c["close"] for c in candles]
    
    # 13 EMA
    ema13 = _ema(closes, 13)
    ema13_slope = ema13[-1] - ema13[-3]  # 2-bar slope
    
    # MACD Histogram
    macd_hist = _macd_histogram(closes)
    macd_hist_slope = macd_hist[-1] - macd_hist[-3]  # 2-bar slope
    
    # Determine signal
    if ema13_slope > 0 and macd_hist_slope > 0:
        signal = "GREEN"
        direction = "LONG"
        score = 10
    elif ema13_slope < 0 and macd_hist_slope < 0:
        signal = "RED"
        direction = "SHORT"
        score = 10
    else:
        signal = "BLUE"
        direction = "NEUTRAL"
        score = 5
    
    return {
        "signal": signal,
        "ema13_slope": ema13_slope,
        "macd_hist_slope": macd_hist_slope,
        "direction": direction,
        "score": score,
    }


def get_multi_tf_signal(multi_tf_candles: Dict[str, List[Dict]]) -> Dict:
    """Get impulse signals across multiple timeframes.
    
    Args:
        multi_tf_candles: {"4h": [...], "1h": [...], "15m": [...]}
    
    Returns:
        {
            "htf_signal": str,
            "ltf_signal": str,
            "combined_direction": str,
            "score": int,
            "details": dict,
        }
    """
    signals = {}
    for tf, candles in multi_tf_candles.items():
        signals[tf] = get_signal(candles)
    
    # HTF takes priority
    # Assuming first key is HTF, last is LTF
    tfs = list(signals.keys())
    htf = signals[tfs[0]] if tfs else {"signal": "BLUE", "direction": "NEUTRAL"}
    ltf = signals[tfs[-1]] if tfs else {"signal": "BLUE", "direction": "NEUTRAL"}
    
    # Combined direction
    if htf["direction"] == ltf["direction"] and htf["direction"] != "NEUTRAL":
        combined = htf["direction"]
        score = 10  # High conviction
    elif htf["direction"] != "NEUTRAL" and ltf["direction"] == "NEUTRAL":
        combined = htf["direction"]
        score = 7  # HTF aligned, LTF neutral
    elif htf["direction"] == "NEUTRAL":
        combined = ltf["direction"]
        score = 5  # HTF neutral, rely on LTF
    else:
        # Conflicting — HTF overrides
        combined = htf["direction"]
        score = 3  # Low conviction
    
    return {
        "htf_signal": htf["signal"],
        "ltf_signal": ltf["signal"],
        "combined_direction": combined,
        "score": score,
        "details": signals,
    }


def analyze(candles: List[Dict], multi_tf_candles: Dict[str, List[Dict]] = None) -> Dict:
    """Full impulse analysis."""
    if multi_tf_candles:
        result = get_multi_tf_signal(multi_tf_candles)
    else:
        single = get_signal(candles)
        result = {
            "htf_signal": single["signal"],
            "ltf_signal": single["signal"],
            "combined_direction": single["direction"],
            "score": single["score"],
            "details": {"1h": single},
        }
    
    result["module"] = "impulse_system"
    return result
