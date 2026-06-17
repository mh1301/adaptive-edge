"""
Binance Public API — OHLCV Data Feed
No authentication required. Used for chart analysis.
"""

import requests
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

BASE_URL = "https://api.binance.com/api/v3"


def get_klines(symbol: str, interval: str, limit: int = 100) -> List[Dict]:
    """Fetch OHLCV candles from Binance."""
    url = f"{BASE_URL}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        print(f"[BinanceFeed] Error fetching {symbol} {interval}: {e}")
        return []
    
    candles = []
    for k in raw:
        candles.append({
            "time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc),
            "quote_volume": float(k[7]),
            "trades": int(k[8]),
            "taker_buy_volume": float(k[9]),
            "taker_buy_quote_volume": float(k[10]),
        })
    return candles


def get_ticker_24hr(symbol: Optional[str] = None) -> List[Dict]:
    """Get 24hr ticker stats. If symbol is None, returns all tickers."""
    url = f"{BASE_URL}/ticker/24hr"
    params = {}
    if symbol:
        params["symbol"] = symbol
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception as e:
        print(f"[BinanceFeed] Error fetching ticker: {e}")
        return []


def get_price(symbol: str) -> Optional[float]:
    """Get current price for a symbol."""
    url = f"{BASE_URL}/ticker/price"
    params = {"symbol": symbol}
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception as e:
        print(f"[BinanceFeed] Error fetching price for {symbol}: {e}")
        return None


def get_multi_tf_data(symbol: str, timeframes: Dict[str, int]) -> Dict[str, List[Dict]]:
    """Fetch multiple timeframes for a symbol.
    
    Args:
        symbol: e.g. "SOLUSDT"
        timeframes: e.g. {"4h": 50, "1h": 100, "15m": 50}
    
    Returns:
        Dict mapping timeframe to candle list
    """
    result = {}
    for tf, limit in timeframes.items():
        result[tf] = get_klines(symbol, tf, limit)
        time.sleep(0.1)  # Rate limit: 1200 weight/min, klines = 5-10 weight
    return result


def get_top_usdt_pairs(min_volume_usd: float = 5_000_000) -> List[Dict]:
    """Get top USDT perpetual pairs by 24h volume."""
    tickers = get_ticker_24hr()
    usdt_pairs = []
    
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        vol_usd = float(t.get("quoteVolume", 0))
        if vol_usd < min_volume_usd:
            continue
        usdt_pairs.append({
            "symbol": sym,
            "price": float(t.get("lastPrice", 0)),
            "change_24h": float(t.get("priceChangePercent", 0)),
            "volume_usd": vol_usd,
            "high_24h": float(t.get("highPrice", 0)),
            "low_24h": float(t.get("lowPrice", 0)),
        })
    
    # Sort by volume descending
    usdt_pairs.sort(key=lambda x: x["volume_usd"], reverse=True)
    return usdt_pairs


if __name__ == "__main__":
    # Quick test
    print("=== Binance Feed Test ===")
    
    price = get_price("BTCUSDT")
    print(f"BTC Price: ${price:,.2f}")
    
    candles = get_klines("SOLUSDT", "1h", 5)
    print(f"\nSOL 1H candles (last 5):")
    for c in candles:
        print(f"  {c['time'].strftime('%Y-%m-%d %H:%M')} | O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f} V:{c['volume']:.0f}")
    
    top = get_top_usdt_pairs(5_000_000)[:5]
    print(f"\nTop 5 USDT pairs by volume:")
    for p in top:
        print(f"  {p['symbol']}: ${p['price']:.4f} ({p['change_24h']:+.2f}%) Vol: ${p['volume_usd']/1e6:.1f}M")
