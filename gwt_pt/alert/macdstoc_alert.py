#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb
from gwt_pt.common.indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

from gwt_pt.datasource import ibkr 
from gwt_pt.telegram import bot_sender
from gwt_pt.charting import frameplot
from gwt_pt.redis import redis_pool

import time
import datetime
import logging, sys

if (os.name == 'nt'):
    logfile = 'C:\\Users\\Hin\\eggyolktech\\gwtPT\\gwt_pt\\log\\macdstoc_alert.log'
    testMode = True
else:
    logfile = '/app/gwtPT/gwt_pt/log/macdstoc_alert_%s.log' % datetime.datetime.today().strftime('%m%d-%H%M%S')
    testMode = False
    #sys.stderr.write = lambda s: logger.error(s)
    #sys.stdout.write = lambda s: logger.info(s)

logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger()

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

#CURRENCY_PAIR = ["EUR/USD","USD/JPY"]
METAL_PAIR = ["XAGUSD", "XAUUSD"]
HKFE_PAIR = ["HSI"]

def write_signals_log(signals_str):

    tstr = str(int(round(time.time() * 1000)))
    if not os.name == 'nt':        
        logpath = "/var/www/eggyolk.tech/html/gwtpt/" + 'signals' + tstr + '.txt'
    else:
        logpath = "C:\\Temp\\gwtpt\\" + 'signals' + tstr + '.txt'
        
    with open(logpath, "w") as text_file:
        text_file.write(signals_str)
        
    return logpath

