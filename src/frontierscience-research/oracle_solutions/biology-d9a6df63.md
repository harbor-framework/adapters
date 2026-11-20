# Interpreting elevated BMP before vancomycin and its fall afterwards

## 1. Framing the problem

The clinical picture — **abnormal body movements (a movement disorder/dystonia-like presentation), memory loss and agitation** — is compatible with a neuronal **lysosomal storage disorder (LSD)**, and **bis(monoacylglycero)phosphate (BMP, also called LBPA, lysobisphosphatidic acid)** was therefore measured as a lysosomal biomarker. BMP is a di-acylated anionic phospholipid that is highly enriched in the internal membranes of late endosomes/multivesicular bodies and lysosomes, where it supports intraluminal vesicle formation, lipid sorting and sphingolipid hydrolysis (including activation of acid sphingomyelinase and presentation of glycosphingolipids to hydrolases via saposins). Its accumulation is a well-recognised marker of **lysosomal lipid storage and of drug-induced phospholipidosis**, and it is elevated in disorders such as Niemann–Pick disease types A/B and C and in several other LSDs.

The result set to be explained is:

| Time point | Brain BMP | Serum BMP |
|---|---|---|
| Before vancomycin | **Elevated** | **Elevated** |
| After vancomycin | (not re-measured / unchanged) | **Notably reduced** |

The key interpretive problem is that the **serum signal fell after an antibacterial drug was given**, which no primary, host, genetic lysosomal defect can plausibly explain — a germline LSD does not resolve over days in response to vancomycin. The explanation must therefore lie in (a) a *bacterial* contribution to the measured signal, and (b) an *analytical* limitation of the method used.

---

## 2. The analytes measured were anionic phospholipids — and BMP is not the only one

The assay quantified **anionic (acidic) phospholipids**. This class comprises several structurally related species, including:

- **phosphatidylglycerol (PG)**
- **phosphatidylserine (PS)**
- **phosphatidylinositol (PI) and its phosphorylated forms**
- **phosphatidic acid (PA)** and **cardiolipin (CL)**
- **BMP (bis(monoacylglycero)phosphate)**

Among these, **PG is structurally extremely similar to BMP** — indeed the two are the central problem here. Both carry a single phosphodiester bridging two glycerol backbones with two fatty-acyl chains in total; they differ only in the *distribution* of those acyl chains:

- **PG**: both acyl chains esterified to the *same* glycerol (sn-1 and sn-2 of one glycerol), with the second glycerol as a free, unacylated head group — i.e. a **1,2-diacyl-sn-glycero-3-phospho-(1′-glycerol)**.
- **BMP**: **one acyl chain on each of the two glycerols** flanking the phosphate — i.e. a symmetric **sn-(2-acyl)glycero-phospho-sn-(2′-acyl)glycerol** (in the lysosomal 2,2′-isomer with the unusual S,S stereochemistry).

Because they contain the same atoms in the same numbers and differ only in acyl positioning (and stereochemistry), **BMP and PG of the same total acyl composition are structural (positional/regio-) isomers**: for example BMP 18:1/18:1 and PG 18:1/18:1 share the identical molecular formula and identical nominal and exact mass.

### Why this matters for GC-MS

**GC-MS cannot directly distinguish BMP from PG.** The reasons are inherent to the method:

- Intact phospholipids are non-volatile and thermally labile, so GC-MS analysis of phospholipids requires **chemical derivatisation — typically transesterification/hydrolysis to fatty acid methyl esters (FAMEs) or release of the glycerophosphoglycerol backbone**. This destroys exactly the information (acyl *position* on the two glycerols) that distinguishes BMP from PG. A BMP species and the corresponding PG species liberate the **same fatty acids in the same ratio and the same glycerophosphoglycerol backbone**, so they give **indistinguishable chromatographic and mass spectral signatures**.
- Being isomers, they have **identical exact mass**, so even accurate mass measurement in a single-stage experiment cannot separate them.
- The derivatised products co-elute or elute with insufficient resolution, and the fragmentation of the derivatives does not report acyl positional isomerism.

**Consequence: the "BMP" value reported by this GC-MS assay is not BMP-specific. It is a composite measurement of BMP plus any co-measured isomeric/co-eluting anionic phospholipid — above all PG.** Any elevation of PG will be read out as an elevation of BMP.

---

## 3. Biological basis of the elevated BMP *before* treatment

### 3.1 The bacterial contribution: *Staphylococcus aureus* membranes are PG-rich

