"""Mode N1: bounded session amortization. The hard bounds must never be exceeded (Phase 7 exit)."""

import json
import threading
from collections import defaultdict

import pytest

from pqcstore.crypto import chunked_aead as ca
from pqcstore.crypto import mlkem
from pqcstore.crypto.envelope import decrypt_bytes, encrypt_bytes
from pqcstore.crypto.kdf import canonical_json
from pqcstore.crypto.session import ReceiverSessionCache, SenderSession, SessionPolicy


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(scope="module")
def pair():
    return mlkem.generate_keypair()


def by_session(grants):
    sessions = defaultdict(list)
    for grant in grants:
        sessions[grant.session_id].append(grant)
    return sessions


@pytest.mark.parametrize("b_max,n", [(1, 7), (5, 23), (10, 10), (100, 250)])
def test_count_bound(pair, b_max, n):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=b_max, t_max_s=3600))
    grants = [session.grant() for _ in range(n)]
    sessions = by_session(grants)
    assert session.rotations == len(sessions) == -(-n // b_max)
    for members in sessions.values():
        assert [g.seq for g in members] == list(range(len(members)))
        assert len(members) <= b_max
        assert [g.rotated for g in members] == [True] + [False] * (len(members) - 1)
        assert len({g.ke_ct for g in members}) == 1


def test_b_max_one_is_per_object_kem(pair):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=1, t_max_s=3600))
    grants = [session.grant() for _ in range(5)]
    assert len({g.root for g in grants}) == 5 and all(g.rotated for g in grants)


def test_time_bound(pair):
    clock = FakeClock()
    session = SenderSession(pair.public_key, SessionPolicy(b_max=1000, t_max_s=10), clock=clock)
    first = session.grant()
    clock.now += 9.999
    assert session.grant().session_id == first.session_id
    clock.now += 0.001  # age reaches T_max exactly: rotate before issuing
    rotated = session.grant()
    assert rotated.session_id != first.session_id and rotated.rotated and rotated.age_s == 0


def test_queue_aware_bound_follows_load_within_caps(pair):
    """The bound is fixed per session (a hard cap), and adapts from one session to the next."""
    level = {"u": 0.0}
    policy = SessionPolicy(b_max=100, t_max_s=3600, queue_aware=True, b_min=2, ewma_alpha=0.5)
    session = SenderSession(pair.public_key, policy, utilization=lambda: level["u"])

    def phase(u, n):
        level["u"] = u
        return [session.grant() for _ in range(n)]

    idle = phase(0.0, 6)
    busy = phase(7.0, 400)   # out-of-range utilization is clipped to 1
    calm = phase(-3.0, 400)  # ... and to 0
    assert {g.bound for g in idle} == {2}
    assert max(g.bound for g in busy) == 100
    assert calm[-1].bound == 2
    for grants in (idle, busy, calm):
        for members in by_session(grants).values():
            assert len(members) <= members[0].bound <= policy.b_max
    assert 0.0 <= session.rho_hat <= 1.0


def test_concurrent_stress_never_exceeds_bounds(pair):
    """64 threads x 400 grants against B_max = 10 and a short T_max."""
    policy = SessionPolicy(b_max=10, t_max_s=0.05)
    session = SenderSession(pair.public_key, policy)
    grants, lock = [], threading.Lock()

    def worker():
        local = [session.grant() for _ in range(400)]
        with lock:
            grants.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(64)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(grants) == 64 * 400
    for members in by_session(grants).values():
        seqs = sorted(g.seq for g in members)
        assert seqs == list(range(len(seqs)))          # no duplicates, no gaps
        assert len(members) <= policy.b_max           # hard count bound
        assert max(g.age_s for g in members) < policy.t_max_s  # hard lifetime bound
        assert sum(g.rotated for g in members) == 1


