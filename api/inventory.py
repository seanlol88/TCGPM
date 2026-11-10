from datetime import date as date_type, timedelta
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models.base import SessionLocal
from models.product import Product
from models.category import Category
from models.subcategory import Subcategory
from services.audit import log_change
import os
import urllib.request
import uuid
import io

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]

# Directory for uploaded product images
PRODUCT_IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "product_images")
PRODUCT_IMAGES_LARGE_DIR = os.path.join(PRODUCT_IMAGES_DIR, "large")
PRODUCT_IMAGES_THUMB_DIR = os.path.join(PRODUCT_IMAGES_DIR, "thumb")

# Image size constants
LARGE_MAX_SIZE = (800, 800)
THUMB_SIZE = (80, 80)


def ensure_product_images_dir():
    os.makedirs(PRODUCT_IMAGES_DIR, exist_ok=True)
    os.makedirs(PRODUCT_IMAGES_LARGE_DIR, exist_ok=True)
    os.makedirs(PRODUCT_IMAGES_THUMB_DIR, exist_ok=True)


def resize_and_save_image(image_data: bytes, base_name: str, ext: str = ".jpg"):
    """Resize an image to large and thumbnail sizes, saving both versions.
    Returns the base filename (without extension) that is shared across sizes."""
    try:
        from PIL import Image
    except ImportError:
        # Fallback: save original without resizing if Pillow is unavailable
        ensure_product_images_dir()
        original_path = os.path.join(PRODUCT_IMAGES_DIR, f"{base_name}{ext}")
        with open(original_path, "wb") as f:
            f.write(image_data)
        return base_name

    ensure_product_images_dir()

    # Open image from bytes
    img = Image.open(io.BytesIO(image_data))

    # Convert to RGB if necessary (for JPEG saving)
    if img.mode in ("P", "RGBA", "LA") or (img.mode == "RGB" and img.info.get("transparency")):
        img = img.convert("RGB")

    # Save large version (maintain aspect ratio, max 800x800)
    large_img = img.copy()
    large_img.thumbnail(LARGE_MAX_SIZE, Image.LANCZOS)
    large_path = os.path.join(PRODUCT_IMAGES_LARGE_DIR, f"{base_name}{ext}")
    large_img.save(large_path, "JPEG", quality=85)

    # Save thumbnail version (80x80, maintain aspect ratio)
    thumb_img = img.copy()
    thumb_img.thumbnail(THUMB_SIZE, Image.LANCZOS)
    thumb_path = os.path.join(PRODUCT_IMAGES_THUMB_DIR, f"{base_name}{ext}")
    thumb_img.save(thumb_path, "JPEG", quality=85)

    return base_name


def get_image_urls(base_name: str, ext: str = ".jpg"):
    """Return the URL paths for large and thumbnail versions of an image."""
    return {
        "large": f"static/product_images/large/{base_name}{ext}",
        "thumb": f"static/product_images/thumb/{base_name}{ext}",
    }


