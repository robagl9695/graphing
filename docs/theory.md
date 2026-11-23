# Theory notes

Derivations behind the numbers the app computes. Each section names the code that
uses it. Citations are keys of `docs/references.bib`; the list at the end is in ACS
format. Entries marked pending have not yet been checked against the source.

## 1. Oscillator strength → molar absorptivity (UV-Vis)

Used by `core.constants.INTEGRATED_ABSORPTIVITY_PER_F` and
`core.transforms.OscillatorStrengthToAbsorptivity` (T3.4).

The oscillator strength f of a transition and the Napierian integrated absorption
cross-section per molecule are related by

    ∫ σ(ν̃) dν̃ = π rₑ f,

with rₑ = e²/(4πε₀ mₑ c²) the classical electron radius and ν̃ the wavenumber. Per mole
of absorbers this is N_A π rₑ f, a Napierian molar quantity in cm mol⁻¹ when rₑ is in
cm. The decadic molar absorptivity ε (L mol⁻¹ cm⁻¹) is the Napierian one divided by
ln 10, and 1 L = 1000 cm³, so

    ∫ ε(ν̃) dν̃ = π rₑ N_A f / (1000 ln 10)      [L mol⁻¹ cm⁻², ν̃ in cm⁻¹]

With rₑ = 2.8179403262 × 10⁻¹³ cm [codata2018] and N_A = 6.02214076 × 10²³ mol⁻¹
(exact, SI 2019):

    ∫ ε dν̃ = 2.315351 × 10⁸ · f,   that is   f = 4.31900 × 10⁻⁹ ∫ ε dν̃.

**Correction to qclab-utilities (D-20261122-09).** `qclab-utilities` uses
f = 4.31944 × 10⁻⁹ ∫ ε dν̃ (2.315115 × 10⁸), with no source. It is 1.02 × 10⁻⁴
relative below the value above. The app uses the CODATA value; the comparison test
with `absspectra` scales its output by the ratio (T3.4 AC3).

## 2. IR intensity (km/mol) → molar absorptivity

Used by `core.constants.INTEGRATED_ABSORPTIVITY_PER_KM_MOL` and
`core.transforms.IRIntensityToAbsorptivity` (T3.4), decision D-20261117-01.

ORCA and Turbomole report the IR intensity of a mode as an integrated absorption
coefficient A = ∫ κ dν̃ in km mol⁻¹, with κ the Napierian molar absorption coefficient
[iupac2023, §4.7.1; ORCA 6.0 manual §6.12]. Two changes give the decadic integrated
molar absorptivity:

- units: 1 km mol⁻¹ = 10⁵ cm mol⁻¹ = 100 L mol⁻¹ cm⁻² (1 L = 10³ cm³);
- base: decadic = Napierian / ln 10.

So

    ∫ ε(ν̃) dν̃ = (100 / ln 10) · A ≈ 43.429 · A      [L mol⁻¹ cm⁻², A in km mol⁻¹]

## 3. From a broadened curve to ε

Used by `core.evaluate` (T3.4, D-20261122-08).

A line of intensity h (f or km/mol) is broadened with a shape g of unit area in the
broadening variable u (cm⁻¹ or eV), so the curve y(u) = Σ hᵢ g(u − uᵢ) is a density per
unit of u. With K the constant of §1 or §2:

- u in cm⁻¹: ε = K · y;
- u in eV: g per cm⁻¹ is g per eV divided by the cm⁻¹ in one eV, so
  ε = K · y / 8065.54…

Showing the curve in nm keeps every x–y pair, so ε does not depend on the view. A
curve whose density is per nm is not defined: broadening is never done in nm (T3.2).

The conversion is linear, so applying it to the lines before broadening gives the
same curve. A stick on an ε axis shows the maximum its band would reach alone,

    ε_max,i = K · hᵢ · g(0),

which is the form of Rob's thesis: for a Gaussian written exp[−(ν̃/σ′)²],
g(0) = 1/(σ′√π), and K/√π = 1.306297 × 10⁸ L mol⁻¹ cm⁻² per unit f with the
constant of §1. This agrees with the thesis value 1.3062974 × 10⁸ to all its digits;
qclab's constant would give 1.306164 × 10⁸. With FWHM = 2√(ln 2)·σ′:
g(0) = 2√(ln 2 / π)/FWHM ≈ 0.9394/FWHM (Gaussian) and 2/(π·FWHM) ≈ 0.6366/FWHM
(Lorentzian).

## 4. Beer–Lambert

Used by `core.transforms.AbsorptivityToAbsorbance` and `AbsorbanceToAbsorptivity`
(T3.4). For a decadic absorbance A, path length b (cm) and amount concentration c
(mol L⁻¹) [iupac2023]:

    A = ε b c,      ε = A / (b c).

Both are linear, so the sticks of a theoretical layer follow the curve exactly. A → %T
then uses %T = 10^(2 − A), which is not linear and is applied to the broadened curve
(D-20261122-08).

## References

- (codata2018) Tiesinga, E.; Mohr, P. J.; Newell, D. B.; Taylor, B. N. CODATA
  Recommended Values of the Fundamental Physical Constants: 2018. *Rev. Mod. Phys.*
  **2021**, *93*, 025010. (pending)
- (iupac2023) Brett, C. M. A.; Frey, J. G.; et al., Comps. *Quantities, Units and
  Symbols in Physical Chemistry*, 4th ed., abridged version; IUPAC; Royal Society of
  Chemistry, 2023. (pending)
