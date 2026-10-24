"""Lake AI v0 segmenter: water-index (optical) and backscatter (radar) thresholds.
This is the baseline column of the plan; a learned U-Net must beat it on the same lakes."""
import numpy as np
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape as to_shape
from shapely.ops import unary_union

# Sentinel-2 scene classification: 3 cloud shadow, 8/9 cloud, 10 thin cirrus.
SCL_BAD = (3, 8, 9, 10)
SWIR_CLOUD = 0.10  # B11 reflectance above which a cloud label is believed


def ndwi(green, nir):
    g, n = green.astype("float32"), nir.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        return (g - n) / (g + n)


def mndwi(green, swir):
    g, s = green.astype("float32"), swir.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        return (g - s) / (g + s)


def otsu(values, bins=256):
    """Otsu threshold of finite values."""
    v = values[np.isfinite(values)]
    if v.size < 10:
        raise ValueError("not enough valid pixels to threshold")
    hist, edges = np.histogram(v, bins=bins)
    mids = (edges[:-1] + edges[1:]) / 2
    w1 = np.cumsum(hist)
    w2 = w1[-1] - w1
    m1 = np.cumsum(hist * mids) / np.maximum(w1, 1)
    m2 = (np.sum(hist * mids) - np.cumsum(hist * mids)) / np.maximum(w2, 1)
    between = w1 * w2 * (m1 - m2) ** 2
    return float(mids[np.argmax(between)])


def reflectance(dn, offset=0):
    """Sentinel-2 L2A digital numbers to reflectance. Processing baseline 04.00+ (from Jan 2022) adds 1000."""
    return (dn.astype("float32") - offset) / 10000.0


def water_s2(green, nir, swir, scl=None, ndwi_t=0.2, nir_max=0.15):
    """Open water: NDWI above `ndwi_t` AND dark in near-infrared. MNDWI alone also lights up snow, which is
    bright in NIR; turbid glacial lakes stay dark there. Inputs are reflectances. Returns (mask, valid)."""
    # No-data is marked by NaN upstream. Clear dark water can read slightly below zero after the L2A offset,
    # so the sign of a reflectance says nothing about validity.
    valid = np.isfinite(green) & np.isfinite(nir) & np.isfinite(swir)
    if scl is not None:
        # Sen2Cor labels bright, silty glacial water as cloud. Real cloud is bright in SWIR; water is not,
        # so a cloud label only counts where SWIR agrees.
        valid &= ~(np.isin(scl, SCL_BAD) & (swir > SWIR_CLOUD))
    w = (ndwi(green, nir) > ndwi_t) & (nir < nir_max) & valid
    return w, valid


def water_s1(vv_db, threshold=None):
    """Calm water is dark in VV. Threshold by Otsu unless given; capped so bright slopes never count."""
    t = otsu(vv_db) if threshold is None else threshold
    t = min(t, -15.0)
    valid = np.isfinite(vv_db)
    return (vv_db < t) & valid, valid, t


def largest_component(mask, min_px=50):
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask, bool)
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    k = int(np.argmax(sizes)) + 1
    return (lab == k) if sizes[k - 1] >= min_px else np.zeros_like(mask, bool)


def component_at(mask, row, col):
    """The connected water body containing (row, col); empty if that pixel is not water."""
    if not (0 <= row < mask.shape[0] and 0 <= col < mask.shape[1]) or not mask[row, col]:
        return np.zeros_like(mask, bool)
    lab, _ = ndimage.label(mask)
    return lab == lab[row, col]


def component_overlapping(mask, ref, min_px=20):
    """The connected water body in `mask` that overlaps `ref` most (follows one lake across dates)."""
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask, bool)
    overlap = ndimage.sum(ref, lab, range(1, n + 1))
    k = int(np.argmax(overlap)) + 1
    comp = lab == k
    return comp if overlap[k - 1] > 0 and comp.sum() >= min_px else np.zeros_like(mask, bool)


def clean(mask, open_iter=1, close_iter=2):
    m = ndimage.binary_opening(mask, iterations=open_iter)
    m = ndimage.binary_closing(m, iterations=close_iter)
    return ndimage.binary_fill_holes(m)


def area_m2(mask, transform):
    return float(mask.sum()) * abs(transform.a * transform.e)


def outline(mask, transform):
    polys = [to_shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=transform) if v == 1]
    return unary_union(polys) if polys else None
