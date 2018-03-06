#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb
from gwt_pt.common.indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

from gwt_pt.datasource import ibkr 
from gwt_pt.telegram import bot_sender
from gwt_pt.charting import frameplot

import time
import datetime

EL = "\n"
DEL = "\n\n"

STOC_UPPER_LIMIT = 75
STOC_LOWER_LIMIT = 25
STOC_WINDOW = 16
MACD_WINDOW = 12 
MACDSTOC_WINDOW = 11
#MACDSTOC_UPPER_LIMIT = 95
#MACDSTOC_LOWER_LIMIT = 5
MACDSTOC_UPPER_LIMIT = 0
MACDSTOC_LOWER_LIMIT = 100
MACDSTOC_THRESHOLD = 1.0

MONITOR_PERIOD = 20
SLEEP_PERIOD = 8

def get_alert(title, historic_data): 
    
    # Set float format
    #pd.options.display.float_format = "{:.9f}".format
    
    # Data pre-processing
    historic_df = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    historic_df.set_index('datetime', inplace=True)
    historic_df.index = pd.to_datetime(historic_df.index)

    signals = pd.DataFrame(index=historic_df.index)
    signals['open'] = historic_df['open']    
    signals['high'] = historic_df['high']
    signals['low'] = historic_df['low']
    signals['close'] = historic_df['close']
    signals["ema25"] = EMA(signals, 'close', 25)

    # MACD
    macd = MACD(historic_df['close'])
    signals = pd.concat([signals, macd], axis=1)

    # Slowstoc
    kslow, dslow = SLOWSTOC(historic_df, 'low', 'high', 'close', STOC_WINDOW, 6, False)
    signals = pd.concat([signals, kslow, dslow], axis=1)

    # Super Macdstoc
    skslow, sdslow = FASTSTOC(signals, "macd", "macd", "macd", MACDSTOC_WINDOW, 3, False)
    skslow = skslow.rename(columns = {'k_fast':'sk_slow'})
    sdslow = sdslow.rename(columns = {'d_fast':'sd_slow'})
    signals = pd.concat([signals, skslow, sdslow], axis=1)
    
    # Xover Mark
    signals['signal_stoc_xup'] = 0.0
    signals['signal_stoc_xdown'] = 0.0
    signals['signal_macd_xup'] = 0.0
    signals['signal_macd_xdown'] = 0.0
    signals['signal_macdstoc_xup'] = 0.0
    signals['signal_macdstoc_xdown'] = 0.0    

    ###############################################################################
    ## Create a 'signal' for Slow Stoc cross over <=25    
    if (len(signals) >= STOC_WINDOW):
        signals['signal_stoc_xup'][STOC_WINDOW:] = np.where(
            (signals['k_slow'][STOC_WINDOW:] > signals['d_slow'][STOC_WINDOW:])
            & (signals['k_slow'][STOC_WINDOW:] <= STOC_LOWER_LIMIT)
            , 1.0, 0.0)
    else:
        signals['signal_stoc_xup'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['stoc_xup_positions'] = signals['signal_stoc_xup'].diff()
    signals.loc[signals.stoc_xup_positions == -1.0, 'stoc_xup_positions'] = 0.0    
    
    ###############################################################################
    ## Create a 'signal' for Macdstoc cross up <=5
    if (len(signals) >= MACDSTOC_WINDOW):
        signals['signal_macdstoc_xup'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] > signals['sd_slow'][MACDSTOC_WINDOW:] + MACDSTOC_THRESHOLD)
            & (signals['sd_slow'][MACDSTOC_WINDOW:] <= MACDSTOC_LOWER_LIMIT)
            , 1.0, 0.0)
    else:
        signals['signal_macdstoc_xup'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['macdstoc_xup_positions'] = signals['signal_macdstoc_xup'].diff()
    signals.loc[signals.macdstoc_xup_positions == -1.0, 'macdstoc_xup_positions'] = 0.0
 
    ## Create a 'signal' for Macdstoc cross down >=95
    if (len(signals) >= MACDSTOC_WINDOW):
        signals['signal_macdstoc_xdown'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] < signals['sd_slow'][MACDSTOC_WINDOW:] - MACDSTOC_THRESHOLD)
            & (signals['sd_slow'][MACDSTOC_WINDOW:] >= MACDSTOC_UPPER_LIMIT)
            , 1.0, 0.0)
    else:
        signals['signal_macdstoc_xdown'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['macdstoc_xdown_positions'] = signals['signal_macdstoc_xdown'].diff()
    signals.loc[signals.macdstoc_xdown_positions == -1.0, 'macdstoc_xdown_positions'] = 0.0
    
    latest_signal = signals.tail(1)
    lts = latest_signal.index[0]
    lxup = int(latest_signal.iloc[0]['macdstoc_xup_positions'])
    lxdown = int(latest_signal.iloc[0]['macdstoc_xdown_positions'])
    lkslow = "%.2f" % latest_signal.iloc[0]['sk_slow']
    ldslow = "%.2f" % latest_signal.iloc[0]['sd_slow']
    
    lopen = "%.4f" % latest_signal.iloc[0]['open']
    lhigh = "%.4f" % latest_signal.iloc[0]['high']
    llow = "%.4f" % latest_signal.iloc[0]['low']
    lclose = "%.4f" % latest_signal.iloc[0]['close']
    lmacd = "%.5f" % latest_signal.iloc[0]['macd']
    lemas = "%.5f" % latest_signal.iloc[0]['emaSmooth']
    lskslow = "%.2f" % latest_signal.iloc[0]['k_slow']
    lsdslow = "%.2f" % latest_signal.iloc[0]['d_slow']
           
    message_tmpl = "<b>" + u'\U0001F514' + "%s: \nMACDSTOC X%s</b>\n<i>at %s</i>"
    signals_list = ["<b>OPEN:</b> " + lopen
                    , "<b>HIGH:</b> " + lhigh
                    , "<b>LOW:</b> " + llow
                    , "<b>CLOSE:</b> " + lclose
                    , "<b>MACD:</b> " + lmacd
                    , "<b>emaSmooth:</b> " + lemas
                    , "<b>STOC_K:</b> " + lskslow
                    , "<b>STOC_D:</b> " + lsdslow
                    , "<b>MSTOC_K:</b> " + lkslow
                    , "<b>MSTOC_D:</b> " + ldslow
                    ]
    signals_stmt = EL.join(signals_list)
    message_nil_tmpl = "%s: NO MACDSTOC Alert at %s"
    message = ""    
    
    if (lxup):
        message = (message_tmpl % (title, "Up", lts))
        filepath = frameplot.plot_macdstoc_signals(historic_df, signals, title, True)
        filename = filepath.split("/")[-1]
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Chart</a>)" % filename 
        message = message + DEL + signals_stmt
    elif (lxdown):
        message = (message_tmpl % (title, "Down", lts))
        filepath = frameplot.plot_macdstoc_signals(historic_df, signals, title, True)
        filename = filepath.split("/")[-1]
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Chart</a>)" % filename
        message = message + DEL + signals_stmt
    else:
        print(message_nil_tmpl % (title, lts))
        
    if (message):
        bot_sender.broadcast(message, False)
    
    #print(signals.info())
    #print(signals.to_string())
    #print(signals.tail())
    print(signals[['sk_slow','sd_slow', 'macdstoc_xup_positions', 'macdstoc_xdown_positions']].tail().to_string())
    #print(signals.tail().to_string())

