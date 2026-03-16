"""
Simulador de ClickEvents — E-commerce

Simula usuarios navegando la tienda en tiempo real.
Cada usuario tiene una sesión con un flujo realista:

  1. Entra a la tienda (page_view /home)
  2. Busca algo (search "laptop")
  3. Ve un producto (product_view /products/prod-001)
  4. Lo agrega al carrito (add_to_cart)
  5. A veces lo quita (remove_from_cart)
  6. Inicia checkout (checkout_start)
  7. Compra o abandona (purchase / abandono)

Cada acción se publica como un evento en Pub/Sub → Dataflow → BigQuery Bronze.

Ejecutar:
  python click_simulator.py

Opciones:
  python click_simulator.py --users 10 --speed fast
  python click_simulator.py --users 1 --speed slow (ver evento por evento)

Ctrl+C para parar.
"""

import json
import random
import time
import uuid
import argparse
import threading
from datetime import datetime, timezone

from google.cloud import pubsub_v1

# ============================================
# Configuración
# ============================================

PROJECT_ID = "project-dev-490218"
TOPIC = "realtime-events"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC)

# Datos ficticios para simular
CUSTOMERS = [
    {"id": f"cust-{i:04d}", "name": name, "country": country}
    for i, (name, country) in enumerate([
        ("Maria Garcia", "MX"), ("Juan Lopez", "CO"), ("Ana Martinez", "MX"),
        ("Carlos Rodriguez", "AR"), ("Laura Hernandez", "CL"), ("Pedro Gonzalez", "PE"),
        ("Sofia Perez", "ES"), ("Diego Sanchez", "MX"), ("Valentina Torres", "CO"),
        ("Miguel Flores", "AR"), ("Camila Rivera", "CL"), ("Andres Gomez", "PE"),
        ("Isabella Diaz", "ES"), ("Luis Cruz", "MX"), ("Fernanda Morales", "CO"),
        ("Jorge Reyes", "AR"), ("Paula Ortiz", "CL"), ("Ricardo Ramirez", "PE"),
        ("Daniela Silva", "ES"), ("Santiago Vargas", "MX"),
    ], start=1)
]

PRODUCTS = [
    {"id": "prod-0001", "name": "Laptop Pro 15", "price": 1299.99, "category": "Electronics"},
    {"id": "prod-0002", "name": "Mouse Wireless", "price": 29.99, "category": "Electronics"},
    {"id": "prod-0003", "name": "Teclado Mecanico RGB", "price": 89.99, "category": "Electronics"},
    {"id": "prod-0004", "name": "Webcam HD", "price": 49.99, "category": "Electronics"},
    {"id": "prod-0005", "name": "Auriculares BT Pro", "price": 159.99, "category": "Electronics"},
    {"id": "prod-0006", "name": "Smartphone Ultra", "price": 899.99, "category": "Electronics"},
    {"id": "prod-0007", "name": "Tablet Pro 12", "price": 599.99, "category": "Electronics"},
    {"id": "prod-0008", "name": "Camiseta Basica", "price": 19.99, "category": "Clothing"},
    {"id": "prod-0009", "name": "Jeans Slim", "price": 49.99, "category": "Clothing"},
    {"id": "prod-0010", "name": "Zapatillas Running", "price": 79.99, "category": "Clothing"},
    {"id": "prod-0011", "name": "Silla Ergonomica", "price": 349.99, "category": "Home"},
    {"id": "prod-0012", "name": "Escritorio Standing", "price": 449.99, "category": "Home"},
    {"id": "prod-0013", "name": "Cafetera Express", "price": 199.99, "category": "Home"},
]

SEARCH_QUERIES = ["laptop", "mouse", "teclado", "auriculares", "camiseta", "zapatillas",
                  "silla oficina", "cafetera", "smartphone", "tablet", "webcam"]

DEVICES = ["mobile", "desktop", "tablet"]

PAGES = {
    "home": "/",
    "categories": "/categories",
    "deals": "/deals",
    "account": "/account",
}

