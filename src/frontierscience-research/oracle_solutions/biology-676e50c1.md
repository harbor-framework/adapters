# TDP-43 aggregation inside stress granules: intra-condensate demixing, and the effect of a hyper-stable RRM1 plus elevated short-chain fatty acids

## Part 1. The proposed molecular pathway from soluble TDP-43 to a pathological aggregate inside stress granules

TDP-43 is a 414-residue, predominantly nuclear hnRNP with an N-terminal domain (NTD, residues 1–76, which mediates physiological head-to-tail oligomerisation), two RNA-recognition motifs (**RRM1**, ~residues 106–176; RRM2, ~191–262) and a C-terminal low-complexity/prion-like domain (CTD, 274–414) that contains the evolutionarily **conserved region (CR, ~residues 318–343)**, a transiently **α-helical hydrophobic patch (HP)** flanked by Gly/Ser/Gln-rich segments. The pathway below is a sequence of **five discrete, separable events**; the key conceptual point is that pathological aggregation does not occur directly from the cytoplasmic pool, but within a pre-existing condensate, and only after the TDP-43 molecules **demix a second time *inside* that condensate**.

### Step 1 — Stress granule formation and up-concentration of TDP-43 within stress granules (the critical initiating event)

Oxidative (or other proteotoxic) stress stalls translation initiation, eIF2α is phosphorylated, and untranslated mRNPs coalesce with G3BP1/TIA-1/caprin-1 into **stress granules (SGs)** by liquid–liquid phase separation (LLPS). TDP-43 is recruited into SGs through RRM-mediated RNA binding (UG-rich RNA), NTD oligomerisation and CTD–CTD contacts, and through cytoplasmic mislocalisation (stress-impaired nuclear import).

The decisive consequence is physico-chemical: **up-concentration of TDP-43 within stress granules**. The dilute cytoplasmic concentration of TDP-43 (~hundreds of nM) is raised inside the SG by one to two orders of magnitude (to tens of µM, i.e. a local enrichment/partition coefficient of roughly $K_p = c_{\text{dense}}/c_{\text{dilute}} \sim 10$–$100$). Because the rate of any *n*-th-order homotypic reaction scales as

$$v \propto k\,[\text{TDP-43}]^{n},\qquad n \ge 2,$$

a 10–100-fold rise in local concentration accelerates bimolecular self-association by $10^2$–$10^4$-fold, and raises the supersaturation $\ln(c/c^{*})$ that governs nucleation. **The up-concentration of TDP-43 inside SGs is therefore the critical initiating event**: it is what converts a protein that is soluble and functional at physiological concentration into one that is metastable and poised to nucleate. SGs act as the crucible; they are not themselves the aggregate.

### Step 2 — Oxidative stress as a distinct, critical initiating event

Up-concentration alone is reversible: normal SGs disassemble when stress is relieved. A **second, mechanistically distinct initiating event is required, and that event is oxidative stress itself** (chronic ROS/H₂O₂, depleted GSH, an oxidising cytoplasmic thiol–disulfide potential; $E_{\text{GSH/GSSG}}$ shifting from ~−300 mV towards ~−200 mV). Oxidative stress is not merely the trigger that builds the granule — it independently **licenses a specific set of covalent and conformational changes in TDP-43 that cannot occur under reducing conditions**: cysteine oxidation and intermolecular disulfide cross-linking, plus oxidative/conformational destabilisation of the folded RRM domains. It is this separation of the two initiating events (crowding *and* oxidation) that explains why physiological SGs are benign while chronic oxidative stress converts them into aggregation sites.

### Step 3 — Local unfolding of RRM1 exposes specific buried cysteines

Under these oxidising conditions, **local (partial) unfolding of the RRM1 domain occurs, and this local unfolding is necessary to expose specific cysteine residues**. RRM1 contains the reactive cysteine pair **Cys173 and Cys175** (with Cys198/Cys244 in RRM2 playing a secondary role); in the native β1-α1-β2-β3-α2-β4 RRM fold these thiols are buried/sequestered at low solvent accessibility and are not available for chemistry. RRM1 is only marginally stable ($\Delta G_{\text{unf}}$ of a few kcal mol⁻¹), and it is further destabilised when its cognate UG-rich RNA is lost (RNA engagement is the main thermodynamic buttress of the RRM fold) and by oxidation. The equilibrium

