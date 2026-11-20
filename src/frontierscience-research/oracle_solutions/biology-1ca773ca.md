# A 29-colour spectral flow cytometry panel (Cytek Aurora, 5L) for human NK/ILC developmental subsets and lineage-specifying transcription factors in peripheral blood and tonsil

## 1. Design objective and the logic that fixes the marker list

The panel must do four things simultaneously on **cryopreserved** human PBMC and tonsil mononuclear cells:

1. **Exclude everything that is not an ILC/NK cell** (T, B, myeloid, stromal) in a single "dump" detector, because ILCs are defined negatively as Lin⁻ lymphocytes and are extremely rare (0.01–0.5% of PBMC lymphocytes).
2. **Resolve the full developmental trajectory**: CD34⁺ progenitor → common lymphoid progenitor (CLP) → common innate lymphoid progenitor (CILP/EILP) → the three precursors (NKP, CHILP, and the PLZF⁺ ILCP) → mature effectors.
3. **Resolve all mature subsets**: CD56^bright, CD56^dim and CD57⁺CD56^dim NK cells; ILC1 and intraepithelial ILC1 (ieILC1); ILC2; and group 3 ILCs (NCR⁻ ILC3, NCR⁺ ILC3, LTi).
4. **Measure the lineage-specifying transcription factors through differentiation**: the earliest ILC/NK specification factors **NFIL3 (E4BP4)** and **ID2**, the precursor-stage factor **PLZF (ZBTB16)**, and the effector factors **T-BET, EOMES, GATA3, RORγt**.

Because transcription factors are intracellular, low-abundance and require fixation/permeabilisation, and because surface receptors on these populations span four logs of expression, the full-spectrum Aurora is essential: 64 detectors across 5 lasers (UV 1–16, V 1–16, B 1–14, YG 1–10, R 1–8) allow 29 parameters with unmixing based on each dye's full emission signature, plus **autofluorescence extraction as an additional "parameter"** — critical for tonsil, which is far more autofluorescent than PBMC.

---

## 2. The panel: markers, fluorochromes, **Cytek Aurora peak channels**, clones and commercial sources

Every reagent below is a catalogued conjugate from BioLegend (BL), BD Biosciences (BD), Miltenyi Biotec (MB) or Thermo Fisher/Invitrogen (TF) except NFIL3, for which the purified antibody is commercially available and is conjugated in-house (see note). **Each marker is assigned a single, distinct Cytek Aurora peak channel.**

### 2.1 Viability and lineage exclusion

| # | Parameter | Fluorochrome | **Peak channel** | Clone / source |
|---|---|---|---|---|
| 1 | **Viability dye** | **Zombie NIR** (amine-reactive, **fixable** — survives fix/perm) | **R7** | BL 423105 |
| 2 | **Lineage "dump": CD3 + CD19 + CD14 + CD31** (all four on the same fluorochrome, read in one detector) | BV510 | **V5** | CD3 UCHT1 (BL/BD), CD19 HIB19 (BL), CD14 M5E2 (BL/BD), CD31 WM59 (BD) |

Alternative viability dyes if R7 is needed: LIVE/DEAD Fixable Blue (UV2) or Zombie UV (UV3). A fixable dye is mandatory because the transcription-factor stain requires fixation after the surface stain.

### 2.2 Progenitor and precursor surface markers

