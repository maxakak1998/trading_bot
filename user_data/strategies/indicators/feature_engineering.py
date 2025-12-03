"""
Feature Engineering Module - Đúng Chuẩn AI/ML
=============================================
Module này chứa các features được thiết kế đúng cách cho Machine Learning:

NGUYÊN TẮC:
1. Không dùng giá trị tuyệt đối → Dùng biến thiên (Delta/Slope/Distance)
2. Tránh indicators bị lag → Ưu tiên Oscillators, Volume
3. Log Returns là VUA → Chuẩn hóa giá về dao động quanh 0
4. Stationary features → RSI, %, độ biến động (không phải giá thô)

Author: AI Trading System
Date: 2025-11-30
"""

import numpy as np
import pandas as pd
import pandas_ta as pta
import talib.abstract as ta
from pandas import DataFrame
from typing import Optional
import logging

# Import VSA Indicators module (từ báo cáo nghiên cứu SMC/Wyckoff/VSA)
try:
    from indicators.vsa_indicators import VSAIndicators
    VSA_AVAILABLE = True
except ImportError:
    try:
        # Fallback: relative import
        from .vsa_indicators import VSAIndicators
        VSA_AVAILABLE = True
    except ImportError:
        VSA_AVAILABLE = False
        import logging
        logging.getLogger(__name__).warning("VSA Indicators not available - skipping")

logger = logging.getLogger(__name__)


