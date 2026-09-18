# Architecture Audit

No files were modified. No migrations, commits, or pushes were created.

## A. Existing Architecture Relevant to Groups

The current system has a single persistent trip aggregate:

- [`database/models.py`](database/models.py) defines `Trip`, `User`, `UserPreference`, authentication token models, and `KnowledgeSource`.
- `Trip.user_id` is the current ownership boundary.
- `TripService` performs owner-scoped reads and writes through `user_id`.
- The API returns `404 Not Found` when another user accesses a trip, intentionally avoiding resource disclosure.
- The frontend has one saved-trip workflow:
  - [`frontend/src/pages/TripsPage.jsx`](frontend/src/pages/TripsPage.jsx)
  - [`frontend/src/pages/TripDetailPage.jsx`](frontend/src/pages/TripDetailPage.jsx)
  - [`frontend/src/components/PlanCard.jsx`](frontend/src/components/PlanCard.jsx)

There is no separate group, workspace, collaboration, messaging, notification, or checklist abstraction.

The existing architecture should therefore extend `Trip` rather than introduce a duplicate `GroupTrip` or `CollaborativeTrip` model.

## B. Existing Models That Can Be Reused

### `User`

Reusable for:

- trip ownership
- membership identity
- invitation targets
- proposal creators
- vote authors
- checklist assignees
- chat senders
- notification recipients

Current role information is global only through `User.is_admin`. That must not be reused for group-level admin permissions. A user may be a normal application user but an admin of one specific trip.

### `Trip`

Reusable as the group workspace root.

Existing fields already cover:

- title
- destination
- dates
- group size
- budget
- preferences
- weather
- generated itinerary
- AI metadata

The existing `itinerary` is stored as a JSON array of `DayPlan` objects. Each day contains structured hotel, meal, attraction, activity, transport, and cost information, but there are no stable relational itinerary-item IDs.

### `UserPreference`

This remains personal preference data. It should not be copied into group membership or treated as the shared trip preference record.

A group trip may use the owner's or creator's preferences for initial AI generation, but future group planning should represent shared decisions separately.

### Existing authentication models

The current JWT and refresh-token system is reusable. Group endpoints should use the existing `get_current_user` dependency from [`api/v1/dependencies.py`](api/v1/dependencies.py).

### Existing SSE infrastructure

SSE exists in [`main.py`](main.py), but only for long-running AI plan generation. It is not a persistent event or collaboration system.

## C. New Models Genuinely Required

### 1. `TripMember`

Required. This is the central authorization model.

Suggested fields:

```text
id
trip_id
user_id
role              owner | admin | member
status            active | left | removed
joined_at
updated_at
left_at
removed_at
```

Recommended constraints:

- primary key on `id`
- foreign key `trip_id -> trips.id`
- foreign key `user_id -> users.id`
- unique constraint on `(trip_id, user_id)` if historical membership is not required
- otherwise use an active-membership uniqueness strategy and retain membership history separately
- index `(trip_id, status)`
- index `(user_id, status)`
- index `(trip_id, role)`

Recommended initial design: keep one membership row per user/trip and update its status. This makes rejoining and historical reporting explicit without creating duplicate active memberships.

Important invariants:

- exactly one active `owner`
- at most one active membership per `(trip_id, user_id)`
- the owner cannot leave without transferring ownership or deleting the trip
- a removed or former member cannot access the private trip

The owner should be represented in `TripMember` even though `Trip.user_id` remains for backward compatibility and existing owner behavior.

### 2. `TripInvitation`

Required for a proper invitation flow.

Suggested fields:

```text
id
trip_id
inviter_user_id
invitee_user_id       nullable
invitee_email         nullable
token_hash
status                pending | accepted | declined | expired | revoked
expires_at
accepted_at
created_at
updated_at
```

Use a cryptographically random raw token sent to the frontend/email flow, but store only its hash in the database.

Recommended constraints and indexes:

- unique `token_hash`
- index `(trip_id, status)`
- index `(invitee_user_id, status)`
- index `(invitee_email, status)`
- index `(expires_at, status)`
- prevent duplicate active invitations for the same trip and target:
  - `(trip_id, invitee_user_id)` for known users
  - normalized `(trip_id, invitee_email)` for email invitations
- an invitation must target either a user or an email, not neither
- invitation creation must verify inviter membership and role

If PostgreSQL is the production database, partial unique indexes are preferable for active invitations. SQLite test support may require a broader unique constraint or application-level test-compatible enforcement.

### 3. `Proposal`

Required for collaborative decisions.

Suggested fields:

```text
id
trip_id
created_by_user_id
proposal_type       destination | hotel | restaurant | activity | itinerary_item | other
title
description
payload             JSON
status              draft | open | closed | accepted | rejected | cancelled
deadline
created_at
updated_at
closed_at
```

`payload` is appropriate because proposal types have different data:

- hotel candidate details
- restaurant details
- activity metadata
- destination alternatives
- itinerary change request

The payload should be validated by proposal type at the API/service layer. It should not be treated as an unrestricted arbitrary JSON patch.

Recommended indexes:

- `(trip_id, status, created_at)`
- `(trip_id, deadline)`
- `(created_by_user_id, created_at)`

A proposal should capture a snapshot of the proposed content. It should not depend on a live external recommendation or mutable RAG result.

### 4. `ProposalVote`

Required for one-vote-per-member enforcement.

Suggested fields:

```text
id
proposal_id
user_id
choice_key
created_at
updated_at
```

Recommended constraints:

- unique `(proposal_id, user_id)`
- foreign key to proposal with cascade delete
- foreign key to user
- index `(proposal_id, choice_key)`

`choice_key` allows a proposal to contain multiple candidate options. For a binary proposal, values might be `approve` and `reject`; for a hotel proposal, it could identify the candidate option.

Vote changes should update the existing row rather than insert a second vote.

Voting must verify active membership at the time of voting.

### 5. `Decision`

Required to separate voting results from actual shared-trip changes.

Suggested fields:

```text
id
trip_id
proposal_id
decided_by_user_id
result
decision_type
applied_action
source_revision
target_revision
created_at
```

Possible values:

```text
decision_type:
  selected_hotel
  selected_restaurant
  selected_activity
  approved_itinerary_change
  selected_destination
  other

result:
  accepted
  rejected
```

Recommended constraints:

- one finalized decision per proposal
- unique `proposal_id`
- index `(trip_id, created_at)`
- foreign key to proposal
- foreign key to trip
- foreign key to deciding user

The decision should preserve the winning proposal and vote-count snapshot so that later changes to membership or proposal data do not rewrite history.

### 6. `ChecklistItem`

Required for the shared checklist portion of the workspace.

Suggested fields:

```text
id
trip_id
created_by_user_id
assigned_to_user_id       nullable
title
description               nullable
completed
completed_by_user_id      nullable
completed_at              nullable
due_at                     nullable
created_at
updated_at
```

Recommended indexes:

- `(trip_id, completed, due_at)`
- `(trip_id, assigned_to_user_id, completed)`

Foreign keys:

- `trip_id -> trips.id`
- creator and assignee -> `users.id`
- completed-by -> `users.id`

Deleting or leaving a group should not silently delete a checklist item. If the assignee leaves, clear the assignee and retain the item.

### 7. `GroupMessage`

Not needed for the first membership/proposal/voting slice, but required if group chat is included in the complete workspace.

Suggested fields:

```text
id
trip_id
sender_user_id
body
created_at
edited_at
deleted_at
```

Recommended indexes:

- `(trip_id, created_at, id)`
- `(trip_id, sender_user_id)`

Use soft deletion if message history is intended to remain auditable.

There is no existing compatible persisted messaging model. The reference RAG chatbot’s chat history is unrelated and should not be reused.