| # | Marker | Fluorochrome | **Peak channel** | Clone / source | Purpose |
|---|---|---|---|---|---|
| 3 | **CD45** | BUV805 | **UV16** | HI30 (BD) | Leukocyte gate; haematopoietic vs stromal |
| 4 | **CD34** | BUV395 | **UV3** | 581 (BD) | Earliest haematopoietic progenitors (CLP, CILP, NKP) |
| 5 | **CD45RA** | BUV496 | **UV7** | HI100 (BD) | Lymphoid priming of CD34⁺ cells |
| 6 | **CD10** | BV650 | **V10** | HI10a (BD) / SN5c (TF) | Common lymphoid progenitor |
| 7 | **Integrin β7 (ITGB7, α4β7)** | PE-Cy5 | **YG5** | FIB504 (BL/BD) | α4β7⁺ ILC-committed progenitor (CILP/EILP) |
| 8 | **CD7** | BUV563 | **UV9** | M-T701 (BD) | Early lymphoid/ILC commitment |
| 9 | **CD117 (c-Kit)** | BV750 | **V13** | 104D2 (BD/BL) | CILP, NKP, CHILP/ILCP, ILC2, ILC3 |
| 10 | **CD127 (IL-7Rα)** | BV711 | **V11** | A019D5 (BL) / HIL-7R-M21 (BD) | Helper-ILC lineage (CHILP, ILC1/2/3, LTi) |
| 11 | **CD122 (IL-2Rβ)** | BUV737 | **UV14** | Mik-β3 (BD) | Discriminates NKP (CD122⁺) from CHILP (CD122⁻) |
| 12 | **CD161 (KLRB1)** | BV421 | **V1** | HP-3G10 (BL) | Pan-ILC/NK marker |

### 2.3 NK-maturation surface markers

| # | Marker | Fluorochrome | **Peak channel** | Clone / source | Purpose |
|---|---|---|---|---|---|
| 13 | **CD56 (NCAM)** | BV605 | **V9** | 5.1H11 (BL) / NCAM16.2 (BD) | CD56^bright vs CD56^dim |
| 14 | **CD16 (FcγRIII)** | BV480 | **V3** | 3G8 (BD/BL) | CD56^dim maturation |
| 15 | **CD57** | BV570 | **V7** | HCD57/HNK-1 (BL) | Terminally differentiated/adaptive CD56^dim |
| 16 | **CD94 (KLRD1)** | APC-Fire 750 | **R6** | DX22 (BL) / HP-3D9 (TF) | Stage 3→4 transition of NK development; CD94 acquisition marks the CD56^bright stage and is lost on CD57⁺ cells |
| 17 | **NKp46 (CD335)** | APC-R700 | **R3** | 9E2/B159 (BD) | NK and NCR⁺ ILC |
| 18 | **NKp44 (CD336)** | PerCP-eFluor 710 | **B9** | 44.189 (TF) / P44-8 (BL) | **NCR⁺ vs NCR⁻ ILC3** |

### 2.4 Helper-ILC surface markers

| # | Marker | Fluorochrome | **Peak channel** | Clone / source | Purpose |
|---|---|---|---|---|---|
| 19 | **CD294 (CRTH2/PTGDR2)** | PerCP-Cy5.5 | **B8** | BM16 (BL/BD) | **ILC2 definition** |
| 20 | **CCR6 (CD196)** | BUV661 | **UV11** | 11A9 (BD) / G034E3 (BL) | **LTi / ILC3 subsetting** |
| 21 | **CD103 (ITGAE)** | BB700 | **B6** | Ber-ACT8 (BD) | **ieILC1 (intraepithelial ILC1)** in tonsil |
| 22 | **CD25 (IL-2Rα)** | APC-Fire 810 | **R8** | BC96 (BL) | ILC2 and LTi activation state |

### 2.5 Transcription factors (intracellular, after fix/perm)

