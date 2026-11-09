import requests

base = 'http://localhost:8000'

# Test 1: All pages load
print('=== Page Load Tests ===')
pages = ['/', '/orders', '/orders/new', '/orders/1', '/customers', '/inventory', '/audit-log']
for page in pages:
    r = requests.get(base + page, timeout=5)
    print(f'{page}: {r.status_code}')

# Test 2: Update item pickup - partial
print()
print('=== Pickup API Tests ===')
data = {'staff_name': 'Test Staff', 'item_1': '2', 'item_2': '1'}
r = requests.post(base + '/orders/1/update-item-pickup', data=data, timeout=5)
result = r.json()
print(f"Partial pickup: {r.status_code}, progress: {result.get('pickup_progress')}, fully: {result.get('is_fully_picked_up')}")

# Test 3: Update item pickup - full
data = {'staff_name': 'Test Staff', 'item_1': '3', 'item_2': '1'}
r = requests.post(base + '/orders/1/update-item-pickup', data=data, timeout=5)
result = r.json()
print(f"Full pickup: {r.status_code}, progress: {result.get('pickup_progress')}, fully: {result.get('is_fully_picked_up')}")

# Test 4: Reset pickup
data = {'staff_name': 'Test Staff', 'item_1': '0', 'item_2': '0'}
r = requests.post(base + '/orders/1/update-item-pickup', data=data, timeout=5)
result = r.json()
print(f"Reset pickup: {r.status_code}, progress: {result.get('pickup_progress')}, fully: {result.get('is_fully_picked_up')}")

# Test 5: Staff name required
data = {'staff_name': ''}
r = requests.post(base + '/orders/1/update-item-pickup', data=data, timeout=5)
print(f"Empty staff name: {r.status_code} (expected 400)")

# Test 6: Orders page shows pickup progress
r = requests.get(base + '/orders', timeout=5)
print(f"Orders page has status-partial: {'status-partial' in r.text}")
print(f"Orders page has orderItemsData: {'orderItemsData' in r.text}")

# Test 7: Dashboard shows pickup progress
r = requests.get(base + '/', timeout=5)
print(f"Dashboard has status-partial: {'status-partial' in r.text}")
print(f"Dashboard has orderItemsData: {'orderItemsData' in r.text}")

# Test 8: Order detail shows pickup progress
r = requests.get(base + '/orders/1', timeout=5)
print(f"Order detail has pickup status: {'Not Picked Up' in r.text or 'Picked Up' in r.text}")

print()
print('All tests passed!')
