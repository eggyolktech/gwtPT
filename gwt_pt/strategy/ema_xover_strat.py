#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb
from gwt_pt.common.indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

from gwt_pt.datasource import ibkr 
from gwt_pt.telegram import bot_sender
from gwt_pt.charting import btplot
from gwt_pt.strategy.strat_base import strategy, portfolio

import time
import datetime
import logging, sys

LOGFILE_ENABLED = False

if (os.name == 'nt'):
    logfile = 'C:\\Users\\Hin\\eggyolktech\\gwtPT\\gwt_pt\\log\\macdstoc_strat.log'
else:
    logfile = '/app/gwtPT/gwt_pt/log/macdstoc_strat_%s.log' % datetime.datetime.today().strftime('%m%d-%H%M%S')

logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger()

if LOGFILE_ENABLED:
    sys.stderr.write = lambda s: logger.error(s)
    sys.stdout.write = lambda s: logger.info(s)

EL = "\n"
DEL = "\n\n"

STOC_UPPER_LIMIT = 75
STOC_LOWER_LIMIT = 25
STOC_WINDOW = 16
MACD_WINDOW = 12 
EMA_WINDOW = 25

MONITOR_PERIOD = 20
SLEEP_PERIOD = 8

class ema_xover_strategy(strategy):
    """    
    Requires:
    symbol - A stock symbol on which to form a strategy on.
    bars - A DataFrame of bars for the above symbol."""

    def __init__(self, symbol, bars, window1=25, window2=25):
        self.symbol = symbol
        self.bars = bars
        self.window1 = window1
        self.window2 = window2

    def generate_signals(self):
        """Returns the DataFrame of symbols containing the signals
        to go long, short or hold (1, -1 or 0)."""
            
        signals = pd.DataFrame(index=self.bars.index)
        signals['open'] = self.bars['open']    
        signals['high'] = self.bars['high']
        signals['low'] = self.bars['low']
        signals['close'] = self.bars['close']
        signals["ema25"] = EMA(signals, 'close', 25)

        # MACD
        macd = MACD(self.bars['close'])
        signals = pd.concat([signals, macd], axis=1)

        # Slowstoc
        kslow, dslow = SLOWSTOC(self.bars, 'low', 'high', 'close', STOC_WINDOW, 6, False)
        signals = pd.concat([signals, kslow, dslow], axis=1)   

        signals['xup'] = signals['xdown'] = signals['xup_pos'] = signals['xdown_pos'] = 0.0

        ###############################################################################
        if (len(signals) >= EMA_WINDOW):
            signals['xup'][EMA_WINDOW:] = np.where(
                (signals['close'][EMA_WINDOW:] > signals['ema25'][EMA_WINDOW:]), 1.0, 0.0)
        else:
            signals['xup'] = 0.0
        
        ## Take the difference of the signals in order to generate actual trading orders
        signals['xup_pos'] = signals['xup'].diff()
        signals.loc[signals.xup_pos == -1.0, 'xup_pos'] = 0.0

        ###############################################################################
        if (len(signals) >= EMA_WINDOW):
            signals['xdown'][EMA_WINDOW:] = np.where(
                (signals['close'][EMA_WINDOW:] < signals['ema25'][EMA_WINDOW:]), 1.0, 0.0)
        else:
            signals['xdown'] = 0.0
        
        ## Take the difference of the signals in order to generate actual trading orders
        signals['xdown_pos'] = signals['xdown'].diff()
        signals.loc[signals.xdown_pos == -1.0, 'xdown_pos'] = 0.0
        
        return signals

class ema_xover_portfolio(portfolio):
    """Encapsulates the notion of a portfolio of positions based
    on a set of signals as provided by a Strategy.

    Requires:
    symbol - A stock symbol which forms the basis of the portfolio.
    bars - A DataFrame of bars for a symbol set.
    signals - A pandas DataFrame of signals (1, 0, -1) for each symbol.
    initial_capital - The amount in cash at the start of the portfolio."""

    def __init__(self, symbol, bars, signals, initial_capital=100000.0):
        self.symbol = symbol        
        self.bars = bars
        self.signals = signals
        self.initial_capital = float(initial_capital)
        self.positions = self.generate_positions()
        
    def generate_positions(self):
        positions = pd.DataFrame(index=self.signals.index).fillna(0.0)
        positions[self.symbol] = 10 * self.signals['xup_pos']
        positions[self.symbol] = positions[self.symbol] + (-10 * self.signals['xdown_pos'])
        #print(positions.to_string())
        return positions
                    
    def backtest_portfolio(self):
        pf = pd.DataFrame(index=self.bars.index)
        pf['close'] = self.bars['close']
        pf['pos'] = self.positions
        pf['holdings'] = self.positions.mul(self.bars['close'], axis='index')
        pf['cash'] = self.initial_capital - pf['holdings'].cumsum()
        pf['total'] = pf['cash'] + self.positions[self.symbol].cumsum() * self.bars['close']
        pf['returns'] = pf['total'].pct_change()
        pf['sma25'] = EMA(pf, 'total', 25)
        print(pf.to_string())
        return pf

def run_strat(symbol, historic_data): 
    
    # Set float format
    #pd.options.display.float_format = "{:.9f}".format
    
    # Data pre-processing
    bars = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    bars.set_index('datetime', inplace=True)
    bars.index = pd.to_datetime(bars.index)
    
    ema_strats = ema_xover_strategy(symbol, bars, 25)
    signals = ema_strats.generate_signals()
    
    ema_portfolio = ema_xover_portfolio(symbol, bars, signals, initial_capital=100000.0)
    pf = ema_portfolio.backtest_portfolio()
  
    ## Plot the strategy charting
    title = "EMA Xover Strategy Backtest for %s" % symbol
    #print(signals[['sk_slow','sd_slow', 'macdstoc_xup_positions', 'macdstoc_xdown_positions']].tail(20).to_string())
    #print(signals[['close','xup_pos', 'xdown_pos']].to_string())

    btplot.plot_with_portfolio(bars, signals, pf, title, True)

def main():
    
    passage = "Generation of Macdstoc Strats............."
    print(passage)

    HKFE_PAIR = ["HSI"]
        
    # Futures Pair
    for cur in HKFE_PAIR:

        symbol = cur
        #duration = "3 Y"
        duration = "6 M"        
        period = "1 hour"
        current_mth = datetime.datetime.today().strftime('%Y%m')
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
        run_strat(title, hist_data)

if __name__ == "__main__":
    main() 
