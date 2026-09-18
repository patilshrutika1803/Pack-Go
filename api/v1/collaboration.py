import base64
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from api.v1.dependencies import get_current_user
from database import User
from database.connection import get_db
from database.models import ChecklistItem, Decision, GroupMessage, Notification, Proposal, ProposalVote, TripInvitation, TripMember
from models.api_schemas import (ChecklistItemCreateRequest, ChecklistItemResponse, ChecklistItemUpdateRequest, DecisionResponse, InvitationAcceptResponse, InvitationCreateRequest, InvitationPreviewResponse, InvitationResponse, MessageCreateRequest, MessagePageResponse, MessageResponse, NotificationListResponse, NotificationResponse, OwnershipTransferRequest, ProposalCreateRequest, ProposalListResponse, ProposalResponse, ProposalResultResponse, ProposalUpdateRequest, TripMemberListResponse, TripMemberResponse, TripMemberRoleUpdateRequest, VoteRequest, VoteResponse, WorkspaceResponse)
from services.collaboration_service import AccessDenied, CollaborationService, GroupTripService, ProposalService, proposal_result

router = APIRouter(prefix="/api/v1", tags=["Group Travel"])

def fail(exc: Exception, default: str = "Request denied."):
    if isinstance(exc, AccessDenied):
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Trip not found." else status.HTTP_403_FORBIDDEN
        detail = str(exc) if str(exc) in {"Trip not found.", "Proposal not found.", "Decision not found.", "Checklist item not found.", "Message not found."} else default
        raise HTTPException(code, detail=detail)
    if isinstance(exc, ValueError):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status.HTTP_409_CONFLICT, detail=default)

def member_out(member): return TripMemberResponse.model_validate(member)
def proposal_out(proposal):
    data = ProposalResponse.model_validate(proposal).model_dump()
    data["vote_count"] = len(proposal.votes)
    return ProposalResponse(**data)


def _message_cursor(created_at: datetime, message_id: str) -> str:
    value = f"{created_at.isoformat()}|{message_id}".encode()
    return base64.urlsafe_b64encode(value).decode()


def _parse_message_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        created_at, message_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(created_at), message_id
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid message cursor.") from exc