# Colores para la consola
COLORS = {
    "page_view": "\033[90m",       # gris
    "search": "\033[36m",          # cyan
    "product_view": "\033[34m",    # azul
    "add_to_cart": "\033[33m",     # amarillo
    "remove_from_cart": "\033[31m",# rojo
    "checkout_start": "\033[35m",  # magenta
    "purchase": "\033[32m",        # verde
    "abandon": "\033[31m",         # rojo
    "reset": "\033[0m",
}

# Contadores globales
stats = {
    "total": 0,
    "page_view": 0,
    "search": 0,
    "product_view": 0,
    "add_to_cart": 0,
    "remove_from_cart": 0,
    "checkout_start": 0,
    "purchase": 0,
}
stats_lock = threading.Lock()


# ============================================
# Publicar evento en Pub/Sub
# ============================================

def publish_event(event):
    """Publica un evento en Pub/Sub y lo muestra en consola."""
    message = json.dumps(event, ensure_ascii=False).encode("utf-8")
    publisher.publish(topic_path, message)

    color = COLORS.get(event["event_type"], "")
    reset = COLORS["reset"]

    # Mostrar en consola
    customer = event["customer_id"]
    etype = event["event_type"]
    detail = ""

    if etype == "search":
        detail = f' → "{event["search_query"]}"'
    elif etype == "product_view":
        prod = next((p for p in PRODUCTS if p["id"] == event["product_id"]), None)
        detail = f' → {prod["name"]} (${prod["price"]})' if prod else ""
    elif etype == "add_to_cart":
        prod = next((p for p in PRODUCTS if p["id"] == event["product_id"]), None)
        detail = f' → {prod["name"]}' if prod else ""
    elif etype == "purchase":
        detail = " 🎉"

    print(f"  {color}[{etype:20s}]{reset} {customer}{detail}")

    with stats_lock:
        stats["total"] += 1
        if etype in stats:
            stats[etype] += 1


# ============================================
# Simular sesión de un usuario
# ============================================

