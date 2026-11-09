---
sessionId: session-261109-144848-lq86
---

# Requirements

### Overview & Goals
Build a web-based preorder management system for trading card game stock. The program will track inventory, manage customer data, create orders that reserve stock, and send email receipts via Gmail API.

### Scope
**In Scope:**
- Web application with browser-based interface for creating and managing orders
- SQLite database for inventory and customer data persistence
- Inventory tracking with stock numbers to prevent overselling
- Customer database with name, phone number, and email
- Order creation that attaches stock items and updates inventory counts
- Gmail API (OAuth2) integration to send order receipts to customers

**Out of Scope:**
- Payment processing
- Multi-user authentication
- Supplier/order management for incoming stock
- Advanced inventory features (batch numbers, categories, etc.)

### User Stories
1. As a shop owner, I want to add products with stock quantities and prices so I can manage my inventory.
2. As a shop owner, I want to create a preorder for a customer with their name, phone, and email so I can track what they ordered.
3. As a shop owner, I want the system to automatically reduce available stock when an order is placed so I cannot oversell.
4. As a shop owner, I want the system to send a receipt email to the customer after an order is confirmed.
5. As a shop owner, I want to view current inventory levels and order history from the web interface.

### Functional Requirements
- **Inventory Management**: Add/edit/delete products with name, quantity, and price. View current stock levels.
- **Customer Management**: Store customer name, phone number, and email.
- **Order Management**: Create orders by selecting a customer and adding stock items. Automatically deduct stock. View order history.
- **Email Receipts**: Send a formatted receipt via Gmail after each order, including items, quantities, and total.
- **Oversell Protection**: Prevent ordering more stock than available.

### Non-Functional Requirements
- SQLite database for simplicity and zero-config deployment.
- Gmail OAuth2 for secure email integration.
- Responsive web interface accessible from any device on the network.

# Technical Design

### Current Implementation
The project is a blank Python project with only a default `main.py` placeholder. No existing code, database, or dependencies.

### Key Decisions
- **Framework**: FastAPI for the backend API — modern, async support, auto-generated docs, and lightweight.
- **Frontend**: Jinja2 templates with basic HTML/CSS — simple server-rendered pages, no build step required.
- **Database**: SQLite with SQLAlchemy ORM — file-based, no server setup, type-safe queries.
- **Email**: Gmail API via `google-auth` and `google-api-python-client` libraries with OAuth2 credentials.
- **Session Auth**: Simple session-based login for the admin (shop owner) to protect the management interface.

### Proposed Changes
1. **Project Structure**: Organize into a modular structure with separate modules for models, API routes, templates, and configuration.
2. **Database Models**: Define `Product`, `Customer`, and `Order` models with relationships (Order → OrderItem → Product).
3. **API Routes**: RESTful endpoints for inventory CRUD, customer management, order creation, and order history.
4. **Web UI**: Templates for dashboard, inventory management, customer list, order creation form, and order history.
5. **Email Service**: Gmail API integration to send HTML receipts with order details.
6. **Stock Protection**: Database-level checks to prevent overselling when creating orders.

### Data Models / Contracts

**Product**
- `id` (int, PK)
- `name` (string)
- `quantity` (int)
- `price` (float)

**Customer**
- `id` (int, PK)
- `name` (string)
- `phone` (string)
- `email` (string)

**Order**
- `id` (int, PK)
- `customer_id` (int, FK → Customer)
- `order_date` (datetime)
- `total` (float)

**OrderItem**
- `id` (int, PK)
- `order_id` (int, FK → Order)
- `product_id` (int, FK → Product)
- `quantity` (int)
- `unit_price` (float)

### File Structure
```
PythonProject/
├── main.py                 # FastAPI app entry point
├── config.py               # App configuration (Gmail credentials, DB path)
├── requirements.txt        # Python dependencies
├── database/
│   └── app.db              # SQLite database file (auto-created)
├── models/
│   ├── __init__.py
│   ├── base.py             # SQLAlchemy base and session setup
│   ├── product.py          # Product model
│   ├── customer.py         # Customer model
│   └── order.py            # Order and OrderItem models
├── services/
│   ├── __init__.py
│   ├── inventory.py        # Inventory management logic
│   ├── orders.py           # Order creation and stock deduction
│   └── email.py            # Gmail API email sending
├── api/
│   ├── __init__.py
│   ├── inventory.py        # Inventory API routes
│   ├── customers.py        # Customer API routes
│   └── orders.py           # Order API routes
└── templates/
    ├── base.html           # Base layout template
    ├── dashboard.html      # Main dashboard
    ├── inventory.html      # Inventory management
    ├── customers.html      # Customer list
    ├── new_order.html      # Order creation form
    └── orders.html         # Order history
```

