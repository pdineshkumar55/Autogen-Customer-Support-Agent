"""Snapshot and reset of the in-memory mock data (used by evals and the UI)."""
import copy

import data.mock_db as db
from tools import common

_STATEFUL = [db.EMPLOYEES, db.LEAVE_BALANCES, db.PAYSLIPS, db.ACCOUNTS, db.ASSETS,
             db.SERVICE_STATUS, db.ROOM_BOOKINGS, common.TICKETS]
_SNAPSHOT = copy.deepcopy(_STATEFUL)


def reset_state() -> None:
    """Restores mock data IN PLACE, so modules holding references see the reset."""
    for live, snapshot in zip(_STATEFUL, _SNAPSHOT):
        fresh = copy.deepcopy(snapshot)
        live.clear()
        if isinstance(live, dict):
            live.update(fresh)
        else:
            live.extend(fresh)