def simulate_user_session(customer, speed):
    """
    Simula una sesión completa de un usuario en la tienda.
    Cada sesión sigue un flujo realista de navegación.
    """
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    device = random.choice(DEVICES)
    delay = {"slow": 2.0, "normal": 0.8, "fast": 0.2}[speed]

    def make_event(event_type, product_id=None, search_query=None, page_url="/"):
        return {
            "event_id": f"rt-{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "customer_id": customer["id"],
            "session_id": session_id,
            "product_id": product_id,
            "search_query": search_query,
            "page_url": page_url,
            "device": device,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    cust_name = customer["name"]
    print(f"\n  {'='*60}")
    print(f"  👤 {cust_name} ({customer['id']}) entró a la tienda [{device}]")
    print(f"  {'='*60}")

    # 1. Entra a la tienda
    publish_event(make_event("page_view", page_url="/"))
    time.sleep(random.uniform(delay * 0.5, delay))

    # 2. Navega páginas aleatorias (1-3)
    for _ in range(random.randint(1, 3)):
        page = random.choice(list(PAGES.values()))
        publish_event(make_event("page_view", page_url=page))
        time.sleep(random.uniform(delay * 0.3, delay * 0.8))

    # 3. Busca algo (70% de probabilidad)
    if random.random() < 0.7:
        query = random.choice(SEARCH_QUERIES)
        publish_event(make_event("search", search_query=query, page_url=f"/search?q={query}"))
        time.sleep(random.uniform(delay * 0.5, delay))

    # 4. Ve productos (1-4)
    viewed_products = random.sample(PRODUCTS, min(random.randint(1, 4), len(PRODUCTS)))
    for product in viewed_products:
        publish_event(make_event("product_view", product_id=product["id"], page_url=f'/products/{product["id"]}'))
        time.sleep(random.uniform(delay * 0.3, delay * 0.8))

    # 5. Agrega al carrito (60% de probabilidad por producto visto)
    cart_products = []
    for product in viewed_products:
        if random.random() < 0.6:
            publish_event(make_event("add_to_cart", product_id=product["id"], page_url="/cart"))
            cart_products.append(product)
            time.sleep(random.uniform(delay * 0.2, delay * 0.5))

    if not cart_products:
        print(f"  {'─'*60}")
        print(f"  👤 {cust_name} se fue sin agregar nada al carrito")
        return

    # 6. Quita algo del carrito (20% de probabilidad)
    if cart_products and random.random() < 0.2:
        removed = random.choice(cart_products)
        publish_event(make_event("remove_from_cart", product_id=removed["id"], page_url="/cart"))
        cart_products.remove(removed)
        time.sleep(random.uniform(delay * 0.2, delay * 0.5))

    if not cart_products:
        print(f"  {'─'*60}")
        print(f"  👤 {cust_name} vació su carrito y se fue")
        return

    # 7. Checkout (70% de los que tienen carrito)
    if random.random() < 0.7:
        publish_event(make_event("checkout_start", page_url="/checkout"))
        time.sleep(random.uniform(delay * 0.5, delay))

        # 8. Compra (80% de los que empiezan checkout)
        if random.random() < 0.8:
            total = sum(p["price"] for p in cart_products)
            publish_event(make_event("purchase", page_url="/order-confirmation"))
            print(f"  {'─'*60}")
            print(f"  💰 {cust_name} compró {len(cart_products)} producto(s) por ${total:.2f}")
        else:
            print(f"  {'─'*60}")
            print(f"  ❌ {cust_name} abandonó el checkout")
    else:
        print(f"  {'─'*60}")
        print(f"  ❌ {cust_name} dejó {len(cart_products)} producto(s) en el carrito y se fue")


# ============================================
# Main
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Simulador de ClickEvents E-commerce")
    parser.add_argument("--users", type=int, default=5, help="Cantidad de usuarios a simular (default: 5)")
    parser.add_argument("--speed", choices=["slow", "normal", "fast"], default="normal",
                        help="Velocidad: slow (2s entre eventos), normal (0.8s), fast (0.2s)")
    parser.add_argument("--loop", action="store_true", help="Repetir indefinidamente (Ctrl+C para parar)")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║         Simulador de ClickEvents — E-commerce           ║
║                                                         ║
║  Usuarios: {args.users:<5}                                      ║
║  Velocidad: {args.speed:<10}                                 ║
║  Loop: {'Sí' if args.loop else 'No':<5}                                        ║
║                                                         ║
║  Cada evento se publica en Pub/Sub → Dataflow → Bronze  ║
║  Ctrl+C para parar                                      ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        round_num = 0
        while True:
            round_num += 1
            if args.loop:
                print(f"\n{'━'*60}")
                print(f"  Ronda {round_num}")
                print(f"{'━'*60}")

            # Seleccionar usuarios aleatorios
            selected_customers = random.sample(CUSTOMERS, min(args.users, len(CUSTOMERS)))

            for customer in selected_customers:
                simulate_user_session(customer, args.speed)
                time.sleep(random.uniform(0.5, 1.5))

            # Mostrar estadísticas
            print(f"\n{'━'*60}")
            print(f"  📊 Estadísticas (Ronda {round_num})")
            print(f"{'━'*60}")
            with stats_lock:
                print(f"  Total eventos:     {stats['total']}")
                print(f"  page_view:         {stats['page_view']}")
                print(f"  search:            {stats['search']}")
                print(f"  product_view:      {stats['product_view']}")
                print(f"  add_to_cart:       {stats['add_to_cart']}")
                print(f"  remove_from_cart:  {stats['remove_from_cart']}")
                print(f"  checkout_start:    {stats['checkout_start']}")
                print(f"  purchase:          {stats['purchase']}")

                if stats["product_view"] > 0:
                    cart_rate = stats["add_to_cart"] / stats["product_view"] * 100
                    print(f"\n  View → Cart rate:  {cart_rate:.1f}%")
                if stats["checkout_start"] > 0:
                    purchase_rate = stats["purchase"] / stats["checkout_start"] * 100
                    print(f"  Checkout → Buy:    {purchase_rate:.1f}%")

            if not args.loop:
                break

            print(f"\n  Siguiente ronda en 5 segundos...")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n\n{'━'*60}")
        print(f"  Simulación terminada")
        print(f"  Total eventos publicados: {stats['total']}")
        print(f"{'━'*60}")


if __name__ == "__main__":
    main()
