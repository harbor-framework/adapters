# A multi-layered design for AND-gated, three-enzyme metabolite X production with neighbour-cell defence signalling in *Arabidopsis thaliana*

## 0. Design decomposition

The specification contains four separable engineering problems, and each imposes constraints on the others:

1. **Payload integration** — stable, single-copy, structurally intact insertion of a large (~10–12 kb) synthetic cassette.
2. **Logic** — a two-input AND gate reading P_stress (salinity) and P_flower (flowering), with a tight OFF state.
3. **Metabolic output** — stoichiometric, sequential co-expression of Enzymes A → B → C with no accumulation of toxic intermediates.
4. **Intercellular communication** — a cell-autonomously produced, cell-non-autonomously acting signal that upregulates *G_defense* in immediate, non-transgenic neighbours.

A fifth problem cuts across all four: **long-term genetic and epigenetic stability** of the construct in a plant that will be propagated through generations.

The architecture below is presented layer by layer, with the mechanistic justification and then a critical evaluation of its failure modes.

---

## 1. Layer 1 — The metabolic output cassette: a polycistronic-like 2A-peptide unit

### Design

The three enzymes are expressed from a **single transcriptional unit under the single output promoter P_output**, built as a **polycistronic-like (pseudo-operonic) open reading frame in which the enzyme coding sequences are joined by self-cleaving 2A peptides**:

```
P_output — 5'UTR — [Enzyme A] — T2A — [Enzyme B] — P2A — [Enzyme C] — terminator
```

Each 2A element is a ~20-residue viral *cis*-acting hydrolase element (T2A from *Thosea asigna* virus, P2A from porcine teschovirus-1, E2A, F2A) ending in the conserved **D-V/I-E-X-N-P-G ↓ P** motif, preceded by a GSG linker to improve cleavage efficiency. Translation proceeds as one ORF; at the glycyl–prolyl ester bond the ribosome fails to form the peptide bond ("ribosomal skipping"), releasing the upstream protein and re-initiating on the downstream proline. One mRNA therefore yields **three separate, near-equimolar polypeptides** — Enzymes A, B and C.

### Justification

- **Single regulatory input.** Only one promoter needs to be placed under AND-gate control. If each enzyme had its own promoter, the AND gate would need to be replicated three times, tripling the chance of leaky expression and of partial (stoichiometrically unbalanced) induction.
- **Co-expression with fixed stoichiometry.** Because the three cistrons share one mRNA, their relative translation is set by the cassette architecture rather than by three independent promoter/terminator strengths that would drift apart with chromatin context, developmental stage and stress state. For a *sequential* pathway (A → B → C), coordinate induction is essential; otherwise induction of A without C generates intermediates with no sink.
- **Plants lack efficient cap-independent internal initiation,** so true IRES-based polycistrons work poorly in plant cytoplasm; 2A peptides are translation-level, not initiation-level, and work robustly in plant cells. They are also far more compact than the alternatives.
- **Compactness lowers repeat content.** Three separate promoter–gene–terminator units would require either three copies of the same regulatory parts (a direct-repeat hazard; see §6) or three different ones (more parts, more characterisation).

### Critical evaluation

- 2A cleavage is efficient but **not 100%**, so a small fraction of A–B and B–C fusion protein is produced; and the upstream protein retains a C-terminal 2A "scar" while the downstream protein gains an N-terminal proline. Both can perturb folding, activity or targeting. **Mitigation:** place the enzyme most sensitive to N-terminal extension first in the cassette; validate each enzyme's specific activity in the 2A context; use different 2A variants (T2A, P2A) at the two junctions so that recombination between them is not possible and so that cleavage efficiencies can be tuned.
- 2A gives *near*-equimolar, not *tuned*, stoichiometry. If flux analysis shows B or C to be rate-limiting, position in the cassette (and 2A variant choice) gives only coarse control; finer control is addressed in §5 by protein-stability engineering.
- Organellar targeting (if any enzyme must be plastidic or peroxisomal) must be achieved by **N-terminal transit peptides on the downstream cistrons**, which is incompatible with a free N-terminal proline from 2A cleavage. In that case the affected enzyme is moved to the first position, or a C-terminal targeting signal (e.g. a PTS1 tripeptide for peroxisomes) is used instead.

---

## 2. Layer 2 — Genome integration: transposase-assisted CRISPR-Cas9 targeted integration

### Design

The whole construct is delivered as a **synthetic transposon** — the payload plus its insulators (§3) flanked by **piggyBac inverted terminal repeats (ITRs)** — and inserted at a pre-characterised genomic "safe-harbour" locus by **transposase-assisted CRISPR-Cas9 (TAC) targeted integration**: Cas9/gRNA (or a Cas9–transposase fusion/tethered complex) directs the **piggyBac transposase** to a defined genomic **TTAA** site in a transcriptionally permissive, euchromatic, intergenic region with no nearby essential genes, no known imprinting and no small-RNA-generating loci.

