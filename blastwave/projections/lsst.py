"""
LSST alert projections
"""

# pylint: disable=duplicate-code

prefixes = ["prv_candidates", "fp_hists"]
fields = [
    "jd",
    "magpsf",
    "sigmapsf",
    "diffmaglim",
    "ra",
    "dec",
    "snr",
    "band",
    "isdiffpos",
    "psfFlux",
    "psfFluxErr",
    "reliability",
    "isDipole",
    "centroid_flag",
    "isNegative",
    "psfFlux_flag",
    "pixelFlags",
    "glint_trail",
]

lsst_aux_projection = {
    f"{prefix}.{field}": 1 for prefix in prefixes for field in fields
}
lsst_aux_projection["aliases"] = 1
