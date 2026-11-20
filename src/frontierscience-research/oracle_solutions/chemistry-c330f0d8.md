# Maleimide Polyacetylene (mPA): precursor ROMP, oxidative aromatisation, and n-type structure–property relationships

## Overview of the system

**Monomer M:** an *N*-alkylmaleimide-fused cyclobutene, i.e. a bicyclo[3.2.0] system in which a cyclobutene ring is *cis*-fused to a succinimide (dihydromaleimide) ring bearing an *N*-alkyl group.

**Precursor polymer P (ROMP):** ring-opening metathesis of the strained cyclobutene opens only the C=C of the four-membered ring, giving a main chain of alternating **vinylene (–CH=CH–)** units and **saturated (sp³) *N*-alkyl-dihydromaleimide (succinimide)** units. The two ring-fusion carbons flanking each imide remain sp³ and each carries one hydrogen that is $\alpha$ to a carbonyl.

**mPA (oxidation):** treatment of P with triethylamine (TEA) and a mild one-/two-electron oxidant (TCNQ or I₂) removes the two $\alpha$-C–H hydrogens of every repeat unit as two protons plus two electrons, creating the endocyclic C=C of the maleimide and thereby a **fully conjugated, alternating vinylene/maleimide polyacetylene analogue**.

Repeat-unit SMILES: P (precursor) `C(/C=C/[*])1C(=O)N(R)C(=O)C1[*]` → mPA `[*]/C=C/C1=C(/[*])C(=O)N(R)C1=O` (idealised, all-*trans*, alternating vinylene–maleimide backbone).

---

## a) Strategic rationale for the two-stage precursor ROMP route and the catalyst choice

### a.1 Why a precursor route at all

A direct polymerisation of an acetylene bearing imide/carbonyl substituents, or a Ziegler–Natta-type polymerisation to a substituted polyacetylene, cannot deliver this target. The precursor (ROMP) strategy is chosen because it decouples **chain construction** from **conjugation formation**, and this buys three distinct, chemically specific advantages.

**(i) Processability.** The fully conjugated target mPA is a rigid-rod, electron-poor, highly planar ladder-like chain. Such chains have very high backbone rigidity (low conformational entropy of mixing), strong interchain interactions (dense $\pi$-stacking reinforced by quadrupolar/dipolar imide–imide contacts) and consequently very high cohesive energy and crystallinity. The combination means mPA itself is expected to be essentially **insoluble and infusible**, i.e. it could not be processed from solution at all if it were made directly — the classic problem of parent polyacetylene and of most electron-poor rigid conjugated polymers. The precursor P, by contrast, is **soluble**: (1) the two **sp³ carbons per repeat unit interrupt the conjugation**, so the chain is kinked and flexible, with no extended $\pi$-system to drive planar stacking, and interchain $\pi$–$\pi$ attraction is largely absent, and (2) the **N-alkyl group** provides solubilising, entropically favourable side-chain volume and disrupts close packing. P can therefore be purified, characterised (NMR, SEC) and — critically — **processed from solution, e.g. spin-coated, drop-cast or blade-coated into thin films** or shaped into free-standing membranes, and only then converted *in situ*, in the solid state or in solution, into the intractable conjugated material. The processing step is performed on the tractable precursor, and the "difficult" polymer is generated at the end, in the final shape required for a device.

**(ii) Control of molecular weight and dispersity.** ROMP with a well-defined, single-site alkylidene initiator is a **living/controlled chain-growth polymerisation**: initiation is fast relative to propagation, there is no irreversible chain transfer or termination under properly chosen conditions, and therefore $M_n$ is set by the monomer-to-initiator ratio, $M_n = ([\mathrm{M}]_0/[\mathrm{I}]_0)\times M_{0,\text{monomer}}\times p$ (with $p$ the conversion), while the dispersity approaches the Poisson limit

$$Đ = \frac{M_w}{M_n} \approx 1 + \frac{1}{\mathrm{DP}_n},$$

