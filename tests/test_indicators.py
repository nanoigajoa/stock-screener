import pytest
import pandas as pd
import numpy as np
from screener.indicators import (
    calculate_indicators, 
    calc_atr_zones, 
    calc_stoch_rsi, 
    calc_bb_advanced, 
    calc_obv_divergence
)

@pytest.fixture
def mock_ohlcv():
    """100일간의 결정론적인 OHLCV 데이터 생성"""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100)
    
    # 사인파 기반의 주가 생성 (트렌드 + 변동성)
    x = np.linspace(0, 4 * np.pi, 100)
    close_vals = 100 + 10 * np.sin(x) + np.cumsum(np.random.randn(100))
    
    df = pd.DataFrame(index=dates)
    df["Close"] = close_vals
    df["High"]  = df["Close"] + np.random.rand(100) * 2
    df["Low"]   = df["Close"] - np.random.rand(100) * 2
    df["Open"]  = df["Close"].shift(1).fillna(100)
    df["Volume"] = np.random.randint(1000000, 5000000, size=100)
    
    return df

def test_calculate_indicators_structure(mock_ohlcv):
    result = calculate_indicators(mock_ohlcv)
    assert result is not None
    assert "price" in result
    assert "rsi" in result
    assert "macd" in result
    assert "bb_upper" in result
    assert isinstance(result["higher_high"], bool)

def test_calc_atr_zones_structure(mock_ohlcv):
    result = calc_atr_zones(mock_ohlcv)
    assert result is not None
    assert all(k in result for k in ["atr", "entry_low", "entry_high", "signal_stop"])
    # entry_low(MA60) > entry_high(MA20+0.5*ATR) when bearish — intentional empty zone

def test_calc_stoch_rsi_structure(mock_ohlcv):
    result = calc_stoch_rsi(mock_ohlcv)
    assert result is not None
    assert all(k in result for k in ["k", "d", "signal"])
    assert 0 <= result["k"] <= 1
    assert result["signal"] in ["buy", "sell", "neutral"]

def test_calc_bb_advanced_structure(mock_ohlcv):
    result = calc_bb_advanced(mock_ohlcv)
    assert result is not None
    assert "pct_b" in result
    assert "signal" in result

def test_calc_obv_divergence_structure(mock_ohlcv):
    result = calc_obv_divergence(mock_ohlcv)
    assert result is not None
    assert "obv_last" in result
    assert "divergence" in result
    assert result["divergence"] in ["bullish", "bearish", "none"]
