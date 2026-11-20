# $^1$H NMR assignment and $M_\mathrm{n}$ determination for poly(5-methyl-5-ethyloxycarbonyl-1,3-dioxan-2-one) initiated by benzyl alcohol (crude, CDCl$_3$)

## 1. The chemistry being monitored

**Monomer (MTC-Et):** 5-methyl-5-ethyloxycarbonyl-1,3-dioxan-2-one — a six-membered cyclic carbonate whose C5 is quaternary, bearing a methyl group and an ethyl ester.
SMILES: `CCOC(=O)C1(C)COC(=O)OC1`

Proton environments in the monomer:
- 4 **ring methylene** protons (C4-H$_2$ and C6-H$_2$, both $-$O**CH$_2$**$-$ of the cyclic carbonate), which form a rigid AB system in the chair-locked ring (one "axial-like" and one "equatorial-like" doublet, $J \approx 11$ Hz);
- 2 **ethyl ester methylene** protons ($-$O**CH$_2$**CH$_3$, quartet);
- 3 **ring methyl** protons (C5$-$**CH$_3$**, singlet);
- 3 **ethyl methyl** protons (OCH$_2$**CH$_3$**, triplet).

**Initiator:** benzyl alcohol, PhCH$_2$OH, which opens the cyclic carbonate (organocatalytic ROP, e.g. DBU/TBD/TU) to give a benzyl carbonate chain end. SMILES of the repeat unit: `[*]OCC(C)(C(=O)OCC)COC(=O)[*]`

**Polymer repeat unit** (ring-opened): $-$O$-$CH$_2-$C(CH$_3$)(CO$_2$Et)$-$CH$_2-$O$-$C(=O)$-$, i.e.
- 4 **backbone methylene** protons (the two former ring $-$OCH$_2-$ groups, now acyclic and conformationally averaged, so they appear as a broad, unresolved envelope rather than a sharp AB pair);
- 2 ethyl ester methylene protons;
- 3 quaternary-carbon methyl protons;
- 3 ethyl methyl protons.

Chain end: one benzyl carbonate head group (PhCH$_2$O$-$, 5 aromatic + 2 benzylic protons **per chain**) and one terminal primary alcohol ($-$CH$_2$OH).

Degree of polymerisation is obtained by referencing polymer repeat-unit protons to the end-group protons of the single initiator per chain:

$$\mathrm{DP}_\mathrm{n} = \frac{(\text{integral per repeat-unit proton of polymer})}{(\text{integral per initiator proton})},\qquad
M_\mathrm{n} = \mathrm{DP}_\mathrm{n}\times 188.18 + 108.14\ \text{g mol}^{-1}$$

($M$(MTC-Et) = 188.18 g mol$^{-1}$, $M$(BnOH) = 108.14 g mol$^{-1}$.)

Because the spectrum is of a **crude** sample taken at an arbitrary time point, unreacted monomer is present and **all monomer resonances overlap polymer resonances except one**. That single fact dictates which shifts can and cannot be used.

## 2. All relevant chemical shifts (CDCl$_3$)

| $\delta$ (ppm) | Assignment | Protons | Species |
|---|---|---|---|
| **7.4** | **aromatic protons of the benzyl alcohol (initiator) phenyl ring** | 5 H per chain | initiator end group |
| **5.2** | **benzyl methylene protons, PhCH$_2$O$-$** | 2 H per chain | initiator end group |
| **4.7** | **ring methylene protons of the unreacted monomer** ($-$OCH$_2-$ of the intact cyclic carbonate; downfield half of the ring AB system, the sharp doublet) | unreacted monomer only | **monomer only — no polymer signal here** |
| **4.4–4.2** | (i) **methylene protons of the ring-opened polymer backbone** ($-$OCH$_2-$C$<$, 4 H per repeat unit) and (ii) **methylene protons of the ethyl functional group ($-$OCH$_2$CH$_3$) of both reacted (polymer) and unreacted (monomer) units** (2 H each); the upfield half of the monomer's ring AB doublet also falls at the top of this envelope | mixed | polymer **and** monomer |
| **1.4–1.3** | **ring methyl group (C5$-$CH$_3$) and $-$CH$_3$ of the ethyl group of the unreacted monomer** (3 H + 3 H per monomer) | monomer | monomer, overlapping the polymer methyls |
| **1.3–1.2** | **two groups: the ring methyl group of the polymer (quaternary C$-$CH$_3$) and the $-$CH$_3$ of the ethyl ester groups on the polymer** (3 H + 3 H per repeat unit) | polymer | polymer, overlapping the monomer methyls |

