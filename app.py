# -*- coding: utf-8 -*-

bot_title = 'Binance{}-SYY 2.2 (Build 8) mod by appcorner'
bot_title_orig = '[from Bitkub-SYY 2.1 (Build 32) by tidLord]'

# system setup
botSetup_system_delay = 5
botSetup_ts_threshold = 60 # ค่าระยะห่าง(หน่วยเป็นวินาที) ไว้เช็คเมื่อบอทหยุดทำงาน
botSetup_pid_threshold = 3 # ค่าระยะเวลาตรวจจับ last_active ป้องกันบอทรันซ้อนกัน
botSetup_orders_verbose = True # เก็บรายละเอียดออเดอร์เข้า orders_verbose.txt
botSetup_precision_margin = 4 # จำนวนทศนิยม MARGIN amount
botSetup_precision_coin = 8 # จำนวนทศนิยม COIN amount

# system file name
fileName_config = 'config'
fileName_log = 'app'
fileName_orders_verbose = 'orders_verbose'
fileName_stat = 'stat'
fileName_temp = 'temp'
fileName_last_active = 'last_active'
fileName_database = 'BN_SYY'

# ansi escape code
CLS_SCREEN = '\033[2J\033[1;1H' # cls + set top left
CLS_LINE = '\033[0J'
SHOW_CURSOR = '\033[?25h'
HIDE_CURSOR = '\033[?25l'

import sys

from binance import Client
import os, shutil, json, hmac, requests, hashlib, time, sqlite3, websocket
from tabulate import tabulate
from datetime import datetime
from numpy import format_float_positional
from pytz import timezone

import math
import pathlib
import logging
from logging.handlers import RotatingFileHandler
from TelegramNotify import TelegramNotify
# throttle: แจ้งเตือน DCA เงินไม่พอได้ไม่เกิน 1 ครั้ง/ชั่วโมง
last_dca_insufficient_notify_ts = 0

# สำหรับ Windows OS
if os.name == 'nt':
    from colorama import Back, Fore, Style, init
    init()
else:
    from colorama import Back, Fore, Style

# โหลด config (return -> dict / error -> 0 int)
def read_config():
    try:
        fileName_config_json = fileName_config + '.json'
        with open(fileName_config_json, 'r', encoding='utf-8') as config:
            config = json.load(config)
            if config['MAX_ORDER'] > 100:
                config['MAX_ORDER'] = 100
            return config
    except Exception as error_is:
        print('config : ' + str(error_is))
        return 0
    
# ฟังก์ชั่นตัดทศนิยมแบบไม่ปัดเศษ(return -> string)
def number_truncate(number, precision):
    return format_float_positional(number, unique=True, precision=precision, trim='0')
        
# ฟังก์ชั่นเก็บรายละเอียดออเดอร์ ( orders verbose ) ใส่ orders verbose file
def orders_verbose(order_type, order_number, order_detail):
    if botSetup_orders_verbose:
        fileName_orders_verbose_txt = f'{path_data}/{fileName_orders_verbose}.txt'
        try:
            with open(fileName_orders_verbose_txt, 'r', encoding='utf-8') as f:
                f = f.read()
            with open(fileName_orders_verbose_txt, 'w', encoding='utf-8') as f2:
                f2.write('\n' + str(datetime.now()) + '\norder type : ' + order_type + '\norder number : ' + str(order_number) + '\n' + str(order_detail) + '\n............\n' + f)
        except FileNotFoundError:
            with open(fileName_orders_verbose_txt, 'w', encoding='utf-8') as f:
                f.write('\n' + str(datetime.now()) + '\norder type : ' + order_type + '\norder number : ' + str(order_number) + '\n' + str(order_detail) + '\n............\n')
        except Exception as error_is:
            print('orders_verbose() : ' + str(error_is))

# ฟังก์ชั่นเพิ่มจำนวนไม้ที่เทรดใส่ stat file
def stat_add_circle_total():
    fileName_stat_txt = f'{path_data}/{fileName_stat}.json'
    try:
        with open(fileName_stat_txt, 'r', encoding='utf-8') as stat_json:
            stat_json = json.load(stat_json)
        stat_json['circle_total'] += 1
        with open(fileName_stat_txt, 'w', encoding='utf-8') as update_stat_json:
            json.dump(stat_json, update_stat_json, indent=4)
    except FileNotFoundError:
        stat_json = { 'profit_total': 0.0, 'circle_total': 1 }
        with open(fileName_stat_txt, 'w', encoding='utf-8') as update_stat_json:
            json.dump(stat_json, update_stat_json, indent=4)
    except Exception as error_is:
        logger.info('stat_add_circle_total() : ' + str(error_is))

# ฟังก์ชั่นเพิ่มยอดกำไรขาดทุนใส่ stat file
def stat_add_profit_total(qty):
    fileName_stat_json = f'{path_data}/{fileName_stat}.json'
    try:
        with open(fileName_stat_json, 'r', encoding='utf-8') as stat_json:
            stat_json = json.load(stat_json)
        stat_json['profit_total'] += qty
        with open(fileName_stat_json, 'w', encoding='utf-8') as update_stat_json:
            json.dump(stat_json, update_stat_json, indent=4)
    except FileNotFoundError:
        stat_json = { 'profit_total': qty, 'circle_total': 1 }
        with open(fileName_stat_json, 'w', encoding='utf-8') as update_stat_json:
            json.dump(stat_json, update_stat_json, indent=4)
    except Exception as error_is:
        logger.info('stat_add_profit_total() : ' + str(error_is))
        
# ฟังก์ชั่นอ่าน stat file (return -> dict)
def stat_read():
    fileName_stat_json = f'{path_data}/{fileName_stat}.json'
    try:
        with open(fileName_stat_json, 'r', encoding='utf-8') as stat_json:
            stat_json = json.load(stat_json)
            return stat_json
    except FileNotFoundError:
        stat_json = { 'profit_total': 0, 'circle_total': 0 }
        with open(fileName_stat_json, 'w', encoding='utf-8') as update_stat_json:
            json.dump(stat_json, update_stat_json, indent=4)
        with open(fileName_stat_json, 'r', encoding='utf-8') as stat_json:
            stat_json = json.load(stat_json)
            return stat_json
    except Exception as error_is:
        logger.info('stat_read() : ' + error_is)

