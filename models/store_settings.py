from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from models.base import Base


class StoreSettings(Base):
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_name = Column(String, nullable=True, default=None)
    address = Column(String, nullable=True, default=None)
    contact_number = Column(String, nullable=True, default=None)
    email = Column(String, nullable=True, default=None)
    website = Column(String, nullable=True, default=None)
    abn = Column(String, nullable=True, default=None)
    logo_path = Column(String, nullable=True, default=None)
    gmail_sender_email = Column(String, nullable=True, default=None)
    # Color scheme
    primary_color = Column(String, nullable=True, default="#3b82f6")
    secondary_color = Column(String, nullable=True, default="#6b7280")
    background_color = Column(String, nullable=True, default="#f9fafb")
    text_color = Column(String, nullable=True, default="#111827")
    nav_bg_color = Column(String, nullable=True, default="#1e293b")
    nav_text_color = Column(String, nullable=True, default="#f8fafc")
    card_bg_color = Column(String, nullable=True, default="#ffffff")
    border_color = Column(String, nullable=True, default="#e5e7eb")
    # Backup settings
    backup_enabled = Column(Boolean, nullable=True, default=False)
    backup_storage = Column(String, nullable=True, default="local")  # "local" or "google_drive"
    backup_schedule = Column(String, nullable=True, default="daily")  # "hourly", "daily", "weekly"
    backup_time = Column(String, nullable=True, default="02:00")  # Time of day for daily/weekly backups (HH:MM)
    backup_weekday = Column(String, nullable=True, default="monday")  # Day of week for weekly backups
    backup_google_folder_id = Column(String, nullable=True, default=None)
    backup_google_token_path = Column(String, nullable=True, default=None)
    backup_last_run = Column(DateTime, nullable=True, default=None)
    backup_last_status = Column(String, nullable=True, default=None)  # "success", "error", "pending"
    backup_last_message = Column(String, nullable=True, default=None)
    # System settings
    app_port = Column(Integer, nullable=True, default=8000)  # Port the app runs on
    logo_size = Column(Integer, nullable=True, default=40)  # Header logo size in pixels (max-height), max 80

    @classmethod
    def get(cls, db):
        """Get the single settings row, creating it if it doesn't exist."""
        settings = db.query(cls).first()
        if not settings:
            settings = cls()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings
