#! /usr/bin/python

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
# Now I'll try and replicate the historical data example

from ibapi.wrapper import EWrapper
from ibapi.client import EClient

from gwt_pt.util import config_loader

from threading import Thread
import queue
import time

"""
Next section is 'scaffolding'
"""

ACCOUNT_UPDATE_FLAG = "update"
ACCOUNT_VALUE_FLAG = "value"
ACCOUNT_TIME_FLAG = "time"

class identifed_as(object):
    """
    Used to identify
    """

    def __init__(self, label, data):
        self.label = label
        self.data = data

    def __repr__(self):
        return "Identified as %s" % self.label


class list_of_identified_items(list):
    """
    A list of elements, each of class identified_as (or duck equivalent)

    Used to seperate out accounting data
    """
    def seperate_into_dict(self):
        """

        :return: dict, keys are labels, each element is a list of items matching label
        """

        all_labels = [element.label for element in self]
        dict_data = dict([
                             (label,
                              [element.data for element in self if element.label==label])
                          for label in all_labels])

        return dict_data


## marker for when queue is finished
FINISHED = object()
STARTED = object()
TIME_OUT = object()


class finishableQueue(object):
    """
    Creates a queue which will finish at some point
    """

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


## cache used for accounting data
class simpleCache(object):
    """
    Cache is stored in _cache in nested dict, outer key is accountName, inner key is cache label
    """
    def __init__(self, max_staleness_seconds):
        self._cache = dict()
        self._cache_updated_local_time = dict()

        self._max_staleness_seconds = max_staleness_seconds

    def __repr__(self):
        return "Cache with labels"+",".join(self._cache.keys())

    def update_data(self, accountName):
        raise Exception("You need to set this method in an inherited class")

    def _get_last_updated_time(self, accountName, cache_label):
        if accountName not in self._cache_updated_local_time.keys():
            return None

        if cache_label not in self._cache_updated_local_time[accountName]:
            return None

        return self._cache_updated_local_time[accountName][cache_label]


    def _set_time_of_updated_cache(self, accountName, cache_label):
        # make sure we know when the cache was updated
        if accountName not in self._cache_updated_local_time.keys():
            self._cache_updated_local_time[accountName]={}

        self._cache_updated_local_time[accountName][cache_label] = time.time()


    def _is_data_stale(self, accountName, cache_label, ):
        """
        Check to see if the cached data has been updated recently for a given account and label, or if it's stale

        :return: bool
        """
        STALE = True
        NOT_STALE = False

        last_update = self._get_last_updated_time(accountName, cache_label)

        if last_update is None:
            ## we haven't got any data, so by construction our data is stale
            return STALE

        time_now = time.time()
        time_since_updated = time_now - last_update

        if time_since_updated > self._max_staleness_seconds:
            return STALE
        else:
            ## recently updated
            return NOT_STALE

    def _check_cache_empty(self, accountName, cache_label):
        """

        :param accountName: str
        :param cache_label: str
        :return: bool
        """
        CACHE_EMPTY = True
        CACHE_PRESENT = False

        cache = self._cache
        if accountName not in cache.keys():
            return CACHE_EMPTY

        cache_this_account = cache[accountName]
        if cache_label not in cache_this_account.keys():
            return CACHE_EMPTY

        return CACHE_PRESENT

    def _return_cache_values(self, accountName, cache_label):
        """

        :param accountName: str
        :param cache_label: str
        :return: None or cache contents
        """

        if self._check_cache_empty(accountName, cache_label):
            return None

        return self._cache[accountName][cache_label]


    def _create_cache_element(self, accountName, cache_label):

        cache = self._cache
        if accountName not in cache.keys():
            cache[accountName] = {}

        cache_this_account = cache[accountName]
        if cache_label not in cache_this_account.keys():
            cache[accountName][cache_label] = None


    def get_updated_cache(self, accountName, cache_label):
        """
        Checks for stale cache, updates if needed, returns up to date value

        :param accountName: str
        :param cache_label:  str
        :return: updated part of cache
        """

        if self._is_data_stale(accountName, cache_label) or self._check_cache_empty(accountName, cache_label):
            self.update_data(accountName)

        return self._return_cache_values(accountName, cache_label)


    def update_cache(self, accountName, dict_with_data):
        """

        :param accountName: str
        :param dict_with_data: dict, which has keynames with cache labels
        :return: nothing
        """

        all_labels = dict_with_data.keys()
        for cache_label in all_labels:
            self._create_cache_element(accountName, cache_label)
            self._cache[accountName][cache_label] = dict_with_data[cache_label]
            self._set_time_of_updated_cache(accountName, cache_label)


"""
Now into the main bit of the code; Wrapper and Client objects
"""

