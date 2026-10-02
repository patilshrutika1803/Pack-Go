import importlib
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from database import Base, Trip


def test_database_package_imports():
    import database

    assert hasattr(database, "Base")
    assert hasattr(database, "engine")
    assert hasattr(database, "SessionLocal")
    assert hasattr(database, "get_db")
    assert hasattr(database, "Trip")


def test_engine_creation_uses_configured_sqlite_database(tmp_path, monkeypatch):
    db_file = tmp_path / "engine_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    import database.connection as connection_module

    connection_module = importlib.reload(connection_module)

    assert connection_module.DATABASE_URL == db_url
    assert connection_module.engine is not None
    assert connection_module.SessionLocal.kw["bind"] is connection_module.engine


def test_trip_model_registration():
    assert "trips" in Base.metadata.tables


def test_database_session_creation(tmp_path, monkeypatch):
    db_file = tmp_path / "session_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    import database.connection as connection_module

    connection_module = importlib.reload(connection_module)
    session = connection_module.SessionLocal()

    assert session is not None
    assert session.bind is connection_module.engine
    session.close()


def test_alembic_upgrade_creates_trips_table(tmp_path, monkeypatch):
    db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    project_root = Path(__file__).resolve().parents[1]
    alembic_ini = project_root / "alembic.ini"

    assert alembic_ini.exists(), "alembic.ini must exist before running migration tests"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    assert "trips" in inspector.get_table_names()


def test_trip_crud_round_trip(tmp_path, monkeypatch):
    db_file = tmp_path / "crud_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    trip_id = str(uuid4())

    with SessionFactory() as session:
        trip = Trip(
            id=trip_id,
            title="Spring in Kyoto",
            destination="Kyoto, Japan",
            duration=7,
            total_budget=1800.0,
            budget_currency="INR",
            group_size=2,
            travel_style="balanced",
            travel_dates="2026-04-10 to 2026-04-17",
            interests=["temples", "food", "culture"],
            things_to_avoid=["crowded areas"],
            itinerary=[{"day": 1, "summary": "Arrival and temple walk"}],
            weather={"temperature_c": 22},
            budget_breakdown={"flight": 500},
            critic_review={"score": 9},
            revision_history=[{"step": "initial"}],
            data_freshness={"last_updated": "2026-09-09"},
            original_query="Plan a 7-day trip to Kyoto",
        )
        session.add(trip)
        session.commit()

        saved_trip = session.get(Trip, trip_id)
        assert saved_trip is not None
        assert saved_trip.destination == "Kyoto, Japan"

        saved_trip.title = "Spring in Kyoto - Updated"
        session.commit()

    with SessionFactory() as session:
        updated_trip = session.get(Trip, trip_id)
        assert updated_trip is not None
        assert updated_trip.title == "Spring in Kyoto - Updated"

        session.delete(updated_trip)
        session.commit()

    with SessionFactory() as session:
        deleted_trip = session.get(Trip, trip_id)
        assert deleted_trip is None