def gen_signal(historic_df):

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
    signals['signal_xup'] = 0.0
    signals['signal_xdown'] = 0.0    
    signals['signal_sxup'] = 0.0
    signals['signal_sxdown'] = 0.0  

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
        signals['signal_xup'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] > signals['sd_slow'][MACDSTOC_WINDOW:] + MACDSTOC_THRESHOLD)
            & (signals['sd_slow'][MACDSTOC_WINDOW:] <= MACDSTOC_LOWER_LIMIT)
            , 1.0, 0.0)
            
        signals['signal_sxup'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] == 100) 
            & (signals['sd_slow'][MACDSTOC_WINDOW:] == 100)
            , 1.0, 0.0)
    else:
        signals['signal_xup'] = 0.0
        signals['signal_sxup'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['xup_positions'] = signals['signal_xup'].diff()
    signals.loc[signals.xup_positions == -1.0, 'xup_positions'] = 0.0
    signals['sxup_positions'] = signals['signal_sxup'].diff()
    signals.loc[signals.sxup_positions == -1.0, 'sxup_positions'] = 0.0
 
    ## Create a 'signal' for Macdstoc cross down >=95
    if (len(signals) >= MACDSTOC_WINDOW):
        signals['signal_xdown'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] < signals['sd_slow'][MACDSTOC_WINDOW:] - MACDSTOC_THRESHOLD)
            & (signals['sd_slow'][MACDSTOC_WINDOW:] >= MACDSTOC_UPPER_LIMIT)
            , 1.0, 0.0)
            
        signals['signal_sxdown'][MACDSTOC_WINDOW:] = np.where(
            (signals['sk_slow'][MACDSTOC_WINDOW:] == 0) 
            & (signals['sd_slow'][MACDSTOC_WINDOW:] == 0)
            , 1.0, 0.0)
    else:
        signals['signal_xdown'] = 0.0
        signals['signal_sxdown'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['xdown_positions'] = signals['signal_xdown'].diff()
    signals.loc[signals.xdown_positions == -1.0, 'xdown_positions'] = 0.0
    signals['sxdown_positions'] = signals['signal_sxdown'].diff()
    signals.loc[signals.sxdown_positions == -1.0, 'sxdown_positions'] = 0.0
    
    ## Aggregrate the special case + normal case together
    signals['xup_positions'] = signals['xup_positions'] + signals['sxup_positions']
    signals['xdown_positions'] = signals['xdown_positions'] + signals['sxdown_positions']
    
    return signals
 
def format_hist_df(historic_data):

    # Set float format
    #pd.options.display.float_format = "{:.9f}".format
    
    # Data pre-processing
    historic_df = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    historic_df.set_index('datetime', inplace=True)
    historic_df.index = pd.to_datetime(historic_df.index)
    
    return historic_df
 
def get_alert(cur, title, historic_data): 
    
    historic_df = format_hist_df(historic_data)
    signals = gen_signal(historic_df)
    
    latest_signal = signals.tail(1)
    lts = latest_signal.index[0]
    lxup = int(latest_signal.iloc[0]['xup_positions'])
    lxdown = int(latest_signal.iloc[0]['xdown_positions'])
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
    
    message_tmpl = "<b>" + u'\U0001F514' + "%s: \nMACDSTOC X%s</b>\n<i>at %s%s</i>"
    signals_list = ["<b>OPEN:</b> " + lopen
                    , "<b>HIGH:</b> " + lhigh
                    , "<b>LOW:</b> " + llow
                    , "<b>CLOSE:</b> " + lclose
                    , "<b>MACD:</b> " + lmacd
                    , "<b>emaSmooth:</b> " + lemas
                    , "<b>STOC:</b> " + lskslow + "/" + lsdslow
                    , "<b>MSTOC:</b> " + lkslow + "/" + ldslow
                    , "<b>TS:</b> " + datetime.datetime.now().strftime("%H:%M:%S") + "HKT"
                    ]
    signals_stmt = EL.join(signals_list)
    message_nil_tmpl = "%s: NO MACDSTOC Alert at %s"
    message = ""    
    
    #signals_log = signals[['open','high','low','close','ema25','divergence','emaSmooth','macd','k_slow','d_slow','sk_slow','sd_slow','xup_positions','xdown_positions']].tail(20).to_string()
    signals_log = signals[['sk_slow','sd_slow','xup_positions','xdown_positions','sxup_positions','sxdown_positions']].tail(20).to_string()
    #print(">>>>>>>>>>>>>>>>>> Get DS Key " + cur) 
    ds = redis_pool.getV("DS:" + cur)
    if (not ds):
        ds = ""
    else:
        ds = ds.decode()
        
    print(">>>>>>>>>>>>>>>>>> Daily Sig [" + cur + "]: " + str(lxup) + "/" + str(lxdown) + "/" + ds)
    if (lxup and "XUP" in ds):
        message = (message_tmpl % (title, "Up", lts, "GMT"))
        filepath = frameplot.plot_macdstoc_signals(historic_df, signals, title, True)
        filename = filepath.split("/")[-1]
        logname = write_signals_log(signals_log).split("/")[-1]
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Chart</a>)" % filename 
        message = message + DEL + signals_stmt + EL
        message = message + ("<b>DAILY:</b> %s" % ds) + EL
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Log</a>)" % logname
    elif (lxdown and "XDOWN" in ds):
        message = (message_tmpl % (title, "Down", lts, "GMT"))
        filepath = frameplot.plot_macdstoc_signals(historic_df, signals, title, True)
        filename = filepath.split("/")[-1]
        logname = write_signals_log(signals_log).split("/")[-1]
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Chart</a>)" % filename
        message = message + DEL + signals_stmt + EL
        message = message + ("<b>DAILY:</b> %s" % ds) + EL
        message = message + " (<a href='http://www.eggyolk.tech/gwtpt/%s' target='_blank'>Log</a>)" % logname
    else:
        print(message_nil_tmpl % (title, lts))
        
    if (message):
        bot_sender.broadcast(message, testMode)
    
    #print(signals.info())
    #print(signals.to_string())
    #print(signals.tail())
    #print(signals[['sk_slow','sd_slow', 'xup_positions', 'xdown_positions']].tail(20).to_string())
    print(signals_log)