def test_objects_in_one_session_get_distinct_keys(pair, identity):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=10, t_max_s=60))
    manifest_a, stored_a = encrypt_bytes(pair.public_key, identity, b"same" * 50, 1024, "N1",
                                         session)
    manifest_b, stored_b = encrypt_bytes(pair.public_key, identity, b"same" * 50, 1024, "N1",
                                         session)
    ctx_a, ctx_b = json.loads(manifest_a)["context"], json.loads(manifest_b)["context"]
    assert ctx_a["session_id"] == ctx_b["session_id"]
    assert (ctx_a["session_seq"], ctx_b["session_seq"]) == (0, 1)
    assert stored_a != stored_b
    assert decrypt_bytes(pair.private_key, manifest_b, stored_b, identity, mode="N1") == \
        b"same" * 50


def test_receiver_cache_amortizes_decapsulation(pair, identity):
    policy = SessionPolicy(b_max=10, t_max_s=60)
    session = SenderSession(pair.public_key, policy)
    sealed = [encrypt_bytes(pair.public_key, identity, bytes([i]) * 100, 1024, "N1", session)
              for i in range(25)]
    cache = ReceiverSessionCache(policy)
    for i, (manifest, stored) in enumerate(sealed):
        assert decrypt_bytes(pair.private_key, manifest, stored, identity, mode="N1",
                             session_cache=cache) == bytes([i]) * 100
    assert cache.decapsulations == 3  # 25 objects in sessions of 10, 10, 5


def test_receiver_refuses_objects_beyond_its_bound(pair, identity):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=50, t_max_s=60))
    for _ in range(20):
        manifest, stored = encrypt_bytes(pair.public_key, identity, b"x", 1024, "N1", session)
    strict = ReceiverSessionCache(SessionPolicy(b_max=10, t_max_s=60))
    with pytest.raises(ca.IntegrityError, match="session bound"):
        decrypt_bytes(pair.private_key, manifest, stored, identity, mode="N1",
                      session_cache=strict)


@pytest.mark.parametrize("field,value", [
    ("session_seq", 5), ("session_bound", 9), ("session_id", "f" * 32),
])
def test_session_fields_are_authenticated(pair, identity, field, value):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=10, t_max_s=60))
    manifest, stored = encrypt_bytes(pair.public_key, identity, b"data", 1024, "N1", session)
    doc = json.loads(manifest)
    doc["context"][field] = value
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(pair.private_key, canonical_json(doc), stored, identity, mode="N1")


@pytest.mark.parametrize("mutate", [
    lambda c: c.pop("session_id"),
    lambda c: c.update(session_seq=10),          # seq must be < bound
    lambda c: c.update(session_bound=True),
    lambda c: c.update(session_id="short"),
])
def test_malformed_session_fields_are_rejected(pair, identity, mutate):
    session = SenderSession(pair.public_key, SessionPolicy(b_max=10, t_max_s=60))
    manifest, stored = encrypt_bytes(pair.public_key, identity, b"data", 1024, "N1", session)
    doc = json.loads(manifest)
    mutate(doc["context"])
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(pair.private_key, canonical_json(doc), stored, identity, mode="N1")


def test_n1_and_p1_keys_are_domain_separated(pair, identity):
    """An N1 object relabelled as P1 must not decrypt (different HKDF domain and fields)."""
    session = SenderSession(pair.public_key, SessionPolicy(b_max=10, t_max_s=60))
    manifest, stored = encrypt_bytes(pair.public_key, identity, b"data", 1024, "N1", session)
    doc = json.loads(manifest)
    for name in ("session_id", "session_seq", "session_bound"):
        doc["context"].pop(name)
    doc["context"].update(mode="P1", ke="ML-KEM-768")
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(pair.private_key, canonical_json(doc), stored, identity, mode="P1")


def test_invalid_policies_are_rejected():
    for kwargs in ({"b_max": 0, "t_max_s": 1}, {"b_max": 5, "t_max_s": 0},
                   {"b_max": 5, "t_max_s": 1, "b_min": 6}):
        with pytest.raises(ValueError):
            SessionPolicy(**kwargs)
