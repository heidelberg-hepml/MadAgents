#########################################################################
## Compatibility helpers ###############################################
#########################################################################

def ensure_aiosqlite_is_alive() -> None:
    """Patch aiosqlite.Connection with is_alive if missing."""
    try:
        import aiosqlite

        if not hasattr(aiosqlite.Connection, "is_alive"):
            def _is_alive(self) -> bool:
                try:
                    return not getattr(self, "_closed", False)
                except Exception:
                    return True

            aiosqlite.Connection.is_alive = _is_alive
    except Exception:
        pass
