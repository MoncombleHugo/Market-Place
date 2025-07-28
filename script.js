// Helper function to format date for datetime-local
function formatDateTimeLocal(date) {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function convertDateToTimestamp(dateString) {
  const date = new Date(dateString);
  return Math.floor(date.getTime() / 1000); // Convert to seconds
}

// Initialize WebSocket connection
const ws = new WebSocket("ws://127.0.0.1:8766");

// Data storage for OHLCV
let ohlcData = {
  time: [],
  open: [],
  high: [],
  low: [],
  close: [],
  volume: []
};

// For zoom functionality
let currentTimeRange = null;
let isUserZoomed = false;
let autoUpdateInterval = null;
const AUTO_UPDATE_INTERVAL = 1000; // Update every 1 second

// For order book
let subscribedOrderBook = false;
let orderBookPlotInitialized = false;
const toggleButton = document.getElementById("toggle-orderbook");
let showOrderBook = false;


toggleButton.addEventListener("click", () => {
  showOrderBook = !showOrderBook;
  if (showOrderBook) {
    if (!subscribedOrderBook) {
      ws.send(JSON.stringify({ type: "suscribe_order_book" }));
      subscribedOrderBook = true;
    }
    document.getElementById("orderbook-plot").style.display = "block";
    toggleButton.textContent = "Hide Order Book";
  } else {
    if (subscribedOrderBook) {
      ws.send(JSON.stringify({ type: "unsubscribe_order_book" }));
      subscribedOrderBook = false;
    }
    document.getElementById("orderbook-plot").style.display = "none";
    toggleButton.textContent = "Show Order Book";
  }
});

// Date range elements
const startDateInput = document.getElementById("start-date");
const endDateInput = document.getElementById("end-date");
const candleIntervalSelect = document.getElementById("candle-interval");
const applyButton = document.getElementById("apply-range");

// Load persistent range from localStorage
const savedStart = localStorage.getItem("startDate");
const savedEnd = localStorage.getItem("endDate");
const savedCandleInterval = localStorage.getItem("candleInterval");

if (savedStart) startDateInput.value = savedStart;
if (savedEnd) endDateInput.value = savedEnd;
if (savedCandleInterval) candleIntervalSelect.value = savedCandleInterval;

// Set default start if not saved
if (!startDateInput.value) {
  const now = new Date();
  const marketOpen = new Date(now.getTime() - 3600000); // 1 hour ago
  startDateInput.value = formatDateTimeLocal(marketOpen);
}

// Function to request OHLCV data
function requestOHLCV(fromTime, toTime, candleInterval) {
  ws.send(
    JSON.stringify({
      type: "request_history_ohlc",
      from_time: fromTime,
      to_time: toTime,
      candle_interval: candleInterval,
    })
  );
}

// Add these at the top with your other variables
let plotInitialized = false;
let currentTraces = null;

// Replace your updateOHLCVPlot function with this version
function updateOHLCVPlot(data, fromTime, toTime) {
  if (!Array.isArray(data)) {
    console.error("Invalid historical OHLC data received:", data);
    return;
  }

  // Store the current time range
  currentTimeRange = {
    from: fromTime * 1000,
    to: toTime * 1000
  };

  // Process data into candles
  const processedData = processDataToCandles(data, fromTime, toTime);

  if (!plotInitialized) {
    // First time - create the plot
    createNewPlot(processedData, fromTime, toTime);
    plotInitialized = true;
  } else {
    // Subsequent updates - extend traces
    updateExistingPlot(processedData);
  }
}

function processDataToCandles(data, fromTime, toTime) {
  const times = [];
  const opens = [];
  const highs = [];
  const lows = [];
  const closes = [];

  const fromTimeMs = fromTime * 1000;
  const toTimeMs = toTime * 1000;
  const candleInterval = parseInt(candleIntervalSelect.value) * 1000;
  let currentBucket = Math.floor(fromTimeMs / candleInterval) * candleInterval;

  while (currentBucket <= toTimeMs) {
    const candleData = data.find(d => {
      const candleTime = d.time * 1000;
      return candleTime >= currentBucket && candleTime < currentBucket + candleInterval;
    });

    if (candleData) {
      times.push(new Date(currentBucket));
      opens.push(candleData.open);
      highs.push(candleData.high);
      lows.push(candleData.low);
      closes.push(candleData.close);
    } else {
      times.push(new Date(currentBucket));
      opens.push(null);
      highs.push(null);
      lows.push(null);
      closes.push(null);
    }

    currentBucket += candleInterval;
  }

  return { times, opens, highs, lows, closes };
}

// Replace the createNewPlot function with this version:
function createNewPlot(data, fromTime, toTime) {
  const trace = {
    type: 'candlestick',
    x: data.times,
    open: data.opens,
    high: data.highs,
    low: data.lows,
    close: data.closes,
    increasing: { line: { color: 'green' }, fillcolor: 'green' },
    decreasing: { line: { color: 'red' }, fillcolor: 'red' },
    showlegend: false
  };

  currentTraces = [trace];

  // Calculate the actual min and max from the data
  const { minPrice, maxPrice } = getPriceRange(data.highs, data.lows);
  const padding = (maxPrice - minPrice) * 0.1; // 10% padding

  const layout = {
  title: 'Price Chart',
  xaxis: { 
    title: 'Time',
    range: [new Date(fromTime * 1000), new Date(toTime * 1000)],
    type: 'date',
    rangeslider: {
      visible: true,
      range: [new Date(fromTime * 1000), new Date(toTime * 1000)]
    }
  },
  yaxis: { 
    title: 'Price',
    range: [minPrice - padding, maxPrice + padding],
    autorange: false,
    fixedrange: false
  },
  margin: { t: 40, b: 40, l: 80, r: 40 },
  plot_bgcolor: '#f8f8f8',
  paper_bgcolor: '#f8f8f8',
  height: null // Let it take the full container height
};

  Plotly.newPlot('plot', currentTraces, layout).then(() => {
    setupZoomHandler();
  });
}

// Add this helper function to calculate price range:
function getPriceRange(highs, lows) {
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  
  // Filter out null values and find actual min/max
  const validHighs = highs.filter(h => h !== null);
  const validLows = lows.filter(l => l !== null);
  
  if (validLows.length > 0) minPrice = Math.min(...validLows);
  if (validHighs.length > 0) maxPrice = Math.max(...validHighs);
  
  // Fallback values if no valid data
  if (minPrice === Infinity) minPrice = 0;
  if (maxPrice === -Infinity) maxPrice = minPrice + 1;
  
  return { minPrice, maxPrice };
}

// Update the updateExistingPlot function:
function updateExistingPlot(newData) {
  // Get current zoom state before updating
  const plotDiv = document.getElementById('plot');
  const currentZoom = plotDiv.layout || {};
  
  // Update the trace data
  currentTraces[0].x = newData.times;
  currentTraces[0].open = newData.opens;
  currentTraces[0].high = newData.highs;
  currentTraces[0].low = newData.lows;
  currentTraces[0].close = newData.closes;

  // Calculate new y-axis range based on actual data
  const { minPrice, maxPrice } = getPriceRange(newData.highs, newData.lows);
  const padding = (maxPrice - minPrice) * 0.1;

  // Prepare layout update
  const layoutUpdate = {
    xaxis: {
      rangeslider: {
        range: [new Date(currentTimeRange.from), new Date(currentTimeRange.to)]
      }
    }
  };

  // Only update y-axis if user hasn't manually zoomed
  if (!isUserZoomed || !currentZoom.yaxis || !currentZoom.yaxis.range) {
    layoutUpdate.yaxis = {
      range: [minPrice - padding, maxPrice + padding],
      autorange: false
    };
  }

  if (isUserZoomed && currentZoom.xaxis) {
    layoutUpdate.xaxis.range = currentZoom.xaxis.range;
    layoutUpdate.xaxis.autorange = false;
  }

  Plotly.react('plot', currentTraces, layoutUpdate);
}

// Update the handleNewTrade function:
function handleNewTrade(trade) {
  const candleInterval = parseInt(candleIntervalSelect.value) * 1000;
  const currentBucket = Math.floor(trade.timestamp / candleInterval) * candleInterval;
  const bucketTime = new Date(currentBucket);
  
  // Get current zoom state
  const plotDiv = document.getElementById('plot');
  const currentZoom = plotDiv.layout || {};
  
  // Find existing candle index
  const existingIndex = currentTraces[0].x.findIndex(t => 
    t.getTime() === bucketTime.getTime()
  );

  if (existingIndex >= 0) {
    // Update existing candle
    const update = {
      'high[0]': currentTraces[0].high.map((val, i) => 
        i === existingIndex ? Math.max(val || -Infinity, trade.price) : val
      ),
      'low[0]': currentTraces[0].low.map((val, i) => 
        i === existingIndex ? Math.min(val || Infinity, trade.price) : val
      ),
      'close[0]': currentTraces[0].close.map((val, i) => 
        i === existingIndex ? trade.price : val
      )
    };
    
    // Update the trace data
    currentTraces[0].high[existingIndex] = update['high[0]'][existingIndex];
    currentTraces[0].low[existingIndex] = update['low[0]'][existingIndex];
    currentTraces[0].close[existingIndex] = update['close[0]'][existingIndex];
    
    // Only adjust y-axis if user hasn't manually zoomed
    if (!isUserZoomed || !currentZoom.yaxis || !currentZoom.yaxis.range) {
      const { minPrice, maxPrice } = getPriceRange(currentTraces[0].high, currentTraces[0].low);
      const padding = (maxPrice - minPrice) * 0.1;
      
      update.yaxis = {
        range: [minPrice - padding, maxPrice + padding]
      };
    }
    
    Plotly.restyle('plot', update, [0]);
  } else {
    // Add new candle (only if within current range)
    const bucketTimestamp = bucketTime.getTime();
    if (bucketTimestamp >= currentTimeRange.from && bucketTimestamp <= currentTimeRange.to) {
      // Create new arrays with the added candle
      const newX = [...currentTraces[0].x, bucketTime];
      const newOpen = [...currentTraces[0].open, trade.price];
      const newHigh = [...currentTraces[0].high, trade.price];
      const newLow = [...currentTraces[0].low, trade.price];
      const newClose = [...currentTraces[0].close, trade.price];
      
      // Sort by time
      const sortedIndices = newX
        .map((_, i) => i)
        .sort((a, b) => newX[a] - newX[b]);
      
      // Update trace data
      currentTraces[0].x = sortedIndices.map(i => newX[i]);
      currentTraces[0].open = sortedIndices.map(i => newOpen[i]);
      currentTraces[0].high = sortedIndices.map(i => newHigh[i]);
      currentTraces[0].low = sortedIndices.map(i => newLow[i]);
      currentTraces[0].close = sortedIndices.map(i => newClose[i]);
      
      // Prepare layout update
      const layoutUpdate = {};
      
      // Only adjust y-axis if user hasn't manually zoomed
      if (!isUserZoomed || !currentZoom.yaxis || !currentZoom.yaxis.range) {
        const { minPrice, maxPrice } = getPriceRange(currentTraces[0].high, currentTraces[0].low);
        const padding = (maxPrice - minPrice) * 0.1;
        
        layoutUpdate.yaxis = {
          range: [minPrice - padding, maxPrice + padding]
        };
      }
      
      if (isUserZoomed && currentZoom.xaxis) {
        layoutUpdate.xaxis = {
          range: currentZoom.xaxis.range,
          autorange: false
        };
      }
      
      Plotly.react('plot', currentTraces, layoutUpdate);
    }
  }
}

// Order book update function remains the same
function updateOrderBook(messageData) {
  const state = messageData.data;

  if (!state || !state.bids || !state.asks) {
    console.error("Invalid order book data:", messageData);
    return;
  }

  // Aggregate bids
  const bidLevels = Object.entries(state.bids).map(([priceStr, orders]) => {
    const price = parseFloat(priceStr);
    const totalQty = orders.reduce((sum, order) => sum + parseFloat(order.quantity), 0);
    return { price, quantity: totalQty };
  }).sort((a, b) => b.price - a.price).slice(0, 10);

  // Aggregate asks
  const askLevels = Object.entries(state.asks).map(([priceStr, orders]) => {
    const price = parseFloat(priceStr);
    const totalQty = orders.reduce((sum, order) => sum + parseFloat(order.quantity), 0);
    return { price, quantity: totalQty };
  }).sort((a, b) => a.price - b.price).slice(0, 10);

  const bid_prices = bidLevels.map(b => b.price);
  const bid_quantities = bidLevels.map(b => -b.quantity);
  const ask_prices = askLevels.map(a => a.price);
  const ask_quantities = askLevels.map(a => a.quantity);

  const maxQty = Math.max(
    ...bidLevels.map(b => b.quantity),
    ...askLevels.map(a => a.quantity)
  ) || 0;

  const trace1 = {
    y: bid_prices,
    x: bid_quantities,
    type: "bar",
    orientation: "h",
    marker: { color: "green" },
    name: "Bids",
    width: 0.1,
  };

  const trace2 = {
    y: ask_prices,
    x: ask_quantities,
    type: "bar",
    orientation: "h",
    marker: { color: "red" },
    name: "Asks",
    width: 0.1,
  };

  const layout = {
    title: "Market Depth",
    yaxis: { title: "Price" },
    xaxis: {
      title: "Quantity",
      range: [-maxQty * 1.1, maxQty * 1.1],
    },
    showlegend: true,
    barmode: "overlay",
  };

  if (!orderBookPlotInitialized) {
    Plotly.newPlot("orderbook-plot", [trace1, trace2], layout);
    orderBookPlotInitialized = true;
  } else {
    Plotly.react("orderbook-plot", [trace1, trace2], layout);
  }
}

// WebSocket event handlers
ws.onopen = function() {
  console.log("WebSocket connected");
  
  const startValue = startDateInput.value;
  const endValue = endDateInput.value;
  const candleIntervalValue = parseInt(candleIntervalSelect.value);

  const fromTime = convertDateToTimestamp(startValue);
  const toTime = endValue ? convertDateToTimestamp(endValue) : Math.floor(Date.now() / 1000);
  
  // Initial data load
  requestOHLCV(fromTime, toTime, candleIntervalValue);
  ws.send(JSON.stringify({ type: "suscribe_trades" }));
  
  // Start auto-update
  startAutoUpdate(fromTime, toTime, candleIntervalValue);
};

ws.onmessage = function(event) {
  let data;
  try {
    data = JSON.parse(event.data);
  } catch (e) {
    console.error("Invalid JSON received:", event.data);
    return;
  }

  switch(data.type) {
    case "history_ohlc":
      const fromTime = startDateInput.value ? convertDateToTimestamp(startDateInput.value) : 0;
      const toTime = endDateInput.value ? convertDateToTimestamp(endDateInput.value) : Math.floor(Date.now() / 1000);
      updateOHLCVPlot(data.data, fromTime, toTime);
      break;
    case "new_trade":
      data.trades.forEach(trade => handleNewTrade(trade));
      break;
    case "order_book_update":
      updateOrderBook(data);
      break;
    default:
      console.warn("Unknown message type:", data.type);
  }
};

ws.onclose = function() {
  console.log("WebSocket disconnected");
  stopAutoUpdate();
};

ws.onerror = function(error) {
  console.error("WebSocket error:", error);
};

// Event listeners
applyButton.addEventListener("click", () => {
  const startValue = startDateInput.value;
  const endValue = endDateInput.value;
  const candleIntervalValue = parseInt(candleIntervalSelect.value);

  // Save to localStorage
  localStorage.setItem("startDate", startValue || "");
  localStorage.setItem("endDate", endValue || "");
  localStorage.setItem("candleInterval", candleIntervalValue || "");

  const fromTime = convertDateToTimestamp(startValue);
  const toTime = endValue ? convertDateToTimestamp(endValue) : Math.floor(Date.now() / 1000);

  // Restart auto-update with new range
  stopAutoUpdate();
  requestOHLCV(fromTime, toTime, candleIntervalValue);
  startAutoUpdate(fromTime, toTime, candleIntervalValue);
});

function startAutoUpdate(fromTime, toTime, candleInterval) {
  // Clear any existing interval
  if (autoUpdateInterval) {
    clearInterval(autoUpdateInterval);
  }
  
  // Set up new interval
  autoUpdateInterval = setInterval(() => {
    requestOHLCV(fromTime, toTime, candleInterval);
  }, AUTO_UPDATE_INTERVAL);
}

function stopAutoUpdate() {
  if (autoUpdateInterval) {
    clearInterval(autoUpdateInterval);
    autoUpdateInterval = null;
  }
}

// Update your setupZoomHandler function
function setupZoomHandler() {
  const plot = document.getElementById('plot');
  plot.on('plotly_relayout', function(eventdata) {
    // Check if user zoomed or panned
    if (eventdata['xaxis.range[0]'] || eventdata['xaxis.range'] || 
        eventdata['xaxis.autorange'] === false) {
      isUserZoomed = true;
      
      // Store the current zoom range
      const currentLayout = plot.layout;
      if (currentLayout && currentLayout.xaxis) {
        currentTimeRange.userZoom = {
          from: currentLayout.xaxis.range[0],
          to: currentLayout.xaxis.range[1]
        };
      }
    } else if (eventdata['xaxis.autorange'] === true) {
      // User clicked "reset axes" or similar
      isUserZoomed = false;
      delete currentTimeRange.userZoom;
    }
  });
}