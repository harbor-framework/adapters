# Critical analysis of the Genexol-PM preparation protocol

The published procedure is a classic **solvent-evaporation / film(gel)-hydration** method: paclitaxel (PTX, 30 mg) and mPEG-poly(D,L-lactide) (mPEG-PDLLA, 150 mg) are co-dissolved in 2.0 mL acetonitrile (20 % drug loading w/w relative to polymer), the solvent is stripped on a rotary evaporator at 60 °C to leave a transparent gel/film, the film is hydrated with water at 60 °C (above the PDLLA $T_g$ and well above the CMC regime, so the amphiphile self-assembles), the suspension is sterile-filtered through 0.22 µm, and the filtrate is lyophilised.

Each question is answered in turn.

## 1. Consequence of stirring for 1 minute instead of 5 minutes

**There is no consequence.** The stirring step serves only one purpose — to dissolve the drug and the polymer in the organic solvent before evaporation. It is not a self-assembly step (no water is present yet), so there is no kinetic process whose outcome could depend on 1 vs 5 min.

The quantitative justification is solubility: **both paclitaxel and mPEG-PDLLA are highly soluble in acetonitrile.** Paclitaxel dissolves in acetonitrile to >30 mg/mL (it is routinely handled as 1–10 mg/mL stocks and acetonitrile is the standard HPLC/formulation solvent for it), and mPEG-PDLLA block copolymers are freely soluble in acetonitrile (a good solvent for both the PEG and the PDLLA block) at well over 100 mg/mL. The protocol asks for only

- PTX: 30 mg / 2.0 mL = **15 mg/mL**
- mPEG-PDLLA: 150 mg / 2.0 mL = **75 mg/mL**
- total solids 180 mg / 2.0 mL = 90 mg/mL,

i.e. concentrations comfortably below the saturation limits of either solute in acetonitrile. **At these listed masses and volumes the polymer and the drug therefore dissolve almost immediately — certainly in less than 60 s — with ordinary magnetic stirring.** Dissolution is complete long before the 1 min mark, so a clear, molecularly dispersed solution is obtained either way. Because the subsequent film composition, the drug/polymer ratio, and everything downstream (gel transparency, micelle size, encapsulation efficiency) depend only on having a homogeneous solution, reducing the stirring time from 5 min to 1 min changes **nothing** about the product. (The only situation in which it would matter is if undissolved PTX crystals remained and acted as seeds for drug precipitation during hydration — and that does not occur at 15 mg/mL in acetonitrile.)

**Answer: no consequence; the micellar solution and the final Genexol-PM product are unchanged.**

## 2. Consequence of adding saline at 60 °C instead of water

**There is no consequence** — the micelles form and remain stable, with the same size distribution and drug loading.

The general concern is legitimate and should be stated: **a high salt content can destabilise micelles.** Electrolytes screen electrostatic repulsion (irrelevant here, since mPEG-PDLLA is non-ionic), and more importantly they are kosmotropic "salting-out" agents: high concentrations of Na$^+$/Cl$^-$ compete for water of hydration, dehydrate the PEG corona, lower the polymer cloud point and the CMC, and at sufficient ionic strength can collapse/aggregate the PEG shell and precipitate the drug. **However, this is not the case for saline in this particular protocol.** The reasons are:

- Normal saline is only 0.9 % NaCl ≈ **154 mM** (ionic strength ~0.15 M). PEG salting-out and cloud-point depression require molar concentrations of structure-making salts (e.g. >1–2 M Na$_2$SO$_4$/K$_3$PO$_4$); NaCl at 0.15 M lowers the PEG cloud point by only a few degrees and leaves the corona fully hydrated.
- The driving force for assembly is the extremely hydrophobic PDLLA block plus a highly hydrophobic drug ($\log P_{\mathrm{PTX}} \approx 3$, aqueous solubility ~0.3 µg/mL). The free energy of micellisation is large and negative and the CMC is very low (µg/mL range); a mild increase in ionic strength actually makes the hydrophobic effect marginally stronger, i.e. it *favours* assembly rather than opposing it.
- The micelles are **sterically** (not electrostatically) stabilised by the PEG brush, so there is no electrical double layer to compress; DLVO-type salt-induced coagulation does not apply.
- Empirically, Genexol-PM is *clinically reconstituted and administered in 0.9 % NaCl (and in 5 % dextrose)*; the lyophilised cake is routinely dispersed in saline for infusion without change in particle size or drug release. Hydrating the gel matrix with saline at 60 °C is simply doing that step earlier.

**Answer: no consequence; saline at 60 °C gives the same transparent micellar solution. (The only practical caveat is cosmetic rather than colloidal: the NaCl becomes a non-volatile excipient that will remain in the lyophilised powder and will contribute to the tonicity/mass of the final cake.)**

## 3. Consequence of adding 5 % sucrose at 60 °C instead of water

**There is no consequence** for micelle formation, size, or drug incorporation.

Again the general concern should be acknowledged: **sugar molecules can sometimes destabilise micelles.** Sugars are strong water-structure makers; at high concentration they reduce the amount of "free" water, dehydrate PEG, lower the cloud point/CMC, raise the viscosity of the medium and slow the chain exchange needed for ordered assembly, and in extreme cases can drive aggregation or drug expulsion. **But this is not the case with 5 % sucrose in this particular protocol:**

