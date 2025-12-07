"""
Custom Hyperopt Loss Function - Win Ratio Focus
Optimizes directly for Win Rate while maintaining minimum profit requirement.
"""
from datetime import datetime
from pandas import DataFrame
from freqtrade.data.metrics import calculate_max_drawdown
from freqtrade.optimize.hyperopt import IHyperOptLoss


class WinRatioHyperOptLoss(IHyperOptLoss):
    """
    Custom hyperopt loss function that prioritizes Win Rate.
    
    Loss = -(win_rate * 100) + penalties
    
    Lower is better (more negative = higher win rate)
    """

    @staticmethod
    def hyperopt_loss_function(
        *,
        results: DataFrame,
        trade_count: int,
        min_date: datetime,
        max_date: datetime,
        config: dict,
        **kwargs,
    ) -> float:
        """
        Objective function: Maximize Win Rate with minimum trade requirement.
        
        Returns negative win rate (lower = better for hyperopt minimization)
        """
        # No trades = bad
        if trade_count == 0:
            return 100.0  # High penalty
        
        # Need at least 10 trades for reliable WR calculation
        min_trades = 10
        if trade_count < min_trades:
            return 50.0 + (min_trades - trade_count) * 5  # Penalty for too few trades
        
        # Calculate Win Rate
        winning_trades = results[results['profit_abs'] > 0].shape[0]
        win_rate = winning_trades / trade_count
        
        # Calculate total profit
        total_profit = results['profit_abs'].sum()
        
        # Penalty for losses
        profit_penalty = 0
        if total_profit < 0:
            profit_penalty = abs(total_profit) * 0.1  # Small penalty for negative profit
        
        # Primary objective: maximize win rate (negative because hyperopt minimizes)
        # Secondary: slight bonus for higher trade count (up to limit)
        trade_bonus = min(trade_count / 50, 0.1)  # Max 0.1 bonus for 50+ trades
        
        loss = -(win_rate * 100) + profit_penalty - trade_bonus
        
        return loss
