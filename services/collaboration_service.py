from __future__ import annotations

import hashlib
import secrets
from copy import deepcopy
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from database.models import ChecklistItem, Decision, GroupMessage, Notification, Proposal, ProposalVote, Trip, TripInvitation, TripMember, User


class AccessDenied(Exception):
    pass


class TripAccessService:
    def __init__(self, db: Session):
        self.db = db

    def get_trip_for_member(self, trip_id: str, user_id: str) -> Trip:
        trip = self.db.scalar(select(Trip).where(Trip.id == trip_id))
        active_member = self.db.scalar(select(TripMember.id).where(TripMember.trip_id == trip_id, TripMember.user_id == user_id, TripMember.status == "active"))
        if trip is None or (active_member is None and trip.user_id != user_id):
            raise AccessDenied("Trip not found.")
        return trip

    def list_trips_for_user(self, user_id: str) -> list[Trip]:
        membership = select(TripMember.id).where(
            TripMember.trip_id == Trip.id,
            TripMember.user_id == user_id,
            TripMember.status == "active",
        ).exists()
        return list(self.db.scalars(select(Trip).where((Trip.user_id == user_id) | membership).order_by(Trip.created_at.desc(), Trip.id.desc())).all())

    def member(self, trip_id: str, user_id: str) -> TripMember:
        member = self.db.scalar(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == user_id, TripMember.status == "active"))
        if member is None:
            raise AccessDenied("Trip not found.")
        return member

    def require_active_member(self, trip_id: str, user_id: str) -> TripMember:
        return self.member(trip_id, user_id)

    def get_trip_for_role(self, trip_id: str, user_id: str, roles: set[str] | tuple[str, ...]) -> Trip:
        trip = self.get_trip_for_member(trip_id, user_id)
        member = self.member(trip_id, user_id)
        if member.role not in set(roles):
            raise AccessDenied("Insufficient trip permissions.")
        return trip

    def require_owner(self, trip_id: str, user_id: str) -> TripMember:
        trip = self.get_trip_for_member(trip_id, user_id)
        member = self.db.scalar(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == user_id, TripMember.status == "active"))
        if (member is None and trip.user_id == user_id) or (member is not None and member.role == "owner"):
            return member
        if member is None or member.role != "owner":
            raise AccessDenied("Owner access required.")
        return member

    def require_admin_or_owner(self, trip_id: str, user_id: str) -> TripMember:
        trip = self.get_trip_for_member(trip_id, user_id)
        member = self.db.scalar(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == user_id, TripMember.status == "active"))
        if member is None and trip.user_id == user_id:
            return member
        if member is None or member.role not in {"owner", "admin"}:
            raise AccessDenied("Administrator access required.")
        return member

    def require_can_edit_trip(self, trip_id: str, user_id: str) -> TripMember | None:
        return self.require_admin_or_owner(trip_id, user_id)

    def require_can_vote(self, trip_id: str, user_id: str) -> TripMember:
        return self.member(trip_id, user_id)


def now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def notify(db: Session, trip_id: str | None, recipients: list[str], event_type: str, payload: dict) -> None:
    for recipient_id in set(recipients):
        db.add(Notification(id=str(uuid4()), recipient_user_id=recipient_id, trip_id=trip_id, event_type=event_type, payload=payload))


def active_recipient_ids(db: Session, trip_id: str, exclude: str | None = None) -> list[str]:
    query = select(TripMember.user_id).where(TripMember.trip_id == trip_id, TripMember.status == "active")
    if exclude:
        query = query.where(TripMember.user_id != exclude)
    return list(db.scalars(query).all())