| # | Marker | Fluorochrome | **Peak channel** | Clone / source | Purpose |
|---|---|---|---|---|---|
| 23 | **NFIL3 (E4BP4)** | Alexa Fluor 532 (in-house conjugate) | **B3** | purified anti-NFIL3 (TF/Novus), conjugated with Lightning-Link / Zenon, or biotin-anti-NFIL3 + streptavidin-AF532 | **Earliest NK/ILC specification factor**: required for progenitor → precursor transition |
| 24 | **ID2** | PE | **YG1** | ILCID2 (TF; PE and eFluor 660 conjugates catalogued) | **Earliest NK/ILC specification factor**; PE chosen because ID2 is dim and PE is the brightest available dye |
| 25 | **PLZF (ZBTB16)** | Alexa Fluor 488 | **B2** | R17-809 (BD) / Mags.21F7 (BL) | **Intermediate precursor identity (ILCP/CHILP)** |
| 26 | **T-BET (TBX21)** | PE-Cy7 | **YG10** | 4B10 (BL) / O4-46 (BD) | ILC1, ieILC1, CD56^dim/CD57⁺ NK |
| 27 | **EOMES** | APC | **R1** | WD1928 (TF) / X4-83 (BD) | NK lineage (and ieILC1); EOMES⁺ vs EOMES⁻ separates NK from ILC1 |
| 28 | **GATA3** | PE-CF594 (PE-Dazzle 594) | **YG3** | L50-823 (BD) / TWAJ (TF) | **ILC2 (high) and ILC1 (low)**; helper-ILC programme |
| 29 | **RORγt (RORC)** | BV786 | **V14** | Q21-559 (BD) / AFKJS-9 (TF) | **Group 3 ILC (ILC3, LTi)** |

**Free detectors remaining** (UV1–2, UV4–6, UV8, UV10, UV12–13, UV15, V2, V4, V6, V8, V12, V15–16, B1, B4–5, B7, B10–14, YG2, YG4, YG6–9, R2, R4–5) leave ample room for expansion markers such as CD49a, CD62L, AHR, TCF-1, Ki-67, CD200R1, c-Myc or IFN-γ/IL-13/IL-22 for a stimulation arm.

**Fluorochrome–antigen pairing rules applied:** the brightest dyes (PE, PE-Cy7, APC, BV421, BUV395) were given to the dimmest/lowest-density targets (the transcription factors ID2, T-BET, EOMES; CD34); the brightest antigens (CD45, CD56, CD16, CD3-dump) were given dimmer dyes (BUV805, BV605, BV480, BV510); markers that must be resolved from one another (CD56/CD16/CD57; CD127/CD117; CD294/NKp44; T-BET/EOMES) were placed on different lasers to minimise spillover spreading; and dye pairs with high similarity indices were avoided (BUV395/BV421, BB700/PerCP, APC/AF647, PE/PE-CF594 were never co-used on competing markers). Each candidate design was checked in the Cytek Full Spectrum Viewer so that all similarity indices are below ~0.98 and the spillover-spreading matrix is acceptable for the dim transcription-factor channels.

---

## 3. Staining protocol for cryopreserved samples

1. **Thaw** PBMC and tonsil mononuclear cells rapidly at 37 °C into warm RPMI + 10% FBS containing **DNase I/benzonase (25 U/mL)** to prevent clumping; rest 1–2 h at 37 °C to restore surface epitopes (notably CD62L, CD16 and chemokine receptors such as CCR6, which are cryo-sensitive); count and assess viability (require >70%).
2. **Input numbers:** ≥10 × 10⁶ live cells per PBMC sample and ≥5–10 × 10⁶ per tonsil sample, because CD34⁺ CILP/NKP/CHILP are ~10⁻⁴–10⁻⁵ of mononuclear cells; to reach ≥100 events in the rarest gate, ≥5 × 10⁶ cells must be acquired. Optional pre-enrichment: Miltenyi CD3/CD19/CD14 depletion or CD117/CD127 positive selection on a parallel aliquot (never on the aliquot used for frequency calculations).
3. **Block** with Human TruStain FcX and True-Stain Monocyte Blocker (polymer-dye non-specific binding), 10 min, 4 °C.
4. **Viability dye** (Zombie NIR) in PBS, 15 min, room temperature, protein-free.
5. **Surface stain** 30 min at 4 °C in **BD Brilliant Stain Buffer Plus** (mandatory with multiple BUV/BV polymer dyes) + 2 mM EDTA; include the dump cocktail. Use titrated, lot-matched antibodies.
6. **Fix/permeabilise** for transcription factors with the **BioLegend True-Nuclear Transcription Factor Buffer Set** (or eBioscience Foxp3/Transcription Factor Staining Buffer Set), then stain NFIL3, ID2, PLZF, T-BET, EOMES, GATA3, RORγt together for 45–60 min at room temperature in perm buffer.
7. **Acquire** on the 5L Aurora at ≤10,000 events/s with a wide acquisition gate (do not gate during acquisition); record ≥5 × 10⁶ events per sample.

