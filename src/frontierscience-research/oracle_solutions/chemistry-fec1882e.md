# Identification of an unknown lipid: $[M+\mathrm{Na}]^+$ 846.56 → 363.27 / 337.27

## 1. Convert the observed precursor to a neutral (monoisotopic) mass

The precursor was detected as a **sodium adduct** in positive mode. A sodium adduct adds a sodium cation in place of nothing (no proton is lost from the neutral), so

$$[M+\mathrm{Na}]^+ = M + m(\mathrm{Na}) - m(e^-)$$

The **mass of sodium is about 23 Da** (monoisotopic $^{23}$Na = 22.9898 Da; subtracting the electron mass is negligible at this precision). Hence

$$M = 846.56 - 22.99 \approx \mathbf{823.57\ \text{Da}} \approx 823.6\ \text{Da}$$

**The neutral mass of the unknown compound is therefore about 823.6 Da.** This is far too large for a mono- or diacylglycerol and sits squarely in the glycerophospholipid range, which already suggests a phosphorus-containing lipid rather than a neutral lipid.

## 2. Identify the two product ions

The two major product ions differ by

$$363.27 - 337.27 = 26.00\ \text{Da} = \mathrm{C_2H_2}\ (26.016)$$

i.e. the two fragments are members of the same homologous series differing by **two carbons and one double bond** — the classic relationship between, e.g., an 18:2 and a 20:3 acyl species.

Acylglycerol fragment ions in positive mode are observed as the **water-loss (dehydrated) acylglycerol ion**, $[\text{acylglycerol} + \mathrm{H} - \mathrm{H_2O}]^+$. Testing monoacylglycerols (MAG = glycerol + one acyl chain):

**MAG 18:2 (1-linoleoyl-glycerol), C$_{21}$H$_{38}$O$_4$, monoisotopic 354.28 Da:**

$$[\mathrm{MAG\ 18{:}2}+\mathrm{H}-\mathrm{H_2O}]^+ = 354.28 + 1.008 - 18.011 = \mathbf{337.27}$$

**MAG 20:3 (1-eicosatrienoyl-glycerol), C$_{23}$H$_{40}$O$_4$, monoisotopic 380.29 Da:**

$$[\mathrm{MAG\ 20{:}3}+\mathrm{H}-\mathrm{H_2O}]^+ = 380.29 + 1.008 - 18.011 = \mathbf{363.28}$$

Both match the observed ions to within rounding.

- **$m/z$ 337.27 is the MAG 18:2 derivative** — the dehydrated monoacylglycerol ion of a linoleoyl (18:2) chain, i.e. $[\mathrm{MAG}(18{:}2)-\mathrm{H_2O}+\mathrm{H}]^+$ (equivalently the 18:2 acyl group carried on a glycerol backbone that has lost one water).
- **$m/z$ 363.27 is the MAG 20:3 derivative** — the dehydrated monoacylglycerol ion of an eicosatrienoyl (20:3) chain, $[\mathrm{MAG}(20{:}3)-\mathrm{H_2O}+\mathrm{H}]^+$.

(Cross-check: the corresponding acylium/ketene-type ions would be 263.2 for 18:2 and 289.3 for 20:3, and the free-fatty-acid-related ions 281.2/307.3 — neither matches, confirming the fragments retain a glycerol unit, i.e. they are monoacylglycerol-derived, not simple fatty-acyl ions.)

So the molecule carries **one 18:2 chain and one 20:3 chain** (total acyl composition 38:5).

## 3. Why the absence of a DAG fragment is the decisive clue

Essentially every common glycerophospholipid (PC, PE, PS, PI, PG, PA) and every triacylglycerol is built on a **diacylglycerol (DAG) backbone**: both acyl chains sit on the *same* glycerol. On collision-induced dissociation such lipids lose the head group and give an intense **DAG-type product ion** $[\mathrm{DAG}-\mathrm{H_2O}+\mathrm{H}]^+$ (or its sodiated analogue). The researcher therefore looked for the DAG that carries both detected chains:

**The DAG that would have been looked for is DAG(18:2/20:3)** — a diacylglycerol bearing one 18:2 (linoleoyl) and one 20:3 (eicosatrienoyl) chain. A DAG backbone is never reported by positive-mode MS/MS as the intact diester; it is always seen as the dehydrated diacylglycerol species, so that is the mass that must be searched for:

$$92.047\ (\text{glycerol}) + 280.240\ (18{:}2) + 306.256\ (20{:}3) - 2(18.011)\ (\text{two ester bonds}) - 18.011\ (\text{loss of the free OH as water}) + 1.008\ (\mathrm{H^+})$$

$$\Rightarrow\quad [\mathrm{DAG}(18{:}2/20{:}3) - \mathrm{H_2O} + \mathrm{H}]^+ = \mathbf{625.5}$$

i.e. **the mass of the sought DAG (18:2/20:3) is ≈ 625.5 Da** (the DAG residue itself, DAG − H$_2$O, being **624.5 Da**; the fully esterified neutral diester before this water loss would be 642.5 Da). No ion near $m/z$ 625 was observed, in either the protonated or the sodiated form ($[\mathrm{DAG}-\mathrm{H_2O}+\mathrm{Na}]^+ = 647.5$).

