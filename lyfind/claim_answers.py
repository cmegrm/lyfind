"""Store one ownership answer per row instead of a JSON bundle in claims."""


class ClaimAnswers:
    """Use the caller's connection so answers and their claim commit together."""

    def __init__(self, connection):
        self.connection = connection

    def save(self, claim_id, answers):
        self.connection.executemany(
            "INSERT INTO claim_answers(claim_id, question, answer) VALUES(?, ?, ?)",
            [(claim_id, question, answer) for question, answer in answers.items()],
        )

    def for_claim(self, claim_id):
        rows = self.connection.execute(
            "SELECT question, answer FROM claim_answers WHERE claim_id=? ORDER BY question",
            (claim_id,),
        )
        return {row["question"]: row["answer"] for row in rows}

    def for_claims(self, claim_ids):
        """Read a dashboard's answers in batches, without one query per claim."""
        result = {claim_id: {} for claim_id in claim_ids}
        ids = list(result)
        for start in range(0, len(ids), 500):
            batch = ids[start:start + 500]
            placeholders = ",".join("?" for _ in batch)
            rows = self.connection.execute(
                f"SELECT claim_id, question, answer FROM claim_answers "
                f"WHERE claim_id IN ({placeholders}) ORDER BY claim_id, question",
                batch,
            )
            for row in rows:
                result[row["claim_id"]][row["question"]] = row["answer"]
        return result
