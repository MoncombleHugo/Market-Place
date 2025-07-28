import time
from dataclasses import dataclass
import sortedcontainers
from collections import deque
import sqlite3
from typing import List, Dict
import asyncio

@dataclass
class Order:
    id:int
    trader_id:int
    price:float
    quantity:int
    side:str
    timestamp:float

class OrderBook:
    def __init__ (self, db_path='trade.db',buffer_size=1000):
        self.asks=sortedcontainers.SortedDict()
        self.bids=sortedcontainers.SortedDict()
        self.db_path = db_path
        self.buffer_size = buffer_size
        self.order_buffer = {}
        self.last_trade_price = None
        self.trades=deque(maxlen=buffer_size)
        self.time_history = deque(maxlen=buffer_size)
        self.volume_history = deque(maxlen=buffer_size)
        self.price_history = deque(maxlen=buffer_size)
        self.lock=asyncio.Lock()
        self.event_queue = asyncio.Queue()
        self.pending_trades=[]
        self.batch_size = 100
        asyncio.create_task(self.flush_periodically())

        self.db_conn= sqlite3.connect(db_path)
        self.db_conn.execute('''CREATE TABLE IF NOT EXISTS trades
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 buyer_id INTEGER,
                                 seller_id INTEGER,
                                 price REAL,
                                 quantity INTEGER,
                                 timestamp REAL)''')
        self.db_conn.commit()
        self.db_conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)')
        self.db_conn.commit()

    def reset_orderbook(self):
        """Reset the order book to empty state"""
        self.bids = sortedcontainers.SortedDict()  # Maintain SortedDict type
        self.asks = sortedcontainers.SortedDict()  # Maintain SortedDict type
        self.order_buffer = {}
        self.last_trade_price = None
        self.trades = deque(maxlen=self.buffer_size)
        self.time_history = deque(maxlen=self.buffer_size)
        self.volume_history = deque(maxlen=self.buffer_size)
        self.price_history = deque(maxlen=self.buffer_size)
        self.pending_trades = []

    def validate_order(self, order: Order) -> bool:
        if order.quantity <= 0 or order.price <= 0:
            return False
        if order.side not in ['buy', 'sell']:
            return False
        if order.id in self.order_buffer:
            return False
        return True
    
    async def flush_db(self):
        async with self.lock:
            if self.pending_trades:
                query = 'INSERT INTO trades (buyer_id, seller_id, price, quantity, timestamp) VALUES (?, ?, ?, ?, ?)'
                args = [(trade['buyer_id'], trade['seller_id'], trade['price'], trade['quantity'], trade['timestamp']) for trade in self.pending_trades]
                self.db_conn.executemany(query, args)
                self.db_conn.commit()
                self.pending_trades.clear()
    
    async def flush_periodically(self):
        while True:
            await self.flush_db()
            await asyncio.sleep(5)

    async def match_order(self, order: Order) -> List[Dict]:
        trades = []
        opposite_book = self.asks if order.side == 'buy' else self.bids
        get_best_price = self.get_best_ask if order.side == 'buy' else self.get_best_bid
        buyer_id = order.trader_id if order.side == 'buy' else None
        seller_id = order.trader_id if order.side == 'sell' else None

        while order.quantity > 0 and opposite_book:
            best_price, opposite_orders = get_best_price()
            if best_price is None:
                break
            if (order.side == 'buy'  and best_price > order.price) or \
               (order.side == 'sell' and best_price < order.price):
                break 

            opposite_order = opposite_orders[0]
            trade_quantity = min(order.quantity, opposite_order.quantity)
            trade = {
                'timestamp': time.time(),
                'buyer_id': buyer_id or opposite_order.trader_id,
                'seller_id': seller_id or opposite_order.trader_id,
                'price': best_price,
                'quantity': trade_quantity
            }
            trades.append(trade)
            self.last_trade_price = best_price
            order.quantity -= trade_quantity
            opposite_order.quantity -= trade_quantity

            if opposite_order.quantity == 0:
                opposite_orders.pop(0)
                if not opposite_orders:
                    del opposite_book[best_price]
                del self.order_buffer[opposite_order.id]
            if order.quantity == 0:
                del self.order_buffer[order.id]
            print(f"Matched order {order.side} trade, price={best_price}, qty={trade_quantity}")

        return trades

    def add_to_book(self, order: Order) -> None:
        book= self.bids if order.side == 'buy' else self.asks
        if order.price not in book:
            book[order.price] = []
        book[order.price].append(order)
    
    async def trades_record(self, trades: List[Dict]) -> None:
        for trade in trades:
            self.trades.append(trade)
            self.time_history.append(trade['timestamp'])
            self.volume_history.append(trade['quantity'])
            self.price_history.append(trade['price'])
            self.pending_trades.append(trade)
        if len(self.pending_trades) >= self.batch_size:
            await self.flush_db()
        
        if trades:
            await self.event_queue.put({'type': 'new_trade', 'trades': trades})
        
    async def add_order(self, order: Order):
        async with self.lock:
            if not self.validate_order(order):
                raise ValueError("Invalid order")
            
            self.order_buffer[order.id] = order
            trades= await self.match_order(order)
            if order.quantity > 0:
                self.add_to_book(order)
            if trades:
                await self.trades_record(trades)
            
            return trades
        
    def order_book_snapshot(self) -> Dict[str, List[Order]]:
        return {
            'bids': {price: [o.__dict__ for o in orders] for price, orders in self.bids.items()},
            'asks': {price: [o.__dict__ for o in orders] for price, orders in self.asks.items()},
            'last_price': self.last_trade_price,
            'recent_trades': list(self.trades)[-10:]
            }
    
    async def cancel_order(self, order_id: int) -> bool:
        async with self.lock:
            if order_id not in self.order_buffer:
                return False
            order=self.order_buffer(order_id)
            book= self.bids if order.side == 'buy' else self.asks
            if order.price in book:
                book[order.price] = [o for o in book[order.price] if o.id != order_id]
                if not book[order.price]:
                    del book[order.price]
            del self.order_buffer[order_id]
            await self.event_queue.put({'type': 'order_cancelled', 'order_id': order_id})
            return True
        
    async def get_history(self, start_time: float, end_time: float) -> List[Order]:
        async with self.lock:
            query = 'SELECT * FROM trades WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC'
            cursor = self.db_conn.execute(query, (start_time, end_time))
            rows = cursor.fetchall()
            return [Order(id=row[0], trader_id=row[1], price=row[3], quantity=row[4], side='buy' if row[1] else 'sell', timestamp=row[5]).__dict__ for row in rows]
    def get_best_bid(self):
        if not self.bids:
            return None, []
        return self.bids.peekitem(-1)
    
    def get_best_ask(self):
        if not self.asks:
            return None, []
        return self.asks.peekitem(0)

    def get_last_price(self):
        return self.last_trade_price
    