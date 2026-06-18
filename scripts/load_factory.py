from __future__ import annotations

import argparse
import random
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def hit(base_url: str, route: str, mode: str, timeout: float) -> None:
    url = f"{base_url.rstrip('/')}{route}?mode={mode}"
    try:
        with urlopen(url, timeout=timeout) as response:
            response.read()
    except HTTPError:
        pass
    except URLError as exc:
        print(f"request failed: {exc}", flush=True)


def run_phase(base_url: str, name: str, duration: int, rps: float, error_rate: float) -> None:
    print(
        f"phase={name} duration={duration}s rps={rps} error_rate={error_rate}",
        flush=True,
    )
    deadline = time.time() + duration
    interval = 1.0 / rps
    next_tick = time.time()
    sent = 0

    while time.time() < deadline:
        route = "/checkout" if random.random() < 0.75 else "/search"
        mode = "error" if random.random() < error_rate else "normal"
        if name == "slow-latency" and random.random() < 0.65:
            mode = "slow"

        threading.Thread(target=hit, args=(base_url, route, mode, 3.0), daemon=True).start()
        sent += 1
        next_tick += interval
        sleep_for = next_tick - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)

    print(f"phase={name} sent={sent}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="http://demo-api:9102")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    phases = [
        ("warmup-baseline", 180, 2.0, 0.01),
        ("traffic-spike", 75, 18.0, 0.01),
        ("recovery-baseline", 120, 2.0, 0.01),
        ("error-spike", 75, 8.0, 0.45),
        ("slow-latency", 75, 5.0, 0.02),
        ("cooldown", 120, 2.0, 0.01),
    ]

    while True:
        for phase in phases:
            run_phase(args.target, *phase)
        if not args.loop:
            break


if __name__ == "__main__":
    main()
