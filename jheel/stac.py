"""Reading windows of public Sentinel and Copernicus COGs from Microsoft Planetary Computer (no account)."""
from functools import lru_cache

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from .config import STAC_URL

GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_MAX_RETRY": "4",
            "GDAL_HTTP_RETRY_DELAY": "2", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff,.TIFF"}


@lru_cache(maxsize=1)
def catalog():
    return pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)


def search(collection, bbox, datetime=None, query=None, limit=500):
    return list(catalog().search(collections=[collection], bbox=list(bbox), datetime=datetime,
                                 query=query, max_items=limit).items())


def read_window(href, bbox_wgs84, res=None, ref=None, resampling=Resampling.bilinear):
    """Read the bbox from a COG. With `ref` (transform, shape, crs) the result is resampled onto that grid,
    so bands of different resolution line up pixel for pixel. Returns (array, transform, crs)."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        if ref is None:
            b = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
            win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
            scale = (res / abs(src.transform.a)) if res else 1.0
            shape = (max(1, int(round(win.height / scale))), max(1, int(round(win.width / scale))))
            arr = src.read(1, window=win, out_shape=shape, resampling=resampling, boundless=True)
            t = src.window_transform(win) * rasterio.Affine.scale(win.width / shape[1], win.height / shape[0])
            return arr, t, src.crs
        t, shape, crs = ref
        if crs != src.crs:
            raise ValueError("reference grid must share the source CRS")
        b = rasterio.transform.array_bounds(shape[0], shape[1], t)
        win = from_bounds(b[0], b[1], b[2], b[3], transform=src.transform)
        arr = src.read(1, window=win, out_shape=shape, resampling=resampling, boundless=True)
        return arr, t, crs


def to_db(linear):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(np.where(linear > 0, linear, np.nan))
