# Choosing the optimal label-free method for measuring protein heterodimer binding affinities in three scenarios

## 0. The quantity being measured, and the common framework

For a heterodimer formed from partners A and B,

$$\text{A} + \text{B} \rightleftharpoons \text{AB}, \qquad K_D = \frac{[\text{A}][\text{B}]}{[\text{AB}]} = \frac{k_{\text{off}}}{k_{\text{on}}}$$

Two experimental routes give $K_D$:

* **Equilibrium (thermodynamic) route** — measure the bound fraction as a function of one partner's concentration and fit a 1:1 Langmuir isotherm,
 $$\theta = \frac{[\text{AB}]}{[\text{A}]_{\text{tot}}} = \frac{[\text{B}]}{K_D + [\text{B}]}\;,$$
 or, when the ligand is not in large excess, the quadratic (tight-binding) solution
 $$[\text{AB}] = \tfrac{1}{2}\Big( [\text{A}]_t + [\text{B}]_t + K_D - \sqrt{([\text{A}]_t+[\text{B}]_t+K_D)^2 - 4[\text{A}]_t[\text{B}]_t} \Big).$$
* **Kinetic route** — follow association and dissociation in real time, fit $k_{\text{on}}$ and $k_{\text{off}}$ from
 $$\frac{d[\text{AB}]}{dt} = k_{\text{on}}[\text{A}][\text{B}] - k_{\text{off}}[\text{AB}], \qquad R(t)_{\text{assoc}} = R_{\text{eq}}\big(1-e^{-(k_{\text{on}}C + k_{\text{off}})t}\big),\quad R(t)_{\text{dissoc}} = R_0 e^{-k_{\text{off}}t},$$
 and compute $K_D = k_{\text{off}}/k_{\text{on}}$.

All three methods below are **label-free** — no fluorophore, no biotinylation chemistry, no fusion tag perturbing the interface — which is what allows measurement **as close to native conditions as possible**, the stated priority. A different method is selected for each scenario, matched to the limiting constraint in that scenario (affinity regime; sample matrix/solvent; mechanical noise).

| Scenario | Limiting constraint | **Method chosen** | Physical observable |
|---|---|---|---|
| 1. Sub-µM affinities | Must work at low concentration, in solution, without immobilisation | **Mass photometry (MP)** | Interferometric light scattering → single-molecule mass |
| 2. Large volumes of crude sample, high DMSO | Matrix tolerance | **Biolayer interferometry (BLI)** | Wavelength shift from biolayer thickness change |
| 3. Real time, high mechanical noise | Vibration/flow insensitivity | **Localised surface plasmon resonance (LSPR)** | Shift in the absorbance maximum of metal nanoparticles |

---

## Scenario 1 — Heterodimers with binding affinities in the sub-µM range

### Method: **Mass photometry**

**Final answer: use mass photometry (MP).**

### How it works

Mass photometry is **based on interferometric scattering microscopy (iSCAT)**. A laser is focused at the interface between a clean glass coverslip and the buffer containing the sample. Two optical fields return to the detector:

1. the **incident laser light reflected from the glass–buffer interface** (a strong, constant reference field, $E_r = r E_i$, where $r$ is the interfacial reflectivity), and
2. the **light scattered by individual biomolecules as they land on (bind to) the glass coverslip** (a very weak field, $E_s = s E_i$).

**Images of single biomolecules are produced using the interference between the light scattered from individual molecules as they bind to the glass coverslip and the light of the incident laser reflected from the glass–buffer interface.** The detected intensity is therefore

$$I_{\text{det}} = |E_r + E_s|^2 = |E_i|^2\left(|r|^2 + |s|^2 + 2|r||s|\cos\phi\right),$$

in which the pure-scattering term $|s|^2$ is negligible but the **cross (interference) term $2|r||s|\cos\phi$** is detectable: it is linear in the scattering amplitude $s$ rather than quadratic, which is what makes single unlabelled proteins visible. A ratiometric background subtraction of sequential frames isolates each landing event as a diffraction-limited dark spot whose contrast is

$$C \propto s \propto \alpha \propto V \cdot (n_p - n_m) \;\propto\; m,$$

i.e. **the interferometric contrast is directly proportional to the molecule's polarisability and hence to its molecular mass**. Calibration with mass standards (e.g. BSA 66 kDa, IgG 150 kDa, β-amylase oligomers) converts contrast into mass with ~2% accuracy and ~20–25 kDa resolution, from a few tens of kDa up to several MDa.

