package main

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os/exec"
	"regexp"
	"strconv"
	"time"
)

const maxPingCount = 100

// hostnameRe accepts RFC 1123 hostnames: dot-separated labels of letters,
// digits and inner hyphens. No shell metacharacters, spaces or leading '-'.
var hostnameRe = regexp.MustCompile(`^(?i:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?i:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*\.?$`)

// avgRe matches the summary line of iputils/busybox/BSD ping, e.g.
// "rtt min/avg/max/mdev = 0.1/0.2/0.3/0.0 ms" or "round-trip min/avg/max = ...".
var avgRe = regexp.MustCompile(`min/avg/max(?:/[a-z]+)? = [\d.]+/([\d.]+)/`)

func validHost(host string) bool {
	if net.ParseIP(host) != nil {
		return true
	}
	return len(host) <= 253 && hostnameRe.MatchString(host)
}

// MeasureLatency pings host count times and returns the average RTT in milliseconds.
// ping is executed directly (no shell) with the host as a single argv element,
// after strict validation of the host and count.
func MeasureLatency(host string, count int) (float64, error) {
	if !validHost(host) {
		return 0, errors.New("invalid host")
	}
	if count <= 0 || count > maxPingCount {
		return 0, fmt.Errorf("count must be between 1 and %d", maxPingCount)
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(count)*2*time.Second+5*time.Second)
	defer cancel()

	// "--" ends option parsing so the host can never be read as a flag.
	out, err := exec.CommandContext(ctx, "ping", "-c", strconv.Itoa(count), "--", host).CombinedOutput()
	if err != nil {
		return 0, fmt.Errorf("ping failed: %w", err)
	}

	m := avgRe.FindSubmatch(out)
	if m == nil {
		return 0, errors.New("could not parse ping output")
	}
	avg, err := strconv.ParseFloat(string(m[1]), 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse average latency: %w", err)
	}
	return avg, nil
}
