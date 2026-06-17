"""
Bitget API — Account & Trading Data Feed
Authentication required (HMAC SHA256).
"""

import os
import time
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"


def _get_creds() -> Dict[str, str]:
    """Load credentials from environment."""
    return {
        "api_key": os.getenv("BITGET_API_KEY", ""),
        "api_secret": os.getenv("BITGET_API_SECRET", ""),
        "passphrase": os.getenv("BITGET_API_PASSPHRASE", ""),
    }


def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    """Generate HMAC SHA256 signature for Bitget API."""
    creds = _get_creds()
    message = timestamp + method.upper() + path + body
    mac = hmac.new(
        creds["api_secret"].encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(mac.digest()).decode("utf-8")


def _headers(method: str, path: str, body: str = "") -> Dict[str, str]:
    """Build authenticated headers."""
    creds = _get_creds()
    timestamp = str(int(time.time() * 1000))
    sign = _sign(timestamp, method, path, body)
    
    return {
        "ACCESS-KEY": creds["api_key"],
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": creds["passphrase"],
        "Content-Type": "application/json",
        "locale": "en-US",
    }


def _get(path: str, params: Dict = None) -> Dict:
    """Authenticated GET request."""
    url = BASE_URL + path
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"{path}?{query}"
        url = f"{url}?{query}"
    
    headers = _headers("GET", path)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[BitgetFeed] GET {path} error: {e}")
        return {"code": "error", "msg": str(e), "data": None}


def _post(path: str, body: Dict) -> Dict:
    """Authenticated POST request."""
    url = BASE_URL + path
    body_str = json.dumps(body)
    headers = _headers("POST", path, body_str)
    
    try:
        resp = requests.post(url, headers=headers, data=body_str, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[BitgetFeed] POST {path} error: {e}")
        return {"code": "error", "msg": str(e), "data": None}


# ─── Account ──────────────────────────────────────────

def get_balance() -> Dict:
    """Get account balance."""
    result = _get("/api/v2/mix/account/accounts", {"productType": PRODUCT_TYPE})
    if result.get("code") == "00000" and result.get("data"):
        accounts = result["data"]
        if accounts:
            acc = accounts[0]
            return {
                "equity": float(acc.get("equity", 0)),
                "available": float(acc.get("available", 0)),
                "frozen": float(acc.get("frozen", 0)),
                "margin_used": float(acc.get("marginSize", 0)),
                "unrealized_pnl": float(acc.get("unrealizedPL", 0)),
                "coin": acc.get("marginCoin", "USDT"),
            }
    return {"equity": 0, "available": 0, "frozen": 0, "margin_used": 0, "unrealized_pnl": 0, "coin": "USDT"}


def get_positions() -> List[Dict]:
    """Get all open positions."""
    result = _get("/api/v2/mix/position/all-position", {"productType": PRODUCT_TYPE})
    if result.get("code") == "00000" and result.get("data"):
        positions = []
        for p in result["data"]:
            size = float(p.get("total", 0))
            if size == 0:
                continue
            positions.append({
                "symbol": p.get("symbol", ""),
                "side": p.get("holdSide", ""),  # "long" or "short"
                "size": size,
                "avg_price": float(p.get("averageOpenPrice", 0)),
                "mark_price": float(p.get("markPrice", 0)),
                "unrealized_pnl": float(p.get("unrealizedPL", 0)),
                "leverage": int(p.get("leverage", 1)),
                "margin_mode": p.get("marginMode", "crossed"),
                "liquidation_price": float(p.get("liquidationPrice", 0)),
            })
        return positions
    return []


def get_open_orders() -> List[Dict]:
    """Get pending orders."""
    result = _get("/api/v2/mix/order/orders-pending", {"productType": PRODUCT_TYPE})
    if result.get("code") == "00000" and result.get("data"):
        orders = []
        for o in result["data"].get("orderList", []):
            orders.append({
                "order_id": o.get("orderId", ""),
                "symbol": o.get("symbol", ""),
                "side": o.get("side", ""),
                "order_type": o.get("orderType", ""),
                "price": float(o.get("price", 0)),
                "size": float(o.get("size", 0)),
                "status": o.get("status", ""),
            })
        return orders
    return []


def get_trade_history(limit: int = 20) -> List[Dict]:
    """Get recent trade fills."""
    result = _get("/api/v2/mix/order/fills-history", {
        "productType": PRODUCT_TYPE,
        "limit": str(limit),
    })
    if result.get("code") == "00000" and result.get("data"):
        trades = []
        for t in result["data"].get("fillList", []):
            trades.append({
                "order_id": t.get("orderId", ""),
                "symbol": t.get("symbol", ""),
                "side": t.get("side", ""),
                "price": float(t.get("price", 0)),
                "size": float(t.get("size", 0)),
                "fee": float(t.get("fee", 0)),
                "pnl": float(t.get("pnl", 0)),
                "timestamp": int(t.get("cTime", 0)),
            })
        return trades
    return []


# ─── Market Data (Public — No Auth) ──────────────────

def get_ticker(symbol: str) -> Optional[Dict]:
    """Get ticker for a symbol (public, no auth)."""
    url = f"{BASE_URL}/api/v2/mix/market/ticker"
    params = {"symbol": symbol, "productType": PRODUCT_TYPE}
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "00000" and data.get("data"):
            t = data["data"]
            return {
                "symbol": t.get("symbol", ""),
                "price": float(t.get("lastPr", 0)),
                "change_24h": float(t.get("change24h", 0)),
                "high_24h": float(t.get("high24h", 0)),
                "low_24h": float(t.get("low24h", 0)),
                "volume_24h": float(t.get("baseVolume", 0)),
                "quote_volume_24h": float(t.get("quoteVolume", 0)),
            }
    except Exception as e:
        print(f"[BitgetFeed] Ticker {symbol} error: {e}")
    return None


def get_contract_info(symbol: str) -> Optional[Dict]:
    """Get contract specifications."""
    url = f"{BASE_URL}/api/v2/mix/market/contracts"
    params = {"productType": PRODUCT_TYPE, "symbol": symbol}
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "00000" and data.get("data"):
            c = data["data"][0] if isinstance(data["data"], list) else data["data"]
            return {
                "symbol": c.get("symbol", ""),
                "min_trade_num": float(c.get("minTradeNum", 1)),
                "price_scale": int(c.get("priceScale", 2)),
                "quantity_scale": int(c.get("quantityScale", 0)),
                "max_leverage": int(c.get("maxLeverage", 20)),
            }
    except Exception as e:
        print(f"[BitgetFeed] Contract info {symbol} error: {e}")
    return None


# ─── Trading Actions ──────────────────────────────────

def set_leverage(symbol: str, leverage: int, margin_mode: str = "crossed") -> bool:
    """Set leverage for a symbol."""
    result = _post("/api/v2/mix/account/set-leverage", {
        "productType": PRODUCT_TYPE,
        "symbol": symbol,
        "marginCoin": "USDT",
        "leverage": str(leverage),
        "marginMode": margin_mode,
    })
    return result.get("code") == "00000"


def set_position_mode(mode: str = "one_way_mode") -> bool:
    """Set position mode (one_way_mode or hedge_mode)."""
    result = _post("/api/v2/mix/account/set-position-mode", {
        "productType": PRODUCT_TYPE,
        "posMode": mode,
    })
    return result.get("code") == "00000"


def place_market_order(symbol: str, side: str, size: int, leverage: int = 15,
                       margin_mode: str = "crossed", sl_price: float = None,
                       tp_price: float = None) -> Dict:
    """Place a market order with optional TP/SL.
    
    Args:
        symbol: e.g. "SOLUSDT"
        side: "buy" (long) or "sell" (short)
        size: number of contracts (integer)
        leverage: leverage multiplier
        margin_mode: "crossed" or "isolated"
        sl_price: stop loss price (optional)
        tp_price: take profit price (optional)
    """
    body = {
        "productType": PRODUCT_TYPE,
        "symbol": symbol,
        "marginCoin": "USDT",
        "marginMode": margin_mode,
        "orderType": "market",
        "side": side,
        "size": str(int(size)),
    }
    
    if sl_price:
        body["presetStopLossPrice"] = str(sl_price)
    if tp_price:
        body["presetTakeProfitPrice"] = str(tp_price)
    
    result = _post("/api/v2/mix/order/place-order", body)
    return result


def close_position(symbol: str, side: str = None) -> Dict:
    """Close an open position."""
    body = {
        "productType": PRODUCT_TYPE,
        "symbol": symbol,
        "marginCoin": "USDT",
    }
    if side:
        body["holdSide"] = side
    return _post("/api/v2/mix/order/close-positions", body)


if __name__ == "__main__":
    print("=== Bitget Feed Test ===")
    
    # Public data (no auth needed)
    ticker = get_ticker("BTCUSDT")
    if ticker:
        print(f"BTC: ${ticker['price']:,.2f} ({ticker['change_24h']:+.2f}%)")
    
    contract = get_contract_info("SOLUSDT")
    if contract:
        print(f"SOL contract: min={contract['min_trade_num']}, max_lev={contract['max_leverage']}")
    
    # Authenticated (needs valid API key)
    balance = get_balance()
    print(f"\nBalance: ${balance['equity']:.2f} (available: ${balance['available']:.2f})")
    
    positions = get_positions()
    print(f"Open positions: {len(positions)}")
    for p in positions:
        print(f"  {p['symbol']} {p['side']} | Size: {p['size']} | PnL: ${p['unrealized_pnl']:.2f}")
