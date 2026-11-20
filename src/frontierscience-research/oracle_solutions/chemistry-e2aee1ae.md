# Analysis of the PLS–FTC polymeric prodrug synthesis

Throughout, PLS = poly(lysine succinylated) (a poly(L-lysine) whose every $\varepsilon$-amine has been capped with succinic anhydride, leaving one pendant carboxylic acid per repeat unit); as supplied it is the **sodium (or other alkali) carboxylate salt**. FTC = emtricitabine, whose only acylatable handle is the primary 5′-hydroxyl of the oxathiolane ring; conjugation is therefore an **ester** (carboxylic acid + alcohol → ester) formed by DIC (carbodiimide) activation with DMAP as the acyl-transfer catalyst.

---

## 1. Consequence of not first converting PLS to the free acid form

**Consequence: the reaction would simply not proceed — there would be no conjugation.**

Reasoning:

1. The esterification chemistry chosen here (DIC/DMAP, "Steglich-type" carbodiimide coupling) is **water-incompatible**. Water hydrolyses the *O*-acylisourea intermediate and the acylpyridinium species back to the free acid, and the protocol goes to considerable lengths to exclude water (oven-dried flask and vial, nitrogen purge, *anhydrous* DMF and *anhydrous* DMSO). It must therefore be run in dry **organic** solvent.
2. The **salt form of PLS (polymeric sodium carboxylate) is a polyelectrolyte that is only soluble in aqueous solvents**; it does not dissolve in dipolar aprotic organic solvents such as DMF or DMSO. Sonication would not help — the material would remain a suspended, non-solvated solid.
3. Consequently, **if the PLS were not first converted to the free acid (PLS-COOH), it would not be soluble in the organic solvents used (DMF and DMSO), and no reaction would occur**: the carboxylates would be neither molecularly dissolved nor accessible for DIC activation, so no *O*-acylisourea, no acylpyridinium, and no ester bond to FTC.
4. A second, related point: the ionised carboxylate is intrinsically a poorer substrate for carbodiimide activation than the protonated acid, because DIC activation requires proton transfer from the –COOH to the carbodiimide nitrogen to generate the *O*-acylisourea. Even in a hypothetical homogeneous system, the carboxylate salt would be sluggish/unreactive.

Hence treatment with 1 N HCl (4.4 mL for 1000 mg PLS), which precipitates PLS-COOH, washing and lyophilising is a **required** step: it converts the water-only-soluble salt into **a form that is soluble in organic solvent**, which is the form that DMAP/DIC esterification chemistry demands.

---

## 2. Consequence of using 1k instead of 10k MWCO dialysis tubing

**Consequence: none — a 1k MWCO membrane would work just as well here, and the purity achieved would be comparable.**

Reasoning:

- The purpose of dialysis here is to remove **small-molecule** reaction components: unreacted FTC ($M_\mathrm{w}$ 247 Da), DMAP (122 Da), DIC (126 Da) and its hydration/consumption product *N,N′*-diisopropylurea (144 Da), DMF (73 Da), DMSO (78 Da), acetate/bicarbonate salts and NaCl (<100 Da).
- **All of the impurities generated in this reaction are much smaller than 1 kDa**, so a 1k MWCO membrane still retains the polymer conjugate (PLS is a polymer well above both cut-offs, and the 10k tubing was chosen with a comfortable margin) while passing every impurity. **A 1k membrane would therefore have no problem achieving comparable purity.**
- The only differences are practical, not qualitative: a tighter membrane has a somewhat lower permeability, so clearance of each species is slower (longer dialysis times / more buffer changes for the same residual level), and a 1k membrane additionally retains low-molecular-weight *polymer* fragments (e.g. short PLS chains, 1–10 kDa) that the 10k tubing would lose — if anything this slightly **increases** recovered yield, at the cost of retaining low-MW polymer species. Neither changes the identity or the achievable purity of the product.

---

## 3. Consequence of dialysing in water rather than sodium acetate buffer

**Consequence: DMAP would not be sufficiently removed from the product.**

Reasoning:

- DMAP is used stoichiometrically with the acid (429 mg, 3.51 mmol) and is a strong base for a pyridine (conjugate acid p$K_\mathrm{a}$ ≈ 9.2). In the presence of a **polyanionic** carrier such as succinylated poly(lysine), protonated DMAP (DMAP-H$^+$) is retained as a **counter-ion electrostatically bound along the polymer backbone**, i.e. it behaves as part of the macromolecule rather than as a free small molecule.
- Pure water provides no exchangeable counter-ions and essentially no ionic strength, so there is nothing to displace the ion-paired DMAP-H$^+$; it co-migrates with the retentate and dialysis against water alone leaves DMAP behind, however many water changes are performed.
- **DMAP therefore requires an ionic component in the dialysate in order to be completely removed by dialysis.** Dialysis against 100 mM sodium acetate buffer at pH 5.8 supplies (i) a large excess of Na$^+$, which exchanges for DMAP-H$^+$ on the polymer carboxylates by simple mass action (ion exchange), and (ii) a pH well below the p$K_\mathrm{a}$ of DMAP, keeping it fully protonated, water-soluble and mobile. Freed DMAP-H$^+$ acetate then passes the membrane.
- Note the buffer pH is also chosen to be acidic enough to protonate DMAP but not so acidic as to hydrolyse the new ester or re-precipitate the polymer; the subsequent 100 % water dialysis then strips the acetate salts.