def validate_proposal_payload(proposal_type: str, payload: dict) -> None:
    if proposal_type not in {"destination", "hotel", "restaurant", "activity", "itinerary_item", "other"}:
        raise ValueError("Unsupported proposal type.")
    if not isinstance(payload, dict):
        raise ValueError("Proposal payload must be an object.")
    required = {
        "destination": ("destination",),
        "hotel": ("day_number", "value"),
        "restaurant": ("day_number", "meal_index", "value"),
        "activity": ("day_number", "activity_index", "value"),
        "itinerary_item": ("day_number", "item_index", "value"),
    }.get(proposal_type, ())
    missing = [field for field in required if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValueError(f"Payload for {proposal_type} requires: {', '.join(missing)}.")
    for field in ("day_number", "meal_index", "activity_index", "item_index"):
        if field in payload and (not isinstance(payload[field], int) or payload[field] < 0):
            raise ValueError(f"{field} must be a non-negative integer.")
    if "day_number" in payload and payload["day_number"] < 1:
        raise ValueError("day_number must be a positive integer.")
    for field in ("destination", "name", "value"):
        if field in payload and (not isinstance(payload[field], str) or not payload[field].strip() or len(payload[field]) > 4000):
            raise ValueError(f"{field} must be a non-empty string of at most 4000 characters.")


def proposal_result(votes: list[ProposalVote]) -> tuple[dict[str, int], str | None, list[str]]:
    counts = dict(sorted(Counter(vote.choice_key for vote in votes).items()))
    highest = max(counts.values(), default=0)
    ties = [choice for choice, count in counts.items() if count == highest] if highest else []
    return counts, ties[0] if len(ties) == 1 else None, ties if len(ties) > 1 else []


class GroupTripService:
    def __init__(self, db: Session):
        self.db = db
        self.access = TripAccessService(db)

    def _commit(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def convert(self, trip_id: str, user_id: str) -> Trip:
        trip = self.db.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
        if trip is None or trip.user_id != user_id:
            raise AccessDenied("Trip not found.")
        member = self.db.scalar(select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == user_id))
        if member is None:
            self.db.add(TripMember(id=str(uuid4()), trip_id=trip_id, user_id=user_id, role="owner", status="active"))
        elif member.status != "active":
            member.status = "active"; member.role = "owner"; member.joined_at = now(); member.left_at = None; member.removed_at = None
        self._commit()
        return trip

    def workspace(self, trip_id: str, user_id: str) -> dict:
        self.access.get_trip_for_member(trip_id, user_id)
        members = list(self.db.scalars(select(TripMember).options(selectinload(TripMember.user)).where(TripMember.trip_id == trip_id, TripMember.status == "active").order_by(TripMember.joined_at)).all())
        return {"trip_id": trip_id, "is_group": True, "member_count": len(members), "members": members}

    def update_member(self, trip_id: str, actor_id: str, target_id: str, role: str) -> TripMember:
        actor = self.access.require_admin_or_owner(trip_id, actor_id)
        target = self.access.member(trip_id, target_id)
        if target.role == "owner" or (actor.role != "owner" and target.role == "admin"):
            raise AccessDenied("Member role cannot be changed.")
        target.role = role
        notify(self.db, trip_id, [target_id], "role_changed", {"trip_id": trip_id})
        self._commit(); return target

    def remove_member(self, trip_id: str, actor_id: str, target_id: str) -> None:
        actor = self.access.require_admin_or_owner(trip_id, actor_id)
        target = self.access.member(trip_id, target_id)
        if target.role == "owner" or (actor.role != "owner" and target.role == "admin"):
            raise AccessDenied("Member cannot be removed.")
        target.status = "removed"; target.removed_at = now()
        for item in self.db.scalars(select(ChecklistItem).where(ChecklistItem.trip_id == trip_id, ChecklistItem.assigned_to_user_id == target_id)).all():
            item.assigned_to_user_id = None
        notify(self.db, trip_id, [target_id], "member_removed", {"trip_id": trip_id}); self._commit()

    def leave(self, trip_id: str, user_id: str) -> None:
        member = self.access.member(trip_id, user_id)
        if member.role == "owner": raise AccessDenied("Owner must transfer ownership before leaving.")
        member.status = "left"; member.left_at = now()
        for item in self.db.scalars(select(ChecklistItem).where(ChecklistItem.trip_id == trip_id, ChecklistItem.assigned_to_user_id == user_id)).all():
            item.assigned_to_user_id = None
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "member_left", {"trip_id": trip_id, "user_id": user_id})
        self._commit()

    def transfer_ownership(self, trip_id: str, actor_id: str, target_id: str) -> TripMember:
        current = self.access.require_owner(trip_id, actor_id)
        if target_id == actor_id:
            raise ValueError("Ownership is already assigned to this user.")
        target = self.access.member(trip_id, target_id)
        trip = self.db.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
        if trip is None:
            raise AccessDenied("Trip not found.")
        current.role = "admin"
        target.role = "owner"
        trip.user_id = target_id
        notify(self.db, trip_id, [actor_id, target_id], "ownership_transferred", {"trip_id": trip_id})
        self._commit()
        return target

    def invitation(self, trip_id: str, actor_id: str, invitee_user_id: str | None, invitee_email: str | None, expires_days: int) -> tuple[TripInvitation, str]:
        self.access.require_admin_or_owner(trip_id, actor_id)
        if invitee_user_id and invitee_email:
            raise ValueError("Provide at most one invitation target.")
        if invitee_user_id and self.db.get(User, invitee_user_id) is None:
            raise ValueError("Invitee user was not found.")
        normalized_email = invitee_email.lower().strip() if invitee_email else None
        if normalized_email:
            existing_user = self.db.scalar(select(User).where(func.lower(User.email) == normalized_email))
            if existing_user is not None:
                invitee_user_id = existing_user.id
                normalized_email = None
        if invitee_user_id and self.db.scalar(select(TripMember.id).where(TripMember.trip_id == trip_id, TripMember.user_id == invitee_user_id, TripMember.status == "active")):
            raise ValueError("User is already a member.")
        target_filters = []
        if invitee_user_id:
            target_filters.append(TripInvitation.invitee_user_id == invitee_user_id)
        elif normalized_email:
            target_filters.append(TripInvitation.invitee_email == normalized_email)
        else:
            target_filters.append(TripInvitation.invitee_user_id.is_(None), TripInvitation.invitee_email.is_(None))
        duplicate = self.db.scalar(select(TripInvitation.id).where(TripInvitation.trip_id == trip_id, TripInvitation.status == "pending", TripInvitation.expires_at > now(), *target_filters))
        if duplicate: raise ValueError("An active invitation already exists.")
        raw = secrets.token_urlsafe(32)
        invitation = TripInvitation(id=str(uuid4()), trip_id=trip_id, inviter_user_id=actor_id, invitee_user_id=invitee_user_id, invitee_email=normalized_email, token_hash=token_digest(raw), expires_at=now() + timedelta(days=expires_days))
        self.db.add(invitation)
        if invitee_user_id:
            notify(self.db, trip_id, [invitee_user_id], "invitation_created", {"invitation_id": invitation.id})
        self._commit(); return invitation, raw

    def invitation_preview(self, raw_token: str) -> dict:
        invitation = self.db.scalar(select(TripInvitation).where(TripInvitation.token_hash == token_digest(raw_token)))
        if invitation is None:
            raise AccessDenied("Invitation not found.")
        if invitation.status == "pending" and as_utc(invitation.expires_at) <= now():
            invitation.status = "expired"
            self._commit()
        trip = self.db.get(Trip, invitation.trip_id)
        if trip is None:
            raise AccessDenied("Invitation not found.")
        member_count = self.db.scalar(select(func.count(TripMember.id)).where(TripMember.trip_id == trip.id, TripMember.status == "active")) or 0
        return {"trip_id": trip.id, "trip_title": trip.title, "destination": trip.destination, "duration": trip.duration, "member_count": member_count, "expires_at": invitation.expires_at, "status": invitation.status}

    def accept(self, raw_token: str, user: User) -> tuple[TripInvitation, TripMember]:
        invitation = self.db.scalar(select(TripInvitation).where(TripInvitation.token_hash == token_digest(raw_token)).with_for_update())
        if invitation is None or invitation.status != "pending" or as_utc(invitation.expires_at) <= now() or (invitation.invitee_user_id and invitation.invitee_user_id != user.id) or (invitation.invitee_email and invitation.invitee_email.lower() != user.email.lower()):
            raise AccessDenied("Invitation is invalid or expired.")
        member = self.db.scalar(select(TripMember).where(TripMember.trip_id == invitation.trip_id, TripMember.user_id == user.id))
        if member is None: member = TripMember(id=str(uuid4()), trip_id=invitation.trip_id, user_id=user.id, role="member", status="active"); self.db.add(member)
        else: member.status = "active"; member.left_at = None; member.removed_at = None
        invitation.status = "accepted"; invitation.accepted_at = now()
        notify(self.db, invitation.trip_id, active_recipient_ids(self.db, invitation.trip_id, user.id), "member_joined", {"trip_id": invitation.trip_id})
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return invitation, member

    def revoke_invitation(self, invitation_id: str, actor_id: str) -> None:
        invitation = self.db.get(TripInvitation, invitation_id)
        if invitation is None:
            raise AccessDenied("Invitation not found.")
        self.access.require_admin_or_owner(invitation.trip_id, actor_id)
        if invitation.status != "pending":
            raise ValueError("Only pending invitations can be revoked.")
        invitation.status = "revoked"
        notify(self.db, invitation.trip_id, active_recipient_ids(self.db, invitation.trip_id, actor_id), "invitation_revoked", {"invitation_id": invitation.id})
        self._commit()


