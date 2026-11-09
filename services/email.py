import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from models.order import Order
from models.payment import Payment

import config

logger = logging.getLogger(__name__)


def get_gmail_service():
    """Get authenticated Gmail API service using stored token."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    credentials = None

    # Load stored token
    if Path(config.GMAIL_TOKEN_FILE).exists():
        try:
            credentials = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_FILE, SCOPES)
        except Exception:
            # Try loading without scopes (token may have been saved differently)
            try:
                import json
                with open(config.GMAIL_TOKEN_FILE, "r") as f:
                    token_data = json.load(f)
                credentials = Credentials(
                    token=token_data.get("token", ""),
                    refresh_token=token_data.get("refresh_token"),
                    token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                    client_id=token_data.get("client_id"),
                    client_secret=token_data.get("client_secret"),
                    scopes=SCOPES,
                )
            except Exception:
                credentials = None

    # Refresh expired credentials
    if credentials:
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    # Save refreshed credentials
                    with open(config.GMAIL_TOKEN_FILE, "w") as token_file:
                        import json
                        json.dump({
                            "token": credentials.token,
                            "refresh_token": credentials.refresh_token,
                            "token_uri": credentials.token_uri,
                            "client_id": credentials.client_id,
                            "client_secret": credentials.client_secret,
                            "scopes": credentials.scopes,
                        }, token_file)
                except Exception:
                    credentials = None

    if not credentials or not credentials.valid:
        logger.warning("Gmail not authenticated. Use /gmail/connect to authorize first.")
        return None

    return build("gmail", "v1", credentials=credentials)


def get_sender_email() -> str:
    """Get the Gmail sender email from store settings, falling back to config."""
    # First check environment variable
    if config.GMAIL_SENDER_EMAIL:
        return config.GMAIL_SENDER_EMAIL
    
    # Then check store settings
    from models.store_settings import StoreSettings
    from models.base import SessionLocal
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.gmail_sender_email:
            return settings.gmail_sender_email
    finally:
        db.close()
    
    return ""


def build_receipt_html(order: Order) -> str:
    """Build an HTML receipt for an order."""
    from models.store_settings import StoreSettings
    from models.base import SessionLocal

    order_date = order.order_date.strftime("%Y-%m-%d %H:%M") if order.order_date else "N/A"
    customer_name = order.customer.full_name if order.customer else "Customer"

    # Get store details for the receipt
    store_name = "TCG Preorder Manager"
    store_address = ""
    store_contact = ""
    store_abn = ""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.store_name:
            store_name = settings.store_name
        store_address = settings.address or ""
        store_contact = settings.contact_number or ""
        store_abn = settings.abn or ""
    finally:
        db.close()

    items_html = ""
    for item in order.items:
        product_name = item.product.name if item.product else "Unknown"
        subtotal = item.quantity * item.unit_price
        items_html += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{product_name}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{item.quantity}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${item.unit_price:.2f}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${subtotal:.2f}</td>
        </tr>"""

    balance = order.total - order.deposit

    store_info = ""
    if store_address or store_contact or store_abn:
        parts = []
        if store_address:
            parts.append(f"📍 {store_address}")
        if store_contact:
            parts.append(f"📞 {store_contact}")
        if store_abn:
            parts.append(f"🏢 ABN: {store_abn}")
        store_info = f'<p style="color: #7f8c8d; font-size: 0.85rem; margin-top: 0.5rem;">{" | ".join(parts)}</p>'

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">{store_name}</h2>
        <h3 style="color: #34495e; margin-top: 0;">Order Confirmation</h3>
        <p>Thank you for your preorder, <strong>{customer_name}</strong>!</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Product</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Qty</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: right;">Price</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: right;">Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
        
        <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
            <tr><td style="padding: 8px;"><strong>Total:</strong></td><td style="padding: 8px; text-align: right;">${order.total:.2f}</td></tr>
            <tr><td style="padding: 8px;"><strong>Deposit Paid:</strong></td><td style="padding: 8px; text-align: right;">${order.deposit:.2f}</td></tr>
            <tr style="background: #f8f9fa;"><td style="padding: 8px;"><strong>Balance Remaining:</strong></td><td style="padding: 8px; text-align: right;">${balance:.2f}</td></tr>
        </table>
        
        <p style="color: #7f8c8d; font-size: 0.9rem;">Order #{order.id} | {order_date}</p>
        <hr style="border: 1px solid #eee; margin: 1rem 0;">
        {store_info}
        <p style="color: #7f8c8d; font-size: 0.85rem;">This is an automated message from {store_name}.</p>
    </body>
    </html>
    """


def send_order_receipt(order: Order, db: Session) -> bool:
    """Send an order receipt email to the customer."""
    if not order.customer or not order.customer.email:
        logger.info(f"Skipping email for order {order.id}: no customer email.")
        return False

    sender_email = get_sender_email()
    if not sender_email:
        logger.warning("Gmail sender email not configured. Set it in Settings or GMAIL_SENDER_EMAIL env var.")
        return False

    service = get_gmail_service()
    if service is None:
        logger.warning("Gmail service not available. Skipping email.")
        return False

    from email.mime.text import MIMEText
    import base64

    subject = f"Order Confirmation #{order.id}"
    html_body = build_receipt_html(order)

    message = MIMEText(html_body, "html")
    message["to"] = order.customer.email
    message["from"] = sender_email
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()
        logger.info(f"Receipt sent to {order.customer.email} for order {order.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send receipt for order {order.id}: {e}")
        return False


def build_payment_receipt_html(payment: Payment, order: Order) -> str:
    """Build an HTML receipt for a payment."""
    from models.store_settings import StoreSettings
    from models.base import SessionLocal

    payment_time = payment.timestamp.strftime("%Y-%m-%d %H:%M") if payment.timestamp else "N/A"
    customer_name = order.customer.full_name if order.customer else "Customer"
    balance = order.total - order.deposit

    # Get store details
    store_name = "TCG Preorder Manager"
    store_address = ""
    store_contact = ""
    store_abn = ""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.store_name:
            store_name = settings.store_name
        store_address = settings.address or ""
        store_contact = settings.contact_number or ""
        store_abn = settings.abn or ""
    finally:
        db.close()

    store_info = ""
    if store_address or store_contact or store_abn:
        parts = []
        if store_address:
            parts.append(f"📍 {store_address}")
        if store_contact:
            parts.append(f"📞 {store_contact}")
        if store_abn:
            parts.append(f"🏢 ABN: {store_abn}")
        store_info = f'<p style="color: #7f8c8d; font-size: 0.85rem; margin-top: 0.5rem;">{" | ".join(parts)}</p>'

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">{store_name}</h2>
        <h3 style="color: #34495e; margin-top: 0;">Payment Receipt</h3>
        <p>Thank you for your payment, <strong>{customer_name}</strong>!</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
            <tr><td style="padding: 8px;"><strong>Order:</strong></td><td style="padding: 8px; text-align: right;">#{order.id}</td></tr>
            <tr><td style="padding: 8px;"><strong>Payment Amount:</strong></td><td style="padding: 8px; text-align: right;">${payment.amount:.2f}</td></tr>
            <tr><td style="padding: 8px;"><strong>Payment Method:</strong></td><td style="padding: 8px; text-align: right;">{payment.payment_type.capitalize()}</td></tr>
            <tr><td style="padding: 8px;"><strong>Date:</strong></td><td style="padding: 8px; text-align: right;">{payment_time}</td></tr>
        </table>
        
        <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
            <tr><td style="padding: 8px;"><strong>Order Total:</strong></td><td style="padding: 8px; text-align: right;">${order.total:.2f}</td></tr>
            <tr><td style="padding: 8px;"><strong>Total Paid:</strong></td><td style="padding: 8px; text-align: right;">${order.deposit:.2f}</td></tr>
            <tr style="background: #f8f9fa;"><td style="padding: 8px;"><strong>Balance Remaining:</strong></td><td style="padding: 8px; text-align: right;">${balance:.2f}</td></tr>
        </table>
        
        <hr style="border: 1px solid #eee; margin: 1rem 0;">
        {store_info}
        <p style="color: #7f8c8d; font-size: 0.85rem;">This is an automated message from {store_name}.</p>
    </body>
    </html>
    """


def send_payment_receipt(payment: Payment, order: Order, db: Session) -> bool:
    """Send a payment receipt email to the customer."""
    if not order.customer or not order.customer.email:
        logger.info(f"Skipping payment receipt for order {order.id}: no customer email.")
        return False

    sender_email = get_sender_email()
    if not sender_email:
        logger.warning("Gmail sender email not configured. Set it in Settings or GMAIL_SENDER_EMAIL env var.")
        return False

    service = get_gmail_service()
    if service is None:
        logger.warning("Gmail service not available. Skipping email.")
        return False

    from email.mime.text import MIMEText
    import base64

    subject = f"Payment Receipt - Order #{order.id}"
    html_body = build_payment_receipt_html(payment, order)

    message = MIMEText(html_body, "html")
    message["to"] = order.customer.email
    message["from"] = sender_email
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()
        logger.info(f"Payment receipt sent to {order.customer.email} for order {order.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send payment receipt for order {order.id}: {e}")
        return False