i.e. $Đ \lesssim 1.1$. The chain ends are defined by the initiator and the quench, and block copolymers or end-functional chains are accessible by sequential monomer addition. This level of architectural control is **critical for optimising charge transport in semiconductors**: in conjugated polymers the mobility is a strong function of $M_n$ (short chains cannot bridge crystallites, so transport is limited by interchain hopping), and chemical/structural defects and chain ends act as traps and scattering centres, so uniform chain lengths with few defects and few end-groups give reproducible, higher mobility and reproducible device characteristics (threshold voltage, on/off ratio) from batch to batch. This is explicitly **in contrast to Ziegler–Natta polymerisation of acetylene** (and to most direct routes to polyacetylene or to polymerisations of functionalised acetylenes), which are multi-site, uncontrolled chain-growth processes: they give broad, often bimodal molecular weight distributions ($Đ$ of 2 to >10), insoluble intractable products of unknown $M_n$, no end-group control and no batch-to-batch reproducibility.

**(iii) Regioregularity and sequence fidelity.** In mPA the electronic structure depends on the strict alternation –CH=CH–(maleimide)–CH=CH–(maleimide)– and on the regiochemical uniformity of the linkages. The ROMP precursor route **guarantees** this: the alternating sequence is *built into monomer M* (one cyclobutene C=C and one imide per monomer unit), and metathesis cleaves only the strained cyclobutene double bond, so every monomer inserts in exactly the same way. The subsequent oxidation is a **selective backbone modification** that touches only the two $\alpha$-C–H bonds of each imide and creates the new C=C exactly where the sp³ carbons were; it changes no connectivity. Hence the regioregularity and alternating sequence defined by M are **perfectly preserved in mPA**. A direct polymerisation of a functionalised acetylene, by contrast, must contend with head-to-head/head-to-tail regio-errors, *cis/trans* mixtures, cyclotrimerisation, branching/cross-linking, and attack of the catalyst on the electrophilic carbonyls — i.e. side reactions and **structural scrambling** that would destroy the defined alternating architecture.

### a.2 Why a Mo-based Schrock catalyst rather than a Ru Grubbs catalyst

The monomer is a **cyclobutene**, whose polymerisation is thermodynamically very favourable (ring strain $\approx$ 30 kcal mol⁻¹, so $\Delta G_{\text{ROMP}} \ll 0$) but which is **sterically and electronically demanding**: the alkene is flanked by the fused imide ring and the ring-fusion C–H's, and the two electron-withdrawing carbonyls deactivate the olefin toward metallacyclobutane formation by making it a poor $\pi$-donor to the metal. A **highly active, strongly Lewis-acidic, electrophilic alkylidene initiator is therefore required** to achieve fast, quantitative, living propagation.

**Mo-based Schrock catalysts** — $\mathrm{Mo(\!=\!CHCMe_2Ph)(\!=\!NAr)(OR)_2}$ (Ar = 2,6-diisopropylphenyl, OR = OC(CF₃)₂Me or OC(CF₃)₃-type fluorinated alkoxides) — are d⁰, high-oxidation-state, four-coordinate 12-electron alkylidenes. They are far more electrophilic and far less sterically protected at the metal than the Ru carbenes, and their metathesis activity toward **electron-poor, sterically encumbered and strained olefins is orders of magnitude higher** than that of Ru-based Grubbs catalysts. In practice **Mo Schrock initiators possess significantly higher reactivity for such monomers than Ru-based Grubbs catalysts**: Grubbs (Ru) systems are comparatively electron-rich, mid-oxidation-state 16-electron carbenes whose reactivity toward electron-deficient, imide-flanked cyclobutenes is poor (slow initiation relative to propagation, incomplete conversion, broadened $Đ$, loss of living character); Ru catalysts also readily undergo chain transfer/backbiting with such substrates. In addition, Mo alkylidenes initiate essentially instantaneously ($k_i \gg k_p$) with these monomers, which is the prerequisite for low dispersity, and they allow good control of the backbone *cis/trans* vinylene stereochemistry through the imido/alkoxide ligand set — useful because an all-*trans* vinylene backbone is what maximises planarity and conjugation length in the final mPA. The usual trade-off (lower functional-group tolerance and higher sensitivity to air/moisture/protic groups for Mo) is acceptable here because the monomer bears only robust, non-protic imide functionality.

---

## b) Mechanism of the P → mPA conversion under TEA/mild oxidant

