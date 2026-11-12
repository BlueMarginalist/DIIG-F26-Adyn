"""Synthetic data for tests: builds the minimal tables the package reads and fills them with a small,
deterministic population. Used by the integration test and handy for trying the package without real data."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

MIN_SCHEMA = """
create table customers (id uuid, created_date timestamp, date_of_birth date, role int, email text, first_name text, last_name text);
create table orders (id uuid, customer_id uuid, name text, sku text, status text, date_order_paid timestamp, created_date timestamp,
                     por_approved boolean, ip text, activated boolean, activation_date timestamp, allied_order_date timestamp);
create table orderstatuses (id uuid, order_id uuid, new_status text, created_date timestamp);
create table shipments (id uuid, order_id uuid, date_shipped timestamp, delivered_to_customer_date timestamp, delivered_to_facility1_date timestamp);
create table samples (id varchar, shipment_id uuid, kind text, status text, received_by_lab_date timestamp, processed_by_lab_date timestamp);
create table resultvalues (id uuid, dna_sample_id varchar, hormone_sample_id varchar, created_date timestamp, adyn_approved boolean, customer_viewed_date timestamp);
create table resultvalueshistory (id uuid, result_values_id uuid, dna_sample_id varchar, hormone_sample_id varchar, created_date timestamp, adyn_approved boolean);
create table profilecompletions (id uuid, customer_id uuid, complete boolean, created_date timestamp);
create table customerintake (id uuid, customer_id uuid, completed_date timestamp);
create table medicalhistory (id uuid, customer_id uuid, completed_date timestamp);
create table medicalbiosubmissions (id uuid, customer_id uuid, completion int);
create table couponorders (id uuid, customer_id uuid);
create table coupons_redeemers (redeemer_id uuid);
create table paymentissues (customer_id uuid);
create table shippingaddresses (id uuid, customer_id uuid, state text);
create table shipments_replacements (old_shipment_id uuid, reason text, reimbursed_date timestamp);
create table shipmentstatuses (id uuid, shipment_id uuid, status text, return_status1 text, return_status2 text, created_date timestamp);
"""


def _columns() -> dict:
    """{table: [columns]} in the order the rows are built, read from MIN_SCHEMA."""
    import re
    out = {}
    for m in re.finditer(r"create table (\w+) \((.*?)\);", MIN_SCHEMA, re.S):
        out[m.group(1)] = [c.strip().split()[0] for c in m.group(2).split(",")]
    return out


def _id() -> str:
    return str(uuid.uuid4())


def seed(conn, n_customers: int = 400, rng_seed: int = 7) -> dict:
    """Insert a synthetic population; returns the ground-truth counts for checking results."""
    rnd = random.Random(rng_seed)
    cust, orders, ostat, ship, samp, res, resh, prof = [], [], [], [], [], [], [], []
    intake, medh, repl, sstat, addr = [], [], [], [], []
    truth = dict(paid=0, sent=0, shipped=0, lab=0, result=0, approved=0, viewed=0, replacement_orders=0, bulk=0)

    def add_customer(i, role=2, domain="adyn.com", paid_month=None, bulk=False):
        cid = _id()
        paid_at = paid_month or datetime(2022, 1, 1) + timedelta(days=rnd.randint(0, 1000))
        cust.append((cid, paid_at - timedelta(days=rnd.randint(0, 20)), datetime(1996, 1, 1).date(), role,
                     f"u{i}@{domain}", "a", "b"))
        addr.append((_id(), cid, rnd.choice(["CA", "NY", "TX", "NC"])))
        return cid, paid_at

    def add_order(cid, paid_at, name="The Birth Control Test", status="reserved", ip=None):
        oid = _id()
        orders.append((oid, cid, name, "ADYN-K-001", status, paid_at, paid_at, False, ip or f"10.0.{rnd.randint(0,255)}.{rnd.randint(0,255)}",
                       False, None, None))
        return oid

    for i in range(n_customers):
        domain = "example.com" if i % 20 == 0 else "adyn.com"
        month = datetime(2023, 2, rnd.randint(1, 28)) if i % 6 == 0 else None
        cid, paid_at = add_customer(i, role=rnd.choice([2, 2, 3]), domain=domain, paid_month=month)
        if rnd.random() > 0.92:       # a few accounts never pay
            continue
        profile_ok = (month is None) and rnd.random() < 0.40 and domain == "adyn.com"
        oid = add_order(cid, paid_at, ip="1.1.1.1" if i % 7 == 0 else None)
        truth["paid"] += 1
        if profile_ok:
            prof.append((_id(), cid, True, paid_at + timedelta(days=rnd.randint(0, 5))))
            if rnd.random() < 0.4:
                intake.append((_id(), cid, paid_at + timedelta(days=2)))
                medh.append((_id(), cid, paid_at + timedelta(days=3)))
        ok_ship = profile_ok and rnd.random() < 0.85
        if not ok_ship:
            continue
        # sent to Allied then left Allied
        ostat.append((_id(), oid, "allied_reserved", paid_at + timedelta(days=1)))
        left = paid_at + timedelta(days=rnd.randint(1, 12))
        ostat.append((_id(), oid, "left_allied_facility", left))
        orders[-1] = orders[-1][:4] + ("left allied facility",) + orders[-1][5:8] + (True,) + orders[-1][9:]
        truth["sent"] += 1
        truth["shipped"] += 1
        sid = _id()
        ship.append((sid, oid, left, left + timedelta(days=3), left + timedelta(days=20)))
        sstat.append((_id(), sid, "delivered", "delivered", "delivered", left + timedelta(days=3)))
        s_slv, s_bld = f"SLV{i:05d}", f"BLD{i:05d}"
        valid_s, valid_b = rnd.random() < 0.97, rnd.random() < 0.94
        recv = left + timedelta(days=rnd.randint(10, 40))
        samp.append((s_slv, sid, "KIT-SLV", "valid" if valid_s else "invalid", recv, recv + timedelta(days=2)))
        samp.append((s_bld, sid, "KIT-BLD", "valid" if valid_b else "invalid", recv, recv + timedelta(days=2)))
        truth["lab"] += 1
        if rnd.random() < 0.12:       # a replacement order for this customer
            rid = add_order(cid, left + timedelta(days=30), name="The Birth Control Test Replacement")
            repl.append((sid, rnd.choice(["Some reason", "Lab reported: QNS", "testing", "Mail: Sample lost in mail",
                                          "Lab reported: Hemolyzed"]), None))
            truth["replacement_orders"] += 1
        if rnd.random() < 0.75:
            created = recv + timedelta(days=rnd.randint(3, 20))
            rv = _id()
            approved = rnd.random() < 0.85
            viewed = created + timedelta(days=rnd.randint(0, 6)) if (approved and rnd.random() < 0.7) else None
            res.append((rv, s_slv, s_bld, created, approved, viewed))
            truth["result"] += 1
            if approved:
                resh.append((_id(), rv, s_slv, s_bld, created + timedelta(days=1), True))
                truth["approved"] += 1
            if viewed:
                truth["viewed"] += 1
    # a bulk account that must be excluded
    bcid, bpaid = add_customer(99999, domain="adyn.com")
    for _ in range(12):
        add_order(bcid, bpaid)
    truth["bulk"] = 1

    with conn.cursor() as cur:
        for table, rows in [("customers", cust), ("orders", orders), ("orderstatuses", ostat), ("shipments", ship),
                            ("samples", samp), ("resultvalues", res), ("resultvalueshistory", resh),
                            ("profilecompletions", prof), ("customerintake", intake), ("medicalhistory", medh),
                            ("shipments_replacements", repl), ("shipmentstatuses", sstat), ("shippingaddresses", addr)]:
            if rows:
                cols = ", ".join(_columns()[table])
                ph = ", ".join(["%s"] * len(_columns()[table]))
                cur.executemany(f"insert into {table} ({cols}) values ({ph})", rows)
    return truth
