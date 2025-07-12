# CryptoStream - Traitement Fonctionnel de Données Crypto

## Source de Données

### API Binance
J'ai choisi l'API publique de Binance pour récupérer les données de marché crypto :
- **URL** : `https://api.binance.com/api/v3/klines`
- **Données** : Prix OHLC (Open, High, Low, Close), volume, nombre de trades
- **Fréquences** : 1s, 1m, 15m, 1h, 1d
- **Cryptos surveillées** : BTC, ETH, XRP, SOL (contre USDC)

### Avantages de cette source
- **Données en temps réel** : Flux continu et fiable
- **Richesse des données** : Métriques complètes pour l'analyse technique
- **Haute fréquence** : Permet de tester les performances du pipeline
- **Gratuité** : Pas de limitation pour ce volume de données

## Architecture Fonctionnelle

### Vue d'ensemble

L'architecture suit un modèle de pipeline fonctionnel basé sur la séparation des responsabilités :

```
API Crypto → Producers → Kafka → Consumers → InfluxDB
```

### Composants principaux

**Producers (Producteurs)**
- Récupèrent les données de prix depuis une API crypto
- Appliquent des transformations pures sur les données
- Publient les messages dans Kafka

**Consumers (Consommateurs)**
- Lisent les flux Kafka
- Enrichissent et transforment les données via des fonctions pures
- Persistent le résultat dans InfluxDB

**Kafka**
- Centralise la distribution des flux de données
- Découple les producteurs des consommateurs
- Garantit la résilience et la scalabilité

**InfluxDB**
- Base de données orientée séries temporelles
- Optimisée pour les métriques financières
- Stockage des données enrichies

## Choix Techniques

### Justification des Technologies

| Composant | Choix | Justification |
|-----------|-------|---------------|
| **Kafka** | Confluent Platform | Écosystème complet avec interface de monitoring |
| **InfluxDB v2** | Time-Series DB | Adaptée aux données OHLC et métriques financières |
| **Python** | Langage principal | Riche écosystème pour le traitement de données |
| **Docker** | Conteneurisation | Isolation des services et reproductibilité |

### Paradigme Fonctionnel Appliqué

#### 1. Immutabilité des Données
- Les messages Kafka ne sont jamais modifiés après publication
- Les transformations créent de nouvelles structures de données
- Pipeline : `RAW → ENRICHED → PERSISTED`

#### 2. Fonctions Pures
```python
# Transformation pure des données Kline
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
        "interval": interval
    }

# Enrichissement pur des données
def compute_indicators(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule des indicateurs techniques (fonction pure)."""
    data['sma'] = (float(data['open']) + float(data['close'])) / 2
    return data
```

#### 3. Composition de Fonctions
Le traitement suit une logique de pipeline fonctionnel :
```
fetch_kline_data → parse_kline_entry → compute_indicators → build_influx_point
```

**Producer Pipeline :**
```python
def process_coin(producer, topic, coin, interval):
    """Pipeline : fetch → transform → send"""
    data = fetch_kline_data(coin, interval)  # Pure
    count = send_to_kafka(producer, topic, data)  # Effect
    return count
```

**Consumer Pipeline :**
```python
def process_message(write_api, buckets, org, interval):
    """Pipeline : parse → enrich → persist"""
    raw_data = parse_message(value)  # Pure
    enriched = compute_indicators(raw_data)  # Pure
    write_to_influx(write_api, enriched, bucket, org)  # Effect
```

#### 4. Absence d'Effets de Bord
- **Séparation claire** : Fonctions pures vs fonctions d'effet
- **Logique métier isolée** : Calculs séparés des opérations I/O
- **Testabilité** : Chaque transformation peut être testée indépendamment
- **Prédictibilité** : Même input produit toujours le même output

## Traitements Effectués

### 1. Nettoyage et Validation
```python
def convert_to_float(value: Any) -> float:
    """Conversion sécurisée en float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return value
```
- Validation des formats de données reçues de l'API
- Conversion sécurisée des types (string → float)
- Gestion des valeurs nulles ou aberrantes