### Architecture Diagram
``` mermaid
graph LR
    Browser[Browser] --> FastAPI[FastAPI App]
    FastAPI --> API[API Routes]
    FastAPI --> Templates[Jinja2 Templates]
    API --> Services[Services Layer]
    Services --> InventorySvc[Inventory Service]
    Services --> OrdersSvc[Orders Service]
    Services --> EmailSvc[Email Service]
    InventorySvc --> DB[(SQLite DB)]
    OrdersSvc --> DB
    EmailSvc --> Gmail[Gmail API]
```

### Risks
- **Gmail OAuth2 Setup**: Requires creating a Google Cloud project and downloading credentials. The user will need to follow setup steps.
- **Concurrent Orders**: SQLite may have locking issues with high concurrency. Acceptable for single-user shop management.
- **Email Delivery**: Gmail API has rate limits (approx. 100 emails/day for free accounts).

# Testing

### Validation Approach
The agent will validate the implementation by running the application and verifying each feature works end-to-end.

### Key Scenarios
1. **Inventory CRUD**: Add a product, view it in the list, edit quantity, and delete it.
2. **Customer Management**: Add a customer with name, phone, and email; verify it appears in the customer list.
3. **Order Creation**: Create an order for a customer with multiple products; verify stock is deducted correctly.
4. **Oversell Protection**: Attempt to order more stock than available; verify the system rejects the order.
5. **Email Receipt**: Place an order and verify a receipt email is sent (requires Gmail credentials configured).

### Edge Cases
- Ordering the last unit of stock (quantity goes to 0).
- Creating an order with no products (should be rejected).
- Customer without an email address (email should be skipped gracefully).
- Product deleted after being in an order (order history should still show the item).

# Delivery Steps

### ✓ Step 1: Set up project structure and database models
Establish the project foundation with FastAPI, SQLAlchemy, and all data models.
- Create `requirements.txt` with dependencies (FastAPI, uvicorn, SQLAlchemy, Jinja2, google-api-python-client, google-auth).
- Set up `config.py` for app configuration (database path, Gmail credentials).
- Create `models/base.py` with SQLAlchemy engine and session setup for SQLite.
- Implement `Product`, `Customer`, `Order`, and `OrderItem` models with proper relationships.
- Update `main.py` as the FastAPI application entry point with database initialization.

### ✓ Step 2: Implement inventory and customer management
Build the core inventory and customer CRUD functionality with API routes and web UI.
- Create `services/inventory.py` for product CRUD operations.
- Create API routes in `api/inventory.py` for managing products.
- Create API routes in `api/customers.py` for managing customers.
- Build Jinja2 templates: `base.html` layout, `dashboard.html`, `inventory.html`, and `customers.html`.
- Wire up the web UI so users can add, edit, and delete products and customers.

### ✓ Step 3: Implement order creation with stock protection
Add order management logic that creates orders and deducts stock, preventing overselling.
- Create `services/orders.py` with order creation logic and stock deduction.
- Implement oversell protection: check available stock before confirming an order.
- Create API routes in `api/orders.py` for creating orders and viewing order history.
- Build `new_order.html` template with a form to select a customer and add products with quantities.
- Build `orders.html` template to display order history with item details.
- Update `main.py` to register all API routers.

### ✓ Step 4: Integrate Gmail API for email receipts
Add Gmail OAuth2 integration to send order confirmation receipts to customers.
- Create `services/email.py` with Gmail API client and receipt sending logic.
- Implement OAuth2 flow for Gmail authentication (using `google-auth` library).
- Design an HTML receipt template with order details (customer info, items, quantities, total).
- Integrate email sending into the order creation flow — send receipt after a successful order.
- Add configuration in `config.py` for Gmail credentials path and sender email.
- Handle edge cases: skip email if customer has no email address, log errors gracefully.

### ✓ Step 5: Add order detail and edit page
Restructure order history into a summary list and add a fully editable order detail page with stock validation.
- Simplified `orders.html` to show only order number, date, customer name (as a link), and total.
- Created `order_detail.html` template with editable customer, products, quantities, and prices.
- Added real-time stock availability warnings in JavaScript when editing quantities.
- Added server-side stock validation before confirming order updates — blocks save if stock is insufficient.
- Added order deletion with automatic stock restoration.
- Added API routes: `GET /orders/{order_id}` (view/edit), `POST /orders/{order_id}` (update), `POST /orders/{order_id}/delete` (delete with stock restore).

