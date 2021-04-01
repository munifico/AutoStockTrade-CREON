import os, sys, ctypes
import win32com.client
import pandas as pd
from datetime import datetime
from slacker import Slacker
import time, calendar

slack = Slacker('xoxb-1732937242453-1736270685187-hHO1EartFxxy1XThNzCLa9n0')
def dbgout(message):
    """인자로 받은 문자열을 파이썬 셸과 슬랙으로 동시에 출력한다."""
    print(datetime.now().strftime('[%m/%d %H:%M:%S]'), message)
    strbuf = datetime.now().strftime('[%m/%d %H:%M:%S] ') + message
    slack.chat.post_message('#stockauto', strbuf)

def printlog(message, *args):
    """인자로 받은 문자열을 파이썬 셸에 출력한다."""
    print(datetime.now().strftime('[%m/%d %H:%M:%S]'), message, *args)
 
# 크레온 플러스 공통 OBJECT
cpCodeMgr = win32com.client.Dispatch('CpUtil.CpStockCode')
cpStatus = win32com.client.Dispatch('CpUtil.CpCybos')
cpTradeUtil = win32com.client.Dispatch('CpTrade.CpTdUtil')
cpStock = win32com.client.Dispatch('DsCbo1.StockMst')
cpOhlc = win32com.client.Dispatch('CpSysDib.StockChart')
cpBalance = win32com.client.Dispatch('CpTrade.CpTd6033')
cpCash = win32com.client.Dispatch('CpTrade.CpTdNew5331A')
cpOrder = win32com.client.Dispatch('CpTrade.CpTd0311')  

def check_creon_system():
    """크레온 플러스 시스템 연결 상태를 점검한다."""
    # 관리자 권한으로 프로세스 실행 여부
    if not ctypes.windll.shell32.IsUserAnAdmin():
        printlog('check_creon_system() : admin user -> FAILED')
        return False
 
    # 연결 여부 체크
    if (cpStatus.IsConnect == 0):
        printlog('check_creon_system() : connect to server -> FAILED')
        return False
 
    # 주문 관련 초기화 - 계좌 관련 코드가 있을 때만 사용
    if (cpTradeUtil.TradeInit(0) != 0):
        printlog('check_creon_system() : init trade -> FAILED')
        return False
    return True

def get_current_price(code):
    """인자로 받은 종목의 현재가, 매수호가, 매도호가를 반환한다."""
    cpStock.SetInputValue(0, code)  # 종목코드에 대한 가격 정보
    cpStock.BlockRequest()
    item = {}
    item['cur_price'] = cpStock.GetHeaderValue(11)   # 현재가
    item['ask'] =  cpStock.GetHeaderValue(16)        # 매수호가
    item['bid'] =  cpStock.GetHeaderValue(17)        # 매도호가    
    return item['cur_price'], item['ask'], item['bid']

def get_now_price(code):
    """인자로 받은 종목의 현재가, 매수호가, 매도호가를 반환한다."""
    cpStock.SetInputValue(0, code)  # 종목코드에 대한 가격 정보
    cpStock.BlockRequest()
    item = {}
    item['cur_price'] = cpStock.GetHeaderValue(11)   # 현재가
    return item['cur_price']

def get_ohlc(code, qty):
    """인자로 받은 종목의 OHLC 가격 정보를 qty 개수만큼 반환한다."""
    cpOhlc.SetInputValue(0, code)           # 종목코드
    cpOhlc.SetInputValue(1, ord('2'))        # 1:기간, 2:개수
    cpOhlc.SetInputValue(4, qty)             # 요청개수
    cpOhlc.SetInputValue(5, [0, 2, 3, 4, 5]) # 0:날짜, 2~5:OHLC
    cpOhlc.SetInputValue(6, ord('D'))        # D:일단위
    cpOhlc.SetInputValue(9, ord('1'))        # 0:무수정주가, 1:수정주가
    cpOhlc.BlockRequest()
    count = cpOhlc.GetHeaderValue(3)   # 3:수신개수
    columns = ['open', 'high', 'low', 'close']
    index = []
    rows = []
    for i in range(count): 
        index.append(cpOhlc.GetDataValue(0, i)) 
        rows.append([cpOhlc.GetDataValue(1, i), cpOhlc.GetDataValue(2, i),
            cpOhlc.GetDataValue(3, i), cpOhlc.GetDataValue(4, i)]) 
    df = pd.DataFrame(rows, columns=columns, index=index) 
    return df

