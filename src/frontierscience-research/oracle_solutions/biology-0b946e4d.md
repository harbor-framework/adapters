# Establishing a rapid pathosystem in *Chenopodium pallidicaule*: selection of a model pathogen, virulence screening and identification of the best pathovar

## 1. The core constraint: no genetic tools exist on the host side

*Chenopodium pallidicaule* (kañiwa/cañihua) is a **novel, understudied, halophytic crop**. Practically, this means that on the **plant side** there are:

- **no mutant collections** (no T-DNA/EMS/transposon lines, no TILLING population),
- **no established transformation or regeneration protocol**, no reliable VIGS or transient-expression system,
- **limited or no annotated reference genome**, and no characterised immune-gene repertoire (no catalogue of PRRs, NLRs, or susceptibility genes),
- **no validated immune-response markers** or antibodies,
- no pre-existing germplasm panel phenotyped for disease resistance.

Forward or reverse genetics on the host is therefore not available as the entry point, and will take years to develop.

**The consequence for pathogen choice is decisive: because all of the genetic tractability is missing on the crop side, the model pathogen must compensate for it.** The pathogen must be the genetically tractable partner in the interaction — i.e. it must be **extremely well studied, genetically amenable, and supplied with pre-existing genetic tools and mutant collections** — so that the biology of the interaction can be dissected by manipulating the *pathogen* (deleting, swapping and complementing individual effectors and virulence factors, and using reporter strains) while the host is held as an unmodified wild type. Every host immune process that can be inferred will, at least initially, be inferred from how the plant responds to a defined pathogen genotype. A poorly characterised pathogen would leave both sides of the interaction as black boxes, and the project would stall.

Three further criteria follow from the requirement to do this "as quickly as possible": the pathogen must be **easy and safe to acquire**, **easy and fast to culture and handle**, and must come with **pre-established, reliable infection protocols** that give clear, scorable phenotypes within days rather than weeks.

---

## 2. Choice of model pathogen: *Pseudomonas syringae*

**The most suitable model pathogen is *Pseudomonas syringae*.**

Justification — *P. syringae* satisfies every one of the constraints above:

1. **Broad genetic diversity of pathovars.** *P. syringae* is a species complex comprising **>60 named pathovars distributed across at least 13 phylogroups**, collectively infecting a very wide range of host plants. This diversity is the key practical advantage: rather than gambling on a single strain, one can screen a panel spanning different phylogroups and different effector repertoires, which dramatically raises the probability of finding at least one strain that is virulent on a previously untested host such as *C. pallidicaule*.
2. **Readily available genetic mutants, and ease of creating new ones.** This is the critical point given §1. Large collections of characterised **effector deletion mutants, polymutants (e.g. the DC3000 *ΔCEL*, effector-knockout and the "D28E"-type series), type-III secretion-deficient mutants (*hrcC⁻*, *hrpL⁻*), coronatine/phytotoxin mutants, and complementation and effector-delivery strains** already exist and are freely shared. *P. syringae* is also genetically amenable: it is transformable and conjugatable, has well-established broad-host-range vectors (pBBR1MCS, pDSK519, pME6012), allelic-exchange and marker-exchange protocols, and is readily tagged with GFP/mCherry or *lux* reporters. This allows reverse genetics to be done entirely on the pathogen side.
3. **A wealth of existing knowledge of its virulence strategies and factors.** The type-III secretion system (*hrp/hrc*), >50 characterised type-III effectors and their host targets, coronatine and other phytotoxins (syringomycin, syringopeptin, tabtoxin), the AvrPto/AvrPtoB–kinase, AvrPtoB–BAK1 and HopM1/HopAI1/HopF2 interactions with immune signalling, PAMPs (flg22, csp22) and their cognate PRRs, biofilm and epiphytic fitness determinants — all are described in detail. Any phenotype observed in *C. pallidicaule* can therefore be interpreted against a deep mechanistic framework.
4. **Ease of acquisition.** Strains are easily obtained from **established research groups** that work on *P. syringae*, and from public culture collections — in particular the **National Collection of Plant Pathogenic Bacteria (NCPPB)**, as well as CFBP, ICMP, DSMZ and ATCC. Material transfer is routine, and the strains are not quarantine-restricted in the way many other pathogens are (import/containment permits should still be checked).
5. **Ease of handling and propagation.** It is a fast-growing, aerobic, Gram-negative bacterium that grows overnight at 28 °C on simple media (King's B, LB, NYGA), is easy to store (glycerol stocks, –80 °C), easy to quantify (OD₆₀₀ and dilution plating), and requires only standard BSL-1/plant-pathogen containment. No obligate biotrophy, no spore production, no specialist growth facilities.
6. **Reliability of pre-established infection protocols.** The standard inoculation methods (syringe/apoplast infiltration, dip and spray inoculation) and the standard quantitative read-out (in planta CFU per unit leaf area over time) are highly reproducible, well documented across many hosts, and produce **clear, scorable phenotypes within ~3 days**, which is exactly what "as quickly as possible" requires.
7. **Model-system compatibility.** The *Arabidopsis*–*P. syringae* and tomato–*P. syringae* interactions are the best-characterised plant–bacterium pathosystems in existence, so results in *C. pallidicaule* can be benchmarked directly against a reference host.

(Briefly, why alternatives are weaker for this specific purpose: *Agrobacterium* is not a suitable disease model; oomycetes such as *Peronospora*/*Phytophthora* and biotrophic fungi are slower, often obligate, and far less genetically tractable; *Xanthomonas* and *Pectobacterium* are reasonable second choices but offer fewer pathovars/effector mutants and, for *Pectobacterium*, a largely non-effector, macerating lifestyle that reveals little about immune recognition; viral systems require host transformation or infectious clones adapted to the species.)

---

## 3. Choosing the candidate pathovars

### 3.1 Acquire several pathovars from closely related plant species

**Several (two or more) *P. syringae* pathovars should be acquired from host plant species closely related to *C. pallidicaule*.** The rationale is host-range phylogeny: *P. syringae* pathovars are, to a first approximation, host-adapted, and effector repertoires are tuned to the immune systems of their host lineage. Strains isolated from relatives of the target crop therefore have the highest prior probability of being virulent on it, because the host immune repertoire they have evolved to subvert is the most similar.

*C. pallidicaule* belongs to the **Amaranthaceae (Chenopodiaceae, Chenopodioideae)**, so the relevant close relatives are **quinoa (*Chenopodium quinoa*), *Chenopodium album*, spinach (*Spinacia oleracea*), beet/sugar beet (*Beta vulgaris*)** and the amaranths. Accordingly, pathovars isolated from these hosts should be obtained (from the NCPPB or from groups working on them):

- ***Pseudomonas syringae* pv. spinaciae** — isolated from **spinach** (*Spinacia oleracea*), a close Amaranthaceae relative;
- ***Pseudomonas syringae* pv. aptata** — isolated from **sugar beet** (*Beta vulgaris*), also Amaranthaceae, and notable for a relatively broad host range;
- (where available) ***P. syringae* isolates from *Chenopodium quinoa* or *C. album***, and ***P. syringae* pv. *beticola***.

### 3.2 Ensure genetic diversity of effectors — sample across phylogroups — and include a broad-range pathovar

Restricting the panel to close-relative isolates alone would be a mistake, for two reasons: such isolates may not exist or may be poorly characterised, and host-adapted strains may be *too* specialised (recognised and resisted, or simply unable to colonise a new host). The panel must therefore be designed so that the candidate strains **differ substantially in their effector/virulence-protein repertoires**, which in *P. syringae* is achieved most reliably by **choosing strains from different phylogroups** (phylogroup membership correlates strongly with core-genome divergence, type-III effector content, phytotoxin production and host range). Sampling diverse effector repertoires maximises the chance that at least one strain deploys a combination of effectors able to suppress *C. pallidicaule* immunity, and — just as usefully — differential outcomes across the panel immediately generate hypotheses about which effector families matter in this host.

The panel should also **include a "broad-range" pathovar — i.e. a strain known to be able to infect diverse/multiple plant hosts** — because broad-host-range strains carry effector repertoires that are effective against many different immune systems and are therefore the most likely to succeed on a host never previously tested. Good choices:

| Strain | Phylogroup | Source host | Role in the panel |
|---|---|---|---|
| ***P. syringae* pv. tomato DC3000** | PG1 | tomato / *Arabidopsis* | the reference **broad-range** model strain; infects multiple hosts; the richest available mutant toolkit |
| ***P. syringae* pv. syringae B728a** | PG2 | bean | **very broad host range**, strong epiphytic fitness, phytotoxin producer; fully sequenced with genetic tools |
| ***P. syringae* pv. aptata** (e.g. DSM 50252 / NCPPB isolates) | PG2 | **sugar beet (*Beta vulgaris*)** — close relative | close-relative isolate, also relatively broad range |
| ***P. syringae* pv. spinaciae** | PG2/other | **spinach (*Spinacia oleracea*)** — close relative | closest host-adapted candidate |
| ***P. syringae* pv. maculicola* ES4326** (= *P. cannabina* pv. *alisalensis*) | PG5 | brassicas / broad | effector-divergent, broad-range comparator |

This gives a panel of ~5 strains that (i) includes **at least two pathovars from closely related host species**, (ii) spans **at least three phylogroups** and therefore substantially different effector/virulence-protein complements, (iii) includes **broad-range pathovars able to infect diverse hosts**, and (iv) includes at least one strain (DC3000) for which the deepest mutant resources exist.

All strains should be received as authenticated cultures, re-streaked for single colonies, identity-confirmed (16S/*rpoD*/MLST or whole-genome sequencing, plus *hrpL*/effector PCR), stored as glycerol stocks, and — where needed — marked with an appropriate antibiotic resistance (most *P. syringae* model strains are rifampicin-resistant) to allow clean selective recovery from plant tissue.

---

## 4. Inoculation method: apoplast (syringe) infiltration

**The inoculation method should be the apoplast infiltration method** — pressure infiltration of a defined bacterial suspension into the leaf apoplast using a **needleless syringe** pressed against the abaxial leaf surface (or, for small or difficult leaves, vacuum infiltration of whole leaves/plantlets).

Justification:

- It is the **best-established and most reliable *P. syringae* inoculation method**, used across hundreds of host–strain combinations, and it is the method for which comparative data and protocols already exist.
- It **delivers a precisely known inoculum dose directly to the apoplast**, which is where *P. syringae* multiplies and where the type-III secretion system engages host cells. It therefore bypasses the highly variable, environment-dependent steps of epiphytic survival and stomatal/wound entry, which would otherwise dominate the result and confound comparison between strains.
- It gives **quick and clear diseased phenotypes** — water-soaking within hours and visible chlorosis/necrosis within 1–3 days — and produces **uniform, reproducible lesions in a defined infiltrated area**, which is essential for both symptom scoring and quantitative CFU determination per unit leaf area.
- It therefore **maximises the sensitivity of the screen**: if a strain cannot grow and cause symptoms when placed directly into the apoplast at high dose, it is very unlikely to be a useful model pathogen on this host by any route.
- Practically: suspend bacteria from an overnight King's B plate in **10 mM MgCl₂** (no surfactant needed), adjust by OD₆₀₀ to the required concentration, infiltrate fully expanded leaves of plants at a defined, consistent developmental stage grown under controlled conditions (e.g. 22–24 °C, 60–70% RH, 10–12 h photoperiod), mark the infiltrated zone, include **10 mM MgCl₂ mock infiltration** on comparable leaves of every plant as the negative control, and keep humidity high immediately after inoculation.

---

## 5. Experiment 1 — Rapid preliminary virulence screen (symptoms only, inoculum titration)

The aim is to find out, in the shortest possible time, **whether any of the candidate strains is virulent at all** on *C. pallidicaule*, and at what dose. Speed is prioritised over mechanism at this stage.

**Design:**

- **Read-out: visual symptom development alone.** No bacterial quantification is performed in this first screen — scoring symptoms by eye is immediate, requires no processing, and is sufficient to triage the panel.
- **Vary the starting inoculum concentration.** **Begin with a low starting inoculum for all strains — e.g. $10^5$ CFU/ml** — and, where no symptoms develop, **increase the starting concentration incrementally (e.g. $10^5 \rightarrow 10^6 \rightarrow 10^7 \rightarrow 10^8$ CFU/ml) up to the maximum of $10^8$ CFU/ml, until virulence symptoms are shown.** Starting low is important for two reasons: a low dose reveals genuine, growth-dependent virulence (a strain that causes disease from $10^5$ CFU/ml is truly aggressive), whereas a high dose can produce dose-dependent, non-specific tissue collapse or an HR-like response that is easily mistaken for disease. Escalating only as needed also keeps the experiment small.
- **Timeframe: 3 days or less.** Infiltrate at day 0 and score symptoms at **24, 48 and 72 h post-inoculation (hpi)**, i.e. the whole preliminary screen is complete within **3 days**. This is both biologically appropriate (*P. syringae* disease symptoms on a susceptible host appear within 1–3 days of apoplast infiltration) and the fastest route to a decision.
- **Scoring:** record the presence, timing and extent of water-soaking, chlorosis, necrosis, lesion spreading beyond the infiltrated zone and tissue collapse, using a defined ordinal scale (e.g. 0 = no symptoms, 1 = faint chlorosis, 2 = clear chlorosis, 3 = localised necrosis, 4 = spreading necrosis/collapse) plus photographs at each time point; distinguish, as far as possible, spreading chlorosis/necrosis (disease-like) from rapid, confined dry necrosis within 12–24 h (HR-like).
- **Controls:** mock (10 mM MgCl₂) infiltration on every plant; where possible a known susceptible reference host (e.g. *Arabidopsis* for DC3000, bean for B728a) infiltrated in parallel to confirm that the inoculum was viable and virulent.

**Decision rule:** **if no virulence symptoms are induced by any strain across the whole $10^5$–$10^8$ CFU/ml range, then new pathovars will need to be obtained and tested** — a further round of strain acquisition (additional phylogroups, additional close-relative hosts, additional broad-range strains, or strains from halophytic/related wild *Chenopodium* species), rather than continuing with an unproductive panel. Only strains that produce symptoms somewhere in this range are carried forward.

**Reliability.** No conclusion is drawn from a single run: the experiment must be **repeated (at least two to three independent biological experiments on separate batches of plants) and must use a minimum of n = 6 biological replicates (six independent plants, each with independently infiltrated leaves) per strain × dose × time point** before any conclusion is drawn. Plants should be randomised in the growth chamber, leaf position and age standardised, and scoring blinded to treatment where feasible.

---

## 6. Experiment 2 — Quantitative infection assay: symptoms *plus* bacterial growth over time

The preliminary screen cannot distinguish a strain that multiplies in the apoplast (true virulence) from one that merely causes a dose-dependent reaction. **In a second, subsequent experiment, score both symptom development *and* a quantitative analysis — colony counts — to evaluate bacterial growth in planta over time.**

**Design:**

- Carry forward the strains that produced symptoms, at the lowest inoculum concentration at which they did so. For quantitative growth assays a **lower inoculum is preferable** (e.g. $10^4$–$10^5$ CFU/ml) because it allows several logs of growth to be resolved before saturation.
- **Sample at a minimum of two time points — day 0 (≈1–2 h post-infiltration, to verify that all strains were delivered at the same starting titre) and day 3 (72 hpi)** — with intermediate sampling at **day 1 and day 2** to describe the growth curve. The whole assay again runs within **3 days**.
- **Colony counting procedure:** at each time point, excise defined leaf discs (e.g. 2 × 0.5 cm² cork borer) from the infiltrated zone, surface-sterilise briefly (e.g. 15 s in 70% ethanol, then rinse in sterile water) to remove epiphytic bacteria, homogenise in 10 mM MgCl₂ with a bead mill or micro-pestle, prepare **10-fold serial dilutions**, plate on **King's B agar with the appropriate selection (e.g. rifampicin 50 µg/ml ± cycloheximide)**, incubate at 28 °C for 2 days, count colonies, and express the result as **log₁₀ CFU per cm² of leaf tissue** (or per mg fresh weight).
- **Symptom scoring on the same plants/leaves** at each time point, using the same ordinal scale and photography as in Experiment 1, so that symptom and growth data are paired.
- **Replication and statistics:** again **a minimum of n = 6 biological replicates per strain per time point, and the entire experiment repeated independently at least twice to three times.** Analyse log₁₀-transformed CFU data by two-way ANOVA (strain × time) with post-hoc multiple-comparison correction, or by mixed-effects modelling with experiment as a random factor; report effect sizes and confidence intervals, and test explicitly for a **significant change in bacterial titre between day 0 and day 3** for each strain. Pre-specify the significance threshold.
- Mock controls and, ideally, a non-pathogenic/T3SS-deficient control (*hrcC⁻*) are included to define the "no growth" baseline.

---

## 7. Expected outcomes and how to score and interpret them

Pairing the quantitative growth data (change in CFU/cm² between day 0 and day 3) with the visual symptom data gives five interpretable scenarios:

1. **Bacterial growth shows a significant *reduction* over time → the pathovar is *not virulent* on this host.** The bacterium cannot establish or multiply in the *C. pallidicaule* apoplast; its titre declines from the inoculum level. This strain is not a candidate model pathogen (it may be being actively restricted by basal/non-host resistance).
2. **Bacterial growth shows a significant *increase* over time → the pathovar *is virulent* on this host.** The strain multiplies in the apoplast, i.e. it successfully colonises the host and (at least partly) suppresses or evades its immunity. Typically a susceptible interaction gives ~2–4 log₁₀ growth over 3 days.
3. **Visual symptoms *together with* significant bacterial growth → the symptoms are most likely genuine disease symptoms of that pathovar.** Growth and symptom development are causally linked; this is the classic compatible (susceptible) interaction and the ideal basis for a pathosystem.
4. **No visual symptoms but significant bacterial growth → these strains may not be pathogenic** (they may be growing as endophytes/commensals, or be only weakly virulent on this host) **and will require further investigation, in particular by extending the duration of the experiment** — symptoms may simply appear later than 3 days in this host, so the assay should be extended (e.g. to 5–7 dpi), and additional sensitive read-outs added (ion leakage/electrolyte conductivity, trypan blue staining, chlorophyll fluorescence/photosynthetic efficiency imaging, dry weight) to detect sub-visible damage.
5. **Visual symptoms but a significant *reduction* of bacterial growth over time → the symptoms are most likely immune responses of the host rather than disease, i.e. signs of host resistance.** This is the signature of an incompatible interaction, typically effector-triggered immunity with a hypersensitive response: rapid, confined necrosis coincident with restriction of bacterial multiplication. Such strains are not useful as the primary virulent model pathogen, but they are extremely valuable as **avirulent/resistance-eliciting reference strains** for studying *C. pallidicaule* immune recognition, and the responsible recognised effector can later be identified by effector-swap experiments.

(A sixth, trivial outcome — no symptoms and no significant growth — indicates a wholly non-host/incompatible interaction with no useful phenotype, and the strain is discarded.)

---

## 8. Choosing the best "model pathovar(s)"

On completion of the infection assays, the pathovars are ranked using the paired growth/symptom data, and the rationale for the choice is:

- **A pathovar that showed fast and significant growth in planta** — the greatest increase in CFU/cm² over the 3-day window, and ideally from the lowest starting inoculum. Rapid, robust multiplication means the strain genuinely colonises *C. pallidicaule* and that assays will give large, statistically clean effect sizes in a short experiment, which is exactly what is needed for a workable, high-throughput pathosystem.
- **A pathovar that showed significant growth *and also* produced clear visual disease symptoms** — i.e. scenario 3 above. Visible, reproducible, quantifiable disease symptoms provide a fast, cheap, non-destructive phenotype that can be scored at scale (for germplasm screens, mutant screens, time courses and dose–response work) and that can be cross-validated against the CFU data. A strain that grows but causes nothing visible (scenario 4) is far less practical, and a strain that causes symptoms without growing (scenario 5) is measuring resistance, not disease.

The preferred outcome is therefore to take forward **one or two pathovars that combine fast, significant in planta growth with clear disease symptom development**, giving the project both a quantitative (CFU) and a visual (symptom) read-out. Where two such strains exist and belong to **different phylogroups** with divergent effector repertoires, both should be retained — this provides an internal comparison of host responses to different virulence strategies, and insurance against strain-specific idiosyncrasies. A strain that elicits a clear resistance response (scenario 5) should be retained alongside them as the avirulent counterpart. Preference should also be given, among otherwise equivalent candidates, to the strain with the **richest existing mutant toolkit** (e.g. DC3000), since that is what makes the pathogen-side genetics in §1 possible.

---

## 9. Appropriate follow-up experiments

Once the model pathovar(s) are chosen, the pathosystem is extended — these are the experiments that begin to decipher the *C. pallidicaule* immune system:

- **Use genetically modified strains — effector deletion mutants.** Infect with **type-III-secretion-deficient mutants (*hrcC⁻*, *hrpL⁻*)** to confirm that virulence is T3SS-dependent and to establish the PAMP-triggered-immunity baseline, and then with **individual and polygenic effector deletion mutants** (and effector-complementation/effector-delivery strains) to identify which effectors are required for virulence on *C. pallidicaule* and which are recognised by it. Because the host has no genetic tools, this pathogen-side reverse genetics is the primary route to identifying host immune pathways and candidate recognition events.
- **Use fluorescence- or luminescence-tagged bacterial strains** (GFP/mCherry-expressing or *luxCDABE*-tagged derivatives) to track colonisation non-destructively in space and time — tissue tropism, apoplastic distribution, epiphytic versus endophytic populations, and spread beyond the infiltration site — with confocal microscopy or whole-plant luminescence imaging. These also provide a faster, non-destructive quantitative proxy for bacterial load than dilution plating.
- **Use a different, more natural mode of inoculation — spray inoculation** (with a surfactant such as 0.02–0.04% Silwet L-77), and/or **dip inoculation** — to evaluate infection by a route that includes the natural, epiphytic and stomatal-entry steps that syringe infiltration bypasses. This tests whether the strain is a realistic pathogen of the crop under field-relevant conditions, allows stomatal immunity and surface colonisation to be studied, and is the appropriate assay for later screening of resistance in germplasm under more natural inoculum pressure.

Further useful extensions: dose–response and growth-curve refinement across a wider time course; testing under the **saline conditions** relevant to this halophytic crop, to examine the interaction between abiotic stress signalling and immunity; development of host response markers (RNA-seq of infected tissue to define the transcriptional immune response and to build marker-gene assays de novo, since none exist); ROS burst, callose deposition and MAPK activation assays following treatment with purified PAMPs (flg22, csp22) to establish which PRR-mediated responses are functional; screening a *C. pallidicaule* germplasm panel with the chosen pathovar to find natural resistance variation; and, in parallel, building host-side tools (reference genome assembly/annotation, transformation and transient-expression protocols) so that the host eventually becomes tractable too.

---

## 10. Summary of the proposed workflow

1. **Recognise the constraint:** *C. pallidicaule* has no genetic tools, so the model pathogen must supply the genetic tractability — it must be well studied, genetically amenable, and come with existing mutants.
2. **Choose *Pseudomonas syringae*,** justified by its broad diversity of pathovars, ease of acquisition (NCPPB and research groups), ease of handling and propagation, reliable pre-established infection protocols, deep knowledge of its virulence factors, and readily available (or easily made) genetic mutants.
3. **Assemble a candidate panel** of ≥5 strains: **two or more pathovars from closely related host species** (*P. syringae* pv. *spinaciae* from spinach, *P. syringae* pv. *aptata* from sugar beet), spanning **different phylogroups** to ensure diversity of effector/virulence-protein repertoires, and including **broad-range pathovars able to infect diverse hosts** (*P. syringae* pv. *tomato* DC3000, PG1; *P. syringae* pv. *syringae* B728a, PG2; *P. syringae* pv. *maculicola* ES4326, PG5).
4. **Inoculate by apoplast (syringe) infiltration** — the well-established, reliable method that gives quick, clear disease phenotypes.
5. **Experiment 1 (≤3 days):** preliminary screen on **visual symptoms alone**, titrating the starting inoculum from **$10^5$ up to $10^8$ CFU/ml** until symptoms appear; **if no strain causes symptoms across that range, acquire and test new pathovars.** Use **≥6 biological replicates** and repeat the experiment.
6. **Experiment 2 (≤3 days):** score **symptoms together with quantitative colony counts** (log₁₀ CFU/cm², day 0 vs days 1–3) to measure bacterial growth over time; again **≥6 biological replicates**, independently repeated, with ANOVA-based statistics.
7. **Interpret using the five scenarios:** significant decline = not virulent; significant increase = virulent; symptoms + growth = genuine disease; growth without symptoms = possibly non-pathogenic, extend the experiment duration; symptoms without growth = host immune response/resistance.
8. **Select the model pathovar(s):** the one(s) showing **fast and significant in planta growth**, and **significant growth accompanied by clear visual disease symptoms**.
9. **Follow up** with **effector deletion and T3SS mutants, fluorescently/luminescently tagged strains, and spray (natural-route) inoculation**, then build host-side resources and immune-response assays.
