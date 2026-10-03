"""Retry a transient HTTP failure and catch a typed client error."""

import httpx

from mountainash_transport import (
    HttpClientError,
    HttpNotFoundError,
    HttpRequestEngine,
    RequestPolicy,
    RetryPolicy,
)


def main() -> None:
    attempts: list[str] = []

    def files_service(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        if request.url.path == "/reports/missing.csv":
            return httpx.Response(404)
        if attempts.count(request.url.path) == 1:
            return httpx.Response(503)  # first attempt: transient failure
        return httpx.Response(200, content=b"region,total\nnorth,120\n")

    policy = RequestPolicy(retry=RetryPolicy(max_attempts=3, backoff_base=0, backoff_jitter=False))
    with httpx.Client(transport=httpx.MockTransport(files_service)) as client:
        engine = HttpRequestEngine(client, policy)
        response = engine.request("GET", "https://files.example.com/reports/sales.csv")
        try:
            engine.request("GET", "https://files.example.com/reports/missing.csv")
        except HttpNotFoundError as error:
            not_found = error
        else:
            raise AssertionError("404 must raise")

    assert response.status_code == 200 and response.text.startswith("region,total")
    assert attempts.count("/reports/sales.csv") == 2
    assert attempts.count("/reports/missing.csv") == 1  # 404 is not retried
    assert isinstance(not_found, HttpClientError)
    print(f"sales.csv: 200 after {attempts.count('/reports/sales.csv')} attempts")
    print(f"missing.csv: {type(not_found).__name__}, not retried")


if __name__ == "__main__":
    main()