def remove_old_images(image_url: str):
    """Remove both large and thumbnail versions of an old image."""
    if not image_url or not image_url.startswith("static/product_images/"):
        return
    # Try to find and remove the file from both large and thumb directories
    filename = os.path.basename(image_url)
    for directory in [PRODUCT_IMAGES_LARGE_DIR, PRODUCT_IMAGES_THUMB_DIR, PRODUCT_IMAGES_DIR]:
        old_path = os.path.join(directory, filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass


@router.get("/inventory/search-products")
def search_products(q: str = ""):
    """Search products by name for the Image Scraper tool. Returns id, name, image_url, and thumb_url."""
    db = SessionLocal()
    try:
        query = db.query(Product.id, Product.name, Product.image_url)
        if q.strip():
            search_term = f"%{q.strip()}%"
            query = query.filter(Product.name.ilike(search_term))
        products = query.order_by(Product.name.asc()).limit(20).all()
        result = []
        for p in products:
            entry = {"id": p.id, "name": p.name, "image_url": p.image_url}
            if p.image_url and p.image_url.startswith("static/product_images/"):
                # Derive thumbnail URL from the large URL
                filename = os.path.basename(p.image_url)
                base, ext = os.path.splitext(filename)
                if p.image_url.startswith("static/product_images/large/"):
                    entry["thumb_url"] = f"static/product_images/thumb/{base}_thumb{ext}"
                elif p.image_url.startswith("static/product_images/thumb/"):
                    entry["thumb_url"] = p.image_url
                else:
                    # Old format - no thumb yet
                    entry["thumb_url"] = None
            else:
                entry["thumb_url"] = p.image_url
            result.append(entry)
        return JSONResponse(content={"products": result})
    finally:
        db.close()


@router.post("/inventory/bulk-resize-images")
def bulk_resize_images():
    """Reprocess all existing product images into the new two-size format (large + thumbnail)."""
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.image_url != None).filter(
            Product.image_url.startswith("static/product_images/")
        ).all()
    finally:
        db.close()

    resized = 0
    errors = 0
    skipped = 0

    for product in products:
        img_url = product.image_url
        if not img_url:
            skipped += 1
            continue

        # Find the source image file
        source_path = None
        filename = os.path.basename(img_url)

        # Check in large, thumb, and root directories
        for directory in [PRODUCT_IMAGES_LARGE_DIR, PRODUCT_IMAGES_THUMB_DIR, PRODUCT_IMAGES_DIR]:
            candidate = os.path.join(directory, filename)
            if os.path.exists(candidate):
                source_path = candidate
                break

        if not source_path:
            skipped += 1
            continue

        try:
            from PIL import Image
            with open(source_path, "rb") as f:
                image_data = f.read()

            base, ext = os.path.splitext(filename)
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                ext = ".jpg"

            # Use a consistent base name for this product
            new_base = f"prod_{product.id}_{uuid.uuid4().hex[:8]}"
            resize_and_save_image(image_data, new_base, ext)
            urls = get_image_urls(new_base, ext)

            # Update the product to point to the new large image
            db = SessionLocal()
            try:
                prod = db.query(Product).filter(Product.id == product.id).first()
                if prod:
                    # Remove old files
                    remove_old_images(prod.image_url)
                    prod.image_url = urls["large"]
                    db.commit()
                resized += 1
            finally:
                db.close()

        except Exception:
            errors += 1
            continue

    return JSONResponse(content={
        "status": "success",
        "resized": resized,
        "errors": errors,
        "skipped": skipped,
        "total": len(products)
    })


def get_thumb_url(image_url):
    """Derive the thumbnail URL from a product's image_url."""
    if not image_url or not image_url.startswith("static/product_images/"):
        return image_url  # External URL, return as-is
    filename = os.path.basename(image_url)
    base, ext = os.path.splitext(filename)
    if image_url.startswith("static/product_images/large/"):
        return f"static/product_images/thumb/{base}{ext}"
    elif image_url.startswith("static/product_images/thumb/"):
        return image_url
    else:
        # Old format — try to find a matching thumb, fallback to original
        thumb = f"static/product_images/thumb/{filename}"
        thumb_path = os.path.join(PRODUCT_IMAGES_THUMB_DIR, filename)
        if os.path.exists(thumb_path):
            return thumb
        return image_url  # Fallback to original


@router.get("/inventory")
def get_inventory(request: Request, search: str = ""):
    db = SessionLocal()
    try:
        query = db.query(Product).options(
            joinedload(Product.category),
            joinedload(Product.subcategory).joinedload(Subcategory.category)
        )
        if search.strip():
            search_term = f"%{search.strip()}%"
            query = query.filter(
                (Product.name.ilike(search_term)) |
                (Product.category.has(Category.name.ilike(search_term))) |
                (Product.subcategory.has(Subcategory.name.ilike(search_term)))
            )
        products = query.order_by(Product.id.desc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
    finally:
        db.close()

    # Enrich products with thumbnail URLs
    for p in products:
        p.thumb_url = get_thumb_url(p.image_url)  # type: ignore[attr-defined]

    import time
    cache_bust = int(time.time())
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "products": products,
        "categories": categories,
        "subcategories": subcategories,
        "search": search,
        "cache_bust": cache_bust,
    })


@router.post("/inventory")
def add_product(request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), image_url: str = Form(""), image: UploadFile = File(None), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        cat_id = int(category_id) if category_id.strip() else None
        sub_id = int(subcategory_id) if subcategory_id.strip() else None
        rel_date = date_type.fromisoformat(release_date) if release_date.strip() else None
        max_order = int(max_per_order) if max_per_order.strip() else None
        img_url = image_url.strip() or None

        # Handle local image upload
        if image and image.filename:
            image_data = image.file.read()
            ext = os.path.splitext(image.filename)[1] or ".jpg"
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                ext = ".jpg"
            base_name = uuid.uuid4().hex
            resize_and_save_image(image_data, base_name, ext)
            urls = get_image_urls(base_name, ext)
            img_url = urls["large"]

        product = Product(name=name, quantity=quantity, price=price, cost_price=cost_price, max_per_order=max_order, release_date=rel_date, category_id=cat_id, subcategory_id=sub_id, image_url=img_url)
        db.add(product)
        db.flush()
        pid = product.id
        db.commit()
    finally:
        db.close()
    log_change("product", pid, f"Added product: {name} (qty: {quantity}, price: ${price:.2f}, cost: ${cost_price:.2f})", staff_name)
    return RedirectResponse(url="/inventory", status_code=303)


