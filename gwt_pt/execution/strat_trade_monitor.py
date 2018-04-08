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

def trade_monitor_hkfe(json_args):     

    symbol = json_args['symbol']
    duration = json_args['duration']
    period = json_args['period']
    signal = json_args['signal']

    signal_gap = signal['gap']
    signal_date = signal['date']
    signal_trigger = "%.0f" % signal['trigger']
    
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
    
    print(bars.tail())
    
    latest_bar = bars.iloc[-2:].head(1)
    lts = str(latest_bar.index[0])
    ldt = str(latest_bar.index[0]).split()[0]
    lrec = latest_bar.iloc[0]
    lopen = "%.0f" % lrec['open']
    lhigh = "%.0f" % lrec['high']
    llow = "%.0f" % lrec['low']
    lclose = "%.0f" % lrec['close']    
    
    print("\nSignal:[\n%s]" % signal)
    print("\nLast Bar:[\n%s]" % latest_bar)
    print("Last Bar Date: [%s]" % ldt)
    
    # Test case {'date': '2018-04-06', 'gap': 'UP', 'trigger': 30064.0}
    
    message = "" 
    message_tmpl = "<b>" + u'\U0001F514' + " GAP %s Trade Trigger Hit : %s %s %s</b>\n<i>at %s</i>"
    
    if (ldt == signal_date):
        print("Signal Date Check Passed [%s / %s]" % (ldt, signal_date))
        if (signal_gap == "UP"):
            if (lclose < signal_trigger):
                print("GAP UP Trade Trigger Hit %s < %s" % (lclose, signal_trigger))
                message = message_tmpl %(signal_gap, lclose, "&lt;", signal_trigger, lts)
            else:
                print("GAP UP Trade Trigger NOT Hit %s < %s" % (lclose, signal_trigger))
        elif (signal_gap == "DOWN"):
            if (lclose > signal_trigger):
                print("GAP DOWN Trade Trigger Hit %s > %s" % (lclose, signal_trigger))
                message = message_tmpl %(signal_gap, lclose, "&gt;",  signal_trigger, lts)
            else:
                print("GAP DOWN Trade Trigger NOT Hit %s < %s" % (lclose, signal_trigger))
        else:
            print("Signal Gap is invalid: [%s]" % signal_gap)  
    else:
        print("Signal Date Check Failed [%s / %s]" % (ldt, signal_date))
    
       
    if (message):
        print(message)
        #bot_sender.broadcast_list(message, "telegram-chat-test")   
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
        
def strat_scheduler(function, json_args, cycle=10.0, iterations=10):

    starttime=time.time()
    
    print("Scheduler starts at %s" % time.ctime(int(starttime)))
    runcount = 0
    while (runcount < iterations):
        print("Iteration %s runs at %s" % (runcount+1, time.ctime(int(time.time()))))
        function( json_args )
        time.sleep(cycle - ((time.time() - starttime) % cycle))
        runcount = runcount + 1

def testfun(json_args={}):

    print("tick: " + str(json_args))
      
def main(args):
    
    start_time = time.time()
    
    json_args = {"symbol": "MHI", "duration": "28800 S", "period": "1 min", "signal": {"date": "2018-04-06", "gap": "UP", "trigger": 30064.0}}
    strat_scheduler(trade_monitor_hkfe, json_args, 60.0, 3)
    
    print("Time elapsed: " + "%.3f" % (time.time() - start_time) + "s")    

if __name__ == "__main__":
    main(sys.argv) 
