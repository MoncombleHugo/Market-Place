# Market-Place Project Documentation

## Overview

This project is a comprehensive **electronic trading marketplace simulation** that mimics the behavior of a real financial exchange. It includes an order book, multiple types of automated traders, real-time data streaming, and visualization tools.

## Architecture

### Core Components

#### 1. Order Book (`Order_Book.py`)
The heart of the trading system that manages all orders and trades.

**Key Features:**
- **Order Management**: Stores buy/sell orders in sorted dictionaries for efficient price-time priority matching
- **Order Matching Engine**: Automatically matches compatible buy/sell orders using price-time priority
- **Trade Execution**: Executes trades when orders match and records all transaction details
- **Data Persistence**: Stores all trades in SQLite database (`trade.db`) with timestamps
- **Real-time Events**: Publishes trade events to subscribers via async queues
- **Historical Data**: Provides OHLCV (Open, High, Low, Close, Volume) aggregation for charting

**Order Matching Logic:**
- Buy orders are matched with the lowest-priced sell orders
- Sell orders are matched with the highest-priced buy orders
- Orders are filled partially if quantities don't match exactly
- Remaining unfilled quantities stay in the order book

#### 2. WebSocket Servers

##### Order Server (`Order_Server.py`)
Handles incoming trading orders from clients.

**Functionality:**
- Accepts WebSocket connections from traders/clients
- Assigns unique IDs to each connected client
- Receives JSON-formatted orders and forwards them to the order book
- Returns trade confirmations and execution details
- Supports both single orders and batch order submissions

##### Data Server (`Data_Server.py`)
Provides real-time market data and historical information.

**Services:**
- **Real-time Trade Feed**: Broadcasts new trades to subscribed clients
- **Order Book Updates**: Sends live order book snapshots
- **Historical Data**: Provides trade history for specific time ranges
- **OHLCV Data**: Aggregates historical trades into candlestick data
- **Client Subscriptions**: Manages client subscriptions to different data feeds

### Trading Agents

#### 1. Base Trader Class (`Simulated_Trader.py`)
Abstract base class that defines the common interface for all traders.

**Common Features:**
- WebSocket connections to both order and data servers
- Market data subscription and processing
- Order generation and submission
- Connection management and error handling
- Clean shutdown procedures

#### 2. Trader Types

##### SimulatedTrader
**Strategy**: Random trading with Gaussian price noise
- Generates random buy/sell orders around the current market price
- Uses configurable price volatility (sigma parameter)
- Alternates between buy and sell orders to maintain balance
- Adjusts prices based on current bid/ask spread when available

##### TrendFollowingTrader
**Strategy**: Follows price momentum
- Maintains a history of recent prices
- Calculates cumulative returns over a rolling window
- Buys when detecting upward trends, sells on downward trends
- Adjusts order quantities based on trend strength

##### MeanReverterTrader
**Strategy**: Trades against price movements expecting reversion
- Calculates moving average of recent prices
- Sells when price is significantly above average
- Buys when price is significantly below average
- Based on the assumption that prices revert to historical means

##### MarketMakerTrader
**Strategy**: Provides liquidity by placing both buy and sell orders
- Simultaneously places buy orders below market and sell orders above
- Adjusts spreads based on market conditions and order book imbalance
- Aims to profit from the bid-ask spread while providing liquidity

### User Interfaces

#### 1. Manual Trading Client (`Client.py`)
Console-based interface for manual order entry.
- Interactive command-line interface
- Allows users to place individual buy/sell orders
- Real-time feedback on order execution
- Graceful shutdown with Ctrl+C

#### 2. Web-based Dashboard (`index.html` + `script.js`)
Real-time web interface for market visualization.

**Features:**
- **Price Charts**: Interactive candlestick charts
- **Order Book Visualization**: Live display of current bids and asks
- **Trade Feed**: Real-time list of recent trades
- **Time Range Selection**: Configurable chart time windows
- **Candle Intervals**: Multiple timeframes (10s, 30s, 1m, 30m, 1h)
- **Auto-refresh**: Continuous updates of live data

## Data Flow