@router.post("/inventory/{product_id}/edit")
def edit_product(product_id: int, request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), image_url: str = Form(""), image: UploadFile = File(None), remove_image: str = Form("no"), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.name = name
            product.quantity = quantity
            product.price = price
            product.cost_price = cost_price
            product.max_per_order = int(max_per_order) if max_per_order.strip() else None
            product.release_date = date_type.fromisoformat(release_date) if release_date.strip() else None
            product.category_id = int(category_id) if category_id.strip() else None
            product.subcategory_id = int(subcategory_id) if subcategory_id.strip() else None

            # Handle image removal
            if remove_image == "yes":
                remove_old_images(product.image_url)
                product.image_url = None
            # Handle local image upload
            elif image and image.filename:
                remove_old_images(product.image_url)
                image_data = image.file.read()
                ext = os.path.splitext(image.filename)[1] or ".jpg"
                if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                    ext = ".jpg"
                base_name = uuid.uuid4().hex
                resize_and_save_image(image_data, base_name, ext)
                urls = get_image_urls(base_name, ext)
                product.image_url = urls["large"]
            # Handle URL-based image
            elif image_url.strip():
                product.image_url = image_url.strip()

            db.commit()
    finally:
        db.close()
    log_change("product", product_id, f"Edited product: {name} (qty: {quantity}, price: ${price:.2f}, cost: ${cost_price:.2f})", staff_name)
    return RedirectResponse(url="/inventory", status_code=303)