### 2. Enrichissement des Données
```python
def compute_indicators(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule des indicateurs techniques."""
    data['sma'] = (float(data['open']) + float(data['close'])) / 2
    return data
```
- Calcul d'indicateurs techniques (SMA, etc.)
- Ajout de métadonnées temporelles
- Enrichissement avec des données calculées

### 3. Agrégation Multi-Intervalles
- Traitement parallèle des différents intervalles (1s, 1m, 15m, 1h, 1d)
- Synchronisation des données entre timeframes
- Calculs statistiques sur fenêtres glissantes

### 4. Persistance Structurée
- Séparation des données brutes et enrichies
- Stockage optimisé pour les séries temporelles
- Indexation par coin, intervalle et timestamp

### 5. Monitoring et Logs
- Logging structuré en JSON Lines
- Métriques de performance (latence, débit)
- Alertes sur les erreurs de traitement

## Installation et Démarrage

### Prérequis
```bash
# Créer le réseau Docker
docker network create crypto_network

# Préparer les secrets InfluxDB
mkdir -p ./influxdb/secrets/
echo "admin" > ./influxdb/secrets/.env.influxdb2-admin-username
echo "password123" > ./influxdb/secrets/.env.influxdb2-admin-password
echo "token123" > ./influxdb/secrets/.env.influxdb2-admin-token
```

### Lancement
```bash
# Démarrer tous les services
docker-compose up --build
```

### Accès aux Interfaces
- **Confluent Control Center** : http://localhost:9021
- **InfluxDB UI** : http://localhost:8086

## Structure du Code

### Producer (producer.py)
```python
# Fonctions pures
def get_coin_list() -> List[str]
def parse_kline_entry(entry: List[Any], coin: str, interval: str) -> Dict[str, Any]
def fetch_kline_data(coin: str, interval: str) -> List[Dict[str, Any]]

# Fonctions d'effet (I/O)
def connect_kafka(servers: str) -> KafkaProducer
def send_to_kafka(producer: KafkaProducer, topic: str, messages: List[Dict[str, Any]]) -> int

# Pipeline fonctionnel
def process_coin(producer, topic, coin, interval) -> int
def process_all(producer, topic, coins, interval) -> int
```

### Consumer (consumer.py)
```python
# Fonctions pures
def parse_message(value: bytes) -> Dict[str, Any]
def build_influx_point(data: Dict[str, Any], interval: str, measurement_type: str) -> Point
def compute_indicators(data: Dict[str, Any]) -> Dict[str, Any]

# Fonctions d'effet (I/O)
def connect_kafka(topic: str, servers: str) -> KafkaConsumer
def write_to_influx(write_api, point: Point, bucket: str, org: str) -> None
def append_to_file(path: str, line: str) -> None

# Pipeline fonctionnel
def process_message(write_api, buckets, org, interval, log_dir) -> Callable[[bytes], None]
```

### Architecture Docker
- **Services isolés** : Chaque producer/consumer dans son container
- **Ressources limitées** : CPU/Memory constraints pour éviter la surcharge
- **Secrets management** : Credentials InfluxDB sécurisés
- **Réseaux privés** : Communication interne uniquement

## Sécurité

- Utilisation des Docker secrets pour les credentials
- Pas de mots de passe hardcodés
- Kafka accessible uniquement en interne
- Chiffrement des communications sensibles

## Démonstration des Concepts Fonctionnels

### Map, Filter, Reduce
```python
# Map : Transformation de tous les éléments
def process_all(producer, topic, coins, interval):
    with ThreadPoolExecutor() as executor:
        results = executor.map(
            lambda coin: process_coin(producer, topic, coin, interval), 
            coins
        )
    return sum(results)  # Reduce

# Filter : Sélection conditionnelle
def get_valid_coins() -> List[str]:
    all_coins = ['BTCUSDC', 'ETHUSDC', 'XRPUSDC', 'SOLUSDC']
    return [coin for coin in all_coins if is_valid_symbol(coin)]
```

