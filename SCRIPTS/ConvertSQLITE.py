import sqlite3

schema = """
-- Strong entity
CREATE TABLE Customer (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- Weak entity (depends on Customer)
CREATE TABLE Customer_Address_History (
    history_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    address TEXT,
    start_date DATE,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id)
);

-- Another strong entity
CREATE TABLE Product (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- Another strong entity
CREATE TABLE "Order" (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id)
);

-- Associative entity (many-to-many)
CREATE TABLE Order_Product (
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id) REFERENCES "Order"(order_id),
    FOREIGN KEY (product_id) REFERENCES Product(product_id)
);

"""

conn = sqlite3.connect("../test_schema.sqlite")
cursor = conn.cursor()
cursor.executescript(schema)
conn.commit()
conn.close()

print("SQLite database created: test_schema.sqlite")
