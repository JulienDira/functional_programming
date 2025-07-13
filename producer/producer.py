import json
import asyncio
import websockets
from kafka import KafkaProducer
from typing import List, Dict, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass
from functools import partial
import os
import logging
from time import time
import time as t

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- TYPES & DATA STRUCTURES ---

@dataclass(frozen=True)
class KlineData:
    """Structure immutable pour les données kline."""
    coin: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float
    interval: str
    is_closed: bool
    processed_at: int

@dataclass(frozen=True)
class Config:
    """Configuration immutable."""
    coins: Tuple[str, ...]
    interval: str
    kafka_servers: str
    topic: str
    
    @classmethod
    def from_env(cls) -> 'Config':
        interval = os.getenv("INTERVAL")
        if not interval:
            raise ValueError("❌ La variable d'environnement INTERVAL n'est pas définie.")
        
        return cls(
            coins=('BTCUSDC', 'ETHUSDC', 'XRPUSDC', 'SOLUSDC'),
            interval=interval,
            kafka_servers='broker:29092',
            topic=f"prices-{interval}"
        )

# --- UTILITAIRES DE CONVERSION ---

def safe_float(value: Any) -> float:
    """Convertit une valeur en float en toute sécurité. Retourne 0.0 si échec."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_int(value: Any) -> int:
    """Convertit une valeur en int en toute sécurité. Retourne 0 si échec."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

def parse_kline_message(raw_data: Dict[str, Any], current_time: int) -> Optional[KlineData]:
    """Extrait et structure les données kline d’un message WebSocket brut."""
    try:
        # Messages combinés ont une structure différente
        if 'data' in raw_data and 'k' in raw_data['data']:
            kline = raw_data['data']['k']
        elif 'k' in raw_data:
            kline = raw_data['k']
        else:
            return None
            
        return KlineData(
            coin=kline['s'],
            timestamp=safe_int(kline['t']),
            open=safe_float(kline['o']),
            high=safe_float(kline['h']),
            low=safe_float(kline['l']),
            close=safe_float(kline['c']),
            volume=safe_float(kline['v']),
            close_time=safe_int(kline['T']),
            quote_asset_volume=safe_float(kline['q']),
            number_of_trades=safe_int(kline['n']),
            taker_buy_base_asset_volume=safe_float(kline['V']),
            taker_buy_quote_asset_volume=safe_float(kline['Q']),
            interval=kline['i'],
            is_closed=kline['x'],
            processed_at=current_time
        )
    except Exception:
        return None

def kline_to_kafka_message(kline: KlineData) -> Dict[str, Any]:
    """Transforme une instance de KlineData en dictionnaire pour Kafka."""
    return {
        "coin": kline.coin,
        "timestamp": kline.timestamp,
        "open": kline.open,
        "high": kline.high,
        "low": kline.low,
        "close": kline.close,
        "volume": kline.volume,
        "close_time": kline.close_time,
        "quote_asset_volume": kline.quote_asset_volume,
        "number_of_trades": kline.number_of_trades,
        "taker_buy_base_asset_volume": kline.taker_buy_base_asset_volume,
        "taker_buy_quote_asset_volume": kline.taker_buy_quote_asset_volume,
        "interval": kline.interval,
        "is_closed": kline.is_closed,
        "processed_at": kline.processed_at
    }

def should_process_kline(kline: KlineData) -> bool:
    """Détermine si une kline est fermée et donc prête à être traitée."""
    return kline.is_closed


# --- CONSTRUCTION DE L'URL WEBSOCKET ---

def create_websocket_url(coins: Tuple[str, ...], interval: str) -> str:
    """Construit l’URL WebSocket Binance pour une liste de coins et un intervalle donné."""
    streams = [f"{coin.lower()}@kline_{interval}" for coin in coins]
    stream_names = "/".join(streams)
    return f"wss://stream.binance.com:9443/stream?streams={stream_names}"

# --- FONCTIONS D'ORDRE SUPÉRIEUR (HIGHER-ORDER FUNCTIONS) ---

async def periodic_flush(producer: KafkaProducer, interval: float = 1.0) -> None:
    """Force le flush régulier du producteur Kafka pour éviter la latence de buffer."""
    while True:
        await asyncio.sleep(interval)
        producer.flush()

def with_error_handling(func: Callable) -> Callable:
    """Décorateur async qui ajoute une gestion d’erreur générique autour d’une fonction."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Erreur dans {func.__name__}: {e}")
            return None
    return wrapper

def with_logging(message: str) -> Callable:
    """Décorateur qui log un message personnalisé après exécution d’une fonction."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            logger.info(message.format(result=result))
            return result
        return wrapper
    return decorator

