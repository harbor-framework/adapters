# Generating cell-type-specific Golgi-tagged mice and measuring the Golgi proteome, lipidome and metabolome in astrocytes, microglia, oligodendrocytes and neurons

## 1. Strategy overview

To study Golgi proteins, lipids and metabolites **specifically** in astrocytes (a), microglia (b), oligodendrocytes (c) and neurons (d), the student needs a way to (i) place an affinity handle on the Golgi membrane **only in one cell type at a time**, (ii) confirm that the handle is present and correctly localised, (iii) physically isolate intact Golgi from whole brain using that handle, and (iv) profile the isolated organelle by mass spectrometry.

The design therefore has three genetic components, which must be combined into one animal:

1. a **Cre-dependent Golgi Tag allele** — a Golgi membrane protein fused to an epitope tag, kept silent by a loxP-flanked STOP cassette;
2. a **Cre-dependent reporter allele** — to visualise and verify which cells have undergone recombination;
3. a **cell-type-specific Cre driver** — one per cell type of interest.

Because three alleles must be combined, the end product is a **triple transgenic mouse**, and the cleanest breeding route is to first build a stable double-transgenic "**Reporter-Golgi tag mouse**" line and then cross that line to each Cre driver.

The organelle isolation method is **Golgi immunopurification (GolgiIP / Golgi-IP)** — rapid immunocapture of tagged Golgi membranes from brain homogenate on anti-tag beads — which is what makes cell-type-specific organelle profiling from a complex tissue possible at all.

---

## 2. Step 1 — Obtain the Golgi Tag mouse

**For Golgi content to be measured, the transgenic mice that are generated must carry (and express) the Golgi Tag** — without a tagged Golgi membrane protein there is no affinity handle, and no cell-type-specific Golgi can be captured out of a brain homogenate. The Golgi Tag allele is therefore the indispensable component of the design and the first thing to secure.

**Golgi Tag allele (example): *Tmem115*-3×HA** — i.e. a **Tmem115-3xHA** knock-in/transgenic allele in which the Golgi membrane protein **TMEM115** is fused to a **3×HA (triple haemagglutinin) epitope tag**. TMEM115 is a multi-pass Golgi membrane protein that resides stably in Golgi (cis/medial-Golgi) membranes, so the 3×HA tag is displayed on the cytosolic face of intact Golgi membranes and is accessible to anti-HA antibodies without permeabilising or lysing the organelle. The tag is small, does not disturb Golgi morphology or function, and anti-HA immunocapture is high-affinity and highly specific.

The allele is made **Cre-dependent** by placing a **loxP-flanked STOP (LSL) cassette** upstream of the Tmem115-3×HA coding sequence, targeted to a defined locus (e.g. *Rosa26* or *Hipp11*) or expressed from the endogenous *Tmem115* locus with a conditional cassette. Consequently:

- **no Cre → no Golgi Tag expression** (silent allele, no background capture);
- **Cre present → excision of the STOP cassette → Tmem115-3×HA expressed, and only in Cre-expressing cells.**

(Equivalent Golgi tags that could be used in place of TMEM115-3×HA: GOLT1B-3×HA, GLG1/Golgin-84-3×HA, B4GALT1-3×HA, TGN38/TGOLN2-3×HA, GalNAc-T2-3×HA, or a 3×FLAG/3×Myc variant of any of these. The principle — an epitope-tagged, stably resident Golgi membrane protein under Cre control — is the same, and TMEM115-3×HA is the example used here.)

---

## 3. Step 2 — Obtain the reporter mouse

**A Cre-dependent reporter mouse must also be obtained**, so that recombination can be visualised directly in tissue and the cell-type specificity of each Cre driver can be verified independently of the tag.

**Reporter allele (examples):**
- **Rosa26-LSL-tdTomato (Ai14 / Ai9)** — the standard, bright, cytosolic red fluorescent Cre reporter;
- alternatives: **Rosa26-LSL-ZsGreen (Ai6)**, **Rosa26-LSL-EYFP**, **Rosa26-mT/mG** (membrane tdTomato → membrane EGFP switch, useful because it marks both recombined and non-recombined cells), or **Rosa26-LSL-GFP**.