Minor/not-used signals in a crude spectrum: residual CHCl$_3$ at 7.26 ppm, residual CH$_2$Cl$_2$ at 5.30 ppm, terminal $-$CH$_2$OH at ≈3.7 ppm plus a broad OH, and catalyst/solvent (DBU, TBD, thiourea, DMF, toluene) peaks. These are impurity/end-of-chain signals and are excluded from the quantitation.

Two practical integration cautions follow directly from this list:

- The aromatic resonance is taken as the multiplet **at 7.4 ppm** and the integration window must **not be extended below 7.3 ppm**, because the residual CHCl$_3$ solvent peak at 7.26 ppm sits immediately upfield and would inflate the initiator integral.
- The benzylic resonance is the sharp 2 H singlet **at 5.2 ppm**; it should be integrated as that single peak and **not as a wide range extending below 5.0 ppm**, which would pick up crude-sample impurity signals and baseline distortion rather than initiator protons.

## 3. Which shifts to use, and why

### (a) Initiator (denominator): either the 7.4 ppm aromatic peak **or** the 5.2 ppm benzyl methylene peak

Both arise exclusively from the covalently attached initiator, one per chain, and neither overlaps monomer or polymer signals. **Either one may be used for the initiator integration**:

$$N_{\text{chains}} \;\propto\; \frac{I_{7.4}}{5} \quad\text{or}\quad \frac{I_{5.2}}{2}$$

**Which is preferable depends on the quality of the respective peaks, and the better choice can differ from sample to sample depending on spectrum quality.** The aromatic peak has 5 H (2.5× the intensity, so better signal-to-noise and a smaller relative error at low initiator loading/high $M_\mathrm{n}$), but it sits next to the residual CHCl$_3$ peak and can suffer from baseline roll or overlap with aromatic impurities (e.g. residual toluene, benzyl benzoate-type side products). The benzylic singlet is clean and well isolated but weaker, and can be broadened or shouldered by dibenzyl carbonate/benzyl alcohol impurity resonances at nearby shifts. In practice one should inspect both, check that $I_{7.4}/5 \approx I_{5.2}/2$, and use whichever is better resolved and cleanly baseline-separated in that particular spectrum.

### (b) Unreacted monomer (the correction term): the 4.7 ppm peak **must** be used

The resonance at 4.7 ppm comes from the **ring methylene protons of the intact cyclic carbonate**. On ring opening, those methylenes shift upfield into the 4.4–4.2 ppm envelope, so the 4.7 ppm signal disappears as conversion proceeds and is **the only resonance in the whole spectrum that belongs exclusively to unreacted monomer**. Every other monomer signal (ethyl OCH$_2$ at 4.4–4.2; ring CH$_3$ and ethyl CH$_3$ at 1.4–1.3) is superimposed on a polymer signal.

Therefore, whenever it is present (i.e. at any time point before full conversion), **the 4.7 ppm peak must be used** to quantify residual monomer:

$$N_{\text{monomer}} \;\propto\; \frac{I_{4.7}}{n_{4.7}}$$

with $n_{4.7} = 2$ when, as is usual in CDCl$_3$, the ring AB system is resolved so that the 4.7 ppm doublet carries two of the four ring protons (the partner doublet falling at ~4.2 ppm); use $n_{4.7} = 4$ if the full ring methylene multiplet is observed as a single resonance at 4.7 ppm. The proton count must be assigned consistently, since this number propagates into every subtraction below. Monomer conversion follows immediately:

$$p = 1 - \frac{N_{\text{monomer}}(t)}{N_{\text{monomer}}(0)}$$

### (c) Polymer repeat units (numerator), route 1: the 4.4–4.2 ppm envelope — **should be used**

**The chemical shift at 4.4–4.2 ppm should be used, because it contains the methylene protons of the polymer backbone (the ring-opened $-$OCH$_2-$ groups, 4 H per repeat unit) together with overlapping signals from unreacted monomer** (the ethyl $-$OCH$_2-$ of the monomer and the upfield half of its ring AB doublet, in addition to the polymer's own ethyl $-$OCH$_2-$). It is the most intense polymer-specific region of the spectrum and is well separated from the methyl region, so it gives the best precision — provided the monomer contribution is removed using the 4.7 ppm integral:

$$I_{4.4\text{–}4.2} = \underbrace{6\,N_{\text{polymer repeat units}}}_{4\ \mathrm{H\ backbone}\,+\,2\ \mathrm{H\ ethyl\ OCH_2}} \;+\; \underbrace{4\,N_{\text{monomer}}}_{2\ \mathrm{H\ ethyl\ OCH_2}\,+\,2\ \mathrm{H\ ring\ AB\ partner}}$$

$$\Rightarrow\quad N_{\text{polymer}} = \frac{I_{4.4\text{–}4.2} - 4\,N_{\text{monomer}}}{6},\qquad
\mathrm{DP}_\mathrm{n} = \frac{N_{\text{polymer}}}{I_{7.4}/5}$$

(If one prefers to ignore the AB partner and treat the monomer contribution in this window as the 2 H ethyl methylene only, the subtraction coefficient becomes 2 instead of 4; the point is that **some** monomer intensity unavoidably sits in this window, and it must be subtracted using the 4.7 ppm peak.)

### (d) Polymer repeat units, route 2: the 1.4–1.2 ppm methyl region — **can also be used, with subtraction**

**The chemical shift at 1.4–1.2 ppm can also be used to calculate the polymer molecular weight, provided the number of unreacted monomer units is appropriately subtracted from its integration.** The combined window holds 6 H per polymer repeat unit (3 H quaternary ring methyl at 1.3–1.2 + 3 H ethyl CH$_3$ at 1.3–1.2) and 6 H per unreacted monomer (3 H ring methyl + 3 H ethyl CH$_3$ at 1.4–1.3):

$$I_{1.4\text{–}1.2} = 6\,N_{\text{polymer}} + 6\,N_{\text{monomer}}
\quad\Rightarrow\quad
N_{\text{polymer}} = \frac{I_{1.4\text{–}1.2} - 6\,N_{\text{monomer}}}{6} = \frac{I_{1.4\text{–}1.2}}{6} - N_{\text{monomer}}$$

with $N_{\text{monomer}}$ again taken from the 4.7 ppm peak. Used this way the methyl region gives a $M_\mathrm{n}$ that should agree with route (c), and the agreement of the two routes is a useful internal consistency check.

### (e) What must **not** be used

**The chemical shift from the unreacted monomer ring methyl protons together with the unreacted monomer CH$_3$ protons of the ethyl group at 1.4–1.3 ppm must NOT be used to determine the number of unreacted monomer units, because this chemical shift overlaps with the methyl groups from the polymer** (the polymer ring methyl and polymer ethyl CH$_3$ at 1.3–1.2 ppm). The two sets of methyls are separated by only ~0.05–0.1 ppm, the polymer resonances are broad (and are a distribution of slightly different environments along the chain, including end-unit effects), and the monomer triplet/singlet sit on the shoulder of that broad polymer envelope. Deconvolution is unreliable and becomes worse as conversion increases, so integrating 1.4–1.3 ppm systematically **overestimates** residual monomer and corrupts both the conversion value and every subtraction that depends on it. Residual monomer must instead be quantified from the isolated 4.7 ppm ring-methylene resonance.

By the same token, the 4.4–4.2 ppm envelope must never be integrated as if it were pure polymer, and the methyl window at 1.4–1.2 ppm must never be integrated as if it were pure polymer: both require the monomer correction derived from 4.7 ppm.

## 4. Worked recipe

1. Reference the spectrum, phase and baseline-correct carefully (the broad polymer envelopes are sensitive to baseline roll).
2. Integrate the aromatic multiplet **at 7.4 ppm** (5 H/chain), stopping above 7.3 ppm to exclude residual CHCl$_3$ at 7.26 ppm; also integrate the benzylic singlet **at 5.2 ppm** (2 H/chain) as a narrow window. Choose whichever is cleaner in this particular spectrum (checking $I_{7.4}/5 \approx I_{5.2}/2$); set that value $= 1.00$ per chain.
3. Integrate the **4.7 ppm** ring-methylene doublet → $N_{\text{monomer}} = I_{4.7}/2$ (per chain). This is the only available measure of unreacted monomer.
4. Integrate **4.4–4.2 ppm** → $N_{\text{polymer}} = (I_{4.4\text{–}4.2} - 4N_{\text{monomer}})/6$.
5. Optionally integrate **1.4–1.2 ppm** → $N_{\text{polymer}} = I_{1.4\text{–}1.2}/6 - N_{\text{monomer}}$, and confirm it matches step 4.
6. $\mathrm{DP}_\mathrm{n} = N_{\text{polymer}}$ (per chain, since the initiator integral was normalised to 1 chain), and

$$M_{\mathrm{n}} = \mathrm{DP}_\mathrm{n}\times 188.18 + 108.14\ \text{g mol}^{-1}$$

*Example:* if, per chain, $I_{4.7} = 4.0$ (so $N_{\text{monomer}} = 2.0$) and $I_{4.4\text{–}4.2} = 128.0$, then $N_{\text{polymer}} = (128.0 - 8.0)/6 = 20.0$, i.e. $\mathrm{DP}_\mathrm{n} = 20$ and $M_\mathrm{n} = 20\times188.18 + 108.14 = 3872$ g mol$^{-1}$; the methyl region should then integrate to $6(20) + 6(2) = 132$, giving $132/6 - 2 = 20$ ✓.

## Final answer

- **7.4 ppm** — benzyl alcohol (initiator) aromatic protons, 5 H/chain. **Usable as the initiator reference** (integrate at 7.4, nothing below 7.3 ppm, to avoid residual CHCl$_3$).
- **5.2 ppm** — benzyl methylene protons PhCH$_2$O, 2 H/chain. **Also usable as the initiator reference** (integrate the single 5.2 ppm peak, not a range reaching below 5.0 ppm). **Either the aromatic peak or the benzyl methylene peak can be used; which is better depends on the quality of the respective peaks and may differ from sample to sample with spectrum quality.**
- **4.7 ppm** — ring methylene protons of **unreacted monomer**. **Must be used (when present): it is the only peak available for counting unreacted monomer units.**
- **4.4–4.2 ppm** — methylene protons of the **ring-opened polymer backbone** plus the **ethyl-group methylene protons of reacted and unreacted monomer units** (and the AB partner of the monomer ring methylenes). **Should be used** for the polymer repeat-unit count, after subtracting the overlapping unreacted-monomer contribution.
- **1.4–1.3 ppm** — **unreacted monomer** ring methyl + ethyl CH$_3$. **Must NOT be used to determine the number of unreacted monomers**, because it overlaps the polymer methyl groups.
- **1.3–1.2 ppm** — two groups from the **polymer**: the ring methyl group and the $-$CH$_3$ of the ethyl functional groups. Taken together as the **1.4–1.2 ppm** window, this region **can also be used to calculate the polymer molecular weight provided the unreacted monomer is appropriately subtracted** (using the 4.7 ppm integral).
- $M_\mathrm{n} = \mathrm{DP}_\mathrm{n}\times 188.18 + 108.14$ g mol$^{-1}$.
