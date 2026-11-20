# Oxidative damage to RNA and DNA: 8-oxoG burden in Alzheimer's disease, transcript-selective oxidation, and 8-oxo-dG as a regulatory mark

## Part 1) Explaining <2% versus >50% immunoprecipitation of the neuronal mRNA pool by an 8-oxoG antibody

The comparison is: **less than 2%** of the total neuronal mRNA pool pulled down by an anti-8-oxoG antibody in healthy individuals, versus **more than 50%** in Alzheimer's disease (AD) patients. A >25-fold apparent difference is large enough that both genuine biological mechanisms and technical/experimental explanations must be considered. It is possible to explain the discrepancy, and a complete explanation has four parts.

### 1.1 ROS are an unavoidable by-product of metabolism

8-oxo-7,8-dihydroguanosine (8-oxoG) is formed when **reactive oxygen species (ROS)** attack the C8 position of the guanine base — guanine being the most readily oxidised of the four bases because it has the lowest one-electron reduction potential. The supply of ROS is therefore the primary determinant of 8-oxoG burden, and **ROS are generated as an unavoidable by-product of normal metabolic reactions**:

- **Mitochondrial electron transport is the dominant source.** During oxidative phosphorylation, electrons passing through the respiratory chain can be transferred prematurely and univalently to molecular oxygen, chiefly at **Complex I (NADH:ubiquinone oxidoreductase)** and at **Complex III (the ubiquinol–cytochrome *c* oxidoreductase Q-cycle, via the semiquinone intermediate)**, **producing superoxide radicals ($\mathrm{O_2^{\bullet-}}$)**. Typically a small but non-trivial percentage of total electron flux leaks in this way, in proportion to respiratory rate and to the degree of reduction of the carriers (high proton-motive force and reverse electron transport increase leak).
- Superoxide is then dismutated by **SOD1/SOD2** to **hydrogen peroxide ($\mathrm{H_2O_2}$)**, which, in the presence of redox-active transition metals (Fe²⁺, Cu⁺), yields the highly reactive **hydroxyl radical ($\mathrm{^{\bullet}OH}$)** through **Fenton/Haber–Weiss chemistry**: $\mathrm{Fe^{2+} + H_2O_2 \rightarrow Fe^{3+} + {}^{\bullet}OH + OH^-}$. It is principally $\mathrm{^{\bullet}OH}$ (and peroxynitrite, formed from $\mathrm{O_2^{\bullet-}} + \mathrm{NO^{\bullet}}$) that oxidises guanine to 8-oxoG.
- Additional metabolic ROS sources: NADPH oxidases (NOX/DUOX), monoamine oxidase (highly relevant in neurons that metabolise catecholamines), xanthine oxidase, peroxisomal β-oxidation, cytochrome P450 reactions and ER oxidative protein folding (ERO1/PDI).

So the ROS level, and hence the steady-state 8-oxoG level, is a direct function of metabolic flux: **oxidative damage is an intrinsic cost of metabolism**, counterbalanced by antioxidant defences (SOD, catalase, glutathione peroxidase/glutathione, thioredoxin/peroxiredoxin, vitamins C and E) and by damage-removal systems.

### 1.2 Neurons — in healthy individuals *and* in AD patients — are especially prone to accumulating oxidised RNA

Neurons sit at the extreme end of the metabolic-risk spectrum, and this matters for *both* groups, not only for the patients:

- **Neurons have exceptionally high energy usage and a high metabolic rate.** The brain consumes roughly 20% of the body's oxygen and glucose while representing ~2% of body mass, and the great majority of neuronal ATP is spent restoring ion gradients after synaptic and action-potential activity (Na⁺/K⁺-ATPase, Ca²⁺ handling, neurotransmitter cycling). Neurons are almost entirely dependent on **oxidative phosphorylation** rather than glycolysis, so their electron-transport flux — and therefore their **rate of superoxide production** — is correspondingly high. **High ROS levels are the direct consequence, and these contribute to oxidative damage of nucleic acids.**
- Neurons also have **comparatively modest antioxidant capacity** (notably low catalase and relatively low glutathione compared with astrocytes, on which they depend for glutathione precursors), **high polyunsaturated fatty acid content** (lipid peroxidation generating secondary reactive aldehydes), **high iron and copper content** in several regions (feeding Fenton chemistry), and **monoamine oxidase-dependent $\mathrm{H_2O_2}$ production**.
- Critically, **neurons are post-mitotic and extremely long-lived**: they cannot dilute damaged macromolecules by division, so oxidative lesions and oxidised transcripts **accumulate over the lifetime of the cell**. Long-lived mRNAs — and transcripts stalled in dendritic transport granules or in stress granules — are exposed for correspondingly long periods.