So: **the consequence of dialysing with water rather than sodium acetate buffer is that the DMAP will not be sufficiently removed**, leaving a DMAP-contaminated (and therefore toxicologically unacceptable) product.

---

## 4. Consequence of adjusting the pH inside the dialysis bag to 6.5–7 instead of 6–6.5

**Consequence: none.**

Reasoning:

- The pH adjustment with saturated NaHCO$_3$ exists to bring the free-acid polymer back to a physiologically tolerable, water-soluble carboxylate form; a target of 6–6.5 is a conservative choice bracketed below neutrality.
- **Poly(lysine succinylated) ester prodrugs are quite stable at pH 5–7, especially at lower temperatures.** Ester hydrolysis of this linkage is catalysed by H$_3$O$^+$ at low pH and, far more steeply, by OH$^-$ at high pH; the pH–rate profile has a broad minimum across roughly pH 4–7. Moving the endpoint from 6.5 to 7.0 changes $[\mathrm{OH}^-]$ by only a factor of ~3 while remaining in that minimum, and the remaining manipulations (dialysis against water at **4 °C**, sterile filtration, lyophilisation) are performed cold and quickly, which suppresses hydrolysis further.
- Therefore adjusting the internal pH to between 6.5 and 7 would **not** cause measurable loss of drug loading, premature FTC release or polymer degradation: there is no consequence. (Only pushing well into the alkaline region — e.g. pH > 8, which saturated bicarbonate could reach if added carelessly — would begin to cleave the ester prodrug.)

---

## 5. Difference in biodistribution between 10 % and 100 % conjugation

**Consequence: the two materials would have significantly different biodistributions.** **Poly(lysine succinylated) prodrugs with 10 % versus 100 % drug conjugation do not distribute alike.**

Reasoning:

- The targeting function of PLS resides in its **pendant free succinyl carboxylates**: the polyanionic, succinylated (maleylated/succinylated poly-amino acid) surface is a recognised ligand for **scavenger receptor A1 (SR-A1, class A scavenger receptor)**, which is **expressed by myeloid cells** (monocytes/macrophages, including liver Kupffer cells, splenic and alveolar macrophages, and macrophages recruited to sites of inflammation and to HIV sanctuary tissues). Uptake is therefore receptor-mediated and cell-type selective.
- At **10 % conjugation**, only one in ten repeat units has had its carboxylate esterified with FTC; ~90 % of the polyanionic charge array is intact. The polymer retains the charge density and ligand presentation required for SR-A1 recognition, so the prodrug **displays selective targeting of the cells and tissues that express scavenger receptor A1** — i.e. preferential accumulation in myeloid cells and in macrophage-rich organs (liver, spleen, lymph nodes, lung), which is exactly the pharmacological objective for a macrophage-targeted antiretroviral depot.
- At **100 % conjugation**, every carboxylate has been converted to an FTC ester. The polymer loses its anionic character and becomes far more hydrophobic (every repeat unit now bears a nucleoside analogue). Consequently it is **no longer recognised by SR-A1 and shows no selective targeting**: its disposition is governed instead by non-specific factors — size-dependent circulation and renal handling, increased hydrophobicity leading to protein binding/aggregation and non-specific phagocytic or hepatic clearance, and a correspondingly broader, untargeted tissue distribution. Solubility also falls, which can further skew distribution toward aggregate-driven first-pass capture in liver and lung.
- Practical consequence: the 10 % material gives myeloid-cell-directed delivery with drug release inside the target cell, whereas the 100 % material behaves as a generic hydrophobic polymer–drug conjugate without SR-A1-mediated cell and tissue selectivity.

---

## Summary of answers

1. **Not converting to free acid:** PLS salt is soluble only in aqueous media, which is incompatible with DMAP/DIC esterification; in DMF/DMSO it would not dissolve, so **no reaction would occur** — the free-acid form is required for organic solubility.
2. **1k instead of 10k MWCO:** **no consequence**; every impurity in this reaction is far below 1 kDa, so comparable purity is achieved (only slower clearance, with retention of low-MW polymer).
3. **Water instead of sodium acetate buffer:** **DMAP would not be sufficiently removed** — removing ion-paired DMAP from the polyanionic polymer requires an ionic (salt-containing) dialysate to exchange it off.
4. **pH 6.5–7 instead of 6–6.5:** **no consequence**; PLS ester prodrugs are stable at pH 5–7, particularly at the 4 °C used here.
5. **10 % vs 100 % conjugation:** **significantly different biodistributions**; PLS targets **SR-A1**, expressed by **myeloid cells**, so the 10 % conjugate retains selective targeting of SR-A1-expressing cells/tissues, whereas the 100 % conjugate consumes all the carboxylate ligand array and shows **no selective targeting**.
