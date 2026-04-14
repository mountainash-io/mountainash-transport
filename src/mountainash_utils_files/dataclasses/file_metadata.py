from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class FileMetadata(BaseModel):
    """Standardized file metadata model across different storage systems."""
    filename: str = Field(..., description="Name of the file without path")
    directory: str = Field(..., description="Directory path without filename")
    full_path: str = Field(..., description="Complete path including filename")
    size: int = Field(0, description="File size in bytes")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    etag: str = Field("", description="Entity tag identifier")
    storage_class: str = Field("", description="Storage class information")
    checksum: List[str] = Field(default_factory=list, description="Checksum algorithms used")
    source: str = Field(..., description="Source system (s3, local, etc.)")


    class Config:
        frozen = True  # Makes instances immutable
