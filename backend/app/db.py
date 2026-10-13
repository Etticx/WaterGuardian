from datetime import datetime, timezone
from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, Index, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    zone: Mapped[str]
    recording_id: Mapped[str]
    cursor: Mapped[int] = mapped_column(default=0)
    session_id: Mapped[str]
    status: Mapped[str] = mapped_column(default='model_pending')


class Reading(Base):
    __tablename__ = 'readings'
    __table_args__ = (UniqueConstraint('asset_id', 'session_id', 'sample_index'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    session_id: Mapped[str] = mapped_column(index=True)
    sample_index: Mapped[int]
    received_at: Mapped[str] = mapped_column(default=now)
    values: Mapped[dict] = mapped_column(JSON)
    prediction: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Incident(Base):
    __tablename__ = 'incidents'
    __table_args__ = (Index('one_active_incident_per_asset', 'asset_id', unique=True,
        sqlite_where=text("status IN ('investigating', 'pending_approval', 'approved', 'in_progress')")),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    status: Mapped[str] = mapped_column(default='investigating')
    classification: Mapped[str] = mapped_column(default='review')
    priority: Mapped[str] = mapped_column(default='medium')
    title: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSON)
    diagnosis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Crew(Base):
    __tablename__ = 'crews'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    skill: Mapped[str]
    zone: Mapped[str]
    available: Mapped[bool] = mapped_column(default=True)


class WorkOrder(Base):
    __tablename__ = 'work_orders'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), unique=True)
    asset_id: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)
    title: Mapped[str]
    instructions: Mapped[str] = mapped_column(Text)
    priority: Mapped[str]
    crew_id: Mapped[str | None] = mapped_column(ForeignKey('crews.id'), nullable=True)
    status: Mapped[str] = mapped_column(default='pending_approval')
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[str | None] = mapped_column(nullable=True)


class Activity(Base):
    __tablename__ = 'activity'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(default=now)
    incident_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    agent: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(nullable=True)


url = settings.database_url
if url.startswith('sqlite:///'):
    path = settings.path(url[len('sqlite:///'):])
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f'sqlite:///{path.as_posix()}'
engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite:') else {})
Session = sessionmaker(engine, expire_on_commit=False)
if url.startswith('sqlite:'):
    @event.listens_for(engine, 'connect')
    def setup_sqlite(connection, _):
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')


def log(agent: str, message: str, incident_id=None, provider=None):
    with Session.begin() as s:
        s.add(Activity(agent=agent, message=message, incident_id=incident_id, provider=provider))


def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

