from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Decision, Proposal, ProposalVote, Trip, TripMember, User
from services.collaboration_service import ProposalService


@pytest.fixture
def proposal_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'proposal.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    owner = User(id=str(uuid4()), name="Owner", email=f"owner-{uuid4()}@example.com", password_hash="hash")
    trip = Trip(id=str(uuid4()), user_id=owner.id, title="Shared", destination="Kyoto", duration=2, total_budget=500, itinerary=[{"day_number": 1, "hotel": "Old hotel", "meals": ["Old lunch"], "activities": ["Old activity", "Keep me"]}, {"day_number": 2, "activities": ["Day two"]}], revision_history=[], data_freshness=[])
    with Session() as db:
        db.add_all([owner, trip, TripMember(id=str(uuid4()), trip_id=trip.id, user_id=owner.id, role="owner", status="active")])
        db.commit()
    return Session, trip.id, owner.id


def create_proposal(Session, trip_id, owner_id, proposal_type, payload):
    with Session() as db:
        proposal = ProposalService(db).create(trip_id, owner_id, {"proposal_type": proposal_type, "title": proposal_type, "payload": payload})
        ProposalService(db).vote(proposal.id, owner_id, "yes")
        return proposal.id


@pytest.mark.parametrize("proposal_type,payload", [
    ("destination", {"destination": "Osaka", "value": "Osaka"}),
    ("hotel", {"day_number": 1, "value": "New hotel"}),
    ("restaurant", {"day_number": 1, "meal_index": 0, "value": "New lunch"}),
    ("activity", {"day_number": 1, "activity_index": 0, "value": "New activity"}),
    ("itinerary_item", {"day_number": 1, "item_index": 0, "value": "New item"}),
    ("other", {"value": "A decision"}),
])
def test_supported_proposal_types_finalize_and_snapshot(proposal_db, proposal_type, payload):
    Session, trip_id, owner_id = proposal_db
    proposal_id = create_proposal(Session, trip_id, owner_id, proposal_type, payload)
    with Session() as db:
        _, decision = ProposalService(db).finalize(proposal_id, owner_id)
        assert decision.vote_counts == {"yes": 1}
        assert decision.proposal_snapshot == payload
        assert db.scalar(select(Decision).where(Decision.proposal_id == proposal_id)) is not None


def test_tie_is_explicit_and_closed_proposals_cannot_mutate(proposal_db):
    Session, trip_id, owner_id = proposal_db
    with Session() as db:
        proposal = ProposalService(db).create(trip_id, owner_id, {"proposal_type": "other", "title": "Tie", "payload": {"value": "x"}})
        member = User(id=str(uuid4()), name="Member", email=f"member-{uuid4()}@example.com", password_hash="hash")
        db.add_all([member, TripMember(id=str(uuid4()), trip_id=trip_id, user_id=member.id, role="member", status="active")]); db.commit()
        ProposalService(db).vote(proposal.id, owner_id, "a"); ProposalService(db).vote(proposal.id, member.id, "b")
        ProposalService(db).finalize(proposal.id, owner_id)
        result = ProposalService(db).get(proposal.id, owner_id)
        assert result.status == "rejected"
        with pytest.raises(ValueError): ProposalService(db).vote(proposal.id, owner_id, "a")
        with pytest.raises(Exception): ProposalService(db).update(proposal.id, owner_id, {"title": "closed"})


def test_application_preserves_unrelated_days_and_records_revisions(proposal_db):
    Session, trip_id, owner_id = proposal_db
    proposal_id = create_proposal(Session, trip_id, owner_id, "restaurant", {"day_number": 1, "meal_index": 0, "value": "New lunch"})
    with Session() as db:
        _, decision = ProposalService(db).finalize(proposal_id, owner_id)
        before = deepcopy(db.get(Trip, trip_id).itinerary)
        applied = ProposalService(db).apply(decision.id, owner_id)
        trip = db.get(Trip, trip_id)
        assert trip.itinerary[0]["meals"] == ["New lunch"]
        assert trip.itinerary[0]["activities"] == before[0]["activities"]
        assert trip.itinerary[1] == before[1]
        assert applied.applied_action["before"]["value"] == "Old lunch"
        assert applied.source_revision == 0 and applied.target_revision == 1


def test_expired_proposal_rejects_votes(proposal_db):
    Session, trip_id, owner_id = proposal_db
    with Session() as db:
        proposal = ProposalService(db).create(trip_id, owner_id, {"proposal_type": "other", "title": "Expired", "payload": {"value": "x"}, "deadline": datetime.now(UTC) + timedelta(minutes=1)})
        proposal.deadline = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        with pytest.raises(ValueError): ProposalService(db).vote(proposal.id, owner_id, "yes")


def test_invalid_target_is_recorded_without_overwriting_itinerary(proposal_db):
    Session, trip_id, owner_id = proposal_db
    proposal_id = create_proposal(Session, trip_id, owner_id, "restaurant", {"day_number": 1, "meal_index": 99, "value": "Unsafe"})
    with Session() as db:
        _, decision = ProposalService(db).finalize(proposal_id, owner_id)
        applied = ProposalService(db).apply(decision.id, owner_id)
        assert applied.applied_action["applied"] is False
        assert db.get(Trip, trip_id).itinerary[0]["meals"] == ["Old lunch"]


def test_removed_member_cannot_vote_or_finalize(proposal_db):
    Session, trip_id, owner_id = proposal_db
    with Session() as db:
        member = User(id=str(uuid4()), name="Former", email=f"former-{uuid4()}@example.com", password_hash="hash")
        db.add_all([member, TripMember(id=str(uuid4()), trip_id=trip_id, user_id=member.id, role="member", status="removed")])
        proposal = ProposalService(db).create(trip_id, owner_id, {"proposal_type": "other", "title": "Access", "payload": {"value": "x"}})
        db.commit()
        with pytest.raises(Exception): ProposalService(db).vote(proposal.id, member.id, "yes")
        with pytest.raises(Exception): ProposalService(db).finalize(proposal.id, member.id)


def test_destination_replanning_success_and_failure_preserve_decision(proposal_db, monkeypatch):
    Session, trip_id, owner_id = proposal_db
    proposal_id = create_proposal(Session, trip_id, owner_id, "destination", {"destination": "Osaka", "value": "Osaka"})
    with Session() as db:
        _, decision = ProposalService(db).finalize(proposal_id, owner_id)
        ProposalService(db).apply(decision.id, owner_id)
        monkeypatch.setattr("services.trip_service.TripService.regenerate_day", lambda self, trip_id, day_number: {"trip_id": trip_id, "day_number": day_number})
        replanned = ProposalService(db).replan_destination(decision.id, owner_id)
        assert replanned.applied_action["replanning"] == "completed"

    with Session() as db:
        proposal = db.get(Proposal, proposal_id)
        proposal.status = "open"
        proposal.decision = None
        db.commit()
        decision = db.scalar(select(Decision).where(Decision.proposal_id == proposal_id))
        decision.applied_action = {"applied": True, "replanning": "required"}
        monkeypatch.setattr("services.trip_service.TripService.regenerate_day", lambda self, trip_id, day_number: (_ for _ in ()).throw(RuntimeError("planner down")))
        with pytest.raises(RuntimeError): ProposalService(db).replan_destination(decision.id, owner_id)
        assert db.get(Decision, decision.id).applied_action["replanning"] == "failed"