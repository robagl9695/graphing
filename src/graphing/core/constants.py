# SPDX-License-Identifier: GPL-3.0-or-later
"""Physical constants and conversion factors, each with its source."""

import math

# SI 2019 redefinition: these three values are exact by definition.
# Source: BIPM, "The International System of Units (SI)", 9th ed., 2019.
PLANCK_J_S: float = 6.62607015e-34
SPEED_OF_LIGHT_M_S: float = 299792458.0
ELEMENTARY_CHARGE_C: float = 1.602176634e-19

# E[eV] = HC_EV_NM / wavelength[nm]. Derived: h * c / e, converted from m to nm.
HC_EV_NM: float = PLANCK_J_S * SPEED_OF_LIGHT_M_S / ELEMENTARY_CHARGE_C * 1e9

# wavenumber[cm^-1] = EV_TO_CM1 * E[eV]. Derived: 1e7 nm/cm divided by hc in eV nm.
EV_TO_CM1: float = 1e7 / HC_EV_NM

# wavenumber[cm^-1] = NM_TO_CM1 / wavelength[nm]. Exact: 1 cm = 1e7 nm.
NM_TO_CM1: float = 1e7

# Avogadro constant, exact by definition. Source: BIPM SI Brochure, 9th ed., 2019.
AVOGADRO_PER_MOL: float = 6.02214076e23

# Classical electron radius r_e = 2.8179403262e-15 m, here in cm.
# Source: [codata2018].
CLASSICAL_ELECTRON_RADIUS_CM: float = 2.8179403262e-13

# Integrated decadic molar absorptivity per unit oscillator strength, in
# L mol^-1 cm^-2 with the wavenumber in cm^-1: integral(eps d nu) = this * f.
# Derived: pi r_e N_A / (1000 ln 10); the 1000 turns cm^3 into L and ln 10 turns the
# Napierian absorption coefficient into the decadic one (docs/theory.md §1).
# qclab-utilities used 2.315115e8 (f = 4.31944e-9 * integral), with no source; that
# value is 1.02e-4 relative below this one (D-20261122-09).
INTEGRATED_ABSORPTIVITY_PER_F: float = (
    math.pi
    * CLASSICAL_ELECTRON_RADIUS_CM
    * AVOGADRO_PER_MOL
    / (1000.0 * math.log(10.0))
)

# Integrated decadic molar absorptivity per km mol^-1 of program IR intensity, in
# L mol^-1 cm^-2: integral(eps d nu) = (100 / ln 10) * A. 1 km mol^-1 = 100 L mol^-1
# cm^-2; program intensities are Napierian (D-20261117-01). Sources: [iupac2023]
# section 4.7.1; ORCA 6.0 manual section 6.12 (docs/theory.md §2).
INTEGRATED_ABSORPTIVITY_PER_KM_MOL: float = 100.0 / math.log(10.0)
