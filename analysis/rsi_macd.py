"""
RSI + MACD Analysis — Overbought/oversold, divergence detection.
"""

from typing import List, Dict


def _ema(data: List[float], period: int) -> List[float]:
    if not data:
        return []
    k = 2 / (period + 1)
    result = [data[0]]
    for i in range(1, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result


def _rsi(closes: List[float], period: int = 14) -> float:
    """Calculate RSI."""
    if len(closes) < period + 1:
        return 50
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(closes: List[float]) -> Dict:
    """Calculate MACD."""
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
    signal = _ema(macd_line, 9)
    histogram = [macd_line[i] - signal[i] for i in range(len(closes))]
    
    return {
        "macd": macd_line[-1],
        "signal": signal[-1],
        "histogram": histogram[-1],
        "histogram_prev": histogram[-2] if len(histogram) > 1 else 0,
    }


def analyze(candles: List[Dict]) -> Dict:
    """Full RSI + MACD analysis."""
    if len(candles) < 30:
        return {"score": 0, "direction": "NEUTRAL", "module": "rsi_macd"}
    
    closes = [c["close"] for c in candles]
    
    rsi = _rsi(closes)
    macd = _macd(closes)
    
    score = 0
    direction = "NEUTRAL"
    
    # RSI overbought/oversold
    if rsi < 30:
        score = 8
        direction = "LONG"  # Oversold = potential bounce
    elif rsi > 70:
        score = 8
        direction = "SHORT"  # Overbought = potential drop
    elif 40 < rsi < 60:
        score = 3
    else:
        score = 5
    
    # MACD confirmation
    if macd["histogram"] > 0 and macd["histogram"] > macd["histogram_prev"]:
        if direction == "LONG":
            score = min(score + 3, 10)
        elif direction == "NEUTRAL":
            direction = "LONG"
            score = 5
    elif macd["histogram"] < 0 and macd["histogram"] < macd["histogram_prev"]:
        if direction == "SHORT":
            score = min(score + 3, 10)
        elif direction == "NEUTRAL":
            direction = "SHORT"
            score = 5
    
    return {
        "rsi": rsi,
        "macd": macd,
        "score": min(score, 10),
        "direction": direction,
        "module": "rsi_macd",
    }