In the examples below, **Ai14 (Rosa26-LSL-tdTomato)** is used as the reporter.

---

## 4. Step 3 — The first cross: generate the "Reporter-Golgi tag mouse"

**The first thing to do is to generate Golgi Tag reporter mice by crossing the Reporter mouse to the Golgi Tag mouse.**

$$\textbf{Reporter mouse (Rosa26-LSL-tdTomato / Ai14)} \;\times\; \textbf{Golgi Tag mouse (LSL-Tmem115-3×HA)}$$
$$\downarrow$$
$$\textbf{Reporter-Golgi tag mouse}\ \ (\text{LSL-tdTomato}^{+}\;;\;\text{LSL-Tmem115-3×HA}^{+})$$

Practical notes on this cross:

- Breed to obtain animals carrying **both** conditional alleles, ideally **homozygous for both** (LSL-Tmem115-3×HA^fl/fl^; Ai14^fl/fl^), so that every pup of the subsequent Cre cross inherits both alleles and no further segregation of these two alleles is needed.
- Genotype each generation by PCR for the Tmem115-3×HA allele (tag-specific and locus-junction primers) and for the Rosa26 reporter allele, distinguishing homozygotes from heterozygotes (or by ddPCR/qPCR copy-number assay).
- Confirm that, in the **absence of Cre**, these double-transgenic animals show **no tdTomato fluorescence and no HA signal** — i.e. that both STOP cassettes are intact and there is no leaky expression. This Cre-negative Reporter-Golgi tag animal is the essential negative control for every later experiment (both for immunofluorescence and for the immunopurification).

This double-transgenic line is the **"Reporter-Golgi tag mouse"**, and it is the common parental line used for all four cell types.

---

## 5. Step 4 — Obtain the four cell-type-specific Cre driver lines

Specific Cre lines must be obtained for each cell type of interest, chosen for specificity and (where possible) in inducible CreERT2 form so that recombination can be timed and off-target/developmental expression minimised.

**(a) Astrocyte-specific Cre mice** — obtain an astrocyte Cre line, for example **Aldh1l1-CreERT2** (highly astrocyte-specific, tamoxifen-inducible). Alternatives: **Aldh1l1-Cre**, **GFAP-Cre (hGFAP-Cre)**, **Slc1a3/GLAST-CreERT2**, **Aqp4-Cre**.

**(b) Microglia-specific Cre mice** — obtain a microglial Cre line, for example **Cx3cr1-CreERT2** (tamoxifen-inducible; with a tamoxifen-to-analysis interval chosen so that short-lived peripheral monocytes are replaced and labelling is restricted to long-lived microglia). Alternatives: **Tmem119-CreERT2**, **P2ry12-CreER**, **Hexb-CreERT2**, **Sall1-CreERT2**, **Csf1r-Cre/LysM-Cre** (less specific).

**(c) Oligodendrocyte-specific Cre mice** — obtain an oligodendrocyte Cre line, for example **Cnp-Cre (Cnp1-Cre)**. Alternatives: **Mbp-Cre**, **Plp1-CreERT2**, **Mog-Cre**, **Sox10-Cre**, **Olig2-Cre**, or **Pdgfra-CreERT2** if oligodendrocyte precursor cells are wanted.

**(d) Neuron-specific Cre mice** — obtain a neuronal Cre line, for example **Syn1-Cre (synapsin I-Cre)**, which drives pan-neuronal recombination. Alternatives: **Snap25-Cre**, **Camk2a-Cre** (excitatory forebrain neurons), **NeuroD6/Nex-Cre**, **Baf53b-Cre**, **Gad2-Cre** or **Vgat-Cre/Slc32a1-Cre** (inhibitory neurons), **Slc17a7/Vglut1-Cre** (excitatory neurons).

---

## 6. Step 5 — The second cross: generate the cell-type-specific, triple transgenic Golgi mice

**The "Reporter-Golgi tag mouse" is then crossed with each specific Cre mouse line to obtain the cell-type-specific Golgi mice — producing triple transgenic mice.**

