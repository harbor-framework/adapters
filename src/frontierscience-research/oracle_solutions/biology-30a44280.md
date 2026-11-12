# An optogenetic strategy for the Keap1–Nrf2 pathway

## 0. Mechanistic starting point: what in this pathway is actually "druggable" by light

Before choosing a tool, it is worth writing down the molecular steps of the pathway, because the optogenetic design must act on a **protein–protein interaction step**, not on an enzymatic active site.

1. **Keap1 is an obligate homodimer.** Keap1 (Kelch-like ECH-associated protein 1) is a sensor–adaptor protein. It dimerises through its N-terminal **BTB domain** (the Cys151-containing domain), and the dimer is bridged by the **IVR** region to **Cul3–Rbx1**, forming a CRL3^Keap1 E3 ubiquitin ligase.
2. **Only the Keap1 dimer can capture Nrf2.** The two Kelch/DGR β-propellers of the dimer engage the two degrons in the Neh2 domain of Nrf2: the high-affinity **ETGE** motif ($K_d \sim 20$ nM) and the low-affinity **DLG** motif ($K_d \sim 1$ µM). This is the "hinge-and-latch" geometry: **two** Kelch domains are needed simultaneously to position the Nrf2 lysine-rich region for polyubiquitination. A Keap1 monomer can still bind ETGE but cannot productively ubiquitinate Nrf2.
3. **Degradation vs. escape.** Under basal conditions ubiquitinated Nrf2 is destroyed by the 26S proteasome ($t_{1/2} \approx 20$ min). Electrophiles/oxidants modify Keap1 sensor cysteines (C151 in BTB, C273/C288 in the IVR), which disrupts the hinge-and-latch cycle so that newly synthesised Nrf2 escapes.
4. **Nuclear translocation.** Free Nrf2 is imported through the nuclear pore (NLS in Neh1/CNC region, importin-α5/β1 dependent).
5. **Heterodimerisation with the transcriptional activator.** In the nucleus Nrf2 must heterodimerise through its **CNC-bZIP (Neh1)** domain with a **small Maf protein (MafG/MafK/MafF)**. Only the **Nrf2–sMaf heterodimer** binds the antioxidant/electrophile response element (ARE/EpRE, 5′-TGACnnnGC-3′) and, with CBP/p300 recruited via Neh4/Neh5, induces the cytoprotective battery: *NQO1, HMOX1, GCLC, GCLM, TXN1, TXNRD1, SRXN1, GSTs, SLC7A11, FTL/FTH1, G6PD, ME1, PGD*.

Every step that light can control here is therefore an **interaction/localisation** step: Keap1 homodimerisation, Nrf2 nuclear transit, and Nrf2–sMaf heterodimerisation. That observation drives the whole design below.

---

## 1. Optogenetic techniques available as options for this perturbation

Below are nine options, with how each works and what it buys us for Keap1–Nrf2. (Any six of these would be sufficient to cover the design space; all nine are listed for completeness.)

1. **Microbial opsins (e.g. channelrhodopsin-2, ChR2–YFP; halorhodopsin NpHR; Arch).** Seven-transmembrane retinal-binding light-gated ion channels/pumps. Blue light (~470 nm) opens ChR2 and depolarises the membrane/admits Ca²⁺; the YFP fusion reports expression. These are *activity* actuators rather than interaction actuators: for Keap1–Nrf2 they are useful only indirectly (Ca²⁺/depolarisation-driven ROS changes), so they are the weakest option here.
2. **Modular photoreceptors.** The generic design principle: a natural photoreceptor is split into a modular light-sensing domain (chromophore-binding) plus an effector domain, and the sensing domain is grafted onto a protein of interest so that illumination changes the effector's conformation, oligomerisation state or accessibility. This is the conceptual chassis for everything below.
3. **Phytochrome–PIF system (PhyB–PIF3/PIF6).** Plant phytochrome B binds phycocyanobilin; 650 nm red light converts Pr→Pfr, which binds PIF; 750 nm far-red light reverts it. Gives bidirectional, reversible, near-instant recruitment of a PIF-fused protein to a PhyB-fused anchor — but requires exogenous chromophore in mammalian cells.
4. **CRY2/CIB system (cryptochrome 2 PHR domain + CIB1/CIBN).** *Arabidopsis* CRY2 uses endogenous flavin (FAD), so no exogenous chromophore is needed in mammalian cells. Blue light (450–488 nm) does two things: (i) CRY2 binds CIB1, allowing light-induced heterodimerisation/recruitment, and (ii) CRY2(PHR) **homo-oligomerises into clusters ("CRY2olig"/CRY2clust)**. Dark reversion occurs in ~5 min. This clustering/sequestration behaviour is exactly what is needed to force or forbid a dimerisation event, and it is the module I use for all three designs.
5. **Fluorescent proteins as photo-actuators and read-outs.** Dronpa-145N and PhoCl-type FP scaffolds photo-switch/dissociate under light, allowing light-controlled caging of a fused peptide or domain; conventional FPs (mCherry, YFP) are also used as the imaging read-out of clustering and of nucleo-cytoplasmic ratio.
6. **Intrabodies (IB) against endogenous proteins.** A nanobody/scFv that recognises an endogenous epitope is fused to an optogenetic module (CRY2, LOV, or a light-controlled degron). This avoids over-expressing a tagged version of the target — light then clusters, sequesters or degrades the *endogenous* Keap1 or Nrf2.
7. **LOV (light–oxygen–voltage) domain systems (AsLOV2-based iLID/SspB, LOVTRAP/Zdk1, EL222, Vivid/VVD, BcLOV4).** FMN-binding domains in which blue light unlatches a Jα helix. Used either to *uncage* a motif (iLID exposes an SsrA peptide that binds SspB) or to *release* a binder (LOVTRAP: Zdk1 dissociates in the light). Ideal for light-controlled caging of the DLG/ETGE degron or of an NLS.
8. **BphP1–Q-PAS1 (bacteriophytochrome system).** *Rhodopseudomonas palustris* BphP1 uses endogenous **biliverdin** and binds Q-PAS1 under **near-infrared (740–780 nm)** light. NIR gives deep tissue penetration and minimal phototoxicity — the option of choice for *in vivo* liver/intestine experiments.
9. **PhoCl (photocleavable protein).** A green-to-violet photoconvertible FP engineered so that violet light (~400 nm) induces backbone cleavage and dissociation. Fusing PhoCl between a target and an anchor/degron allows **irreversible, single-shot** release — useful for uncaging Nrf2 or for triggering degradation at a defined instant.

Additional options worth noting: **Magnets (pMag/nMag)**, **UVR8**, **Dronpa dimerisation switches**, and **light-controlled degrons (B-LID, psd, LOV-degron)** which directly destroy a tagged protein under illumination.

**Chosen module for all three designs: CRY2(PHR)/CIB1**, because (i) it needs no exogenous chromophore, (ii) it gives *both* light-induced heterodimerisation and light-induced clustering, and (iii) clustering is the single most effective way to sequester a protein away from an obligate dimerisation or translocation step. PhyB–PIF, iLID/LOV and BphP1–Q-PAS1 are retained as orthogonal/NIR alternatives.

---

## 2. Possible targets for optogenetic perturbation in this pathway

Three principal nodes, which map onto the three interaction steps identified in §0:

* **Target 1 — Keap1 itself.** Keap1 is the sensor–adaptor protein that binds Nrf2 and delivers it to Cul3 for ubiquitination. Because it must be a **homodimer** to work, it is intrinsically light-targetable: anything that stops BTB-mediated homodimerisation inactivates the ligase. Keap1 is therefore the first and best target.
* **Target 2 — Nrf2 itself.** Nrf2 must physically translocate from cytoplasm to nucleus. Anything that immobilises it in the cytoplasm blocks the pathway at the level of localisation.
* **Target 3 — the transcriptional activator/partner complex in the nucleus**, i.e. the site where Nrf2 binds its transcriptional activator partner (small Maf, MafG/MafK/MafF, and the CBP/p300 coactivator). Blocking the Nrf2–Maf interface prevents ARE-driven transcription even when Nrf2 is nuclear.

(Secondary, lower-priority nodes: Cul3/Rbx1 recruitment, β-TrCP/GSK-3β-dependent Nrf2 degradation, p62/SQSTM1 competition for the Keap1 Kelch pocket, importin-α5, and BACH1 as the ARE repressor. These are mentioned for completeness but the three nodes above give clean gain- and loss-of-function control.)

---

## 3. Each target, the construct, and the consequence for pathway function

### Option 1 — Optogenetic Keap1: light-induced clustering blocks Keap1 homodimerisation → **gain of function** of Nrf2 target genes

**Construct.** Knock in / express **Keap1–CRY2(PHR)–mCherry** (tag on the C-terminus, away from the BTB dimerisation surface), together with a membrane- or cytoskeleton-anchored **CIB1** partner (e.g. CIBN–CAAX) to sharpen the sequestration. An intrabody format (anti-Keap1 nanobody–CRY2) can be used instead to act on endogenous Keap1.

