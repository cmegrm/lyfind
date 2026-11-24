# Understand the website

CSA Automated Lost and Found System | Simple group reviewer | 1 of 3

## What problem does it solve?

The website helps the CSA office record found belongings, connect them with lost reports, verify the owner, and record a safe handover. A suggested match starts a review; it does not prove ownership.

## Who uses it?

| User | What they can do |
|---|---|
| Student or professor | Report lost or found items and track their own claims. |
| Guest | Report lost or found items and track their own claims. |
| CSA administrator | Receive items, review matches, verify claims, approve and release items, and manage staff. |

## The full workflow to remember

**1. Report and receive.** The owner files a lost report. CSA physically receives a found item and records its photo and private details.

**2. Suggest and confirm.** The system compares same-category records. CSA reviews a suggestion and confirms it before the owner is notified.

**3. Online check.** The invited owner submits identifying answers. CSA compares them with the hidden details.

**4. In-person check.** The owner visits CSA with ID and ownership proof. CSA records explicit evidence-capture consent and checks ownership.

**5. Approve and release.** CSA records the required photo evidence and signature, approves the claim, then separately records physical handover.

**6. Preserve the record.** The item becomes Claimed / released, the lost report closes, and notifications and audit history remain saved.

## Two important differences

**A found report is not inventory yet.** The item cannot be claimed until it is physically received by CSA.<br/>**Approval is not physical release.** Handover is a separate recorded action.

To open the project: run `python3 main.py`, keep the terminal open, and visit http://127.0.0.1:8765. Use the clearly labeled demonstration accounts.


---

# Understand the code and database

Use these explanations when the instructor asks how the website works | 2 of 3

## What happens when someone submits a form?

**Browser form -> Python service -> SQLite database -> screen update.** HTML gives the page structure, CSS controls appearance, and JavaScript handles interaction. The Python backend checks permissions and business rules before saving. Related database changes are grouped in a transaction: they succeed together or roll back together.

Technology: HTML, CSS, JavaScript, Python with its built-in HTTP server, and SQLite. Our own Python classes provide the OOP design.

## OOP concepts in simple terms

| Concept | Actual example in our project |
|---|---|
| Encapsulation | Item and Claim protect status. Controlled methods reject a skipped step or an invalid transition. See lyfind/domain.py. |
| Inheritance | Student, Professor, Guest, and CSAAdministrator share behavior through the User hierarchy. See lyfind/users.py. |
| Polymorphism | The same permissions() call produces role-appropriate actions. Permission checks use that shared interface. |
| Abstraction | MatchingService defines score(). AI and typed-detail implementations provide different ways to calculate it. |
| Factory pattern | MatchingServiceFactory selects the usable matching service. |
| Adapter pattern | ClipAdapter translates our text/image embedding methods into the external model's encode() calls. |

## Where are records stored?

| Location or table | Purpose |
|---|---|
| data/demo.sqlite3 | The local demonstration database file; it persists after restart. |
| users | Identity, role, staff password hash, and account status. |
| lost_reports / found_reports | Owner reports and finder reports awaiting physical turn-in. |
| items / matches | Received inventory and scored report-item connections. |
| claims | Answers, verification, consent, evidence references, approval, and release. |
| notifications / audit_logs | User updates and append-only action history. |
| data/uploads + uploads table | Photos/signatures are files; the table stores metadata and references. |

Cleone can explain: "I am assigned to the database. Users, reports, items, and claims are linked using IDs and foreign keys. The schema also prevents duplicate active claims. We keep the database and upload folder together so the records and images stay connected."


---

# Practice explaining it

Learn the reason behind each rule, not just the screen buttons | 3 of 3

## A short opening you can say

"Our project is the CSA Automated Lost and Found System. It helps the campus office manage lost reports and physically received belongings. The system suggests matches, but CSA confirms them and verifies ownership online and in person. Consent and evidence are required before approval and physical release. The records are stored in SQLite."

## Questions you should be ready to answer

**Why keep photos and identifying details private?**
So claimants must describe details themselves instead of copying the answers from the website.

**What prevents two people claiming the same item?**
An active claim reserves the item. The service checks it, and a database unique index also prevents duplicate active claims.

**What happens when verification fails?**
CSA records a rejection reason, the attempt is counted, and the reservation is removed. Three rejections block that claimant from further claims on that item.

**Can users approve their own claims?**
No. Approval and release are administrator-only actions. The backend rejects unauthorized requests.

**Is matching fully AI-powered in the class demo?**
The prepared Windows installation now uses local DINOv2 for photo similarity and CLIP for words versus photos. A new computer needs one-time AI setup. Clearly labeled typed fallback remains available. A high score is not proof of ownership.

**How is matching scored?**
AI mode uses description 30, photo 30, color 15, brand 15, and place/date 10. The fallback rescales its 40 typed-detail points to 100. Strong starts at 60; possible starts at 40.

**Do the sample accounts mean real school sign-in is active?**
No. They are fictional local identities for presentation, and the on-screen code only appears in demo mode without SMTP. Live school email codes need real SMTP settings and the real roster of allowed emails.

**How do you know the workflow works?**
The repeatable demo completes release and rejects invalid operations. The latest delivered version also passed 63 automated tests.

## What everyone should practice

Explain the full workflow once without reading. Then each member should explain their assigned component and show one invalid operation. Cleone can lead the database explanation; agree on the other presentation areas as a group. Describe actual responsibilities honestly.

Useful files: lyfind/users.py (roles), lyfind/domain.py (state), lyfind/matching.py (abstraction and patterns), lyfind/services.py (workflow), lyfind/schema.sql (database), and scripts/demo.py (repeatable evidence). Use fictional ID and signature images during the presentation.

## Updated code structure and normalization

Read `docs/CODE_GUIDE.md` for the new service classes and an example call.
`lyfind/services.py` now delegates to six smaller classes under `lyfind/workflows/`.
`claims` stores the claim lifecycle; `claim_answers` stores one question/answer per
row with a composite key. `users.name` is generated from name parts, rather than
a separately editable field. See `docs/DATABASE.md` for the normal forms and
explicit remaining exceptions; do not describe the whole schema as strict 3NF.