### ✓ Step 6: Add product sets and category filter
Add a "Product Set" field to inventory items and a category filter on the orders page.
- Created `models/product_set.py`: New ProductSet model with id and name fields.
- Updated `models/product.py`: Added `product_set_id` foreign key and `product_set` relationship.
- Created `api/product_sets.py`: Full CRUD API routes for managing product sets.
- Created `templates/product_sets.html`: New product sets management page.
- Updated `api/inventory.py`: Products now accept `product_set_id` when adding/editing; inventory page loads product sets for the dropdown.
- Updated `templates/inventory.html`: Added product set dropdown when adding products, product set column in the table, and product set selector in the edit form.
- Updated `api/orders.py`: Added category filter parameter to order history endpoint.
- Updated `templates/orders.html`: Added category filter dropdown at the top of the orders list.
- Updated `main.py`: Registered product_sets router, added product set count to dashboard.
- Updated `templates/base.html`: Added "Product Sets" link to Management dropdown.
- Updated `templates/dashboard.html`: Added product set count stat card.
- Created `migrate.py`: Database migration script to add product_sets table and product_set_id column.

### ✓ Step 7: Make product sets subcategories of categories and add dark mode
Restructure Product Sets so each belongs to a parent Category, and add a dark mode toggle switch to the UI.
- Update `models/product_set.py`: Add `category_id` foreign key and `category` relationship to make product sets subcategories.
- Update `api/product_sets.py`: Product set creation/editing now requires a parent category; list view groups sets by category.
- Update `templates/product_sets.html`: Add category selector when adding/editing product sets, group display by parent category.
- Update `api/inventory.py`: When loading product sets for the dropdown, filter by selected category; cascade category → product set filtering.
- Update `templates/inventory.html`: Product set dropdown dynamically filters based on selected category via JavaScript.
- Update `templates/base.html`: Add dark mode CSS variables and toggle switch, store preference in localStorage.
- Update all templates to use CSS variables for colors so dark mode works across all pages.
- Create migration to add `category_id` column to `product_sets` table.

### ✓ Step 8: Split customer names and add finance, staff tracking, and audit logs
Add customer first/last name fields, finance tracking (deposits, balance, payments), staff member tracking, and audit logs with Melbourne timezone.
- Update `models/customer.py`: Replace `name` with `first_name` and `last_name` fields.
- Update `models/order.py`: Add `deposit` (float), `balance` (float), and `staff_name` (string) fields to Order.
- Create `models/payment.py`: New Payment model with order_id, amount, payment_type (cash/eftpos/other), staff_name, timestamp.
- Create `models/order_log.py`: New OrderLog model with order_id, action description, staff_name, timestamp.
- Update `api/customers.py`: All customer routes now use first_name and last_name instead of name.
- Update `api/orders.py`: Order creation and editing now accept deposit amount and staff_name; create audit log entries.
- Create `api/payments.py`: API routes for adding payments to orders and viewing payment history.
- Create `api/audit.py`: Admin page to view all order change logs.
- Update `templates/customers.html`: Split name into first_name and last_name fields.
- Update `templates/new_order.html`: Add deposit field, staff name field, update customer modal for first/last name.
- Update `templates/order_detail.html`: Add finance section showing deposit, balance, payment history with add payment form; add staff name field.
- Update `templates/orders.html`: Show balance column in order list.
- Create `templates/audit_log.html`: Admin page showing all order changes with timestamps.
- Update `templates/base.html`: Add "Audit Log" link to Management dropdown.
- Update `services/email.py`: Add payment receipt email function.
- Update `main.py`: Register new routers, add payment count to dashboard.
- Update `migrate.py`: Add all new columns and tables.