@router.post("/inventory/{product_id}/quantity")
def update_quantity(product_id: int, request: Request, quantity: int = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.quantity = quantity
            db.commit()
    finally:
        db.close()
    log_change("product", product_id, f"Updated quantity to {quantity}", staff_name)
    return RedirectResponse(url="/inventory", status_code=303)


@router.post("/inventory/add-json")
def add_product_json(request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), image_url: str = Form(""), image: UploadFile = File(None), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        cat_id = int(category_id) if category_id.strip() else None
        sub_id = int(subcategory_id) if subcategory_id.strip() else None
        rel_date = date_type.fromisoformat(release_date) if release_date.strip() else None
        max_order = int(max_per_order) if max_per_order.strip() else None
        img_url = image_url.strip() or None

        # Handle local image upload
        if image and image.filename:
            image_data = image.file.read()
            ext = os.path.splitext(image.filename)[1] or ".jpg"
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                ext = ".jpg"
            base_name = uuid.uuid4().hex
            resize_and_save_image(image_data, base_name, ext)
            urls = get_image_urls(base_name, ext)
            img_url = urls["large"]

        product = Product(name=name, quantity=quantity, price=price, cost_price=cost_price, max_per_order=max_order, release_date=rel_date, category_id=cat_id, subcategory_id=sub_id, image_url=img_url)
        db.add(product)
        db.commit()
        db.refresh(product)
        pid = product.id
    finally:
        db.close()
    log_change("product", pid, f"Added product: {name} (qty: {quantity}, price: ${price:.2f}, cost: ${cost_price:.2f})", staff_name)
    return JSONResponse(content={
        "id": product.id,
        "name": product.name,
        "quantity": product.quantity,
        "price": product.price,
        "cost_price": product.cost_price,
        "max_per_order": product.max_per_order,
        "release_date": product.release_date.isoformat() if product.release_date else "",
        "category_id": product.category_id or "",
        "subcategory_id": product.subcategory_id or "",
        "image_url": product.image_url or "",
    }, status_code=201)


@router.post("/inventory/{product_id}/edit-json")
def edit_product_json(product_id: int, request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), image_url: str = Form(""), image: UploadFile = File(None), remove_image: str = Form("no"), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.name = name
            product.quantity = quantity
            product.price = price
            product.cost_price = cost_price
            product.max_per_order = int(max_per_order) if max_per_order.strip() else None
            product.release_date = date_type.fromisoformat(release_date) if release_date.strip() else None
            product.category_id = int(category_id) if category_id.strip() else None
            product.subcategory_id = int(subcategory_id) if subcategory_id.strip() else None

            # Handle image removal
            if remove_image == "yes":
                remove_old_images(product.image_url)
                product.image_url = None
            # Handle local image upload
            elif image and image.filename:
                remove_old_images(product.image_url)
                image_data = image.file.read()
                ext = os.path.splitext(image.filename)[1] or ".jpg"
                if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                    ext = ".jpg"
                base_name = uuid.uuid4().hex
                resize_and_save_image(image_data, base_name, ext)
                urls = get_image_urls(base_name, ext)
                product.image_url = urls["large"]
            # Handle URL-based image
            elif image_url.strip():
                product.image_url = image_url.strip()

            db.commit()
            db.refresh(product)
    finally:
        db.close()
    log_change("product", product_id, f"Edited product: {name} (qty: {quantity}, price: ${price:.2f}, cost: ${cost_price:.2f})", staff_name)
    if product:
        return JSONResponse(content={
            "id": product.id,
            "name": product.name,
            "quantity": product.quantity,
            "price": product.price,
            "cost_price": product.cost_price,
            "max_per_order": product.max_per_order,
            "release_date": product.release_date.isoformat() if product.release_date else "",
            "category_id": product.category_id or "",
            "subcategory_id": product.subcategory_id or "",
            "image_url": product.image_url or "",
        })
    return JSONResponse(content={"error": "Product not found."}, status_code=404)


@router.post("/inventory/{product_id}/delete")
def delete_product(product_id: int, request: Request, staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            pname = product.name
            db.delete(product)
            db.commit()
    finally:
        db.close()
    log_change("product", product_id, f"Deleted product: {pname}", staff_name)
    return RedirectResponse(url="/inventory", status_code=303)


@router.post("/inventory/{product_id}/delete-json")
def delete_product_json(product_id: int, request: Request, staff_name: str = Form(None)):
    """AJAX endpoint for deleting a product with confirmation modal."""
    db = SessionLocal()
    pname = None
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            pname = product.name
            db.delete(product)
            db.commit()
    finally:
        db.close()
    if pname:
        log_change("product", product_id, f"Deleted product: {pname}", staff_name)
        return JSONResponse(content={"status": "success", "name": pname})
    return JSONResponse(content={"status": "error", "message": "Product not found."}, status_code=404)


@router.get("/upcoming-releases")
def get_upcoming_releases(request: Request):
    db = SessionLocal()
    try:
        today = date_type.today()
        products = db.query(Product).options(
            joinedload(Product.category),
            joinedload(Product.subcategory).joinedload(Subcategory.category)
        ).filter(
            Product.release_date != None,
        ).order_by(Product.release_date.asc(), Product.name.asc()).all()
    finally:
        db.close()
    return templates.TemplateResponse("upcoming_releases.html", {
        "request": request,
        "products": products,
        "today": today,
    })


@router.post("/inventory/bulk-delete")
def bulk_delete_products(request: Request, product_ids: str = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        ids = [int(x.strip()) for x in product_ids.split(",") if x.strip()]
        count = 0
        names = []
        for pid in ids:
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                names.append(product.name)
                db.delete(product)
                count += 1
        db.commit()
    finally:
        db.close()
    if names:
        log_change("product", 0, f"Bulk deleted {count} products: {', '.join(names)}", staff_name)
    return JSONResponse(content={"status": "success", "count": count})


@router.post("/inventory/bulk-change-category")
def bulk_change_category(request: Request, product_ids: str = Form(...), category_id: str = Form(""), subcategory_id: str = Form(""), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        ids = [int(x.strip()) for x in product_ids.split(",") if x.strip()]
        cat_id = int(category_id) if category_id.strip() else None
        sub_id = int(subcategory_id) if subcategory_id.strip() else None
        count = 0
        for pid in ids:
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                product.category_id = cat_id
                product.subcategory_id = sub_id
                count += 1
        db.commit()
    finally:
        db.close()
    cat_name = ""
    if cat_id:
        db2 = SessionLocal()
        try:
            cat = db2.query(Category).filter(Category.id == cat_id).first()
            if cat:
                cat_name = f" to {cat.name}"
        finally:
            db2.close()
    log_change("product", 0, f"Changed category{cat_name} for {count} products", staff_name)
    return JSONResponse(content={"status": "success", "count": count})


@router.post("/inventory/{product_id}/scrape-image")
def scrape_product_image(product_id: int, request: Request, image_url: str = Form(...)):
    """Download an image from a URL and save it locally for a product."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return JSONResponse(content={"status": "error", "message": "Product not found."}, status_code=404)

        url = image_url.strip()
        if not url:
            return JSONResponse(content={"status": "error", "message": "No URL provided."}, status_code=400)

        # Determine file extension from URL
        url_path = url.split("?")[0]  # Remove query params
        ext = os.path.splitext(url_path)[1]
        if not ext or ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            ext = ".jpg"

        # Download the image
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=15) as response:
                image_data = response.read()
        except Exception as e:
            return JSONResponse(content={"status": "error", "message": f"Failed to download image: {str(e)}"}, status_code=400)

        # Save locally with resizing
        base_name = uuid.uuid4().hex
        resize_and_save_image(image_data, base_name, ext)
        urls = get_image_urls(base_name, ext)

        # Remove old local image if exists
        remove_old_images(product.image_url)

        product.image_url = urls["large"]
        db.commit()
    finally:
        db.close()
    return JSONResponse(content={"status": "success", "image_url": urls["large"], "thumb_url": urls["thumb"]})


@router.post("/inventory/{product_id}/upload-image")
def upload_product_image(product_id: int, request: Request, image: UploadFile = File(...)):
    """Upload a local image file for a product."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return JSONResponse(content={"status": "error", "message": "Product not found."}, status_code=404)

        if not image or not image.filename:
            return JSONResponse(content={"status": "error", "message": "No file provided."}, status_code=400)

        ext = os.path.splitext(image.filename)[1] or ".jpg"
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            ext = ".jpg"
        image_data = image.file.read()
        base_name = uuid.uuid4().hex
        resize_and_save_image(image_data, base_name, ext)
        urls = get_image_urls(base_name, ext)

        # Remove old local image if exists
        remove_old_images(product.image_url)

        product.image_url = urls["large"]
        db.commit()
    finally:
        db.close()
    return JSONResponse(content={"status": "success", "image_url": urls["large"], "thumb_url": urls["thumb"]})


@router.post("/inventory/{product_id}/remove-image")
def remove_product_image(product_id: int, request: Request):
    """Remove the image from a product."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return JSONResponse(content={"status": "error", "message": "Product not found."}, status_code=404)

        remove_old_images(product.image_url)

        product.image_url = None
        db.commit()
    finally:
        db.close()
    return JSONResponse(content={"status": "success"})


@router.post("/inventory/search-images")
def search_images(request: Request, q: str = Form(...)):
    """Search Openverse (formerly CC Search) for images and return up to 4 results. No API key required."""
    query = q.strip()
    if not query:
        return JSONResponse(content={"status": "error", "message": "Search query is required."}, status_code=400)

    try:
        # Openverse API - free, open-source image search (700M+ images from Flickr, Wikimedia, etc.)
        search_url = f"https://api.openverse.org/v1/images/?q={urllib.request.quote(query)}&limit=4"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode("utf-8")

        import json
        result = json.loads(data)
        images = []
        for item in result.get("results", [])[:4]:
            # Openverse returns 'thumbnail' field with a thumb endpoint URL
            thumbnail_url = item.get("thumbnail", "")
            # Openverse returns 'url' field with the direct image URL from the source (Flickr, etc.)
            image_url = item.get("url", "")
            images.append({
                "url": image_url,
                "thumbnail": thumbnail_url,
                "title": item.get("title", ""),
            })
        return JSONResponse(content={"status": "success", "images": images})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": f"Search failed: {str(e)}"}, status_code=500)


@router.post("/inventory/download-image")
def download_image_for_preview(request: Request, image_url: str = Form(...)):
    """Download an image from a URL and save it locally. Returns the local path. Used for selecting images before creating a product."""
    url = image_url.strip()
    if not url:
        return JSONResponse(content={"status": "error", "message": "No URL provided."}, status_code=400)

    # Determine file extension from URL
    url_path = url.split("?")[0]
    ext = os.path.splitext(url_path)[1]
    if not ext or ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        ext = ".jpg"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=15) as response:
            image_data = response.read()
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": f"Failed to download image: {str(e)}"}, status_code=400)

    base_name = uuid.uuid4().hex
    resize_and_save_image(image_data, base_name, ext)
    urls = get_image_urls(base_name, ext)

    return JSONResponse(content={"status": "success", "image_url": urls["large"], "thumb_url": urls["thumb"]})