# --- ACCÈS EXTERNE : KAFKA & TEMPS (I/O FUNCTIONS) ---

def connect_kafka(servers: str) -> KafkaProducer:
    """Établit la connexion à un cluster Kafka, avec retry infini en cas d’échec."""
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda v: v.encode('utf-8'),
                batch_size=4096,
                linger_ms=1,
                compression_type='gzip'
            )
            logger.info("✅ Kafka connecté")
            return producer
        except Exception as e:
            logger.error(f"⏳ En attente de Kafka: {e}")
            t.sleep(5)

async def send_to_kafka_async(producer: KafkaProducer, topic: str, message: Dict[str, Any]) -> bool:
    """Envoie un message au topic Kafka spécifié. Retourne True si succès."""
    try:
        producer.send(topic, key=message['coin'], value=message)
        return True
    except Exception as e:
        logger.error(f"❌ Erreur Kafka: {e}")
        return False

def get_current_time() -> int:
    """Retourne le timestamp courant en millisecondes."""
    return int(time() * 1000)

# --- 🔄 PIPELINE DE TRAITEMENT D'UN MESSAGE (ASYNC) ---

async def process_message_pipeline(
    raw_message: str,
    config: Config,
    producer: KafkaProducer,
    time_provider: Callable[[], int] = get_current_time
) -> Optional[bool]:
    """Pipeline complet de traitement d’un message WebSocket jusqu’à l’envoi Kafka."""
    try:
        # 1. Parse JSON
        raw_data = json.loads(raw_message)
        
        # 2. Parse kline
        current_time = time_provider()
        kline = parse_kline_message(raw_data, current_time)
        if not kline:
            return None
            
        # 3. Filtrer
        if not should_process_kline(kline):
            return None
            
        # 4. Transformer
        kafka_message = kline_to_kafka_message(kline)
        
        # 5. Envoyer
        success = await send_to_kafka_async(producer, config.topic, kafka_message)
        
        if success:
            logger.info(f"✅ {kline.coin}: kline traitée")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Erreur pipeline: {e}")
        return False

# --- GESTION DU CLIENT WEBSOCKET (ASYNC) ---

@with_error_handling
async def websocket_message_handler(
    websocket,
    config: Config,
    producer: KafkaProducer
) -> None:
    """Lit les messages WebSocket, les traite via pipeline, et flush périodiquement."""
    # Créer un pipeline partiel avec la config
    process_func = partial(process_message_pipeline, config=config, producer=producer)
    
    async for message in websocket:
        await process_func(message)
        
        # Flush périodique
        if get_current_time() % 5000 < 100:  # ~toutes les 5 secondes
            producer.flush()

async def websocket_client_functional(config: Config, producer: KafkaProducer) -> None:
    """Client WebSocket résilient avec reconnexion automatique et traitement des messages."""
    url = create_websocket_url(config.coins, config.interval)
    logger.info(f"🔗 Connexion WebSocket: {url}")
    
    reconnect_delay = 1
    max_delay = 60
    
    while True:
        try:
            async with websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                logger.info("✅ WebSocket connecté")
                reconnect_delay = 1
                
                await websocket_message_handler(websocket, config, producer)
                
        except Exception as e:
            logger.error(f"❌ Erreur WebSocket: {e}")
            logger.info(f"🔄 Reconnexion dans {reconnect_delay} secondes...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_delay)

# --- PIPELINE PRINCIPAL (LANCEMENT) ---

async def run_functional_pipeline() -> None:
    """Point d’entrée principal de l’application : connecte Kafka, lance les workers."""
    config = Config.from_env()
    producer = connect_kafka(config.kafka_servers)

    logger.info(f"🚀 Démarrage WebSocket Binance → Kafka (Functional)")
    logger.info(f"📊 Coins: {', '.join(config.coins)}")
    logger.info(f"⏱️ Intervalle: {config.interval}")
    logger.info(f"🎯 Topic: {config.topic}")

    await asyncio.gather(
        websocket_client_functional(config, producer),
        periodic_flush(producer, interval=1.0)
    )

# --- POINT D’ENTRÉE SCRIPT PYTHON ---

if __name__ == "__main__":
    """Lancement de l'application en mode fonctionnel avec gestion des erreurs de haut niveau."""
    try:
        asyncio.run(run_functional_pipeline())
    except KeyboardInterrupt:
        logger.info("🚪 Interruption utilisateur")
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
        raise