def update_latest_pos(cur, signals):

    lsig = signals.loc[(signals['xup_positions'] == 1.0) | (signals['xdown_positions'] == 1.0)].tail(1)
    lrec = lsig.iloc[0]
    #print(lrec)
    ltime = lsig.index[0]
    ltime = str(ltime).split()[0]
    message = ""
    if (lrec['xup_positions']):
        message = ("%s XUP since %s" % (cur, ltime))
        redis_pool.setV("DS:" + cur, "XUP since %s" % ltime)
    else:
        message = ("%s XDOWN since %s" % (cur, ltime))
        redis_pool.setV("DS:" + cur, "XDOWN since %s" % ltime)
    
    print(message)
    return message

def alert_daily():    
    
    passage = "Generation of Macdstoc Hourly Alert............."
    print(passage)
    
    errorMessage = ""
    duration = "3 M"
    period = "1 day"
    
    dsl = []

    for cur in CURRENCY_PAIR:
    
        symbol = cur.split("/")[0]
        currency = cur.split("/")[1]
        title = symbol + "/" + currency + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_fx_data(symbol, currency, duration, period)
 
        historic_df = format_hist_df(hist_data)
        signals = gen_signal(historic_df)
        print(signals[['sk_slow','sd_slow','xup_positions','xdown_positions','sxup_positions','sxdown_positions']].tail(20).to_string())
        dsl.append(update_latest_pos(cur, signals))
        
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Metal Pair
    for cur in METAL_PAIR:

        symbol = cur
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_metal_data(symbol, duration, period)
        
        historic_df = format_hist_df(hist_data)
        signals = gen_signal(historic_df)
        dsl.append(update_latest_pos(cur, signals))
        
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Futures Pair
    for cur in HKFE_PAIR:

        symbol = cur
        current_mth = datetime.datetime.today().strftime('%Y%m')
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
 
        historic_df = format_hist_df(hist_data)
        signals = gen_signal(historic_df)
        dsl.append(update_latest_pos(cur, signals))

        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    message = "<b>Daily Macdstoc Signal</b>" + DEL
    message = message + EL.join(dsl)
    print(message)
    
    if (message):
        print(message)
        #bot_sender.broadcast(message, testMode)
    
def alert_hourly():

    passage = "Generation of Macdstoc Hourly Alert............."
    print(passage)
    
    errorMessage = ""
    duration = "16 D"
    period = "1 hour"
    
    for cur in CURRENCY_PAIR:
    
        symbol = cur.split("/")[0]
        currency = cur.split("/")[1]
        title = symbol + "/" + currency + "@" + period
        print("Checking on " + title + " ......")
        
        hist_data = ibkr.get_fx_data(symbol, currency, duration, period)

        if (not hist_data):
            hist_data = ibkr.get_fx_data(symbol, currency, duration, period)

        if (not hist_data):
            bot_sender.broadcast("ERROR: No Data returns for %s" % cur, testMode)
            return

        get_alert(cur, title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Metal Pair
    for cur in METAL_PAIR:

        symbol = cur
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_metal_data(symbol, duration, period)
        get_alert(cur, title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)
        
    # Futures Pair
    for cur in HKFE_PAIR:

        symbol = cur
        current_mth = datetime.datetime.today().strftime('%Y%m')
        title = symbol + "@" + period
        print("Checking on " + title + " ......")

        hist_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
        get_alert(cur, title, hist_data)
        print("Sleeping for " + str(SLEEP_PERIOD) + " seconds...")
        time.sleep(SLEEP_PERIOD)

def main(args):
    
    start_time = time.time()

    if (len(args) > 1 and args[1] == "alert_daily"):
        alert_daily()        
    else:
        alert_hourly()
    
    print("Time elapsed: " + "%.3f" % (time.time() - start_time) + "s")    

if __name__ == "__main__":
    main(sys.argv) 
