"""
Genera CSVs de prueba para E-commerce y los guarda en pub-sub/sample-data/
Ejecutar: python generate.py
Después subir: gsutil cp *.csv gs://project-dev-490218-ecommerce-raw-data/{carpeta}/
"""

import csv
import random
import uuid
from datetime import datetime, timedelta

OUTPUT_DIR = "."

# ============================================
# Configuración
# ============================================
NUM_CUSTOMERS = 50
NUM_PRODUCTS = 20
NUM_ORDERS = 100
NUM_EVENTS = 500
NUM_REVIEWS = 30

COUNTRIES = ["MX", "CO", "AR", "CL", "PE", "ES"]
CITIES = {
    "MX": ["CDMX", "Monterrey", "Guadalajara", "Puebla"],
    "CO": ["Bogota", "Medellin", "Cali", "Barranquilla"],
    "AR": ["Buenos Aires", "Cordoba", "Rosario"],
    "CL": ["Santiago", "Valparaiso", "Concepcion"],
    "PE": ["Lima", "Arequipa", "Cusco"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Sevilla"],
}
FIRST_NAMES = ["Maria", "Juan", "Ana", "Carlos", "Laura", "Pedro", "Sofia", "Diego", "Valentina", "Miguel",
               "Camila", "Andres", "Isabella", "Luis", "Fernanda", "Jorge", "Paula", "Ricardo", "Daniela", "Santiago"]
LAST_NAMES = ["Garcia", "Lopez", "Martinez", "Rodriguez", "Hernandez", "Gonzalez", "Perez", "Sanchez",
              "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz", "Cruz", "Morales", "Reyes", "Ortiz"]
DEVICES = ["mobile", "desktop", "tablet"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "bank_transfer", "crypto"]
ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "completed", "cancelled"]
EVENT_TYPES = ["page_view", "product_view", "search", "add_to_cart", "remove_from_cart", "checkout_start", "purchase"]

CATEGORIES = {
    "Electronics": ["Laptops", "Phones", "Accessories", "Tablets", "Audio"],
    "Clothing": ["Men", "Women", "Kids", "Shoes", "Accessories"],
    "Home": ["Furniture", "Kitchen", "Decor", "Garden"],
}

PRODUCT_NAMES = {
    "Laptops": ["Laptop Pro 15", "Laptop Air 13", "Laptop Gaming X", "Chromebook Lite"],
    "Phones": ["Smartphone Ultra", "Phone Lite SE", "Phone Pro Max"],
    "Accessories": ["Mouse Wireless", "Teclado Mecanico RGB", "Webcam HD", "USB-C Hub"],
    "Tablets": ["Tablet Pro 12", "Tablet Mini 8"],
    "Audio": ["Auriculares BT Pro", "Speaker Portatil", "Microfono USB"],
    "Men": ["Camiseta Basica", "Jeans Slim", "Chaqueta Casual"],
    "Women": ["Blusa Elegante", "Falda Midi", "Vestido Verano"],
    "Kids": ["Camiseta Divertida", "Pantalon Comodo"],
    "Shoes": ["Zapatillas Running", "Botas Urban", "Sandalias Verano"],
    "Furniture": ["Escritorio Standing", "Silla Ergonomica"],
    "Kitchen": ["Cafetera Express", "Licuadora Pro", "Set Cuchillos"],
    "Decor": ["Lampara LED", "Cuadro Moderno"],
    "Garden": ["Set Herramientas", "Maceta Grande"],
}

START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 3, 15)


