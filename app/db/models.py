"""SQLAlchemy ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Use dialect-agnostic types so unit tests can run against SQLite as well as Postgres.
try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    _UUID = PG_UUID(as_uuid=True)
except Exception:  # pragma: no cover
    _UUID = String(36)  # type: ignore[assignment]

# Always use plain JSON (not JSONB) so SQLite unit tests work.
_JSONB = JSON


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["ChatSessionModel"]] = relationship("ChatSessionModel", back_populates="user", lazy="dynamic")


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(_UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(64), default="reception", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["UserModel | None"] = relationship("UserModel", back_populates="sessions")
    messages: Mapped[list["ChatMessageModel"]] = relationship("ChatMessageModel", back_populates="session", cascade="all, delete-orphan", lazy="dynamic")


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["ChatSessionModel"] = relationship("ChatSessionModel", back_populates="messages")


class EscalationModel(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(_UUID, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department: Mapped[str] = mapped_column(String(64), default="reception", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[dict] = mapped_column(_JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class PlatformSecretModel(Base):
    """Stores runtime API keys / secrets saved through the Settings UI."""
    __tablename__ = "platform_secrets"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CompanySettingsModel(Base):
    """Per-tenant company branding and per-agent persona overrides."""
    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), default="AlgoWorkforce", nullable=False)
    company_tagline: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    company_website: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    greeting_script: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agent_overrides: Mapped[dict] = mapped_column(_JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TenantModel(Base):
    """Organisation / company that uses the platform (multi-tenant)."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="starter", nullable=False)  # free|starter|pro|enterprise
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    max_users: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_chat_sessions: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    max_voice_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    settings: Mapped[dict] = mapped_column(_JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantUsageModel(Base):
    """Daily usage snapshot per tenant — for billing and analytics."""
    __tablename__ = "tenant_usage"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    chat_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chat_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    voice_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    voice_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_users: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    knowledge_uploads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SystemAlertModel(Base):
    """Persisted system alert history — fired when metric thresholds are breached."""
    __tablename__ = "system_alerts"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)   # info | warning | critical
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    threshold: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class BillingSubscriptionModel(Base):
    """Billing subscription per tenant — Stripe-ready, works without Stripe too."""
    __tablename__ = "billing_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Stripe fields (all optional — populated when Stripe is connected)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Subscription state
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    # active | trialing | past_due | canceled | unpaid | paused
    billing_cycle: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False)
    # monthly | annual
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 0 for free plan; amount in cents (e.g. 4900 = $49.00)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BillingInvoiceModel(Base):
    """Invoice records per tenant — synced from Stripe or created manually."""
    __tablename__ = "billing_invoices"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g. INV-2024-001
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    # draft | open | paid | void | uncollectible
    amount_due_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_paid_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_items: Mapped[list] = mapped_column(_JSONB, default=list, nullable=False)
    # [{"description": "Pro plan", "amount_cents": 4900, "quantity": 1}]
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", _JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
