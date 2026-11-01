import unittest
from unittest.mock import patch
from uuid import uuid4

from app.repositories.technician_repository import TechnicianRepository


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.executions.append((query, params))

    def fetchone(self):
        return next(self.rows)


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True


class TechnicianAssignmentOutboxTests(unittest.TestCase):
    def test_assignment_and_event_are_committed_together(self):
        assignment_id = uuid4()
        technician_id = str(uuid4())
        owner_id = str(uuid4())
        cursor = FakeCursor(
            [
                (assignment_id,),
                ("FARM-01", "Farm One", owner_id, "Technician One"),
            ]
        )
        connection = FakeConnection(cursor)

        with patch(
            "app.repositories.technician_repository.get_connection",
            return_value=connection,
        ):
            result = TechnicianRepository().assign_technician(
                technician_id,
                str(uuid4()),
            )

        self.assertEqual(result, str(assignment_id))
        self.assertTrue(connection.committed)
        self.assertEqual(len(cursor.executions), 3)
        insert_query, insert_params = cursor.executions[2]
        self.assertIn("INSERT INTO event_outbox", insert_query)
        event = insert_params[2].obj
        self.assertEqual(
            event["recipient_user_ids"],
            [technician_id, owner_id],
        )
        self.assertEqual(
            event["event_type"],
            "management.technician_assigned",
        )
        self.assertEqual(event["event_id"], insert_params[0])


if __name__ == "__main__":
    unittest.main()
