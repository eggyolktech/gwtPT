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
    logfile = 'C:\\Users\\Hin\\eggyolktech\\gwtPT\\gwt_pt\\log\\mkt_open_reversal_strat.log'
else:
    logfile = '/app/gwtPT/gwt_pt/log/mkt_open_reversal_strat_%s.log' % datetime.datetime.today().strftime('%m%d-%H%M%S')

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

GAP_THRESHOLD = 100

LAST_TDAY_DICT = { 
    'Jan-17': 26,
    'Feb-17': 27,
    'Mar-17': 30,
    'Apr-17': 27,
    'May-17': 29,
    'Jun-17': 29,
    'Jul-17': 28,
    'Aug-17': 30,
    'Sep-17': 28,
    'Oct-17': 30,
    'Nov-17': 29,
    'Dec-17': 28,
    'Jan-18': 30,
    'Feb-18': 27,
    'Mar-18': 28,
    'Apr-18': 27,
    'May-18': 30,
    'Jun-18': 28,
    'Jul-18': 30,
    'Aug-18': 30,
    'Sep-18': 27,
    'Oct-18': 30,
    'Nov-18': 29,
    'Dec-18': 28
}

class mkt_open_reversal_strategy(strategy):
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

class mkt_open_reversal_portfolio(portfolio):
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
    
    strats = mkt_open_reversal_strategy(symbol, bars, 25)
    signals = strats.generate_signals()
    
    portfolio = mkt_open_reversal_portfolio(symbol, bars, signals, initial_capital=100000.0)
    pf = portfolio.backtest_portfolio()
    
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
    
    duration = "2 M"        
    period = "5 mins"
    contract_mth = get_contract_month()
    title = symbol + "@" + period + " (" + contract_mth + ")"
    print("Checking on " + title + " ......")
    time.sleep(5)

    historic_data = ibkr.get_hkfe_data(contract_mth, symbol, duration, period)
    
    if (not historic_data):
        print("Historic Data is empty!!!")
        return

    # Data pre-processing
    bars = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    bars.set_index('datetime', inplace=True)
    bars.index = pd.to_datetime(bars.index)
    
    # get today time    
    now = datetime.datetime.now()
    mkt_open_str = now.strftime('%Y-%m-%d 09:20:00')
    
    # test data
    #mkt_open_str = '2018-03-29 09:20:00'
    
    # get mkt open bars
    mkt_open_bars = (bars.loc[bars.index <= mkt_open_str]).tail(3)
   
    last_bar = mkt_open_bars.tail(1)
    last_2nd_bar = mkt_open_bars.tail(2).head(1)
    last_3rd_bar = mkt_open_bars.tail(3).head(1)
    
    print(last_bar)
    print(last_2nd_bar)
    print(last_3rd_bar)
    
    signal_gap = 0
    signal_change = 0
    signal_price = 0
    
    if (
            last_bar.tail(1).index == mkt_open_str 
            and "09:15" in str(last_2nd_bar.tail(1).index) 
            and "16:25" in str(last_3rd_bar.tail(1).index)
        ):
        print("Processing Mkt Open bar %s ......" % mkt_open_str )
        last_mkt_close = last_3rd_bar.iloc[0]['close']
        today_mkt_open = last_2nd_bar.iloc[0]['open']
        
        print("Last Mkt Close %s, Today Mkt Open %s" % (last_mkt_close, today_mkt_open))
        
        signal_gap = today_mkt_open - last_mkt_close
        
        if abs(signal_gap) >= GAP_THRESHOLD:
            print("Gap threshold limit satisfied [%s]" % signal_gap)
        else:
            print("Gap threshold limit NOT satisfied [%s]" % signal_gap)
            return
        
        signal_change = last_2nd_bar.iloc[0]['close'] - last_2nd_bar.iloc[0]['open']
        
        if (signal_gap > 0 and signal_change < 0):
            print("Upward Gap and Reversal (-ve) identified")
            signal_price = last_2nd_bar.iloc[0]['low']
        elif (signal_gap < 0 and signal_change > 0):
            print("Downward Gap and Reversal (+ve) identified")
            signal_price = last_2nd_bar.iloc[0]['high']
        else:
            print("NOT hitting any reversal scenario!")
            return
    else:
        print("No Mkt Open bar is found, terminate!")
        return
    
    #strats = mkt_open_reversal_strategy(symbol, bars, 25)
    #signals = strats.generate_signals()
    
    '''latest_signal = signals.iloc[-2:].head(1)
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
        print(message_nil_tmpl % (title, lts))'''     
    
    message = ""
    
    if (signal_change != 0 and signal_price != 0):
    
        message = "Reversal Strategy Monitor \n@ %s" % mkt_open_str 
        signals_list = ["<b>Gap:</b> " + str(signal_gap)
                        , "<b>Mkt Open Change:</b> " + str(signal_change)
                        , "<b>Reversal Price:</b> " + str(signal_price)
                        , "<b>TS:</b> " + datetime.datetime.now().strftime("%H:%M:%S") + "HKT"
                        ]
        signals_stmt = EL.join(signals_list)
        message = message + DEL + signals_stmt + EL
        
    if (message):
        print(message)
        bot_sender.broadcast_list(message, "telegram-chat-test")        
        #bot_sender.broadcast_list(message, "telegram-pt")

def get_contract_month():

    now = datetime.datetime.now()
    later = now.replace(day=1).replace(month=now.month+1)
    
    cur_mth_str = now.strftime('%Y%m')
    next_mth_str = later.strftime('%Y%m')

    days = int(now.strftime('%d'))
    cur_mth_key = now.strftime('%b-%y')
    print("Days now %s, curMth %s, LastTDay %s" % (days, cur_mth_key, LAST_TDAY_DICT[cur_mth_key]))
    
    if (LAST_TDAY_DICT[cur_mth_key] and LAST_TDAY_DICT[cur_mth_key] <=  days):
        print("Use " + next_mth_str)
        return next_mth_str
    else:
        print("Use " + cur_mth_str)
        return cur_mth_str
    
def main(args):
    
    start_time = time.time()

    if (len(args) > 1 and args[1] == "gen_alert"):
        gen_alert("MHI")
    else:
        symbol = "MHI"
        #duration = "3 Y"
        duration = "2 M"        
        period = "5 mins"
        contract_mth = get_contract_month()
        #contract_mth = datetime.datetime.now().strftime('%Y%m')
        title = symbol + "@" + period + " (" + contract_mth + ")"
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(contract_mth, symbol, duration, period)
        print(hist_data)
        #run_strat(title, hist_data)
    
    print("Time elapsed: " + "%.3f" % (time.time() - start_time) + "s")    

if __name__ == "__main__":
    main(sys.argv) 
