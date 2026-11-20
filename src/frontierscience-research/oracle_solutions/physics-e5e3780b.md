# Fabrication of a high-efficiency p-on-n GaAs solar cell: methodology

## 1. Device concept and design of the n- and p-type GaAs layers

The cell is built in-house as a **p-on-n homojunction**. The n-type GaAs (substrate plus epitaxial base) is contacted from the rear. The p-type GaAs emitter is contacted from the front through a metal grid, and a window layer plus an anti-reflection coating (ARC) cover the illuminated area.

| Layer (top → bottom) | Material / dopant | Thickness | Doping (cm$^{-3}$) | Function |
|---|---|---|---|---|
| Contact cap | p$^+$-GaAs (Zn or C) | 200–300 nm | $\ge1\times10^{19}$ | low-resistance front ohmic contact; removed between fingers |
| Window | p-Al$_{0.8}$Ga$_{0.2}$As (or p-InGaP) | 30–40 nm | $\sim2\times10^{18}$ | front-surface passivation, transparent |
| **Emitter** | **p-GaAs** (Zn, Be or C) | 0.3–0.5 µm | $1$–$2\times10^{18}$ | junction formation, collects carriers generated at short $\lambda$ |
| **Base** | **n-GaAs** (Si or Te) | 2.5–3 µm | $1$–$2\times10^{17}$ | main absorber |
| BSF | n-Al$_{0.3}$Ga$_{0.7}$As or n-InGaP | 0.1 µm | $\sim1\times10^{18}$ | back-surface field, minority-hole reflector |
| Buffer | n$^+$-GaAs (Si) | 0.3 µm | $2\times10^{18}$ | clean growth start |
| **Substrate** | **n$^+$-GaAs (100)** wafer, Si-doped | 350 µm | $1$–$4\times10^{18}$ | mechanical support, rear contact |

**Design equations (why these thicknesses and dopings).**

* Absorption: the fraction of light absorbed in a thickness $d$ is $A=1-e^{-\alpha d}$. Near the band edge of GaAs ($E_g=1.42$ eV), $\alpha\approx1$–$2\times10^4\ {\rm cm^{-1}}$, so $d\approx3$ µm absorbs $\gtrsim95\%$ of the above-gap photons. This sets the **base thickness**.
* Collection: carriers must be generated within a diffusion length $L=\sqrt{D\tau}$ of the junction. For electrons in p-GaAs at $2\times10^{18}$, $L_n$ is a few µm. For holes in n-GaAs at $10^{17}$, $L_p$ is a few µm. A thin, moderately doped emitter (0.3–0.5 µm) plus a longer, lightly doped base is therefore optimal.
* Junction: the built-in voltage and the depletion width are
  $$V_{bi}=\frac{kT}{q}\ln\frac{N_AN_D}{n_i^2}\approx0.0259\ln\frac{(2\times10^{18})(10^{17})}{(2.1\times10^{6})^2}\approx1.35\ {\rm V},$$
  $$W=\sqrt{\frac{2\varepsilon_s V_{bi}}{q}\Big(\frac1{N_A}+\frac1{N_D}\Big)}\approx0.14\ {\rm µm}.$$
  The depletion region therefore lies almost entirely in the n-base.
* Output: $V_{oc}=\dfrac{kT}{q}\ln\!\Big(\dfrac{J_{sc}}{J_0}+1\Big)$. High crystalline quality (low $J_0$) and abrupt doping transitions are what make $V_{oc}\approx1.0$–$1.1$ V possible.

---

## 2. Fabrication sequence

For each step we give (a) the material deposited, removed or modified, (b) the method, with options, and (c) the reason for its position in the sequence.

### Step 0. Substrate preparation
* **(a)** n$^+$-GaAs (100) wafer, epi-ready, Si-doped $1$–$4\times10^{18}$ cm$^{-3}$. This is the **n-type GaAs** that later carries the rear contact.
* **(b)** Solvent degrease (acetone, isopropanol, DI water, N$_2$ dry), then in-situ thermal desorption of the native oxide in the growth reactor: about 580–620 °C under an As$_4$ flux in MBE, or about 700 °C under AsH$_3$ in MOCVD.
* **(c)** This comes first because every later layer is grown epitaxially on this surface. Contamination or residual oxide nucleates defects that lower the lifetime and the $V_{oc}$.

