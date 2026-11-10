"""Migration script to add subcategories, finance tracking, customer name split, and audit logging."""
import sqlite3
import os

db_path = "database/app.db"

if not os.path.exists(db_path):
    print("Database not found. Skipping migration.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Migrate product_sets to subcategories
# Check if subcategories table already exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subcategories'")
if cursor.fetchone():
    print("Subcategories table already exists. Skipping.")
else:
    # Check if product_sets table exists and migrate its data
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product_sets'")
    if cursor.fetchone():
        # Create subcategories table
        cursor.execute("""
            CREATE TABLE subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                category_id INTEGER REFERENCES categories(id)
            )
        """)
        # Migrate data from product_sets to subcategories
        cursor.execute("INSERT INTO subcategories (id, name, category_id) SELECT id, name, category_id FROM product_sets")
        print("Migrated product_sets data to subcategories table.")
    else:
        # Create subcategories table from scratch
        cursor.execute("""
            CREATE TABLE subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                category_id INTEGER REFERENCES categories(id)
            )
        """)
        print("Created subcategories table.")

# Check if subcategory_id column already exists in products
cursor.execute("PRAGMA table_info(products)")
product_columns = [row[1] for row in cursor.fetchall()]
if "subcategory_id" in product_columns:
    print("subcategory_id column already exists. Skipping.")
else:
    # Check if product_set_id exists and migrate
    if "product_set_id" in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN subcategory_id INTEGER REFERENCES subcategories(id)")
        cursor.execute("UPDATE products SET subcategory_id = product_set_id")
        print("Migrated product_set_id to subcategory_id column in products table.")
    else:
        cursor.execute("ALTER TABLE products ADD COLUMN subcategory_id INTEGER REFERENCES subcategories(id)")
        print("Added subcategory_id column to products table.")

# --- Finance Tracking ---

# Check if deposit column already exists in orders
cursor.execute("PRAGMA table_info(orders)")
order_columns = [row[1] for row in cursor.fetchall()]
if "deposit" in order_columns:
    print("deposit column in orders already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE orders ADD COLUMN deposit FLOAT NOT NULL DEFAULT 0.0")
    print("Added deposit column to orders table.")

if "staff_name" in order_columns:
    print("staff_name column in orders already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE orders ADD COLUMN staff_name VARCHAR")
    print("Added staff_name column to orders table.")

# --- Customer Name Split ---

# Check if first_name/last_name columns exist in customers
cursor.execute("PRAGMA table_info(customers)")
cust_columns = [row[1] for row in cursor.fetchall()]
# Check if name column still exists and needs to be removed
if "name" in cust_columns:
    # Recreate table without name column
    cursor.execute("PRAGMA table_info(customers)")
    columns_info = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    new_columns = [col for col in columns_info if col[1] != "name"]
    col_defs = []
    for col in new_columns:
        col_defs.append(f"{col[1]} {col[2]}")
    create_sql = f"CREATE TABLE customers_new ({', '.join(col_defs)})"
    cursor.execute(create_sql)
    
    insert_cols = [col[1] for col in new_columns]
    cursor.execute(f"INSERT INTO customers_new ({', '.join(insert_cols)}) SELECT {', '.join(['customers.' + c for c in insert_cols])} FROM customers")
    
    cursor.execute("DROP TABLE customers")
    cursor.execute("ALTER TABLE customers_new RENAME TO customers")
    print("Removed old name column from customers table.")
elif "first_name" in cust_columns:
    print("first_name/last_name columns in customers already exist. Skipping.")
else:
    # Add new columns
    cursor.execute("ALTER TABLE customers ADD COLUMN first_name VARCHAR")
    cursor.execute("ALTER TABLE customers ADD COLUMN last_name VARCHAR")
    # Migrate existing name data: split into first and last name
    # Get all customers with existing names
    cursor.execute("SELECT id, name FROM customers WHERE name IS NOT NULL AND name != ''")
    rows = cursor.fetchall()
    for row_id, name in rows:
        parts = name.split(' ', 1)
        first = parts[0] if parts else name
        last = parts[1] if len(parts) > 1 else ''
        cursor.execute("UPDATE customers SET first_name = ?, last_name = ? WHERE id = ?", (first, last, row_id))
    # Make the old name column nullable so it won't block new inserts
    # SQLite doesn't support DROP COLUMN in older versions, so we recreate the table
    # Get all existing data
    cursor.execute("PRAGMA table_info(customers)")
    columns_info = cursor.fetchall()
    cursor.execute("SELECT * FROM customers")
    all_rows = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    # Check if name column exists and needs to be removed
    if "name" in column_names:
        # Create new table without name column
        new_columns = [col for col in columns_info if col[1] != "name"]
        col_defs = []
        for col in new_columns:
            col_defs.append(f"{col[1]} {col[2]}")
        create_sql = f"CREATE TABLE customers_new ({', '.join(col_defs)})"
        cursor.execute(create_sql)
        
        # Copy data without name column
        insert_cols = [col[1] for col in new_columns]
        insert_indices = [column_names.index(col) for col in insert_cols]
        placeholders = ', '.join(['?' for _ in insert_cols])
        cursor.execute(f"INSERT INTO customers_new ({', '.join(insert_cols)}) SELECT {', '.join(['customers.' + c for c in insert_cols])} FROM customers")
        
        # Replace old table
        cursor.execute("DROP TABLE customers")
        cursor.execute("ALTER TABLE customers_new RENAME TO customers")
        print("Added first_name/last_name columns to customers table. Existing names split into first/last, old name column removed.")
    else:
        print("Added first_name/last_name columns to customers table. Existing names split into first/last.")

# --- Payments Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
if cursor.fetchone():
    print("Payments table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            amount FLOAT NOT NULL,
            payment_type VARCHAR NOT NULL DEFAULT 'cash',
            staff_name VARCHAR,
            timestamp DATETIME NOT NULL
        )
    """)
    print("Created payments table.")

# --- Order Logs Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_logs'")
if cursor.fetchone():
    print("Order logs table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            action TEXT NOT NULL,
            staff_name VARCHAR,
            timestamp DATETIME NOT NULL
        )
    """)
    print("Created order_logs table.")