*Staphylococcus aureus*, like other Gram-positive bacteria, has a membrane lipidome quite unlike that of mammalian cells. It contains **no phosphatidylcholine and no cholesterol**, and instead its membrane is dominated by anionic and glycolipid species: **phosphatidylglycerol (PG) is the major membrane phospholipid of *Staphylococcus*** (typically the largest single phospholipid fraction), together with lysyl-PG (lysyl-phosphatidylglycerol, the MprF product), cardiolipin (itself made from two PG molecules) and glycolipids such as diglucosyldiacylglycerol. PG is also the biosynthetic precursor of lipoteichoic acid in these organisms, which further amplifies PG turnover and demand.

Therefore a **rapidly worsening, high-burden *S. aureus* infection delivers a large load of bacterial PG** into the patient — from circulating bacteria themselves, from bacterial membrane fragments and released membrane vesicles, and from lysed organisms (bacteriolysis by host neutrophils and complement, and, once treatment begins, by the antibiotic). This bacterially derived PG is present in blood and is extracted along with host lipids in the sample preparation. Host inflammatory responses (increased lipoprotein-associated phospholipid turnover, phagocyte activation) and uptake of bacterial lipids by phagocytes can add to the anionic phospholipid load.

**Result: elevated serum PG → elevated apparent "BMP" on GC-MS, because the method cannot resolve the two isomers.** The pre-treatment "elevation of BMP" is therefore, at least in substantial part, an **elevation of PG misread as BMP** — i.e. the observed BMP increase is connected to, and explained by, the presence of PG in the sample. (A genuine component of true BMP elevation may coexist — see §5 — but it cannot be separated from the PG contribution by this assay.)

### 3.2 Possible host/lysosomal contribution

Two host mechanisms could additionally raise *genuine* BMP:

- **An underlying LSD**, consistent with the neurological history (movement disorder, memory loss, agitation): impaired lysosomal lipid catabolism (e.g. Niemann–Pick A/B/C) causes true BMP accumulation in late endosomes/lysosomes, which can be reflected in both brain tissue and plasma/serum.
- **Secondary (acquired) lysosomal dysfunction/phospholipidosis**, driven by heavy phagocytic loading of macrophages with bacterial membrane lipids, by inflammation, or by cationic amphiphilic drug exposure, all of which can transiently raise BMP.

Importantly, the **brain** elevation is less readily attributable to circulating bacterial PG (bacteria and their lipids are largely excluded from brain parenchyma by the blood–brain barrier unless there is CNS infection), so the brain signal is the more suggestive of a genuine lysosomal abnormality — although brain tissue also contains mitochondrial cardiolipin and host PG, which again are not distinguished by GC-MS.

---

## 4. Biological basis of the fall in serum BMP *after* vancomycin

**Vancomycin** is a glycopeptide that binds the **D-Ala-D-Ala terminus of lipid II/peptidoglycan precursors**, blocking transglycosylation and transpeptidation and therefore cell-wall synthesis in Gram-positive organisms. It is bactericidal against *S. aureus*, and effective therapy produces a rapid reduction in bacterial burden and in circulating bacterial material (with clearance of bacterial debris and membrane fragments by the reticuloendothelial system).

Because the bacteria are the source of the excess PG:

1. Vancomycin reduces the *S. aureus* bacterial load.
2. The **supply of bacterial PG (and lysyl-PG/cardiolipin) into the circulation falls**, and existing bacterial lipid debris is cleared.
3. Since the GC-MS "BMP" signal includes that PG, the **measured serum BMP falls** — not because lysosomal BMP in the patient's cells has changed, but because the **PG interference has been removed**.

This also explains the **compartment-specific nature of the change**: the serum signal, which carried the bacterial PG contribution, fell; there is no reason for the brain signal to fall in parallel over the same timescale, since brain BMP reflects host lysosomal biology rather than circulating bacterial lipid. A fall in serum "BMP" that tracks antibiotic therapy is thus a **strong internal indicator that the pre-treatment serum elevation was an analytical artefact of PG co-measurement, not evidence of a treatable lysosomal defect.**

**Summary of the mechanism:**

$$\text{high }\textit{S. aureus}\text{ burden} \rightarrow \uparrow\text{bacterial PG in serum} \xrightarrow{\text{GC-MS cannot resolve PG from its isomer BMP}} \uparrow\text{apparent BMP}$$
$$\xrightarrow{\text{vancomycin} \,\rightarrow\, \downarrow \text{bacterial load}} \downarrow \text{PG} \rightarrow \downarrow \text{apparent serum BMP}$$

---

## 5. Diagnostic implication: BMP alone cannot establish an LSD

Several conclusions follow, and they bear directly on how the patient should be investigated:

- **The "elevated BMP" result is not interpretable as evidence of an LSD on its own.** It is confounded by PG from the staphylococcal infection and by the inability of GC-MS to distinguish the isomers. The fall after vancomycin demonstrates that confounding empirically.
- **BMP is in any case a non-specific biomarker.** Even when measured accurately, BMP/LBPA is raised in many LSDs (Niemann–Pick A/B/C, several sphingolipidoses, mucolipidoses), in drug-induced phospholipidosis (cationic amphiphilic drugs: amiodarone, chloroquine, several antidepressants and antibiotics), and in states of general lysosomal stress or inflammation. A raised value identifies "lysosomal lipid handling is abnormal", not *which* disease — and it has limited sensitivity and specificity for any individual LSD.
- **Therefore, further testing beyond BMP measurement is essential before an LSD diagnosis can be confirmed.** Confirmation requires orthogonal, disease-specific evidence: a demonstrated enzymatic deficiency, a causative genotype, disease-specific storage material, and supporting imaging/pathology. Measurement should also be repeated once the infection has fully resolved, so that the baseline is not contaminated by bacterial lipid or acute inflammation.

---

## 6. Other methods that would be appropriate

### 6.1 An analytical method for BMP that is not confounded by PG

The immediate requirement is to re-measure BMP with a technique that **resolves BMP from its isomer PG**, so that PG cannot interfere with the result. Appropriate choices:

- **a. LC-MS/MS (liquid chromatography–tandem mass spectrometry).** This is the method of choice. Intact phospholipids are analysed without derivatisation, so acyl positional information is retained. Reversed-phase LC separates BMP from PG by retention time, and, critically, **tandem MS gives isomer-distinguishing product ions**: in negative-ion mode, BMP (two monoacylglycerols) yields characteristic monoacylglycerophosphate/lyso-type fragments and a diagnostic neutral-loss pattern, whereas PG yields the glycerophosphoglycerol head-group fragment ($m/z$ 245/209/152 series) and a diacylglycerol-derived pattern; multiple-reaction monitoring (MRM) transitions can be chosen that are specific to BMP and not shared with PG. This directly **prevents interference from PG**, which is precisely the failure of the GC-MS assay.
- **b. HILIC-LC-MS (hydrophilic interaction liquid chromatography–MS).** HILIC separates phospholipid classes by head-group polarity rather than by acyl chain, so BMP and PG are resolved into distinct, class-specific retention windows before they ever reach the detector. This is particularly valuable here because the two isomers have identical mass and would otherwise be inseparable; chromatographic class separation removes the PG interference at the front end and can be coupled to MS/MS for confirmation.
- **c. High-resolution mass spectrometry (Orbitrap or Q-TOF).** High resolving power and sub-ppm mass accuracy, combined with HCD/CID fragmentation (and ideally ion mobility, which separates isomers by collision cross-section), allow unambiguous assignment of the species and separation of true BMP from PG and from other co-eluting anionic phospholipids — again, specifically to avoid the PG interference that invalidates the GC-MS result.

Supporting good practice for whichever platform is chosen: use **authentic BMP and PG standards (including the di-18:1 pair) and stable-isotope-labelled internal standards** to demonstrate chromatographic resolution and to exclude cross-talk; analyse a PG-spiked matrix to prove that PG does not generate signal in the BMP channel; and confirm the lysosomal **2,2′-BMP isomer** specifically. A complementary orthogonal approach is immunostaining/imaging of BMP (anti-LBPA antibody, e.g. 6C4) in patient fibroblasts, which reports lysosomal BMP accumulation morphologically and is insensitive to bacterial PG entirely.

### 6.2 Enzyme assays (functional confirmation of an LSD)

**Enzyme activity assays** are the cornerstone of LSD diagnosis and should be performed to confirm or exclude the suspected disorder. In leucocytes, dried blood spots, cultured skin fibroblasts or plasma, assay the relevant lysosomal hydrolases with fluorogenic (4-methylumbelliferyl) or MS-based substrates, with an appropriate reference enzyme measured in parallel as a sample-quality control. Given the neurological phenotype, a panel-based approach is appropriate: **acid sphingomyelinase** (Niemann–Pick A/B), **β-glucocerebrosidase** (Gaucher), **β-galactosidase and hexosaminidase A/B** (GM1/GM2 gangliosidoses), **arylsulfatase A** (metachromatic leukodystrophy), **galactocerebrosidase** (Krabbe), **α-L-iduronidase and other MPS enzymes**, **acid lipase** and **α-glucosidase**. Importantly, Niemann–Pick type C — which fits a movement disorder with cognitive and psychiatric features particularly well — has **no primary enzyme deficiency**, so it requires the specific biochemical markers below plus genetics.

### 6.3 Imaging and cholesterol/storage accumulation assays

