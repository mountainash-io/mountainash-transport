#utils/security.py

from typing import Optional, Dict, Any

from ..exceptions import StorageSecurityError

# class CredentialProtection:
#     """
#     Simple credential protection utilities for client-side storage configurations.
#     Focuses on protecting credentials in memory and configuration files.
#     """

#     def __init__(
#         self,
#         protection_key: Optional[Union[str, bytes]] = None,
#         key_file: Optional[str] = None
#     ):
#         self._key = self._init_protection_key(protection_key, key_file)
#         self._fernet = Fernet(self._key)

#     def _init_protection_key(
#         self,
#         protection_key: Optional[Union[str, bytes]],
#         key_file: Optional[str]
#     ) -> bytes:
#         """Initialize protection key"""
#         try:
#             if protection_key:
#                 if isinstance(protection_key, str):
#                     # Convert string key to proper format
#                     key_bytes = protection_key.encode()
#                     if len(key_bytes) < 32:
#                         key_bytes = key_bytes.ljust(32, b'0')
#                     return base64.urlsafe_b64encode(key_bytes[:32])
#                 return protection_key
#             elif key_file:
#                 return self._load_key_file(key_file)
#             else:
#                 # Generate a random key if none provided
#                 return Fernet.generate_key()
#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Failed to initialize protection key: {str(e)}",
#                 security_check="key_init"
#             )

#     def _load_key_file(self, key_file: str) -> bytes:
#         """Load protection key from file"""
#         try:
#             path = UPath(key_file).resolve()
#             if not path.exists():
#                 raise StorageSecurityError(
#                     f"Key file not found: {key_file}",
#                     security_check="key_file"
#                 )

#             # Validate path is within user space
#             if not str(path).startswith(str(UPath.home())):
#                 raise StorageSecurityError(
#                     "Key file must be in user directory",
#                     security_check="key_file"
#                 )

#             with open(path, 'rb') as f:
#                 key_data = f.read().strip()
#                 return base64.urlsafe_b64encode(key_data[:32])
#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Failed to load key file: {str(e)}",
#                 security_check="key_file"
#             )

#     def protect_value(self, value: str) -> str:
#         """Protect sensitive string value"""
#         try:
#             return self._fernet.encrypt(value.encode()).decode()
#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Value protection failed: {str(e)}",
#                 security_check="protect"
#             )

#     def unprotect_value(self, protected_value: str) -> str:
#         """Unprotect sensitive string value"""
#         try:
#             return self._fernet.decrypt(protected_value.encode()).decode()
#         except InvalidToken:
#             raise StorageSecurityError(
#                 "Invalid or corrupted protected value",
#                 security_check="unprotect"
#             )
#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Value unprotection failed: {str(e)}",
#                 security_check="unprotect"
#             )

class ConnectionValidator:
    """
    Simple connection security validator.
    Focuses on basic security checks for storage connections.
    """

    @staticmethod
    def validate_connection_params(
        params: Dict[str, Any],
        required_params: set,
        allowed_params: Optional[set] = None
    ) -> bool:
        """Validate connection parameters"""
        # Check required parameters
        if not all(param in params for param in required_params):
            missing = required_params - params.keys()
            raise StorageSecurityError(
                f"Missing required parameters: {missing}",
                security_check="params"
            )

        # Check for unexpected parameters if allowed list provided
        if allowed_params:
            unexpected = params.keys() - allowed_params
            if unexpected:
                raise StorageSecurityError(
                    f"Unexpected parameters: {unexpected}",
                    security_check="params"
                )

        return True

    @staticmethod
    def validate_endpoint(endpoint: str, allowed_schemes: set) -> bool:
        """Validate storage endpoint"""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(endpoint)

            # Validate scheme
            if parsed.scheme not in allowed_schemes:
                raise StorageSecurityError(
                    f"Invalid endpoint scheme. Allowed: {allowed_schemes}",
                    security_check="endpoint"
                )

            # Basic endpoint security checks
            if parsed.username or parsed.password:
                raise StorageSecurityError(
                    "Credentials in endpoint URL not allowed",
                    security_check="endpoint"
                )

            return True

        except Exception as e:
            if isinstance(e, StorageSecurityError):
                raise
            raise StorageSecurityError(
                f"Invalid endpoint: {str(e)}",
                security_check="endpoint"
            )

