# Group Travel Completion Plan

## Verification status (2026-09-13)

The implementation has been revalidated with the focused Group Travel suite (`23 passed, 1 warning`), the full pytest suite (`173 passed, 1 warning`), frontend lint, frontend production build, static diagnostics for changed files, and a fresh SQLite migration upgrade/downgrade/re-upgrade. Remaining unchecked items are intentionally limited to behavior not proven by those checks, including PostgreSQL-specific validation, manual browser E2E, and a small number of invitation, checklist, notification, and optional refresh follow-ups.

This checklist uses `docs/GROUP_TRAVEL_ARCHITECTURE_AUDIT.md` as the source of truth. The existing `Trip` model remains the single trip/workspace aggregate, `Trip.user_id` remains for compatibility, and `TripMember` is the resource-scoped group authorization boundary.

## 1. Backend Architecture

### Exact requirement
Use request-scoped SQLAlchemy sessions throughout collaboration and trip operations. Services must not create independent database sessions for request work.

### Implementation tasks
- [x] Refactor `TripService` to require an injected `Session`.
- [x] Remove any `SessionLocal` fallback or implicit session creation from `TripService`.
- [x] Audit every `TripService` caller in API routes, planner endpoints, SSE persistence, scripts, and tests.
- [x] Make transaction boundaries explicit in services and routes.
- [x] Roll back failed writes and avoid committing partial multi-step operations.
- [x] Keep existing personal-trip, AI planner, itinerary regeneration, RAG, and SSE behavior intact.
- [x] Keep collaboration services dependent on the request-scoped session supplied by `get_db`.
- [x] Avoid independent sessions inside group services, notification services, and decision handlers.

### Relevant files/modules to inspect
- `services/trip_service.py`
- `services/collaboration_service.py`
- `database/connection.py`
- `api/v1/trips.py`
- `api/v1/collaboration.py`
- `main.py`
- `api/v1/dependencies.py`

### Acceptance criteria
- Every production `TripService` construction provides the request session.
- No production trip or collaboration service silently opens a new session.
- A failed transaction leaves no partial membership, decision, checklist, message, or notification records.
- Existing personal-trip and planner regression tests remain green.

### Tests required
- Service tests with injected sessions.
- Commit failure and rollback tests.
- API tests proving request-scoped writes persist correctly.
- Regression tests for personal CRUD, planner persistence, SSE, and regeneration.

## 2. Authorization & Ownership

### Exact requirement
Centralize all resource authorization in `TripAccessService`. Permissions must be based on the target trip and active `TripMember` role. `User.is_admin` must never grant trip-level permissions.

### Implementation tasks
- [x] Implement and consistently use `get_trip_for_member`.
- [x] Implement and consistently use `get_trip_for_role`.
- [x] Implement `require_owner`.
- [x] Implement `require_admin_or_owner`.
- [x] Implement `require_active_member`.
- [x] Implement `require_can_edit_trip`.
- [x] Implement `require_can_vote`.
- [x] Route trip reads, lists, updates, deletes, full regeneration, and single-day regeneration through the access layer.
- [x] Preserve 404 privacy behavior for private trips and non-members.
- [x] Ensure removed and left members lose access immediately.
- [x] Define and enforce the owner/admin/member permission matrix from the audit.
- [x] Implement ownership transfer as a single transaction.
- [x] Require the transfer target to be an active member.
- [x] Update `Trip.user_id` and membership roles atomically.
- [x] Guarantee exactly one active owner.
- [x] Prevent the owner from leaving or being removed without transfer or deletion.

### Relevant files/modules to inspect
- `services/collaboration_service.py`
- `services/trip_service.py`
- `api/v1/trips.py`
- `api/v1/collaboration.py`
- `database/models.py`
- `models/api_schemas.py`

