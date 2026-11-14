# Why iron incorporation helps Ni for OER but hurts it for ethanol oxidation

## 1. The two reactions are not run by the same sites, and not by the same kind of chemistry

### 1.1 Structural picture of the working catalyst

Under alkaline anodic conditions a nickel-based catalyst converts to a layered nickel (oxy)hydroxide, cycling through the Bode scheme $\beta$-Ni(OH)$_2 \rightleftharpoons \beta$-NiOOH and $\alpha$-Ni(OH)$_2 \rightleftharpoons \gamma$-NiOOH. Such a layered material offers two chemically distinct populations of nickel:

- **Basal-plane / "bulk" sites.** Ni$^{2+}$ in the interior of the brucite-like sheets, six-coordinate and fully saturated by $\mu_3$-OH/O bridges. These nickels are coordinatively *complete*: they cannot bind an adsorbate, but they can and do change oxidation state (the whole sheet is redox-active, and protons/electrons move in and out of it). This is the population that carries the **Ni$^{2+}$/Ni$^{3+}$ solid-state redox capacity** that is measured as the large, reversible anodic/cathodic wave before the OER onset.
- **Edge, step, corner, vacancy and grain-boundary / "defect" sites.** Here Ni is **coordinatively unsaturated** (4- or 5-coordinate), has dangling OH/H$_2$O ligands, is more easily oxidised beyond Ni$^{3+}$, and has neighbours at a geometry that can host two adjacent oxygenic adsorbates. These are the sites at which *adsorbate-based* electrocatalysis happens.

### 1.2 OER requires edge/defect sites — coordination and mechanistic reasons

OER is an **inner-sphere, four-electron/four-proton adsorbate reaction**:

$$4\,\mathrm{OH^-} \rightarrow \mathrm{O_2} + 2\,\mathrm{H_2O} + 4e^-$$

via the conventional adsorbate-evolution sequence on a metal site M:

$$\mathrm{M} + \mathrm{OH^-} \rightarrow \mathrm{M\text{–}OH} + e^- \;\rightarrow\; \mathrm{M\text{=}O} + \mathrm{H_2O} + e^- \;\rightarrow\; \mathrm{M\text{–}OOH} + e^- \;\rightarrow\; \mathrm{M} + \mathrm{O_2} + e^-$$

(or, on highly covalent lattices, the lattice-oxygen/oxide path with direct O–O coupling between two adjacent oxo/oxyl ligands).

Three features of this mechanism dictate *where* it can occur:

