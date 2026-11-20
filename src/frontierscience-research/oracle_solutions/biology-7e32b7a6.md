# HaloTag knock-in: interpreting the western blot, and validating an endogenously tagged receptor

## Reference values used throughout

* **HaloTag is a ~33 kDa (297 aa) modified haloalkane dehalogenase.** A single in-frame HaloTag therefore adds **≈33 kDa** to whatever polypeptide it is fused to.
* The blot was probed with an **anti-HaloTag antibody**. This is the single most important constraint on the interpretation: **every band on this blot must contain at least one HaloTag moiety.** An untagged allele product is invisible to this antibody.
* The loading control showed equal loading, so band differences are not a loading artefact.

---

# Part 1

## Step 1 — Arithmetic: what the band spacing tells us

Tabulating the data and the within-lane differences:

| Lane | Bands (kDa) | Within-lane difference |
|---|---|---|
| 1 | 73, 106 | **33 kDa** |
| 2 | 108 | – (single band) |
| 3 | 75, 108 | **33 kDa** |
| 4 | 80, 113 | **33 kDa** |

In every lane that has two bands, the two bands are separated by **exactly ~33 kDa — one HaloTag**.

Because the antibody only sees HaloTag, a doublet spaced by exactly one HaloTag mass cannot be "tagged vs. untagged protein". It must be **one HaloTag vs. two HaloTags in the same detected species**. Two HaloTag moieties in one species means **two separately translated, separately tagged polypeptides are travelling together as one complex**. Since all four cell lines were tagged at the *same* gene, that complex is a **dimer of the same protein — a homodimer**.

## Step 2 — Fitting a homodimer model

Let $m$ = mass of the untagged monomer. The species detectable with anti-HaloTag are then:

* **mono-tagged dimer** (one allele tagged, one not): $2m + 33$
* **bi-tagged dimer** (both alleles tagged): $2m + 66$
* (an untagged/untagged dimer, $2m$, exists but is invisible on this blot)

Solving each lane:

| Lane | Lower band $=2m+33$ | $\Rightarrow 2m$ | $\Rightarrow m$ (monomer) | Predicted $2m+66$ | Observed upper band |
|---|---|---|---|---|---|
| 1 | 73 | 40 | **20.0 kDa** | **106** | 106 ✔ |
| 2 | – | (42) | **21.0 kDa** | **108** | 108 ✔ |
| 3 | 75 | 42 | **21.0 kDa** | **108** | 108 ✔ |
| 4 | 80 | 47 | **23.5 kDa** | **113** | 113 ✔ |

The model fits all four lanes exactly, with no free parameters other than $m$. This internal consistency is strong evidence for the homodimer interpretation.

## Part 1A. What can we determine about this protein?

**(i) The HaloTag knock-in/transfection worked, and HaloTag is properly expressed in all four cell lines.** An anti-HaloTag antibody gives a specific signal in all four lanes, so in every species the donor HaloTag sequence was delivered, integrated at the target locus and is **transcribed, translated and stably expressed as an in-frame fusion**. Crucially, the HaloTag signal does **not** appear at ~33 kDa (free/cleaved HaloTag) nor as a smear of degradation products: it appears at higher masses that correspond to tag + protein. So the CRISPR-mediated knock-in produced a correctly fused, full-length, stable HaloTag–protein product rather than a truncation, a frameshift or free tag, and there is no evidence of tag cleavage. Transfection efficiency was sufficient and the single-cell sorting/expansion yielded HaloTag-expressing clones. (Expression level can be compared across lines because loading was equal.)

**(ii) The protein is very likely a homodimer (an obligate or at least a stable dimer).** Two independent arguments:

* The **within-lane 33 kDa spacing**, which — on an anti-HaloTag blot — can only mean two HaloTags, i.e. two tagged subunits, in one detected species.
* The **large absolute shift in kDa**: the detected species run at 73–113 kDa, i.e. roughly **twice** the ~20–23.5 kDa monomer plus tags. Even allowing generously for species-to-species differences in orthologue length (which account for only a few kDa, see Part 1B/1C), a shift of this magnitude cannot be explained by sequence divergence or by post-translational modification alone; it is the mass of a second subunit. The protein therefore self-associates into a **homodimer**, and the dimer is stable enough to survive lysis, purification and electrophoresis.

**(iii) It is a small protein (~20–24 kDa monomer) whose dimer is the predominant species**, and the tag does not prevent dimerisation — the HaloTag-fused subunits still assemble with each other and with untagged subunits, which is a reassuring (if preliminary) indication that the fusion is not grossly misfolded.