### Justification

- **"Seamless" integration with a defined target-site duplication.** piggyBac transposition is precise at base-pair resolution: the element inserts at a **TTAA** tetranucleotide and generates a **defined TTAA target-site duplication** flanking the insert, with **no insertion or deletion of host sequence** and no vector backbone, filler DNA or scar of unpredictable length. The junction sequences are therefore *known a priori*, which makes the insertion verifiable by simple junction PCR and sequencing, and makes the locus re-usable and comparable across independent lines.
- **Reduced likelihood of deletions and rearrangements compared with simple NHEJ-mediated knock-in.** A straightforward Cas9 + NHEJ knock-in relies on the error-prone end-joining of a blunt or staggered double-strand break to a donor end. In plants this routinely produces indels at the junctions, partial/truncated insertions, tandem and inverted multimers of the donor, vector-backbone co-integration, large deletions on one side of the break, and occasional chromosomal translocations — all of which are catastrophic for a 10–12 kb multi-part cassette whose internal architecture must remain exactly as designed. Transposase-mediated strand transfer is a **cut-and-paste chemistry that does not depend on host end-joining**, so the donor ends are not exposed to NHEJ processing. This is the central argument: Cas9 supplies the *targeting* specificity while the transposase supplies the *integration* fidelity, giving a single-copy, intact, precisely defined insertion at a chosen locus.
- **Avoids HDR's limitations in plants.** Homology-directed knock-in in somatic plant cells is inefficient and requires long homology arms, which for a 12 kb payload makes donor construction and delivery difficult.
- **Reversibility/remobilisation.** Retaining ITRs allows later excision (also seamless, restoring the single TTAA) or remobilisation, which is useful for building and debugging versions of the device, and for removing selectable markers.

### Critical evaluation

- The transposase can **re-mobilise the element** in later generations if any transposase activity persists; the transposase must therefore be supplied *transiently* (RNP/mRNA, or on a segregating T-DNA that is crossed out) and its absence confirmed in the final line.
- piggyBac retains **residual TTAA-site promiscuity**: targeting is biased, not absolute. Whole-genome sequencing of candidate lines is required to confirm single-copy, on-target insertion and the absence of secondary events.
- The chosen safe harbour must be validated empirically for **position effects** — expression level, inducibility and heritable stability over ≥T4 — because "euchromatic and intergenic" is a necessary but not sufficient condition.

---

## 3. Layer 3 — Protecting the insertion from epigenetic silencing: flanking chromatin insulators

### Design

**The entire synthetic transposon is flanked, immediately inside the ITRs, by chromatin insulator (boundary) elements** — e.g. matrix attachment regions (MARs/SARs such as the tobacco RB7 MAR or the chicken lysozyme A element), the *Arabidopsis* ACTIN2/TM6 upstream boundary, the sea-urchin *arylsulfatase* insulator, or engineered CTCF-like/boundary-element arrays and nucleosome-depleted spacer sequences. Insulators are placed on **both** sides, in the same orientation convention at each end, and are themselves sequence-diversified so the left and right elements are not identical repeats.

### Justification

Plants mount vigorous, heritable transcriptional gene silencing against transgenes: RNA-directed DNA methylation (RdDM) via Pol IV/Pol V, 24-nt siRNAs, DRM2 and CMT3, and MET1 maintenance methylation, with spreading of repressive H3K9me2 and CHG/CHH methylation from adjacent heterochromatin or from the insertion junction into the transgene. This is the single most common cause of the progressive loss of transgene expression over generations.

Insulators address this specifically and mechanistically: they act as **barrier elements** that block the processive spreading of heterochromatin and DNA methylation into the flanked domain, and as **enhancer-blocking elements** that prevent regulatory cross-talk between the synthetic domain and the host locus (in both directions: the host enhancers cannot drive P_output, and the synthetic activators cannot misregulate neighbouring host genes). MARs additionally tether the domain to the nuclear matrix, creating an independent, topologically insulated chromatin loop with more uniform and more heritable expression and markedly reduced line-to-line variability.

This is *epigenetic* protection and is logically distinct from the *genetic* protection provided by sequence diversification (§6): insulators stop silencing *entering the domain from outside*, whereas diversification stops silencing being *nucleated inside* the domain by internal repeats.

### Critical evaluation

Insulator function in plants is less well characterised than in *Drosophila* or vertebrates and is partly context-dependent; no element is a guaranteed barrier. The design therefore (i) uses two different element types in tandem at each boundary, (ii) requires empirical validation across at least T1–T4 generations and under the inducing conditions, and (iii) treats insulators as risk reduction rather than elimination, which is why the construct is *also* diversified internally and inserted at a validated safe harbour.

---

## 4. Layer 4 — The AND gate: a CRISPRi-based split-activator (split-dCas9-activator) system

### Design