### b.1 Overall redox bookkeeping

Per repeat unit, the transformation converts the two **sp³ carbons $\alpha$ to the carbonyls** (the ring-fusion CH units of the dihydro-maleimide/succinimide ring) into **sp² carbons**, forming the **intramolecular endocyclic C=C double bond within the maleimide ring**. This requires removal of two hydrogen atoms, i.e.

$$\mathrm{P\!-\!(C_\alpha H)(C_\alpha H)} \;\longrightarrow\; \mathrm{mPA\!-\!(C_\alpha\!\!=\!\!C_\alpha)} + 2\,\mathrm{H^+} + 2\,e^-$$

so the reaction is a **net two-electron, two-proton oxidation (formal dehydrogenation) per dihydro-maleimide repeat unit**. It is *not* an elimination of a leaving group and *not* a thermal retro-reaction: both protons are taken by the amine base and both electrons by the oxidant.

**Role of the oxidant.** TCNQ or I₂ is the **stoichiometric terminal electron acceptor**. Per double bond formed it must take up **two electrons**, being reduced to its corresponding reduced form:

$$\mathrm{TCNQ} + 2e^- \rightarrow \mathrm{TCNQ^{2-}}\quad(\text{via the radical anion } \mathrm{TCNQ^{\bullet-}},\ E^{0}_{1} \approx +0.2\ \text{V vs SCE})$$

$$\mathrm{I_2} + 2e^- \rightarrow 2\,\mathrm{I^-}$$

so one equivalent of TCNQ (→ TCNQ²⁻, isolated as its triethylammonium salt) or of I₂ (→ 2 I⁻, isolated as Et₃NH⁺I⁻) is consumed per repeat unit, together with two equivalents of TEA which end up as **two equivalents of triethylammonium** ($\mathrm{Et_3NH^+}$). The overall stoichiometry is

$$\mathrm{P} + \mathrm{TCNQ} + 2\,\mathrm{Et_3N} \;\longrightarrow\; \mathrm{mPA} + \mathrm{TCNQ^{2-}} + 2\,\mathrm{Et_3NH^+}$$

(and analogously with I₂ → 2 I⁻). The oxidant is "mild" precisely because it only has to intercept electrons from a transiently generated, very electron-rich (enolate-like) intermediate; it never has to attack a closed-shell C–H bond directly, which is why no strong oxidant (DDQ in forcing conditions, peroxides, high-potential quinones), no high temperature and no transition-metal dehydrogenation catalyst is needed.

**Thermodynamic driving force.** The reaction is strongly downhill because each dehydrogenation converts two isolated sp³ centres into a new C=C that is **cross-conjugated into the imide and, crucially, directly conjugated with the flanking vinylene units**. Propagating this along the whole chain creates the **highly stable, extended $\pi$-conjugated system along the polymer backbone** (aromatisation/conjugation energy of the maleimide plus delocalisation over many repeat units, together with the relief of eclipsing/ring-fusion strain at the sp³ ring-fusion carbons). It is this **formation of the extended conjugated backbone that is the thermodynamic driving force** for the transformation, and it is what allows a weak base and a mild oxidant to drive a formally difficult C–H functionalisation of every repeat unit to completion.

### b.2 Why simple deprotonation by TEA cannot be the mechanism

The $\alpha$-C–H protons of P are imide-$\alpha$ protons on a succinimide, i.e. essentially those of a mono-activated ketone-like carbon: their $pK_a$ in organic media is high, of order $pK_a \approx 25$–30 (DMSO scale), comparable to a simple ketone $\alpha$-C–H and far above that of a 1,3-dicarbonyl. Triethylamine is a weak base whose conjugate acid $\mathrm{Et_3NH^+}$ has $pK_a \approx 9$ (DMSO; ~10.7 in water). The equilibrium constant for stoichiometric proton transfer is therefore

$$K_{\text{eq}} = 10^{-(pK_a(\mathrm{C-H})-pK_a(\mathrm{Et_3NH^+}))} \approx 10^{-(28-9)} = 10^{-19},$$

