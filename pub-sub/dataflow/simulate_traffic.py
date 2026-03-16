"""
Simula tráfico de E-commerce publicando eventos en Pub/Sub.
Ejecutar: python simulate_traffic.py
Ctrl+C para parar.
"""

import json
import random
import time
import uuid
from datetime import datetime, timezone

from google.cloud import pubsub_v1

PROJECT_ID = "project-dev-490218"
TOPIC = "realtime-events"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC)

EVENT_TYPES = ["page_view", "product_view", "search", "add_to_cart", "remove_from_cart", "checkout_start", "purchase"]
WEIGHTS = [30, 25, 10, 15, 5, 8, 7]
DEVICES = ["mobile", "desktop", "tablet"]
CUSTOMERS = [f"cust-{i:04d}" for i in range(1, 51)]
PRODUCTS = [f"prod-{i:04d}" for i in range(1, 21)]

print("Simulando tráfico de E-commerce... (Ctrl+C para parar)")

try:
    count = 0
    while True:
        event_type = random.choices(EVENT_TYPES, weights=WEIGHTS)[0]
        event = {
            "event_id": f"rt-{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "customer_id": random.choice(CUSTOMERS),
            "session_id": f"sess-{random.randint(1, 500):04d}",
            "product_id": random.choice(PRODUCTS) if event_type in ["product_view", "add_to_cart", "remove_from_cart"] else None,
            "search_query": random.choice(["laptop", "mouse", "teclado", "auriculares"]) if event_type == "search" else None,
            "page_url": f"/{event_type}",
            "device": random.choice(DEVICES),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        message = json.dumps(event).encode("utf-8")
        publisher.publish(topic_path, message)
        count += 1

        if count % 10 == 0:
            print(f"  Publicados {count} eventos...")

        time.sleep(random.uniform(0.3, 1.0))

except KeyboardInterrupt:
    print(f"\nParado. Total eventos publicados: {count}")
