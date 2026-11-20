# Iron metabolism and the proliferative capacity of hematopoietic stem cells: an experimental programme

## Preliminary: the cells and the constraint they impose

Long-term HSCs are vanishingly rare — in mouse bone marrow (BM), LSK (Lin⁻ Sca-1⁺ c-Kit⁺) cells are ~0.1–0.5% of nucleated cells and the SLAM LT-HSC fraction (LSK CD150⁺ CD48⁻ CD34⁻ Flt3⁻) is ~0.005–0.01%, i.e. a few thousand cells per mouse. Every assay below is therefore chosen to work at **single-cell resolution on a prospectively gated, immunophenotypically defined population**, not on bulk marrow. Bulk-marrow iron or protein measurements are dominated by erythroid precursors, which have enormous iron fluxes and would completely mask the HSC signal.

---

## 1. Measuring labile iron content in mouse HSCs

### Final answer
**Use a fluorescent (fluorogenic) labile-iron probe and read it out by flow cytometry on immunophenotypically gated HSCs.** This is the best way to measure the labile iron pool (LIP) in HSCs.

### Protocol and rationale

1. **Harvest and stain.** Flush femurs/tibiae/pelvis, lyse or density-deplete, deplete lineage⁺ cells (or stain directly), and stain the surface panel: lineage cocktail (CD3, CD4, CD8, B220, CD11b, Gr-1, Ter119), c-Kit (CD117), Sca-1, CD150, CD48, CD34, Flt3 (CD135), plus a viability dye (DAPI/7-AAD) and Fc block. This defines LT-HSC (LSK CD150⁺CD48⁻CD34⁻Flt3⁻), ST-HSC, MPP, and the progenitor compartments as internal comparators.
2. **Load a live-cell fluorescent iron probe.** Options, each read in a free channel:
 * **Calcein-AM (or calcein blue-AM)** — the classic LIP probe. Calcein-AM is cleaved intracellularly to fluorescent calcein, which is **quenched stoichiometrically by chelatable Fe²⁺/Fe³⁺**. The LIP is read as the *dequenching* (fluorescence increase, $\Delta F$) after addition of a strong membrane-permeant chelator such as deferiprone or SIH (salicylaldehyde isonicotinoyl hydrazone); $\Delta F$ is proportional to the labile iron concentration, calibrated against a standard curve of Fe-loaded cells or in-vitro calcein/Fe titration. Because the measurement is a *difference*, it corrects for cell-to-cell loading differences.
 * **Fe²⁺-selective turn-on probes — FeRhoNox-1 / RhoNox-1, or FIP-1 / "iron probes" of the N-oxide class** — non-fluorescent until deoxygenated specifically by labile Fe²⁺, giving a direct "more iron = brighter" readout; minimal interference from Ca²⁺/Zn²⁺/Cu²⁺ compared with calcein.
 * **Phen Green SK** — quenched by labile iron (dequench with chelator), an alternative to calcein.
3. **Read on the cytometer** (or by confocal imaging/ImageStream for subcellular localisation), gating on live, single, LT-HSC/ST-HSC/MPP/progenitor populations, and report probe fluorescence or $\Delta F_{\text{chelator}}$ per population as median fluorescence intensity.
4. **Essential controls/calibration:** iron-loaded cells (ferric ammonium citrate or hemin) as a positive control and chelator-treated cells (DFO/deferiprone/SIH) as a negative control, to bracket the dynamic range; unstained and single-stain controls; compensation; probe-only (no-cell) blanks; and confirmation that the probe does not itself chelate significantly during the incubation (short loading, low concentration).

### Why this is the right approach
* **It is the only method with the sensitivity and single-cell resolution needed.** The LIP is the small (~0.5–5 µM), redox-active, chelatable, cytosolic pool that is biologically relevant for proliferation, ROS production and Fenton chemistry — and it is exactly the pool that fluorescent probes report. A fluorescent probe plus flow cytometry can quantify it in **rare, prospectively gated populations of a few hundred to a few thousand cells**, and simultaneously in each neighbouring progenitor compartment on the same sample.
* **Alternatives are inadequate on their own and serve only as orthogonal/bulk confirmation:** ICP-MS or colorimetric ferrozine assays measure *total* (not labile) iron and need ~10⁵–10⁶ cells, so they are impractical for LT-HSCs and cannot distinguish the labile pool from ferritin- and heme-bound iron; Mössbauer/EPR and ²⁵Mg/⁵⁷Fe tracing are bulk methods; Perls' Prussian blue/ferritin IHC detects only storage iron aggregates; and transcriptional surrogates (IRP1/IRP2–IRE activity, *Tfrc* up / *Fth1-Ftl* down, as read by qPCR or RNA-seq on sorted cells) are indirect inference, useful as corroboration. A reasonable package is therefore: **fluorescent probe + flow cytometry as the primary measurement**, with ICP-MS on sorted pooled cells, intracellular ferritin staining, and IRP/IRE target gene expression as supporting orthogonal evidence.