$$\text{RRM1}_{\text{folded, Cys buried}} \rightleftharpoons \text{RRM1}_{\text{locally unfolded, Cys exposed}}$$

is thus shifted to the right inside the oxidising, RNA-depleted, crowded SG interior. **Exposure of Cys173/Cys175 is strictly conditional on this local unfolding** — the cysteines are a cryptic, conformationally gated reactive site, and the folded state is the "off" state.

### Step 4 — Intermolecular disulfide bonds between exposed RRM1 cysteines drive homotypic TDP-43 interaction and **intra-condensate demixing**

Once exposed in an oxidising environment and held at high local concentration, the RRM1 cysteines of neighbouring molecules react:

$$\text{TDP-43}^{(i)}\text{–Cys–SH} + \text{TDP-43}^{(j)}\text{–Cys–SH} \xrightarrow{\;\text{oxidation}\;} \text{TDP-43}^{(i)}\text{–S–S–}\text{TDP-43}^{(j)} + 2\,[\text{H}]$$

**The formation of these intermolecular disulfide bonds between exposed RRM1 cysteines is a key driver of homotypic (TDP-43–TDP-43) interaction.** Three features make them decisive:

1. They are **covalent** — unlike the transient, multivalent, weak contacts that keep the SG liquid, a disulfide does not exchange on the second timescale, so it converts fleeting encounters into persistent dimers/oligomers.
2. They **increase valency**: each cross-linked species presents multiple NTD, RRM and CTD interaction surfaces, so the effective interaction strength per particle rises steeply; in Flory–Huggins terms the effective $\chi$ parameter for TDP-43–TDP-43 contacts increases relative to TDP-43–(SG matrix) contacts.
3. They **bias TDP-43 towards itself and away from the rest of the granule proteome and RNA** — i.e. they make the homotypic interaction dominant.

The consequence is **intra-condensate demixing**: within the already phase-separated SG, TDP-43 undergoes a *second* phase transition, nucleating a TDP-43-enriched sub-phase (a distinct droplet-within-a-droplet, seen as a TDP-43-rich core or "nested"/multiphase condensate that no longer exchanges with the surrounding granule material). Formally, when the free energy of mixing of TDP-43 with the SG phase becomes positive,

$$\Delta G_{\text{mix}} = \Delta H_{\text{mix}} - T\Delta S_{\text{mix}} > 0,$$

the system lowers its free energy by segregating TDP-43 into its own sub-compartment.

**The significance of intra-condensate demixing** is that it is the point of no return in the pathway, for four reasons:
* It raises the TDP-43 concentration a *second* time — now to near-pure-protein densities (hundreds of µM to mM) in the demixed sub-phase, the regime in which nucleation of ordered structure becomes probable rather than rare.
* It **strips away the protective components of the SG**: chaperones (HSPB1, HSP70/HSP40, DNAJB), and above all **RNA**, which is the principal physiological inhibitor of TDP-43 self-assembly. Loss of RNA buffering removes both the thermodynamic buttress of the RRM fold and the electrostatic/steric shielding of the CTD.
* It **aligns and concentrates the CTD/HP regions** in a water-poor, low-dielectric, high-local-density environment that favours intermolecular hydrogen bonding over hydration of the backbone.
* It changes the material state of the sub-phase: the demixed phase begins as a liquid but has a much shorter ageing time than the parent granule, so the SG becomes the site at which an irreversible species is born while the SG itself may still look normal.

### Step 5 — Liquid-to-solid transition of the demixed phase: α-helix → cross-β-sheet in the HP region

Finally, **the demixed TDP-43 phase undergoes a liquid-to-solid (liquid-to-gel/solid) transition, which involves a structural conversion of the HP region from α-helix to cross-β-sheet.** In the soluble and liquid states the conserved HP (~318–343) is a transient, partially populated **α-helix** that mediates weak, dynamic, reversible helix–helix (HP–HP) contacts — the contacts responsible for normal CTD-driven LLPS. At the protein densities and dehydrated conditions of the demixed sub-phase, and with the molecules held in register by RRM1 disulfide cross-links, the helical ensemble converts to extended β-strands that stack into **intermolecular, in-register cross-β sheets** (β-strands perpendicular to the fibril axis, ~4.7 Å strand spacing), stabilised by a continuous backbone hydrogen-bond ladder and by Gln/Asn and aromatic/hydrophobic ladders from the flanking low-complexity segments.

