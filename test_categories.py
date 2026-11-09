import urllib.request
import urllib.parse

base = 'http://127.0.0.1:8000'

def post_form(url, data_dict):
    data = urllib.parse.urlencode(data_dict).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def get_page(url):
    resp = urllib.request.urlopen(url)
    return resp.status, resp.read().decode()

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f'  PASS: {name}')
        passed += 1
    else:
        print(f'  FAIL: {name}')
        failed += 1

print('=' * 60)
print('Final Comprehensive Test')
print('=' * 60)

# 1. Categories page
print('\n=== Categories Page ===')
s, h = get_page(f'{base}/categories')
check('Page loads', s == 200)
check('Add form present', 'Add Category' in h)

# 2. Add categories
print('\n=== Add Categories ===')
for cat in ['Magic: The Gathering', 'Pokemon', 'Yu-Gi-Oh!']:
    s, h = post_form(f'{base}/categories', {'name': cat})
    check(f'Add {cat}', s == 200)

s, h = get_page(f'{base}/categories')
check('All 3 categories visible', all(c in h for c in ['Magic: The Gathering', 'Pokemon', 'Yu-Gi-Oh!']))

# 3. Dashboard
print('\n=== Dashboard ===')
s, h = get_page(f'{base}/')
check('Dashboard loads', s == 200)
check('Categories stat shown', 'Categories' in h)

# 4. Add products with categories
print('\n=== Products with Categories ===')
s, h = post_form(f'{base}/inventory', {'name': 'MTG Booster', 'quantity': '50', 'price': '4.99', 'category_id': '1'})
check('Product with category', s == 200)
s, h = post_form(f'{base}/inventory', {'name': 'No Category Item', 'quantity': '10', 'price': '5.00', 'category_id': ''})
check('Product without category', s == 200)

s, h = get_page(f'{base}/inventory')
check('Category in inventory table', 'Magic: The Gathering' in h)
check('Uncategorized shows dash', '-' in h)

# 5. Edit product category
print('\n=== Edit Product Category ===')
s, h = post_form(f'{base}/inventory/2/edit', {'name': 'No Category Item', 'price': '5.00', 'category_id': '2'})
check('Edit with new category', s == 200)

# 6. Customers
print('\n=== Customers ===')
s, h = post_form(f'{base}/customers', {'name': 'Alice', 'phone': '555-0101', 'email': 'alice@test.com'})
check('Add customer', s == 200)

# 7. Order creation
print('\n=== Order Creation ===')
order_data = urllib.parse.urlencode([
    ('customer_id', '1'), ('product_ids', '1'), ('quantities', '2'), ('prices', '4.99'),
]).encode()
req = urllib.request.Request(f'{base}/orders/new', data=order_data, method='POST')
try:
    resp = urllib.request.urlopen(req)
    check('Order created', resp.status == 200 or resp.status == 303)
except urllib.error.HTTPError as e:
    check('Order created', False)

# 8. Order history
print('\n=== Order History ===')
s, h = get_page(f'{base}/orders')
check('Order history loads', s == 200)
check('Customer in history', 'Alice' in h)

# 9. New order page categories
print('\n=== New Order Page ===')
s, h = get_page(f'{base}/orders/new')
check('Categories in dropdown', 'Magic: The Gathering' in h or 'Pokemon' in h)

# 10. Delete category
print('\n=== Delete Category ===')
s, h = post_form(f'{base}/categories/3/delete', {})
check('Delete category', s == 200)
s, h = get_page(f'{base}/categories')
check('Category removed', 'Yu-Gi-Oh' not in h)

# 11. Navigation
print('\n=== Navigation ===')
s, h = get_page(f'{base}/')
check('Categories nav link', '/categories' in h)

total = passed + failed
print()
print('=' * 60)
print(f'Results: {passed} passed, {failed} failed out of {total} tests')
print('=' * 60)
