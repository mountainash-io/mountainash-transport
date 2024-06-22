import pytest
from mountainash_utils_files import FileInterface#, get_file_interface
# from mountainash_utils_files.file_helpers import FileHelperFactory, Base_FileHelper

from mountainash_constants import CONST_STORAGESYSTEM
from mountainash_settings import SettingsUtils, SettingsParameters
from mountainash_auth_settings import AuthSettings

import random
from upath import UPath


auth_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace="local", 
                                                                                settings_class=AuthSettings, 
                                                                                STORAGE_SYSTEM=CONST_STORAGESYSTEM.LOCAL_DISK.value)

@pytest.mark.parametrize(
    "path, expected",
    [
        ("/", True),
        ("~", True),        
        ("~/", True),

        ("~/data/directory/", False),
        ("randomfile.txt", False),
        ("./randomfile.txt", False),
        ("../randomfile.txt", False),

        (UPath("/"), True),
        (UPath("~"), True),        
        (UPath("~/"), True),

        (UPath("~/data/directory/"), False),
        (UPath("randomfile.txt"), False),
        (UPath("./randomfile.txt"), False),
        (UPath("../randomfile.txt"), False),
    ]
)
def test_path_exists(path: UPath | str, expected: str):
    result = FileInterface.path_exists(auth_parameters=auth_parameters,path=path)
    assert result == expected

@pytest.mark.parametrize(
    "path, expected",
    [
        ("/", True),
        ("~", True),        
        ("~/", True),
        # ("/etc/sudoers", False),
        # ("/etc/sudoers.d", True),

        ("~/data/directory/", False),
        ("randomfile.txt", False),
        ("./randomfile.txt", False),
        ("../randomfile.txt", False),

        (UPath("/"), True),
        (UPath("~"), True),        
        (UPath("~/"), True),

        (UPath("~/data/directory/"), False),
        (UPath("randomfile.txt"), False),
        (UPath("./randomfile.txt"), False),
        (UPath("../randomfile.txt"), False),
    ]
)
def test_path_is_dir(path: UPath | str, expected: str):
    result = FileInterface.path_is_dir(auth_parameters=auth_parameters,path=path)
    assert result == expected

@pytest.mark.parametrize(
    "path, expected",
    [
        ("/", False),
        ("~", False),        
        ("~/", False),
        # ("/etc/sudoers", True),
        # ("/etc/sudoers.d", False),

        ("~/data/directory/", False),
        ("randomfile.txt", False),
        ("./randomfile.txt", False),
        ("../randomfile.txt", False),

        (UPath("/"), False),
        (UPath("~"), False),        
        (UPath("~/"), False),
        (UPath("/etc/sudoers"), True),

        # (UPath("~/data/directory/"), False),
        # (UPath("randomfile.txt"), False),
        # (UPath("./randomfile.txt"), False),
        # (UPath("../randomfile.txt"), False),
    ]
 )
def test_path_is_file(path: UPath | str, expected: str):
    result = FileInterface.path_is_file(auth_parameters=auth_parameters,path=path)
    assert result == expected



# @pytest.mark.parametrize(
#     "source_path, destination_path",
#     [
#         ("~/test_report.xml", "~/test_report{rand}.xml"),
#     ]
# )
# def test_copy_file_local(source_path: UPath | str, destination_path: UPath | str):

#     rand = random.randint(0, 1000)

#     destination_path = destination_path.format(rand=rand)

#     storage_facade: FileInterface = get_file_interface()  

#     #Auth
#     local_auth_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace="local", settings_class=AuthSettings)
#     local_storage: Base_FileHelper = FileHelperFactory.get_storage_interface(auth_parameters=local_auth_parameters, storage_system=CONST_STORAGESYSTEM.LOCAL_DISK.value) 
    
#     copied: bool = storage_facade.copy_binarystream(destination_path=destination_path, source_path=source_path, obj_destination_storage=local_storage, obj_source_storage=local_storage)

#     assert copied == True    
#     assert local_storage.path_is_file(path=destination_path)


# @pytest.mark.parametrize(
#     "source_path, destination_path",
#     [
#         ("POFL2021Draft.csv", "~/POFL2021Draft{rand}.csv"),
#     ]
# )
# def test_copy_file_s3(source_path: UPath | str, destination_path: UPath | str):

#     rand = random.randint(0, 1000)

#     destination_path = destination_path.format(rand=rand)

#     storage_facade: FileInterface = get_file_interface()  

#     #Auth
#     s3_auth_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace="s3_warehouse", 
#                                                                                           settings_class=AuthSettings, 
#                                                                                           settings_system=CONST_STORAGESYSTEM.S3.value,
#                                                                                           USERNAME="minio",
#                                                                                           PASSWORD="minio123",
#                                                                                           HOST="192.168.1.52",
#                                                                                           PORT=9000)

#     s3_storage: Base_FileHelper = FileHelperFactory.get_storage_interface(auth_parameters=s3_auth_parameters, storage_system=CONST_STORAGESYSTEM.S3.value) 
    
#     local_auth_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace="local", settings_class=AuthSettings)
#     local_storage: Base_FileHelper = FileHelperFactory.get_storage_interface(auth_parameters=local_auth_parameters, storage_system=CONST_STORAGESYSTEM.LOCAL_DISK.value) 


#     copied: bool = storage_facade.copy_binarystream(destination_path=destination_path, source_path=source_path, obj_destination_storage=local_storage, obj_source_storage=s3_storage)

#     assert copied == True    
#     assert local_storage.path_is_file(path=destination_path)