Logic is implemented on the **CRISPRi/dCas9 platform**, but reconfigured as a **split transcriptional activator**. Catalytically dead Cas9 (dCas9, D10A/H840A) is provided as two separate fusion proteins, each carrying **one half of a split activation domain** — the **N-terminal half and the C-terminal half of VP64** (or, equivalently, split VPR/VP64-p65-Rta, or a split EDLL/ERF2m plant activation domain):

- **dCas9–VP64(N)** — the N-terminal activator fragment
- **dCas9–VP64(C)** — the C-terminal activator fragment

Both dCas9 fusion proteins are expressed constitutively at low level (from diversified, moderate-strength plant promoters — see §6). The **logic is encoded in the sgRNAs**, which are the input-driven components:

- **sgRNA1** is transcribed from **P_stress** (salinity-responsive; e.g. an RD29A/DREB2A-type element) and targets **site 1** in P_output.
- **sgRNA2** is transcribed from **P_flower** (flower-specific; e.g. an AP1/AP3/SEP-type promoter) and targets **site 2** in P_output.

Sites 1 and 2 are placed in the P_output upstream region **adjacent to one another**, separated by a designed spacing (empirically optimised, typically ~15–40 bp between PAM-proximal ends, with the two protospacers on defined strands so the dCas9 N-termini face each other) such that the two bound dCas9 molecules present their split-activator halves in the correct geometry and proximity for reassembly.

Both sgRNAs are expressed as Pol II transcripts processed to mature guides using **tRNA–sgRNA arrays or Csy4/ribozyme flanking**, so that tissue-specific Pol II promoters (P_stress, P_flower) can drive them while still yielding correctly 5′/3′-processed guides.

A minimal, nucleosome-permissive **P_output** core promoter (TATA box + 5′UTR, e.g. a minimal 35S or minimal NOS core stripped of all enhancers) sits downstream of the two target sites, driving the 2A polycistron of §1.

### Mechanistic explanation of the gate

| Salinity (P_stress) | Flowering (P_flower) | sgRNA1 | sgRNA2 | dCas9 at site 1 | dCas9 at site 2 | VP64 halves | P_output |
|---|---|---|---|---|---|---|---|
| – | – | absent | absent | none | none | both free, unassembled | **OFF** |
| **+** | – | present | absent | dCas9–VP64(N) or (C) bound | none | one half only, at one site | **OFF** |
| – | **+** | absent | present | none | dCas9 bound | one half only, at one site | **OFF** |
| **+** | **+** | present | present | bound | bound | **reconstituted VP64** | **ON** |

The mechanism in words:

1. **Input 1 (salinity)** activates P_stress, producing **sgRNA1**, which loads into the available dCas9 pool and directs dCas9 (carrying either VP64 half) to **site 1** of P_output.
2. **Input 2 (flowering)** activates P_flower, producing **sgRNA2**, which directs dCas9 to **site 2** of P_output.
3. With **only one** input present, only one dCas9 complex is recruited. A single VP64 half has **no intrinsic transactivation capacity** — the activation surface that contacts the Mediator complex and the general transcription machinery exists only in the assembled domain. Occupancy of one site by a dCas9 carrying half a domain is therefore transcriptionally silent (and, if anything, mildly occlusive). The gate is OFF.
4. With **both** inputs present, **both** sgRNAs are made, **both** dCas9 fusions are recruited to their adjacent target sites, and the two halves are brought into high **local concentration and correct relative orientation on the DNA**. This **co-localisation drives reconstitution (intramolecular-like complementation) of the split VP64 activation domain** at the promoter.
5. The reassembled VP64 then performs its normal function: recruitment of **Mediator (MED15/MED25), SWI/SNF-type chromatin remodellers and histone acetyltransferases**, local nucleosome displacement and histone acetylation, recruitment of TFIID/TBP and RNA **Pol II** to the minimal core promoter, and productive initiation.
6. **P_output transcription therefore occurs if and only if both inputs are present** — a genuine two-input AND, because the non-linearity (cooperative reassembly of a bipartite activator) is enforced at the protein level on the DNA, not merely by summing two weak transcriptional inputs.

### Justification for this topology

- **Proximity-dependent reconstitution gives a sharp, cooperative transfer function**, rather than the graded, additive response of a promoter bearing two independent *cis*-elements (which behaves as an OR/SUM gate with substantial single-input leak).
- **The dCas9 platform is fully programmable and orthogonal**: the target sites in P_output are synthetic, exist nowhere in the *Arabidopsis* genome (verified by genome-wide off-target search including PAM-proximal mismatch and bulge tolerance), and dCas9 has no endogenous plant interaction partners. Logic can be re-wired by changing 20-nt spacers rather than redesigning proteins.
- **Only small RNAs are input-driven**, which makes the inducible layer fast, low-burden and free of the folding/aggregation problems of inducibly expressed large proteins.
- The same platform supplies the **repressive** arm of §4b, so one protein scaffold (dCas9) serves both activation and repression, reducing total parts count and metabolic burden.