# ฟังก์ชั่นเขียน hash ใส่ temp file (cmd 1 -> buy first, 2 -> buy DCA, 3 -> sell profit, 4 -> sell DCA, 5 -> sell clear)
def temp_write(hash, cmd, detail):
    if detail:
        logger.debug(detail)
    fileName_temp_json = f'{path_data}/{fileName_temp}.json'
    try:
        with open(fileName_temp_json, 'r', encoding='utf-8') as hash_json:
            hash_json = json.load(hash_json)
        hash_json['HASH'] = hash
        hash_json['cmd'] = cmd
        hash_json['detail'] = detail
        with open(fileName_temp_json, 'w', encoding='utf-8') as update_hash_json:
            json.dump(hash_json, update_hash_json, indent=4)
    except FileNotFoundError:
        hash_json = {'HASH': hash, 'cmd': cmd, 'detail': detail}
        with open(fileName_temp_json, 'w', encoding='utf-8') as update_hash_json:
            json.dump(hash_json, update_hash_json, indent=4)
    except Exception as error_is:
        logger.info('temp_write() : ' + str(error_is))

# ฟังก์ชั่นอ่าน temp ใน temp file (return -> dict)
def temp_read():
    fileName_temp_json = f'{path_data}/{fileName_temp}.json'
    try:
        with open(fileName_temp_json, 'r', encoding='utf-8') as hash_json:
            hash_json = json.load(hash_json)
            return hash_json
    except FileNotFoundError:
        hash_json = {'HASH': '', 'cmd': 0, 'detail': ''}
        with open(fileName_temp_json, 'w', encoding='utf-8') as update_hash_json:
            json.dump(hash_json, update_hash_json, indent=4)
        with open(fileName_temp_json, 'r', encoding='utf-8') as hash_json:
            hash_json = json.load(hash_json)
            return hash_json
    except Exception as error_is:
        logger.info('temp_read() : ' + error_is)

    
# ฟังก์ชั่นเก็บเวลาการทำงานครั้งล่าสุดใส่ last_active file
def last_active_update(datetime_now):
    fileName_last_active_txt = f'{path_data}/{fileName_last_active}.txt'
    with open(fileName_last_active_txt, 'w', encoding='utf-8') as last_active:
        last_active.write(str(datetime_now))
        
# ฟังก์ชั่นการแจ้งเตือนใน telegram ผ่าน telegram api
def telegram_notify_classic(thisOrder, notifyMsg, order_no, side, price, base_amt, profit, ordercount):
    try:
        if config['TELEGRAM'] == 1:
            if thisOrder:
                symbol = config['COIN'] + config['MARGIN']
                if side == 'buy':               
                    msg = '\nออเดอร์ที่ : ' + str(order_no) + '\nซื้อ : ' + symbol + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + '\nจำนวน : ' + number_truncate(base_amt, botSetup_precision_margin) + ' '
                elif side == 'sell_profit':
                    if profit >= 0:
                        msg = '\nขาย : ' + symbol + '\nออเดอร์ที่ : ' + str(order_no) + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + '\nกำไร : ' + number_truncate(profit, botSetup_precision_margin) + ' '
                    else:
                        msg = '\nขาย : ' + symbol + '\nออเดอร์ที่ : ' + str(order_no) + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + '\nขาดทุน : ' + number_truncate(profit, botSetup_precision_margin) + ' '
                elif side == 'sell_dca':
                    if profit >= 0:
                        msg = '\nขาย : ' + symbol + '\nออเดอร์ที่ : ' + str(order_no) + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' '
                    else:
                        msg = '\nขาย : ' + symbol + '\nออเดอร์ที่ : ' + str(order_no) + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' '
                elif side == 'sell_clear': 
                    msg = '\nเคลียร์ออเดอร์ : ' + symbol + '\nจำนวนออเดอร์ : ' + str(ordercount) + '\nที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + '\nกำไรจากการเคลียร์ : ' + number_truncate(profit, botSetup_precision_margin)+' '
            else:
                msg = notifyMsg
            telegram.send(msg)
    except Exception as error_is:
        logger.debug('telegram function error : '+str(error_is))
        print('!!! telegram function error !!!')

# ฟังก์ชั่นการแจ้งเตือนใน telegram ผ่าน telegram api
def telegram_notify(thisOrder, notifyMsg, order_no, side, price, base_amt, profit, ordercount):
    try:
        if config['TELEGRAM'] == 1:
            if thisOrder:
                symbol = config['COIN'] + config['MARGIN']
                if side == 'buy':
                    msg = (
                        '🟢 *คำสั่งซื้อใหม่!*' +
                        '\n📦 ออเดอร์ที่ : ' + str(order_no) +
                        '\n💰 ซื้อ : ' + symbol +
                        '\n💵 ที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + config['MARGIN'] +
                        '\n📊 จำนวน : ' + number_truncate(base_amt, botSetup_precision_margin) + ' ' + config['MARGIN']
                    )
                elif side == 'sell_profit':
                    if profit >= 0:
                        msg = (
                            '🟢 *ขายทำกำไร!*' +
                            '\n📦 ออเดอร์ที่ : ' + str(order_no) +
                            '\n💰 ขาย : ' + symbol +
                            '\n💵 ที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + config['MARGIN'] +
                            '\n✅ กำไร : ' + number_truncate(profit, botSetup_precision_margin) + ' ' + config['MARGIN']
                        )
                    else:
                        msg = (
                            '🔴 *ขายขาดทุน!*' +
                            '\n📦 ออเดอร์ที่ : ' + str(order_no) +
                            '\n💰 ขาย : ' + symbol +
                            '\n💵 ที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + config['MARGIN'] +
                            '\n📉 ขาดทุน : ' + number_truncate(profit, botSetup_precision_margin) + ' ' + config['MARGIN']
                        )
                elif side == 'sell_dca':
                    msg = (
                        '🔵 *ขาย DCA!*' +
                        '\n📦 ออเดอร์ที่ : ' + str(order_no) +
                        '\n💰 ขาย : ' + symbol +
                        '\n💵 ที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + config['MARGIN'] +
                        '\n✅ กำไร : ' + number_truncate(profit, botSetup_precision_margin) + ' ' + config['MARGIN']
                    )
                elif side == 'sell_clear':
                    msg = (
                        '⚪ *เคลียร์ออเดอร์!*' +
                        '\n💰 เหรียญ : ' + symbol +
                        '\n📦 จำนวนออเดอร์ : ' + str(ordercount) +
                        '\n💵 ที่ราคา : ' + number_truncate(price, botSetup_precision_coin) + ' ' + config['MARGIN'] +
                        '\n✅ กำไรจากการเคลียร์ : ' + number_truncate(profit, botSetup_precision_margin) + ' ' + config['MARGIN']
                    )
            else:
                msg = notifyMsg
            telegram.send(msg, parse_mode='Markdown')
    except Exception as error_is:
        logger.debug('telegram function error : ' + str(error_is))
        print('!!! telegram function error !!!')

