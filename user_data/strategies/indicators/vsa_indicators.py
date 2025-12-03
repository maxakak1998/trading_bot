"""
VSA Indicators - Volume Spread Analysis
========================================
Triển khai logic từ báo cáo nghiên cứu SMC/Wyckoff/VSA

Features:
- Spread Analysis (Biên độ nến)
- Effort vs Result (Nỗ lực vs Kết quả)
- Climactic Volume (Volume cực đại)
- Absorption (Hấp thụ)
- No Demand / No Supply
- Stopping Volume

Author: AI Trading System
Date: 2025-12-03
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
import logging

logger = logging.getLogger(__name__)


class VSAIndicators:
    """
    Volume Spread Analysis (VSA) Indicators
    Phân tích mối quan hệ giữa Spread (biên độ nến) và Volume
    để phát hiện hành vi Smart Money.
    """

    @staticmethod
    def add_all_indicators(dataframe: DataFrame) -> DataFrame:
        """
        Main method - Thêm tất cả VSA indicators.
        
        Args:
            dataframe: OHLCV DataFrame
            
        Returns:
            DataFrame với VSA features
        """
        logger.info("Adding VSA Indicators...")
        
        features = {}
        
        VSAIndicators._calc_spread_analysis(dataframe, features)
        VSAIndicators._calc_effort_vs_result(dataframe, features)
        VSAIndicators._calc_climactic_volume(dataframe, features)
        VSAIndicators._calc_absorption(dataframe, features)
        VSAIndicators._calc_no_demand_supply(dataframe, features)
        VSAIndicators._calc_stopping_volume(dataframe, features)
        
        # Single concat for performance
        if features:
            features_df = pd.DataFrame(features, index=dataframe.index)
            dataframe = pd.concat([dataframe, features_df], axis=1)
        
        logger.info("VSA Indicators added successfully")
        return dataframe

    @staticmethod
    def _calc_spread_analysis(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        Spread Analysis - Phân tích biên độ nến.
        
        Spread = High - Low
        So sánh với trung bình để phát hiện nến bất thường.
        """
        spread = dataframe['high'] - dataframe['low']
        avg_spread = spread.rolling(period).mean()
        
        # Spread ratio (so với trung bình)
        # > 1.5: Wide spread (biên độ rộng)
        # < 0.5: Narrow spread (biên độ hẹp)
        features['%-vsa_spread_ratio'] = spread / (avg_spread + 1e-10)
        
        # Body to spread ratio (thân nến / biên độ)
        # Cao: Nến mạnh, Thấp: Nến yếu (nhiều râu)
        body = (dataframe['close'] - dataframe['open']).abs()
        features['%-vsa_body_spread_ratio'] = body / (spread + 1e-10)
        
        # Close position in spread (vị trí đóng cửa trong nến)
        # 1: Đóng cửa ở đỉnh, 0: Đóng cửa ở đáy
        features['%-vsa_close_position'] = (dataframe['close'] - dataframe['low']) / (spread + 1e-10)

    @staticmethod
    def _calc_effort_vs_result(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        Effort vs Result - Nỗ lực (Volume) vs Kết quả (Price Change).
        
        Nguyên lý Wyckoff: 
        - Volume cao + Price change lớn = Effort matches Result (Bình thường)
        - Volume cao + Price change nhỏ = Effort exceeds Result (Smart Money đang gom/xả)
        - Volume thấp + Price change lớn = No effort (Breakout yếu, dễ thất bại)
        """
        price_change = (dataframe['close'] - dataframe['close'].shift(1)).abs()
        avg_price_change = price_change.rolling(period).mean()
        
        vol_ratio = dataframe['volume'] / (dataframe['volume'].rolling(period).mean() + 1e-10)
        price_ratio = price_change / (avg_price_change + 1e-10)
        
        # Effort vs Result Ratio
        # > 1.5: Volume quá cao so với price change (Smart Money activity)
        # < 0.5: Volume quá thấp so với price change (Weak move)
        features['%-vsa_effort_result'] = vol_ratio / (price_ratio + 1e-10)
        
        # Anomaly detection (Volume cao nhưng giá không chạy)
        # Binary feature: 1 = Bất thường (Smart Money)
        features['%-vsa_anomaly'] = np.where(
            (vol_ratio > 2.0) & (price_ratio < 0.8),
            1.0, 0.0
        )

    @staticmethod
    def _calc_climactic_volume(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        Climactic Volume - Volume cực đại.
        
        Selling Climax: Volume cực cao + Giá giảm mạnh + Rút chân (Đáy tiềm năng)
        Buying Climax: Volume cực cao + Giá tăng mạnh + Rút đầu (Đỉnh tiềm năng)
        """
        avg_vol = dataframe['volume'].rolling(period).mean()
        std_vol = dataframe['volume'].rolling(period).std()
        
        spread = dataframe['high'] - dataframe['low']
        avg_spread = spread.rolling(period).mean()
        
        # Volume Z-score
        vol_zscore = (dataframe['volume'] - avg_vol) / (std_vol + 1e-10)
        features['%-vsa_volume_zscore'] = vol_zscore.clip(-3, 3)
        
        # Ultra high volume (> 2.5 std)
        ultra_high_vol = vol_zscore > 2.5
        
        # Wide spread (> 1.5x average)
        wide_spread = spread > 1.5 * avg_spread
        
        # Close position
        close_position = (dataframe['close'] - dataframe['low']) / (spread + 1e-10)
        
        # Selling Climax: Volume cực cao + Spread rộng + Nến giảm + Đóng cửa ở phần trên (rút chân)
        is_bearish = dataframe['close'] < dataframe['open']
        close_in_upper = close_position > 0.6
        
        features['%-vsa_selling_climax'] = np.where(
            ultra_high_vol & wide_spread & is_bearish & close_in_upper,
            1.0, 0.0
        )
        
        # Buying Climax: Volume cực cao + Spread rộng + Nến tăng + Đóng cửa ở phần dưới (rút đầu)
        is_bullish = dataframe['close'] > dataframe['open']
        close_in_lower = close_position < 0.4
        
        features['%-vsa_buying_climax'] = np.where(
            ultra_high_vol & wide_spread & is_bullish & close_in_lower,
            1.0, 0.0
        )

    @staticmethod
    def _calc_absorption(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        Absorption - Hấp thụ.
        
        Volume cao nhưng giá không di chuyển nhiều = Smart Money đang hấp thụ.
        Bearish Absorption: Giá không giảm dù có volume bán lớn (Đáy)
        Bullish Absorption: Giá không tăng dù có volume mua lớn (Đỉnh)
        """
        avg_vol = dataframe['volume'].rolling(period).mean()
        spread = dataframe['high'] - dataframe['low']
        avg_spread = spread.rolling(period).mean()
        
        # High volume (> 1.5x) + Narrow spread (< 0.7x)
        high_vol = dataframe['volume'] > 1.5 * avg_vol
        narrow_spread = spread < 0.7 * avg_spread
        
        # Absorption (chung)
        features['%-vsa_absorption'] = np.where(
            high_vol & narrow_spread,
            1.0, 0.0
        )
        
        # Bearish candle with absorption = Bullish absorption (đang hấp thụ lực bán)
        is_bearish = dataframe['close'] < dataframe['open']
        features['%-vsa_bullish_absorption'] = np.where(
            high_vol & narrow_spread & is_bearish,
            1.0, 0.0
        )
        
        # Bullish candle with absorption = Bearish absorption (đang hấp thụ lực mua)
        is_bullish = dataframe['close'] > dataframe['open']
        features['%-vsa_bearish_absorption'] = np.where(
            high_vol & narrow_spread & is_bullish,
            1.0, 0.0
        )

    @staticmethod
    def _calc_no_demand_supply(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        No Demand / No Supply - Không có cầu / Không có cung.
        
        No Demand: Nến tăng + Volume thấp + Spread hẹp = Lực mua yếu
        No Supply: Nến giảm + Volume thấp + Spread hẹp = Lực bán yếu
        
        Đây là tín hiệu XÁC NHẬN cho entry:
        - No Supply trong uptrend = An toàn mua tiếp
        - No Demand trong downtrend = An toàn bán tiếp
        """
        avg_vol = dataframe['volume'].rolling(period).mean()
        spread = dataframe['high'] - dataframe['low']
        avg_spread = spread.rolling(period).mean()
        
        # Low volume (< 0.7x average)
        low_vol = dataframe['volume'] < 0.7 * avg_vol
        
        # Narrow spread (< 0.8x average)
        narrow_spread = spread < 0.8 * avg_spread
        
        # No Demand: Nến tăng + Volume thấp + Spread hẹp
        is_bullish = dataframe['close'] > dataframe['open']
        features['%-vsa_no_demand'] = np.where(
            is_bullish & low_vol & narrow_spread,
            1.0, 0.0
        )
        
        # No Supply: Nến giảm + Volume thấp + Spread hẹp
        is_bearish = dataframe['close'] < dataframe['open']
        features['%-vsa_no_supply'] = np.where(
            is_bearish & low_vol & narrow_spread,
            1.0, 0.0
        )

    @staticmethod
    def _calc_stopping_volume(dataframe: DataFrame, features: dict, period: int = 20) -> None:
        """
        Stopping Volume - Volume dừng.
        
        Trong xu hướng giảm, xuất hiện nến với:
        - Volume rất cao (> 2x)
        - Giá giảm nhưng đóng cửa gần đỉnh (rút chân mạnh)
        
        Đây là dấu hiệu Smart Money bắt đầu mua vào (Accumulation).
        """
        avg_vol = dataframe['volume'].rolling(period).mean()
        spread = dataframe['high'] - dataframe['low']
        
        # High volume (> 2x)
        high_vol = dataframe['volume'] > 2.0 * avg_vol
        
        # Close in upper 25% of spread (rút chân mạnh)
        close_position = (dataframe['close'] - dataframe['low']) / (spread + 1e-10)
        close_in_upper = close_position > 0.75
        
        # Price was falling (low < previous low)
        falling = dataframe['low'] < dataframe['low'].shift(1)
        
        features['%-vsa_stopping_volume'] = np.where(
            high_vol & close_in_upper & falling,
            1.0, 0.0
        )
