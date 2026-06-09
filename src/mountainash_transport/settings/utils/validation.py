# #utils/validation.py

# from typing import Optional, Dict, Any, Set, Callable
# from upath import UPath
# import re
# import os
# from urllib.parse import urlparse
# import ipaddress

# from mountainash_auth_client import StorageValidationError  # TBD

# class StorageValidator:
#     """Storage configuration validation utilities"""

#     @staticmethod
#     def validate_path(
#         path: str,
#         must_exist: bool = True,
#         writable: bool = False,
#         allowed_types: Optional[Set[str]] = None
#     ) -> bool:
#         """
#         Validate storage path
        
#         Args:
#             path: Path to validate
#             must_exist: Whether path must exist
#             writable: Whether path must be writable
#             allowed_types: Set of allowed path types ('file', 'dir')
#         """
#         try:
#             path_obj = UPath(path).resolve()
            
#             if must_exist and not path_obj.exists():
#                 raise StorageValidationError(
#                     f"Path does not exist: {path}",
#                     validation_type="path"
#                 )
                
#             if writable:
#                 if path_obj.exists() and not os.access(path_obj, os.W_OK):
#                     raise StorageValidationError(
#                         f"Path not writable: {path}",
#                         validation_type="path"
#                     )
#                 parent = path_obj.parent
#                 if not os.access(parent, os.W_OK):
#                     raise StorageValidationError(
#                         f"Parent directory not writable: {parent}",
#                         validation_type="path"
#                     )
                    
#             if allowed_types:
#                 if path_obj.exists():
#                     path_type = 'dir' if path_obj.is_dir() else 'file'
#                     if path_type not in allowed_types:
#                         raise StorageValidationError(
#                             f"Invalid path type. Expected one of: {allowed_types}",
#                             validation_type="path"
#                         )
                        
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Path validation failed: {str(e)}",
#                 validation_type="path"
#             )

#     @staticmethod
#     def validate_url(
#         url: str,
#         allowed_schemes: Optional[Set[str]] = None,
#         required_parts: Optional[Set[str]] = None,
#         allowed_hosts: Optional[Set[str]] = None,
#         max_port: int = 65535
#     ) -> bool:
#         """
#         Validate storage URL
        
#         Args:
#             url: URL to validate
#             allowed_schemes: Set of allowed URL schemes
#             required_parts: Set of required URL parts
#             allowed_hosts: Set of allowed hostnames/IPs
#             max_port: Maximum allowed port number
#         """
#         try:
#             parsed = urlparse(url)
            
#             # Validate scheme
#             if allowed_schemes and parsed.scheme not in allowed_schemes:
#                 raise StorageValidationError(
#                     f"Invalid URL scheme. Allowed: {allowed_schemes}",
#                     validation_type="url"
#                 )
                
#             # Validate required parts
#             if required_parts:
#                 for part in required_parts:
#                     if not getattr(parsed, part, None):
#                         raise StorageValidationError(
#                             f"Missing required URL part: {part}",
#                             validation_type="url"
#                         )
            
#             # Validate hostname
#             if allowed_hosts and parsed.hostname:
#                 if parsed.hostname not in allowed_hosts:
#                     try:
#                         # Check if IP is in allowed networks
#                         ip = ipaddress.ip_address(parsed.hostname)
#                         if not any(ip in ipaddress.ip_network(host) for host in allowed_hosts):
#                             raise StorageValidationError(
#                                 f"Host not allowed: {parsed.hostname}",
#                                 validation_type="url"
#                             )
#                     except ValueError:
#                         raise StorageValidationError(
#                             f"Host not allowed: {parsed.hostname}",
#                             validation_type="url"
#                         )
            
#             # Validate port
#             if parsed.port:
#                 if not (1 <= parsed.port <= max_port):
#                     raise StorageValidationError(
#                         f"Invalid port number: {parsed.port}",
#                         validation_type="url"
#                     )
                        
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"URL validation failed: {str(e)}",
#                 validation_type="url"
#             )

#     @staticmethod
#     def validate_permissions(
#         permissions: Set[str],
#         required_permissions: Set[str],
#         optional_permissions: Optional[Set[str]] = None
#     ) -> bool:
#         """
#         Validate storage permissions
        
