import requests
import re

base = 'http://localhost:8000'

# Get order detail page for order 10 (has valid customer)
resp = requests.get(f'{base}/orders/10')
print('Status:', resp.status_code)

# Extract hidden pickup inputs
picked_ups = re.findall(r'name="picked_up_(\d+)" value="(\d+)"', resp.text)
print('Hidden pickup inputs:', picked_ups)

# Extract quantities
quantities = re.findall(r'name="quantities"[^>]*value="(\d+)"', resp.text)
print('Quantities:', quantities)

# Extract product_ids
product_ids = re.findall(r'name="product_ids" value="(\d+)"', resp.text)
print('Product IDs:', product_ids)

# Extract prices
prices = re.findall(r'name="prices" value="([^"]+)"', resp.text)
print('Prices:', prices)

# Extract customer_id
customer_id = re.findall(r'customer_id[^>]*value="(\d+)"', resp.text)
print('Customer ID:', customer_id)

# Extract staff_name
staff_name = re.findall(r'name="staff_name"[^>]*value="([^"]*)"', resp.text)
print('Staff Name:', staff_name)

# Now test updating the order with changed pickup quantities
if product_ids and customer_id:
    form = {
        'customer_id': customer_id[0],
        'staff_name': (staff_name[0] if staff_name and staff_name[0] else 'Test User').strip(),
        'deposit': '0',
    }
    
    for i, pid in enumerate(product_ids):
        form['product_ids'] = pid
        form['quantities'] = quantities[i] if i < len(quantities) else '1'
        form['prices'] = prices[i] if i < len(prices) else '0'
    
    # Increment first pickup by 1
    if picked_ups:
        item_id, picked = picked_ups[0]
        new_picked = min(int(picked) + 1, int(quantities[0]) if quantities else 999)
        form[f'picked_up_{item_id}'] = str(new_picked)
        print(f'\nSubmitting pickup change: item {item_id} from {picked} to {new_picked}')
    
    print('Form data:', form)
    
    resp = requests.post(f'{base}/orders/10', data=form)
    print('Update response:', resp.status_code)
    
    # Check the new pickup values
    new_picked_ups = re.findall(r'name="picked_up_(\d+)" value="(\d+)"', resp.text)
    print('New pickup inputs:', new_picked_ups)
    
    if 'Order updated successfully' in resp.text:
        print('SUCCESS: Order updated!')
    elif 'flash-error' in resp.text:
        errors = re.findall(r'flash-error[^>]*>(.*?)<', resp.text)
        print('Errors:', errors)
    else:
        print('Check response manually')
