import pandas as pd
import mplfinance as mpf
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import sqlite3
import os
from datetime import datetime

class CandleChartAppDB:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualiseur de chandeliers depuis DB de trades")

        self.df_trades = None
        self.df_candles = None
        self.timeframe = "5T"  # Durée des bougies par défaut (5 minutes)

        self.load_btn = tk.Button(root, text="Charger fichier DB SQLite", command=self.load_db)
        self.load_btn.pack(pady=10)

        self.tf_btn = tk.Button(root, text="Modifier durée des bougies", command=self.ask_timeframe)
        self.tf_btn.pack(pady=10)

        self.plot_btn = tk.Button(root, text="Afficher le graphique", command=self.plot_candles)
        self.plot_btn.pack(pady=10)

        self.info_label = tk.Label(root, text="Aucune DB chargée", fg="red")
        self.info_label.pack(pady=10)

    def load_db(self):
        file_path = filedialog.askopenfilename(
            title="Sélectionnez votre fichier DB SQLite",
            filetypes=[("SQLite DB files", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            conn = sqlite3.connect(file_path)
            query = "SELECT id, buyer_id, seller_id, price, quantity, timestamp FROM trades"

            df = pd.read_sql_query(query, conn)
            conn.close()

            # Conversion du timestamp Python (seconds since epoch) en datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

            # Tri chronologique
            df.sort_values('timestamp', inplace=True)

            # Garder uniquement ce qui est utile
            self.df_trades = df[['timestamp', 'price', 'quantity']]

            self.info_label.config(text=f"DB chargée: {os.path.basename(file_path)} ({len(df)} trades)", fg="green")
            print(f"DB chargée, {len(df)} trades")

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger la DB:\n{e}")
            self.df_trades = None

    def ask_timeframe(self):
        tf = simpledialog.askstring("Durée bougies", "Entrez la durée des bougies (ex: 1T, 5T, 15T, 1H, 1D):", initialvalue=self.timeframe)
        if tf:
            self.timeframe = tf.upper()
            self.info_label.config(text=f"Durée bougies mise à jour: {self.timeframe}", fg="blue")

    def prepare_candles(self):
        if self.df_trades is None:
            messagebox.showwarning("Avertissement", "Chargez d'abord une DB de trades.")
            return False

        df = self.df_trades.set_index('timestamp')

        self.df_candles = df['price'].resample(self.timeframe).ohlc()
        self.df_candles['volume'] = df['quantity'].resample(self.timeframe).sum()
        self.df_candles.dropna(subset=['open'], inplace=True)

        return True

    def plot_candles(self):
        if not self.prepare_candles():
            return

        style = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size':10})
        addplots = [mpf.make_addplot(self.df_candles['volume'], type='bar', panel=1, ylabel='Volume')]

        mav = (20, 50) if len(self.df_candles) > 50 else ()

        print(f"Affichage chandeliers, timeframe={self.timeframe}")

        mpf.plot(
            self.df_candles,
            type='candle',
            style=style,
            volume=True,
            addplot=addplots,
            mav=mav,
            title=f"Chandeliers - timeframe {self.timeframe}",
            ylabel='Prix',
            ylabel_lower='Volume',
            figscale=1.2,
            datetime_format='%Y-%m-%d %H:%M',
            tight_layout=True,
            show_nontrading=False
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = CandleChartAppDB(root)
    root.mainloop()