### ✓ Step 9: Add order pickup tracking
Add a "picked up" status to orders with visual indicators and quick-toggle functionality.
- Updated `models/order.py`: Added `picked_up` (boolean) field to track whether an order has been collected.
- Updated `api/orders.py`: Added `POST /orders/{order_id}/toggle-pickup` endpoint for AJAX pickup toggling with audit logging.
- Updated `api/orders.py`: Order history now sorts picked-up orders to the bottom of the list.
- Updated `api/orders.py`: Order edit now accepts `picked_up` checkbox value and logs status changes.
- Updated `templates/order_detail.html`: Added "Picked Up" checkbox with visual label in the order edit form.
- Updated `templates/orders.html`: Added "Status" column with color-coded badges (green "✓ Picked Up" / orange "Pending").
- Updated `templates/orders.html`: Added pickup toggle button (📦 Pickup / ↩ Undo) next to the View button for each order.
- Updated `templates/orders.html`: Picked-up orders display with reduced opacity to visually distinguish them.
- Updated `templates/orders.html`: Added `togglePickup()` JavaScript function for AJAX-based status updates with toast notifications.
- Updated `migrate.py`: Added migration for `picked_up` column with default value of 0 (False).

### ✓ Step 10: Make staff name required and fix live deposit update
Make staff name a required field on all entries and pages, and fix the live deposit update on order history.
- Updated `api/orders.py`: All endpoints (create_order, create_order_json, update_order, toggle_pickup, add_payment_to_order) now require `staff_name` with `Form(...)` and server-side validation.
- Updated `api/payments.py`: Both payment endpoints (add_payment, add_payment_json) now require `staff_name` with validation.
- Updated `templates/orders.html`: Added `required` attribute and asterisk to staff name inputs in both pickup and payment modals. Added JavaScript validation showing toast error when staff name is empty. Fixed live deposit/balance update to use `data-deposit` and `data-balance` attributes instead of fragile cell indices.
- Updated `templates/new_order.html`: Added `required` attribute and asterisk to staff name input.
- Updated `templates/order_detail.html`: Added `required` attribute and asterisk to both the order form staff name and the payment form staff name inputs.

### ✓ Step 11: Add per-item pickup tracking
Replace the single order-level pickup toggle with per-item pickup tracking so each item in an order can be individually marked as picked up.
- Updated `models/order.py`: Added `picked_up_quantity` field to OrderItem with `is_fully_picked_up` property. Added `pickup_progress` and `is_fully_picked_up` properties to Order.
- Updated `api/orders.py`: Replaced `toggle-pickup` endpoint with `update-item-pickup` async endpoint that accepts per-item pickup quantities. Updated `update_order` to recalculate `picked_up` from item-level status.
- Updated `templates/orders.html`: Status column now shows pickup progress (e.g., "1/3") with color-coded badges (green fully picked up, blue partial, orange pending). Pickup modal shows quantity inputs for each item with ✓/✗ quick-set buttons.
- Updated `templates/dashboard.html`: Same pickup progress badges and item-level pickup modal for Recent Orders.
- Updated `templates/order_detail.html`: Replaced "Picked Up" checkbox with pickup progress display.
- Updated `migrate.py`: Added migration for `picked_up_quantity` column in order_items table.

### ✓ Step 12: Add soft delete for orders with confirmation popup
Replace hard deletion with soft deletion so orders remain in the database and are searchable, with a confirmation popup requiring staff name.
- Updated `models/order.py`: Added `deleted` (boolean) field to track soft-deleted orders.
- Updated `api/orders.py`: Changed `delete_order` to soft-delete (set `deleted=True`) instead of removing from DB. Added `delete-json` AJAX endpoint for the confirmation modal. Added `restore` endpoint to restore soft-deleted orders and re-deduct stock. Updated order history to filter out deleted orders by default with a `show_deleted` query parameter.
- Updated `templates/order_detail.html`: Replaced the simple delete form with a confirmation modal that shows order details, requires staff name, and submits via AJAX.
- Updated `templates/orders.html`: Added "Show Deleted" toggle button in the filter section. Deleted orders show with reduced opacity, strikethrough text, and a "🗑 Deleted" badge. Added "↩ Restore" button for deleted orders. Added restore modal with staff name input.
- Updated `main.py`: Dashboard now filters out deleted orders from both the order count and recent orders list.
- Updated `migrate.py`: Added migration for `deleted` column with default value of 0 (False).

### ✓ Step 13: Add upcoming releases page
Add a page listing inventory products releasing within the next 4 weeks, based on the release date field.
- Updated `api/inventory.py`: Added `GET /upcoming-releases` endpoint that queries products with release dates between today and 4 weeks from now, sorted by date.
- Created `templates/upcoming_releases.html`: New page showing product name, category, subcategory, release date, days away, stock quantity, and price. Shows "Today!" and "Tomorrow" labels for imminent releases.
- Updated `main.py`: Added upcoming release count query to the dashboard.
- Updated `templates/dashboard.html`: Added "Upcoming Releases" stat card with a link to the new page.
- Updated `templates/base.html`: Added "Upcoming Releases" link to the Management dropdown.

