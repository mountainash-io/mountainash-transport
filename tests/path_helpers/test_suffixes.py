"""Tests for infer_pipeline — suffix-driven Pipeline construction."""
from __future__ import annotations

import pytest

from mountainash_transport.path_helpers.suffixes import infer_pipeline, SUFFIX_TRANSFORMS
from mountainash_transport.storage_transforms import GPG, Gzip, Pipeline


def _kinds(pipeline: Pipeline) -> list[str]:
    """Return the transform class names in outer-to-inner order."""
    return [type(t).__name__ for t in pipeline._outer_to_inner]


def test_suffix_map_covers_spec_baseline():
    assert SUFFIX_TRANSFORMS == {
        ".gz": "gzip",
        ".gzip": "gzip",
        ".gpg": "gpg",
        ".asc": "gpg",
        ".pgp": "gpg",
    }


def test_no_known_suffix_returns_none_and_original_path():
    assert infer_pipeline("data.parquet") == (None, "data.parquet")


def test_bare_stem_returns_none():
    assert infer_pipeline("data") == (None, "data")


@pytest.mark.parametrize("path", ["data.gz", "data.gzip", "data.GZ", "data.Gzip"])
def test_gzip_suffix_default_instance(path: str):
    pipeline, stripped = infer_pipeline(path)
    assert isinstance(pipeline, Pipeline)
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "data"


def test_gzip_custom_instance_threaded_through():
    custom = Gzip(level=9)
    pipeline, _ = infer_pipeline("data.gz", gzip=custom)
    assert pipeline is not None
    assert pipeline._outer_to_inner == (custom,)


@pytest.mark.parametrize("suffix", [".gpg", ".asc", ".pgp"])
def test_gpg_suffix_requires_instance(suffix: str):
    gpg = GPG()
    pipeline, stripped = infer_pipeline(f"data{suffix}", gpg=gpg)
    assert pipeline is not None
    assert pipeline._outer_to_inner == (gpg,)
    assert stripped == "data"


@pytest.mark.parametrize("suffix", [".gpg", ".asc", ".pgp"])
def test_gpg_suffix_without_instance_raises(suffix: str):
    with pytest.raises(ValueError, match=rf"\{suffix} suffix"):
        infer_pipeline(f"data{suffix}")


def test_combined_gz_gpg_outer_is_gpg():
    gpg = GPG()
    pipeline, stripped = infer_pipeline("data.parquet.gz.gpg", gpg=gpg)
    assert pipeline is not None
    # Right-most suffix (.gpg) is the outermost layer.
    assert _kinds(pipeline) == ["GPG", "Gzip"]
    assert stripped == "data.parquet"


def test_repeated_gzip_suffix():
    pipeline, stripped = infer_pipeline("data.gz.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip", "Gzip"]
    assert stripped == "data"


def test_unknown_suffix_mid_chain_halts_parsing():
    pipeline, stripped = infer_pipeline("data.txt.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "data.txt"


def test_url_path_is_handled():
    pipeline, stripped = infer_pipeline("s3://bucket/path/to/data.parquet.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "s3://bucket/path/to/data.parquet"


def test_no_splitting_on_dot_in_directory_segment():
    # Dots in directory components must not be consumed.
    pipeline, stripped = infer_pipeline("/some.dir/data")
    assert pipeline is None
    assert stripped == "/some.dir/data"


def test_infer_pipeline_exported_from_path_helpers():
    from mountainash_transport.path_helpers import infer_pipeline as from_subpkg
    from mountainash_transport.path_helpers.suffixes import infer_pipeline as from_mod
    assert from_subpkg is from_mod


def test_infer_pipeline_exported_at_top_level():
    from mountainash_transport import infer_pipeline as from_top
    from mountainash_transport.path_helpers.suffixes import infer_pipeline as from_mod
    assert from_top is from_mod


def test_suffix_transforms_exported_from_path_helpers():
    from mountainash_transport.path_helpers import SUFFIX_TRANSFORMS as from_subpkg
    from mountainash_transport.path_helpers.suffixes import SUFFIX_TRANSFORMS as from_mod
    assert from_subpkg is from_mod
