# Completing the enzyme purification table

## 1. Definitions of the quantities and the working formulas

Each step is reported as five columns, in order:

**Volume (mL); Protein concentration (mg/mL); Activity (units/mL); Specific activity (units/mg); Yield (%)**

Note carefully that "Activity" in this table is a **volumetric** activity (units per mL), and "Protein concentration" is a **concentration** (mg per mL). Therefore:

**(i) Specific activity** — activity per unit mass of protein. Because both "Activity" and "Protein concentration" are per-mL quantities, the volume cancels and

$$\text{Specific activity}\ \left(\tfrac{\text{units}}{\text{mg}}\right) = \frac{\text{Activity}\ (\text{units/mL})}{\text{Protein concentration}\ (\text{mg/mL})}$$

This is **Activity ÷ Protein concentration**, *not* Activity ÷ (total protein). Dividing the volumetric activity by the total protein (mg) would mix a per-mL numerator with an absolute denominator and give a meaningless number.

**(ii) Protein concentration** — rearranging (i):

$$\text{Protein concentration} = \frac{\text{Activity}}{\text{Specific activity}}$$

**(iii) Total activity** — the absolute number of units present in the whole fraction at a given step:

$$\text{Total activity}\ (\text{units}) = \text{Volume}\ (\text{mL}) \times \text{Activity}\ (\text{units/mL})$$

"Total activity" is therefore **not** the same quantity as "Activity": the latter is units/mL, the former is units.

**(iv) Yield** — the fraction of the enzyme activity originally present that survives to the step in question, expressed as a percentage:

$$\text{Yield}\ (\%) = \left[\frac{\text{Total activity at that step}}{\text{Total activity in the first step}}\right] \times 100$$

Equivalently, $\text{Total activity at a step} = \dfrac{\text{Yield}\,(\%)}{100}\times \text{Total activity}_{\text{step 1}}$, which is the form used to back-calculate volumes and activities below.

**(v) Yield of the first step.** The crude extract (step 1) is by definition the reference against which all later steps are measured, so its total activity is the denominator of its own yield:

$$\text{Yield}_{\text{step 1}} = \frac{\text{Total activity}_{\text{step 1}}}{\text{Total activity}_{\text{step 1}}}\times 100 = 100\%$$

Purification can only lose activity, never create it, so the starting yield is always the maximum possible value:

$$\mathbf{B = 100.0\ \%}$$

## 2. Reference total activity (step 1)

$$\text{Total activity}_{\text{step 1}} = 1450\ \text{mL} \times 9\ \text{units/mL} = 13{,}050\ \text{units}$$

All yields below are referred to this value.

## 3. Step-by-step calculation

### Step 1 — 1450; A; 9; 0.8; B

$$A = \frac{\text{Activity}}{\text{Specific activity}} = \frac{9}{0.8} = 11.25 \Rightarrow \mathbf{A = 11.3\ \text{mg/mL}}$$

$$\mathbf{B = 100.0\ \%}\quad(\text{reference step, maximum yield})$$

### Step 2 — 1450; 8; C; D; 87.5

Use the yield to obtain the total activity at this step, then convert to a volumetric activity:

$$\text{Total activity}_2 = \frac{87.5}{100}\times 13{,}050 = 11{,}418.75\ \text{units}$$

$$C = \frac{\text{Total activity}_2}{\text{Volume}} = \frac{11{,}418.75}{1450} = 7.875 \Rightarrow \mathbf{C = 7.9\ \text{units/mL}}$$

$$D = \frac{\text{Activity}}{\text{Protein concentration}} = \frac{7.875}{8} = 0.984 \Rightarrow \mathbf{D = 1.0\ \text{units/mg}}$$

### Step 3 — 280; E; 30; 11; F

$$E = \frac{\text{Activity}}{\text{Specific activity}} = \frac{30}{11} = 2.727 \Rightarrow \mathbf{E = 2.7\ \text{mg/mL}}$$

$$\text{Total activity}_3 = 280 \times 30 = 8400\ \text{units}$$

$$F = \frac{8400}{13{,}050}\times 100 = 64.37 \Rightarrow \mathbf{F = 64.4\ \%}$$

### Step 4 — G; H; 900; 150; 37

$$\text{Total activity}_4 = \frac{37}{100}\times 13{,}050 = 4828.5\ \text{units}$$

$$G = \frac{\text{Total activity}_4}{\text{Activity}} = \frac{4828.5}{900} = 5.365 \Rightarrow \mathbf{G = 5.4\ \text{mL}}$$

$$H = \frac{\text{Activity}}{\text{Specific activity}} = \frac{900}{150} = 6.0 \Rightarrow \mathbf{H = 6.0\ \text{mg/mL}}$$

### Step 5 — 10; 2; I; J; 32

$$\text{Total activity}_5 = \frac{32}{100}\times 13{,}050 = 4176\ \text{units}$$

$$I = \frac{\text{Total activity}_5}{\text{Volume}} = \frac{4176}{10} = 417.6 \Rightarrow \mathbf{I = 417.6\ \text{units/mL}}$$

$$J = \frac{\text{Activity}}{\text{Protein concentration}} = \frac{417.6}{2} = 208.8 \Rightarrow \mathbf{J = 208.8\ \text{units/mg}}$$

### Step 6 — 5; K; 700; 500; L

$$K = \frac{\text{Activity}}{\text{Specific activity}} = \frac{700}{500} = 1.4 \Rightarrow \mathbf{K = 1.4\ \text{mg/mL}}$$

$$\text{Total activity}_6 = 5 \times 700 = 3500\ \text{units}$$

$$L = \frac{3500}{13{,}050}\times 100 = 26.819 \Rightarrow \mathbf{L = 26.8\ \%}$$

## 4. Completed purification table

| Step | Volume (mL) | Protein conc. (mg/mL) | Activity (units/mL) | Specific activity (units/mg) | Total activity (units) | Yield (%) |
|---|---|---|---|---|---|---|
| 1 | 1450 | **A = 11.3** | 9 | 0.8 | 13,050 | **B = 100.0** |
| 2 | 1450 | 8 | **C = 7.9** | **D = 1.0** | 11,418.8 | 87.5 |
| 3 | 280 | **E = 2.7** | 30 | 11 | 8,400 | **F = 64.4** |
| 4 | **G = 5.4** | **H = 6.0** | 900 | 150 | 4,828.5 | 37 |
| 5 | 10 | 2 | **I = 417.6** | **J = 208.8** | 4,176 | 32 |
| 6 | 5 | **K = 1.4** | 700 | 500 | 3,500 | **L = 26.8** |

## Final answer

$$A = 11.3,\quad B = 100.0,\quad C = 7.9,\quad D = 1.0,\quad E = 2.7,\quad F = 64.4,$$
$$G = 5.4,\quad H = 6.0,\quad I = 417.6,\quad J = 208.8,\quad K = 1.4,\quad L = 26.8$$

The scheme behaves as a sensible purification: specific activity rises monotonically from 0.8 to 500 units/mg (a 625-fold purification) while the yield falls from 100.0 % to 26.8 %, the usual trade-off between purity and recovery.