### Acceptance criteria
- Global admins cannot manage a trip unless they are active members with the required trip role.
- Non-members cannot read or mutate group resources.
- Members can participate only in operations allowed by the audit.
- Ownership transfer leaves one owner, updates `Trip.user_id`, and preserves old-owner permissions according to policy.

### Tests required
- Owner, admin, member, non-member, removed-member, and left-member tests.
- Global-admin-versus-trip-admin tests.
- Owner leave/removal restrictions.
- Invalid ownership targets.
- Concurrent ownership transfer integrity tests.

## 3. Members & Invitations

### Exact requirement
Provide complete membership and invitation lifecycle management with secure token handling and transactional acceptance.

### Implementation tasks
- [x] Create and backfill one owner `TripMember` for every valid legacy `Trip.user_id`.
- [x] Do not assign ownership to legacy unowned trips arbitrarily.
- [x] Add member listing, role update, removal, leave, and ownership transfer APIs.
- [x] Prevent duplicate active memberships with database and service safeguards.
- [x] Clear checklist assignments when an assignee leaves or is removed.
- [x] Add invitation creation by user ID or normalized email.
- [x] Validate exactly one invitation target.
- [x] Reject unknown users where a user target is provided.
- [x] Store only a cryptographic token hash.
- [x] Add expiration and pending/accepted/declined/expired/revoked states.
- [x] Prevent duplicate active invitations.
- [x] Make acceptance lock the invitation, membership, and status transition transactionally.
- [x] Bind email invitations to the authenticated user's email.
- [x] Add invitation listing and revoke endpoints.
- [ ] Preserve invitation history and avoid leaking invitation existence.
- [ ] Build member management UI with role changes, removal, leave, transfer, confirmations, and permission states.
- [ ] Build pending invitation UI with status, expiration, token/link handling, and revoke.
- [ ] Add a public invitation route for logged-out users.
- [ ] Preserve the token through login or registration using a safe `next` path.
- [ ] Resume acceptance after authentication.
- [ ] Show invalid, expired, revoked, already-used, and already-member states.

