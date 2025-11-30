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
import pandas_ta as ta
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
import talib.abstract as ta
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
    
    # Leverage calculation:
    # Target Risk per Trade = 20% of Stake (Margin)
    # Loss = Stake * Leverage * Stoploss_Price_Dist
    # 0.20 * Stake = Stake * Leverage * Stoploss_Price_Dist
    # Leverage = 0.20 / Stoploss_Price_Dist
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        """
        Customize leverage for each new trade.
        """
        risk_per_trade = 0.20  # 20% loss allowed on margin
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
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get ATR from last candle
        atr = last_candle.get('atr', 0)
        
        if atr > 0 and current_rate > 0:
            # Stoploss = -2 * (ATR / current_rate)
            # Example: ATR = 2000, Price = 40000 → SL = -2 * (2000/40000) = -10%
            dynamic_sl = -2.0 * (atr / current_rate)
            
            # Cap between -15% (max loss) and -2% (min protection)
            return max(dynamic_sl, -0.15, min(dynamic_sl, -0.02))
        
        # Fallback to static stoploss if ATR not available
        return self.stoploss
    
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
        # Ensure ADX is calculated
        if 'adx' not in dataframe.columns:
            adx_result = ta.adx(dataframe['high'], dataframe['low'], dataframe['close'])
            if isinstance(adx_result, DataFrame):
                dataframe['adx'] = adx_result['ADX_14'] if 'ADX_14' in adx_result.columns else adx_result.iloc[:, 0]
            else:
                dataframe['adx'] = adx_result
        
        # Ensure ATR is calculated
        if 'atr' not in dataframe.columns:
            dataframe['atr'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
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
        """
        # Market Regime Detection - must be called after BB indicators are available
        # Will be calculated in feature_engineering after all indicators are ready
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
        dataframe['mfi'] = ta.mfi(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'])
        dataframe['adx'] = ta.adx(dataframe['high'], dataframe['low'], dataframe['close'])['ADX_14']
        dataframe['rsi'] = ta.rsi(dataframe['close'])
        
        # Bollinger Bands (cần cho market regime detection)
        bollinger = ta.bbands(dataframe['close'], length=20, std=2)
        dataframe['bb_lowerband'] = bollinger['BBL_20_2.0']
        dataframe['bb_middleband'] = bollinger['BBM_20_2.0']
        dataframe['bb_upperband'] = bollinger['BBU_20_2.0']
        
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
        """
        # We are trying to predict the price 20 candles into the future
        dataframe["&s-up_or_down"] = np.where(
            dataframe["close"].shift(-20) > dataframe["close"], 1, 0
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        
        Entry conditions:
        1. Market Regime = TREND (strong directional movement)
        2. AI Prediction > 0.6 (high confidence)
        3. Volume > 0 (market is active)
        4. [Phase 2] Not in Extreme Greed (avoid FOMO entries)
        5. [Phase 2] Volume Imbalance > 0 (more buyers than sellers)
        6. [Phase 2] Market not overheated (price premium z-score < 2)
        """
        # Debug: Print columns to see what FreqAI added
        # print(f"Columns available: {dataframe.columns.tolist()}")
        
        if self.config['freqai']['enabled']:
            # Check if prediction column exists
            prediction_col = '&s-up_or_down_mean'
            if prediction_col in dataframe.columns:
                # Base conditions
                base_conditions = (
                    (dataframe['market_regime'] == 'TREND') &  # Only trade in TREND
                    (dataframe[prediction_col] > 0.6) &  # High confidence it goes up
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
                pass
                # print(f"Warning: {prediction_col} not found in dataframe.")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        
        Exit conditions:
        1. AI Prediction < 0.4 (high confidence it goes down)
        2. Volume > 0 (market is active)
        3. [Phase 2] Extreme Fear detected (panic selling in market) - early exit
        4. [Phase 2] Market oversold (may bounce, but safer to exit)
        """
        if self.config['freqai']['enabled']:
            prediction_col = '&s-up_or_down_mean'
            if prediction_col in dataframe.columns:
                # Base exit condition
                base_exit = (
                    (dataframe[prediction_col] < 0.4) &  # Confidence it goes down
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