# ฟังก์ชั่นเทรด
def buy(client, ask, ordersize, cmd): # cmd 1 -> buy first order, 2 -> buy DCA
    try:
        logger.debug('buy : ' + '{:.8f}'.format(ask) + ' / ' + str(ordersize) + ' / ' + str(cmd))
        symbol = config['COIN'] + config['MARGIN']

        qty_size = round(ordersize / ask, lot_precision)
        qty_amt = qty_size * ask
        while qty_amt < minNotional:
            qty_size += lot_size
            qty_amt = qty_size * ask
        logger.debug(f'qty_size : {qty_size:.{lot_precision}f}')
        # lot_size = ordersize / ask
        # lot_size = round(lot_size, 0)
        # logger.debug('lot_size : ' + str(lot_size))
        buy_order = client.order_limit_buy(
            symbol=symbol.upper(),
            quantity=f'{qty_size:.{lot_precision}f}',
            price=f'{ask:.{botSetup_precision_coin}f}')
        temp_write(buy_order['clientOrderId'], cmd, buy_order)
        return 1
    except Exception as e:
        logger.debug('buy() : BN error code = ' + str(e))
        logger.exception('buy() : ' + str(e))
        time.sleep(botSetup_system_delay)
        return 0

def sell(client, bid, qty_size, cmd): # cmd 3 -> sell profit, 4 -> sell dca, 5 -> sell clear
    try:
        qty_size = round(qty_size, lot_precision)
        logger.debug('sell : ' + '{:.8f}'.format(bid) + ' / ' + f'{qty_size:.{lot_precision}f}' + ' / ' + str(cmd))
        symbol = config['COIN'] + config['MARGIN']
        # lot_size = ordersize / bid
        # lot_size = round(lot_size, 0)
        # logger.debug('lot_size : ' + str(lot_size))
        sell_order = client.order_limit_sell(
            symbol=symbol.upper(),
            quantity=f'{qty_size:.{lot_precision}f}',
            price=f'{bid:.{botSetup_precision_coin}f}')
        temp_write(sell_order['clientOrderId'], cmd, sell_order)
        return 1
    except Exception as e:
        logger.debug('sell() : BN error code = ' + str(e))
        logger.exception('sell() : ' + str(e))
        time.sleep(botSetup_system_delay)
        return 0

# ฟังก์ชั่นโชว์ข้อความบน console ในกรณี skip การส่งคำสั่ง
def show_skip_text():
    print('> Skip for safe filling')

# ฟังก์ชั่นโชว์ข้อความบน console ในกรณีเกิด error การส่งคำสั่ง
def show_error_text():
    print('> Error for buy/sell order, please check log file')

#########################
### $$$ Websocket $$$ ###
#########################
pid_signature = None # pid signature ป้องกันการรันบอทซ้อนกัน

def on_close(connect):
    print('Websocket : closed')