### How the $K_D$ is obtained

Because MP counts single molecules and assigns each a mass, a single measurement returns the **mass distribution** of the solution: free A, free B and the heterodimer AB appear as separate peaks (A, B, A+B). Integrating the peaks gives the molar fractions directly, with no model of the signal required:

$$K_D = \frac{[\text{A}]_{\text{free}}[\text{B}]_{\text{free}}}{[\text{AB}]} = \frac{(f_A)(f_B)}{f_{AB}} \cdot c_{\text{tot}}' ,$$

evaluated from the counted populations at several total concentrations and fitted globally to the quadratic binding equation above. This is a true **solution-phase equilibrium measurement**: nothing is immobilised, nothing is labelled, and the stoichiometry (1:1 heterodimer vs. higher-order species) is read out simultaneously.

### Why this is the best choice for sub-µM affinities

* **The dynamic range matches the affinity.** A reliable $K_D$ requires measuring at concentrations spanning $K_D$ (ideally ~0.1–10 × $K_D$). MP operates on dilute solutions in the **~100 pM to ~100 nM** range (typically single-digit µL of sample at low nM), which is exactly the window needed for sub-µM binders — and, critically, **unlike other label-free techniques, mass photometry can measure binding affinities in the sub-µM range**. Methods that rely on an ensemble optical response at a surface (SPR/LSPR/BLI) or on bulk thermodynamic signals (ITC, which typically needs µM–mM protein and large sample amounts; or analytical ultracentrifugation/SEC, which are slow and dilution-prone) either cannot be operated at low enough concentrations to resolve a sub-µM $K_D$ accurately or suffer mass-transport/rebinding artefacts there. MP's single-molecule counting makes the signal-to-noise independent of concentration in that regime.
* **Closest to native conditions.** Measurement is in free solution, in physiological buffer, with no label, no tag, no surface tethering and no avidity artefacts; the only surface contact is the transient landing event used for detection. Weak, transient heterodimers that would be disrupted by immobilisation chemistry or by labelling of a lysine/cysteine at the interface are preserved.
* **It resolves stoichiometry and heterogeneity.** The mass histogram distinguishes 1:1 heterodimer from homodimers, higher oligomers and aggregates, so an apparent affinity is not contaminated by the wrong species — a common failure mode for surface-based assays.
* **Tiny sample requirement** (µL-scale, ng of protein), which matters when a sub-µM experiment must be run at many low concentrations.
* **Caveats to control:** landing-rate bias/surface affinity differences between species, the ~20–25 kDa mass-resolution limit (so A and B must differ enough in mass, or the dimer must be resolvable from the monomers), dilution-induced re-equilibration during the measurement window, and the need for scrupulously clean coverslips.

---

## Scenario 2 — Heterodimers in a large quantity of crude samples with high levels of DMSO

### Method: **Biolayer interferometry**

**Final answer: use biolayer interferometry (BLI).** **Of these techniques, biolayer interferometry is the only method that can analyse in crude materials with large volumes of DMSO present.**

### How it works

**In biolayer interferometry one binding partner is immobilised on a sensor, while the other binding partner is in solution.** The sensor is the tip of a disposable fibre-optic probe carrying a biocompatible layer (e.g. streptavidin, Ni-NTA, anti-His/anti-Fc, protein A or amine-reactive surface) to which partner A is captured; the probe is then dipped into a well containing partner B in solution. **White light is sent down the fibre and reflects at the biolayer** — specifically, it is reflected from two interfaces: the internal optical reference layer and the outer surface of the immobilised biolayer. The two reflected beams interfere.

**Upon binding of the protein in solution to the immobilised protein, there is a change in the thickness of the biolayer. This change in biolayer thickness causes the light to undergo a wavelength shift, generating an interference pattern that can be analysed.** Quantitatively, constructive interference occurs when

$$2\,n\,d = m\,\lambda \quad\Rightarrow\quad \Delta\lambda = \frac{2\,n\,\Delta d}{m},$$

so an increase in optical thickness $\Delta d$ (more mass bound per unit area) produces a measurable shift of the interference spectrum, reported in nanometres. The shift is recorded continuously, giving real-time association and dissociation traces from which $k_{\text{on}}$, $k_{\text{off}}$ and $K_D = k_{\text{off}}/k_{\text{on}}$ are fitted (or, from the plateau values, a steady-state $R_{\text{eq}}$ vs. $[\text{B}]$ Langmuir isotherm).

