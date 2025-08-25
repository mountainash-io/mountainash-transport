from typing import  Any, Type, Dict, Optional

from functools import lru_cache




# from mountainash_acdrs.utils.file_helper.base_file_helper import Base_FileHelper
from .base_file_helper import Base_FileHelper
from .local_file_helper import Local_FileHelper
from .sftp_file_helper import SFTP_FileHelper
from .s3_file_helper import S3_FileHelper
from .r2_file_helper import R2_FileHelper


from mountainash_settings import SettingsParameters, get_settings
from ..settings import StorageAuthBase
from ..settings.providers import LocalStorageAuthSettings



from ..constants import CONST_STORAGE_PROVIDER_TYPE

class FileHelperFactory:

    path_util_classes: Dict[str, Type[Base_FileHelper]] = {

        CONST_STORAGE_PROVIDER_TYPE.LOCAL: Local_FileHelper,
        CONST_STORAGE_PROVIDER_TYPE.SFTP:       SFTP_FileHelper,
        CONST_STORAGE_PROVIDER_TYPE.S3:         S3_FileHelper,
        CONST_STORAGE_PROVIDER_TYPE.R2:         R2_FileHelper,

        # CONST_STORAGE_PROVIDER_TYPE.S3U:        S3U_FileHelper,


        # CONST_STORAGESYSTEM.GCS:        GCS_FileHelper(),
        # CONST_STORAGESYSTEM.AZ:         AzurePathFormatter(),
        # CONST_STORAGESYSTEM.SSH:        SSHPathFormatter(),
        # Add other filesystem formatters as needed
    }


    storage_interface_objects: dict[Any, Base_FileHelper] = {}



    @classmethod
    def is_storage_initialised(cls, auth_parameters: SettingsParameters) -> bool:

        return auth_parameters in cls.storage_interface_objects.keys()

    @classmethod
    def validate_init_existing_storage_interface(cls, auth_parameters: SettingsParameters, storage_system: str):
        #Check that the types match
        if not isinstance(cls.storage_interface_objects[auth_parameters], cls._get_util_class(storage_system=storage_system)):
            raise ValueError(f"Configuration for namespace '{auth_parameters}' found, but is not an MountainAshBaseSettings object.")


    @classmethod
    def _get_storage_interface_object(cls, auth_parameters: SettingsParameters) -> Base_FileHelper:


        ################################################################################################
        # Big Question - should the index be the settings parameters, or the Auth_Settings?
        # Are there two levels of cache here too, like in retrieving settings objects themselves?
        # The object storage, and the object retrieval lru_cache...
        # The LRU Cache needs to work on the immuatable SettingsParameters Object. Not the AuthSettinsg object.
        # WE should use the Auth_Settinsg object here. As the Settinsg PArameters do not have ALL the information we need. The could have a kwarg over-ride.

        obj_storage: Optional[Base_FileHelper] = cls.storage_interface_objects.get(auth_parameters, None)

        if isinstance(obj_storage, Base_FileHelper):
            return obj_storage
        else:
            raise ValueError(f"Storage object for namespace '{auth_parameters}' found, but is not an MountainAshBaseSettings object.")


    @classmethod
    def get_storage_interface(cls,
                              auth_parameters: Optional[SettingsParameters] = None,
                            #   storage_system: Optional[str] = None,
                              #path: Optional[Union[str,UPath]] =  None,
                              #**kwargs
                              ) -> Base_FileHelper:


        if auth_parameters is None:
            auth_parameters = SettingsParameters.create("DEFAULT_LOCAL", settings_class=LocalStorageAuthSettings)


        auth_settings: StorageAuthBase = get_settings(settings_parameters=auth_parameters)

        if not isinstance(auth_settings, StorageAuthBase):
            raise ValueError(f"Settings object for namespace '{auth_parameters}' found, but is not an StorageAuthBase object.")

        # if not auth_settings.STORAGE_SYSTEM:
        #     raise ValueError(f"Storage system not defined in settings for auth namespace '{auth_settings.STORAGE_NAMESPACE}'")

        # Check the path if provided
        # Move this to the base class for validation...
        # if path:
        #     path_storage_system = PathHelper.identify_storage_system(path=path)

        #     if path_storage_system != auth_settings.STORAGE_SYSTEM:
        #         raise ValueError(f"Storage system in path '{path_storage_system}' does not match storage system in settings '{auth_settings.STORAGE_SYSTEM}'")



        #Validate the kwargs


        #Validate the namespace


        if cls.is_storage_initialised(auth_parameters=auth_parameters):

            #If it was already initialised, why are we trying to re-initialse it? Fail if parameters have changed. Pass if the same, but with a warning.
            cls.validate_init_existing_storage_interface(auth_parameters=auth_parameters, storage_system=auth_settings.PROVIDER_TYPE)

            #Get the existing settings object
            obj_storage: Base_FileHelper = cls._get_storage_interface_object(auth_parameters=auth_parameters)


        #Otherwise We have a new storage interface to create
        else:

            #Create the Storage Interface object
            storage_class: Type[Base_FileHelper] = cls._get_util_class(storage_system=auth_settings.PROVIDER_TYPE)

            #HEre is where we create a storage system interface object, and where we can set kwargs!
            obj_storage = storage_class(auth_parameters)

            cls.storage_interface_objects[auth_parameters] = obj_storage

        return obj_storage




    @classmethod
    def _get_util_class(cls, storage_system: str) -> Type[Base_FileHelper]:
        """
        Returns the path utility class for the given storage system.

        :param storage_system: The storage system for which to get the path utility class.
        :return: The path utility class for the given storage system.
        """
        util_class: Optional[Type[Base_FileHelper]] = cls.path_util_classes.get(storage_system, None)

        if not util_class:
            raise ValueError(f"Unsupported storage_system: {storage_system}")

        return util_class

    # Delegation methods

@lru_cache(maxsize=None)
def get_file_helper_factory() -> FileHelperFactory:
    return FileHelperFactory()
