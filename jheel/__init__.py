# rasterio's Linux wheel links the system libexpat, which Vercel's Python runtime lacks. The Vercel bundle ships
# one in lib/ (see scripts/build_vercel_api.sh); load it before anything imports rasterio. Absent everywhere else.
from pathlib import Path as _Path

_EXPAT = _Path(__file__).resolve().parent.parent / "lib" / "libexpat.so.1"
if _EXPAT.exists():
    import ctypes as _ctypes
    _ctypes.CDLL(str(_EXPAT), mode=_ctypes.RTLD_GLOBAL)