- **Brain MRI** (with volumetric and, where available, MR spectroscopy sequences) to look for the structural correlates of a neuronal LSD: cerebellar and brainstem atrophy, white-matter signal change/leukodystrophy pattern, thinning of the corpus callosum, hippocampal and cortical atrophy, basal-ganglia signal abnormality (including the "eye-of-the-tiger" sign if a PANK2/NBIA-type disorder is considered given the movement disorder), and iron deposition on susceptibility-weighted imaging. MRI also serves to exclude alternatives (CNS infection/abscess, which is relevant in a bacteraemic patient, stroke, demyelination, hydrocephalus).
- **Cholesterol accumulation assays** — most importantly **filipin staining of cultured skin fibroblasts** for unesterified cholesterol accumulation in late endosomes/lysosomes, the classical cytochemical test for **Niemann–Pick type C**, supported by impaired cholesterol esterification (LDL-induced esterification assay). These should be combined with the NPC-specific plasma biomarkers (**oxysterols such as cholestane-3β,5α,6β-triol and 7-ketocholesterol, lysosphingomyelin-509/lyso-SM, and bile acid metabolite B**), which are not isomeric with bacterial PG and therefore unaffected by the infection.
- **Additional supportive investigations**: ophthalmological examination (vertical supranuclear gaze palsy, cherry-red spot, retinopathy, corneal clouding), hepatosplenomegaly assessment by abdominal ultrasound, electron microscopy of a tissue biopsy or of buffy-coat cells for lamellar/multilamellar storage bodies and foam cells, bone marrow examination for storage macrophages, and urinary glycosaminoglycan/oligosaccharide screening.

### 6.4 Genetic sequencing

**Molecular genetic testing** provides the definitive diagnosis and is unaffected by the infection or by any lipid-analytical artefact. Appropriate strategy:

- a **targeted next-generation-sequencing LSD/neurometabolic gene panel** (covering, e.g., *SMPD1*, *NPC1*, *NPC2*, *GBA1*, *GLA*, *GALC*, *ARSA*, *HEXA/HEXB*, *GLB1*, *IDUA* and the other MPS genes, *GAA*, *LIPA*, *CTSD*, *CLN1–14*, plus *PANK2* and other NBIA genes given the movement disorder), or
- **whole-exome or whole-genome sequencing** if the panel is negative, which additionally detects non-canonical splice, deep-intronic and structural variants;
- with **copy-number/deletion-duplication analysis (MLPA/array)**, **RNA studies** to resolve splice variants, **parental segregation testing** and **variant classification by ACMG criteria**;
- and, where a variant of uncertain significance is found, functional confirmation by the corresponding enzyme assay or storage assay, closing the loop between genotype and biochemistry.

---

## 7. Final answer

**Before treatment:** the patient had a heavy *Staphylococcus aureus* infection, and **PG (phosphatidylglycerol) is the major membrane phospholipid of *Staphylococcus***, so bacterial membranes, membrane vesicles and lysed organisms released a large excess of PG into the circulation. The GC-MS assay quantified **anionic phospholipids**, a class that includes **PG, PS and BMP**, and **BMP and PG are structural isomers** — identical molecular formula, differing only in the positions of the two acyl chains on the two glycerols — which **GC-MS cannot directly distinguish**, because derivatisation to FAMEs/backbone fragments destroys the positional information and the isomers have identical exact mass. The **apparent elevation of BMP therefore reflects the presence of bacterially derived PG being counted as BMP** (with, possibly, a smaller genuine BMP contribution, most plausibly in the brain, from an underlying or secondary lysosomal abnormality).

**After treatment:** vancomycin killed the *S. aureus*, **lowering the bacterial PG load in serum**; because that PG was being measured as BMP, the **serum "BMP" level fell**. The fall is thus an antibiotic-driven reduction in PG interference, not a change in lysosomal BMP — and the compartment specificity (serum falls, brain need not) supports this.

**Consequently, BMP measurement alone cannot confirm a lysosomal storage disorder, and further testing is required.** The recommended additional methods are: (1) re-measurement of BMP by a **PG-resolving technique — LC-MS/MS (ideally MRM with BMP-specific transitions), HILIC-LC-MS, or high-resolution MS (Orbitrap/Q-TOF), chosen specifically to prevent interference from PG** — with authentic standards and after the infection has resolved; (2) **lysosomal enzyme activity assays** (acid sphingomyelinase, β-glucocerebrosidase, hexosaminidase A/B, β-galactosidase, arylsulfatase A, galactocerebrosidase, etc.) in leucocytes/dried blood spots/fibroblasts; (3) **imaging and storage assays — brain MRI** (atrophy, white-matter and basal-ganglia changes) and **cholesterol accumulation assays (filipin staining of fibroblasts, cholesterol esterification, plasma oxysterols/lyso-SM)**, plus ophthalmology and electron microscopy for storage bodies; and (4) **genetic sequencing** — a targeted LSD/neurometabolic NGS panel or whole-exome/genome sequencing with copy-number analysis — to identify the causative mutation and establish the diagnosis definitively.
