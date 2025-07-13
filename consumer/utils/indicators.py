
from statistics import mean
from functools import reduce
from typing import List

def compute_sma(values: List[float], period: int) -> float:

    if len(values) < period:
        return float('nan')
    return mean(values[-period:])

def compute_ema(values: List[float], period: int) -> float:

    if len(values) < period:
        return float('nan')
    
    multiplier = 2 / (period + 1)
    
    def ema_step(acc: float, price: float) -> float:
        return (price - acc) * multiplier + acc
    
    return reduce(ema_step, values[1:], values[0])

def compute_rsi(prices: List[float], period: int = 14) -> float:

    if len(prices) < period + 1:
        return float('nan')
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    gains = list(map(lambda x: max(0, x), deltas))
    losses = list(map(lambda x: abs(min(0, x)), deltas))
    
    avg_gain = mean(gains[-period:])
    avg_loss = mean(losses[-period:])
    
    return 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))