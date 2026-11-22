import logging
import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

SEED_PRODUCTS = [
    ("Laptop", "A powerful laptop for everyday work", 99900, 10),
    ("Headphones", "Wireless over-ear headphones", 12900, 25),
    ("Keyboard", "Mechanical keyboard", 7900, 40),
    ("Mouse", "Ergonomic wireless mouse", 3900, 50),
    ("Monitor", "27-inch 4K monitor", 34900, 8),
    ("Webcam", "1080p HD webcam", 5900, 0),
]


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "products_db"),
        user=os.getenv("DB_USER", "shop"),
        password=os.getenv("DB_PASSWORD", "shop123"),
    )


@contextmanager
def connection():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    last_error = None
    for attempt in range(1, 11):
        try:
            with connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS products (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL,
                            description TEXT NOT NULL DEFAULT '',
                            price_cents BIGINT NOT NULL CHECK (price_cents > 0),
                            stock INTEGER NOT NULL CHECK (stock >= 0)
                        )
                        """
                    )
                    cur.execute("SELECT COUNT(*) FROM products")
                    count = cur.fetchone()[0]
                    if count == 0:
                        cur.executemany(
                            "INSERT INTO products (name, description, price_cents, stock) "
                            "VALUES (%s, %s, %s, %s)",
                            SEED_PRODUCTS,
                        )
                        logger.info("Seeded %d products", len(SEED_PRODUCTS))
            logger.info("Database initialized")
            return
        except psycopg2.Error as exc:
            last_error = exc
            logger.warning(
                "Database not ready (attempt %d/10): %s", attempt, exc
            )
            time.sleep(2)
    raise RuntimeError(f"Could not initialize database: {last_error}")
