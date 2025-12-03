"""
SMC Indicators - Smart Money Concepts
Upgraded version with stationary features for AI/ML

Features:
- Sonic R System (Distance-based)
- Institutional EMAs (Distance & Slope)
- Fair Value Gaps (FVG)
- SMC Swings & Structure
- Moon Phases

Performance optimized: Uses dict collection + single pd.concat to avoid fragmentation
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
import logging

logger = logging.getLogger(__name__)


class SMCIndicators:
    """
    Smart Money Concepts (SMC) Indicators
    All features are stationary (distance-based, normalized) for AI learning.
    Performance optimized with single concat.
    """

    @staticmethod
    def add_all_indicators(dataframe: DataFrame) -> DataFrame:
        """
        Main method to add all SMC indicators to the dataframe.
        All features use %-prefix for FreqAI compatibility.
        Uses optimized single concat for performance.
        """
        logger.info("Adding SMC Indicators...")
        
        # Collect all features in dict to avoid fragmentation
        features = {}
        
        SMCIndicators._calc_sonic_r(dataframe, features)
        SMCIndicators._calc_institutional_emas(dataframe, features)
        SMCIndicators._calc_fair_value_gaps(dataframe, features)
        SMCIndicators._calc_smc_structure(dataframe, features)
        SMCIndicators._calc_moon_phases(dataframe, features)
        
        # NEW: Order Block, Wyckoff, CHoCH, Liquidity (từ báo cáo nghiên cứu)
        SMCIndicators._calc_order_blocks(dataframe, features)
        SMCIndicators._calc_wyckoff_patterns(dataframe, features)
        SMCIndicators._calc_choch(dataframe, features)
        SMCIndicators._calc_liquidity_pools(dataframe, features)
        
        # Single concat - much faster than individual inserts
        if features:
            features_df = pd.DataFrame(features, index=dataframe.index)
            dataframe = pd.concat([dataframe, features_df], axis=1)
        
        logger.info("SMC Indicators added successfully")
        return dataframe

    @staticmethod
    def _calc_sonic_r(dataframe: DataFrame, features: dict, period: int = 34) -> None:
        """Calculate Sonic R features into dict"""
        sonic_h = ta.ema(dataframe['high'], length=period)
        sonic_l = ta.ema(dataframe['low'], length=period)
        sonic_c = ta.ema(dataframe['close'], length=period)
        
        _sonic_h = sonic_h.fillna(dataframe['high']) if sonic_h is not None else dataframe['high']
        _sonic_l = sonic_l.fillna(dataframe['low']) if sonic_l is not None else dataframe['low']
        _sonic_c = sonic_c.fillna(dataframe['close']) if sonic_c is not None else dataframe['close']
        
        features['%-dist_to_sonic_h'] = (dataframe['close'] - _sonic_h) / dataframe['close']
        features['%-dist_to_sonic_l'] = (dataframe['close'] - _sonic_l) / dataframe['close']
        features['%-dist_to_sonic_c'] = (dataframe['close'] - _sonic_c) / dataframe['close']
        
        tunnel_width = _sonic_h - _sonic_l
        features['%-sonic_tunnel_width'] = tunnel_width / dataframe['close']
        
        sonic_position = (dataframe['close'] - _sonic_l) / (tunnel_width + 1e-10)
        features['%-sonic_position'] = sonic_position.clip(-1, 2)

    @staticmethod
    def _calc_institutional_emas(dataframe: DataFrame, features: dict) -> None:
        """Calculate Institutional EMA features into dict"""
        for length in [369, 630]:
            ema_values = ta.ema(dataframe['close'], length=length)
            
            if ema_values is None or ema_values.isna().all():
                features[f'%-dist_to_ema_{length}'] = pd.Series(0, index=dataframe.index)
                features[f'%-slope_ema_{length}'] = pd.Series(0, index=dataframe.index)
                _ema = pd.Series(0, index=dataframe.index)
            else:
                _ema = ema_values.fillna(0)
                features[f'%-dist_to_ema_{length}'] = np.where(
                    _ema != 0,
                    (dataframe['close'] - _ema) / dataframe['close'],
                    0
                )
                ema_diff = _ema.diff(5)
                features[f'%-slope_ema_{length}'] = np.where(
                    _ema != 0,
                    (ema_diff / _ema) * 100,
                    0
                ).astype(float)
            
            if length == 369:
                _ema_369 = _ema
            else:
                _ema_630 = _ema
        
        features['%-ema_369_vs_630'] = np.where(
            dataframe['close'] != 0,
            (_ema_369 - _ema_630) / dataframe['close'],
            0
        )

    @staticmethod
    def _calc_fair_value_gaps(dataframe: DataFrame, features: dict) -> None:
        """Calculate Fair Value Gap features into dict"""
        fvg_bull = np.where(dataframe['low'] > dataframe['high'].shift(2), 1, 0).astype(float)
        fvg_bear = np.where(dataframe['high'] < dataframe['low'].shift(2), 1, 0).astype(float)
        
        features['%-fvg_bull'] = fvg_bull
        features['%-fvg_bear'] = fvg_bear
        
        bull_gap = np.where(
            fvg_bull == 1,
            (dataframe['low'] - dataframe['high'].shift(2)) / dataframe['close'],
            0
        )
        bear_gap = np.where(
            fvg_bear == 1,
            (dataframe['high'] - dataframe['low'].shift(2)) / dataframe['close'],
            0
        )
        features['%-fvg_size'] = bull_gap + bear_gap
        
        fvg_bull_series = pd.Series(fvg_bull, index=dataframe.index)
        fvg_bear_series = pd.Series(fvg_bear, index=dataframe.index)
        fvg_bull_count = fvg_bull_series.rolling(20).sum()
        fvg_bear_count = fvg_bear_series.rolling(20).sum()
        
        features['%-fvg_bull_count_20'] = fvg_bull_count
        features['%-fvg_bear_count_20'] = fvg_bear_count
        features['%-fvg_net_count'] = fvg_bull_count - fvg_bear_count

    @staticmethod
    def _calc_smc_structure(dataframe: DataFrame, features: dict, length: int = 50) -> None:
        """Calculate SMC Structure features into dict"""
        swing_high = dataframe['high'].rolling(window=length).max()
        swing_low = dataframe['low'].rolling(window=length).min()
        
        features['%-dist_to_swing_high'] = (dataframe['close'] - swing_high) / dataframe['close']
        features['%-dist_to_swing_low'] = (dataframe['close'] - swing_low) / dataframe['close']
        
        swing_range = swing_high - swing_low
        features['%-position_in_range'] = (dataframe['close'] - swing_low) / (swing_range + 1e-10)
        
        prev_swing_high = swing_high.shift(1)
        features['%-bos_bull'] = np.where(
            (dataframe['close'] > prev_swing_high) & 
            (dataframe['close'].shift(1) <= prev_swing_high),
            1, 0
        ).astype(float)
        
        prev_swing_low = swing_low.shift(1)
        features['%-bos_bear'] = np.where(
            (dataframe['close'] < prev_swing_low) &
            (dataframe['close'].shift(1) >= prev_swing_low),
            1, 0
        ).astype(float)
        
        hh = (swing_high > swing_high.shift(length//2)).astype(int)
        ll = (swing_low < swing_low.shift(length//2)).astype(int)
        hl = (swing_low > swing_low.shift(length//2)).astype(int)
        lh = (swing_high < swing_high.shift(length//2)).astype(int)
        
        structure_dir = ((hh + hl) - (ll + lh)).clip(-2, 2) / 2
        features['%-structure_direction'] = structure_dir

    @staticmethod
    def _calc_moon_phases(dataframe: DataFrame, features: dict) -> None:
        """Calculate Moon Phase features into dict"""
        SYNODIC_MONTH = 29.530588853
        REFERENCE_JD = 2451550.1
        JULIAN_EPOCH = 2440587.5
        MILLIS_PER_DAY = 86400000.0

        timestamps = dataframe['date'].astype('int64') // 10**6
        julian_days = JULIAN_EPOCH + (timestamps / MILLIS_PER_DAY)
        moon_ages = (julian_days - REFERENCE_JD) % SYNODIC_MONTH
        moon_ages = np.where(moon_ages < 0, moon_ages + SYNODIC_MONTH, moon_ages)
        
        features['%-moon_phase'] = moon_ages / SYNODIC_MONTH
        
        phase_angle = 2 * np.pi * moon_ages / SYNODIC_MONTH
        features['%-moon_illumination'] = (1 + np.cos(phase_angle)) / 2
        
        features['%-moon_is_new'] = np.where(
            (moon_ages <= 1.5) | (moon_ages >= SYNODIC_MONTH - 1.5),
            1, 0
        ).astype(float)
        
        features['%-moon_is_full'] = np.where(
            (moon_ages >= SYNODIC_MONTH/2 - 1.5) & (moon_ages <= SYNODIC_MONTH/2 + 1.5),
            1, 0
        ).astype(float)

    # ============================================================
    # ORDER BLOCK DETECTION (từ báo cáo nghiên cứu)
    # ============================================================
    
    @staticmethod
    def _calc_order_blocks(dataframe: DataFrame, features: dict, 
                           lookback: int = 50, displacement_pct: float = 0.02) -> None:
        """
        Order Block Detection - Phát hiện vùng lệnh tổ chức.
        
        Bullish OB: Nến giảm CUỐI CÙNG trước khi giá tăng mạnh (displacement)
        Bearish OB: Nến tăng CUỐI CÙNG trước khi giá giảm mạnh
        
        Logic:
        1. Tìm nến có displacement mạnh (> 2%)
        2. Đánh dấu nến ngược chiều trước đó là Order Block
        3. Tính khoảng cách từ giá hiện tại đến OB
        """
        # Displacement: Giá di chuyển mạnh (> displacement_pct trong 3 nến)
        price_change_3 = (dataframe['close'] - dataframe['close'].shift(3)) / (dataframe['close'].shift(3) + 1e-10)
        
        # Bullish displacement (tăng > 2%)
        bullish_displacement = price_change_3 > displacement_pct
        
        # Bearish displacement (giảm > 2%)
        bearish_displacement = price_change_3 < -displacement_pct
        
        # Identify Order Blocks
        # Bullish OB: Nến giảm (close < open) trước displacement tăng
        is_bearish_candle = dataframe['close'] < dataframe['open']
        bullish_ob = is_bearish_candle.shift(3) & bullish_displacement
        
        # Bearish OB: Nến tăng (close > open) trước displacement giảm
        is_bullish_candle = dataframe['close'] > dataframe['open']
        bearish_ob = is_bullish_candle.shift(3) & bearish_displacement
        
        features['%-order_block_bull'] = bullish_ob.astype(float).fillna(0)
        features['%-order_block_bear'] = bearish_ob.astype(float).fillna(0)
        
        # Track OB zones và tính distance
        ob_bull_high = np.where(bullish_ob, dataframe['high'].shift(3), np.nan)
        ob_bull_low = np.where(bullish_ob, dataframe['low'].shift(3), np.nan)
        
        ob_bear_high = np.where(bearish_ob, dataframe['high'].shift(3), np.nan)
        ob_bear_low = np.where(bearish_ob, dataframe['low'].shift(3), np.nan)
        
        # Forward fill để giữ OB zone gần nhất
        ob_bull_high = pd.Series(ob_bull_high, index=dataframe.index).ffill()
        ob_bull_low = pd.Series(ob_bull_low, index=dataframe.index).ffill()
        ob_bear_high = pd.Series(ob_bear_high, index=dataframe.index).ffill()
        ob_bear_low = pd.Series(ob_bear_low, index=dataframe.index).ffill()
        
        # Distance to nearest Bullish OB (normalized)
        features['%-dist_to_bull_ob'] = (dataframe['close'] - ob_bull_high) / (dataframe['close'] + 1e-10)
        
        # Distance to nearest Bearish OB (normalized)
        features['%-dist_to_bear_ob'] = (dataframe['close'] - ob_bear_low) / (dataframe['close'] + 1e-10)
        
        # Is price testing OB zone?
        features['%-testing_bull_ob'] = np.where(
            (dataframe['low'] <= ob_bull_high) & (dataframe['close'] >= ob_bull_low),
            1.0, 0.0
        )
        
        features['%-testing_bear_ob'] = np.where(
            (dataframe['high'] >= ob_bear_low) & (dataframe['close'] <= ob_bear_high),
            1.0, 0.0
        )

    # ============================================================
    # WYCKOFF PATTERNS (từ báo cáo nghiên cứu)
    # ============================================================
    
    @staticmethod
    def _calc_wyckoff_patterns(dataframe: DataFrame, features: dict, 
                               range_lookback: int = 50) -> None:
        """
        Wyckoff Pattern Detection - Spring & Upthrust.
        
        Spring (Bear Trap):
        - Giá phá đáy trading range
        - Nhưng đóng cửa lại TRÊN đáy
        - Volume thấp hoặc rất cao (hấp thụ)
        
        Upthrust (Bull Trap):
        - Giá phá đỉnh trading range
        - Nhưng đóng cửa lại DƯỚI đỉnh
        - Volume thấp hoặc rất cao
        """
        # Xác định Trading Range
        rolling_high = dataframe['high'].rolling(range_lookback).max().shift(1)
        rolling_low = dataframe['low'].rolling(range_lookback).min().shift(1)
        
        avg_vol = dataframe['volume'].rolling(20).mean()
        
        # === SPRING (Bear Trap) ===
        # Điều kiện 1: Low hiện tại phá đáy cũ
        breaks_low = dataframe['low'] < rolling_low
        
        # Điều kiện 2: Close rút chân lên trên đáy cũ
        closes_above_low = dataframe['close'] > rolling_low
        
        # Điều kiện 3: Volume confirmation
        low_volume = dataframe['volume'] < 0.7 * avg_vol
        ultra_high_volume = dataframe['volume'] > 2.5 * avg_vol
        volume_confirm = low_volume | ultra_high_volume
        
        features['%-wyckoff_spring'] = np.where(
            breaks_low & closes_above_low,
            1.0, 0.0
        )
        
        # Spring có volume confirmation (chất lượng cao hơn)
        features['%-wyckoff_spring_confirmed'] = np.where(
            breaks_low & closes_above_low & volume_confirm,
            1.0, 0.0
        )
        
        # === UPTHRUST (Bull Trap) ===
        # Điều kiện 1: High hiện tại phá đỉnh cũ
        breaks_high = dataframe['high'] > rolling_high
        
        # Điều kiện 2: Close rút đầu xuống dưới đỉnh cũ
        closes_below_high = dataframe['close'] < rolling_high
        
        features['%-wyckoff_upthrust'] = np.where(
            breaks_high & closes_below_high,
            1.0, 0.0
        )
        
        # Upthrust có volume confirmation
        features['%-wyckoff_upthrust_confirmed'] = np.where(
            breaks_high & closes_below_high & volume_confirm,
            1.0, 0.0
        )
        
        # === RANGE POSITION ===
        range_size = rolling_high - rolling_low
        features['%-wyckoff_range_position'] = (dataframe['close'] - rolling_low) / (range_size + 1e-10)
        
        # === DISCOUNT / PREMIUM ZONES ===
        position = features['%-wyckoff_range_position']
        features['%-is_discount_zone'] = np.where(position < 0.3, 1.0, 0.0)
        features['%-is_premium_zone'] = np.where(position > 0.7, 1.0, 0.0)
        features['%-is_equilibrium'] = np.where((position >= 0.45) & (position <= 0.55), 1.0, 0.0)

    # ============================================================
    # CHoCH (Change of Character) - Phân biệt với BOS
    # ============================================================
    
    @staticmethod
    def _calc_choch(dataframe: DataFrame, features: dict, length: int = 20) -> None:
        """
        CHoCH (Change of Character) Detection.
        
        CHoCH khác với BOS (Break of Structure):
        - BOS: Phá vỡ cấu trúc THEO xu hướng (continuation)
        - CHoCH: Phá vỡ cấu trúc NGƯỢC xu hướng (reversal signal)
        
        Logic:
        1. Xác định xu hướng hiện tại (HH+HL = Uptrend, LL+LH = Downtrend)
        2. CHoCH Bull: Trong downtrend, phá vỡ LH gần nhất
        3. CHoCH Bear: Trong uptrend, phá vỡ HL gần nhất
        """
        # Tìm swing points
        swing_high = dataframe['high'].rolling(length).max()
        swing_low = dataframe['low'].rolling(length).min()
        
        # Previous swing points (shifted)
        prev_swing_high = swing_high.shift(length // 2)
        prev_swing_low = swing_low.shift(length // 2)
        
        # Trend detection
        higher_high = swing_high > prev_swing_high
        higher_low = swing_low > prev_swing_low
        uptrend = higher_high & higher_low
        
        lower_low = swing_low < prev_swing_low
        lower_high = swing_high < prev_swing_high
        downtrend = lower_low & lower_high
        
        # CHoCH Bull: Trong downtrend, giá phá vỡ đỉnh trước đó (LH)
        choch_bull = downtrend.shift(1) & (dataframe['close'] > prev_swing_high)
        features['%-choch_bull'] = choch_bull.astype(float).fillna(0)
        
        # CHoCH Bear: Trong uptrend, giá phá vỡ đáy trước đó (HL)
        choch_bear = uptrend.shift(1) & (dataframe['close'] < prev_swing_low)
        features['%-choch_bear'] = choch_bear.astype(float).fillna(0)
        
        # Trend state for reference
        features['%-trend_state'] = np.where(uptrend, 1, np.where(downtrend, -1, 0)).astype(float)

    # ============================================================
    # LIQUIDITY POOLS
    # ============================================================
    
    @staticmethod
    def _calc_liquidity_pools(dataframe: DataFrame, features: dict, 
                              lookback: int = 50, tolerance: float = 0.002) -> None:
        """
        Liquidity Pool Detection - Vùng thanh khoản.
        
        Equal Highs: Nhiều đỉnh bằng nhau = Vùng có nhiều Stop Loss
        Equal Lows: Nhiều đáy bằng nhau = Vùng có nhiều Stop Loss
        
        Smart Money thường "săn" các vùng này trước khi đảo chiều.
        """
        swing_high = dataframe['high'].rolling(lookback).max()
        swing_low = dataframe['low'].rolling(lookback).min()
        
        # Check if current high is near swing high (within tolerance)
        near_swing_high = (dataframe['high'] - swing_high).abs() / (swing_high + 1e-10) < tolerance
        
        # Check if current low is near swing low
        near_swing_low = (dataframe['low'] - swing_low).abs() / (swing_low + 1e-10) < tolerance
        
        # Count how many times price touched these levels recently
        features['%-liquidity_above_count'] = near_swing_high.rolling(lookback).sum() / lookback
        features['%-liquidity_below_count'] = near_swing_low.rolling(lookback).sum() / lookback
        
        # Distance to liquidity pools
        features['%-dist_to_liquidity_above'] = (swing_high - dataframe['close']) / (dataframe['close'] + 1e-10)
        features['%-dist_to_liquidity_below'] = (dataframe['close'] - swing_low) / (dataframe['close'] + 1e-10)
        
        # Liquidity Sweep Detection
        swept_above = (dataframe['high'] > swing_high.shift(1)) & (dataframe['close'] < swing_high.shift(1))
        features['%-liquidity_swept_above'] = swept_above.astype(float).fillna(0)
        
        swept_below = (dataframe['low'] < swing_low.shift(1)) & (dataframe['close'] > swing_low.shift(1))
        features['%-liquidity_swept_below'] = swept_below.astype(float).fillna(0)

    # Legacy methods for backward compatibility
    @staticmethod
    def add_sonic_r(dataframe: DataFrame, period: int = 34) -> DataFrame:
        """Legacy wrapper - use add_all_indicators for better performance"""
        features = {}
        SMCIndicators._calc_sonic_r(dataframe, features, period)
        return pd.concat([dataframe, pd.DataFrame(features, index=dataframe.index)], axis=1)
    
    @staticmethod
    def add_institutional_emas(dataframe: DataFrame) -> DataFrame:
        """Legacy wrapper - use add_all_indicators for better performance"""
        features = {}
        SMCIndicators._calc_institutional_emas(dataframe, features)
        return pd.concat([dataframe, pd.DataFrame(features, index=dataframe.index)], axis=1)
    
    @staticmethod
    def add_fair_value_gaps(dataframe: DataFrame) -> DataFrame:
        """Legacy wrapper - use add_all_indicators for better performance"""
        features = {}
        SMCIndicators._calc_fair_value_gaps(dataframe, features)
        return pd.concat([dataframe, pd.DataFrame(features, index=dataframe.index)], axis=1)
    
    @staticmethod
    def add_smc_structure(dataframe: DataFrame, length: int = 50) -> DataFrame:
        """Legacy wrapper - use add_all_indicators for better performance"""
        features = {}
        SMCIndicators._calc_smc_structure(dataframe, features, length)
        return pd.concat([dataframe, pd.DataFrame(features, index=dataframe.index)], axis=1)
    
    @staticmethod
    def add_moon_phases(dataframe: DataFrame) -> DataFrame:
        """Legacy wrapper - use add_all_indicators for better performance"""
        features = {}
        SMCIndicators._calc_moon_phases(dataframe, features)
        return pd.concat([dataframe, pd.DataFrame(features, index=dataframe.index)], axis=1)
