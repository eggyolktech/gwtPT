#! /usr/bin/python

import numpy as np
import pandas as pd
import os
from pandas_datareader import data as web, wb

from gwt_pt.datasource import ibkr 

import time
import datetime

FILTER_DICT_FX = {
    "4 hours": ["06:15", "18:15", "22:15"],
    "1 hour": ["05:15"]
}

FILTER_DICT_HKFE = {
    "1 hour": ["09:15"]
}

def filter_data(type, ib_tuples, period):

    filter = filterDict = None
    if type == "FX":
        filterDict = FILTER_DICT_FX
    elif type == "HKFE":
        filterDict = FILTER_DICT_HKFE
        
    if period in filterDict:
        filter = filterDict[period]

    if filter:
        for f in filter:
            ib_tuples = [i for i in ib_tuples if f not in i[0]]
            
    return ib_tuples

def main():
    
    passage = "Test............."
    print(passage)
    
    symbol = "EUR"
    currency = "USD"
    duration = "2 M"
    #period = "1 hour"
    period = "4 hours"
    
    data = filter_data(ibkr.get_data(symbol, currency, duration, period), FILTER_DICT[period])

if __name__ == "__main__":
    main() 
