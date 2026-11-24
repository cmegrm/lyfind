# Local class demonstration

This package demonstrates the proposed CSA Lost and Found workflow with fictional identities and stored records. It runs with Python 3.10 or newer, SQLite, and a browser. University account registration, mail delivery, and downloading an AI model are unnecessary for this local presentation.

## Start

Run `python3 setup_ai.py` once (optional, for AI), then `python3 main.py`. Open `http://127.0.0.1:8765`. Open **Help > Demo accounts** for the sample sign-ins. They are demonstration identities, not verified Microsoft accounts.

## Present the workflow

1. Sign in as CSA staff. **To do** lists what needs a decision. **Found items** shows what is in the office. Explain that found items have a photo and private details.
2. Open **Matches**. Show **Strong match 96%**, the **AI-assisted** badge and **Why this match?**. Click **Approve**. Only staff see scores.
3. Sign out and sign in as the student. In **My claims** choose **Claim item** and describe something only the owner knows (a yellow star keychain).
4. Back as staff, open **Claims** and **Approve** the answers (online check).
5. When the owner arrives, **Start check**, then **Approve** the office check.
6. Add the owner photo, ID photo and signature (use the fictional images), tick the box and **Approve**.
7. **Hand over**. Show the closed report, the "Done" message and **Admin > Activity**.

If this copy already finished the backpack, reset the demo (delete `data/demo.sqlite3` and `data/uploads` while the server is stopped) or use another item.

## Repeatable evidence and checks

Run `python scripts/demo.py` for a fresh temporary demonstration that leaves the application's database untouched. It completes the release and shows rejected invalid operations. 

Run `python -m unittest discover -s tests -v` to check permissions, privacy, concurrent reservations, both verification steps, consent, evidence, release, authentication boundaries, and storage integrity.

## Explain the OOP design

- `lyfind/users.py` implements shared identity attributes and role-specific permission behavior through inheritance and polymorphism.
- `lyfind/domain.py` protects item and claim state using properties and controlled transitions.
- `lyfind/matching.py` defines an abstract service, AI and typed implementations, a Factory selecting an implementation, and an Adapter wrapping the external encoder.
- `lyfind/services.py` coordinates these objects with database transactions, notifications, and an append-only audit log.
- `lyfind/schema.sql` documents relationships and database-level transition and uniqueness safeguards. `lyfind/storage.py` keeps image references portable and restricted to the upload folder.

## Scope and honest limitations

The presentation follows the supplied workflow. It adds no claim-cancellation policy, claim-timeout policy, exports, or backup interface. Claim timelines and availability explanations display existing rules rather than introduce new ones. The unclaimed-item holding period remains separate from claim reservations.

Real university Microsoft sign-in and real email delivery still need external configuration and have not been verified live. Local DINOv2 and CLIP inference is checked with network connections blocked. Groupmates run `python3 setup_ai.py` once to enable it on their own computer. See LOCAL_AI_MATCHING.md. `python main.py --check-config` reports local setup readiness without printing credentials.

## Update an existing copy

Stop the old server with **Ctrl+C**. Extract the updated package into a new folder. To retain existing records, copy the old **data** folder into the new project folder; copy `.env` separately only if you already configured it. Start the new project and refresh the browser with **Ctrl+F5**. This is a full application update, so replacing only **static** is insufficient.

Uploaded images now use relative references. Earlier absolute references are resolved by filename inside the current upload directory, so a copied data folder remains usable. Missing required images block approval and release rather than produce an incomplete handover record.