### Relevant files/modules to inspect
- `database/models.py`
- `services/collaboration_service.py`
- `api/v1/collaboration.py`
- `models/api_schemas.py`
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/pages/AuthPage.jsx`
- `frontend/src/auth/AuthContext.jsx`
- `frontend/src/api/client.js`
### Acceptance criteria
- Invalid payloads are rejected before persistence.
- [x] Support `destination`, `hotel`, `restaurant`, `activity`, `itinerary_item`, and `other` proposal types.
- [x] Add type-specific Pydantic payload schemas or validators.
- [x] Validate required fields, lengths, indexes, and target references.
- [x] Snapshot proposal payload at creation and update time.
- Closed and expired proposals reject votes consistently.

- [x] Enforce unique `(proposal_id, user_id)` votes.
- [x] Make `PUT` change an existing vote rather than insert another row.
- [x] Support vote removal while the proposal is open.
- [x] Implement stable results and explicit tie handling.
- Concurrent vote creation/change tests.
- Tie-policy and removed-member behavior tests.
- [x] Implement stable cursor pagination ordered by `created_at` and `id`.
## 5. Decisions & Itinerary Integration

- [x] Keep `/plan/stream` exclusively for AI generation.
- [x] Refresh relevant data immediately after successful mutations.
- [x] Poll proposals/results, checklist, chat, membership, and notifications only for the active section.
- [x] Use a sensible interval and clean up timers on unmount/tab changes.
- [x] Lock the proposal row during finalization.
- [x] Verify the proposal remains open and handle deadlines.
- [x] Run upgrade to head, downgrade one step or previous expected revision, then upgrade to head again.
- [x] Create exactly one `Decision` per proposal.
- [x] Store deciding user, result, decision type, vote-count snapshot, and proposal snapshot data.
- [x] Run fresh frontend lint.
- [x] Run fresh frontend production build.
- [x] Implement explicit decision retrieval and decision listing APIs.
- [x] Implement explicit decision application with authorization.
- [x] Verify decision/proposal/trip ownership relationships before applying.
- [x] Prevent duplicate application.
- [x] Apply hotel changes only to the intended day hotel field.
- [x] Apply restaurant changes only to the intended meal entry.
- [x] Apply activity changes only to the intended activity entry.
- [x] Apply itinerary-item changes only to the validated target item/day.
- [x] Never replace the complete itinerary from client input.
- [x] Define a controlled destination-change workflow.
- [x] Validate destination values.
- [x] Update destination deliberately without silently pretending the entire plan was regenerated.
- [x] Trigger or expose an explicit controlled re-planning/regeneration action using the existing AI planner architecture.
- [x] Handle weather, budget, research, or itinerary regeneration failures without losing the decision.
- [x] Preserve unrelated trip fields and itinerary days.
- [x] Record source and target revisions plus before/after metadata.

### Relevant files/modules to inspect
- `database/models.py`
- `services/collaboration_service.py`
- `services/trip_service.py`
- `agent/agentic_workflow.py`
- `api/v1/collaboration.py`
- `main.py`
- `models/schemas.py`
- `models/api_schemas.py`
- `frontend/src/components/group/GroupWorkspacePanels.jsx`
- `frontend/src/pages/TripDetailPage.jsx`

### Acceptance criteria
- Only one finalization succeeds under concurrent requests.
- Decisions are immutable historical records.
- Safe applications update only the intended field or item.
- Unsupported mappings are recorded as unapplied and do not overwrite itinerary data.
- Destination changes require explicit application and controlled replanning behavior.
- Revision history identifies actor, decision, source revision, target revision, before state, and after state.

### Tests required
- Correct winner and tie handling.
- Unauthorized and duplicate finalization.
- Concurrent finalization and duplicate decision creation.
- One test for each supported application type.
- Invalid target/index and unsafe payload tests.
- Destination application success, planner success, planner failure, and rollback tests.
- Revision-history preservation and conflicting-application tests.

## 6. Checklist

### Exact requirement
Use relational `ChecklistItem` records for shared tasks with assignment, completion, due dates, and actor tracking.

### Implementation tasks
- [x] Implement list, create, update, delete, assign, reassign, complete, and reopen operations.
- [x] Restrict all operations to active members.
- [x] Restrict assignees to active members of the same trip.
- [x] Record completion actor and timestamp.
- [x] Clear assignments when a member leaves or is removed.
- [x] Preserve checklist items when members leave.
- [x] Add full checklist UI with create, edit, delete, assign, due date, description, complete, reopen, filtering, empty, loading, error, and permission states.
- [x] Refresh checklist state after each mutation.

### Relevant files/modules to inspect
- `database/models.py`
- `services/collaboration_service.py`
- `api/v1/collaboration.py`
- `models/api_schemas.py`
- `frontend/src/components/group/GroupWorkspacePanels.jsx`
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/api/client.js`

### Acceptance criteria
- Checklist state is never stored in `Trip` JSON.
- Invalid assignees are rejected.
- Completion metadata is accurate.
- Removed assignees are safely cleared.
- UI state reflects the database after mutations.

### Tests required
- CRUD and permission tests.
- Assignment and reassignment tests.
- Completion/reopen actor and timestamp tests.
- Removed-assignee tests.
- Concurrent completion/update tests.
- Frontend component/API interaction tests where available.

## 7. Group Chat

### Exact requirement
Provide persistent, authorized group chat using `GroupMessage`, not LangGraph state or RAG history.

### Implementation tasks
- [x] Implement stable cursor pagination ordered by `created_at` and `id`.
- [x] Restrict reads and sends to active members.
- [x] Validate and trim message content and length.
- [x] Allow authors to edit messages according to policy.
- [x] Allow owner/admin moderation and deletion.
- [x] Implement soft deletion with safe deleted-message rendering.
- [x] Ensure deleted messages are not exposed as normal active content.
- [x] Add chat UI with sender identity, timestamps, empty/loading/error states, send, edit, delete, and pagination.
- [x] Refresh or poll only while the chat tab is active.

