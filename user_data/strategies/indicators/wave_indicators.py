"""
Wave Indicators - Elliott Wave Lite for AI Trading
===================================================
Provides objective, non-repainting features based on Elliott Wave principles:
- Fibonacci Retracement levels (key support/resistance)
- Fibonacci Extensions (price targets)
- Awesome Oscillator (wave momentum identification)
- Wave structure proxies (without subjective wave counting)

Author: AI Trading Bot
Created: 2025-01-24
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Tuple, Optional


def safe_atr(high, low, close, length=14) -> pd.Series:
    """Safely calculate ATR, returning NaN series if insufficient data"""
    try:
        atr = ta.atr(high, low, close, length=length)
        if atr is None:
            return pd.Series(np.nan, index=high.index)
        return atr.replace(0, np.nan)
    except Exception:
        return pd.Series(np.nan, index=high.index)


def safe_ema(series, length=20) -> pd.Series:
    """Safely calculate EMA, returning NaN series if insufficient data"""
    try:
        ema = ta.ema(series, length=length)
        if ema is None:
            return pd.Series(np.nan, index=series.index)
        return ema
    except Exception:
        return pd.Series(np.nan, index=series.index)


class WaveIndicators:
    """
    Elliott Wave Lite - Objective features for AI
    
    Philosophy:
    - NO wave counting (too subjective, repaints)
    - YES Fibonacci levels (objective math)
    - YES momentum oscillators (wave identification)
    - YES swing detection (structure analysis)
    
    Performance optimized: Uses dict collection + single pd.concat to avoid fragmentation
    """
    
    # Fibonacci ratios used in Elliott Wave
    FIB_RETRACEMENT = [0.236, 0.382, 0.5, 0.618, 0.786]
    FIB_EXTENSION = [1.0, 1.272, 1.618, 2.0, 2.618]
    
    @staticmethod
    def add_all_features(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """Add all wave-related features to dataframe using optimized single concat"""
        # Collect all features in a dict first to avoid fragmentation
        features = {}
        
        WaveIndicators._calc_fibonacci_retracement(df, prefix, features)
        WaveIndicators._calc_fibonacci_extensions(df, prefix, features)
        WaveIndicators._calc_awesome_oscillator(df, prefix, features)
        WaveIndicators._calc_wave_momentum(df, prefix, features)
        WaveIndicators._calc_swing_structure(df, prefix, features)
        
        # Single concat - much faster than individual inserts
        if features:
            features_df = pd.DataFrame(features, index=df.index)
            # Fill NaN values
            features_df = features_df.ffill().fillna(0)
            df = pd.concat([df, features_df], axis=1)
        
        return df
    
    @staticmethod
    def find_swing_points(df: pd.DataFrame, lookback: int = 20) -> Tuple[pd.Series, pd.Series]:
        """
        Find recent swing high and swing low points
        
        Returns:
            Tuple of (swing_high, swing_low) Series
        """
        high = df['high']
        low = df['low']
        
        # Rolling max/min for swing detection
        swing_high = high.rolling(lookback, center=True).max()
        swing_low = low.rolling(lookback, center=True).min()
        
        return swing_high, swing_low
    
    @staticmethod
    def _calc_fibonacci_retracement(df: pd.DataFrame, prefix: str, features: dict, lookback: int = 50) -> None:
        """Calculate Fibonacci retracement features into dict"""
        high = df['high'].rolling(lookback).max()
        low = df['low'].rolling(lookback).min()
        close = df['close']
        
        price_range = high - low
        price_range = price_range.replace(0, np.nan)
        
        # Current position in range (0 = low, 1 = high)
        position = (close - low) / price_range
        features[f'{prefix}%-fib_position'] = position
        
        # Distance from each Fibonacci level
        for fib in WaveIndicators.FIB_RETRACEMENT:
            fib_price = low + (price_range * fib)
            features[f'{prefix}%-fib_dist_{int(fib*1000)}'] = (close - fib_price) / price_range
        
        # Which Fib zone are we in? (0-4)
        features[f'{prefix}%-fib_zone'] = pd.cut(
            position, 
            bins=[-np.inf, 0.236, 0.382, 0.5, 0.618, 0.786, np.inf],
            labels=[0, 1, 2, 3, 4, 5]
        ).astype(float)
        
        # Is price near a Fib level? (within 2%)
        for fib in WaveIndicators.FIB_RETRACEMENT:
            dist = features[f'{prefix}%-fib_dist_{int(fib*1000)}']
            features[f'{prefix}%-fib_near_{int(fib*1000)}'] = (abs(dist) < 0.02).astype(float)
    
    @staticmethod
    def _calc_fibonacci_extensions(df: pd.DataFrame, prefix: str, features: dict, lookback: int = 50) -> None:
        """Calculate Fibonacci extension features into dict"""
        high = df['high'].rolling(lookback).max()
        low = df['low'].rolling(lookback).min()
        close = df['close']
        
        price_range = high - low
        price_range = price_range.replace(0, np.nan)
        
        # Extension above high
        for ext in WaveIndicators.FIB_EXTENSION:
            ext_price = high + (price_range * (ext - 1))
            features[f'{prefix}%-fib_ext_up_{int(ext*1000)}'] = (close - ext_price) / price_range
        
        # Extension below low  
        for ext in WaveIndicators.FIB_EXTENSION:
            ext_price = low - (price_range * (ext - 1))
            features[f'{prefix}%-fib_ext_down_{int(ext*1000)}'] = (close - ext_price) / price_range
    
    @staticmethod
    def _calc_awesome_oscillator(df: pd.DataFrame, prefix: str, features: dict) -> None:
        """Calculate Awesome Oscillator features into dict"""
        median_price = (df['high'] + df['low']) / 2
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        
        atr = safe_atr(df['high'], df['low'], df['close'], length=14)
        
        features[f'{prefix}%-wave_ao'] = ao / atr
        features[f'{prefix}%-wave_ao_hist'] = ao.diff() / atr
        
        ao_hist = features[f'{prefix}%-wave_ao_hist']
        features[f'{prefix}%-wave_ao_accel'] = ao_hist.diff() if isinstance(ao_hist, pd.Series) else pd.Series(ao_hist).diff()
        
        features[f'{prefix}%-wave_ao_above_zero'] = (ao > 0).astype(float)
        
        ao_cross = np.where(
            (ao > 0) & (ao.shift(1) <= 0), 1,
            np.where((ao < 0) & (ao.shift(1) >= 0), -1, 0)
        )
        features[f'{prefix}%-wave_ao_cross'] = ao_cross
        
        ao_peak = (ao.shift(1) > ao) & (ao.shift(1) > ao.shift(2))
        features[f'{prefix}%-wave_ao_peak'] = ao_peak.astype(float)
    
    @staticmethod
    def _calc_wave_momentum(df: pd.DataFrame, prefix: str, features: dict) -> None:
        """Calculate wave momentum features into dict"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        median_price = (high + low) / 2
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        
        price_higher = close > close.rolling(10).max().shift(1)
        price_lower = close < close.rolling(10).min().shift(1)
        ao_higher = ao > ao.rolling(10).max().shift(1)
        ao_lower = ao < ao.rolling(10).min().shift(1)
        
        bearish_div = (price_higher & ao_lower).astype(float)
        bullish_div = (price_lower & ao_higher).astype(float)
        features[f'{prefix}%-wave_bearish_div'] = bearish_div
        features[f'{prefix}%-wave_bullish_div'] = bullish_div
        
        adx = ta.adx(high, low, close, length=14)
        if adx is not None and 'ADX_14' in adx.columns:
            features[f'{prefix}%-wave_strength'] = adx['ADX_14'] / 100
        else:
            features[f'{prefix}%-wave_strength'] = pd.Series(0.5, index=df.index)
        
        atr = safe_atr(high, low, close, length=14)
        ema20 = safe_ema(close, length=20)
        extension = (close - ema20) / atr
        extension = extension.fillna(0)
        
        features[f'{prefix}%-wave_exhaustion_up'] = ((extension > 2) & bearish_div).astype(float)
        features[f'{prefix}%-wave_exhaustion_down'] = ((extension < -2) & bullish_div).astype(float)
    
    @staticmethod
    def _calc_swing_structure(df: pd.DataFrame, prefix: str, features: dict, lookback: int = 20) -> None:
        """Calculate swing structure features into dict"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        swing_high = high.rolling(lookback).max()
        swing_low = low.rolling(lookback).min()
        
        hh = swing_high > swing_high.shift(lookback)
        ll = swing_low < swing_low.shift(lookback)
        hl = swing_low > swing_low.shift(lookback)
        lh = swing_high < swing_high.shift(lookback)
        
        features[f'{prefix}%-wave_uptrend'] = (hh & hl).astype(float)
        features[f'{prefix}%-wave_downtrend'] = (ll & lh).astype(float)
        
        features[f'{prefix}%-wave_break_high'] = (close > swing_high.shift(1)).astype(float)
        features[f'{prefix}%-wave_break_low'] = (close < swing_low.shift(1)).astype(float)
        
        swing_range = swing_high - swing_low
        swing_range = swing_range.replace(0, np.nan)
        
        features[f'{prefix}%-wave_swing_position'] = (close - swing_low) / swing_range
        
        atr = safe_atr(high, low, close, length=14)
        features[f'{prefix}%-wave_swing_size'] = swing_range / atr
        
        momentum = close.pct_change(5)
        volatility = close.pct_change().rolling(5).std()
        volatility = volatility.replace(0, np.nan)
        
        features[f'{prefix}%-wave_impulse_ratio'] = abs(momentum) / volatility
    
    # Legacy methods for backward compatibility
    @staticmethod
    def add_fibonacci_retracement(df: pd.DataFrame, prefix: str = "", lookback: int = 50) -> pd.DataFrame:
        """Legacy wrapper - use add_all_features for better performance"""
        features = {}
        WaveIndicators._calc_fibonacci_retracement(df, prefix, features, lookback)
        return pd.concat([df, pd.DataFrame(features, index=df.index)], axis=1)
    
    @staticmethod
    def add_fibonacci_extensions(df: pd.DataFrame, prefix: str = "", lookback: int = 50) -> pd.DataFrame:
        """Legacy wrapper - use add_all_features for better performance"""
        features = {}
        WaveIndicators._calc_fibonacci_extensions(df, prefix, features, lookback)
        return pd.concat([df, pd.DataFrame(features, index=df.index)], axis=1)
    
    @staticmethod
    def add_awesome_oscillator(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """Legacy wrapper - use add_all_features for better performance"""
        features = {}
        WaveIndicators._calc_awesome_oscillator(df, prefix, features)
        return pd.concat([df, pd.DataFrame(features, index=df.index)], axis=1)
    
    @staticmethod
    def add_wave_momentum(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """Legacy wrapper - use add_all_features for better performance"""
        features = {}
        WaveIndicators._calc_wave_momentum(df, prefix, features)
        return pd.concat([df, pd.DataFrame(features, index=df.index)], axis=1)
    
    @staticmethod
    def add_swing_structure(df: pd.DataFrame, prefix: str = "", lookback: int = 20) -> pd.DataFrame:
        """Legacy wrapper - use add_all_features for better performance"""
        features = {}
        WaveIndicators._calc_swing_structure(df, prefix, features, lookback)
        return pd.concat([df, pd.DataFrame(features, index=df.index)], axis=1)