### 8. `Notification`

Not currently present. A persisted notification model is appropriate once invitations, proposals, decisions, assignments, and itinerary changes become user-facing events.

Suggested fields:

```text
id
recipient_user_id
trip_id                 nullable
event_type
payload                 JSON
read_at                 nullable
created_at
```

Recommended indexes:

- `(recipient_user_id, read_at, created_at)`
- `(trip_id, created_at)`
- `(event_type, created_at)`

Notifications should be generated from domain events or an outbox mechanism, not directly duplicated across every API route.

## D. Relationships

Recommended SQLAlchemy relationships:

```text
User
  trips_owned
  trip_memberships
  sent_invitations
  received_invitations
  proposals_created
  proposal_votes
  decisions_made
  checklist_items_created
  checklist_assignments
  messages
  notifications

Trip
  owner
  members
  invitations
  proposals
  decisions
  checklist_items
  messages
  notifications

Proposal
  trip
  creator
  votes
  decision

ProposalVote
  proposal
  voter

Decision
  trip
  proposal
  decided_by

ChecklistItem
  trip
  creator
  assignee
  completed_by
```

Cascade recommendations:

- deleting a trip should cascade invitations, memberships, proposals, votes, decisions, checklist items, messages, and trip notifications
- deleting a user should not necessarily cascade their authored decisions or messages
- use nullable foreign keys with `SET NULL` for historical actor references where audit history must survive account deletion
- avoid database cascades that silently remove decision history unless product requirements explicitly allow it

## E. Database Constraints and Indexes

### Ownership compatibility

Keep `Trip.user_id` for backward compatibility. During migration:

1. Create `TripMember`.
2. For every existing trip with a non-null `user_id`, create an active `owner` membership.
3. Preserve `Trip.user_id` as the owner pointer.
4. Enforce application-level consistency between `Trip.user_id` and the active owner membership.
5. Later, consider making `Trip.user_id` non-null after legacy data is verified.

Current `Trip.user_id` is nullable because older trips may have been generated without authentication. Those trips need an explicit migration policy:

- assign them to a known owner where possible
- otherwise mark them as legacy/unowned and prevent group conversion until claimed
- do not assign them arbitrarily

### Race conditions

Use both database constraints and transaction logic.

#### Duplicate membership

- unique active membership constraint
- transaction with row locking on the trip and target user
- handle `IntegrityError` as a deterministic conflict response

#### Duplicate votes

- unique `(proposal_id, user_id)`
- `INSERT ... ON CONFLICT DO UPDATE` or locked update for vote changes
- verify proposal remains open inside the same transaction

#### Vote closure

Finalization should:

1. lock the proposal row
2. verify it is still open
3. verify deadline has not passed or transition it to closed
4. aggregate votes
5. create one decision
6. mark proposal finalized
7. apply an explicit domain action if one exists
8. commit once

The unique `Decision.proposal_id` constraint protects against double finalization.

#### Invitation acceptance

Acceptance should:

1. lock the invitation row
2. verify token, status, and expiration
3. lock or query the target membership
4. insert or reactivate membership
5. mark invitation accepted
6. commit atomically

#### Member removal during voting

Votes should remain historically valid, but future actions must define policy. Recommended behavior:

- a vote already cast remains recorded
- a removed member cannot change their vote
- membership eligibility is evaluated when the vote is cast
- the proposal’s voting rules should define whether removed members’ votes remain counted

For a first version, retain already-cast votes and count them in the final result, while clearly recording membership state at vote time if auditability is important.

#### Trip deletion

The owner-only trip deletion operation must delete or archive group data consistently. A hard delete is acceptable only if the product accepts losing collaboration history. Otherwise, introduce soft deletion or an archive state before adding chat/activity history.

## F. API Endpoints

The existing convention is a single `/api/v1` router with authenticated FastAPI dependencies, as shown in [`api/v1/trips.py`](api/v1/trips.py). Recommended routes:

### Trip conversion and workspace

```text
POST   /api/v1/trips/{trip_id}/group
GET    /api/v1/trips/{trip_id}/workspace
```

`POST /group` should be owner-only and idempotent. It should create the owner membership and return the group workspace metadata.

Existing personal trip routes remain:

```text
GET    /api/v1/trips
GET    /api/v1/trips/{trip_id}
PATCH  /api/v1/trips/{trip_id}
DELETE /api/v1/trips/{trip_id}
```

They should be changed internally to authorize through a shared trip-access service rather than directly comparing `Trip.user_id`.

### Members

```text
GET    /api/v1/trips/{trip_id}/members
PATCH  /api/v1/trips/{trip_id}/members/{user_id}
DELETE /api/v1/trips/{trip_id}/members/{user_id}
POST   /api/v1/trips/{trip_id}/leave
```

Rules:

- owner can manage admins and members
- admin can manage members, but not the owner or other admins unless explicitly allowed
- member can view members and leave
- owner cannot leave without ownership transfer
- role updates must be owner/admin-authorized server-side

### Invitations

```text
POST   /api/v1/trips/{trip_id}/invitations
GET    /api/v1/trips/{trip_id}/invitations
POST   /api/v1/invitations/{token}/accept
POST   /api/v1/invitations/{invitation_id}/revoke
```

Prefer a token acceptance route that does not expose invitation existence before authentication. The backend should bind an email invitation to the authenticated email when applicable.

### Proposals

```text
POST   /api/v1/trips/{trip_id}/proposals
GET    /api/v1/trips/{trip_id}/proposals
GET    /api/v1/proposals/{proposal_id}
PATCH  /api/v1/proposals/{proposal_id}
POST   /api/v1/proposals/{proposal_id}/close
POST   /api/v1/proposals/{proposal_id}/finalize
```

Proposal retrieval must confirm the caller is an active member of the proposal’s trip.

### Voting

```text
PUT    /api/v1/proposals/{proposal_id}/vote
DELETE /api/v1/proposals/{proposal_id}/vote
GET    /api/v1/proposals/{proposal_id}/results
```

`PUT` naturally supports changing one’s vote because the uniqueness boundary is `(proposal_id, user_id)`.

### Decisions

```text
GET    /api/v1/trips/{trip_id}/decisions
GET    /api/v1/proposals/{proposal_id}/decision
POST   /api/v1/decisions/{decision_id}/apply
```

The separate apply route is useful if voting finalization and applying a trip change should be independently authorized or retried.

### Checklist

```text
GET    /api/v1/trips/{trip_id}/checklist
POST   /api/v1/trips/{trip_id}/checklist
PATCH  /api/v1/checklist-items/{item_id}
DELETE /api/v1/checklist-items/{item_id}
```

### Chat

```text
GET    /api/v1/trips/{trip_id}/messages
POST   /api/v1/trips/{trip_id}/messages
PATCH  /api/v1/messages/{message_id}
DELETE /api/v1/messages/{message_id}
```

The initial chat implementation can be request/response plus polling. A realtime transport can be added without changing persistence routes.

## G. Pydantic Schemas

Add collaboration-specific schemas to [`models/api_schemas.py`](models/api_schemas.py), keeping database models separate from API contracts.

Recommended schema families:

```text
TripGroupCreateRequest
TripMemberResponse
TripMemberRoleUpdateRequest
TripMemberListResponse

InvitationCreateRequest
InvitationResponse
InvitationAcceptResponse

ProposalCreateRequest
ProposalUpdateRequest
ProposalResponse
ProposalListResponse
ProposalResultResponse

VoteRequest
VoteResponse

DecisionResponse
DecisionApplyResponse

ChecklistItemCreateRequest
ChecklistItemUpdateRequest
ChecklistItemResponse

MessageCreateRequest
MessageResponse
MessagePageResponse

NotificationResponse
NotificationListResponse
```

Validation requirements:

- enum validation for membership roles and statuses
- proposal type validation
- deadline must be in the future when opening a proposal
- proposal payload validated according to proposal type
- checklist title length and non-empty validation
- message length limits and whitespace validation
- do not allow clients to submit owner IDs, creator IDs, vote user IDs, or timestamps as authoritative values

## H. Service-Layer Changes

The current [`services/trip_service.py`](services/trip_service.py) owns its own sessions, while API routes receive a `db` dependency but often discard it. That pattern is workable for current CRUD but is not appropriate for multi-step group transactions.

Recommended changes:

### Introduce `TripAccessService`

Centralize:

- `get_trip_for_member`
- `get_trip_for_role`
- `require_owner`
- `require_admin_or_owner`
- `require_active_member`
- `require_can_edit_trip`
- `require_can_vote`

This avoids reproducing authorization logic across routes.

### Introduce `GroupTripService`

Responsibilities:

- convert a personal trip into a group trip
- create owner membership
- list members
- manage roles
- leave/remove members
- create and accept invitations

All methods should accept an existing SQLAlchemy `Session`.

### Introduce `ProposalService`

Responsibilities:

- create proposals
- open/close proposals
- cast/change/remove votes
- calculate results
- finalize proposals
- create decisions
- apply deterministic updates

### Introduce `ChecklistService`

Responsibilities:

- create and update checklist items
- assign members
- complete/reopen items
- enforce trip membership

### Introduce `MessageService`

Only when chat is implemented.

### Transaction boundary

Routes should call services using the request-scoped `db` session from [`database/connection.py`](database/connection.py). Avoid opening independent sessions inside services for collaborative operations.

This is necessary so membership checks, writes, locks, and finalization occur in one transaction.

## I. Authorization Rules

Authorization must be server-side and resource-scoped.

| Operation | Owner | Admin | Member |
|---|---:|---:|---:|
| View workspace | Yes | Yes | Yes |
| View members | Yes | Yes | Yes |
| Invite members | Yes | Yes | No |
| Revoke invitations | Yes | Yes | No |
| Change member role | Yes | Limited | No |
| Remove member | Yes | Members only | No |
| Transfer ownership | Yes | No | No |
| Leave group | No, transfer first | Yes | Yes |
| Create proposal | Yes | Yes | Yes |
| Edit own open proposal | Yes | Yes | Yes |
| Edit another member’s proposal | Yes | Yes | No |
| Vote | Yes | Yes | Yes |
| Close proposal | Yes | Yes | No |
| Finalize proposal | Yes | Yes | No |
| Apply shared trip change | Yes | Yes | No |
| Manage checklist | Yes | Yes | Yes, subject to item policy |
| Assign checklist item | Yes | Yes | Possibly self/other members according to policy |
| Send chat message | Yes | Yes | Yes |
| Delete another user’s message | Yes/admin | Yes | No |

Additional rules:

- application-wide `User.is_admin` must not grant group membership permissions automatically
- users must be active and authenticated
- membership must be checked against the target trip, not merely the existence of the user
- all resource lookups should avoid leaking private trip existence where current behavior already uses `404`
- frontend route guards are supplementary only

## J. Frontend Architecture

Group travel should be integrated into the existing trip workspace rather than creating a second trip page.

Recommended structure:

```text
/trips
/trips/:tripId
/trips/:tripId?tab=overview
/trips/:tripId?tab=itinerary
/trips/:tripId?tab=proposals
/trips/:tripId?tab=decisions
/trips/:tripId?tab=checklist
/trips/:tripId?tab=chat
```

Keep [`TripDetailPage.jsx`](frontend/src/pages/TripDetailPage.jsx) as the route-level container, then split the workspace into focused components:

```text
TripWorkspace
TripHeader
TripMembersPanel
TripItineraryPanel
ProposalList
ProposalComposer
ProposalDetail
VoteControls
DecisionTimeline
ChecklistPanel
GroupChatPanel
```

