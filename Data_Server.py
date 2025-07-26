import asyncio
import websockets
import json
from typing import List, Dict

class DataServer:
    def __init__(self, order_book, host='localhost', port=8766):
        self.order_book = order_book
        self.host = host
        self.port = port
        self.clients=set()
        self.subscribers={}
        self.order_book_interval=0.5

    async def listen_event(self):
        while True:
            event=await self.order_book.event_queue.get()
            if event['type'] == 'new_trade':
                message = json.dumps(event)
                for client, subs in list(self.subscribers.items()):
                    if subs.get('trades', False):
                        try:
                            await client.send(message)
                        except Exception:
                            self.clients.discard(client)
                            self.subscribers.pop(client, None)
    async def handle_client(self, websocket):
        self.clients.add(websocket)
        self.subscribers[websocket] = {'trades': False, 'order_book': False}
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    type= data.get('type')
                    if type=='request_history':
                        from_time = data.get('from_time')
                        to_time = data.get('to_time')
                        history = await self.order_book.get_history(from_time, to_time)
                        await websocket.send(json.dumps({'type':'history','trades':history}))
                    elif type=='request_history_ohlc':
                        from_time = data.get('from_time')
                        to_time = data.get('to_time')
                        candle_interval = data.get('candle_interval', 60.0)
                        ohlc=await self.get_history_ohlc(from_time, to_time, candle_interval)
                        await websocket.send(json.dumps({'type':'history_ohlc','data':ohlc}))
                    elif type=='suscribe_trades':
                        self.subscribers[websocket]['trades'] = True
                        await websocket.send(json.dumps({'type': 'subscription', 'status': 'trades'}))
                    elif type=='suscribe_order_book':
                        self.subscribers[websocket]['order_book'] = True
                        await websocket.send(json.dumps({'type': 'subscription', 'status': 'order_book'}))
                    elif type=='unsubscribe_trades':
                        self.subscribers[websocket]['trades'] = False
                        await websocket.send(json.dumps({'type': 'unsubscription', 'status': 'trades'}))
                    elif type=='unsubscribe_order_book':
                        self.subscribers[websocket]['order_book'] = False
                        await websocket.send(json.dumps({'type': 'unsubscription', 'status': 'order_book'}))
                except json.JSONDecodeError:
                    pass
        finally:
            self.clients.discard(websocket)
            self.subscribers.pop(websocket, None)

    async def get_history_ohlc(self, start_time: float=None, end_time: float=None, interval: float=60.0) -> List[Dict]:
        async with self.order_book.lock:
            if interval <= 0:
                raise ValueError("Interval must be greater than 0")
            params = {'interval': interval}
            query = '''
                WITH buckets AS (
                    SELECT
                        floor(timestamp / :interval) * :interval AS bucket_start,
                        timestamp,
                        price,
                        quantity,
                        ROW_NUMBER() OVER (PARTITION BY floor(timestamp / :interval) ORDER BY timestamp ASC) AS rn_asc,
                        ROW_NUMBER() OVER (PARTITION BY floor(timestamp / :interval) ORDER BY timestamp DESC) AS rn_desc
                    FROM trades
            '''
            if start_time is not None:
                query += ' WHERE timestamp >= :start_time'
                params['start_time'] = start_time
                if end_time is not None:
                    query += ' AND timestamp <= :end_time'
                    params['end_time'] = end_time
            elif end_time is not None:
                query += ' WHERE timestamp <= :end_time'
                params['end_time'] = end_time
            query += '''
                )
                SELECT
                    bucket_start,
                    MAX(CASE WHEN rn_asc = 1 THEN price END) AS open,
                    MAX(price) AS high,
                    MIN(price) AS low,
                    MAX(CASE WHEN rn_desc = 1 THEN price END) AS close,
                    SUM(quantity) AS volume
                FROM buckets
                GROUP BY bucket_start
                HAVING open IS NOT NULL  -- Skip empty buckets
                ORDER BY bucket_start ASC
            '''
            cursor = self.order_book.db_conn.execute(query, params)
            return [{'time': row[0], 'open': row[1], 'high': row[2], 'low': row[3], 'close': row[4], 'volume': row[5]}for row in cursor.fetchall()]
        
    async def broadcast_order_book(self):
        while True:
            state=self.order_book.order_book_snapshot()
            message=json.dumps({'type': 'order_book_update', 'data': state})
            for client, subs in list(self.subscribers.items()):
                if subs.get('order_book', False):
                    try:
                        await client.send(message)
                    except Exception:
                        self.clients.discard(client)
                        self.subscribers.pop(client, None)
            await asyncio.sleep(self.order_book_interval)
    
    async def start_server(self):
        server=await websockets.serve(self.handle_client, self.host, self.port)
        asyncio.create_task(self.listen_event())
        asyncio.create_task(self.broadcast_order_book())
        print(f"Data server started on ws://{self.host}:{self.port}")
        await server.wait_closed()