def get_stock_balance(code):
    """인자로 받은 종목의 종목명과 수량을 반환한다."""
    cpTradeUtil.TradeInit()
    acc = cpTradeUtil.AccountNumber[0]      # 계좌번호
    accFlag = cpTradeUtil.GoodsList(acc, 1) # -1:전체, 1:주식, 2:선물/옵션
    cpBalance.SetInputValue(0, acc)         # 계좌번호
    cpBalance.SetInputValue(1, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
    cpBalance.SetInputValue(2, 50)          # 요청 건수(최대 50)
    cpBalance.BlockRequest()     
    if code == 'ALL_MSG':
        dbgout('계좌명: ' + str(cpBalance.GetHeaderValue(0)))
        dbgout('결제잔고수량 : ' + str(cpBalance.GetHeaderValue(1)))
        dbgout('평가금액: ' + str(cpBalance.GetHeaderValue(3)))
        dbgout('평가손익: ' + str(cpBalance.GetHeaderValue(4)))
        dbgout('종목수: ' + str(cpBalance.GetHeaderValue(7)))
    stocks = []
    for i in range(cpBalance.GetHeaderValue(7)):
        stock_code = cpBalance.GetDataValue(12, i)  # 종목코드
        stock_name = cpBalance.GetDataValue(0, i)   # 종목명
        stock_qty = cpBalance.GetDataValue(15, i)   # 수량
        stock_yield_ratio = cpBalance.GetDataValue(11, i)   # 수익률
        if code == 'ALL':
            stocks.append({'code': stock_code, 'name': stock_name, 
                'qty': stock_qty, 'yield_ratio': stock_yield_ratio})
        if code == 'ALL_MSG':
            dbgout(str(i+1) + ' ' + stock_code + '(' + stock_name + ')' 
                + ':' + str(stock_qty))
            stocks.append({'code': stock_code, 'name': stock_name, 
                'qty': stock_qty, 'yield_ratio': stock_yield_ratio})
        if stock_code == code:  
            return stock_name, stock_qty
    if code == 'ALL' or code == 'ALL_MSG':
        return stocks
    else:
        stock_name = cpCodeMgr.CodeToName(code)
        return stock_name, 0

def get_current_cash():
    """증거금 100% 주문 가능 금액을 반환한다."""
    cpTradeUtil.TradeInit()
    acc = cpTradeUtil.AccountNumber[0]    # 계좌번호
    accFlag = cpTradeUtil.GoodsList(acc, 1) # -1:전체, 1:주식, 2:선물/옵션
    cpCash.SetInputValue(0, acc)              # 계좌번호
    cpCash.SetInputValue(1, accFlag[0])      # 상품구분 - 주식 상품 중 첫번째
    cpCash.BlockRequest() 
    return cpCash.GetHeaderValue(9) # 증거금 100% 주문 가능 금액

def get_target_price(code):
    """매수 목표가를 반환한다."""
    try:
        time_now = datetime.now()
        str_today = time_now.strftime('%Y%m%d')
        ohlc = get_ohlc(code, 10)
        if str_today == str(ohlc.iloc[0].name):
            today_open = ohlc.iloc[0].open 
            lastday = ohlc.iloc[1]
        else:
            lastday = ohlc.iloc[0]                                      
            today_open = lastday[3]
        lastday_high = lastday[1]
        lastday_low = lastday[2]
        target_price = today_open + (lastday_high - lastday_low) * 0.3
        return target_price
    except Exception as ex:
        dbgout("`get_target_price() -> exception! " + str(ex) + "`")
        return None
    
def get_movingaverage(code, window):
    """인자로 받은 종목에 대한 이동평균가격을 반환한다."""
    try:
        time_now = datetime.now()
        str_today = time_now.strftime('%Y%m%d')
        ohlc = get_ohlc(code, 60)
        if str_today == str(ohlc.iloc[0].name):
            lastday = ohlc.iloc[1].name
        else:
            lastday = ohlc.iloc[0].name
        closes = ohlc['close'].sort_index()         
        ma = closes.rolling(window=window).mean()
        return ma.loc[lastday]
    except Exception as ex:
        dbgout('get_movingavrg(' + str(window) + ') -> exception! ' + str(ex))
        return None    

def buy_etf(code):
    """인자로 받은 종목을 최유리 지정가 FOK 조건으로 매수한다."""
    try:
        global bought_list      # 함수 내에서 값 변경을 하기 위해 global로 지정
        if code in bought_list: # 매수 완료 종목이면 더 이상 안 사도록 함수 종료
            #printlog('code:', code, 'in', bought_list)
            return False
        time_now = datetime.now()
        current_price, ask_price, bid_price = get_current_price(code) 
        target_price = get_target_price(code)    # 매수 목표가
        ma5_price = get_movingaverage(code, 5)   # 5일 이동평균가
        ma20_price = get_movingaverage(code, 20) # 20일 이동평균가
        ma60_price = get_movingaverage(code, 60) # 60일 이동평균가

        # 이미 매도한 종목이 있을경우 매도했던 금액과 현재금액을 비교하여 -4프로 이상의 차이가 있을시에만 매수.

        sell_end_list_idx = -1
        
        for s in sell_end_list:
            sell_end_list_idx = sell_end_list_idx + 1
            if code == s['code']:
                if current_price >= (s['sell_price'] - (s['sell_price']*0.03)):
                    return False
        
        buy_qty = 0        # 매수할 수량 초기화
        if ask_price > 0:  # 매수호가가 존재하면   
            buy_qty = buy_amount // ask_price  
        stock_name, stock_qty = get_stock_balance(code)  # 종목명과 보유수량 조회

        #printlog('bought_list:', bought_list, 'len(bought_list):',
        #    len(bought_list), 'target_buy_count:', target_buy_count)     
        if current_price >= target_price \
            and current_price >= ma20_price and current_price >= ma60_price:  
            printlog(stock_name + '(' + str(code) + ') ' + str(buy_qty) +
                'EA : ' + str(current_price) + ' meets the buy condition!`')            
            cpTradeUtil.TradeInit()
            acc = cpTradeUtil.AccountNumber[0]      # 계좌번호
            accFlag = cpTradeUtil.GoodsList(acc, 1) # -1:전체,1:주식,2:선물/옵션                
            # 최유리 FOK 매수 주문 설정
            cpOrder.SetInputValue(0, "2")        # 2: 매수
            cpOrder.SetInputValue(1, acc)        # 계좌번호
            cpOrder.SetInputValue(2, accFlag[0]) # 상품구분 - 주식 상품 중 첫번째
            cpOrder.SetInputValue(3, code)       # 종목코드
            cpOrder.SetInputValue(4, buy_qty)    # 매수할 수량
            cpOrder.SetInputValue(7, "2")        # 주문조건 0:기본, 1:IOC, 2:FOK
            cpOrder.SetInputValue(8, "12")       # 주문호가 1:보통, 3:시장가
                                                 # 5:조건부, 12:최유리, 13:최우선 
            # 매수 주문 요청
            ret = cpOrder.BlockRequest()
            printlog('거래 결과 ->',cpOrder.GetDibStatus(), cpOrder.GetDibMsg1())
            printlog('최유리 FoK 매수 -CpTd0311>', stock_name, code, buy_qty, '->', ret)
            if ret == 4:
                remain_time = cpStatus.LimitRequestRemainTime
                printlog('주의: 연속 주문 제한에 걸림. 대기 시간:', remain_time/1000)
                time.sleep(remain_time/1000) 
                return False
            time.sleep(2)
            printlog('현금주문 가능금액 :', buy_amount)
            stock_name, bought_qty = get_stock_balance(code)
            printlog('get_stock_balance :', stock_name, stock_qty)
            if bought_qty > 0:
                bought_list.append(code)
                dbgout("`buy_etf("+ str(stock_name) + ' : ' + str(code) + 
                    ") -> " + str(bought_qty) + "EA bought!" + "`")
                if sell_end_list_idx > -1:
                    sell_end_list.pop(sell_end_list_idx)
    except Exception as ex:
        dbgout("`buy_etf("+ str(code) + ") -> exception! " + str(ex) + "`")

def sell_all():
    """보유한 모든 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션   
        
        printlog('sell_all while True', '9')
        stocks = get_stock_balance('ALL') 
        total_qty = 0 
        for s in stocks:
            total_qty += s['qty'] 
        if total_qty == 0:
            return True
        for s in stocks:
            if s['qty'] != 0 and 1 <= s['yield_ratio']:                  
                cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                cpOrder.SetInputValue(1, acc)         # 계좌번호
                cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                cpOrder.SetInputValue(3, s['code'])   # 종목코드
                cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선 
                # 최유리 IOC 매도 주문 요청
                ret = cpOrder.BlockRequest()
                    
                sell_price = get_now_price(s['code'])
                printlog('최유리 IOC 매도', s['code'], s['name'], s['qty'], 
                        '-> cpOrder.BlockRequest() -> returned', ret)
                sell_end_list.append({'code': s['code'], 'name': s['name'], 
                'qty': s['qty'], 'sell_price': sell_price})
                if ret == 4:
                    remain_time = cpStatus.LimitRequestRemainTime
                    printlog('주의: 연속 주문 제한, 대기시간:', remain_time/1000)
            time.sleep(1)
            
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))

def sell_condition_chk_10():
    """보유한 모든 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션   
        while True:    
            stocks = get_stock_balance('ALL') 
            total_qty = 0 
            for s in stocks:
                total_qty += s['qty'] 
            if total_qty == 0:
                return True
            for s in stocks:
                if s['qty'] != 0 and 10 <= s['yield_ratio']:                  
                    cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                    cpOrder.SetInputValue(1, acc)         # 계좌번호
                    cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                    cpOrder.SetInputValue(3, s['code'])   # 종목코드
                    cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                    cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                    cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선 
                    # 최유리 IOC 매도 주문 요청
                    ret = cpOrder.BlockRequest()

                    sell_price = get_now_price(s['code'])
                    printlog('최유리 IOC 매도 10 ', s['code'], s['name'], s['qty'], 
                        '-> cpOrder.BlockRequest() -> returned', ret)
                    sell_end_list.append({'code': s['code'], 'name': s['name'], 
                'qty': s['qty'], 'sell_price': sell_price})
                    if ret == 4:
                        remain_time = cpStatus.LimitRequestRemainTime
                        printlog('주의: 연속 주문 제한, 대기시간:', remain_time/1000)
                time.sleep(1)
            time.sleep(30)
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))