1. **It involves multiple sequential electron transfers** — four electrons and four proton transfers through at least three bound intermediates (\*OH, \*O, \*OOH). The site must therefore survive several oxidation-state changes (Ni$^{3+}\rightarrow$Ni$^{4+}$/oxyl character) while holding an adsorbate.
2. **It requires specific coordination geometries.** An open coordination position is mandatory simply to bind \*OH; a fully saturated basal-plane Ni$^{2+}$ has none. Moreover, O–O coupling needs either a single site able to accommodate the bent, sterically demanding \*OOH with the right M–O–O angle, or — in the oxide path — **two adjacent oxygen-bearing metal centres at ~2.5–3 Å with the correct relative orientation**. Edges, steps and vacancy-adjacent sites supply exactly this: unsaturated coordination plus a neighbour at bonding distance; basal-plane terraces do not.
3. **O–O bond formation is the rate-determining step.** Both the \*O $\rightarrow$ \*OOH step (nucleophilic attack of OH$^-$ on the electrophilic oxo) and the direct radical coupling of two oxyls are the highest-barrier events, and they are the steps that fix the $\sim$0.3–0.4 V intrinsic overpotential through the universal scaling relation $\Delta G_{\mathrm{*OOH}} \approx \Delta G_{\mathrm{*OH}} + 3.2\ \mathrm{eV}$. Because the RDS is a *bond-forming* step between two oxygen atoms, it is extraordinarily sensitive to the electrophilicity of the oxo (i.e. the metal's ability to reach a high formal valence and to delocalise charge) and to the local geometry — again, properties of undercoordinated edge/defect sites, not of saturated bulk sites.

**Conclusion:** **OER occurs preferentially at edge and defect sites**, because it demands open coordination, a high accessible valence state, adjacent sites for O–O coupling, and the capacity for multiple electron transfers at one locus.

### 1.3 EOR runs on bulk Ni$^{3+}$ by an indirect, mediated mechanism

Alcohol oxidation on nickel in alkali is *not* an adsorbate-based inner-sphere process of the OER type. It is the classical **three-step indirect (redox-mediated) mechanism**, in which the nickel oxyhydroxide behaves as a regenerable chemical oxidant:

**Step 1 — electrochemical oxidation of Ni$^{2+}$ to Ni$^{3+}$:**
$$\mathrm{Ni(OH)_2} + \mathrm{OH^-} \rightarrow \mathrm{NiOOH} + \mathrm{H_2O} + e^- \qquad (\mathrm{Ni^{2+}} \rightarrow \mathrm{Ni^{3+}},\ E^{\circ}\approx 1.35\ \mathrm{V\ vs\ RHE})$$

The electrode is first charged: protons leave the hydroxide sheet and electrons go to the current collector, converting the material into Ni$^{3+}$–OOH. This is a **solid-state, bulk** transformation that proceeds throughout the sheets, not only at the surface.

**Step 2 — chemical oxidation of ethanol by Ni$^{3+}$, with reduction of nickel back to Ni$^{2+}$:**
$$\mathrm{NiOOH} + \mathrm{CH_3CH_2OH} \rightarrow \mathrm{Ni(OH)_2} + \mathrm{CH_3CHO}\ (\rightarrow \mathrm{CH_3COO^-})$$

This step is a **chemical (non-electrochemical) hydrogen-atom/hydride abstraction** from the $\alpha$-C–H of the adsorbed/contacting alcohol by the Ni$^{3+}$–O(H) centre, giving the aldehyde (and, after further oxidation of the hemiacetal/gem-diol, acetate as the main product); the nickel is **reduced back to Ni$^{2+}$** in the process. Overall: $\mathrm{CH_3CH_2OH} + 5\mathrm{OH^-} \rightarrow \mathrm{CH_3COO^-} + 4\mathrm{H_2O} + 4e^-$, with the electrons delivered to the electrode only *through* the nickel redox couple.

**Step 3 — re-oxidation of Ni$^{2+}$ back to Ni$^{3+}$:**
$$\mathrm{Ni(OH)_2} + \mathrm{OH^-} \rightarrow \mathrm{NiOOH} + \mathrm{H_2O} + e^-$$

The reduced nickel is immediately re-oxidised electrochemically, closing the catalytic loop. The measured faradaic current is therefore the rate of **Ni$^{2+}$/Ni$^{3+}$ redox cycling** (mediator turnover), and the steady-state rate obeys

$$j_{\mathrm{EOR}} \propto k_{\mathrm{chem}}\,\theta_{\mathrm{Ni^{3+}}}\,[\mathrm{EtOH}],\qquad \theta_{\mathrm{Ni^{3+}}} = \frac{1}{1+\exp\!\left[\tfrac{F}{RT}\left(E^{\circ}_{\mathrm{Ni^{2+}/Ni^{3+}}}-E\right)\right]}$$

i.e. **EOR current is proportional to the amount of accessible Ni$^{3+}$ at the working potential and to the rate of its chemical reduction by ethanol.**

Consequences for site requirements, in direct contrast with OER:
- the reaction needs **no open coordination site and no adjacent-site geometry** — outer-sphere/contact hydride abstraction by a Ni$^{3+}$–O centre works on the basal plane;
- it needs **no high valence beyond Ni$^{3+}$** and no multi-electron accumulation at one atom: each nickel supplies one electron per turnover;
- it needs **a large population of redox-cyclable nickel**, which is precisely the bulk/basal-plane Ni$^{2+}$/Ni$^{3+}$ reservoir, and it needs that nickel to be oxidisable at a potential *below* the OER onset.

**Conclusion:** **EOR is carried by bulk (basal-plane, lattice) nickel sites** acting as a Ni$^{2+}$/Ni$^{3+}$ redox mediator, whereas **OER is carried by edge/defect sites** acting as adsorbate-binding, multi-electron, O–O-coupling centres. This site separation is the foundation of everything that follows.

---

## 2. Where iron goes, and what it does electronically

### 2.1 Site preference for iron incorporation: trace vs extensive

Iron incorporation is itself site-selective, and the selectivity is concentration-dependent:

- **Trace iron preferentially occupies edge, step, corner and vacancy (defect) sites.** These sites are thermodynamically the most favourable for substitution: they are high-energy, coordinatively unsaturated positions where the lattice strain penalty for accommodating the larger, harder, more Lewis-acidic Fe$^{3+}$ ion is smallest and where a trivalent cation can be charge-compensated most easily by terminal OH$^-$/O$^{2-}$ ligands. Kinetically, it is also these sites that are exposed to the electrolyte, so adventitious Fe (even sub-ppm Fe in KOH) adsorbs and incorporates there first; defect/edge incorporation is the **first-filled** population. Simple site-energy arguments give $\Delta G_{\mathrm{sub}}^{\mathrm{edge}} < \Delta G_{\mathrm{sub}}^{\mathrm{bulk}}$, so at low Fe loading the defect population is decorated while the basal planes remain essentially pure Ni.
- **Extensive (higher) iron content forces substitution into bulk lattice Ni positions.** Once the limited number of edge/defect sites is saturated, additional Fe must substitute for Ni$^{2+}$ in the interior of the sheets (Fe$^{3+}$ and Ni$^{2+}$ have similar radii, 0.645 vs 0.690 Å, so solid solutions Ni$_{1-x}$Fe$_x$(OH)$_2$ form readily up to $x \approx 0.25$–0.4 before phase segregation to FeOOH). Now iron is distributed **throughout** the redox-active sheets, in direct electronic contact with the bulk Ni that EOR depends on.

### 2.2 Electronic consequences, from the d-electron configurations

The key electronic fact is the **different d-electron configuration of Fe$^{3+}$ (d$^5$) versus Ni$^{3+}$ (d$^7$)**, and the different configuration of Ni$^{2+}$ (d$^8$):

- **Fe$^{3+}$ is high-spin d$^5$**, $t_{2g}^3 e_g^2$, a **half-filled shell** with zero ligand-field stabilisation but maximal exchange stabilisation (large spin-pairing/exchange energy, spherically symmetric charge density, no Jahn–Teller distortion). This makes Fe$^{3+}$ an unusually *stable* oxidation state: oxidising it further to Fe$^{4+}$ is expensive in a hydroxide lattice, and reducing it to Fe$^{2+}$ in an alkaline oxyhydroxide is also unfavourable. **Fe$^{3+}$ is therefore a redox-inert spectator over the potential window where Ni cycles**, yet it is a strong Lewis acid with high charge density.
- **Ni$^{3+}$ is low-spin d$^7$** ($t_{2g}^6 e_g^1$) — a Jahn–Teller-active, single-$e_g$-electron configuration whose $e_g$ occupancy near unity is exactly the descriptor associated with optimal oxygen-intermediate binding, and which is easily oxidised further towards Ni$^{4+}$ (d$^6$) at edge sites. Ni$^{2+}$ is d$^8$ ($t_{2g}^6e_g^2$), the state that must be regenerated in the EOR cycle.
- **Mixed Ni–O–Fe sites are electronically distinct from either pure oxide.** Because Fe$^{3+}$ (d$^5$) has a different $e_g$/$t_{2g}$ filling, a different $d$-level energy and a much higher effective nuclear charge than Ni$^{3+}$ (d$^7$), substituting Fe into the sheet:
  - **alters the d-band structure and the Ni 3d–O 2p hybridisation at the mixed-metal sites.** Fe$^{3+}$ withdraws electron density through the bridging oxygens (inductive/Lewis-acid effect), lowering the Ni $e_g$ level, increasing **M–O covalency** and shifting the O 2p band towards the Fe$^{3+}$/Fe$^{4+}$ and Ni$^{3+}$/Ni$^{4+}$ levels. Pure Ni oxyhydroxide has relatively ionic, "hard" Ni–O bonds and binds \*O/\*OOH too strongly at the Ni$^{3+/4+}$ centre; in the Fe-containing lattice the Ni–O bond is more covalent and shorter, and the Fe–O bond is shorter and more covalent still, which **weakens/optimises the binding of oxygenic intermediates** and brings $\Delta G_{\mathrm{*O}}-\Delta G_{\mathrm{*OH}}$ nearer the ideal 1.6 eV;
  - **raises the effective potential required to oxidise nickel.** An adjacent, hard, redox-inert Fe$^{3+}$ (d$^5$) stabilises the lower-valent Ni$^{2+}$ (d$^8$) state by withdrawing charge from Ni and by suppressing the cooperative, sheet-wide deprotonation that accompanies Ni$^{2+}\rightarrow$Ni$^{3+}$; the measurable result is the well-known **anodic (positive) shift of the Ni$^{2+}$/Ni$^{3+}$ redox wave in Fe-containing layered hydroxides**, together with a decrease in its charge (fewer nickels oxidised per potential window);
  - **increases electronic conductivity**: substitutional Fe introduces states in the gap of the poorly conducting Ni(OH)$_2$ (p-type doping, Fe$^{3+}$/Ni$^{2+}$ charge-transfer and Ni$^{3+}$ hole states), narrowing the band gap and improving charge transport through the film.

---

## 3. Putting the pieces together: the three catalyst regimes

### 3.1 How trace iron enhances OER — three mechanisms

1. **Electronic modification that optimises oxygen-intermediate binding.** At the edge/defect sites where trace Fe sits, the Fe$^{3+}$ (d$^5$) centre polarises the bridging oxygens and modifies the Ni $e_g$/O 2p manifold, raising the covalency of the M–O bond and tuning $\Delta G_{\mathrm{*OH}}$, $\Delta G_{\mathrm{*O}}$ and $\Delta G_{\mathrm{*OOH}}$ away from the too-strong-binding regime of pure NiOOH. Because the RDS is O–O bond formation, the resulting partial decoupling of \*OOH from \*OH energetics (and the greater electrophilicity/oxyl character of the oxygen bound to a high-valent centre adjacent to Fe) lowers the O–O coupling barrier directly, cutting the overpotential by the observed 50–100 mV. Equivalently, Fe acts as the Lewis-acidic, electron-withdrawing partner that makes the Ni centre reach a more oxidised, more electrophilic state (nominal Ni$^{3.6+}$–Ni$^{4+}$/oxyl) at a given potential.
2. **Creation of genuinely new, favourably coordinated Ni–Fe active sites.** Trace Fe at an edge creates **Ni–O–Fe pairs** in which Fe$^{3+}$ provides the oxo-binding, strongly Lewis-acidic site and the neighbouring Ni provides the redox/hole reservoir and the second oxygen for coupling. These bimetallic edge motifs have a coordination environment (unsaturated, with two adjacent metal–oxygen units at the right distance and the right M–O–M angle) that neither pure NiOOH edges nor pure FeOOH provides, and they relieve the single-site scaling-relation constraint by distributing \*O and \*OOH over two different metals — a bifunctional O–O coupling path. This is why OER enhancement saturates at low Fe content: it tracks the **limited number of edge/defect positions**.
3. **Enhanced conductivity and charge transfer.** Fe doping narrows the band gap of the insulating Ni(OH)$_2$/NiOOH, increases hole mobility in the sheets, and lowers the film resistance and the charge-transfer resistance (smaller $R_{\mathrm{ct}}$ in EIS). Since OER demands **four sequential electron transfers** from one site, with the electrode having to deliver/accept charge at a high rate at high overpotential, improved conductivity translates directly into higher current at a given potential and reduces iR/transport-limited losses in thick films.

### 3.2 Why trace iron barely affects EOR — site-specific reasoning

Because **trace iron is consumed by the edge and defect sites**, it leaves the basal-plane/bulk nickel population essentially untouched. EOR, by the three-step indirect mechanism of §1.3, is carried by exactly that untouched population: the bulk Ni$^{2+}$/Ni$^{3+}$ reservoir which generates NiOOH, oxidises ethanol chemically, and is re-oxidised. Specifically:

- the **number of bulk Ni$^{3+}$ sites** available at the working potential is unchanged, because no Fe has entered the sheets' interior;
- the **Ni$^{2+}$/Ni$^{3+}$ redox potential of the bulk** is unchanged, because the electronic perturbation from Fe is short-ranged (first/second coordination shell through Ni–O–Fe bridges) and a few per cent of Fe confined to edges perturbs only the few per cent of nickels adjacent to the edges;
- the chemical step (Step 2) is an outer-sphere-like hydride/H-atom abstraction by Ni$^{3+}$–O that needs no special geometry, so blocking or modifying a small number of edge sites does not remove it.

Hence the EOR voltammetric wave, its onset and its peak current are essentially identical for pure Ni and trace-Fe Ni: **trace iron is "invisible" to EOR because it is not located where EOR happens.**

### 3.3 Why high iron content suppresses EOR — three mechanisms

Once Fe is forced into bulk lattice positions, every one of the requirements of the indirect mechanism is attacked:

1. **Redox-potential shift reducing Ni$^{3+}$ availability.** Bulk Fe$^{3+}$ (d$^5$), being hard, redox-inert and electron-withdrawing, stabilises Ni$^{2+}$ (d$^8$) and raises $E^{\circ}_{\mathrm{Ni^{2+}/Ni^{3+}}}$ (anodic shift of the Ni redox wave, commonly 50–150 mV, growing with Fe content). From the Nernst-type expression in §1.3, a positive shift $\Delta E^{\circ}$ multiplies $\theta_{\mathrm{Ni^{3+}}}$ — and hence $j_{\mathrm{EOR}}$ — by $\exp(-F\Delta E^{\circ}/RT)$ in the pre-wave region: at 100 mV shift, roughly a 50-fold loss of Ni$^{3+}$ coverage at a fixed EOR potential. Worse, the Ni$^{2+}\rightarrow$Ni$^{3+}$ oxidation is pushed **into or beyond the OER onset**, so the mediator is only generated where OER competes for the same potential window.
2. **Site competition / dilution of the active nickel density.** Each substituted Fe$^{3+}$ removes one Ni from the sheet. Since EOR current scales with the *number* of redox-cyclable Ni centres (it is a mediator-stoichiometric reaction, not a surface-area-limited adsorbate reaction), replacing 20–40 % of the Ni by Fe removes 20–40 % of the mediator inventory outright, and the integrated Ni$^{2+}$/Ni$^{3+}$ redox charge falls accordingly. Fe$^{3+}$ itself cannot substitute functionally, because Fe$^{3+}$/Fe$^{4+}$ is not accessible at these potentials and Fe$^{3+}$ is not a competent hydride abstractor for the $\alpha$-C–H of ethanol — it is a spectator in Step 2. Iron may additionally occupy or block the surface positions at which ethanol/ethoxide adsorbs, and surface Fe–O sites bind OH$^-$/oxygen intermediates strongly, further reducing the ethanol-accessible Ni fraction.
3. **Electronic modification that impairs nickel's ability to redox-cycle.** Beyond the thermodynamic shift, Fe changes the *kinetics and reversibility* of the Ni$^{2+}\leftrightarrow$Ni$^{3+}$ shuttle on which the mechanism depends. Increased Fe–O/Ni–O covalency and charge delocalisation across Ni–O–Fe bridges localise holes on oxygen rather than on nickel, stabilise the $\gamma$-NiOOH-like, highly oxidised, proton-poor phase and hinder the **reduction back to Ni$^{2+}$** required in Step 2 (the chemical step is precisely a reduction of the nickel). Fe$^{3+}$ also suppresses the cooperative proton/vacancy transport in the sheets that makes the bulk redox reaction fast and reversible, broadening and attenuating the redox wave (larger peak separation, lower peak charge). A nickel that cannot be reduced by ethanol — or cannot be re-oxidised quickly afterwards — cannot mediate EOR, even if it is formally present.

### 3.4 Selectivity and competition for the three catalyst types

OER and EOR compete for the same potential window, the same electrode charge and, when they share sites, for the same nickel. The site-specific picture predicts three distinct competition patterns:

- **Pure Ni.** Both reactions depend on the same Ni$^{2+}$/Ni$^{3+}$ chemistry, but EOR has the kinetic advantage: it turns over as soon as Ni$^{3+}$ appears (onset at/just above the Ni redox wave, ~1.35 V) and it consumes Ni$^{3+}$ chemically, keeping the surface in a partially reduced state. OER, which needs the *more* oxidised edge sites (Ni$^{3+}\rightarrow$Ni$^{4+}$/oxyl) and a high overpotential, is therefore actively **suppressed while ethanol is present**: the ethanol scavenges the Ni$^{3+}$ holes before they can be driven to the high-valent state needed for O–O coupling, and edge sites are relatively few. Selectivity: good EOR (high faradaic efficiency to acetate), modest OER; the catalyst is a decent alcohol-oxidation catalyst and a mediocre OER catalyst.
- **Trace-Fe Ni.** The two reactions are now run by **two spatially and chemically separated populations**: OER at Fe-decorated edge/defect sites, EOR at the unmodified bulk Ni$^{2+}$/Ni$^{3+}$ reservoir. Because trace Fe neither shifts the bulk Ni redox potential nor removes bulk Ni, **the two processes can proceed simultaneously with minimal interference**: OER activity rises (new, better edge sites plus better conductivity) while EOR activity is essentially that of pure Ni. This is the regime of "enhanced OER, unaffected EOR". The only interaction is the shared potential axis and shared electron flow, which is why the *selectivity* between the two begins to tilt towards O$_2$ even though the EOR rate itself is unchanged.
- **High-Fe content.** OER is now enhanced over the whole surface (Fe in bulk and edge positions, maximal electronic optimisation and conductivity — the classical NiFe-LDH OER catalyst), while EOR is suppressed by all three mechanisms of §3.3. Competition becomes strongly asymmetric: the Ni$^{3+}$ mediator appears only at potentials where the Fe-optimised OER sites are already turning over fast, so the current is diverted almost entirely to O$_2$ evolution, the faradaic efficiency for ethanol products collapses, and the catalyst behaves as a selective OER catalyst even in the presence of ethanol. Hence the design rule: **trace Fe (or deliberate Fe at edges only) for a bifunctional/alcohol-oxidation catalyst; high Fe for a dedicated OER catalyst; strict Fe exclusion (purified KOH) if one wants EOR selectivity without parasitic O$_2$.**

---

## 4. Unified explanation

The apparently contradictory effects of iron dissolve once three things are recognised simultaneously — *where* iron goes, *what* each reaction mechanistically needs, and *how* Fe$^{3+}$ (d$^5$) differs electronically from Ni$^{3+}$ (d$^7$):

1. **Site specificity of iron incorporation.** Trace iron likely occupies defect and edge sites preferentially (lowest substitution energy, direct electrolyte exposure); only when those are saturated does extensive iron enter bulk lattice Ni positions.
2. **Site and mechanism requirements of the two reactions.** OER is an adsorbate-based, multi-electron (4e⁻) reaction with O–O bond formation as the rate-determining step; it therefore requires coordinatively unsaturated, geometrically specific, high-valence-capable **edge/defect** sites. EOR runs by the three-step indirect mechanism — electrochemical Ni$^{2+}\rightarrow$Ni$^{3+}$, chemical ethanol oxidation by Ni$^{3+}$ with reduction to Ni$^{2+}$, then re-oxidation — and therefore requires a large, easily and reversibly cycled **bulk** Ni$^{2+}$/Ni$^{3+}$ reservoir at a potential below the OER onset. **These fundamentally different mechanisms and site requirements cause OER and EOR to respond differently to iron incorporation.**
3. **Electronic structure.** The different electron configuration of **Fe$^{3+}$ (d$^5$, half-filled, redox-inert, strongly Lewis acidic) compared with Ni$^{3+}$ (d$^7$, $e_g^1$, easily driven to Ni$^{4+}$)** alters the d-band structure and M–O covalency at mixed-metal sites. The *same* perturbation has opposite consequences for the two reactions: at an **edge** site it optimises the binding energies of the oxygen intermediates and lowers the O–O coupling barrier (good for OER) and adds conductivity; in the **bulk** it stabilises Ni$^{2+}$, shifts the Ni$^{2+}$/Ni$^{3+}$ potential anodically, dilutes and electronically "freezes" the mediator, and so throttles the redox cycling that EOR is entirely built on (bad for EOR). Pure Ni, by contrast, has more ionic Ni–O bonds — excellent for a reversible, low-potential Ni$^{2+}$/Ni$^{3+}$ shuttle but suboptimal (too-strong oxygen binding, poor conductivity) for OER.

Therefore: **trace iron lands on the edge/defect sites that OER needs and nowhere near the bulk nickel that EOR needs, so it enhances OER and leaves EOR almost unchanged; higher iron content continues to help OER (more optimised, more conductive, more numerous Ni–Fe oxo sites) but now invades the bulk, where its d$^5$, redox-inert, electron-withdrawing character raises the Ni$^{2+}$/Ni$^{3+}$ potential, removes nickel sites and impairs nickel redox cycling — the three mechanisms by which it suppresses ethanol oxidation.** Iron is not intrinsically "good" or "bad": it is an edge-site promoter of adsorbate-based multi-electron catalysis and a bulk-site poison of mediated redox catalysis, and the measured outcome simply reflects which of the two populations the added iron has reached.
