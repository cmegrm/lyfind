# LyFind code guide

Start with `lyfind/services.py`. It is now a small entry point that sends each task to
an object responsible for that area. The application still starts with
`python3 main.py`; the browser routes have not changed.

## Where to read each feature

| File | Class | Responsibility |
|---|---|---|
| `lyfind/services.py` | `Service` | Connect the application services and delegate calls |
| `lyfind/workflows/reports.py` | `ReportService` | Lost/found reports, guest desk reports, report review |
| `lyfind/workflows/inventory.py` | `InventoryService` | Receive physical items, apply holding periods, control file access |
| `lyfind/workflows/matching.py` | `MatchService` | Run comparisons and record CSA match decisions |
| `lyfind/workflows/claims.py` | `ClaimService` | Submit claims, verify ownership, record consent, approve, release |
| `lyfind/workflows/accounts.py` | `AccountService` | Profiles, passwords, staff management, school roster |
| `lyfind/workflows/dashboard.py` | `DashboardService` | Read and filter records for the current role |
| `lyfind/workflows/base.py` | `WorkflowBase` | Shared validation, permission checks, transactions, record lookup |
| `lyfind/workflows/base.py` | `WorkflowContext` | Share the database, uploads location, matcher, and AI object |
| `lyfind/users.py` | `User` and role subclasses | Represent users and their permitted actions |
| `lyfind/domain.py` | `Item`, `Claim` | Protect the allowed status transitions |
| `lyfind/claim_answers.py` | `ClaimAnswers` | Save and read relational ownership answers |
| `lyfind/database.py` | `Database` | Open connections, initialize, check integrity, back up |
| `lyfind/migrations.py` | `SchemaMigrator` | Convert older schemas without clearing existing records |

## A short example

When the browser submits ownership answers, the HTTP layer calls:

```python
service.submit_claim(current_user, form_data)
```

The facade in `lyfind/services.py` delegates the operation:

```python
def submit_claim(self, user, data):
    return self.claims.submit_claim(user, data)
```

Open `lyfind/workflows/claims.py` to follow the actual rule checks. The service checks
permission, valid answers, consent, report ownership, item availability, a
CSA-confirmed match, and attempt limits. It then saves the claim, answer rows,
and audit entry in one transaction. If any write fails, they all roll back.

`ClaimAnswers` receives that same connection:

```python
ClaimAnswers(connection).save(claim_id, {
    "details": "My initials are inside the pocket",
    "contents": "A blue receipt",
})
```

Two rows are stored in `claim_answers`. The dashboard returns the same familiar
dictionary to the browser. The browser does not need to know the storage layout.

## OOP concepts you can explain in class

| Concept | Actual example | Meaning |
|---|---|---|
| Class and object | `ClaimService` and `service.claims` | The class defines behavior; the object performs it |
| Encapsulation | `Claim.advance()` and `Item.change_status()` | Status changes go through methods that enforce rules |
| Inheritance | `ClaimService(WorkflowBase)` | Claim handling reuses permission and transaction checks |
| Polymorphism | `user.permissions()` | Different role objects answer the same method call differently |
| Abstraction | `MatchingService` | Callers use a shared matching interface |
| Composition | `Service` owns focused service objects | A large task is assembled from smaller objects |
| Separation of concerns | `ClaimAnswers` versus `ClaimService` | Storage code saves answers; workflow code decides when saving is allowed |

Inheritance and composition serve different purposes here: role and workflow
classes inherit genuinely shared behavior, while the facade composes services
that perform different jobs. There is no need for a class for every small helper.
Simple functions such as password hashing remain functions.

## Why the database changed

`claims.answers` previously bundled multiple question/answer pairs into JSON.
`claim_answers` now has `(claim_id, question)` as its composite primary key, and
one `answer` per row. This gives SQLite real keys and constraints for answers.

The account's display name is now a generated `users.name` column. Store or edit
`first_name`, `middle_name`, `last_name`, and `suffix`; SQLite computes `name`.
Do not insert or update `name` directly. Splitting a name into parts alone does
not establish 3NF; removing the independently editable duplicate is the useful
change here. The database guide explains remaining redundant dependencies.

## Suggested reading order

1. `lyfind/users.py`: understand roles and `permissions()`.
2. `lyfind/domain.py`: understand protected item/claim transitions.
3. `lyfind/services.py`: see which object handles each task.
4. `lyfind/workflows/claims.py`: follow one complete ownership workflow.
5. `lyfind/workflows/base.py`: read shared checks when you encounter them.
6. `lyfind/claim_answers.py` and `lyfind/schema.sql`: connect objects to database rows.
7. `lyfind/database.py` and `lyfind/migrations.py`: understand initialization and upgrades.
8. `lyfind/web.py`, `lyfind/auth.py`, and `lyfind/matching.py`: study HTTP, authentication, and AI last.

Authentication and AI are still more advanced modules. The refactor focuses on
the business workflows, shared validation, and normalized ownership storage; it
does not replace working security or AI algorithms with classroom shortcuts.

## Verification

```text
python3 scripts/demo.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p test_normalization.py -v
```

Tests use temporary databases and files. Normalization tests cover composite
keys, answer rollback, legacy answer migration, generated names, stable IDs,
pre-upgrade snapshots, invalid-data rollback, and rejecting newer schemas.

### Verification for this refactor

129 tests passed and 11 optional dependency tests were skipped in the runnable
suite. The full run also encountered 85 local HTTP tests blocked by the execution
environment's socket permissions; those same errors were present before the
refactor. HTTP behavior still needs verification in an unrestricted local run.
The complete `scripts/demo.py` workflow passed. A temporary copy of the existing demo
database upgraded successfully, passed integrity/foreign-key checks, preserved
all original table row counts, and tolerated repeat initialization.

The server already running on port 8765 was left running with its current
schema. Stop it before starting the updated code. The normal startup then
backs up and migrates the original database automatically.
