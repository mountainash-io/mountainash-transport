# from typing import TYPE_CHECKING
import lazy_loader

# Core file helpers (always available - eager loading)

# Type hints for optional storage backends (zero runtime cost)
# if TYPE_CHECKING:
#     from .base_file_helper import Base_FileHelper
#     from .local_file_helper import Local_FileHelper
#     from .file_helper_factory import FileHelperFactory, get_file_helper_factory
#     from .s3_file_helper import S3_FileHelper
#     from .s3_minio_file_helper import S3_MinIO_FileHelper
#     from .s3express_file_helper import S3Express_FileHelper
#     from .r2_file_helper import R2_FileHelper
#     from .gcs_file_helper import GCS_FileHelper
#     from .azure_file_helper import Azure_FileHelper
#     from .sftp_file_helper import SFTP_FileHelper
#     from .ssh_file_helper import SSH_FileHelper

# Lazy loading for optional storage backends (imported only when used)
__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=[],
    submod_attrs={
        'base_file_helper': ['Base_FileHelper'],
        'local_file_helper': ['Local_FileHelper'],
        'file_helper_factory': ['FileHelperFactory', 'get_file_helper_factory'],

        's3_file_helper': ['S3_FileHelper'],
        's3_minio_file_helper': ['S3_MinIO_FileHelper'],
        's3express_file_helper': ['S3Express_FileHelper'],
        'r2_file_helper': ['R2_FileHelper'],
        'gcs_file_helper': ['GCS_FileHelper'],
        'azure_file_helper': ['Azure_FileHelper'],
        'sftp_file_helper': ['SFTP_FileHelper'],
        'ssh_file_helper': ['SSH_FileHelper'],
    }
)

# Manually extend __all__ to include core exports
# __all__ = [
#     "Base_FileHelper",
#     "Local_FileHelper",
# ] + list(__all__)
