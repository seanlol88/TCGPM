import requests

base = "http://localhost:8000"
s = requests.Session()

# Test 1: Toggle pickup on order 1
print("=== Test 1: Toggle pickup ===")
r = s.post(f"{base}/orders/1/toggle-pickup", timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

# Test 2: Order history shows picked up status and sorting
print("\n=== Test 2: Order history with pickup status ===")
r = s.get(f"{base}/orders", timeout=5)
print(f"Status: {r.status_code}")
text = r.text

# Find positions of order rows
import re
rows = re.findall(r'data-order-id="(\d+)"', text)
print(f"Order row IDs in HTML order: {rows}")

# Check order 1 has picked up badge
idx1 = text.find('data-order-id="1"')
if idx1 >= 0:
    chunk = text[idx1:idx1+500]
    print(f"Order 1 has 'Picked Up' badge: {'Picked Up' in chunk}")
    print(f"Order 1 has opacity 0.65: {'opacity: 0.65' in chunk}")

# Test 3: Toggle pickup off
print("\n=== Test 3: Toggle pickup off ===")
r = s.post(f"{base}/orders/1/toggle-pickup", timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

# Test 4: Order detail page has checkbox
print("\n=== Test 4: Order detail checkbox ===")
r = s.get(f"{base}/orders/1", timeout=5)
print(f"Status: {r.status_code}")
print(f"Has picked_up checkbox: {'name=\"picked_up\"' in r.text}")
print(f"Has 'Not Picked Up' label: {'Not Picked Up' in r.text}")

# Test 5: Update order with picked_up checkbox
print("\n=== Test 5: Update order with picked_up ===")
r = s.get(f"{base}/orders/1", timeout=5)
# Extract current form data
print(f"Status: {r.status_code}")

# Test 6: All pages load
print("\n=== Test 6: All pages load ===")
for page in ["/", "/orders", "/orders/new", "/customers", "/inventory"]:
    r = s.get(f"{base}{page}", timeout=5)
    print(f"{page}: {r.status_code}")

# Test 7: Sorting - picked up orders at bottom
print("\n=== Test 7: Sorting picked up orders to bottom ===")
# Mark orders 4 and 5 as picked up
s.post(f"{base}/orders/4/toggle-pickup", timeout=5)
s.post(f"{base}/orders/5/toggle-pickup", timeout=5)
r = s.get(f"{base}/orders", timeout=5)
rows = re.findall(r'data-order-id="(\d+)"', r.text)
print(f"Order IDs in HTML order: {rows}")
# Orders 4 and 5 should be at the end since they are picked up
if rows:
    last_two = rows[-2:]
    print(f"Last two orders: {last_two}")
    print(f"Orders 4 and 5 at bottom: {'4' in last_two and '5' in last_two}")

# Reset: un-pickup orders 4 and 5
s.post(f"{base}/orders/4/toggle-pickup", timeout=5)
s.post(f"{base}/orders/5/toggle-pickup", timeout=5)
s.post(f"{base}/orders/1/toggle-pickup", timeout=5)

print("\nAll tests complete!")
