import websocket
import json
import time
import threading
import random
import signal
import sys
from abc import ABC, abstractmethod

class Trader(ABC):
    def __init__(self, order_ws_url="ws://127.0.0.1:8765", md_ws_url="ws://127.0.0.1:8766"):
        self.lock = threading.Lock()
        self.last_price = 100.0
        self.stop_event = threading.Event()
        self.send_thread = None

        self.md_ws = websocket.WebSocketApp(
            md_ws_url,
            on_message=self.on_md_message,
            on_error=self.on_ws_error,
            on_close=self.on_ws_close
        )
        self.md_ws.on_open = self.on_md_open

        self.order_ws = websocket.WebSocketApp(
            order_ws_url,
            on_message=self.on_order_message,
            on_error=self.on_ws_error,
            on_close=self.on_ws_close
        )
        self.order_ws.on_open = self.on_order_open

    def on_md_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('type') == 'order_book_update':
                last = data['data'].get('last_price')
                if last is not None:
                    with self.lock:
                        self.last_price = last
        except json.JSONDecodeError:
            print("Invalid JSON from market data server.")

    def on_md_open(self, ws):
        ws.send(json.dumps({"type": "subscribe_order_book"}))
        ws.send(json.dumps({"type": "subscribe_trades"}))

    def on_order_open(self, ws):
        if self.send_thread is None or not self.send_thread.is_alive():
            self.send_thread = threading.Thread(target=self.send_orders, daemon=True)
            self.send_thread.start()

    def on_order_message(self, ws, message):
        try:
            response = json.loads(message)
            print(f"[{self.__class__.__name__}] Order server responded: {response}")
        except json.JSONDecodeError:
            print("Invalid JSON from order server.")

    def on_ws_error(self, ws, error):
        print(f"Websocket error: {error}")

    def on_ws_close(self, ws, close_status_code, close_msg):
        print("Websocket connection closed.")

    @abstractmethod
    def generate_order(self):
        pass

    def send_orders(self):
        while not self.stop_event.is_set():
            order = self.generate_order()
            if not self.order_ws.keep_running:
                break
            try:
                self.order_ws.send(json.dumps(order))
            except websocket.WebSocketConnectionClosedException:
                break
            # Remplacer time.sleep par stop_event.wait pour un arrêt immédiat
            delay = random.expovariate(getattr(self, 'arrival_rate', 1))
            if self.stop_event.wait(delay):
                break

    def run_md_ws(self):
        while not self.stop_event.is_set():
            self.md_ws.run_forever(ping_interval=30, ping_timeout=20)
            if self.stop_event.is_set():
                break
            # plus court délai pour reconnexion
            if self.stop_event.wait(0.1):
                break

    def run_order_ws(self):
        while not self.stop_event.is_set():
            self.order_ws.run_forever(ping_interval=30, ping_timeout=20)
            if self.stop_event.is_set():
                break
            if self.stop_event.wait(0.1):
                break

    def run(self):
        # Threads en daemon : ils ne bloqueront pas la sortie process
        self.md_thread = threading.Thread(target=self.run_md_ws, daemon=True)
        self.order_thread = threading.Thread(target=self.run_order_ws, daemon=True)
        self.md_thread.start()
        self.order_thread.start()

    def stop(self):
        print(f"Stopping {self.__class__.__name__}...")
        self.stop_event.set()
        try:
            self.md_ws.close()
        except Exception:
            pass
        try:
            self.order_ws.close()
        except Exception:
            pass


class SimulatedTrader(Trader):
    def __init__(self, price_sigma=0.5, qty_min=1, qty_max=20, arrival_rate=1.0, **kwargs):
        super().__init__(**kwargs)
        self.price_sigma = price_sigma
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.arrival_rate = arrival_rate

    def generate_order(self):
        with self.lock:
            current_last = self.last_price
        side = random.choice(["buy", "sell"])
        price = random.gauss(0, self.price_sigma)
        order_price = max(0.1, round(current_last + price, 1))
        quantity = random.randint(self.qty_min, self.qty_max)
        # Le délai de génération sera géré dans send_orders via stop_event.wait()
        return {"side": side, "price": order_price, "quantity": quantity}


class TraderManager:
    def __init__(self, trader_counts):
        self.traders = []
        self.threads = []
        for i in range(trader_counts.get('SimulatedTrader', 0)):
            trader = SimulatedTrader(
                price_sigma=0.7,
                qty_min=1,
                qty_max=10,
                arrival_rate=3
            )
            trader.name = f"Trader-{i+1}"
            self.traders.append(trader)

    def start_traders(self):
        for trader in self.traders:
            t = threading.Thread(target=trader.run, daemon=True)
            t.start()
            self.threads.append(t)

    def stop_traders(self):
        for trader in self.traders:
            trader.stop()


def setup_signal_handler(manager):
    def signal_handler(sig, frame):
        print("\nCTRL+C détecté ! Arrêt immédiat des traders...")
        manager.stop_traders()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