---

## 4. Unmixing and controls (essential for a panel of this size)

* **Single-stained reference controls for every one of the 29 parameters**, prepared under exactly the fluorochrome-matched conditions used for the sample: **cells** (not beads) for all intracellular transcription factors and for markers whose dye behaves differently on cells; beads (UltraComp eBeads) only where expression is too low for a cell control. Reference controls for intracellular markers must be taken through the same fix/perm.
* **Autofluorescence (AF) controls, run separately for each tissue.** An unstained PBMC control and an unstained tonsil control are acquired and used for **AF extraction**, because tonsil mononuclear cells (and any contaminating epithelium/macrophages) have a distinct, much brighter AF signature; unmixing each tissue with its own AF signature prevents false-positive dim transcription-factor signals. Where AF is heterogeneous within tonsil, extract multiple AF signatures.
* **FMO controls** for the dim/continuous markers — all seven transcription factors, CD94, CD103, CCR6, NKp44, CD122 — to set positivity thresholds, and **internal biological controls** on every sample: CD3⁺ T cells (T-BET⁺, GATA3^lo, PLZF⁻), Th2 cells (GATA3^hi), MAIT/Vδ2 cells (PLZF^hi), CD8 effector memory (EOMES⁺, T-BET⁺, CD57⁺), and tonsil B cells (all TF-negative).
* **Titration** of each antibody on the relevant tissue (8-point, staining index maximisation), **drop-one controls** for the critical resolution pairs, and a **spillover spreading matrix** review focused on the channels carrying ID2 (YG1), NFIL3 (B3) and PLZF (B2).
* Daily QC beads, a longitudinal reference sample (one cryovial of the same tonsil/PBMC donor in every run) and CD45-barcoding of samples that will be pooled.

---

## 5. Gating strategy

### 5.0 Common pre-gates
Time stability → FSC-A/FSC-H singlets → FSC-A/SSC-A mononuclear cells → **Zombie NIR⁻ (live)** → **CD45⁺** → **lineage dump-negative (BV510⁻: CD3⁻ CD19⁻ CD14⁻ CD31⁻)** = **Lin⁻**. The combined dump removes **T cells (CD3), B cells (CD19), myeloid cells (CD14) and stromal/endothelial cells (CD31)** in one detector, which is what makes a true ILC gate possible in tonsil.

### 5.1 Earliest progenitors (≥2 dedicated surface markers: CD34, integrin β7, CD10)
* **CD34⁺ progenitors:** Lin⁻ **CD34⁺**
* **CLP (common lymphoid progenitor):** Lin⁻ CD34⁺ **CD45RA⁺ CD10⁺** CD117^lo CD127⁺ CD7^lo, **ID2^lo/⁻ NFIL3^lo PLZF⁻**
* **CILP / early innate lymphoid progenitor (EILP):** Lin⁻ CD34⁺ **CD45RA⁺ integrin β7 (α4β7)⁺ CD10⁻** CD117⁺ CD7⁺ CD127^lo/⁻, and — the defining molecular feature — **NFIL3⁺ ID2⁺** with **PLZF⁻**. NFIL3 and ID2 are precisely the factors that are **essential for the early NK/ILC progenitor → precursor transition**: NFIL3 acts upstream and induces ID2 (and TOX/TCF-1), and ID2 sequesters E-proteins (E2A/HEB) to extinguish the B/T option and lock in the innate lymphoid fate. Plotting NFIL3 against ID2 within CD34⁺ α4β7⁺ cells therefore shows the acquisition of ILC potential, and the NFIL3⁺ID2⁺ gate is carried forward through every downstream precursor.

