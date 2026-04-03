import pytest
from mountainash_utils_files import PathHelper

from upath import UPath

@pytest.mark.parametrize(
    "path, expected",
    [
        ("/path/to/file", "LOCAL_DISK"),

        ("s3://bucket/object", "S3"),
        # ("gcs://bucket/object", "GCS"),
        # ("az://container/blob", "AZ"),
        ("sftp://user@host/path", "SFTP"),
        ("ssh://user@host/path", "SSH"),
        ("github://user@host/path", "GITHUB"),
        ("SSH://user@host/path", "SSH"),

        # ("C:\\path\\to\\file", "LOCAL_DISK"),
        # ("D:\\path\\to\\file", "LOCAL_DISK"),
        ("/", "LOCAL_DISK"),
        ("~", "LOCAL_DISK"),
        ("~/", "LOCAL_DISK"),

        ("~/data/directory/", "LOCAL_DISK"),
        ("randomfile.txt", "LOCAL_DISK"),
        ("./randomfile.txt", "LOCAL_DISK"),
        ("../randomfile.txt", "LOCAL_DISK"),
        ("file:/", "LOCAL_DISK"),

        (UPath("/"), "LOCAL_DISK"),
        (UPath("~"), "LOCAL_DISK"),
        (UPath("~/"), "LOCAL_DISK"),

        (UPath("~/data/directory/"), "LOCAL_DISK"),
        (UPath("randomfile.txt"), "LOCAL_DISK"),
        (UPath("./randomfile.txt"), "LOCAL_DISK"),
        (UPath("../randomfile.txt"), "LOCAL_DISK"),
    ]
)
def test_identify_storage_system(path: UPath | str, expected: str):
    result = PathHelper.identify_storage_system(path)
    assert result == expected


@pytest.mark.parametrize(
    "path, expected",
    [

        ("s3://bucket/object", "s3://bucket/object"),
        ("s3://bucket/object/", "s3://bucket/object"),
        # ("github://bucket/object", "github://bucket/object"),
        # ("nots3butshouldbe://bucket/object", "s3://bucket/object"),

        ("/path/to/file", "/path/to/file"),
        ("/path/to/file/", "/path/to/file"),


        # ("C:\\path\\to\\file", "C:\\path\\to\\file"),
        # ("D:\\path\\to\\file\\", "D:\\path\\to\\file"),

        ("/", "/"),
        # ("~", "/Users/nathanielramm"),
        # ("~/", "/Users/nathanielramm"),

        ("randomfile.txt", "randomfile.txt"),
        ("randomfile.txt/", "randomfile.txt"),
        ("./randomfile.txt", "randomfile.txt"),
        ("../randomfile.txt", "../randomfile.txt"),

        (UPath("/"), "/"),
        # (UPath("~"), "/Users/nathanielramm"),
        # (UPath("~/"), "/Users/nathanielramm"),
        # (UPath("/Users/nathanielramm/"), "/Users/nathanielramm"),
        (UPath("s3://bucket/object"), "s3://bucket/object"),
        (UPath("s3://bucket/object/"), "s3://bucket/object"),

        # (UPath("~/data/directory/"), CONST_STORAGESYSTEM.LOCAL_DISK),
        # (UPath("randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK),
        # (UPath("./randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK),
        # (UPath("../randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK),
        # ("s3:bucket/object", "s3://bucket/object"),
        # ("s3:bucket/object/", "s3://bucket/object"),
        # ("s3:///bucket/object", "s3://bucket/object"),
        # ("file:/", "file:/"),


    ]
)
def test_format_path(path: UPath | str, expected: str):

    result = PathHelper.format_path(path)
    # result_str = PathHelper.path_to_str(result)

    assert str(result) == str(UPath(expected))



@pytest.mark.parametrize(
    "path",
    [

        ("github://bucket/object"),
        ("nots3butshouldbe://bucket/object"),
        ("s3:bucket/object"),
        ("s3:bucket/object/"),
        ("S3://bucket/object/"),
    ]
)
def test_format_path_invalid(path: UPath | str):

    with pytest.raises(ValueError):
        PathHelper.format_path(path)
