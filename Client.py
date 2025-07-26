import websocket
import json
import threading
import signal
import sys

def on_message(ws, message):
    try:
        response = json.loads(message)
        print(f"Server responded: {response}")
    except json.JSONDecodeError:
        print("Received invalid JSON response")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"Connection closed: {close_status_code}, {close_msg}")

def on_open(ws):
    print("Connection opened")

def on_open(ws):
    print("Connection opened")

    def interactive_input():
        print("Enter order details (e.g., 'b' for buy, 's' for sell, 'q' to quit):")
        while ws.keep_running:
            try:
                side_input = input("Side (buy/sell) or 'quit' to quit: ").strip().lower()
                if side_input == 'quit':
                    ws.close()
                    break
                if side_input not in ('buy', 'sell'):
                    print("Invalid side. Please enter 'buy' or 'sell'.")
                    continue

                side = 'buy' if side_input == 'b' else 'sell'

                try:
                    price = float(input("Limit price: ").strip())
                    if price <= 0:
                        print("Price must be positive.")
                        continue
                except ValueError:
                    print("Invalid price. Please enter a valid number.")
                    continue

                try:
                    quantity = int(input("Quantity: ").strip())
                    if quantity <= 0:
                        print("Quantity must be positive.")
                        continue
                except ValueError:
                    print("Invalid quantity. Please enter a valid integer.")
                    continue

                order = {
                    "side": side,
                    "price": price,
                    "quantity": quantity
                }
                ws.send(json.dumps(order))
                print(f"Sent order: {order}")

            except EOFError:
                print("\nEOF received. Closing connection...")
                ws.close()
                break
            except Exception as e:
                print(f"Error in console input: {e}")
    
    threading.Thread(target=interactive_input, daemon=True).start()

def signal_handler(sig, frame):
    print("\nCtrl+C received. Closing WebSocket connection...")
    ws.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ws = websocket.WebSocketApp(
    "ws://localhost:8765",
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)
ws.on_open = on_open
ws.run_forever()