i.e. the concentration of free carbanion/enolate generated by TEA alone is vanishingly small. **Full stoichiometric deprotonation of P by TEA is thus thermodynamically unreasonable**, and yet the reaction proceeds smoothly at or near room temperature. A purely base-mediated (E1cb-type) pathway is therefore excluded, and a synergistic base/oxidant mechanism must operate.

### b.3 Charge-transfer complex formation: the key proposal

The resolution is that **TEA and the oxidant first associate to form a charge-transfer (CT) complex**:

$$\mathrm{Et_3N} + \mathrm{TCNQ} \;\rightleftharpoons\; [\mathrm{Et_3N}^{\delta+}\cdots\mathrm{TCNQ}^{\delta-}]\qquad(\text{likewise } [\mathrm{Et_3N}^{\delta+}\cdots\mathrm{I_2}^{\delta-}],\ \text{an } n\!\rightarrow\!\sigma^* \text{ amine–iodine CT adduct})$$

Triethylamine is a good $n$-donor (IP $\approx$ 7.5 eV) and TCNQ is a strong $\pi$-acceptor ($EA \approx$ 2.8 eV); amine/TCNQ and amine/I₂ CT complexes are well known and are immediately evident experimentally as intense new visible/NIR CT absorption bands (and, for TCNQ, the appearance of $\mathrm{TCNQ^{\bullet-}}$ marker bands at ~750 and ~840 nm). **This CT complex is the key element that allows the weakly basic TEA to initiate the transformation despite the high $pK_a$ of the $\alpha$-protons**: inside the complex the amine lone pair is partially transferred to the acceptor, and the resulting species is simultaneously (i) a base and (ii) a built-in electron sink. Proton removal no longer has to pay the full $\Delta pK_a$ penalty, because the electron that would otherwise remain as a localised, high-energy carbanion is taken up by the acceptor in the *same* encounter. In thermodynamic terms the prohibitive $10^{-19}$ proton-transfer equilibrium is replaced by a **coupled proton–electron transfer** whose driving force includes the reduction potential of the acceptor and the conjugation energy of the product — a classic concerted/coupled PCET-type bypass of an unfavourable pure proton transfer.

### b.4 Step-by-step mechanism

**Step 1 — Initial activation (C–H activation / transient partial proton abstraction).** The CT complex $[\mathrm{Et_3N}\cdots\mathrm{Ox}]$ encounters a dihydro-maleimide unit of P. The amine nitrogen hydrogen-bonds to, and polarises, one $\alpha$-C–H bond, while the acceptor moiety of the same complex interacts with the electron density of that C–H/adjacent carbonyl. The result is **activation (polarisation, elongation) of the $\alpha$-C–H bond and only transient, partial proton abstraction** — the proton is shared in an $[\mathrm{N}\cdots\mathrm{H}\cdots\mathrm{C}]$ arrangement rather than fully transferred. **Full, stoichiometric deprotonation by TEA alone is both unlikely (see b.2) and unnecessary** in this synergistic scheme: the only requirement is that enough negative charge build up on $\mathrm{C}_\alpha$ for the adjacent acceptor to remove an electron. Equivalently, the reaction may be formulated as a concerted proton-coupled electron transfer in which the amine takes H⁺ and the acceptor takes e⁻ in a single kinetically coupled event, giving directly the $\alpha$-radical plus $\mathrm{Et_3NH^+}$ plus $\mathrm{TCNQ^{\bullet-}}$ (or $\mathrm{I_2^{\bullet-}} \rightarrow \mathrm{I^\bullet} + \mathrm{I^-}$). The small equilibrium concentration of genuine imide enolate that TEA does generate is likewise intercepted by single-electron transfer to the acceptor; both descriptions converge on the same intermediate.

**Step 2 — First one-electron oxidation.** Electron transfer from the (partially formed) enolate/activated C–H to the acceptor gives a **$\alpha$-carbon radical stabilised by the adjacent carbonyl** (a captodatively stabilised, delocalised imide-$\alpha$ radical) together with $\mathrm{Et_3NH^+}$ and $\mathrm{TCNQ^{\bullet-}}$ (or $\mathrm{I^\bullet/I^-}$). Radical formation is the step that makes the second abstraction easy, because the C–H bond on the *adjacent* $\alpha$-carbon is now both weakened (the bond dissociation free energy of a C–H $\beta$ to a radical centre is strongly reduced, since loss of the second H creates a C=C) and far more acidic.

