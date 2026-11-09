from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from models.base import SessionLocal
from models.order_log import OrderLog
from models.audit_log import AuditLog
from models.order import Order
from models.customer import Customer

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


@router.get("/audit-log")
def audit_log_page(request: Request, search: str = ""):
    db = SessionLocal()
    try:
        # Get order logs with customer info
        order_query = (
            db.query(OrderLog, Customer)
            .outerjoin(Order, OrderLog.order_id == Order.id)
            .outerjoin(Customer, Order.customer_id == Customer.id)
        )
        # Get general audit logs
        audit_query = db.query(AuditLog)
        
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            order_query = order_query.filter(
                OrderLog.action.ilike(search_term)
                | OrderLog.staff_name.ilike(search_term)
                | Customer.first_name.ilike(search_term)
                | Customer.last_name.ilike(search_term)
                | Customer.phone.ilike(search_term)
            )
            audit_query = audit_query.filter(
                AuditLog.action.ilike(search_term)
                | AuditLog.staff_name.ilike(search_term)
                | AuditLog.entity_type.ilike(search_term)
            )
        
        order_results = order_query.order_by(OrderLog.timestamp.desc()).all()
        audit_results = audit_query.order_by(AuditLog.timestamp.desc()).all()
        
        # Combine all logs into a single list
        logs = []
        for log, customer in order_results:
            entry = {
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "staff_name": log.staff_name,
                "entity_type": "order",
                "entity_id": log.order_id,
                "customer": customer,
            }
            logs.append(entry)
        
        for log in audit_results:
            entry = {
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "staff_name": log.staff_name,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "customer": None,
            }
            logs.append(entry)
        
        # Sort all logs by timestamp, newest first
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
    finally:
        db.close()
    return templates.TemplateResponse("audit_log.html", {
        "request": request,
        "logs": logs,
        "search": search,
    })
