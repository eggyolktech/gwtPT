
import os
import sys
import time
import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton
from decimal import Decimal
import urllib.request
import urllib.error
from socket import timeout
import random
#import resource
from gwt_pt.util import config_loader

# Load static properties
config = config_loader.load()

LOADING = [u'\U0000231B', u'\U0001F6AC', u'\U0001F37B', u'\U0001F377', u'\U000023F3', u'\U0000231A']
DEL = "\n\n"
EL = "\n"

def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    
    print("Text Command: " + msg['text'])
    
    command = msg['text'].split("@")[0]
    
    keyboard_list = []
    reply = ""
    
    if(command == "/test"):
    
        bot.sendMessage(chat_id, random.choice(LOADING), parse_mode='HTML')
        bot.sendMessage(chat_id, "Test", parse_mode='HTML')
        
    elif (command == "/fxEU"):
        
        bot.sendMessage(chat_id, random.choice(LOADING), parse_mode='HTML')         
        try:
            #result = stock_history.get_stocks_rs_charts([code] + params)
            #chartpath = result[0]
            #invalidcodelist = result[1]
            chartpath="#"
            print("Chart Path: [" + chartpath + "]")

        except Exception as e:
            print("Exception raised: [" + str(e) +  "]")
            bot.sendMessage(chat_id, u'\U000026D4' + ' ' + str(e), parse_mode='HTML')
        else:
            bot.sendPhoto(chat_id=chat_id, photo=open(chartpath, 'rb'))      
        return

    elif (command.startswith("/")):    
    
        menuitemlist = [{'command': '/test', 'desc': 'Test', 'icon': u'\U0001F4B9'},
                        {'command': '/fx[FX_SYM]', 'desc': 'FX Chart', 'icon': u'\U0001F310'},\
        ]
        
        menu = '金鑊鏟 PT Bot v0.1 '
        
        for menuitem in menuitemlist:
            menu = menu + DEL + ' ' + menuitem['command'] + ' - ' + menuitem['desc'] + ' ' + menuitem['icon']
    
        bot.sendMessage(chat_id, menu, parse_mode='HTML')
        
    else: 
        print("DO NOTHING for non / command")

        
def on_callback_query(msg):

    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
    print('Callback Query:', query_id, from_id, query_data)
    
    result = "No live rate is available"

    # if query data is available
    if query_data:
    
        result = query_data
        bot.answerCallbackQuery(query_id, text=result)
    
TOKEN = config.get("telegram","bot-id") # get token from command-line

# Set resource limit
#rsrc = resource.RLIMIT_DATA
#soft, hard = resource.getrlimit(rsrc)
#print('Soft limit start as :' + str(soft))

#resource.setrlimit(rsrc, (300 * 1024, hard))
#soft, hard = resource.getrlimit(rsrc)

#print('Soft limit start as :' + str(soft))

bot = telepot.Bot(TOKEN)
print(bot.getMe())
bot.message_loop({'chat': on_chat_message,
                  'callback_query': on_callback_query})
print('Listening ...')

while 1:
    time.sleep(10)
 
