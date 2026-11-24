# Implementation requirements map

This map describes the delivered application and its verification points. The supplied activity documents and combined workflow were used as project references. This is a technical handoff for the implementation, not a completed assignment questionnaire.

| Requirement | Implementation and review point |
|---|---|
| Same CSA Lost and Found project and achievable Python backend | README, local web application, and three core operations in `ARCHITECTURE.md` |
| Shared attributes and polymorphic overridden behavior | `lyfind/users.py`: user subclasses and `permissions()` |
| Protected status and rejected invalid transitions | `lyfind/domain.py`: private item and claim status; `lyfind/schema.sql`: transition triggers |
| Service abstraction and two concrete implementations | `lyfind/matching.py`: abstract matching interface, typed details service, and AI service |
| Creational pattern used by real workflow | Matching factory selects the available service |
| Structural pattern used by real workflow | CLIP adapter exposes text and image embedding methods |
| Complete workflow and rejected operation | `WORKFLOW.md`, browser actions, and automated release workflow test |
| Activity diagram with decisions and rejected path | Mermaid activity diagram in `WORKFLOW.md` |
| Database and relationships | `lyfind/schema.sql` and `DATABASE.md` |
| Persistent lost reports and received inventory | Service record creation and SQLite storage |
| University and guest authentication separated from CSA | HTTP authentication routes and role checks |
| Guest one time code and expiry | Authentication component; live delivery requires SMTP configuration |
| Microsoft university identity | Microsoft authentication component; live sign in requires a registered tenant and application |
| Guests report lost items only | Guest role cannot create online found reports or become a staff member |
| Found report physical handoff | Awaiting turn in queue is separate from claimable inventory |
| Private inventory information | Administrator dashboard and authorized private file delivery |
| Weighted matching and typed fallback | Automatic comparisons after report submission and physical receipt, manual rerun, same category rule, threshold levels, factory selection, and fallback audit entry |
| CSA confirmation before owner notice | Match decision operation and user dashboard filtering |
| One active claim and one release per item | Transaction checks and database partial unique indexes |
| Rejected attempt limit | Three rejected claims block the same claimant and item pair |
| Online and in person verification | Separate service actions and guarded status transitions |
| Explicit in person consent before evidence | Recorded purpose, timestamp, evidence association, and approval checks |
| Complete release evidence | Claimant with item photo, ID photo, and signature references required for approval |
| Separate approval and physical release | Approved claim remains reserved until release action records handover |
| Expiry to unclaimed | Configurable item period, default 30 days; active claims excluded |
| Preserved history and audit records | Claims retained and audit update/delete triggers |
| Staff permissions and account status | Administrator management actions and authentication checks |
| Setup and repeatable evidence | README, automated tests, and locally generated workflow evidence |

## External setup required

Microsoft application registration, authorized university tenant details, and SMTP credentials belong to the group or institution and are not fabricated or bundled. Demo mode allows a local end to end review without those services. Optional CLIP matching needs its documented model dependencies and model download; the typed details fallback works without them.

The code and tests provide project evidence. Group members should review and personalize any formal submission or contribution statement; the application does not claim that a named member personally implemented unverified work.
