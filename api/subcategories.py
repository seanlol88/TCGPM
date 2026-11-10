from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models.base import SessionLocal
from models.subcategory import Subcategory
from models.category import Category
from services.audit import log_change
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/subcategories")
def get_subcategories(request: Request):
    db = SessionLocal()
    try:
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.products),
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
    finally:
        db.close()
    return templates.TemplateResponse("subcategories.html", {
        "request": request,
        "subcategories": subcategories,
        "categories": categories,
    })


@router.post("/subcategories")
def add_subcategory(request: Request, name: str = Form(...), category_id: str = Form(""), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        cat_id = int(category_id) if category_id.strip() else None
        sub = Subcategory(name=name.strip(), category_id=cat_id)
        db.add(sub)
        db.flush()
        sid = sub.id
        db.commit()
    except Exception as e:
        db.rollback()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.products), joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        return templates.TemplateResponse("subcategories.html", {
            "request": request,
            "subcategories": subcategories,
            "categories": categories,
            "error": str(e),
        })
    finally:
        db.close()
    log_change("Set Name", sid, f"Added Set Name: {name.strip()}", staff_name)
    return RedirectResponse(url="/subcategories", status_code=303)


@router.post("/subcategories/{subcategory_id}/edit")
def edit_subcategory(subcategory_id: int, request: Request, name: str = Form(...), category_id: str = Form(""), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        sub = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if sub:
            sub.name = name.strip()
            sub.category_id = int(category_id) if category_id.strip() else None
            db.commit()
    finally:
        db.close()
    log_change("Set Name", subcategory_id, f"Edited Set Name: {name.strip()}", staff_name)
    return RedirectResponse(url="/subcategories", status_code=303)


@router.post("/subcategories/{subcategory_id}/delete")
def delete_subcategory(subcategory_id: int, request: Request, staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        sub = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if sub:
            sname = sub.name
            db.delete(sub)
            db.commit()
    finally:
        db.close()
    log_change("Set Name", subcategory_id, f"Deleted Set Name: {sname}", staff_name)
    return RedirectResponse(url="/subcategories", status_code=303)


@router.post("/subcategories/add-json")
def add_subcategory_json(request: Request, name: str = Form(...), category_id: str = Form(""), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        name = name.strip()
        cat_id = int(category_id) if category_id.strip() else None
        if not name:
            raise HTTPException(status_code=400, detail="Set Name is required.")
        existing = db.query(Subcategory).filter(
            Subcategory.name.ilike(name),
            Subcategory.category_id == cat_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A Set Name with this name already exists in this category.")
        sub = Subcategory(name=name, category_id=cat_id)
        db.add(sub)
        db.commit()
        db.refresh(sub)
        sid = sub.id
        sub_name = sub.name
        sub_cat_id = sub.category_id
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("Set Name", sid, f"Added Set Name: {name}", staff_name)
    return JSONResponse(status_code=201, content={
        "id": sid,
        "name": sub_name,
        "category_id": sub_cat_id,
    })


@router.post("/subcategories/{subcategory_id}/edit-json")
def edit_subcategory_json(subcategory_id: int, request: Request, name: str = Form(...), category_id: str = Form(""), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        name = name.strip()
        cat_id = int(category_id) if category_id.strip() else None
        if not name:
            raise HTTPException(status_code=400, detail="Set Name is required.")
        existing = db.query(Subcategory).filter(
            Subcategory.name.ilike(name),
            Subcategory.category_id == cat_id,
            Subcategory.id != subcategory_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A Set Name with this name already exists in this category.")
        sub = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if not sub:
            raise HTTPException(status_code=404, detail="Set Name not found.")
        sub.name = name
        sub.category_id = cat_id
        db.commit()
        sub_id = sub.id
        sub_name = sub.name
        sub_cat_id = sub.category_id
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("Set Name", sub_id, f"Edited Set Name: {sub_name}", staff_name)
    return JSONResponse(content={"id": sub_id, "name": sub_name, "category_id": sub_cat_id})


@router.post("/subcategories/{subcategory_id}/delete-json")
def delete_subcategory_json(subcategory_id: int, request: Request, staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        sub = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if not sub:
            raise HTTPException(status_code=404, detail="Set Name not found.")
        sname = sub.name
        db.delete(sub)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
    log_change("Set Name", subcategory_id, f"Deleted Set Name: {sname}", staff_name)
    return JSONResponse(content={"status": "success"})
