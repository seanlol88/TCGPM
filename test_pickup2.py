import requests
import sqlite3

base = "http://localhost:8000"
s = requests.Session()

# Check actual database state
print("=== Database picked_up states ===")
conn = sqlite3.connect("database/app.db")
cursor = conn.cursor()
cursor.execute("SELECT id, picked_up FROM orders ORDER BY id")
for row in cursor.fetchall():
    print(f"Order {row[0]}: picked_up={bool(row[1])}")
conn.close()

# Reset all orders to not picked up
print("\n=== Resetting all orders ===")
for oid in [1, 2, 3, 4, 5]:
    r = s.get(f"{base}/orders", timeout=5)
    # Check current state
    conn = sqlite3.connect("database/app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT picked_up FROM orders WHERE id=?", (oid,))
    current = cursor.fetchone()[0]
    conn.close()
    if current:
        s.post(f"{base}/orders/{oid}/toggle-pickup", timeout=5)
        print(f"Order {oid}: was picked up, now toggled off")

# Verify all are False
conn = sqlite3.connect("database/app.db")
cursor = conn.cursor()
cursor.execute("SELECT id, picked_up FROM orders ORDER BY id")
for row in cursor.fetchall():
    print(f"Order {row[0]}: picked_up={bool(row[1])}")
conn.close()

# Now mark orders 4 and 5 as picked up
print("\n=== Marking orders 4 and 5 as picked up ===")
s.post(f"{base}/orders/4/toggle-pickup", timeout=5)
s.post(f"{base}/orders/5/toggle-pickup", timeout=5)

# Check order history sorting
r = s.get(f"{base}/orders", timeout=5)
import re
rows = re.findall(r'data-order-id="(\d+)"', r.text)
print(f"Order IDs in HTML: {rows}")
print(f"Expected: non-picked-up first (3, 2, 1), then picked-up (5, 4)")

# Check badges - look for status-badge classes
for oid in rows:
    idx = r.text.find(f'data-order-id="{oid}"')
    # Find the next </tr> to get the full row
    end_idx = r.text.find('</tr>', idx)
    chunk = r.text[idx:end_idx] if end_idx > 0 else r.text[idx:idx+1000]
    has_picked = 'status-picked' in chunk
    has_pending = 'status-pending' in chunk
    print(f"Order {oid}: {'Picked Up (status-picked)' if has_picked else 'Pending (status-pending)'}")

# Also check opacity
for oid in rows:
    idx = r.text.find(f'data-order-id="{oid}"')
    chunk = r.text[idx:idx+200]
    has_opacity = 'opacity: 0.65' in chunk
    print(f"Order {oid}: opacity reduced = {has_opacity}")
