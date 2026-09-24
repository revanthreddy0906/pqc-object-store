"""Mode N1: bounded ML-KEM session amortization (SoT §16, candidate contribution C3).

The sender runs ML-KEM-768 once per *session root* S_r and derives a distinct key
for every object from it:

    K_i = HKDF-SHA256(S_r, salt_i, "pqc-s3-session-v1" || 0x00 || context_i)

where context_i (authenticated in every chunk) carries the session id, the
object's sequence number in the session and the bound in force. A root is
rotated before it would protect more than B objects or live longer than
T_max seconds. B is either fixed (= B_max) or queue-aware:

    B_t = clip(B_min, B_max, round(B_min + (B_max - B_min) * rho_hat))

with rho_hat an EWMA of the observed client utilization. The hard caps B_max
and T_max are never exceeded; B_max = 1 is per-object ML-KEM (mode P1's cost).

Compromise scope: whoever learns one root learns at most B_max object keys.
The receiver enforces its own B_max too and caches decapsulated roots for at
most T_max and B_max uses.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from pqcstore.crypto import mlkem
from pqcstore.crypto.chunked_aead import IntegrityError

SESSION_DOMAIN = b"pqc-s3-session-v1"


@dataclass(frozen=True)
class SessionPolicy:
    b_max: int
    t_max_s: float
    queue_aware: bool = False
    b_min: int = 1
    ewma_alpha: float = 0.2

    def __post_init__(self) -> None:
        if not 1 <= self.b_min <= self.b_max or self.t_max_s <= 0 or not 0 < self.ewma_alpha <= 1:
            raise ValueError(f"invalid session policy {self}")


@dataclass(frozen=True)
class SessionGrant:
    session_id: str
    seq: int          # 0-based position of this object within its session
    bound: int        # the bound in force for this session (<= b_max)
    ke_ct: bytes      # ML-KEM ciphertext of the session root (stored with every object)
    root: bytes       # S_r; never logged, never stored
    age_s: float      # session age when this grant was issued (< t_max_s)
    rotated: bool     # this grant created the session (it paid for encapsulation)


class SenderSession:
    """Thread-safe issuer of per-object grants under a bounded root."""

    def __init__(self, recipient_mlkem_public: bytes, policy: SessionPolicy,
                 utilization: Callable[[], float] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.policy = policy
        self._public = recipient_mlkem_public
        self._utilization = utilization
        self._clock = clock
        self._lock = threading.Lock()
        self._rho_hat = 0.0
        self._session: tuple[str, bytes, bytes, float, int] | None = None  # id, ct, root, t0, bound
        self._issued = 0
        self.rotations = 0

    @property
    def rho_hat(self) -> float:
        return self._rho_hat

    def active_bound(self) -> int:
        """Bound for the next session: B_max, or queue-aware within [B_min, B_max]."""
        p = self.policy
        if not p.queue_aware:
            return p.b_max
        return max(p.b_min, min(p.b_max, round(p.b_min + (p.b_max - p.b_min) * self._rho_hat)))

    def _observe(self) -> None:
        if self.policy.queue_aware and self._utilization is not None:
            observed = min(1.0, max(0.0, self._utilization()))
            self._rho_hat += self.policy.ewma_alpha * (observed - self._rho_hat)

    def grant(self) -> SessionGrant:
        """Issue the next object's grant, rotating the root first if a bound is reached.
        Rotation (one encapsulation) happens under the lock, so concurrent callers wait
        for it; that waiting is part of the key-establishment cost being measured."""
        with self._lock:
            self._observe()
            now = self._clock()
            rotated = False
            if (self._session is None or self._issued >= self._session[4]
                    or now - self._session[3] >= self.policy.t_max_s):
                ke_ct, root = mlkem.encapsulate(self._public)
                self._session = (uuid.uuid4().hex, ke_ct, root, now, self.active_bound())
                self._issued = 0
                self.rotations += 1
                rotated = True
            session_id, ke_ct, root, created, bound = self._session
            seq = self._issued
            self._issued += 1
            return SessionGrant(session_id, seq, bound, ke_ct, root, now - created, rotated)


class ReceiverSessionCache:
    """Caches decapsulated roots so GETs within a session skip decapsulation, under the
    receiver's own caps: at most b_max objects per root and t_max_s in memory."""

    def __init__(self, policy: SessionPolicy, max_entries: int = 64,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.policy = policy
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple[str, bytes], list] = OrderedDict()  # [root, t0, uses]
        self.decapsulations = 0

    def root(self, mlkem_private: bytes, session_id: str, seq: int, bound: int,
             ke_ct: bytes) -> bytes:
        if not 0 <= seq < bound <= self.policy.b_max:
            raise IntegrityError(f"session bound violated: seq {seq}, bound {bound}, "
                                 f"receiver limit {self.policy.b_max}")
        key = (session_id, ke_ct)
        with self._lock:
            entry = self._entries.get(key)
            now = self._clock()
            if entry is not None and now - entry[1] < self.policy.t_max_s \
                    and entry[2] < self.policy.b_max:
                entry[2] += 1
                self._entries.move_to_end(key)
                return entry[0]
        root = mlkem.decapsulate(mlkem_private, ke_ct)
        with self._lock:
            self.decapsulations += 1
            self._entries[key] = [root, self._clock(), 1]
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return root