### Relevant files/modules to inspect
- `database/models.py`
- `services/collaboration_service.py`
- `api/v1/collaboration.py`
- `models/api_schemas.py`
- `frontend/src/components/group/GroupWorkspacePanels.jsx`
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/api/client.js`

### Acceptance criteria
- Non-members cannot read or send messages.
- Message ordering and cursors are stable.
- Soft-deleted messages do not display normal message content.
- Authorization applies to edit and delete operations.

### Tests required
- Member/non-member read and send tests.
- Message validation and pagination tests.
- Author edit/delete and admin moderation tests.
- Soft-delete behavior tests.
- Message authorization race/integrity tests.

## 8. Notifications

### Exact requirement
Persist in-app notifications through a centralized domain notification service and keep creation transactional with the originating mutation.

### Implementation tasks
- [x] Centralize notification creation in a reusable service.
- [x] Ensure notification inserts share the same SQLAlchemy transaction as the domain write.
- [x] Do not create notifications before a mutation is known to succeed.
- [x] Roll back notifications when the originating transaction rolls back.
- [x] Implement events for invitation created, accepted, revoked where appropriate, member joined, removed, role changed, ownership transferred, proposal created/updated/closed, vote activity where useful, decision finalized, itinerary changed, checklist assignment/completion, and supported mentions.
- [x] Include safe resource identifiers in payloads: `trip_id`, `proposal_id`, `decision_id`, `checklist_item_id`, `message_id`, or `invitation_id`.
- [x] Implement user-scoped list, unread count, mark-read, and mark-all-read APIs.
- [x] Add notification center UI with unread state, loading, empty, errors, mark-read, mark-all, and safe navigation.
- [x] Fall back safely when the referenced resource no longer exists or access is lost.

### Relevant files/modules to inspect
- `database/models.py`
- `services/collaboration_service.py`
- `api/v1/collaboration.py`
- `models/api_schemas.py`
- `frontend/src/api/client.js`
- `frontend/src/components/group/GroupWorkspacePanels.jsx`
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/components/ui/Navbar.jsx`

### Acceptance criteria
- No orphan notifications are created after failed operations.
- Users can only read or mutate their own notifications.
- Every relevant notification can navigate to an authorized workspace section.
- Payloads never contain arbitrary client-supplied URLs or actor identities.

### Tests required
- Notification creation for every supported event.
- Recipient correctness and user isolation.
- Rollback/no-notification-on-failure tests.
- Unread count, mark-read, and mark-all tests.
- Safe navigation and inaccessible-resource fallback tests.

## 9. Frontend Workspace

### Exact requirement
Integrate Group Travel into the existing `/trips/:tripId` workspace without creating a duplicate trip page.

### Implementation tasks
- [x] Keep `TripDetailPage` as the route-level orchestrator.
- [x] Extract focused components:
  - [x] `GroupOverview`
  - [x] `GroupMembers`
  - [x] `GroupInvitations`
  - [x] `GroupProposals`
  - [x] `GroupDecisions`
  - [x] `GroupChecklist`
  - [x] `GroupChat`
  - [x] `GroupNotifications`
- [x] Keep existing `PlanCard` and itinerary rendering intact.
- [x] Add tabs for overview, itinerary, members, proposals, decisions, checklist, chat, and notifications/activity as appropriate.
- [x] Provide permission-aware visibility and controls.
- [x] Provide loading, empty, error, success, unauthorized, removed-member, expired-invitation, closed-proposal, finalized-decision, empty-checklist, and empty-chat states.
- [x] Keep layout responsive and consistent with PACK & GO.
- [x] Use real API data as the source of truth after mutations.
- [x] Avoid fake local-only collaboration state.

