from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from models.base import SessionLocal
from models.order import Order, OrderItem
from models.customer import Customer
from models.payment import Payment
from models.order_log import OrderLog
from models.product import Product
from models.category import Category
from models.subcategory import Subcategory
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


def get_melbourne_time():
    """Get current time in Melbourne, Australia timezone."""
    from datetime import datetime, timezone, timedelta
    # Melbourne is UTC+10 (AEST) or UTC+11 (AEDT during DST)
    # Check if DST is in effect (first Sunday in October to first Sunday in April)
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    # First Sunday in October
    import calendar
    oct_cal = calendar.monthcalendar(year, 10)
    first_sun_oct = datetime(year, 10, oct_cal[0][6] if oct_cal[0][6] else oct_cal[1][6], tzinfo=timezone.utc)
    # First Sunday in April
    apr_cal = calendar.monthcalendar(year, 4)
    first_sun_apr = datetime(year, 4, apr_cal[0][6] if apr_cal[0][6] else apr_cal[1][6], tzinfo=timezone.utc)
    
    if first_sun_oct <= now_utc < first_sun_apr:
        # AEDT (Daylight Saving)
        return now_utc.astimezone(timezone(timedelta(hours=11)))
    else:
        # AEST (Standard)
        return now_utc.astimezone(timezone(timedelta(hours=10)))


@router.post("/orders/{order_id}/payment")
def add_payment(
    request: Request,
    order_id: int,
    amount: float = Form(...),
    payment_type: str = Form(...),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        order = (
            db.query(Order)
            .options(joinedload(Order.customer))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return RedirectResponse(url="/orders", status_code=303)

        # Prevent overpayment: don't allow more money than the outstanding balance
        balance = order.total - order.deposit
        if amount > balance + 0.01:
            return templates.TemplateResponse("order_detail.html", {
                "request": request,
                "order": order,
                "error": f"Payment exceeds the outstanding balance of ${balance:.2f}.",
            })

        # Create payment record
        payment = Payment(
            order_id=order_id,
            amount=amount,
            payment_type=payment_type,
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(payment)

        # Update order deposit
        order.deposit += amount
        order.staff_name = staff_name or order.staff_name

        # Log the payment
        log = OrderLog(
            order_id=order_id,
            action=f"Payment of ${amount:.2f} received ({payment_type})",
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        db.commit()

        # Send payment receipt email
        try:
            from services.email import send_payment_receipt
            if order.customer and order.customer.email:
                send_payment_receipt(payment, order, db)
        except Exception as e:
            print(f"Failed to send payment receipt: {e}")

        return RedirectResponse(url=f"/orders/{order_id}", status_code=303)

    except Exception as e:
        db.rollback()
        print(f"Error adding payment: {e}")
    finally:
        db.close()

    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)


@router.post("/payments/{payment_id}/refund")
async def refund_payment(
    request: Request,
    payment_id: int,
):
    db = SessionLocal()
    try:
        form_data = await request.form()
        staff_name = form_data.get('staff_name', '').strip()
        reason = form_data.get('reason', '').strip()
        
        if not staff_name:
            return JSONResponse(content={"error": "Staff name is required."}, status_code=400)
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return JSONResponse(content={"error": "Payment not found"}, status_code=404)

        order = (
            db.query(Order)
            .options(joinedload(Order.customer))
            .filter(Order.id == payment.order_id).first()
        )
        if not order:
            return JSONResponse(content={"error": "Order not found"}, status_code=404)

        payment_amount = payment.amount

        # Log the refund before deleting
        action_text = f"Refund of ${payment_amount:.2f} ({payment.payment_type}) - Payment deleted"
        if reason:
            action_text += f"\nReason: {reason}"
        log = OrderLog(
            order_id=payment.order_id,
            action=action_text,
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        # Reduce order deposit
        order.deposit -= payment_amount
        if order.deposit < 0:
            order.deposit = 0.0

        # Delete the payment record
        db.delete(payment)

        db.commit()

        return JSONResponse(content={
            "status": "success",
            "message": f"Refund of ${payment_amount:.2f} processed.",
            "new_deposit": order.deposit,
            "new_balance": order.balance,
        })

    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/orders/{order_id}/payment-json")
def add_payment_json(
    request: Request,
    order_id: int,
    amount: float = Form(...),
    payment_type: str = Form(...),
    staff_name: str = Form(""),
):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        order = (
            db.query(Order)
            .options(joinedload(Order.customer))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return JSONResponse(content={"error": "Order not found"}, status_code=404)

        # Prevent overpayment: don't allow more money than the outstanding balance
        balance = order.total - order.deposit
        if amount > balance + 0.01:
            return JSONResponse(content={"error": f"Payment exceeds the outstanding balance of ${balance:.2f}."}, status_code=400)

        # Create payment record
        payment = Payment(
            order_id=order_id,
            amount=amount,
            payment_type=payment_type,
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(payment)
        db.flush()
        db.refresh(payment)

        # Update order deposit
        order.deposit += amount
        order.staff_name = staff_name or order.staff_name

        # Log the payment
        log = OrderLog(
            order_id=order_id,
            action=f"Payment of ${amount:.2f} received ({payment_type})",
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        db.commit()

        # Send payment receipt email
        try:
            from services.email import send_payment_receipt
            if order.customer and order.customer.email:
                send_payment_receipt(payment, order, db)
        except Exception as e:
            print(f"Failed to send payment receipt: {e}")

        return JSONResponse(content={
            "payment_id": payment.id,
            "amount": payment.amount,
            "payment_type": payment.payment_type,
            "new_deposit": order.deposit,
            "new_balance": order.balance,
        }, status_code=201)

    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()