class TestWrapper(EWrapper):
    """
    The wrapper deals with the action coming back from the IB gateway or TWS instance

    We override methods in EWrapper that will get called when this action happens, like currentTime

    Extra methods are added as we need to store the results in this object
    """

    def __init__(self):
        ## use a dict as could have different accountids
        self._my_accounts = {}

        ## We set these up as we could get things coming along before we run an init
        self._my_positions = queue.Queue()
        self._my_errors = queue.Queue()


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

    ## get positions code
    def init_positions(self):
        positions_queue = self._my_positions = queue.Queue()

        return positions_queue

    def position(self, account, contract, position,
                 avgCost):

        ## uses a simple tuple, but you could do other, fancier, things here
        position_object = (account, contract, position,
                 avgCost)

        self._my_positions.put(position_object)

    def positionEnd(self):
        ## overriden method

        self._my_positions.put(FINISHED)


    ## get accounting data
    def init_accounts(self, accountName):
        accounting_queue = self._my_accounts[accountName] = queue.Queue()

        return accounting_queue


    def updateAccountValue(self, key:str, val:str, currency:str,
                            accountName:str):

        ## use this to seperate out different account data
        data = identifed_as(ACCOUNT_VALUE_FLAG, (key,val, currency))
        self._my_accounts[accountName].put(data)


    def updatePortfolio(self, contract, position:float,
                        marketPrice:float, marketValue:float,
                        averageCost:float, unrealizedPNL:float,
                        realizedPNL:float, accountName:str):

        ## use this to seperate out different account data
        data = identifed_as(ACCOUNT_UPDATE_FLAG, (contract, position, marketPrice, marketValue, averageCost,
                                          unrealizedPNL, realizedPNL))
        self._my_accounts[accountName].put(data)

    def updateAccountTime(self, timeStamp:str):

        ## use this to seperate out different account data
        data = identifed_as(ACCOUNT_TIME_FLAG, timeStamp)
        self._my_accounts[accountName].put(data)


    def accountDownloadEnd(self, accountName:str):

        self._my_accounts[accountName].put(FINISHED)



class TestClient(EClient):
    """
    The client method

    We don't override native methods, but instead call them from our own wrappers
    """
    def __init__(self, wrapper):
        ## Set up with a wrapper inside
        EClient.__init__(self, wrapper)

        ## We use these to store accounting data
        self._account_cache = simpleCache(max_staleness_seconds = 5*60)
        ## override function
        self._account_cache.update_data = self._update_accounting_data


    def get_current_positions(self):
        """
        Current positions held

        :return:
        """

        ## Make a place to store the data we're going to return
        positions_queue = finishableQueue(self.init_positions())

        ## ask for the data
        self.reqPositions()

        ## poll until we get a termination or die of boredom
        MAX_WAIT_SECONDS = 10
        positions_list = positions_queue.get(timeout=MAX_WAIT_SECONDS)

        while self.wrapper.is_error():
            print(self.get_error())

        if positions_queue.timed_out():
            print("Exceeded maximum wait for wrapper to confirm finished whilst getting positions")

        return positions_list

    def _update_accounting_data(self, accountName):
        """
        Update the accounting data in the cache

        :param accountName: account we want to get data for
        :return: nothing
        """

        ## Make a place to store the data we're going to return
        accounting_queue = finishableQueue(self.init_accounts(accountName))

        ## ask for the data
        self.reqAccountUpdates(True, accountName)

        ## poll until we get a termination or die of boredom
        MAX_WAIT_SECONDS = 10
        accounting_list = accounting_queue.get(timeout=MAX_WAIT_SECONDS)

        while self.wrapper.is_error():
            print(self.get_error())

        if accounting_queue.timed_out():
            print("Exceeded maximum wait for wrapper to confirm finished whilst getting accounting data")

        # seperate things out, because this is one big queue of data with different things in it
        accounting_list = list_of_identified_items(accounting_list)
        seperated_accounting_data = accounting_list.seperate_into_dict()

        ## update the cache with different elements
        self._account_cache.update_cache(accountName, seperated_accounting_data)

        ## return nothing, information is accessed via get_... methods



    def get_accounting_time_from_server(self, accountName):
        """
        Get the accounting time from IB server

        :return: accounting time as served up by IB
        """

        #All these functions follow the same pattern: check if stale or missing, if not return cache, else update values

        return self._account_cache.get_updated_cache(accountName, ACCOUNT_TIME_FLAG)


    def get_accounting_values(self, accountName):
        """
        Get the accounting values from IB server

        :return: accounting values as served up by IB
        """

        #All these functions follow the same pattern: check if stale, if not return cache, else update values

        return self._account_cache.get_updated_cache(accountName, ACCOUNT_VALUE_FLAG)


    def get_accounting_updates(self, accountName):
        """
        Get the accounting updates from IB server

        :return: accounting updates as served up by IB
        """

        #All these functions follow the same pattern: check if stale, if not return cache, else update values

        return self._account_cache.get_updated_cache(accountName, ACCOUNT_UPDATE_FLAG)


class TestApp(TestWrapper, TestClient):

    def __init__(self, ipaddress, portid, clientid):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)

        self.connect(ipaddress, portid, clientid)

        thread = Thread(target = self.run)
        thread.start()

        setattr(self, "_thread", thread)

if __name__ == '__main__':

    config = config_loader.load()
    ip = config.get("ib-gateway","ip")
    #ip = "127.0.0.1"

    app = TestApp(ip, 4001, 59)

    ## lets get positions
    positions_list = app.get_current_positions()
    print(positions_list)

    ## get the account name from the position
    ## normally you would know your account name
    accountName = positions_list[0][0]

    ## and accounting information
    accounting_values = app.get_accounting_values(accountName)
    print(accounting_values)

    ## these values are cached
    ## if we ask again in more than 5 minutes it will update everything
    accounting_updates = app.get_accounting_updates(accountName)
    print(accounting_updates)

    app.disconnect()