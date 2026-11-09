from datetime import date as date_type, timedelta
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models.base import SessionLocal
from models.product import Product
from models.category import Category
from models.subcategory import Subcategory
from services.audit import log_change

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


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
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "products": products,
        "categories": categories,
        "subcategories": subcategories,
        "search": search,
    })


@router.post("/inventory")
def add_product(request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        cat_id = int(category_id) if category_id.strip() else None
        sub_id = int(subcategory_id) if subcategory_id.strip() else None
        rel_date = date_type.fromisoformat(release_date) if release_date.strip() else None
        max_order = int(max_per_order) if max_per_order.strip() else None
        product = Product(name=name, quantity=quantity, price=price, cost_price=cost_price, max_per_order=max_order, release_date=rel_date, category_id=cat_id, subcategory_id=sub_id)
        db.add(product)
        db.flush()
        pid = product.id
        db.commit()
    finally:
        db.close()
    log_change("product", pid, f"Added product: {name} (qty: {quantity}, price: ${price:.2f}, cost: ${cost_price:.2f})", staff_name)
    return RedirectResponse(url="/inventory", status_code=303)


@router.post("/inventory/{product_id}/edit")
def edit_product(product_id: int, request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), staff_name: str = Form(None)):
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
def add_product_json(request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        cat_id = int(category_id) if category_id.strip() else None
        sub_id = int(subcategory_id) if subcategory_id.strip() else None
        rel_date = date_type.fromisoformat(release_date) if release_date.strip() else None
        max_order = int(max_per_order) if max_per_order.strip() else None
        product = Product(name=name, quantity=quantity, price=price, cost_price=cost_price, max_per_order=max_order, release_date=rel_date, category_id=cat_id, subcategory_id=sub_id)
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
    }, status_code=201)


@router.post("/inventory/{product_id}/edit-json")
def edit_product_json(product_id: int, request: Request, name: str = Form(...), quantity: int = Form(...), price: float = Form(...), cost_price: float = Form(0.0), max_per_order: str = Form(""), release_date: str = Form(""), category_id: str = Form(""), subcategory_id: str = Form(""), staff_name: str = Form(None)):
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