### Why BLI is the right — indeed the only workable — choice here

* **Crude-sample compatibility.** BLI is a **dip-and-read**, microfluidics-free technique: the probe is simply immersed in the sample well of a microplate. There are no flow cells, no microchannels, no pumps and no tubing, so there is nothing for cell lysate, serum, conditioned medium, periplasmic extract, fermentation broth, membrane preparations or particulates to clog. The optical signal arises **only from material that changes the thickness of the biolayer at the probe tip within the evanescent sensing depth**, so unbound, bulk crude components contribute essentially nothing — the instrument is intrinsically insensitive to the bulk refractive index of the well. Flow-based SPR, by contrast, is both prone to channel blockage and highly sensitive to bulk refractive-index mismatch, which is fatal in crude matrices.
* **High DMSO tolerance.** BLI tolerates high DMSO content (routinely 5–10%, and up to tens of percent with matched reference wells), precisely because the measurement is a *thickness/optical-path* change at the sensor surface rather than a bulk refractive-index change. DMSO at high concentration drastically alters bulk $n$, which in SPR/RI-based readouts produces enormous "DMSO bulk shifts" requiring elaborate solvent-correction calibration curves; in BLI the same mismatch is largely common-mode and is removed by a reference sensor loaded with an irrelevant protein and dipped in the identical buffer. This is the decisive advantage when the samples are compound- or lysate-derived and carry a high solvent load.
* **Large quantities/high throughput.** BLI is plate-based (96/384-well) and parallel (8–96 probes simultaneously), with regenerable or cheap disposable sensors, so **a large quantity of samples** can be processed quickly; sample is not consumed by flow (the well can be recovered), and no sample pre-purification step is needed. Immobilising one partner via a specific capture chemistry (His/biotin/Fc tag) also means **the immobilised partner is purified on the sensor out of the crude mixture**, giving specificity without a purification workflow.
* **Near-native conditions.** The solution-phase partner is never labelled or modified and remains in its own (crude) milieu, including its native binding partners and solutes; only the captured partner is tethered, and oriented capture through a terminal tag keeps the binding interface free.
* **Controls/caveats:** always run a reference sensor (no immobilised A) and a buffer-only reference well to subtract non-specific binding and solvent effects; match DMSO exactly between all wells; check for mass-transport limitation; avoid overloading the sensor (avidity/steric artefacts); verify that the crude matrix does not foul the capture chemistry.

---

## Scenario 3 — Heterodimers measured in real time, in an environment with high mechanical noise

### Method: **Localised surface plasmon resonance**

**Final answer: use localised surface plasmon resonance (LSPR).**

### How it works

**In LSPR, a sensor made of metal nanoparticles is used, upon which a protein is immobilised.** The sensor chip carries immobilised noble-metal nanostructures — gold (or silver) nanoparticles, nanorods, nanoholes or nanoislands — and one binding partner (A) is immobilised on those nanoparticles (e.g. through a self-assembled-monolayer/carboxyl–NHS chemistry, or via a capture tag). Light illuminating the nanoparticles drives a collective oscillation of their conduction electrons; at the resonance condition the particles absorb/scatter strongly, producing a sharp extinction peak at $\lambda_{\max}$ in the visible/near-IR.

The resonance position depends on the refractive index of the medium **within the tightly confined near-field (evanescent decay length $l_d \approx 5$–$30$ nm) immediately around each particle**:

$$\Delta\lambda_{\max} = m\,\Delta n\,\Big[1 - \exp\!\big(-2 d / l_d\big)\Big],$$

where $m$ is the refractive-index sensitivity and $d$ the adlayer thickness. When partner B in solution binds the immobilised A, the local refractive index inside this nanoscale shell increases and the extinction peak red-shifts. **LSPR therefore measures changes in the absorbance maxima (the shift in $\lambda_{\max}$, or equivalently the change in absorbance/extinction at a fixed wavelength) to determine the binding affinities of the protein heterodimers.** The shift is recorded continuously, giving real-time sensorgrams:

$$\Delta\lambda_{\max}(t) \propto [\text{AB}](t) \;\Rightarrow\; k_{\text{on}},\,k_{\text{off}} \;\Rightarrow\; K_D = k_{\text{off}}/k_{\text{on}},$$

