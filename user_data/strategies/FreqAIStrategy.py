# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, CategoricalParameter
import logging
from pandas import DataFrame
import pandas_ta as pta  # pandas_ta for advanced indicators
import talib.abstract as ta  # talib for basic indicators (required by FreqAI)
import sys
from pathlib import Path

# Add strategies directory to path to import local modules
sys.path.append(str(Path(__file__).parent))
from indicators.smc_indicators import SMCIndicators
from indicators.data_enhancement import DataEnhancement  # Phase 2 Features
from indicators.feature_engineering import FeatureEngineering  # Phase 3: Proper ML Features
from indicators.chart_patterns import ChartPatterns  # Phase 3: Chart Pattern Recognition
from indicators.wave_indicators import WaveIndicators  # Phase 3: Elliott Wave Lite (Fibonacci + AO)

logger = logging.getLogger(__name__)
import freqtrade.vendor.qtpylib.indicators as qtpylib

class FreqAIStrategy(IStrategy):
    """
    FreqAI Strategy example.
    """
    INTERFACE_VERSION = 3
    
    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "60": 0.01,
        "30": 0.03,
        "0": 0.05
    }

    # Risk Management
    stoploss = -0.05
    trailing_stop = False
    
    # Maximum risk per trade (% of margin)
    # Can be overridden in config.json under strategy settings
    # Example: "max_risk_per_trade": 0.15 for 15% max loss
    max_risk_per_trade = 0.20  # 20% default - Change this value to adjust risk tolerance
    
    # Leverage calculation:
    # Target Risk per Trade = max_risk_per_trade% of Stake (Margin)
    # Loss = Stake * Leverage * Stoploss_Price_Dist
    # max_risk_per_trade * Stake = Stake * Leverage * Stoploss_Price_Dist
    # Leverage = max_risk_per_trade / Stoploss_Price_Dist
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        """
        Customize leverage for each new trade.
        Uses max_risk_per_trade to calculate appropriate leverage.
        """
        risk_per_trade = self.max_risk_per_trade  # Use configurable risk limit
        stoploss_dist = abs(self.stoploss)
        
        # Calculate leverage
        # Example: Stoploss 5% (0.05) -> Leverage = 0.20 / 0.05 = 4x
        # Example: Stoploss 1% (0.01) -> Leverage = 0.20 / 0.01 = 20x
        
        target_leverage = risk_per_trade / stoploss_dist
        
        # Cap leverage at max_leverage or a safe limit (e.g. 20x)
        final_leverage = min(target_leverage, max_leverage, 20.0)
        
        return final_leverage
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, based on ATR (Average True Range).
        Returns a negative percentage value relative to current_rate.
        
        High volatility (high ATR) → Wider stoploss
        Low volatility (low ATR) → Tighter stoploss
        
        SAFETY: Stoploss is CLIPPED to ensure max loss never exceeds 20% of margin.
        Formula: Max_SL_Price = Max_Risk(20%) / Leverage
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get ATR from last candle
        atr = last_candle.get('atr', 0)
        
        # Get current leverage of the trade (default 1x if not available)
        current_leverage = getattr(trade, 'leverage', 1.0) or 1.0
        
        # SAFETY LIMIT: Max risk = max_risk_per_trade% of margin
        # Max_SL_Price = Max_Risk / Leverage
        # Example: Leverage 5x, Risk 20% → Max SL = 20% / 5 = -4%
        # Example: Leverage 10x, Risk 20% → Max SL = 20% / 10 = -2%
        # Example: Leverage 20x, Risk 20% → Max SL = 20% / 20 = -1%
        max_risk_on_margin = self.max_risk_per_trade  # Use configurable risk limit
        safe_sl_limit = -(max_risk_on_margin / current_leverage)
        
        if atr > 0 and current_rate > 0:
            # Stoploss = -2 * (ATR / current_rate)
            # Example: ATR = 2000, Price = 40000 → SL = -2 * (2000/40000) = -10%
            dynamic_sl = -2.0 * (atr / current_rate)
            
            # Apply safety limits:
            # 1. Cannot be wider than safe_sl_limit (protect margin)
            # 2. Cannot be tighter than -1% (allow some movement)
            # 3. Cannot be wider than -15% absolute max
            final_sl = max(dynamic_sl, safe_sl_limit, -0.15)  # Not wider than limit
            final_sl = min(final_sl, -0.01)  # Not tighter than 1%
            
            logger.debug(f"{pair}: ATR-SL={dynamic_sl:.2%}, SafeLimit={safe_sl_limit:.2%}, "
                        f"Leverage={current_leverage}x, FinalSL={final_sl:.2%}")
            
            return final_sl
        
        # Fallback to static stoploss if ATR not available
        return max(self.stoploss, safe_sl_limit)
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        """
        Customize stake amount for each trade based on AI confidence.
        
        Logic:
        - Low confidence (0.5-0.6): 50% of base stake (25 USDT)
        - Medium confidence (0.6-0.8): 100% of base stake (50 USDT)
        - High confidence (>0.8): 120% of base stake (60 USDT)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get AI confidence score (prediction mean)
        ai_confidence = last_candle.get('&s-up_or_down_mean', 0.5)
        
        # Scale stake based on confidence
        if ai_confidence > 0.8:
            stake_multiplier = 1.2  # High confidence: 120%
        elif ai_confidence > 0.6:
            stake_multiplier = 1.0  # Medium confidence: 100%
        else:
            stake_multiplier = 0.5  # Low confidence: 50%
        
        final_stake = proposed_stake * stake_multiplier
        
        # Ensure within min/max bounds
        if min_stake:
            final_stake = max(final_stake, min_stake)
        final_stake = min(final_stake, max_stake)
        
        return final_stake

    # Timeframe
    timeframe = '5m'
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # FreqAI attributes
    can_short = False

    def detect_market_regime(self, dataframe: DataFrame) -> DataFrame:
        """
        Classify market regime: TREND, SIDEWAY, or VOLATILE
        
        Logic:
        - ADX > 25 + BB Width > 0.04 → TREND (strong directional movement)
        - ADX < 20 + BB Width < 0.02 → SIDEWAY (no clear direction)
        - Otherwise → VOLATILE (unpredictable, avoid trading)
        """
        # Ensure ADX is calculated (using talib - uppercase function names)
        if 'adx' not in dataframe.columns:
            dataframe['adx'] = ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        
        # Ensure ATR is calculated
        if 'atr' not in dataframe.columns:
            dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        
        # Ensure BB width is calculated
        if 'bb_width' not in dataframe.columns:
            dataframe['bb_width'] = (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband']
        
        # Classify regime
        conditions = [
            (dataframe['adx'] > 25) & (dataframe['bb_width'] > 0.04),  # Strong trend
            (dataframe['adx'] < 20) & (dataframe['bb_width'] < 0.02),  # Sideway/consolidation
        ]
        choices = ['TREND', 'SIDEWAY']
        dataframe['market_regime'] = np.select(conditions, choices, default='VOLATILE')
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        
        CRITICAL: Must call self.freqai.start() to trigger FreqAI training and prediction!
        Without this call, FreqAI will NOT train and you get 0 trades.
        """
        # Calculate Bollinger Bands for market_regime detection (needed before detect_market_regime)
        # ta.BBANDS returns tuple: (upperband, middleband, lowerband)
        bb_upper, bb_middle, bb_lower = ta.BBANDS(dataframe['close'], timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upperband'] = bb_upper
        dataframe['bb_lowerband'] = bb_lower
        dataframe['bb_middleband'] = bb_middle
        
        # This is THE critical line that triggers FreqAI training!
        # It calls feature_engineering_* methods and trains/predicts
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # Add market_regime for entry/exit decisions (after FreqAI processing)
        dataframe = self.detect_market_regime(dataframe)
        
        return dataframe

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        
        expand_all: Features ở đây KHÔNG được tự động nhân bản cho các timeframes khác.
        Chỉ dùng cho các features đặc thù của 1 timeframe hoặc khó scale.
        
        Đặt ở đây:
        - Chart Patterns (khó scale đa khung)
        - SMC Indicators (đặc thù SMC)
        - Data Enhancement (API-based, không cần đa khung)
        - Market Regime Detection (tổng hợp cuối cùng)
        """
        
        # ==== Chart Pattern Recognition ====
        # Nhận dạng các mô hình giá: Double Top/Bottom, Head & Shoulders, Wedge, Triangle, Flag
        # Khó scale đa khung vì logic phức tạp
        dataframe = ChartPatterns.add_all_patterns(dataframe)
        
        # ==== Wave Indicators (Elliott Wave Lite) ====
        # Fibonacci Retracement/Extensions, Awesome Oscillator, Wave Structure
        # Objective features based on EW principles (no subjective wave counting)
        dataframe = WaveIndicators.add_all_features(dataframe)
        
        # ==== SMC Indicators ====
        # Sonic R, EMA 369/630, Moon Phases - đặc thù SMC strategy
        dataframe = SMCIndicators.add_all_indicators(dataframe)
        
        # ==== Data Enhancement (Phase 2) ====
        # Fear & Greed Index, Volume Imbalance, Funding Proxy
        # API-based features, không cần đa khung
        dataframe = DataEnhancement.add_all_features(dataframe, period=period)

        # ==== Legacy indicators (cho Market Regime) ====
        # Using talib (uppercase function names)
        dataframe['mfi'] = ta.MFI(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        
        # Bollinger Bands (cần cho market regime detection)
        dataframe['bb_upperband'], dataframe['bb_middleband'], dataframe['bb_lowerband'] = ta.BBANDS(
            dataframe['close'], timeperiod=20, nbdevup=2.0, nbdevdn=2.0
        )
        
        dataframe["bb_width"] = (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        ) / dataframe["bb_middleband"]
        
        # ==== Market Regime Detection (cuối cùng) ====
        dataframe = self.detect_market_regime(dataframe)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        
        expand_basic: Features ở đây SẼ ĐƯỢC TỰ ĐỘNG NHÂN BẢN cho các timeframes khác!
        FreqAI sẽ tạo ra: %-log_return_1_5m, %-log_return_1_1h, %-log_return_1_4h, v.v.
        
        ĐÂY LÀ NƠI ĐẶT CORE FEATURES:
        - Log Returns (quan trọng nhất)
        - EMA Distance & Slopes
        - Momentum Oscillators (RSI, Williams %R, CCI)
        - Volume Features (OBV, CMF, MFI, VWAP)
        - Volatility (ATR%, BB Width)
        - Candle Patterns
        - Support/Resistance
        
        Kết quả: Bot sẽ học từ 5m + 1h + 4h (Multi-timeframe Analysis)
        """
        # ==== CORE FEATURE ENGINEERING ====
        # Tất cả features sẽ được expand cho 5m, 1h, 4h
        dataframe = FeatureEngineering.add_all_features(dataframe)
        
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This optional function will be called once with the dataframe of the base timeframe.
        This is the final chance to add features. The columns won't be modified.
        All features must be prepended with `%` to be recognized by FreqAI internals.
        """
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        Required function to set the targets for the model.
        All targets must be prepended with `&` to be recognized by the FreqAI internals.
        
        Using regression target (% price change) instead of classification
        to avoid "unseen labels" error when training data is imbalanced.
        """
        # Regression target: % price change in next 20 candles
        # Positive = price goes up, Negative = price goes down
        future_close = dataframe["close"].shift(-20)
        dataframe["&-price_change_pct"] = (future_close - dataframe["close"]) / dataframe["close"]
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        
        Entry conditions (using Regression model):
        1. Market Regime = TREND (strong directional movement)
        2. AI Prediction > 0.01 (predicts >1% price increase)
        3. Volume > 0 (market is active)
        4. [Phase 2] Not in Extreme Greed (avoid FOMO entries)
        5. [Phase 2] Volume Imbalance > 0 (more buyers than sellers)
        6. [Phase 2] Market not overheated (price premium z-score < 2)
        """
        # Debug: Print columns to see what FreqAI added
        logger.info(f"Columns available: {len(dataframe.columns)} columns")
        logger.info(f"Sample columns: {dataframe.columns[:20].tolist()}")
        
        if self.config['freqai']['enabled']:
            # Regression target column (predicts % price change)
            prediction_col = '&-price_change_pct'
            logger.info(f"Looking for prediction column: {prediction_col}")
            logger.info(f"Prediction column exists: {prediction_col in dataframe.columns}")
            
            if prediction_col in dataframe.columns:
                logger.info(f"Prediction values sample: {dataframe[prediction_col].head()}")
                
                # Base conditions (regression: predict > 1% price increase)
                base_conditions = (
                    (dataframe['market_regime'] == 'TREND') &  # Only trade in TREND
                    (dataframe[prediction_col] > 0.01) &  # Predicts >1% price increase
                    (dataframe['volume'] > 0)
                )
                
                # Phase 2 enhancement conditions (optional, with safe defaults)
                fg_condition = True  # Default to True if feature not available
                if '%-is_extreme_greed' in dataframe.columns:
                    fg_condition = dataframe['%-is_extreme_greed'] == 0  # Not extreme greed
                
                vi_condition = True  # Default to True
                if '%-volume_imbalance' in dataframe.columns:
                    vi_condition = dataframe['%-volume_imbalance'] > 0  # More buyers
                
                overheat_condition = True  # Default to True
                if '%-is_overheated' in dataframe.columns:
                    overheat_condition = dataframe['%-is_overheated'] == 0  # Not overheated
                
                # Combine all conditions
                dataframe.loc[
                    base_conditions & fg_condition & vi_condition & overheat_condition,
                    'enter_long'] = 1
            else:
                logger.warning(f"Prediction column {prediction_col} NOT FOUND - FreqAI not training!")
                pass
                # print(f"Warning: {prediction_col} not found in dataframe.")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        
        Exit conditions (using Regression model):
        1. AI Prediction < -0.01 (predicts >1% price decrease)
        2. Volume > 0 (market is active)
        3. [Phase 2] Extreme Fear detected (panic selling in market) - early exit
        4. [Phase 2] Market oversold (may bounce, but safer to exit)
        """
        if self.config['freqai']['enabled']:
            # Regression target column (predicts % price change)
            prediction_col = '&-price_change_pct'
            if prediction_col in dataframe.columns:
                # Base exit condition (predict > 1% price decrease)
                base_exit = (
                    (dataframe[prediction_col] < -0.01) &  # Predicts >1% price decrease
                    (dataframe['volume'] > 0)
                )
                
                # Phase 2 enhancement: Early exit on extreme fear
                extreme_fear_exit = False  # Default to False
                if '%-is_extreme_fear' in dataframe.columns:
                    extreme_fear_exit = dataframe['%-is_extreme_fear'] == 1
                
                # Phase 2 enhancement: Exit when market is oversold (potential bounce but risky)
                oversold_exit = False  # Default to False
                if '%-is_oversold' in dataframe.columns:
                    oversold_exit = (
                        (dataframe['%-is_oversold'] == 1) & 
                        (dataframe[prediction_col] < 0.5)  # Only if AI also not confident
                    )
                
                # Combine exit conditions (any condition triggers exit)
                dataframe.loc[
                    base_exit | extreme_fear_exit | oversold_exit,
                    'exit_long'] = 1
        
        return dataframe