**Step 3 — Second proton/electron removal.** The second $\alpha$-C–H, now dramatically activated, is removed by a second TEA (again assisted by the acceptor) with transfer of the second electron to the oxidant. This completes the **2 H⁺/2 e⁻ loss** and directly furnishes the new **$\mathrm{C}_\alpha\!\!=\!\!\mathrm{C}_\alpha$ double bond within the maleimide ring**, converting both carbons from sp³ to sp². The oxidant has now taken two electrons in total (TCNQ → TCNQ²⁻, or I₂ → 2 I⁻) and two TEA have become two $\mathrm{Et_3NH^+}$.

**Step 4 — Propagation along the chain (autocatalytic/anchimeric acceleration).** Once one unit is aromatised, the adjacent repeat units are activated: the newly formed, conjugated vinylene–maleimide segment lowers the oxidation potential of neighbouring units (the growing conjugated segment is a better electron donor and better stabilises radical/anionic intermediates by delocalisation), and the $\alpha$-C–H bonds adjacent to a conjugated segment are both weaker and more acidic because their removal extends the conjugation further. The dehydrogenation therefore propagates cooperatively along the chain rather than stalling, which accounts for the near-quantitative conversion of every repeat unit under mild conditions and for the strongly downhill overall thermodynamics (extended conjugation, Step b.1).

**Net reaction per repeat unit:**

$$\mathrm{-(CH\!=\!CH)\!-\!(C_\alpha H\!-\!C_\alpha H\ \text{imide})\!-} + \mathrm{Ox} + 2\,\mathrm{Et_3N} \rightarrow \mathrm{-(CH\!=\!CH)\!-\!(C_\alpha\!\!=\!\!C_\alpha\ \text{maleimide})\!-} + \mathrm{Ox^{2-}} + 2\,\mathrm{Et_3NH^+}$$

Consistency checks that support the mechanism: the reaction requires **both** components (TEA alone or oxidant alone leaves P untouched); the rate shows first-order dependence on both; an immediate CT colour change (and $\mathrm{TCNQ^{\bullet-}}$/ $\mathrm{TCNQ^{2-}}$ or $\mathrm{I^-}$ signatures) accompanies conversion; a primary kinetic isotope effect is expected at the $\alpha$-positions; and the mass balance of the by-products ($\mathrm{Et_3NH^+}$ salts of $\mathrm{TCNQ^{2-}}$ or $\mathrm{I^-}$, removable by washing) matches the 2 H⁺/2 e⁻ stoichiometry.

---

## c) Structure–property relationships: LUMO level, n-type behaviour, planarity and conductivity

### c.1 Mechanism of LUMO lowering

The deep LUMO of mPA arises **primarily from the strong electron-withdrawing character of the maleimide carbonyl groups, which are now conjugated with the backbone**. Two distinct and reinforcing effects operate:

- **Inductive ($-I$):** the two carbonyl carbons and the imide nitrogen are highly electronegative/polarised ($\mathrm{C}\!\!=\!\!\mathrm{O}$ dipoles), which withdraws $\sigma$-electron density from the backbone carbons, stabilising (lowering) all the frontier orbital energies and in particular the $\pi^*$ manifold.
- **Resonance/mesomeric ($-M$):** because the newly formed $\mathrm{C}_\alpha\!\!=\!\!\mathrm{C}_\alpha$ is now **conjugated with both carbonyls**, the carbonyl $\pi^*$ orbitals mix directly into the backbone $\pi^*$ system. Negative charge placed on the backbone can delocalise onto the carbonyl oxygens (push–pull resonance structures $\mathrm{C^-\!-\!C\!=\!O} \leftrightarrow \mathrm{C\!=\!C\!-\!O^-}$), which stabilises the LUMO strongly and places substantial LUMO amplitude on the imide carbonyls.

