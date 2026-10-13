// Closed-loop GET benchmark for the native reader (SoT v1.14). One process, N goroutines; each
// request reads the manifest and the data of a random fixture object and opens it. Prints one
// JSON line per run: throughput, process CPU per request and latency percentiles.
package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/rand"
	"net"
	"net/http"
	"os"
	"runtime"
	"sort"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type fixture struct {
	X25519SK  string `json:"x25519_sk"`
	MLKEMSeed string `json:"mlkem_seed"`
	XwingSeed string `json:"xwing_seed"`
	Endpoint  string `json:"endpoint"`
	Bucket    string `json:"bucket"`
	Size      int    `json:"size"`
	Objects   map[string][]struct {
		Manifest string `json:"manifest"`
		Data     string `json:"data"`
	} `json:"objects"`
}

func mustHex(s string) []byte {
	b, err := hex.DecodeString(s)
	if err != nil {
		panic(err)
	}
	return b
}

func cpuSeconds() float64 {
	var ru syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &ru)
	tv := func(t syscall.Timeval) float64 { return float64(t.Sec) + float64(t.Usec)/1e6 }
	return tv(ru.Utime) + tv(ru.Stime)
}

func main() {
	fixturePath := flag.String("fixture", "fixture.json", "file written by native_fixture.py")
	mode := flag.String("mode", "P1", "B2, P1 or P3")
	workers := flag.Int("workers", 128, "concurrent requests")
	warmup := flag.Duration("warmup", 5*time.Second, "warm-up before the measured window")
	duration := flag.Duration("duration", 20*time.Second, "measured window")
	label := flag.String("label", "", "copied into the output (repetition, cell)")
	flag.Parse()

	raw, err := os.ReadFile(*fixturePath)
	if err != nil {
		panic(err)
	}
	var fx fixture
	if err := json.Unmarshal(raw, &fx); err != nil {
		panic(err)
	}
	keys, err := NewKeys(mustHex(fx.X25519SK), mustHex(fx.MLKEMSeed), mustHex(fx.XwingSeed))
	if err != nil {
		panic(err)
	}
	objects := fx.Objects[*mode]
	if len(objects) == 0 {
		panic("no fixture objects for mode " + *mode)
	}
	transport := &http.Transport{
		DialContext:         (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
		MaxIdleConns:        *workers + 16,
		MaxIdleConnsPerHost: *workers + 16,
		MaxConnsPerHost:     0,
		DisableCompression:  true,
	}
	client, err := minio.New(fx.Endpoint, &minio.Options{
		Creds:     credentials.NewStaticV4(os.Getenv("MINIO_ROOT_USER"), os.Getenv("MINIO_ROOT_PASSWORD"), ""),
		Secure:    false,
		Transport: transport,
		Region:    "us-east-1",
	})
	if err != nil {
		panic(err)
	}
	client.SetAppInfo("pqcnative", "1")

	read := func(ctx context.Context, key string) ([]byte, error) {
		obj, err := client.GetObject(ctx, fx.Bucket, key, minio.GetObjectOptions{})
		if err != nil {
			return nil, err
		}
		defer obj.Close()
		return io.ReadAll(obj)
	}

	begin := time.Now()
	measureFrom := begin.Add(*warmup)
	stop := measureFrom.Add(*duration)
	var failures int64
	var firstError atomic.Value
	latencies := make([][]float64, *workers)
	var wg sync.WaitGroup
	ctx := context.Background()
	for w := 0; w < *workers; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			rng := rand.New(rand.NewSource(int64(w)*7919 + begin.UnixNano()))
			for {
				start := time.Now()
				if !start.Before(stop) {
					return
				}
				o := objects[rng.Intn(len(objects))]
				var n int
				m, err := read(ctx, o.Manifest)
				var d []byte
				if err == nil {
					d, err = read(ctx, o.Data)
				}
				if err == nil {
					_, n, err = keys.Open(*mode, m, d)
				}
				if err == nil && n != fx.Size {
					err = fmt.Errorf("read %d bytes, expected %d", n, fx.Size)
				}
				end := time.Now()
				if !start.Before(measureFrom) {
					if err != nil {
						atomic.AddInt64(&failures, 1)
						firstError.CompareAndSwap(nil, err.Error())
					} else {
						latencies[w] = append(latencies[w], float64(end.Sub(start))/1e6)
					}
				} else if err != nil {
					firstError.CompareAndSwap(nil, "warm-up: "+err.Error())
				}
			}
		}(w)
	}
	time.Sleep(time.Until(measureFrom))
	cpu0 := cpuSeconds()
	time.Sleep(time.Until(stop))
	cpu1 := cpuSeconds()
	wg.Wait()

	var all []float64
	for _, l := range latencies {
		all = append(all, l...)
	}
	sort.Float64s(all)
	pct := func(p float64) float64 {
		if len(all) == 0 {
			return 0
		}
		return all[int(p*float64(len(all)-1))]
	}
	mean := 0.0
	for _, v := range all {
		mean += v
	}
	if len(all) > 0 {
		mean /= float64(len(all))
	}
	window := duration.Seconds()
	out := map[string]any{
		"mode": *mode, "workers": *workers, "label": *label, "gomaxprocs": runtime.GOMAXPROCS(0),
		"size": fx.Size, "window_s": window, "requests": len(all), "failures": failures,
		"ops_per_s": float64(len(all)) / window, "client_cores": (cpu1 - cpu0) / window,
		"cpu_ms_per_req": 0.0, "mean_ms": mean, "p50_ms": pct(0.50), "p99_ms": pct(0.99),
		"started_unix": float64(begin.UnixNano()) / 1e9, "go": runtime.Version(),
	}
	if len(all) > 0 {
		out["cpu_ms_per_req"] = (cpu1 - cpu0) * 1000 / float64(len(all))
	}
	if e := firstError.Load(); e != nil {
		out["first_error"] = e
	}
	line, _ := json.Marshal(out)
	fmt.Println(string(line))
}