class ProposalService:
    def __init__(self, db: Session): self.db = db; self.access = TripAccessService(db)
    def create(self, trip_id: str, user_id: str, data: dict) -> Proposal:
        self.access.member(trip_id, user_id)
        validate_proposal_payload(data["proposal_type"], data["payload"])
        if data.get("deadline") and data["deadline"] <= now(): raise ValueError("Deadline must be in the future.")
        data = dict(data)
        data["title"] = data["title"].strip()
        if data.get("description") is not None:
            data["description"] = data["description"].strip() or None
        data["payload"] = deepcopy(data["payload"])
        proposal = Proposal(id=str(uuid4()), trip_id=trip_id, created_by_user_id=user_id, payload_history=[deepcopy(data["payload"])], **data); self.db.add(proposal)
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "proposal_created", {"proposal_id": proposal.id})
        try:
            self.db.commit()
            self.db.refresh(proposal)
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to create proposal.")
        return proposal
    def get(self, proposal_id: str, user_id: str) -> Proposal:
        proposal = self.db.scalar(select(Proposal).where(Proposal.id == proposal_id))
        if proposal is None: raise AccessDenied("Proposal not found.")
        self.access.member(proposal.trip_id, user_id); return proposal
    def vote(self, proposal_id: str, user_id: str, choice: str) -> ProposalVote:
        proposal = self.get(proposal_id, user_id)
        choice = choice.strip()
        if not choice or len(choice) > 120:
            raise ValueError("Vote choice must be between 1 and 120 characters.")
        if proposal.deadline and as_utc(proposal.deadline) <= now():
            proposal.status = "closed"
            proposal.closed_at = now()
            self.db.commit()
            raise ValueError("Voting is closed.")
        if proposal.status != "open": raise ValueError("Voting is closed.")
        vote = self.db.scalar(select(ProposalVote).where(ProposalVote.proposal_id == proposal_id, ProposalVote.user_id == user_id))
        if vote is None: vote = ProposalVote(id=str(uuid4()), proposal_id=proposal_id, user_id=user_id, choice_key=choice); self.db.add(vote)
        else: vote.choice_key = choice
        notify(self.db, proposal.trip_id, active_recipient_ids(self.db, proposal.trip_id, user_id), "vote_activity", {"proposal_id": proposal.id})
        try:
            self.db.commit()
            self.db.refresh(vote)
        except IntegrityError as exc:
            self.db.rollback()
            raise exc
        return vote
    def remove_vote(self, proposal_id: str, user_id: str) -> None:
        proposal = self.get(proposal_id, user_id)
        if proposal.status != "open" or proposal.deadline and as_utc(proposal.deadline) <= now(): raise ValueError("Voting is closed.")
        vote = self.db.scalar(select(ProposalVote).where(ProposalVote.proposal_id == proposal_id, ProposalVote.user_id == user_id))
        if vote:
            self.db.delete(vote)
            notify(self.db, proposal.trip_id, active_recipient_ids(self.db, proposal.trip_id, user_id), "vote_activity", {"proposal_id": proposal.id})
            self.db.commit()
    def finalize(self, proposal_id: str, user_id: str) -> tuple[Proposal, Decision]:
        proposal = self.db.scalar(select(Proposal).where(Proposal.id == proposal_id).with_for_update())
        if proposal is None: raise AccessDenied("Proposal not found.")
        actor = self.access.require_admin_or_owner(proposal.trip_id, user_id)
        existing = self.db.scalar(select(Decision).where(Decision.proposal_id == proposal_id).with_for_update())
        if existing is not None: raise ValueError("Proposal has already been finalized.")
        if proposal.status != "open": raise ValueError("Proposal is already closed.")
        if proposal.deadline and as_utc(proposal.deadline) <= now():
            proposal.status = "closed"
            proposal.closed_at = now()
            self.db.commit()
            raise ValueError("Proposal deadline has passed.")
        self.db.refresh(proposal, ["votes", "trip"])
        counts, winner, ties = proposal_result(proposal.votes)
        result = "accepted" if winner else "rejected"
        decision = Decision(id=str(uuid4()), trip_id=proposal.trip_id, proposal_id=proposal.id, decided_by_user_id=actor.user_id, result=result, decision_type=f"selected_{proposal.proposal_type}", vote_counts=counts, proposal_snapshot=deepcopy(proposal.payload), applied_action={"winner": winner, "ties": ties, "applied": False}, source_revision=len(proposal.trip.revision_history or []), target_revision=None)
        proposal.status = "accepted" if winner else "rejected"; proposal.closed_at = now(); self.db.add(decision)
        notify(self.db, proposal.trip_id, active_recipient_ids(self.db, proposal.trip_id, user_id), "decision_finalized", {"decision_id": decision.id, "proposal_id": proposal.id})
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Proposal has already been finalized.") from exc
        return proposal, decision

    def close(self, proposal_id: str, user_id: str) -> Proposal:
        proposal = self.get(proposal_id, user_id)
        self.access.require_admin_or_owner(proposal.trip_id, user_id)
        if proposal.status != "open": raise ValueError("Proposal is already closed.")
        proposal.status = "closed"; proposal.closed_at = now()
        notify(self.db, proposal.trip_id, active_recipient_ids(self.db, proposal.trip_id, user_id), "proposal_closed", {"proposal_id": proposal.id})
        self.db.commit(); return proposal

    def update(self, proposal_id: str, user_id: str, updates: dict) -> Proposal:
        proposal = self.get(proposal_id, user_id)
        member = self.access.member(proposal.trip_id, user_id)
        if proposal.status != "open" or (proposal.created_by_user_id != user_id and member.role not in {"owner", "admin"}): raise AccessDenied("Proposal cannot be edited.")
        if "deadline" in updates and updates["deadline"] is not None and updates["deadline"] <= now():
            raise ValueError("Deadline must be in the future.")
        validate_proposal_payload(updates.get("proposal_type", proposal.proposal_type), updates.get("payload", proposal.payload))
        for key, value in updates.items():
            if value is not None:
                setattr(proposal, key, deepcopy(value) if key == "payload" else value.strip() if isinstance(value, str) else value)
        if "payload" in updates:
            proposal.payload_history = [*(proposal.payload_history or []), deepcopy(updates["payload"])]
        notify(self.db, proposal.trip_id, active_recipient_ids(self.db, proposal.trip_id, user_id), "proposal_updated", {"proposal_id": proposal.id})
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to update proposal.")
        return proposal

    def replan_destination(self, decision_id: str, user_id: str) -> Decision:
        decision = self.db.get(Decision, decision_id)
        if decision is None: raise AccessDenied("Decision not found.")
        self.access.require_admin_or_owner(decision.trip_id, user_id)
        action = dict(decision.applied_action or {})
        if action.get("replanning") == "completed": return decision
        if not action.get("applied") or decision.decision_type != "selected_destination":
            raise ValueError("Only an applied destination decision can be replanned.")
        from services.trip_service import DayNotFoundError, TripService
        trip = self.db.get(Trip, decision.trip_id)
        try:
            for day_number in range(1, len(trip.itinerary or []) + 1):
                TripService(self.db).regenerate_day(trip.id, day_number)
        except Exception as exc:
            action["replanning"] = "failed"; action["replanning_error"] = str(exc)[:500]
            decision.applied_action = action; self.db.commit()
            raise RuntimeError("Destination replanning failed; the decision was preserved.") from exc
        action["replanning"] = "completed"; decision.applied_action = action; decision.target_revision = len(trip.revision_history or [])
        self.db.commit(); return decision

    def apply(self, decision_id: str, user_id: str) -> Decision:
        decision = self.db.scalar(select(Decision).where(Decision.id == decision_id).with_for_update())
        if decision is None: raise AccessDenied("Decision not found.")
        self.access.require_admin_or_owner(decision.trip_id, user_id)
        if decision.applied_action and decision.applied_action.get("applied"): return decision
        proposal = self.db.get(Proposal, decision.proposal_id)
        trip = self.db.get(Trip, decision.trip_id)
        if proposal is None or trip is None or proposal.trip_id != decision.trip_id or decision.result != "accepted":
            decision.applied_action = {**(decision.applied_action or {}), "applied": False, "reason": "No accepted proposal to apply."}
            self.db.commit(); return decision
        payload = deepcopy(decision.proposal_snapshot)
        validate_proposal_payload(proposal.proposal_type, payload)
        itinerary = deepcopy(trip.itinerary or [])
        day_number = payload.get("day_number")
        source_revision = len(trip.revision_history or [])
        before = {"destination": trip.destination, "day_number": day_number}
        applied = False
        target = None
        if proposal.proposal_type == "destination":
            before["value"] = trip.destination; trip.destination = payload["destination"].strip(); trip.title = trip.destination; target = {"target": "trip.destination", "replanning": "required"}; applied = True
        elif day_number is not None:
            day_index = next((index for index, candidate in enumerate(itinerary) if isinstance(candidate, dict) and candidate.get("day_number") == day_number), None)
            if day_index is None and 1 <= day_number <= len(itinerary):
                day_index = day_number - 1
            if day_index is None:
                day = None
            else:
                day = dict(itinerary[day_index])
            replacement = payload.get("value", payload.get("name"))
            if day is not None and not isinstance(replacement, str):
                replacement = None
            if day is not None and replacement:
                if proposal.proposal_type == "hotel":
                    before["value"] = day.get("hotel"); day["hotel"] = replacement; target = {"day_number": day_number, "field": "hotel"}; applied = True
                elif proposal.proposal_type == "restaurant" and 0 <= payload["meal_index"] < len(day.get("meals", [])):
                    meals = list(day.get("meals", [])); before["value"] = meals[payload["meal_index"]]; meals[payload["meal_index"]] = replacement; day["meals"] = meals; target = {"day_number": day_number, "field": "meals", "index": payload["meal_index"]}; applied = True
                elif proposal.proposal_type == "activity" and 0 <= payload["activity_index"] < len(day.get("activities", [])):
                    activities = list(day.get("activities", [])); before["value"] = activities[payload["activity_index"]]; activities[payload["activity_index"]] = replacement; day["activities"] = activities; target = {"day_number": day_number, "field": "activities", "index": payload["activity_index"]}; applied = True
                elif proposal.proposal_type == "itinerary_item" and 0 <= payload.get("item_index", -1) < len(day.get("activities", [])):
                    activities = list(day.get("activities", [])); before["value"] = activities[payload["item_index"]]; activities[payload["item_index"]] = replacement; day["activities"] = activities; target = {"day_number": day_number, "field": "activities", "index": payload["item_index"]}; applied = True
                if applied:
                    itinerary[day_index] = day; trip.itinerary = itinerary
        target_revision = source_revision + (1 if applied else 0)
        if applied:
            after = {"destination": trip.destination, "day_number": day_number}
            if target and target.get("field"):
                after["value"] = trip.itinerary[day_number - 1][target["field"]][target["index"]] if "index" in target else trip.itinerary[day_number - 1][target["field"]]
            else: after["value"] = trip.destination
            trip.revision_history = [*(trip.revision_history or []), {"iteration": target_revision, "decision_id": decision.id, "changed_by_user_id": user_id, "change_type": proposal.proposal_type, "source_revision": source_revision, "target_revision": target_revision, "before": before, "after": after}]
            notify(self.db, decision.trip_id, active_recipient_ids(self.db, decision.trip_id, user_id), "itinerary_changed", {"decision_id": decision.id, "change_type": proposal.proposal_type})
        decision.target_revision = target_revision
        decision.applied_action = {**(decision.applied_action or {}), "applied": applied, "reason": None if applied else "Proposal target could not be mapped safely.", "before": before, "after": after if applied else None, "target": target}
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to apply decision.")
        return decision


