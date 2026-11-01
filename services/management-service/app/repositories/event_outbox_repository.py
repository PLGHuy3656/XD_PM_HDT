from app.database import get_connection


def claim_pending_events(limit: int = 25) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH candidates AS (
                    SELECT event_id
                    FROM event_outbox
                    WHERE published_at IS NULL
                      AND next_attempt_at <= NOW()
                      AND (
                          locked_until IS NULL
                          OR locked_until < NOW()
                      )
                    ORDER BY created_at
                      LIMIT %s
                      FOR UPDATE SKIP LOCKED
                )
                UPDATE event_outbox AS events
                SET locked_until = NOW() + INTERVAL '60 seconds',
                    attempts = events.attempts + 1
                FROM candidates
                WHERE events.event_id = candidates.event_id
                RETURNING events.event_id, events.event_type, events.payload
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "event_id": str(row[0]),
            "event_type": row[1],
            "payload": row[2],
        }
        for row in rows
    ]


def mark_event_published(event_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE event_outbox
                SET published_at = NOW(),
                    locked_until = NULL,
                    last_error = NULL
                WHERE event_id = %s
                """,
                (event_id,),
            )


def release_event_for_retry(event_id: str, error: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE event_outbox
                SET locked_until = NULL,
                    next_attempt_at = NOW() + INTERVAL '5 seconds',
                    last_error = %s
                WHERE event_id = %s
                  AND published_at IS NULL
                """,
                (error[:1000], event_id),
            )