Hence a measurable 8-oxoG burden in the neuronal mRNA pool is expected even in health (consistent with the <2% baseline), and neurons are the cell type in which an increase in ROS, or a decrease in damage removal, will produce the largest change in oxidised-RNA content.

### 1.3 Disease-specific amplification: impaired RNA quality control in AD

A >25-fold rise is unlikely to be produced by increased ROS production alone; it also implies a **failure to remove or dispose of oxidised transcripts**. Steady-state damage is set by a balance:

$$[\text{8-oxoG-RNA}]_{ss} = \frac{k_{\text{oxidation}}}{k_{\text{removal}}}$$

so an apparently enormous increase can arise from a modest rise in $k_{\text{oxidation}}$ combined with a fall in $k_{\text{removal}}$.

**The RNA quality-control mechanisms that normally recognise and clear oxidatively damaged RNA may be impaired in AD patients.** Relevant systems include:

- **Surveillance/binding proteins that recognise 8-oxoG-containing RNA** — e.g. **PCBP1/PCBP2, hnRNP D (AUF1), YB-1, polynucleotide phosphorylase (PNPT1)** and **Ago2**-associated pathways — which bind oxidised transcripts and route them for degradation and/or exclude them from translation.
- **Ribonucleolytic and exosome-mediated decay** (the cytoplasmic RNA exosome, XRN1, no-go/non-stop decay pathways that clear ribosomes stalled on damaged templates).
- **Sanitisation of the nucleotide pool** — **MTH1 (NUDT1)**, which hydrolyses 8-oxo-dGTP/8-oxo-GTP and so prevents incorporation of pre-oxidised nucleotides into nascent RNA and DNA; and **NUDT5/NUDT18** acting on related substrates.
- **Autophagy/lysosomal clearance and the proteasome**, both documented to be impaired in AD, which handle oxidised ribonucleoprotein aggregates.

In AD, mitochondrial dysfunction (reduced Complex I/IV activity), Aβ- and tau-driven oxidative stress, iron dyshomeostasis, impaired autophagy and widespread RNA-binding-protein pathology (TDP-43, hnRNP and stress-granule abnormalities that sequester the very proteins needed for surveillance) would all be expected to depress $k_{\text{removal}}$ while raising $k_{\text{oxidation}}$ — a combination that can plausibly generate the observed jump from <2% to >50%.

### 1.4 The experimental-design caveat: antibody specificity

Before accepting the figures at face value, the **immunoprecipitation design itself must be questioned**, and this is a genuine alternative explanation for the discrepancy:

- **The anti-8-oxoG antibody may be non-specific.** Antibodies raised against a single modified base on a polynucleotide backbone are notoriously cross-reactive, because the epitope is small, is chemically similar to many related species, and is presented in a highly variable sequence/structural context. Such an antibody can recognise **other, structurally similar modifications and oxidation products** (8-oxo-dG in DNA, other oxidised purines such as 8-nitroguanine, FapyG, 8-hydroxyadenine, and other modified bases including m⁷G, m¹A or 7-methylguanine-containing species), free 8-oxo-G nucleosides/nucleotides, and in particular it can **pull down RNA–protein complexes (ribonucleoprotein particles) non-specifically** rather than 8-oxoG-modified RNA itself.
- This matters most in exactly the samples where the large signal is seen. **AD patient cells are rich in abnormal RNA–protein complexes and aggregates** — stress granules, TDP-43 and hnRNP inclusions, tau- and Aβ-associated ribonucleoprotein assemblies, dysregulated RNA-binding-protein condensates, and lipofuscin/aggregate material. If the antibody has affinity for such complexes (or if they adsorb to beads), then a single oxidised transcript, or a single antibody-reactive protein, within a large ribonucleoprotein assembly will bring down **many non-oxidised mRNAs with it**, grossly inflating the apparent fraction of the mRNA pool that is "8-oxoG-positive". The >50% figure would then measure the abundance of aggregated RNP material in AD neurons rather than the extent of RNA oxidation.
- Additional technical confounders pointing the same way: **ex vivo oxidation artefacts** during tissue collection, post-mortem interval and RNA extraction (phenol/metal-catalysed oxidation during workup is a well-known source of spurious 8-oxoG, and AD and control tissues often differ systematically in post-mortem interval and agonal state); **differences in input RNA integrity** (degraded AD RNA gives more fragment ends and more non-specific binding); **absence of appropriate controls**; and a **non-linear, saturable antibody–epitope relationship** that makes percentage-of-pool figures a poor quantitative scale.