The existing `PlanCard` and `DayCard` can continue rendering the generated itinerary. The group workspace should wrap that content with collaboration controls rather than replace the itinerary model immediately.

Recommended rollout:

1. Add group state and member display to the existing trip detail page.
2. Add proposals and voting as tabs or workspace panels.
3. Add decisions with explicit “apply change” actions.
4. Add checklist.
5. Add chat.
6. Add notifications to the global authenticated shell.

The existing API client pattern in [`frontend/src/api/client.js`](frontend/src/api/client.js) is sufficient. Add grouped clients such as:

```text
groupTripsApi
membersApi
invitationsApi
proposalsApi
checklistApi
messagesApi
notificationsApi
```

Avoid putting all new requests into `tripsApi` if they have separate authorization and cache lifecycles.

## K. Shared Itinerary Design

The current itinerary is a JSON array and existing personal-trip behavior must remain unchanged.

Do not immediately normalize the entire itinerary into relational tables. That would be a high-risk migration affecting AI generation, serialization, frontend rendering, regeneration, and Travel Guide compatibility.

Recommended first design:

- keep `Trip.itinerary` unchanged
- use `Proposal.payload` for proposed itinerary changes
- store the selected proposal and applied action in `Decision`
- when applying an itinerary change:
  - validate the proposal payload against the existing `DayPlan` structure
  - make one deterministic JSON update
  - append an explicit revision record
  - record the applied decision ID and actor
- do not allow arbitrary client-supplied replacement of the entire itinerary
- do not automatically apply every accepted proposal

For stronger auditability, add a future `TripRevision` model only if JSON revision history becomes insufficient. It is not required for the first collaboration slice because `revision_history` already exists, although it currently lacks actor and decision identifiers.

Recommended revision-history additions:

```text
decision_id
changed_by_user_id
change_type
before
after
```

These can initially be appended to the existing JSON history, but a relational revision model becomes preferable once collaborative edits become frequent.

### Deterministic application mapping

Only support automatic application for explicitly defined proposal types:

- selected hotel: update the relevant day’s hotel field
- selected restaurant: update a specific meal entry
- selected activity: update a specific activity entry
- approved itinerary item: replace a specific day or item identified by stable day/item coordinates
- destination: require a deliberate trip-level update flow because destination changes affect weather, budget, research, and the entire itinerary

If the proposal cannot identify a deterministic target, finalize the decision without modifying the itinerary and require a subsequent explicit edit or regeneration action.

## L. Realtime Strategy

The repository contains SSE for AI planning, but no WebSocket, event-stream, or polling implementation for persisted collaboration.

Recommended initial strategy:

- normal REST endpoints for writes
- short polling for proposal results, checklist state, and chat
- optional `updated_at` or monotonically increasing event cursor
- frontend refresh after successful mutations
- polling only while the relevant workspace tab is active

This is simpler and consistent with the current application.

When collaboration usage justifies realtime:

- use WebSockets for trip-scoped authenticated subscriptions
- authenticate the WebSocket connection with the existing JWT
- authorize the trip before joining a channel
- publish domain events after successful database commits
- do not publish uncommitted state
- use Redis or another shared broker when running multiple backend instances

SSE could also support server-to-client updates, but it is less suitable for bidirectional chat and does not currently have a persistent event pipeline. WebSockets are the eventual better fit for chat and collaborative updates, but should not be introduced before the domain events and authorization model exist.

## M. Notification Strategy

There is currently no notification system. The profile UI’s notification row is only a placeholder, and no notification database model or API exists.

Recommended design:

1. Define domain event types:
   - invitation created
   - invitation accepted
   - member joined
   - member removed
   - proposal created
   - voting opened
   - voting closing
   - decision finalized
   - itinerary changed
   - checklist assignment
   - new message mention, if supported

2. Create notifications after the domain transaction commits.

3. For production reliability, use an outbox table or transactionally recorded event table before asynchronous delivery is introduced.