### 1. Order Lifecycle
```
Trader → Order Server → Order Book → Trade Execution → Database Storage
                                   ↓
                              Data Server → WebSocket Clients
```

### 2. Market Data Flow
```
Order Book (Trades) → Event Queue → Data Server → Subscribed Clients
                                                     ↓
                                              Web Interface, Traders
```

### 3. Historical Data
```
SQLite Database → Data Server → OHLCV Aggregation → Chart Visualization
```

## Configuration and Startup

### Main Application (`main.py`)
The entry point that orchestrates the entire system.

**Startup Process:**
1. **Configuration Dialog**: GUI prompts for trader quantities and settings
2. **Order Book Initialization**: Creates or resets the order book with initial liquidity
3. **Server Startup**: Launches WebSocket servers for orders and data
4. **Trader Deployment**: Starts configured numbers of each trader type
5. **Signal Handling**: Sets up graceful shutdown on Ctrl+C

**Configuration Options:**
- Number of each trader type (0-N for each)
- Order book reset option (starts with fresh liquidity)
- All settings are configurable via dialog boxes

### Running the System

1. **Start the main application:**
   ```bash
   python main.py
   ```

2. **Configure trader populations** through the GUI dialogs

3. **Access the web interface:**
   ```bash
   python -m http.server 8000
   # Then visit http://localhost:8000/
   ```

4. **Optional manual trading:**
   ```bash
   python Client.py
   ```

## Technical Implementation Details

### Database Schema
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id TEXT,
    seller_id TEXT,
    price REAL,
    quantity INTEGER,
    timestamp REAL
);
```

### WebSocket Message Formats

#### Order Submission
```json
{
    "side": "buy|sell",
    "price": 100.50,
    "quantity": 10
}
```

#### Trade Notification
```json
{
    "type": "new_trade",
    "trades": [{
        "timestamp": 1693526400.123,
        "buyer_id": "uuid-1",
        "seller_id": "uuid-2", 
        "price": 100.50,
        "quantity": 5
    }]
}
```

#### OHLCV Request
```json
{
    "type": "request_history_ohlc",
    "from_time": 1693526400,
    "to_time": 1693530000,
    "candle_interval": 60
}
```

### Performance Features
- **Asynchronous Processing**: All I/O operations use asyncio for high concurrency
- **Batch Database Writes**: Trades are buffered and written in batches
- **Efficient Order Matching**: SortedDict data structures for O(log n) order book operations
- **Event-driven Architecture**: Real-time updates via async event queues

## Use Cases

### 1. Trading Strategy Research
- Test different algorithmic trading strategies
- Analyze market microstructure effects
- Study trader interaction dynamics

### 2. Market Simulation
- Model different market conditions
- Test system behavior under various trader compositions
- Simulate market stress scenarios

### 3. Educational Tool
- Demonstrate order book mechanics
- Visualize market dynamics in real-time
- Understand price formation processes

### 4. Development Platform
- Test new trading algorithms in a controlled environment
- Prototype market-making strategies
- Validate order management systems

## Extension Points

The system is designed for easy extension:

1. **New Trader Types**: Inherit from the Trader base class and implement `generate_order()`
2. **Additional Data Feeds**: Extend the Data Server with new message types
3. **Enhanced Visualizations**: Add new chart types to the web interface
4. **Risk Management**: Add position tracking and risk controls
5. **Market Data Providers**: Integrate external data sources
6. **Order Types**: Implement stop-losses, iceberg orders, etc.

## Dependencies

### Python Packages
- `asyncio`: Asynchronous programming
- `websockets`: WebSocket server/client implementation
- `sqlite3`: Database operations
- `sortedcontainers`: Efficient sorted data structures
- `tkinter`: GUI dialogs
- `pandas`: Data manipulation (for plotting tools)
- `matplotlib`: Chart generation
- `mplfinance`: Financial chart plotting

### Web Technologies
- `plotly.js`: Interactive web charts
- WebSocket API for real-time communication
- HTML5/CSS3 for user interface
---

This documentation provides a comprehensive overview of the Market-Place project. For specific implementation details, refer to the individual source files and their inline comments.