**Interpretation:** the two acyl chains cannot both be on one glycerol. The only way to generate *two* monoacylglycerol-type fragments and *no* diacylglycerol fragment is for the molecule to contain **two separate glycerol backbones, each bearing a single acyl chain**, joined through the only linkage that can hold them together at this mass and that cleaves to give exactly these two ions — a **phosphodiester**. Cleavage on either side of the phosphate then releases the 18:2-bearing monoacylglycerol (337.27) and the 20:3-bearing monoacylglycerol (363.27).

## 4. The identification

A lipid consisting of **two monoacylglycerols bridged by a phosphodiester** is a **bis(monoacylglycero)phosphate (BMP)**, also known in the cell-biology literature as **lysobisphosphatidic acid (LBPA)**.

- **Compound: BMP 18:2/20:3** — bis(monoacylglycero)phosphate carrying one linoleoyl (18:2, 9*Z*,12*Z*) and one eicosatrienoyl (20:3, e.g. 8*Z*,11*Z*,14*Z*, dihomo-$\gamma$-linolenoyl) chain, observed as its sodium adduct at $m/z$ 846.56 (neutral ≈ 823.6 Da).
- **IUPAC-style name** (physiological sn-2,2′ isomer): *(2R)-3-hydroxy-2-[(9Z,12Z)-octadeca-9,12-dienoyloxy]propyl (2R)-3-hydroxy-2-[(8Z,11Z,14Z)-icosa-8,11,14-trienoyloxy]propyl hydrogen phosphate*. (The 1,1′-regioisomer is named analogously, with the acyl groups on the primary positions; MS/MS does not distinguish the regiochemistry, only the chain composition.)
- **Common/shorthand name: BMP 18:2/20:3** (= LBPA 18:2/20:3).

**Lipid classification:** this is a **phospholipid** — specifically a **glycerophospholipid of the glycerophosphoglycerol class (LIPID MAPS GP04)**, and within it the **bis(monoacylglycero)phosphate (BMP/LBPA) sub-class**: a glycerophosphoglycerol in which *each* of the two glycerols carries one acyl chain (in contrast to phosphatidylglycerol, where both chains are on one glycerol and which is why PG would have given the DAG fragment at 625.5). BMP is the anionic marker lipid of late endosomal/lysosomal internal membranes.

## 5. Reconciling the identification with the LipidTOX result

The LipidTOX result is not evidence for a neutral lipid: **LipidTOX reagents stain both neutral lipids and phospholipids** (the HCS LipidTOX family includes neutral-lipid stains for triacylglycerol/cholesteryl-ester-rich lipid droplets *and* a phospholipidosis detection reagent that is a phospholipid analogue reporting on phospholipid accumulation). A concentration-dependent LipidTOX signal is therefore fully consistent with a phospholipid, and in fact BMP/LBPA is *the* diagnostic lipid of drug-induced phospholipidosis — intralysosomal BMP accumulation is exactly what the phospholipidosis reagent reports. So the staining behaviour and the MS/MS data agree: the analyte is an accumulating anionic phospholipid, not a neutral glyceride, which is why no DAG or DAG-derived fragment of any composition was found.

## Final answer

- Sodium (≈ **23 Da**) removed from the precursor $m/z$ 846.56 gives a **neutral mass of ≈ 823.6 Da**.
- **Product ion $m/z$ 337.27 = MAG 18:2 derivative** ($[\mathrm{MAG}(18{:}2)-\mathrm{H_2O}+\mathrm{H}]^+$); **product ion $m/z$ 363.27 = MAG 20:3 derivative** ($[\mathrm{MAG}(20{:}3)-\mathrm{H_2O}+\mathrm{H}]^+$); they differ by C$_2$H$_2$ (26.0 Da).
- Two monoacylglycerol fragments and **no DAG fragment** ⇒ the two chains are on two different glycerols linked by a phosphodiester.
- **Compound: BMP 18:2/20:3** — bis(monoacylglycero)phosphate (lysobisphosphatidic acid, LBPA) with 18:2 and 20:3 chains; IUPAC: (2R)-3-hydroxy-2-[(9Z,12Z)-octadeca-9,12-dienoyloxy]propyl (2R)-3-hydroxy-2-[(8Z,11Z,14Z)-icosa-8,11,14-trienoyloxy]propyl hydrogen phosphate.
- **Class: a phospholipid** — glycerophosphoglycerol class, **bis(monoacylglycero)phosphate (BMP/LBPA) sub-class**.
- **DAG the researcher would have searched for: DAG(18:2/20:3)**, of mass **≈ 625.5 Da** ($[\mathrm{DAG}-\mathrm{H_2O}+\mathrm{H}]^+$, the DAG species MS/MS reports; DAG residue 624.5 Da) — absent from the spectrum.
- **LipidTOX stains both neutral lipids and phospholipids**, so the concentration-dependent stain is consistent with this phospholipid (BMP is the marker lipid of phospholipidosis).