**(iv) The lines differ in zygosity of tagging** (see 1B/1C): lanes 1, 3 and 4 contain *both* mono-tagged and bi-tagged dimers, lane 2 contains only bi-tagged dimers.

## Part 1B. Likely reasoning for the varying kDa values in each of the lines

Two distinct sources of variation must be separated — *between*-lane variation and *within*-lane variation.

**(1) Within-lane variation (the 33 kDa doublet): incomplete transfection/editing, with only one allele tagged.** The most likely reason is that the knock-in was **not complete at both alleles**. Transfection and HDR-mediated knock-in are inefficient and stochastic, so a given clone may have received the HaloTag donor at **only one allele** (mono-allelic/heterozygous tagging), and the population may also be incompletely transfected or an incompletely resolved mixture despite single-cell sorting (sorting can fail to give true clonality, cells can be lost/doublets sorted, and clones can drift during expansion). In a heterozygous cell, tagged and untagged subunits are made simultaneously and assemble randomly, so dimers form binomially:

$$\text{TT}:\text{TU}:\text{UU} = 1:2:1$$

Of these, anti-HaloTag detects **TU** at $2m+33$ and **TT** at $2m+66$ (and is blind to UU), predicting a doublet with the lower band roughly twice as intense as the upper. Lanes 1, 3 and 4 show exactly this doublet pattern → **heterozygous (mono-allelically tagged) lines**. Lane 2 shows only the $2m+66$ species → a **homozygous (bi-allelically tagged) line**, in which every subunit carries a tag. (Other contributors to within-lane heterogeneity, which should be excluded: partial proteolysis of the tag or linker, incomplete reduction/denaturation, and alternative start/splice products.)

**(2) Between-lane variation (73/106 vs 108 vs 75/108 vs 80/113): species differences in the orthologue.** The fitted monomer masses are 20.0, 21.0, 21.0 and 23.5 kDa. Orthologues of the same protein differ in primary sequence length (insertions/deletions, divergent N-/C-termini, different isoform usage) and in **post-translational modification** — N- and O-linked glycosylation in particular differs markedly between species and between cell lines, as do phosphorylation, acetylation and ubiquitination — so the same protein legitimately runs a few kDa apart in different species. Because the HaloTag contribution is constant (33 kDa per tag), the between-lane offsets are carried entirely by the endogenous subunit mass. Note also that apparent mass on a gel is affected by charge/shape and by gel percentage, so small differences should be confirmed against predicted MW.

## Part 1C. Which lanes, if any, are likely from the same species?

**Lanes 2 and 3 are likely from the same species.**

* Lane 3: lower band 75 kDa → $2m+33$ → $2m = 42$ kDa; predicted bi-tagged dimer $2m+66 = 108$ kDa, which is exactly the observed upper band.
* Lane 2: single band at **108 kDa**, identical to lane 3's upper band, i.e. the same $2m = 42$ kDa.
* The difference between the two lanes is therefore **not** a difference in the protein but a difference in how many alleles carry the tag: **the variation in kDa is due to the addition of HaloTag to both protein alleles** in lane 2 (bi-allelic/homozygous knock-in → only the 108 kDa, two-HaloTag dimer), whereas **lane 3 is most consistent with cells that are heterozygous** for the HaloTagged protein (one allele tagged, one untagged → both the 75 kDa one-HaloTag dimer and the 108 kDa two-HaloTag dimer, the latter arising from pairing of two tagged subunits). Lane 3 could equivalently be a mixed/incompletely cloned population containing both heterozygous and homozygous cells.
* Lanes 1 ($2m = 40$ kDa; 73/106) and 4 ($2m = 47$ kDa; 80/113) give different subunit masses from each other and from lanes 2/3, so they are from **different species**. Confirmation would come from species-specific markers, STR/SNP profiling or sequencing of the locus, and from comparing observed masses with each species' predicted orthologue MW plus glycosylation state (PNGase F treatment).

## Part 1D. Two unspecified details needed to judge whether the experiment succeeded

**(1) A key detail about the protein: whether *both alleles* of the protein were tagged (the zygosity of the knock-in).** "Success" for an endogenous tagging experiment means every copy of the protein is tagged and reports faithfully on the endogenous pool; a heterozygous clone leaves an untagged allele whose product is invisible and which competes with the tagged subunit (especially for a dimer, where it generates mixed dimers). **This information cannot be obtained from this western blot, because the blot was probed for the HaloTag rather than with an antibody against the protein itself** — an anti-HaloTag blot is by definition blind to the untagged allele product, so absence of an untagged species proves nothing. Determining it requires either (a) re-probing with an **antibody against the protein of interest**, which would detect tagged *and* untagged subunits and reveal whether an untagged monomer/dimer band exists, or (b) genotyping the locus: PCR across the insertion site with primers flanking the homology arms, Sanger/NGS amplicon sequencing, ddPCR copy-number assay, or Southern blot to exclude additional/off-target integrations. One also needs to know the protein's predicted monomeric MW and native oligomeric state, since all of the mass arithmetic above depends on it.