### Step 1. Epitaxial growth of the n-type GaAs base and p-type GaAs emitter (plus BSF, window, cap)
* **(a)** Deposited, in order: n$^+$-GaAs buffer, n-AlGaAs (or InGaP) BSF, **n-GaAs base (Si)**, **p-GaAs emitter (Zn/Be/C)**, p-AlGaAs window, p$^+$-GaAs cap.
* **(b) Method options:**
  1. **MOCVD (preferred for scalability):** TMGa or TEGa plus AsH$_3$ (or TBAs) at 650–750 °C, V/III ratio 30–100, growth rate 2–4 µm/h. n-type dopant: SiH$_4$/Si$_2$H$_6$ or DETe. p-type dopant: DEZn/DMZn, or CBr$_4$ for carbon (C diffuses less than Zn, which keeps the junction abrupt). TMAl for the AlGaAs layers.
  2. **MBE (best abruptness, research scale):** solid Ga, Al and As$_4$/As$_2$ (cracker) sources, 580–600 °C, about 1 µm/h. Si effusion cell for n-type, Be cell for p-type. RHEED provides in-situ growth monitoring.
  3. *Alternatives for forming the p-emitter on an n-GaAs base:* Zn diffusion (closed-ampoule ZnAs$_2$ or a spin-on Zn source, about 600–700 °C), or Be$^+$/Mg$^+$ ion implantation followed by rapid thermal annealing with a SiN$_x$ cap. Liquid-phase epitaxy is a historical option. These give less abrupt profiles and more damage than epitaxy.
* **(c)** The active n- and p-GaAs layers must be grown **before any processing**, in one uninterrupted run. This keeps the p–n interface oxide- and contamination-free and the doping transition abrupt. All later steps are low-temperature (≤ 450 °C), so they cannot redistribute the dopants of the junction once it exists. The n-layer is grown before the p-layer because the substrate is n-type and the rear contact is made to the n-side.

### Step 2. Native oxide etch of the wafer (first time)
* **(a)** Removed: the native Ga/As oxide (Ga$_2$O$_3$/As$_2$O$_3$, about 1–3 nm) that forms on both faces after the wafer leaves the reactor.
* **(b)** Wet etch in **HCl:DI water = 1:10** (by volume) for 30–60 s at room temperature, DI rinse, N$_2$ dry. *Options:* NH$_4$OH:DI = 1:10 (30 s), or very dilute HF:DI = 1:50 (avoid prolonged HF on Al-containing layers).
* **(c)** This is done immediately before the first metallization. Oxide at the metal/GaAs interface raises the specific contact resistivity and degrades adhesion. HCl removes the oxide without measurably etching GaAs.

### Step 3. Rear surface metallization of the n-type GaAs wafer
* **(a)** Deposited: n-type ohmic contact over the whole rear face of the **n-type GaAs** substrate, e.g. AuGe (88:12) 100 nm / Ni 30 nm / Au 200 nm. *Alternatives:* Pd/Ge/Au, or Ni/AuGe/Ni/Au.
* **(b)** **Thermal (resistive) evaporation or e-beam deposition** at base pressure below $10^{-6}$ Torr, with the wafer face-down and the front protected by a spin-coated sacrificial resist layer. Then remove the protective resist in acetone and alloy by rapid thermal annealing at 380–420 °C for 30–60 s in N$_2$ or forming gas. Ge dopes the interface n$^{++}$, which gives a tunnelling ohmic contact.
* **(c)** The rear contact comes first among the contacts because it needs the **highest alloying temperature**. Done later, that anneal would make the front Au spike through the thin emitter and window and would damage the ARC. A full-area contact needs no lithography, and the unpatterned front can be safely protected while the wafer lies face-down.

