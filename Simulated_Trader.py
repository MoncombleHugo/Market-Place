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
        self.price_history = []

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
                        self.price_history.append(last)
                        if len(self.price_history) > 100:  # Keep last 100 prices
                            self.price_history.pop(0)
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
        self.side_counter = 0
        self.best_bid = None
        self.best_ask = None

    def on_md_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('type') == 'order_book_update':
                # Update best bid/ask from market data
                book = data['data']
                if book.get('bids'):
                    self.best_bid = max(float(price) for price in book['bids'].keys())
                if book.get('asks'):
                    self.best_ask = min(float(price) for price in book['asks'].keys())
                
                # Original price tracking
                last = data['data'].get('last_price')
                if last is not None:
                    with self.lock:
                        self.last_price = last
                        self.price_history.append(last)
                        if len(self.price_history) > 100:
                            self.price_history.pop(0)
        except json.JSONDecodeError:
            print("Invalid JSON from market data server.")

    def generate_order(self):
        with self.lock:
            current_last = self.last_price

        # Alternate sides more aggressively
        if self.side_counter > 2:  # More buys recently
            side = "sell"
            self.side_counter -= 3
        elif self.side_counter < -2:  # More sells recently
            side = "buy"
            self.side_counter += 3
        else:
            side = random.choice(["buy", "sell"])

        # Update counter
        self.side_counter += 1 if side == "buy" else -1

        # Aggressive price matching - take the best available price
        if side == "buy" and self.best_ask is not None:
            # Buy at the best ask price (market order)
            order_price = self.best_ask
        elif side == "sell" and self.best_bid is not None:
            # Sell at the best bid price (market order)
            order_price = self.best_bid
        else:
            # If no opposite orders, use limit order logic
            if side == "buy":
                order_price = current_last * (1 + abs(random.gauss(0, self.price_sigma/3)))
            else:
                order_price = current_last * (1 - abs(random.gauss(0, self.price_sigma/3)))

        order_price = max(0.1, round(order_price, 1))
        quantity = random.randint(self.qty_min, self.qty_max)
        
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
            trader.name = f"SimulatedTrader-{i+1}"
            self.traders.append(trader)
        for i in range(trader_counts.get('TrendFollowingTrader', 0)):
            trader = TrendFollowingTrader(
                trend_threshold=0.05,
                buffer_len=20,
                change_coeff=0.1,
                qty=20
            )
            trader.name = f"TrendTrader-{i+1}"
            self.traders.append(trader)

        for i in range(trader_counts.get('MeanReverterTrader', 0)):
            trader = MeanReverterTrader(
                mean_reversion_threshold=0.02,
                buffer_len=20,
                change_coeff=0.1,
                qty=20
            )
            trader.name = f"MeanReverter-{i+1}"
            self.traders.append(trader)
        
        for i in range(trader_counts.get('MarketMakerTrader', 0)):
            trader = MarketMakerTrader(
                spread=0.5,
                qty=10
            )
            trader.name = f"MarketMaker-{i+1}"
            self.traders.append(trader)
        
        for i in range(trader_counts.get('BalancedTrader', 0)):
            trader = BalancedTrader(
                qty=10
            )
            trader.name = f"BalancedTrader-{i+1}"
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

class TrendFollowingTrader(Trader):
    def __init__(self, trend_threshold=0.05, buffer_len=20, change_coeff=0.1, qty=20, **kwargs):
        super().__init__(**kwargs)
        self.trend_threshold = trend_threshold
        self.last_price = 100.0 
        self.buffer_len = buffer_len
        self.change_coeff = change_coeff
        self.qty = qty

    def generate_order(self):
        with self.lock:
            current_last = self.last_price
        
        if len(self.price_history) < self.buffer_len:
            return None
            
        cumulative_return = self.last_price/sum(self.price_history[-self.buffer_len:]) -1 if len(self.price_history) >= self.buffer_len else 1
        
        # More balanced decision making
        if abs(cumulative_return) > self.trend_threshold:
            if cumulative_return > 0:
                side = "sell"  # Sell when price is rising (take profit)
            else:
                side = "buy"   # Buy when price is falling (value buy)
        else:
            return {"side": "None", "price": 0, "quantity": 0}
            
        price_change = cumulative_return * self.change_coeff + random.gauss(0, self.change_coeff * 0.1)
        order_price = max(0.1, round(current_last + price_change, 1))
        quantity = abs(cumulative_return) * random.gauss(self.qty, abs(cumulative_return)*10)
        
        return {"side": side, "price": order_price, "quantity": quantity}
        
