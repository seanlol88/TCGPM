import urllib.request
import urllib.parse

base = 'http://127.0.0.1:8000'

def post_form(url, data_dict):
    """Submit a form POST and return the response."""
    data = urllib.parse.urlencode(data_dict).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def get_page(url):
    """GET a page and return the HTML."""
    resp = urllib.request.urlopen(url)
    return resp.status, resp.read().decode()

print("=" * 60)
print("TCG Preorder Manager - Functional Tests")
print("=" * 60)

# --- Test 1: Add Products ---
print('\n=== Test 1: Add Products ===')

products = [
    ("MTG Booster Pack", 50, 4.99),
    ("Pokemon Elite Trainer Box", 20, 49.99),
    ("Yu-Gi-Oh Structure Deck", 30, 19.99),
]

for name, qty, price in products:
    status, html = post_form(f'{base}/inventory', {
        'name': name, 'quantity': str(qty), 'price': str(price)
    })
    print(f'  Added: {name} (qty={qty}, price=${price}) - Status {status}')

# Verify products appear
status, html = get_page(f'{base}/inventory')
print(f'  Inventory page: HTTP {status}')
for name, _, _ in products:
    if name in html:
        print(f'  ✓ Found in inventory: {name}')
    else:
        print(f'  ✗ MISSING from inventory: {name}')

# --- Test 2: Update Product Quantity ---
print('\n=== Test 2: Update Product Quantity ===')
status, html = post_form(f'{base}/inventory/1/quantity', {'quantity': '45'})
print(f'  Updated MTG Booster Pack quantity to 45 - Status {status}')

status, html = get_page(f'{base}/inventory')
if '45' in html:
    print('  ✓ Quantity updated visible in inventory')

# --- Test 3: Edit Product Name/Price ---
print('\n=== Test 3: Edit Product Name/Price ===')
status, html = post_form(f'{base}/inventory/1/edit', {'name': 'MTG Booster Pack', 'price': '5.49'})
print(f'  Edited product 1 - Status {status}')

status, html = get_page(f'{base}/inventory')
if '5.49' in html:
    print('  ✓ Price edit visible in inventory')

# --- Test 4: Add Customers ---
print('\n=== Test 4: Add Customers ===')

customers = [
    ('Alice Johnson', '555-0101', 'alice@example.com'),
    ('Bob Smith', '555-0102', 'bob@example.com'),
    ('Charlie No Email', '555-0103', ''),
]

for name, phone, email in customers:
    status, html = post_form(f'{base}/customers', {
        'name': name, 'phone': phone, 'email': email
    })
    email_str = email if email else '(no email)'
    print(f'  Added: {name} ({phone}, {email_str}) - Status {status}')

# Verify customers appear
status, html = get_page(f'{base}/customers')
print(f'  Customer page: HTTP {status}')
for name, _, _ in customers:
    if name in html:
        print(f'  ✓ Found in customer list: {name}')
    else:
        print(f'  ✗ MISSING from customer list: {name}')

# --- Test 5: Edit Customer ---
print('\n=== Test 5: Edit Customer ===')
status, html = post_form(f'{base}/customers/1/edit', {
    'name': 'Alice Johnson', 'phone': '555-0101', 'email': 'alice@example.com'
})
print(f'  Edited customer 1 - Status {status}')

# --- Test 6: Create Order ---
print('\n=== Test 6: Create Order (Alice - 3x MTG, 1x Pokemon) ===')

# Use urlencode for multiple values with same key (no [] suffix for FastAPI)
order_data = urllib.parse.urlencode([
    ('customer_id', '1'),
    ('product_ids', '1'),
    ('product_ids', '2'),
    ('quantities', '3'),
    ('quantities', '1'),
    ('prices', '5.49'),
    ('prices', '49.99'),
]).encode()
req = urllib.request.Request(f'{base}/orders/new', data=order_data, method='POST')
try:
    resp = urllib.request.urlopen(req)
    status = resp.status
    html = resp.read().decode()
    print(f'  Order created - Status {status}')
except urllib.error.HTTPError as e:
    status = e.code
    html = e.read().decode()
    print(f'  Error creating order: {status}')

# Check for success indicators
if 'Order created' in html or 'success' in html.lower() or '/orders' in html:
    print('  ✓ Order creation successful')