This α→β conversion is the molecular identity of the liquid-to-solid transition: the sub-phase loses internal diffusivity and FRAP recovery, becomes non-exchanging, 1,6-hexanediol- and SDS-resistant, thioflavin-S/amyloid-dye positive, and seeding-competent. The resulting species have all the hallmarks of ALS/FTD pathology: cytoplasmic phosphorylated (pS409/410) TDP-43 inclusions, ubiquitinated, C-terminal-fragment-containing, and accompanied by nuclear TDP-43 clearance and loss of splicing function (e.g. STMN2, UNC13A cryptic exon inclusion), i.e. combined gain of toxic function and loss of function.

### Pathway summary

$$
\underbrace{\text{oxidative stress}}_{\text{initiating event 2}} + \underbrace{\text{SG assembly}\;\rightarrow\;\text{up-concentration of TDP-43 in SGs}}_{\text{initiating event 1}} \rightarrow \underbrace{\text{RRM1 local unfolding}\;\rightarrow\;\text{Cys173/175 exposure}}_{\text{conformational gate}} \rightarrow \underbrace{\text{intermolecular RRM1 disulfides}\;\rightarrow\;\text{homotypic interaction}}_{\text{covalent driver}} \rightarrow \underbrace{\textbf{intra-condensate demixing}}_{\text{point of no return}} \rightarrow \underbrace{\text{liquid}\rightarrow\text{solid via HP }\alpha\text{-helix}\rightarrow\text{cross-}\beta}_{\text{pathological aggregate}}
$$

---

## Part 2. Predicted combined consequence of (i) a hyper-stabilised RRM1 and (ii) a sustained five-fold rise in short-chain (C6–C10) saturated fatty acids

### 2.1 Analysing alteration 1: hyper-stabilised RRM1

The variant increases the thermodynamic/structural stability of the RRM1 fold (higher $\Delta G_{\text{unf}}$, higher $T_m$, slower local breathing). Its effect propagates directly down the pathway described above, because RRM1 local unfolding is the conformational gate for everything that follows.

Treating the exposure of the cysteines as a pre-equilibrium with equilibrium constant $K_{\text{exp}}$:

$$K_{\text{exp}} = \frac{[\text{Cys exposed}]}{[\text{Cys buried}]} = \exp\!\left(-\frac{\Delta G_{\text{unf}}}{RT}\right)$$

so that an increase in stability of, say, $\Delta\Delta G_{\text{unf}} = +2$ kcal mol⁻¹ reduces the exposed fraction by $e^{-\Delta\Delta G/RT} \approx e^{-3.4} \approx 30$-fold at 37 °C.

* **Prediction (a): the hyper-stabilised RRM1 domain will markedly reduce the exposure of its cysteine residues.** Cys173/Cys175 remain buried in the reinforced β-sheet core even under the oxidising, RNA-depleted, crowded conditions inside the SG; the cryptic reactive site is not unmasked.
* **Prediction (b): reduced cysteine exposure translates mechanistically into a decrease in intermolecular disulfide bond formation.** Disulfide formation requires two solvent-accessible, deprotonated thiolates in productive geometry; its rate is second-order in the exposed species,

$$v_{\text{S-S}} = k_{\text{ox}}\,[\text{Cys}_{\text{exposed}}]^{2} \;\propto\; k_{\text{ox}}\,\big(K_{\text{exp}}\,[\text{TDP-43}]\big)^{2},$$

so a ~30-fold drop in the exposed fraction predicts a ~$10^3$-fold drop in the cross-linking rate. Oxidant availability is unchanged (indeed it is elevated), but there is no accessible substrate: the chemistry is substrate-limited, not oxidant-limited. The covalent homotypic driver is therefore effectively removed.
* **Prediction (c): consequently, the hyper-stabilised RRM1 will substantially reduce the likelihood and slow the kinetics of intra-condensate demixing, precisely because it inhibits intermolecular disulfide bond formation.** Without covalent cross-links, TDP-43 inside the SG retains only its weak, transient, exchanging contacts; its effective homotypic interaction strength (effective valency) stays below the threshold at which a TDP-43-rich sub-phase can nucleate out of the granule. In phase-separation terms the demixing boundary is not crossed: TDP-43 remains miscible with the SG matrix, continues to exchange with the cytoplasm, and the SG remains dissolvable on stress relief. The nucleation barrier for the sub-phase is raised, so even where demixing eventually occurs its rate is greatly reduced (long lag times, few events per granule). As a secondary benefit, a stably folded RRM1 also retains RNA binding, and bound RNA is itself an inhibitor of TDP-43 self-assembly.

