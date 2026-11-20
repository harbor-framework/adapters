# Plasmon-enhanced photochemical decomposition of methylene blue on Ag nanocubes at 785 nm vs 532 nm

## 1. Physical model

For a molecule adsorbed on a plasmonic Ag nanocube, the photochemistry is driven by **charge (hot-carrier) excitation** from the metal into the adsorbate, and the probability of that event scales with the **local** photon flux at the molecule, not with the incident flux.

Two steps are therefore needed:

1. Convert the **electromagnetic enhancement factor** $\Sigma$ into the **field enhancement factor** $\eta = \Sigma^{1/2}$, and then into an **effective photon intensity** $I_{\text{eff}} = I_{\text{photon}}\,\eta^{2}$ seen by the molecule.
2. Multiply $I_{\text{eff}}$ by the **charge-excitation cross-section** $\sigma$ to obtain the rate of charge-excitation events per molecule, and then scale by the **intrinsic (unenhanced) decomposition rate** of MB at that wavelength, which carries the wavelength-dependent quantum efficiency of the chemical step.

Since photon-induced heating is negligible (assumption 4), the whole rate difference between 785 nm and 532 nm comes from (i) the charge-excitation cross-section and (ii) the intrinsic photochemical efficiency at each wavelength.

## 2. Field (amplitude) enhancement from the electromagnetic enhancement factor

$$\eta = \Sigma^{1/2}$$

$$\eta = \left(4 \times 10^{4}\right)^{1/2} = \mathbf{200}$$

This value is the same at both wavelengths (assumption 1): the 75 nm Ag nanocube on Si supports broad plasmon modes covering both 532 nm and 785 nm, so $\Sigma = 4\times10^{4}$ and $\eta = 200$ at each wavelength.

## 3. Effective photon intensity

The effective (plasmon-amplified) photon intensity experienced by an MB molecule in the near field is

$$\boxed{I_{\text{eff}} = I_{\text{photon}} \times \eta^{2}}$$

with $\eta^{2} = (200)^{2} = 4\times 10^{4}$.

**At 785 nm:**

$$I_{\text{eff, 785}} = 2.0\times10^{20} \times (200)^{2} = 2.0\times10^{20} \times 4\times10^{4} = \mathbf{8.0\times10^{24}\ \text{photons·cm}^{-2}\text{s}^{-1}}$$

**At 532 nm:**

$$I_{\text{eff, 532}} = 2.0\times10^{20} \times (200)^{2} = 2.0\times10^{20} \times 4\times10^{4} = \mathbf{8.0\times10^{24}\ \text{photons·cm}^{-2}\text{s}^{-1}}$$

The two effective intensities are identical because both lasers are specified at the same incident intensity ($2.0\times10^{20}$ photons cm$^{-2}$ s$^{-1}$) and the same electromagnetic enhancement ($\Sigma = 4\times10^{4}$, $\eta = 200$).

## 4. Charge-excitation rates

The number of charge-excitation events per second per molecule is the effective photon flux times the charge-excitation cross-section:

$$\text{Rate}_{\text{exc}} = I_{\text{eff}} \times \sigma$$

**At 785 nm** ($\sigma_{785} = 3\times10^{-18}\ \text{cm}^2$):

$$\text{Rate}_{\text{exc, 785}} = I_{\text{eff, 785}} \times \sigma_{785} = 8.0\times10^{24} \times 3\times10^{-18} = \mathbf{2.4\times10^{7}\ \text{electrons·s}^{-1}}$$

**At 532 nm** ($\sigma_{532} = 1\times10^{-18}\ \text{cm}^2$):

$$\text{Rate}_{\text{exc, 532}} = I_{\text{eff, 532}} \times \sigma_{532} = 8.0\times10^{24} \times 1\times10^{-18} = \mathbf{8.0\times10^{6}\ \text{electrons·s}^{-1}}$$

The 785 nm excitation rate is three times larger, exactly tracking the three-fold larger charge-excitation cross-section at the near-IR plasmon resonance.

## 5. Photochemical decomposition rates