$$\textbf{Reporter-Golgi tag mouse}\ (\text{LSL-tdTomato};\ \text{LSL-Tmem115-3×HA}) \;\times\; \textbf{cell-type-specific Cre mouse}$$
$$\downarrow$$
$$\textbf{Triple transgenic mouse: Cre}^{+}\;;\;\text{LSL-tdTomato}^{+}\;;\;\text{LSL-Tmem115-3×HA}^{+}$$

**Triple transgenic mice will therefore be generated** — carrying (1) the cell-type-specific Cre, (2) the Cre-dependent reporter and (3) the Cre-dependent Golgi tag — one line per cell type:

| Cell type | Triple transgenic genotype |
|---|---|
| **(a) Astrocytes** | **Aldh1l1-CreERT2**; Rosa26-LSL-tdTomato; LSL-Tmem115-3×HA |
| **(b) Microglia** | **Cx3cr1-CreERT2**; Rosa26-LSL-tdTomato; LSL-Tmem115-3×HA |
| **(c) Oligodendrocytes** | **Cnp-Cre**; Rosa26-LSL-tdTomato; LSL-Tmem115-3×HA |
| **(d) Neurons** | **Syn1-Cre**; Rosa26-LSL-tdTomato; LSL-Tmem115-3×HA |

In each line, Cre excises both STOP cassettes **only in the targeted cell type**, so that cell type — and only that cell type — expresses **tdTomato** (visual reporter) and **TMEM115-3×HA** on its Golgi membranes. For the CreERT2 lines, tamoxifen is administered (e.g. 2 mg/day i.p. or by oral gavage for 5 days) and animals are analysed after a defined interval.

**Controls to breed in parallel:** Cre-negative littermates (LSL-tdTomato; LSL-Tmem115-3×HA, no Cre) as the "no-tag" negative control for the immunopurification, plus, where available, a ubiquitously expressing (e.g. CAG-Cre or CMV-Cre) Tmem115-3×HA animal as a positive control for whole-brain Golgi capture.

---

## 7. Step 6 — Validate the mice: confirm the reporter and confirm the Golgi tag

Before any organelle isolation, two things must be verified in each triple-transgenic line: that recombination occurred in the intended cell type, and that the Golgi tag is expressed and correctly localised.

### 7.1 Immunofluorescence to confirm the presence of the reporter

**An immunofluorescence (IF) assay is used to confirm the presence of the reporter.** On fixed brain sections (perfusion-fixed, cryosectioned) from each triple-transgenic line:

- image the **tdTomato reporter** signal directly, and/or stain with an anti-RFP/anti-tdTomato antibody, to confirm that the reporter is expressed and to map which cells have recombined;
- **co-stain with cell-type markers** to confirm specificity: **S100β/ALDH1L1/GFAP/GS** for astrocytes, **IBA1/P2RY12/TMEM119** for microglia, **OLIG2/CC1(APC)/MBP/CNPase** for oligodendrocytes, **NeuN/MAP2/βIII-tubulin** for neurons;
- quantify **specificity** (fraction of reporter⁺ cells that are the intended cell type) and **efficiency/penetrance** (fraction of the intended cell type that is reporter⁺) across several brain regions, and confirm the absence of reporter signal in Cre-negative littermates.

### 7.2 Immunofluorescence to confirm correct Golgi localisation of the tag

In the same sections, **co-immunostain for the HA tag** (anti-HA) together with:
- an independent **Golgi marker** — **GM130 (GOLGA2)**, **giantin**, **golgin-97**, **TGN38/TGOLN2** or **GalNAc-T2** — to confirm that the HA signal shows the expected perinuclear, ribbon/stack Golgi morphology and **co-localises with endogenous Golgi markers**; and
- the **cell-type marker** and the **tdTomato reporter**, to confirm that HA is confined to the intended cell type.

### 7.3 Western blot (and other techniques) to confirm presence of the Golgi tag

**Western blotting, together with other complementary techniques, is used to confirm the presence of the "Golgi tag" (TMEM115-3×HA)**:

- **Western blot (immunoblot)** of brain lysates from each triple-transgenic line with **anti-HA antibody**, confirming a band of the expected molecular weight for TMEM115-3×HA, present in Cre⁺ animals and **absent in Cre-negative littermates** (demonstrating both expression and the absence of leaky expression);
- **immunoblot for TMEM115** itself, to compare tagged and endogenous protein levels and confirm that tagging has not altered abundance;
- **additional confirmatory techniques:** PCR/ddPCR genotyping and Sanger sequencing of the recombined allele; **RT-qPCR** for the tag transcript; **immunoprecipitation followed by immunoblot or mass spectrometry** showing that anti-HA beads capture TMEM115-3×HA together with other Golgi proteins; **flow cytometry** of dissociated brain cells for tdTomato to quantify the labelled population; and **immuno-electron microscopy** or anti-HA immunogold labelling to confirm localisation to Golgi membranes at ultrastructural resolution.

Only once the reporter and the Golgi tag are both confirmed should the organelle isolation proceed.

---

## 8. Step 7 — Golgi immunopurification (GolgiIP): the main method for isolating cell-type-specific Golgi from brain

**Golgi immunopurification (Golgi-IP / GolgiIP, i.e. immunoprecipitation of the tagged Golgi) is the main method used to pull down Golgi from specific cell types out of the brain.** This is the core of the whole approach: a brain contains all cell types mixed together, and only immunocapture via the cell-type-restricted epitope tag can isolate the Golgi belonging to one of them. Classical density-gradient Golgi fractionation cannot do this, because it separates organelles by physical properties and is blind to cell type.

**Protocol:**

1. **Harvest and homogenise rapidly and gently.** Euthanise the animal, rapidly dissect the brain (or the region of interest — cortex, hippocampus, cerebellum, white matter), and homogenise in ice-cold, iso-osmotic KPBS/sucrose-based buffer (e.g. 136 mM KCl, 10 mM KH₂PO₄, pH 7.25, or 0.25 M sucrose/HEPES) with protease and phosphatase inhibitors, using a Dounce homogeniser or gentle mechanical disruption — **no detergent**, so that Golgi membranes remain intact and their luminal contents are retained. Keep everything at 4 °C and work fast (the entire capture should be completed within ~10–20 min of homogenisation) to preserve labile metabolites.
2. **Clear the homogenate** by low-speed centrifugation (e.g. 1,000 × g, 2 min) to remove nuclei, unbroken cells and debris; retain the post-nuclear supernatant.
3. **Immunocapture.** Incubate the post-nuclear supernatant with **anti-HA-conjugated magnetic beads** (e.g. anti-HA Dynabeads/Pierce anti-HA magnetic beads) for a short, defined period (~3–15 min) with gentle rotation at 4 °C. The 3×HA tag on the cytosolic face of TMEM115 is captured, bringing down intact Golgi membranes derived **only from the Cre-expressing cell type**.
4. **Wash** the beads several times in the same iso-osmotic, detergent-free buffer to remove unbound organelles and cytosol, using a magnetic rack and minimal handling.
5. **Elute/process according to the downstream read-out:** lyse the captured Golgi in a mass-spectrometry-compatible buffer for proteomics; quench in cold organic solvent (e.g. 80% methanol, or methanol/chloroform) directly on the beads for metabolomics; and extract with chloroform/methanol (Folch/Bligh–Dyer or MTBE) for lipidomics. For immunoblot validation, elute in SDS sample buffer or with HA peptide.

**Essential controls for the IP:**
- **Cre-negative (tag-less) littermate** processed identically — defines the non-specific background that binds the beads, and every downstream hit must be enriched over this control;
- **bead-only / IgG-conjugated bead** controls;
- a **ubiquitous-Cre (CAG-Cre) Tmem115-3×HA** positive control;
- **input, unbound and bead fractions** retained at every step for quantitative recovery and enrichment calculations.

---

## 9. Step 8 — Confirm purity: blot for non-Golgi organelle markers

**Other, non-Golgi organelle markers must be blotted for (or otherwise measured) to confirm that no contamination occurred during the Golgi purification.** This is indispensable: Golgi membranes are physically and functionally continuous with the ER and the endolysosomal system through vesicular traffic, and mitochondria, lysosomes and ER membranes can co-sediment or adhere non-specifically to beads. Without a purity assessment, any protein, lipid or metabolite detected could belong to a contaminating organelle rather than to the Golgi, and the entire data set would be uninterpretable.