**Controls needed to discriminate these possibilities:** an isotype-matched IgG control and a bead-only control; competition with free 8-oxo-G nucleoside (signal should be abolished) versus unmodified G (no effect); spike-in of in-vitro-synthesised oxidised and non-oxidised transcripts at known 8-oxoG stoichiometry to build a standard curve; RNase/proteinase treatment to break up RNP complexes before IP; validation of the absolute lesion frequency by an orthogonal, antibody-free method — **HPLC with electrochemical detection or LC-MS/MS quantification of 8-oxoG per 10⁶ G** — with anti-oxidant/metal chelator (deferoxamine, TEMPO) added during extraction to suppress artefactual oxidation; and single-nucleotide-resolution mapping to confirm that the pulled-down transcripts actually carry lesions.

### Final answer (Part 1)

Yes, the discrepancy can be explained, and most likely by a combination of all of the following: (i) **ROS are an inevitable by-product of metabolic reactions — notably superoxide radicals generated by electron leak at Complexes I and III of the electron transport chain**, converted via $\mathrm{H_2O_2}$ and Fenton chemistry to the hydroxyl radicals that oxidise guanine to 8-oxoG; (ii) **neurons in both AD patients and healthy individuals are especially prone to accumulating oxidised RNA, because their high energy usage and high metabolic rate generate high ROS levels that drive oxidative damage**, compounded by weak antioxidant defences and by their post-mitotic longevity; (iii) in AD, the **RNA quality-control/surveillance machinery that normally recognises and degrades oxidatively damaged RNA may be impaired**, so damaged transcripts accumulate rather than being cleared, amplifying a modest rise in damage rate into a very large rise in steady-state damage; and (iv) critically, the **experimental design may be at fault — the 8-oxoG antibody may be non-specific and may be pulling down other RNA–protein complexes, and modifications similar to 8-oxo-G, that are abundant in AD patient cells**, thereby exaggerating the apparent oxidised fraction. Orthogonal, antibody-independent quantification (HPLC-ECD/LC-MS/MS) with appropriate IgG, competition and spike-in controls is required before the >50% figure is accepted.

---

## Part 2) Why do different RNA types show different oxidation levels even though ROS depend on the cellular environment?

The naive prediction — if ROS are a property of the cellular environment, then the probability of any given nucleotide being hit is uniform, so damage per transcript species should scale only with **transcript abundance** (and length) — fails because the reaction is not a well-mixed, uniform-exposure process. Three features of RNA biology break the assumption, and each predicts transcript-selective oxidation.

### 2.1 Subcellular localisation of the transcript determines its ROS exposure

ROS are extremely short-lived and act over very short diffusion distances (the hydroxyl radical has a diffusion radius of only nanometres before it reacts), so the concentration of oxidant experienced by an RNA molecule is set by **where in the cell that molecule resides**, not by a cell-average value. Oxidant production is strongly spatially heterogeneous — it is concentrated at specific membranes and organelles. Therefore:

- **An RNA transcript's location within the cell strongly affects its susceptibility to oxidation.** Transcripts localised **close to mitochondria** sit beside the dominant superoxide/$\mathrm{H_2O_2}$ source (Complex I/III) and are much more heavily oxidised — this includes mitochondrially encoded RNAs, mRNAs translated on the outer mitochondrial surface, and transcripts in mitochondria-rich compartments (e.g. in synaptic terminals and dendrites). Likewise transcripts localised **adjacent to the plasma membrane** are exposed to NADPH oxidase (NOX)-derived ROS and to ROS generated by lipid peroxidation of membrane PUFAs.
- Conversely, nuclear transcripts are relatively protected (compartmental antioxidants, chromatin and protein shielding, and distance from mitochondria), while transcripts in ER-associated, peroxisomal or stress-granule microenvironments each experience their own characteristic oxidant flux.

### 2.2 The extent of protein association of an RNA species determines its protection

RNA in the cell is never naked: it is coated by RNA-binding proteins, packaged into ribonucleoprotein particles, bound by ribosomes, or housed in granules. Bound protein sterically occludes the bases, can scavenge radicals before they reach the RNA, and alters local accessibility of the C8 position of guanine. Equally, some associations *increase* risk by holding the transcript in an oxidant-rich location or in an exposed, single-stranded conformation.

