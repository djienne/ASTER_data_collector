# ASTER Data Collector

This project contains a Python script (`data_collector.py`) for collecting real-time cryptocurrency trade, price, and order book data from the ASTER exchange using websockets.

Referral link to support this work: [https://www.asterdex.com/en/referral/164f81](https://www.asterdex.com/en/referral/164f81) .\
Earn 10% rebate (I put maximum for you).

## Usage

To collect data, run the `data_collector.py` script:

```bash
python data_collector.py
```

The script will connect to the ASTER exchange via websockets to stream and save trade, price, and order book data.

### Command Line Options

```bash
# Default usage (collects 10 levels of order book data)
python data_collector.py

# Specify symbols and order book levels
python data_collector.py BTCUSDT ETHUSDT --order-book-levels 5

# Adjust flush interval for CSV writes
python data_collector.py --flush-interval 2 --order-book-levels 20

# Show help
python data_collector.py --help
```

**Available Options:**
- `symbols`: Trading symbols to collect (e.g., BTCUSDT ETHUSDT). Defaults to LIST_MARKETS.
- `--order-book-levels`: Number of order book levels to collect (5, 10, or 20). Default: 10.
- `--flush-interval`: Interval in seconds to flush data to CSV files. Default: 5.

Update the `LIST_MARKETS` variable at the top of `data_collector.py` (e.g., `LIST_MARKETS = ['ASTERUSDT', 'BTCUSDT', 'ETHUSDT', 'USD1USDT']`) to specify default markets.

## Data

The script generates the following data files in the `ASTER_data/` directory:

*   `prices_<symbol>.csv`: Contains best bid/ask/mid price data for a given symbol (e.g., `prices_ASTERUSDT.csv`).
    - Columns: `unix_timestamp`, `bid`, `ask`, `mid`
*   `orderbook_<symbol>.csv`: Contains full order book depth data for a given symbol (e.g., `orderbook_ASTERUSDT.csv`).
    - Columns: `unix_timestamp`, `lastUpdateId`, `bid_price_0`, `bid_qty_0`, ..., `ask_price_N`, `ask_qty_N`
    - Contains up to N levels of bid/ask data based on `--order-book-levels` setting
*   `trades_<symbol>.csv`: Contains historical trade data for a given symbol (e.g., `trades_ASTERUSDT.csv`).
    - Columns: `id`, `unix_timestamp_ms`, `side`, `price`, `quantity`

### Data Format Details

**Order Book Data**: Each row contains a timestamp, update ID, and bid/ask levels sorted by price. Bids are in descending order (highest first), asks in ascending order (lowest first). Empty levels are filled with blank values.

**Price Data**: Provides best bid/offer (BBO) data for quick access to top-of-book prices.

**Trade Data**: Contains executed trades with unique IDs, timestamps, side (buy/sell), price, and quantity.

## Dependencies

This project likely requires the `websocket-client` library and potentially others for data handling (e.g., `pandas`). It's recommended to install dependencies via a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## Docker Usage

This project can also be run using Docker and Docker Compose, providing an isolated environment for data collection.

To build and run the Docker container:

```bash
docker-compose up --build -d
```

This command will:
1.  Build the Docker image for the `data-collector` service.
2.  Create and start the container in detached mode (`-d`).
3.  Mount the `ASTER_data` directory from your host into the container to persist collected data.

To stop the Docker container:

```bash
docker-compose down
```