class FeatureEngineering:
    """
    Class chứa các methods tạo features chuẩn cho AI/ML.
    
    Tất cả features đều được chuẩn hóa hoặc là tỷ lệ phần trăm,
    không có giá trị tuyệt đối (như giá $60,000).
    """
    
    # ============================================================
    # 1. CORE FEATURES - Log Returns & Price Changes
    # ============================================================
    
    @staticmethod
    def add_log_returns(dataframe: DataFrame, periods: list = [1, 5, 10, 20]) -> DataFrame:
        """
        Log Returns - Feature QUAN TRỌNG NHẤT cho AI.
        
        Công thức: ln(Price_t / Price_{t-n})
        
        Ưu điểm:
        - Biến đổi giá dốc đứng thành dao động quanh 0
        - Stationary (ổn định) - Tốt cho ML
        - Có thể cộng dồn (additive)
        
        Args:
            dataframe: OHLCV DataFrame
            periods: Các khoảng thời gian để tính log returns
            
        Returns:
            DataFrame với log returns features
        """
        for period in periods:
            dataframe[f'%-log_return_{period}'] = np.log(
                dataframe['close'] / dataframe['close'].shift(period)
            )
        
        # Log return của volume (biến động volume)
        dataframe['%-log_volume_change'] = np.log(
            (dataframe['volume'] + 1) / (dataframe['volume'].shift(1) + 1)
        )
        
        return dataframe
    
    @staticmethod
    def add_price_momentum(dataframe: DataFrame) -> DataFrame:
        """
        Price Momentum features.
        
        Đo lường tốc độ thay đổi giá theo nhiều cách.
        """
        # ROC (Rate of Change) - Phần trăm thay đổi
        dataframe['%-roc_5'] = pd.Series(ta.ROCP(dataframe['close'], timeperiod=5), index=dataframe.index)
        dataframe['%-roc_10'] = pd.Series(ta.ROCP(dataframe['close'], timeperiod=10), index=dataframe.index)
        dataframe['%-roc_20'] = pd.Series(ta.ROCP(dataframe['close'], timeperiod=20), index=dataframe.index)
        
        # Price momentum (close - close.shift) / close.shift
        dataframe['%-momentum_5'] = (dataframe['close'] - dataframe['close'].shift(5)) / (dataframe['close'].shift(5) + 1e-10)
        
        return dataframe
    
    # ============================================================
    # 2. TREND FEATURES - Distance & Slopes (Không phải giá trị thô)
    # ============================================================
    
    @staticmethod
    def add_ema_features(dataframe: DataFrame, periods: list = [10, 20, 50, 200]) -> DataFrame:
        """
        EMA Features - Khoảng cách và Độ dốc (KHÔNG PHẢI giá trị EMA thô).
        
        Thay vì: EMA_20 = 60000 (vô nghĩa cho AI)
        Dùng: dist_to_ema_20 = -0.02 (giá thấp hơn EMA 2%)
        
        Features:
        - Distance to EMA: (close - ema) / ema
        - EMA Slope: ema.diff() / ema (độ dốc)
        
        Args:
            dataframe: OHLCV DataFrame
            periods: Các periods cho EMA
            
        Returns:
            DataFrame với EMA distance và slope features
        """
        for period in periods:
            # Tính EMA - convert to pandas Series
            ema = pd.Series(ta.EMA(dataframe['close'], timeperiod=period), index=dataframe.index)
            
            # Distance to EMA (chuẩn hóa)
            # Dương: Giá trên EMA, Âm: Giá dưới EMA
            dataframe[f'%-dist_to_ema_{period}'] = (dataframe['close'] - ema) / (ema + 1e-10)
            
            # EMA Slope (độ dốc - thể hiện xu hướng)
            # Dương: EMA đang tăng, Âm: EMA đang giảm
            dataframe[f'%-ema_slope_{period}'] = ema.diff() / (ema + 1e-10)
        
        # EMA Cross (tín hiệu giao cắt) - Chuẩn hóa
        if 20 in periods and 50 in periods:
            ema_20 = pd.Series(ta.EMA(dataframe['close'], timeperiod=20), index=dataframe.index)
            ema_50 = pd.Series(ta.EMA(dataframe['close'], timeperiod=50), index=dataframe.index)
            dataframe['%-ema_20_50_diff'] = (ema_20 - ema_50) / (ema_50 + 1e-10)
        
        return dataframe
    
    @staticmethod
    def add_trend_strength(dataframe: DataFrame) -> DataFrame:
        """
        Trend Strength indicators.
        
        ADX đã chuẩn hóa (0-100) nên có thể dùng trực tiếp.
        Thêm thông tin về hướng xu hướng.
        """
        # ADX - Sức mạnh xu hướng (đã chuẩn hóa 0-100)
        adx = pd.Series(ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
        dataframe['%-adx'] = adx / 100  # Chuẩn hóa về 0-1
        
        # +DI và -DI để biết hướng
        plus_di = pd.Series(ta.PLUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
        minus_di = pd.Series(ta.MINUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
        
        # DI Difference (chuẩn hóa) - Hướng xu hướng
        # Dương: Xu hướng tăng, Âm: Xu hướng giảm
        dataframe['%-di_diff'] = (plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        
        return dataframe
    
    # ============================================================
    # 3. MOMENTUM FEATURES - Oscillators (Đã chuẩn hóa)
    # ============================================================
    
    @staticmethod
    def add_momentum_oscillators(dataframe: DataFrame) -> DataFrame:
        """
        Momentum Oscillators - Phản ứng nhanh, đã chuẩn hóa.
        
        RSI, Williams %R, TSI đều dao động trong khoảng cố định.
        Chuyển về khoảng [-1, 1] hoặc [0, 1] để AI dễ học.
        """
        # RSI (0-100) → Chuẩn hóa về [-1, 1]
        rsi = pd.Series(ta.RSI(dataframe['close'], timeperiod=14), index=dataframe.index)
        dataframe['%-rsi_normalized'] = (rsi - 50) / 50  # -1 (oversold) to +1 (overbought)
        
        # RSI Slope (momentum của RSI) - rsi already is pd.Series
        dataframe['%-rsi_slope'] = rsi.diff(3) / 100
        
        # Williams %R (-100 to 0) → Chuẩn hóa về [-1, 1]
        willr = pd.Series(ta.WILLR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
        dataframe['%-willr_normalized'] = (willr + 50) / 50  # -1 (oversold) to +1 (overbought)
        
        # Stochastic RSI (0-100) → Chuẩn hóa
        stochrsi = pta.stochrsi(dataframe['close'], length=14)
        if stochrsi is not None and 'STOCHRSIk_14_14_3_3' in stochrsi.columns:
            dataframe['%-stochrsi'] = (stochrsi['STOCHRSIk_14_14_3_3'] - 50) / 50
        else:
            dataframe['%-stochrsi'] = 0
        
        # CCI (Commodity Channel Index) - Đã dao động quanh 0
        cci = pd.Series(ta.CCI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=20), index=dataframe.index)
        dataframe['%-cci_normalized'] = cci / 200  # Thường dao động -200 to +200
        
        return dataframe
    
    # ============================================================
    # 4. VOLATILITY FEATURES - ATR, BB Width (Chuẩn hóa theo giá)
    # ============================================================
    
    @staticmethod
    def add_volatility_features(dataframe: DataFrame) -> DataFrame:
        """
        Volatility Features - Chuẩn hóa theo giá.
        
        ATR thô (vd: 2000) không có nghĩa cho AI.
        ATR / Price (vd: 5%) thì AI hiểu được.
        """
        # ATR normalized by price (%)
        atr = pd.Series(ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
        dataframe['%-atr_pct'] = atr / dataframe['close']
        
        # ATR change (volatility đang tăng hay giảm?)
        dataframe['%-atr_change'] = atr.pct_change(5)
        
        # Bollinger Band Width (đã chuẩn hóa)
        bb = pta.bbands(dataframe['close'], length=20, std=2)
        if bb is not None and len(bb.columns) >= 3:
            # Dynamic column name detection (pandas_ta may use different naming)
            bb_cols = bb.columns.tolist()
            upper_col = [c for c in bb_cols if 'BBU' in c][0] if any('BBU' in c for c in bb_cols) else None
            lower_col = [c for c in bb_cols if 'BBL' in c][0] if any('BBL' in c for c in bb_cols) else None
            middle_col = [c for c in bb_cols if 'BBM' in c][0] if any('BBM' in c for c in bb_cols) else None
            
            if upper_col and lower_col and middle_col:
                upper = bb[upper_col]
                lower = bb[lower_col]
                middle = bb[middle_col]
                
                # BB Width (% of price)
                dataframe['%-bb_width'] = (upper - lower) / middle
                
                # BB Position (vị trí giá trong BB)
                # 0 = lower band, 1 = upper band, 0.5 = middle
                dataframe['%-bb_position'] = (dataframe['close'] - lower) / (upper - lower + 1e-10)
                
                # Distance to bands
                dataframe['%-dist_to_bb_upper'] = (upper - dataframe['close']) / dataframe['close']
                dataframe['%-dist_to_bb_lower'] = (dataframe['close'] - lower) / dataframe['close']
        
        # True Range normalized
        tr = pd.Series(ta.TRANGE(dataframe['high'], dataframe['low'], dataframe['close']), index=dataframe.index)
        dataframe['%-true_range_pct'] = tr / dataframe['close']
        
        return dataframe
    
    # ============================================================
    # 5. VOLUME FEATURES - OBV, CMF, Volume Ratio
    # ============================================================
    
    @staticmethod
    def add_volume_features(dataframe: DataFrame) -> DataFrame:
        """
        Volume Features - Dòng tiền thường đi trước giá.
        
        OBV, CMF, MFI phản ánh áp lực mua/bán.
        """
        # MFI (Money Flow Index) - Đã chuẩn hóa 0-100
        mfi = pd.Series(ta.MFI(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], timeperiod=14), index=dataframe.index)
        dataframe['%-mfi_normalized'] = (mfi - 50) / 50  # -1 to +1
        
        # OBV (On Balance Volume) - Cần chuẩn hóa
        obv = pd.Series(ta.OBV(dataframe['close'], dataframe['volume']), index=dataframe.index)
        # OBV Change (normalized by rolling max)
        obv_change = obv.diff(5)
        obv_std = obv.rolling(20).std()
        dataframe['%-obv_change'] = obv_change / (obv_std + 1e-10)
        
        # OBV Slope (xu hướng của OBV)
        obv_ema = obv.ewm(span=10).mean()
        dataframe['%-obv_slope'] = obv_ema.diff(3) / (obv_ema.abs() + 1e-10)
        
        # Volume Ratio (current volume vs average)
        vol_sma = dataframe['volume'].rolling(20).mean()
        dataframe['%-volume_ratio'] = dataframe['volume'] / (vol_sma + 1e-10)
        
        # Volume Trend (volume increasing or decreasing?)
        vol_ema = dataframe['volume'].ewm(span=10).mean()
        dataframe['%-volume_trend'] = vol_ema.diff(5) / (vol_ema + 1e-10)
        
        # CMF (Chaikin Money Flow) - Đã dao động quanh 0
        cmf = pta.cmf(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], length=20)
        if cmf is not None:
            dataframe['%-cmf'] = cmf
        else:
            dataframe['%-cmf'] = 0
        
        # VWAP Distance (Volume Weighted Average Price)
        # Note: pta.vwap requires datetime index, use manual calculation instead
        typical_price = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
        vwap_approx = (typical_price * dataframe['volume']).rolling(20).sum() / (dataframe['volume'].rolling(20).sum() + 1e-10)
        dataframe['%-dist_to_vwap'] = (dataframe['close'] - vwap_approx) / (vwap_approx + 1e-10)
        
        return dataframe
    
    # ============================================================
    # 6. PRICE PATTERN FEATURES - Candle Patterns (Binary)
    # ============================================================
    
    @staticmethod
    def add_candle_features(dataframe: DataFrame) -> DataFrame:
        """
        Candle Pattern Features.
        
        Các thông tin từ candlestick được chuẩn hóa.
        """
        # Candle body size (normalized by price)
        body = abs(dataframe['close'] - dataframe['open'])
        dataframe['%-body_size'] = body / dataframe['close']
        
        # Candle direction (1: bullish, -1: bearish, 0: doji)
        dataframe['%-candle_direction'] = np.sign(dataframe['close'] - dataframe['open'])
        
        # Upper/Lower shadow size (normalized)
        upper_shadow = dataframe['high'] - np.maximum(dataframe['close'], dataframe['open'])
        lower_shadow = np.minimum(dataframe['close'], dataframe['open']) - dataframe['low']
        dataframe['%-upper_shadow'] = upper_shadow / dataframe['close']
        dataframe['%-lower_shadow'] = lower_shadow / dataframe['close']
        
        # Shadow to body ratio
        dataframe['%-shadow_to_body'] = (upper_shadow + lower_shadow) / (body + 1e-10)
        
        # Consecutive candles (streak of bullish/bearish)
        direction = np.sign(dataframe['close'] - dataframe['open'])
        
        # Count consecutive same direction candles
        streak = direction.groupby((direction != direction.shift()).cumsum()).cumcount() + 1
        streak = streak * direction  # Positive for bullish streak, negative for bearish
        dataframe['%-candle_streak'] = streak / 10  # Normalize (max ~10 candles)
        
        return dataframe
    
    # ============================================================
    # 7. SUPPORT/RESISTANCE FEATURES
    # ============================================================
    
    @staticmethod
    def add_sr_features(dataframe: DataFrame, lookback: int = 50) -> DataFrame:
        """
        Support/Resistance Features.
        
        Khoảng cách đến các mức hỗ trợ/kháng cự.
        """
        # Rolling high/low (Donchian-style)
        rolling_high = dataframe['high'].rolling(lookback).max()
        rolling_low = dataframe['low'].rolling(lookback).min()
        
        # Distance to rolling high/low (normalized)
        dataframe['%-dist_to_high'] = (rolling_high - dataframe['close']) / dataframe['close']
        dataframe['%-dist_to_low'] = (dataframe['close'] - rolling_low) / dataframe['close']
        
        # Position within range (0 = at low, 1 = at high)
        range_size = rolling_high - rolling_low
        dataframe['%-range_position'] = (dataframe['close'] - rolling_low) / (range_size + 1e-10)
        
        # New high/low binary
        dataframe['%-is_new_high'] = (dataframe['high'] >= rolling_high).astype(int)
        dataframe['%-is_new_low'] = (dataframe['low'] <= rolling_low).astype(int)
        
        return dataframe
    
    # ============================================================
    # 8. MARKET REGIME FEATURES - KER, Volatility Regime
    # ============================================================
    
    @staticmethod
    def add_market_regime_features(dataframe: DataFrame) -> DataFrame:
        """
        Advanced Market Regime Detection.
        
        Kaufman Efficiency Ratio (KER):
        - Gần 1: Trending cực mạnh (ít nhiễu, tín hiệu rõ)
        - Gần 0: Sideway/Choppy (nhiều nhiễu, tránh trade)
        
        Volatility Regime:
        - Phân loại độ biến động: Low/Normal/High
        - Z-score của ATR so với historical
        
        Features:
        - %-ker_10: Kaufman Efficiency Ratio (10 periods)
        - %-ker_20: Kaufman Efficiency Ratio (20 periods)
        - %-volatility_zscore: ATR z-score vs 100-period mean
        - %-volatility_regime: -1=Low, 0=Normal, 1=High
        - %-choppiness: Choppiness Index (0-100 normalized)
        """
        # === Kaufman Efficiency Ratio (KER) ===
        # KER = |Change| / Total Volatility
        # High KER = Trending, Low KER = Choppy
        for period in [10, 20]:
            change = dataframe['close'].diff(period).abs()
            volatility = dataframe['close'].diff(1).abs().rolling(period).sum()
            dataframe[f'%-ker_{period}'] = change / (volatility + 1e-10)
            dataframe[f'%-ker_{period}'] = dataframe[f'%-ker_{period}'].clip(0, 1)
        
        # === Volatility Regime ===
        # Z-score of current ATR vs rolling mean/std
        if '%-atr_pct' not in dataframe.columns:
            atr = pd.Series(ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14), index=dataframe.index)
            dataframe['%-atr_pct'] = atr / dataframe['close']
        
        atr_mean = dataframe['%-atr_pct'].rolling(100).mean()
        atr_std = dataframe['%-atr_pct'].rolling(100).std()
        dataframe['%-volatility_zscore'] = (dataframe['%-atr_pct'] - atr_mean) / (atr_std + 1e-10)
        dataframe['%-volatility_zscore'] = dataframe['%-volatility_zscore'].clip(-3, 3)  # Clip extremes
        
        # Volatility regime classification
        # -1: Low volatility, 0: Normal, 1: High volatility
        dataframe['%-volatility_regime'] = np.select(
            [
                dataframe['%-volatility_zscore'] < -1,  # Low vol
                dataframe['%-volatility_zscore'] > 1,   # High vol
            ],
            [-1, 1],
            default=0  # Normal
        )
        
        # === Choppiness Index ===
        # High = Choppy/Sideway, Low = Trending
        high_low_diff = dataframe['high'] - dataframe['low']
        sum_high_low = high_low_diff.rolling(14).sum()
        highest_high = dataframe['high'].rolling(14).max()
        lowest_low = dataframe['low'].rolling(14).min()
        true_range = highest_high - lowest_low
        
        choppiness = 100 * np.log10(sum_high_low / (true_range + 1e-10)) / np.log10(14)
        dataframe['%-choppiness'] = (choppiness - 50) / 50  # Normalize to [-1, 1]
        dataframe['%-choppiness'] = dataframe['%-choppiness'].clip(-1, 1)
        
        # === Range Expansion/Contraction ===
        # Are we breaking out or consolidating?
        price_range = dataframe['high'] - dataframe['low']
        avg_range = price_range.rolling(20).mean()
        dataframe['%-range_expansion'] = (price_range - avg_range) / (avg_range + 1e-10)
        
        return dataframe
    
    # ============================================================
    # 9. CONFLUENCE FEATURES - Meta-indicators
    # ============================================================
    
    @staticmethod
    def add_confluence_features(dataframe: DataFrame) -> DataFrame:
        """
        Confluence (Meta-features) - Tổng hợp nhiều tín hiệu.
        
        Thay vì để AI tự mò mẫm trong biển indicators,
        tạo các "Siêu chỉ báo" đại diện cho sự đồng thuận.
        
        Features:
        - %-trend_confluence: Sự đồng thuận xu hướng (EMAs + ADX)
        - %-momentum_confluence: Sự đồng thuận momentum (RSI + MFI + CMF)
        - %-money_pressure: Áp lực dòng tiền (OBV + Volume Imbalance)
        - %-overall_score: Điểm tổng hợp cho entry decision
        """
        # === TREND CONFLUENCE ===
        # Nếu EMA ngắn > dài VÀ ADX mạnh VÀ KER cao → Trend rất mạnh
        # Scale: 0 (no trend) to 1 (strong trend)
        
        trend_signals = []
        
        # EMA 10 > close?
        if '%-dist_to_ema_10' in dataframe.columns:
            trend_signals.append((dataframe['%-dist_to_ema_10'] > 0).astype(float))
        
        # EMA 20 > close?
        if '%-dist_to_ema_20' in dataframe.columns:
            trend_signals.append((dataframe['%-dist_to_ema_20'] > 0).astype(float))
        
        # EMA 50 > close?
        if '%-dist_to_ema_50' in dataframe.columns:
            trend_signals.append((dataframe['%-dist_to_ema_50'] > 0).astype(float))
        
        # ADX strong (> 0.25 = 25 in raw)?
        if '%-adx' in dataframe.columns:
            trend_signals.append((dataframe['%-adx'] > 0.25).astype(float))
        
        # KER trending (> 0.5)?
        if '%-ker_10' in dataframe.columns:
            trend_signals.append((dataframe['%-ker_10'] > 0.5).astype(float))
        
        if trend_signals:
            dataframe['%-trend_confluence'] = sum(trend_signals) / len(trend_signals)
        else:
            dataframe['%-trend_confluence'] = 0.5
        
        # === MOMENTUM CONFLUENCE ===
        # RSI tăng + MFI tăng + Volume tăng
        # Scale: 0 (bearish) to 1 (bullish)
        
        momentum_signals = []
        
        # RSI > 50?
        if '%-rsi_normalized' in dataframe.columns:
            momentum_signals.append((dataframe['%-rsi_normalized'] > 0).astype(float))
        
        # MFI > 50?
        if '%-mfi_normalized' in dataframe.columns:
            momentum_signals.append((dataframe['%-mfi_normalized'] > 0).astype(float))
        
        # CMF > 0?
        if '%-cmf' in dataframe.columns:
            momentum_signals.append((dataframe['%-cmf'] > 0).astype(float))
        
        # OBV rising?
        if '%-obv_slope' in dataframe.columns:
            momentum_signals.append((dataframe['%-obv_slope'] > 0).astype(float))
        
        if momentum_signals:
            dataframe['%-momentum_confluence'] = sum(momentum_signals) / len(momentum_signals)
        else:
            dataframe['%-momentum_confluence'] = 0.5
        
        # === MONEY PRESSURE ===
        # Áp lực dòng tiền: Kết hợp OBV và Volume momentum
        # Scale: -1 (selling pressure) to +1 (buying pressure)
        
        pressure_components = []
        
        if '%-obv_slope' in dataframe.columns:
            # OBV slope normalized to [-1, 1]
            obv_normalized = dataframe['%-obv_slope'].clip(-0.1, 0.1) * 10
            pressure_components.append(obv_normalized)
        
        if '%-cmf' in dataframe.columns:
            # CMF already in [-1, 1]
            pressure_components.append(dataframe['%-cmf'])
        
        if '%-volume_trend' in dataframe.columns:
            # Volume trend normalized
            vol_normalized = dataframe['%-volume_trend'].clip(-0.5, 0.5) * 2
            pressure_components.append(vol_normalized)
        
        if pressure_components:
            dataframe['%-money_pressure'] = sum(pressure_components) / len(pressure_components)
            dataframe['%-money_pressure'] = dataframe['%-money_pressure'].clip(-1, 1)
        else:
            dataframe['%-money_pressure'] = 0
        
        # === OVERALL ENTRY SCORE ===
        # Combine trend + momentum + money pressure
        # Scale: 0 (avoid) to 1 (strong entry)
        
        dataframe['%-overall_score'] = (
            dataframe['%-trend_confluence'] * 0.4 +  # 40% weight on trend
            dataframe['%-momentum_confluence'] * 0.35 +  # 35% weight on momentum
            (dataframe['%-money_pressure'] + 1) / 2 * 0.25  # 25% weight on money pressure
        )
        
        # === BEARISH SCORE (for shorts) ===
        # Inverse of bullish signals
        dataframe['%-bearish_score'] = 1 - dataframe['%-overall_score']
        
        return dataframe
    
    # ============================================================
    # MAIN METHOD - Add All Features
    # ============================================================
    
    @staticmethod
    def add_all_features(dataframe: DataFrame) -> DataFrame:
        """
        Add ALL properly engineered features to dataframe.
        
        Đây là method chính để gọi từ FreqAIStrategy.
        Tất cả features đều đã được chuẩn hóa và stationary.
        
        Args:
            dataframe: OHLCV DataFrame
            
        Returns:
            DataFrame với tất cả features đúng chuẩn
        """
        logger.info("Adding Feature Engineering features...")
        
        # 1. Core: Log Returns (QUAN TRỌNG NHẤT)
        dataframe = FeatureEngineering.add_log_returns(dataframe)
        dataframe = FeatureEngineering.add_price_momentum(dataframe)
        
        # 2. Trend: EMA Distances & Slopes
        dataframe = FeatureEngineering.add_ema_features(dataframe)
        dataframe = FeatureEngineering.add_trend_strength(dataframe)
        
        # 3. Momentum: Oscillators
        dataframe = FeatureEngineering.add_momentum_oscillators(dataframe)
        
        # 4. Volatility: ATR%, BB Width
        dataframe = FeatureEngineering.add_volatility_features(dataframe)
        
        # 5. Volume: OBV, CMF, MFI
        dataframe = FeatureEngineering.add_volume_features(dataframe)
        
        # 6. Candle Patterns
        dataframe = FeatureEngineering.add_candle_features(dataframe)
        
        # 7. Support/Resistance
        dataframe = FeatureEngineering.add_sr_features(dataframe)
        
        # 8. Market Regime (KER, Volatility, Choppiness)
        dataframe = FeatureEngineering.add_market_regime_features(dataframe)
        
        # 9. Confluence (Meta-features)
        dataframe = FeatureEngineering.add_confluence_features(dataframe)
        
        # 10. VSA (Volume Spread Analysis) - từ báo cáo nghiên cứu
        if VSA_AVAILABLE:
            dataframe = VSAIndicators.add_all_indicators(dataframe)
            logger.info("VSA Indicators added")
        
        # 11. Handle NaN values from rolling indicators
        # Rolling indicators like EMA(200), rolling(50) create NaN in first N rows
        # Strategy: Forward fill first, then fill remaining with 0
        feature_cols = [c for c in dataframe.columns if c.startswith('%-')]
        dataframe[feature_cols] = dataframe[feature_cols].ffill()  # Forward fill
        dataframe[feature_cols] = dataframe[feature_cols].fillna(0)  # Fill remaining NaN with 0
        
        logger.info(f"Added {len(feature_cols)} features")
        
        return dataframe


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    import pandas as pd
    import numpy as np
    
    # Create sample OHLCV data
    np.random.seed(42)
    n = 500
    dates = pd.date_range(start='2025-01-01', periods=n, freq='5min')
    
    # Simulate price movement
    returns = np.random.normal(0.0001, 0.001, n)
    price = 40000 * np.exp(np.cumsum(returns))
    
    sample_data = pd.DataFrame({
        'date': dates,
        'open': price * (1 + np.random.uniform(-0.001, 0.001, n)),
        'high': price * (1 + np.random.uniform(0, 0.003, n)),
        'low': price * (1 - np.random.uniform(0, 0.003, n)),
        'close': price,
        'volume': np.random.uniform(100, 1000, n) * (1 + 0.5 * np.random.randn(n))
    })
    
    # Fix high/low
    sample_data['high'] = sample_data[['open', 'close', 'high']].max(axis=1)
    sample_data['low'] = sample_data[['open', 'close', 'low']].min(axis=1)
    sample_data['volume'] = np.abs(sample_data['volume'])
    
    # Add all features
    enhanced_data = FeatureEngineering.add_all_features(sample_data)
    
    print("\n" + "="*60)
    print("FEATURE ENGINEERING TEST RESULTS")
    print("="*60)
    
    feature_cols = [col for col in enhanced_data.columns if col.startswith('%-')]
    print(f"\nTotal features created: {len(feature_cols)}")
    
    print("\nFeature categories:")
    categories = {
        'Log Returns': [c for c in feature_cols if 'log' in c],
        'Momentum': [c for c in feature_cols if any(x in c for x in ['roc', 'momentum', 'rsi', 'willr', 'stoch', 'cci'])],
        'Trend': [c for c in feature_cols if any(x in c for x in ['ema', 'adx', 'di_diff'])],
        'Volatility': [c for c in feature_cols if any(x in c for x in ['atr', 'bb_', 'true_range'])],
        'Volume': [c for c in feature_cols if any(x in c for x in ['volume', 'obv', 'mfi', 'cmf', 'vwap'])],
        'Candle': [c for c in feature_cols if any(x in c for x in ['body', 'shadow', 'candle', 'direction'])],
        'S/R': [c for c in feature_cols if any(x in c for x in ['high', 'low', 'range', 'new_'])]
    }
    
    for cat, cols in categories.items():
        print(f"  {cat}: {len(cols)} features")
        for col in cols[:3]:  # Show first 3
            print(f"    - {col}")
        if len(cols) > 3:
            print(f"    ... and {len(cols) - 3} more")
    
    print("\nSample values (last row):")
    print(enhanced_data[feature_cols].iloc[-1].to_string())
    
    print("\nFeature statistics:")
    print(enhanced_data[feature_cols].describe().T[['mean', 'std', 'min', 'max']].to_string())