### Step 4. Front surface contact lithography (grid finger mask design)
* **(a)** Modified: a lift-off stencil in photoresist that opens the **grid fingers and busbar** on the p$^+$-GaAs cap. A typical design uses fingers 5–10 µm wide at 100–300 µm pitch, giving 2–5 % shadowing, chosen by balancing shadow loss against the series resistance of the emitter and fingers.
* **(b) Method options.** All of them must give an **undercut (re-entrant) resist profile** for clean lift-off.
  * **Option 1: negative resist (e.g. NR9-1500PY).** Spin at 3000 rpm for 40 s (about 1.5 µm), **soft bake** 150 °C for 60 s (hotplate), **exposure** with the finger mask (i-line, about 200–300 mJ cm$^{-2}$), **post-exposure bake (PEB)** 100 °C for 60 s, **develop** in RD6 for about 10–15 s, DI rinse. The negative tone naturally gives a negative sidewall slope.
  * **Option 2: image-reversal resist (e.g. AZ 5214E).** Spin at 4000 rpm for 30 s (about 1.4 µm), **soft bake** 95–100 °C for 60 s, **exposure** through the mask at low dose (about 30–40 mJ cm$^{-2}$), **PEB / reversal bake** 115–120 °C for 60–120 s (this cross-links the exposed areas), **flood exposure** with no mask (about 200 mJ cm$^{-2}$), **develop** in AZ 726 MIF (or AZ 400K 1:4) for 40–60 s. The resist ends up in negative tone with an undercut.
  * **Option 3: positive resist with chlorobenzene soak (e.g. AZ 1518 / S1813).** Spin at 4000 rpm (about 1.3–1.8 µm), **soft bake** 90–100 °C for 60 s, **exposure** with a dark-field finger mask, **chlorobenzene soak** for 5–15 min followed by an N$_2$ dry, then **develop** (MF-319 or AZ 726 MIF). The soak hardens the top skin of the resist so it develops more slowly than the bulk, which forms an overhanging lip. The chlorobenzene soak can also be done before exposure. Work in a fume hood.
  * **Option 4: positive resist plus LOR bilayer.** **LOR spin** (LOR 3A/5A, 3000–4000 rpm, about 0.3–0.5 µm; thickness at least about 1.3× the metal thickness), **soft bake** 170–190 °C for 3–5 min (the bake temperature sets the undercut rate), **PR spin** (S1813, 4000 rpm, about 1.3 µm), **soft bake** 115 °C for 60 s, **exposure**, **develop** in MF-319 for 60–90 s. The developer patterns the PR and isotropically undercuts the LOR by about 0.5–1 µm.
  * In all options, finish with a short O$_2$-plasma descum (about 30 s) to remove resist scum from the openings.
* **(c)** The front grid is defined **after** the rear contact anneal (see Step 3), and **before** the mesa and ARC, while the front surface is still planar. A planar surface gives uniform resist thickness and the best resolution for narrow fingers, and the grid must be aligned first because the mesa and ARC masks are aligned to it.

### Step 5. Metal deposition for the p-type GaAs contact
* **(a)** Deposited: **Ti/Au** (e.g. Ti 20–50 nm / Au 500–1000 nm) **or Cr/Au** (Cr 20 nm / Au 500 nm), or Ti/Pt/Au with Pt as a diffusion barrier, on the p$^+$-GaAs cap that sits on the **p-type GaAs** emitter.
* **(b)** **Thermal evaporation or e-beam deposition.** Both are directional line-of-sight processes, which is essential so that the sidewalls stay uncoated for lift-off. Use a base pressure below $10^{-6}$ Torr, about 1 Å/s for Ti/Cr and 2–5 Å/s for Au. Then **lift-off** in acetone or NMP-based remover (Remover PG / 1165 at 60–80 °C, mild ultrasonic agitation), followed by IPA, DI and N$_2$. Ti (or Cr) is the adhesion layer and also getters any thin regrown oxide. On p$^+\ge10^{19}$ cm$^{-3}$ the contact is ohmic as deposited; an optional sinter at 350–400 °C for 30 s lowers $\rho_c$ further, to below $10^{-5}\ \Omega$ cm$^2$.
* **(c)** It follows the front lithography directly so the stencil is used while it is fresh. It precedes the mesa, the cap removal and the ARC because the fingers then act as a **self-aligned etch mask** for removing the p$^+$ cap, and the ARC must be deposited last over the finished surface.