---

## 2. Measuring Transferrin Receptor 1 (CD71/Tfr1), and what to expect

### Final answer
**Measure CD71 both as surface protein by flow cytometry and as transcript by mRNA quantification (qRT-PCR or RNA-seq on sorted HSCs).** And the expectation is nuanced: **surface CD71 on HSCs is low, yet Tfr1 is highly expressed in HSCs** (high transcript and high total/intracellular protein).

### How to measure it

1. **Flow cytometry for surface CD71.** Add a fluorochrome-conjugated anti-mouse CD71 antibody (clone R17217/RI7217 or 8D3) to the HSC panel above and quantify MFI on gated LT-HSC/ST-HSC/MPP/CMP/MEP/erythroblast populations. Titrate the antibody; include an isotype/FMO control and a positive control population (Ter119⁺ CD71^hi erythroid precursors, which are the brightest CD71 cells in marrow and set the top of the scale); quantify in absolute terms with calibration beads (molecules of equivalent soluble fluorochrome, or Quantum Simply Cellular beads to estimate receptors per cell).
2. **Total versus surface protein.** Because surface and total pools dissociate (see below), also measure (i) **total CD71 by intracellular/permeabilised flow cytometry** (fix/perm, stain with the same or an intracellular-validated antibody) or imaging flow cytometry to localise receptor in endosomal compartments; (ii) **surface-restricted quantification** by labelling at 4 °C only, or by acid-strip/trypsin controls; (iii) **functional uptake** with fluorescent holo-transferrin (Alexa-Tf) uptake assays at 37 °C versus 4 °C, which measures Tfr1-dependent iron import flux rather than static receptor number; and (iv) western blot or intracellular staining on sorted, pooled cells where numbers permit.
3. **mRNA quantification.** FACS-sort LT-HSCs directly into lysis buffer and quantify ***Tfrc*** mRNA by **qRT-PCR** (relative to *Actb*/*Gapdh*/*Hprt*), by low-input/Smart-seq2 **RNA-seq**, by single-cell RNA-seq (which also gives the distribution across the compartment), or by RNA-FISH/nCounter. This is essential because it reports the transcriptional/IRP-driven state of the iron-import machinery independently of receptor trafficking.

### What to expect, and why
* **Surface CD71 is low on HSCs.** Phenotypically, HSCs are routinely found in the CD71^low/− fraction; quiescent LT-HSCs are not proliferating, do not have the enormous heme-synthesis demand of erythroid cells, and keep a smaller amount of receptor displayed at the plasma membrane. The classic contrast is erythroid precursors (CD71^hi Ter119⁺), which are 1–2 orders of magnitude brighter. Flow cytometry alone therefore gives the misleading impression that HSCs do not use transferrin-mediated iron import.
* **Nevertheless, Tfr1 is highly expressed in HSCs.** At the level of transcript and total cellular protein, *Tfrc*/Tfr1 is abundantly — indeed highly — expressed in HSCs: iron import through Tfr1 is required for HSC maintenance and for their proliferative/regenerative capacity, HSCs are iron-dependent, and *Tfrc* deletion impairs HSC function. The resolution of the apparent paradox is that in HSCs much of the receptor pool is **intracellular/endosomally recycling rather than displayed at the surface**, and the IRP–IRE system holds *Tfrc* mRNA stable (IRPs bound to the 3′ UTR IREs) in the relatively iron-restricted, low-LIP state of a quiescent HSC. Hence the methodological point: **surface flow cytometry must be combined with mRNA quantification (and total-protein/uptake measurements)**, or the conclusion drawn will be wrong.
* **Prediction to be tested:** low surface CD71 MFI on LT-HSC, rising sharply along differentiation into MPP → CMP → MEP → proerythroblast; high *Tfrc* mRNA in LT-HSC; and transferrin uptake capacity in HSCs that is higher than surface staining alone would predict. Iron chelation should further increase *Tfrc* mRNA and surface CD71 (IRP-mediated stabilisation), which is a useful internal control for the chelation experiments in §3.

---

## 3. Iron chelation *in vivo*: DFO versus DFX, read-outs, and predictions

### 3.1 Choice of chelator — **deferoxamine (DFO)**

**Final answer: choose DFO.** The decisive reason is efficacy in the compartment under study: **DFO has greater efficacy for the bone marrow microenvironment**, which is precisely the niche in which HSCs reside and the site at which the labile iron pool of HSCs and their supporting stromal/macrophage/erythroblastic-island cells must be lowered. DFO is a hexadentate siderophore that binds Fe³⁺ 1:1 with extremely high affinity ($K_a \sim 10^{31}$ M⁻¹), efficiently strips the chelatable/labile pool and is well validated for depleting marrow iron in mouse models, giving a robust, interpretable reduction of the HSC labile iron pool.

Side-effect and pharmacology comparison supporting this choice:

| | **DFO (deferoxamine)** | **DFX (deferasirox)** |
|---|---|---|
| Route / schedule | Parenteral (s.c./i.p./infusion); short plasma $t_{1/2}$ (~20–30 min) so repeated or continuous dosing / osmotic minipump is needed | Oral, once daily, long $t_{1/2}$ (~8–16 h) — more convenient |
| Denticity / stoichiometry | Hexadentate, 1:1 with Fe³⁺ | Tridentate, 2:1 — more prone to forming redox-active partial complexes |
| **Efficacy in bone marrow** | **Greater efficacy in the bone marrow microenvironment** — the key criterion here | More tissue-distributed with strong hepatic (and cardiac) iron removal, less well suited to the marrow compartment |
| Key toxicities | Local injection-site reactions, ocular/auditory toxicity and growth effects at high cumulative dose, rare *Yersinia* infections; **does not cause the hematologic/renal toxicities that confound HSC read-outs** | **Nephrotoxicity (rising creatinine, renal tubulopathy, Fanconi syndrome), hepatotoxicity, GI haemorrhage, and — critically — cytopenias/agranulocytosis and reports of marrow suppression**; off-target effects including NF-κB inhibition and mTOR effects |
| Confounding for this experiment | Minimal: its effects on HSCs can be attributed to iron chelation | Severe: any change in HSC number, cycling or engraftment could be a direct drug toxicity on hematopoiesis or a secondary consequence of renal/hepatic injury and inflammation, not of iron chelation |

So DFX's oral convenience is outweighed by (i) lower efficacy in the marrow niche and (ii) a side-effect profile — cytopenias/agranulocytosis, renal and hepatic toxicity — that directly confounds hematopoietic end-points. **DFO is the chelator of choice for this model.** (Practical design: DFO 100–200 mg/kg/day s.c. or i.p., or continuous minipump, for 2–4 weeks, with vehicle controls; confirm target engagement by the labile-iron probe assay of §1, reduced ferritin, increased *Tfrc*/surface CD71, and IRP-target gene changes; monitor haemoglobin, reticulocytes and body weight to exclude frank iron-deficiency anaemia, and include a low-iron-diet arm as an orthogonal iron-restriction comparator.)

### 3.2 Parameters to measure — **ex vivo culture models and bone-marrow transplantation are the best ways to measure the effect of iron chelation on HSCs**

Functional stem-cell capacity cannot be inferred from phenotype alone, so the two pillars are:

**(a) *Ex vivo* culture models**
* **LTC-IC (long-term culture-initiating cell) assay** — the central read-out. Marrow or sorted HSPCs from DFO- versus vehicle-treated mice are plated on a pre-established stromal feeder layer (M2-10B4/S17, or irradiated primary stroma) under Dexter-type long-term culture conditions for 5 weeks, after which the culture is harvested and replated in semi-solid methylcellulose with cytokines; the colonies produced measure the frequency of primitive cells that survived and sustained 5 weeks of culture. Quantify LTC-IC frequency by limiting-dilution analysis with Poisson statistics.
* **CFU-C / CFU-GEMM colony assays** (methylcellulose + SCF, IL-3, IL-6, EPO, GM-CSF) for lineage output and progenitor number; **serial replating** for self-renewal capacity.
* **Liquid expansion/ex vivo maintenance cultures** (SCF + TPO ± polyvinyl alcohol) with periodic LSK/SLAM phenotyping, division tracking (CFSE/H2B-GFP label retention), cell-cycle (Ki-67/DAPI, EdU/BrdU), apoptosis (Annexin V), ROS (CellROX/DCFDA), mitochondrial membrane potential (TMRM) and metabolic flux (Seahorse OCR/ECAR on sorted cells).
* **Cobblestone-area-forming cell (CAFC)** assay as an additional primitive-cell read-out.

