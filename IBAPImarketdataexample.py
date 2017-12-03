# Gist example of IB wrapper ...
#
# Download API from http://interactivebrokers.github.io/#
#
# Install python API code /IBJts/source/pythonclient $ python3 setup.py install
#
# Note: The test cases, and the documentation refer to a python package called IBApi,
#    but the actual package is called ibapi. Go figure.
#
# Get the latest version of the gateway:
# https://www.interactivebrokers.com/en/?f=%2Fen%2Fcontrol%2Fsystemstandalone-ibGateway.php%3Fos%3Dunix
#    (for unix: windows and mac users please find your own version)
#
# Run the gateway
#
# user: edemo
# pwd: demo123
#

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract as IBcontract
from threading import Thread
import queue
import datetime

import numpy as np
import pandas as pd
from pandas_datareader import data as web, wb
from indicator import SMA, EMA, RSI, FASTSTOC, SLOWSTOC, MACD

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

DEFAULT_HISTORIC_DATA_ID=50
DEFAULT_GET_CONTRACT_ID=43

## marker for when queue is finished
FINISHED = object()
STARTED = object()
TIME_OUT = object()

class finishableQueue(object):

    def __init__(self, queue_to_finish):

        self._queue = queue_to_finish
        self.status = STARTED

    def get(self, timeout):
        """
        Returns a list of queue elements once timeout is finished, or a FINISHED flag is received in the queue
        :param timeout: how long to wait before giving up
        :return: list of queue elements
        """
        contents_of_queue=[]
        finished=False

        while not finished:
            try:
                current_element = self._queue.get(timeout=timeout)
                if current_element is FINISHED:
                    finished = True
                    self.status = FINISHED
                else:
                    contents_of_queue.append(current_element)
                    ## keep going and try and get more data

            except queue.Empty:
                ## If we hit a time out it's most probable we're not getting a finished element any time soon
                ## give up and return what we have
                finished = True
                self.status = TIME_OUT


        return contents_of_queue

    def timed_out(self):
        return self.status is TIME_OUT





class TestWrapper(EWrapper):
    """
    The wrapper deals with the action coming back from the IB gateway or TWS instance
    We override methods in EWrapper that will get called when this action happens, like currentTime
    Extra methods are added as we need to store the results in this object
    """

    def __init__(self):
        self._my_contract_details = {}
        self._my_historic_data_dict = {}
        self.init_error()

    ## error handling code
    def init_error(self):
        error_queue=queue.Queue()
        self._my_errors = error_queue

    def get_error(self, timeout=5):
        if self.is_error():
            try:
                return self._my_errors.get(timeout=timeout)
            except queue.Empty:
                return None

        return None

    def is_error(self):
        an_error_if=not self._my_errors.empty()
        return an_error_if

    def error(self, id, errorCode, errorString):
        ## Overriden method
        errormsg = "IB error id %d errorcode %d string %s" % (id, errorCode, errorString)
        self._my_errors.put(errormsg)


    ## get contract details code
    def init_contractdetails(self, reqId):
        contract_details_queue = self._my_contract_details[reqId] = queue.Queue()

        return contract_details_queue

    def contractDetails(self, reqId, contractDetails):
        ## overridden method

        if reqId not in self._my_contract_details.keys():
            self.init_contractdetails(reqId)

        self._my_contract_details[reqId].put(contractDetails)

    def contractDetailsEnd(self, reqId):
        ## overriden method
        if reqId not in self._my_contract_details.keys():
            self.init_contractdetails(reqId)

        self._my_contract_details[reqId].put(FINISHED)

    ## Historic data code
    def init_historicprices(self, tickerid):
        historic_data_queue = self._my_historic_data_dict[tickerid] = queue.Queue()

        return historic_data_queue


    def historicalData(self, tickerid , bar):

        ## Overriden method
        ## Note I'm choosing to ignore barCount, WAP and hasGaps but you could use them if you like
        bardata=(bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume)

        historic_data_dict=self._my_historic_data_dict

        ## Add on to the current data
        if tickerid not in historic_data_dict.keys():
            self.init_historicprices(tickerid)

        historic_data_dict[tickerid].put(bardata)

    def historicalDataEnd(self, tickerid, start:str, end:str):
        ## overriden method

        if tickerid not in self._my_historic_data_dict.keys():
            self.init_historicprices(tickerid)

        self._my_historic_data_dict[tickerid].put(FINISHED)




