# Halogen effects on the Au–S breaking energy in a single-molecule break junction

## 0. Data and physical model

Measured/computed quantities:

| Case | Plateau length $L$ (nm) | Breaking energy $E$ (eV) |
|---|---|---|
| No halogen interaction (TCB and TIB) | 0.97 | 1.5 |
| With Cl interaction (TCB) | 0.59 | 1.0 |
| With Cl interaction (TIB) | 0.64 | — |
| With I interaction (TIB) | 0.46 | 0.5 |

Physical picture: the plateau length is the elongation the junction sustains before the Au–S bond ruptures, and the breaking energy is the work needed to rupture it. If the junction is pulled quasi-statically and the energy varies **linearly** with the stretching distance, then

$$E = F\,L \qquad\Longrightarrow\qquad F = \frac{E}{L}$$

i.e. the force acting at the Au–S bond is the energy–distance slope (the mean rupture force over the plateau). Likewise, the sensitivity of the breaking energy to the halogen-induced shortening of the plateau is

$$\left\langle \frac{\Delta E}{\Delta L}\right\rangle = \frac{E_{\text{no halogen}} - E_{\text{halogen}}}{L_{\text{no halogen}} - L_{\text{halogen}}}$$

Unit conversion needed for forces:

$$1\ \text{eV nm}^{-1} = \frac{1.602\times10^{-19}\ \text{J}}{1\times10^{-9}\ \text{m}} = 1.602\times10^{-10}\ \text{N} = \mathbf{0.1602\ \text{nN}}$$

---

## 1. Change in plateau length with Cl

$$\Delta L_{\mathrm{Cl}} = 0.97 - 0.59 = \mathbf{0.38\ \text{nm}}$$

(Using the directly measured Cl-interaction plateau in TCB. The Cl plateau measured in TIB, 0.64 nm, would give $\Delta L = 0.33$ nm, i.e. the same conclusion within experimental scatter.)

## 2. Change in plateau length with I

$$\Delta L_{\mathrm{I}} = 0.97 - 0.46 = \mathbf{0.51\ \text{nm}}$$

## 3. Change in breaking energy with Cl

$$\Delta E_{\mathrm{Cl}} = 1.5\ \text{eV} - 1.0\ \text{eV} = \mathbf{0.5\ \text{eV}}$$

## 4. Change in breaking energy with I

$$\Delta E_{\mathrm{I}} = 1.5\ \text{eV} - 0.5\ \text{eV} = \mathbf{1.0\ \text{eV}}$$

## 5. Average change in breaking energy per nm of plateau shortening — Cl

$$\left\langle\frac{\Delta E}{\Delta L}\right\rangle_{\mathrm{Cl}} = \frac{0.5\ \text{eV}}{0.38\ \text{nm}} = \mathbf{1.316\ \text{eV nm}^{-1}}$$

(Equivalently $1.316 \times 0.1602 = 0.211$ nN of equivalent force scale, and $1.316\ \text{eV nm}^{-1} \approx 127\ \text{kJ mol}^{-1}\text{nm}^{-1}$.)

## 6. Average change in breaking energy per nm of plateau shortening — I

$$\left\langle\frac{\Delta E}{\Delta L}\right\rangle_{\mathrm{I}} = \frac{1.0\ \text{eV}}{0.51\ \text{nm}} = \mathbf{1.961\ \text{eV nm}^{-1}}$$

Mean of the two halogen cases: $(1.316 + 1.961)/2 \approx 1.64\ \text{eV nm}^{-1}$ — i.e. **on average the breaking energy falls by roughly 1.6 eV for every nanometre of plateau-length reduction**, and the iodine case shows the steeper (≈1.5× larger) sensitivity, consistent with the larger, more polarisable, more strongly Au-interacting iodine perturbing the Au–S bond more effectively per unit of lost junction extension.

---

## 7. Force at the Au–S junction — no halogen

$$F_{\text{no halogen}} = \frac{E}{L} = \frac{1.5\ \text{eV}}{0.97\ \text{nm}} = 1.5464\ \text{eV nm}^{-1}$$
$$F_{\text{no halogen}} = 1.5464 \times 0.1602\ \text{nN} = \mathbf{0.2478\ \text{nN}}$$

## 8. Force at the Au–S junction — with Cl

$$F_{\mathrm{Cl}} = \frac{1.0\ \text{eV}}{0.59\ \text{nm}} = 1.6949\ \text{eV nm}^{-1}$$
$$F_{\mathrm{Cl}} = 1.6949 \times 0.1602\ \text{nN} = \mathbf{0.2718\ \text{nN}}$$

## 9. Force at the Au–S junction — with I

$$F_{\mathrm{I}} = \frac{0.5\ \text{eV}}{0.46\ \text{nm}} = 1.0870\ \text{eV nm}^{-1}$$
$$F_{\mathrm{I}} = 1.0870 \times 0.1602\ \text{nN} = \mathbf{0.1745\ \text{nN}}$$

## 10. Conversion factor used

All forces above were obtained from the energy-per-length slopes using

$$1\ \text{eV nm}^{-1} = 0.1602\ \text{nN}$$

---

## Summary of results

| Quantity | Cl | I |
|---|---|---|
| Plateau-length reduction $\Delta L$ | $0.97 - 0.59 = 0.38$ nm | $0.97 - 0.46 = 0.51$ nm |
| Breaking-energy reduction $\Delta E$ | $1.5 - 1.0 = 0.5$ eV | $1.5 - 0.5 = 1.0$ eV |
| Average $\Delta E/\Delta L$ | **1.316 eV nm$^{-1}$** | **1.961 eV nm$^{-1}$** |

| Case | $E$ (eV) | $L$ (nm) | $F = E/L$ (eV nm$^{-1}$) | $F$ (nN) |
|---|---|---|---|---|
| No halogen | 1.5 | 0.97 | 1.5464 | **0.2478** |
| With Cl | 1.0 | 0.59 | 1.6949 | **0.2718** |
| With I | 0.5 | 0.46 | 1.0870 | **0.1745** |

Interpretation: halogen interaction with the junction both shortens the plateau and lowers the Au–S breaking energy, with iodine (larger, softer, more polarisable, forming the stronger halogen/Au interaction) having about twice the energetic effect of chlorine. The *force* scale behaves non-monotonically: Cl coordination shortens the plateau proportionally more than it lowers the energy, so the mean rupture force is essentially unchanged or slightly higher (0.2718 vs 0.2478 nN), whereas with I the energy drops faster than the plateau shortens and the rupture force falls markedly to 0.1745 nN — i.e. iodine genuinely weakens the Au–S bond (≈30 % lower rupture force), while chlorine mainly changes *how far* the junction can be stretched before it breaks.
