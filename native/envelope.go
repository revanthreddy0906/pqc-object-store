// Native reader for the pqc-s3 object format (SoT v1.14): the GET path of modes B2 (X25519),
// P1 (ML-KEM-768) and P3 (X-Wing), reading objects written by the Python client.
//
// It does the same per-object work as the Python reader: parse the manifest, check the mode
// and the hash of the key-establishment ciphertext, recover the shared secret, derive the
// object key with HKDF-SHA256 over the canonical context, and open every AES-256-GCM chunk
// with the index, length and final flag in the associated data.
package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/hkdf"
	"crypto/mlkem"
	"crypto/sha256"
	"crypto/sha3"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
)

const (
	objectDomain = "pqc-s3-object-v2"
	tagBytes     = 16
	mlkemCT      = 1088
)

var xwingLabel = []byte{0x5c, 0x2e, 0x2f, 0x2f, 0x5e, 0x5c}

// Keys holds the recipient's private key material in the forms Go needs.
type Keys struct {
	X25519 *ecdh.PrivateKey
	MLKEM  *mlkem.DecapsulationKey768
	// X-Wing: expanded once per process, as the draft permits (the Python client caches too).
	XwingM  *mlkem.DecapsulationKey768
	XwingX  *ecdh.PrivateKey
	XwingPK []byte // X25519 public key of the X-Wing recipient
}

func NewKeys(x25519SK, mlkemSeed, xwingSeed []byte) (*Keys, error) {
	k := &Keys{}
	var err error
	if k.X25519, err = ecdh.X25519().NewPrivateKey(x25519SK); err != nil {
		return nil, err
	}
	if k.MLKEM, err = mlkem.NewDecapsulationKey768(mlkemSeed); err != nil {
		return nil, err
	}
	expanded := make([]byte, 96)
	shake := sha3.NewSHAKE256()
	shake.Write(xwingSeed)
	shake.Read(expanded)
	if k.XwingM, err = mlkem.NewDecapsulationKey768(expanded[:64]); err != nil {
		return nil, err
	}
	if k.XwingX, err = ecdh.X25519().NewPrivateKey(expanded[64:96]); err != nil {
		return nil, err
	}
	k.XwingPK = k.XwingX.PublicKey().Bytes()
	return k, nil
}

type manifest struct {
	Context     json.RawMessage `json:"context"`
	KeCT        string          `json:"ke_ct"`
	Salt        string          `json:"salt"`
	NoncePrefix string          `json:"nonce_prefix"`
}

type objectContext struct {
	Mode          string `json:"mode"`
	ChunkSize     int    `json:"chunk_size"`
	ChunkCount    int    `json:"chunk_count"`
	PlaintextSize int    `json:"plaintext_size"`
	KeCTSHA256    string `json:"ke_ct_sha256"`
}

func b64(s string) ([]byte, error) {
	if b, err := base64.StdEncoding.DecodeString(s); err == nil {
		return b, nil
	}
	if b, err := base64.URLEncoding.DecodeString(s); err == nil {
		return b, nil
	}
	if b, err := base64.RawURLEncoding.DecodeString(s); err == nil {
		return b, nil
	}
	return base64.RawStdEncoding.DecodeString(s)
}

func (k *Keys) recover(mode string, keCT []byte) ([]byte, error) {
	switch mode {
	case "B2":
		pub, err := ecdh.X25519().NewPublicKey(keCT)
		if err != nil {
			return nil, err
		}
		return k.X25519.ECDH(pub)
	case "P1":
		return k.MLKEM.Decapsulate(keCT)
	case "P3":
		if len(keCT) != mlkemCT+32 {
			return nil, errors.New("bad X-Wing ciphertext length")
		}
		ctM, ctX := keCT[:mlkemCT], keCT[mlkemCT:]
		ssM, err := k.XwingM.Decapsulate(ctM)
		if err != nil {
			return nil, err
		}
		pub, err := ecdh.X25519().NewPublicKey(ctX)
		if err != nil {
			return nil, err
		}
		ssX, err := k.XwingX.ECDH(pub)
		if err != nil {
			return nil, err
		}
		h := sha3.New256()
		h.Write(ssM)
		h.Write(ssX)
		h.Write(ctX)
		h.Write(k.XwingPK)
		h.Write(xwingLabel)
		return h.Sum(nil), nil
	}
	return nil, fmt.Errorf("unsupported mode %q", mode)
}

// Open verifies and decrypts one object and returns the SHA-256 of its plaintext (the Python
// benchmark also hashes what it reads) and the plaintext length.
func (k *Keys) Open(mode string, manifestBytes, data []byte) ([32]byte, int, error) {
	var none [32]byte
	var m manifest
	if err := json.Unmarshal(manifestBytes, &m); err != nil {
		return none, 0, err
	}
	var ctx objectContext
	if err := json.Unmarshal(m.Context, &ctx); err != nil {
		return none, 0, err
	}
	if ctx.Mode != mode {
		return none, 0, fmt.Errorf("mode mismatch: manifest %q, expected %q", ctx.Mode, mode)
	}
	keCT, err := b64(m.KeCT)
	if err != nil {
		return none, 0, err
	}
	want, err := b64(ctx.KeCTSHA256)
	if err != nil {
		return none, 0, err
	}
	if got := sha256.Sum256(keCT); !bytes.Equal(got[:], want) {
		return none, 0, errors.New("key-establishment ciphertext does not match its hash")
	}
	salt, err := b64(m.Salt)
	if err != nil {
		return none, 0, err
	}
	prefix, err := b64(m.NoncePrefix)
	if err != nil {
		return none, 0, err
	}
	ikm, err := k.recover(mode, keCT)
	if err != nil {
		return none, 0, err
	}
	info := make([]byte, 0, len(objectDomain)+1+len(m.Context))
	info = append(append(append(info, objectDomain...), 0), m.Context...)
	key, err := hkdf.Key(sha256.New, ikm, salt, string(info), 32)
	if err != nil {
		return none, 0, err
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return none, 0, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return none, 0, err
	}
	hash := sha256.New()
	total, offset := 0, 0
	nonce := make([]byte, 12)
	copy(nonce, prefix)
	aad := make([]byte, len(m.Context)+13)
	copy(aad, m.Context)
	for i := 0; i < ctx.ChunkCount; i++ {
		length := ctx.ChunkSize
		final := i == ctx.ChunkCount-1
		if final {
			length = ctx.PlaintextSize - ctx.ChunkSize*(ctx.ChunkCount-1)
		}
		end := offset + length + tagBytes
		if end > len(data) {
			return none, 0, errors.New("ciphertext truncated")
		}
		binary.BigEndian.PutUint64(nonce[4:], uint64(i))
		binary.BigEndian.PutUint64(aad[len(m.Context):], uint64(i))
		binary.BigEndian.PutUint32(aad[len(m.Context)+8:], uint32(length))
		aad[len(m.Context)+12] = 0
		if final {
			aad[len(m.Context)+12] = 1
		}
		plain, err := gcm.Open(nil, nonce, data[offset:end], aad)
		if err != nil {
			return none, 0, fmt.Errorf("chunk %d: %w", i, err)
		}
		hash.Write(plain)
		total += len(plain)
		offset = end
	}
	if offset != len(data) {
		return none, 0, errors.New("trailing data after the final chunk")
	}
	var sum [32]byte
	copy(sum[:], hash.Sum(nil))
	return sum, total, nil
}
