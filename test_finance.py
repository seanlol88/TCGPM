import requests
import re

s = requests.Session()

# Test 1: Add customer with first/last name
r = s.post('http://localhost:8000/customers/add-json', data={'first_name': 'John', 'last_name': 'Doe', 'phone': '555-0100', 'email': 'john@test.com'}, timeout=5)
print('1. Add customer:', r.status_code, r.json())

# Test 2: Add product
r = s.post('http://localhost:8000/inventory', data={'name': 'Test Product Finance', 'quantity': '10', 'price': '29.99', 'category_id': '', 'product_set_id': ''}, timeout=5)
print('2. Add product:', r.status_code)

# Get the product ID from inventory page
r = s.get('http://localhost:8000/inventory', timeout=5)
match = re.search(r'value="(\d+)"[^>]*>.*?Test Product Finance', r.text)
prod_id = match.group(1) if match else '1'
print('   Product ID:', prod_id)

# Test 3: Create order with deposit
r = s.post('http://localhost:8000/orders/new', data={'customer_id': '7', 'product_ids': [prod_id], 'quantities': ['2'], 'prices': ['29.99'], 'deposit': '20.00', 'staff_name': 'Staff1'}, timeout=5, allow_redirects=False)
print('3. Create order:', r.status_code)

# Test 4: Check audit log
r = s.get('http://localhost:8000/audit-log', timeout=5)
print('4. Audit log:', r.status_code, 'Has order created:', 'Order created' in r.text)

# Test 5: Check order detail has finance section
r = s.get('http://localhost:8000/orders', timeout=5)
print('5. Orders page has balance:', 'Balance' in r.text)
print('   Orders page has deposit:', 'Deposit' in r.text)

# Test 6: Check new order page has finance section
r = s.get('http://localhost:8000/orders/new', timeout=5)
print('6. New order has deposit field:', 'deposit' in r.text)
print('   New order has staff field:', 'staff_name' in r.text)

# Test 7: Check customers page has first/last name
r = s.get('http://localhost:8000/customers', timeout=5)
print('7. Customers has first_name:', 'first_name' in r.text)
print('   Customers has last_name:', 'last_name' in r.text)

# Test 8: Check dashboard has payment count
r = s.get('http://localhost:8000/', timeout=5)
print('8. Dashboard has payments:', 'Payments' in r.text)
print('   Base has audit link:', 'audit-log' in r.text)

# Test 9: Check order detail page
r = s.get('http://localhost:8000/orders/4', timeout=5)
print('9. Order detail has finance:', 'Finance' in r.text)
print('   Order detail has payment history:', 'Payment History' in r.text)
print('   Order detail has add payment:', 'Add Payment' in r.text)

# Test 10: Add payment to order
r = s.post('http://localhost:8000/orders/4/payment-json', data={'amount': '15.00', 'payment_type': 'cash', 'staff_name': 'Staff2'}, timeout=5)
print('10. Add payment:', r.status_code, r.json())

print('\nAll tests completed!')
