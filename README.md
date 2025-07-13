
# CryptoStream - Traitement Fonctionnel de Données Crypto

![Architecture](assets/architecture.png)

Pipeline de traitement de données crypto basé sur les principes de programmation fonctionnelle pour une analyse temps réel.

## 🚀 Fonctionnalités

- **Collecte temps réel** depuis l'API Binance (BTC, ETH, XRP, SOL/USDC)  
- **Traitement fonctionnel** avec transformations pures et immutables  
- **Multi-fréquence** : 1s, 1m, 15m, 1h, 1d  
- **Indicateurs techniques** calculés en streaming  
- **Monitoring intégré** avec Grafana et Confluent Control Center  

## 🛠 Architecture

```mermaid
graph LR
    A[API Binance] --> B[Producers]
    B --> C[Kafka]
    C --> D[Consumers]
    D --> E[InfluxDB]
    E --> F[Grafana]
```

## Composants clés

| Composant | Technologie     | Rôle                                   |
| --------- | -------------- | ------------------------------------- |
| Producers | Python         | Récupération et transformation des données |
| Broker    | Confluent Kafka| Centralisation des flux                |
| Consumers | Python         | Enrichissement et persistance         |
| BDD       | InfluxDB v2    | Stockage des séries temporelles       |
| Viz       | Grafana        | Visualisation des données              |

## 📦 Installation

### Prérequis

- Docker 20.10+  
- Docker Compose 2.0+  

### Commandes

```bash
# 1. Créer le réseau Docker
docker network create crypto_network

# 2. Configurer les secrets (optionnel)
mkdir -p ./influxdb/secrets/
echo "admin" > ./influxdb/secrets/.env.influxdb2-admin-username
echo "password123" > ./influxdb/secrets/.env.influxdb2-admin-password

# 3. Lancer les services
docker-compose up --build
```

## 🔌 Accès aux interfaces

| Service                 | URL                     |
| ----------------------- | ----------------------- |
| Confluent Control Center| http://localhost:9021   |
| InfluxDB UI             | http://localhost:8086   |
| Grafana                 | http://localhost:3000   |

## 🌟 Principes Fonctionnels

- **Immutabilité** : Toutes les transformations créent de nouvelles données  
- **Fonctions pures** : Logique métier sans effets de bord  
- **Composition** : Pipeline fetch → parse → enrich → store  
- **Séparation I/O** : Isolation des opérations impures  

## 📊 Exemple de Pipeline

```python
# Producer
fetch_data() → parse_kline() → validate() → send_to_kafka()

# Consumer
read_kafka() → compute_indicators() → build_influx_point() → store()
```

## 📈 Cas d'usage

- Analyse technique temps réel  
- Backtesting de stratégies  
- Surveillance de marché  
- Alertes automatiques  