A corollary worth stating: this is a specifically *anti-aggregation* prediction even though "greater stability" might naively be expected to be neutral. The pathology here requires a *loss* of native structure as its permissive step, so stabilising the native state is protective.

### 2.2 Analysing alteration 2: five-fold elevation of short-chain (C6–C10) saturated fatty acids

Short-chain/medium-chain saturated fatty acids (caproic C6, caprylic C8, capric C10) are small amphiphiles that are membrane-permeant, partition readily into the hydrophobic interior of condensates, and engage the **hydrophobic patch (HP)/conserved region of the TDP-43 CTD** — the same amphipathic helical surface that mediates HP–HP contacts. A sustained five-fold elevation therefore acts on the pathway at an entirely different node from alteration 1:

* The acyl chains dock against the HP amphipathic face and **stabilise/template the α-helical conformation of the CR and promote helix–helix (HP-mediated) association**, increasing the fraction of molecules in assembly-competent HP conformers and increasing the strength and residence time of HP–HP contacts (lowering the saturation concentration $c_{\text{sat}}$ for CTD-driven self-association and favouring subsequent conversion of that helical interface towards β-structure).
* In isolation, i.e. on a wild-type TDP-43 background, this is expected to be **pro-aggregation**: it lowers the barrier to the liquid-to-solid transition and accelerates HP-driven ageing of TDP-43-rich material.
* However, the HP arm acts **downstream of, and in synergy with, the RRM1 arm**. HP–HP contacts are weak, dynamic and non-covalent; by themselves they support reversible LLPS, not demixing out of a granule. They become pathological only when TDP-43 molecules have first been (i) up-concentrated, and (ii) covalently cross-linked and oriented through RRM1 disulfides so that HP segments are held at high local density, in register, for long enough to undergo the α→β conversion. The disulfide step provides the persistence and the register; the HP step provides the ordered solid structure.

### 2.3 Combined prediction

**Prediction: compared with the wild-type scenario, the combined presence of a hyper-stabilised RRM1 and a five-fold elevation of C6–C10 saturated fatty acids produces an overall *reduction* in pathological TDP-43 aggregation, specifically because the intra-condensate demixing pathway is blocked.** TDP-43 will still be recruited into and up-concentrated within SGs, the cell is still oxidatively stressed, and the HP region is in a more assembly-prone, fatty-acid-stabilised state — yet the measurable outcomes (frequency of TDP-43-rich demixed sub-phases per granule, formation of FRAP-immobile/non-exchanging TDP-43 cores, thioflavin/amyloid-positive and detergent-insoluble TDP-43, pS409/410 inclusions, seeding competence) are all predicted to fall, and those events that do occur will be slower and rarer.

### 2.4 Mechanistic justification: loss of the critical synergy between RRM1-mediated disulfide bonding and HP interactions

The justification rests on the architecture of the pathway, which is **sequential and synergistic rather than additive**. The two arms contribute multiplicatively to the probability of forming an irreversible aggregate:

$$P_{\text{aggregate}} \;\approx\; \underbrace{P_{\text{up-concentration}}}_{\text{unchanged (SGs still form)}} \times \underbrace{P_{\text{Cys exposure}} \times P_{\text{S–S cross-link}}}_{\textbf{collapsed by the stabilised RRM1}} \times \underbrace{P_{\text{HP }\alpha\rightarrow\beta}}_{\text{increased by the fatty acids}}$$

