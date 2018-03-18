#! /usr/bin/python

import numpy as np
import pandas as pd
import os
import matplotlib

if not os.name == 'nt':
    print("Set Display Variable when non-Windows..")
    matplotlib.use('Agg')
    
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker

from gwt_pt.datasource import ibkr 

import time
import datetime

def plot_with_portfolio(historic_df, signals, portfolio, title, isFile=False):

    fig = plt.figure(figsize=(15, 20))
    fig.patch.set_facecolor('white')     # Set the outer colour to white
    fig.suptitle(title, fontsize=12, color='grey')

    plt.style.use('bmh')

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

    ax1 = plt.subplot2grid((10, 1), (0, 0), rowspan=4, ylabel='Price in $')

    N = len(historic_df)
    df_idx = np.arange(N) # the evenly spaced plot indices   
    
    def format_date(x, pos=None):
        thisind = np.clip(int(x+0.5), 0, N-1)
        return historic_df.index[thisind].strftime('%Y-%m-%d')    
    
    ax1.plot(df_idx, historic_df['close'], color='r', lw=1.)
    ax1.plot(df_idx, signals['ema25'], lw=1.)
    
    # plot pf xup / xdown
    pf_xup_idx = signals.ix[signals.xup_pos == 1.0].index
    df_pf_xup_idx = [signals.index.get_loc(idx) for idx in pf_xup_idx]
    ax1.plot(df_pf_xup_idx, signals.low[signals.xup_pos == 1.0], '^', markersize=7, color='m')

    pf_xdown_idx = signals.ix[signals.xdown_pos == 1.0].index
    df_pf_xdown_idx = [signals.index.get_loc(idx) for idx in pf_xdown_idx]
    ax1.plot(df_pf_xdown_idx, signals.high[signals.xdown_pos == 1.0], 'v', markersize=7, color='r')
    
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))

    # Set the tick labels font
    for label in (ax1.get_xticklabels() + ax1.get_yticklabels()):
        label.set_fontname('Arial')
        label.set_fontsize(8)
        label.set_rotation(0)
        
    ax1.grid(True)

    # Plot the Slow Stoc
    ax2 = plt.subplot2grid((10, 1), (4, 0), rowspan=2, ylabel='Slow Stoc')
    ax2.axes.xaxis.set_visible(False)
    
    ax2.plot(df_idx, signals[['k_slow', 'd_slow']], lw=1.)
    
    ax2.fill_between(df_idx, 90, 100, facecolor='red', alpha=.2, interpolate=True)
    ax2.fill_between(df_idx, 0, 10, facecolor='red', alpha=.2, interpolate=True)

    ax2.axhline(y = 90, color = "brown", lw = 0.5)
    ax2.axhline(y = 10, color = "red", lw = 0.5)    

    # Plot the MACD
    ax3 = plt.subplot2grid((10, 1), (6, 0), rowspan=2, ylabel='MACD')
    ax3.axes.xaxis.set_visible(False)
    
    ax3.plot(df_idx, signals[['macd', 'emaSmooth']], lw=1.)
    ax3.plot(df_idx, signals['divergence'], lw=0.1)

    ax3.fill_between(df_idx, signals['divergence'], 0,
                where=signals['divergence'] >= 0,
                facecolor='blue', alpha=.8, interpolate=True)
                
    ax3.fill_between(df_idx, signals['divergence'], 0,
                where=signals['divergence'] < 0,
                facecolor='red', alpha=.8, interpolate=True)

    # Plot the super MACD            
    ax4 = plt.subplot2grid((10, 1), (8, 0), rowspan=2, ylabel='P&L')
    
    # Plot the equity curve in dollars
    ax4.plot(df_idx, portfolio['total'], lw=1.)
    ax4.plot(df_idx, portfolio['sma25'], lw=1.)
    ax4.axes.xaxis.set_visible(False)

    #ax4.axes.xaxis.set_visible(False)
    #ax4.plot(df_idx, signals[['sk_slow', 'sd_slow']], lw=1.)
    #ax4.fill_between(signals.index, 95, 100, facecolor='red', alpha=.2, interpolate=True)
    #ax4.fill_between(signals.index, 0, 5, facecolor='red', alpha=.2, interpolate=True)
    # plot macdstoc xup / xdown
    #ax4.plot(df_macdstoc_xup_idx, signals.sk_slow[signals.macdstoc_xup_positions == 1.0], '^', markersize=7, color='m')
    #ax4.plot(df_macdstoc_xdown_idx, signals.sk_slow[signals.macdstoc_xdown_positions == 1.0], 'v', markersize=7, color='r')    
    #ax4.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    #ax4.axes.xaxis.set_visible(True)

    # Plot the figure
    plt.tight_layout(w_pad=3, h_pad=3)
    if (isFile):
        if not os.name == 'nt':
            tstr = str(int(round(time.time() * 1000)))
            chartpath = "/var/www/eggyolk.tech/html/gwtpt/" + 'pchart' + tstr + '.png'
        else:
            chartpath = "C:\\Temp\\gwtpt\\" + 'pchart' + str(int(round(time.time() * 1000))) + '.png'
        
        plt.savefig(chartpath, bbox_inches='tight')
        print("Chart generated at %s" % chartpath)
        return chartpath 
    else:
        print("Plotting Chart.............")
        plt.show()
    
def main():
    
    passage = "Test............."
    print(passage)

if __name__ == "__main__":
    main() 
