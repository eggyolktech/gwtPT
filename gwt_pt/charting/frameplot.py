#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb
from gwt_pt.common.indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker

from gwt_pt.datasource import ibkr 

import time
import datetime

STOC_UPPER_LIMIT = 75
STOC_LOWER_LIMIT = 25
STOC_WINDOW = 16
MACD_WINDOW = 12 
MACDSTOC_WINDOW = 11
MACDSTOC_UPPER_LIMIT = 95
MACDSTOC_LOWER_LIMIT = 5

MONITOR_PERIOD = 20

def plot(historic_data, title, isFile=False): 
    
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
    kslow, dslow = SLOWSTOC(historic_df, 'low', 'high', 'close', STOC_WINDOW, 8, False)
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
            (signals['sk_slow'][MACDSTOC_WINDOW:] > signals['sd_slow'][MACDSTOC_WINDOW:])
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
            (signals['sk_slow'][MACDSTOC_WINDOW:] < signals['sd_slow'][MACDSTOC_WINDOW:])
            & (signals['sd_slow'][MACDSTOC_WINDOW:] >= MACDSTOC_UPPER_LIMIT)
            , 1.0, 0.0)
    else:
        signals['signal_macdstoc_xdown'] = 0.0
    
    ## Take the difference of the signals in order to generate actual trading orders
    signals['macdstoc_xdown_positions'] = signals['signal_macdstoc_xdown'].diff()
    signals.loc[signals.macdstoc_xdown_positions == -1.0, 'macdstoc_xdown_positions'] = 0.0
 
    #print(signals.info())
    #print(signals.to_string())
    #print(signals.tail())
    print(signals[['sk_slow','sd_slow', 'signal_macdstoc_xup', 'signal_macdstoc_xdown']].to_string())

    fig = plt.figure(figsize=(15, 20))
    fig.patch.set_facecolor('white')     # Set the outer colour to white
    fig.suptitle(title, fontsize=12, color='grey')

    plt.style.use('bmh')
    #plt.style.use('ggplot')
    #plt.style.use('fivethirtyeight')

    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = 'Ubuntu'
    plt.rcParams['font.monospace'] = 'Ubuntu Mono'
    plt.rcParams['font.size'] = 8

    plt.rcParams['axes.labelsize'] = 8
    plt.rcParams['axes.labelweight'] = 'bold'
    plt.rcParams['axes.titlesize'] = 9
    plt.rcParams['axes.titleweight'] = 'bold'
    plt.rcParams['xtick.labelsize'] = 8
    plt.rcParams['ytick.labelsize'] = 8
    plt.rcParams['lines.linewidth'] = 1
    plt.rcParams['legend.fontsize'] = 8
    plt.rcParams['figure.facecolor'] = '#fffff9'
    plt.rcParams['figure.titlesize'] = 8

    #ax1 = fig.add_subplot(211,  ylabel='Price in $')
    ax1 = plt.subplot2grid((10, 1), (0, 0), rowspan=4, ylabel='Price in $')

    N = len(historic_df)
    df_idx = np.arange(N) # the evenly spaced plot indices   
    
    def format_date(x, pos=None):
        thisind = np.clip(int(x+0.5), 0, N-1)
        return historic_df.index[thisind].strftime('%Y-%m-%d')    
    
    ax1.plot(df_idx, historic_df['close'], color='r', lw=1.)
    ax1.plot(df_idx, signals['ema25'], lw=1.)
    
    # plot stoc xup
    #stoc_xup_idx = signals.ix[signals.stoc_xup_positions == 1.0].index
    #df_stoc_xup_idx = [signals.index.get_loc(idx) for idx in stoc_xup_idx]
    #ax1.plot(df_stoc_xup_idx, signals.low[signals.stoc_xup_positions == 1.0], '^', markersize=7, color='m')

    # plot macdstoc xup / xdown
    macdstoc_xup_idx = signals.ix[signals.macdstoc_xup_positions == 1.0].index
    df_macdstoc_xup_idx = [signals.index.get_loc(idx) for idx in macdstoc_xup_idx]
    ax1.plot(df_macdstoc_xup_idx, signals.low[signals.macdstoc_xup_positions == 1.0], '^', markersize=7, color='m')

    macdstoc_xdown_idx = signals.ix[signals.macdstoc_xdown_positions == 1.0].index
    df_macdstoc_xdown_idx = [signals.index.get_loc(idx) for idx in macdstoc_xdown_idx]
    ax1.plot(df_macdstoc_xdown_idx, signals.high[signals.macdstoc_xdown_positions == 1.0], 'v', markersize=7, color='r')
    
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    
    #historic_df['close'].plot(ax=ax1, color='r', lw=1.)
    #signals[['ema25']].plot(ax=ax1, lw=1.)

    # Set the tick labels font
    for label in (ax1.get_xticklabels() + ax1.get_yticklabels()):
        label.set_fontname('Arial')
        label.set_fontsize(8)
        label.set_rotation(0)
        
    #myFmt = DateFormatter("%Y-%m-%d %H:%M:%S")
    #ax1.xaxis.set_major_formatter(myFmt)
    #ax1.set_xticks(np.arange(len(historic_df['close'])))
    #ax1.axes.xaxis.label.set_visible(False)
    ax1.grid(True)

    # Plot the Slow Stoc
    ax2 = plt.subplot2grid((10, 1), (4, 0), rowspan=2, ylabel='Slow Stoc')
    ax2.axes.xaxis.set_visible(False)
    
    ax2.plot(df_idx, signals[['k_slow', 'd_slow']], lw=1.)
    
    #signals[['k_slow', 'd_slow']].plot(ax=ax2, lw=1., grid=True, legend=None)

    ax2.fill_between(df_idx, 90, 100, facecolor='red', alpha=.2, interpolate=True)
    ax2.fill_between(df_idx, 0, 10, facecolor='red', alpha=.2, interpolate=True)

    ax2.axhline(y = 90, color = "brown", lw = 0.5)
    ax2.axhline(y = 10, color = "red", lw = 0.5)    

    # Plot the MACD
    ax3 = plt.subplot2grid((10, 1), (6, 0), rowspan=2, ylabel='MACD')
    ax3.axes.xaxis.set_visible(False)
    
    ax3.plot(df_idx, signals[['macd', 'emaSmooth']], lw=1.)
    ax3.plot(df_idx, signals['divergence'], lw=0.1)

    #signals[['macd', 'emaSmooth']].plot(x=signals.index, ax=ax3, lw=1., grid=True, legend=None)
    #signals[['divergence']].plot(x=signals.index, ax=ax3, lw=0.1, grid=True, legend=None)

    ax3.fill_between(df_idx, signals['divergence'], 0,
                where=signals['divergence'] >= 0,
                facecolor='blue', alpha=.8, interpolate=True)
                
    ax3.fill_between(df_idx, signals['divergence'], 0,
                where=signals['divergence'] < 0,
                facecolor='red', alpha=.8, interpolate=True)

    # Plot the super MACD            
    ax4 = plt.subplot2grid((10, 1), (8, 0), rowspan=2, ylabel='Macdstoc')

    ax4.axes.xaxis.set_visible(False)
    
    ax4.plot(df_idx, signals[['sk_slow', 'sd_slow']], lw=1.)
    #signals[['sk_slow', 'sd_slow']].plot(ax=ax4, lw=1., grid=True, legend=None)

    #ax4.fill_between(signals.index, 95, 100, facecolor='red', alpha=.2, interpolate=True)
    #ax4.fill_between(signals.index, 0, 5, facecolor='red', alpha=.2, interpolate=True)
    
    # plot macdstoc xup / xdown
    ax4.plot(df_macdstoc_xup_idx, signals.sk_slow[signals.macdstoc_xup_positions == 1.0], '^', markersize=7, color='m')
    ax4.plot(df_macdstoc_xdown_idx, signals.sk_slow[signals.macdstoc_xdown_positions == 1.0], 'v', markersize=7, color='r')    
    
    ax4.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    ax4.axes.xaxis.set_visible(True)

    # Plot the figure
    plt.tight_layout(w_pad=3, h_pad=3)
    if (isFile):
        if not os.name == 'nt':
            tstr = str(int(round(time.time() * 1000)))
            tstr = "42"
            chartpath = "/var/www/eggyolk.tech/html/gwtpt/" + 'pchart' + tstr + '.png'
        else:
            chartpath = "C:\\Temp\\gwtpt\\" + 'pchart' + str(int(round(time.time() * 1000))) + '.png'
        
        plt.savefig(chartpath, bbox_inches='tight')
        return chartpath 
    else:
        plt.show()

def main():
    
    passage = "Test............."
    print(passage)
    
    symbol = "GBP"
    currency = "USD"
    duration = "2 M"
    period = "4 hours"
    title = symbol + "/" + currency + " " + period

    print(plot(ibkr.get_data(symbol, currency, duration, period), title, True))

if __name__ == "__main__":
    main() 