class TestClient(EClient):
    """
    The client method
    We don't override native methods, but instead call them from our own wrappers
    """
    def __init__(self, wrapper):
        ## Set up with a wrapper inside
        EClient.__init__(self, wrapper)


    def resolve_ib_contract(self, ibcontract, reqId=DEFAULT_GET_CONTRACT_ID):

        """
        From a partially formed contract, returns a fully fledged version
        :returns fully resolved IB contract
        """

        ## Make a place to store the data we're going to return
        contract_details_queue = finishableQueue(self.init_contractdetails(reqId))

        print("Getting full contract details from the server... ")

        self.reqContractDetails(reqId, ibcontract)

        ## Run until we get a valid contract(s) or get bored waiting
        MAX_WAIT_SECONDS = 20
        new_contract_details = contract_details_queue.get(timeout = MAX_WAIT_SECONDS)

        while self.wrapper.is_error():
            print(self.get_error())

        if contract_details_queue.timed_out():
            print("Exceeded maximum wait for wrapper to confirm finished - seems to be normal behaviour")

        if len(new_contract_details)==0:
            print("Failed to get additional contract details: returning unresolved contract")
            return ibcontract

        if len(new_contract_details)>1:
            print("got multiple contracts using first one")

        new_contract_details=new_contract_details[0]

        resolved_ibcontract=new_contract_details.summary

        return resolved_ibcontract


    def get_IB_historical_data(self, ibcontract, durationStr="1 Y", barSizeSetting="4 hours",
                               tickerid=DEFAULT_HISTORIC_DATA_ID):

        """
        Returns historical prices for a contract, up to today
        ibcontract is a Contract
        :returns list of prices in 4 tuples: Open high low close volume
        """


        ## Make a place to store the data we're going to return
        historic_data_queue = finishableQueue(self.init_historicprices(tickerid))

        # Request some historical data. Native method in EClient
        self.reqHistoricalData(
            tickerid,  # tickerId,
            ibcontract,  # contract,
            datetime.datetime.today().strftime("%Y%m%d %H:%M:%S %Z"),  # endDateTime,
            durationStr,  # durationStr,
            barSizeSetting,  # barSizeSetting,
            "MIDPOINT",
            #"TRADES",  # whatToShow,
            1,  # useRTH,
            1,  # formatDate
            False,  # KeepUpToDate <<==== added for api 9.73.2
            [] ## chartoptions not used
        )



        ## Wait until we get a completed data, an error, or get bored waiting
        MAX_WAIT_SECONDS = 20
        print("Getting historical data from the server... could take %d seconds to complete " % MAX_WAIT_SECONDS)

        historic_data = historic_data_queue.get(timeout = MAX_WAIT_SECONDS)

        while self.wrapper.is_error():
            print(self.get_error())

        if historic_data_queue.timed_out():
            print("Exceeded maximum wait for wrapper to confirm finished - seems to be normal behaviour")

        self.cancelHistoricalData(tickerid)


        return historic_data



class TestApp(TestWrapper, TestClient):
    def __init__(self, ipaddress, portid, clientid):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)

        self.connect(ipaddress, portid, clientid)

        thread = Thread(target = self.run)
        thread.start()

        setattr(self, "_thread", thread)

        self.init_error()


#if __name__ == '__main__':

app = TestApp("127.0.0.1", 4001, 1)

ibcontract = IBcontract()
#ibcontract.lastTradeDateOrContractMonth="201809"
#ibcontract.secType = "FUT"
#ibcontract.symbol="GE"
#ibcontract.exchange="GLOBEX"
ibcontract.symbol = "EUR"
ibcontract.secType = "CASH"
ibcontract.currency = "USD"
ibcontract.exchange = "IDEALPRO"

duration = "2 M"
period = "4 hours"
xsymbol = ibcontract.symbol + "/" + ibcontract.currency

resolved_ibcontract=app.resolve_ib_contract(ibcontract)

historic_data = app.get_IB_historical_data(resolved_ibcontract, duration, period)
#print(historic_data)
historic_df = pd.DataFrame(historic_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
historic_df.set_index('datetime', inplace=True)

signals = pd.DataFrame(index=historic_df.index)
signals['close'] = historic_df['close']
#print(signals)
signals["ema25"] = EMA(signals, 'close', 25)

# MACD
macd = MACD(historic_df['close'])
signals = pd.concat([signals, macd], axis=1)

# Slowstoc
#print("T1: " + str(type(historic_df)))
kslow, dslow = SLOWSTOC(historic_df, 'low', 'high', 'close', 16, 8, False)
signals = pd.concat([signals, kslow, dslow], axis=1)
#print(signals)
# Super Macdstoc
#print("T2: " + str(type(signals)))
skslow, sdslow = SLOWSTOC(signals, "macd", "macd", "macd", 11, 3, False)
skslow = skslow.rename(columns = {'k_slow':'sk_slow'})
sdslow = sdslow.rename(columns = {'d_slow':'sd_slow'})
#print(skslow)
#print(sdslow)
signals = pd.concat([signals, skslow, sdslow], axis=1)

#('20161201  06:15:00', 1.059275, 1.059875, 1.05856, 1.059045

#print(historic_df)
#print(signals)
print(signals.info())

try:
    app.disconnect()
except:
    print("Disconnect with errors (no harm)!")
    
# Plot plot plot
historic_df.index = pd.to_datetime(historic_df.index)
signals.index = pd.to_datetime(signals.index)

print(signals.to_string())

fig = plt.figure(figsize=(15, 20))
fig.patch.set_facecolor('white')     # Set the outer colour to white
fig.suptitle(xsymbol + " " + period, fontsize=12, color='grey')

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
plt.show()











    
