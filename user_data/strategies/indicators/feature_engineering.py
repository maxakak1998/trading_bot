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
        dataframe['%-roc_5'] = ta.ROCP(dataframe['close'], timeperiod=5)
        dataframe['%-roc_10'] = ta.ROCP(dataframe['close'], timeperiod=10)
        dataframe['%-roc_20'] = ta.ROCP(dataframe['close'], timeperiod=20)
        
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
            # Tính EMA
            ema = ta.EMA(dataframe['close'], timeperiod=period)
            
            # Distance to EMA (chuẩn hóa)
            # Dương: Giá trên EMA, Âm: Giá dưới EMA
            dataframe[f'%-dist_to_ema_{period}'] = (dataframe['close'] - ema) / (ema + 1e-10)
            
            # EMA Slope (độ dốc - thể hiện xu hướng)
            # Dương: EMA đang tăng, Âm: EMA đang giảm
            dataframe[f'%-ema_slope_{period}'] = ema.diff() / (ema + 1e-10)
        
        # EMA Cross (tín hiệu giao cắt) - Chuẩn hóa
        if 20 in periods and 50 in periods:
            ema_20 = ta.EMA(dataframe['close'], timeperiod=20)
            ema_50 = ta.EMA(dataframe['close'], timeperiod=50)
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
        adx = ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['%-adx'] = adx / 100  # Chuẩn hóa về 0-1
        
        # +DI và -DI để biết hướng
        plus_di = ta.PLUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        minus_di = ta.MINUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        
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
        rsi = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['%-rsi_normalized'] = (rsi - 50) / 50  # -1 (oversold) to +1 (overbought)
        
        # RSI Slope (momentum của RSI)
        dataframe['%-rsi_slope'] = rsi.diff(3) / 100
        
        # Williams %R (-100 to 0) → Chuẩn hóa về [-1, 1]
        willr = ta.WILLR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['%-willr_normalized'] = (willr + 50) / 50  # -1 (oversold) to +1 (overbought)
        
        # Stochastic RSI (0-100) → Chuẩn hóa
        stochrsi = pta.stochrsi(dataframe['close'], length=14)
        if stochrsi is not None and 'STOCHRSIk_14_14_3_3' in stochrsi.columns:
            dataframe['%-stochrsi'] = (stochrsi['STOCHRSIk_14_14_3_3'] - 50) / 50
        else:
            dataframe['%-stochrsi'] = 0
        
        # CCI (Commodity Channel Index) - Đã dao động quanh 0
        cci = ta.CCI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=20)
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
        atr = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['%-atr_pct'] = atr / dataframe['close']
        
        # ATR change (volatility đang tăng hay giảm?)
        dataframe['%-atr_change'] = atr.pct_change(5)
        
        # Bollinger Band Width (đã chuẩn hóa)
        bb = pta.bbands(dataframe['close'], length=20, std=2)
        if bb is not None:
            upper = bb['BBU_20_2.0']
            lower = bb['BBL_20_2.0']
            middle = bb['BBM_20_2.0']
            
            # BB Width (% of price)
            dataframe['%-bb_width'] = (upper - lower) / middle
            
            # BB Position (vị trí giá trong BB)
            # 0 = lower band, 1 = upper band, 0.5 = middle
            dataframe['%-bb_position'] = (dataframe['close'] - lower) / (upper - lower + 1e-10)
            
            # Distance to bands
            dataframe['%-dist_to_bb_upper'] = (upper - dataframe['close']) / dataframe['close']
            dataframe['%-dist_to_bb_lower'] = (dataframe['close'] - lower) / dataframe['close']
        
        # True Range normalized
        tr = ta.TRANGE(dataframe['high'], dataframe['low'], dataframe['close'])
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
        mfi = ta.MFI(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], timeperiod=14)
        dataframe['%-mfi_normalized'] = (mfi - 50) / 50  # -1 to +1
        
        # OBV (On Balance Volume) - Cần chuẩn hóa
        obv = ta.OBV(dataframe['close'], dataframe['volume'])
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
        vwap = pta.vwap(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'])
        if vwap is not None:
            dataframe['%-dist_to_vwap'] = (dataframe['close'] - vwap) / (vwap + 1e-10)
        else:
            # Fallback: Use typical price weighted
            typical_price = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
            vwap_approx = (typical_price * dataframe['volume']).rolling(20).sum() / dataframe['volume'].rolling(20).sum()
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
        
        logger.info(f"Added {len([c for c in dataframe.columns if c.startswith('%-')])} features")
        
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
