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
    def _add_log_returns(dataframe: DataFrame, features: dict, periods: list = [1, 5, 10, 20]) -> None:
        """Calculate Log Returns features into dict"""
        for period in periods:
            features[f'%-log_return_{period}'] = np.log(
                dataframe['close'] / dataframe['close'].shift(period)
            )
        
        # Log return của volume (biến động volume)
        features['%-log_volume_change'] = np.log(
            (dataframe['volume'] + 1) / (dataframe['volume'].shift(1) + 1)
        )
    
    @staticmethod
    def _add_price_momentum(dataframe: DataFrame, features: dict) -> None:
        """Calculate Price Momentum features into dict"""
        # ROC (Rate of Change)
        features['%-roc_5'] = ta.ROCP(dataframe['close'], timeperiod=5)
        features['%-roc_10'] = ta.ROCP(dataframe['close'], timeperiod=10)
        features['%-roc_20'] = ta.ROCP(dataframe['close'], timeperiod=20)
        
        # Price momentum
        features['%-momentum_5'] = (dataframe['close'] - dataframe['close'].shift(5)) / (dataframe['close'].shift(5) + 1e-10)
    
    # ============================================================
    # 2. TREND FEATURES - Distance & Slopes
    # ============================================================
    
    @staticmethod
    def _add_ema_features(dataframe: DataFrame, features: dict, periods: list = [10, 20, 50, 200]) -> None:
        """Calculate EMA features into dict"""
        for period in periods:
            ema = ta.EMA(dataframe['close'], timeperiod=period)
            if isinstance(ema, np.ndarray):
                ema = pd.Series(ema, index=dataframe.index)
            
            # Distance to EMA
            features[f'%-dist_to_ema_{period}'] = (dataframe['close'] - ema) / (ema + 1e-10)
            
            # EMA Slope
            features[f'%-ema_slope_{period}'] = ema.diff() / (ema + 1e-10)
        
        # EMA Cross
        if 20 in periods and 50 in periods:
            ema_20 = ta.EMA(dataframe['close'], timeperiod=20)
            ema_50 = ta.EMA(dataframe['close'], timeperiod=50)
            if isinstance(ema_20, np.ndarray): ema_20 = pd.Series(ema_20, index=dataframe.index)
            if isinstance(ema_50, np.ndarray): ema_50 = pd.Series(ema_50, index=dataframe.index)
            
            features['%-ema_20_50_diff'] = (ema_20 - ema_50) / (ema_50 + 1e-10)
    
    @staticmethod
    def _add_trend_strength(dataframe: DataFrame, features: dict) -> None:
        """Calculate Trend Strength features into dict"""
        # ADX
        adx = ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        features['%-adx'] = adx / 100
        
        # DI Difference
        plus_di = ta.PLUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        minus_di = ta.MINUS_DI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        
        if isinstance(plus_di, np.ndarray): plus_di = pd.Series(plus_di, index=dataframe.index)
        if isinstance(minus_di, np.ndarray): minus_di = pd.Series(minus_di, index=dataframe.index)
        
        features['%-di_diff'] = (plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    
    # ============================================================
    # 3. MOMENTUM FEATURES - Oscillators
    # ============================================================
    
    @staticmethod
    def _add_momentum_oscillators(dataframe: DataFrame, features: dict) -> None:
        """Calculate Momentum Oscillators into dict"""
        # RSI
        rsi = ta.RSI(dataframe['close'], timeperiod=14)
        if isinstance(rsi, np.ndarray): rsi = pd.Series(rsi, index=dataframe.index)
        
        features['%-rsi_normalized'] = (rsi - 50) / 50
        features['%-rsi_slope'] = rsi.diff(3) / 100
        
        # Williams %R
        willr = ta.WILLR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        features['%-willr_normalized'] = (willr + 50) / 50
        
        # Stochastic RSI
        stochrsi = pta.stochrsi(dataframe['close'], length=14)
        if stochrsi is not None and 'STOCHRSIk_14_14_3_3' in stochrsi.columns:
            features['%-stochrsi'] = (stochrsi['STOCHRSIk_14_14_3_3'] - 50) / 50
        else:
            features['%-stochrsi'] = pd.Series(0, index=dataframe.index)
        
        # CCI
        cci = ta.CCI(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=20)
        features['%-cci_normalized'] = cci / 200
    
    # ============================================================
    # 4. VOLATILITY FEATURES
    # ============================================================
    
    @staticmethod
    def _add_volatility_features(dataframe: DataFrame, features: dict) -> None:
        """Calculate Volatility features into dict"""
        # ATR
        atr = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        if isinstance(atr, np.ndarray): atr = pd.Series(atr, index=dataframe.index)
        
        features['%-atr_pct'] = atr / dataframe['close']
        features['%-atr_change'] = atr.pct_change(5)
        
        # Bollinger Bands
        bb = pta.bbands(dataframe['close'], length=20, std=2)
        if bb is not None and len(bb.columns) >= 3:
            bb_cols = bb.columns.tolist()
            upper_col = [c for c in bb_cols if 'BBU' in c][0] if any('BBU' in c for c in bb_cols) else None
            lower_col = [c for c in bb_cols if 'BBL' in c][0] if any('BBL' in c for c in bb_cols) else None
            middle_col = [c for c in bb_cols if 'BBM' in c][0] if any('BBM' in c for c in bb_cols) else None
            
            if upper_col and lower_col and middle_col:
                upper = bb[upper_col]
                lower = bb[lower_col]
                middle = bb[middle_col]
                
                features['%-bb_width'] = (upper - lower) / middle
                features['%-bb_position'] = (dataframe['close'] - lower) / (upper - lower + 1e-10)
                features['%-dist_to_bb_upper'] = (upper - dataframe['close']) / dataframe['close']
                features['%-dist_to_bb_lower'] = (dataframe['close'] - lower) / dataframe['close']
            else:
                # Default values when BB columns not found
                features['%-bb_width'] = pd.Series(0.0, index=dataframe.index)
                features['%-bb_position'] = pd.Series(0.5, index=dataframe.index)
                features['%-dist_to_bb_upper'] = pd.Series(0.0, index=dataframe.index)
                features['%-dist_to_bb_lower'] = pd.Series(0.0, index=dataframe.index)
        else:
            # Default values when BB calculation fails
            features['%-bb_width'] = pd.Series(0.0, index=dataframe.index)
            features['%-bb_position'] = pd.Series(0.5, index=dataframe.index)
            features['%-dist_to_bb_upper'] = pd.Series(0.0, index=dataframe.index)
            features['%-dist_to_bb_lower'] = pd.Series(0.0, index=dataframe.index)
        
        # True Range
        tr = ta.TRANGE(dataframe['high'], dataframe['low'], dataframe['close'])
        features['%-true_range_pct'] = tr / dataframe['close']
    
    # ============================================================
    # 5. VOLUME FEATURES
    # ============================================================
    
    @staticmethod
    def _add_volume_features(dataframe: DataFrame, features: dict) -> None:
        """Calculate Volume features into dict"""
        # MFI
        mfi = ta.MFI(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], timeperiod=14)
        features['%-mfi_normalized'] = (mfi - 50) / 50
        
        # OBV
        obv = ta.OBV(dataframe['close'], dataframe['volume'])
        if isinstance(obv, np.ndarray): obv = pd.Series(obv, index=dataframe.index)
        
        obv_std = obv.rolling(20).std()
        features['%-obv_change'] = obv.diff(5) / (obv_std + 1e-10)
        
        obv_ema = obv.ewm(span=10).mean()
        features['%-obv_slope'] = obv_ema.diff(3) / (obv_ema.abs() + 1e-10)
        
        # Volume Ratio
        vol_sma = dataframe['volume'].rolling(20).mean()
        features['%-volume_ratio'] = dataframe['volume'] / (vol_sma + 1e-10)
        
        # Volume Trend
        vol_ema = dataframe['volume'].ewm(span=10).mean()
        features['%-volume_trend'] = vol_ema.diff(5) / (vol_ema + 1e-10)
        
        # CMF
        cmf = pta.cmf(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], length=20)
        features['%-cmf'] = cmf if cmf is not None else pd.Series(0, index=dataframe.index)
        
        # VWAP Distance
        typical_price = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
        vwap_approx = (typical_price * dataframe['volume']).rolling(20).sum() / (dataframe['volume'].rolling(20).sum() + 1e-10)
        features['%-dist_to_vwap'] = (dataframe['close'] - vwap_approx) / (vwap_approx + 1e-10)
    
    # ============================================================
    # 6. CANDLE PATTERN FEATURES
    # ============================================================
    
    @staticmethod
    def _add_candle_features(dataframe: DataFrame, features: dict) -> None:
        """Calculate Candle features into dict"""
        body = abs(dataframe['close'] - dataframe['open'])
        features['%-body_size'] = body / dataframe['close']
        
        features['%-candle_direction'] = np.sign(dataframe['close'] - dataframe['open'])
        
        upper_shadow = dataframe['high'] - np.maximum(dataframe['close'], dataframe['open'])
        lower_shadow = np.minimum(dataframe['close'], dataframe['open']) - dataframe['low']
        features['%-upper_shadow'] = upper_shadow / dataframe['close']
        features['%-lower_shadow'] = lower_shadow / dataframe['close']
        
        features['%-shadow_to_body'] = (upper_shadow + lower_shadow) / (body + 1e-10)
        
        direction = np.sign(dataframe['close'] - dataframe['open'])
        streak = direction.groupby((direction != direction.shift()).cumsum()).cumcount() + 1
        features['%-candle_streak'] = (streak * direction) / 10
    
    # ============================================================
    # 7. SUPPORT/RESISTANCE FEATURES
    # ============================================================
    
    @staticmethod
    def _add_sr_features(dataframe: DataFrame, features: dict, lookback: int = 50) -> None:
        """Calculate S/R features into dict"""
        rolling_high = dataframe['high'].rolling(lookback).max()
        rolling_low = dataframe['low'].rolling(lookback).min()
        
        features['%-dist_to_high'] = (rolling_high - dataframe['close']) / dataframe['close']
        features['%-dist_to_low'] = (dataframe['close'] - rolling_low) / dataframe['close']
        
        range_size = rolling_high - rolling_low
        features['%-range_position'] = (dataframe['close'] - rolling_low) / (range_size + 1e-10)
        
        features['%-is_new_high'] = (dataframe['high'] >= rolling_high).astype(int)
        features['%-is_new_low'] = (dataframe['low'] <= rolling_low).astype(int)
    
    # ============================================================
    # 8. MARKET REGIME FEATURES
    # ============================================================
    
    @staticmethod
    def _add_market_regime_features(dataframe: DataFrame, features: dict) -> None:
        """Calculate Market Regime features into dict"""
        # KER
        for period in [10, 20]:
            change = dataframe['close'].diff(period).abs()
            volatility = dataframe['close'].diff(1).abs().rolling(period).sum()
            ker = change / (volatility + 1e-10)
            features[f'%-ker_{period}'] = ker.clip(0, 1)
        
        # Volatility Regime
        # Use existing ATR if available, else calc temp
        if '%-atr_pct' in features:
            atr_pct = features['%-atr_pct']
        else:
            atr = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
            atr_pct = pd.Series(atr, index=dataframe.index) / dataframe['close']
            
        atr_mean = atr_pct.rolling(100).mean()
        atr_std = atr_pct.rolling(100).std()
        zscore = (atr_pct - atr_mean) / (atr_std + 1e-10)
        features['%-volatility_zscore'] = zscore.clip(-3, 3)
        
        features['%-volatility_regime'] = np.select(
            [zscore < -1, zscore > 1],
            [-1, 1],
            default=0
        )
        
        # Choppiness
        high_low_diff = dataframe['high'] - dataframe['low']
        sum_high_low = high_low_diff.rolling(14).sum()
        highest_high = dataframe['high'].rolling(14).max()
        lowest_low = dataframe['low'].rolling(14).min()
        true_range = highest_high - lowest_low
        
        choppiness = 100 * np.log10(sum_high_low / (true_range + 1e-10)) / np.log10(14)
        features['%-choppiness'] = ((choppiness - 50) / 50).clip(-1, 1)
        
        # Range Expansion
        price_range = dataframe['high'] - dataframe['low']
        avg_range = price_range.rolling(20).mean()
        features['%-range_expansion'] = (price_range - avg_range) / (avg_range + 1e-10)
    
    # ============================================================
    # 9. CONFLUENCE FEATURES
    # ============================================================
    
    @staticmethod
    def _add_confluence_features(dataframe: DataFrame, features: dict) -> None:
        """Calculate Confluence features into dict"""
        # Helper to safely get feature
        def get_f(name):
            return features.get(name, pd.Series(0, index=dataframe.index))
            
        # === TREND CONFLUENCE ===
        trend_score = (
            (get_f('%-dist_to_ema_10') > 0).astype(float) +
            (get_f('%-dist_to_ema_20') > 0).astype(float) +
            (get_f('%-dist_to_ema_50') > 0).astype(float) +
            (get_f('%-adx') > 0.25).astype(float) +
            (get_f('%-ker_10') > 0.5).astype(float)
        ) / 5
        features['%-trend_confluence'] = trend_score
        
        # === MOMENTUM CONFLUENCE ===
        momentum_score = (
            (get_f('%-rsi_normalized') > 0).astype(float) +
            (get_f('%-mfi_normalized') > 0).astype(float) +
            (get_f('%-cmf') > 0).astype(float) +
            (get_f('%-obv_slope') > 0).astype(float)
        ) / 4
        features['%-momentum_confluence'] = momentum_score
        
        # === MONEY PRESSURE (VSA Integrated) ===
        # VSA Logic: Effort (Volume) vs Result (Price Spread)
        # High Volume + Small Spread = Churning (Potential Reversal) -> Negative
        # High Volume + Large Spread = Valid Move -> Positive
        
        vol_ma = dataframe['volume'].rolling(20).mean()
        spread = dataframe['high'] - dataframe['low']
        spread_ma = spread.rolling(20).mean()
        
        # Normalized Volume & Spread
        rel_vol = dataframe['volume'] / (vol_ma + 1e-10)
        rel_spread = spread / (spread_ma + 1e-10)
        
        # VSA Score:
        # 1. Valid Move: High Vol (>1.5) + High Spread (>1.5) -> +1
        # 2. Churning: High Vol (>1.5) + Low Spread (<0.8) -> -1
        # 3. Weak Move: Low Vol (<0.8) + High Spread (>1.5) -> -0.5 (Fakeout)
        
        vsa_score = np.zeros(len(dataframe))
        
        # Vectorized conditions
        c_high_vol = rel_vol > 1.5
        c_low_vol = rel_vol < 0.8
        c_high_spread = rel_spread > 1.5
        c_low_spread = rel_spread < 0.8
        
        # Apply VSA logic
        vsa_score = np.where(c_high_vol & c_high_spread, 1.0, vsa_score)   # Valid
        vsa_score = np.where(c_high_vol & c_low_spread, -1.0, vsa_score)   # Churning
        vsa_score = np.where(c_low_vol & c_high_spread, -0.5, vsa_score)   # Fakeout
        
        # Convert to Series
        vsa_series = pd.Series(vsa_score, index=dataframe.index)
        features['%-vsa_score'] = vsa_series
        
        # Enhanced Money Pressure
        pressure = (
            get_f('%-obv_slope').clip(-0.1, 0.1) * 10 +
            get_f('%-cmf') +
            get_f('%-volume_trend').clip(-0.5, 0.5) * 2 +
            vsa_series * 0.5  # Add VSA weight
        ) / 3.5  # Normalize by sum of weights (1+1+1+0.5)
        
        features['%-money_pressure'] = pressure.clip(-1, 1)
        
        # === OVERALL SCORE ===
        features['%-overall_score'] = (
            trend_score * 0.4 +
            momentum_score * 0.35 +
            (pressure + 1) / 2 * 0.25
        )
        
        # === WYCKOFF & VSA ADVANCED ===
        # Wyckoff Volume Effort (Volume / Price Range)
        # Low Effort (High Vol, Low Range) = Accumulation/Distribution
        price_range = dataframe['high'] - dataframe['low']
        effort = dataframe['volume'] / (price_range + 1e-10)
        # Normalize log-effort
        log_effort = np.log1p(effort)
        features['%-wyckoff_volume_effort'] = (log_effort - log_effort.rolling(20).mean()) / (log_effort.rolling(20).std() + 1e-10)
        
        # VSA Divergence (Price vs Volume Correlation)
        # High Negative Corr = Divergence (Price up, Vol down or Price down, Vol up)
        vol_corr = dataframe['close'].rolling(20).corr(dataframe['volume']).fillna(0)
        features['%-vsa_divergence'] = vol_corr
        
        features['%-bearish_score'] = 1 - features['%-overall_score']
    
    # ============================================================
    # MAIN METHOD - Add All Features
    # ============================================================
    
    @staticmethod
    def add_all_features(dataframe: DataFrame, config: dict = None) -> DataFrame:
        """
        Add ALL properly engineered features to dataframe.
        Uses dictionary collection + single concat for performance.
        
        Args:
            dataframe: Input DataFrame
            config: Optional config dict to check feature_flags
        """
        logger.info("Adding Feature Engineering features...")
        
        # Collect all features in a dictionary
        features = {}
        
        # 1. Core
        FeatureEngineering._add_log_returns(dataframe, features)
        FeatureEngineering._add_price_momentum(dataframe, features)
        
        # 2. Trend
        FeatureEngineering._add_ema_features(dataframe, features)
        FeatureEngineering._add_trend_strength(dataframe, features)
        
        # 3. Momentum
        FeatureEngineering._add_momentum_oscillators(dataframe, features)
        
        # 4. Volatility
        FeatureEngineering._add_volatility_features(dataframe, features)
        
        # 5. Volume
        FeatureEngineering._add_volume_features(dataframe, features)
        
        # 6. Candle Patterns
        FeatureEngineering._add_candle_features(dataframe, features)
        
        # 7. Support/Resistance
        FeatureEngineering._add_sr_features(dataframe, features)
        
        # 8. Market Regime
        FeatureEngineering._add_market_regime_features(dataframe, features)
        
        # 9. Confluence (depends on previous features)
        FeatureEngineering._add_confluence_features(dataframe, features)
        
        # 10. VSA (if available)
        if VSA_AVAILABLE:
            # VSA module might still be using old style, but that's okay for now
            # Ideally we should refactor VSA too, but let's stick to scope
            pass 
        
        # Create DataFrame from features dict
        if features:
            features_df = pd.DataFrame(features, index=dataframe.index)
            
            # Handle NaN values (ffill then 0)
            features_df = features_df.ffill().fillna(0)
            
            # Single concatenation
            dataframe = pd.concat([dataframe, features_df], axis=1)
            
        logger.info(f"Added {len(features)} features")
        
        # VSA is added separately if needed (legacy support)
        # Check vsa_indicators flag from config
        if VSA_AVAILABLE:
            vsa_enabled = True
            if config:
                vsa_enabled = config.get('freqai', {}).get('feature_flags', {}).get('vsa_indicators', True)
            if vsa_enabled:
                dataframe = VSAIndicators.add_all_indicators(dataframe)
            else:
                logger.info("VSA Indicators disabled via feature_flags")
        
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