4. Start with in-app persisted notifications.

5. Add email delivery later through a background worker, without changing the domain models.

Do not send notification logic directly from route handlers in a way that can be lost when a transaction fails.

## N. Chat and Checklist Findings

### Chat

No existing compatible messaging infrastructure exists.

The LangGraph message state and reference RAG chatbot history are not suitable for persistent group chat. A new `GroupMessage` model is appropriate if chat is included.

Start with:

- REST message persistence
- cursor pagination
- soft deletion
- active-member authorization
- polling

Add realtime later.

### Checklist

No existing checklist model or service exists. `ChecklistItem` should be a new model because checklist items have independent lifecycle, assignment, completion, and authorization requirements.

It should not be stored as a JSON field on `Trip`; relational storage is required for:

- assignment queries
- filtering incomplete items
- member-specific views
- indexes
- concurrent completion updates
- future notifications

## O. Migration Plan

The Alembic chain currently ends at the admin-role migration:

- [`alembic/versions/20260909_000001_create_trips_table.py`](alembic/versions/20260909_000001_create_trips_table.py)
- [`alembic/versions/20260910_000003_add_auth_tokens_preferences_ownership.py`](alembic/versions/20260910_000003_add_auth_tokens_preferences_ownership.py)
- [`alembic/versions/20260913_000006_add_admin_role.py`](alembic/versions/20260913_000006_add_admin_role.py)

Recommended migration sequence:

### Migration 1: Core memberships

Create:

- `trip_members`
- indexes and active-membership uniqueness
- owner backfill from `trips.user_id`

Do not add all collaboration tables in the first migration.

### Migration 2: Invitations

Create `trip_invitations`, token indexes, expiration fields, and active-duplicate constraints.

### Migration 3: Proposals and votes

Create:

- `proposals`
- `proposal_votes`
- indexes
- unique vote constraint
- proposal status/deadline fields

### Migration 4: Decisions

Create `decisions` with unique `proposal_id`.

### Migration 5: Checklist

Create `checklist_items`.

### Migration 6: Messaging

Create `group_messages` only when chat is part of the implementation milestone.

### Migration 7: Notifications and events

Create `notifications`, and an outbox/event table if asynchronous delivery or realtime fan-out is introduced.

Each migration should be backward-compatible with existing personal trips and should be tested against both PostgreSQL and the repository’s SQLite test setup.

## P. Complete Implementation Sequence

### Phase 1: Authorization foundation

1. Add `TripMember`.
2. Backfill owner memberships.
3. Add membership relationships.
4. Introduce `TripAccessService`.
5. Update trip read/list/update/delete/regenerate authorization to accept owners and authorized group members according to operation.
6. Preserve existing personal-trip behavior and `404` semantics.

### Phase 2: Group conversion and membership

1. Add group conversion endpoint.
2. Make conversion idempotent.
3. Add member listing.
4. Add leave/remove/role management.
5. Add ownership-transfer rules.
6. Add frontend member panel.

### Phase 3: Invitations

1. Add invitation model and token hashing.
2. Add invitation creation, revoke, and accept flows.
3. Add duplicate/expiry handling.
4. Add invitation notifications later through the notification abstraction.
5. Add frontend invitation dialog and invitation acceptance route.

### Phase 4: Proposals and voting

1. Add proposal and vote models.
2. Add proposal-type schemas.
3. Add active-member authorization.
4. Add vote uniqueness and vote-change behavior.
5. Add deadline and closure logic.
6. Add transactional finalization with row locks.
7. Add proposals and voting UI.

### Phase 5: Decisions and itinerary updates

1. Add `Decision`.
2. Define explicit proposal-type application handlers.
3. Add deterministic hotel, restaurant, activity, and itinerary update mappings.
4. Add revision metadata and decision references.
5. Require explicit application for changes that cannot be mapped safely.
6. Add decision history UI.

### Phase 6: Checklist

