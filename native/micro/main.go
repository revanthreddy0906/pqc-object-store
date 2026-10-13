// Single-thread timing of the key-recovery operations the native reader uses (exploratory;
// not part of the pre-registered batch N). Prints nanoseconds per operation.
package main

import (
	"crypto/ecdh"
	"crypto/mlkem"
	"crypto/rand"
	"crypto/sha3"
	"encoding/json"
	"fmt"
	"runtime"
	"time"
)

func timeIt(n int, f func()) float64 {
	f()
	start := time.Now()
	for i := 0; i < n; i++ {
		f()
	}
	return float64(time.Since(start).Nanoseconds()) / float64(n)
}

func main() {
	dk, _ := mlkem.GenerateKey768()
	_, ct := dk.EncapsulationKey().Encapsulate()
	sk, _ := ecdh.X25519().GenerateKey(rand.Reader)
	eph, _ := ecdh.X25519().GenerateKey(rand.Reader)
	epk := eph.PublicKey().Bytes()
	out := map[string]any{"go": runtime.Version(), "arch": runtime.GOARCH}
	best := func(f func()) float64 {
		b := 1e18
		for r := 0; r < 5; r++ {
			if v := timeIt(20000, f); v < b {
				b = v
			}
		}
		return b
	}
	out["mlkem768_decaps_ns"] = best(func() { dk.Decapsulate(ct) })
	out["x25519_ns"] = best(func() {
		pub, _ := ecdh.X25519().NewPublicKey(epk)
		sk.ECDH(pub)
	})
	out["xwing_decaps_ns"] = best(func() {
		ssM, _ := dk.Decapsulate(ct)
		pub, _ := ecdh.X25519().NewPublicKey(epk)
		ssX, _ := sk.ECDH(pub)
		h := sha3.New256()
		h.Write(ssM)
		h.Write(ssX)
		h.Write(epk)
		h.Write(epk)
		h.Sum(nil)
	})
	line, _ := json.Marshal(out)
	fmt.Println(string(line))
}
