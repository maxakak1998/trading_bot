import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame

class SMCIndicators:
    """
    Ported logic from 'SMC + Sonic R + Moon Phases' Pine Script.
    """

    @staticmethod
    def add_all_indicators(dataframe: DataFrame) -> DataFrame:
        """
        Main method to add all indicators to the dataframe.
        """
        dataframe = SMCIndicators.add_sonic_r(dataframe)
        dataframe = SMCIndicators.add_ema_system(dataframe)
        dataframe = SMCIndicators.add_moon_phases(dataframe)
        # SMC is complex and computationally heavy for pandas in a loop. 
        # We will implement a simplified vectorized version for Swings.
        dataframe = SMCIndicators.add_smc_swings(dataframe)
        return dataframe

    @staticmethod
    def add_sonic_r(dataframe: DataFrame, period: int = 34) -> DataFrame:
        """
        Sonic R Dragon Lines: EMA 34 of High, Low, Close.
        """
        dataframe['sonic_h'] = ta.ema(dataframe['high'], length=period)
        dataframe['sonic_l'] = ta.ema(dataframe['low'], length=period)
        dataframe['sonic_c'] = ta.ema(dataframe['close'], length=period)
        return dataframe

    @staticmethod
    def add_ema_system(dataframe: DataFrame) -> DataFrame:
        """
        EMA 369 and 630.
        """
        dataframe['ema_369'] = ta.ema(dataframe['close'], length=369)
        dataframe['ema_630'] = ta.ema(dataframe['close'], length=630)
        return dataframe

    @staticmethod
    def add_moon_phases(dataframe: DataFrame) -> DataFrame:
        """
        Moon Phases based on Julian Day calculation.
        """
        # Constants
        SYNODIC_MONTH = 29.530588853
        REFERENCE_JD = 2451550.1
        JULIAN_EPOCH = 2440587.5
        MILLIS_PER_DAY = 86400000.0

        # Calculate Julian Day for each row
        # timestamp in dataframe is usually in milliseconds (if using Freqtrade)
        # date column is datetime object.
        
        # Convert datetime to timestamp (ms) if needed, or use .astype(int) / 10**6 for ns to ms
        # Freqtrade 'date' is datetime64[ns]
        
        # We can use a vectorized approach
        timestamps = dataframe['date'].astype('int64') // 10**6 # Convert ns to ms
        
        julian_days = JULIAN_EPOCH + (timestamps / MILLIS_PER_DAY)
        moon_ages = (julian_days - REFERENCE_JD) % SYNODIC_MONTH
        moon_ages = np.where(moon_ages < 0, moon_ages + SYNODIC_MONTH, moon_ages)
        
        dataframe['moon_age'] = moon_ages
        
        # Illumination
        phase_angle = 2 * np.pi * moon_ages / SYNODIC_MONTH
        dataframe['moon_illumination'] = (1 + np.cos(phase_angle)) / 2

        # Phases (Simplified for features)
        # 0: New Moon, 0.5: Full Moon approx (normalized 0-1 phase)
        dataframe['moon_phase_normalized'] = moon_ages / SYNODIC_MONTH
        
        # Categorical Phase (One-Hot encoding style or integer for trees)
        # New Moon: 0, First Quarter: 1, Full Moon: 2, Last Quarter: 3
        conditions = [
            (moon_ages <= 1) | (moon_ages >= 28.5), # New Moon
            (moon_ages >= 7.38 - 1) & (moon_ages <= 7.38 + 1), # First Quarter
            (moon_ages >= 14.77 - 1) & (moon_ages <= 14.77 + 1), # Full Moon
            (moon_ages >= 22.15 - 1) & (moon_ages <= 22.15 + 1) # Last Quarter
        ]
        choices = [0, 1, 2, 3] # 0: New, 1: Q1, 2: Full, 3: Q3
        dataframe['moon_phase_cat'] = np.select(conditions, choices, default=-1) # -1: Intermediate

        return dataframe

    @staticmethod
    def add_smc_swings(dataframe: DataFrame, length: int = 50) -> DataFrame:
        """
        Simplified SMC Swings (High/Low) detection.
        Note: True SMC requires looking forward, which is 'lookahead bias' in ML.
        However, for 'lagging' indicators (labeling past swings), it's fine.
        For real-time features, we can only use 'confirmed' swings (lagged).
        """
        # Pivot High/Low
        # This is a lagging indicator by definition (needs 'length' bars after to confirm)
        # For ML features, we usually don't use the pivot point itself at t=0 because we don't know it yet.
        # We can use "Distance to last Swing High/Low".
        
        # Using pandas_ta or similar if available, else custom.
        # Freqtrade doesn't have built-in pivot points in default TA-Lib.
        
        # Vectorized rolling max/min to find local extrema
        # Note: This is computationally expensive if not careful.
        
        # Let's use a simpler approach for features:
        # Donchian Channels (High/Low of last N bars)
        dataframe[f'donchian_high_{length}'] = dataframe['high'].rolling(window=length).max()
        dataframe[f'donchian_low_{length}'] = dataframe['low'].rolling(window=length).min()
        
        # Is current bar a swing high? (High > surrounding bars)
        # We can't know if it's a swing high for the NEXT bars, but we can check previous.
        # Fractal: High[t] > High[t-2]...High[t+2] -> This is lookahead.
        
        # For AI features, let's provide:
        # 1. Distance to recent highest high
        # 2. Distance to recent lowest low
        dataframe['dist_to_recent_high'] = (dataframe['close'] - dataframe[f'donchian_high_{length}']) / dataframe['close']
        dataframe['dist_to_recent_low'] = (dataframe['close'] - dataframe[f'donchian_low_{length}']) / dataframe['close']
        
        return dataframe
