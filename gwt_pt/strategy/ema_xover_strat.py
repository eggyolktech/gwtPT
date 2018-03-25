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
        signals['nopen'] = signals['open'].shift(-1) # get next bar open for trade action

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
        pf['open'] = self.bars['open']
        pf['nopen'] = self.signals['nopen']
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
    
    #print(pf)
    recon = (pf[(pf.pos == 10) | (pf.pos == -10)])[['close', 'nopen', 'pos']]
    recon['l'] = recon['nopen'].diff() - 30
    recon.loc[recon['pos'] == 10, 'l'] = None
    recon['lpos'] = (recon['l'] * 10)
    recon.loc[recon['lpos'] != 0, 'lpos_comm'] = recon['lpos'] - 34 
    ltotal = recon['lpos_comm'].sum()
  
    recon['s'] = recon['nopen'].diff() + 30
    recon.loc[recon['pos'] == -10, 's'] = None
    recon['spos'] = (recon['s'] * -10)
    recon.loc[recon['spos'] != 0, 'spos_comm'] = recon['spos'] - 34 
    stotal = recon['spos_comm'].sum()
  
    print(recon.to_string())
    print("Total P&L (Long): $%f" % ltotal)
    print("Total P&L (Short): $%f" % stotal)
  
    
    ## Plot the strategy charting
    title = "EMA Xover Strategy Backtest for %s" % symbol
    #print(signals[['sk_slow','sd_slow', 'macdstoc_xup_positions', 'macdstoc_xdown_positions']].tail(20).to_string())
    #print(signals[['close','xup_pos', 'xdown_pos']].to_string())

    btplot.plot_with_portfolio(bars, signals, pf, title, True)

def gen_alert(symbol="MHI"):     
    
    duration = "1 M"        
    period = "1 hour"
    current_mth = datetime.datetime.today().strftime('%Y%m')
    #current_mth = "201802"
    title = symbol + "@" + period + " (Contract: " + current_mth + ")"
    print("Checking on " + title + " ......")

    historic_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
    
    # Data pre-processing
    bars = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    bars.set_index('datetime', inplace=True)
    bars.index = pd.to_datetime(bars.index)
    
    ema_strats = ema_xover_strategy(symbol, bars, 25)
    signals = ema_strats.generate_signals()
    
    latest_signal = signals.iloc[-2:].head(1)
    lts = latest_signal.index[0]
    lrec = latest_signal.iloc[0]
    lxup = int(lrec['xup_pos'])
    lxdown = int(lrec['xdown_pos'])
    lopen = "%.0f" % lrec['open']
    lhigh = "%.0f" % lrec['high']
    llow = "%.0f" % lrec['low']
    lclose = "%.0f" % lrec['close']
    lmacd = "%.2f" % lrec['macd']
    lemas = "%.2f" % lrec['emaSmooth']
    lskslow = "%.2f" % lrec['k_slow']
    lsdslow = "%.2f" % lrec['d_slow']
    lema25 = "%.2f" % lrec['ema25']

    print(signals[['open', 'close', 'nopen', 'ema25', 'xup_pos', 'xdown_pos']].to_string())
    print(latest_signal[['open', 'close', 'nopen', 'ema25', 'xup_pos', 'xdown_pos']].to_string())
    
    message_tmpl = "<b>" + u'\U0001F514' + " %s: \nMA Strategy X%s%s</b>\n<i>at %s%s</i>"
    message_nil_tmpl = "%s: NO MA Strategy Alert at %s"
    signals_list = ["<b>OPEN:</b> " + lopen
                    , "<b>HIGH:</b> " + lhigh
                    , "<b>LOW:</b> " + llow
                    , "<b>CLOSE:</b> " + lclose
                    , "<b>MA Signal:</b> " + lema25
                    #, "<b>MACD:</b> " + lmacd
                    #, "<b>emaSmooth:</b> " + lemas
                    #, "<b>STOC:</b> " + lskslow + "/" + lsdslow
                    , "<b>TS:</b> " + datetime.datetime.now().strftime("%H:%M:%S") + "HKT"
                    ]
    signals_stmt = EL.join(signals_list)
    message = ""    
    
    if (lxup):
        message = (message_tmpl % (title, "Up", u'\U0001F332', lts, "HKT"))
        message = message + DEL + signals_stmt + EL
    elif (lxdown):
        message = (message_tmpl % (title, "Down", u'\U0001F53B', lts, "HKT"))
        message = message + DEL + signals_stmt + EL
    else:
        print(message_nil_tmpl % (title, lts))        
       
    if (message):
        print(message)
        bot_sender.broadcast_list(message, "telegram-pt")
    
def main(args):
    
    start_time = time.time()

    if (len(args) > 1 and args[1] == "gen_alert"):
        gen_alert("MHI")
    else:
        symbol = "MHI"
        #duration = "3 Y"
        duration = "2 M"        
        period = "1 hour"
        current_mth = datetime.datetime.today().strftime('%Y%m')
        #current_mth = "201802"
        title = symbol + "@" + period + " (" + current_mth + ")"
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
        run_strat(title, hist_data)
    
    print("Time elapsed: " + "%.3f" % (time.time() - start_time) + "s")    

if __name__ == "__main__":
    main(sys.argv) 
