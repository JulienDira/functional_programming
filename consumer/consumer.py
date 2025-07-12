from kafka import KafkaConsumer
import json
import polars as pl
import rx
from rx import operators as ops

from utils.transformations import clean_and_type, is_valid, polars_from_batch, enrich_polars, window_aggregate
from utils.save_data import save_raw, save_curated, save_to_duck

consumer = KafkaConsumer(
    'shorttime',
    bootstrap_servers=['kafka:9092'],
    auto_offset_reset='latest',
    value_deserializer=lambda x: json.loads(x.decode('utf-8')),
    consumer_timeout_ms=1000
)

def process_batch(entries):
    cleaned = list(map(clean_and_type, entries))
    filtered = list(filter(is_valid, cleaned))
    df = polars_from_batch(filtered)
    enriched = enrich_polars(df)
    aggregated = window_aggregate(enriched)
    return enriched, aggregated

def main():
    def on_batch(batch):
        # side‑effect souverains, en fin de pipeline
        for e in batch:
            save_raw(e)
        enriched, aggregated = process_batch(batch)
        save_curated(aggregated)
        save_to_duck(aggregated)

    rx.from_iterable(consumer).pipe(
        ops.map(lambda msg: msg.value),
        ops.buffer_with_time_or_count(1.0, 100),
        ops.filter(lambda b: b and len(b) > 0),
        ops.do_action(on_batch)
    ).run()

if __name__ == "__main__":
    main()
