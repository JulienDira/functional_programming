import json
import os
from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Dict, Any, Callable, Tuple, List
from os import getenv
from time import sleep
from functools import reduce
from collections import deque

from utils.indicators import compute_ema, compute_sma, compute_rsi

# --- PURE FUNCTIONS --- #

def parse_message(value: bytes) -> Dict[str, Any]:
    """Transforme un message Kafka brut en dictionnaire."""
    return json.loads(value.decode('utf-8'))

def build_influx_point(data: Dict[str, Any], interval: str, measurement_type: str) -> Point:
    def maybe_add_field(p: Point, key: str) -> Point:
        return p.field(key, float(data[key])) if key in data else p

    base_point = (
        Point("kline")
        .tag("coin", data["coin"])
        .tag("interval", interval)
        .tag("type", measurement_type)
        .field("open", float(data["open"]))
        .field("high", float(data["high"]))
        .field("low", float(data["low"]))
        .field("close", float(data["close"]))
        .field("volume", float(data["volume"]))
        .field("trades", int(data["number_of_trades"]))
        .time(int(data["timestamp"]), WritePrecision.MS)
    )

    indicators = ["sma_7", "sma_21", "ema_12", "rsi_14"]
    return reduce(maybe_add_field, indicators, base_point)


def format_log_line(data: Dict[str, Any]) -> str:
    """Formate la ligne pour append dans un fichier."""
    return json.dumps(data, ensure_ascii=False) + "\n"

def compute_indicators(
    data: Dict[str, Any], 
    history: List[float]
) -> Tuple[Dict[str, Any], List[float]]:
    """
    Prend les données actuelles et l'historique des prix.
    Retourne les données enrichies + nouvel historique (mise à jour).
    """
    close_price = float(data["close"])
    updated_history = (history + [close_price])[-50:]

    sma_7 = compute_sma(updated_history, 7)
    sma_21 = compute_sma(updated_history, 21)
    ema_12 = compute_ema(updated_history[-12:], 12)
    rsi_14 = compute_rsi(updated_history, 14)

    new_data = {
        **data,
        "sma_7": sma_7,
        "sma_21": sma_21,
        "ema_12": ema_12,
        "rsi_14": rsi_14
    }

    return new_data, updated_history

# --- EFFECTFUL FUNCTIONS --- #

def connect_kafka(topic: str, servers: str, group_id: str = None) -> KafkaConsumer:
    """Connexion Kafka (effet de bord)."""
    return KafkaConsumer(
        topic,
        bootstrap_servers=servers,
        auto_offset_reset='earliest',  # Lit depuis le début si nouveau consumer
        enable_auto_commit=True,
        group_id=group_id or f"consumer-group-{topic}",  # Groupe par défaut
        value_deserializer=lambda x: x
    )


def connect_influx(url: str, token: str, org: str) -> tuple:
    """Connexion InfluxDB (effet de bord)."""
    client = InfluxDBClient(url=url, token=token, org=org)
    return client.write_api(write_options=SYNCHRONOUS), client


def ensure_log_directory(interval: str) -> str:
    """Crée le dossier de logs si nécessaire et retourne le path."""
    log_dir = os.path.join("data", interval)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def append_to_file(path: str, line: str) -> None:
    """Append d'une ligne dans un fichier texte (effet de bord)."""
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line)
        

def create_bucket_if_missing(client: InfluxDBClient, bucket_name: str, org: str):
    buckets_api = client.buckets_api()
    
    # Vérifie si le bucket existe déjà
    existing = buckets_api.find_bucket_by_name(bucket_name)
    if existing:
        print(f"✅ Bucket '{bucket_name}' déjà existant.")
        return

    # Crée le bucket
    buckets_api.create_bucket(bucket_name=bucket_name, org=org)
    print(f"✅ Bucket '{bucket_name}' créé avec succès.")

def write_to_influx(write_api, point: Point, bucket: str, org: str) -> None:
    """Écriture dans InfluxDB (effet de bord)."""
    write_api.write(bucket=bucket, org=org, record=point)


