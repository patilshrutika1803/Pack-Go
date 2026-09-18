from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Trip, TripMember, User
from services.collaboration_service import GroupTripService


def test_concurrent_ownership_transfers_leave_one_owner(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ownership.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    owner = User(id=str(uuid4()), name="Owner", email=f"owner-{uuid4()}@example.com", password_hash="hash")
    first = User(id=str(uuid4()), name="First", email=f"first-{uuid4()}@example.com", password_hash="hash")
    second = User(id=str(uuid4()), name="Second", email=f"second-{uuid4()}@example.com", password_hash="hash")
    trip = Trip(id=str(uuid4()), user_id=owner.id, title="Transfer", destination="Goa", duration=2, total_budget=500, budget_currency="INR", group_size=3, travel_style="balanced", interests=[], things_to_avoid=[], itinerary=[], revision_history=[], data_freshness={})
    with Session() as db:
        db.add_all([owner, first, second, trip, TripMember(id=str(uuid4()), trip_id=trip.id, user_id=owner.id, role="owner", status="active"), TripMember(id=str(uuid4()), trip_id=trip.id, user_id=first.id, role="member", status="active"), TripMember(id=str(uuid4()), trip_id=trip.id, user_id=second.id, role="member", status="active")])
        db.commit()

    def transfer(target_id):
        try:
            with Session() as db:
                GroupTripService(db).transfer_ownership(trip.id, owner.id, target_id)
                return "transferred"
        except (IntegrityError, OperationalError, ValueError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(transfer, [first.id, second.id]))
    with Session() as db:
        owners = db.scalars(select(TripMember).where(TripMember.trip_id == trip.id, TripMember.role == "owner", TripMember.status == "active")).all()
        stored_trip = db.get(Trip, trip.id)
    assert len(owners) == 1
    assert stored_trip.user_id == owners[0].user_id
