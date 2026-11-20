# Deconvoluting five mislabelled MAPK-pathway inhibitors in KRAS G12D SW48 cells

## 0. The analytical framework

The five compounds belong to three mechanistic classes acting at three successive tiers of the RAS→RAF→MEK→ERK cascade:

| Compound | Class | Mechanistic signature expected |
|---|---|---|
| **LY3009120** | pan-RAF inhibitor (A-, B-, C-RAF; "paradox-breaker") | Blocks the kinase **above** MEK → **p-MEK low, p-ERK absent**, downstream (RSK, S6) off, and the RAF-scaffolded MEK–ERK complex is destabilised, so nuclear ERK accumulation is lost |
| **AZD6244 (selumetinib)** | allosteric (non-ATP-competitive) MEK1/2 inhibitor | p-ERK drops early, then **rebounds** as ERK-dependent negative feedback (DUSP6, SPRY1/2) is relieved; **p-MEK rises** over time because MEK phosphorylation by RAF is *not* blocked by an allosteric inhibitor |
| **SCH722984 (SCH772984)** | **dual-mechanism** ERK1/2 inhibitor — inhibits ERK catalytic activity **and** prevents MEK1/2-mediated phosphorylation of the ERK activation loop | **p-ERK unchanged** (no accumulation), yet ERK substrates (RSK) are lost |
| **BVD-523 (ulixertinib)** | ATP-competitive ERK1/2 inhibitor; strongest inducer of **ERK2 degradation** | p-ERK **increases** (catalytic block without blocking pTEpY), DUSP6 falls, and **ERK2 protein is progressively lost with detectable ubiquitinated ERK2** |
| **LY3214996 (temuterkib)** | ATP-competitive ERK1/2 inhibitor | **Strong accumulation of p-ERK1/2**; also causes some ERK2 protein loss (post-transcriptional) but weaker than BVD-523 |

Two structural rules do most of the work:

1. **Where the block is** determines the p-MEK/p-ERK pattern. Only an inhibitor **upstream of MEK** can make **both** p-MEK and p-ERK disappear (RAF inhibitor). A MEK inhibitor lowers p-ERK but *raises* p-MEK. An ERK inhibitor lowers ERK *substrate* phosphorylation while leaving — or increasing — p-ERK itself.
2. **How the ERK inhibitor binds** determines whether p-ERK rises. ATP-competitive ERK inhibitors (BVD-523, LY3214996) block catalysis but do not prevent MEK1/2 from phosphorylating the **pT-E-pY** activation motif; in fact, by abolishing ERK-dependent negative feedback (and by blocking ERK autoregulation of its own dephosphorylation/DUSP induction), they cause **p-ERK to accumulate**. A **dual-mechanism** inhibitor (SCH772984) additionally locks ERK in a conformation that MEK cannot phosphorylate, so **p-ERK does not accumulate** — as Kidger et al. showed, dual-mechanism inhibitors give at most a gradual recovery of p-ERK1/2 during pathway rebound, whereas **LY3214996 induces a strong accumulation of p-ERK1/2**.

---

# Part A. Matching Inhibitors A–E

## Inhibitor A = **SCH722984 (SCH772984)** — dual-mechanism ERK1/2 inhibitor

**Data:** p-ERK1/2 unchanged; p-RSK reduced; total ERK1/2 stable; p-S6 unaffected.

**Justification.**
* **p-RSK is reduced while total ERK is stable** → ERK *catalytic activity* is inhibited (RSK is a direct, proximal ERK substrate), so the compound is an ERK-level inhibitor, not a MEK or RAF inhibitor (those would also collapse p-ERK).
* **p-ERK1/2 is unchanged** — this is the diagnostic feature. An ATP-competitive ERK inhibitor relieves ERK-dependent negative feedback and leaves the activation loop fully phosphorylatable by MEK, so it *increases* p-ERK. The only ERK inhibitor in this set that does **not** produce p-ERK accumulation is the **dual-mechanism** inhibitor **SCH772984**, which both blocks catalysis and prevents MEK1/2-mediated phosphorylation of ERK1/2, holding p-ERK flat. **Kidger et al. showed that dual-mechanism inhibitors caused only a gradual recovery of p-ERK1/2 over time during pathway rebound, whereas LY3214996 induced a strong accumulation of p-ERK1/2 — so the flat p-ERK profile identifies Inhibitor A as SCH722984 and the strong p-ERK accumulation (Inhibitor E) as LY3214996.**
* **p-S6 unaffected** is consistent: p-S6 is dominated by mTORC1–S6K1 input, and in a KRAS-mutant background PI3K/mTOR signalling runs in parallel, so a selective ERK-catalytic block need not reduce p-S6 at 24 h (and SCH772984 does not inhibit RSK-independent S6 phosphorylation).
* **Total ERK1/2 stable** → no ERK degradation, distinguishing A from the ERK2-degrading inhibitors B and E.

