import logging
import os
from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection
from psycopg2.extras import RealDictCursor

import db
import product_pb2
import product_pb2_grpc

logger = logging.getLogger(__name__)


def _to_product(row):
    return product_pb2.Product(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price_cents=row["price_cents"],
        stock=row["stock"],
    )


class ProductService(product_pb2_grpc.ProductServiceServicer):
    def CreateProduct(self, request, context):
        name = request.name.strip()
        if not name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name must not be empty")
        if request.price_cents <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "price_cents must be positive")
        if request.stock < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "stock must not be negative")

        with db.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO products (name, description, price_cents, stock) "
                    "VALUES (%s, %s, %s, %s) "
                    "RETURNING id, name, description, price_cents, stock",
                    (name, request.description, request.price_cents, request.stock),
                )
                row = cur.fetchone()
        return _to_product(row)

    def GetProduct(self, request, context):
        with db.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, description, price_cents, stock "
                    "FROM products WHERE id = %s",
                    (request.id,),
                )
                row = cur.fetchone()
        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"product {request.id} not found")
        return _to_product(row)

    def ListProducts(self, request, context):
        with db.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, description, price_cents, stock "
                    "FROM products ORDER BY id"
                )
                rows = cur.fetchall()
        return product_pb2.ListProductsResponse(
            products=[_to_product(row) for row in rows]
        )

    def ReduceStock(self, request, context):
        if request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "quantity must be positive")

        with db.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE products SET stock = stock - %s "
                    "WHERE id = %s AND stock >= %s "
                    "RETURNING id, name, description, price_cents, stock",
                    (request.quantity, request.id, request.quantity),
                )
                row = cur.fetchone()

                if row is None:
                    cur.execute("SELECT 1 FROM products WHERE id = %s", (request.id,))
                    if cur.fetchone() is None:
                        context.abort(
                            grpc.StatusCode.NOT_FOUND,
                            f"product {request.id} not found",
                        )
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION, "not enough stock"
                    )
        return _to_product(row)


def serve():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_db()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductServiceServicer_to_server(
        ProductService(), server
    )

    service_names = (
        product_pb2.DESCRIPTOR.services_by_name["ProductService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    port = os.getenv("PORT", "50051")
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info("ProductService listening on port %s", port)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