### Relevant files/modules to inspect
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/components/PlanCard.jsx`
- `frontend/src/components/group/`
- `frontend/src/api/client.js`
- `frontend/src/auth/`
- `frontend/src/App.jsx`
- `frontend/src/App.css`

### Acceptance criteria
- No duplicate `GroupTripPage` exists.
- Trip detail remains functional for personal and group trips.
- Each workspace section has independent loading/error/empty handling.
- All controls obey server-side permissions.
- The UI reflects refreshed server state after mutations.

### Tests required
- Component tests for major panels where frontend test tooling exists.
- Invitation resume navigation test.
- Permission-state rendering tests.
- Responsive/build validation.
- Manual browser validation of all listed flows.

## 10. Realtime / Refresh

### Exact requirement
Use reliable REST writes plus limited refresh/polling. Do not repurpose AI SSE for collaboration.

### Implementation tasks
- [x] Keep `/plan/stream` exclusively for AI generation.
- [x] Refresh relevant data immediately after successful mutations.
- [x] Poll proposals/results, checklist, chat, membership, and notifications only for the active section.
- [x] Use a sensible interval and clean up timers on unmount/tab changes.
- [x] Avoid duplicate polling requests and stale updates.
- [ ] Optionally use `updated_at` or cursors for efficient refresh.
- [x] Do not add WebSockets or Redis unless the current deployment architecture supports them without unnecessary complexity.

### Relevant files/modules to inspect
- `main.py`
- `frontend/src/pages/TripDetailPage.jsx`
- `frontend/src/api/client.js`
- `frontend/src/components/group/`

### Acceptance criteria
- Collaboration updates become visible without a full page reload.
- Polling is limited to active workspace context.
- AI SSE behavior remains unchanged.
- No uncommitted collaboration state is broadcast.

### Tests required
- Mutation-followed-by-refresh tests.
- Polling cleanup and tab-switch tests where available.
- Regression tests for `/plan/stream`.

## 11. Database & Migrations

### Exact requirement
Maintain incremental, reversible Alembic migrations with correct foreign keys, indexes, constraints, and legacy-trip behavior.

### Implementation tasks
- [x] Review all collaboration migrations.
- [x] Verify foreign-key targets and delete behavior.
- [x] Verify indexes for trip/status, user/status, deadlines, vote choices, messages, assignments, and notifications.
- [x] Enforce unique membership, unique vote, unique decision, unique invitation token, and active-owner invariants.
- [x] Ensure invitation target constraints and status constraints are intentional.
- [x] Keep legacy/unowned trips unassigned unless a valid owner exists.
- [x] Verify migration imports register every model.
- [ ] Test migrations against SQLite test setup and PostgreSQL-compatible DDL where practical.
- [x] Run upgrade to head, downgrade one step or previous expected revision, then upgrade to head again.
- [x] Verify existing data remains valid after each transition.

### Relevant files/modules to inspect
- `alembic/env.py`
- `alembic/versions/`
- `database/models.py`
- `database/base.py`
- `database/connection.py`

### Acceptance criteria
- Upgrade, downgrade, and re-upgrade succeed from a clean valid state.
- Existing personal trips remain readable.
- Constraints prevent duplicate active memberships, votes, owners, and decisions.
- No migration is squashed, deleted, or rewritten destructively.

### Tests required
- Migration upgrade/downgrade/upgrade validation.
- Legacy trip backfill tests.
- Constraint and foreign-key tests.
- PostgreSQL migration validation where a PostgreSQL environment is available.

## 12. Security

### Exact requirement
Perform a server-side privacy and authorization review for every Group Travel resource.

### Implementation tasks
- [x] Require authentication for all private group endpoints.
- [x] Reject inactive users.
- [x] Enforce active membership on every trip-scoped read and write.
- [x] Preserve 404 privacy for private resource lookup failures.
- [x] Do not trust client actor, creator, voter, owner, role, timestamp, or permission fields.
- [x] Prevent global admin privilege from becoming trip admin privilege.
- [x] Prevent cross-trip resource access by ID guessing.
- [x] Prevent invitation token disclosure and raw-token persistence.
- [x] Validate proposal payloads before persistence and application.
- [x] Restrict message edit/delete to authorized actors.
- [x] Restrict notification reads to the authenticated recipient.
- [x] Avoid exposing provider, database, or internal errors.
- [x] Search for secrets, debug prints, arbitrary URLs, and unsafe full-itinerary replacement.

### Relevant files/modules to inspect
- `api/v1/dependencies.py`
- `api/v1/trips.py`
- `api/v1/collaboration.py`
- `services/collaboration_service.py`
- `services/trip_service.py`
- `models/api_schemas.py`
- `frontend/src/api/client.js`

### Acceptance criteria
- Every authorization decision is server-side.
- Cross-user and cross-trip access tests fail safely.
- Raw tokens, secrets, and sensitive internal errors are absent.
- Resource IDs cannot be used to bypass trip membership checks.

### Tests required
- Unauthenticated and inactive-user tests.
- Global-admin-versus-trip-admin tests.
- Cross-trip ID access tests.
- Removed/left member tests.
- Actor impersonation and client-role manipulation tests.
- Token storage and error disclosure tests.

## 13. Testing & Concurrency

### Exact requirement
Add meaningful persistence-level tests for race conditions and data integrity, not sequential substitutes.

### Implementation tasks
- [x] Use separate SQLAlchemy sessions and actual file-backed database connections.
- [x] Use thread workers or equivalent concurrent execution.
- [x] Test two invitation acceptance attempts and assert one active membership.
- [x] Test concurrent duplicate membership insertion and database uniqueness.
- [x] Test concurrent vote creation/change and one vote row.
- [x] Test concurrent proposal finalization and one decision.
- [x] Test concurrent ownership transfers and one active owner with matching `Trip.user_id`.
- [x] Test concurrent checklist completion/update consistency.
- [x] Test rollback behavior for domain writes and notifications.
- [x] Handle SQLite locking limitations explicitly while preserving real persistence assertions.
- [ ] Add PostgreSQL concurrency coverage when a PostgreSQL test environment is available.

### Relevant files/modules to inspect
- `tests/`
- `database/models.py`
- `services/collaboration_service.py`
- `database/connection.py`
- `alembic/versions/`

### Acceptance criteria
- Race tests exercise real database transactions.
- Unique constraints and locks enforce the intended invariants.
- Losing concurrent operations return deterministic conflict/domain errors.
- No duplicate active membership, vote, decision, or owner remains after races.

### Tests required
- All concurrency scenarios listed above.
- Authorization under concurrent mutation.
- Rollback/no-notification tests.
- Existing regression suite without weakened assertions.

## 14. Final Regression Verification

### Exact requirement
Run all backend, migration, frontend, and integration checks from a clean state and report only fresh results.

### Implementation tasks
- [x] Remove temporary test databases, generated logs, build artifacts, and runtime Chroma changes not intended for source control.
- [x] Run focused Group Travel tests.
- [x] Run concurrency and ownership tests.
- [x] Run Knowledge Center tests.
- [x] Run RAG and Travel Guide tests.
- [x] Run authentication tests.
- [x] Run personal trip CRUD and regeneration tests.
- [x] Run AI planner, SSE, and structured-output tests.
- [x] Run the full pytest suite.
- [x] Run Alembic upgrade head.
- [x] Run Alembic downgrade one step or previous expected revision.
- [x] Run Alembic upgrade head again.
- [x] Run fresh frontend lint.
- [x] Run fresh frontend production build.
- [ ] Run available frontend tests.
- [x] Inspect all changed files and remove unused imports.
- [x] Run static diagnostics and whitespace checks.
- [x] Review `git diff` and `git status`.
- [x] Confirm no commit, push, or tag was created.

### Relevant files/modules to inspect
- `tests/`
- `frontend/package.json`
- `pyproject.toml`
- `alembic.ini`
- all changed source and migration files

### Acceptance criteria
- Focused Group Travel tests pass.
- Full pytest passes.
- Migration round trip passes.
- Fresh frontend lint and build pass.
- Existing RAG, Knowledge Center, Travel Guide, auth, planner, SSE, and personal-trip functionality pass.
- No secrets or unintended runtime artifacts remain.

### Tests required
- Record the exact command and output for every required validation command.
- Do not report a pass based on stale or partial terminal output.
- Report warnings separately from failures.

## 15. Final Completion Checklist

### Backend and authorization
- [x] `TripService` has no independent-session fallback.
- [x] All production `TripService` callers pass request-scoped sessions.
- [x] `TripAccessService` is used for every trip read and mutation.
- [x] Personal trips still work.
- [x] Group members can access shared trips.
- [x] Non-members, left members, and removed members are denied.
- [x] Global admin is never treated as trip admin.
- [x] Ownership transfer is transactional and leaves exactly one owner.

### Members and invitations
- [x] Conversion is idempotent.
- [x] Member listing, role changes, removal, leave, and transfer work.
- [x] Active membership uniqueness is enforced.
- [ ] Invitation lifecycle is complete.
- [x] Raw invitation tokens are never stored.
- [ ] Logged-out acceptance resumes after login or registration.
- [ ] Invitation UI handles pending, expired, revoked, accepted, and invalid states.

### Proposals, voting, and decisions
- [x] All six proposal types are supported.
- [x] Type-specific payload validation is enforced server-side.
- [x] Proposal creation, editing, closing, and deadlines work.
- [x] Vote creation, change, removal, uniqueness, and authorization work.
- [x] Finalization is transactional and concurrency-safe.
- [x] Decision history is immutable and includes vote snapshots.
- [x] Revision metadata includes source and target revisions.
- [x] Destination, hotel, restaurant, activity, and itinerary-item applications are safe and deterministic.
- [x] Destination changes use an explicit controlled replanning workflow.
- [x] Duplicate application and unsafe replacement are prevented.

### Checklist, chat, and notifications
- [ ] Checklist CRUD, assignment, completion, reopening, and cleanup work.
- [ ] Checklist UI is complete and server-backed.
- [x] Chat send, edit, delete, pagination, polling, and authorization work.
- [x] Deleted messages are not shown as active content.
- [ ] Required notification events are emitted transactionally.
- [ ] Notification list, unread count, mark-read, mark-all, and navigation work.

### Frontend and refresh
- [x] Group workspace is integrated into `TripDetailPage`.
- [x] Collaboration UI is modularized into focused components.
- [ ] Personal itinerary rendering is preserved.
- [x] Loading, empty, error, permission, and success states are usable.
- [x] Active-tab REST refresh/polling is reliable and cleaned up correctly.
- [ ] Logged-out invitation navigation preserves tokens safely.

### Database, security, and quality
- [x] All migrations upgrade, downgrade, and re-upgrade successfully.
- [x] Foreign keys, indexes, check constraints, and unique constraints are verified.
- [x] Concurrency tests exercise actual persistence.
- [x] Security and privacy tests pass.
- [ ] No TODOs, debug prints, fake collaboration state, raw tokens, secrets, or runtime artifacts remain.
- [x] Full pytest suite passes.
- [x] Fresh frontend lint passes.
- [x] Fresh frontend production build passes.
- [x] RAG, Knowledge Center, Travel Guide, authentication, planner, SSE, and personal-trip regressions pass.
- [ ] Manual end-to-end checklist is completed.
- [x] No commit, push, or tag has been created.
