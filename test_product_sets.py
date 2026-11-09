"""Test script for product sets and category filter features."""
import requests

BASE = "http://localhost:8000"

def test_product_sets():
    print("=== Testing Product Sets ===")
    
    # 1. Add a product set
    print("\n1. Adding product set 'Starter Deck'...")
    r = requests.post(f"{BASE}/product-sets", data={"name": "Starter Deck"})
    print(f"   Status: {r.status_code}, Redirect: {r.history}")
    
    # 2. Check product sets page
    print("\n2. Fetching product sets page...")
    r = requests.get(f"{BASE}/product-sets")
    print(f"   Status: {r.status_code}")
    assert "Starter Deck" in r.text, "Product set not found on page!"
    print("   ✓ Product set found on page")
    
    # 3. Add another product set
    print("\n3. Adding product set 'Booster Box'...")
    r = requests.post(f"{BASE}/product-sets", data={"name": "Booster Box"})
    print(f"   Status: {r.status_code}")
    
    # 4. Check inventory page has product set dropdown
    print("\n4. Checking inventory page for product set dropdown...")
    r = requests.get(f"{BASE}/inventory")
    print(f"   Status: {r.status_code}")
    assert "product_set_id" in r.text, "Product set dropdown not found!"
    assert "Starter Deck" in r.text, "Starter Deck not in dropdown!"
    print("   ✓ Product set dropdown found on inventory page")
    
    # 5. Add a product with product set
    print("\n5. Adding product with product set...")
    # Get product sets from page
    r = requests.get(f"{BASE}/product-sets")
    # Find the ID of Starter Deck
    import re
    match = re.search(r'value="(\d+)"[^>]*>Starter Deck', r.text)
    if not match:
        # Try alternate pattern
        match = re.search(r'Starter Deck.*?value="(\d+)"', r.text)
    if not match:
        # Just use ID 1 as default
        set_id = "1"
    else:
        set_id = match.group(1)
    
    r = requests.post(f"{BASE}/inventory", data={
        "name": "MTG Starter Deck Test",
        "quantity": "10",
        "price": "29.99",
        "category_id": "",
        "product_set_id": set_id
    })
    print(f"   Status: {r.status_code}")
    
    # 6. Check product appears in inventory
    print("\n6. Checking product in inventory...")
    r = requests.get(f"{BASE}/inventory")
    assert "MTG Starter Deck Test" in r.text, "Product not found in inventory!"
    print("   ✓ Product found in inventory")
    
    # 7. Test category filter on orders page
    print("\n7. Testing category filter on orders page...")
    r = requests.get(f"{BASE}/orders")
    print(f"   Status: {r.status_code}")
    assert "Filter by Category" in r.text, "Category filter not found!"
    print("   ✓ Category filter found on orders page")
    
    # 8. Test dashboard has product set count
    print("\n8. Checking dashboard for product set count...")
    r = requests.get(f"{BASE}/")
    assert "Product Sets" in r.text, "Product Sets not found on dashboard!"
    print("   ✓ Product Sets stat found on dashboard")
    
    # 9. Test navigation has Product Sets link
    print("\n9. Checking navigation for Product Sets link...")
    r = requests.get(f"{BASE}/")
    assert "/product-sets" in r.text, "Product Sets link not found in navigation!"
    print("   ✓ Product Sets link found in navigation")
    
    print("\n=== All tests passed! ===")

if __name__ == "__main__":
    test_product_sets()
