import asyncio
from Order_Book import OrderBook
from Order_Server import OrderServer
from Data_Server import DataServer

async def main():
    order_book = OrderBook()
    order_server = OrderServer(order_book)
    data_server = DataServer(order_book)
    await asyncio.gather(order_server.start_server(), data_server.start_server())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")