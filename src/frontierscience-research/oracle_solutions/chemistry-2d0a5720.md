# Which platinum complex gives the sharpest $^{195}$Pt–$^{1}$H satellites?

## Final answer (stated first)

**$[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$** — the octahedral Pt(IV) complex — is expected to show the **sharpest and most well-defined $^{195}$Pt–$^{1}$H satellite peaks** in its $^1$H NMR spectrum at 600 MHz, in the same solvent and at the same temperature.

The reasoning is developed below.

## 1. What determines the sharpness of a $^{195}$Pt–$^{1}$H satellite?

$^{195}$Pt is the only naturally occurring spin-active Pt isotope ($I = 1/2$, ~33.8 % abundance). The ~66 % of molecules containing NMR-silent Pt isotopes give the central $^1$H line; the ~34 % containing $^{195}$Pt give a pair of **satellites** flanking it, separated by $^{n}J(^{195}\mathrm{Pt}-^{1}\mathrm{H})$.

A satellite is only observed as a sharp doublet component if the $^{195}$Pt spin state persists for a time that is long compared with the inverse of the coupling constant. The relevant criterion is

$$T_{1,2}(^{195}\mathrm{Pt}) \gg \frac{1}{2\pi\, J(\mathrm{Pt-H})}$$

and the extra broadening transmitted to the $^1$H satellite by the coupled $^{195}$Pt nucleus is

$$\Delta\nu_{1/2}^{\text{(satellite)}} \approx \frac{1}{\pi\,T_{1}(^{195}\mathrm{Pt})}\quad\text{(plus the intrinsic }^{1}\text{H linewidth)}$$

Hence:

- **Fast** relaxation of $^{195}$Pt (short $T_1$/$T_2$) means the Pt spin flips rapidly between $m_I = +1/2$ and $-1/2$; the two satellite lines are averaged and broadened, and in the limit of very fast Pt relaxation they collapse entirely ("self-decoupling"). The satellites become shallow, broad humps.
- **Slow** relaxation of $^{195}$Pt (long $T_1$/$T_2$) preserves the two Pt spin states for many coupling periods, so the satellites remain narrow, intense and well resolved.

**Therefore the question "which complex has the sharpest satellites?" reduces to "in which complex does the $^{195}$Pt nucleus relax most slowly?" — i.e. which complex has the longest $^{195}$Pt spin relaxation time.** Sharpness and resolution of the satellite peak are a direct consequence of an **increased spin relaxation time of the $^{195}$Pt nucleus**, and for Pt the relaxation time is governed by the **chemical shift anisotropy (CSA) mechanism**.

## 2. Why CSA is the dominant relaxation mechanism here

For a spin-$1/2$ nucleus there is no quadrupolar relaxation ($Q = 0$ for $I = 1/2$), and for a heavy metal centre the dipolar coupling to remote protons is weak (it falls off as $r^{-6}$, and the ligand protons are several Å away). What remains, and what dominates for **heavy spin-$1/2$ nuclei**, is **chemical shift anisotropy relaxation**. This is the well-known situation for $^{195}$Pt and for the other heavy $I = 1/2$ nuclei ($^{199}$Hg, $^{207}$Pb, $^{183}$W, $^{103}$Rh, $^{205}$Tl): their valence electron distributions are highly polarizable and strongly anisotropic, the paramagnetic shielding term is huge, and their chemical shift ranges span many thousands of ppm (for $^{195}$Pt, > 13,000 ppm). A large shift range is a direct signature of a large shielding anisotropy, and $\Delta\sigma$ for Pt(II)/Pt(IV) complexes is of the order of $10^3$ ppm. CSA relaxation is therefore **especially relevant to $^{195}$Pt**, and it is the mechanism that controls whether $^{195}$Pt–$^{1}$H satellites are sharp or washed out — all the more so at the high field of a 600 MHz instrument, because the CSA rate scales with $B_0^2$.

## 3. The physical origin of CSA relaxation

When the platinum complex is placed in the applied magnetic field $B_0$ of the spectrometer, the $^{195}$Pt nucleus **does not experience $B_0$ to its full extent**. The electron density of the coordination sphere surrounding the $^{195}$Pt nucleus is itself polarized by the applied field and **generates its own (induced) local magnetic field**. This local field opposes (shields) the applied field at the nucleus — the **shielding effect** — so that the nucleus senses

$$B_{\text{local}} = B_0\,(1-\sigma)$$

Because the electron density around Pt is not spherically symmetric, the shielding is **not a scalar but a second-rank tensor** $\boldsymbol{\sigma}$ with principal components $\sigma_{xx},\sigma_{yy},\sigma_{zz}$: the degree of shielding depends on the orientation of the molecule with respect to $B_0$. In other words, the shielding — and hence the local field — is **anisotropic**:

$$\Delta\sigma = \sigma_{zz} - \tfrac{1}{2}(\sigma_{xx}+\sigma_{yy})$$

In solution the molecule undergoes **constant molecular motions (Brownian tumbling)**, which continuously re-orients the shielding tensor with respect to $B_0$. The local field at the $^{195}$Pt nucleus is therefore **fluctuating** in time, with a correlation time $\tau_c$ equal to the rotational correlation time of the complex. A randomly fluctuating magnetic field at the nucleus is precisely what induces spin relaxation; this is the **chemical shift anisotropy relaxation** mechanism. The larger the anisotropy of the electron (charge) distribution, the larger the amplitude of the fluctuating field and the faster the relaxation.

## 4. Quantitative expression

The CSA relaxation rates for a spin-$1/2$ nucleus such as $^{195}$Pt (extreme-narrowing limit, axially symmetric shielding tensor) are

$$T_1^{-1}(\text{CSA}) = \frac{6}{7}\,T_2^{-1}(\text{CSA}) = \frac{2}{15}\,\gamma_{\mathrm{Pt}}^{2}\,\beta_0^{2}\,\Delta\sigma^{2}\,\tau_c$$

where

- $\gamma_{\mathrm{Pt}}$ = gyromagnetic ratio of $^{195}$Pt,
- $\beta_0$ = applied magnetic field strength ($B_0$),
- $\Delta\sigma^{2}$ = the (square of the) **chemical shift anisotropy tensor** term,
- $\tau_c$ = rotational correlation time.

Now compare the four complexes term by term under the stated conditions (same temperature, same solvent, same 600 MHz spectrometer):

- **$\gamma_{\mathrm{Pt}}^{2}$ — identical for all four complexes.** The gyromagnetic ratio is an intrinsic nuclear property of $^{195}$Pt ($\gamma/2\pi = 9.153$ MHz T$^{-1}$); it is the same for every $^{195}$Pt nucleus regardless of its chemical environment, so this term cannot discriminate between the complexes.
- **$\beta_0^{2}$ — identical for all four**, since all spectra are acquired on the same 600 MHz ($\beta_0 \approx 14.1$ T) instrument.
- **$\tau_c$ — essentially comparable for all four**, because the measurements are made at the same temperature in the same solvent (same viscosity $\eta$) and the complexes are of similar molecular size/hydrodynamic radius ($\tau_c = 4\pi\eta r^{3}/3k_BT$ from the Stokes–Einstein–Debye relation). It therefore cannot be the discriminating factor either.
- **$\Delta\sigma^{2}$ — this is the only term that differs significantly.** The chemical shift anisotropy tensor term is governed by the **symmetry of the electronic charge distribution around the nucleus**, which in turn is determined by the **symmetry and the coordination geometry of the complex** (the number, arrangement and donor properties of the ligands).

So the problem reduces entirely to comparing $\Delta\sigma^2$, i.e. to comparing the symmetry of the four complexes.

## 5. Symmetry argument

**A more symmetrical molecule experiences a smaller CSA effect**, because the electron density of the coordination sphere is distributed more evenly about the nucleus. In the limiting case of perfectly cubic/spherical symmetry the three principal components of the shielding tensor become equal, $\sigma_{xx} = \sigma_{yy} = \sigma_{zz}$, so $\Delta\sigma \to 0$ and CSA relaxation vanishes. Conversely, a low-symmetry environment with electron density concentrated in one plane produces a very large $\Delta\sigma$.

### Geometries of the four complexes

The four complexes do **not** all have the same geometry/symmetry:

- *cis*-$[\mathrm{Pt(N_3)_2(pyridine)_2}]$ — **square planar** Pt(II), $d^8$, four-coordinate ($C_{2v}$).
- *trans*-$[\mathrm{Pt(pyridine)_2(N_3)_2}]$ — **square planar** Pt(II), $d^8$, four-coordinate ($C_{2h}$/$D_{2h}$-like).
- $[\mathrm{Pt(NH_3)_2(N_3)_2}]$ — **square planar** Pt(II), $d^8$, four-coordinate.
- $[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$ — **octahedral** Pt(IV), $d^6$, six-coordinate.

### Why the octahedral Pt(IV) complex has the smallest $\Delta\sigma^2$

**Octahedral complexes such as $[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$ are more symmetrical than the square planar complexes** *cis*-$[\mathrm{Pt(N_3)_2(pyridine)_2}]$, *trans*-$[\mathrm{Pt(pyridine)_2(N_3)_2}]$ and $[\mathrm{Pt(NH_3)_2(N_3)_2}]$. Their higher symmetry is a result of their **extreme crystal(-field) regularity** compared with square planar Pt(II) complexes: six donor atoms occupy all vertices of a regular polyhedron, filling the coordination sphere along $\pm x$, $\pm y$ **and** $\pm z$, so that the ligand electron density approaches a cubic (near-spherically symmetric) distribution about the $^{195}$Pt nucleus.

A square planar $d^8$ Pt(II) centre, in contrast, is intrinsically and severely anisotropic: there are **no axial ligands at all**, so the in-plane $\sigma$-donation and the filled $5d_{z^2}$ density along $z$ create a shielding tensor whose unique ($z$) component differs enormously from the in-plane components. The paramagnetic shielding contribution, which depends on low-lying $d\!-\!d$ excitations mixing in under the field, is strongly orientation-dependent in a four-coordinate planar field. Square planar Pt(II) complexes therefore have very large $\Delta\sigma$ (thousands of ppm). The same conclusion is reached from the differing geometry/symmetry of the complexes: *cis*- and *trans*-$[\mathrm{Pt(N_3)_2(py)_2}]$ and $[\mathrm{Pt(NH_3)_2(N_3)_2}]$ are planar and hence electronically "flat"; among them, lowering of symmetry by *cis* arrangement of inequivalent ligands makes matters worse still, but **all three are far more anisotropic than the octahedral Pt(IV) species.**

### Consequences

Because of its **higher symmetry, $[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$ has a smaller chemical shift anisotropy tensor ($\Delta\sigma^{2}$) and consequently a slower chemical shift anisotropy relaxation** (longer $T_1$ and $T_2$ for $^{195}$Pt):

$$\Delta\sigma^{2}_{\text{oct}} \ll \Delta\sigma^{2}_{\text{sq. planar}} \;\Longrightarrow\; T_{1}^{-1}(\text{CSA})_{\text{oct}} \ll T_{1}^{-1}(\text{CSA})_{\text{sq. planar}} \;\Longrightarrow\; T_{1,2}(\text{oct}) \gg T_{1,2}(\text{sq. planar})$$

and hence, from $\Delta\nu_{1/2} \approx 1/\pi T_1(^{195}\mathrm{Pt})$,

$$\Delta\nu_{1/2}^{\text{(satellite)}}(\text{oct}) \ll \Delta\nu_{1/2}^{\text{(satellite)}}(\text{sq. planar})$$

The three square planar Pt(II) complexes relax rapidly through the CSA mechanism, so their $^{195}$Pt–$^{1}$H satellites are broadened and poorly defined (partially self-decoupled), whereas the slowly relaxing $^{195}$Pt nucleus of the octahedral Pt(IV) complex preserves its spin states and yields narrow, well-resolved satellites. (The effect is accentuated at 600 MHz, where the $\beta_0^2$ factor amplifies any CSA difference.)

## 6. Summary of the logic

1. Satellite sharpness/resolution $\propto$ the **spin relaxation time of the $^{195}$Pt nucleus**: slower $^{195}$Pt relaxation (longer $T_1$, $T_2$) $\Rightarrow$ sharper, better-defined satellites; fast relaxation broadens and ultimately self-decouples them.
2. For heavy $I = 1/2$ nuclei — very much including $^{195}$Pt — the dominant relaxation pathway is **chemical shift anisotropy**, arising because the coordination-sphere electron density generates its own local field that shields the nucleus from $B_0$, and this shielding is orientation-dependent (anisotropic) and made to fluctuate by constant molecular tumbling.
3. $T_1^{-1}(\text{CSA}) = \frac{6}{7}T_2^{-1}(\text{CSA}) = \frac{2}{15}\gamma_{\mathrm{Pt}}^{2}\beta_0^{2}\Delta\sigma^{2}\tau_c$.
4. $\gamma_{\mathrm{Pt}}^2$ (intrinsic to $^{195}$Pt), $\beta_0^2$ (same 600 MHz magnet) and $\tau_c$ (same solvent/temperature, similar size) are the same for all four complexes; only $\Delta\sigma^{2}$ differs, and it is set by the symmetry of the electronic charge distribution, i.e. by the symmetry/geometry of the complex.
5. More symmetrical $\Rightarrow$ more even electron density $\Rightarrow$ smaller $\Delta\sigma^{2}$ $\Rightarrow$ slower CSA relaxation.
6. Three of the complexes are square planar Pt(II); $[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$ is octahedral Pt(IV) and is the most symmetrical (extreme regularity of the six-coordinate crystal field).

**Conclusion: $[\mathrm{Pt(N_3)_2(pyridine)_2(OH)_2}]$ has the smallest $\Delta\sigma^{2}$, the slowest CSA relaxation and therefore the longest $^{195}$Pt relaxation time, and so it displays the sharpest and most well-defined $^{195}$Pt–$^{1}$H satellite peaks in its $^1$H NMR spectrum.**