**(b) Bone-marrow transplantation (the definitive *in vivo* test of HSC function)**
* **Competitive repopulation:** transplant a fixed number of sorted LT-HSCs (or whole BM) from DFO- versus vehicle-treated CD45.2 donors together with CD45.1 competitor marrow into lethally irradiated recipients; track donor chimerism in blood at 4, 8, 12, 16 weeks and in marrow at 16+ weeks, with multilineage (myeloid/B/T) analysis.
* **Limiting-dilution transplantation** to obtain the absolute **competitive repopulating unit (CRU)/HSC frequency** by Poisson/ELDA analysis.
* **Serial (secondary and tertiary) transplantation** to test self-renewal and long-term durability.
* **Stress/regeneration challenges:** 5-FU or irradiation recovery, and transplantation into non-conditioned or niche-manipulated hosts.
* Supporting phenotypic parameters: absolute numbers and frequencies of LT-HSC/ST-HSC/MPP/LSK/CMP/GMP/MEP, HSC quiescence (G0 fraction), homing efficiency, and niche parameters (CXCL12-abundant reticular cells, macrophages, endosteal/vascular localisation by imaging).

### 3.3 Expected effect

**Iron chelation will increase the regenerative capacity of HSCs, and this will be seen most clearly as an increase in LTC-IC** — i.e. DFO-treated marrow yields a higher frequency of long-term-culture-initiating cells, indicating expansion/preservation of the primitive, self-renewing compartment. Correspondingly, expect:

* **Higher LTC-IC frequency** (the primary expectation) and greater colony output on replating;
* **Enhanced engraftment and higher donor chimerism** in competitive transplantation, higher CRU frequency by limiting dilution, and preserved or improved secondary/serial transplant capacity — i.e. improved self-renewal and regenerative/proliferative capacity;
* **Mechanistic correlates:** reduced labile iron pool, lower ROS and oxidative damage (less Fenton chemistry), better maintained quiescence/stress resistance, improved mitochondrial health, and the epigenetic and metabolic reprogramming detailed in §§4–5;
* Caveats to control for: excessive/prolonged chelation produces functional iron deficiency, impaired erythropoiesis and ultimately reduced HSPC output, so a dose–response and duration series is required to stay within the window where chelation is beneficial; and effects may be partly niche-mediated, which is why both *ex vivo* (cell-intrinsic, on defined feeders) and transplantation (in vivo, niche-dependent) read-outs are needed.

---

## 4. Interpreting the histone-acetylation signature: Tip60 and Myc

### The signature
Enrichment of genes decorated with **H2A.Zac (acetylated H2A.Z), H4K5ac, H4K8ac, H4K12ac and H4K16ac** is a highly specific fingerprint. H4K5/K8/K12/K16 are the four acetylatable lysines of the histone H4 N-terminal tail, and acetylated H2A.Z is a hallmark of a particular acetyltransferase complex. The single enzyme that acetylates **both the full H4 N-terminal lysine set (K5, K8, K12, K16) and H2A/H2A.Z** is the MYST-family lysine acetyltransferase **KAT5 — Tip60** — the catalytic subunit of the **NuA4/TIP60** complex (with TRRAP, EPC1, DMAP1, BRD8, MRG15, ING3, and the H2A.Z-exchange machinery p400/EP400, which deposits and acetylates H2A.Z).

