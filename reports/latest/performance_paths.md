# Performance paths

| Path | Measurement | Count | Success | Failure | P50 ms | P95 ms | Throughput/s | Provider calls | Provider failures | Fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deterministic | MEASURED | 520 | 520 | 0 | 43.127950018970296 | 160.60770998301447 | 25.627 | 0 | 0 | 0 |
| AI-assisted | NOT_MEASURED_NO_PROVIDER_CALLS | 0 | 0 | 0 | None | None | None | 0 | 0 | 0 |
| Overall | MEASURED | 520 | 520 | 0 | 43.127950018970296 | 160.60770998301447 | 25.627 | 0 | 0 | 0 |

> `NOT_MEASURED_NO_PROVIDER_CALLS` means the run made no live AI-provider calls; it is not a zero-latency or zero-failure claim.
