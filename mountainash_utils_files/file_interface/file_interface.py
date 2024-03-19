from upath import UPath
from typing import Union, Any, Type, Dict, Optional, List, IO, Iterable
from functools import lru_cache
import io
from mountainash_utils_files.file_helpers import Base_FileHelper, FileHelperFactory, get_file_helper_factory

# from mountainash_acdrs.utils.data_storage.base_data_storage import Base_FileHelper
# from mountainash_acdrs.utils.data_storage.data_storage_factory import FileHelperFactory

from mountainash_utils_files import PathHelper
from mountainash_settings import SettingsParameters, AuthSettings, get_auth_settings, SettingsUtils
from mountainash_constants import CONST_STORAGESYSTEM

import shutil


class FileInterface:
    
    factory: FileHelperFactory = get_file_helper_factory()

    @classmethod
    def resolve_storage_object(cls, 
                                obj_storage: Optional[Base_FileHelper],
                                auth_parameters: Optional[SettingsParameters]
                               ) -> Base_FileHelper:
       
        if obj_storage:
            return obj_storage
        
        if not auth_parameters:
            raise ValueError("resolve_storage_object(): No settings provided")
        
        return cls.factory.get_storage_interface(auth_parameters=auth_parameters)


    #===================
    # File Copy Operations
    # When identifying each storage system, we will need to determine the type of connection to use
    # Where a connection is not required (ie local filesystem), we can use the standard file operations
    # Therefore we will need to identify the type of connection to use for each storage system combination
    # Eg: When the two systems are the same, we can do path to path
    # When the two systems are different, and one does not require a connection

    @classmethod
    def copy_path_to_path(cls, 
                  source_path: UPath|str, 
                  destination_path: UPath|str,                    
                  source_auth_settings_parameters: SettingsParameters, 
                  destination_auth_settings_parameters: SettingsParameters,
                  
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False

                 ) -> bool:

        #Get the auth settings objects
        source_auth_settings: AuthSettings = get_auth_settings(auth_settings_parameters=source_auth_settings_parameters)
        destination_auth_settings: AuthSettings = get_auth_settings(auth_settings_parameters=destination_auth_settings_parameters)

        #Storage System Exists
        settings_source_storage_system: str|None = source_auth_settings.STORAGE_SYSTEM
        settings_destination_storage_system: str|None = destination_auth_settings.STORAGE_SYSTEM

        if not settings_source_storage_system:
            raise ValueError(f"Source storage system not defined in source settings for auth namespace '{source_auth_settings.STORAGE_NAMESPACE}'")

        if not settings_destination_storage_system:
            raise ValueError(f"Source storage system not defined in destination settings for auth namespace '{destination_auth_settings.STORAGE_NAMESPACE}'")

        #Storage System Validation
        path_source_storage_system: str|None = PathHelper.identify_storage_system(path=source_path)
        path_destination_storage_system: str|None = PathHelper.identify_storage_system(path=destination_path)

        if path_source_storage_system != settings_source_storage_system:
            raise ValueError(f"Storage system in path '{path_source_storage_system}' does not match storage system in settings '{settings_source_storage_system}'")

        if path_destination_storage_system != settings_destination_storage_system:
            raise ValueError(f"Storage system in path '{path_source_storage_system}' does not match storage system in settings '{settings_destination_storage_system}'")

        #Get the storage interfaces
        source_storage_interface: Base_FileHelper = FileHelperFactory.get_storage_interface(auth_parameters=source_auth_settings_parameters) 
        destination_storage_interface: Base_FileHelper = FileHelperFactory.get_storage_interface(auth_parameters=destination_auth_settings_parameters) 

        source_attributes: dict[str, bool] = source_storage_interface.get_interface_attributes(role="source")
        destination_attributes: dict[str, bool] = destination_storage_interface.get_interface_attributes(role="destination")


        #Resolve the best way to move the data

        return True


    @classmethod
    def _init_connections(cls,
                    obj_destination_storage: Base_FileHelper, 
                    obj_source_storage: Base_FileHelper,                           
                          ) -> None:
       #Resolve connections
        if obj_destination_storage.requires_ssh_connection:
            obj_destination_storage.connect_ssh()
        if obj_destination_storage.requires_io_connection:
            obj_destination_storage.connect()
        if obj_source_storage.requires_ssh_connection:
            obj_source_storage.connect_ssh()
        if obj_source_storage.requires_io_connection:
            obj_source_storage.connect()        


    @classmethod
    def put_object_from_stream(cls,
                    destination_path: Optional[Union[str, UPath]], 
                    source_path: Optional[Union[str, UPath]], 

                    obj_destination_storage: Optional[Base_FileHelper] = None, 
                    obj_source_storage: Optional[Base_FileHelper] = None, 

                    obj_destination_settings: Optional[SettingsParameters] = None, 
                    obj_source_settings: Optional[SettingsParameters] = None, 

                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,

                    ) -> bool|Any:

        #Format Paths
        u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
        u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

        if not u_source_path:
            raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
        if not u_destination_path:
            raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

        #Resolve and establish storage objects
        obj_destination_storage = cls.resolve_storage_object(obj_storage=obj_destination_storage, auth_parameters=obj_destination_settings)
        obj_source_storage = cls.resolve_storage_object(obj_storage=obj_source_storage, auth_parameters=obj_source_settings)

        if not obj_destination_storage.supports_put_from_stream:
            raise ValueError(f"put_object_from_stream(): Destination storage system does not support put from stream")
        
        #Resolve connections
        cls._init_connections(obj_destination_storage=obj_destination_storage, obj_source_storage=obj_source_storage)


        if obj_source_storage.check_if_io_connected() and obj_destination_storage.check_if_io_connected():

            try:
                source_stream_length: int = obj_source_storage.get_size(path=u_source_path)
                source_stream: IO = obj_source_storage.open_read_binarystream(source_path=u_source_path)

                put_object = obj_destination_storage.put_object_from_stream(destination_path=u_destination_path, 
                                                                            source_stream=source_stream, 
                                                                            length=source_stream_length,
                                                                            encrypt=encrypt, 
                                                                            decrypt=decrypt,
                                                                            compress=compress,
                                                                            decompress=decompress
                                                                            )
                return put_object

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False


    @classmethod
    def put_object_from_path(cls,
                    destination_path: Optional[Union[str, UPath]], 
                    source_path: Optional[Union[str, UPath]], 

                    obj_destination_storage: Optional[Base_FileHelper] = None, 
                    obj_source_storage: Optional[Base_FileHelper] = None, 

                    obj_destination_settings: Optional[SettingsParameters] = None, 
                    obj_source_settings: Optional[SettingsParameters] = None, 

                    ) -> bool|Any:

        #Format Paths
        u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
        u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

        if not u_source_path:
            raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
        if not u_destination_path:
            raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

        #Resolve and establish storage objects
        obj_destination_storage = cls.resolve_storage_object(obj_storage=obj_destination_storage, auth_parameters=obj_destination_settings)
        obj_source_storage = cls.resolve_storage_object(obj_storage=obj_source_storage, auth_parameters=obj_source_settings)

        if not obj_destination_storage.supports_put_from_path:
            raise ValueError(f"put_object_from_stream(): Destination storage system does not support put from stream")
        
        #Resolve connections
        cls._init_connections(obj_destination_storage=obj_destination_storage, obj_source_storage=obj_source_storage)

        #Do it!
        if obj_source_storage.check_if_io_connected() and obj_destination_storage.check_if_io_connected():
            try:
                put_object = obj_destination_storage.put_object_from_path(destination_path=u_destination_path, 
                                                                          source_path=source_path)
                return put_object

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False


    @classmethod
    def get_object_to_stream(cls,
                    destination_path: Optional[Union[str, UPath]], 
                    source_path: Optional[Union[str, UPath]], 

                    obj_destination_storage: Optional[Base_FileHelper] = None, 
                    obj_source_storage: Optional[Base_FileHelper] = None, 

                    obj_destination_settings: Optional[SettingsParameters] = None, 
                    obj_source_settings: Optional[SettingsParameters] = None, 

                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,

                    ) -> bool|Any:

        #Format Paths
        u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
        u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

        if not u_source_path:
            raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
        if not u_destination_path:
            raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

        #Resolve and establish storage objects
        obj_destination_storage = cls.resolve_storage_object(obj_storage=obj_destination_storage, auth_parameters=obj_destination_settings)
        obj_source_storage = cls.resolve_storage_object(obj_storage=obj_source_storage, auth_parameters=obj_source_settings)

        if not obj_source_storage.supports_get_to_stream:
            raise ValueError(f"put_object_from_stream(): Destination storage system does not support put from stream")
        
        #Resolve connections
        cls._init_connections(obj_destination_storage=obj_destination_storage, obj_source_storage=obj_source_storage)

        #Do it!
        if obj_source_storage.check_if_io_connected() and obj_destination_storage.check_if_io_connected():

            try:
                source_length = obj_source_storage.get_size(path=u_source_path)

                destination_stream: IO = obj_destination_storage.open_write_binarystream(destination_path=u_destination_path)
                get_object: bool = obj_source_storage.get_object_to_stream(source_path=u_source_path, 
                                                                           destination_stream=destination_stream, 
                                                                           length=source_length,
                                                                            encrypt=encrypt, 
                                                                            decrypt=decrypt,
                                                                            compress=compress,
                                                                            decompress=decompress)

                return get_object

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False

    @classmethod
    def get_object_to_path(cls,
                    destination_path: Optional[Union[str, UPath]], 
                    source_path: Optional[Union[str, UPath]], 

                    obj_destination_storage: Optional[Base_FileHelper] = None, 
                    obj_source_storage: Optional[Base_FileHelper] = None, 

                    obj_destination_settings: Optional[SettingsParameters] = None, 
                    obj_source_settings: Optional[SettingsParameters] = None, 

                    ) -> bool|Any:

        #Format Paths
        u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
        u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

        if not u_source_path:
            raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
        if not u_destination_path:
            raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

        #Resolve and establish storage objects
        obj_destination_storage = cls.resolve_storage_object(obj_storage=obj_destination_storage, auth_parameters=obj_destination_settings)
        obj_source_storage = cls.resolve_storage_object(obj_storage=obj_source_storage, auth_parameters=obj_source_settings)

        if not obj_source_storage.supports_get_to_path:
            raise ValueError(f"put_object_from_stream(): Destination storage system does not support put from stream")
        
        #Resolve connections
        cls._init_connections(obj_destination_storage=obj_destination_storage, obj_source_storage=obj_source_storage)

        #Do it!
        if obj_source_storage.check_if_io_connected() and obj_destination_storage.check_if_io_connected():

            try:
                get_object: bool = obj_source_storage.get_object_to_path(source_path=u_source_path, 
                                                                         destination_path=u_destination_path,
                                                                         )

                return get_object

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False


    @classmethod
    def copy_stream_to_stream(cls,
                    destination_path: Optional[Union[str, UPath]], 
                    source_path: Optional[Union[str, UPath]], 

                    obj_destination_storage: Optional[Base_FileHelper] = None, 
                    obj_source_storage: Optional[Base_FileHelper] = None, 

                    obj_destination_settings: Optional[SettingsParameters] = None, 
                    obj_source_settings: Optional[SettingsParameters] = None, 

                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,

                    ) -> bool|Any:

        #Format Paths
        u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
        u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

        if not u_source_path:
            raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
        if not u_destination_path:
            raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

        #Resolve and establish storage objects
        obj_destination_storage = cls.resolve_storage_object(obj_storage=obj_destination_storage, auth_parameters=obj_destination_settings)
        obj_source_storage = cls.resolve_storage_object(obj_storage=obj_source_storage, auth_parameters=obj_source_settings)


        #Resolve connections
        cls._init_connections(obj_destination_storage=obj_destination_storage, obj_source_storage=obj_source_storage)

        #Do it!

        if obj_source_storage.check_if_io_connected() and obj_destination_storage.check_if_io_connected():

            #create a bit mask for encrypt/decrypt and compress/decompress 

            try:
                with obj_source_storage.open_read_binarystream(source_path=u_source_path) as source_stream:
                    with obj_destination_storage.open_write_binarystream(destination_path=u_destination_path) as destination_stream:

                        obj_source_storage.copy_stream_to_stream(source_stream=source_stream,
                                                    destination_stream=destination_stream,
                                                    encrypt=encrypt, 
                                                    decrypt=decrypt,
                                                    compress=compress,
                                                    decompress=decompress)

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False


    @classmethod
    def list_sources(cls, 
                     auth_parameters: SettingsParameters, 
                     path: Union[str, UPath] = "", 
                     **kwargs) -> List[str]:

        if not auth_parameters:

            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)


            

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.list_sources(path, **kwargs)

    @classmethod
    def path_exists(cls, 
                    path: Union[str, UPath], 
                    auth_parameters: Optional[SettingsParameters]=None, 
                    **kwargs) -> bool:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.path_exists(path=path, **kwargs)

    @classmethod
    def calculate_checksum(cls, 
                           path: Union[str, UPath], 
                           auth_parameters: Optional[SettingsParameters]=None,  
                           **kwargs) -> str:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.calculate_checksum(path=path, **kwargs)
    
    @classmethod
    def get_size(cls, 
                 path: Union[str, UPath],
                 auth_parameters: Optional[SettingsParameters]=None, 
                 ) -> int:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.get_size(path=path)    
    
    @classmethod
    def count_sources(cls, 
                      path: Union[str, UPath], 
                      auth_parameters: Optional[SettingsParameters]=None,
                      **kwargs) -> int:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)


        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.count_sources(path=path, **kwargs)        
    
    @classmethod
    def path_is_dir(cls, 
                    path: Union[str, UPath],
                    auth_parameters: Optional[SettingsParameters]=None, 
                    ) -> bool:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)


        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.path_is_dir(path=path)    
    
    @classmethod
    def path_is_file(cls, 
                     path: Union[str, UPath],
                     auth_parameters: Optional[SettingsParameters]=None,  
                     ) -> bool:    

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.path_is_file(path=path)            
    
    @classmethod
    def create_directory(cls, 
                         path: Union[str, UPath],
                         auth_parameters: Optional[SettingsParameters]=None, 
                         ) -> bool:

        if not auth_parameters:
            storage_system: str|None = PathHelper.identify_storage_system(path=path)
            settings_namespace: str = f"default_{storage_system}"
            auth_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=settings_namespace, settings_class=AuthSettings, STORAGE_SYSTEM=storage_system)

        obj_storage: Base_FileHelper = cls.factory.get_storage_interface(auth_parameters=auth_parameters)

        return obj_storage.create_directory(path=path)
    

@lru_cache(maxsize=None)
def get_file_interface() -> FileInterface:
    return FileInterface()    

@lru_cache(maxsize=None)
def get_file_helper_object(auth_parameters: SettingsParameters, 
                            #    storage_system: Optional[str] = None,
                            #   path: Optional[str|UPath] =  None
                               ) -> Base_FileHelper:

    factory: FileHelperFactory = get_file_helper_factory()
    
    return factory.get_storage_interface(auth_parameters=auth_parameters)
