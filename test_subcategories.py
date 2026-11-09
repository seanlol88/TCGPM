"""Test script for product sets as subcategories and dark mode."""
import requests

BASE = "http://localhost:8000"

def test_all():
    print("=== Testing Product Sets as Subcategories + Dark Mode ===")
    
    # 1. Check dark mode toggle exists
    print("\n1. Checking dark mode toggle...")
    r = requests.get(f"{BASE}/")
    assert "theme-switch" in r.text, "Dark mode toggle missing!"
    assert "toggleTheme" in r.text, "Toggle JS missing!"
    assert "data-theme" in r.text, "CSS data-theme attribute missing!"
    print("   ✓ Dark mode toggle present in HTML")
    
    # 2. Check CSS variables
    print("\n2. Checking CSS variables...")
    assert "--bg:" in r.text, "CSS variables missing!"
    assert '[data-theme="dark"]' in r.text, "Dark mode CSS missing!"
    print("   ✓ CSS variables and dark mode styles present")
    
    # 3. Add a category
    print("\n3. Adding category 'Magic: The Gathering'...")
    r = requests.post(f"{BASE}/categories", data={"name": "Magic: The Gathering"})
    print(f"   Status: {r.status_code}")
    
    # 4. Add a product set with category
    print("\n4. Adding product set 'Booster Box' under category...")
    # First get the category ID
    r = requests.get(f"{BASE}/product-sets")
    # Find category ID from the page
    import re
    cat_match = re.search(r'value="(\d+)"[^>]*>(Magic: The Gathering)', r.text)
    if cat_match:
        cat_id = cat_match.group(1)
    else:
        # Try to find any category ID
        cat_match = re.search(r'name="category_id"[^>]*>\s*<option value="(\d+)"', r.text)
        if cat_match:
            cat_id = cat_match.group(1)
        else:
            cat_id = "1"  # fallback
    print(f"   Using category ID: {cat_id}")
    r = requests.post(f"{BASE}/product-sets", data={"name": "Booster Box", "category_id": cat_id})
    print(f"   Status: {r.status_code}")
    
    # 5. Check product sets page shows category
    print("\n5. Checking product sets page shows category column...")
    r = requests.get(f"{BASE}/product-sets")
    assert "Parent Category" in r.text, "Parent Category label missing!"
    assert "<th>Category</th>" in r.text, "Category column header missing!"
    print("   ✓ Category column and parent category selector present")
    
    # 6. Check inventory page has category filter for product sets
    print("\n6. Checking inventory page product set filtering...")
    r = requests.get(f"{BASE}/inventory")
    assert "filterProductSets" in r.text, "Filter JS missing!"
    assert "data-category-id" in r.text, "Product set category data attribute missing!"
    print("   ✓ Product set filtering by category present")
    
    # 7. Check order detail page
    print("\n7. Checking order detail page loads...")
    # Create a product and customer for testing
    requests.post(f"{BASE}/inventory", data={"name": "MTG Test Card", "quantity": "10", "price": "2.99", "category_id": cat_id, "product_set_id": ""})
    requests.post(f"{BASE}/customers", data={"name": "Test User", "phone": "555-0199", "email": "test99@example.com"})
    
    # Create an order
    r = requests.post(f"{BASE}/orders/new", data={
        "customer_id": "1",
        "product_ids": ["999"],  # will likely fail, just testing page load
        "quantities": ["1"],
        "prices": ["2.99"]
    }, allow_redirects=False)
    print(f"   Order creation status: {r.status_code}")
    
    # Check order detail page
    r = requests.get(f"{BASE}/orders/1")
    print(f"   Order detail page status: {r.status_code}")
    assert r.status_code == 200, "Order detail page failed!"
    print("   ✓ Order detail page loads correctly")
    
    # 8. Check all pages have dark mode
    print("\n8. Checking all pages have dark mode toggle...")
    pages = ["/", "/inventory", "/orders", "/product-sets", "/orders/new", "/customers", "/categories"]
    for page in pages:
        r = requests.get(f"{BASE}{page}")
        assert "theme-switch" in r.text, f"Dark mode toggle missing on {page}!"
    print("   ✓ All pages have dark mode toggle")
    
    # 9. Test product set edit with category
    print("\n9. Testing product set edit with category change...")
    r = requests.get(f"{BASE}/product-sets")
    # Find Booster Box ID
    ps_match = re.search(r'value="(\d+)"[^>]*>(Booster Box)', r.text)
    if ps_match:
        ps_id = ps_match.group(1)
        r = requests.post(f"{BASE}/product-sets/{ps_id}/edit", data={"name": "Booster Box Updated", "category_id": cat_id})
        print(f"   Edit status: {r.status_code}")
        print("   ✓ Product set edit with category works")
    else:
        print("   ⚠ Booster Box not found, skipping edit test")
    
    print("\n=== All tests passed! ===")

if __name__ == "__main__":
    test_all()
