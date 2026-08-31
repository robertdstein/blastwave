"""
Minimal projections for ZTF
"""

# pylint: disable=duplicate-code

ztf_alert_projection = {
    "objectId": 1,
    "candidate.distpsnr1": 1,
    "candidate.jd": 1,
    "candidate.fid": 1,
    "candidate.magpsf": 1,
    "candidate.sigmapsf": 1,
    "candidate.ra": 1,
    "candidate.dec": 1,
}

prefixes = ["prv_candidates", "fp_hists", "prv_nondetections"]
fields = [
    "jd",
    "magpsf",
    "sigmapsf",
    "diffmaglim",
    "ra",
    "dec",
    "band",
    "isdiffpos",
    "psfFlux",
    "psfFluxErr",
    "snr_psf",
]

ztf_aux_projection = {f"{prefix}.{field}": 1 for prefix in prefixes for field in fields}
ztf_aux_projection["aliases"] = 1
ztf_aux_projection["cross_matches"] = 1