### 4b. Tightening the OFF state: an additional, independently regulated repression layer

A single-layer AND gate will still leak: constitutive dCas9 fusions, basal activity of P_stress (salt-responsive promoters show basal and wound/ABA-related activity) and of P_flower, and intrinsic core-promoter basal transcription all contribute. Because metabolite X and its intermediates are potentially cytotoxic and metabolically expensive, the OFF state must be actively enforced.

**Design:** add **additional layers of repression — a dCas9–repressor fusion that also targets P_output**, i.e. **dCas9–SRDX (EAR-motif repressor), dCas9–KRAB or dCas9–MeCP2/LHP1**, directed by a third guide (**sgRNA3**) to a site overlapping or immediately downstream of the P_output core promoter/TSS, where it sterically blocks Pol II recruitment and additionally imposes local repressive chromatin (SRDX-mediated recruitment of TPL/TPR corepressors and HDACs). This repressor is itself placed under **its own complex regulation** so that it is *removed* exactly when the gate should open:

- **sgRNA3 is expressed from a constitutive promoter**, so repression is the default state, **and**
- the repressor arm is **inverted with respect to the inputs** by a NOT/NIMPLY layer: an input-driven inverter (e.g. P_stress- and P_flower-driven expression of a Csy4 or ribozyme-based guide-destabilising module, an anti-CRISPR protein such as AcrIIA4, a TEV-protease-cleavable degron on dCas9–SRDX, or an sgRNA3-targeting trans-cleaving ribozyme) degrades or inactivates the repressor arm only when **both** inputs are present (e.g. by a split-protease or split-anti-CRISPR requiring both inputs).

The output logic becomes **(sgRNA1 AND sgRNA2) AND NOT(repressor)**, where the repressor is itself removed only by (input1 AND input2). This is a **double-check architecture**: a single leaky event in the activator arm cannot open the gate, because the repressor must *also* be cleared. The result is a much lower basal output and a steeper, more digital input–output response.

**Additional OFF-state measures layered on top:**
- a minimal core promoter with **all cryptic enhancer/TATA-like elements removed** and cryptic ATGs eliminated from the 5′UTR;
- **transcriptional terminators/insulators immediately upstream of P_output** to prevent read-through from any upstream synthetic unit;
- a **destabilising degron** on the enzymes themselves in the OFF state (§5), so that leaky transcription does not accumulate as enzyme protein.

### Critical evaluation of the logic layer

- **Cost of constitutive dCas9.** Two dCas9 fusions plus a dCas9 repressor represent a substantial constitutive protein burden (~160 kDa each) and compete for the same guide pool; expression levels must be kept low and balanced, and the three dCas9 variants should be orthogonal scaffolds (e.g. *Sp*dCas9, *Sa*dCas9 and *Lb*dCas12a) so that the activator and repressor arms cannot swap guides.
- **Guide competition and dilution.** sgRNAs compete for dCas9; an input-driven surge of sgRNA1 could titrate dCas9 away from the repressor site, which would *help* the ON state but could also cause an unwanted single-input leak. Orthogonal scaffolds (above) remove this coupling.
- **Spacing optimisation is empirical.** The geometry needed for split-VP64 reassembly must be found by screening a small library of site-1/site-2 spacings and strand configurations in transient assays (protoplasts, *N. benthamiana* agroinfiltration) before stable transformation.
- **Dynamic range vs. leak trade-off.** A stronger activation domain (VPR) raises the ON level but also raises the leak from half-domain and from incomplete repression; the split architecture plus the repressor arm is what permits a strong activator to be used without sacrificing the OFF state.
- **Input promoter fidelity is the gate's ultimate limit.** No amount of downstream logic can correct a P_stress promoter that also responds to drought/ABA/wounding, or a P_flower promoter with low-level vegetative activity. Both must be characterised quantitatively (reporter time-courses across tissues, stresses and developmental stages), and if necessary replaced with synthetic promoters built from minimal, well-characterised *cis*-elements (DRE/CRT for salinity; CArG/AP1-binding sites for flowering).

---

## 5. Layer 5 — Managing metabolic imbalance and intermediate cytotoxicity: enzyme stability engineering and inducible degradation tags

### The problem

In a sequential pathway A → B → C, any mismatch in flux causes accumulation of the intermediate upstream of the slowest step. Pathway intermediates are frequently more reactive and more cytotoxic than the end product (electrophiles, aldehydes, quinones, free radicals), can be shunted into endogenous metabolism by promiscuous host enzymes, and can inhibit growth, trigger the unfolded-protein/oxidative-stress responses, or be glycosylated and sequestered in the vacuole with loss of yield. 2A-based co-expression (§1) fixes *translation* stoichiometry but not *catalytic* stoichiometry, since the three enzymes differ in $k_{cat}$, $K_M$ and in vivo half-life.

