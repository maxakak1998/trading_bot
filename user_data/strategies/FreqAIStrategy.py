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
    # RESTORED: Standard range to ensure sufficient trade frequency
    buy_pred_threshold = DecimalParameter(0.005, 0.03, default=0.01, space="buy", optimize=True)
    sell_pred_threshold = DecimalParameter(-0.03, -0.005, default=-0.01, space="sell", optimize=True)
    
    # Entry Score Threshold for weighted scoring system
    # Higher = stricter (fewer but higher quality trades)
    # Lower = looser (more trades but lower quality)
    # Note: Currently only AI (30%) + ADX (15%) = 45% max, so threshold must be <= 0.45
    entry_score_threshold = DecimalParameter(0.3, 0.6, default=0.45, space="buy", optimize=True)
    
    # Sell Signal Optimization
    sell_rsi_threshold = IntParameter(20, 80, default=50, space="sell", optimize=True)
    
    # ATR multiplier for dynamic stoploss (used in custom_stoploss)
    # MOVED to 'buy' space (safe space) to avoid KeyError
    atr_multiplier = DecimalParameter(1.5, 4.0, default=3.0, space="buy", optimize=True)
    
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

    # Risk Management - Custom Optimized Trailing
    stoploss = -0.05
    
    # DISABLED: Standard trailing stop (replaced by custom logic)
    trailing_stop = False
    
    # Custom Trailing Parameters (Optimizable) - MOVED TO BUY SPACE
    # p_trail_start: Profit required to activate trailing
    p_trail_start = DecimalParameter(0.005, 0.05, default=0.01, space="buy", optimize=True)
    # p_trail_offset: Distance from CURRENT PRICE (e.g. 0.01 = 1% below current)
    p_trail_offset = DecimalParameter(0.002, 0.03, default=0.01, space="buy", optimize=True)
    
    # Use ROI and exit signals instead of trailing
    use_exit_signal = True
    use_custom_stoploss = True  # Enable custom_stoploss function
    
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
        
        # 1. Custom Trailing Stop Logic
        # If profit > start => Lock in profit with trailing offset
        if current_profit >= self.p_trail_start.value:
            # Return offset relative to CURRENT PRICE
            # Returning -0.01 means SL is 1% below current price
            return -self.p_trail_offset.value
            
        # 2. Initial Stoploss (ATR or Fixed)
        # If not yet profitable enough to trail, use ATR Logic
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get ATR from last candle
        atr = last_candle.get('atr', 0)
        
        # Get current leverage of the trade (default 1x if not available)
        current_leverage = getattr(trade, 'leverage', 1.0) or 1.0
        
        # SAFETY LIMIT: Max risk = max_risk_per_trade% of margin
        max_risk_on_margin = self.max_risk_per_trade
        safe_sl_limit = -(max_risk_on_margin / current_leverage)
        
        if atr > 0 and trade.open_rate > 0:
            # Dynamic SL based on ATR
            dynamic_sl = -self.atr_multiplier.value * (atr / trade.open_rate)
            
            # Apply limits
            final_sl = max(dynamic_sl, safe_sl_limit, -0.15)
            final_sl = min(final_sl, -0.01)
            
            return final_sl
        
        # Fallback
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
                # LONG ENTRY - WEIGHTED SCORING SYSTEM
                # =====================================================
                # Instead of AND logic (all must be True), use weighted scores
                # This allows partial confluence and better trade frequency control
                
                # Get flags once
                flags = self.config.get('freqai', {}).get('feature_flags', {})
                use_htf_ob_confluence = flags.get('htf_ob_confluence', True)
                
                # 1. AI Prediction (30% weight) - REQUIRED BASE
                ai_positive = (dataframe[prediction_col] > self.buy_pred_threshold.value).astype(float)
                
                # 2. HTF Order Block (25% weight)
                htf_ob_signal = np.zeros(len(dataframe))
                if use_htf_ob_confluence:
                    if '%-testing_bull_ob_4h' in dataframe.columns:
                        htf_ob_signal = (dataframe['%-testing_bull_ob_4h'] > 0).astype(float).values
                    elif '%-testing_bull_ob_1h' in dataframe.columns:
                        htf_ob_signal = (dataframe['%-testing_bull_ob_1h'] > 0).astype(float).values
                    if '%-ob_fib_bull_confluence' in dataframe.columns:
                        htf_ob_signal = np.maximum(htf_ob_signal, (dataframe['%-ob_fib_bull_confluence'] > 0).astype(float).values)
                
                # 3. ADX/Regime (15% weight) - Trending market
                adx_signal = np.zeros(len(dataframe))
                if '%-ker_10' in dataframe.columns:
                    adx_signal = (dataframe['%-ker_10'] > 0.4).astype(float).values
                elif 'adx' in dataframe.columns:
                    adx_signal = (dataframe['adx'] > self.buy_adx_threshold.value).astype(float).values
                
                # 4. Momentum Confluence (15% weight)
                momentum_signal = np.zeros(len(dataframe))
                if '%-momentum_confluence' in dataframe.columns:
                    momentum_signal = (dataframe['%-momentum_confluence'] > 0.4).astype(float).values
                
                # 5. Money Pressure (15% weight)
                pressure_signal = np.zeros(len(dataframe))
                if '%-money_pressure' in dataframe.columns:
                    pressure_signal = (dataframe['%-money_pressure'] > 0).astype(float).values
                
                # Calculate total LONG score (sum of weighted signals)
                long_score = (
                    ai_positive.values * 0.30 +      # AI: 30%
                    htf_ob_signal * 0.25 +           # HTF OB: 25%
                    adx_signal * 0.15 +              # ADX: 15%
                    momentum_signal * 0.15 +         # Momentum: 15%
                    pressure_signal * 0.15           # Pressure: 15%
                )
                
                # Volume filter (must have volume - not scored, just required)
                has_volume = dataframe['volume'] > 0
                
                # LONG ENTRY: Score >= threshold AND has volume AND AI is positive (base requirement)
                dataframe.loc[
                    (ai_positive > 0) & has_volume & (long_score >= self.entry_score_threshold.value),
                    'enter_long'] = 1
                
                # Log score distribution for debugging
                if len(dataframe) > 0:
                    logger.info(f"LONG Score stats: mean={long_score.mean():.3f}, max={long_score.max():.3f}, entries={((long_score >= self.entry_score_threshold.value) & (ai_positive > 0)).sum()}")
                
                # =====================================================
                # SHORT ENTRY - WEIGHTED SCORING SYSTEM
                # =====================================================
                
                use_trend_filter = flags.get('trend_filter', True)
                
                # 1. AI Prediction (30% weight) - REQUIRED BASE
                ai_negative = (dataframe[prediction_col] < -self.buy_pred_threshold.value).astype(float)
                
                # 2. HTF Order Block - Bear (25% weight)
                htf_ob_bear = np.zeros(len(dataframe))
                if use_htf_ob_confluence:
                    if '%-testing_bear_ob_4h' in dataframe.columns:
                        htf_ob_bear = (dataframe['%-testing_bear_ob_4h'] > 0).astype(float).values
                    elif '%-testing_bear_ob_1h' in dataframe.columns:
                        htf_ob_bear = (dataframe['%-testing_bear_ob_1h'] > 0).astype(float).values
                    if '%-ob_fib_bear_confluence' in dataframe.columns:
                        htf_ob_bear = np.maximum(htf_ob_bear, (dataframe['%-ob_fib_bear_confluence'] > 0).astype(float).values)
                
                # 3. ADX/Regime (15% weight)
                adx_short = np.zeros(len(dataframe))
                if '%-ker_10' in dataframe.columns:
                    adx_short = (dataframe['%-ker_10'] > 0.4).astype(float).values
                elif 'adx' in dataframe.columns:
                    adx_short = (dataframe['adx'] > self.buy_adx_threshold.value).astype(float).values
                
                # 4. Momentum Confluence - Bearish (15% weight)
                momentum_short = np.zeros(len(dataframe))
                if '%-momentum_confluence' in dataframe.columns:
                    momentum_short = (dataframe['%-momentum_confluence'] < 0.6).astype(float).values
                
                # 5. Money Pressure - Selling (15% weight)
                pressure_short = np.zeros(len(dataframe))
                if '%-money_pressure' in dataframe.columns:
                    pressure_short = (dataframe['%-money_pressure'] < 0).astype(float).values
                
                # Calculate total SHORT score
                short_score = (
                    ai_negative.values * 0.30 +
                    htf_ob_bear * 0.25 +
                    adx_short * 0.15 +
                    momentum_short * 0.15 +
                    pressure_short * 0.15
                )
                
                # EMA 200 TREND FILTER (REQUIRED for shorts - not scored)
                # Only allow SHORT when price < EMA 200 (downtrend)
                ema_filter = pd.Series(True, index=dataframe.index)
                if use_trend_filter:
                    if '%-dist_to_ema_200' in dataframe.columns:
                        ema_filter = dataframe['%-dist_to_ema_200'] < 0
                    else:
                        ema_200 = ta.EMA(dataframe['close'], timeperiod=200)
                        ema_filter = dataframe['close'] < ema_200
                
                # SHORT ENTRY: Score >= threshold AND EMA filter AND volume AND AI negative
                dataframe.loc[
                    (ai_negative > 0) & has_volume & ema_filter & (short_score >= self.entry_score_threshold.value),
                    'enter_short'] = 1
                
                # Log score distribution
                if len(dataframe) > 0:
                    logger.info(f"SHORT Score stats: mean={short_score.mean():.3f}, max={short_score.max():.3f}, entries={((short_score >= self.entry_score_threshold.value) & (ai_negative > 0) & ema_filter).sum()}")
                    
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
