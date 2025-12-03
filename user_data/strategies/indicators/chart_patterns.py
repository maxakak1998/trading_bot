"""
Chart Patterns Recognition Module
=================================
Module nhận dạng các mô hình giá (Chart Patterns) phổ biến.

Patterns được triển khai:
1. Double Top/Bottom (Đỉnh/Đáy đôi)
2. Head and Shoulders (Vai đầu vai)
3. Wedge (Nêm tăng/giảm)
4. Triangle (Tam giác)
5. Flag/Pennant (Cờ)

QUAN TRỌNG:
- Các patterns được phát hiện dựa trên dữ liệu quá khứ
- Features output là binary (0/1) hoặc confidence score (0-1)
- Không có lookahead bias (chỉ dùng dữ liệu đến thời điểm hiện tại)

Author: AI Trading System
Date: 2025-11-30
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Tuple, Optional, List
import logging
from scipy.signal import argrelextrema

logger = logging.getLogger(__name__)


class ChartPatterns:
    """
    Class chứa các methods nhận dạng Chart Patterns.
    
    Tất cả patterns trả về features cho ML model.
    """
    
    # ============================================================
    # HELPER FUNCTIONS - Swing High/Low Detection
    # ============================================================
    
    @staticmethod
    def find_swing_points(dataframe: DataFrame, order: int = 5) -> DataFrame:
        """
        Tìm các điểm Swing High và Swing Low.
        
        Swing High: Điểm cao hơn 'order' nến trước và sau
        Swing Low: Điểm thấp hơn 'order' nến trước và sau
        
        Args:
            dataframe: OHLCV DataFrame
            order: Số nến để so sánh (default 5 = so với 5 nến mỗi bên)
            
        Returns:
            DataFrame với swing_high và swing_low columns
        """
        # Sử dụng scipy để tìm local extrema
        # Note: Shift để tránh lookahead bias (chỉ xác nhận khi có đủ dữ liệu sau)
        
        # Find local maxima (swing highs)
        highs = dataframe['high'].values
        swing_high_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        
        # Find local minima (swing lows)
        lows = dataframe['low'].values
        swing_low_idx = argrelextrema(lows, np.less_equal, order=order)[0]
        
        # Create columns
        dataframe['swing_high'] = 0.0
        dataframe['swing_low'] = 0.0
        
        # Mark swing points (shifted by 'order' to avoid lookahead)
        for idx in swing_high_idx:
            if idx + order < len(dataframe):
                dataframe.loc[dataframe.index[idx + order], 'swing_high'] = highs[idx]
        
        for idx in swing_low_idx:
            if idx + order < len(dataframe):
                dataframe.loc[dataframe.index[idx + order], 'swing_low'] = lows[idx]
        
        return dataframe
    
    @staticmethod
    def get_recent_swings(dataframe: DataFrame, lookback: int = 100) -> Tuple[List, List]:
        """
        Lấy danh sách các swing points gần đây.
        
        Returns:
            Tuple of (swing_highs, swing_lows) as list of (index, price) tuples
        """
        recent = dataframe.tail(lookback)
        
        swing_highs = []
        swing_lows = []
        
        for i, (idx, row) in enumerate(recent.iterrows()):
            if row['swing_high'] > 0:
                swing_highs.append((i, row['swing_high']))
            if row['swing_low'] > 0:
                swing_lows.append((i, row['swing_low']))
        
        return swing_highs, swing_lows
    
    # ============================================================
    # 1. DOUBLE TOP / DOUBLE BOTTOM
    # ============================================================
    
    @staticmethod
    def detect_double_top(dataframe: DataFrame, tolerance: float = 0.02) -> DataFrame:
        """
        Phát hiện mô hình Double Top (Đỉnh đôi).
        
        Đặc điểm:
        - 2 đỉnh gần bằng nhau (trong tolerance %)
        - Có một đáy ở giữa
        - Bearish signal (giá có thể giảm)
        
        Args:
            dataframe: OHLCV DataFrame với swing points
            tolerance: Phần trăm chênh lệch cho phép giữa 2 đỉnh
            
        Returns:
            DataFrame với double_top features
        """
        n = len(dataframe)
        dataframe['%-double_top'] = 0.0
        dataframe['%-double_top_neckline'] = 0.0
        
        # Cần ít nhất 50 nến để phát hiện pattern
        if n < 50:
            return dataframe
        
        # Duyệt qua các swing highs
        swing_highs, swing_lows = ChartPatterns.get_recent_swings(dataframe)
        
        if len(swing_highs) < 2 or len(swing_lows) < 1:
            return dataframe
        
        # Tìm 2 đỉnh gần nhất và 1 đáy ở giữa
        for i in range(1, len(swing_highs)):
            peak1_idx, peak1_price = swing_highs[i-1]
            peak2_idx, peak2_price = swing_highs[i]
            
            # 2 đỉnh phải gần bằng nhau
            price_diff = abs(peak1_price - peak2_price) / peak1_price
            if price_diff > tolerance:
                continue
            
            # Tìm đáy giữa 2 đỉnh
            middle_lows = [
                (idx, price) for idx, price in swing_lows
                if peak1_idx < idx < peak2_idx
            ]
            
            if not middle_lows:
                continue
            
            # Lấy đáy thấp nhất giữa 2 đỉnh (neckline)
            neckline_idx, neckline_price = min(middle_lows, key=lambda x: x[1])
            
            # Tính confidence (dựa trên độ sâu của pattern)
            pattern_depth = (peak1_price - neckline_price) / peak1_price
            confidence = min(1.0, pattern_depth * 10)  # Scale 10% depth = 100% confidence
            
            # Mark pattern tại vị trí peak2
            if peak2_idx < len(dataframe):
                actual_idx = len(dataframe) - 100 + peak2_idx  # Convert relative to absolute
                if 0 <= actual_idx < len(dataframe):
                    dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-double_top')] = confidence
                    dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-double_top_neckline')] = neckline_price / dataframe.iloc[actual_idx]['close']
        
        return dataframe
    
    @staticmethod
    def detect_double_bottom(dataframe: DataFrame, tolerance: float = 0.02) -> DataFrame:
        """
        Phát hiện mô hình Double Bottom (Đáy đôi).
        
        Đặc điểm:
        - 2 đáy gần bằng nhau (trong tolerance %)
        - Có một đỉnh ở giữa
        - Bullish signal (giá có thể tăng)
        """
        n = len(dataframe)
        dataframe['%-double_bottom'] = 0.0
        dataframe['%-double_bottom_neckline'] = 0.0
        
        if n < 50:
            return dataframe
        
        swing_highs, swing_lows = ChartPatterns.get_recent_swings(dataframe)
        
        if len(swing_lows) < 2 or len(swing_highs) < 1:
            return dataframe
        
        for i in range(1, len(swing_lows)):
            bottom1_idx, bottom1_price = swing_lows[i-1]
            bottom2_idx, bottom2_price = swing_lows[i]
            
            price_diff = abs(bottom1_price - bottom2_price) / bottom1_price
            if price_diff > tolerance:
                continue
            
            middle_highs = [
                (idx, price) for idx, price in swing_highs
                if bottom1_idx < idx < bottom2_idx
            ]
            
            if not middle_highs:
                continue
            
            neckline_idx, neckline_price = max(middle_highs, key=lambda x: x[1])
            
            pattern_depth = (neckline_price - bottom1_price) / bottom1_price
            confidence = min(1.0, pattern_depth * 10)
            
            if bottom2_idx < len(dataframe):
                actual_idx = len(dataframe) - 100 + bottom2_idx
                if 0 <= actual_idx < len(dataframe):
                    dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-double_bottom')] = confidence
                    dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-double_bottom_neckline')] = neckline_price / dataframe.iloc[actual_idx]['close']
        
        return dataframe
    
    # ============================================================
    # 2. HEAD AND SHOULDERS
    # ============================================================
    
    @staticmethod
    def detect_head_and_shoulders(dataframe: DataFrame, tolerance: float = 0.02) -> DataFrame:
        """
        Phát hiện mô hình Head and Shoulders (Vai Đầu Vai).
        
        Đặc điểm:
        - Left Shoulder (vai trái): Đỉnh đầu tiên
        - Head (đầu): Đỉnh cao nhất ở giữa
        - Right Shoulder (vai phải): Đỉnh tương đương vai trái
        - Neckline: Đường nối 2 đáy
        - Bearish signal khi break neckline
        """
        n = len(dataframe)
        dataframe['%-head_shoulders'] = 0.0
        dataframe['%-head_shoulders_inv'] = 0.0  # Inverse (bullish)
        
        if n < 100:
            return dataframe
        
        swing_highs, swing_lows = ChartPatterns.get_recent_swings(dataframe)
        
        if len(swing_highs) < 3 or len(swing_lows) < 2:
            return dataframe
        
        # Tìm pattern: LS - H - RS
        for i in range(2, len(swing_highs)):
            ls_idx, ls_price = swing_highs[i-2]  # Left Shoulder
            head_idx, head_price = swing_highs[i-1]  # Head
            rs_idx, rs_price = swing_highs[i]  # Right Shoulder
            
            # Head phải cao hơn cả 2 shoulders
            if not (head_price > ls_price and head_price > rs_price):
                continue
            
            # 2 shoulders phải gần bằng nhau
            shoulder_diff = abs(ls_price - rs_price) / ls_price
            if shoulder_diff > tolerance:
                continue
            
            # Tìm 2 đáy (neckline points)
            left_lows = [(idx, price) for idx, price in swing_lows if ls_idx < idx < head_idx]
            right_lows = [(idx, price) for idx, price in swing_lows if head_idx < idx < rs_idx]
            
            if not left_lows or not right_lows:
                continue
            
            left_neckline = min(left_lows, key=lambda x: x[1])
            right_neckline = min(right_lows, key=lambda x: x[1])
            
            # Neckline slope (có thể nghiêng)
            neckline_avg = (left_neckline[1] + right_neckline[1]) / 2
            
            # Tính confidence
            head_height = head_price - neckline_avg
            pattern_quality = head_height / head_price
            confidence = min(1.0, pattern_quality * 10)
            
            if rs_idx < len(dataframe):
                actual_idx = len(dataframe) - 100 + rs_idx
                if 0 <= actual_idx < len(dataframe):
                    dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-head_shoulders')] = confidence
        
        # Inverse Head and Shoulders (Bullish)
        if len(swing_lows) >= 3 and len(swing_highs) >= 2:
            for i in range(2, len(swing_lows)):
                ls_idx, ls_price = swing_lows[i-2]
                head_idx, head_price = swing_lows[i-1]
                rs_idx, rs_price = swing_lows[i]
                
                if not (head_price < ls_price and head_price < rs_price):
                    continue
                
                shoulder_diff = abs(ls_price - rs_price) / ls_price
                if shoulder_diff > tolerance:
                    continue
                
                left_highs = [(idx, price) for idx, price in swing_highs if ls_idx < idx < head_idx]
                right_highs = [(idx, price) for idx, price in swing_highs if head_idx < idx < rs_idx]
                
                if not left_highs or not right_highs:
                    continue
                
                neckline_avg = (max(left_highs, key=lambda x: x[1])[1] + 
                               max(right_highs, key=lambda x: x[1])[1]) / 2
                
                pattern_quality = (neckline_avg - head_price) / neckline_avg
                confidence = min(1.0, pattern_quality * 10)
                
                if rs_idx < len(dataframe):
                    actual_idx = len(dataframe) - 100 + rs_idx
                    if 0 <= actual_idx < len(dataframe):
                        dataframe.iloc[actual_idx, dataframe.columns.get_loc('%-head_shoulders_inv')] = confidence
        
        return dataframe
    
    # ============================================================
    # 3. WEDGE PATTERNS
    # ============================================================
    
    @staticmethod
    def detect_wedge(dataframe: DataFrame, lookback: int = 50) -> DataFrame:
        """
        Phát hiện mô hình Wedge (Nêm).
        
        Rising Wedge: Higher highs + Higher lows, nhưng converging → Bearish
        Falling Wedge: Lower highs + Lower lows, nhưng converging → Bullish
        
        Phương pháp: Dùng linear regression trên highs và lows
        """
        n = len(dataframe)
        dataframe['%-rising_wedge'] = 0.0
        dataframe['%-falling_wedge'] = 0.0
        
        if n < lookback + 10:
            return dataframe
        
        for i in range(lookback, n):
            window = dataframe.iloc[i-lookback:i]
            
            highs = window['high'].values
            lows = window['low'].values
            x = np.arange(lookback)
            
            # Linear regression cho highs và lows
            high_slope = np.polyfit(x, highs, 1)[0]
            low_slope = np.polyfit(x, lows, 1)[0]
            
            # Normalize slopes by price
            avg_price = window['close'].mean()
            high_slope_pct = high_slope / avg_price
            low_slope_pct = low_slope / avg_price
            
            # Rising Wedge: Cả high và low đều tăng, low tăng nhanh hơn (converging)
            if high_slope_pct > 0 and low_slope_pct > 0 and low_slope_pct > high_slope_pct:
                convergence = (low_slope_pct - high_slope_pct) / high_slope_pct if high_slope_pct != 0 else 0
                confidence = min(1.0, abs(convergence))
                dataframe.iloc[i, dataframe.columns.get_loc('%-rising_wedge')] = confidence
            
            # Falling Wedge: Cả high và low đều giảm, high giảm nhanh hơn (converging)
            if high_slope_pct < 0 and low_slope_pct < 0 and high_slope_pct < low_slope_pct:
                convergence = (low_slope_pct - high_slope_pct) / low_slope_pct if low_slope_pct != 0 else 0
                confidence = min(1.0, abs(convergence))
                dataframe.iloc[i, dataframe.columns.get_loc('%-falling_wedge')] = confidence
        
        return dataframe
    
    # ============================================================
    # 4. TRIANGLE PATTERNS
    # ============================================================
    
    @staticmethod
    def detect_triangle(dataframe: DataFrame, lookback: int = 50) -> DataFrame:
        """
        Phát hiện mô hình Triangle (Tam giác).
        
        Ascending Triangle: Flat top (resistance) + Rising bottom → Bullish
        Descending Triangle: Falling top + Flat bottom (support) → Bearish
        Symmetrical Triangle: Converging equally → Breakout either way
        """
        n = len(dataframe)
        dataframe['%-ascending_triangle'] = 0.0
        dataframe['%-descending_triangle'] = 0.0
        dataframe['%-symmetrical_triangle'] = 0.0
        
        if n < lookback + 10:
            return dataframe
        
        for i in range(lookback, n):
            window = dataframe.iloc[i-lookback:i]
            
            highs = window['high'].values
            lows = window['low'].values
            x = np.arange(lookback)
            
            high_slope = np.polyfit(x, highs, 1)[0]
            low_slope = np.polyfit(x, lows, 1)[0]
            
            avg_price = window['close'].mean()
            high_slope_pct = high_slope / avg_price
            low_slope_pct = low_slope / avg_price
            
            # Thresholds
            flat_threshold = 0.0001  # Gần như ngang
            slope_threshold = 0.0005  # Có độ dốc
            
            # Ascending Triangle: Flat high, rising low
            if abs(high_slope_pct) < flat_threshold and low_slope_pct > slope_threshold:
                dataframe.iloc[i, dataframe.columns.get_loc('%-ascending_triangle')] = min(1.0, low_slope_pct * 1000)
            
            # Descending Triangle: Falling high, flat low
            if high_slope_pct < -slope_threshold and abs(low_slope_pct) < flat_threshold:
                dataframe.iloc[i, dataframe.columns.get_loc('%-descending_triangle')] = min(1.0, abs(high_slope_pct) * 1000)
            
            # Symmetrical Triangle: Both converging towards center
            if high_slope_pct < 0 and low_slope_pct > 0:
                convergence = min(abs(high_slope_pct), abs(low_slope_pct)) / max(abs(high_slope_pct), abs(low_slope_pct))
                if convergence > 0.5:  # Similar slopes
                    dataframe.iloc[i, dataframe.columns.get_loc('%-symmetrical_triangle')] = convergence
        
        return dataframe
    
    # ============================================================
    # 5. FLAG / PENNANT
    # ============================================================
    
    @staticmethod
    def detect_flag(dataframe: DataFrame, pole_lookback: int = 20, flag_lookback: int = 15) -> DataFrame:
        """
        Phát hiện mô hình Flag/Pennant (Cờ).
        
        Bull Flag: Strong upward pole, then small downward/sideways channel
        Bear Flag: Strong downward pole, then small upward/sideways channel
        
        Continuation patterns - expect trend to continue
        """
        n = len(dataframe)
        dataframe['%-bull_flag'] = 0.0
        dataframe['%-bear_flag'] = 0.0
        
        total_lookback = pole_lookback + flag_lookback
        if n < total_lookback + 10:
            return dataframe
        
        for i in range(total_lookback, n):
            # Pole section
            pole_start = i - total_lookback
            pole_end = i - flag_lookback
            pole = dataframe.iloc[pole_start:pole_end]
            
            # Flag section
            flag = dataframe.iloc[pole_end:i]
            
            # Pole movement
            pole_move = (pole['close'].iloc[-1] - pole['close'].iloc[0]) / pole['close'].iloc[0]
            
            # Flag movement
            flag_move = (flag['close'].iloc[-1] - flag['close'].iloc[0]) / flag['close'].iloc[0]
            flag_range = (flag['high'].max() - flag['low'].min()) / flag['close'].mean()
            
            # Bull Flag: Strong up pole, small pullback
            if pole_move > 0.03:  # Pole up > 3%
                if flag_move < 0 and abs(flag_move) < pole_move * 0.5:  # Pullback < 50% of pole
                    if flag_range < pole_move * 0.3:  # Flag tight
                        confidence = min(1.0, pole_move * 10)
                        dataframe.iloc[i, dataframe.columns.get_loc('%-bull_flag')] = confidence
            
            # Bear Flag: Strong down pole, small rally
            if pole_move < -0.03:  # Pole down > 3%
                if flag_move > 0 and flag_move < abs(pole_move) * 0.5:
                    if flag_range < abs(pole_move) * 0.3:
                        confidence = min(1.0, abs(pole_move) * 10)
                        dataframe.iloc[i, dataframe.columns.get_loc('%-bear_flag')] = confidence
        
        return dataframe
    
    # ============================================================
    # MAIN METHOD - Add All Patterns
    # ============================================================
    
    @staticmethod
    def add_all_patterns(dataframe: DataFrame) -> DataFrame:
        """
        Add ALL chart pattern features to dataframe.
        
        Features added:
        - %-double_top, %-double_bottom
        - %-head_shoulders, %-head_shoulders_inv
        - %-rising_wedge, %-falling_wedge
        - %-ascending_triangle, %-descending_triangle, %-symmetrical_triangle
        - %-bull_flag, %-bear_flag
        - %-pattern_bull_score, %-pattern_bear_score, %-pattern_net_score
        
        Args:
            dataframe: OHLCV DataFrame
            
        Returns:
            DataFrame với tất cả pattern features
        """
        logger.info("Adding Chart Pattern features...")
        
        # Step 1: Find swing points
        dataframe = ChartPatterns.find_swing_points(dataframe)
        
        # Step 2: Detect patterns
        dataframe = ChartPatterns.detect_double_top(dataframe)
        dataframe = ChartPatterns.detect_double_bottom(dataframe)
        dataframe = ChartPatterns.detect_head_and_shoulders(dataframe)
        dataframe = ChartPatterns.detect_wedge(dataframe)
        dataframe = ChartPatterns.detect_triangle(dataframe)
        dataframe = ChartPatterns.detect_flag(dataframe)
        
        # Step 3: Summarize patterns into scores
        dataframe = ChartPatterns.summarize_patterns(dataframe)
        
        pattern_cols = [col for col in dataframe.columns if any(
            p in col for p in ['double', 'head', 'wedge', 'triangle', 'flag', 'pattern_']
        ) and col.startswith('%-')]
        
        logger.info(f"Added {len(pattern_cols)} chart pattern features")
        
        return dataframe
    
    # ============================================================
    # PATTERN SUMMARIZATION - Meta-features
    # ============================================================
    
    @staticmethod
    def summarize_patterns(dataframe: DataFrame) -> DataFrame:
        """
        Tổng hợp các patterns thành điểm số tổng.
        
        Thay vì ném 13 cột 0/1 vào AI (làm nhiễu), 
        gộp lại thành 3 điểm số:
        - %-pattern_bull_score: Tổng patterns bullish (0-5)
        - %-pattern_bear_score: Tổng patterns bearish (0-5)
        - %-pattern_net_score: Bull - Bear score (-5 to +5)
        
        Weights:
        - Double Top/Bottom: 1.0 (reliable reversal)
        - Head & Shoulders: 1.5 (strong reversal)
        - Wedge: 0.8 (moderate)
        - Triangle: 0.7 (continuation)
        - Flag: 0.6 (short-term)
        """
        # Bullish patterns with weights
        bullish_patterns = {
            '%-double_bottom': 1.0,
            '%-head_shoulders_inv': 1.5,
            '%-falling_wedge': 0.8,
            '%-ascending_triangle': 0.7,
            '%-bull_flag': 0.6,
        }
        
        # Bearish patterns with weights
        bearish_patterns = {
            '%-double_top': 1.0,
            '%-head_shoulders': 1.5,
            '%-rising_wedge': 0.8,
            '%-descending_triangle': 0.7,
            '%-bear_flag': 0.6,
        }
        
        # Calculate bull score
        bull_score = pd.Series(0.0, index=dataframe.index)
        for col, weight in bullish_patterns.items():
            if col in dataframe.columns:
                # Use min() to avoid overstating when pattern confidence > 1
                bull_score += dataframe[col].clip(0, 1) * weight
        
        # Calculate bear score
        bear_score = pd.Series(0.0, index=dataframe.index)
        for col, weight in bearish_patterns.items():
            if col in dataframe.columns:
                bear_score += dataframe[col].clip(0, 1) * weight
        
        # Normalize scores (max possible = sum of weights ≈ 4.6)
        max_score = sum(bullish_patterns.values())
        dataframe['%-pattern_bull_score'] = bull_score / max_score  # 0 to 1
        dataframe['%-pattern_bear_score'] = bear_score / max_score  # 0 to 1
        
        # Net score: -1 (very bearish) to +1 (very bullish)
        dataframe['%-pattern_net_score'] = dataframe['%-pattern_bull_score'] - dataframe['%-pattern_bear_score']
        
        # Pattern strength (any strong pattern detected?)
        dataframe['%-pattern_strength'] = dataframe[['%-pattern_bull_score', '%-pattern_bear_score']].max(axis=1)
        
        # Has active pattern?
        dataframe['%-has_pattern'] = (dataframe['%-pattern_strength'] > 0.1).astype(float)
        
        return dataframe


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    import pandas as pd
    import numpy as np
    
    print("="*60)
    print("CHART PATTERNS TEST")
    print("="*60)
    
    # Create sample data with some patterns
    np.random.seed(42)
    n = 500
    dates = pd.date_range(start='2025-01-01', periods=n, freq='5min')
    
    # Create price with patterns
    base_price = 40000
    price = np.zeros(n)
    
    # Simulate: Uptrend -> Double Top -> Downtrend -> Double Bottom
    for i in range(n):
        if i < 100:  # Uptrend
            price[i] = base_price + i * 20
        elif i < 150:  # First peak
            price[i] = base_price + 2000 + np.sin((i-100)/10) * 500
        elif i < 200:  # Pullback
            price[i] = base_price + 1500 + (i-150) * 5
        elif i < 250:  # Second peak (double top)
            price[i] = base_price + 2000 + np.sin((i-200)/10) * 500
        elif i < 350:  # Downtrend
            price[i] = base_price + 2000 - (i-250) * 15
        elif i < 400:  # First bottom
            price[i] = base_price + 500 - np.sin((i-350)/10) * 300
        elif i < 450:  # Rally
            price[i] = base_price + 800 - (i-400) * 3
        else:  # Second bottom (double bottom)
            price[i] = base_price + 500 - np.sin((i-450)/10) * 300
    
    # Add some noise
    price = price + np.random.normal(0, 50, n)
    
    sample_data = pd.DataFrame({
        'date': dates,
        'open': price * (1 + np.random.uniform(-0.001, 0.001, n)),
        'high': price * (1 + np.random.uniform(0, 0.005, n)),
        'low': price * (1 - np.random.uniform(0, 0.005, n)),
        'close': price,
        'volume': np.random.uniform(100, 1000, n)
    })
    
    # Fix high/low
    sample_data['high'] = sample_data[['open', 'close', 'high']].max(axis=1)
    sample_data['low'] = sample_data[['open', 'close', 'low']].min(axis=1)
    
    # Add patterns
    enhanced_data = ChartPatterns.add_all_patterns(sample_data)
    
    pattern_cols = [col for col in enhanced_data.columns if col.startswith('%-')]
    print(f"\nTotal pattern features: {len(pattern_cols)}")
    print("\nPattern columns:")
    for col in pattern_cols:
        non_zero = (enhanced_data[col] > 0).sum()
        if non_zero > 0:
            print(f"  {col}: {non_zero} detections")
    
    print("\nSample pattern detections:")
    for col in pattern_cols:
        detections = enhanced_data[enhanced_data[col] > 0][[col, 'close']].head(3)
        if len(detections) > 0:
            print(f"\n{col}:")
            print(detections.to_string())