# class CredentialStore:
#     """
#     Simple credential store for temporary storage of connection credentials.
#     Focuses on secure handling of credentials in memory.
#     """

#     def __init__(self):
#         self._store: Dict[str, Dict[str, Any]] = {}
#         self._protection = CredentialProtection()

#     def store_credentials(
#         self,
#         store_id: str,
#         credentials: Dict[str, Any],
#         protect: bool = True
#     ) -> None:
#         """Store credentials temporarily"""
#         try:
#             if protect:
#                 protected_creds = {
#                     key: self._protection.protect_value(str(value))
#                     for key, value in credentials.items()
#                 }
#             else:
#                 protected_creds = credentials

#             self._store[store_id] = {
#                 'credentials': protected_creds,
#                 'timestamp': datetime.now().isoformat(),
#                 'protected': protect
#             }
#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Failed to store credentials: {str(e)}",
#                 security_check="credential_store"
#             )

#     def get_credentials(
#         self,
#         store_id: str,
#         unprotect: bool = True
#     ) -> Dict[str, Any]:
#         """Retrieve stored credentials"""
#         try:
#             stored = self._store.get(store_id)
#             if not stored:
#                 raise StorageSecurityError(
#                     f"Credentials not found: {store_id}",
#                     security_check="credential_retrieve"
#                 )

#             creds = stored['credentials']
#             if unprotect and stored.get('protected'):
#                 return {
#                     key: self._protection.unprotect_value(value)
#                     for key, value in creds.items()
#                 }
#             return creds

#         except Exception as e:
#             if isinstance(e, StorageSecurityError):
#                 raise
#             raise StorageSecurityError(
#                 f"Failed to retrieve credentials: {str(e)}",
#                 security_check="credential_retrieve"
#             )

#     def remove_credentials(self, store_id: str) -> None:
#         """Remove stored credentials"""
#         if store_id in self._store:
#             del self._store[store_id]

#     def clear_all(self) -> None:
#         """Clear all stored credentials"""
#         self._store.clear()

# class ConfigurationProtection:
#     """
#     Simple protection for configuration files.
#     Focuses on basic security for local configuration storage.
#     """

#     @staticmethod
#     def protect_config(
#         config: Dict[str, Any],
#         sensitive_keys: set
#     ) -> Dict[str, Any]:
#         """Protect sensitive configuration values"""
#         try:
#             protection = CredentialProtection()
#             protected = config.copy()

#             for key in sensitive_keys:
#                 if key in protected:
#                     if isinstance(protected[key], str):
#                         protected[key] = protection.protect_value(protected[key])

#             return protected

#         except Exception as e:
#             raise StorageSecurityError(
#                 f"Failed to protect configuration: {str(e)}",
#                 security_check="config_protection"
#             )

#     @staticmethod
#     def safe_save_config(
#         config: Dict[str, Any],
#         file_path: Union[str, UPath],
#         sensitive_keys: Optional[set] = None
#     ) -> None:
#         """Safely save configuration to file"""
#         try:
#             path = UPath(file_path).resolve()

#             # Ensure directory is secure
#             if not str(path).startswith(str(UPath.home())):
#                 raise StorageSecurityError(
#                     "Configuration file must be in user directory",
#                     security_check="config_save"
#                 )

#             # Protect sensitive values if specified
#             if sensitive_keys:
#                 config = ConfigurationProtection.protect_config(
#                     config,
#                     sensitive_keys
#                 )

#             # Safely write configuration
#             temp_path = path.with_suffix('.tmp')
#             with open(temp_path, 'w') as f:
#                 json.dump(config, f, indent=2)

#             # Atomic replace
#             os.replace(temp_path, path)

#         except Exception as e:
#             if isinstance(e, StorageSecurityError):
#                 raise
#             raise StorageSecurityError(
#                 f"Failed to save configuration: {str(e)}",
#                 security_check="config_save"
#             )