The imide is a *cyclic*, planarised, doubly-carbonyl-substituted acceptor, so both effects act twice per repeat unit and in a geometry that enforces maximum $\pi$-overlap with the backbone — a far stronger LUMO-lowering motif than isolated ester, ketone or cyano substituents. The predicted result is a LUMO around $-4$ eV or below (versus $\approx -2.5$ to $-3$ eV for unsubstituted polyacetylene/polythiophene), i.e. extreme electron deficiency, with a modest optical gap because the HOMO is also only partly stabilised.

### c.2 Consequences of the low LUMO: n-doping and stability of the charged states

A deep-lying LUMO has two distinct and essential consequences:

1. **It facilitates facile n-doping (reduction).** Electron injection/transfer into the polymer is thermodynamically favourable, so mPA can be reduced by common, mild n-dopants whose donor levels lie above $-4$ eV (e.g. $\mathrm{N\text{-}DMBI}$, TDAE, cobaltocene, simple alkali-metal salts/reductants) rather than requiring the extremely strong, air-sensitive reductants that shallow-LUMO polymers need. In device terms the low LUMO also reduces the electron-injection barrier from common cathodes/contacts and gives Ohmic rather than injection-limited contacts.
2. **It enhances the electrochemical (ambient) stability of the resulting negatively charged states** — the radical anions/polarons and dianions/bipolarons carried on the backbone. The stability requirement is thermodynamic: the polaron level must lie below the potentials of the ambient oxidants, i.e. roughly below the $\mathrm{O_2/H_2O}$ reduction level (around $-4.0$ to $-4.3$ eV on the vacuum scale). Because the maleimide carbonyls place the extra electron density partly on electronegative oxygen (the $-M$ delocalisation above), the anionic state is intrinsically low in energy and is not quenched by O₂ or by moisture; the doped (n-type) state therefore survives in air rather than back-transferring its electron to oxygen. This is why extreme electron deficiency, and not merely planarity, is a prerequisite for a *usable*, **air-stable n-doped** conducting polymer.

Together these two points define mPA's **n-type behaviour**: electrons, not holes, are the majority carriers; the material is easily and stably reduced, and the chemical potential of the doped state lies deep enough for ambient operation.

### c.3 Planarity analysis

mPA is predicted to be **highly planar along the backbone**, for three structural reasons:

- The **vinylene units (–CH=CH–) are inherently planar**: sp² carbons with 120° angles, and the all-*trans* configuration delivered by ROMP places substituents anti, so each vinylene is a flat, rigid, conjugation-transmitting link.
- The **maleimide rings are inherently planar**: a five-membered, fully sp², cross-conjugated ring (C=C flanked by two C=O and an N) whose geometry is rigidly fixed; both of its exocyclic bonds to the backbone lie in the ring plane.
- There is **no significant steric hindrance directly on the conjugated backbone** to force twisting. The only substituent in the repeat unit is the **N-alkyl chain, which sits on the imide nitrogen** — a position that is *in* the ring plane but **points outward, away from the backbone axis**, so it cannot clash with the neighbouring vinylene protons. The backbone carbons themselves bear only hydrogens (on the vinylene) or are part of the fused imide; there are no bulky *ortho*-type substituents, no ring-ring *peri* interactions, and no 1,3-allylic strain along the chain. Consequently the torsional potential about the vinylene–maleimide single bonds has a deep minimum at $\theta = 0°$ (and 180°), and the barrier to planarity is essentially absent.

This is in direct contrast to the usual situation in electron-poor polyacetylene analogues, in which the electron-withdrawing groups are attached as pendant substituents on the backbone carbons and sterically force large dihedral twists.

### c.4 Role of planarity for conductivity

Backbone planarity is the structural prerequisite for high conductivity, because conductivity depends on **efficient $\pi$-orbital overlap**, in two complementary directions:

