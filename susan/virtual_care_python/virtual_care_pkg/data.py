"""Cached retrieval, following Shihyun's AdynData pattern."""
from functools import cached_property
from . import queries


class VirtualCareData:
    def __init__(self, db):
        self.db = db

    @cached_property
    def appointments(self):
        return self.db.query(queries.APPOINTMENTS)

    @cached_property
    def reports(self):
        return self.db.query(queries.VIEWED_REPORTS)

    def refresh(self):
        for name in ("appointments", "reports"):
            self.__dict__.pop(name, None)