# --- Picked Up Status ---

if "picked_up" in order_columns:
    print("picked_up column in orders already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE orders ADD COLUMN picked_up BOOLEAN NOT NULL DEFAULT 0")
    print("Added picked_up column to orders table.")

# --- Per-Item Pickup Tracking ---

cursor.execute("PRAGMA table_info(order_items)")
order_item_columns = [row[1] for row in cursor.fetchall()]
if "picked_up_quantity" in order_item_columns:
    print("picked_up_quantity column in order_items already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE order_items ADD COLUMN picked_up_quantity INTEGER NOT NULL DEFAULT 0")
    print("Added picked_up_quantity column to order_items table.")

# --- Release Date for Products ---

cursor.execute("PRAGMA table_info(products)")
product_columns = [row[1] for row in cursor.fetchall()]
if "release_date" in product_columns:
    print("release_date column in products already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE products ADD COLUMN release_date DATE")
    print("Added release_date column to products table.")

# --- Soft Delete for Orders ---

if "deleted" in order_columns:
    print("deleted column in orders already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE orders ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT 0")
    print("Added deleted column to orders table.")

# --- Store Settings Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='store_settings'")
if cursor.fetchone():
    print("Store settings table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE store_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name VARCHAR,
            address VARCHAR,
            contact_number VARCHAR,
            email VARCHAR,
            website VARCHAR,
            abn VARCHAR,
            logo_path VARCHAR,
            primary_color VARCHAR DEFAULT '#3b82f6',
            secondary_color VARCHAR DEFAULT '#6b7280',
            background_color VARCHAR DEFAULT '#f9fafb',
            text_color VARCHAR DEFAULT '#111827',
            nav_bg_color VARCHAR DEFAULT '#1e293b',
            nav_text_color VARCHAR DEFAULT '#f8fafc',
            card_bg_color VARCHAR DEFAULT '#ffffff',
            border_color VARCHAR DEFAULT '#e5e7eb'
        )
    """)
    print("Created store_settings table.")

# --- General Audit Logs Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
if cursor.fetchone():
    print("Audit logs table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            staff_name VARCHAR,
            timestamp DATETIME NOT NULL
        )
    """)
    print("Created audit_logs table.")

