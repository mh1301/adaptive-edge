"""
Bitget Public API - Market Data Feed
No authentication required for market data.
Used by scanner for OHLCV candle data.
"""

import requests
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"

# Map config timeframes to Bitget granularity
TF_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1H", "4h": "4H", "6h": "6H",
    "12h": "12H", "1d": "1D", "1w": "1W", "1M": "1M",
}


def _granularity(tf: str) -> str:
    """Convert config timeframe to Bitget granularity."""
    return TF_MAP.get(tf, tf)


def get_klines(symbol: str, interval: str, limit: int = 100) -> List[Dict]:
    """Fetch OHLCV candles from Bitget."""
    url = f"{BASE_URL}/api/v2/mix/market/candles"
    params = {
        "symbol": symbol,
        "granularity": _granularity(interval),
        "limit": str(min(limit, 1000)),
        "productType": PRODUCT_TYPE,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != "00000":
            print(f"[BitgetFeed] Klines error {symbol} {interval}: {data.get('msg')}")
            return []
        
        raw = data.get("data", [])
    except Exception as e:
        print(f"[BitgetFeed] Error fetching {symbol} {interval}: {e}")
        return []
    
    # Bitget format: [timestamp, open, high, low, close, volume, quoteVolume]
    # Sorted oldest first (reverse of what we need)
    candles = []
    for k in raw:  # Reverse to get oldest first
        candles.append({
            "time": datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "quote_volume": float(k[6]) if len(k) > 6 else 0,
        })
    return candles


def get_ticker_24hr(symbol: Optional[str] = None) -> List[Dict]:
    """Get 24hr ticker stats."""
    if symbol:
        url = f"{BASE_URL}/api/v2/mix/market/ticker"
        params = {"symbol": symbol, "productType": PRODUCT_TYPE}
    else:
        url = f"{BASE_URL}/api/v2/mix/market/tickers"
        params = {"productType": PRODUCT_TYPE}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != "00000":
            print(f"[BitgetFeed] Ticker error: {data.get('msg')}")
            return []
        
        raw = data.get("data", [])
        if isinstance(raw, dict):
            raw = [raw]
        
        results = []
        for t in raw:
            results.append({
                "symbol": t.get("symbol", ""),
                "price": float(t.get("lastPr", 0)),
                "change_24h": float(t.get("change24h", 0)) * 100,  # Convert to %
                "volume_usd": float(t.get("quoteVolume", t.get("usdtVolume", 0))),
                "high_24h": float(t.get("high24h", 0)),
                "low_24h": float(t.get("low24h", 0)),
            })
        return results
    except Exception as e:
        print(f"[BitgetFeed] Error fetching ticker: {e}")
        return []


def get_price(symbol: str) -> Optional[float]:
    """Get current price for a symbol."""
    url = f"{BASE_URL}/api/v2/mix/market/ticker"
    params = {"symbol": symbol, "productType": PRODUCT_TYPE}
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "00000" and data.get("data"):
            return float(data["data"][0]["lastPr"])
    except Exception as e:
        print(f"[BitgetFeed] Error fetching price for {symbol}: {e}")
    return None


def get_multi_tf_data(symbol: str, timeframes: Dict[str, int]) -> Dict[str, List[Dict]]:
    """Fetch multiple timeframes for a symbol."""
    result = {}
    for tf, limit in timeframes.items():
        result[tf] = get_klines(symbol, tf, limit)
        time.sleep(0.1)
    return result


def get_top_usdt_pairs(min_volume_usd: float = 5_000_000) -> List[Dict]:
    """Get top USDT pairs by 24h volume."""
    tickers = get_ticker_24hr()
    usdt_pairs = []
    
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        vol_usd = t.get("volume_usd", 0)
        if vol_usd < min_volume_usd:
            continue
        usdt_pairs.append(t)
    
    usdt_pairs.sort(key=lambda x: x["volume_usd"], reverse=True)
    return usdt_pairs


if __name__ == "__main__":
    print("=== Bitget Feed Test ===")
    
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