### 5.2 Precursor populations
* **NKP (natural killer precursor):** Lin⁻ CD34^+/lo CD45RA⁺ **CD117⁺ CD122⁺ CD127⁻ CD94⁻ CD56⁻ CD16⁻**, **NFIL3⁺ ID2⁺ EOMES^lo T-BET^lo PLZF⁻**. CD122 (IL-2Rβ) acquisition with CD127 loss is the cardinal NK-committed signature, and CD94 negativity places it before the CD94⁺ stage.
* **CHILP (common helper innate lymphoid precursor):** Lin⁻ CD34^lo/⁻ **CD127⁺ CD117⁺ CD122⁻**, **ID2⁺ NFIL3⁺**, CD161⁺; by definition it retains ILC1/ILC2/ILC3/LTi potential but has lost conventional NK potential (hence CD122⁻, EOMES⁻).
* **ILCP (PLZF⁺ innate lymphoid cell precursor, the intermediate precursor inside the CHILP compartment):** CHILP gate **PLZF⁺** (CD117⁺ CD127⁺ CD294⁻ NKp44⁻ RORγt^lo/⁻). **PLZF is the transcription factor that identifies this intermediate precursor stage**: PLZF⁺ ILCPs give rise to ILC1/ILC2/ILC3 but not to LTi cells or cNK, so PLZF⁺ versus PLZF⁻ within CD127⁺CD117⁺ cells is the single most informative split in the precursor compartment. In tonsil this PLZF⁺CD117⁺CD127⁺ "ILC precursor" pool is abundant and is the main site of ILC differentiation.
* **Developmental staging of NK cells (Freud/Caligiuri stages), read out with CD34, CD117, CD94, CD56, CD16:** Stage 1 CD34⁺CD117⁻CD94⁻ → Stage 2 CD34⁺CD117⁺CD94⁻ → Stage 3 CD34⁻CD117⁺CD94⁻CD56⁻/⁺ → **Stage 4 CD34⁻CD94⁺CD56^bright CD16⁻** → **Stage 5 CD56^dim CD16⁺**, with **Stage 6 CD57⁺ CD56^dim**.

### 5.3 NK cell subsets (CD56^bright, CD56^dim, CD57⁺CD56^dim) using **CD94, CD56, T-BET, EOMES, CD16, CD57**
Within Lin⁻ **CD127^lo/⁻** cells, plot CD56 against CD16, then overlay CD94, CD57 and the T-BET/EOMES pair:

| Subset | Gate |
|---|---|
| **CD56^bright NK** (immature, cytokine-producing) | **CD56^bright CD16^−/lo CD94^hi CD57⁻**, **EOMES^hi T-BET^int**, NKp46⁺, CD117^lo, CD161⁺ |
| **CD56^dim NK** (mature, cytotoxic) | **CD56^dim CD16⁺ CD94^int/lo CD57⁻**, **EOMES⁺ T-BET^hi**, NKp46⁺ |
| **CD57⁺ CD56^dim NK** (terminally differentiated/adaptive) | **CD56^dim CD16⁺ CD57⁺ CD94^lo/⁻**, **T-BET^hi EOMES^int/lo** |

The strategy is explicitly a maturation axis: **CD94 is high on CD56^bright cells and is progressively lost as cells become CD56^dim and then CD57⁺**, while **CD16 and CD57 are progressively gained and the T-BET:EOMES ratio inverts** (EOMES-dominant in CD56^bright → T-BET-dominant in CD57⁺CD56^dim). Plotting CD94 vs CD57 on CD56^dim cells, and T-BET vs EOMES on each of the three gates, gives the ordered trajectory from Stage 4 through Stage 6.

### 5.4 ILC1 and ieILC1 (using **CD103, T-BET, GATA3, CD127**)
Within Lin⁻ cells:

* **ILC1:** **CD127⁺** CD117⁻ CD294⁻ NKp44⁻ CD103⁻ CD161⁺, **T-BET⁺**, **GATA3^lo** (helper-ILC-level GATA3, clearly below ILC2), **EOMES⁻**, RORγt⁻, CD56^−/lo.
* **ieILC1 (intraepithelial ILC1; prominent in tonsil, essentially absent from blood):** **CD103⁺** CD56⁺ **CD94⁺** NKp46⁺, **CD127^lo/⁻**, **T-BET^hi**, **EOMES⁺**, **GATA3^lo**, CD161⁺, NKp44^+/−.

The four markers named do the discrimination explicitly: **CD103** separates the intraepithelial (ieILC1) from the conventional ILC1; **CD127** is high on ILC1 and low/negative on ieILC1 (and negative on NK); **T-BET** is required by both and marks them against ILC2/ILC3; **GATA3** is low-but-present in both (confirming helper-ILC identity in ILC1 and distinguishing them from GATA3^hi ILC2); and EOMES separates ieILC1 (EOMES⁺) from ILC1 (EOMES⁻).

### 5.5 ILC2
**ILC2 are explicitly defined as CD127-positive, CD117-positive, CD294-positive and GATA3-positive:**

> Lin⁻ (CD3⁻CD19⁻CD14⁻CD31⁻) → **CD127⁺** → **CD117⁺** → **CD294 (CRTH2)⁺** → **GATA3⁺ (GATA3^hi)**

with CD161⁺, CD25⁺, and RORγt⁻, T-BET⁻, NKp44⁻ as confirmatory negatives. The four-marker sequence (CD127⁺ CD117⁺ CD294⁺ GATA3^hi) is the gate; CD294 is the ILC2-defining surface receptor and GATA3^hi is its transcription-factor confirmation (GATA3 is expressed at an intermediate level by all helper ILCs, so the ILC2 call requires the *high* level together with CD294 positivity).

### 5.6 Group 3 ILCs — NCR⁻ ILC3, NCR⁺ ILC3 and LTi (using **CD127, CD117, RORγt, NKp44, CCR6**)
Within Lin⁻ **CD127⁺ CD117⁺ CD294⁻** cells, gate **RORγt⁺** (group 3 identity), then split on **NKp44** and **CCR6**:

| Population | Gate |
|---|---|
| **NCR⁻ ILC3** | CD127⁺ CD117⁺ **RORγt⁺ NKp44⁻** CCR6^+/− , CD294⁻, T-BET^lo |
| **NCR⁺ ILC3** | CD127⁺ CD117⁺ **RORγt⁺ NKp44⁺** (NKp46^+/−), CD294⁻ — the IL-22-producing, mucosa-associated ILC3 |
| **LTi (lymphoid-tissue-inducer) cells** | CD127⁺ CD117⁺ **RORγt⁺ CCR6⁺ NKp44⁻**, CD25⁺, **PLZF⁻** — CCR6 is the defining marker that separates the LTi/LTi-like lineage from the other ILC3 |

Tonsil is the correct tissue for all three (blood contains essentially only a small NKp44⁻ ILC3-like/ILCP population), and NKp44 vs CCR6 on RORγt⁺ cells resolves all three in one plot. A T-BET-vs-RORγt plot additionally captures the ILC3→ILC1 "ex-ILC3" plasticity axis.

### 5.7 The transcription-factor read-out through differentiation
Because all seven factors are measured in the same cells, the panel directly reports the sequence:

$$\text{CLP} \xrightarrow{\textbf{NFIL3}\uparrow} \text{CILP (NFIL3}^+\textbf{ID2}^+\text{)} \xrightarrow{} \begin{cases} \textbf{NKP (CD122}^+ \text{)} \rightarrow \text{EOMES}\uparrow \rightarrow \text{CD56}^{\text{bright}} \rightarrow \text{CD56}^{\text{dim}} \rightarrow \text{CD57}^+ \;(\textbf{T-BET}\uparrow)\\ \textbf{CHILP/ILCP (\textbf{PLZF}}^+\text{)} \rightarrow \begin{cases}\text{ILC1}\;(\textbf{T-BET}^+,\text{GATA3}^{lo})\\ \text{ieILC1}\;(\text{CD103}^+,\textbf{T-BET}^{hi},\text{EOMES}^+)\\ \text{ILC2}\;(\textbf{GATA3}^{hi},\text{CD294}^+)\\ \text{ILC3/LTi}\;(\textbf{ROR}\gamma\textbf{t}^+,\text{NKp44}^{\pm},\text{CCR6}^{\pm})\end{cases}\end{cases}$$