def write_raw_data(raw_data: Dict[str, Any], write_api, bucket: str, org: str, interval: str):
    """Écrit les données brutes dans InfluxDB."""
    raw_point = build_influx_point(raw_data, interval, "raw")
    write_to_influx(write_api, raw_point, bucket, org)
    

def write_enriched_data(enriched_data: Dict[str, Any], write_api, bucket: str, org: str, interval: str):
    """Écrit les données enrichies dans InfluxDB."""
    enriched_point = build_influx_point(enriched_data, interval, "enriched")
    write_to_influx(write_api, enriched_point, bucket, org)

# --- PIPELINE FONCTIONNELLE --- #

def process_message(
    write_api,
    raw_bucket: str,
    enriched_bucket: str,
    org: str,
    interval: str,
    log_dir: str
) -> Callable[[bytes], None]:
    """Crée un handler de message avec contexte fermé."""
    
    # Historique des prix par coin (état local encapsulé)
    price_histories: Dict[str, List[float]] = {}
    
    def handle(value: bytes) -> None:
        try:
            raw_data = parse_message(value)
            coin = raw_data["coin"]
            
            # Chemin du fichier de log spécifique à la crypto
            log_path = os.path.join(log_dir, f"{coin}.jsonl")
            
            # 1. Log et write
            raw_line = format_log_line(raw_data)
            append_to_file(log_path, raw_line)
            write_raw_data(raw_data, write_api, raw_bucket, org, interval)

            # 2. Enrichissement avec historique
            current_history = price_histories.get(coin, [])
            enriched_data, new_history = compute_indicators(raw_data, current_history)
            
            # Mise à jour de l'historique
            price_histories[coin] = new_history
            
            # Log et write enrichi
            enriched_line = format_log_line(enriched_data)
            append_to_file(log_path, enriched_line)
            write_enriched_data(enriched_data, write_api, enriched_bucket, org, interval)

            print(f"✅ {coin} @ {raw_data['timestamp']} ({interval} | brut + enrichi)")

        except json.JSONDecodeError as e:
            print(f"❌ Erreur décodage JSON: {e}")
        except KeyError as e:
            print(f"❌ Champ manquant dans les données: {e}")
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            
    return handle

# --- MAIN LOOP --- #

def run_consumer_loop():
    """Boucle d'écoute Kafka avec traitement."""
    
    interval = getenv("INTERVAL")
    if not interval:
        raise ValueError("La variable INTERVAL doit être définie")
    
    topic = f"prices-{interval}"
    kafka_servers = getenv("KAFKA_SERVERS", "broker:29092")
    influx_url = getenv("INFLUX_URL", "http://influxdb2:8086")

    token_path = getenv("INFLUX_TOKEN_FILE", "/run/secrets/influxdb2-admin-token")
    with open(token_path, "r") as f:
        influx_token = f.read().strip()

    influx_org = getenv("INFLUX_ORG", "my-org")
    raw_bucket = getenv("RAW_BUCKET", "marketdata_raw")
    enriched_bucket = getenv("ENRICHED_BUCKET", "marketdata_enriched")
    
    # Préparation des répertoires de logs
    log_dir = ensure_log_directory(interval)
    
    # Connexions
    consumer = connect_kafka(topic, kafka_servers, group_id=f"consumer-{interval}")
    write_api, influx_client = connect_influx(influx_url, influx_token, influx_org)
    
    create_bucket_if_missing(influx_client, raw_bucket, influx_org)
    create_bucket_if_missing(influx_client, enriched_bucket, influx_org)
    
    # Création du handler
    handler = process_message(
        write_api,
        raw_bucket,
        enriched_bucket,
        influx_org,
        interval,
        log_dir
    )

    print(f"🔄 Démarrage du consumer pour le topic '{topic}' (intervalle: {interval})")

    try:
        while True:
            for msg in consumer:
                handler(msg.value)
                sleep(0.1)  # Petite tempo pour éviter la surcharge
    except KeyboardInterrupt:
        print("🛑 Interruption utilisateur")
    finally:
        influx_client.close()
        consumer.close()
        print("🚪 Fermeture propre")


# --- ENTRYPOINT --- #

if __name__ == "__main__":
    price_history = {}
    run_consumer_loop()