**Western blot the input, unbound and Golgi-IP (bead) fractions for:**

| Compartment | Marker to blot |
|---|---|
| **Golgi (should be strongly enriched)** | **GM130/GOLGA2, giantin (GOLGB1), golgin-97, TGN38/TGOLN2, GalNAc-T2, B4GALT1, TMEM115/HA** |
| **Lysosome (should be absent/depleted)** | **LAMP1, LAMP2, cathepsin D, TMEM192, V-ATPase subunits** |
| **Mitochondria** | **TOM20, VDAC1, COXIV, CS, ATP5A** |
| **Endoplasmic reticulum** | **calnexin, PDI, BiP/HSPA5, SEC61B, RTN4** |
| **Early/recycling endosome** | **EEA1, RAB5, RAB11, transferrin receptor** |
| **Peroxisome** | **catalase, PMP70/ABCD3** |
| **Nucleus** | **lamin B1, histone H3, TBP** |
| **Cytosol** | **GAPDH, β-actin, LDH, tubulin** |
| **Plasma membrane** | **Na⁺/K⁺-ATPase (ATP1A1), transferrin receptor, cadherin** |

The expected and required result is **strong enrichment of Golgi markers with depletion (ideally absence) of all of the non-Golgi markers** in the Golgi-IP fraction relative to input, and relative to the Cre-negative control IP. These blots should be quantified (enrichment ratios) and reported.

**Complementary purity checks:** mass-spectrometry-based purity assessment (compare the recovered proteome against curated organelle-marker lists — e.g. the fraction of identified proteins annotated as Golgi versus lysosomal, mitochondrial or ER); **electron microscopy** of the bead-bound material to confirm intact Golgi stacks/cisternae and the absence of mitochondria and other organelles; **enzyme-activity assays** for compartment-specific enzymes (galactosyltransferase/sialyltransferase for Golgi; β-hexosaminidase/acid phosphatase for lysosomes; citrate synthase for mitochondria; glucose-6-phosphatase for ER); and confirmation of **cell-type specificity** of the captured material by blotting/mass-spectrometric detection of cell-type-restricted proteins (e.g. absence of microglial proteins in the neuronal Golgi-IP and vice versa).

---

## 10. Step 9 — Measuring Golgi proteins, lipids and metabolites from each cell type

With purity established, the captured, cell-type-specific Golgi is split for the three "omics" read-outs. Each measurement must be reported as enrichment over the **Cre-negative control IP** and normalised to Golgi marker recovery.

### 10.1 Proteins — proteomics

**Proteomics is used to identify the proteins present in the cell-type-specific Golgi.** Solubilise the bead-bound Golgi (e.g. in 8 M urea or SDS/SDC with reduction and alkylation), digest with trypsin/Lys-C (in-solution, on-bead, FASP or S-Trap), and analyse by **LC-MS/MS on a high-resolution instrument (Orbitrap/timsTOF)**. Use **quantitative strategies**: label-free quantification (LFQ/DIA) or isobaric labelling (**TMT/iTRAQ**) to compare the four cell types directly in one multiplexed experiment, and **SILAC/spike-in standards** where absolute quantification is needed. Downstream: search against the mouse proteome, filter against the tag-less control, annotate Golgi residency, and perform GO/pathway and glycosylation-enzyme-focused analyses. Phospho- and glyco-proteomics can be layered on if post-translational regulation of Golgi enzymes is of interest. (Immunoblotting of selected hits provides orthogonal validation.)

### 10.2 Lipids — lipidomics

**Lipidomics is used to identify the lipids in the cell-type-specific Golgi regions.** Extract lipids directly from the bead-bound Golgi using a chloroform/methanol (Bligh–Dyer or Folch) or **MTBE** extraction, with class-specific stable-isotope-labelled internal standards (e.g. SPLASH LipidoMix) added before extraction. Analyse by **LC-MS/MS (reverse-phase or HILIC) on a high-resolution instrument**, in both positive and negative ion modes, or by shotgun lipidomics; use MS/MS for species-level identification of acyl chains. This profiles the Golgi lipidome of each cell type: **sphingolipids (ceramide, sphingomyelin, glucosyl/galactosylceramide, gangliosides — of particular interest in oligodendrocytes and neurons), glycerophospholipids (PC, PE, PS, PI, PA), cholesterol and cholesteryl esters, diacylglycerol, and glycosphingolipid intermediates**, which are synthesised and remodelled in the Golgi.