with a steady-state Langmuir fit of $\Delta\lambda_{\max,\text{eq}}$ versus $[\text{B}]$ as the independent equilibrium determination.

### Why LSPR is the right choice in a mechanically noisy environment

* **Real-time, label-free kinetics.** LSPR gives continuous association/dissociation traces, so both rate constants (not just the equilibrium constant) are obtained, which is what "in real time" demands.
* **Intrinsic immunity to mechanical/vibrational noise — the decisive point.** The measured quantity is a **spectral position ($\lambda_{\max}$) / absorbance change**, not an angle or an intensity at a fixed geometry. Three consequences follow:
 1. **No precision opto-mechanics to be disturbed.** Conventional (propagating) SPR encodes binding as a shift in the *resonance angle* of a prism-coupled, Kretschmann-configuration beam; angular interrogation depends on rigid optical alignment at the milliradian level, so chassis vibration, table movement, or acoustic/mechanical noise translate directly into angular/baseline noise and drift. LSPR uses simple transmission/reflection spectroscopy of a nanoparticle film; a peak-position measurement is **referenced internally to the spectrum itself**, so small mechanical displacements, beam-pointing jitter, lamp-intensity fluctuations and coupling variations largely cancel (and spectral fitting of the whole peak further averages out noise).
 2. **The sensing volume is nanoscopic and self-referencing.** Because the plasmon field decays over only ~5–30 nm — much shorter than the ~200–300 nm penetration depth of propagating SPR — LSPR senses only the molecular layer at the particle surface. It is therefore far less sensitive to **bulk** refractive-index changes caused by vibration-driven convection, flow pulsation, mixing, micro-temperature gradients and thermal drift; such disturbances perturb the bulk medium, not the first few nanometres. This also reduces the stringency of temperature control, another noise channel.
 3. **No sensitive fluidics or mechanical actuation is required.** LSPR can be run in a simple static cuvette, well or microarray format with no flow cell, pump or moving angular stage, so there is no vibration-coupled flow-rate noise; it can even be read on a plate reader or fibre-coupled spectrometer. Fewer moving parts, less noise transmission.
* **Also near-native and practical:** label-free (no fluorophore or tag on the solution-phase partner), small footprint, small sample volumes, high local field enhancement giving good sensitivity for small mass changes, multiplexable as nanoparticle arrays, and compatible with physiological buffer. With a dual-wavelength/reference-particle scheme, residual common-mode noise can be subtracted explicitly.
* **Caveats:** one partner must be immobilised (orientation and surface density must be controlled to avoid avidity and steric artefacts), non-specific adsorption to the metal must be blocked (PEG/BSA/SAM backfill), and the short decay length means the binding event must occur within ~10–20 nm of the particle surface.

---

## Final answer

* **Scenario 1 (sub-µM affinities): mass photometry** — an iSCAT-based single-molecule method in which **images of single biomolecules are produced by interference between light scattered from individual molecules as they bind the glass coverslip and the incident laser light reflected from the glass–buffer interface**; contrast is proportional to mass, so free A, free B and AB are counted directly in solution and $K_D$ obtained from their populations. **Unlike other label-free techniques, mass photometry can measure binding affinities in the sub-µM range**, label-free and immobilisation-free, i.e. closest to native conditions.
* **Scenario 2 (large quantities of crude sample, high DMSO): biolayer interferometry** — **one partner is immobilised on a fibre-optic sensor while the other is in solution; white light reflects at the biolayer, binding increases the biolayer thickness, and this produces a wavelength shift that generates an analysable interference pattern** from which $k_{\text{on}}$, $k_{\text{off}}$ and $K_D$ are fitted. **BLI is the only one of these methods able to analyse crude materials containing large volumes of DMSO**, because it is dip-and-read (no microfluidics to clog), senses only the sensor-surface optical thickness, and is insensitive to bulk refractive-index/solvent mismatch; it is also parallel and plate-based for large sample numbers.
* **Scenario 3 (real time, high mechanical noise): localised surface plasmon resonance** — **a sensor of metal nanoparticles with one protein immobilised on them**, read out as **changes in the absorbance maxima ($\lambda_{\max}$ shift) to determine the heterodimer binding affinities** in real time. Its spectral (rather than angular/intensity) read-out, its ~5–30 nm evanescent sensing depth and its lack of precision opto-mechanics and flow hardware make it robust to vibration, bulk convection and thermal drift, so reliable real-time kinetics can be obtained in a mechanically noisy environment.