**(2) A key experimental detail: the type of electrophoresis gel that was run.** We must know whether this was **SDS-PAGE** or **native (non-denaturing) PAGE**, and if SDS-PAGE, whether it was reducing or non-reducing. Knowing which gel type was used is essential to understand the protein's structure and its native size:

* **SDS-PAGE** denatures proteins with SDS (and, with DTT/β-ME, reduces disulfides), coating them with uniform negative charge, so polypeptides **separate essentially by molecular weight alone** and non-covalent complexes are dissociated. On SDS-PAGE, the observed 73–113 kDa species should be *monomeric* tagged subunits — which would make the homodimer interpretation untenable and would instead force us to conclude that the monomer is ~40–80 kDa, or that we are looking at covalently cross-linked/disulfide-linked species or SDS-resistant aggregates.
* **Native PAGE** keeps proteins in their natural, folded state, so they **separate according to molecular weight, structure (shape/hydrodynamic radius) and intrinsic charge**, and quaternary structure is preserved. Only on a native (or blue-native/clear-native) gel can a 106 kDa anti-HaloTag band legitimately be read as a non-covalent homodimer of two ~20 kDa subunits plus two 33 kDa tags.

Hence the same four lanes mean completely different things depending on gel type: the dimer conclusion (and therefore the whole judgement of whether the tagged protein assembles normally) is only valid under native conditions, while a clean single-species result under denaturing conditions would be the correct test of in-frame fusion and absence of free tag. Ideally both are run side by side (SDS-PAGE to verify fusion mass and integrity, native PAGE to verify the oligomeric state), together with a HaloTag-ligand (e.g. TMR) in-gel fluorescence read-out as an orthogonal confirmation.

---

# Part 2. An endogenously HaloTagged receptor in cytoplasmic puncta

## Part 2A. What this says about the protein

A cell-surface receptor that, when endogenously HaloTagged, is found **cytoplasmic and in puncta** rather than at the plasma membrane (where the same protein localises when delivered by viral transduction in cells with competent forms of the protein) indicates that **the tagged receptor is very likely structurally compromised and cannot reach the membrane, and is therefore retained intracellularly in puncta**. Specifically:

* The HaloTag fusion is probably **interfering with folding, maturation and/or trafficking of the receptor**. Likely molecular causes, depending on where the tag was inserted: occlusion or disruption of the **N-terminal signal peptide / signal anchor** (so the nascent chain is never properly inserted into the ER membrane and the receptor is mistargeted to the cytosol), steric interference with the ectodomain's disulfide-bonded fold or glycosylation, masking of a **C-terminal trafficking/sorting determinant** (e.g. a PDZ-binding motif, dileucine or tyrosine-based export signal, palmitoylation/prenylation site), or the 33 kDa tag simply being too bulky for the receptor's folding pathway or for partner/chaperone binding.
* Misfolded receptor is then recognised by ER quality control and **retained in the ER/ERGIC/Golgi or accumulates in aggresome-like/aggregated structures and in endolysosomal compartments** — which is exactly what cytoplasmic puncta look like. In other words, the puncta most likely represent a trafficking block (ER/Golgi retention, failure of ER export) and/or aggregation, with subsequent ERAD/autophagic turnover, rather than a genuine, previously unappreciated resting localisation.
* The contrast with the viral-transduction experiments is informative but not decisive in the opposite direction: those experiments used over-expression of a "competent" (untagged or differently tagged) form, which can saturate quality control and force surface delivery, so the discrepancy points to the **tag** (and/or the loss of over-expression) rather than to a new biological truth. Conversely, one must keep in mind the benign alternative — that endogenous-level imaging has revealed the receptor's true steady-state distribution in intracellular vesicles (constitutive internalisation/recycling pools), which over-expression previously masked. Distinguishing "compromised protein" from "true endogenous localisation" is precisely why the tag must be validated (Part 2B), and the structural/trafficking-defect explanation is the one to test first.

## Part 2B. One step to validate the HaloTag