- **RNA oxidative damage therefore correlates with the extent (and nature) of protein association of that RNA species.** Heavily and stably protein-coated RNAs (for instance ribosomal RNA within the assembled ribosome, or tRNAs with their extensive secondary/tertiary structure and bound proteins) are shielded relative to transcripts that are sparsely bound, in an exposed single-stranded state, or bound by proteins that recruit them to oxidant-rich sites. Differences in RBP occupancy between transcript classes thus generate systematic differences in 8-oxoG content that are entirely independent of abundance.
- Secondary structure acts in the same direction: guanines in single-stranded loops, in G-rich tracts and in G-quadruplexes are intrinsically more oxidisable (G-quadruplexes being particularly prone, since the lowest ionisation potential in a stacked G-tetrad delocalises the hole and funnels oxidation to specific guanines), while duplex-paired and protein-clamped guanines are less accessible.

### 2.3 A concrete example

A clear demonstration that oxidation is transcript-selective and association-dependent rather than purely abundance-driven is the behaviour of polyadenylated RNA:

> **PolyA-RNA has 5× higher levels of 8-oxoG than total RNA.**

That is, the polyadenylated (mRNA) fraction carries roughly a **five-fold greater 8-oxoG burden** than the total RNA pool from the same cells. Since total RNA is numerically dominated by rRNA and tRNA, which are abundant, highly structured and heavily protein-associated, while polyA mRNA is comparatively lightly and dynamically protein-bound, often single-stranded during translation, and frequently localised to mitochondria-adjacent and membrane-proximal translation sites, the five-fold enrichment is exactly what the localisation and protein-association arguments predict — and it is the opposite of what pure abundance-scaling would predict. (Other examples consistent with the same principle: mitochondrially encoded transcripts are oxidised far more than nuclear-encoded transcripts of equal abundance; individual mRNAs differ in 8-oxoG content by an order of magnitude independently of their expression level; and transcripts in dendritic transport granules and stress granules show distinctive damage levels.)

### 2.4 Additional contributors

- **Transcript lifetime:** a long-lived transcript accumulates damage for longer at the same hit rate, so stable mRNAs are more oxidised than short-lived ones of equal abundance.
- **Differential surveillance/turnover:** transcripts recognised efficiently by the 8-oxoG-surveillance proteins (PCBP1/2, AUF1, YB-1, PNPT1) are cleared faster, lowering their steady-state damage; those that escape surveillance accumulate lesions.
- **Sequence composition:** GG and GGG runs and overall G content set the number of preferred oxidation targets per transcript, and 5′-GG-3′ doublets are hotspots because the hole localises on the 5′ G.
- **Nucleotide-pool contamination:** pre-oxidised 8-oxo-GTP incorporated by RNA polymerase (when MTH1 sanitisation is insufficient) introduces lesions in proportion to transcription rate rather than to local ROS, giving another abundance-independent route.

### Final answer (Part 2)

Oxidation is not uniform because ROS act over nanometre distances and RNA is neither uniformly distributed nor uniformly exposed. **An RNA's location in the cell determines its oxidant exposure — transcripts sitting close to mitochondria or adjacent to the cell membrane are far more oxidised than those in protected compartments — and the oxidative damage of an RNA species correlates with the extent of its protein association**, since bound RBPs, ribosomes and ribonucleoprotein packaging shield bases while sparse or exposed single-stranded regions are vulnerable. A clear example is that **polyA-RNA has 5× higher levels of 8-oxoG than total RNA**. Transcript lifetime, differential surveillance/turnover, G-rich sequence context and incorporation of pre-oxidised nucleotides add further abundance-independent contributions.

---

## Part 3) What does the VEGF promoter result suggest about the role of the 8-oxo-dG modification?

### 3.1 The observations and the apparent paradox

Two sets of findings must be reconciled:

1. **Synthetic placement of 8-oxo-dG in certain promoter regions activates transcription of reporter genes** — i.e. the lesion, introduced deliberately and site-specifically, is sufficient to turn a promoter on. Activation is therefore a *direct property of the modified base in that sequence context*, not a downstream consequence of generalised stress signalling.
2. **Oxidative stress oxidises the VEGF promoter, and the resulting reduced binding of SP1 to the G-rich elements increases transcription.** Here the lesion acts by *changing the occupancy of a sequence-specific transcription factor* at a G-rich element, and the direction of the effect is an increase in transcription.