- **Intrachain delocalisation.** $\pi$-overlap between adjacent p$_z$ orbitals scales approximately as $\cos\theta$ (and the effective transfer integral as $t \approx t_0\cos\theta$) for a torsion $\theta$ about a backbone single bond. A planar ($\theta \approx 0$) backbone therefore maximises the transfer integral, giving broad $\pi$/$\pi^*$ bands, a long effective conjugation length, small carrier effective mass $m^* \propto 1/t$ and fast, nearly band-like **charge delocalisation along the chain**; a twisted backbone breaks the chain into short, weakly coupled conjugated segments between which carriers must hop, and simultaneously raises the LUMO and the polaron binding energy.
- **Interchain transport.** Since no real chain is infinite, macroscopic conduction requires carriers to pass between chains. A flat, unsubstituted-at-the-backbone chain can approach a neighbouring chain closely and **co-facially, so that the chains $\pi$-stack** at van der Waals contact (~3.3–3.5 Å), which gives large interchain transfer integrals and a three-dimensionally connected transport network; the planar maleimide units with their in-plane dipoles further favour ordered, registered stacking. Twisted backbones cannot pack cofacially, so interchain hopping rates (Marcus-type, $k \propto |t_\perp|^2$) collapse, and mobility becomes limited by the slowest interchain step no matter how good the intrachain conjugation is.

Because mPA combines planarity on both counts with the deep LUMO, it should support **high electron mobility and, upon stable n-doping, high electrical conductivity** — i.e. the material is designed so that the electron-withdrawing groups do not have to be paid for with a twisted backbone.

---

## d) Overall significance for n-type conjugated polymers

High-performance n-type polymers have lagged behind p-type ones because three design requirements normally compete — a **trilemma**:

1. a LUMO deep enough for easy and *air-stable* n-doping,
2. a planar, well-ordered backbone for efficient charge transport, and
3. synthetic control plus processability.

Conventionally, satisfying (1) means hanging strong electron-withdrawing groups on the backbone, which sterically twists it and destroys (2); and making the backbone rigid and planar destroys (3). The mPA system provides a **synergistic solution** to all three at once:

**(i) Extreme electron deficiency from the maleimide core.** By fusing the acceptor *into* the backbone as a cyclic imide rather than appending it as a pendant group, mPA achieves a very low LUMO (via the $-I$ and $-M$ effects of two conjugated carbonyls per repeat unit). This is what is needed for **air-stable n-doping** — the polaron/anion level lies below the ambient O₂/H₂O window, so the doped state does not decay — and for **favourable device energetics**, with low electron-injection barriers from common electrodes and good contact Ohmicity. It thus addresses head-on the ambient-instability problem that has limited earlier low-LUMO n-type polymers, whose doped states were either not deep enough (quenched by O₂/water) or achieved only with reactive dopants.

**(ii) Inherently planar alternating architecture.** The **alternating vinylene–maleimide backbone maintains high planarity by construction**: both building blocks are flat, and the only substituent (the N-alkyl group) is placed on the imide nitrogen, pointing away from the conjugation path. The polymer therefore **overcomes the steric twisting that electron-withdrawing substituents normally introduce in other polyacetylene analogues** (where EWGs on the backbone carbons force large dihedrals), so that strong electron deficiency and efficient intrachain delocalisation plus interchain $\pi$-stacking coexist in one material. Low LUMO and planarity are decoupled from each other.

**(iii) ROMP precursor route for architectural control and processability.** The living Mo-catalysed ROMP gives defined $M_n$ and low $Đ$ with preserved regioregular alternation, and the soluble precursor P can be cast into films before the mild TEA/oxidant post-polymerisation dehydrogenation generates the conjugated material in place. This **circumvents the synthetic and processing limitations faced by rigid conjugated polymers** — insolubility, infusibility, ill-defined molecular weight, defect-ridden direct polymerisations of functionalised acetylenes — and makes the final, otherwise intractable polymer accessible in device-relevant form with reproducible properties.

More broadly, the work establishes a **general, modular design principle**: build the conjugated backbone in a protected (sp³, soluble) form by living ROMP of a strained, acceptor-fused cyclobutene, then unmask the conjugation by a mild, redox-coupled, base-assisted dehydrogenation whose driving force is the conjugation energy itself. Because the imide nitrogen substituent is freely variable (alkyl chain length and branching for solubility and packing; functional, polar or ionic side chains for mixed ionic–electronic conduction and for thermoelectrics or bioelectronics), and because the monomer scaffold can be changed to other fused acceptors, the strategy opens a family of planar, low-LUMO, processable, air-stable n-type polymers — the long-missing counterparts of the well-developed p-type materials — for OFETs, organic thermoelectrics, all-polymer solar cells and n-doped conductive layers.