class CollaborationService:
    def __init__(self, db: Session): self.db = db; self.access = TripAccessService(db)
    def checklist(self, trip_id, user_id, data=None, item_id=None):
        self.access.member(trip_id, user_id)
        if item_id: item = self.db.get(ChecklistItem, item_id); return item
        data = dict(data or {})
        data["title"] = data["title"].strip()
        if data.get("description") is not None:
            data["description"] = data["description"].strip() or None
        if data.get("assigned_to_user_id") and self.db.scalar(select(TripMember.id).where(TripMember.trip_id == trip_id, TripMember.user_id == data["assigned_to_user_id"], TripMember.status == "active")) is None:
            raise ValueError("Assignee must be an active member.")
        item = ChecklistItem(id=str(uuid4()), trip_id=trip_id, created_by_user_id=user_id, **data); self.db.add(item)
        if item.assigned_to_user_id:
            notify(self.db, trip_id, [item.assigned_to_user_id], "checklist_assignment", {"checklist_item_id": item.id})
        try:
            self.db.commit()
            self.db.refresh(item)
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to create checklist item.")
        return item
    def message(self, trip_id, user_id, body):
        self.access.member(trip_id, user_id)
        body = body.strip()
        if not body or len(body) > 4000:
            raise ValueError("Message must be between 1 and 4000 characters.")
        message = GroupMessage(id=str(uuid4()), trip_id=trip_id, sender_user_id=user_id, body=body); self.db.add(message)
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "message_created", {"message_id": message.id})
        try:
            self.db.commit()
            self.db.refresh(message)
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to send message.")
        return message

    def update_item(self, item_id, user_id, updates):
        item = self.db.get(ChecklistItem, item_id)
        if item is None: raise AccessDenied("Checklist item not found.")
        member = self.access.member(item.trip_id, user_id)
        if member.role not in {"owner", "admin"} and item.created_by_user_id != user_id and item.assigned_to_user_id != user_id: raise AccessDenied("Checklist item cannot be edited.")
        updates = dict(updates)
        if "assigned_to_user_id" in updates and updates["assigned_to_user_id"] and self.db.scalar(select(TripMember.id).where(TripMember.trip_id == item.trip_id, TripMember.user_id == updates["assigned_to_user_id"], TripMember.status == "active")) is None: raise ValueError("Assignee must be an active member.")
        previous_assignee = item.assigned_to_user_id
        for key, value in updates.items():
            if key == "completed":
                item.completed = value; item.completed_by_user_id = user_id if value else None; item.completed_at = now() if value else None
            elif key in {"title", "description"} and value is not None: setattr(item, key, value.strip() if isinstance(value, str) else value)
            elif value is not None: setattr(item, key, value)
        if item.assigned_to_user_id and item.assigned_to_user_id != previous_assignee:
            notify(self.db, item.trip_id, [item.assigned_to_user_id], "checklist_assignment", {"checklist_item_id": item.id})
        if "completed" in updates:
            notify(self.db, item.trip_id, active_recipient_ids(self.db, item.trip_id, user_id), "checklist_completed", {"checklist_item_id": item.id, "completed": item.completed})
        try:
            self.db.commit()
            self.db.refresh(item)
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to update checklist item.")
        return item

    def complete_item(self, item_id, user_id):
        return self.update_item(item_id, user_id, {"completed": True})

    def reopen_item(self, item_id, user_id):
        return self.update_item(item_id, user_id, {"completed": False})

    def delete_item(self, item_id, user_id):
        item = self.db.get(ChecklistItem, item_id)
        if item is None: raise AccessDenied("Checklist item not found.")
        member = self.access.member(item.trip_id, user_id)
        if member.role not in {"owner", "admin"} and item.created_by_user_id != user_id: raise AccessDenied("Checklist item cannot be deleted.")
        self.db.delete(item)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise RuntimeError("Failed to delete checklist item.")

    def update_message(self, message_id, user_id, body):
        item = self.db.get(GroupMessage, message_id)
        if item is None: raise AccessDenied("Message not found.")
        member = self.access.member(item.trip_id, user_id)
        if item.deleted_at is not None: raise ValueError("Deleted messages cannot be edited.")
        if item.sender_user_id != user_id and member.role not in {"owner", "admin"}: raise AccessDenied("Message cannot be edited.")
        body = body.strip()
        if not body or len(body) > 4000: raise ValueError("Message must be between 1 and 4000 characters.")
        item.body = body; item.edited_at = now(); self.db.commit(); return item

    def delete_message(self, message_id, user_id):
        item = self.db.get(GroupMessage, message_id)
        if item is None: raise AccessDenied("Message not found.")
        member = self.access.member(item.trip_id, user_id)
        if item.sender_user_id != user_id and member.role not in {"owner", "admin"}: raise AccessDenied("Message cannot be deleted.")
        if item.deleted_at is None:
            item.body = ""; item.deleted_at = now()
            try:
                self.db.commit()
            except SQLAlchemyError:
                self.db.rollback()
                raise RuntimeError("Failed to delete message.")