1. Add `ChecklistItem`.
2. Add assignment and completion endpoints.
3. Add checklist panel.
4. Add assignment notification events.

### Phase 7: Chat

1. Add `GroupMessage`.
2. Add paginated REST APIs.
3. Add polling.
4. Add message authorization and soft deletion.
5. Add WebSocket delivery only after event publication is reliable.

### Phase 8: Notifications and realtime

1. Add persisted notifications.
2. Add domain events/outbox.
3. Add in-app notification UI.
4. Add realtime subscriptions for workspace updates.
5. Add background email delivery if required.

## Q. Testing Plan

### Authentication and access

- unauthenticated group endpoint returns `401`
- inactive users cannot access groups
- non-members cannot view private workspaces
- private trip existence is not disclosed where current `404` behavior applies
- global application admins do not automatically become trip admins

### Membership

- converting a personal trip creates exactly one owner membership
- conversion is idempotent
- owner can invite and manage members
- admin can perform permitted member operations
- member cannot change roles
- member cannot remove arbitrary users
- duplicate memberships are rejected
- owner cannot leave without transfer
- member can leave
- removed member loses access
- trip owner and owner membership cannot diverge silently

### Invitations

- valid invitation is accepted
- invalid token is rejected
- expired invitation is rejected
- revoked invitation is rejected
- duplicate active invitation is rejected
- unauthorized invitation creation is rejected
- invitee email binding is enforced
- concurrent acceptance creates one membership
- accepting an invitation twice is idempotent or returns a clear conflict

### Proposals

- active member creates proposal
- non-member cannot create or retrieve proposals
- proposal payload matches proposal type
- proposal creator can edit an open proposal
- unauthorized users cannot alter another user’s proposal
- proposal closure is authorized
- deadline handling is correct

### Voting

- active member can vote
- one vote per member per proposal
- vote changes update the existing vote
- non-member cannot vote
- closed proposal rejects votes
- expired proposal closes or rejects consistently
- concurrent votes do not duplicate rows
- concurrent finalization creates one decision
- vote counts are stable and auditable

### Decisions

- correct winning option is selected
- ties follow an explicit policy
- only authorized users can finalize
- a proposal cannot be finalized twice
- deterministic hotel/activity/itinerary mappings work
- unmappable decisions do not silently overwrite itinerary JSON
- applied changes create revision metadata
- failed application rolls back the decision/application transaction

### Checklist

- member can create an item
- unauthorized user cannot access another trip’s items
- assignment is restricted to active members
- completion records actor and timestamp
- removed assignee is handled safely
- concurrent completion is consistent

### Chat and notifications

- only members can read or send messages
- deleted messages follow the chosen retention policy
- notification recipients are correct
- notifications are not created for rolled-back transactions
- unread state behaves correctly
- pagination is stable

### Regression

Run the existing suite covering:

- personal trip CRUD
- AI planning and SSE
- RAG retrieval and Travel Guide
- Knowledge Center administration
- authentication
- trip regeneration
- structured output compatibility

The existing tests in [`tests/test_api_trip_crud.py`](tests/test_api_trip_crud.py) are especially important because they encode the current owner-scoped behavior that must remain valid.

## Recommended First Slice

The safest first implementation slice is:

1. `TripMember`
2. `TripInvitation`
3. membership authorization service
4. group conversion
5. member management
6. proposal creation/retrieval
7. proposal voting
8. transactional finalization
9. explicit `Decision`
10. integrated trip workspace UI

Defer persisted chat, notifications, and realtime transport until the relational collaboration core and domain-event boundaries are established. Add the checklist in the same milestone if the workspace must be considered feature-complete, because it is independent and low-risk compared with chat.

The central architectural decision is to keep `Trip` as the single source of itinerary and trip information while adding relational collaboration records around it. That preserves current personal trips, AI planning, RAG, Travel Guide behavior, and existing frontend rendering without creating a second trip domain.
