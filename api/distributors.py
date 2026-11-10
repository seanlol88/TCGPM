from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models.base import SessionLocal
from models.distributor import Distributor
from models.product import Product
from services.audit import log_change
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/distributors")
def get_distributors(request: Request):
    db = SessionLocal()
    try:
        distributors = db.query(Distributor).order_by(Distributor.name.asc()).all()
        # For each distributor, load associated products
        for dist in distributors:
            dist.products = db.query(Product).filter(
                Product.distributors.any(Distributor.id == dist.id)
            ).all()
    finally:
        db.close()
    return templates.TemplateResponse("distributors.html", {
        "request": request,
        "distributors": distributors,
    })


@router.post("/distributors")
def add_distributor(
    request: Request,
    name: str = Form(...),
    store_rep: str = Form(""),
    store_rep_phone: str = Form(""),
    store_rep_email: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = Distributor(
            name=name.strip(),
            store_rep=store_rep.strip() or None,
            store_rep_phone=store_rep_phone.strip() or None,
            store_rep_email=store_rep_email.strip() or None,
            phone=phone.strip() or None,
            email=email.strip() or None,
            website=website.strip() or None,
        )
        db.add(distributor)
        db.flush()
        did = distributor.id
        db.commit()
    finally:
        db.close()
    log_change("distributor", did, f"Added distributor: {name.strip()}", staff_name)
    return RedirectResponse(url="/distributors", status_code=303)


@router.post("/distributors/{distributor_id}/edit")
def edit_distributor(
    distributor_id: int,
    request: Request,
    name: str = Form(...),
    store_rep: str = Form(""),
    store_rep_phone: str = Form(""),
    store_rep_email: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
        if distributor:
            distributor.name = name.strip()
            distributor.store_rep = store_rep.strip() or None
            distributor.store_rep_phone = store_rep_phone.strip() or None
            distributor.store_rep_email = store_rep_email.strip() or None
            distributor.phone = phone.strip() or None
            distributor.email = email.strip() or None
            distributor.website = website.strip() or None
            db.commit()
    finally:
        db.close()
    log_change("distributor", distributor_id, f"Edited distributor: {name.strip()}", staff_name)
    return RedirectResponse(url="/distributors", status_code=303)


@router.post("/distributors/{distributor_id}/delete")
def delete_distributor(distributor_id: int, request: Request, staff_name: str = Form("")):
    db = SessionLocal()
    dname = None
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
        if distributor:
            dname = distributor.name
            db.delete(distributor)
            db.commit()
    finally:
        db.close()
    if dname:
        log_change("distributor", distributor_id, f"Deleted distributor: {dname}", staff_name)
    return RedirectResponse(url="/distributors", status_code=303)


@router.post("/distributors/{distributor_id}/delete-json")
def delete_distributor_json(distributor_id: int, request: Request, staff_name: str = Form("")):
    """AJAX endpoint for deleting a distributor."""
    db = SessionLocal()
    dname = None
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
        if distributor:
            dname = distributor.name
            db.delete(distributor)
            db.commit()
    finally:
        db.close()
    if dname:
        log_change("distributor", distributor_id, f"Deleted distributor: {dname}", staff_name)
        return JSONResponse(content={"status": "success", "name": dname})
    return JSONResponse(content={"status": "error", "message": "Distributor not found."}, status_code=404)


@router.post("/distributors/{distributor_id}/assign-product")
def assign_product_to_distributor(
    distributor_id: int,
    request: Request,
    product_id: int = Form(...),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
        product = db.query(Product).filter(Product.id == product_id).first()
        if distributor and product:
            if product not in distributor.products:
                distributor.products.append(product)
                db.commit()
    finally:
        db.close()
    log_change("distributor", distributor_id, f"Assigned product {product_id} to distributor", staff_name)
    return JSONResponse(content={"status": "success"})


@router.post("/distributors/{distributor_id}/unassign-product")
def unassign_product_from_distributor(
    distributor_id: int,
    request: Request,
    product_id: int = Form(...),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
        product = db.query(Product).filter(Product.id == product_id).first()
        if distributor and product:
            if product in distributor.products:
                distributor.products.remove(product)
                db.commit()
    finally:
        db.close()
    log_change("distributor", distributor_id, f"Unassigned product {product_id} from distributor", staff_name)
    return JSONResponse(content={"status": "success"})


@router.get("/distributors/json")
def get_distributors_json():
    """Return distributors as JSON for AJAX consumption."""
    db = SessionLocal()
    try:
        distributors = db.query(Distributor).order_by(Distributor.name.asc()).all()
        result = []
        for d in distributors:
            result.append({
                "id": d.id,
                "name": d.name,
                "store_rep": d.store_rep,
                "store_rep_phone": d.store_rep_phone,
                "store_rep_email": d.store_rep_email,
                "phone": d.phone,
                "email": d.email,
                "website": d.website,
            })
        return JSONResponse(content=result)
    finally:
        db.close()
