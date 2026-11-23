"""S3 response capture: one permanent handler per client, per-call collectors (#10 §3)."""
from __future__ import annotations

import contextlib

import pytest

from mountainash_transport._core.s3_capture import ResponseCapture, install_client_hooks


def _respond(capture: ResponseCapture, bucket: str, key: str, version: str) -> None:
    capture._on_after_call(parsed={"VersionId": version}, context={"input_params": {"Bucket": bucket, "Key": key}})


def test_a_collector_sees_only_its_own_key() -> None:
    capture = ResponseCapture()
    with capture.collect("b", "k1") as one, capture.collect("b", "k2") as two:
        _respond(capture, "b", "k1", "v1")
        _respond(capture, "b", "k2", "v2")
    assert one == [{"VersionId": "v1"}] and two == [{"VersionId": "v2"}]


def test_overlapping_collectors_on_one_key_both_see_both_responses() -> None:
    capture = ResponseCapture()
    with capture.collect("b", "k") as first, capture.collect("b", "k") as second:
        _respond(capture, "b", "k", "v1")
        _respond(capture, "b", "k", "v2")
    assert len(first) == len(second) == 2


def test_a_collector_closing_early_does_not_take_the_other_ones_place() -> None:
    """A opens, B opens, B's response, B closes, A's response: A must have seen both."""
    capture = ResponseCapture()
    with capture.collect("b", "k") as first:
        with capture.collect("b", "k") as second:
            _respond(capture, "b", "k", "theirs")
        _respond(capture, "b", "k", "ours")
    assert second == [{"VersionId": "theirs"}]
    assert first == [{"VersionId": "theirs"}, {"VersionId": "ours"}]  # ambiguous, so not attributed


@pytest.mark.parametrize("fail", [False, True])
def test_collectors_are_removed_after_success_and_failure(fail: bool) -> None:
    capture = ResponseCapture()
    with pytest.raises(RuntimeError) if fail else contextlib.nullcontext():
        with capture.collect("b", "k"):
            if fail:
                raise RuntimeError("upload failed")
    assert capture._collectors == {}


def test_hooks_are_installed_once_per_client() -> None:
    import boto3

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    first = install_client_hooks(client)
    assert install_client_hooks(client) is first
    with first.collect("b", "k") as seen:
        client.meta.events.emit(
            "after-call.s3.PutObject", parsed={"VersionId": "v"}, context={"input_params": {"Bucket": "b", "Key": "k"}},
            http_response=None, model=None,
        )
    assert seen == [{"VersionId": "v"}]  # one handler, so one response


def test_presigning_uses_sigv4_where_botocore_would_choose_sigv2() -> None:
    import boto3

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    assert "AWSAccessKeyId=" in client.generate_presigned_url("get_object", Params={"Bucket": "b", "Key": "k"})
    install_client_hooks(client)
    url = client.generate_presigned_url("get_object", Params={"Bucket": "b", "Key": "k"})
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url and "AWSAccessKeyId=" not in url