**Test whether the HaloTagged receptor is still functional — i.e. assay its downstream signalling output and compare it with the untagged/parental receptor.** Concretely: stimulate the knock-in line and the parental (untagged) line with the receptor's physiological ligand over a dose range and time course, and read out a **downstream functional response** — for example western blot for ligand-induced phosphorylation of the canonical effectors (p-ERK1/2, p-AKT, p-STAT, receptor autophosphorylation), a second-messenger assay (cAMP, IP₁/IP₃, Ca²⁺ flux), a transcriptional reporter (NFAT/NF-κB/SRE-luciferase), qPCR of ligand-induced target genes, or a cell-level functional end-point (chemotaxis, proliferation, cytotoxicity). If the HaloTag knock-in line shows ligand-induced signalling equivalent to the parental line, the tagged receptor is structurally and functionally intact and the punctate localisation is likely genuine; **if the response is blunted or absent, the tag has compromised receptor structure/trafficking** and the construct must be redesigned.

Useful accompanying/confirmatory steps (same logic, additional evidence):

* **Surface-expression assay:** flow cytometry or immunofluorescence with an antibody against an extracellular epitope of the receptor on non-permeabilised cells, or cell-surface biotinylation (sulfo-NHS-biotin) followed by streptavidin pull-down; add a **cell-impermeant HaloTag ligand (e.g. AlexaFluor 488-HaloTag ligand) versus a cell-permeant ligand (TMR)** to quantify what fraction of tagged receptor is truly at the surface.
* **Identify the puncta** by co-staining with calnexin/KDEL (ER), GM130/giantin (Golgi), EEA1/Rab5, LAMP1 and p62/ubiquitin (aggresome), to show whether this is ER retention, endosomal pool or aggregation.
* **Orthogonal tag/position controls:** move the HaloTag to the other terminus or to a permissive internal loop, insert a flexible linker (e.g. (GGS)₃ or a longer glycine-serine spacer), and compare with a small-epitope knock-in (HA/FLAG, or split-FP/HiBiT) and with an anti-receptor antibody stain of untagged cells; a **functional rescue** experiment (does the tagged allele rescue the phenotype of a receptor-null line?) and confirmation that the knock-in is in-frame, biallelic and free of off-target integration (sequencing + anti-HaloTag/anti-receptor western at the expected fused mass) complete the validation.

---

## Final answers

* **1A.** The HaloTag was correctly expressed and the transfection/knock-in succeeded in all four lines (specific anti-HaloTag signal at tag + protein masses, no free 33 kDa tag); and the protein is almost certainly a **homodimer**, because each lane's doublet is spaced by exactly one HaloTag (33 kDa) — i.e. one vs. two tagged subunits in a single complex — and because the detected species are ~2× the monomer mass, a shift far too large to be explained by species differences.
* **1B.** Within-lane doublets reflect **incomplete transfection/knock-in with only one allele tagged** (mono-tagged $2m+33$ and bi-tagged $2m+66$ dimers, expected ~2:1); between-lane differences reflect **species differences in orthologue mass (20, 21, 21, 23.5 kDa) and post-translational modification**.
* **1C.** **Lanes 2 and 3 are from the same species** ($2m = 42$ kDa, shared 108 kDa band); the kDa difference arises because **HaloTag has been added to both alleles** in lane 2 (homozygous), whereas **lane 3 is consistent with heterozygous cells** expressing both tagged and untagged subunits. Lanes 1 and 4 are different species.
* **1D.** Needed about the protein: **whether both alleles were tagged**, which this blot cannot reveal because it was probed for HaloTag rather than with an antibody for the protein itself (requires anti-protein blot or genotyping). Needed about the experiment: **which type of electrophoresis gel was used** — SDS-PAGE (denaturing; separation by molecular weight) versus native PAGE (folded proteins; separation by molecular weight, structure and charge) — because the homodimer/native-size interpretation is only valid under native conditions.
* **2A.** The receptor is probably **structurally compromised and unable to reach the plasma membrane, hence its retention in cytoplasmic puncta**; the **HaloTag is likely affecting folding and trafficking to the membrane** (signal-peptide/ectodomain or sorting-motif interference, ER/Golgi retention or aggregation), with over-expression having previously forced surface delivery.
* **2B.** Validate by **assaying downstream function**: ligand-stimulated downstream signalling (p-ERK/p-AKT/p-STAT, cAMP/Ca²⁺, reporter or target-gene induction, or a cell-behaviour read-out) in the HaloTag knock-in versus parental cells, supported by surface-labelling/biotinylation, compartment co-staining, and tag-position/orthogonal-tag controls.