Mechanistically, this is coherent: the VEGF promoter contains G-rich, potentially G-quadruplex-forming SP1-binding elements (GC-boxes). Guanines in such G-rich runs and G-quadruplexes have the lowest ionisation potential in the genome and are the preferred targets of oxidation, so 8-oxo-dG forms there first. 8-oxo-dG distorts base pairing and the major-groove hydrogen-bonding pattern and destabilises the duplex locally, so **SP1 binding is reduced**; loss of SP1 occupancy permits G-quadruplex formation and/or allows the promoter to be engaged by other factors and by the base-excision-repair machinery, and the net output is **increased** *VEGF* transcription.

The important inference is that this is **not simply damage**. Random, deleterious lesions would be expected to impair transcription (by blocking Pol II elongation, or by abolishing activator binding and so reducing output). Instead, the lesion produces a *reproducible, sequence-specific, directional* change in gene expression at a defined promoter — the behaviour of a regulatory signal.

### 3.2 8-oxo-dG as an epigenetic marker

**The result suggests that 8-oxo-dG modifications could function as an epigenetic marker that mediates transcriptional regulation.** The modification satisfies the operational criteria for such a mark:

- it is a **chemical modification of the DNA base that does not change the coding sequence** (it is G, modified, not a substitution);
- it is **written** non-randomly — targeted to specific, low-ionisation-potential G-rich promoter elements (GC-boxes, G-quadruplex-forming tracts), so its distribution is sequence- and structure-directed rather than uniform;
- it is **read** by sequence-specific DNA-binding proteins, whose occupancy it changes (here, loss of SP1 from the G-rich elements of the *VEGF* promoter);
- it is **erased** enzymatically and specifically, by OGG1-initiated base excision repair;
- and it **alters transcriptional output in a defined direction**, reversibly and in response to a physiological signal (the cellular redox state).

### 3.3 8-oxo-dG mediates transcriptional regulation *together with its repair proteins*

Crucially, the regulatory function is not performed by the modified base alone: **8-oxo-dG mediates transcriptional regulation together with its repair proteins.** The lesion's biological output depends on the machinery recruited to it:

- **OGG1 (8-oxoguanine DNA glycosylase 1)** binds 8-oxo-dG and, in this regulatory mode, acts as more than a repair enzyme: OGG1 bound at (or acting on) promoter 8-oxo-dG functions as a transcriptional co-regulator, recruiting and cooperating with transcription factors (NF-κB, SP1, HIF-1α, NRF1, and chromatin-modifying activities) and nucleating the assembly of an active promoter complex.
- **APE1/Ref-1**, the downstream AP endonuclease, is simultaneously a classical **redox co-activator** that reduces and thereby activates transcription factors (AP-1, NF-κB, HIF-1α, p53) and that binds nCaRE elements; its recruitment to the lesion couples repair initiation to transactivation.
- The **incision intermediates themselves are functional**: the abasic (AP) site and the single-strand break generated by OGG1/APE1 relax the duplex, permit **G-quadruplex folding** in the now-unpaired G-rich tract, and provide a platform for the hypoxia/stress-responsive complexes that drive *VEGF* expression. **PARP1**, **FEN1**, **Pol β** and **XRCC1/LIG3** complete the short-patch repair and, in doing so, further remodel the local chromatin and recruit additional regulators.
- **Chromatin relaxation** by this repair-coupled process increases promoter accessibility, so the modification plus its repair proteins effectively acts as a switch that opens a specific promoter.

So the lesion is the *mark*, and the repair proteins are the *effectors/readers*; neither alone explains the observed activation.

### 3.4 Recruitment of repair proteins and active interaction with regulatory elements

Following from this: **the modification can recruit repair proteins to control transcription by actively interacting with other regulatory elements — in particular G-rich elements.** The 8-oxo-dG does not act in isolation at a single base; it operates through, and upon, the surrounding *cis*-regulatory architecture:

- 8-oxo-dG forms preferentially *within* **G-rich elements** (GC-boxes/SP1 sites, G-quadruplex-forming runs, and the potential G-quadruplex sequences that are strikingly over-represented in promoters and in the *VEGF* promoter specifically), so the mark is deposited exactly where regulatory information resides;
- its presence there **reduces the binding of the G-rich-element-specific transcription factor (SP1)**, converting a constitutively SP1-occupied GC-box into a signal-responsive element;
- the lesion then **recruits OGG1/APE1/PARP1 and the BER machinery to that element**, and these proteins interact with the G-quadruplex and with neighbouring enhancer/promoter elements and transcription factors (e.g. HIF-1α at the adjacent hypoxia-response element of *VEGF*, NF-κB, AP-1) to assemble an activating complex;
- the result is an active, cooperative interaction between the modified base, its repair proteins and the surrounding regulatory elements — which is why the effect is a *gain* of transcription rather than a loss.