### ✓ Step 14: Replace product sets with subcategories
Replace the Product Sets system with a Subcategories system integrated into the Categories page.
- Created `models/subcategory.py`: New Subcategory model with id, name, category_id, and relationships to Category and Product.
- Updated `models/product.py`: Replaced `product_set_id` with `subcategory_id` and `product_set` relationship with `subcategory`.
- Created `api/subcategories.py`: Full CRUD API routes for managing subcategories, including JSON endpoint for modal-based creation.
- Created `templates/subcategories.html`: New subcategories management page.
- Updated `api/inventory.py`: Products now accept `subcategory_id` when adding/editing; inventory page loads subcategories for the dropdown.
- Updated `templates/inventory.html`: Added subcategory dropdown when adding products, subcategory column in the table, and subcategory selector in the edit form.
- Updated `api/orders.py`: All order routes now use subcategories instead of product sets.
- Updated `templates/new_order.html`, `order_detail.html`, `orders.html`, `dashboard.html`, `upcoming_releases.html`: All product displays now show subcategory instead of product set.
- Updated `api/categories.py`: Categories now eager-load subcategories with their products.
- Updated `templates/categories.html`: Added subcategory section under each category with inline edit/delete and "Add Subcategory" modal.
- Updated `main.py`: Registered subcategories router, replaced product_set_count with subcategory_count.
- Updated `templates/base.html`: Replaced "Product Sets" link with "Subcategories" in Management dropdown.
- Updated `migrate.py`: Migration script now migrates product_sets data to subcategories and product_set_id to subcategory_id.

### ✓ Step 15: Add settings page with store details, logo upload, and color scheme
Add a Settings page for configuring store details, uploading a store logo, and customizing the website color scheme.
- Created `models/store_settings.py`: New StoreSettings model with store name, address, contact number, email, website, logo path, and 8 color scheme fields.
- Created `api/settings.py`: API routes for viewing/editing settings, logo upload, logo removal, color reset, and JSON endpoint.
- Created `templates/settings.html`: Settings page with store details form, logo upload with preview, color pickers for 8 colors, reset button, and live preview section.
- Updated `main.py`: Registered settings router, added static file serving for uploaded logos, injected store settings into all templates via patched TemplateResponse.
- Updated `templates/base.html`: Store name and logo displayed in navigation bar, custom color scheme applied as CSS variable overrides, "Settings" link added to Management dropdown.
- Updated `migrate.py`: Migration script creates store_settings table.

### ✓ Step 16: Comprehensive audit logging for all app changes
Expand the audit log system to capture all changes made within the app, not just order-related changes.
- Created `models/audit_log.py`: New AuditLog model with entity_type, entity_id, action, staff_name, and timestamp fields.
- Created `services/audit.py`: Generic `log_change()` function for logging any entity change.
- Updated `api/inventory.py`: All product endpoints (add, edit, delete) now log changes with staff name.
- Updated `api/customers.py`: All customer endpoints (add, edit, delete, bulk-delete) now log changes with staff name.
- Updated `api/categories.py`: All category endpoints (add, edit, delete) now log changes with staff name.
- Updated `api/subcategories.py`: All subcategory endpoints (add, edit, delete) now log changes with staff name.
- Updated `api/settings.py`: Settings changes (update, remove logo, reset colors) now logged.
- Updated `api/audit.py`: Combined OrderLog and AuditLog into a single unified view sorted by timestamp.
- Updated `templates/audit_log.html`: New unified audit log page with entity type badges (Order/Product/Customer/Category/Subcategory/Settings), entity links, customer column, and search across all entity types.
- Updated `templates/inventory.html`: Added staff name fields to Add/Edit modals and delete confirmation.
- Updated `templates/customers.html`: Added staff name field to add customer form, edit modal, and delete confirmation.
- Updated `templates/categories.html`: Added staff name field to add category form, inline edit/delete buttons, and subcategory modal.
- Updated `templates/subcategories.html`: Added staff name field to add subcategory form and inline edit/delete buttons.
- Updated `templates/new_order.html`: Added staff name field to new customer modal.
- Updated `migrate.py`: Creates audit_logs table for existing databases.

