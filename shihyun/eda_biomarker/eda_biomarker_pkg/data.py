"""AdynData: runs each query once and keeps the cleaned tables for reuse."""
from functools import cached_property

from . import clean, queries


class AdynData:
    """cached access to the tables the analyses need. 
        call refresh() to re-query.
        """

    def __init__(self, db):
        self.db = db

    def refresh(self):
        for name in [k for k, v in type(self).__dict__.items() if isinstance(v, cached_property)]:
            self.__dict__.pop(name, None)

    # --- raw tables
    @cached_property
    def hormones_raw(self):
        return self.db.query(queries.HORMONE_VALUES)

    @cached_property
    def rx_orders(self):
        return clean.label_products(self.db.query(queries.RX_ORDERS))

    @cached_property
    def genetics(self):
        return clean.genetics_flags(self.db.query(queries.GENETICS))

    @cached_property
    def medbio_answers(self):
        return clean.clean_answers(self.db.query(queries.MEDBIO_ANSWERS).set_index("customer_id"))

    @cached_property
    def samples(self):
        return self.db.query(queries.SAMPLES)

    @cached_property
    def medbio_submissions(self):
        return self.db.query(queries.MEDBIO_SUBMISSIONS)

    @cached_property
    def reports(self):
        return self.db.query(queries.REPORTS)

    # --- cleaned / derived tables
    @cached_property
    def hormones(self):
        return clean.clean_hormones(self.hormones_raw)

    @cached_property
    def rx_patients(self):
        return clean.rx_per_patient(self.rx_orders)

    @cached_property
    def patients(self):
        """One row per patient with hormones, prescriptions and genetics."""
        return clean.patient_table(clean.hormone_wide(self.hormones), self.rx_patients, self.genetics)

    @property
    def hormone_names(self):
        return sorted(self.hormones["hormone"].unique())
