from __future__ import annotations

import hashlib
import secrets
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pymongo.database import Database


class AccessDenied(Exception):
    pass


def now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _trip_filter(trip_id: str) -> dict[str, Any]:
    return {"$or": [{"_id": trip_id}, {"id": trip_id}]}


def _embedded_trip(database: Database, array_name: str, record_id: str) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    trip = database.trips.find_one({f"{array_name}.id": record_id})
    if trip is None:
        return None, None
    record = next((item for item in trip.get(array_name, []) if item.get("id") == record_id), None)
    return trip, record


def _set_trip_fields(database: Database, trip: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    database.trips.update_one(_trip_filter(str(trip.get("_id", trip.get("id")))), {"$set": fields})
    trip.update(fields)
    return trip


def _save_embedded(database: Database, trip: dict[str, Any], array_name: str, records: list[dict[str, Any]]) -> None:
    _set_trip_fields(database, trip, {array_name: records, "updated_at": now()})


def _replace_record(records: list[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    return [record if item.get("id") == record.get("id") else item for item in records]


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def notify(database: Database, trip_id: str | None, recipients: list[str], event_type: str, payload: dict[str, Any]) -> None:
    created_at = now()
    for recipient_id in set(recipients):
        notification_id = str(uuid4())
        database.notifications.insert_one({
            "_id": notification_id,
            "id": notification_id,
            "recipient_user_id": recipient_id,
            "trip_id": trip_id,
            "event_type": event_type,
            "payload": deepcopy(payload),
            "read_at": None,
            "created_at": created_at,
        })


def active_recipient_ids(database: Database, trip_id: str, exclude: str | None = None) -> list[str]:
    trip = database.trips.find_one(_trip_filter(trip_id), {"members": 1})
    if trip is None:
        return []
    return [
        member["user_id"]
        for member in trip.get("members", [])
        if member.get("status") == "active"
        and member.get("user_id")
        and member.get("user_id") != exclude
    ]


def validate_proposal_payload(proposal_type: str, payload: dict[str, Any]) -> None:
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
        if field in payload and (
            not isinstance(payload[field], str)
            or not payload[field].strip()
            or len(payload[field]) > 4000
        ):
            raise ValueError(f"{field} must be a non-empty string of at most 4000 characters.")


def proposal_result(votes: list[dict[str, Any]]) -> tuple[dict[str, int], str | None, list[str]]:
    counts = dict(sorted(Counter(vote["choice_key"] for vote in votes).items()))
    highest = max(counts.values(), default=0)
    ties = [choice for choice, count in counts.items() if count == highest] if highest else []
    return counts, ties[0] if len(ties) == 1 else None, ties if len(ties) > 1 else []


class TripAccessService:
    def __init__(self, database: Database):
        self.db = database

    def get_trip_for_member(self, trip_id: str, user_id: str) -> dict[str, Any]:
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        is_member = trip and any(
            member.get("user_id") == user_id and member.get("status") == "active"
            for member in trip.get("members", [])
        )
        if trip is None or (trip.get("is_group") and not is_member) or (
            not trip.get("is_group") and trip.get("user_id") != user_id
        ):
            raise AccessDenied("Trip not found.")
        return trip

    def list_trips_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return list(self.db.trips.find({
            "$or": [
                {"user_id": user_id},
                {"members": {"$elemMatch": {"user_id": user_id, "status": "active"}}},
            ]
        }).sort([("created_at", -1), ("_id", -1)]))

    def member(self, trip_id: str, user_id: str) -> dict[str, Any]:
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        if trip is None or not trip.get("is_group"):
            raise AccessDenied("Trip not found.")
        member = next((
            item for item in trip.get("members", [])
            if item.get("user_id") == user_id and item.get("status") == "active"
        ), None)
        if member is None:
            raise AccessDenied("Trip not found.")
        result = dict(member)
        result["user"] = self.db.users.find_one({"_id": member["user_id"]})
        return result

    def require_active_member(self, trip_id: str, user_id: str) -> dict[str, Any]:
        return self.member(trip_id, user_id)

    def get_trip_for_role(self, trip_id: str, user_id: str, roles: set[str] | tuple[str, ...]) -> dict[str, Any]:
        trip = self.get_trip_for_member(trip_id, user_id)
        member = self.member(trip_id, user_id)
        if member["role"] not in set(roles):
            raise AccessDenied("Insufficient trip permissions.")
        return trip

    def require_owner(self, trip_id: str, user_id: str) -> dict[str, Any]:
        self.get_trip_for_member(trip_id, user_id)
        member = self.member(trip_id, user_id)
        if member["role"] == "owner":
            return member
        raise AccessDenied("Owner access required.")

    def require_admin_or_owner(self, trip_id: str, user_id: str) -> dict[str, Any]:
        self.get_trip_for_member(trip_id, user_id)
        member = self.member(trip_id, user_id)
        if member["role"] not in {"owner", "admin"}:
            raise AccessDenied("Administrator access required.")
        return member

    def require_can_edit_trip(self, trip_id: str, user_id: str) -> dict[str, Any] | None:
        trip = self.get_trip_for_member(trip_id, user_id)
        return self.require_admin_or_owner(trip_id, user_id) if trip.get("is_group") else None

    def require_can_delete_trip(self, trip_id: str, user_id: str) -> dict[str, Any] | None:
        trip = self.get_trip_for_member(trip_id, user_id)
        return self.require_owner(trip_id, user_id) if trip.get("is_group") else None

    def require_can_vote(self, trip_id: str, user_id: str) -> dict[str, Any]:
        return self.member(trip_id, user_id)


class GroupTripService:
    def __init__(self, database: Database):
        self.db = database
        self.access = TripAccessService(database)

    def convert(self, trip_id: str, user_id: str) -> dict[str, Any]:
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        if trip is None or trip.get("user_id") != user_id:
            raise AccessDenied("Trip not found.")
        members = list(trip.get("members", []))
        member = next((item for item in members if item.get("user_id") == user_id), None)
        current = now()
        if member is None:
            members.append({
                "id": str(uuid4()), "trip_id": trip_id, "user_id": user_id,
                "role": "owner", "status": "active", "joined_at": current,
                "updated_at": current, "left_at": None, "removed_at": None,
            })
        elif member.get("status") != "active":
            member.update({
                "status": "active", "role": "owner", "joined_at": current,
                "updated_at": current, "left_at": None, "removed_at": None,
            })
        return _set_trip_fields(self.db, trip, {
            "is_group": True, "members": members, "updated_at": current,
        })

    def workspace(self, trip_id: str, user_id: str) -> dict[str, Any]:
        self.access.member(trip_id, user_id)
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        members = []
        for member in trip.get("members", []):
            if member.get("status") == "active":
                result = dict(member)
                result["user"] = self.db.users.find_one({"_id": member["user_id"]})
                members.append(result)
        members.sort(key=lambda item: as_utc(item["joined_at"]) if item.get("joined_at") else datetime.min.replace(tzinfo=UTC))
        return {"trip_id": trip_id, "is_group": True, "member_count": len(members), "members": members}

    def update_member(self, trip_id: str, actor_id: str, target_id: str, role: str) -> dict[str, Any]:
        actor = self.access.require_admin_or_owner(trip_id, actor_id)
        self.access.member(trip_id, target_id)
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        target = next(item for item in trip["members"] if item.get("user_id") == target_id and item.get("status") == "active")
        if target["role"] == "owner" or (actor["role"] != "owner" and target["role"] == "admin"):
            raise AccessDenied("Member role cannot be changed.")
        target.update({"role": role, "updated_at": now()})
        _save_embedded(self.db, trip, "members", trip["members"])
        notify(self.db, trip_id, [target_id], "role_changed", {"trip_id": trip_id})
        return self._member_with_user(target)

    def remove_member(self, trip_id: str, actor_id: str, target_id: str) -> None:
        actor = self.access.require_admin_or_owner(trip_id, actor_id)
        self.access.member(trip_id, target_id)
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        target = next(item for item in trip["members"] if item.get("user_id") == target_id and item.get("status") == "active")
        if target["role"] == "owner" or (actor["role"] != "owner" and target["role"] == "admin"):
            raise AccessDenied("Member cannot be removed.")
        target.update({"status": "removed", "removed_at": now(), "updated_at": now()})
        for item in trip.get("checklist_items", []):
            if item.get("assigned_to_user_id") == target_id:
                item.update({"assigned_to_user_id": None, "updated_at": now()})
        _set_trip_fields(self.db, trip, {
            "members": trip["members"], "checklist_items": trip.get("checklist_items", []),
            "updated_at": now(),
        })
        notify(self.db, trip_id, [target_id], "member_removed", {"trip_id": trip_id})

    def leave(self, trip_id: str, user_id: str) -> None:
        member = self.access.member(trip_id, user_id)
        if member["role"] == "owner":
            raise AccessDenied("Owner must transfer ownership before leaving.")
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        current = now()
        target = next(item for item in trip["members"] if item.get("user_id") == user_id and item.get("status") == "active")
        target.update({"status": "left", "left_at": current, "updated_at": current})
        for item in trip.get("checklist_items", []):
            if item.get("assigned_to_user_id") == user_id:
                item.update({"assigned_to_user_id": None, "updated_at": current})
        _set_trip_fields(self.db, trip, {
            "members": trip["members"], "checklist_items": trip.get("checklist_items", []),
            "updated_at": current,
        })
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "member_left", {
            "trip_id": trip_id, "user_id": user_id,
        })

    def transfer_ownership(self, trip_id: str, actor_id: str, target_id: str) -> dict[str, Any]:
        self.access.require_owner(trip_id, actor_id)
        if target_id == actor_id:
            raise ValueError("Ownership is already assigned to this user.")
        self.access.member(trip_id, target_id)
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        members = trip["members"]
        current = next(item for item in members if item.get("user_id") == actor_id and item.get("status") == "active")
        target = next(item for item in members if item.get("user_id") == target_id and item.get("status") == "active")
        changed_at = now()
        current.update({"role": "admin", "updated_at": changed_at})
        target.update({"role": "owner", "updated_at": changed_at})
        _set_trip_fields(self.db, trip, {"members": members, "user_id": target_id, "updated_at": changed_at})
        notify(self.db, trip_id, [actor_id, target_id], "ownership_transferred", {"trip_id": trip_id})
        return self._member_with_user(target)

    def invitation(
        self, trip_id: str, actor_id: str, invitee_user_id: str | None,
        invitee_email: str | None, expires_days: int,
    ) -> tuple[dict[str, Any], str]:
        self.access.require_admin_or_owner(trip_id, actor_id)
        if invitee_user_id and invitee_email:
            raise ValueError("Provide at most one invitation target.")
        if invitee_user_id and self.db.users.find_one({"_id": invitee_user_id}) is None:
            raise ValueError("Invitee user was not found.")
        normalized_email = invitee_email.lower().strip() if invitee_email else None
        if normalized_email:
            existing_user = self.db.users.find_one({"email": normalized_email})
            if existing_user is not None:
                invitee_user_id = existing_user["_id"]
                normalized_email = None
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        members = trip.get("members", [])
        if invitee_user_id and any(
            item.get("user_id") == invitee_user_id and item.get("status") == "active"
            for item in members
        ):
            raise ValueError("User is already a member.")
        invitations = list(trip.get("invitations", []))
        current = now()
        duplicate = any(
            item.get("status") == "pending"
            and as_utc(item["expires_at"]) > current
            and (
                item.get("invitee_user_id") == invitee_user_id if invitee_user_id
                else item.get("invitee_email") == normalized_email if normalized_email
                else item.get("invitee_user_id") is None and item.get("invitee_email") is None
            )
            for item in invitations
        )
        if duplicate:
            raise ValueError("An active invitation already exists.")
        raw = secrets.token_urlsafe(32)
        invitation = {
            "id": str(uuid4()), "trip_id": trip_id, "inviter_user_id": actor_id,
            "invitee_user_id": invitee_user_id, "invitee_email": normalized_email,
            "token_hash": token_digest(raw), "status": "pending",
            "expires_at": current + timedelta(days=expires_days), "accepted_at": None,
            "created_at": current, "updated_at": current,
        }
        invitations.append(invitation)
        _save_embedded(self.db, trip, "invitations", invitations)
        if invitee_user_id:
            notify(self.db, trip_id, [invitee_user_id], "invitation_created", {"invitation_id": invitation["id"]})
        return invitation, raw

    def invitation_preview(self, raw_token: str) -> dict[str, Any]:
        trip = self.db.trips.find_one({"invitations.token_hash": token_digest(raw_token)})
        invitation = next((
            item for item in (trip or {}).get("invitations", [])
            if item.get("token_hash") == token_digest(raw_token)
        ), None)
        if invitation is None:
            raise AccessDenied("Invitation not found.")
        if invitation["status"] == "pending" and as_utc(invitation["expires_at"]) <= now():
            invitation.update({"status": "expired", "updated_at": now()})
            _save_embedded(self.db, trip, "invitations", trip["invitations"])
        if trip is None:
            raise AccessDenied("Invitation not found.")
        member_count = sum(1 for item in trip.get("members", []) if item.get("status") == "active")
        return {
            "trip_id": invitation["trip_id"], "trip_title": trip["title"],
            "destination": trip["destination"], "duration": trip["duration"],
            "member_count": member_count, "expires_at": invitation["expires_at"],
            "status": invitation["status"],
        }

    def accept(self, raw_token: str, user: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        digest = token_digest(raw_token)
        trip = self.db.trips.find_one({"invitations.token_hash": digest})
        invitation = next((
            item for item in (trip or {}).get("invitations", [])
            if item.get("token_hash") == digest
        ), None)
        if (
            invitation is None or invitation["status"] != "pending"
            or as_utc(invitation["expires_at"]) <= now()
            or (invitation.get("invitee_user_id") and invitation["invitee_user_id"] != user.id)
            or (invitation.get("invitee_email") and invitation["invitee_email"].lower() != user.email.lower())
        ):
            raise AccessDenied("Invitation is invalid or expired.")
        accepted_at = now()
        trip_query = _trip_filter(str(trip.get("_id", trip.get("id"))))
        claimed = self.db.trips.update_one(
            {"$and": [trip_query, {"invitations": {"$elemMatch": {"id": invitation["id"], "status": "pending"}}}]},
            {"$set": {"invitations.$.status": "accepted", "invitations.$.accepted_at": accepted_at,
                      "invitations.$.updated_at": accepted_at, "updated_at": accepted_at}},
        )
        if claimed.modified_count != 1:
            raise AccessDenied("Invitation is invalid or expired.")
        trip = self.db.trips.find_one(_trip_filter(str(trip.get("_id", trip.get("id")))))
        invitation = next(item for item in trip["invitations"] if item["id"] == invitation["id"])
        members = trip.get("members", [])
        member = next((item for item in members if item.get("user_id") == user.id), None)
        if member is None:
            member = {
                "id": str(uuid4()), "trip_id": invitation["trip_id"], "user_id": user.id,
                "role": "member", "status": "active", "joined_at": accepted_at,
                "updated_at": accepted_at, "left_at": None, "removed_at": None,
            }
            members.append(member)
        else:
            member.update({"status": "active", "left_at": None, "removed_at": None, "updated_at": accepted_at})
            member.setdefault("joined_at", accepted_at)
        _save_embedded(self.db, trip, "members", members)
        notify(self.db, invitation["trip_id"], active_recipient_ids(self.db, invitation["trip_id"], user.id), "member_joined", {
            "trip_id": invitation["trip_id"],
        })
        return invitation, self._member_with_user(member)

    def revoke_invitation(self, invitation_id: str, actor_id: str) -> None:
        trip, invitation = _embedded_trip(self.db, "invitations", invitation_id)
        if invitation is None:
            raise AccessDenied("Invitation not found.")
        self.access.require_admin_or_owner(invitation["trip_id"], actor_id)
        if invitation["status"] != "pending":
            raise ValueError("Only pending invitations can be revoked.")
        invitation.update({"status": "revoked", "updated_at": now()})
        _save_embedded(self.db, trip, "invitations", _replace_record(trip["invitations"], invitation))
        notify(self.db, invitation["trip_id"], active_recipient_ids(self.db, invitation["trip_id"], actor_id), "invitation_revoked", {
            "invitation_id": invitation["id"],
        })

    def list_invitations(self, trip_id: str) -> list[dict[str, Any]]:
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        rows = list(trip.get("invitations", [])) if trip else []
        current = now()
        changed = False
        for invitation in rows:
            if invitation.get("status") == "pending" and as_utc(invitation["expires_at"]) <= current:
                invitation.update({"status": "expired", "updated_at": current})
                changed = True
        if changed:
            _save_embedded(self.db, trip, "invitations", rows)
        return sorted(
            rows,
            key=lambda item: as_utc(item["created_at"]) if item.get("created_at") else datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    def _member_with_user(self, member: dict[str, Any]) -> dict[str, Any]:
        result = dict(member)
        result["user"] = self.db.users.find_one({"_id": member["user_id"]})
        return result


class ProposalService:
    def __init__(self, database: Database):
        self.db = database
        self.access = TripAccessService(database)

    def create(self, trip_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.access.member(trip_id, user_id)
        validate_proposal_payload(data["proposal_type"], data["payload"])
        if data.get("deadline") and as_utc(data["deadline"]) <= now():
            raise ValueError("Deadline must be in the future.")
        data = dict(data)
        data["title"] = data["title"].strip()
        if data.get("description") is not None:
            data["description"] = data["description"].strip() or None
        data["payload"] = deepcopy(data["payload"])
        created_at = now()
        proposal = {
            **data, "id": str(uuid4()), "trip_id": trip_id,
            "created_by_user_id": user_id, "payload_history": [deepcopy(data["payload"])],
            "status": "open", "created_at": created_at, "updated_at": created_at,
            "closed_at": None, "votes": [],
        }
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        proposals = list(trip.get("proposals", []))
        proposals.append(proposal)
        _save_embedded(self.db, trip, "proposals", proposals)
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "proposal_created", {
            "proposal_id": proposal["id"],
        })
        return proposal

    def get(self, proposal_id: str, user_id: str) -> dict[str, Any]:
        trip, proposal = _embedded_trip(self.db, "proposals", proposal_id)
        if proposal is None:
            raise AccessDenied("Proposal not found.")
        self.access.member(proposal["trip_id"], user_id)
        result = dict(proposal)
        result["decision"] = next((
            item for item in trip.get("decisions", [])
            if item.get("proposal_id") == proposal_id
        ), None)
        return result

    def vote(self, proposal_id: str, user_id: str, choice: str) -> dict[str, Any]:
        self.get(proposal_id, user_id)
        choice = choice.strip()
        if not choice or len(choice) > 120:
            raise ValueError("Vote choice must be between 1 and 120 characters.")
        trip, stored = _embedded_trip(self.db, "proposals", proposal_id)
        if stored.get("deadline") and as_utc(stored["deadline"]) <= now():
            stored.update({"status": "closed", "closed_at": now(), "updated_at": now()})
            _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], stored))
            raise ValueError("Voting is closed.")
        if stored["status"] != "open":
            raise ValueError("Voting is closed.")
        votes = list(stored.get("votes", []))
        vote = next((item for item in votes if item.get("user_id") == user_id), None)
        if vote is None:
            current = now()
            vote = {
                "id": str(uuid4()), "proposal_id": proposal_id, "user_id": user_id,
                "choice_key": choice, "created_at": current, "updated_at": current,
            }
            votes.append(vote)
        else:
            vote.update({"choice_key": choice, "updated_at": now()})
        stored["votes"] = votes
        stored["updated_at"] = now()
        _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], stored))
        notify(self.db, stored["trip_id"], active_recipient_ids(self.db, stored["trip_id"], user_id), "vote_activity", {
            "proposal_id": proposal_id,
        })
        return vote

    def remove_vote(self, proposal_id: str, user_id: str) -> None:
        self.get(proposal_id, user_id)
        trip, proposal = _embedded_trip(self.db, "proposals", proposal_id)
        if proposal["status"] != "open" or (
            proposal.get("deadline") and as_utc(proposal["deadline"]) <= now()
        ):
            raise ValueError("Voting is closed.")
        votes = list(proposal.get("votes", []))
        remaining = [vote for vote in votes if vote.get("user_id") != user_id]
        if len(remaining) != len(votes):
            proposal.update({"votes": remaining, "updated_at": now()})
            _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], proposal))
            notify(self.db, proposal["trip_id"], active_recipient_ids(self.db, proposal["trip_id"], user_id), "vote_activity", {
                "proposal_id": proposal_id,
            })

    def finalize(self, proposal_id: str, user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        trip, proposal = _embedded_trip(self.db, "proposals", proposal_id)
        if proposal is None:
            raise AccessDenied("Proposal not found.")
        actor = self.access.require_admin_or_owner(proposal["trip_id"], user_id)
        if any(item.get("proposal_id") == proposal_id for item in trip.get("decisions", [])):
            raise ValueError("Proposal has already been finalized.")
        if proposal["status"] != "open":
            raise ValueError("Proposal is already closed.")
        if proposal.get("deadline") and as_utc(proposal["deadline"]) <= now():
            proposal.update({"status": "closed", "closed_at": now(), "updated_at": now()})
            _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], proposal))
            raise ValueError("Proposal deadline has passed.")
        counts, winner, ties = proposal_result(proposal.get("votes", []))
        result = "accepted" if winner else "rejected"
        created_at = now()
        decision = {
            "id": str(uuid4()), "trip_id": proposal["trip_id"], "proposal_id": proposal["id"],
            "decided_by_user_id": actor["user_id"], "result": result,
            "decision_type": f"selected_{proposal['proposal_type']}", "vote_counts": counts,
            "proposal_snapshot": deepcopy(proposal["payload"]),
            "applied_action": {"winner": winner, "ties": ties, "applied": False},
            "source_revision": len(trip.get("revision_history") or []),
            "target_revision": None, "created_at": created_at,
        }
        proposal.update({"status": "accepted" if winner else "rejected", "closed_at": created_at, "updated_at": created_at})
        decisions = list(trip.get("decisions", []))
        decisions.append(decision)
        identity = str(trip.get("_id", trip.get("id")))
        updated = self.db.trips.update_one(
            {"$and": [
                _trip_filter(identity),
                {"proposals": {"$elemMatch": {"id": proposal_id, "status": "open"}}},
                {"decisions.proposal_id": {"$ne": proposal_id}},
            ]},
            {"$set": {"proposals": _replace_record(trip["proposals"], proposal), "decisions": decisions,
                      "updated_at": created_at}},
        )
        if updated.modified_count != 1:
            raise ValueError("Proposal has already been finalized.")
        notify(self.db, proposal["trip_id"], active_recipient_ids(self.db, proposal["trip_id"], user_id), "decision_finalized", {
            "decision_id": decision["id"], "proposal_id": proposal["id"],
        })
        return proposal, decision

    def close(self, proposal_id: str, user_id: str) -> dict[str, Any]:
        proposal = self.get(proposal_id, user_id)
        self.access.require_admin_or_owner(proposal["trip_id"], user_id)
        if proposal["status"] != "open":
            raise ValueError("Proposal is already closed.")
        trip, stored = _embedded_trip(self.db, "proposals", proposal_id)
        stored.update({"status": "closed", "closed_at": now(), "updated_at": now()})
        _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], stored))
        notify(self.db, stored["trip_id"], active_recipient_ids(self.db, stored["trip_id"], user_id), "proposal_closed", {
            "proposal_id": proposal_id,
        })
        return stored

    def update(self, proposal_id: str, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        proposal = self.get(proposal_id, user_id)
        member = self.access.member(proposal["trip_id"], user_id)
        if proposal["status"] != "open" or (
            proposal["created_by_user_id"] != user_id and member["role"] not in {"owner", "admin"}
        ):
            raise AccessDenied("Proposal cannot be edited.")
        if "deadline" in updates and updates["deadline"] is not None and as_utc(updates["deadline"]) <= now():
            raise ValueError("Deadline must be in the future.")
        validate_proposal_payload(updates.get("proposal_type", proposal["proposal_type"]), updates.get("payload", proposal["payload"]))
        trip, stored = _embedded_trip(self.db, "proposals", proposal_id)
        for key, value in updates.items():
            if value is not None:
                stored[key] = deepcopy(value) if key == "payload" else value.strip() if isinstance(value, str) else value
        if "payload" in updates:
            stored["payload_history"] = [*(stored.get("payload_history") or []), deepcopy(updates["payload"])]
        stored["updated_at"] = now()
        _save_embedded(self.db, trip, "proposals", _replace_record(trip["proposals"], stored))
        notify(self.db, stored["trip_id"], active_recipient_ids(self.db, stored["trip_id"], user_id), "proposal_updated", {
            "proposal_id": proposal_id,
        })
        return stored

    def replan_destination(self, decision_id: str, user_id: str) -> dict[str, Any]:
        trip, decision = _embedded_trip(self.db, "decisions", decision_id)
        if decision is None:
            raise AccessDenied("Decision not found.")
        self.access.require_admin_or_owner(decision["trip_id"], user_id)
        action = dict(decision.get("applied_action") or {})
        if action.get("replanning") == "completed":
            return decision
        if not action.get("applied") or decision["decision_type"] != "selected_destination":
            raise ValueError("Only an applied destination decision can be replanned.")
        from services.trip_service import TripService

        trip_id = decision["trip_id"]
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        try:
            for day_number in range(1, len(trip.get("itinerary") or []) + 1):
                TripService(self.db).regenerate_day(trip_id, day_number)
        except Exception as exc:
            action["replanning"] = "failed"
            action["replanning_error"] = "Itinerary replanning failed."
            decision["applied_action"] = action
            _save_embedded(self.db, trip, "decisions", _replace_record(trip["decisions"], decision))
            raise RuntimeError("Destination replanning failed; the decision was preserved.") from exc
        trip = self.db.trips.find_one(_trip_filter(trip_id))
        action["replanning"] = "completed"
        decision.update({
            "applied_action": action,
            "target_revision": len(trip.get("revision_history") or []),
        })
        _save_embedded(self.db, trip, "decisions", _replace_record(trip["decisions"], decision))
        return decision

    def apply(self, decision_id: str, user_id: str) -> dict[str, Any]:
        trip, decision = _embedded_trip(self.db, "decisions", decision_id)
        if decision is None:
            raise AccessDenied("Decision not found.")
        self.access.require_admin_or_owner(decision["trip_id"], user_id)
        if decision.get("applied_action") and decision["applied_action"].get("applied"):
            return decision
        proposal = next((
            item for item in trip.get("proposals", [])
            if item.get("id") == decision.get("proposal_id")
        ), None)
        if proposal is None or decision["result"] != "accepted":
            decision["applied_action"] = {
                **(decision.get("applied_action") or {}), "applied": False,
                "reason": "No accepted proposal to apply.",
            }
            _save_embedded(self.db, trip, "decisions", _replace_record(trip["decisions"], decision))
            return decision
        payload = deepcopy(decision["proposal_snapshot"])
        validate_proposal_payload(proposal["proposal_type"], payload)
        itinerary = deepcopy(trip.get("itinerary") or [])
        day_number = payload.get("day_number")
        source_revision = len(trip.get("revision_history") or [])
        before: dict[str, Any] = {"destination": trip.get("destination"), "day_number": day_number}
        applied = False
        target = None
        after = None
        changes: dict[str, Any] = {}
        if proposal["proposal_type"] == "destination":
            before["value"] = trip.get("destination")
            changes["destination"] = payload["destination"].strip()
            changes["title"] = changes["destination"]
            target = {"target": "trip.destination", "replanning": "required"}
            applied = True
        elif day_number is not None:
            day_index = next((
                index for index, candidate in enumerate(itinerary)
                if isinstance(candidate, dict) and candidate.get("day_number") == day_number
            ), None)
            if day_index is None and 1 <= day_number <= len(itinerary):
                day_index = day_number - 1
            day = dict(itinerary[day_index]) if day_index is not None else None
            replacement = payload.get("value", payload.get("name"))
            if day is not None and not isinstance(replacement, str):
                replacement = None
            if day is not None and replacement:
                if proposal["proposal_type"] == "hotel":
                    before["value"] = day.get("hotel")
                    day["hotel"] = replacement
                    target = {"day_number": day_number, "field": "hotel"}
                    applied = True
                elif proposal["proposal_type"] == "restaurant" and 0 <= payload["meal_index"] < len(day.get("meals", [])):
                    meals = list(day.get("meals", []))
                    before["value"] = meals[payload["meal_index"]]
                    meals[payload["meal_index"]] = replacement
                    day["meals"] = meals
                    target = {"day_number": day_number, "field": "meals", "index": payload["meal_index"]}
                    applied = True
                elif proposal["proposal_type"] == "activity" and 0 <= payload["activity_index"] < len(day.get("activities", [])):
                    activities = list(day.get("activities", []))
                    before["value"] = activities[payload["activity_index"]]
                    activities[payload["activity_index"]] = replacement
                    day["activities"] = activities
                    target = {"day_number": day_number, "field": "activities", "index": payload["activity_index"]}
                    applied = True
                elif proposal["proposal_type"] == "itinerary_item" and 0 <= payload.get("item_index", -1) < len(day.get("activities", [])):
                    activities = list(day.get("activities", []))
                    before["value"] = activities[payload["item_index"]]
                    activities[payload["item_index"]] = replacement
                    day["activities"] = activities
                    target = {"day_number": day_number, "field": "activities", "index": payload["item_index"]}
                    applied = True
                if applied:
                    itinerary[day_index] = day
                    changes["itinerary"] = itinerary
        target_revision = source_revision + (1 if applied else 0)
        if applied:
            destination = changes.get("destination", trip.get("destination"))
            after = {"destination": destination, "day_number": day_number}
            if target and target.get("field"):
                value = itinerary[day_index][target["field"]]
                after["value"] = value[target["index"]] if "index" in target else value
            else:
                after["value"] = destination
            changes["revision_history"] = [
                *(trip.get("revision_history") or []),
                {
                    "iteration": target_revision, "decision_id": decision["id"],
                    "changed_by_user_id": user_id, "change_type": proposal["proposal_type"],
                    "source_revision": source_revision, "target_revision": target_revision,
                    "before": before, "after": after,
                },
            ]
            notify(self.db, decision["trip_id"], active_recipient_ids(self.db, decision["trip_id"], user_id), "itinerary_changed", {
                "decision_id": decision["id"], "change_type": proposal["proposal_type"],
            })
        decision["target_revision"] = target_revision
        decision["applied_action"] = {
            **(decision.get("applied_action") or {}), "applied": applied,
            "reason": None if applied else "Proposal target could not be mapped safely.",
            "before": before, "after": after if applied else None, "target": target,
        }
        changes.update({
            "decisions": _replace_record(trip.get("decisions", []), decision),
            "updated_at": now(),
        })
        _set_trip_fields(self.db, trip, changes)
        return decision


class CollaborationService:
    def __init__(self, database: Database):
        self.db = database
        self.access = TripAccessService(database)

    def checklist(self, trip_id: str, user_id: str, data: dict[str, Any] | None = None, item_id: str | None = None) -> dict[str, Any]:
        self.access.member(trip_id, user_id)
        if item_id:
            trip = self.db.trips.find_one(_trip_filter(trip_id))
            item = next((entry for entry in trip.get("checklist_items", []) if entry.get("id") == item_id), None)
            return item
        data = dict(data or {})
        data["title"] = data["title"].strip()
        if data.get("description") is not None:
            data["description"] = data["description"].strip() or None
        assigned = data.get("assigned_to_user_id")
        if assigned and not self._is_active_member(trip_id, assigned):
            raise ValueError("Assignee must be an active member.")
        current = now()
        item = {
            **data, "id": str(uuid4()), "trip_id": trip_id,
            "created_by_user_id": user_id, "completed": False,
            "completed_by_user_id": None, "completed_at": None,
            "created_at": current, "updated_at": current,
        }
        trip_doc = self.db.trips.find_one(_trip_filter(trip_id))
        items = list(trip_doc.get("checklist_items", []))
        items.append(item)
        _save_embedded(self.db, trip_doc, "checklist_items", items)
        if assigned:
            notify(self.db, trip_id, [assigned], "checklist_assignment", {"checklist_item_id": item["id"]})
        return item

    def message(self, trip_id: str, user_id: str, body: str) -> dict[str, Any]:
        self.access.member(trip_id, user_id)
        body = body.strip()
        if not body or len(body) > 4000:
            raise ValueError("Message must be between 1 and 4000 characters.")
        message_id = str(uuid4())
        message = {
            "_id": message_id, "id": message_id, "trip_id": trip_id,
            "sender_user_id": user_id, "body": body, "created_at": now(),
            "edited_at": None, "deleted_at": None,
        }
        self.db.trip_messages.insert_one(message)
        notify(self.db, trip_id, active_recipient_ids(self.db, trip_id, user_id), "message_created", {
            "message_id": message_id,
        })
        return message

    def update_item(self, item_id: str, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        trip, item = _embedded_trip(self.db, "checklist_items", item_id)
        if item is None:
            raise AccessDenied("Checklist item not found.")
        member = self.access.member(item["trip_id"], user_id)
        if member["role"] not in {"owner", "admin"} and item["created_by_user_id"] != user_id and item.get("assigned_to_user_id") != user_id:
            raise AccessDenied("Checklist item cannot be edited.")
        updates = dict(updates)
        assigned = updates.get("assigned_to_user_id")
        if "assigned_to_user_id" in updates and assigned and not self._is_active_member(item["trip_id"], assigned):
            raise ValueError("Assignee must be an active member.")
        previous_assignee = item.get("assigned_to_user_id")
        for key, value in updates.items():
            if key == "completed":
                item.update({
                    "completed": value, "completed_by_user_id": user_id if value else None,
                    "completed_at": now() if value else None,
                })
            elif key in {"title", "description"} and value is not None:
                item[key] = value.strip() if isinstance(value, str) else value
            elif value is not None:
                item[key] = value
        item["updated_at"] = now()
        _save_embedded(self.db, trip, "checklist_items", _replace_record(trip["checklist_items"], item))
        if item.get("assigned_to_user_id") and item["assigned_to_user_id"] != previous_assignee:
            notify(self.db, item["trip_id"], [item["assigned_to_user_id"]], "checklist_assignment", {
                "checklist_item_id": item["id"],
            })
        if "completed" in updates:
            notify(self.db, item["trip_id"], active_recipient_ids(self.db, item["trip_id"], user_id), "checklist_completed", {
                "checklist_item_id": item["id"], "completed": item["completed"],
            })
        return item

    def complete_item(self, item_id: str, user_id: str) -> dict[str, Any]:
        return self.update_item(item_id, user_id, {"completed": True})

    def reopen_item(self, item_id: str, user_id: str) -> dict[str, Any]:
        return self.update_item(item_id, user_id, {"completed": False})

    def delete_item(self, item_id: str, user_id: str) -> None:
        trip, item = _embedded_trip(self.db, "checklist_items", item_id)
        if item is None:
            raise AccessDenied("Checklist item not found.")
        member = self.access.member(item["trip_id"], user_id)
        if member["role"] not in {"owner", "admin"} and item["created_by_user_id"] != user_id:
            raise AccessDenied("Checklist item cannot be deleted.")
        _save_embedded(self.db, trip, "checklist_items", [
            entry for entry in trip["checklist_items"] if entry.get("id") != item_id
        ])

    def update_message(self, message_id: str, user_id: str, body: str) -> dict[str, Any]:
        item = self.db.trip_messages.find_one({"$or": [{"_id": message_id}, {"id": message_id}]})
        if item is None:
            raise AccessDenied("Message not found.")
        member = self.access.member(item["trip_id"], user_id)
        if item.get("deleted_at") is not None:
            raise ValueError("Deleted messages cannot be edited.")
        if item["sender_user_id"] != user_id and member["role"] not in {"owner", "admin"}:
            raise AccessDenied("Message cannot be edited.")
        body = body.strip()
        if not body or len(body) > 4000:
            raise ValueError("Message must be between 1 and 4000 characters.")
        edited_at = now()
        self.db.trip_messages.update_one(
            {"_id": item["_id"]}, {"$set": {"body": body, "edited_at": edited_at}}
        )
        item.update({"body": body, "edited_at": edited_at})
        return item

    def delete_message(self, message_id: str, user_id: str) -> None:
        item = self.db.trip_messages.find_one({"$or": [{"_id": message_id}, {"id": message_id}]})
        if item is None:
            raise AccessDenied("Message not found.")
        member = self.access.member(item["trip_id"], user_id)
        if item["sender_user_id"] != user_id and member["role"] not in {"owner", "admin"}:
            raise AccessDenied("Message cannot be deleted.")
        if item.get("deleted_at") is None:
            self.db.trip_messages.update_one(
                {"_id": item["_id"], "deleted_at": None},
                {"$set": {"body": "", "deleted_at": now()}},
            )

    def _is_active_member(self, trip_id: str, user_id: str) -> bool:
        trip = self.db.trips.find_one(_trip_filter(trip_id), {"members": 1})
        return bool(trip and any(
            member.get("user_id") == user_id and member.get("status") == "active"
            for member in trip.get("members", [])
        ))