# --- Backup Settings Columns ---

cursor.execute("PRAGMA table_info(store_settings)")
settings_columns = [row[1] for row in cursor.fetchall()]

backup_columns = {
    "backup_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    "backup_storage": "VARCHAR DEFAULT 'local'",
    "backup_schedule": "VARCHAR DEFAULT 'daily'",
    "backup_time": "VARCHAR DEFAULT '02:00'",
    "backup_weekday": "VARCHAR DEFAULT 'monday'",
    "backup_google_folder_id": "VARCHAR",
    "backup_google_token_path": "VARCHAR",
    "backup_last_run": "DATETIME",
    "backup_last_status": "VARCHAR",
    "backup_last_message": "VARCHAR",
    "gmail_sender_email": "VARCHAR",
    "abn": "VARCHAR",
    "app_port": "INTEGER DEFAULT 8000",
}

for col_name, col_type in backup_columns.items():
    if col_name in settings_columns:
        print(f"{col_name} column in store_settings already exists. Skipping.")
    else:
        cursor.execute(f"ALTER TABLE store_settings ADD COLUMN {col_name} {col_type}")
        print(f"Added {col_name} column to store_settings table.")

# --- Customer Credits Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_credits'")
if cursor.fetchone():
    print("Customer credits table already exists. Checking for notes column...")
    cursor.execute("PRAGMA table_info(customer_credits)")
    credit_columns = [row[1] for row in cursor.fetchall()]
    if "notes" in credit_columns:
        print("notes column in customer_credits already exists. Skipping.")
    else:
        cursor.execute("ALTER TABLE customer_credits ADD COLUMN notes VARCHAR")
        print("Added notes column to customer_credits table.")
else:
    cursor.execute("""
        CREATE TABLE customer_credits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            amount FLOAT NOT NULL,
            credit_type VARCHAR NOT NULL,
            staff_name VARCHAR,
            notes VARCHAR,
            timestamp DATETIME NOT NULL
        )
    """)
    print("Created customer_credits table.")

# --- Order Notes Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_notes'")
if cursor.fetchone():
    print("Order notes table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE order_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            text TEXT NOT NULL,
            staff_name VARCHAR,
            created_at DATETIME NOT NULL
        )
    """)
    print("Created order_notes table.")

# --- Cost Price and Max Per Order for Products ---

cursor.execute("PRAGMA table_info(products)")
product_columns = [row[1] for row in cursor.fetchall()]
if "cost_price" in product_columns:
    print("cost_price column in products already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE products ADD COLUMN cost_price FLOAT NOT NULL DEFAULT 0.0")
    print("Added cost_price column to products table.")

if "max_per_order" in product_columns:
    print("max_per_order column in products already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE products ADD COLUMN max_per_order INTEGER")
    print("Added max_per_order column to products table.")

if "image_url" in product_columns:
    print("image_url column in products already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE products ADD COLUMN image_url VARCHAR")
    print("Added image_url column to products table.")

# --- Logo Size for Store Settings ---

cursor.execute("PRAGMA table_info(store_settings)")
settings_columns = [row[1] for row in cursor.fetchall()]
if "logo_size" in settings_columns:
    print("logo_size column in store_settings already exists. Skipping.")
else:
    cursor.execute("ALTER TABLE store_settings ADD COLUMN logo_size INTEGER DEFAULT 40")
    print("Added logo_size column to store_settings table.")

# --- Distributors Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='distributors'")
if cursor.fetchone():
    print("Distributors table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE distributors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            store_rep VARCHAR,
            store_rep_phone VARCHAR,
            store_rep_email VARCHAR,
            phone VARCHAR,
            email VARCHAR,
            website VARCHAR
        )
    """)
    print("Created distributors table.")

# --- Distributor Products Association Table ---

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='distributor_products'")
if cursor.fetchone():
    print("Distributor products table already exists. Skipping.")
else:
    cursor.execute("""
        CREATE TABLE distributor_products (
            product_id INTEGER NOT NULL REFERENCES products(id),
            distributor_id INTEGER NOT NULL REFERENCES distributors(id),
            PRIMARY KEY (product_id, distributor_id)
        )
    """)
    print("Created distributor_products table.")

conn.commit()
conn.close()
print("Migration complete!")