**Assignment: A = SCH722984.**

## Inhibitor B = **BVD-523 (ulixertinib)** — ATP-competitive ERK1/2 inhibitor with the strongest ERK2 degradation

**Data:** ERK2 progressively lost while ERK1 stable; p-RSK reduced; p-ERK1/2 increased; DUSP6 reduced; ubiquitinated ERK2 detectable after 8 h.

**Justification.**
* **Ubiquitinated ERK2 is detectable at 8 h, and ERK2 protein is progressively lost** → the loss is **proteasomal degradation**, as described for ERK inhibitors by Balmanno et al. (2023). All three ERK1/2 inhibitors in this set (SCH772984, BVD-523, LY3214996) have been reported to cause ERK2 degradation, but **BVD-523 is by far the strongest**, giving the progressive, ubiquitin-marked ERK2 loss seen here (A shows none, E shows a milder effect).
* **p-ERK1/2 increased with p-RSK reduced** → **BVD-523 inhibits ERK1/2 catalytic activity but does not prevent its pT-E-pY phosphorylation by MEK1/2**, so phospho-ERK accumulates while ERK output (p-RSK) is lost. This is the signature of an ATP-competitive, non-dual-mechanism ERK inhibitor.
* **DUSP6 reduced** independently confirms a true catalytic block of ERK: *DUSP6* is an ERK-dependent feedback gene, so loss of ERK transcriptional output lowers DUSP6 — which itself contributes to the rise in p-ERK (less ERK phosphatase).
* ERK1 stability alongside ERK2 loss is the isoform-selective effect analysed in Part B.

**Assignment: B = BVD-523.**

## Inhibitor C = **AZD6244 (selumetinib)** — allosteric MEK1/2 inhibitor

**Data:** p-ERK1/2 drops initially then rebounds at 8–12 h; p-RSK and p-S6 reduced at 4 h and restored by 24 h; ERK1/2 levels stable; MEK phosphorylation increases over time.

**Justification.**
* **p-ERK drops and then rebounds** — this biphasic profile is characteristic of **selumetinib, a MEK1/2 inhibitor**, which initially reduces ERK phosphorylation and then loses efficacy as the pathway reactivates.
* **p-RSK and p-S6 are transiently reduced and then rescued** — the recovery of these downstream read-outs is consistent with **reactivation of the pathway** rather than with a maintained block, exactly as expected for an allosteric MEK inhibitor subject to feedback relief.
* **MEK phosphorylation increases over time** — this **confirms feedback reactivation** and is commonly observed with MEK inhibitors (Duncan et al., 2012). An allosteric MEK inhibitor blocks MEK's catalytic output but not its phosphorylation by RAF on S217/S221, so when ERK-dependent negative feedback is lifted, RAF activity rises and **p-MEK accumulates even while its catalytic activity is inhibited**. No ERK- or RAF-level inhibitor produces rising p-MEK with recovering p-ERK.
* **Stable total ERK1/2** excludes the ERK-degrading compounds.

**Assignment: C = AZD6244.**

## Inhibitor D = **LY3009120** — pan-RAF inhibitor

**Data:** p-ERK1/2 absent throughout; p-MEK low; loss of both ERK1 and ERK2 nuclear accumulation; co-IP shows reduced MEK–ERK complex formation.

