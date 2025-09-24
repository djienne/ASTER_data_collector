import websocket
import json
import threading
import time
import os
import csv
import argparse
import requests
from datetime import datetime
from collections import deque

LIST_MARKETS = ['ASTERUSDT', 'BTCUSDT', 'ETHUSDT', 'USD1USDT']

class WebSocketDataCollector:
    def __init__(self, symbols, flush_interval=5):
        self.symbols = [symbol.upper() for symbol in symbols]
        self.flush_interval = flush_interval
        self.base_url = "wss://fstream.asterdex.com"
        self.api_base_url = "https://fapi.asterdex.com"

        # WebSocket connections
        self.depth_ws = None
        self.trades_ws = None

        # Connection management
        self.is_connected = False
        self.should_reconnect = True
        self.reconnect_interval = 5
        self.ping_timeout = 15
        self.ping_interval = 30

        # Data buffers
        self.prices_buffer = {}  # symbol -> deque of price records
        self.trades_buffer = {}  # symbol -> deque of trade records
        self.seen_trade_ids = {}  # symbol -> set of seen trade IDs

        # Thread management
        self.flush_thread = None
        self.lock = threading.Lock()

        # Initialize buffers and load existing trade IDs
        for symbol in self.symbols:
            self.prices_buffer[symbol] = deque()
            self.trades_buffer[symbol] = deque()
            self.seen_trade_ids[symbol] = self.load_seen_trade_ids(symbol)

        print(f"Initialized WebSocket Data Collector for: {', '.join(self.symbols)}")

    def create_data_directory(self):
        """Creates the ASTER_data directory if it doesn't exist."""
        if not os.path.exists('ASTER_data'):
            os.makedirs('ASTER_data')

    def load_seen_trade_ids(self, symbol):
        """Loads the last 1000 existing trade IDs from the CSV file to prevent duplicates."""
        seen_ids = set()
        file_path = os.path.join('ASTER_data', f'trades_{symbol}.csv')
        if not os.path.isfile(file_path):
            return seen_ids

        try:
            with open(file_path, 'r', newline='') as csvfile:
                lines = csvfile.readlines()
                last_1000_lines = lines[-1000:]

                if lines and last_1000_lines[0] == lines[0] and lines[0].startswith('id,'):
                    start_index = 1
                else:
                    start_index = 0

                reader = csv.reader(last_1000_lines[start_index:])
                for row in reader:
                    if row:
                        try:
                            seen_ids.add(int(row[0]))
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            print(f"Warning: Error loading trade IDs for {symbol}: {e}")

        return seen_ids

    def get_initial_prices_api(self, symbol):
        """Get initial price data via API to establish baseline."""
        endpoint = f"{self.api_base_url}/fapi/v1/ticker/bookTicker"
        params = {'symbol': symbol}

        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            bid = float(data['bidPrice'])
            ask = float(data['askPrice'])
            mid = (bid + ask) / 2
            timestamp = time.time()

            return {
                'timestamp': timestamp,
                'bid': bid,
                'ask': ask,
                'mid': mid
            }
        except Exception as e:
            print(f"Error getting initial prices for {symbol}: {e}")
            return None

    def get_initial_trades_api(self, symbol):
        """Get initial trade data via API to establish baseline."""
        endpoint = f"{self.api_base_url}/fapi/v1/trades"
        params = {'symbol': symbol, 'limit': 100}

        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            trades = response.json()

            new_trades = []
            for trade in trades:
                if trade['id'] not in self.seen_trade_ids[symbol]:
                    trade_data = {
                        'id': trade['id'],
                        'timestamp': trade['time'],
                        'side': "sell" if trade['isBuyerMaker'] else "buy",
                        'price': float(trade['price']),
                        'quantity': float(trade['qty'])
                    }
                    new_trades.append(trade_data)
                    self.seen_trade_ids[symbol].add(trade['id'])

            return new_trades

        except Exception as e:
            print(f"Error getting initial trades for {symbol}: {e}")
            return []

    def on_depth_message(self, ws, message):
        """Handle depth (order book) WebSocket messages."""
        try:
            data = json.loads(message)

            if data.get('e') == 'depthUpdate' and ('b' in data and 'a' in data):
                symbol = data.get('s')
                if symbol not in self.symbols:
                    return

                bids = data.get('b', [])
                asks = data.get('a', [])

                if bids and asks:
                    # Get best bid and ask
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    mid = (best_bid + best_ask) / 2
                    timestamp = time.time()

                    price_record = {
                        'timestamp': timestamp,
                        'bid': best_bid,
                        'ask': best_ask,
                        'mid': mid
                    }

                    with self.lock:
                        self.prices_buffer[symbol].append(price_record)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error processing depth message: {e}")

    def on_trades_message(self, ws, message):
        """Handle aggregate trades WebSocket messages."""
        try:
            data = json.loads(message)

            if data.get('e') == 'aggTrade':
                symbol = data.get('s')
                if symbol not in self.symbols:
                    return

                # Extract trade data
                agg_trade_id = data.get('a')
                first_trade_id = data.get('f')
                last_trade_id = data.get('l')
                price = float(data.get('p', 0))
                quantity = float(data.get('q', 0))
                trade_time = data.get('T')
                is_buyer_maker = data.get('m', False)

                # Use first trade ID to avoid duplicates (since this represents multiple trades)
                # But we need to be careful with aggregate trades vs individual trades
                trade_id = agg_trade_id  # Use aggregate trade ID as unique identifier

                if trade_id not in self.seen_trade_ids[symbol]:
                    side = "sell" if is_buyer_maker else "buy"

                    trade_record = {
                        'id': trade_id,
                        'timestamp': trade_time,
                        'side': side,
                        'price': price,
                        'quantity': quantity
                    }

                    with self.lock:
                        self.trades_buffer[symbol].append(trade_record)
                        self.seen_trade_ids[symbol].add(trade_id)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error processing trades message: {e}")

    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        print(f"WebSocket error: {error}")
        self.is_connected = False

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        print(f"WebSocket connection closed. Status: {close_status_code}")
        self.is_connected = False

    def on_depth_open(self, ws):
        """Handle depth WebSocket open."""
        print("Depth WebSocket connected")

    def on_trades_open(self, ws):
        """Handle trades WebSocket open."""
        print("Trades WebSocket connected")
        self.is_connected = True

    def create_combined_stream_url(self):
        """Create combined stream URL for all symbols."""
        depth_streams = [f"{symbol.lower()}@depth5" for symbol in self.symbols]
        trade_streams = [f"{symbol.lower()}@aggTrade" for symbol in self.symbols]
        all_streams = depth_streams + trade_streams

        stream_names = "/".join(all_streams)
        url = f"{self.base_url}/stream?streams={stream_names}"
        return url

    def on_combined_message(self, ws, message):
        """Handle combined stream messages."""
        try:
            data = json.loads(message)
            stream_name = data.get('stream', '')
            stream_data = data.get('data', {})

            if '@depth' in stream_name:
                # Process as depth message
                self.on_depth_message(None, json.dumps(stream_data))
            elif '@aggTrade' in stream_name:
                # Process as trade message
                self.on_trades_message(None, json.dumps(stream_data))

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error processing combined message: {e}")

    def on_combined_open(self, ws):
        """Handle combined WebSocket open."""
        print("Combined WebSocket connected for all symbols")
        self.is_connected = True

    def start_websockets(self):
        """Start WebSocket connections."""
        websocket.enableTrace(False)

        # Use combined stream for all symbols
        combined_url = self.create_combined_stream_url()
        print(f"Connecting to: {combined_url}")

        self.combined_ws = websocket.WebSocketApp(
            combined_url,
            on_open=self.on_combined_open,
            on_message=self.on_combined_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        # Start WebSocket in a separate thread
        def run_websocket():
            while self.should_reconnect:
                try:
                    self.combined_ws.run_forever(
                        ping_interval=self.ping_interval,
                        ping_timeout=10
                    )

                    if self.should_reconnect:
                        print(f"WebSocket disconnected. Reconnecting in {self.reconnect_interval}s...")
                        time.sleep(self.reconnect_interval)

                except Exception as e:
                    print(f"WebSocket error: {e}")
                    if self.should_reconnect:
                        time.sleep(self.reconnect_interval)

        ws_thread = threading.Thread(target=run_websocket, daemon=True)
        ws_thread.start()

    def flush_buffers(self):
        """Flush all buffers to CSV files."""
        with self.lock:
            # Flush price data
            for symbol in self.symbols:
                if self.prices_buffer[symbol]:
                    self.flush_prices_buffer(symbol)

                if self.trades_buffer[symbol]:
                    self.flush_trades_buffer(symbol)

    def flush_prices_buffer(self, symbol):
        """Flush price buffer for a specific symbol."""
        file_path = os.path.join('ASTER_data', f'prices_{symbol}.csv')
        file_exists = os.path.isfile(file_path)

        try:
            with open(file_path, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(['unix_timestamp', 'bid', 'ask', 'mid'])

                count = 0
                while self.prices_buffer[symbol]:
                    record = self.prices_buffer[symbol].popleft()
                    writer.writerow([
                        record['timestamp'],
                        record['bid'],
                        record['ask'],
                        f"{record['mid']:.6f}"
                    ])
                    count += 1

                if count > 0:
                    print(f"Flushed {count} price records for {symbol}")

        except Exception as e:
            print(f"Error flushing prices for {symbol}: {e}")

    def flush_trades_buffer(self, symbol):
        """Flush trades buffer for a specific symbol."""
        file_path = os.path.join('ASTER_data', f'trades_{symbol}.csv')
        file_exists = os.path.isfile(file_path)

        try:
            with open(file_path, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(['id', 'unix_timestamp_ms', 'side', 'price', 'quantity'])

                count = 0
                while self.trades_buffer[symbol]:
                    record = self.trades_buffer[symbol].popleft()
                    writer.writerow([
                        record['id'],
                        record['timestamp'],
                        record['side'],
                        f"{record['price']:.6f}",
                        f"{record['quantity']:.6f}"
                    ])
                    count += 1

                if count > 0:
                    print(f"Flushed {count} trade records for {symbol}")

        except Exception as e:
            print(f"Error flushing trades for {symbol}: {e}")

    def start_flush_thread(self):
        """Start the buffer flush thread."""
        def flush_worker():
            while self.should_reconnect:
                time.sleep(self.flush_interval)
                self.flush_buffers()

        self.flush_thread = threading.Thread(target=flush_worker, daemon=True)
        self.flush_thread.start()
        print(f"Started buffer flush thread (interval: {self.flush_interval}s)")

    def collect_initial_data(self):
        """Collect initial data via API calls."""
        print("Collecting initial data via API...")

        for symbol in self.symbols:
            print(f"Getting initial data for {symbol}...")

            # Get initial price data
            initial_price = self.get_initial_prices_api(symbol)
            if initial_price:
                with self.lock:
                    self.prices_buffer[symbol].append(initial_price)
                print(f"  Initial price: ${initial_price['mid']:.2f}")

            # Get initial trade data
            initial_trades = self.get_initial_trades_api(symbol)
            if initial_trades:
                with self.lock:
                    self.trades_buffer[symbol].extend(initial_trades)
                print(f"  Loaded {len(initial_trades)} initial trades")

            print(f"  Existing trade IDs loaded: {len(self.seen_trade_ids[symbol])}")

    def start(self):
        """Start the data collector."""
        self.create_data_directory()

        # Collect initial data via API
        self.collect_initial_data()

        # Start buffer flush thread
        self.start_flush_thread()

        # Start WebSocket connections
        self.start_websockets()

        # Wait for connection
        max_wait = 10
        waited = 0
        while not self.is_connected and waited < max_wait:
            time.sleep(1)
            waited += 1

        if self.is_connected:
            print("WebSocket data collector started successfully!")
        else:
            print("Warning: WebSocket connection not established within timeout")

    def stop(self):
        """Stop the data collector."""
        print("Stopping data collector...")
        self.should_reconnect = False

        if hasattr(self, 'combined_ws') and self.combined_ws:
            self.combined_ws.close()

        # Final flush
        self.flush_buffers()
        print("Data collector stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WebSocket-based data collector for crypto market data.')
    parser.add_argument('symbols', type=str, nargs='*', default=LIST_MARKETS,
                        help='The trading symbols to collect data for (e.g., BTCUSDT ETHUSDT).')
    parser.add_argument('--flush-interval', type=int, default=5,
                        help='The interval in seconds to flush buffers to CSV files. Defaults to 5.')
    args = parser.parse_args()

    collector = WebSocketDataCollector(args.symbols, args.flush_interval)

    try:
        collector.start()

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        collector.stop()