from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.base import SessionLocal
from models.customer import Customer
from models.customer_credit import CustomerCredit
from services.audit import log_change
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/customers")
def get_customers(request: Request, search: str = None):
    db = SessionLocal()
    try:
        query = db.query(Customer)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Customer.first_name.ilike(search_term)) |
                (Customer.last_name.ilike(search_term)) |
                (Customer.phone.ilike(search_term)) |
                (Customer.email.ilike(search_term))
            )
        customers = query.order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        # Build credit balance map for all customers
        credit_balances = {}
        for customer in customers:
            credits = db.query(CustomerCredit).filter(CustomerCredit.customer_id == customer.id).all()
            balance = sum(c.amount for c in credits if c.credit_type == 'add') - sum(c.amount for c in credits if c.credit_type == 'remove')
            credit_balances[customer.id] = balance
    finally:
        db.close()
    return templates.TemplateResponse("customers.html", {
        "request": request,
        "customers": customers,
        "credit_balances": credit_balances,
        "search": search or "",
    })


@router.post("/customers")
def add_customer(request: Request, first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(...), email: str = Form(None), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        # Check for duplicate phone
        existing = db.query(Customer).filter(Customer.phone == phone).first()
        if existing:
            return templates.TemplateResponse("customers.html", {
                "request": request,
                "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                "error": f"A customer with phone number {phone} already exists."
            })
        # Check for duplicate email
        if email:
            existing = db.query(Customer).filter(Customer.email == email).first()
            if existing:
                return templates.TemplateResponse("customers.html", {
                    "request": request,
                    "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                    "error": f"A customer with email {email} already exists."
                })
        customer = Customer(first_name=first_name, last_name=last_name, phone=phone, email=email or None)
        db.add(customer)
        db.flush()
        cid = customer.id
        db.commit()
    finally:
        db.close()
    log_change("customer", cid, f"Added customer: {first_name} {last_name} (phone: {phone})", staff_name)
    return RedirectResponse(url="/customers", status_code=303)


@router.post("/customers/{customer_id}/edit")
def edit_customer(customer_id: int, request: Request, first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(...), email: str = Form(None), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            # Check for duplicate phone (excluding current customer)
            existing = db.query(Customer).filter(Customer.phone == phone, Customer.id != customer_id).first()
            if existing:
                return templates.TemplateResponse("customers.html", {
                    "request": request,
                    "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                    "error": f"A customer with phone number {phone} already exists."
                })
            # Check for duplicate email (excluding current customer)
            if email:
                existing = db.query(Customer).filter(Customer.email == email, Customer.id != customer_id).first()
                if existing:
                    return templates.TemplateResponse("customers.html", {
                        "request": request,
                        "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                        "error": f"A customer with email {email} already exists."
                    })
            customer.first_name = first_name
            customer.last_name = last_name
            customer.phone = phone
            customer.email = email or None
            db.commit()
    finally:
        db.close()
    log_change("customer", customer_id, f"Edited customer: {first_name} {last_name} (phone: {phone})", staff_name)
    return RedirectResponse(url="/customers", status_code=303)


@router.post("/customers/{customer_id}/delete")
def delete_customer(customer_id: int, request: Request, staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            cname = customer.full_name
            db.delete(customer)
            db.commit()
    finally:
        db.close()
    log_change("customer", customer_id, f"Deleted customer: {cname}", staff_name)
    return RedirectResponse(url="/customers", status_code=303)


@router.post("/customers/edit-json/{customer_id}")
def edit_customer_json(customer_id: int, request: Request, first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(...), email: str = Form(None), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return JSONResponse(content={"error": "Customer not found."}, status_code=404)
        # Check for duplicate phone (excluding current customer)
        existing = db.query(Customer).filter(Customer.phone == phone, Customer.id != customer_id).first()
        if existing:
            return JSONResponse(content={"error": f"A customer with phone number {phone} already exists."}, status_code=409)
        # Check for duplicate email (excluding current customer)
        if email:
            existing = db.query(Customer).filter(Customer.email == email, Customer.id != customer_id).first()
            if existing:
                return JSONResponse(content={"error": f"A customer with email {email} already exists."}, status_code=409)
        customer.first_name = first_name
        customer.last_name = last_name
        customer.phone = phone
        customer.email = email or None
        db.commit()
        # Capture values before session closes
        cid = customer.id
        fn = customer.first_name
        ln = customer.last_name
        ph = customer.phone
        em = customer.email
    finally:
        db.close()
    log_change("customer", customer_id, f"Edited customer: {first_name} {last_name} (phone: {phone})", staff_name)
    return JSONResponse(content={
        "id": cid,
        "first_name": fn,
        "last_name": ln,
        "full_name": f"{fn} {ln}",
        "phone": ph,
        "email": em
    })


@router.post("/customers/bulk-delete")
def bulk_delete_customers(request: Request, customer_ids: str = Form(...), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        ids = [int(x.strip()) for x in customer_ids.split(',') if x.strip()]
        count = 0
        names = []
        for cid in ids:
            customer = db.query(Customer).filter(Customer.id == cid).first()
            if customer:
                names.append(customer.full_name)
                db.delete(customer)
                count += 1
        db.commit()
    finally:
        db.close()
    for i, cid in enumerate(ids):
        if i < len(names):
            log_change("customer", cid, f"Bulk deleted customer: {names[i]}", staff_name)
    return JSONResponse(content={"message": f"{count} customer(s) deleted successfully.", "count": count})


@router.post("/customers/add-json")
def add_customer_json(request: Request, first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(...), email: str = Form(None), staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        existing = db.query(Customer).filter(Customer.phone == phone).first()
        if existing:
            return JSONResponse(content={
                "error": f"A customer with phone number {phone} already exists.",
                "duplicate": True,
                "duplicate_type": "phone",
                "customer": {
                    "id": existing.id,
                    "first_name": existing.first_name,
                    "last_name": existing.last_name,
                    "full_name": existing.full_name,
                    "phone": existing.phone,
                    "email": existing.email
                }
            }, status_code=409)
        # Check for duplicate email
        if email:
            existing = db.query(Customer).filter(Customer.email == email).first()
            if existing:
                return JSONResponse(content={
                    "error": f"A customer with email {email} already exists.",
                    "duplicate": True,
                    "duplicate_type": "email",
                    "customer": {
                        "id": existing.id,
                        "first_name": existing.first_name,
                        "last_name": existing.last_name,
                        "full_name": existing.full_name,
                        "phone": existing.phone,
                        "email": existing.email
                    }
                }, status_code=409)
        customer = Customer(first_name=first_name, last_name=last_name, phone=phone, email=email or None)
        db.add(customer)
        db.flush()
        cid = customer.id
        fn = customer.first_name
        ln = customer.last_name
        ph = customer.phone
        em = customer.email
        db.commit()
    finally:
        db.close()
    log_change("customer", cid, f"Added customer: {first_name} {last_name} (phone: {phone})", staff_name)
    return JSONResponse(content={
        "id": cid,
        "first_name": fn,
        "last_name": ln,
        "full_name": f"{fn} {ln}",
        "phone": ph,
        "email": em
    }, status_code=201)


@router.get("/customers/{customer_id}/credit")
def get_customer_credit(customer_id: int):
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return JSONResponse(content={"error": "Customer not found."}, status_code=404)
        credits = db.query(CustomerCredit).filter(
            CustomerCredit.customer_id == customer_id
        ).order_by(CustomerCredit.timestamp.desc()).all()
        # Calculate balance
        balance = 0.0
        for credit in credits:
            if credit.credit_type == "add":
                balance += credit.amount
            elif credit.credit_type == "remove":
                balance -= credit.amount
        # Capture data before session closes
        cname = customer.full_name
        history = []
        for c in credits:
            history.append({
                "id": c.id,
                "amount": c.amount,
                "credit_type": c.credit_type,
                "staff_name": c.staff_name,
                "notes": c.notes,
                "timestamp": c.timestamp.strftime("%Y-%m-%d %H:%M")
            })
    finally:
        db.close()
    return JSONResponse(content={
        "customer_id": customer_id,
        "customer_name": cname,
        "balance": balance,
        "history": history
    })


@router.post("/customers/{customer_id}/credit/add")
def add_customer_credit(customer_id: int, amount: float = Form(...), staff_name: str = Form(""), notes: str = Form(None)):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = "System"
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return JSONResponse(content={"error": "Customer not found."}, status_code=404)
        if amount <= 0:
            return JSONResponse(content={"error": "Amount must be greater than 0."}, status_code=400)
        credit = CustomerCredit(customer_id=customer_id, amount=amount, credit_type="add", staff_name=staff_name, notes=notes or None)
        db.add(credit)
        db.flush()
        new_balance = 0.0
        all_credits = db.query(CustomerCredit).filter(CustomerCredit.customer_id == customer_id).all()
        for c in all_credits:
            if c.credit_type == "add":
                new_balance += c.amount
            elif c.credit_type == "remove":
                new_balance -= c.amount
        cname = customer.full_name
        db.commit()
    finally:
        db.close()
    log_change("customer", customer_id, f"Added credit: ${amount:.2f} (new balance: ${new_balance:.2f})", staff_name)
    return JSONResponse(content={
        "status": "success",
        "balance": new_balance,
        "message": f"Added ${amount:.2f} credit to {cname}."
    })


@router.post("/customers/{customer_id}/credit/remove")
def remove_customer_credit(customer_id: int, amount: float = Form(...), staff_name: str = Form(""), notes: str = Form(None)):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = "System"
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return JSONResponse(content={"error": "Customer not found."}, status_code=404)
        if amount <= 0:
            return JSONResponse(content={"error": "Amount must be greater than 0."}, status_code=400)
        # Check current balance
        current_balance = 0.0
        all_credits = db.query(CustomerCredit).filter(CustomerCredit.customer_id == customer_id).all()
        for c in all_credits:
            if c.credit_type == "add":
                current_balance += c.amount
            elif c.credit_type == "remove":
                current_balance -= c.amount
        if amount > current_balance:
            return JSONResponse(content={
                "error": f"Cannot remove more credit than available. Current balance: ${current_balance:.2f}."
            }, status_code=400)
        credit = CustomerCredit(customer_id=customer_id, amount=amount, credit_type="remove", staff_name=staff_name, notes=notes or None)
        db.add(credit)
        db.flush()
        new_balance = current_balance - amount
        cname = customer.full_name
        db.commit()
    finally:
        db.close()
    log_change("customer", customer_id, f"Removed credit: ${amount:.2f} (new balance: ${new_balance:.2f})", staff_name)
    return JSONResponse(content={
        "status": "success",
        "balance": new_balance,
        "message": f"Removed ${amount:.2f} credit from {cname}."
    })