def random_date(start=START_DATE, end=END_DATE):
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return (start + timedelta(days=random_days, seconds=random_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def random_email(first, last):
    domains = ["example.com", "test.com", "mail.com", "correo.com"]
    return f"{first.lower()}.{last.lower()}{random.randint(1,99)}@{random.choice(domains)}"


# ============================================
# Generar Customers
# ============================================
def generate_customers():
    rows = []
    for i in range(NUM_CUSTOMERS):
        country = random.choice(COUNTRIES)
        city = random.choice(CITIES[country])
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        created = random_date()
        rows.append({
            "id": f"cust-{i+1:04d}",
            "email": random_email(first, last),
            "first_name": first,
            "last_name": last,
            "phone": f"+{random.randint(1000000000, 9999999999)}",
            "country": country,
            "city": city,
            "address": f"Calle {random.randint(1,200)} #{random.randint(1,50)}",
            "created_at": created,
            "updated_at": created,
        })

    with open(f"{OUTPUT_DIR}/customers.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} customers")
    return [r["id"] for r in rows]


# ============================================
# Generar Products
# ============================================
def generate_products():
    rows = []
    i = 0
    for category, subcategories in CATEGORIES.items():
        for subcategory in subcategories:
            names = PRODUCT_NAMES.get(subcategory, [f"Producto {subcategory}"])
            for name in names:
                if i >= NUM_PRODUCTS:
                    break
                i += 1
                rows.append({
                    "id": f"prod-{i:04d}",
                    "name": name,
                    "description": f"{name} - producto de alta calidad",
                    "category": category,
                    "subcategory": subcategory,
                    "price": round(random.uniform(9.99, 1499.99), 2),
                    "currency": "USD",
                    "sku": f"{category[:3].upper()}-{subcategory[:3].upper()}-{i:03d}",
                    "is_active": random.choice(["true", "true", "true", "false"]),
                    "created_at": random_date(START_DATE, START_DATE + timedelta(days=30)),
                })
        if i >= NUM_PRODUCTS:
            break

    with open(f"{OUTPUT_DIR}/products.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} products")
    return [r["id"] for r in rows], {r["id"]: r["price"] for r in rows}


# ============================================
# Generar Orders + Order Items
# ============================================
def generate_orders(customer_ids, product_ids, product_prices):
    orders = []
    order_items = []

    for i in range(NUM_ORDERS):
        order_id = f"ord-{i+1:04d}"
        customer_id = random.choice(customer_ids)
        status = random.choices(ORDER_STATUSES, weights=[5, 5, 10, 40, 30, 10])[0]
        ordered_at = random_date()

        # Generar items del pedido
        num_items = random.randint(1, 4)
        selected_products = random.sample(product_ids, min(num_items, len(product_ids)))
        total = 0

        for j, prod_id in enumerate(selected_products):
            qty = random.randint(1, 3)
            unit_price = float(product_prices[prod_id])
            discount = round(random.choice([0, 0, 0, 0.1, 0.15, 0.2]) * unit_price * qty, 2)
            item_total = round(unit_price * qty - discount, 2)
            total += item_total

            order_items.append({
                "order_item_id": f"oi-{i+1:04d}-{j+1}",
                "order_id": order_id,
                "product_id": prod_id,
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": item_total,
                "discount": discount,
            })

        country = random.choice(COUNTRIES)
        city = random.choice(CITIES[country])

        shipped_at = ""
        delivered_at = ""
        if status in ["shipped", "delivered", "completed"]:
            shipped_at = (datetime.strptime(ordered_at, "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=random.randint(1, 3))).strftime("%Y-%m-%dT%H:%M:%SZ")
        if status in ["delivered", "completed"]:
            delivered_at = (datetime.strptime(shipped_at, "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%dT%H:%M:%SZ")

        orders.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "status": status,
            "total_amount": round(total, 2),
            "currency": "USD",
            "shipping_address": f"Calle {random.randint(1,200)} #{random.randint(1,50)}",
            "shipping_city": city,
            "shipping_country": country,
            "ordered_at": ordered_at,
            "shipped_at": shipped_at,
            "delivered_at": delivered_at,
        })

    with open(f"{OUTPUT_DIR}/orders.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=orders[0].keys())
        writer.writeheader()
        writer.writerows(orders)

    with open(f"{OUTPUT_DIR}/order_items.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=order_items[0].keys())
        writer.writeheader()
        writer.writerows(order_items)

    print(f"Generated {len(orders)} orders, {len(order_items)} order items")
    return [o["order_id"] for o in orders]


# ============================================
# Generar Payments
# ============================================
def generate_payments(order_ids, customer_ids):
    rows = []
    for i, order_id in enumerate(order_ids):
        if random.random() < 0.9:  # 90% tienen pago
            status = random.choices(["completed", "completed", "completed", "failed", "refunded"], weights=[70, 10, 5, 10, 5])[0]
            rows.append({
                "payment_id": f"pay-{i+1:04d}",
                "order_id": order_id,
                "customer_id": random.choice(customer_ids),
                "amount": round(random.uniform(10, 2000), 2),
                "currency": "USD",
                "payment_method": random.choice(PAYMENT_METHODS),
                "status": status,
                "paid_at": random_date(),
            })

    with open(f"{OUTPUT_DIR}/payments.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} payments")


# ============================================
# Generar Events (clickstream)
# ============================================
def generate_events(customer_ids, product_ids):
    rows = []
    for i in range(NUM_EVENTS):
        event_type = random.choices(EVENT_TYPES, weights=[30, 25, 10, 15, 5, 8, 7])[0]
        customer_id = random.choice(customer_ids)
        session_id = f"sess-{random.randint(1, NUM_CUSTOMERS * 3):04d}"

        product_id = ""
        search_query = ""
        page_url = "/"

        if event_type == "page_view":
            page_url = random.choice(["/", "/products", "/categories", "/about", "/contact"])
        elif event_type == "product_view":
            product_id = random.choice(product_ids)
            page_url = f"/products/{product_id}"
        elif event_type == "search":
            search_query = random.choice(["laptop", "mouse", "teclado", "auriculares", "camiseta", "zapatillas", "silla", "cafetera"])
            page_url = f"/search?q={search_query}"
        elif event_type == "add_to_cart":
            product_id = random.choice(product_ids)
            page_url = "/cart"
        elif event_type == "remove_from_cart":
            product_id = random.choice(product_ids)
            page_url = "/cart"
        elif event_type == "checkout_start":
            page_url = "/checkout"
        elif event_type == "purchase":
            page_url = "/order-confirmation"

        rows.append({
            "event_id": f"ev-{i+1:06d}",
            "event_type": event_type,
            "customer_id": customer_id,
            "session_id": session_id,
            "product_id": product_id,
            "search_query": search_query,
            "page_url": page_url,
            "device": random.choice(DEVICES),
            "timestamp": random_date(),
        })

    with open(f"{OUTPUT_DIR}/events.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} events")


# ============================================
# Generar Inventory
# ============================================
def generate_inventory(product_ids):
    rows = []
    warehouses = ["warehouse-eu-west", "warehouse-eu-east", "warehouse-latam"]

    for prod_id in product_ids:
        for wh in random.sample(warehouses, random.randint(1, 3)):
            rows.append({
                "product_id": prod_id,
                "warehouse": wh,
                "quantity_available": random.randint(0, 500),
                "quantity_reserved": random.randint(0, 50),
                "last_updated": random_date(),
            })

    with open(f"{OUTPUT_DIR}/inventory.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} inventory records")


# ============================================
# Generar Reviews
# ============================================
def generate_reviews(customer_ids, product_ids):
    titles_good = ["Excelente producto", "Muy bueno", "Lo recomiendo", "Superó mis expectativas", "Genial"]
    titles_bad = ["No me gustó", "Mala calidad", "No lo recomiendo", "Decepcionante"]
    comments_good = ["Llegó rápido y en buen estado.", "La calidad es increíble.", "Muy satisfecho con la compra.", "Justo lo que necesitaba."]
    comments_bad = ["No cumplió con lo esperado.", "Se dañó al poco tiempo.", "No vale el precio.", "Tuve problemas con el envío."]

    rows = []
    for i in range(NUM_REVIEWS):
        rating = random.choices([1, 2, 3, 4, 5], weights=[5, 5, 10, 30, 50])[0]
        if rating >= 4:
            title = random.choice(titles_good)
            comment = random.choice(comments_good)
        else:
            title = random.choice(titles_bad)
            comment = random.choice(comments_bad)

        rows.append({
            "review_id": f"rev-{i+1:04d}",
            "product_id": random.choice(product_ids),
            "customer_id": random.choice(customer_ids),
            "rating": rating,
            "title": title,
            "comment": comment,
            "created_at": random_date(),
        })

    with open(f"{OUTPUT_DIR}/reviews.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} reviews")


# ============================================
# Main
# ============================================
if __name__ == "__main__":
    print("Generando datos de prueba E-commerce...\n")

    customer_ids = generate_customers()
    product_ids, product_prices = generate_products()
    order_ids = generate_orders(customer_ids, product_ids, product_prices)
    generate_payments(order_ids, customer_ids)
    generate_events(customer_ids, product_ids)
    generate_inventory(product_ids)
    generate_reviews(customer_ids, product_ids)

    print(f"\nCSVs generados en {OUTPUT_DIR}/")
    print("\nPara subir a Cloud Storage:")
    print('gsutil cp customers.csv "gs://project-dev-490218-ecommerce-raw-data/customers/"')
    print('gsutil cp products.csv "gs://project-dev-490218-ecommerce-raw-data/products/"')
    print('gsutil cp orders.csv "gs://project-dev-490218-ecommerce-raw-data/orders/"')
    print('gsutil cp order_items.csv "gs://project-dev-490218-ecommerce-raw-data/order_items/"')
    print('gsutil cp payments.csv "gs://project-dev-490218-ecommerce-raw-data/payments/"')
    print('gsutil cp events.csv "gs://project-dev-490218-ecommerce-raw-data/events/"')
    print('gsutil cp inventory.csv "gs://project-dev-490218-ecommerce-raw-data/inventory/"')
    print('gsutil cp reviews.csv "gs://project-dev-490218-ecommerce-raw-data/reviews/"')
