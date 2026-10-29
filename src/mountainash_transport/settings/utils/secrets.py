import typing as t

def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)