def sell_condition_chk_8():
    """보유한 모든 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션   
        while True:    
            stocks = get_stock_balance('ALL') 
            total_qty = 0 
            for s in stocks:
                total_qty += s['qty'] 
            if total_qty == 0:
                return True
            for s in stocks:
                if s['qty'] != 0 and 8 <= s['yield_ratio']:                  
                    cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                    cpOrder.SetInputValue(1, acc)         # 계좌번호
                    cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                    cpOrder.SetInputValue(3, s['code'])   # 종목코드
                    cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                    cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                    cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선 
                    # 최유리 IOC 매도 주문 요청
                    ret = cpOrder.BlockRequest()
                    
                    sell_price = get_now_price(s['code'])
                    printlog('최유리 IOC 매도 8 ', s['code'], s['name'], s['qty'], 
                        '-> cpOrder.BlockRequest() -> returned', ret)
                    sell_end_list.append({'code': s['code'], 'name': s['name'], 
                'qty': s['qty'], 'sell_price': sell_price})
                    if ret == 4:
                        remain_time = cpStatus.LimitRequestRemainTime
                        printlog('주의: 연속 주문 제한, 대기시간:', remain_time/1000)
                time.sleep(1)
            time.sleep(30)
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))


def sell_condition_chk_5():
    """보유한 모든 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션   
        while True:    
            stocks = get_stock_balance('ALL') 
            total_qty = 0 
            for s in stocks:
                total_qty += s['qty'] 
            if total_qty == 0:
                return True
            for s in stocks:
                if s['qty'] != 0 and 5 <= s['yield_ratio']:                  
                    cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                    cpOrder.SetInputValue(1, acc)         # 계좌번호
                    cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                    cpOrder.SetInputValue(3, s['code'])   # 종목코드
                    cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                    cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                    cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선 
                    # 최유리 IOC 매도 주문 요청
                    ret = cpOrder.BlockRequest()
                    
                    sell_price = get_now_price(s['code'])
                    printlog('최유리 IOC 매도 5 ', s['code'], s['name'], s['qty'], 
                        '-> cpOrder.BlockRequest() -> returned', ret)
                    sell_end_list.append({'code': s['code'], 'name': s['name'], 
                'qty': s['qty'], 'sell_price': sell_price})
                    if ret == 4:
                        remain_time = cpStatus.LimitRequestRemainTime
                        printlog('주의: 연속 주문 제한, 대기시간:', remain_time/1000)
                time.sleep(1)
            time.sleep(30)
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))