#         Args:
#             permissions: Set of permissions to validate
#             required_permissions: Set of required permissions
#             optional_permissions: Set of optional permissions
#         """
#         try:
#             # Check required permissions
#             missing = required_permissions - permissions
#             if missing:
#                 raise StorageValidationError(
#                     f"Missing required permissions: {missing}",
#                     validation_type="permissions"
#                 )
                
#             # Check for unexpected permissions
#             if optional_permissions is not None:
#                 allowed = required_permissions | optional_permissions
#                 unexpected = permissions - allowed
#                 if unexpected:
#                     raise StorageValidationError(
#                         f"Unexpected permissions: {unexpected}",
#                         validation_type="permissions"
#                     )
                    
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Permission validation failed: {str(e)}",
#                 validation_type="permissions"
#             )

#     @staticmethod
#     def validate_credentials(
#         credentials: Dict[str, Any],
#         required_fields: Set[str],
#         validators: Optional[Dict[str, Callable]] = None,
#         max_length: Optional[int] = None
#     ) -> bool:
#         """
#         Validate storage credentials
        
#         Args:
#             credentials: Dictionary of credentials to validate
#             required_fields: Set of required credential fields
#             validators: Dictionary of field validators
#             max_length: Maximum length for credential values
#         """
#         try:
#             # Check required fields
#             missing = required_fields - credentials.keys()
#             if missing:
#                 raise StorageValidationError(
#                     f"Missing required credential fields: {missing}",
#                     validation_type="credentials"
#                 )
                
#             # Check field lengths
#             if max_length:
#                 for field, value in credentials.items():
#                     if isinstance(value, str) and len(value) > max_length:
#                         raise StorageValidationError(
#                             f"Credential value too long for field: {field}",
#                             validation_type="credentials"
#                         )
                
#             # Apply field validators if provided
#             if validators:
#                 for field, validator in validators.items():
#                     if field in credentials:
#                         try:
#                             if not validator(credentials[field]):
#                                 raise StorageValidationError(
#                                     f"Invalid credential value for field: {field}",
#                                     validation_type="credentials"
#                                 )
#                         except Exception as e:
#                             raise StorageValidationError(
#                                 f"Credential validation failed for {field}: {str(e)}",
#                                 validation_type="credentials"
#                             )
                            
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Credential validation failed: {str(e)}",
#                 validation_type="credentials"
#             )

#     @staticmethod
#     def validate_connection_params(
#         params: Dict[str, Any],
#         required_params: Set[str],
#         optional_params: Optional[Set[str]] = None,
#         validators: Optional[Dict[str, Callable]] = None,
#         param_constraints: Optional[Dict[str, Dict[str, Any]]] = None
#     ) -> bool:
#         """
#         Validate connection parameters
        
#         Args:
#             params: Dictionary of parameters to validate
#             required_params: Set of required parameters
#             optional_params: Set of optional parameters
#             validators: Dictionary of parameter validators
#             param_constraints: Dictionary of parameter constraints
#         """
#         try:
#             # Check required parameters
#             missing = required_params - params.keys()
#             if missing:
#                 raise StorageValidationError(
#                     f"Missing required parameters: {missing}",
#                     validation_type="connection_params"
#                 )
                
#             # Check for unexpected parameters
#             if optional_params is not None:
#                 allowed = required_params | optional_params
#                 unexpected = params.keys() - allowed
#                 if unexpected:
#                     raise StorageValidationError(
#                         f"Unexpected parameters: {unexpected}",
#                         validation_type="connection_params"
#                     )
                    
#             # Apply constraints if provided
#             if param_constraints:
#                 for param, value in params.items():
#                     if param in param_constraints:
#                         constraints = param_constraints[param]
                        
#                         # Check type constraint
#                         if 'type' in constraints:
#                             if not isinstance(value, constraints['type']):
#                                 raise StorageValidationError(
#                                     f"Invalid type for parameter {param}. Expected {constraints['type']}",
#                                     validation_type="connection_params"
#                                 )
                                
