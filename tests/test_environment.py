"""The measured implementation must be exactly the pinned one (SoT D12, A11)."""

from pqcstore.crypto import oqs_runtime


def test_pinned_liboqs_version_is_loaded():
    assert oqs_runtime.oqs().oqs_version() == oqs_runtime.EXPECTED_LIBOQS_VERSION


def test_ml_kem_768_is_enabled():
    assert "ML-KEM-768" in oqs_runtime.oqs().get_enabled_kem_mechanisms()


def test_ml_kem_768_sizes_match_fips_203():
    details = oqs_runtime.oqs().KeyEncapsulation("ML-KEM-768").details
    assert details["length_public_key"] == 1184
    assert details["length_secret_key"] == 2400
    assert details["length_ciphertext"] == 1088
    assert details["length_shared_secret"] == 32


def test_ml_kem_768_agreement_smoke():
    oqs = oqs_runtime.oqs()
    with oqs.KeyEncapsulation("ML-KEM-768") as recipient:
        public_key = recipient.generate_keypair()
        with oqs.KeyEncapsulation("ML-KEM-768") as sender:
            ciphertext, sent_secret = sender.encap_secret(public_key)
        assert recipient.decap_secret(ciphertext) == sent_secret
