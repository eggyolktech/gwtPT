#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb

from gwt_pt.datasource import ibkr 
from gwt_pt.telegram import bot_sender
from gwt_pt.charting import btplot

import time
import datetime
import logging, sys

LOGFILE_ENABLED = False

if (os.name == 'nt'):
    logfile = 'C:\\Users\\Hin\\eggyolktech\\gwtPT\\gwt_pt\\log\\trade_executor.log'
else:
    logfile = '/app/gwtPT/gwt_pt/log/trade_executor_%s.log' % datetime.datetime.today().strftime('%m%d-%H%M%S')

logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger()

if LOGFILE_ENABLED:
    sys.stderr.write = lambda s: logger.error(s)
    sys.stdout.write = lambda s: logger.info(s)

EL = "\n"
DEL = "\n\n"

MONITOR_PERIOD = 20
SLEEP_PERIOD = 8

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

def trade_monitor_hkfe(symbol="MHI"):     
    
    duration = "3 D"        
    period = "1 min"
    current_mth = get_contract_month()
    #current_mth = "201802"
    title = symbol + "@" + period + " (Contract: " + current_mth + ")"
    print("Checking on " + title + " ......")

    historic_data = ibkr.get_hkfe_data(current_mth, symbol, duration, period)
    
    if (not historic_data):
        print("Historic Data is empty!!!")
        return

    # Data pre-processing
    bars = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    bars.set_index('datetime', inplace=True)
    bars.index = pd.to_datetime(bars.index)
    
    print(bars.to_string())
    
    message = ""    
    
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
        print(message_nil_tmpl % (title, lts)) '''       
       
    if (message):
        print(message)
        bot_sender.broadcast_list(message, "telegram-pt")

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

    trade_monitor_hkfe()
    
    print("Time elapsed: " + "%.3f" % (time.time() - start_time) + "s")    

if __name__ == "__main__":
    main(sys.argv) 
