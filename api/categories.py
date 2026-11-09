from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models.base import SessionLocal
from models.category import Category
from models.subcategory import Subcategory
from services.audit import log_change

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/categories")
def get_categories(request: Request):
    db = SessionLocal()
    try:
        categories = db.query(Category).options(
            joinedload(Category.products),
            joinedload(Category.subcategories).joinedload(Subcategory.products)
        ).order_by(Category.name.asc()).all()
        for cat in categories:
            cat.subcategories.sort(key=lambda s: (s.name or '').lower())
    finally:
        db.close()
    return templates.TemplateResponse("categories.html", {
        "request": request,
        "categories": categories,
    })


@router.post("/categories")
def add_category(request: Request, name: str = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        category = Category(name=name.strip())
        db.add(category)
        db.flush()
        cid = category.id
        db.commit()
    except Exception as e:
        db.rollback()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        return templates.TemplateResponse("categories.html", {
            "request": request,
            "categories": categories,
            "error": str(e),
        })
    finally:
        db.close()
    log_change("category", cid, f"Added category: {name.strip()}", staff_name)
    return RedirectResponse(url="/categories", status_code=303)


@router.post("/categories/{category_id}/edit")
def edit_category(category_id: int, request: Request, name: str = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if category:
            category.name = name.strip()
            db.commit()
    finally:
        db.close()
    log_change("category", category_id, f"Edited category: {name.strip()}", staff_name)
    return RedirectResponse(url="/categories", status_code=303)


@router.post("/categories/{category_id}/delete")
def delete_category(category_id: int, request: Request, staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if category:
            cname = category.name
            db.delete(category)
            db.commit()
    finally:
        db.close()
    log_change("category", category_id, f"Deleted category: {cname}", staff_name)
    return RedirectResponse(url="/categories", status_code=303)


@router.post("/categories/add-json")
def add_category_json(request: Request, name: str = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name is required.")
        existing = db.query(Category).filter(Category.name.ilike(name)).first()
        if existing:
            raise HTTPException(status_code=409, detail="A category with this name already exists.")
        category = Category(name=name)
        db.add(category)
        db.commit()
        db.refresh(category)
        cid = category.id
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("category", cid, f"Added category: {name}", staff_name)
    return JSONResponse(status_code=201, content={
        "id": category.id,
        "name": category.name,
    })


@router.post("/categories/{category_id}/edit-json")
def edit_category_json(category_id: int, request: Request, name: str = Form(...), staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name is required.")
        existing = db.query(Category).filter(Category.name.ilike(name), Category.id != category_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="A category with this name already exists.")
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found.")
        category.name = name
        db.commit()
        cat_id = category.id
        cat_name = category.name
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("category", cat_id, f"Edited category: {cat_name}", staff_name)
    return JSONResponse(content={"id": cat_id, "name": cat_name})


@router.post("/categories/{category_id}/delete-json")
def delete_category_json(category_id: int, request: Request, staff_name: str = Form(None)):
    db = SessionLocal()
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found.")
        cname = category.name
        db.delete(category)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("category", category_id, f"Deleted category: {cname}", staff_name)
    return JSONResponse(content={"status": "success"})
