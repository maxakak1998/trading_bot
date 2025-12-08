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
    
    # =====================================================
    # HYPEROPT PARAMETERS - Tunable via `freqtrade hyperopt`
    # =====================================================
    
    # Entry/Exit prediction thresholds
    # Entry Signal Optimization
    buy_adx_threshold = IntParameter(20, 50, default=25, space="buy", optimize=True)
    buy_rsi_high = IntParameter(60, 90, default=70, space="buy", optimize=True)
    buy_rsi_low = IntParameter(20, 40, default=30, space="buy", optimize=True)
    
    # AI Prediction Confidence
    # OPTIMIZED: Increased range to force higher confidence entries
    buy_pred_threshold = DecimalParameter(0.02, 0.05, default=0.03, space="buy", optimize=True)
    sell_pred_threshold = DecimalParameter(-0.05, -0.02, default=-0.03, space="sell", optimize=True)
    
    # Sell Signal Optimization
    sell_rsi_threshold = IntParameter(20, 80, default=50, space="sell", optimize=True)
    
    # ATR multiplier for dynamic stoploss (used in custom_stoploss)
    atr_multiplier = DecimalParameter(1.5, 4.0, default=3.0, space="stoploss", optimize=True)
    
    # Confidence threshold for trade entries
    confidence_threshold = DecimalParameter(0.3, 0.7, default=0.5, space="buy", optimize=True)
    
    # =====================================================
    
    # Minimal ROI designed for the strategy.
    # OPTIMIZED: Higher targets for better R:R ratio
    minimal_roi = {
        "120": 0.02,   # 2% after 2 hours
        "60": 0.04,    # 4% after 1 hour  
        "30": 0.05,    # 5% after 30 min
        "0": 0.06      # 6% immediate target
    }

    # Risk Management - Fixed Stoploss, No Trailing
    # Fixed 20% stoploss to allow room for volatility (max risk)
    stoploss = -0.20
    
    # DISABLED: Trailing stop to avoid premature exits
    trailing_stop = False
    # trailing_stop_positive = 0.01 
    # trailing_stop_positive_offset = 0.015
    # trailing_only_offset_is_reached = True
    
    # Use ROI and exit signals instead of trailing
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    # Maximum risk per trade (% of margin)
    # 20% max loss per trade on margin
    # Example: With 4x leverage, actual price loss = 20%/4 = 5%
    max_risk_per_trade = 0.20  # 20% of stake (margin)
    
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
        
        if atr > 0 and trade.open_rate > 0:
            # Stoploss = atr_multiplier * (ATR / open_rate)
            # HYPEROPT: atr_multiplier is tunable (default 3.0)
            # FIX: Using trade.open_rate instead of current_rate to avoid trailing effect
            # Example: ATR = 2000, Price = 40000, mult = 3 → SL = -3 * (2000/40000) = -15%
            # Using 3x ATR gives more room for price movement before stop
            dynamic_sl = -self.atr_multiplier.value * (atr / trade.open_rate)
            
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
    # TEMPORARILY DISABLED SHORT - Testing long-only in bull market
    # Market +63.68%, shorts caused -4.73% loss
    can_short = True

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
        Chỉ dùng cho các features cục bộ của base timeframe (5m).
        
        ĐẶT Ở ĐÂY (Chỉ 5m):
        - Chart Patterns (Double Top/Bottom, H&S, Wedge, Triangle, Flag)
          → Mô hình nến mang tính chất cục bộ, nhân bản 4 TF tạo dữ liệu rác
        - Data Enhancement (Fear & Greed, API-based)
          → Dữ liệu từ API, không cần đa khung
        - Legacy indicators for Market Regime
        
        KHÔNG ĐẶT Ở ĐÂY (Đã move sang expand_basic):
        - SMC Indicators → Order Block 4h có giá trị gấp 10 lần 5m
        - Wave Indicators → Fibonacci levels cần nhìn từ HTF
        """
        
        # ==== Chart Pattern Recognition (5m only) ====
        # Nhận dạng các mô hình giá: Double Top/Bottom, Head & Shoulders, Wedge, Triangle, Flag
        # Mang tính chất cục bộ - không cần expand cho multi-TF
        # Can be disabled via feature_flags.chart_patterns
        if self.config.get('freqai', {}).get('feature_flags', {}).get('chart_patterns', True):
            dataframe = ChartPatterns.add_all_patterns(dataframe)
        
        # ==== Data Enhancement (5m only) ====
        # Fear & Greed Index, Volume Imbalance, Funding Proxy
        # API-based features, không cần đa khung
        # Can be disabled via feature_flags.data_enhancement
        if self.config.get('freqai', {}).get('feature_flags', {}).get('data_enhancement', True):
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
        
        ĐÂY LÀ NƠI ĐẶT CORE FEATURES + SMC/WAVE:
        
        1. Core Features (Log Returns, EMA, Momentum, Volume, Volatility)
           → Nền tảng cho mọi phân tích, cần nhìn ở tất cả TF
           
        2. SMC Indicators (Order Blocks, FVG, Structure, Liquidity)
           → Order Block ở 4H có giá trị GẤP 10 LẦN ở 5m
           → Structure ở HTF quyết định trend chính
           
        3. Wave Indicators (Fibonacci Retracement/Extension, Awesome Oscillator)
           → Fibo levels từ swing 4H là key levels cho toàn bộ price action
           → AO divergence ở 1H xác nhận reversal mạnh hơn
        
        Kết quả: Bot sẽ học từ 5m + 15m + 1h + 4h (True Multi-timeframe SMC Analysis)
        
        Ví dụ AI sẽ học:
        "Nếu giá chạm vùng Fibo 0.618 của khung 4H (từ expand_basic)
        VÀ xuất hiện mẫu nến đảo chiều ở khung 5m (từ expand_all)
        → Vào lệnh Mua"
        """
        # ==== CORE FEATURE ENGINEERING ====
        # Tất cả features sẽ được expand cho 5m, 15m, 1h, 4h
        # Pass config to enable feature_flags checks (e.g., vsa_indicators)
        dataframe = FeatureEngineering.add_all_features(dataframe, config=self.config)
        
        # ==== SMC INDICATORS (Multi-TF) ====
        # Order Blocks, FVG, Structure Direction, Liquidity Zones
        # Order Block ở 4H có giá trị gấp 10 lần ở 5m
        # Can be disabled via feature_flags.smc_indicators
        if self.config.get('freqai', {}).get('feature_flags', {}).get('smc_indicators', True):
            dataframe = SMCIndicators.add_all_indicators(dataframe)
        
        # ==== WAVE INDICATORS (Multi-TF) ====
        # Fibonacci Retracement/Extension, Awesome Oscillator, Wave Structure
        # Fibo levels từ swing 4H là key levels cho toàn bộ price action
        # Can be disabled via feature_flags.wave_indicators
        if self.config.get('freqai', {}).get('feature_flags', {}).get('wave_indicators', True):
            dataframe = WaveIndicators.add_all_features(dataframe)
        
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
        
        Two labeling methods (MUTUALLY EXCLUSIVE):
        1. regression_labels: % price change in next 20 candles
        2. trend_scanning: t-statistics based trend detection (statistically significant trends)
        """
        # Get flags
        flags = self.config.get('freqai', {}).get('feature_flags', {})
        use_trend_scanning = flags.get('trend_scanning', False)
        use_regression = flags.get('regression_labels', True)
        
        # Validate: they are mutually exclusive
        if use_trend_scanning and use_regression:
            raise ValueError(
                "CONFLICT: 'trend_scanning' và 'regression_labels' không thể cùng True! "
                "Hãy chọn 1 trong 2 trong config.json → freqai.feature_flags"
            )
        
        if not use_trend_scanning and not use_regression:
            raise ValueError(
                "ERROR: Phải enable ít nhất 1 trong 'trend_scanning' hoặc 'regression_labels'! "
                "Không có labeling method nào được chọn."
            )
        
        if use_trend_scanning:
            # Trend Scanning: Use rolling linear regression with t-statistics
            # to detect statistically significant trends
            logger.info("Using Trend Scanning labeling method")
            dataframe = self._trend_scanning_labels(dataframe, window=20, t_threshold=2.0)
        else:
            # Regression: Simple % price change prediction
            logger.info("Using Regression labeling method")
            dataframe = self._regression_labels(dataframe, horizon=20)
        
        return dataframe
    
    def _regression_labels(self, dataframe: DataFrame, horizon: int = 20) -> DataFrame:
        """Simple regression target: % price change in next N candles."""
        future_close = dataframe["close"].shift(-horizon)
        dataframe["&-price_change_pct"] = (future_close - dataframe["close"]) / dataframe["close"]
        return dataframe
    
    def _trend_scanning_labels(self, dataframe: DataFrame, window: int = 20, t_threshold: float = 2.0) -> DataFrame:
        """
        Trend Scanning labeling using t-statistics.
        
        Method:
        1. For each point, look forward `window` candles
        2. Fit linear regression to future prices
        3. Calculate t-statistic of slope
        4. If |t| > threshold, trend is statistically significant
        
        Returns:
        - &-price_change_pct: Expected % change (slope * window)
        - Also creates internal &-trend_direction for classification if needed
        """
        import numpy as np
        from scipy import stats
        
        close_prices = dataframe['close'].values
        n = len(close_prices)
        
        # Initialize arrays
        trend_slopes = np.zeros(n)
        trend_t_stats = np.zeros(n)
        
        x = np.arange(window)
        
        for i in range(n - window):
            y = close_prices[i:i + window]
            
            # Linear regression: y = slope * x + intercept
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            
            # Calculate t-statistic for slope
            if std_err > 0:
                t_stat = slope / std_err
            else:
                t_stat = 0
            
            # Expected % price change = slope * window / current_price
            current_price = close_prices[i]
            if current_price > 0:
                expected_pct_change = (slope * window) / current_price
            else:
                expected_pct_change = 0
            
            # Apply t-threshold filter: only significant trends
            if abs(t_stat) >= t_threshold:
                trend_slopes[i] = expected_pct_change
            else:
                trend_slopes[i] = 0  # Not significant = no clear trend
            
            trend_t_stats[i] = t_stat
        
        # Assign to dataframe
        dataframe["&-price_change_pct"] = trend_slopes
        dataframe["&-trend_t_stat"] = trend_t_stats  # Optional: for analysis
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        
        UPGRADED Entry conditions with Confluence system:
        
        LONG CONDITIONS:
        1. AI Prediction > threshold (FreqAI output)
        2. Market Regime = TREND (KER > 0.5 hoặc ADX > 25)
        3. Trend Confluence > 0.5 (EMA alignment + ADX strong)
        4. Momentum Confluence > 0.4 (RSI + MFI + CMF agree)
        5. Money Pressure > 0 (buying pressure)
        6. Pattern Net Score >= 0 (no bearish patterns)
        7. Not in Extreme Greed (avoid FOMO)
        8. Structure Direction > 0 (Higher Highs)
        
        SHORT CONDITIONS:
        1. AI Prediction < -threshold 
        2. Market Regime = TREND
        3. Trend Confluence < 0.5 (bearish alignment)
        4. Momentum Confluence < 0.6 (bearish momentum)
        5. Money Pressure < 0 (selling pressure)
        6. Pattern Net Score <= 0 (no bullish patterns)
        7. RSI > 75 (overbought)
        8. Structure Direction < 0 (Lower Lows)
        """
        # Debug logging
        logger.info(f"Columns available: {len(dataframe.columns)} columns")
        
        if self.config['freqai']['enabled']:
            prediction_col = '&-price_change_pct'
            
            if prediction_col in dataframe.columns:
                logger.info(f"Prediction values sample: {dataframe[prediction_col].head()}")
                
                # =====================================================
                # LONG ENTRY CONDITIONS (Upgraded with Confluence)
                # =====================================================
                
                # Base: AI prediction positive
                long_prediction = dataframe[prediction_col] > self.buy_pred_threshold.value
                
                # Get flags once
                flags = self.config.get('freqai', {}).get('feature_flags', {})
                use_trend_filter = flags.get('trend_filter', True)
                use_regime_filter = flags.get('regime_filter', True)
                
                # NOTE: For LONG entries in uptrend, we DON'T restrict with EMA 200
                # because in bull market we WANT long trades
                # EMA filter is used ONLY for SHORT to block counter-trend shorts
                long_ema_filter = True  # Always allow long entries
                
                # Market regime: Use KER or ADX
                long_regime = True
                if '%-ker_10' in dataframe.columns:
                    long_regime = dataframe['%-ker_10'] > 0.4  # Trending market
                elif 'adx' in dataframe.columns:
                    long_regime = dataframe['adx'] > self.buy_adx_threshold.value
                
                # Trend confluence (new)
                long_trend_confluence = True
                if '%-trend_confluence' in dataframe.columns:
                    long_trend_confluence = dataframe['%-trend_confluence'] > 0.5
                
                # Momentum confluence (new)
                long_momentum = True
                if '%-momentum_confluence' in dataframe.columns:
                    long_momentum = dataframe['%-momentum_confluence'] > 0.4
                
                # Money pressure (new)
                long_pressure = True
                if '%-money_pressure' in dataframe.columns:
                    long_pressure = dataframe['%-money_pressure'] > 0
                
                # REMOVED: Pattern check - too many false positives
                # REMOVED: Fear/Greed - external API data unreliable
                
                # SMC Structure (new) - Higher Highs
                long_structure = True
                if '%-structure_direction' in dataframe.columns:
                    long_structure = dataframe['%-structure_direction'] > -0.2
                
                # Volume active
                long_volume = dataframe['volume'] > 0
                
                # =====================================================
                # NEW: HTF Order Block + LTF CHoCH Confluence
                # =====================================================
                use_htf_ob_confluence = flags.get('htf_ob_confluence', True)
                
                # HTF OB Filter: Entry at 4H Order Block zone or OB+Fib confluence
                long_htf_ob = True
                if use_htf_ob_confluence:
                    # Try 4H timeframe first (auto-generated by FreqAI expand_basic)
                    if '%-testing_bull_ob_4h' in dataframe.columns:
                        long_htf_ob = (
                            (dataframe['%-testing_bull_ob_4h'] > 0) |  # At 4H Bull OB
                            (dataframe.get('%-ob_fib_bull_confluence', 0) > 0)  # OR OB+Fib
                        )
                    elif '%-testing_bull_ob_1h' in dataframe.columns:
                        # Fallback to 1H
                        long_htf_ob = (
                            (dataframe['%-testing_bull_ob_1h'] > 0) |
                            (dataframe.get('%-ob_fib_bull_confluence', 0) > 0)
                        )
                    elif '%-ob_fib_bull_confluence' in dataframe.columns:
                        # No HTF available, use OB+Fib confluence from base TF
                        long_htf_ob = dataframe['%-ob_fib_bull_confluence'] > 0
                
                # REMOVED: CHoCH filter - keep HTF OB only for simpler confluence
                
                # Combine LONG conditions (simplified: 7 filters instead of 12)
                dataframe.loc[
                    long_prediction & long_ema_filter & long_htf_ob &
                    long_regime & long_trend_confluence & 
                    long_momentum & long_pressure & 
                    long_structure & long_volume,
                    'enter_long'] = 1
                
                # =====================================================
                # SHORT ENTRY CONDITIONS (Upgraded with Confluence)
                # =====================================================
                
                # Base: AI prediction negative
                short_prediction = dataframe[prediction_col] < -self.buy_pred_threshold.value
                
                # EMA 200 TREND FILTER (KEY FIX for counter-trend protection)
                # Only allow SHORT when price < EMA 200 (downtrend)
                short_ema_filter = True
                if use_trend_filter:
                    if '%-dist_to_ema_200' in dataframe.columns:
                        # dist_to_ema_200 < 0 means price < EMA 200
                        short_ema_filter = dataframe['%-dist_to_ema_200'] < 0
                    else:
                        # Fallback: calculate EMA 200 on the fly
                        ema_200 = ta.EMA(dataframe['close'], timeperiod=200)
                        short_ema_filter = dataframe['close'] < ema_200
                
                # REGIME FILTER: Only SHORT in bearish/sideways regime
                short_regime = True
                if use_regime_filter and '%-market_regime' in dataframe.columns:
                    # Only short when regime is BEARISH (<0.4)
                    # Block shorts in bullish or sideways regime (>0.4)
                    short_regime = dataframe['%-market_regime'] < 0.4
                elif '%-ker_10' in dataframe.columns:
                    # Fallback: use KER for trend strength
                    short_regime = dataframe['%-ker_10'] > 0.4
                elif 'adx' in dataframe.columns:
                    short_regime = dataframe['adx'] > self.buy_adx_threshold.value
                
                # Trend confluence (bearish)
                short_trend = True
                if '%-trend_confluence' in dataframe.columns:
                    short_trend = dataframe['%-trend_confluence'] < 0.5
                
                # Momentum confluence (bearish)
                short_momentum = True
                if '%-momentum_confluence' in dataframe.columns:
                    short_momentum = dataframe['%-momentum_confluence'] < 0.6
                
                # Money pressure (selling)
                short_pressure = True
                if '%-money_pressure' in dataframe.columns:
                    short_pressure = dataframe['%-money_pressure'] < 0
                
                # REMOVED: Pattern check - too many false positives
                
                # SMC Structure - Lower Lows
                short_structure = True
                if '%-structure_direction' in dataframe.columns:
                    short_structure = dataframe['%-structure_direction'] < 0.2
                
                # RSI overbought
                short_rsi = True
                if 'rsi' in dataframe.columns:
                    short_rsi = dataframe['rsi'] > self.sell_rsi_threshold.value
                
                # Volume active
                short_volume = dataframe['volume'] > 0
                
                # =====================================================
                # NEW: HTF Order Block + LTF CHoCH Confluence (SHORT)
                # =====================================================
                
                # HTF OB Filter: Entry at 4H Supply Zone (Bearish OB)
                short_htf_ob = True
                if use_htf_ob_confluence:
                    # Try 4H timeframe first
                    if '%-testing_bear_ob_4h' in dataframe.columns:
                        short_htf_ob = (
                            (dataframe['%-testing_bear_ob_4h'] > 0) |  # At 4H Bear OB
                            (dataframe.get('%-ob_fib_bear_confluence', 0) > 0)  # OR OB+Fib
                        )
                    elif '%-testing_bear_ob_1h' in dataframe.columns:
                        # Fallback to 1H
                        short_htf_ob = (
                            (dataframe['%-testing_bear_ob_1h'] > 0) |
                            (dataframe.get('%-ob_fib_bear_confluence', 0) > 0)
                        )
                    elif '%-ob_fib_bear_confluence' in dataframe.columns:
                        # No HTF available, use OB+Fib confluence from base TF
                        short_htf_ob = dataframe['%-ob_fib_bear_confluence'] > 0
                
                # REMOVED: CHoCH filter - keep HTF OB only
                
                # Combine SHORT conditions (simplified: 9 filters instead of 12)
                dataframe.loc[
                    short_prediction & short_ema_filter & short_htf_ob &
                    short_regime & short_trend &
                    short_momentum & short_pressure &
                    short_structure & short_rsi & short_volume,
                    'enter_short'] = 1
                    
            else:
                logger.warning(f"Prediction column {prediction_col} NOT FOUND - FreqAI not training!")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signal using 5-Layer Confluence System:
        
        LONG EXIT when ANY of these conditions:
        1. AI Prediction < sell_pred_threshold (bearish forecast)
        2. Trend confluence < 0.5 (trend weakening)
        3. Momentum confluence < 0.4 (momentum fading)
        4. Pattern net score becomes negative (bearish patterns forming)
        5. RSI overbought (> sell_rsi_threshold)
        6. SMC: Price at Order Block resistance / FVG filled
        7. Extreme Fear (panic in market)
        
        SHORT EXIT when ANY of these conditions:
        1. AI Prediction > buy_pred_threshold (bullish forecast)
        2. Trend confluence > 0.5 (trend reversing up)
        3. Momentum confluence > 0.6 (momentum turning bullish)
        4. Pattern net score becomes positive (bullish patterns forming)
        5. RSI oversold (< buy_rsi_low)
        6. SMC: Price at Order Block support / Bullish FVG
        """
        if self.config['freqai']['enabled']:
            # Regression target column (predicts % price change)
            prediction_col = '&-price_change_pct'
            if prediction_col in dataframe.columns:
                
                # =====================================================
                # LONG EXIT CONDITIONS
                # =====================================================
                
                # AI prediction bearish
                exit_prediction = (
                    (dataframe[prediction_col] < self.sell_pred_threshold.value) &
                    (dataframe['volume'] > 0)
                )
                
                # Trend confluence weakening
                exit_trend = False
                if '%-trend_confluence' in dataframe.columns:
                    exit_trend = dataframe['%-trend_confluence'] < 0.4
                
                # Momentum fading
                exit_momentum = False
                if '%-momentum_confluence' in dataframe.columns:
                    exit_momentum = dataframe['%-momentum_confluence'] < 0.3
                
                # Money pressure turning negative (selling)
                exit_pressure = False
                if '%-money_pressure' in dataframe.columns:
                    exit_pressure = dataframe['%-money_pressure'] < -0.3
                
                # Bearish pattern forming
                exit_pattern = False
                if '%-pattern_net_score' in dataframe.columns:
                    exit_pattern = dataframe['%-pattern_net_score'] < -1
                
                # RSI overbought
                exit_rsi = False
                if 'rsi' in dataframe.columns:
                    exit_rsi = dataframe['rsi'] > self.sell_rsi_threshold.value
                
                # SMC: At resistance (Order Block bear) or Bearish FVG
                exit_smc = False
                if '%-fvg_bear' in dataframe.columns:
                    exit_smc = dataframe['%-fvg_bear'] == 1
                elif '%-order_block_bear' in dataframe.columns:
                    exit_smc = dataframe['%-order_block_bear'] == 1
                
                # Extreme Fear (market panic - exit to safety)
                exit_fear = False
                if '%-is_extreme_fear' in dataframe.columns:
                    exit_fear = dataframe['%-is_extreme_fear'] == 1
                
                # Combine LONG exit conditions (ANY triggers exit)
                dataframe.loc[
                    exit_prediction | exit_trend | exit_momentum | 
                    exit_pressure | exit_pattern | exit_rsi | 
                    exit_smc | exit_fear,
                    'exit_long'] = 1
                
                # =====================================================
                # SHORT EXIT CONDITIONS (mirror of Long exit)
                # =====================================================
                
                # AI prediction bullish
                short_exit_prediction = (
                    (dataframe[prediction_col] > self.buy_pred_threshold.value) &
                    (dataframe['volume'] > 0)
                )
                
                # Trend confluence turning bullish
                short_exit_trend = False
                if '%-trend_confluence' in dataframe.columns:
                    short_exit_trend = dataframe['%-trend_confluence'] > 0.6
                
                # Momentum turning bullish
                short_exit_momentum = False
                if '%-momentum_confluence' in dataframe.columns:
                    short_exit_momentum = dataframe['%-momentum_confluence'] > 0.7
                
                # Money pressure positive (buying coming in)
                short_exit_pressure = False
                if '%-money_pressure' in dataframe.columns:
                    short_exit_pressure = dataframe['%-money_pressure'] > 0.3
                
                # Bullish pattern forming
                short_exit_pattern = False
                if '%-pattern_net_score' in dataframe.columns:
                    short_exit_pattern = dataframe['%-pattern_net_score'] > 1
                
                # RSI oversold (potential bounce)
                short_exit_rsi = False
                if 'rsi' in dataframe.columns:
                    short_exit_rsi = dataframe['rsi'] < self.buy_rsi_low.value
                
                # SMC: At support (Order Block bull) or Bullish FVG
                short_exit_smc = False
                if '%-fvg_bull' in dataframe.columns:
                    short_exit_smc = dataframe['%-fvg_bull'] == 1
                elif '%-order_block_bull' in dataframe.columns:
                    short_exit_smc = dataframe['%-order_block_bull'] == 1
                
                # Extreme Fear (market bottoming, shorts may get squeezed)
                short_exit_fear = False
                if '%-is_extreme_fear' in dataframe.columns:
                    short_exit_fear = dataframe['%-is_extreme_fear'] == 1
                
                # Combine SHORT exit conditions (ANY triggers exit)
                dataframe.loc[
                    short_exit_prediction | short_exit_trend | short_exit_momentum |
                    short_exit_pressure | short_exit_pattern | short_exit_rsi |
                    short_exit_smc | short_exit_fear,
                    'exit_short'] = 1
        
        return dataframe
