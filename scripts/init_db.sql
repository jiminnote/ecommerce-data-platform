-- =====================================================
-- E-commerce Source Database Schema
-- Simulates a production database for CDC pipeline
-- =====================================================

-- Enable logical replication for Debezium CDC
ALTER SYSTEM SET wal_level = 'logical';

-- ─── Users ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    nickname        VARCHAR(100),
    phone           VARCHAR(20),
    grade           VARCHAR(20) DEFAULT 'NORMAL'
                    CHECK (grade IN ('NORMAL', 'SILVER', 'GOLD', 'VIP', 'VVIP')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

-- ─── Products ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    product_id      BIGSERIAL PRIMARY KEY,
    name            VARCHAR(500) NOT NULL,
    category_l1     VARCHAR(100),
    category_l2     VARCHAR(100),
    category_l3     VARCHAR(100),
    price           NUMERIC(12, 2) NOT NULL,
    discount_rate   NUMERIC(5, 2) DEFAULT 0,
    stock_quantity  INTEGER DEFAULT 0,
    is_kurly_only   BOOLEAN DEFAULT FALSE,
    storage_type    VARCHAR(20) DEFAULT 'AMBIENT'
                    CHECK (storage_type IN ('FROZEN', 'CHILLED', 'AMBIENT')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Orders ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id        BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(user_id),
    order_status    VARCHAR(20) DEFAULT 'PENDING'
                    CHECK (order_status IN (
                        'PENDING', 'PAID', 'PREPARING', 'SHIPPING',
                        'DELIVERED', 'CANCELLED', 'REFUNDED'
                    )),
    total_amount    NUMERIC(12, 2) NOT NULL,
    delivery_fee    NUMERIC(8, 2) DEFAULT 0,
    payment_method  VARCHAR(30),
    delivery_type   VARCHAR(20) DEFAULT 'DAWN'
                    CHECK (delivery_type IN ('DAWN', 'SAME_DAY', 'NEXT_DAY')),
    ordered_at      TIMESTAMPTZ DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Order Items ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    item_id         BIGSERIAL PRIMARY KEY,
    order_id        BIGINT REFERENCES orders(order_id),
    product_id      BIGINT REFERENCES products(product_id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12, 2) NOT NULL,
    subtotal        NUMERIC(12, 2) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Indexes ─────────────────────────────────────────
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category_l1, category_l2);

-- ─── Publication for Debezium CDC ────────────────────
CREATE PUBLICATION cdc_publication FOR TABLE users, products, orders, order_items;

-- ─── Sample Data ─────────────────────────────────────
INSERT INTO users (email, nickname, phone, grade) VALUES
    ('user1@example.com', '마켓러버', '010-1234-5678', 'VIP'),
    ('user2@example.com', '신선지킴이', '010-2345-6789', 'GOLD'),
    ('user3@example.com', '새벽배송팬', '010-3456-7890', 'NORMAL');

INSERT INTO products (name, category_l1, category_l2, price, storage_type, stock_quantity) VALUES
    ('유기농 바나나 1kg', '과일', '열대과일', 4900, 'AMBIENT', 500),
    ('제주 감귤 3kg', '과일', '국내과일', 15900, 'CHILLED', 200),
    ('한우 등심 300g', '정육', '소고기', 29900, 'CHILLED', 100),
    ('프리미엄 아이스크림', '간식', '아이스크림', 8900, 'FROZEN', 300);