### Design

Two complementary, specific strategies:

**(a) Protein-stability engineering of Enzyme C (the terminal, and typically flux-limiting, enzyme).** Enzyme C is engineered for increased in planta half-life and specific activity so that the terminal step cannot become the bottleneck at which the intermediate pools back up:
- removal of destabilising N-terminal residues and compliance with a stabilising N-end-rule context; removal of PEST-like and surface-exposed protease-labile loops;
- removal/masking of ubiquitination-prone surface lysines and of cryptic degrons;
- consensus/ancestral-sequence and ΔΔG-guided (e.g. FoldX/Rosetta or ProteinMPNN-based) stabilising substitutions, plus disulfide or proline/glycine rigidification;
- codon optimisation for *Arabidopsis* and removal of cryptic splice sites and polyadenylation signals;
- optional fusion to a stabilising partner or scaffolding to co-localise C with B (see below).

If total pathway flux rather than C's stability is limiting, the equivalent levers are raising C's effective concentration (position in the 2A cassette) and improving $k_{cat}/K_M$ by directed evolution.

**(b) Inducible degradation tags on Enzymes A and B.** Enzymes A and B are fused to **conditional degrons** so their abundance can be actively collapsed — either constitutively in the OFF state or on demand if intermediates accumulate:
- **auxin-inducible degron (AID/mAID)** with OsTIR1, giving auxin/5-Ph-IAA-triggered SCF^TIR1^-dependent polyubiquitination and 26S-proteasomal degradation;
- **plant-adapted degrons**: the IAA17 domain II degron, an N-degron/ODC-type degron, a photosensitive B-LID/light-controlled degron, or an FKBP-based destabilising domain stabilised by Shield-1.

This provides an orthogonal, post-translational "pressure-relief valve": the first two enzymes — the ones that *generate* the intermediates — can be switched off within minutes to hours, independently of the transcriptional gate, which responds only on the timescale of mRNA and protein turnover.

**Supporting measures** (secondary to the two strategies above): co-localise the pathway by **enzyme scaffolding/fusion of B and C** or targeting to a synthetic compartment or the ER surface, so the intermediate is channelled substrate-to-substrate and never reaches a bulk cytosolic concentration; sequester the pathway in an organelle (plastid/peroxisome) away from cytosolic targets; and add an intermediate-responsive feedback circuit (an intermediate-sensing transcription factor driving a dCas9–SRDX against P_output) so the cell self-limits flux.

### Critical evaluation

- Degron systems in plants require delivery of the small-molecule or light input to the right tissue and depend on OsTIR1 expression levels; they are therefore excellent for research-scale control and for suppressing leak, but awkward as a field-deployable safety mechanism.
- Stabilising Enzyme C too aggressively could invert the problem, making the *substrate* of C limiting and depleting a shared host metabolite pool; flux must be re-balanced empirically with ¹³C labelling and targeted metabolomics at each design iteration.
- Hyperstable enzymes accumulate across the long induction window of a flowering, salt-stressed plant, so a stable C plus degron-controlled A/B is deliberately asymmetric: the step that *consumes* intermediates is persistent, the steps that *produce* them are collapsible.

---

## 6. Layer 6 — Mitigating homology-dependent gene silencing: sequence diversification of internal parts

### The problem

**Homology-dependent gene silencing (HDGS)** — both transcriptional (TGS, via RdDM and 24-nt siRNAs acting on shared promoter sequence) and post-transcriptional (PTGS, via aberrant/read-through transcripts, dsRNA formation between repeats, DCL processing and AGO-mediated slicing) — is triggered by **repeated, identical sequence** within and between transgenes. A construct of this complexity needs ~6–8 promoters (two dCas9 activator halves, a dCas9 repressor, sgRNA1/2/3, the mobile-peptide module, the receptor module, selectable markers) and a similar number of terminators. If these are built from multiple identical copies of the same part, the construct contains long direct repeats, which is the classic recipe for its own silencing — and identical direct repeats are also substrates for intrachromosomal recombination and cassette deletion.

### Design

**Every repeated regulatory part in the construct is sequence-diversified, so that no two internal promoters or terminators share extended identity.** Concretely:

- **Replace multiple CaMV 35S copies with a diversified promoter set.** Instead of using the 35S promoter for every constitutive unit, use **a different constitutive promoter for each**: the **NOS (nopaline synthase) promoter**, the ***Arabidopsis* / maize ubiquitin promoters (UBQ10, UBQ1, ZmUbi1)**, *AtACT2*, *AtEF1α*, the *Arabidopsis* polyubiquitin UBQ3/UBQ11, the figwort mosaic virus (FMV) and MMV promoters, and the *Nicotiana* NtMPI/NtPMA4 promoters. At most one copy of 35S is used anywhere in the construct.
- **Diversify terminators similarly**: NOS-ter, OCS-ter, *rbcS*-ter, *HSP18.2*-ter, *AtMAS*-ter, *35S*-ter — one each rather than multiple copies of one.
- **Codon-diversify all coding sequences that are internally repeated.** The two dCas9 fusions and the dCas9 repressor would otherwise be ~4 kb identical repeats: use **synonymous codon diversification to drive pairwise nucleotide identity below ~75–80%** (below the threshold for efficient siRNA-mediated cross-silencing and for homologous recombination), or use **genuinely orthologous nucleases** (*Sp*dCas9, *Sa*dCas9, *Lb*dCas12a, *Nme*dCas9), which are naturally non-homologous and solve the repeat problem and the guide-crosstalk problem (§4) simultaneously.
- **Diversify the sgRNA scaffolds** by using orthogonal scaffolds matched to the orthogonal nucleases, and diversify the tRNA spacers in guide arrays.
- **Use different 2A variants** (T2A, P2A) at the two junctions of the enzyme cassette rather than two copies of one.
- Remove internal cryptic polyadenylation signals, cryptic TATA boxes and inverted repeats (which form dsRNA hairpins and nucleate PTGS), and screen the final sequence computationally for any direct or inverted repeat >~50 bp and for predicted siRNA-generating structure.

### Justification

Diversification removes the *substrate* for both silencing routes: without extended identical sequence there is no efficient template for RdDM-mediated spreading between units, no dsRNA formed by sense/antisense pairing between repeated parts, and no high-identity target for siRNAs generated against any one unit to cross-silence the others. It simultaneously removes the substrate for homologous recombination between repeats, which is a major cause of cassette truncation and of structural instability over generations — complementing the *structural* fidelity provided by transposase-mediated integration (§2) and the *positional* protection provided by insulators (§3). The three measures target three distinct failure modes and are not substitutes for one another.

### Critical evaluation

Diversified parts differ in strength, tissue profile and developmental dynamics, so "equivalent" promoters are not interchangeable: each must be quantitatively characterised (reporter fusions; RT-qPCR) and assigned to the unit whose required expression level it matches. Diversification also increases DNA synthesis cost and makes cloning junctions unique (loss of modular part re-use). Both are acceptable prices for heritable stability, but they must be planned at the design stage.

---

## 7. Layer 7 — Intercellular signalling to non-transgenic neighbours

### 7a. A synthetic, orthogonal peptide–receptor pair (primary specificity strategy)

**Design.** The signal is a **small secreted peptide**, and the **primary strategy to reduce off-target signalling is to use a synthetic, orthogonal peptide–receptor pair engineered for high affinity and high specificity.** Concretely:

- the **ligand** is a designed peptide (~8–20 residues of mature sequence) that is *not* a member of any endogenous *Arabidopsis* peptide family (not a Pep/PIP/PAMP mimic, not a CLE, RGF, IDA, RALF or PSK homologue), chosen/evolved so that it does not bind any endogenous LRR-RK ectodomain;
- the **receptor** is an engineered chimeric receptor kinase: a **re-specified LRR ectodomain** (directed evolution/computational redesign of a PEPR1/BAK1-, FLS2- or HAESA-type ectodomain, or a designed binder grafted onto the LRR scaffold) fused to a native plant RK transmembrane and cytoplasmic kinase domain, so that ligand binding triggers **canonical co-receptor (SERK/BAK1) recruitment, kinase trans-phosphorylation, BIK1/RLCK release, RBOH-dependent ROS burst, Ca²⁺ influx and MAPK (MPK3/MPK6) activation**, which is wired to a synthetic promoter driving **G_defense** upregulation;
- the pair is co-evolved for **high affinity (target $K_D$ in the low nM range)** so that the very low apoplastic concentrations reached after diffusion from a single producing cell are still saturating at the receptor, and for **mutual specificity** — the peptide must not activate endogenous receptors (avoiding spurious whole-plant immune activation and growth penalty) and the receptor must not be activated by any endogenous peptide (avoiding constitutive or stress-coincident firing of the defence output).

**Justification.** Orthogonality is what makes the circuit *private*: because neither partner has an endogenous counterpart, signalling is confined to the engineered channel and cannot be triggered by, or interfere with, the plant's own peptide–receptor networks (which are large, partly redundant and heavily cross-reactive — exactly why a native peptide mimic would be a poor choice). High affinity converts a steep, rapidly diluting diffusion gradient into a sharp binary response in the first ring of neighbours, which is the required spatial behaviour ("immediate neighbours", localised protection).

**Specificity validation and tuning:** counter-screen the peptide against the *Arabidopsis* LRR-RK ectodomain panel and against *bak1/serk* and *pepr1 pepr2* mutant backgrounds; confirm no ROS burst, no MAPK activation, no *PR1/FRK1/WRKY* induction and no growth penalty in receptor-free plants; and tune the signalling range by adjusting peptide affinity, the secreted dose and the expression level of an apoplastic peptide-degrading protease to sharpen the gradient.

