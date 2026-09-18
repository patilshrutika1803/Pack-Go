from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Trip, TripInvitation, TripMember, User
from services.collaboration_service import GroupTripService, token_digest


def test_failed_invitation_acceptance_rolls_back_membership_and_status(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    owner = User(id=str(uuid4()), name="Owner", email=f"owner-{uuid4()}@example.com", password_hash="hash")
    invitee = User(id=str(uuid4()), name="Invitee", email=f"invitee-{uuid4()}@example.com", password_hash="hash")
    trip = Trip(id=str(uuid4()), user_id=owner.id, title="Rollback", destination="Goa", duration=2, total_budget=500, budget_currency="INR", group_size=2, travel_style="balanced", interests=[], things_to_avoid=[], itinerary=[], revision_history=[], data_freshness={})
    raw = "rollback-token"
    invitation = TripInvitation(id=str(uuid4()), trip_id=trip.id, inviter_user_id=owner.id, invitee_user_id=invitee.id, token_hash=token_digest(raw), status="pending", expires_at=datetime.now(UTC) + timedelta(days=1))
    with Session() as db:
        db.add_all([owner, invitee, trip, invitation, TripMember(id=str(uuid4()), trip_id=trip.id, user_id=owner.id, role="owner", status="active")])
        db.commit()
        original_commit = db.commit

        def fail_commit():
            raise SQLAlchemyError("forced commit failure")

        db.commit = fail_commit
        with pytest.raises(SQLAlchemyError):
            GroupTripService(db).accept(raw, invitee)
        db.commit = original_commit
        db.rollback()
        stored_invitation = db.get(TripInvitation, invitation.id)
        memberships = db.scalars(select(TripMember).where(TripMember.trip_id == trip.id, TripMember.user_id == invitee.id)).all()

    assert stored_invitation.status == "pending"
    assert memberships == []
