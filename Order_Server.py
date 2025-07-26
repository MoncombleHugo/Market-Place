import asyncio
import websockets
import json
import time
import uuid

from Order_Book import Order, OrderBook

class OrderServer:
    def __init__(self,order_book, host='localhost', port=8765):
        self.order_book = order_book
        self.host = host
        self.port = port
        self.clients_ids = {}
        self.websocket_traders = {}

    async def handle_order(self, websocket):
        print(f"New connnection from {websocket.remote_address}")
        print(self.clients_ids)
        if websocket not in self.clients_ids:
            client_id = str(uuid.uuid4())
            self.clients_ids[websocket] = client_id
            self.websocket_traders[client_id] = websocket
            print(f"Assigned client ID: {client_id}")
        try:
            async for message in websocket:
                order_dict = json.loads(message)
                order = Order(
                    id=str(uuid.uuid4()),
                    trader_id=client_id,
                    side=order_dict["side"],
                    price=float(order_dict["price"]),
                    quantity=int(order_dict["quantity"]),
                    timestamp=time.time()
                )
                trades = await self.order_book.add_order(order)
                await websocket.send(json.dumps(trades))

                for trade in trades:
                    buyer_ws=self.websocket_traders.get(trade['buyer_id'])
                    seller_ws=self.websocket_traders.get(trade['seller_id'])
                    if buyer_ws and buyer_ws != websocket:
                        await buyer_ws.send(json.dumps([trade]))
                    if seller_ws and seller_ws != websocket:
                        await seller_ws.send(json.dumps([trade]))
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed for {client_id}")
        finally:
            if websocket in self.clients_ids:
                del self.clients_ids[websocket]
            if client_id in self.websocket_traders:
                del self.websocket_traders[client_id]

    async def start_server(self):
        async with websockets.serve(self.handle_order, self.host, self.port):
            print(f"Server started on ws://{self.host}:{self.port}")
            await asyncio.Future()
        