
import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb

from gwt_pt.datasource import ibkr 

import time
import datetime

FILTER_DICT = {
    "4 hours": "06:15",
    "1 hour": "05:15"
}

def resample_ib_data(ib_tuples, filter):

    if filter:
        ib_tuples = [i for i in ib_tuples if filter not in i[0]]

    # Data pre-processing
    historic_df = pd.DataFrame(ib_tuples, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    historic_df.set_index('datetime', inplace=True)
    historic_df.index = pd.to_datetime(historic_df.index)
    
    #print(historic_df.to_string())
    #print(historic_df)
    print(historic_df['open'].groupby(historic_df['open'].index // 4 * 4).sum())
      
    return historic_df


def main():
    
    passage = "Test............."
    print(passage)
    
    symbol = "EUR"
    currency = "USD"
    duration = "2 M"
    period = "1 hour"
    #period = "4 hours"
    
    data = resample_ib_data(ibkr.get_data(symbol, currency, duration, period), FILTER_DICT[period])

if __name__ == "__main__":
    main() 