The decomposition rate is obtained by scaling the charge-excitation rate by the intrinsic (unenhanced) decomposition rate at that wavelength, which encodes the wavelength-dependent quantum efficiency of converting an excited charge into a chemical (MB bond-breaking) event:

$$\text{Decomp Rate} = \text{Rate}_{\text{exc}} \times \text{Initial Rate}$$

**At 785 nm** (initial rate $= 0.1$ molecules/s):

$$\text{Decomp Rate}_{785} = \text{Rate}_{\text{exc, 785}} \times \text{Initial Rate}_{785} = 2.4\times10^{7} \times 0.1 = \mathbf{2.4\times10^{6}\ \text{molecules·s}^{-1}}$$

**At 532 nm** (initial rate $= 0.02$ molecules/s):

$$\text{Decomp Rate}_{532} = \text{Rate}_{\text{exc, 532}} \times \text{Initial Rate}_{532} = 8.0\times10^{6} \times 0.02 = \mathbf{1.6\times10^{5}\ \text{molecules·s}^{-1}}$$

## 6. Comparison of the two wavelengths

The formula for comparing the rates is

$$\text{Ratio} = \frac{\text{Decomp Rate}_{785}}{\text{Decomp Rate}_{532}}$$

$$\text{Ratio} = \frac{2.4\times10^{6}}{1.6\times10^{5}} = \mathbf{15}$$

## 7. Interpretation

- The electromagnetic contribution is **wavelength-independent here**: $\Sigma = 4\times10^4$, $\eta = 200$, and $I_{\text{eff}} = 8.0\times10^{24}$ photons cm$^{-2}$ s$^{-1}$ at both 532 nm and 785 nm, so the near-field amplification alone cannot explain any difference.
- The entire 15-fold advantage of 785 nm comes from the **chemistry of charge transfer**: a factor of $3\times$ from the larger charge-excitation cross-section ($3\times10^{-18}$ vs $1\times10^{-18}$ cm$^2$) and a factor of $5\times$ from the higher intrinsic photochemical efficiency at 785 nm (0.1 vs 0.02 molecules/s), giving $3 \times 5 = 15$.
- Physically, the 785 nm plasmon of the 75 nm Ag nanocube on the high-index Si substrate produces hot carriers whose energies and lifetimes are better matched to the Ag→MB charge-transfer (LUMO) manifold, so a larger fraction of the absorbed near-IR photons generates reactive electrons that are injected into MB. At 532 nm the charge-excitation channel is less efficient (smaller cross-section and lower intrinsic quantum efficiency), so fewer excitations end in MB decomposition.
- With heating neglected, the result is a purely **non-thermal, charge-transfer-driven** plasmonic photochemistry, and the predicted decomposition is an order of magnitude faster under near-IR (785 nm) than under visible (532 nm) illumination at equal photon flux.

## Final answer

| Quantity | 785 nm | 532 nm |
|---|---|---|
| $\eta = \Sigma^{1/2}$ | 200 | 200 |
| $I_{\text{eff}} = I_{\text{photon}}\eta^2$ | $8.0\times10^{24}$ cm$^{-2}$s$^{-1}$ | $8.0\times10^{24}$ cm$^{-2}$s$^{-1}$ |
| $\sigma$ | $3\times10^{-18}$ cm$^2$ | $1\times10^{-18}$ cm$^2$ |
| $\text{Rate}_{\text{exc}} = I_{\text{eff}}\sigma$ | $2.4\times10^{7}$ e$^-$/s | $8.0\times10^{6}$ e$^-$/s |
| Initial (unenhanced) rate | 0.1 molecules/s | 0.02 molecules/s |
| **Decomposition rate** | $\mathbf{2.4\times10^{6}}$ molecules/s | $\mathbf{1.6\times10^{5}}$ molecules/s |

$$\frac{\text{Decomp Rate}_{785}}{\text{Decomp Rate}_{532}} = \frac{2.4\times10^{6}}{1.6\times10^{5}} = \mathbf{15}$$

MB decomposition at 785 nm is **15 times faster** than at 532 nm under identical photon intensity.