def on_message(connect, message):
    global pid_signature
    try:
        # config
        config = read_config()
        if config == 0:
            # time.sleep(botSetup_system_delay)
            # return
            raise SystemExit("Can not read config file")
        
        # # credentials สำหรับ exchange
        # api_key = config['KEY']
        # api_secret = config['SECRET']
        # api_tld = config['TLD'].lower()
        # try:
        #     if api_tld == 'th':
        #         client = Client(api_key, api_secret, tld=api_tld)
        #     else:
        #         client = Client(api_key, api_secret)
        # except Exception as error_is:
        #     # throw error
        #     print('connect exchange : ' + str(error_is))
        #     logger.info('connect exchange : ' + str(error_is))
        #     time.sleep(botSetup_system_delay)
        #     raise error_is
        
        # datetime สำหรับ loop บอท
        datetime_now = datetime_now = datetime.now(timezone('Asia/Bangkok')).replace(tzinfo=None)
        
        ###############################
        # *** ป้องกันการรันบอทซ้อนกัน *** #
        ###############################
        try:
            fileName_last_active_txt = f'{path_data}/{fileName_last_active}.txt'
            with open(fileName_last_active_txt, 'r', encoding='utf-8') as read_last_active_txt:
                read_last_active_txt = read_last_active_txt.read()
                if read_last_active_txt == '':
                    last_active_update(datetime_now)
                    time.sleep(botSetup_pid_threshold)
                    return
                else:
                    ts_last_active_txt = datetime.strptime(read_last_active_txt, '%Y-%m-%d %H:%M:%S.%f').timestamp()
        except FileNotFoundError:
            last_active_update(datetime_now)
            ts_last_active_txt = 0
            time.sleep(botSetup_pid_threshold)
        except Exception:
            ts_last_active_txt = 0

        if pid_signature is None:
            pid_signature = datetime_now.timestamp()
            
        try:
            with open('BOT_PID_FILE', 'r', encoding='utf-8') as pid_file:
                pid_file = float(pid_file.read())
        except FileNotFoundError:
            with open('BOT_PID_FILE', 'w', encoding='utf-8') as pid_file:
                pid_file = pid_file.write(str(pid_signature))
            with open('BOT_PID_FILE', 'r', encoding='utf-8') as pid_file:
                pid_file = float(pid_file.read())

        if pid_signature != pid_file:
            if ts_last_active_txt == 0:
                return
            elif pid_signature - float(ts_last_active_txt) > botSetup_pid_threshold:
                with open('BOT_PID_FILE', 'w', encoding='utf-8') as pid_file:
                    pid_file = pid_file.write(str(pid_signature))
                    return
            else:
                pid_signature = datetime.today().timestamp()
                print('!!! Running bots repeatedly is not allowed. Please Wait... !!!')
                time.sleep(botSetup_pid_threshold)
                return
        last_active_update(datetime_now)
        ###############################
        
        ###############################
        # *** แจ้งเตือนบอทหยุดทำงาน *** #
        ###############################
        try:
            if config['TELEGRAM'] == 1 and ts_last_active_txt != 0:
                ts_now = datetime_now.timestamp()
                #threshold ถ้าเวลาใน last_active file ต่างกับเวลาปัจจุบันเกินค่าที่ตั้งไว้
                if ts_now - ts_last_active_txt > botSetup_ts_threshold:
                    str_last_active_txt = datetime.fromtimestamp(ts_last_active_txt).strftime('%d/%m/%y %H:%M:%S')
                    str_time_now = datetime.fromtimestamp(ts_now).strftime('%d/%m/%y %H:%M:%S')
                    # ส่งแจ้งเตือน               
                    msg = '🔴 *บอทหยุดทำงาน*\nเมื่อ : ' + str_last_active_txt + '\n🟢 *กลับมาทำงาน*\nเมื่อ : ' + str_time_now
                    telegram_notify(False, msg, None, None, None, None, None, None)
        except Exception as error_is:
            print('check_bot_stop : '+str(error_is))
            logger.info('check_bot_stop : '+str(error_is))
            time.sleep(botSetup_system_delay)
            return
        ###############################
        
        ##############################
        # *** ระบบฐานข้อมูลของบอท *** #
        ##############################
        try:
            dbcon = sqlite3.connect(f'{path_data}/{fileName_database}.db')
            dbcursor = dbcon.cursor()
            dbcursor.execute('create table if not exists orders(id integer primary key, rate real, base_amt real, coin_amt real, fee_amt real, pricerange integer, ts integer)')
            dbcursor.execute('create table if not exists sold(id integer primary key, total_profit real)')
        except Exception as error_is:
            logger.info('database : ' + str(error_is))
            print('database : ' + str(error_is))
            time.sleep(botSetup_system_delay)
            return
        ##############################

        # ฟังก์ชั่นเรียกดูจำนวนออเดอร์ เพราะมีการเรียกหลายรอบใน operate()
        def fetch_db_ordercount():
            dbcursor.execute('select * from orders')
            db_res = dbcursor.fetchall()
            return len(db_res)
        db_ordercount = fetch_db_ordercount()
        try:
            if db_ordercount > 0:
                dbcursor.execute('select ts from orders where id=(select min(id) from orders)')
                db_res = dbcursor.fetchone()
                db_firstorder_ts = db_res[0] # timestamp ออเดอร์แรก
                dbcursor.execute('select rate from orders where id=(select max(id) from orders)')
                db_res = dbcursor.fetchone()
                db_lastorder_price = db_res[0] # เรทของออเดอร์ล่าสุด(ราคาที่ต่ำที่สุด)
                dbcursor.execute('select coin_amt from orders where id=(select max(id) from orders)')
                db_res = dbcursor.fetchone()
                db_lastorder_coin_amt = db_res[0] # จำนวนโทเคนของออเดอร์ล่าสุด
                dbcursor.execute('select base_amt from orders where id=(select max(id) from orders)')
                db_res = dbcursor.fetchone()
                db_lastorder_base_amt = db_res[0] # จำนวน base ของออเดอร์ล่าสุด
                dbcursor.execute('select max(pricerange) from orders')
                db_res = dbcursor.fetchone()
                db_pricerange = db_res[0] # pricerange จากออเดอร์แรก
                dbcursor.execute('select base_amt from orders where id=(select min(id) from orders)')
                db_res = dbcursor.fetchone()
                db_firstorder_cost = db_res[0] # cost ออเดอร์แรก
                dbcursor.execute('select sum(base_amt) from orders')
                db_res = dbcursor.fetchone()
                db_total_base = db_res[0] # ผลรวม total base
                dbcursor.execute('select sum(coin_amt) from orders')
                db_res = dbcursor.fetchone()
                db_total_coin = db_res[0] #ผลรวม total coin
                dbcursor.execute('select sum(fee_amt) from orders')
                db_res = dbcursor.fetchone()
                db_total_fee = db_res[0] # ผลรวม total fee
                dbcursor.execute('select sum(total_profit) from sold')
                db_res = dbcursor.fetchone()
                db_sold_total_profit = db_res[0] # ผลรวม total profit จาก sold
                if db_sold_total_profit is None:
                    db_sold_total_profit = 0
                if db_ordercount > 1:
                    dbcursor.execute('select rate from orders where id=(select max(?) from orders)',(db_ordercount - 1,))
                    db_res = dbcursor.fetchone()
                    db_dca_sell_price = db_res[0] # เรทของออเดอร์รองล่าสุด
                else:
                    db_dca_sell_price = 0
            else:
                db_firstorder_ts = 0
                db_lastorder_price = 0
                db_lastorder_coin_amt = 0
                db_lastorder_base_amt = 0
                db_pricerange = 0
                db_firstorder_cost = 0
                db_total_base = 0
                db_total_coin = 0
                db_total_fee = 0
                db_sold_total_profit = 0
                db_dca_sell_price = 0
        except Exception as error_is:
            logger.info('database orders : ' + str(error_is))
            print('database orders : ' + str(error_is))
            return

        # Break-even
        if db_ordercount > 0:
            break_even = (((((db_total_fee / db_total_base) * 100) * 2) / 100) * ((db_total_base - db_sold_total_profit) / db_total_coin)) + ((db_total_base - db_sold_total_profit) / db_total_coin)
        else:
            break_even = None

        # Ask, Bid
        try:
            symbol = config['COIN'] + config['MARGIN']
            msg = json.loads(message)
            if ((msg['stream'] == symbol.lower()+'@ticker' or msg['stream'] == symbol.lower()+'@bookTicker') \
                and msg['data']['s'] == symbol.upper()):
                ask = float(msg['data']['a'])
                ask_size_coin = float(msg['data']['A'])
                ask_size_margin = ask_size_coin * ask
                bid = float(msg['data']['b'])
                bid_size_coin = float(msg['data']['B'])
            else:
                logger.debug(message)
                return
        except Exception:
            logger.exception('websocket message parse error')
            return
        
        # circle period
        try:
            if db_firstorder_ts != 0:
                date_time_first_order = datetime.fromtimestamp(db_firstorder_ts)
                current_timestamp = datetime.timestamp(datetime_now)
                date_time_current = datetime.fromtimestamp(current_timestamp)
                time_diff = date_time_current - date_time_first_order
                years = time_diff.days // 365
                if years > 0:
                    months = time_diff.days % 365 // 30
                else:
                    months = (time_diff.days % 365 // 30) if (time_diff.days % 365 // 30) > 0 else 0
                days = time_diff.days % 365 % 30
                hours = time_diff.seconds // 3600
                minutes = (time_diff.seconds % 3600) // 60
                seconds = time_diff.seconds % 60
                time_components = []
                if years > 0:
                    time_components.append(f'{years} years')
                if months > 0:
                    time_components.append(f'{months} months')
                if days > 0:
                    time_components.append(f'{days} days')
                if hours > 0:
                    time_components.append(f'{hours} hours')
                if minutes > 0:
                    time_components.append(f'{minutes} minutes')
                if seconds > 0:
                    time_components.append(f'{seconds} seconds')
                time_diff_str = ', '.join(time_components)
                circle_period = time_diff_str
            else:
                circle_period = None
        except Exception as error_is:
            logger.info('circle_period : ' + str(error_is))
            logger.exception(error_is)
            print('circle_period : ' + str(error_is))
            return
        
            
        def order_operate():
            temp = temp_read()
            if temp['HASH'] == '':
                return 0
            else:
                symbol = config['COIN'].upper() + config['MARGIN'].upper()
                clientOrderId = temp['HASH']

                try:
                    order_info = client.get_order(symbol=symbol, origClientOrderId=clientOrderId)
                except Exception as e:
                    logger.exception('order_operate() : ' + str(e))
                    if 'code=-2013' in str(e):
                        # order not found, clear temp
                        temp_write('', 0, '')
                        print('Order ' + clientOrderId + ' not found, clearing temp...')
                        return 1
                    elif 'code=-2011' in str(e):
                        # unknown order, clear temp
                        temp_write('', 0, '')
                        print('Order ' + clientOrderId + ' unknown, clearing temp...')
                        return 1
                    else:
                        time.sleep(botSetup_system_delay)
                        return 0
                
                print('Order ' + temp['HASH'] + ' Filling')
                while order_info['status'].lower() not in ['filled', 'cancelled']:
                    order_info = client.get_order(symbol=symbol, origClientOrderId=clientOrderId)
                
                logger.debug(order_info)

                if order_info['status'] == 'cancelled':
                    temp_write('', 0, '')
                    return 1
                
                if float(order_info['price']) > 0:
                    executed_qty = float(order_info['executedQty'])  # จำนวนเหรียญที่ซื้อได้ (ยังไม่หักค่าคอม)
                    if api_tld == 'th':
                        base_amt = float(order_info['cumulativeQuoteQty'])  # USDT ที่ใช้ซื้อ
                    else:
                        base_amt = float(order_info['cummulativeQuoteQty'])
                    rate = float(order_info['price'])
                    
                    # fee_amt = executed_qty * 0.0001 * rate
                    fee_amt = base_amt * 0.001  # ✅ ค่าคอม = 0.1% ของ USDT
                    coin_amt = executed_qty - (executed_qty * 0.001)  # ปรับจำนวนเหรียญที่ซื้อได้หลังหักค่าคอม
                    coin_amt = float(number_truncate(coin_amt, lot_precision))  # ตัดทศนิยมตาม lot_precision (ไม่ปัดเศษ)
                    
                    if 'updateTime' in order_info:
                        ts_sec = int(order_info['updateTime']) / 1000
                    else:
                        ts_sec = int(time.time())
                else:
                    temp_for_order = temp_read()['detail']
                    if not temp_for_order.get('fills') or len(temp_for_order['fills']) == 0:
                        logger.debug('order filled but no fills info, skipping...')
                        temp_write('', 0, '')
                        return 1
                    # print(temp_for_order)
                    executed_qty = float(temp_for_order['fills'][0]['qty'])
                    if api_tld == 'th':
                        base_amt = float(order_info['cumulativeQuoteQty'])
                    else:
                        base_amt = float(order_info['cummulativeQuoteQty'])

                    rate = float(temp_for_order['fills'][0]['price'])
                    fee_amt = base_amt * 0.001
                    coin_amt = executed_qty - (executed_qty * 0.001)

                    #  ถ้า transactTime ไม่มี ให้ fallback ไปใช้ updateTime
                    if 'transactTime' in temp_for_order:
                        ts_sec = int(temp_for_order['transactTime']) / 1000
                    elif 'updateTime' in order_info:
                        ts_sec = int(order_info['updateTime']) / 1000
                    else:
                        ts_sec = int(time.time())

                logger.debug(f"base_amt:{base_amt}, coin_amt:{coin_amt:.{lot_precision}f}, rate:{rate}, fee_amt:{fee_amt}, ts_sec:{ts_sec}")
                if temp['cmd'] == 1:
                    pricerange = ask / config['MAX_ORDER'] # คำนวณ pricerage
                    dbcursor.execute('insert into orders (rate, base_amt, coin_amt, fee_amt, pricerange, ts)values(?, ?, ?, ?, ?, ?)',(rate, base_amt, coin_amt, fee_amt, pricerange, ts_sec))
                    dbcon.commit()
                    print(f'-- BUY first order filled ({temp["HASH"]}) --')
                    temp_write('', 0, '')
                    db_ordercount = fetch_db_ordercount()
                    print(f'> OrderCount ({db_ordercount}/{config["MAX_ORDER"]})')
                    stat_add_circle_total()
                    orders_verbose('buy', db_ordercount, order_info)
                    telegram_notify(True, None, db_ordercount, 'buy', rate, base_amt, 0, 0)
                elif temp['cmd'] == 2:
                    # temp_for_order = temp_read()['detail']['result']
                    dbcursor.execute('insert into orders (rate, base_amt, coin_amt, fee_amt, pricerange, ts)values(?, ?, ?, ?, ?, ?)',(rate, base_amt, coin_amt, fee_amt, 0, ts_sec))
                    dbcon.commit()
                    print(f'-- BUY DCA order filled ({temp["HASH"]}) --')
                    temp_write('', 0, '')
                    db_ordercount = fetch_db_ordercount()
                    print(f'> OrderCount ({db_ordercount}/{config["MAX_ORDER"]})')
                    orders_verbose('buy DCA', db_ordercount, order_info)
                    telegram_notify(True, None, db_ordercount, 'buy', rate, base_amt, 0, 0)
                elif temp['cmd'] == 3:
                    # temp_for_order = temp_read()['detail']['result']
                    order_profit = (base_amt + db_sold_total_profit) - db_total_base
                    db_ordercount = fetch_db_ordercount()
                    dbcursor.execute('delete from sold')
                    dbcursor.execute('delete from orders')
                    dbcon.commit()
                    print(f'-- SELL order filled ({temp["HASH"]}) --')
                    temp_write('', 0, '')
                    db_ordercount = fetch_db_ordercount()
                    stat_add_profit_total(order_profit)
                    # ในกรณีมีการขาย dca แต่ไม่เข้าเงื่อนไข sell clear(5) ที่ต้องมีหลายออเดอร์ จะถือว่าเป็น sell clear profit
                    if db_sold_total_profit == 0:
                        sell_type = 'sell profit'
                    else:
                        sell_type = 'sell clear profit'
                    orders_verbose(sell_type, db_ordercount + 1, order_info)
                    telegram_notify(True, None, db_ordercount + 1, 'sell_profit', rate, 0, order_profit, 0)
                elif temp['cmd'] == 4:
                    # temp_for_order = temp_read()['detail']['result']
                    order_profit = base_amt - db_lastorder_base_amt
                    db_ordercount = fetch_db_ordercount()
                    dbcursor.execute('delete from orders where id=?',(db_ordercount,))
                    dbcursor.execute('insert into sold (total_profit)values(?)',(order_profit,))
                    dbcon.commit()
                    print(f'-- SELL DCA order filled ({temp["HASH"]}) --')
                    temp_write('', 0, '')
                    db_ordercount = fetch_db_ordercount()
                    print(f'> OrderCount ({db_ordercount}/{config["MAX_ORDER"]})')
                    orders_verbose('sell dca', db_ordercount + 1, order_info)
                    telegram_notify(True, None, db_ordercount + 1, 'sell_dca', rate, 0, order_profit, 0)
                elif temp['cmd'] == 5:
                    # temp_for_order = temp_read()['detail']['result']
                    order_profit = (base_amt + db_sold_total_profit) - db_total_base
                    db_ordercount = fetch_db_ordercount()
                    dbcursor.execute('delete from sold')
                    dbcursor.execute('delete from orders')
                    dbcon.commit()
                    print(f'-- SELL Clear order filled ({temp["HASH"]}) --')
                    temp_write('', 0, '')
                    stat_add_profit_total(order_profit)
                    orders_verbose('sell clear', db_ordercount, order_info)
                    telegram_notify(True, None, 0, 'sell_clear', rate, 0, order_profit, db_ordercount)
                return 1
                
        # $$$$$$$$$$$$$$$$$$$$$$$ #
        # $$$$$$ Condition $$$$$$ #
        # $$$$$$$$$$$$$$$$$$$$$$$ #
        
        # เช็คว่ามี hash ค้างไหม ถ้ามีแล้วถูก operate ให้ return
        if order_operate() == 1:
            return

        if db_ordercount < 1: # ถ้าไม่มีออเดอร์ในหน้าตัก
            # เช็คว่า config อนุญาตไหม (stopnextcircle = 0 หรือเปล่า)
            if config['STOPNEXTCIRCLE'] != 0:
                print('STOPNEXTCIRCLE != 0')
                return
            # คำนวณ order size
            try:
                if config['ALL_IN'] == 0:
                    ordersize = config['ORDER_SIZE']
                else:
                    balance = client.get_asset_balance(asset=config['MARGIN'].upper())
                    balance_free = float(balance['free']) if balance else 0.0
                    ordersize = balance_free / config['MAX_ORDER']
            except Exception as error_is:
                logger.info('ordersize cal : ' + str(error_is))
                print('ordersize cal : ' + str(error_is))
                return
            # ส่งคำสั่งซื้อออเดอร์แรก ถ้าส่งคำสั่งสำเร็จให้ return
            if ask_size_margin > ordersize:
                if buy(client, ask, ordersize, 1) == 1:
                    return
                else:
                    show_error_text()
                    return
            else:
                show_skip_text()
                return
        else: # ถ้ามีออเดอร์ในหน้าตัก  ซื้อ DCA
            if ask < db_lastorder_price - db_pricerange: # buy dca
                if db_ordercount < config['MAX_ORDER']:

                    # 1) อ่านยอดเงินคงเหลือของ quote asset (เช่น USDT)
                    try:
                        balance = client.get_asset_balance(asset=config['MARGIN'].upper())
                        balance_free = float(balance['free']) if balance else 0.0
                    except Exception as e:
                        logger.info('get_asset_balance error: ' + str(e))
                        # ถ้าอ่าน balance ไม่ได้ ให้ข้ามรอบนี้ไปก่อน
                        time.sleep(botSetup_system_delay)
                        return

                    # 2) จำนวนเงินที่ต้องใช้ซื้อ DCA เท่ากับค่า cost ของออเดอร์แรก
                    required_usdt = float(db_firstorder_cost)
                    # 3) กันค่าคอม/ส่วนเผื่อเล็กน้อย (เช่น 0.1%) เพื่อไม่ให้ติดลบตอนส่งจริง
                    required_usdt_with_fee = required_usdt * 1.001
                    # 4) ต้องไม่ต่ำกว่า minNotional ด้วย (กัน error จาก Exchange)
                    if required_usdt_with_fee < minNotional:
                        # เล็กเกินไป ข้ามไปก่อน
                        show_skip_text()
                        return

                    # 5) เช็คให้พอจริงก่อนส่งคำสั่ง
                    if balance_free >= required_usdt_with_fee:
                        # (ออปชัน) เดิมมีการเช็คสภาพคล่องด้วย ask_size_margin > db_firstorder_cost
                        # สำหรับ limit order ไม่จำเป็นต้องใช้เงื่อนไขนี้ก็ได้
                        if buy(client, ask, required_usdt, 2) == 1:
                            return
                        else:
                            # buy() ภายในจะจับ exception และคืน 0 มาแล้ว
                            # ไม่ต้องแจ้งหน้า console ตามที่ต้องการ
                            # ถ้าต้องการแจ้ง Telegram ว่าส่งคำสั่งไม่สำเร็จ สามารถใส่ได้ที่นี่
                            return
                    else:
                        # 6) เงินไม่พอ -> แจ้งเตือน Telegram แต่ไม่ขึ้นหน้า console
                        global last_dca_insufficient_notify_ts
                        symbol = config['COIN'].upper() + config['MARGIN'].upper()
                        now_ts = time.time()
                        if now_ts - last_dca_insufficient_notify_ts >= 3600:
                            msg = (
                                '⚠️ *ยอดเงินไม่พอสำหรับ DCA*'
                                f'\n💱 เหรียญ : *{symbol}*'
                                f'\n💵 ต้องใช้ : {number_truncate(required_usdt_with_fee, botSetup_precision_margin)} {config["MARGIN"].upper()}'
                                f'\n💰 คงเหลือ : {number_truncate(balance_free, botSetup_precision_margin)} {config["MARGIN"].upper()}'
                                f'\n⛔ งดส่งคำสั่งซื้อ DCA'
                            )
                            telegram_notify(False, msg, None, None, None, None, None, None)
                            last_dca_insufficient_notify_ts = now_ts
                        return
            if db_ordercount == 1: # ถ้ามีแค่ 1 ออเดอร์
                if bid > db_lastorder_price + db_pricerange: # sell profit
                    if bid_size_coin > db_total_coin:
                        if sell(client, bid, db_total_coin, 3) == 1:
                            return
                        else:
                            show_error_text()
                            return
                    else:
                        show_skip_text()
                        return
            else: # ถ้ามี 2 ออเดอร์ขึ้นไป
                if bid >= break_even: # sell clear
                    if bid_size_coin > db_total_coin:
                        if sell(client, bid, db_total_coin, 5) == 1:
                            return
                        else:
                            show_error_text()
                            return
                elif bid >= db_dca_sell_price: # sell dca
                    if bid_size_coin > db_lastorder_coin_amt:
                        if sell(client, bid, db_lastorder_coin_amt, 4) == 1:
                            return
                        else:
                            show_error_text()
                            return
                    else:
                        show_skip_text()
                        return
            
        #$$$$$$$$$$$$$$$$$$$$$$$$$$
        #   โชว์สถิติและข้อมูลออเดอร์   #
        #$$$$$$$$$$$$$$$$$$$$$$$$$$
        
        # price table
        header = [' Symbol ', Back.RED + Fore.WHITE + Style.BRIGHT + ' Ask ' + Style.RESET_ALL, Back.GREEN + Fore.WHITE + Style.BRIGHT + ' Bid ' + Style.RESET_ALL, Back.YELLOW + Style.BRIGHT + ' Break-Even ' + Style.RESET_ALL + Style.RESET_ALL, ' Price Range ']

        # distance last order price
        if bid > db_lastorder_price:
            distance_lastorder = ((bid - db_lastorder_price) / db_lastorder_price) * 100
            distance_lastorder = Style.BRIGHT + 'DistanceLastOrder' + Style.RESET_ALL + ' : ' + number_truncate(distance_lastorder, 4) + ' % ( ' + number_truncate(bid - db_lastorder_price, botSetup_precision_coin) + ' ' + config['MARGIN'] + ' )\n'
        elif bid < db_lastorder_price:
            distance_lastorder = ((db_lastorder_price - ask) / db_lastorder_price) * 100
            distance_lastorder = Style.BRIGHT + 'DistanceLastOrder' + Style.RESET_ALL + ' : ' + number_truncate(distance_lastorder * -1, 4) + ' % ( ' + number_truncate((db_lastorder_price - ask) * -1, botSetup_precision_coin) + ' ' + config['MARGIN'] + ' )\n'
        else:
            distance_lastorder = Style.BRIGHT + 'DistanceLastOrder' + Style.RESET_ALL + ' : 0.0 % ( 0.0 ' + config['MARGIN'] + ' )\n'

        # price range show
        pricerange_show = db_pricerange

        pricerange_show = number_truncate(pricerange_show, botSetup_precision_coin)

        data = [[config['COIN'] + config['MARGIN'], number_truncate(ask, botSetup_precision_coin), number_truncate(bid, botSetup_precision_coin), number_truncate(break_even, botSetup_precision_coin), pricerange_show]]
        price_table_show = tabulate(
            data, 
            header, 
            tablefmt="rounded_outline", 
            disable_numparse=True, 
            stralign='center', 
            numalign='center'
        )
        # orders table
        dbcursor.execute('select * from orders')
        db_res = dbcursor.fetchall()
        
        #ordercount for show
        if db_ordercount < config['MAX_ORDER']:
            order_table_order_count = Style.BRIGHT + 'OrderCount' + Style.RESET_ALL + ' : ' + str(len(db_res)) + '/' + str(config['MAX_ORDER'])
        else:
            order_table_order_count = Style.BRIGHT + 'OrderCount' + Style.RESET_ALL + ' : ' + Back.RED + Fore.WHITE + Style.BRIGHT + ' ' + str(len(db_res)) + '/' + str(config['MAX_ORDER']) + ' ' + Style.RESET_ALL
            
        order_table_circle_period = Style.BRIGHT + 'Circle Period' + Style.RESET_ALL + ' : ' + circle_period

        header = [Back.WHITE + Fore.BLACK + Style.BRIGHT + ' No. ' + Style.RESET_ALL, Back.WHITE + Fore.BLACK + Style.BRIGHT + ' Rate ' + Style.RESET_ALL, Back.WHITE + Fore.BLACK + Style.BRIGHT + ' Cost ' + Style.RESET_ALL, Back.WHITE + Fore.BLACK + Style.BRIGHT + ' Amount ' + Style.RESET_ALL, Back.WHITE + Fore.BLACK + Style.BRIGHT + ' Fee ' + Style.RESET_ALL]
        data = []
        for row in db_res:
            data.append((row[0], number_truncate(row[1], botSetup_precision_coin), number_truncate(row[2], botSetup_precision_margin) + ' ' + config['MARGIN'], number_truncate(row[3], botSetup_precision_coin), number_truncate(row[4], botSetup_precision_coin)))

        orders_table_show = tabulate(
            data, 
            header, 
            tablefmt="rounded_outline", 
            disable_numparse=True, 
            stralign='center', 
            numalign='center'
        )

        header = []
        stats = stat_read()
        if stats['profit_total'] == 0:
            header.append(Back.BLUE+Fore.WHITE + Style.BRIGHT + ' Profit Total ' + Style.RESET_ALL)
        elif stats['profit_total']>0:
            header.append(Back.GREEN+Fore.WHITE + Style.BRIGHT + ' Profit Total ' + Style.RESET_ALL)
        else:
            header.append(Back.RED + Fore.WHITE + Style.BRIGHT + ' Profit Total ' + Style.RESET_ALL)
        header.append(Back.MAGENTA + Fore.WHITE + Style.BRIGHT + ' Circle Total ' + Style.RESET_ALL)

        # check profit total
        if stats['profit_total'] == 0:
            profit_total_show = str(0.0) + ' ' + config['MARGIN']
        else:
            profit_total_show = number_truncate(stats['profit_total'], botSetup_precision_margin) + ' ' + config['MARGIN']
            
        data = [[profit_total_show, stats['circle_total']]]
        stats_table_show = tabulate(
            data, 
            header, 
            tablefmt="rounded_outline", 
            disable_numparse=True, 
            stralign='center', 
            numalign='center'
        )

        top = '\n'
        top += '█▀█ █▀█ █▀█ █▀▀ █▀█ █▀█ █▌▐ █▀▀ █▀█\n'
        top += '█▀█ █▀▀ █▀▀ █░░ █ █ █▀▄ █▐▐ █▀  █▀▄\n'
        top += '▀ ▀ ▀   ▀   ▀▀▀ ▀▀▀ ▀ ▀ ▀ ▀ ▀▀▀ ▀ ▀\n'
        top += Style.BRIGHT + bot_title.format(api_tld.upper()) + Style.RESET_ALL + '\n'
        top += Style.DIM + bot_title_orig + Style.RESET_ALL + '\n'
        loop_time = str(datetime_now.strftime('%Y-%m-%d %H:%M:%S'))
        top += '# ' + loop_time + '\n'
        print(CLS_SCREEN, end="")
        print(top + price_table_show + '\n' + distance_lastorder + order_table_order_count + '\n' + order_table_circle_period + '\n' + orders_table_show + '\n'+stats_table_show + '\n', end='')
        #$$$$$$$$$$$$$$$$$$$$$$$$$$ 
            
    except Exception as error:
        print('Websocket : ' + str(error))
        logger.exception('Websocket : ' + str(error))
    
if __name__ == '__main__':

    config = read_config()
    if config == 0:
        print('!!! config file not found !!!')
        exit(0)

    api_tld = config['TLD'].lower()
    symbol = config['COIN'] + config['MARGIN']
    if api_tld == 'th':
        path_data = f'./th_{symbol.lower()}'
    else:
        path_data = f'./en_{symbol.lower()}'

    # สำหรับ Windows OS
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(symbol.upper() + " " + bot_title.format(api_tld.upper()))
    
    pathlib.Path('./logs').mkdir(parents=True, exist_ok=True)
    pathlib.Path(path_data).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(f'{path_data}/{fileName_database}.db'):
        if os.path.exists(f'{fileName_database}.db'):
            shutil.move(f'{fileName_database}.db', f'{path_data}/{fileName_database}.db')
    if not os.path.exists(f'{path_data}/{fileName_last_active}.txt'):
        if os.path.exists(f'{fileName_last_active}.txt'):
            shutil.move(f'{fileName_last_active}.txt', f'{path_data}/{fileName_last_active}.txt')
    if not os.path.exists(f'{path_data}/{fileName_temp}.json'):
        if os.path.exists(f'{fileName_temp}.json'):
            shutil.move(f'{fileName_temp}.json', f'{path_data}/{fileName_temp}.json')
    if not os.path.exists(f'{path_data}/{fileName_stat}.json'):
        if os.path.exists(f'{fileName_stat}.json'):
            shutil.move(f'{fileName_stat}.json', f'{path_data}/{fileName_stat}.json')
    if not os.path.exists(f'{path_data}/{fileName_orders_verbose}.txt'):
        if os.path.exists(f'{fileName_orders_verbose}.txt'):
            shutil.move(f'{fileName_orders_verbose}.txt', f'{path_data}/{fileName_orders_verbose}.txt')

    try:
        log_level = logging.DEBUG
        logger = logging.getLogger("BN_SYY")
        logger.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler = RotatingFileHandler(f'./logs/{fileName_log}.log', maxBytes=250000, backupCount=10)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        logger.info('===== BN_SYY start =====')

        print(HIDE_CURSOR, end="")
        while True:
            try:
                config = read_config()
                if config == 0:
                    time.sleep(botSetup_system_delay)
                    continue

                if config['TELEGRAM'] == 1:
                    telegram_token = config['TOKEN']
                    telegram_chatid = config['CHATID']
                    telegram = TelegramNotify(telegram_token, telegram_chatid)
                    if telegram.Get_ChatID() is None:
                        break

                api_key = config['KEY']
                api_secret = config['SECRET']
                api_tld = config['TLD'].lower()
                try:
                    if api_tld == 'th':
                        client = Client(api_key, api_secret, tld=api_tld)
                    else:
                        client = Client(api_key, api_secret)
                except Exception as error_is:
                    # throw error
                    print('connect exchange : ' + str(error_is))
                    logger.info('connect exchange : ' + str(error_is))
                    time.sleep(botSetup_system_delay)
                    continue

                exchange_info = client.get_exchange_info()
                symbol = config['COIN'] + config['MARGIN']
                logger.debug('symbol: ' + symbol.upper())

                found = any(item['symbol'] == symbol.upper() for item in exchange_info['symbols'])
                if found:
                    symbol_info = client.get_symbol_info(symbol.upper())
                    logger.debug(symbol_info)
                    botSetup_precision_coin = symbol_info['quoteAssetPrecision']
                    logger.debug(f'set botSetup_precision_coin: {botSetup_precision_coin}')
                    for f in symbol_info['filters']:
                        if f['filterType'] == 'NOTIONAL':
                            minNotional = float(f['minNotional'])
                            logger.debug(f'minNotional: {minNotional}')
                        elif f['filterType'] == 'MIN_NOTIONAL':
                            minNotional = float(f['minNotional'])
                            logger.debug(f'minNotional: {minNotional}')
                        elif f['filterType'] == 'LOT_SIZE':
                            lot_size = float(f['stepSize'])
                            lot_precision = int(round(-math.log(lot_size, 10), 0))
                            logger.debug(f'lot_size: {lot_size:.{lot_precision}f}')
                            logger.debug(f'lot_precision: {lot_precision}')
                    if minNotional > config['ORDER_SIZE']:
                        print('> Minimum order for ' + symbol.upper() + ' is ' + str(minNotional) + ' ' + config['MARGIN'].upper())
                        print('!!! ORDER_SIZE in config.json is too small !!!')
                        time.sleep(botSetup_system_delay)
                        continue
                    if api_tld == 'th':
                        if config['MARGIN'].upper() == 'THB':
                            socket = 'wss://stream-th.2meta.app/stream?streams={}@ticker'.format(symbol.lower())
                        else:
                            socket = 'wss://www.binance.th/stream?streams={}@ticker'.format(symbol.lower())
                    else:
                        socket = 'wss://fstream.binance.com/stream?streams={}@ticker'.format(symbol.lower())
                    connect = websocket.WebSocketApp(socket, on_message=on_message, on_close=on_close)
                    connect.run_forever()
                else:
                    print('!!! ' + symbol.upper() + ' was not found in BN !!!')
                    time.sleep(botSetup_system_delay)
            except Exception as error:
                print('Core : ' + str(error))
                logger.exception('Core : ' + str(error))
                # clear websocket connection
                connect.close()
                connect = None
                time.sleep(botSetup_system_delay)

    except KeyboardInterrupt:
        print(CLS_LINE+'\rbye')

    except Exception as ex:
        print(type(ex).__name__, str(ex))
        logger.exception('SYY stop with error')

    finally:
        print(SHOW_CURSOR, end="")
        logger.info('===== BN_SYY stop =====')

#poetry run pyinstaller app.py --add-data "D:/pypoetry/Cache/virtualenvs/bn-syy-Efwh64a3-py3.12/Lib/site-packages/dateparser/data/dateparser_tz_cache.pkl;dateparser/data" --icon=ATK_new.ico --clean --collect-submodules application --onefile --name bn_syy
#pyinstaller app.py --add-data "<python lib path>/site-packages/dateparser/data/dateparser_tz_cache.pkl;dateparser/data" --icon=ATK_new.ico --clean --collect-submodules application --onefile --name bn_syy