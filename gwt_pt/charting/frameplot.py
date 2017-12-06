
import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb
from gwt_pt.common.indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

from gwt_pt.datasource import ibkr 

import time
import datetime

def plot(historic_data, title, isFile=False): 
    
    # Data pre-processing
    historic_df = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    historic_df.set_index('datetime', inplace=True)
    historic_df.index = pd.to_datetime(historic_df.index)

    signals = pd.DataFrame(index=historic_df.index)
    signals['close'] = historic_df['close']
    signals["ema25"] = EMA(signals, 'close', 25)

    # MACD
    macd = MACD(historic_df['close'])
    signals = pd.concat([signals, macd], axis=1)

    # Slowstoc
    kslow, dslow = SLOWSTOC(historic_df, 'low', 'high', 'close', 16, 8, False)
    signals = pd.concat([signals, kslow, dslow], axis=1)

    # Super Macdstoc
    skslow, sdslow = FASTSTOC(signals, "macd", "macd", "macd", 10, 3, False)
    skslow = skslow.rename(columns = {'k_fast':'sk_slow'})
    sdslow = sdslow.rename(columns = {'d_fast':'sd_slow'})
    signals = pd.concat([signals, skslow, sdslow], axis=1)

    print(signals.info())
    print(signals.to_string())

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

    historic_df['close'].plot(ax=ax1, color='r', lw=1.)
    signals[['ema25']].plot(ax=ax1, lw=1.)

    # Set the tick labels font
    for label in (ax1.get_xticklabels() + ax1.get_yticklabels()):
        label.set_fontname('Arial')
        label.set_fontsize(8)
        label.set_rotation(0)

    #myFmt = DateFormatter("%Y-%m-%d %H:%M:%S")
    #ax1.xaxis.set_major_formatter(myFmt)
    #ax1.set_xticks(np.arange(len(historic_df['close'])))
    ax1.axes.xaxis.label.set_visible(False)
    ax1.grid(True)

    # Plot the Slow Stoc
    ax2 = plt.subplot2grid((10, 1), (4, 0), rowspan=2, ylabel='Slow Stoc')
    ax2.axes.xaxis.set_visible(False)
    signals[['k_slow', 'd_slow']].plot(ax=ax2, lw=1., grid=True, legend=None)

    ax2.fill_between(signals.index, 90, 100, facecolor='red', alpha=.2, interpolate=True)
    ax2.fill_between(signals.index, 0, 10, facecolor='red', alpha=.2, interpolate=True)

    ax2.axhline(y = 90, color = "brown", lw = 0.5)
    ax2.axhline(y = 10, color = "red", lw = 0.5)    

    # Plot the MACD
    ax3 = plt.subplot2grid((10, 1), (6, 0), rowspan=2, ylabel='MACD')
    ax3.axes.xaxis.set_visible(False)

    signals[['macd', 'emaSmooth']].plot(x=signals.index, ax=ax3, lw=1., grid=True, legend=None)
    signals[['divergence']].plot(x=signals.index, ax=ax3, lw=0.1, grid=True, legend=None)

    ax3.fill_between(signals.index, signals['divergence'], 0,
                where=signals['divergence'] >= 0,
                facecolor='blue', alpha=.8, interpolate=True)
                
    ax3.fill_between(signals.index, signals['divergence'], 0,
                where=signals['divergence'] < 0,
                facecolor='red', alpha=.8, interpolate=True)

    # Plot the super MACD            
    ax4 = plt.subplot2grid((10, 1), (8, 0), rowspan=2, ylabel='Macdstoc')

    ax4.axes.xaxis.set_visible(False)
    signals[['sk_slow', 'sd_slow']].plot(ax=ax4, lw=1., grid=True, legend=None)

    #ax4.fill_between(signals.index, 95, 100, facecolor='red', alpha=.2, interpolate=True)
    #ax4.fill_between(signals.index, 0, 5, facecolor='red', alpha=.2, interpolate=True)

    ax4.axes.xaxis.set_visible(False)

    # Plot the figure
    plt.tight_layout(w_pad=3, h_pad=3)
    if (isFile):
        if not os.name == 'nt':
            chartpath = "/tmp/gwtpt/" + 'gchart' + str(int(round(time.time() * 1000))) + '.png'
        else:
            chartpath = "C:\\Temp\\gwtpt\\" + 'gchart' + str(int(round(time.time() * 1000))) + '.png'
        
        plt.savefig(chartpath, bbox_inches='tight')
        return chartpath 
    else:
        plt.show()

def main():
    
    passage = "Test............."
    print(passage)
    
    symbol = "EUR"
    currency = "USD"
    duration = "2 M"
    period = "4 hours"
    title = symbol + "/" + currency + " " + period

    print(plot(ibkr.get_data(symbol, currency, duration, period), title, False))

if __name__ == "__main__":
    main() 
