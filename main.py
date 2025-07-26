import asyncio
import tkinter as tk
from tkinter import simpledialog
from Order_Book import OrderBook
from Order_Server import OrderServer
from Data_Server import DataServer
from Simulated_Trader import SimulatedTrader, TraderManager, setup_signal_handler
import threading
import time
import signal
import sys

# --- Fenêtre pour demander combien d'acteurs par classe ---
def ask_trader_counts():
    root = tk.Tk()
    root.withdraw()
    trader_counts = {}
    trader_counts['SimulatedTrader'] = simpledialog.askinteger(
        "Configuration",
        "Combien de traders simulés voulez-vous ?",
        minvalue=0,
        initialvalue=3
    )
    root.destroy()
    return trader_counts

async def main(trader_counts):
    # Création du carnet et des serveurs
    order_book = OrderBook()
    order_server = OrderServer(order_book)
    data_server = DataServer(order_book)

    # Création et lancement des traders
    manager = TraderManager(trader_counts)
    setup_signal_handler(manager)  # Pour arrêter proprement
    manager.start_traders()

    # Lancement des serveurs
    await asyncio.gather(
        order_server.start_server(),
        data_server.start_server()
    )

if __name__ == "__main__":
    trader_counts = ask_trader_counts()
    print(f"Lancement avec {trader_counts['SimulatedTrader']} traders simulés")
    try:
        asyncio.run(main(trader_counts))
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur. Fermeture...")
        time.sleep(1)