#                         # Check range constraint
#                         if 'range' in constraints:
#                             min_val, max_val = constraints['range']
#                             if not (min_val <= value <= max_val):
#                                 raise StorageValidationError(
#                                     f"Value out of range for parameter {param}. Expected {min_val}-{max_val}",
#                                     validation_type="connection_params"
#                                 )
                                
#                         # Check pattern constraint
#                         if 'pattern' in constraints and isinstance(value, str):
#                             if not re.match(constraints['pattern'], value):
#                                 raise StorageValidationError(
#                                     f"Invalid format for parameter {param}",
#                                     validation_type="connection_params"
#                                 )
                                
#                         # Check enum constraint
#                         if 'enum' in constraints:
#                             if value not in constraints['enum']:
#                                 raise StorageValidationError(
#                                     f"Invalid value for parameter {param}. Allowed: {constraints['enum']}",
#                                     validation_type="connection_params"
#                                 )
                
#             # Apply validators if provided
#             if validators:
#                 for param, validator in validators.items():
#                     if param in params:
#                         try:
#                             if not validator(params[param]):
#                                 raise StorageValidationError(
#                                     f"Validation failed for parameter: {param}",
#                                     validation_type="connection_params"
#                                 )
#                         except Exception as e:
#                             raise StorageValidationError(
#                                 f"Validation error for parameter {param}: {str(e)}",
#                                 validation_type="connection_params"
#                             )
                            
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Parameter validation failed: {str(e)}",
#                 validation_type="connection_params"
#             )

#     @staticmethod
#     def validate_timeout_settings(
#         connect_timeout: Optional[float] = None,
#         read_timeout: Optional[float] = None,
#         write_timeout: Optional[float] = None,
#         max_timeout: float = 300.0
#     ) -> bool:
#         """
#         Validate timeout settings
        
#         Args:
#             connect_timeout: Connection timeout in seconds
#             read_timeout: Read timeout in seconds
#             write_timeout: Write timeout in seconds
#             max_timeout: Maximum allowed timeout value
#         """
#         try:
#             timeouts = {
#                 'connect': connect_timeout,
#                 'read': read_timeout,
#                 'write': write_timeout
#             }
            
#             for name, timeout in timeouts.items():
#                 if timeout is not None:
#                     if timeout <= 0:
#                         raise StorageValidationError(
#                             f"Invalid {name} timeout: must be positive",
#                             validation_type="timeout"
#                         )
#                     if timeout > max_timeout:
#                         raise StorageValidationError(
#                             f"Invalid {name} timeout: exceeds maximum {max_timeout}s",
#                             validation_type="timeout"
#                         )
                        
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Timeout validation failed: {str(e)}",
#                 validation_type="timeout"
#             )

#     @staticmethod
#     def validate_retry_settings(
#         max_retries: int,
#         retry_delay: float,
#         max_delay: float,
#         retry_codes: Optional[Set[int]] = None
#     ) -> bool:
#         """
#         Validate retry settings
        
#         Args:
#             max_retries: Maximum number of retries
#             retry_delay: Initial retry delay in seconds
#             max_delay: Maximum retry delay in seconds
#             retry_codes: Set of retryable error codes
#         """
#         try:
#             if max_retries < 0:
#                 raise StorageValidationError(
#                     "Invalid max_retries: must be non-negative",
#                     validation_type="retry"
#                 )
                
#             if retry_delay <= 0:
#                 raise StorageValidationError(
#                     "Invalid retry_delay: must be positive",
#                     validation_type="retry"
#                 )
                
#             if max_delay < retry_delay:
#                 raise StorageValidationError(
#                     "Invalid max_delay: must be greater than retry_delay",
#                     validation_type="retry"
#                 )
                
#             if retry_codes:
#                 if not all(isinstance(code, int) and 100 <= code <= 599 for code in retry_codes):
#                     raise StorageValidationError(
#                         "Invalid retry_codes: must be HTTP status codes (100-599)",
#                         validation_type="retry"
#                     )
                    
#             return True
            
#         except Exception as e:
#             if isinstance(e, StorageValidationError):
#                 raise
#             raise StorageValidationError(
#                 f"Retry validation failed: {str(e)}",
#                 validation_type="retry"
#             )