# A copper-catalysed catalytic cycle for Ar₂NH from ArB(OH)₂ and NaNO₂

## 0. The transformation and its stoichiometric requirements

$$2\ \mathrm{ArB(OH)_2} + \mathrm{NaNO_2} \xrightarrow[\text{ligand, base, solvent}]{\mathrm{Cu\ cat.}} \mathrm{Ar_2NH} + \text{(boron oxide / borate by-products)} + \mathrm{Na^+}$$

Three bookkeeping facts fix the mechanism before any step is written:

1. **Two aryl groups per nitrogen.** The product contains two Ar–N bonds, so the **2:1 ArB(OH)₂:NaNO₂ stoichiometry maps directly onto the mechanistic necessity of two distinct aryl transfer events** to the copper/nitrogen complex within one turnover. One transfer makes the first Ar–N bond; a second, separate transmetalation/transfer event makes the second. Neither can be dispensed with, and this is why the reaction fails (or stops at ArNO₂/ArNO-derived products) with only one equivalent of boronic acid. In practice an excess (2.5–3 equiv) is used because the boron also serves as the oxygen sink (point 3).
2. **Nitrogen oxidation state.** Nitrite is N(+III) with two oxygens; the amine product is N(–III) with none. The nitrogen must therefore be **both deoxygenated and reduced** inside the cycle, and the convenient staging post at the correct oxidation level for C–N bond formation is the **nitroso level (Ar–N=O, N(+I))**, reached by loss of one oxygen from $\mathrm{NO_2^-}$.
3. **Fate of the oxygens.** The two oxygen atoms of $\mathrm{NO_2^-}$ must leave as something. They are taken up by **boron**, the most oxophilic element present: $\mathrm{B\!-\!O}$ bond energies (~520–540 kJ mol⁻¹) greatly exceed $\mathrm{N\!-\!O}$ (~200–230 kJ mol⁻¹ for N–O single bonds) and $\mathrm{B\!-\!C}$ (~320 kJ mol⁻¹), so O-transfer from N to B is strongly exergonic. The by-products are boronic/boric esters, boroxines and borate: $\mathrm{ArB(OH)_2 \to ArB(OH)(OR)/boroxine}$, ultimately $\mathrm{B(OH)_3}$/$\mathrm{[B(OH)_4]^-}$ and, where the aryl group is sacrificed in an O-abstraction event, ArOB(OH)₂ → **ArOH** (phenol) as a recognised minor by-product. This thermodynamic sink is the hidden engine of the whole reaction.

## a) The catalytic cycle and the copper oxidation states

The cycle operates on the **Cu(I)/Cu(III) couple**, the hallmark of Chan–Lam-type and Cu-catalysed C–N coupling chemistry (two-electron, organometallic steps rather than Cu(I)/Cu(II) single-electron chemistry). The sequence of oxidation states is:

$$\mathbf{Cu(I)} \xrightarrow[\text{transmetalation}]{\mathrm{ArB(OH)_2}} \mathbf{aryl\text{-}Cu(I)}\ (\mathrm{Ar\text{-}Cu^{I}}) \xrightarrow[\text{+ deoxygenation}]{\mathrm{NaNO_2}} \mathbf{Cu(III)} \xrightarrow[\text{C–N reductive elimination}]{} \mathbf{Cu(I)}$$

i.e. **Cu(I) → aryl-Cu(I) → Cu(III) (upon nitrite incorporation/transformation) → Cu(I) (upon reductive elimination)**, the Cu(I) resting state being regenerated at the end of every turnover so that no external oxidant is required.

### Step-by-step

**Step 1 — Resting state and first transmetalation.** The precatalyst (CuI, CuBr, Cu(OAc)₂ pre-reduced by the boronic acid, or Cu(MeCN)₄PF₆) with an N-donor ligand (phen, bipy, DMEDA) or as the simple halide/carboxylate generates **$\mathrm{L_nCu^{I}\text{-}X}$**. Base-assisted transmetalation with the boronic acid — proceeding through the four-coordinate boronate $\mathrm{[ArB(OH)_3]^-}$, which is the kinetically competent aryl donor, and a Cu–O–B pre-association — delivers the aryl group with retention of oxidation state:

$$\mathrm{L_nCu^{I}\!-\!X} + \mathrm{[ArB(OH)_3]^-} \longrightarrow \mathbf{L_nCu^{I}\!-\!Ar} + \mathrm{XB(OH)_2} + \mathrm{OH^-}$$

**aryl-Cu(I)** ($d^{10}$, Cu(I) retained; transmetalation is redox-neutral).

**Step 2 — Nitrite binding.** $\mathrm{NO_2^-}$ is an excellent ligand for copper and binds in the first coordination sphere, initially $\kappa^1$-O (nitrito) or $\kappa^1$-N (nitro), with the $\eta^2$-O,O chelate also accessible:

$$\mathrm{L_nCu^{I}\!-\!Ar} + \mathrm{NO_2^-} \longrightarrow \mathbf{[L_nCu^{I}(Ar)(\kappa^1\text{-}ONO)]^-} \rightleftharpoons \mathbf{[L_nCu^{I}(Ar)(\kappa^1\text{-}NO_2)]^-}$$

This is the essential activation event: **NaNO₂ is not activated as a free species in solution but is transformed within the copper coordination sphere.**

**Step 3 — O-atom abstraction / deoxygenation (nitro → nitroso level).** The bound nitrite must lose one oxygen to reach the nitroso oxidation level. **Boron is the agent of this deoxygenation, which is a specific mechanistic role for ArB(OH)₂ beyond that of a simple aryl source.** Two closely related, kinetically plausible variants:

- *(a) Boron-mediated O-abstraction.* The pendant oxygen of the $\kappa^1$-N-bound nitrite is Lewis-basic and is captured by the Lewis-acidic boron of a second $\mathrm{ArB(OH)_2}$, giving a Cu–N(O)–O–B(OH)₂Ar adduct in which the N–O bond is strongly polarised and weakened. Collapse of this adduct cleaves N–O heterolytically with transfer of oxygen to boron, generating the Cu-bound nitroso fragment and $\mathrm{ArB(OH)_2(O^-)}$, which proceeds on to boroxine/borate (and, via 1,2-aryl migration from B to O — the standard oxidative pathway of boronates with an O–X electrophile — to **ArOH/ArOB(OH)₂**; detection of small amounts of phenol is diagnostic of this step).
- *(b) Aryl-Cu-mediated O-transfer.* Alternatively, the **aryl-Cu(I)** species itself performs the reduction: migration of the aryl group from Cu to an oxygen of the bound nitrite generates an $\mathrm{Ar\!-\!O}$ linkage that is expelled (as ArO⁻, trapped instantly by boron as ArOB(OH)₂), leaving the nitrogen one oxidation level lower and still bound to copper. Here the boronic acid supplies the aryl group that is sacrificed to carry the oxygen away, and the oxophilic boron again provides the thermodynamic driving force.

In either variant the stoichiometric oxygen sink is boron and the net result is the same:

$$\mathrm{[L_nCu(Ar)(NO_2)]^-} \xrightarrow{\mathrm{ArB(OH)_2}} \mathbf{nitroso\text{-}level\ Cu\ complex} + \mathrm{[ArB(OH)_2O]^-}\ (\rightarrow \mathrm{ArOH/boroxine})$$

**Step 4 — Aryl migration and formation of the key Cu(III)–η²-nitroso complex.** Migration of the aryl ligand from copper to the nitrogen (intramolecular aryl transfer within the coordination sphere), coupled to the deoxygenation above, converts the fragment into a **copper-bound nitrosoarene**. Crucially, this ligand does **not** dissociate: it binds **side-on, $\eta^2$ through both the N and the O atoms**, formally as a dianionic (reduced) nitroso/azadioxo ligand, which oxidises copper by two units:

$$\mathbf{[L_nCu^{III}(\eta^2\text{-}N,O\text{-}ArNO)]}\qquad\text{a closed Cu–N–O metallacycle, with the nitroso ligand chelating through both N and O}$$

Thus **Cu(III) is reached upon nitrite incorporation/transformation**: the two-electron reduction of the N-centre (nitro → nitroso, with O-loss to boron) is compensated by two-electron oxidation of the metal, $\mathrm{Cu(I)} \to \mathrm{Cu(III)}$ ($d^{10} \to d^8$, square-planar, strongly stabilised by the chelating N,O-ligand and the N-donor ancillary ligand). This metallacyclic $\eta^2$-N,O coordination is the structural key to the whole cycle (see part d).

**Step 5 — Second transmetalation: the second aryl transfer.** A second equivalent of boronate transmetalates onto this Cu(III) centre (transmetalation onto Cu(III) is fast — the metal is highly electrophilic), and the aryl group is delivered **to the nitrogen atom of the $\eta^2$-bound nitroso ligand**:

$$\mathrm{[L_nCu^{III}(\eta^2\text{-}ArNO)]} + \mathrm{[Ar'B(OH)_3]^-} \longrightarrow \mathrm{[L_nCu^{III}(Ar')(\eta^2\text{/}\kappa^1\text{-}ArNO)]} \longrightarrow \mathrm{[L_nCu(N(Ar)(Ar')\!-\!O)]}$$

**The nitrogen atom of the $\eta^2$-bound nitroso ligand is the direct site of the second aryl group transfer** — either by transmetalation onto Cu followed by immediate Ar→N reductive elimination/migration, or by direct attack of the nucleophilic boronate aryl group on the electrophilic, copper-activated nitrogen. $\eta^2$-N,O coordination to Cu(III) is precisely what makes that nitrogen electrophilic: back-donation into the N=O $\pi^*$ is removed, the N–O bond is lengthened and the nitrogen is umpolung-activated toward the nucleophilic aryl boronate. (Free nitrosoarenes are of course also electrophilic at N, but in the free state they are diverted — see part d.)

**Step 6 — C–N reductive elimination and loss of the second oxygen.** Reductive elimination forms the second Ar–N bond and returns copper to Cu(I); the remaining oxygen is expelled as a Cu/boron oxo or hydroxide species, trapped as borate:

$$\mathrm{[L_nCu^{III}(Ar)(\eta^2\text{-}ArNO)]} \longrightarrow \mathrm{[L_nCu^{I}\!-\!N(Ar)_2]} + \text{``O''}\ (\to \mathrm{B\!-\!O})$$

giving the **copper(I) diarylamide**. The N–O bond cleavage that accompanies (or immediately follows) reductive elimination is again driven by O-capture at boron, which is why no external reductant is needed.

**Step 7 — Protonation and catalyst regeneration.** Protonolysis of the Cu(I)–amide by the boronic acid (B–OH is a sufficient proton source), by water or by the solvent liberates the product and **regenerates the Cu(I) catalyst**:

$$\mathrm{[L_nCu^{I}\!-\!NAr_2]} + \mathrm{H\!-\!OB(OH)Ar} \longrightarrow \mathbf{Ar_2NH} + \mathrm{L_nCu^{I}\!-\!OB(OH)Ar} \rightarrow \mathrm{L_nCu^{I}\!-\!X}$$

The cycle closes with copper in its original +1 oxidation state, having passed through Cu(I) → aryl-Cu(I) → Cu(III) → Cu(I) in each turnover, with **both oxygens of nitrite ending up on boron** (boroxine/boric acid/borate, plus minor ArOH) and sodium as a spectator cation. The net cycle consumes the 2 ArB(OH)₂ : 1 NaNO₂ demanded by the two aryl transfer events, with additional boronic acid consumed in the two deoxygenation events (hence the typical use of 2.5–3 equiv).

### Cycle in summary

$$
\begin{aligned}
&\mathrm{L_nCu^{I}X} \;\xrightarrow{\ \mathrm{ArB(OH)_2/base}\ }\; \mathrm{Ar\text{-}Cu^{I}L_n} \;\xrightarrow{\ \mathrm{NO_2^-}\ }\; [\mathrm{Ar\text{-}Cu^{I}(NO_2)}]^- \\
&\xrightarrow[\text{(O to boron)}]{-\,\text{``O''}}\; \mathbf{L_nCu^{III}(\eta^2\text{-}N,O\text{-}ArNO)} \;\xrightarrow{\ \mathrm{ArB(OH)_2}\ \text{(2nd aryl to N)}}\; \mathrm{L_nCu^{III}(Ar)(ArNO)} \\
&\xrightarrow[\text{RE},\,-\,\text{``O''}]{}\; \mathrm{L_nCu^{I}\text{-}NAr_2} \;\xrightarrow{\ \mathrm{H^+}\ }\; \mathbf{Ar_2NH} + \mathrm{L_nCu^{I}X}
\end{aligned}
$$

## b) Mechanistic role of NaNO₂ and how it is activated

NaNO₂ is an inexpensive, bench-stable, inorganic nitrogen source that supplies the single nitrogen atom of the product. It is **not** an amine surrogate that simply binds and is arylated twice at its as-purchased oxidation level, and it is **not** usefully activated outside the metal: free nitrite is a poor electrophile at N, and its acid-mediated chemistry (HNO₂ → NO⁺) would lead to diazotisation/nitrosation side reactions rather than to C–N coupling.

Instead, **activation of NaNO₂ occurs by its transformation within the copper coordination sphere to generate a copper-bound nitroso-type species, with the explicit, required loss of one oxygen atom** (and loss of the second oxygen later, at the N–O cleavage/reductive elimination stage):

1. **Coordination:** $\mathrm{NO_2^-}$ binds to the aryl-Cu(I) centre ($\kappa^1$-N nitro ⇌ $\kappa^1$-O nitrito ⇌ $\eta^2$-O,O), which polarises the N–O bonds and brings the nitrogen into bonding contact with the aryl ligand.
2. **Deoxygenation (N(+III) → N(+I)):** the bound nitrite is reduced by one O-atom transfer to boron (or by Cu→O aryl migration, Step 3a/3b above) — the step that **accounts for the required loss of oxygen**. The nitrogen is now at the **nitroso level**.
3. **Metal-bound nitroso intermediate:** coupled with intramolecular aryl migration, this gives the key **$\mathrm{Cu(III)}$–$\eta^2$-(N,O)-nitrosoarene** complex, i.e. the nitrogen is delivered to the organic framework while still ligated to copper.
4. **Second N–O cleavage:** removal of the remaining oxygen (again to boron) at/after the second C–N bond-forming step completes the reduction to the amide/amine level N(–III).

In short, nitrite acts as an **"N" transfer reagent that is stepwise deoxygenated and reduced on copper**, with each deoxygenation paid for by the formation of very strong B–O bonds. The role of nitrite's oxygens is not incidental: they are the internal oxidants that allow copper to cycle through Cu(III) without any external oxidant, which is why this reaction (unlike classical Chan–Lam couplings) needs neither O₂ nor a stoichiometric oxidant.

## c) Influence of electron-donating vs electron-withdrawing substituents on ArB(OH)₂

Two steps in the cycle respond to the aryl electronics in **opposite** directions, so the prediction requires weighing them.

**Effect on transmetalation (Steps 1 and 5).** Transmetalation proceeds by transfer of a nucleophilic (carbanion-like) aryl group from the boronate $\mathrm{[ArB(OH)_3]^-}$ to copper. Electron-**donating** groups (EDGs: 4-OMe, 4-Me, 4-NMe₂) increase the nucleophilicity/carbanion character at the ipso carbon and accelerate Ar transfer; electron-**withdrawing** groups (EWGs: 4-CF₃, 4-CN, 4-NO₂, 4-CO₂R) reduce the nucleophilicity of the ipso carbon and therefore **retard** transmetalation (Hammett $\rho < 0$ for this step in isolation). EWGs also slightly lower the Lewis basicity/boronate formation equilibrium and, for very electron-poor arenes, promote competing **protodeboronation** and oxidative side reactions.

**Effect on C–N reductive elimination (Step 6) and on the second aryl transfer to nitrogen (Step 5).** Reductive elimination from high-valent Cu(III) is accelerated by ligands that stabilise the electron-rich, reduced metal centre and by increasing the electrophilicity of the metal; electron-poor aryl groups are better $\pi$-acceptors/weaker $\sigma$-donors, they reduce the electron density at Cu(III), favour the two-electron C–N bond-forming collapse and lower the barrier to Cu(III) → Cu(I). More importantly, the **nitrogen-centred steps** are helped by EWGs in two ways: (i) an electron-poor $\eta^2$-ArNO ligand is a markedly more **electrophilic nitrogen**, so the attack of the second aryl nucleophile on N is faster; and (ii) the resulting diarylamide nitrogen is less basic and less $\sigma$-donating, so the Cu(I)–amide is formed and released more readily (the amide is a poorer ligand and protonolysis/turnover is faster). Electron-rich aryls do the reverse: a strongly donating ArNO ligand is a poor electrophile at N, and the resulting electron-rich diarylamide binds Cu(I) tightly, slowing catalyst turnover; EDG-substituted diarylamines are also more easily over-oxidised (to aminyl radicals/benzidine-type dimers), eroding yield.

**Net prediction.** The **turnover-limiting step of the cycle is the C–N bond-forming event at the copper-bound nitroso nitrogen / reductive elimination**, not transmetalation (transmetalation of arylboronates onto Cu(I)/Cu(III) is generally fast, and it can in any case be driven by using excess boronic acid and base, whereas the N-arylation step has no such remedy). Consequently, although EWGs hinder transmetalation, that penalty is small and can be compensated by stoichiometry, whereas the EWG acceleration of the nitrogen-centred coupling and of reductive elimination acts on the slow step. **Weighing the two effects, the facilitation of reductive elimination (and of aryl transfer to the electrophilic N) dominates, so electron-withdrawing substituents are predicted to enhance the reaction** — giving higher rates and yields for electron-poor arylboronic acids (4-CF₃, 4-F, 4-CN, 4-CO₂Me) than for electron-rich ones (4-OMe, 4-NMe₂), i.e. an overall **positive Hammett $\rho$**. The exception is at the extreme of electron deficiency (e.g. 2,4-(NO₂)₂, pentafluorophenyl), where protodeboronation and failure of transmetalation finally take over and yields fall again — so the expected rate/yield profile is volcano-shaped with its maximum on the electron-poor side.

## d) Key Cu–N intermediates, and why free ArNO is disfavoured

### d.1 Structures of the key intermediates

- **$\mathrm{L_nCu^{I}\!-\!Ar}$** — two-/three-coordinate aryl-Cu(I), $d^{10}$; the aryl nucleophile carrier.
- **$\mathrm{[L_nCu^{I}(Ar)(\kappa^1\text{-}NO_2)]^-}$ / $\mathrm{[L_nCu(Ar)(\kappa^1\text{-}ONO)]^-}$** — nitro/nitrito aryl-Cu(I) adduct; the activation complex in which nitrite is polarised and positioned.
- **$\mathrm{[L_nCu^{III}(\eta^2\text{-}N,O\text{-}ArNO)]}$ — the key intermediate.** Here the nitrosoarene is bound **side-on, $\eta^2$, through *both* the nitrogen and the oxygen atoms simultaneously**, so that Cu, N and O form a closed three-membered **metallacycle** (an azametallaoxirane / "metalla-oxaziridine"). The N–O bond is substantially lengthened (≈1.35–1.40 Å, i.e. reduced toward a single bond) and both N and O carry significant negative charge, so the ligand is best described as a reduced, dianionic *N,O*-chelate and the metal as **square-planar Cu(III), $d^8$**, with the ancillary N-donor ligand completing the coordination sphere. This $\eta^2$-N,O chelation is what (i) stabilises the high oxidation state, (ii) rigidly holds the nitrogen next to the metal's aryl-binding site, and (iii) renders the nitrogen strongly electrophilic.
- **$\mathrm{[L_nCu^{III}(Ar)(\eta^2\!/\kappa^1\text{-}ArNO)]}$** — the pre-reductive-elimination species after the second transmetalation: aryl and the N-bound nitroso ligand mutually *cis* on square-planar Cu(III).
- **$\mathrm{[L_nCu^{I}\!-\!N(Ar)_2]}$** — the copper(I) diarylamide formed by C–N reductive elimination with N–O cleavage; protonated to give $\mathrm{Ar_2NH}$.
- (Possible off-cycle/resting species: $\mathrm{[L_nCu^{III}(Ar)(N(Ar)O^-)]}$, i.e. a Cu(III)–*N*-aryl-*N*-oxide (nitroxide-like) intermediate, and Cu–O–B adducts.)

### d.2 Why C–N reductive elimination from the Cu(III)–$\eta^2$-nitroso intermediate outcompetes dissociation or decomposition

**Kinetic factors.**
- The second C–N bond-forming step is **intramolecular** within a rigid metallacycle: the migrating aryl group on Cu and the nitrogen of the $\eta^2$-ligand are held mutually *cis*, 2–2.5 Å apart, in a geometry already close to the transition state for migration. The entropy of activation is therefore small and favourable ($\Delta S^\ddagger \approx 0$), whereas any bimolecular alternative — dissociation of ArNO followed by re-encounter and attack by a boronate or by a second aryl-Cu — pays a large entropic penalty and is concentration-dependent (and under the dilute catalytic conditions, slow).
- Reductive elimination from **square-planar Cu(III)** is intrinsically very fast: Cu(III) is a strongly oxidising, electrophilic $d^8$ centre with a large thermodynamic driving force to return to the stable $d^{10}$ Cu(I) configuration, and C–N reductive eliminations from well-defined Cu(III) complexes are known to occur with very low barriers (often < 15 kcal mol⁻¹) even at or below room temperature. The barrier for **ligand dissociation** of the chelating $\eta^2$-N,O-ArNO ligand is comparatively high, because **two** bonds (Cu–N and Cu–O) must be broken simultaneously and, in doing so, the Cu(III) oxidation state would be left without the dianionic ligand that stabilises it — an electronically prohibitive demand. Chelate dissociation is thus both enthalpically and kinetically disfavoured relative to a low-barrier intramolecular coupling.
- **Decomposition pathways are outcompeted.** Possible decompositions — homolysis to aryl radical plus Cu(II), $\beta$-H elimination (impossible for aryl), N–N coupling of two nitroso units to azoxy/azo products, or protonolysis of the Cu–aryl bond to give arene — all have higher barriers than the preorganised C–N coupling: Cu(III)-aryl homolysis is slow because Cu(III)–C bonds are strong and the aryl radical is high in energy; bimolecular N–N coupling again requires dissociation or a second metal complex; and the aryl ligand on an electrophilic Cu(III) centre is only weakly basic and resists protonolysis on the timescale of reductive elimination.

**Thermodynamic factors.**
- The reductive elimination forms a strong **C(aryl)–N bond (~310–340 kJ mol⁻¹)** and converts $d^8$ Cu(III) into the much more stable $d^{10}$ Cu(I) closed shell — a large, irreversible driving force; the amide product is additionally stabilised by chelation/protonation, and the extruded oxygen is captured by boron as **B–O (~520 kJ mol⁻¹)**, making the whole sequence effectively irreversible.
- By contrast, **dissociation of ArNO** would be, at best, thermoneutral and would destroy the N,O chelate that stabilises the intermediate; it also leads to a dead end, since free nitrosoarene has no copper to activate it and no built-in oxygen sink.

### d.3 Why free nitrosoarene is not observed

Free ArNO is **not detected** in these reactions, and the explanation is kinetic rather than thermodynamic: **the intramolecular aryl transfer within the copper coordination sphere is simply much faster than dissociation of the ArNO ligand.** Quantitatively, $k_{\text{intramolecular\ C–N}} \gg k_{\text{dissociation}}$ because (i) the coupling is a unimolecular, preorganised, low-barrier process from a *cis*-disposed square-planar Cu(III) centre while dissociation requires rupture of a bidentate $\eta^2$-N,O chelate on a metal that needs that chelate to exist in its +3 state; (ii) the bidentate binding mode raises the effective concentration of the nitroso nitrogen at the metal's reactive site enormously relative to any solution-phase encounter; and (iii) even the small fraction that might dissociate re-coordinates faster than it escapes the solvent cage, because nitrosoarenes are excellent N,O-donors toward Cu.

Three further considerations reinforce the conclusion:

- **If free ArNO were generated, it would be diverted.** Free nitrosoarenes are highly reactive toward dimerisation (azodioxides), toward further reduction or oxidation (ArNH₂/ArNO₂), toward ene/Diels–Alder chemistry, and toward uncontrolled reaction with boronic acids giving azo and azoxy compounds, hydroxylamines and anilines. The clean, high-yielding formation of symmetric Ar₂NH — and the *absence* of azo/azoxy/nitro by-products — is itself strong evidence that the nitroso-level nitrogen never leaves copper.
- **Attempted independent generation.** Adding free ArNO as a substrate to the same catalytic mixture does not reproduce the reaction efficiently (or gives a different product distribution), consistent with the ArNO-on-copper, not free ArNO, being the competent intermediate; conversely, no induction period or ArNO build-up is observed spectroscopically.
- **Metal-sphere control of selectivity.** Keeping the nitrogen in the coordination sphere is also what guarantees the *symmetric* product and stops the reaction at the diarylamine rather than at the triarylamine: the nitrogen is arylated exactly twice, once by the aryl already on copper and once by a second boronate delivered to the metal, after which reductive elimination and protonolysis release the amine and liberate Cu(I).

## Summary

| Mechanistic element | Assignment |
|---|---|
| Cu oxidation states | Cu(I) → aryl-Cu(I) → Cu(III) (on nitrite incorporation/transformation) → Cu(I) (on reductive elimination) |
| Role of NaNO₂ | N-atom source, activated **inside** the Cu coordination sphere; stepwise deoxygenation (loss of O to boron) to a Cu-bound **nitroso-level** species |
| Role of ArB(OH)₂ (beyond Ar source) | **O-atom acceptor/reductant**: oxophilic boron abstracts the nitrite oxygens (B–O ≫ N–O), giving boroxine/borate and minor ArOH; this internal redox removes the need for an external oxidant |
| Stoichiometry | 2 ArB(OH)₂ : 1 NaNO₂ = **two distinct aryl transfer events** per nitrogen (plus extra boronic acid consumed as O-sink) |
| Key intermediate | **Cu(III)–$\eta^2$-(N,O)-nitrosoarene metallacycle** (side-on N *and* O coordination, square-planar $d^8$ Cu) |
| Site of second aryl transfer | the **nitrogen atom** of the $\eta^2$-bound nitroso ligand |
| Substituent effect | EWGs retard transmetalation but accelerate N-arylation/reductive elimination; the latter dominates, so **EWGs enhance the reaction** (positive $\rho$) |
| Why no free ArNO | intramolecular aryl transfer inside the Cu sphere is kinetically much faster than dissociation of the chelating $\eta^2$-ArNO ligand (which would also destabilise Cu(III)); free ArNO would in any case be diverted to azo/azoxy by-products, which are not seen |
| Turnover | C–N reductive elimination plus N–O cleavage gives $\mathrm{Cu^{I}\!-\!NAr_2}$; protonolysis releases $\mathrm{Ar_2NH}$ and **regenerates Cu(I)**, both nitrite oxygens having been delivered to boron |