### Step 6. Native oxide etch of the wafer: HCl:DI, 1:10 (second time, after the rear and front contact formation)
* **(a)** Removed: the native oxide regrown during the contact steps and anneals, together with lift-off residues.
* **(b)** **HCl:DI = 1:10**, 30–60 s at room temperature, DI rinse, N$_2$ dry. Au is not attacked, and the Ti/Cr adhesion layer is protected under the Au. *Option:* NH$_4$OH:DI = 1:10.
* **(c)** This is repeated **after the rear and front contacts are complete** and before the mesa/cap etch and the ARC. An oxide-free surface makes the wet mesa etch start uniformly, with no "induction time" or micromasking, gives reproducible etch depths, and gives a clean, low-recombination interface and good adhesion for the ARC.

### Step 7. Mesa lithography
* **(a)** Modified: a positive-resist etch mask defining each cell's active area (e.g. 0.25–1 cm$^2$ squares), with the busbar inside the mesa.
* **(b)** Positive resist (S1813 or AZ 1518 / AZ 4533 for deeper etches): spin, soft bake (about 100 °C, 60 s), exposure through the mesa mask **aligned to the front grid**, develop (MF-319 / AZ 726 MIF), then a **hard bake** at 110–120 °C for 2–5 min to improve adhesion and wet-etch resistance. The resist also covers and protects the grid metal.
* **(c)** It follows the contact steps because it is aligned to the grid, and it precedes the ARC so that the ARC also covers the mesa edges.

### Step 8. Mesa etching
* **(a)** Removed: the p$^+$ cap, window, **p-GaAs emitter**, junction, and part or all of the **n-GaAs base** outside the mesa. The etch depth is at least about 1 µm beyond the junction, or down to the n$^+$ buffer/substrate (about 3.5–4 µm) for full isolation.
* **(b) Method options:**
  1. **Wet etch:** H$_3$PO$_4$:H$_2$O$_2$:H$_2$O = 3:1:50 (about 0.1 µm/min, smooth and well controlled) or 1:1:10 (faster), or H$_2$SO$_4$:H$_2$O$_2$:H$_2$O = 1:8:80 (about 1 µm/min). Check the depth with a profilometer.
  2. **Dry etch:** ICP-RIE in BCl$_3$/Cl$_2$/Ar (or SiCl$_4$) with laser-interferometric endpoint detection. This gives vertical sidewalls but sidewall damage, which needs a short wet clean afterwards.

  Then strip the resist (acetone/NMP, O$_2$ descum).
* **(c)** Etching through the junction electrically isolates each cell and defines its area accurately, which is needed for a correct $J_{sc}$. It also removes the damaged and shunting edge regions. It is done after the metallization, so the contacts are already in place, and before the ARC, so the ARC can also coat and passivate the exposed sidewalls.

### Step 9. Removal of the p$^+$-GaAs contact cap between the fingers (self-aligned)
* **(a)** Removed: p$^+$-GaAs cap in the optically active area. The cap remains only under the metal.
* **(b)** Selective wet etch in citric acid (50 wt%):H$_2$O$_2$ = 4:1 (GaAs:Al$_{0.8}$Ga$_{0.2}$As selectivity > 100), which stops on the window, using the grid metal as the mask. *Option:* NH$_4$OH:H$_2$O$_2$ (pH-adjusted) selective etch.
* **(c)** The heavily doped cap absorbs strongly and has a short lifetime. It is needed only under the metal and must be removed before the ARC is deposited.

### Step 10. ARC lithography (final step 1 of 2)
* **(a)** Modified: a resist pattern that **covers the busbar/probe pads** (and the dicing streets), so the ARC can later be removed there and the pads stay contactable.
* **(b) Options:**
  1. **Lift-off route (ARC deposited afterwards):** use any of the undercut stencils of Step 4, e.g. AZ 5214E image reversal, NR9 negative resist, or LOR + S1813, with the inverse (pad) mask aligned to the grid. The steps are spin, soft bake, exposure, (PEB/flood), develop and O$_2$ descum.
  2. **Etch-back route (ARC deposited first):** deposit the ARC as a blanket layer, then spin a positive resist, expose the pad windows, develop, hard bake, and open the pads by etching the ARC (buffered HF for SiN$_x$/SiO$_2$/Al$_2$O$_3$, or CF$_4$/CHF$_3$ RIE), then strip the resist. This route is required for conformal ARCs (PECVD, ALD) that do not lift off.
