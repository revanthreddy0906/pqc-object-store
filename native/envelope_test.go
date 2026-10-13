package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"testing"
)

type vectorFile struct {
	X25519SK  string `json:"x25519_sk"`
	MLKEMSeed string `json:"mlkem_seed"`
	XwingSeed string `json:"xwing_seed"`
	Vectors   []struct {
		Mode       string `json:"mode"`
		Manifest   string `json:"manifest"`
		Ciphertext string `json:"ciphertext"`
		SHA256     string `json:"sha256"`
		Size       int    `json:"size"`
	} `json:"vectors"`
}

func unhex(t *testing.T, s string) []byte {
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// Objects written by the Python client (scripts/native_fixture.py --vectors) must open here.
func TestOpensPythonObjects(t *testing.T) {
	raw, err := os.ReadFile("testdata/vectors.json")
	if err != nil {
		t.Fatal(err)
	}
	var f vectorFile
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	keys, err := NewKeys(unhex(t, f.X25519SK), unhex(t, f.MLKEMSeed), unhex(t, f.XwingSeed))
	if err != nil {
		t.Fatal(err)
	}
	if len(f.Vectors) < 9 {
		t.Fatalf("expected at least 9 vectors, got %d", len(f.Vectors))
	}
	for _, v := range f.Vectors {
		data := unhex(t, v.Ciphertext)
		sum, n, err := keys.Open(v.Mode, unhex(t, v.Manifest), data)
		if err != nil {
			t.Fatalf("%s size %d: %v", v.Mode, v.Size, err)
		}
		if n != v.Size || hex.EncodeToString(sum[:]) != v.SHA256 {
			t.Fatalf("%s size %d: wrong plaintext", v.Mode, v.Size)
		}
		// Tampering must be rejected.
		if len(data) > 0 {
			data[0] ^= 1
			if _, _, err := keys.Open(v.Mode, unhex(t, v.Manifest), data); err == nil {
				t.Fatalf("%s size %d: modified ciphertext accepted", v.Mode, v.Size)
			}
		}
		if _, _, err := keys.Open("B1", unhex(t, v.Manifest), unhex(t, v.Ciphertext)); err == nil {
			t.Fatalf("%s: wrong expected mode accepted", v.Mode)
		}
	}
}
