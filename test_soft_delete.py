import requests

base = 'http://localhost:8000'

# Test all pages load
print('=== Page Load Tests ===')
pages = ['/', '/orders', '/orders/new', '/customers', '/inventory', '/audit-log']
for p in pages:
    r = requests.get(base + p, timeout=5)
    print(f'{p}: {r.status_code}')

# Test order detail page
print()
print('=== Order Detail Page ===')
r = requests.get(base + '/orders/1', timeout=5)
print(f'Order detail: {r.status_code}')
print(f'Has delete modal: {"delete-modal" in r.text}')
print(f'Has openDeleteModal: {"openDeleteModal" in r.text}')
print(f'Has delete-json endpoint: {"delete-json" in r.text}')

# Test orders page has show deleted toggle
print()
print('=== Orders Page ===')
r = requests.get(base + '/orders', timeout=5)
print(f'Orders page: {r.status_code}')
print(f'Has show deleted toggle: {"Show Deleted" in r.text or "Hide Deleted" in r.text}')
print(f'Has restore modal: {"restore-modal" in r.text}')
print(f'Has openRestoreModal: {"openRestoreModal" in r.text}')
print(f'Has status-deleted CSS: {"status-deleted" in r.text}')

# Test soft delete via JSON endpoint
print()
print('=== Soft Delete Test ===')
# First check order 1 exists
r = requests.get(base + '/orders/1', timeout=5)
print(f'Order 1 exists: {r.status_code == 200}')

# Soft delete order 1
data = {'staff_name': 'Test Staff'}
r = requests.post(base + '/orders/1/delete-json', data=data, timeout=5)
print(f'Soft delete response: {r.status_code}')
print(f'Response JSON: {r.json()}')

# Check order 1 is no longer in the normal orders list
r = requests.get(base + '/orders', timeout=5)
orders_text = r.text
# Order 1 should still be in DB but filtered out by default
print(f'Order 1 in normal list (should be False): {"data-order-id=\"1\"" in orders_text}')

# Check order 1 appears when showing deleted
r = requests.get(base + '/orders?show_deleted=1', timeout=5)
deleted_text = r.text
print(f'Order 1 in deleted list (should be True): {"data-order-id=\"1\"" in deleted_text}')
print(f'Has restore button: {"openRestoreModal(1)" in deleted_text}')

# Test restore
print()
print('=== Restore Test ===')
r = requests.post(base + '/orders/1/restore', data={'staff_name': 'Test Staff'}, timeout=5)
print(f'Restore response: {r.status_code}')
print(f'Restore JSON: {r.json()}')

# Check order 1 is back in normal list
r = requests.get(base + '/orders', timeout=5)
print(f'Order 1 in normal list after restore (should be True): {"data-order-id=\"1\"" in r.text}')

# Test delete without staff name
print()
print('=== Validation Tests ===')
r = requests.post(base + '/orders/1/delete-json', data={'staff_name': ''}, timeout=5)
print(f'Delete without staff name: {r.status_code} (should be 400)')

r = requests.post(base + '/orders/1/restore', data={'staff_name': ''}, timeout=5)
print(f'Restore without staff name: {r.status_code} (should be 400)')

print()
print('All tests complete!')
