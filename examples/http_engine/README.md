# HTTP engine

How do HTTP retries and typed errors behave?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/http_engine/example.py
```

Expected output:

```text
sales.csv: 200 after 2 attempts
missing.csv: HttpNotFoundError, not retried
```

`HttpRequestEngine` wraps an `httpx.Client` with a `RequestPolicy`: retry,
timeout and redirect sub-policies. Default retries cover 429 and 5xx for safe
methods, with backoff and `Retry-After` handling; zero backoff here keeps the run
instant. Status errors map to a typed hierarchy (`HttpNotFoundError` →
`HttpClientError` → `HttpResponseError` → `HttpTransportError`). `httpx.MockTransport`
stands in for the server, so no request leaves the process.

Back to the [recipe index](../README.md).