### 3.5 Reasoning note: the mutagenic consequence of the same lesion

It is important to be explicit about why 8-oxo-dG is normally classified as damage, because this is what makes its regulatory role notable — and because the same chemistry constrains how such a mark can be used. **8-oxo-dG causes a G → T mutation (a G:C → T:A transversion) during DNA replication**: in its *syn* conformation 8-oxo-dG mispairs with adenine in a Hoogsteen-type pair, so a replicative polymerase (particularly Pol β, Pol λ or a translesion polymerase) can insert **dA opposite 8-oxo-dG**; after a further round of replication the original G:C pair has become **T:A**. (The same lesion in the nucleotide pool, 8-oxo-dGTP, is inserted opposite template A, producing A:T → C:G changes, which is why MTH1 sanitisation matters.) This is how the modification alters the **DNA sequence**, and the MUTYH/OGG1 "GO system" exists to suppress it.

This creates the essential tension and the logic of the system: the *same* lesion is simultaneously **pre-mutagenic** (if replicated before repair) and **regulatory** (if read and repaired in a controlled way in a promoter of a non-replicating or transcriptionally engaged region). Its usefulness as a signal therefore depends on efficient, timely OGG1-dependent erasure — and on its being concentrated in promoter G-rich elements rather than in coding sequence.

### 3.6 Wider implication: redox-mediated control of gene expression

Taking the two observations together, the broader implication is a reconceptualisation of oxidative base modification:

- **Oxidative modifications are not merely stochastic damage to be erased; they constitute a mechanism for the control of gene expression.** The cell can use the position of a lesion, the identity of the transcription factor it displaces, and the repair proteins it recruits to turn specific promoters on or off — producing gene-specific, graded and reversible transcriptional responses. In the *VEGF* case this provides a direct route from oxidative/hypoxic stress to upregulation of an angiogenic gene, i.e. a response that is adaptive precisely when ROS are high and tissue oxygenation is poor. The same logic applies to other stress- and hypoxia-responsive genes with G-rich promoters (*SIRT1*, *KRAS*, *MYC*, *NOS2*, *HIF1A* targets), and it explains why promoter G-quadruplex-forming sequences and OGG1-dependent promoter occupancy are so widespread.
- Mechanistically, this is a form of **redox-mediated control**: the cellular redox state (ROS flux versus antioxidant capacity) is transduced into a chemical mark on specific promoter DNA, which is then read by sequence-specific factors and by repair enzymes to set transcriptional output. **8-oxo-dG is therefore an example of redox-mediated control of transcription** — the redox environment writes the signal, G-rich/G-quadruplex sequence context localises it, transcription-factor displacement and repair-protein recruitment read it, and OGG1-initiated BER erases it, closing a reversible regulatory cycle. This places oxidative base modification alongside cytosine methylation and histone modification as a signal-responsive layer of transcriptional regulation, with the distinctive feature that its input is the cell's metabolic/oxidative state.

### Final answer (Part 3)

The VEGF result shows that oxidation of a specific promoter element produces a defined, directional *increase* in transcription by reducing SP1 occupancy of the G-rich element — behaviour characteristic of a signal, not of random damage. It therefore suggests that **8-oxo-dG modifications could function as an epigenetic marker that mediates transcriptional regulation**. More precisely, **8-oxo-dG mediates transcriptional regulation together with its repair proteins (OGG1, APE1/Ref-1, PARP1 and the BER machinery)**, and the **modification recruits these repair proteins to control transcription by actively interacting with other regulatory elements, notably the G-rich elements/G-quadruplexes in which the lesion preferentially forms**. Because the identical lesion also **causes G → T mutations during DNA replication** (via *syn*-8-oxo-dG:dA mispairing), its regulatory use depends on efficient, targeted repair. The wider implication is that oxidative modifications are a *bona fide* mechanism for the **control of gene expression**, and that 8-oxo-dG represents **redox-mediated control** of transcription — the cell's redox state written onto specific promoters and read out as gene-specific, reversible transcriptional change.