Quantitative analysis: report TF median fluorescence intensity (and %positive vs FMO) per developmental gate, then confirm the trajectory in an unsupervised arm — UMAP/opt-SNE on the arcsinh-transformed unmixed data, FlowSOM/Phenograph clustering, and pseudotime (Slingshot/Wanderlust) rooted on the CD34⁺α4β7⁺ CILP — with tonsil and blood analysed both separately and together, batch-corrected against the longitudinal reference sample.

---

## 6. Commercial availability and reagent notes

All 29 parameters are achievable with catalogued reagents from the stated vendors (BioLegend, BD Biosciences, Miltenyi, Thermo Fisher), including the **Zombie NIR fixable viability dye (BioLegend 423105)** required for this cryopreserved-sample workflow, and the True-Nuclear/Foxp3 transcription-factor buffer sets and Brilliant Stain Buffer Plus needed to run polymer dyes with intracellular staining. Two practical notes:

* **NFIL3 (E4BP4)** is not routinely sold as a flow-ready conjugate. The purified monoclonal/polyclonal antibody is commercially available (Thermo Fisher, Novus) and is conjugated in-house with **Lightning-Link (Abcam) or Zenon** chemistry to Alexa Fluor 532, or detected with a biotinylated antibody plus streptavidin-AF532; the conjugate must be titrated and validated against a positive control (CD34⁺ progenitors, NK cells) and a negative control (B cells), with the same reference control used for unmixing.
* Where a specific listed conjugate is temporarily unavailable, validated same-channel swaps are: CD94 DX22 APC ↔ EOMES moved to Alexa Fluor 647-free channel; CD294 BM16 PE-Dazzle 594 ↔ GATA3 to BV711 (BD L50-823) with CD127 moved to BUV661; RORγt PE (Q21-559) ↔ ID2 to eFluor 660. Any swap is re-checked in the Full Spectrum Viewer for similarity index and spreading before use.

---

## 7. Final panel summary

**29 parameters on the 5-laser Cytek Aurora**, each on a distinct peak channel: viability (Zombie NIR, **R7**); a four-antibody lineage **dump** removing T cells (CD3), B cells (CD19), myeloid cells (CD14) and stromal cells (CD31) in **V5**; CD45 (**UV16**); progenitor markers CD34 (**UV3**), CD45RA (**UV7**), CD10 (**V10**), integrin β7 (**YG5**), CD7 (**UV9**), CD117 (**V13**), CD127 (**V11**), CD122 (**UV14**), CD161 (**V1**); NK-maturation markers CD56 (**V9**), CD16 (**V3**), CD57 (**V7**), CD94 (**R6**), NKp46 (**R3**), NKp44 (**B9**); helper-ILC markers CD294 (**B8**), CCR6 (**UV11**), CD103 (**B6**), CD25 (**R8**); and the transcription factors NFIL3 (**B3**), ID2 (**YG1**), PLZF (**B2**), T-BET (**YG10**), EOMES (**R1**), GATA3 (**YG3**) and RORγt (**V14**). This resolves CLP, **CILP, NKP and CHILP/ILCP** precursors, the **CD56^bright → CD56^dim → CD57⁺CD56^dim** NK trajectory, **ILC1 and ieILC1**, **ILC2 (CD127⁺CD117⁺CD294⁺GATA3⁺)**, and **NCR⁻ ILC3, NCR⁺ ILC3 and LTi** cells, while measuring the lineage-specifying transcription factors — including the early specification factors **NFIL3 and ID2** and the intermediate-precursor factor **PLZF** — across the whole differentiation path in both peripheral blood and tonsil.
