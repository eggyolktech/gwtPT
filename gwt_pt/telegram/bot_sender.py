#!/usr/bin/python

import configparser
import os
import urllib.request
import urllib.parse
from gwt_pt.util import config_loader
from urllib.error import URLError, HTTPError

config = config_loader.load()

MAX_MSG_SIZE = 4096

def broadcast(passage, is_test=False):

    if (is_test):
        chat_list = config.items("telegram-chat-test")
    else:
        chat_list = config.items("telegram-chat")
    bot_send_url = config.get("telegram","bot-send-url")
    
    print(bot_send_url)

    for key, chat_id in chat_list:
        print("Chat to send: " + key + " => " + chat_id);

        messages = [passage[i:i+MAX_MSG_SIZE] for i in range(0, len(passage), MAX_MSG_SIZE)]

        for message in messages:
        
            result = ""
            payload = { "parse_mode": "HTML", "chat_id": chat_id, "text": message }

            try:
                result = urllib.request.urlopen(bot_send_url, urllib.parse.urlencode(payload).encode("utf-8")).read()
                
            except HTTPError as e:
                # do something
                print('Error code: ', e.code)
                print(e)
            except URLError as e:
                # do something
                print('Reason: ', e.reason)
            else:
                # do something
                print('good!')
            print(result)

def broadcast_list(passage, chatlist="telegram-chat-test"):

    chat_list = config.items(chatlist)
    bot_send_url = config.get("telegram","bot-send-url")

    for key, chat_id in chat_list:
        print("Chat to send: " + key + " => " + chat_id);

        messages = [passage[i:i+MAX_MSG_SIZE] for i in range(0, len(passage), MAX_MSG_SIZE)]

        for message in messages:

            result = urllib.request.urlopen(bot_send_url, urllib.parse.urlencode({ "parse_mode": "HTML", "chat_id": chat_id, "text": message }).encode("utf-8")).read()

            print(result)

def main():

    passage = "Test"

    # Send a message to a chat room (chat room ID retrieved from getUpdates)
    broadcast(passage, False)

if __name__ == "__main__":
    main()