**The "non-transgenic neighbour" constraint, and how it is resolved.** A truly naive wild-type cell has no synthetic receptor, so strict orthogonality and strict non-transgenic responsiveness are in tension. The design resolves this by separating the two transgenic layers:

- the **sensor layer** — the orthogonal receptor plus the synthetic *G_defense*-driving promoter — is expressed **constitutively and ubiquitously throughout the plant** (from a diversified ubiquitin/ACT2 promoter, §6), so every cell is competent to *receive*;
- the **producer layer** — the AND gate and the metabolic cassette — is what is conditionally active in individual cells.

Neighbouring cells are therefore "non-transgenic" in the operationally relevant sense: they do not express or activate the metabolic/logic payload, and they respond only because they carry the (silent, ligand-dependent) receptor. If genuinely wild-type, untransformed neighbours must respond — e.g. in a mixed or chimeric tissue, or in a grafted/field context — the orthogonal pair cannot work by itself, and the fallback is a **native immune-peptide agonist (an engineered AtPep1/PIP1 variant acting through endogenous PEPR1/PEPR2, or a designed RALF/CLE-family agonist)**, accepting the loss of orthogonality and the resulting risk of systemic immune activation, growth–defence trade-off and yield penalty. The orthogonal pair remains the primary strategy because it is the only option that gives *specific*, non-leaky signalling.

### 7b. Engineering the mobile peptide for secretion and stability

**Secretion.** The peptide is expressed as a **pre-pro-peptide with an N-terminal signal peptide** (e.g. that of a native apoplastic peptide such as PIP1/RALF/chitinase), so it enters the **co-translational Sec61/ER–Golgi secretory pathway** and is **secreted into the apoplast**. It is designed with **no vacuolar sorting determinant, no ER-retention (HDEL) signal and no transmembrane segment**, and with a defined processing site (a subtilase/SBT or S1P recognition sequence) to release the mature peptide. **Apoplastic secretion is the essential step for cell-non-autonomous action:** once in the continuous extracellular/cell-wall space, the peptide **diffuses through the apoplast to the immediate neighbouring cells**, where it binds the orthogonal receptor on their plasma membrane and triggers the signalling cascade that **upregulates G_defense**. (Note why the alternatives fail: a cytoplasmic signal could only move through plasmodesmata, with size-exclusion-limited, developmentally variable and much shorter range; a volatile or vascular signal would be systemic rather than localised.) The 2A cassette of §1 is not a suitable home for a signal-peptide-bearing cistron (which needs a free N-terminus), so the peptide module is expressed from its **own P_output-controlled unit**, or placed **first** in the polycistron, upstream of Enzyme A.

**Stability engineering (to combat degradation and sequestration).** The apoplast is a hostile compartment: acidic pH, high concentrations of secreted subtilases, papain-like and aspartic proteases and carboxypeptidases, oxidising conditions, and abundant anionic pectin and cell-wall glycoprotein that electrostatically sequester cationic peptides. An unmodified ~10-mer would be degraded or adsorbed before reaching the neighbouring plasma membrane. The peptide is therefore **engineered for enhanced stability**:

- **substitution of protease-labile residues and cleavage-site sequences** — replacing the P1/P1′ residues of predicted subtilase, trypsin-like and chymotrypsin-like sites, removing Asn-Gly (deamidation) and Asp-Pro (acid-labile) motifs, and using **D-amino acids or N-methylated/β-amino acid residues** at the most labile positions;
- **cyclisation** — head-to-tail backbone cyclisation, or a disulfide or lactam staple, which removes the free termini required by amino/carboxypeptidases, rigidifies the structure (raising receptor affinity by reducing the entropic cost of binding) and dramatically increases protease resistance (the strategy used naturally by cyclotides, which are exceptionally stable plant peptides);
- **fusion to a stable carrier** — presenting the active epitope on a hyperstable, disulfide-rich scaffold (a cyclotide/knottin, a defensin-like fold, or a small stable protein domain) that is itself resistant to apoplastic proteolysis, or fusing to a carrier that increases apparent half-life;
- **surface-charge engineering** to reduce non-specific electrostatic adsorption to pectin and wall polyanions (lowering net positive charge, or shielding basic residues), and **glycosylation/hydroxyproline-arabinosylation** where this is known to stabilise the peptide class (as for CLE and RGF peptides) without blocking receptor contact;
- **affinity compensation** (§7a): raising receptor affinity means that even a reduced surviving peptide concentration is sufficient, which is the most robust defence against partial degradation.

