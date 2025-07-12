import json
import requests
from kafka import KafkaProducer
from concurrent.futures import ThreadPoolExecutor
from time import time, sleep
from typing import List, Dict, Any
import os

# --- PURE FUNCTIONS ---

def get_coin_list() -> List[str]:
    """Liste pure des coins à surveiller."""
    return ['BTCUSDC', 'ETHUSDC', 'XRPUSDC', 'SOLUSDC']


def convert_to_float(value: Any) -> float:
    """Conversion sécurisée en float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


def parse_kline_entry(entry: List[Any], coin: str, interval: str) -> Dict[str, Any]:
    """Transforme une ligne brute en dictionnaire structuré."""
    return {
        "coin": coin,
        "timestamp": entry[0],
        "open": convert_to_float(entry[1]),
        "high": convert_to_float(entry[2]),
        "low": convert_to_float(entry[3]),
        "close": convert_to_float(entry[4]),
        "volume": convert_to_float(entry[5]),
        "close_time": entry[6],
        "quote_asset_volume": convert_to_float(entry[7]),
        "number_of_trades": int(entry[8]),
        "taker_buy_base_asset_volume": convert_to_float(entry[9]),
        "taker_buy_quote_asset_volume": convert_to_float(entry[10]),
        "ignore": entry[11],
        "interval": interval
    }


def fetch_kline_data(coin: str, interval: str) -> List[Dict[str, Any]]:
    """Récupère et transforme les données d'une paire."""
    url = f'https://api.binance.com/api/v3/klines?symbol={coin}&interval={interval}&limit=1'
    response = requests.get(url)
    response.raise_for_status()
    return [parse_kline_entry(entry, coin, interval) for entry in response.json()]


# --- EFFECTFUL FUNCTIONS (I/O ONLY) ---

def connect_kafka(servers: str) -> KafkaProducer:
    """Connexion Kafka avec attente active (effet de bord contrôlé)."""
    while True:
        try:
            producer = KafkaProducer(bootstrap_servers=[servers])
            print("✅ Kafka connecté")
            return producer
        except Exception as e:
            print(f"⏳ En attente de Kafka: {e}")
            sleep(1)


def send_to_kafka(producer: KafkaProducer, topic: str, messages: List[Dict[str, Any]]) -> int:
    """Envoie les messages (effet de bord)."""
    for msg in messages:
        key = msg['coin'].encode('utf-8')
        value = json.dumps(msg).encode('utf-8')
        producer.send(topic, key=key, value=value)
    producer.flush()
    return len(messages)


# --- PIPELINE ---

def process_coin(producer: KafkaProducer, topic: str, coin: str, interval: str) -> int:
    """Pipeline d'un coin : fetch, transform, send."""
    try:
        data = fetch_kline_data(coin, interval)
        count = send_to_kafka(producer, topic, data)
        print(f"✅ {coin}: {count} messages envoyés")
        return count
    except Exception as e:
        print(f"❌ {coin}/{interval} -> {e}")
        return 0


def process_all(producer: KafkaProducer, topic: str, coins: List[str], interval: str) -> int:
    """Traitement en parallèle des coins."""
    with ThreadPoolExecutor() as executor:
        results = executor.map(lambda coin: process_coin(producer, topic, coin, interval), coins)
    return sum(results)

def run_pipeline(servers: str):
    """Boucle de traitement fonctionnelle (récursive si besoin)."""
    interval = os.getenv("INTERVAL")
    if not interval:
        raise ValueError("❌ La variable d'environnement INTERVAL n'est pas définie.")
    topic = f"prices-{interval}"
    producer = connect_kafka(servers)
    coins = get_coin_list()
    cycle = 1

    while True:
        start = time()
        print(f"\n🔁 Cycle {cycle} - Début")
        total_messages = process_all(producer, topic, coins, interval)
        duration = time() - start
        print(f"✅ Cycle {cycle} terminé en {duration:.2f}s avec {total_messages} messages")
        cycle += 1


# --- ENTRYPOINT ---

if __name__ == "__main__":
    try:
        run_pipeline(servers='broker:29092')
    except KeyboardInterrupt:
        print("🚪 Interruption utilisateur")
