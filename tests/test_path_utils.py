import pytest
from mountainash_utils_files import PathHelper
from mountainash_constants import CONST_STORAGESYSTEM

from upath import UPath

@pytest.mark.parametrize(
    "path, expected",
    [
        ("/path/to/file", CONST_STORAGESYSTEM.LOCAL_DISK.value),

        ("s3://bucket/object", CONST_STORAGESYSTEM.S3.value),
        # ("gcs://bucket/object", CONST_STORAGESYSTEM.GCS.value),
        # ("az://container/blob", CONST_STORAGESYSTEM.AZ.value),
        ("sftp://user@host/path", CONST_STORAGESYSTEM.SFTP.value),
        ("ssh://user@host/path", CONST_STORAGESYSTEM.SSH.value),
        ("github://user@host/path", CONST_STORAGESYSTEM.GITHUB.value),
        ("SSH://user@host/path", CONST_STORAGESYSTEM.SSH.value),

        ("C:\\path\\to\\file", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("D:\\path\\to\\file", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("/", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("~", CONST_STORAGESYSTEM.LOCAL_DISK.value),        
        ("~/", CONST_STORAGESYSTEM.LOCAL_DISK.value),

        ("~/data/directory/", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("randomfile.txt", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("./randomfile.txt", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("../randomfile.txt", CONST_STORAGESYSTEM.LOCAL_DISK.value),
        ("file:/", CONST_STORAGESYSTEM.LOCAL_DISK.value),

        (UPath("/"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        (UPath("~"), CONST_STORAGESYSTEM.LOCAL_DISK.value),        
        (UPath("~/"), CONST_STORAGESYSTEM.LOCAL_DISK.value),

        (UPath("~/data/directory/"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        (UPath("randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        (UPath("./randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        (UPath("../randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
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


        ("C:\\path\\to\\file", "C:\\path\\to\\file"),
        ("D:\\path\\to\\file\\", "D:\\path\\to\\file"),

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

        # (UPath("~/data/directory/"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        # (UPath("randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        # (UPath("./randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
        # (UPath("../randomfile.txt"), CONST_STORAGESYSTEM.LOCAL_DISK.value),
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
