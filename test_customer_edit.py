import requests

base = "http://localhost:8000"

# Test 1: Customers page has all new elements
print("=== Test 1: Customers page structure ===")
r = requests.get(f"{base}/customers", timeout=5)
print(f"Status: {r.status_code}")
print(f"View Orders link: {'View Orders' in r.text}")
print(f"Edit modal: {'edit-customer-modal' in r.text}")
print(f"openEditModal function: {'openEditModal' in r.text}")
print(f"edit-json endpoint: {'edit-json' in r.text}")

# Test 2: Edit customer via JSON endpoint
print("\n=== Test 2: Edit customer via JSON ===")
r = requests.post(f"{base}/customers/edit-json/1", data={
    "first_name": "Ryan",
    "last_name": "Calleja",
    "phone": "0403365001",
    "email": "ryan@example.com"
}, timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

# Test 3: Duplicate phone detection
print("\n=== Test 3: Duplicate phone detection ===")
r = requests.post(f"{base}/customers/edit-json/2", data={
    "first_name": "Test",
    "last_name": "User",
    "phone": "0403365001",  # Same as customer 1
    "email": "test@example.com"
}, timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

# Test 4: Orders page with customer filter
print("\n=== Test 4: Orders page with customer filter ===")
r = requests.get(f"{base}/orders?customer_search=Ryan", timeout=5)
print(f"Status: {r.status_code}")

print("\nAll tests complete!")