@router.post("/trips/{trip_id}/group", response_model=WorkspaceResponse)
def convert(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: GroupTripService(db).convert(trip_id, user.id); return WorkspaceResponse(**GroupTripService(db).workspace(trip_id, user.id))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.get("/trips/{trip_id}/workspace", response_model=WorkspaceResponse)
def workspace(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return WorkspaceResponse(**GroupTripService(db).workspace(trip_id, user.id))
    except AccessDenied as exc: fail(exc)

@router.get("/trips/{trip_id}/members", response_model=TripMemberListResponse)
def members(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return TripMemberListResponse(members=[member_out(m) for m in GroupTripService(db).workspace(trip_id, user.id)["members"]])
    except AccessDenied as exc: fail(exc)

@router.patch("/trips/{trip_id}/members/{user_id}", response_model=TripMemberResponse)
def update_member(trip_id: str, user_id: str, payload: TripMemberRoleUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return member_out(GroupTripService(db).update_member(trip_id, user.id, user_id, payload.role))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.delete("/trips/{trip_id}/members/{user_id}", status_code=204)
def remove_member(trip_id: str, user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: GroupTripService(db).remove_member(trip_id, user.id, user_id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/trips/{trip_id}/leave", status_code=204)
def leave(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: GroupTripService(db).leave(trip_id, user.id)
    except AccessDenied as exc: fail(exc)

@router.post("/trips/{trip_id}/ownership", response_model=TripMemberResponse)
def transfer_ownership(trip_id: str, payload: OwnershipTransferRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return member_out(GroupTripService(db).transfer_ownership(trip_id, user.id, payload.target_user_id))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/trips/{trip_id}/invitations", response_model=InvitationResponse, status_code=201)
def invite(trip_id: str, payload: InvitationCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        invitation, token = GroupTripService(db).invitation(trip_id, user.id, payload.invitee_user_id, payload.invitee_email, payload.expires_in_days)
        result = InvitationResponse.model_validate(invitation); result.token = token; return result
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.get("/trips/{trip_id}/invitations", response_model=list[InvitationResponse])
def invitations(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        GroupTripService(db).access.require_admin_or_owner(trip_id, user.id)
        rows = list(db.scalars(select(TripInvitation).where(TripInvitation.trip_id == trip_id).order_by(TripInvitation.created_at.desc())).all())
        changed = False
        for invitation in rows:
            if invitation.status == "pending" and invitation.expires_at <= datetime.now(UTC):
                invitation.status = "expired"
                changed = True
        if changed:
            db.commit()
        return rows
    except AccessDenied as exc: fail(exc)

@router.post("/invitations/{token}/accept", response_model=InvitationAcceptResponse)
def accept(token: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        invitation, membership = GroupTripService(db).accept(token, user)
        return InvitationAcceptResponse(invitation_id=invitation.id, trip_id=invitation.trip_id, membership=member_out(membership))
    except AccessDenied as exc: fail(exc)

@router.get("/invitations/{token}", response_model=InvitationPreviewResponse)
def invitation_preview(token: str, db: Session = Depends(get_db)):
    try: return InvitationPreviewResponse(**GroupTripService(db).invitation_preview(token))
    except AccessDenied as exc: fail(exc, "This invitation is no longer active.")

@router.post("/invitations/{invitation_id}/revoke", status_code=204)
def revoke_invitation(invitation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        GroupTripService(db).revoke_invitation(invitation_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/trip-invitations/{invitation_id}/revoke", status_code=204)
def revoke_trip_invitation(invitation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return revoke_invitation(invitation_id, db, user)

@router.post("/trips/{trip_id}/proposals", response_model=ProposalResponse, status_code=201)
def create_proposal(trip_id: str, payload: ProposalCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return proposal_out(ProposalService(db).create(trip_id, user.id, payload.model_dump()))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.get("/trips/{trip_id}/proposals", response_model=ProposalListResponse)
def list_proposals(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ProposalService(db).access.member(trip_id, user.id)
        return ProposalListResponse(proposals=[proposal_out(p) for p in db.scalars(select(Proposal).where(Proposal.trip_id == trip_id).order_by(Proposal.created_at.desc())).all()])
    except AccessDenied as exc: fail(exc)

@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
def get_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return proposal_out(ProposalService(db).get(proposal_id, user.id))
    except AccessDenied as exc: fail(exc)

@router.patch("/proposals/{proposal_id}", response_model=ProposalResponse)
def update_proposal(proposal_id: str, payload: ProposalUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return proposal_out(ProposalService(db).update(proposal_id, user.id, payload.model_dump(exclude_unset=True)))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/proposals/{proposal_id}/close", response_model=ProposalResponse)
def close_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return proposal_out(ProposalService(db).close(proposal_id, user.id))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.put("/proposals/{proposal_id}/vote", response_model=VoteResponse)
def vote(proposal_id: str, payload: VoteRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return ProposalService(db).vote(proposal_id, user.id, payload.choice_key)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.delete("/proposals/{proposal_id}/vote", status_code=204)
def delete_vote(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: ProposalService(db).remove_vote(proposal_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.get("/proposals/{proposal_id}/results", response_model=ProposalResultResponse)
def results(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        proposal = ProposalService(db).get(proposal_id, user.id)
        counts, winner, ties = proposal_result(proposal.votes)
        user_vote = next((vote.choice_key for vote in proposal.votes if vote.user_id == user.id), None)
        return ProposalResultResponse(proposal_id=proposal.id, status=proposal.status, counts=counts, winner=winner, ties=ties, user_vote=user_vote, decision=proposal.decision)
    except AccessDenied as exc: fail(exc)

@router.get("/proposals/{proposal_id}/decision", response_model=DecisionResponse)
def proposal_decision(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        proposal = ProposalService(db).get(proposal_id, user.id)
        if proposal.decision is None: raise HTTPException(404, detail="Decision not found.")
        return proposal.decision
    except AccessDenied as exc: fail(exc)

@router.post("/proposals/{proposal_id}/finalize", response_model=DecisionResponse)
def finalize(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return ProposalService(db).finalize(proposal_id, user.id)[1]
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/decisions/{decision_id}/apply", response_model=DecisionResponse)
def apply_decision(decision_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return ProposalService(db).apply(decision_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/decisions/{decision_id}/replan", response_model=DecisionResponse)
def replan_decision(decision_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return ProposalService(db).replan_destination(decision_id, user.id)
    except AccessDenied as exc: fail(exc)
    except ValueError as exc: fail(exc)
    except RuntimeError as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.get("/trips/{trip_id}/decisions", response_model=list[DecisionResponse])
def decisions(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: GroupTripService(db).access.member(trip_id, user.id); return list(db.scalars(select(Decision).where(Decision.trip_id == trip_id).order_by(Decision.created_at.desc())).all())
    except AccessDenied as exc: fail(exc)

@router.get("/trips/{trip_id}/checklist", response_model=list[ChecklistItemResponse])
def get_checklist(trip_id: str, completed: bool | None = None, assigned_to_user_id: str | None = None, overdue: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        GroupTripService(db).access.member(trip_id, user.id)
        filters = [ChecklistItem.trip_id == trip_id]
        if completed is not None: filters.append(ChecklistItem.completed == completed)
        if assigned_to_user_id is not None: filters.append(ChecklistItem.assigned_to_user_id == assigned_to_user_id)
        if overdue: filters.extend([ChecklistItem.completed.is_(False), ChecklistItem.due_at.is_not(None), ChecklistItem.due_at < datetime.now(UTC)])
        return list(db.scalars(select(ChecklistItem).where(and_(*filters)).order_by(ChecklistItem.completed, ChecklistItem.due_at, ChecklistItem.created_at, ChecklistItem.id)).all())
    except AccessDenied as exc: fail(exc)
    except AccessDenied as exc: fail(exc)

@router.post("/trips/{trip_id}/checklist", response_model=ChecklistItemResponse, status_code=201)
def add_checklist(trip_id: str, payload: ChecklistItemCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).checklist(trip_id, user.id, payload.model_dump())
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.patch("/checklist-items/{item_id}", response_model=ChecklistItemResponse)
def update_checklist(item_id: str, payload: ChecklistItemUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).update_item(item_id, user.id, payload.model_dump(exclude_unset=True))
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/checklist-items/{item_id}/complete", response_model=ChecklistItemResponse)
def complete_checklist(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).complete_item(item_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.post("/checklist-items/{item_id}/reopen", response_model=ChecklistItemResponse)
def reopen_checklist(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).reopen_item(item_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.delete("/checklist-items/{item_id}", status_code=204)
def delete_checklist(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: CollaborationService(db).delete_item(item_id, user.id)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.get("/trips/{trip_id}/messages", response_model=MessagePageResponse)
def get_messages(trip_id: str, limit: int = Query(50, ge=1, le=100), cursor: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        GroupTripService(db).access.member(trip_id, user.id)
        query = select(GroupMessage).where(GroupMessage.trip_id == trip_id)
        if cursor:
            created_at, message_id = _parse_message_cursor(cursor)
            query = query.where((GroupMessage.created_at < created_at) | ((GroupMessage.created_at == created_at) & (GroupMessage.id < message_id)))
        messages = list(db.scalars(query.order_by(GroupMessage.created_at.desc(), GroupMessage.id.desc()).limit(limit + 1)).all())
        has_more = len(messages) > limit
        messages = messages[:limit]
        messages.reverse()
        next_cursor = _message_cursor(messages[0].created_at, messages[0].id) if has_more and messages else None
        return MessagePageResponse(messages=messages, next_cursor=next_cursor)
    except AccessDenied as exc: fail(exc)

@router.post("/trips/{trip_id}/messages", response_model=MessageResponse, status_code=201)
def send_message(trip_id: str, payload: MessageCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).message(trip_id, user.id, payload.body)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.patch("/messages/{message_id}", response_model=MessageResponse)
def update_message(message_id: str, payload: MessageCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: return CollaborationService(db).update_message(message_id, user.id, payload.body)
    except (AccessDenied, ValueError) as exc: fail(exc)

@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try: CollaborationService(db).delete_message(message_id, user.id)
    except AccessDenied as exc: fail(exc)

@router.get("/notifications", response_model=NotificationListResponse)
def get_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotificationListResponse(notifications=list(db.scalars(select(Notification).where(Notification.recipient_user_id == user.id).order_by(Notification.created_at.desc()).limit(100)).all()))

@router.get("/notifications/unread-count")
def unread_notification_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"count": db.query(Notification).filter(Notification.recipient_user_id == user.id, Notification.read_at.is_(None)).count()}

@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.recipient_user_id == user.id))
    if notification is None: raise HTTPException(404, detail="Notification not found.")
    notification.read_at = datetime.now(UTC); db.commit(); return notification

@router.post("/notifications/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for item in db.scalars(select(Notification).where(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))).all(): item.read_at = datetime.now(UTC)
    db.commit()
