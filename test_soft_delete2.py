import requests

base = 'http://localhost:8000'

# Soft delete order 1
r = requests.post(base + '/orders/1/delete-json', data={'staff_name': 'Test'}, timeout=5)
print('Delete:', r.status_code, r.json())

# Check not in normal list
r = requests.get(base + '/orders', timeout=5)
print('In normal list:', 'data-order-id="1"' in r.text)

# Check in deleted list
r = requests.get(base + '/orders?show_deleted=1', timeout=5)
print('In deleted list:', 'data-order-id="1"' in r.text)
print('Has restore button:', 'openRestoreModal(1)' in r.text)

# Restore order 1
r = requests.post(base + '/orders/1/restore', data={'staff_name': 'Test'}, timeout=5)
print('Restore:', r.status_code, r.json())

# Check back in normal list
r = requests.get(base + '/orders', timeout=5)
print('Back in normal list:', 'data-order-id="1"' in r.text)

# Test validation
r = requests.post(base + '/orders/1/delete-json', data={'staff_name': ''}, timeout=5)
print('Empty staff delete:', r.status_code)

r = requests.post(base + '/orders/1/restore', data={'staff_name': ''}, timeout=5)
print('Empty staff restore:', r.status_code)

print('Done!')
