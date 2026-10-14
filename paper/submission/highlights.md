# Highlights

- ML-KEM lowered object-store throughput only at or near client CPU saturation.
- Python client: 4.0 to 4.9 % slower than X25519 when saturated.
- Controls on x86 traced that deficit mainly to the library binding.
- A native Go reader on one core was 9.5 % slower, so cost depends on implementation.
- ML-KEM adds 1,056 bytes of ciphertext per object over X25519.
