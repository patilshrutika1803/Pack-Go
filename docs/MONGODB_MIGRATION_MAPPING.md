# MongoDB migration mapping

MongoDB is the application database; Supabase Auth is the identity provider. The Supabase user UUID is the canonical user ID stored in the `users` document and in every user reference.

| Existing SQLAlchemy model | MongoDB representation | Notes |
| --- | --- | --- |
| `User` | `users` collection | `_id` and `supabase_user_id` are the Supabase UUID. No password, password hash, refresh token, or auth recovery secret is stored. |
| `UserPreference` | Embedded `users.preferences` document | One-to-one preferences travel atomically with the owning profile. |
| `RefreshToken` | No application collection | Supabase owns access and refresh token lifecycle. |
| `VerificationToken` | No application collection | Supabase owns email verification. |
| `PasswordResetToken` | No application collection | Supabase owns password recovery. |
| `Trip` | `trips` collection | Itinerary, generated plan metadata, owner, and trip settings remain in one document. |
| `TripMember` | Embedded `trips.members[]` | Membership state and role are trip-scoped. |
| `TripInvitation` | Embedded `trips.invitations[]` | Invitation status and token digest are trip-scoped. Raw invitation tokens are returned only at creation. |
| `Proposal` | Embedded `trips.proposals[]` | Proposal lifecycle stays with the trip. |
| `ProposalVote` | Embedded `trips.proposals[].votes[]` | A vote belongs to one proposal; the service enforces one vote per user. |
| `Decision` | Embedded `trips.decisions[]` | Decisions are trip-scoped. |
| `ChecklistItem` | Embedded `trips.checklist_items[]` | Checklist items are trip-scoped. |
| `GroupMessage` | `trip_messages` collection | Unbounded conversation history is kept outside the trip document. |
| `Notification` | `notifications` collection | Per-user notification feeds are independently queried. |
| `Expense` | `expenses` collection | Expense ownership, payer, trip, and split semantics are retained. |
| `ExpenseShare` | Embedded `expenses.participants[]` | A bounded share list belongs to its expense. |
| `JournalEntry` | `journal_entries` collection | Entries remain independently pageable/editable, with canonical author IDs. |
| `KnowledgeSource` | `knowledge_sources` collection | Stores PDF metadata and file paths only; PDF files and Chroma vectors remain in their existing storage. |

The MongoDB migration changes persistence only. ChromaDB collections (`travel_knowledge` and `trip_preferences`), PDF storage, planner behavior, and RAG logic remain unchanged.
