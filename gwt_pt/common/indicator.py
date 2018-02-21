
import pandas as pd
import datetime
from datetime import tzinfo, timedelta, datetime
import time
import os
import numpy as np
import traceback
import logging
import sys


def SMA(df, column="close", period=26):

    sma = df[column].rolling(window=period, min_periods=1, center=False).mean()
    return sma

def EMA(df, column="close", period=20):

    ema = df[column].ewm(span=period, min_periods=period - 1).mean()
    return ema.to_frame('EMA')

def RSI(df, column="close", period=14):
    # wilder's RSI
 
    delta = df[column].diff()
    up, down = delta.copy(), delta.copy()

    up[up < 0] = 0
    down[down > 0] = 0

    rUp = up.ewm(com=period - 1,  adjust=False).mean()
    rDown = down.ewm(com=period - 1, adjust=False).mean().abs()

    rsi = 100 - 100 / (1 + rUp / rDown)    

    return rsi.to_frame('RSI')

def BB(df, column="close", period=20):

    sma = df[column].rolling(window=period, min_periods=period - 1).mean()
    std = df[column].rolling(window=period, min_periods=period - 1).std()

    up = (sma + (std * 2)).to_frame('BBANDUP')
    lower = (sma - (std * 2)).to_frame('BBANDLO')
    return up, lower
    
def FASTSTOC(df, column_low="low", column_high="high", column_close="close", period=16, smoothing=8, debug=False):
    """ calculate slow stochastic
    Fast stochastic calculation
    %K = (Current Close - Lowest Low)/(Highest High - Lowest Low) * 100
    %D = 8-day SMA of %K
    """
    
    lowp = df[column_low]
    highp = df[column_high]
    closep = df[column_close]
    
    if debug:
        #print("LLPPPPPP")
        #print(lowp)

        #print("HHPPPPPP")
        #print(highp)

        print("CCPPPPPP")
        #print(closep)

        
    low_min = lowp.rolling(center=False, min_periods=1, window=period).min()
    high_max = highp.rolling(center=False, min_periods=1, window=period).max()
    k_fast = 100 * (closep - low_min)/(high_max - low_min)
    
    if debug:
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print(type(k_fast))
        print("KFFFFFFFFFFFF1================================================")
        print(k_fast)
    
    
    #k_fast = pd.DataFrame(k_fast, columns=['k_fast'])
    k_fast = k_fast.to_frame('k_fast')

    if debug:
        print("KFFFFFFFFFFFF2================================================")
        print(k_fast)
    
    d_fast = SMA(k_fast, "k_fast", smoothing)
    d_fast = d_fast.to_frame('d_fast')
    d_fast = np.round(d_fast, 6)
    
    if debug:
        print("KFFFFFFFFFFFF================================================")
        #print(k_fast)
        print("DFFFFFFFFFFFF================================================")
        #print(d_fast)
    return k_fast, d_fast

def SLOWSTOC(df, column_low="low", column_high="high", column_close="close", period=16, smoothing=8, debug=False):
    """ calculate slow stochastic
    Slow stochastic calculation
    %K = %D of fast stochastic
    %D = 8-day SMA of %K
    """
    
    if debug:
        print(df)
    
    k_fast, d_fast = FASTSTOC(df, column_low, column_high, column_close, period, smoothing, debug)
    
    if debug:
        print("KKKKKKKKKKK")
        print(k_fast)
        print("DDDDDDDDDDD")
        print(d_fast)

    # D in fast stochastic is K in slow stochastic
    k_slow = d_fast
    k_slow = k_slow.rename(columns = {'d_fast':'k_slow'})
    d_slow = SMA(k_slow, 'k_slow', smoothing)
    d_slow = d_slow.to_frame('d_slow')
    return k_slow, d_slow
    
def MACD(prices, nslow=26, nfast=12, smoothing=9):
    emaslow = prices.ewm(min_periods=1, ignore_na=False, span=nslow, adjust=True).mean()
    emafast = prices.ewm(min_periods=1, ignore_na=False, span=nfast, adjust=True).mean()

    macd = emafast - emaslow
    emasmooth = macd.ewm(min_periods=1, ignore_na=False, span=smoothing, adjust=True).mean()

    result = pd.DataFrame({'macd': macd, 'emaSmooth': emasmooth, 'divergence': macd-emasmooth})
    return result

def main():

    print("main....")
    end = datetime.today()
    start = end - timedelta(days=(1*365))

if __name__ == "__main__":
    main()