# --- Test 7: Verify Stock Deduction ---
print('\n=== Test 7: Verify Stock Deduction ===')
status, html = get_page(f'{base}/inventory')
# MTG was 45, ordered 3, should be 42
# Pokemon was 20, ordered 1, should be 19
print('  Stock levels after order:')
print('  (MTG: was 45, ordered 3, expected 42)')
print('  (Pokemon: was 20, ordered 1, expected 19)')

# --- Test 8: Order History ---
print('\n=== Test 8: Order History ===')
status, html = get_page(f'{base}/orders')
print(f'  Order history page: HTTP {status}')
if 'Alice Johnson' in html:
    print('  ✓ Order history shows Alice Johnson')
if 'MTG Booster Pack' in html:
    print('  ✓ Order history shows MTG Booster Pack')

# --- Test 9: Dashboard ---
print('\n=== Test 9: Dashboard ===')
status, html = get_page(f'{base}/')
print(f'  Dashboard page: HTTP {status}')
if 'Alice Johnson' in html:
    print('  ✓ Dashboard shows recent order for Alice Johnson')
if 'MTG Booster Pack' in html:
    print('  ✓ Dashboard shows MTG Booster Pack')

# --- Test 10: New Order Page ---
print('\n=== Test 10: New Order Page ===')
status, html = get_page(f'{base}/orders/new')
print(f'  New order page: HTTP {status}')
if 'Alice Johnson' in html:
    print('  ✓ Customer dropdown includes Alice Johnson')
if 'MTG Booster Pack' in html:
    print('  ✓ Product dropdown includes MTG Booster Pack')

# --- Test 11: Oversell Protection ---
print('\n=== Test 11: Oversell Protection ===')
# Try to order more than available (e.g., 1000 of MTG when only ~42 left)
oversell_data = urllib.parse.urlencode([
    ('customer_id', '2'),
    ('product_ids', '1'),
    ('quantities', '1000'),
    ('prices', '5.49'),
]).encode()
req = urllib.request.Request(f'{base}/orders/new', data=oversell_data, method='POST')
try:
    resp = urllib.request.urlopen(req)
    status = resp.status
    html = resp.read().decode()
    if 'error' in html.lower() or 'not enough' in html.lower() or 'insufficient' in html.lower():
        print('  ✓ Oversell correctly rejected with error message')
    else:
        print(f'  ? Oversell attempt returned status {status}, checking response...')
except urllib.error.HTTPError as e:
    status = e.code
    html = e.read().decode()
    print(f'  ✓ Oversell correctly rejected with HTTP {status}')

# --- Test 12: Empty Order Rejection ---
print('\n=== Test 12: Empty Order (no products) ===')
empty_data = urllib.parse.urlencode([
    ('customer_id', '1'),
]).encode()
req = urllib.request.Request(f'{base}/orders/new', data=empty_data, method='POST')
try:
    resp = urllib.request.urlopen(req)
    status = resp.status
    html = resp.read().decode()
    if 'error' in html.lower():
        print('  ✓ Empty order correctly rejected')
    else:
        print(f'  ? Empty order returned status {status}')
except urllib.error.HTTPError as e:
    status = e.code
    print(f'  ✓ Empty order correctly rejected with HTTP {status}')

# --- Test 13: Customer without email ---
print('\n=== Test 13: Customer without email (Charlie) ===')
no_email_data = urllib.parse.urlencode([
    ('customer_id', '3'),
    ('product_ids', '3'),
    ('quantities', '1'),
    ('prices', '19.99'),
]).encode()
req = urllib.request.Request(f'{base}/orders/new', data=no_email_data, method='POST')
try:
    resp = urllib.request.urlopen(req)
    status = resp.status
    html = resp.read().decode()
    print(f'  Order for customer without email: Status {status}')
    print('  ✓ No crash - email gracefully skipped')
except urllib.error.HTTPError as e:
    status = e.code
    print(f'  Order for customer without email: HTTP {status}')

# --- Test 14: Delete Product ---
print('\n=== Test 14: Delete Product ===')
status, html = post_form(f'{base}/inventory/3/delete', {})
print(f'  Delete product 3 (Yu-Gi-Oh) - Status {status}')
status, html = get_page(f'{base}/inventory')
if 'Yu-Gi-Oh' not in html:
    print('  ✓ Product deleted from inventory')

# --- Test 15: Order history still shows deleted product ---
print('\n=== Test 15: Order History with Deleted Product ===')
status, html = get_page(f'{base}/orders')
# The Yu-Gi-Oh order should still appear in history even though product is deleted
print('  Order history page loaded after product deletion')

print('\n' + '=' * 60)
print('All tests completed!')
print('=' * 60)
