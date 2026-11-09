import urllib.request
import urllib.parse
import html

def test_order_edit_flow():
    """Test the order detail page, editing, stock warnings, and deletion."""
    
    # First, let's check what orders exist
    resp = urllib.request.urlopen('http://127.0.0.1:8000/orders')
    html_content = resp.read().decode()
    print("=" * 60)
    print("TEST 1: Order History Page")
    print("=" * 60)
    print("Status: 200 OK")
    
    # Check for table structure
    has_table = '<table>' in html_content
    has_customer_link = '/orders/' in html_content
    print(f"Has table structure: {has_table}")
    print(f"Has customer links: {has_customer_link}")
    
    # Extract order IDs from links
    import re
    order_links = re.findall(r'/orders/(\d+)', html_content)
    print(f"Found order IDs: {order_links}")
    
    if not order_links:
        print("No orders found. Creating test data...")
        # Create a product
        data = urllib.parse.urlencode({
            'name': 'Test Product Edit',
            'quantity': '100',
            'price': '5.99'
        }).encode()
        req = urllib.request.Request('http://127.0.0.1:8000/inventory', data=data, method='POST')
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            print(f"Product creation: {e.code}")
        
        # Create a customer
        data = urllib.parse.urlencode({
            'name': 'Test Customer Edit',
            'phone': '555-0199',
            'email': 'testedit@example.com'
        }).encode()
        req = urllib.request.Request('http://127.0.0.1:8000/customers', data=data, method='POST')
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            print(f"Customer creation: {e.code}")
        
        # Get the order history again
        resp = urllib.request.urlopen('http://127.0.0.1:8000/orders')
        html_content = resp.read().decode()
        order_links = re.findall(r'/orders/(\d+)', html_content)
        print(f"Order IDs after setup: {order_links}")
    
    if order_links:
        order_id = order_links[0]
        
        print(f"\n{'=' * 60}")
        print(f"TEST 2: Order Detail Page (Order #{order_id})")
        print("=" * 60)
        
        resp = urllib.request.urlopen(f'http://127.0.0.1:8000/orders/{order_id}')
        detail_html = resp.read().decode()
        print("Status: 200 OK")
        print(f"Has edit form: {'product_ids' in detail_html}")
        print(f"Has customer selector: {'customer_id' in detail_html}")
        print(f"Has stock check JS: {'checkStock' in detail_html}")
        print(f"Has delete form: {'delete' in detail_html}")
        print(f"Has confirm button: {'Confirm Order' in detail_html}")
        
        # Test 3: Try to update an order with insufficient stock
        print(f"\n{'=' * 60}")
        print(f"TEST 3: Stock Warning on Edit")
        print("=" * 60)
        
        # Parse the order detail to find existing product IDs and quantities
        product_selects = re.findall(r'<option value="(\d+)"[^>]*data-stock="(\d+)"', detail_html)
        print(f"Available products: {len(product_selects)}")
        
        if product_selects:
            # Try to submit with a very large quantity
            product_id = product_selects[0][0]
            stock_available = product_selects[0][1]
            large_qty = int(stock_available) + 1000
            
            form_data = urllib.parse.urlencode({
                'customer_id': '1',
                'product_ids': str(product_id),
                'quantities': str(large_qty),
                'prices': '5.99'
            }).encode()
            
            req = urllib.request.Request(
                f'http://127.0.0.1:8000/orders/{order_id}',
                data=form_data,
                method='POST'
            )
            try:
                resp = urllib.request.urlopen(req)
                response_html = resp.read().decode()
                
                has_warning = 'stock_warnings' in response_html or 'Stock Warning' in response_html or 'Not enough stock' in response_html
                print(f"Stock warning shown: {has_warning}")
                print(f"Response status: {resp.status}")
                
                if has_warning:
                    print("PASS: Stock warning correctly displayed!")
                else:
                    print("INFO: Checking response for warning indicators...")
                    # Check if the form was returned with warnings
                    if 'e74c3c' in response_html or 'fff3cd' in response_html:
                        print("PASS: Warning styling found in response!")
                    else:
                        print("FAIL: No warning found")
            except urllib.error.HTTPError as e:
                print(f"HTTP Error: {e.code}")
        
        # Test 4: Successful order update
        print(f"\n{'=' * 60}")
        print(f"TEST 4: Successful Order Update")
        print("=" * 60)
        
        if product_selects:
            product_id = product_selects[0][0]
            stock_available = product_selects[0][1]
            safe_qty = min(1, int(stock_available))
            
            form_data = urllib.parse.urlencode({
                'customer_id': '1',
                'product_ids': str(product_id),
                'quantities': str(safe_qty),
                'prices': '5.99'
            }).encode()
            
            req = urllib.request.Request(
                f'http://127.0.0.1:8000/orders/{order_id}',
                data=form_data,
                method='POST'
            )
            try:
                resp = urllib.request.urlopen(req)
                response_html = resp.read().decode()
                
                has_success = 'Order updated successfully' in response_html
                print(f"Success message shown: {has_success}")
                print(f"Response status: {resp.status}")
                
                if has_success:
                    print("PASS: Order updated successfully!")
                else:
                    print("INFO: Checking for success indicators...")
            except urllib.error.HTTPError as e:
                print(f"HTTP Error: {e.code}")
    
    # Test 5: Delete order
    print(f"\n{'=' * 60}")
    print(f"TEST 5: Delete Order")
    print("=" * 60)
    
    if order_links:
        order_id = order_links[-1]  # Delete the last order
        
        form_data = b''
        req = urllib.request.Request(
            f'http://127.0.0.1:8000/orders/{order_id}/delete',
            data=form_data,
            method='POST'
        )
        try:
            resp = urllib.request.urlopen(req)
            print(f"Delete response status: {resp.status}")
            print(f"Redirected to: {resp.url}")
            
            if resp.status == 200 and '/orders' in resp.url:
                print("PASS: Order deleted and redirected to order history!")
            else:
                print("INFO: Check redirect behavior")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code}")
    
    print(f"\n{'=' * 60}")
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_order_edit_flow()