### Final answers
* **Regulatory protein expected to be activated after IC treatment of HSPCs: Tip60 (KAT5/NuA4–TIP60 complex).** The combination of H4K5ac/K8ac/K12ac/K16ac *and* H2A.Z acetylation at the enriched genes is diagnostic of Tip60 acetyltransferase activity, so iron chelation is predicted to activate Tip60, which opens chromatin (H4K16ac in particular decompacts nucleosome arrays and blocks Sir2/SIRT-mediated compaction) at genes that drive HSC proliferative and regenerative programmes.
* **Other transcription factor expected to also be activated after IC: Myc (c-Myc).** Tip60/NuA4 is the canonical **c-Myc coactivator complex** — c-Myc recruits TRRAP–Tip60 to E-box promoters, and Tip60-dependent H4 and H2A.Z acetylation is the chromatin consequence of Myc binding. Therefore **Myc activity is expected to be upregulated after iron chelation**, acting together with Tip60 on the same target genes. This is mechanistically coherent: Myc is the master regulator of HSC self-renewal versus differentiation, of ribosome biogenesis and cell-cycle entry, and of metabolic genes — including fatty-acid and mitochondrial metabolism genes (see §5) — which links the epigenetic signature directly to the metabolic shift and to the increased regenerative capacity measured by LTC-IC and transplantation.

### How to verify
ChIP-seq/CUT&RUN for Tip60/KAT5, c-Myc, H4K16ac and H2A.Zac on sorted HSPCs ± DFO (checking co-occupancy at the enriched gene set and E-box enrichment by motif analysis); Myc target-gene signature by RNA-seq/GSEA; Myc reporter or *Myc*-GFP knock-in mice; functional tests with the Tip60 inhibitor NU9056/TH1834 or *Kat5* conditional knockout and with Myc inhibition (Omomyc, MYCi975) or *Myc* deletion — each of which should abolish the chelation-induced gain in LTC-IC and engraftment if the axis is causal; co-IP of Tip60 with TRRAP/c-Myc.

---

## 5. Metabolic consequences of iron chelation in HSCs

### 5.1 Pathway expected to be upregulated: **fatty-acid oxidation (FAO)**

**Final answer: fatty-acid oxidation (fatty-acid β-oxidation / lipid catabolism) is the pathway expected to be upregulated in HSCs following iron chelation.** Rationale:

* HSCs are normally glycolytic and hypoxic (HIF-1α-driven, PDK2/4-high), but **self-renewal specifically depends on FAO** through the PPARδ–CPT1a axis (and on PML–PPARδ signalling), which promotes asymmetric division and preserves stem-cell identity.
* Iron chelation lowers the labile iron pool and thereby both reduces Fenton-driven ROS and alters the activity of iron-dependent enzymes and iron-sulfur cluster assembly; cells compensate by remodelling fuel use towards lipid catabolism.
* The Tip60/Myc axis identified in §4 directly transactivates genes of mitochondrial and fatty-acid metabolism, providing the transcriptional mechanism; H4K16ac/H2A.Zac-marked, Myc-bound promoters are predicted to be enriched for FAO genes (*Cpt1a*, *Acadm/Acadl*, *Hadha/b*, *Acox1*, *Ppard*, *Acsl* family, *Plin2*, *Lipe/Pnpla2*).
* Expected measurements: increased CPT1a and FAO gene expression; increased palmitate-driven oxygen consumption rate on Seahorse (and sensitivity of that OCR to etomoxir); increased ¹⁴C-palmitate oxidation; increased acylcarnitines (LC-MS); increased lipid-droplet content with increased lipolytic flux.

### 5.2 Would glycolytic inhibition counteract the effect of IC? — **No**

**Final answer: no — inhibiting glycolysis is not expected to counteract (reverse) the beneficial effect of iron chelation on HSCs.** Because the chelation-induced gain in HSC regenerative capacity is driven by a shift *towards* fatty-acid oxidation rather than by glycolysis, blocking glycolysis (2-deoxy-D-glucose, glucose withdrawal, or inhibition of hexokinase/GLUT1/PKM2/LDHA) removes a fuel pathway that the chelation effect does not depend upon. The enhanced LTC-IC/engraftment phenotype should therefore persist essentially intact under glycolytic inhibition (and, if anything, glycolytic restriction can further bias HSCs towards the FAO/self-renewal programme, since glycolysis is more closely tied to proliferation and differentiation-associated biosynthesis). Practically: DFO ± 2-DG, with LTC-IC and competitive transplantation as the read-out, is predicted to show no loss of the DFO benefit.

### 5.3 Would FAO inhibition counteract the effect of IC? — **Yes**