**Justification (any two of the following suffice; all are consistent).**
* **p-ERK1/2 absent throughout** — complete and sustained loss of p-ERK indicates that something **upstream** is inhibited; no ERK-level inhibitor abolishes p-ERK (they raise or maintain it), and a MEK inhibitor alone shows rebound rather than complete, durable loss.
* **p-MEK low** — low p-MEK could indicate a MEK inhibitor but **equally indicates inhibition of something upstream of MEK**; since MEK is phosphorylated by RAF, loss of p-MEK points to RAF blockade. Crucially, an allosteric MEK inhibitor would show *increased* p-MEK (as Inhibitor C does), so low p-MEK excludes the MEK inhibitor and places the block at RAF.
* **Reduced MEK–ERK complex formation by co-IP** — disrupting the MEK–ERK interaction indicates action **upstream of MEK**, because RAF scaffolding and MEK activation are required to assemble and stabilise the MEK–ERK module; pan-RAF inhibition prevents RAF–MEK–ERK complex formation.
* **Loss of ERK1 and ERK2 nuclear accumulation** — nuclear translocation of ERK requires activation-loop phosphorylation and release from cytoplasmic MEK anchoring; its loss is again **indicative of upstream inhibition** rather than of a block at ERK itself.
* **By elimination:** we are confident the MEK inhibitor is Inhibitor C (rising p-MEK with p-ERK rebound), and D cannot be an ERK inhibitor (an ERK inhibitor could not abolish p-ERK or lower p-MEK). **Therefore Inhibitor D must be the RAF inhibitor: LY3009120.** As a pan-RAF "paradox-breaker", it also avoids the paradoxical RAF-dimer activation that would otherwise raise p-MEK/p-ERK.

**Assignment: D = LY3009120.**

## Inhibitor E = **LY3214996 (temuterkib)** — ATP-competitive ERK1/2 inhibitor

**Data:** increase in p-ERK1/2; p-RSK unchanged; banding pattern inconsistent across replicates; ERK2 mRNA unchanged but protein reduced.

**Justification.**
* **LY3214996 is an ATP-competitive ERK1/2 inhibitor and has been shown to increase p-ERK**, which correlates directly with Inhibitor E's dominant phenotype: ATP-competitive binding blocks catalysis without blocking MEK-mediated pT-E-pY phosphorylation, and the loss of ERK-dependent negative feedback (DUSP/SPRY) produces a **strong accumulation of phospho-ERK1/2** — exactly the behaviour Kidger et al. contrasted with the merely gradual p-ERK recovery seen with dual-mechanism inhibitors (Inhibitor A, SCH722984). Of the two remaining candidates after A, B, C and D are assigned, only LY3214996 remains, and its documented strong p-ERK accumulation matches.
* **ERK2 mRNA unchanged but protein reduced** → a purely **post-transcriptional/post-translational** loss of ERK2, i.e. ERK2 protein destabilisation/degradation (the same class of effect as in B, but weaker — ERK inhibitors in general induce ERK2 degradation, with BVD-523 the strongest).
* **p-RSK unchanged and inconsistent banding across replicates** → technical/assay artefacts of a heavily phospho-shifted, partially degraded ERK2 pool: variable epitope accessibility on hyperphosphorylated/ubiquitinated ERK2, variable residual ERK1-dependent RSK phosphorylation (ERK1 remains and can sustain RSK output), incomplete target coverage at the dose used, and run-to-run differences in transfer/exposure. These are the hallmarks of an inhibitor whose principal, reproducible signature is p-ERK accumulation with post-transcriptional ERK2 loss, rather than a clean substrate shut-off.

**Assignment: E = LY3214996.**

## Final matching

| Inhibitor | Compound | Class |
|---|---|---|
| **A** | **SCH722984 (SCH772984)** | dual-mechanism ERK1/2 inhibitor |
| **B** | **BVD-523 (ulixertinib)** | ATP-competitive ERK1/2 inhibitor, strongest ERK2 degrader |
| **C** | **AZD6244 (selumetinib)** | allosteric MEK1/2 inhibitor |
| **D** | **LY3009120** | pan-RAF inhibitor |
| **E** | **LY3214996 (temuterkib)** | ATP-competitive ERK1/2 inhibitor |