* The hyper-stabilised RRM1 drives the middle term towards zero. Because the terms multiply, **no increase in the last term can rescue the product**: a stronger HP arm acting on molecules that are never demixed and never covalently linked has nothing to act upon. The fatty-acid-enhanced HP interactions remain what they are physiologically — weak, transient, reversible, RNA- and chaperone-buffered contacts that support normal dynamic LLPS inside a granule that still disassembles.
* This is precisely the **loss of the critical synergy between RRM1-mediated disulfide bonding and HP interactions**. In wild type, the two cooperate: disulfides create long-lived, high-valency, high-local-density TDP-43 clusters that demix from the granule, and that demixed, RNA-poor, dehydrated environment is what allows HP α-helices to convert into intermolecular cross-β sheets; reciprocally, HP-driven condensation increases the local density of RRM1 domains and so feeds back on disulfide formation. Removing one partner of a cooperative pair removes the cooperativity, not just one additive contribution. The disulfide-driven demixing step is the **rate-limiting, obligate gate**, and it is the step that has been shut.
* Additional reinforcing arguments: (i) a stably folded RRM1 retains UG-rich RNA binding, and RNA occupancy both buttresses the fold and sterically/electrostatically suppresses CTD-driven self-assembly, so the protective effect is self-reinforcing; (ii) without demixing, TDP-43 stays in the chaperone- and RNA-rich granule interior, where HSP70/HSPB1 and RNA actively reverse incipient oligomers; (iii) small amphiphiles such as C6–C10 fatty acids also act as weak solubilisers of hydrophobic surfaces at the concentrations reached, which further limits the net pro-aggregation effect of the lipid arm; and (iv) the HP route on its own is kinetically much slower, since without covalent tethering any nascent β-rich nucleus is dissolved by exchange before it can grow past the critical nucleus size.
* **Caveat, stated for completeness but not altering the prediction:** the fatty-acid-driven HP arm could in principle support a slow, alternative aggregation route that does not require intra-condensate demixing (e.g. direct CTD-driven assembly outside granules at sites of very high local TDP-43 concentration). This route is far less efficient, lacks the covalent persistence that makes the demixed route irreversible, and is therefore not expected to offset the loss of the disulfide-dependent gate. The net effect of the two alterations together remains a **reduction in pathological aggregation propensity relative to wild type**.

### 2.5 Experimental tests of the prediction

* **Demixing:** live-cell imaging of TDP-43–mEGFP with SG markers (G3BP1–mCherry); quantify the fraction of SGs containing a TDP-43-enriched sub-phase, and FRAP/partition coefficients within it.
* **Disulfides:** non-reducing vs reducing SDS-PAGE for disulfide-linked dimers/oligomers; thiol-blocking with NEM/mPEG-maleimide (differential cysteine accessibility), Cys173/175→Ser mutants as the genetic control.
* **RRM1 exposure:** HDX-MS or limited proteolysis of RRM1 under control vs oxidative stress, ± the stabilising variant; thermal/urea denaturation to confirm $\Delta\Delta G_{\text{unf}}$.
* **HP structure:** CD/NMR of the CR peptide ± C6–C10 fatty acids (helicity), and ThT/FTIR for cross-β content; HP mutants (M337V, and helix-breaking or helix-stabilising substitutions) to isolate the HP arm.
* **Synergy:** a 2 × 2 design (wild-type vs hyper-stable RRM1) × (normal vs 5× C6–C10 fatty acids) with insolubility, seeding (FRET-biosensor) and pS409/410 as end-points — the predicted pattern is a large protective effect of the RRM1 variant that is not reversed by the fatty acids, i.e. a statistically significant negative interaction term.

---

## Final answer

1. **Pathway:** oxidative stress and SG assembly **up-concentrate TDP-43 within stress granules** (critical initiating event); **oxidative stress is a second, distinct critical initiating event** that enables **local unfolding of RRM1**, which is *necessary* to expose the specific cysteines Cys173/Cys175; **intermolecular disulfide bonds between these exposed RRM1 cysteines are a key driver of homotypic TDP-43 interaction**, which causes **intra-condensate demixing** of a TDP-43-rich sub-phase inside the SG (the point of no return: a second up-concentration, loss of RNA/chaperone buffering); the **demixed TDP-43 phase then undergoes a liquid-to-solid transition involving an α-helix → cross-β-sheet conversion of the HP region**, giving the irreversible, seeding-competent pathological aggregate.
2. **Combined alterations:** the hyper-stabilised RRM1 **reduces exposure of its cysteine residues**, which **mechanistically decreases intermolecular disulfide bond formation**, and therefore **substantially reduces the likelihood and slows the kinetics of intra-condensate demixing by inhibiting disulfide bonding**; although the 5× elevation in C6–C10 saturated fatty acids strengthens HP-mediated helical interactions, the **net combined effect is an overall reduction in pathological aggregation via the intra-condensate demixing pathway**, because the **critical synergy between RRM1-mediated disulfide bonding and HP interactions is lost** — the two arms act multiplicatively and sequentially, so an enhanced downstream HP arm cannot compensate for an abolished upstream, obligate, disulfide-dependent demixing step.