**Mechanism.** Blue light (450–488 nm) drives CRY2 PHR **homo-oligomerisation**, so the Keap1–CRY2 fusion collapses into micron-scale clusters (and, with CIBN–CAAX, is simultaneously recruited to the plasma membrane). Inside these clusters the Keap1 molecules are sterically locked in a non-productive geometry: the BTB domains can no longer pair correctly, and **Keap1 cannot form its functional homodimer**. Consequently:

* No properly oriented pair of Kelch β-propellers is presented, so the hinge-and-latch capture of the Nrf2 DLG+ETGE degrons fails;
* CRL3^Keap1 cannot polyubiquitinate Nrf2, so **Nrf2 is not degraded** and its half-life rises from ~20 min to hours;
* Stabilised Nrf2 accumulates and **translocates to the nucleus**, heterodimerises with small Maf, binds AREs and drives **transcription of Nrf2 target genes** (*NQO1, HMOX1, GCLC/GCLM, TXNRD1, SLC7A11, FTL/FTH1*).

**Classification: this is a light-induced "gain-of-function" intervention with respect to Nrf2 target genes** — it switches the cytoprotective transcriptional programme ON, phenocopying electrophilic stress or a *KEAP1*-loss tumour, but reversibly (dark reversion in ~5 min, with target-gene mRNAs decaying over hours).

**Read-outs.** mCherry cluster formation; Nrf2 immunofluorescence nuclear/cytoplasmic ratio; ARE-luciferase; NQO1/HMOX1 qPCR and western; cycloheximide chase for Nrf2 half-life; glutathione (GSH/GSSG) and roGFP2-Orp1 for the redox consequence.

### Option 2 — Optogenetic Nrf2: light-induced clustering prevents nuclear entry → **loss of function** of Nrf2 target genes

**Construct.** **Nrf2–CRY2(PHR)–EGFP** (plus optional CIBN–CAAX or CIBN–mito anchor to immobilise the clusters in the cytoplasm).

**Mechanism.** Blue light oligomerises the CRY2 moiety, so **the Nrf2 protein is driven into large cytoplasmic clusters**. These assemblies are far above the ~40 kDa passive-diffusion limit and their NLS is buried/avidity-trapped, so the clustered Nrf2 **cannot move through the nuclear membrane** (nuclear pore complex) even when the Keap1 ligase is inhibited by stress. Because Nrf2 never reaches the nucleoplasm:

* **It cannot heterodimerise with its transcriptional activator partner, the small Maf proteins (MafG/MafK/MafF)**, which are the partners that, together with Nrf2, actually **induce expression of the target genes** at AREs;
* No Nrf2–sMaf heterodimer forms on the ARE, no CBP/p300 is recruited, and **Nrf2 target genes are not transcribed**.

**Classification: this is a light-induced "loss-of-function" intervention with respect to Nrf2 target genes** — an acute, reversible, spatially restricted *NFE2L2*-knockdown equivalent, achieved without changing Nrf2 protein levels. A particular advantage is that it works even in cells where Keap1 is already inactivated (e.g. *KEAP1*-mutant tumour cells), because it acts downstream of degradation.

**Read-outs.** Loss of nuclear EGFP signal and appearance of cytoplasmic puncta; co-IP showing loss of Nrf2–MafG complex; ARE-luciferase collapse; NQO1/HMOX1/GCLM mRNA loss; increased sensitivity to H₂O₂, diamide, tBHQ-withdrawal or cisplatin.

### Option 3 — Optogenetic targeting of the transcriptional activator/complex itself → **loss of function** of Nrf2 target genes

**Construct.** Put the optogenetic module on the **transcriptional activator with which Nrf2 partners in the nucleus** — i.e. **MafG(/MafK)–CRY2(PHR)–mCherry**, optionally with a CIB1 anchor tethered to a nuclear structure (CIBN–lamin B, or CIBN fused to a heterochromatin/nucleolar anchor). An equivalent version places CRY2 on the CNC-bZIP (Neh1) surface of Nrf2, or uses a CRY2-fused intrabody/nanobody directed at the Nrf2–Maf interface or at the CBP/p300 KIX-binding Neh4/Neh5 surface.

**Mechanism.** Under blue light the CRY2 module clusters/sequesters the activator so that **the Nrf2 protein is prevented from binding to the transcriptional activator in the nucleus**. The bZIP leucine-zipper/basic-region interface that normally forms the Nrf2–sMaf heterodimer is occluded by the oligomer, and the activator is physically pulled away from ARE-containing promoters. Therefore:

* Nrf2 can still be stabilised and can still enter the nucleus, but it arrives as a partner-less monomer that cannot bind ARE with high affinity;
* **The transcriptional activator cannot induce expression of Nrf2 target genes** — no ARE occupancy, no coactivator recruitment, no transcription of *NQO1, HMOX1, GCLC, GCLM, TXNRD1, SLC7A11*.

**Classification: this is a light-induced "loss-of-function" intervention with respect to Nrf2 target genes**, acting at the most distal point of the pathway. Because small Mafs also partner Nrf1/Nrf3/BACH1, the specificity controls are: CRY2-nanobody against the Nrf2-specific Neh1 surface, and ChIP-qPCR at ARE loci.

**Read-outs.** ChIP-qPCR/CUT&RUN for Nrf2 and MafG at *NQO1*/*HMOX1* AREs; proximity ligation or FRET loss between Nrf2 and MafG; ARE-luciferase; target-gene qPCR; nascent transcription (4sU-seq) to prove the block is transcriptional.

### Summary table

| Option | Target | Construct | Interaction blocked | Direct consequence | Pathway output |
|---|---|---|---|---|---|
| 1 | **Keap1** (sensor–adaptor) | Keap1–CRY2/CIB | **Keap1 homodimerisation** (BTB) | Nrf2 not ubiquitinated, not degraded; Nrf2 enters nucleus | **Gain of function** of Nrf2 target genes |
| 2 | **Nrf2** | Nrf2–CRY2/CIB | **Nuclear translocation**, hence Nrf2–**Maf** heterodimerisation | Target genes not transcribed | **Loss of function** of Nrf2 target genes |
| 3 | **Transcriptional activator complex (small Maf / Nrf2–Maf interface)** | MafG–CRY2/CIB (or anti-Neh1 intrabody–CRY2) | **Nrf2 binding to the transcriptional activator in the nucleus** | Activator cannot induce target-gene expression | **Loss of function** of Nrf2 target genes |

---

## 4. The main type of protein interaction that optogenetic manipulation impacts here

The pathway is not controlled by catalysis but by **stoichiometric protein–protein association and compartmentalisation**. Accordingly, the two classes of interaction that optogenetic manipulation impacts are:

1. **Dimerisation** — and specifically **homodimerisation of Keap1** through its BTB domain, which is the obligatory requirement for a functional CRL3^Keap1 ligase and for hinge-and-latch capture of the Nrf2 DLG/ETGE degrons. Light-induced CRY2 clustering is, in effect, a dimerisation switch: it forbids the native Keap1 homodimer. The same logic extends to the **heterodimerisation** of Nrf2 with small Maf (the bZIP leucine-zipper interaction that makes a competent transcription factor).
2. **Nuclear translocation** — the regulated nucleocytoplasmic shuttling of Nrf2 through the nuclear pore. Because clustered Nrf2 is excluded from the nucleus, light converts a localisation step into a controllable switch; and because translocation is a prerequisite for Nrf2–Maf dimerisation, blocking translocation also blocks dimerisation.

So the answer is: **dimerisation (above all Keap1 homodimerisation, plus Nrf2–sMaf heterodimerisation) and nuclear translocation.** Degron/adaptor recognition (Keap1-Kelch↔Nrf2-ETGE/DLG) and coactivator recruitment are the subordinate interfaces that these two master interactions control.

---

## 5. What would happen to homeostasis if this pathway were manipulated with optogenetics

**(a) Redox homeostasis.** Nrf2 sets the cell's reductive buffering capacity. Light-ON of Option 1 (gain of function) raises GSH synthesis (GCLC/GCLM), cystine import (SLC7A11), NADPH supply (G6PD, PGD, ME1, IDH1), thioredoxin/peroxiredoxin flux and haem/iron handling (HMOX1, FTL/FTH1). Acutely this is protective: cells resist H₂O₂, electrophiles, lipid peroxidation and ferroptosis. Chronically, however, the cell is pushed into **reductive stress** — the ROS tone that normally acts as a second messenger is quenched, so redox-dependent signalling (PTP oxidation, ASK1, HIF-1α stabilisation, redox-regulated differentiation cues) is blunted. In malignant cells persistent Nrf2 activation is pro-survival and confers chemo/radio-resistance (the "dark side" of Nrf2), so a sustained light-ON regime is predicted to promote cancer cell survival, while transient pulses are cytoprotective without that cost. Conversely, light-ON of Options 2/3 (loss of function) collapses GSH/NADPH buffering, raising steady-state ROS, lipid peroxidation and ferroptosis sensitivity.

**(b) Proliferative homeostasis of stem cells — the intestinal epithelium as the clearest example.** Nrf2 is a direct regulator of **the proliferative activity of intestinal stem cells (ISCs)** and hence of **intestinal homeostasis**, acting through exactly this redox mechanism: Nrf2 keeps ISC ROS within the window permissive for self-renewal. Optogenetic perturbation therefore reads out as a tissue-level phenotype:

* **Light-induced loss of Nrf2 function (Options 2 and 3) in ISCs** depletes the GSH/thioredoxin systems, ROS rise above the permissive window, and ISCs lose proliferative/regenerative capacity, with increased apoptosis and impaired crypt regeneration. **Loss of Nrf2 in intestinal stem cells accelerates age-related degeneration of the intestinal epithelium** — crypt/villus architecture deteriorates, the barrier becomes leaky, dysbiosis and inflammation follow, and the epithelium ages prematurely. Because blue illumination can be delivered to a single crypt, this can be shown cell-autonomously and compared with neighbouring unilluminated crypts in the same animal.
* **Light-induced gain of Nrf2 function (Option 1) in ISCs** lowers ROS, enhances stress resistance and supports ISC proliferation and crypt regeneration after injury/irradiation — but if held ON, the same programme risks over-proliferation, loss of differentiation cues, expansion of damaged clones and, together with other hits, adenoma formation. Non-cell-autonomously, Nrf2 gain in Paneth/goblet cells alters mucus and antimicrobial output, which feeds back on the microbiota and on barrier homeostasis.

**(c) Whole-organism homeostasis.** Keap1–Nrf2 integrates xenobiotic detoxification (phase II enzymes), inflammatory tone (NF-κB cross-talk, NLRP3), iron/haem homeostasis, proteostasis (p62/autophagy) and metabolic reprogramming. Systemic, sustained optogenetic gain of function would therefore mimic *KEAP1*-loss states (chemoprotection, but also reductive stress, altered drug metabolism and tumour-cell survival), while sustained loss of function would mimic *Nfe2l2*-null states (susceptibility to oxidants, electrophiles, inflammation and accelerated degeneration in high-turnover tissues such as the gut).

**(d) Why optogenetics is the right tool for this question.** The decisive advantage is that homeostasis is a *dynamic* set-point. With CRY2/CIB (dark reversion in minutes) or BphP1–Q-PAS1 (NIR, deep tissue), the pathway can be clamped ON or OFF with second-to-minute kinetics in defined cells (e.g. *Lgr5*⁺ ISCs) and then released, so one can separate the acute, adaptive, reversible arm of Nrf2 signalling from the chronic, maladaptive arm — something neither constitutive knockouts nor small-molecule inducers (sulforaphane, bardoxolone, dimethyl fumarate) can do.

---

## Final answer (condensed)

1. **Techniques available:** microbial opsins (ChR2–YFP), modular photoreceptors, PhyB–PIF, **CRY2/CIB**, photoswitchable fluorescent proteins, optogenetic intrabodies, LOV-domain systems (AsLOV2/iLID, LOVTRAP, EL222), BphP1–Q-PAS1 (NIR), PhoCl — plus Magnets/UVR8 and light-controlled degrons.
2. **Targets:** (i) **Keap1**, the sensor–adaptor that binds Nrf2; (ii) **Nrf2** itself; (iii) the **nuclear transcriptional activator/complex** where Nrf2 binds its partner (small Maf, with CBP/p300).
3. **Consequences:** (i) Keap1–CRY2/CIB clustering **prevents Keap1 homodimerisation** → Nrf2 is not degraded, translocates to the nucleus and drives target-gene transcription = **gain of function**; (ii) Nrf2–CRY2/CIB clustering **prevents passage through the nuclear membrane**, so Nrf2 cannot dimerise with **Maf** and target genes are not transcribed = **loss of function**; (iii) CRY2/CIB on the activator **prevents Nrf2 from binding the transcriptional activator in the nucleus**, so the activator cannot induce target-gene expression = **loss of function**.
4. **Interactions impacted:** **dimerisation — specifically Keap1 homodimerisation (and Nrf2–sMaf heterodimerisation) — and nuclear translocation.**
5. **Homeostasis:** light control of this pathway retunes redox homeostasis (GSH/NADPH/thioredoxin, ferroptosis sensitivity) and, in the gut, the **proliferative activity of intestinal stem cells and intestinal homeostasis**; Nrf2 loss of function in ISCs raises ROS and **accelerates age-related degeneration of the intestinal epithelium**, whereas sustained gain of function protects against oxidative injury but risks reductive stress, over-proliferation and tumour-cell survival.