### Higher-Order Functions
```python
# Fonction qui retourne une fonction (closure)
def process_message(write_api, buckets, org, interval, log_dir) -> Callable[[bytes], None]:
    def handle(value: bytes) -> None:
        # Traitement avec contexte fermé
        raw_data = parse_message(value)
        enriched = compute_indicators(raw_data)
        write_to_influx(write_api, enriched, buckets, org)
    return handle

# Utilisation
handler = process_message(write_api, bucket, org, interval, log_dir)
for msg in consumer:
    handler(msg.value)
```

### Currying et Partial Application
```python
# Configuration des fonctions avec contexte
def create_kafka_sender(producer, topic):
    return lambda messages: send_to_kafka(producer, topic, messages)

# Utilisation
sender = create_kafka_sender(producer, "prices-1s")
sender(kline_data)
```

### Monads et Error Handling
```python
# Gestion fonctionnelle des erreurs
def safe_convert(value):
    try:
        return ("success", float(value))
    except (ValueError, TypeError):
        return ("error", value)

# Chaînage sécurisé
def process_safely(data):
    result = safe_convert(data.get('price'))
    if result[0] == "success":
        return transform_price(result[1])
    else:
        return log_error(result[1])
```

## Bonnes Pratiques Respectées

### Programmation Fonctionnelle
- **Séparation des responsabilités** : Producteurs ≠ Consommateurs
- **Fonctions pures** : Logique métier sans effets de bord
- **Immutabilité** : Données jamais modifiées en place
- **Composabilité** : Fonctions combinables et réutilisables

### Architecture
- **Event-driven** : Architecture basée sur les événements
- **Modularité** : Composants isolés et testables
- **Observabilité** : Monitoring intégré via Control Center
- **Résilience** : Gestion des pannes et retry automatique

## Cas d'Usage

Ce projet peut être utilisé pour :
- **Analyse technique** : Calcul d'indicateurs en temps réel
- **Backtesting** : Test de stratégies sur données historiques
- **Surveillance** : Monitoring des marchés crypto
- **Alertes** : Notification sur seuils de prix/volume
- **Recherche** : Étude des patterns de marché

## Captures d'Écran et Visualisations

### Confluent Control Center
- **Topics Kafka** : Visualisation des flux `prices-1s`, `prices-1m`, etc.
- **Débit des messages** : Métriques en temps réel du throughput
- **Latence** : Monitoring des délais de traitement
- **Santé du cluster** : État des brokers et consumers

### InfluxDB Dashboard
- **Données brutes** : Bucket `marketdata_raw` avec prix OHLC
- **Données enrichies** : Bucket `marketdata_enriched` avec indicateurs
- **Métriques temporelles** : Graphiques par crypto et par intervalle
- **Performance** : Temps de traitement et volumes traités

### Logs des Services
```bash
✅ Cycle 1 - Début
✅ BTCUSDC: 1 messages envoyés
✅ ETHUSDC: 1 messages envoyés
✅ XRPUSDC: 1 messages envoyés
✅ SOLUSDC: 1 messages envoyés
✅ Cycle 1 terminé en 0.45s avec 4 messages

🔄 Démarrage du consumer pour le topic 'prices-1s'
✅ BTCUSDC @ 1703251200000 (1s | brut + enrichi)
✅ ETHUSDC @ 1703251200000 (1s | brut + enrichi)
```

### Architecture Visuelle
```
[API Binance] → [Producers] → [Kafka Topics] → [Consumers] → [InfluxDB]
      ↓              ↓             ↓              ↓           ↓
   Pure Funcs    Pure Funcs    Streaming     Pure Funcs   Time-Series
                                Events                      Storage
```

## Conclusion

CryptoStream démontre l'application pratique de la programmation fonctionnelle dans un contexte de traitement de données en temps réel. Le projet respecte les principes fonctionnels tout en maintenant des performances élevées et une architecture robuste pour le traitement de flux financiers.