---

# Part B. Why Inhibitor B (BVD-523) selectively reduces ERK2 but not ERK1

## Two mechanistic explanations

**Mechanism 1 — Drug-induced conformational change exposes a degron in ERK2, leading to selective ubiquitination.** BVD-523 binding to the ERK2 ATP pocket stabilises a non-native/inactive conformation in which a normally buried **degron** (a short degradation-determining motif, e.g. in the ERK2-specific C-terminal/activation-segment region) becomes solvent-exposed. An E3 ligase recognises this exposed degron, polyubiquitinates ERK2, and the proteasome degrades it. Because the degron sequence and its structural context differ between the ERK1 and ERK2 paralogues (ERK1 carries a unique ~17-residue N-terminal extension and differs in surface residues), the same drug-stabilised conformer does not create a recognisable degron in ERK1 — hence the isoform selectivity, and hence the ubiquitinated ERK2 detected at 8 h.

**Mechanism 2 — Loss of stabilising protein–protein interactions (e.g. the MEK–ERK2 scaffold) causes ERK2 to be targeted for degradation.** In the resting state, ERK2 is held in a stable complex with MEK1/2 (via the ERK D-domain/DEF-site docking interactions) and with scaffolds such as KSR1, IQGAP1, PEA-15 and MP1/p14; this binding shields ERK2 from degradative machinery. BVD-523-induced conformational change and the catalytic block disrupt these stabilising interactions (and ERK's own feedback phosphorylation of MEK1 Thr292 and of scaffolds is lost), leaving ERK2 as a "chaperone-orphaned", unprotected protein that is recognised as misfolded and degraded via the ubiquitin–proteasome system. ERK1 associates with these scaffolds with different stoichiometry/affinity and is more abundant in a scaffold-bound, protected pool, so it survives.

## How to distinguish targeted degradation from epitope unmasking/masking or aggregation

**Tests for degradation (any two are sufficient; all four together are definitive):**

1. **Proteasome inhibition.** Pre-treat with **MG132** (or bortezomib/carfilzomib) ± BVD-523 and re-blot ERK2. **If ERK2 is rescued (band restored, and higher-molecular-weight ubiquitin conjugates accumulate), the loss is due to proteasomal degradation**; if ERK2 remains absent, degradation is not the mechanism. Add a lysosomal/autophagy inhibitor arm (bafilomycin A1/chloroquine) as a specificity control.
2. **Cycloheximide chase.** Block new synthesis with cycloheximide and follow ERK2 decay ± BVD-523 over 0–12 h; **fit the decay to obtain the half-life and confirm that BVD-523 shortens ERK2 $t_{1/2}$** (and that it does not shorten ERK1 $t_{1/2}$). This measures turnover directly and is independent of any transcriptional effect.
3. **Immunoprecipitation + western blot for ubiquitin-conjugated ERK2.** Immunoprecipitate ERK2 (or pull down with TUBE/ubiquitin-affinity reagents, under denaturing conditions to exclude co-precipitating partners) and blot for ubiquitin (and vice versa: IP ubiquitin, blot ERK2), ± MG132 to accumulate the conjugates; K48-linkage-specific antibodies confirm proteasome-targeted chains. Mass spectrometry can map the modified lysines.
4. **RT-qPCR for *MAPK1* (ERK2) mRNA**, which **confirms that mRNA levels are stable and thereby rules out transcriptional repression** as the cause of protein loss (as already indicated for Inhibitor E, whose mRNA was unchanged while protein fell).

**Tests that specifically discriminate the alternatives:**

* **Epitope unmasking/masking:** re-probe with **multiple antibodies raised against different ERK2 epitopes** (N-terminal, C-terminal, activation-loop-independent, and a pan-ERK1/2 antibody), and with an orthogonal, antibody-independent quantification — **targeted mass spectrometry (PRM/SRM for ERK2-unique peptides)** or a tagged ERK2 (HA/FLAG knock-in, or ERK2-GFP) read out by anti-tag blot or in-gel fluorescence. If ERK2 is detected by some antibodies/methods but not others, the "loss" is an epitope artefact rather than true protein loss. Also check whether apparent loss depends on sample handling (phosphatase treatment, urea/SDS concentration) — a phospho- or ubiquitin-dependent mobility shift can masquerade as loss.
* **Aggregation/insolubility:** fractionate the lysate into **detergent-soluble and detergent-insoluble (pellet) fractions** and blot both — true degradation removes ERK2 from *all* fractions, whereas aggregation moves it into the insoluble pellet (or into high-molecular-weight/stacking-gel-trapped material). Complement with a **filter-trap assay**, semi-denaturing detergent-agarose gel electrophoresis, size-exclusion/velocity sedimentation, and urea/SDS re-solubilisation of the pellet; non-reducing gels and native gels test for cross-linked species.
* **Genetic confirmation:** siRNA/CRISPR knockdown of candidate E3 ligases, or a degron-mutant ERK2, should abolish the drug-induced loss if Mechanism 1 is correct; forced MEK1 over-expression (restoring the stabilising scaffold) should rescue ERK2 if Mechanism 2 is correct, and the MEK–ERK2 co-IP (already performed for Inhibitor D) can be repeated ± BVD-523 to show loss of the stabilising interaction preceding degradation.

---

# Part C. Why Inhibitor C (AZD6244/selumetinib) shows rebound of p-ERK1/2 and p-S6 at later timepoints

**The rebound is MEK/pathway reactivation driven by relief of ERK-dependent negative feedback.** The sequence is:

1. **Initial MEK inhibition by AZD6244 blocks ERK phosphorylation → p-ERK1/2 and p-RSK drop** (seen at 4 h), and with loss of ERK/RSK output, p-S6 falls as well.
2. **This loss of ERK activity suppresses the expression of ERK-dependent negative-feedback regulators — DUSP6 and SPRY1/2** (and related feedback nodes: DUSP4/5, the ERK-mediated inhibitory phosphorylation of RAF1 Ser289/296/301 and BRAF Ser151, of MEK1 Thr292, and of upstream SOS/GRB2 and EGFR/ErbB receptors). DUSP6 is the cytoplasmic ERK-specific phosphatase and SPRY1/2 restrain RAS–RAF activation, so both are ERK-induced brakes on the cascade.
3. **Without this feedback, RAS–RAF signalling increases.** In a **KRAS G12D** background, RAS is constitutively GTP-loaded, so there is abundant upstream drive the moment the brakes come off: RAF dimerisation and activity rise, receptor tyrosine kinase input is de-repressed, and the consequences are:
 * **MEK hyperphosphorylation** — the observed progressive increase in p-MEK, because an *allosteric* MEK inhibitor does not block RAF-mediated phosphorylation of MEK S217/S221, so p-MEK accumulates even while MEK catalysis is being inhibited. Increased p-MEK also means more inhibitor-occupied-but-phosphorylated MEK competing against a fixed drug concentration.
 * **Rebound ERK activation** — the raised pool of phosphorylated (activated) MEK, together with reduced DUSP6 phosphatase activity, overcomes the incomplete pharmacological blockade (and declining intracellular drug levels), so **p-ERK1/2 recovers at 8–12 h**.
 * **Reactivation of downstream effectors** — restored ERK activity re-phosphorylates **RSK**, and RSK (together with relief of ERK-dependent feedback on PI3K/mTORC1 and restored S6K1 activity) re-phosphorylates **S6**, so **p-RSK and p-S6 return by 24 h**.

**Summary of the mechanism:** inhibition of MEK removes ERK-driven transcription of DUSP6/SPRY1/2, the negative-feedback loop is broken, upstream RAS–RAF signalling is de-repressed in this KRAS G12D context, MEK becomes hyperphosphorylated, and the pathway escapes the drug — producing exactly the observed pattern of early suppression followed by rebound of p-ERK1/2, p-RSK and p-S6, with rising p-MEK as the mechanistic fingerprint. This is the classic adaptive-resistance behaviour of MEK inhibitors (Duncan et al., 2012) and is the rationale for combining a MEK inhibitor with a vertical partner (RAF or ERK inhibitor, or an RTK/SHP2 inhibitor) rather than using it alone.