- 5 % (w/v) sucrose is only **~0.146 M** (MW 342.3), a dilute, iso-osmotic (~160 mOsm) solution. Preferential-hydration effects at this level are far too weak to dehydrate the PEG corona or to alter the hydrophobic driving force for assembly.
- Sucrose is a non-ionic, non-surface-active, non-solvent for PDLLA and for paclitaxel: it neither inserts into the core nor competes with the drug for the hydrophobic domain, and it does not change the polymer–water interfacial tension appreciably.
- At 60 °C the gel matrix hydrates and the copolymer self-assembles exactly as in water; viscosity of 5 % sucrose at 60 °C is close to that of water, so mass transport during hydration is unaffected.
- Functionally the change is *beneficial*: 5 % sucrose is one of the standard **lyoprotectants/cryoprotectants** for polymeric micelles. Being present before freeze-drying, it vitrifies around the micelles, prevents freezing/drying-induced fusion and irreversible aggregation, and gives an elegant cake that reconstitutes to the original ~25 nm size distribution. (Genexol-PM itself is in fact formulated with a sugar-type bulking agent, and 5–10 % sucrose or trehalose is a conventional choice.)

**Answer: no consequence for the micelles; 5 % sucrose simply doubles as the lyoprotectant, and the transparent micellar solution is identical to that obtained with water.**

## 4. DLS size distribution by intensity *before* filtration: how many peaks and what sizes?

**Two peaks are present.**

- **A dominant peak at ≈ 25 nm** (hydrodynamic diameter of the drug-loaded mPEG-PDLLA micelles; this is the well-documented size of Genexol-PM, typically 20–30 nm, with a narrow PDI). This accounts for essentially all of the mass of the sample.
- **A second, much smaller peak at ≈ 1000 nm** (i.e. ~1 µm). This arises from the minor population of large species that the gel-hydration method inevitably generates before clean-up: non-incorporated/recrystallised paclitaxel microparticles, incompletely hydrated polymer aggregates or secondary micellar clusters, and adventitious dust.

Two points about the intensity-weighted representation explain why the 1000 nm population shows up as a separate, clearly visible peak even though it is present in trace amounts:

1. Rayleigh scattering intensity scales as $I \propto d^{6}$ (for particles small relative to $\lambda$) and, in general, strongly superlinearly with size, so a vanishingly small number of 1 µm objects produces a detectable intensity contribution. The intensity distribution over-represents them relative to the volume or number distributions, where the ~25 nm micelles would appear as essentially 100 % of the sample.
2. Because the two populations differ by a factor of ~40 in diameter (far more than the ~3-fold resolution limit of cumulant/CONTIN analysis), they are resolved as two distinct modes rather than one broadened peak.

This is precisely why the protocol includes the **0.22 µm filtration step**: it removes the ~1000 nm population (which cannot pass the membrane) while the 25 nm micelles pass quantitatively, leaving a **single ~25 nm peak** in the post-filtration intensity distribution. The filtration is simultaneously a sterilising step.

**Answer: two peaks — a main peak at about 25 nm (the micelles) and a much smaller peak at about 1000 nm (large aggregates/unincorporated drug), the latter being removed by the 0.22 µm filter.**

## 5. Missing steps in the published protocol

The procedure as written is reproducible only in outline; several operationally decisive parameters are not stated. The important omissions are:

1. **How and when the lyoprotectant is added.** The protocol goes straight from filtration to lyophilisation, yet freeze-drying a 25 nm micellar dispersion without a lyoprotectant/bulking agent risks irreversible aggregation, cake collapse and poor reconstitution; the marketed product contains a sugar excipient. **The protocol does not describe how or when to add a lyoprotectant** (identity, concentration, and whether it is dissolved in the hydration water, added after filtration, or added as a separate sterile-filtered stock) — nor the freeze-drying cycle itself (freezing rate, shelf temperature, primary/secondary drying times, chamber pressure).
2. **For how long, and to what extent, the acetonitrile was removed under reduced pressure.** Only "evaporated on a rotary evaporator under reduced pressure at 60 °C" is given. **No duration, no pressure/vacuum level and no end-point criterion (residual solvent specification) are specified.** Residual acetonitrile is both a toxicological issue (ICH Q3C class 2, limit 410 ppm) and a formulation issue — residual solvent plasticises the core, swells the micelle and can promote drug recrystallisation on storage. Whether a secondary high-vacuum drying step is needed is left undefined.
3. **How much water to add after acetonitrile removal.** **The volume (or final concentration) of the hydration water is not stated.** This sets the polymer and drug concentration in the micellar solution, and hence the loading efficiency, the micelle size and the risk of drug precipitation; the marketed product corresponds to ~6 mg/mL paclitaxel after reconstitution, but the protocol gives no target volume, so the experiment cannot be reproduced quantitatively.
4. **For how long the water should be added/stirred prior to filtration.** **The protocol does not state the hydration/equilibration time** — how long water addition takes, whether the mixture is stirred, vortexed or sonicated, and how long it is held at 60 °C before the solution is considered equilibrated. Micelle formation and film dissolution are kinetically controlled, and insufficient hydration time leaves un-dissolved gel and inflates the large-particle population.
5. **Whether the solution should be cooled to room temperature or maintained at 60 °C for the filtration step.** **This is not specified.** It matters: filtering hot (60 °C) keeps viscosity low and the matrix fully dissolved but is above the cloud-point-sensitive region and can stress the membrane, whereas cooling to room temperature changes the solution viscosity, the micelle hydration and the propensity of paclitaxel to recrystallise, and therefore changes how much material is lost on the 0.22 µm filter.

Further details that are also absent (secondary to the five above) include: the molecular weight/block ratio and polydispersity of the mPEG-PDLLA used; the stirring speed/temperature during dissolution; the filter membrane material (PVDF/PES, to avoid drug adsorption) and whether the filtrate was assayed; and the analytical checks that should follow (HPLC determination of drug loading and encapsulation efficiency, DLS size/PDI before and after lyophilisation, residual solvent and water content).
