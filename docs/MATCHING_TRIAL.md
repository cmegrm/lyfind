# Matching trial: a Possible match, not 100

The trial uses the real prepared local CLIP model and fictional records in its own temporary database. It does not edit normal reports, inventory or claims. `MATCHING_TRIAL_OUTPUT.txt` records an actual successful scripted run; the browser screenshots record the same case exercised through the interface.

## The case

| Clue | Lost report | Received item | Contribution |
| --- | --- | --- | --- |
| Description | Brown wallet lost while visiting campus | Brown leather folding wallet | 22.5728 / 30 |
| Photo | No owner photo | Generated illustrative wallet photograph | 8.1909 / 30, owner description compared with item photo |
| Color | brown | Brown | 15 / 15 |
| Brand | Unknown | Unbranded | 0 / 15 |
| Place/date | Campus cafeteria | Student Center, same date | 0 / 10 because place differs |

Total: **45.8 / 100, Possible match**. The location and brand disagree, but the description/image evidence and matching color still create a reviewable candidate. No score is manufactured or forced to a target value.

## A flexible ownership answer

CSA's private record says: **Blue receipt dated Monday tucked behind a red loyalty card.**

The guest submitted:

> There should be a red membership card in it. I tucked a little blue receipt behind the cards, probably from Monday. I cannot remember the wallet's brand, but those two things should still be inside.

The answer is not copied verbatim. In this fictional trial, the staff reviewer accepts the meaningful agreement about the card and receipt. The application does not automatically grade the free-text answer or grant ownership because any text was submitted. It first saves **Online check pending**; CSA's subsequent recorded decision advances it to **In-person check pending**. No in-person consent, approval or release is recorded by this trial.

The real-world reviewer must decide whether details are sufficiently distinctive; a matching phrase or similarity score alone does not establish ownership.

## Repeat it

Prepare local AI once using the project setup tool.

Windows Terminal, inside the project:

```text
.venv\Scripts\python.exe matching_trial.py
.venv\Scripts\python.exe matching_trial.py --serve
```

Mac Terminal, inside the project:

```text
.venv/bin/python matching_trial.py
.venv/bin/python matching_trial.py --serve
```

The first command runs and verifies the sequence, prints the result and removes its temporary data. The second starts a fresh untouched trial at **http://127.0.0.1:8767** for hands-on practice. The trial server remains separate from the normal website on port 8765. Stop it with Ctrl+C when finished; that trial's temporary records then disappear.

Browser sequence:

1. Choose **CSA admin > Matching**, expand **Why this suggestion?**, inspect the private item details and confirm the Possible match.
2. Sign out, choose **Guest > My claims**, and answer the invitation using the natural wording above.
3. Sign out and return as **CSA admin > Claims**. Compare the saved answer with the hidden details. Record the online pass and its reason as the fictional staff reviewer.
4. Show the pending in-person stage and explain why online acceptance is separate from approval and physical release.

The printed case is verified with default proposal weights (30/30/15/15/10). A different model or scoring configuration may change the score. This is a functional classroom example using a generated illustration, not a benchmark of recognition accuracy on real campus photographs.
