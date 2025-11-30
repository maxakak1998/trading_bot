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


class WaveIndicators:
    """
    Elliott Wave Lite - Objective features for AI
    
    Philosophy:
    - NO wave counting (too subjective, repaints)
    - YES Fibonacci levels (objective math)
    - YES momentum oscillators (wave identification)
    - YES swing detection (structure analysis)
    """
    
    # Fibonacci ratios used in Elliott Wave
    FIB_RETRACEMENT = [0.236, 0.382, 0.5, 0.618, 0.786]
    FIB_EXTENSION = [1.0, 1.272, 1.618, 2.0, 2.618]
    
    @staticmethod
    def add_all_features(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """Add all wave-related features to dataframe"""
        df = WaveIndicators.add_fibonacci_retracement(df, prefix)
        df = WaveIndicators.add_fibonacci_extensions(df, prefix)
        df = WaveIndicators.add_awesome_oscillator(df, prefix)
        df = WaveIndicators.add_wave_momentum(df, prefix)
        df = WaveIndicators.add_swing_structure(df, prefix)
        
        # Handle NaN
        wave_cols = [c for c in df.columns if c.startswith(f"{prefix}%-wave_") or c.startswith(f"{prefix}%-fib_")]
        for col in wave_cols:
            df[col] = df[col].ffill().fillna(0)
        
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
    def add_fibonacci_retracement(df: pd.DataFrame, prefix: str = "", lookback: int = 50) -> pd.DataFrame:
        """
        Calculate price position relative to Fibonacci retracement levels
        
        Features:
        - Distance from each Fib level (normalized)
        - Nearest Fib level
        - Fib zone (which zone price is in)
        """
        high = df['high'].rolling(lookback).max()
        low = df['low'].rolling(lookback).min()
        close = df['close']
        
        # Price range
        price_range = high - low
        price_range = price_range.replace(0, np.nan)  # Avoid division by zero
        
        # Current position in range (0 = low, 1 = high)
        df[f'{prefix}%-fib_position'] = (close - low) / price_range
        
        # Distance from each Fibonacci level
        for fib in WaveIndicators.FIB_RETRACEMENT:
            fib_price = low + (price_range * fib)
            # Normalized distance (as percentage of range)
            df[f'{prefix}%-fib_dist_{int(fib*1000)}'] = (close - fib_price) / price_range
        
        # Which Fib zone are we in? (0-4)
        position = df[f'{prefix}%-fib_position']
        df[f'{prefix}%-fib_zone'] = pd.cut(
            position, 
            bins=[-np.inf, 0.236, 0.382, 0.5, 0.618, 0.786, np.inf],
            labels=[0, 1, 2, 3, 4, 5]
        ).astype(float)
        
        # Is price near a Fib level? (within 2%)
        for fib in WaveIndicators.FIB_RETRACEMENT:
            dist_col = f'{prefix}%-fib_dist_{int(fib*1000)}'
            df[f'{prefix}%-fib_near_{int(fib*1000)}'] = (abs(df[dist_col]) < 0.02).astype(float)
        
        return df
    
    @staticmethod
    def add_fibonacci_extensions(df: pd.DataFrame, prefix: str = "", lookback: int = 50) -> pd.DataFrame:
        """
        Calculate Fibonacci extension levels for price targets
        
        Used for identifying potential Wave 3/5 targets
        """
        high = df['high'].rolling(lookback).max()
        low = df['low'].rolling(lookback).min()
        close = df['close']
        
        price_range = high - low
        price_range = price_range.replace(0, np.nan)
        
        # Extension above high
        for ext in WaveIndicators.FIB_EXTENSION:
            ext_price = high + (price_range * (ext - 1))  # Extension above high
            df[f'{prefix}%-fib_ext_up_{int(ext*1000)}'] = (close - ext_price) / price_range
        
        # Extension below low  
        for ext in WaveIndicators.FIB_EXTENSION:
            ext_price = low - (price_range * (ext - 1))  # Extension below low
            df[f'{prefix}%-fib_ext_down_{int(ext*1000)}'] = (close - ext_price) / price_range
        
        return df
    
    @staticmethod
    def add_awesome_oscillator(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """
        Awesome Oscillator (AO) - Bill Williams indicator
        
        Key for Elliott Wave:
        - AO highest peak often marks Wave 3 top
        - Divergence between AO and price indicates Wave 5
        - Zero line crossover indicates trend change
        
        Features:
        - AO value (normalized)
        - AO histogram (change)
        - AO divergence signal
        - AO zero cross
        """
        # Calculate AO: SMA(5) of median price - SMA(34) of median price
        median_price = (df['high'] + df['low']) / 2
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        
        # Normalize AO by ATR for comparability
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        atr = atr.replace(0, np.nan)
        
        df[f'{prefix}%-wave_ao'] = ao / atr
        
        # AO histogram (momentum of momentum)
        df[f'{prefix}%-wave_ao_hist'] = ao.diff() / atr
        
        # AO acceleration (rate of change of histogram)
        df[f'{prefix}%-wave_ao_accel'] = df[f'{prefix}%-wave_ao_hist'].diff()
        
        # Zero line position
        df[f'{prefix}%-wave_ao_above_zero'] = (ao > 0).astype(float)
        
        # Zero line crossover (1 = bullish cross, -1 = bearish cross, 0 = no cross)
        ao_cross = np.where(
            (ao > 0) & (ao.shift(1) <= 0), 1,
            np.where((ao < 0) & (ao.shift(1) >= 0), -1, 0)
        )
        df[f'{prefix}%-wave_ao_cross'] = ao_cross
        
        # Twin peaks setup (potential Wave 4-5 or A-B-C)
        # Two peaks on same side of zero with second peak smaller
        ao_peak = (ao.shift(1) > ao) & (ao.shift(1) > ao.shift(2))
        df[f'{prefix}%-wave_ao_peak'] = ao_peak.astype(float)
        
        return df
    
    @staticmethod
    def add_wave_momentum(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """
        Wave momentum indicators for structure identification
        
        Features:
        - Momentum divergence (price vs AO)
        - Wave strength (trend strength indicator)
        - Exhaustion signals
        """
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Calculate AO for divergence
        median_price = (high + low) / 2
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        
        # Price momentum (rate of change)
        price_roc = close.pct_change(10)
        ao_roc = ao.pct_change(10)
        
        # Divergence detection
        # Bullish: Price makes lower low, AO makes higher low
        # Bearish: Price makes higher high, AO makes lower high
        
        price_higher = close > close.rolling(10).max().shift(1)
        price_lower = close < close.rolling(10).min().shift(1)
        ao_higher = ao > ao.rolling(10).max().shift(1)
        ao_lower = ao < ao.rolling(10).min().shift(1)
        
        # Bearish divergence (Wave 5 top signal)
        df[f'{prefix}%-wave_bearish_div'] = (price_higher & ao_lower).astype(float)
        
        # Bullish divergence (Wave 5 bottom signal)
        df[f'{prefix}%-wave_bullish_div'] = (price_lower & ao_higher).astype(float)
        
        # Wave strength (ADX-based)
        adx = ta.adx(high, low, close, length=14)
        if adx is not None and 'ADX_14' in adx.columns:
            df[f'{prefix}%-wave_strength'] = adx['ADX_14'] / 100
        else:
            df[f'{prefix}%-wave_strength'] = 0.5
        
        # Exhaustion signal (very high momentum + divergence)
        atr = ta.atr(high, low, close, length=14)
        atr = atr.replace(0, np.nan)
        
        # Price extension from mean
        ema20 = ta.ema(close, length=20)
        extension = (close - ema20) / atr
        
        # Exhaustion when price extended + AO diverging
        df[f'{prefix}%-wave_exhaustion_up'] = ((extension > 2) & df[f'{prefix}%-wave_bearish_div']).astype(float)
        df[f'{prefix}%-wave_exhaustion_down'] = ((extension < -2) & df[f'{prefix}%-wave_bullish_div']).astype(float)
        
        return df
    
    @staticmethod
    def add_swing_structure(df: pd.DataFrame, prefix: str = "", lookback: int = 20) -> pd.DataFrame:
        """
        Swing structure analysis for wave counting proxies
        
        Instead of counting waves, we identify:
        - Higher highs / Lower lows pattern
        - Swing point sequence
        - Structure breaks
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Recent swing points
        swing_high = high.rolling(lookback).max()
        swing_low = low.rolling(lookback).min()
        
        # Higher high / Lower low sequence
        hh = swing_high > swing_high.shift(lookback)  # Higher high
        ll = swing_low < swing_low.shift(lookback)    # Lower low
        hl = swing_low > swing_low.shift(lookback)    # Higher low
        lh = swing_high < swing_high.shift(lookback)  # Lower high
        
        # Trend structure
        # Uptrend: HH + HL
        # Downtrend: LL + LH
        df[f'{prefix}%-wave_uptrend'] = (hh & hl).astype(float)
        df[f'{prefix}%-wave_downtrend'] = (ll & lh).astype(float)
        
        # Structure break (potential wave completion)
        # Break of swing high in downtrend or swing low in uptrend
        df[f'{prefix}%-wave_break_high'] = (close > swing_high.shift(1)).astype(float)
        df[f'{prefix}%-wave_break_low'] = (close < swing_low.shift(1)).astype(float)
        
        # Swing count (proxy for wave position)
        # Count alternating swings in recent history
        swing_range = swing_high - swing_low
        swing_range = swing_range.replace(0, np.nan)
        
        # Position within current swing (0 = at low, 1 = at high)
        df[f'{prefix}%-wave_swing_position'] = (close - swing_low) / swing_range
        
        # Swing size relative to ATR (wave magnitude)
        atr = ta.atr(high, low, close, length=14)
        atr = atr.replace(0, np.nan)
        df[f'{prefix}%-wave_swing_size'] = swing_range / atr
        
        # Impulse vs Corrective proxy
        # Impulse: Strong move with momentum
        # Corrective: Weak move, overlapping
        momentum = close.pct_change(5)
        volatility = close.pct_change().rolling(5).std()
        volatility = volatility.replace(0, np.nan)
        
        # Impulse ratio (high = trending, low = corrective)
        df[f'{prefix}%-wave_impulse_ratio'] = abs(momentum) / volatility
        
        return df
    
    @staticmethod
    def add_harmonic_patterns(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """
        Harmonic pattern ratios (Gartley, Butterfly, etc.)
        
        These patterns are based on Fibonacci and often align with Elliott Waves
        """
        # For now, we use Fibonacci-based price structure
        # Full harmonic detection is complex and may repaint
        
        high = df['high'].rolling(50).max()
        low = df['low'].rolling(50).min()
        close = df['close']
        
        price_range = high - low
        price_range = price_range.replace(0, np.nan)
        
        # Check if price is at harmonic levels
        position = (close - low) / price_range
        
        # Harmonic levels (Gartley pattern key levels)
        harmonic_levels = {
            'xab_382': 0.382,  # XA retracement B point
            'xab_618': 0.618,  # XA retracement B point
            'abc_382': 0.382,  # AB retracement C point  
            'abc_886': 0.886,  # AB retracement C point
        }
        
        for name, level in harmonic_levels.items():
            # Distance from harmonic level
            df[f'{prefix}%-wave_harmonic_{name}'] = abs(position - level)
            # Near level indicator
            df[f'{prefix}%-wave_near_{name}'] = (abs(position - level) < 0.03).astype(float)
        
        return df
