# CSA Lost and Found architecture

This project is a local Python web application with a SQLite database and a browser interface. Its three core backend functions are recording lost and physically received found items, suggesting and confirming matches, and verifying claims before release. The backend owns permissions and state changes; the browser only requests operations and displays their results.

## Layers

| Layer | Responsibility |
|---|---|
| Browser interface | Sign in, forms, dashboards, private administrator review, and workflow actions |
| HTTP and authentication | Request validation, sessions, CSRF protection, authentication, and authorized file delivery |
| Application services | Role checks, matching review, claim eligibility, consent, verification, release, and audit recording |
| Domain classes | Controlled item and claim state changes and shared user behavior |
| Data storage | Relational records, foreign keys, transaction boundaries, indexes, and immutable audit entries |

All business decisions are checked on the server. Hiding a button in the browser is not used as the permission boundary.

## Encapsulation

`Item` and `Claim` expose status through controlled properties and transition methods. Allowed moves are explicit, so a released item cannot become available and a claim cannot skip verification. Services reload the current database state inside a write transaction before checking and saving a transition. This protects against two requests concurrently reserving or releasing the same item.

Private item details, inventory photographs, identity evidence, and unconfirmed scores are limited to administrator views. Ordinary users see their own reports, claim progress, notifications, and administrator confirmed match invitations.

## Inheritance and polymorphism

The user hierarchy shares account identity and active status. Student, professor, guest, and administrator subclasses override their permitted actions. The same permission check calls the current user's implementation: LPU users and guests can report lost and found items, and administrators can verify ownership and release inventory. A guest identity never grants staff access.

`MatchingService` defines the common matching operation. Typed details and AI implementations follow the same interface, letting the caller request a comparison without knowing which algorithm is active.

## Design patterns

**Factory.** `MatchingServiceFactory` chooses the AI service when its model is available and the typed details service when it is not. The matching caller receives the shared interface. This keeps availability checks and fallback selection out of individual report and workflow actions.

**Adapter.** `HybridAdapter` (DINOv2 photos + CLIP words) or `ClipAdapter` gives the matching service a text and image embedding interface. Model specific image loading and encoding stay in those classes. Replacing the embedding library therefore does not require rewriting the matching workflow.

The fallback service remains usable without downloading a model, and typed-only scores are capped below Strong. It compares color, brand, place, and compatible dates, normalizing the available 40 points to a 100 point score. AI matching additionally uses description and image similarity. All suggestions require the same category; scores at least 80 are strong and scores from 60 through 79.9 are possible. CSA confirmation is still required before contacting an owner.

Saving a lost report or physically receiving an item automatically compares eligible records. Administrators can also rerun matching from their dashboard. No match suggestion automatically notifies a user. When `ENABLE_AI=1`, the optional local DINOv2 and CLIP models are loaded and cached; missing dependencies, model load failures, and failed embedding operations use the typed details fallback and record why in the audit history.

## Identity and deployment

The local demonstration mode provides sample identities for review. It is separate from live email delivery. Students and professors sign in with a 6-digit code sent to a school email (hashed, single use, 10 minutes, 5 tries, 60 second resend, rate limited per email and IP). Roles come from the allowed-emails roster. Guests confirm sign-up with a code. In demo mode without SMTP the code is shown on the Check your email screen; live mode requires SMTP and never shows codes. Microsoft sign-in is optional and hidden unless configured. Guest reports and claims are flagged until staff check them; staff can block people and hide spam, each with an audit entry. Browser sessions use random opaque tokens with only their hashes stored in the database. Local demo authentication must be disabled when the application is exposed to other users.

SQLite and the included HTTP server make the project easy to run for a laboratory demonstration. A multi instance deployment needs a production web server, shared file storage, backups, HTTPS, and an appropriate database migration plan.

## Maintenance ownership

Cleone's assigned database responsibility covers the schema, relationships, data validation, transaction safety, and database backup and restore procedure. The team should assign and confirm ongoing responsibility for identity and permissions, matching, and claim workflows. These are maintenance areas, not a claim about work performed by individual group members.

## Focused OOP services

`lyfind.services.Service` is a facade: its short methods delegate to objects that each
own one area of work. It composes `ReportService`, `InventoryService`,
`MatchService`, `ClaimService`, `AccountService`, and `DashboardService`.
These services inherit common checks from `WorkflowBase`. A `WorkflowContext`
shares the database, upload directory, matcher, and local AI object.

Reporting and receiving inventory invoke the same matching object inside their
existing transaction. There is no separate commit between saving a report,
matching it, and writing its audit entry. Private photo and ownership checks
remain server-side. `ClaimAnswers` owns the simple SQL for the normalized answer
rows. `Database` owns connections and backups; `SchemaMigrator` owns upgrades.

For a beginner-oriented reading order and examples, see `docs/CODE_GUIDE.md`.
