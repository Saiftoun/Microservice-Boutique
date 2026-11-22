# Mini Online Shop (gRPC microservices)

A small school project demonstrating a gRPC-based microservices shop.

## Architecture

- **ProductService** (implemented): manages the product catalog and stock.
- **OrderService** (planned, not implemented yet): will manage orders.
- **One database per service**: ProductService uses `products_db`; OrderService
  will use `orders_db` (created now for later). Services never share tables.
- Prices are stored as **integer cents** (`BIGINT`), never floats.

```
shop/
├── protos/product.proto        # API contract
├── product_service/
│   ├── server.py               # gRPC server + ProductService
│   ├── db.py                   # psycopg2 connection helpers + schema/seed
│   └── requirements.txt
├── db-init/init.sql            # creates products_db and orders_db
├── docker-compose.yml          # PostgreSQL 16
└── README.md
```

## Configuration

All settings come from environment variables with sensible defaults:

| Variable      | Default        |
|---------------|----------------|
| `DB_HOST`     | `localhost`    |
| `DB_PORT`     | `5432`         |
| `DB_NAME`     | `products_db`  |
| `DB_USER`     | `shop`         |
| `DB_PASSWORD` | `shop123`      |
| `PORT`        | `50051`        |

## Start the database

```bash
docker compose up -d db
docker compose ps
```

The first start runs `db-init/init.sql`, creating `products_db` and `orders_db`.

> Note: use a **64-bit** Python 3.10+. Recent `psycopg2-binary` releases do not
> ship 32-bit Windows wheels, so installation fails on a 32-bit interpreter.

## Generate the proto code

From the `shop/` directory:

```bash
python -m grpc_tools.protoc -I protos --python_out=product_service --grpc_python_out=product_service protos/product.proto
```

## Run the service

```bash
cd product_service
python server.py
```

`init_db()` creates the `products` table and seeds 6 sample products (including
an out-of-stock Webcam) on first run.

## Test with grpcurl

Server reflection is enabled, so no `.proto` file is needed.

```bash
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 shop.product.ProductService/ListProducts
grpcurl -plaintext -d '{"id": 1}' localhost:50051 shop.product.ProductService/GetProduct
grpcurl -plaintext -d '{"id": 999}' localhost:50051 shop.product.ProductService/GetProduct
grpcurl -plaintext -d '{"id": 1, "quantity": 2}' localhost:50051 shop.product.ProductService/ReduceStock
grpcurl -plaintext -d '{"id": 6, "quantity": 1}' localhost:50051 shop.product.ProductService/ReduceStock
```

Expected results:

- `list` shows `shop.product.ProductService`.
- `ListProducts` returns the 6 seeded products.
- `GetProduct` for id 999 returns `NotFound`.
- `ReduceStock` on the Webcam (id 6) returns `FailedPrecondition` (not enough stock).
- `ReduceStock` on the Laptop (id 1) by 2 returns the product with `stock: 8`.