def main():
    
    passage = "Generation of Macdstoc Alert............."
    print(passage)
    
    CURRENCY_PAIR = ["EUR/USD", 
                    "GBP/USD", 
                    "USD/JPY", 
                    "EUR/JPY", 
                    "GBP/JPY", 
                    #"EUR/GBP", 
                    "USD/CAD", 
                    "AUD/USD", 
                    "NZD/USD", 
                    #"USD/CHF", 
                    #"AUD/NZD", 
                    #"USD/NOK", 
                    #"USD/SEK", 
                    "USD/SGD"]
    
    METAL_PAIR = ["XAGUSD", "XAUUSD"]
    HKFE_PAIR = ["HSI"]

    for cur in CURRENCY_PAIR:
    
        symbol = cur.split("/")[0]
        currency = cur.split("/")[1]
        duration = "16 D"
        period = "1 hour"
        title = symbol + "/" + currency + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_fx_data(symbol, currency, duration, period)
        get_alert(title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Metal Pair
    for cur in METAL_PAIR:

        symbol = cur
        duration = "16 D"
        period = "1 hour"
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_metal_data(symbol, duration, period)
        get_alert(title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Futures Pair
    for cur in HKFE_PAIR:

        symbol = cur
        duration = "16 D"
        period = "1 hour"
        current_mth = datetime.datetime.today().strftime('%Y%m')
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
        get_alert(title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)

if __name__ == "__main__":
    main() 
