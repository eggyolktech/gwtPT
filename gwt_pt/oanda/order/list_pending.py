#!/usr/bin/env python

import argparse
import gwt_pt.oanda.common.config
from view import print_orders
from gwt_pt.telegram import bot_sender

def pending():
    parser = argparse.ArgumentParser()
    gwt_pt.oanda.common.config.add_argument(parser)

    parser.add_argument(
        "--summary",
        dest="summary",
        action="store_true",
        help="Print a summary of the orders",
        default=True
    )

    parser.add_argument(
        "--verbose", "-v",
        dest="summary",
        help="Print details of the orders",
        action="store_false"
    )

    args = parser.parse_args()

    account_id = args.config.active_account
    
    api = args.config.create_context()

    response = api.order.list_pending(account_id)

    orders = response.get("orders", 200)

    passage = ""
    
    if len(orders) == 0:
        passage = "Account {} has no pending Orders".format(account_id)
        print(passage)
        return passage        
        
    orders = sorted(orders, key=lambda o: int(o.id))

    sep = ("-" * 80)
    if not args.summary:
        print(sep)
        #passage = passage + sep + "\n"

    for order in orders:
        if args.summary:
            print(order.title())
            passage = passage + order.title() + "\n"
        else:
            print(order.yaml(True))
            passage = passage + order.yaml(True) + "\n"
            print(sep)
            #passage = passage + sep + "\n"

    return passage    

if __name__ == "__main__":
    p = pending()
    
    if (p):
        h = "<b>" + u'\U0001F514' + " Hourly Pending Orders Updates</b>\n\n"
        p = h + p
    
    bot_sender.broadcast_list(p, "telegram-position")    
    