"""
Data Enhancement Module - Phase 2 Features
==========================================
This module provides additional data features for the AI Trading Strategy:
- Funding Rate (from Binance Futures)
- Fear & Greed Index (from alternative.me API)
- Volume-based indicators

Author: AI Trading System
Date: 2025-11-30
"""

import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataEnhancement:
    """
    Class containing data enhancement methods for trading strategy.
    """
    
    # Cache for Fear & Greed Index (update once per day)
    _fg_cache: Dict[str, Any] = {
        'value': None,
        'classification': None,
        'timestamp': None
    }
    
    @staticmethod
    def get_fear_greed_index() -> Dict[str, Any]:
        """
        Fetch Fear & Greed Index from alternative.me API.
        
        Returns:
            dict: {
                'value': int (0-100),
                'classification': str ('Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'),
                'timestamp': datetime
            }
        
        Example:
            - Extreme Fear (0-24): Good time to buy
            - Fear (25-44): Market is scared
            - Neutral (45-55): Market is neutral
            - Greed (56-75): Market is greedy
            - Extreme Greed (76-100): Market is extremely greedy, potential correction
        """
        # Check cache (valid for 1 hour)
        if DataEnhancement._fg_cache['timestamp']:
            cache_age = datetime.now() - DataEnhancement._fg_cache['timestamp']
            if cache_age < timedelta(hours=1):
                return DataEnhancement._fg_cache
        
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and 'data' in data and len(data['data']) > 0:
                fg_data = data['data'][0]
                result = {
                    'value': int(fg_data['value']),
                    'classification': fg_data['value_classification'],
                    'timestamp': datetime.now()
                }
                
                # Update cache
                DataEnhancement._fg_cache = result
                logger.info(f"Fear & Greed Index: {result['value']} ({result['classification']})")
                
                return result
                
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed Index: {e}")
        
        # Return default if API fails
        return {
            'value': 50,  # Neutral
            'classification': 'Neutral',
            'timestamp': datetime.now()
        }
    
    @staticmethod
    def add_fear_greed_features(dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Add Fear & Greed Index features to dataframe.
        
        Features added:
        - %-fear_greed_value: Raw F&G value (0-100)
        - %-fear_greed_normalized: Normalized to [-1, 1] range
        - %-is_extreme_fear: Binary flag for extreme fear (<20)
        - %-is_extreme_greed: Binary flag for extreme greed (>80)
        
        Args:
            dataframe: OHLCV dataframe
            
        Returns:
            DataFrame with F&G features added
        """
        fg_data = DataEnhancement.get_fear_greed_index()
        fg_value = fg_data['value']
        
        # Add features
        dataframe['%-fear_greed_value'] = fg_value
        
        # Normalize to [-1, 1]: Fear = negative, Greed = positive
        dataframe['%-fear_greed_normalized'] = (fg_value - 50) / 50
        
        # Binary flags
        dataframe['%-is_extreme_fear'] = 1 if fg_value < 20 else 0
        dataframe['%-is_extreme_greed'] = 1 if fg_value > 80 else 0
        
        return dataframe
    
    @staticmethod
    def add_volume_imbalance(dataframe: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Add Volume Imbalance indicator.
        
        This indicator estimates buy/sell pressure based on price movement and volume.
        
        Logic:
        - If close > open: Volume is considered "buy volume"
        - If close < open: Volume is considered "sell volume"
        - Volume Imbalance = (buy_vol - sell_vol) / total_vol
        
        Features added:
        - %-buy_volume: Estimated buy volume
        - %-sell_volume: Estimated sell volume
        - %-volume_imbalance: Ratio (-1 to +1)
        - %-volume_imbalance_ma: Moving average of imbalance
        
        Args:
            dataframe: OHLCV dataframe
            period: Period for moving average
            
        Returns:
            DataFrame with volume features added
        """
        # Calculate buy/sell volume based on candle direction
        dataframe['%-buy_volume'] = np.where(
            dataframe['close'] > dataframe['open'],
            dataframe['volume'],
            dataframe['volume'] * (dataframe['close'] - dataframe['low']) / (dataframe['high'] - dataframe['low'] + 1e-10)
        )
        
        dataframe['%-sell_volume'] = np.where(
            dataframe['close'] < dataframe['open'],
            dataframe['volume'],
            dataframe['volume'] * (dataframe['high'] - dataframe['close']) / (dataframe['high'] - dataframe['low'] + 1e-10)
        )
        
        # Volume imbalance ratio
        total_buy = dataframe['%-buy_volume'].rolling(window=period).sum()
        total_sell = dataframe['%-sell_volume'].rolling(window=period).sum()
        
        dataframe['%-volume_imbalance'] = (total_buy - total_sell) / (total_buy + total_sell + 1e-10)
        
        # Moving average of imbalance
        dataframe['%-volume_imbalance_ma'] = dataframe['%-volume_imbalance'].rolling(window=period).mean()
        
        return dataframe
    
    @staticmethod
    def add_funding_rate_proxy(dataframe: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Add Funding Rate proxy features.
        
        Since Freqtrade doesn't directly support funding rate data,
        we estimate market sentiment using price premium/discount.
        
        Logic:
        - Calculate short-term vs long-term price deviation
        - High premium suggests long-heavy market (high funding)
        - High discount suggests short-heavy market (low/negative funding)
        
        Features added:
        - %-price_premium: Short-term price vs long-term average
        - %-premium_zscore: Z-score of premium (standardized)
        - %-is_overheated: Binary flag for extreme premium
        
        Args:
            dataframe: OHLCV dataframe
            period: Period for calculations
            
        Returns:
            DataFrame with funding proxy features added
        """
        # Short-term vs long-term price comparison
        short_ma = dataframe['close'].rolling(window=period).mean()
        long_ma = dataframe['close'].rolling(window=period * 3).mean()
        
        # Price premium (positive = overheated, negative = oversold)
        dataframe['%-price_premium'] = (short_ma - long_ma) / long_ma
        
        # Z-score of premium
        premium_mean = dataframe['%-price_premium'].rolling(window=period * 2).mean()
        premium_std = dataframe['%-price_premium'].rolling(window=period * 2).std()
        dataframe['%-premium_zscore'] = (dataframe['%-price_premium'] - premium_mean) / (premium_std + 1e-10)
        
        # Binary flag for overheated market
        dataframe['%-is_overheated'] = np.where(dataframe['%-premium_zscore'] > 2, 1, 0)
        dataframe['%-is_oversold'] = np.where(dataframe['%-premium_zscore'] < -2, 1, 0)
        
        return dataframe
    
    @staticmethod
    def add_all_features(dataframe: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Add all Phase 2 data enhancement features.
        
        Args:
            dataframe: OHLCV dataframe
            period: Period for calculations
            
        Returns:
            DataFrame with all Phase 2 features added
        """
        dataframe = DataEnhancement.add_fear_greed_features(dataframe)
        dataframe = DataEnhancement.add_volume_imbalance(dataframe, period)
        dataframe = DataEnhancement.add_funding_rate_proxy(dataframe, period)
        
        return dataframe


# Test function
if __name__ == "__main__":
    # Test Fear & Greed API
    fg_data = DataEnhancement.get_fear_greed_index()
    print(f"Fear & Greed Index: {fg_data['value']} ({fg_data['classification']})")
    
    # Test with sample data
    import pandas as pd
    import numpy as np
    
    # Create sample OHLCV data
    np.random.seed(42)
    n = 100
    dates = pd.date_range(start='2025-01-01', periods=n, freq='5min')
    
    sample_data = pd.DataFrame({
        'date': dates,
        'open': np.random.uniform(40000, 41000, n),
        'high': np.random.uniform(40500, 41500, n),
        'low': np.random.uniform(39500, 40500, n),
        'close': np.random.uniform(40000, 41000, n),
        'volume': np.random.uniform(100, 1000, n)
    })
    
    # Add all features
    enhanced_data = DataEnhancement.add_all_features(sample_data)
    
    print("\nEnhanced columns:")
    print([col for col in enhanced_data.columns if col.startswith('%-')])
    
    print("\nSample values:")
    print(enhanced_data[['%-fear_greed_value', '%-volume_imbalance', '%-price_premium']].tail())