class MeanReverterTrader(Trader):
    def __init__(self, mean_reversion_threshold=0.02, buffer_len=20, change_coeff=0.1, qty=20, **kwargs):
        super().__init__(**kwargs)
        self.mean_reversion_threshold = mean_reversion_threshold
        self.buffer_len = buffer_len
        self.change_coeff = change_coeff
        self.qty = qty

    def generate_order(self):
        with self.lock:
            current_last = self.last_price
        if len(self.price_history) < self.buffer_len:
            return None
        mean_price = sum(self.price_history[-self.buffer_len:]) / self.buffer_len
        deviation = (current_last - mean_price) / mean_price
        if abs(deviation) > self.mean_reversion_threshold:
            side = "buy" if deviation < 0 else "sell"
            price_change = -deviation * self.change_coeff + random.gauss(0, self.change_coeff * 0.1)
            order_price = max(0.1, round(current_last + price_change, 1))
            quantity = abs(deviation) * random.gauss(self.qty, abs(deviation) * 10)
            return {"side": side, "price": order_price, "quantity": quantity}
        else:
            return {"side": "None", "price": 0, "quantity": 0}
        
class MarketMakerTrader(Trader):
    def __init__(self, spread=0.5, qty=10, **kwargs):
        super().__init__(**kwargs)
        self.base_spread = spread
        self.qty = qty
        self.spread_adjustment = 0
        self.imbalance = 0
        
    def on_md_message(self, ws, message):
        super().on_md_message(ws, message)
        try:
            data = json.loads(message)
            if data.get('type') == 'order_book_update':
                bids = data['data'].get('bids', {})
                asks = data['data'].get('asks', {})
                bid_vol = sum(float(qty) for orders in bids.values() for qty in orders)
                ask_vol = sum(float(qty) for orders in asks.values() for qty in orders)
                total = bid_vol + ask_vol
                if total > 0:
                    self.imbalance = (bid_vol - ask_vol) / total
        except:
            pass
            
    def generate_order(self):
        with self.lock:
            current_last = self.last_price
        
        # Adjust spread based on imbalance
        spread = self.base_spread * (1 + abs(self.imbalance))
        
        # Adjust quantities based on imbalance
        bid_qty = self.qty * (1 + self.imbalance)
        ask_qty = self.qty * (1 - self.imbalance)
        
        return [
            {
                "side": "buy",
                "price": round(current_last * (1 - spread/2), 1),
                "quantity": max(1, bid_qty)
            },
            {
                "side": "sell",
                "price": round(current_last * (1 + spread/2), 1),
                "quantity": max(1, ask_qty)
            }
        ]
    
class BalancedTrader(Trader):
    def __init__(self, qty=10, **kwargs):
        super().__init__(**kwargs)
        self.qty = qty
        self.imbalance = 0
        
    def on_md_message(self, ws, message):
        super().on_md_message(ws, message)
        try:
            data = json.loads(message)
            if data.get('type') == 'order_book_update':
                bids = data['data'].get('bids', {})
                asks = data['data'].get('asks', {})
                bid_vol = sum(float(qty) for orders in bids.values() for qty in orders)
                ask_vol = sum(float(qty) for orders in asks.values() for qty in orders)
                total = bid_vol + ask_vol
                if total > 0:
                    self.imbalance = (bid_vol - ask_vol) / total
        except:
            pass
            
    def generate_order(self):
        if abs(self.imbalance) < 0.2:  # Market is reasonably balanced
            return {"side": "None", "price": 0, "quantity": 0}
            
        with self.lock:
            current_last = self.last_price
        
        if self.imbalance > 0.2:  # Too many bids - place asks
            return {
                "side": "sell",
                "price": round(current_last * 1.01, 1),
                "quantity": min(50, self.qty * (1 + self.imbalance))
            }
        elif self.imbalance < -0.2:  # Too many asks - place bids
            return {
                "side": "buy",
                "price": round(current_last * 0.99, 1),
                "quantity": min(50, self.qty * (1 - self.imbalance))
            }