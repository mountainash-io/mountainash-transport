from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable


@runtime_checkable
class StoragePresignProtocol(Protocol):
    """Protocol for handing out time-limited URLs that read or write one object without credentials.

    Implemented only by stores that sign URLs (the S3 family). A URL signed with
    temporary credentials stops working when they expire, whatever ``expires_in`` says.
    """

    def presign(
        self, path: str, *, method: Literal["GET", "PUT"] = "GET",
        expires_in: int = 3600, content_type: str | None = None,
    ) -> str:
        """Return a URL that allows *method* on *path* for *expires_in* seconds.

        ``content_type`` (PUT only) is signed into the URL, so the uploader must
        send exactly that ``Content-Type``. Invalid arguments raise ``ValueError``
        before anything is signed.
        """
        ...