### ✓ Step 17: Add database backup system with local and Google Drive storage
Add a backup system to keep 5 copies of the database, stored either locally or on Google Drive, configurable from Settings.
- Update `models/store_settings.py`: Add backup fields: backup_enabled (bool), backup_storage (local/google_drive), backup_schedule (hourly/daily/weekly), backup_google_folder_id (string), backup_last_run (datetime), backup_google_token_path (string).
- Create `services/backup.py`: Backup service with functions to create local backups, upload to Google Drive, manage backup rotation (keep 5 latest), and list existing backups.
- Create `api/backups.py`: API routes for triggering manual backup, listing backups, deleting backups, connecting Google Drive, and testing connection.
- Update `templates/settings.html`: Add backup configuration section with enable toggle, storage type selector, schedule picker, Google Drive folder ID input, connect/disconnect buttons, last backup status, and manual backup button.
- Update `api/settings.py`: Handle backup settings in the update_settings endpoint.
- Update `main.py`: Register backups router, add backup settings to template context, start background backup scheduler thread.
- Update `migrate.py`: Add backup columns to store_settings table.
- Update `requirements.txt`: Add `google-api-python-client` (already present) for Google Drive API.
- Create backup directory structure: `backups/local/` for local backups.

### ✓ Step 18: Add restore from backup functionality
Add a "Restore" button to each backup entry (local and Google Drive) to restore the database from a previous backup.
- Updated `services/backup.py`: Added `restore_local_backup()` function that copies a local backup over the current database.
- Updated `services/backup.py`: Added `restore_google_drive_backup()` function that downloads a backup from Google Drive and replaces the current database.
- Updated `api/backups.py`: Added `POST /backups/restore-local` endpoint with staff name validation and audit logging.
- Updated `api/backups.py`: Added `POST /backups/restore-google` endpoint with staff name validation and audit logging.
- Updated `templates/backups.html`: Added "Restore" button next to each backup entry (both local and Google Drive).
- Updated `templates/backups.html`: Added restore confirmation modal with warning message, backup details display, staff name input, and AJAX submission.
- Updated `templates/backups.html`: Added JavaScript functions `openRestoreModal()`, `closeRestoreModal()`, and `restoreBackup()` for modal handling and API calls.

### ✓ Step 19: Fix email receipts not sending
Fix email receipts not being sent when creating orders or adding payments by making the Gmail sender email configurable from Settings.
- Updated `models/store_settings.py`: Added `gmail_sender_email` field to store the sender email address.
- Updated `services/email.py`: Added `get_sender_email()` function that checks both the environment variable and store settings. Updated `send_order_receipt()` and `send_payment_receipt()` to use `get_sender_email()` instead of `config.GMAIL_SENDER_EMAIL`. Updated `build_payment_receipt_html()` to use store name, address, and contact from Settings.
- Updated `api/settings.py`: Added `gmail_sender_email` to the settings form and save endpoint.
- Updated `templates/settings.html`: Added "Email Sender" section with sender email input field.
- Fixed `api/orders.py`: Changed `send_payment_receipt(payment, order, customer)` to `send_payment_receipt(payment, order, db)` — the function signature expects `(payment, order, db)`, not `(payment, order, customer)`.
- Updated `migrate.py`: Added `gmail_sender_email` column migration for existing databases.

### ✓ Step 20: Add customer credit system
Add a credit system for customers with tracking of credit balance and transactions.
- Create `models/customer_credit.py`: New CustomerCredit model with customer_id, amount, type (add/remove), staff_name, and timestamp.
- Update `api/customers.py`: Add endpoints for viewing customer credit balance, adding credit, and removing credit with JSON responses for modal-based interactions.
- Update `templates/customers.html`: Add "Credit" button in Actions column for each customer. Add credit modal showing current balance, credit history, and buttons to add/remove credit with amount input and staff name.
- Update `migrate.py`: Create customer_credits table.

### ✓ Step 21: Add backup schedule time and day of week configuration
Add time-of-day picker for daily backups and day-of-week selector for weekly backups.
- Updated `models/store_settings.py`: Added `backup_time` (HH:MM string, default "02:00") and `backup_weekday` (string, default "monday") fields.
- Updated `main.py`: Backup scheduler now checks the configured time for daily backups and both day and time for weekly backups.
- Updated `templates/backups.html`: Added "Time of Day" input and "Day of Week" dropdown with JavaScript to show/hide based on schedule type.
- Updated `api/backups.py`: Settings update endpoint now accepts and saves `backup_time` and `backup_weekday`.
- Updated `migrate.py`: Added migration for `backup_time` and `backup_weekday` columns.