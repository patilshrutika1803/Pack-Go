from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import ChecklistItem, Decision, Proposal, ProposalVote, Trip, TripMember, TripInvitation, User
from services.collaboration_service import AccessDenied, CollaborationService, GroupTripService, ProposalService, token_digest


def setup_database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def seed_group(Session):
    owner = User(id=str(uuid4()), name="Owner", email=f"owner-{uuid4()}@example.com", password_hash="hash")
    member = User(id=str(uuid4()), name="Member", email=f"member-{uuid4()}@example.com", password_hash="hash")
    trip = Trip(id=str(uuid4()), user_id=owner.id, title="Race", destination="Goa", duration=2, total_budget=500, budget_currency="INR", group_size=2, travel_style="balanced", interests=[], things_to_avoid=[], itinerary=[], revision_history=[], data_freshness={})
    with Session() as db:
        db.add_all([owner, member, trip, TripMember(id=str(uuid4()), trip_id=trip.id, user_id=owner.id, role="owner", status="active")])
        db.commit()
    return trip.id, owner, member


def test_concurrent_invitation_acceptance_creates_one_membership(tmp_path):
    engine, Session = setup_database(tmp_path)
    trip_id, owner, invitee = seed_group(Session)
    raw = "race-token"
    with Session() as db:
        db.add(TripInvitation(id=str(uuid4()), trip_id=trip_id, inviter_user_id=owner.id, invitee_user_id=invitee.id, token_hash=token_digest(raw), status="pending", expires_at=datetime.now(UTC) + timedelta(days=1)))
        db.commit()

    def accept_once():
        try:
            with Session() as db:
                user = db.get(User, invitee.id)
                GroupTripService(db).accept(raw, user)
                return "accepted"
        except (AccessDenied, IntegrityError, OperationalError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept_once(), range(2)))
    with Session() as db:
        rows = db.scalars(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == invitee.id, TripMember.status == "active")).all()
        invitation = db.scalar(select(TripInvitation).where(TripInvitation.trip_id == trip_id))
    assert len(rows) == 1
    assert invitation.status == "accepted"
    assert results.count("accepted") == 1


def test_database_constraint_rejects_concurrent_duplicate_membership(tmp_path):
    engine, Session = setup_database(tmp_path)
    trip_id, owner, invitee = seed_group(Session)
    target_user_id = str(uuid4())
    with Session() as db:
        db.add(User(id=target_user_id, name="Race target", email=f"target-{target_user_id}@example.com", password_hash="hash"))
        db.commit()
    def insert_once():
        try:
            with Session() as db:
                db.add(TripMember(id=str(uuid4()), trip_id=trip_id, user_id=target_user_id, role="member", status="active"))
                db.commit()
                return "inserted"
        except (IntegrityError, OperationalError):
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: insert_once(), range(2)))
    with Session() as db:
        rows = db.scalars(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == target_user_id)).all()
    assert len(rows) == 1
    assert results.count("inserted") == 1


def test_concurrent_finalization_creates_one_decision(tmp_path):
    engine, Session = setup_database(tmp_path)
    trip_id, owner, member = seed_group(Session)
    with Session() as db:
        db.add_all([TripMember(id=str(uuid4()), trip_id=trip_id, user_id=member.id, role="member", status="active")])
        proposal = Proposal(id=str(uuid4()), trip_id=trip_id, created_by_user_id=member.id, proposal_type="other", title="Vote", payload={})
        db.add_all([proposal, ProposalVote(id=str(uuid4()), proposal_id=proposal.id, user_id=owner.id, choice_key="yes")])
        db.commit()
        proposal_id = proposal.id

    def finalize_once(user_id):
        try:
            with Session() as db:
                ProposalService(db).finalize(proposal_id, user_id)
                return "finalized"
        except (IntegrityError, OperationalError, ValueError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finalize_once, [owner.id, owner.id]))
    with Session() as db:
        decisions = db.scalars(select(Decision).where(Decision.proposal_id == proposal_id)).all()
    assert len(decisions) == 1
    assert results.count("finalized") == 1


def test_concurrent_vote_changes_keep_one_vote_row(tmp_path):
    engine, Session = setup_database(tmp_path)
    trip_id, owner, member = seed_group(Session)
    with Session() as db:
        db.add(TripMember(id=str(uuid4()), trip_id=trip_id, user_id=member.id, role="member", status="active"))
        proposal = Proposal(id=str(uuid4()), trip_id=trip_id, created_by_user_id=owner.id, proposal_type="other", title="Vote", payload={})
        db.add(proposal)
        db.commit()
        proposal_id = proposal.id

    def vote_once(choice):
        try:
            with Session() as db:
                ProposalService(db).vote(proposal_id, member.id, choice)
                return "voted"
        except (IntegrityError, OperationalError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(vote_once, ["yes", "no"]))
    with Session() as db:
        votes = db.scalars(select(ProposalVote).where(ProposalVote.proposal_id == proposal_id, ProposalVote.user_id == member.id)).all()
    assert len(votes) == 1
    assert votes[0].choice_key in {"yes", "no"}


def test_concurrent_checklist_completion_has_one_consistent_actor(tmp_path):
    engine, Session = setup_database(tmp_path)
    trip_id, owner, member = seed_group(Session)
    with Session() as db:
        item = ChecklistItem(id=str(uuid4()), trip_id=trip_id, created_by_user_id=owner.id, title="Book tickets")
        db.add(item)
        db.commit()
        item_id = item.id

    def complete_once(user_id):
        try:
            with Session() as db:
                CollaborationService(db).update_item(item_id, user_id, {"completed": True})
                return "completed"
        except OperationalError:
            return "locked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(complete_once, [owner.id, owner.id]))
    with Session() as db:
        stored = db.get(ChecklistItem, item_id)
    assert stored.completed is True
    assert stored.completed_by_user_id == owner.id
    assert results.count("completed") >= 1
