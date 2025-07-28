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
        "Combien de SimulatedTraders voulez-vous ?",
        minvalue=0,
        initialvalue=3
    )
    trader_counts['TrendFollowingTrader'] = simpledialog.askinteger(
        "Configuration",
        "Combien de TrendFollowingTraders voulez-vous ?",
        minvalue=0,
        initialvalue=2
    )
    trader_counts['MeanReverterTrader'] = simpledialog.askinteger(
        "Configuration",
        "Combien de MeanReverterTraders voulez-vous ?",
        minvalue=0,
        initialvalue=2
    )
    trader_counts["MarketMakerTrader"] = simpledialog.askinteger(
        "Configuration",
        "Combien de MarketMakerTraders voulez-vous ?",
        minvalue=0,
        initialvalue=2
    )

    trader_counts['BalancedTrader'] = simpledialog.askinteger(
        "Configuration",
        "Combien de BalancedTraders voulez-vous ?",
        minvalue=0,
        initialvalue=2
    )

    # Add a dialog to ask if order book should be reset
    reset_orderbook = simpledialog.askstring(
        "Configuration",
        "Voulez-vous réinitialiser le carnet d'ordres? (oui/non)",
        initialvalue="oui"
    )
    
    root.destroy()
    
    trader_counts['reset_orderbook'] = reset_orderbook.lower() in ('oui', 'yes', 'y', 'o', '1', 'true')
    return trader_counts

async def main(trader_counts):
    # Création du carnet et des serveurs
    order_book = OrderBook()
    
    # Reset order book if requested
    if trader_counts.get('reset_orderbook', False):
        order_book.reset_orderbook()
        print("Carnet d'ordres réinitialisé.")
    
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
    print(f"Lancement avec {trader_counts['SimulatedTrader']} SimulatedTraders et {trader_counts['TrendFollowingTrader']} TrendFollowingTraders.")
    try:
        asyncio.run(main(trader_counts))
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur. Fermeture...")
        time.sleep(1)