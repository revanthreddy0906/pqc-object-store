"""Large-object streaming, interruption and memory bounds against a live MinIO (SoT Phase 4)."""

import io

import pytest

from pqcstore.benchmark.memprobe import run_isolated
from pqcstore.benchmark.payload import HashingSink, PayloadPool
from pqcstore.cli import main as cli_main
from pqcstore.crypto.chunked_aead import TAG_BYTES, IntegrityError
from pqcstore.storage.encrypted_store import DATA, EncryptedObjectStore, version_prefix

pytestmark = pytest.mark.integration

MIB = 1024 * 1024


@pytest.fixture(scope="module")
def pool():
    return PayloadPool(16 * MIB)


@pytest.fixture
def estore(store):
    return EncryptedObjectStore(store)


def round_trip(estore, settings, key, pool, size, recipient, chunk_size):
    reader = pool.reader(size, offset=size)
    put = estore.put(settings.bucket, key, reader, size, recipient.public_key, chunk_size)
    sink = HashingSink()
    estore.get(settings.bucket, key, recipient.private_key, sink, put.identity.object_version)
    assert sink.bytes_written == size
    assert sink.sha256() == reader.sha256()
    return put


@pytest.mark.parametrize("chunk_size", [1 * MIB, 4 * MIB, 16 * MIB])
def test_chunk_sizes_across_multipart_parts(estore, settings, test_prefix, pool, recipient,
                                            chunk_size):
    # 40 MiB + 3 B: several 8 MiB multipart parts, chunk and part boundaries unaligned.
    round_trip(estore, settings, f"{test_prefix}c{chunk_size}", pool, 40 * MIB + 3, recipient,
               chunk_size)


def test_pool_cycles_for_objects_larger_than_pool(estore, settings, test_prefix, pool, recipient):
    round_trip(estore, settings, f"{test_prefix}big", pool, 3 * len(pool) + 7, recipient, 4 * MIB)


def test_stored_chunk_reorder_in_multipart_object(estore, store, settings, test_prefix, pool,
                                                  recipient):
    put = round_trip(estore, settings, f"{test_prefix}swap", pool, 20 * MIB, recipient, 4 * MIB)
    data_key = version_prefix(put.identity.object_key, put.identity.object_version) + DATA
    stored = store.get_bytes(settings.bucket, data_key)
    record = 4 * MIB + TAG_BYTES
    swapped = stored[record:2 * record] + stored[:record] + stored[2 * record:]
    store.put_bytes(settings.bucket, data_key, swapped)
    with pytest.raises(IntegrityError):
        estore.get(settings.bucket, put.identity.object_key, recipient.private_key, HashingSink())


def test_interrupted_download_raises(estore, store, settings, test_prefix, pool, recipient,
                                     monkeypatch):
    put = round_trip(estore, settings, f"{test_prefix}cut", pool, 12 * MIB, recipient, 4 * MIB)
    real_iter = store.iter_object

    def dropping(bucket, key, read_size=MIB):
        for i, piece in enumerate(real_iter(bucket, key, read_size)):
            if i == 5:
                raise ConnectionResetError("simulated connection drop")
            yield piece

    monkeypatch.setattr(store, "iter_object", dropping)
    with pytest.raises(ConnectionResetError):
        estore.get(settings.bucket, put.identity.object_key, recipient.private_key,
                   HashingSink(), put.identity.object_version)


def test_cli_get_publishes_nothing_on_tamper(estore, store, settings, test_prefix, tmp_path,
                                             recipient, pool):
    from pqcstore import keys
    from pqcstore.crypto.mlkem import KEMKeyPair

    public_path, private_path = tmp_path / "r.pub", tmp_path / "r.key"
    keys.write_keypair(KEMKeyPair(recipient.public_key, recipient.private_key), public_path,
                       private_path)
    source = tmp_path / "in.bin"
    source.write_bytes(pool.reader(9 * MIB).read())
    key = f"{test_prefix}cli"
    assert cli_main(["put", "--bucket", settings.bucket, "--key", key, "--input", str(source),
                     "--recipient-public-key", str(public_path)]) == 0
    version = estore.committed_versions(settings.bucket, key)[-1]
    data_key = version_prefix(key, version) + DATA
    stored = bytearray(store.get_bytes(settings.bucket, data_key))
    stored[-1] ^= 0x01  # corrupt the final chunk's tag: every earlier chunk still verifies
    store.put_bytes(settings.bucket, data_key, bytes(stored))

    output = tmp_path / "out.bin"
    assert cli_main(["get", "--bucket", settings.bucket, "--key", key, "--output", str(output),
                     "--recipient-private-key", str(private_path)]) == 2
    assert not output.exists()
    assert not (tmp_path / "out.bin.partial").exists()


def test_memory_growth_is_below_object_size(store, settings):  # `store` skips if MinIO is down
    """A 96 MiB round trip must not need anywhere near 96 MiB of extra memory."""
    result = run_isolated(96 * MIB, settings.bucket)
    assert result["match"]
    assert result["growth"] < 96 * MIB


def test_hashing_sink_and_reader_agree():
    pool = PayloadPool(1024, seed_bytes=b"abc")
    data = pool.reader(3000, offset=5).read()
    assert len(data) == 3000 and data[:3] == b"cab"
    sink = HashingSink()
    sink.write(data)
    reader = pool.reader(3000, offset=5)
    assert io.BytesIO(reader.read()).read() == data and reader.sha256() == sink.sha256()