def sell_condition_chk_3():
    """보유한 모든 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션
        # while True:
        printlog('sell_condition_chk_3 while True', '8')
        stocks = get_stock_balance('ALL') 
        total_qty = 0 
        for s in stocks:
            total_qty += s['qty'] 
        if total_qty == 0:
            return True
        for s in stocks:
            if s['qty'] != 0 and 3 <= s['yield_ratio']:                  
                cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                cpOrder.SetInputValue(1, acc)         # 계좌번호
                cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                cpOrder.SetInputValue(3, s['code'])   # 종목코드
                cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선 
                # 최유리 IOC 매도 주문 요청
                ret = cpOrder.BlockRequest()

                sell_price = get_now_price(s['code'])
                printlog('최유리 IOC 매도 3 ', s['code'], s['name'], s['qty'], 
                        '-> cpOrder.BlockRequest() -> returned', ret)
                sell_end_list.append({'code': s['code'], 'name': s['name'], 
                'qty': s['qty'], 'sell_price': sell_price})
                    
                if ret == 4:
                    remain_time = cpStatus.LimitRequestRemainTime
                    printlog('주의: 연속 주문 제한, 대기시간:', remain_time/1000)
            time.sleep(1)
            # time.sleep(30)
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))



if __name__ == '__main__': 
    try:
        global sell_end_list      # 함수 내에서 값 변경을 하기 위해 global로 지정 [ 이미 구입 후 판매한 종목에 대해서는 판매금액의 -5프로 이상 차이시 다시 구매 가능하도록하기.]
        sell_end_list = []
        
        symbol_list = ['A352820', 'A289080', 'A293490', 'A238090', 'A262260',
             'A034220', 'A139480', 'A330350', 'A326030', 'A010140', 'A047820',
                       'A008770', 'A066570', 'A005930', 'A000660', 'A005380',
                       'A005490', 'A035420', 'A051910', 'A272210', 'A005935', 'A090435', 
                       'A018120', 'A016920', 'A020560', 'A003490', 'A003495', 'A005385',
                       'A272210', 'A065450', 'A042420', 'A036030', 'A234340', 'A096040',
                       'A035600', 'A047310', 'A014130', 'A005880']
        bought_list = []     # 매수 완료된 종목 리스트
        target_buy_count = 5 # 매수할 종목 수
        buy_percent = 0.2   
        printlog('check_creon_system() :', check_creon_system())  # 크레온 접속 점검
        stocks = get_stock_balance('ALL_MSG')      # 보유한 모든 종목 조회
        
        total_cash = int(get_current_cash())   # 100% 증거금 주문 가능 금액 조회
        buy_amount = total_cash * buy_percent  # 종목별 주문 금액 계산
        printlog('100% 증거금 주문 가능 금액 :', total_cash)
        printlog('종목별 주문 비율 :', buy_percent)
        printlog('종목별 주문 금액 :', buy_amount)
        printlog('시작 시간 :', datetime.now().strftime('%m/%d %H:%M:%S'))
        
        soldout = False

        while True:
            printlog('while Truel :', '0')
            t_now = datetime.now()
            t_9 = t_now.replace(hour=9, minute=0, second=0, microsecond=0)
            t_start = t_now.replace(hour=9, minute=0, second=30, microsecond=0)
            t_sell = t_now.replace(hour=15, minute=17, second=0, microsecond=0)
            t_exit = t_now.replace(hour=15, minute=20, second=0, microsecond=0)

            t_90040 = t_now.replace(hour=9, minute=0, second=40, microsecond=0)
            t_935 = t_now.replace(hour=9, minute=35, second=0, microsecond=0)
            t_1040 = t_now.replace(hour=10, minute=40, second=0, microsecond=0)
            t_1045 = t_now.replace(hour=10, minute=45, second=0, microsecond=0)
            t_1150 = t_now.replace(hour=11, minute=50, second=0, microsecond=0)
            t_1155 = t_now.replace(hour=11, minute=55, second=0, microsecond=0)
            t_1327 = t_now.replace(hour=13, minute=27, second=0, microsecond=0)
            t_1335 = t_now.replace(hour=13, minute=35, second=0, microsecond=0)
            t_1455 = t_now.replace(hour=14, minute=55, second=0, microsecond=0)
            
            today = datetime.today().weekday()
            if today == 5 or today == 6:  # 토요일이나 일요일이면 자동 종료
                printlog('Today is', 'Saturday.' if today == 5 else 'Sunday.')
                sys.exit(0)
            if t_9 < t_now < t_start and soldout == False:
                printlog('t_9 < t_now < t_start and soldout == False :', '3')
                soldout = True
                sell_condition_chk_3()
            if t_start < t_now < t_sell :  # AM 09:10 ~ PM 03:15 : 매수
                printlog('t_start < t_now < t_sell :', '4')
                for sym in symbol_list:
                    if len(bought_list) < target_buy_count:
                        printlog('len(bought_list) < target_buy_count', '7')
                        buy_etf(sym)
                        time.sleep(2)
                if t_now.minute == 30 and 0 <= t_now.second <= 5:
                    printlog('t_now.minute == 30 and 0 <= t_now.second <= 5', '5')
                    get_stock_balance('ALL_MSG')
                    time.sleep(8)
                if t_90040 < t_now < t_sell:
                    printlog('t_90040 < t_now < t_sell', '6')
                    sell_condition_chk_3()
                    time.sleep(8)
                # if t_1045 < t_now < t_1150: 
                #    sell_condition_chk_3()
                #    time.sleep(8)
                # if t_1155 < t_now < t_1327: 
                #    sell_condition_chk_3()
                #    time.sleep(8)
                # if t_1335 < t_now < t_1455: 
                #    sell_condition_chk_3()
                #    time.sleep(8)
            if t_sell < t_now < t_exit:  # PM 03:17 ~ PM 03:20 : 일괄 매도
                printlog('t_sell < t_now < t_exit :', '1')
                if sell_all() == True:
                    dbgout('`sell_all() returned True -> self-destructed!`')
                    sys.exit(0)
            if t_exit < t_now:  # PM 03:20 ~ :프로그램 종료
                printlog('t_exit < t_now :', '2')
                dbgout('`self-destructed!`')
                sys.exit(0)
            time.sleep(3)
    except Exception as ex:
        dbgout('`main -> exception! ' + str(ex) + '`')
