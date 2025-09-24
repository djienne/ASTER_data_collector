# ASTER Data Collector

This project contains a Python script (`data_collector.py`) for collecting real-time cryptocurrency trade and price data from the ASTER exchange using websockets.

Referral link to support this work: [https://www.asterdex.com/en/referral/164f81](https://www.asterdex.com/en/referral/164f81) .

Earn 10% rebate (I put maximum for you).

## Usage

To collect data, run the `data_collector.py` script:

```bash
python data_collector.py
```

The script will connect to the ASTER exchange via websockets to stream and save trade and price data.

Update the `LIST_MARKETS` variable at the top of `data_collector.py` (e.g., `LIST_MARKETS = ['ASTERUSDT', 'BTCUSDT', 'ETHUSDT', 'USD1USDT']`) to specify which markets should be collected.

## Data

The script generates the following data files in the `ASTER_data/` directory:

*   `prices_<symbol>.csv`: Contains historical price data for a given symbol (e.g., `prices_ASTERUSDT.csv`).
*   `trades_<symbol>.csv`: Contains historical trade data for a given symbol (e.g., `trades_ASTERUSDT.csv`).

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