### 10.3 Metabolites — metabolomics

**Metabolomics is used to identify the metabolites in the cell-type-specific Golgi regions.** Quench metabolism immediately on the beads with ice-cold 80% methanol (or methanol/acetonitrile/water), extract, dry and reconstitute, and analyse by **LC-MS/MS (reverse-phase and HILIC for polar metabolites) and/or GC-MS**, using both **targeted panels and untargeted high-resolution profiling**, with isotope-labelled internal standards and matched blanks. Targets of particular relevance to the Golgi include **nucleotide sugars and sugar donors (UDP-glucose, UDP-galactose, UDP-GlcNAc/GalNAc, CMP-sialic acid, GDP-fucose), sugar phosphates, PAPS (sulfation donor), nucleotides (ATP/ADP/AMP, UTP, CTP), amino acids and amine-containing metabolites**. Stable-isotope tracing (e.g. ¹³C-glucose, ¹⁵N-glutamine) can be combined with GolgiIP to measure compartment-specific flux.

**Experimental design for all three read-outs:** at least 3–5 biological replicates (independent animals) per cell type plus matched Cre-negative controls; randomised processing order and identical timing across genotypes; pooling of multiple animals per sample if Golgi yield from a rare cell type (e.g. microglia) is limiting; and consistent brain region, sex, age and (for CreERT2 lines) tamoxifen schedule.

---

## 11. Summary of the workflow

1. **Obtain the Golgi Tag mouse** — Cre-dependent **Tmem115-3×HA** (LSL-Tmem115-3×HA). The generated mice must carry the Golgi Tag, since Golgi content cannot otherwise be measured.
2. **Obtain the reporter mouse** — e.g. **Rosa26-LSL-tdTomato (Ai14)**.
3. **First cross — generate the Golgi Tag reporter mice: cross the Reporter mouse to the Golgi Tag mouse**, giving the double-transgenic **"Reporter-Golgi tag mouse"**.
4. **Obtain the four cell-type-specific Cre lines** — astrocytes **Aldh1l1-CreERT2**, microglia **Cx3cr1-CreERT2**, oligodendrocytes **Cnp-Cre**, neurons **Syn1-Cre**.
5. **Second cross — cross the "Reporter-Golgi tag mouse" with each specific Cre mouse** to obtain the cell-type-specific Golgi mice; these are **triple transgenic mice** (Cre + reporter + Golgi tag).
6. **Validate** — **immunofluorescence to confirm the reporter** (tdTomato ± anti-RFP, with cell-type markers) and HA/Golgi-marker co-localisation; **western blot (plus PCR, RT-qPCR, IP-blot, immuno-EM) to confirm presence of the Golgi tag**.
7. **Isolate the organelle — Golgi immunopurification (GolgiIP)** with anti-HA magnetic beads from fresh, detergent-free brain homogenate, with tag-less Cre-negative controls.
8. **Confirm purity — blot/measure non-Golgi organelle markers** (LAMP1/LAMP2, TOM20/VDAC/COXIV, calnexin/PDI, EEA1/RAB5, catalase, lamin B1, GAPDH, Na⁺/K⁺-ATPase) alongside Golgi markers (GM130, giantin, golgin-97, TGN38) to show no contamination occurred during purification.
9. **Measure contents — proteomics** (LC-MS/MS, TMT/DIA) for Golgi **proteins**, **lipidomics** (LC-MS/MS after MTBE/Bligh–Dyer extraction) for Golgi **lipids**, and **metabolomics** (LC-MS/MS and GC-MS after cold methanol quench) for Golgi **metabolites** — in each case for astrocytes, microglia, oligodendrocytes and neurons separately, and in each case quantified relative to the Cre-negative control.