**Critical evaluation.** Stabilisation and range are in tension with spatial precision: an over-stabilised peptide diffuses further and activates *G_defense* in cells well beyond the immediate neighbours, defeating the "localised protective measure" requirement, and persists after the stimulus has passed. The design therefore tunes half-life deliberately — enough stability to cross one or two cell diameters reliably, plus an engineered apoplastic clearance mechanism (a co-expressed, broadly expressed peptide-specific protease, or a designed labile site that is slowly cleaved) to impose a defined spatial and temporal decay. Backbone modifications (D-amino acids, N-methylation) cannot be genetically encoded, so a fully genetic solution must rely on cyclisation (e.g. by a co-expressed asparaginyl endopeptidase/butelase-type cyclase), residue substitution and carrier fusion rather than on non-natural chemistry.

---

## 8. Integrated architecture and critical overall assessment

**Final architecture (one insulated, seamlessly integrated synthetic transposon at a validated safe harbour):**

```
TTAA | ITR | [INSULATOR/MAR] |
  P_UBQ10      → dCas9(Sp)–VP64(N)
  P_ACT2       → dCas9(Sa)–VP64(C)              [codon/scaffold-diversified]
  P_NOS        → dCas12a(Lb)–SRDX                (default repressor arm)
  P_stress     → tRNA–sgRNA1  (site 1, P_output)        [INPUT 1]
  P_flower     → tRNA–sgRNA2  (site 2, P_output)        [INPUT 2]
  P_EF1a       → sgRNA3 (core promoter, repressor site)
  P_stress+P_flower → split inverter (anti-CRISPR / protease) → clears repressor arm
  P_UBQ1       → orthogonal chimeric LRR receptor kinase  (receiver, all cells)
  [site1][site2][minimal P_output] → SP–mobile-peptide(cyclised, stabilised)
                                   → Enzyme A – T2A – Enzyme B – P2A – Enzyme C(stabilised)
                                      (A and B carry AID/mAID degrons; OsTIR1 expressed)
  diversified terminators throughout (NOS-, OCS-, rbcS-, HSP18.2-ter)
| [INSULATOR/MAR] | ITR | TTAA
```

**Operation.** Salinity + flowering → sgRNA1 + sgRNA2 → two dCas9 fusions occupy adjacent sites in P_output → split VP64 reassembles → Mediator/Pol II recruitment, while the inverter simultaneously clears dCas12a–SRDX → P_output fires → the stabilised, cyclised peptide is secreted into the apoplast and the 2A polycistron yields Enzymes A, B and C in near-equimolar amounts → metabolite X is made in that cell, and the apoplastic peptide diffuses to the immediate neighbours, binds the orthogonal receptor, and induces *G_defense* locally.

**Honest assessment of the principal residual risks, in order of severity:**

1. **Input-promoter fidelity** (§4). The gate's specificity cannot exceed that of P_stress and P_flower. Quantitative characterisation, and if necessary synthetic minimal-element promoters, is the first experimental priority.
2. **Metabolic burden and growth–defence trade-off.** Three constitutive dCas9-class proteins, a constitutive receptor, OsTIR1 and an induced three-enzyme pathway are a large drain on ribosomes, ATP, reducing equivalents and carbon — in a cell that is simultaneously salt-stressed and flowering, i.e. already resource-limited. Burden must be measured (growth, seed set, photosynthetic parameters, proteome allocation) and dCas9 expression trimmed to the minimum that supports the gate.
3. **Long-term epigenetic silencing** (§3, §6). Insulators plus diversification plus single-copy seamless integration substantially reduce but do not eliminate the risk; stability must be demonstrated empirically to T4–T5 and under inducing conditions, not assumed.
4. **Intermediate toxicity** (§5). Requires iterative ¹³C-flux and metabolomic re-balancing; the degron valve is a mitigation, not a design-time solution.
5. **Signal range control** (§7b). Peptide half-life sets the spatial domain; achieving "immediate neighbours only" will require empirical tuning of stability, dose and apoplastic clearance.
6. **Biocontainment.** A circuit built on an orthogonal peptide–receptor pair and a conditionally mobile transposon warrants transposase removal, a segregating-marker-free final line, and consideration of a terminator/kill-switch and of pollen-flow containment before any non-contained use.

**Build-and-test order (shortest path to a de-risked device):** (i) characterise P_stress and P_flower quantitatively; (ii) optimise site-1/site-2 spacing and split-VP64 reassembly in protoplasts and *N. benthamiana*; (iii) validate the orthogonal peptide–receptor pair in a receptor-only line (ligand applied exogenously); (iv) test the 2A cassette's enzyme stoichiometry and activity, and the stabilised Enzyme C, with transient expression and targeted metabolomics; (v) assemble the full insulated transposon, integrate by TAC at the safe harbour, verify by junction PCR and WGS; (vi) measure the four-state truth table, the OFF-state leak with and without the repressor arm, metabolite X yield, intermediate accumulation, neighbour-cell *G_defense* induction and its spatial extent; (vii) follow expression and methylation state through T4 to confirm heritable stability.
