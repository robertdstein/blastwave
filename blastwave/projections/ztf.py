"""
Minimal projections for ZTF
"""

ztf_photometry_projection: dict[str, int] = {
    "candidate.jd": 1,
    "candidate.fid": 1,
    "candidate.magpsf": 1,
    "candidate.sigmapsf": 1,
    "candidate.ra": 1,
    "candidate.dec": 1,
}
