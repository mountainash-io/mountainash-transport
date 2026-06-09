#exceptions.py

from typing import Optional, Any, Dict, List

class StorageAuthError(Exception):
    """Base exception for all storage authentication errors"""
    def __init__(self, message: str, provider: Optional[str] = None):
        self.provider = provider
        super().__init__(f"[{provider or 'unknown'}] {message}")

class StorageConfigError(StorageAuthError):
    """Configuration error in storage settings"""
    def __init__(self, message: str, provider: Optional[str] = None, setting: Optional[str] = None):
        self.setting = setting
        super().__init__(
            f"Configuration error - {message}" + (f" (setting: {setting})" if setting else ""),
            provider
        )

class StorageConnectionError(StorageAuthError):
    """Error establishing storage connection"""
    def __init__(self, message: str, provider: Optional[str] = None, endpoint: Optional[str] = None):
        self.endpoint = endpoint
        super().__init__(
            f"Connection error - {message}" + (f" (endpoint: {endpoint})" if endpoint else ""),
            provider
        )

class StorageValidationError(StorageAuthError):
    """Validation error in storage settings"""
    def __init__(self, message: str, provider: Optional[str] = None, validation_type: Optional[str] = None):
        self.validation_type = validation_type
        super().__init__(
            f"Validation error - {message}" + (f" (type: {validation_type})" if validation_type else ""),
            provider
        )

class StorageSecurityError(StorageAuthError):
    """Security-related error in storage"""
    def __init__(self, message: str, provider: Optional[str] = None, security_check: Optional[str] = None):
        self.security_check = security_check
        super().__init__(
            f"Security error - {message}" + (f" (check: {security_check})" if security_check else ""),
            provider
        )

class StoragePermissionError(StorageAuthError):
    """Permission-related error in storage"""
    def __init__(self, message: str, provider: Optional[str] = None, permission: Optional[str] = None):
        self.permission = permission
        super().__init__(
            f"Permission error - {message}" + (f" (permission: {permission})" if permission else ""),
            provider
        )

class StorageEncryptionError(StorageAuthError):
    """Encryption-related error in storage"""
    def __init__(self, message: str, provider: Optional[str] = None, operation: Optional[str] = None):
        self.operation = operation
        super().__init__(
            f"Encryption error - {message}" + (f" (operation: {operation})" if operation else ""),
            provider
        )

class StorageTimeoutError(StorageAuthError):
    """Timeout error in storage operations"""
    def __init__(self, message: str, provider: Optional[str] = None, operation: Optional[str] = None):
        self.operation = operation
        super().__init__(
            f"Timeout error - {message}" + (f" (operation: {operation})" if operation else ""),
            provider
        )

class StorageQuotaError(StorageAuthError):
    """Quota-related error in storage"""
    def __init__(self, message: str, provider: Optional[str] = None, quota_type: Optional[str] = None, current: Optional[int] = None, limit: Optional[int] = None):
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        quota_info = ""
        if quota_type:
            quota_info += f" (type: {quota_type}"
            if current is not None and limit is not None:
                quota_info += f", usage: {current}/{limit})"
            else:
                quota_info += ")"
        super().__init__(f"Quota error - {message}{quota_info}", provider)

class StorageRetryError(StorageAuthError):
    """Error in retry operations"""
    def __init__(self, message: str, provider: Optional[str] = None, attempt: Optional[int] = None, max_attempts: Optional[int] = None):
        self.attempt = attempt
        self.max_attempts = max_attempts
        retry_info = ""
        if attempt is not None and max_attempts is not None:
            retry_info = f" (attempt: {attempt}/{max_attempts})"
        super().__init__(f"Retry error - {message}{retry_info}", provider)

class StoragePoolError(StorageAuthError):
    """Connection pool related error"""
    def __init__(self, message: str, provider: Optional[str] = None, pool_status: Optional[Dict[str, Any]] = None):
        self.pool_status = pool_status or {}
        pool_info = ""
        if pool_status:
            pool_info = f" (pool: {pool_status})"
        super().__init__(f"Pool error - {message}{pool_info}", provider)

class StorageOperationError(StorageAuthError):
    """General storage operation error"""
    def __init__(self, message: str, provider: Optional[str] = None, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.operation = operation
        self.details = details or {}
        op_info = ""
        if operation:
            op_info = f" (operation: {operation})"
        super().__init__(f"Operation error - {message}{op_info}", provider)

class StorageVersionError(StorageAuthError):
    """Version-related storage error"""
    def __init__(self, message: str, provider: Optional[str] = None, current_version: Optional[str] = None, required_version: Optional[str] = None):
        self.current_version = current_version
        self.required_version = required_version
        version_info = ""
        if current_version and required_version:
            version_info = f" (current: {current_version}, required: {required_version})"
        super().__init__(f"Version error - {message}{version_info}", provider)

class StorageStateError(StorageAuthError):
    """State-related storage error"""
    def __init__(self, message: str, provider: Optional[str] = None, current_state: Optional[str] = None, expected_state: Optional[str] = None):
        self.current_state = current_state
        self.expected_state = expected_state
        state_info = ""
        if current_state and expected_state:
            state_info = f" (current: {current_state}, expected: {expected_state})"
        super().__init__(f"State error - {message}{state_info}", provider)

class StorageFeatureError(StorageAuthError):
    """Feature-related storage error"""
    def __init__(self, message: str, provider: Optional[str] = None, feature: Optional[str] = None, supported_features: Optional[List[str]] = None):
        self.feature = feature
        self.supported_features = supported_features or []
        feature_info = ""
        if feature:
            feature_info = f" (feature: {feature}"
            if supported_features:
                feature_info += f", supported: {supported_features})"
            else:
                feature_info += ")"
        super().__init__(f"Feature error - {message}{feature_info}", provider)

class StorageCompatibilityError(StorageAuthError):
    """Compatibility-related storage error"""
    def __init__(self, message: str, provider: Optional[str] = None, component: Optional[str] = None, requirements: Optional[Dict[str, str]] = None):
        self.component = component
        self.requirements = requirements or {}
        compat_info = ""
        if component:
            compat_info = f" (component: {component}"
            if requirements:
                compat_info += f", requirements: {requirements})"
            else:
                compat_info += ")"
        super().__init__(f"Compatibility error - {message}{compat_info}", provider)

class StorageMigrationError(StorageAuthError):
    """Migration-related storage error"""
    def __init__(self, message: str, provider: Optional[str] = None, source_version: Optional[str] = None, target_version: Optional[str] = None, stage: Optional[str] = None):
        self.source_version = source_version
        self.target_version = target_version
        self.stage = stage
        migration_info = ""
        if source_version and target_version:
            migration_info = f" (from: {source_version}, to: {target_version}"
            if stage:
                migration_info += f", stage: {stage})"
            else:
                migration_info += ")"
        super().__init__(f"Migration error - {message}{migration_info}", provider)