* **(c)** This is done last, after all etching, because the ARC must be the final optical layer over the finished window surface, while the pads must remain bare for probing and wire bonding.

### Step 11. ARC deposition (final step 2 of 2)
* **(a)** Deposited: double-layer ARC, e.g. **ZnS (≈60 nm)/MgF$_2$ (≈100 nm)**. *Alternatives:* TiO$_2$/SiO$_2$, Ta$_2$O$_5$/SiO$_2$, TiO$_2$/Al$_2$O$_3$, or single-layer SiN$_x$ (≈75 nm).
* **(b) Method options:** **e-beam evaporation** (TiO$_2$, Ta$_2$O$_5$, SiO$_2$, Al$_2$O$_3$), **thermal evaporation** (ZnS, MgF$_2$), **PECVD** (SiN$_x$, SiO$_2$; at about 300 °C it also passivates), **ALD** (Al$_2$O$_3$/TiO$_2$; conformal, with excellent thickness control), or sputtering. With the lift-off route, follow with lift-off in acetone/NMP. Thicknesses follow the quarter-wave condition at the design wavelength $\lambda_0\approx600$ nm:
  $$d_i=\frac{\lambda_0}{4n_i}\;\Rightarrow\; d_{\rm MgF_2}=\frac{600}{4(1.38)}\approx109\ {\rm nm},\quad d_{\rm ZnS}=\frac{600}{4(2.35)}\approx64\ {\rm nm}.$$
  For a single layer, the reflectance at $\lambda_0$ is $R=\big(\tfrac{n_0n_s-n_1^2}{n_0n_s+n_1^2}\big)^2$, which vanishes for $n_1=\sqrt{n_0n_s}$. A double layer broadens the low-$R$ band, reducing the solar-weighted reflectance from about 30–35 % (bare GaAs) to below 3 %.
* **(c)** The ARC is the **final** layer. It is fragile and optically critical, and any later wet processing or high-temperature step would damage or shift it. Its thickness is designed for the finished surface stack (window plus ARC).

### Step 12. Finishing and characterization
Dicing or cleaving along the mesa streets. Characterization: dark and illuminated $J$–$V$ under AM1.5G (1000 W m$^{-2}$) giving $J_{sc}$, $V_{oc}$, FF and $\eta$; external quantum efficiency (EQE) and reflectance; transfer-length-method (TLM) structures on the same wafer to measure the contact resistivity of the n- and p-contacts.

---

## 3. Summary of the sequence

- Step 0: Substrate preparation (n$^+$-GaAs wafer)
- Step 1: Epitaxy of the n-GaAs base and p-GaAs emitter (plus BSF, window, cap) by MOCVD or MBE (alternatives: Zn diffusion or implantation for the emitter)
- Step 2: **Native oxide etch of the wafer, HCl:DI 1:10**
- Step 3: **Rear surface metallization of the n-type GaAs wafer** (AuGe/Ni/Au) by **thermal evaporation or e-beam deposition**, then alloy anneal
- Step 4: **Front surface contact lithography (grid finger mask design)**: Option 1 NR9 negative resist; Option 2 AZ image-reversal resist; Option 3 positive resist with chlorobenzene soak; Option 4 LOR plus positive resist
- Step 5: **Metal deposition for the p-type GaAs contact: Ti/Au or Cr/Au, by thermal evaporation or e-beam deposition**, then lift-off
- Step 6: **Native oxide etch of the wafer, HCl:DI 1:10 (second time, after rear and front contact formation)**
- Step 7: **Mesa lithography**
- Step 8: **Mesa etching** (wet H$_3$PO$_4$- or H$_2$SO$_4$-based, or ICP-RIE)
- Step 9: Selective removal of the p$^+$ cap between the fingers
- Step 10: **ARC lithography**
- Step 11: **ARC deposition** (e-beam or thermal evaporation, PECVD, ALD), then lift-off
- Step 12: Dicing and characterization

The ordering follows three rules. (i) Junction-forming epitaxy comes first and is never followed by any step hot enough to move the dopants. (ii) Process steps go from the highest to the lowest thermal budget: n-contact alloy, then p-contact, then ARC. (iii) Masks that need alignment and planarity come before deep etches and fragile optical coatings.
