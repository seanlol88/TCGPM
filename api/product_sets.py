from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models.base import SessionLocal
from models.product_set import ProductSet
from models.category import Category

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/product-sets")
def get_product_sets(request: Request):
    db = SessionLocal()
    try:
        product_sets = db.query(ProductSet).options(
            joinedload(ProductSet.products),
            joinedload(ProductSet.category)
        ).order_by(ProductSet.category_id.asc(), ProductSet.name.asc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
    finally:
        db.close()
    return templates.TemplateResponse("product_sets.html", {
        "request": request,
        "product_sets": product_sets,
        "categories": categories,
    })


@router.post("/product-sets")
def add_product_set(request: Request, name: str = Form(...), category_id: str = Form("")):
    db = SessionLocal()
    try:
        cat_id = int(category_id) if category_id.strip() else None
        product_set = ProductSet(name=name.strip(), category_id=cat_id)
        db.add(product_set)
        db.commit()
    except Exception as e:
        db.rollback()
        product_sets = db.query(ProductSet).options(
            joinedload(ProductSet.products), joinedload(ProductSet.category)
        ).order_by(ProductSet.category_id.asc(), ProductSet.name.asc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        return templates.TemplateResponse("product_sets.html", {
            "request": request,
            "product_sets": product_sets,
            "categories": categories,
            "error": str(e),
        })
    finally:
        db.close()
    return RedirectResponse(url="/product-sets", status_code=303)


@router.post("/product-sets/{product_set_id}/edit")
def edit_product_set(product_set_id: int, request: Request, name: str = Form(...), category_id: str = Form("")):
    db = SessionLocal()
    try:
        product_set = db.query(ProductSet).filter(ProductSet.id == product_set_id).first()
        if product_set:
            product_set.name = name.strip()
            product_set.category_id = int(category_id) if category_id.strip() else None
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/product-sets", status_code=303)


@router.post("/product-sets/{product_set_id}/delete")
def delete_product_set(product_set_id: int, request: Request):
    db = SessionLocal()
    try:
        product_set = db.query(ProductSet).filter(ProductSet.id == product_set_id).first()
        if product_set:
            db.delete(product_set)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/product-sets", status_code=303)