**Final answer: yes — FAO inhibition will negatively impact (abrogate) the effect of iron chelation on HSCs.** Blocking β-oxidation at the rate-limiting mitochondrial import step with **etomoxir** (CPT1 inhibitor), with the CPT1a-sparing alternative perhexiline, by *Cpt1a* knockdown/knockout, or by PPARδ antagonism, removes the very pathway through which chelation acts. Predicted outcome of DFO + etomoxir: loss of the increase in LTC-IC frequency, loss of the enhanced engraftment/CRU frequency in competitive and serial transplantation, loss of the preserved quiescence/asymmetric-division phenotype, and reversion towards (or below) vehicle-level HSC function. **This epistasis experiment — FAO inhibition abolishes the chelation benefit whereas glycolytic inhibition does not — is the decisive demonstration that FAO is the effector pathway of iron chelation in HSCs.**

### 5.4 Increased glucose or fatty-acid storage? — **Increased fatty-acid storage (lipid droplets), not glucose storage**

**Final answer: HSCs treated with iron chelation will have increased *fatty-acid* storage — specifically higher lipid-droplet storage of fatty acids — but not increased glucose storage.** Together with §5.1, the prediction is of a **lipid-centred remodelling with increased fatty-acid turnover**: chelation-treated HSCs take up and esterify more fatty acids into triacylglycerol within lipid droplets, and simultaneously mobilise them faster by lipolysis into mitochondrial β-oxidation. Lipid droplets act as the buffering depot that feeds a higher FAO flux, so **fatty-acid turnover (uptake → esterification → lipolysis → β-oxidation) is increased** in IC-treated HSCs, with droplet number/size up and no accumulation of glucose-derived stores.

Conversely, **glucose storage is not increased**: glycogen and glucose-derived carbon stores should be unchanged or reduced, consistent with the shift away from glycolytic fuel use, with glucose carbon not being the pathway through which chelation enhances HSC function (compare the result in §5.2 that glycolytic inhibition does not counteract the effect).

**How to measure:** BODIPY 493/503, LipidTOX or Nile Red staining plus perilipin-2 (PLIN2) for lipid droplets by flow cytometry and confocal/electron microscopy on sorted HSCs; BODIPY-C16 and ²H/¹³C-palmitate tracing for fatty-acid uptake and turnover; lipidomics (TAG species) by LC-MS; acylcarnitine profiling and ¹⁴C-palmitate oxidation for flux; and, for the glucose arm, 2-NBDG uptake, glycogen (periodic-acid Schiff or enzymatic glycogen assay), ¹³C-glucose tracing and ECAR — predicted to be flat or reduced.

---

## Summary of answers

1. **Labile iron in mouse HSCs:** fluorescent labile-iron probes (calcein-AM dequenching with deferiprone/SIH, FeRhoNox-1/RhoNox-1, Phen Green SK) read by **flow cytometry** on gated LT-HSC/ST-HSC/MPP populations — the only approach with single-cell sensitivity for such rare cells; ICP-MS, ferritin staining and IRP/IRE target genes as orthogonal support.
2. **CD71/Tfr1:** measure **surface CD71 by flow cytometry *and* *Tfrc* mRNA by qRT-PCR/RNA-seq on sorted cells** (plus total/intracellular protein and transferrin-uptake assays). Expectation: **surface CD71 is low on HSCs, but Tfr1 is highly expressed in HSCs** (high transcript/total protein, largely intracellular/recycling receptor).
3. **Chelator:** **DFO**, chosen specifically because **DFO has greater efficacy for the bone-marrow microenvironment** studied here, while DFX's cytopenias/agranulocytosis, nephrotoxicity and hepatotoxicity would confound hematopoietic end-points. Measure HSC function with **ex vivo culture models (LTC-IC, CFU, serial replating) and bone-marrow transplantation (competitive, limiting-dilution/CRU, serial)**, plus phenotype, cycling and ROS. Expected effect: **iron chelation increases the regenerative capacity of HSCs, evidenced by increased LTC-IC** (and enhanced engraftment/self-renewal).
4. **Epigenetics:** H2A.Zac + H4K5ac/K8ac/K12ac/K16ac is the signature of **Tip60 (KAT5/NuA4–TIP60)**, so Tip60 is the regulatory protein activated after IC; the other factor also activated is **Myc (c-Myc)**, whose activity is upregulated, consistent with Tip60/TRRAP being the c-Myc coactivator complex.
5. **Metabolism:** **fatty-acid oxidation is upregulated**; **glycolytic inhibition would not counteract** the effect of IC; **FAO inhibition (e.g. etomoxir) would negatively impact/abolish** it; and IC-treated HSCs show **increased fatty-acid turnover and higher lipid-droplet storage of fatty acids, but not increased glucose storage**.
