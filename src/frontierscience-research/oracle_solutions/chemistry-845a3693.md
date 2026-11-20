# A coarse-grained MD protocol (Martini 3 / GROMACS) to locate the CBD binding site(s) in the α7 nAChR

The experimental phenomenology constrains the design: CBD reaches the receptor **through a membrane pathway**, it is not acting via phosphorylation, it is not displaced by PAMs that bind the transmembrane domain, and its effect is compatible with **stabilisation of resting and/or desensitised states**. A lipophilic ligand that partitions into the bilayer and then finds a protein site is exactly the problem that unbiased, long-time-scale coarse-grained (CG) simulation with many free ligand copies solves well: the Martini 3 force field reproduces lipid/ligand partitioning thermodynamics, and the ~3–4 orders of magnitude of effective speed-up allow spontaneous, unbiased binding events to be observed many times, giving site occupancies and residence times rather than a single docked pose.

---

## 1. System preparation

### 1.1 Molecular model of the receptor

**Choice: experimentally resolved cryo-EM structures of the human α7 nAChR, in the two functional states relevant to the hypothesis.** Because CBD is proposed to stabilise the resting and/or desensitised conformations, the protocol must run on **both** end states and compare them:

- **PDB 7KOO** — human α7 in the **apo/resting (closed)** state, and **PDB 7KOQ** — human α7 in the **agonist(+PAM)-bound activated/open** state (same construct and pipeline, so the two are directly comparable).
- Equivalent alternative pair: **7EKI** (resting) and **7EKT** (desensitised) — the same logic applies; what matters is that one resting and one activated/desensitised structure of the same construct are simulated.

Homology modelling or an AlphaFold2 prediction would only be used for segments absent from these structures (see below), not as the primary model, since experimental α7 structures of defined functional state are available and the state assignment is the scientific crux.

**Model curation, with justification of each step:**

- **Sequence and construct check:** restore the wild-type human sequence (remove any thermostabilising/fusion mutations), keep the pentameric assembly and the five-fold subunit order, and verify the Cys-loop and the α7 vicinal-cysteine disulfides.
- **Missing residues must be rebuilt**, because gaps in the backbone break the CG elastic network and create artificial cavities that would be scored as spurious ligand sites. Short missing loops in the ECD and TMD are rebuilt with MODELLER loop refinement (or Rosetta remodel/SWISS-MODEL) using the companion-state structure as donor and checked for clashes. **However, the long intrinsically disordered intracellular segment between the MA and MX helices (the M3–M4/MX–MA disordered stretch) must *not* be modelled in**: it is unresolved because it is genuinely disordered, any model of it is arbitrary, and an invented ~100-residue coil restrained by an elastic network would both distort the TMD and act as a non-physical sticky surface for CBD. The MA and MX helices themselves are kept (they are resolved and they line the lipid-facing intracellular end of the TMD, a region where a lipophilic ligand may well bind); the disordered connector is left as a chain break with capped termini.
- **Protonation states and hydrogens:** add hydrogens and assign ionisation states at pH 7.4 using **PROPKA (via PDB2PQR)** and/or **`gmx pdb2gmx`**, inspecting histidines and any buried Asp/Glu individually. Although the production simulations are CG, this matters because (i) the all-atom reference simulations used for parameter optimisation and validation need correct protonation, and (ii) `martinize2` assigns bead charges from the atomistic residue state, so an incorrectly protonated residue carries the wrong CG charge.
- **Pre-CG validation:** MolProbity/Ramachandran and clash analysis; pore profile check with HOLE/CHAP to confirm the closed vs open gate; a short (100–200 ns) all-atom equilibration (CHARMM36m, POPC, TIP3P, 150 mM NaCl) of each state to relax the rebuilt loops — this atomistic trajectory is reused later as the reference for CG parameter optimisation and validation.

### 1.2 Coarse-graining the protein

- Convert each curated atomistic model to CG with the **`martinize2` (martinize.py) script**, parameterised with the **Martini 3** force field (`-ff martini3001`), with secondary structure assigned by DSSP from the equilibrated atomistic structure (`-dssp`).
- Because Martini's CG backbone does not maintain tertiary/quaternary structure on its own, apply an **elastic network to preserve protein integrity** (`-elastic` / ElNeDyn-style network: force constant ≈ 500–700 kJ mol⁻¹ nm⁻², lower and upper cut-offs ≈ 0.5 and 0.9 nm), applied **within** each subunit and across the subunit interfaces so the pentamer does not dissociate. The network is deliberately built on the *state-specific* structure so each simulation samples fluctuations around the resting or the activated/desensitised conformation; this is what makes the comparison of CBD binding between states meaningful (and it also means conformational transitions are, by construction, excluded — a limitation to revisit atomistically).
- Check the resulting CG model: bead count, net charge, intact disulfide/elastic links, and a short restrained CG equilibration showing a stable Cα-equivalent RMSD (< 0.3 nm) and preserved pore radius.

### 1.3 Membrane, box, solvent and ions

- **Insert the CG protein into a bilayer with `insane.py`** (`-f protein.pdb -o system.gro -p topol.top -x 16 -y 16 -z 18 ...`). A single asymmetric-composition-free but physiologically representative mixture is used, containing **a neutral (zwitterionic) phospholipid, an anionic phospholipid and cholesterol**, because α7 function and the TMD/lipid-facing pockets are cholesterol- and anionic-lipid-sensitive and because a pure POPC bilayer would bias the partitioning of a neutral lipophilic ligand:
  - **POPC : POPS : cholesterol = 60 : 10 : 30** (mol %), e.g. `-l POPC:6 -l POPS:1 -l CHOL:3` in both leaflets.
  - Box ≈ **16 × 16 × 18 nm** (xy large enough to keep ≥ 3 nm between periodic protein images and to host a statistically meaningful lipid shell; z large enough for ≥ 4 nm water slabs on both sides), giving roughly **1000–1200 lipids in total (~500–600 per leaflet)**.
- **Ligand copies in the box:** in addition to the lipids, the box is filled with **several free copies of CBD that do not start in contact with the receptor** — typically **20–30 CBD molecules** placed at random positions in the aqueous phase and/or in the bilayer at least 1.5–2 nm away from any protein bead (`gmx insert-molecules`, or `insane.py` with CBD added as a bilayer component). This is essential: (i) spontaneous, unbiased binding from the bulk/membrane is then observed many times per trajectory, giving statistics (occupancy, residence time, *k*_off) rather than one biased pose; (ii) the unbound copies provide the reference chemical potential/bulk concentration; (iii) the effective ligand concentration (20–30 copies in a ~16 × 16 × 18 nm box ≈ 10–20 mM, or ~2–3 mol % of the bilayer) is high enough to see binding on µs time scales while still well below the point where CBD would perturb bilayer structure (which is checked by monitoring area per lipid and order parameters against a protein-free control).
- **Solvation with a Martini water model:** solvate with the **standard (non-polarisable) Martini 3 regular water bead W** (≈ 4 water molecules per bead). Justification: the regular W model is the model against which all Martini 3 bead-type interactions — including the water/octanol partitioning data that define the C/N/P bead scale — were parameterised, so it is the model that gives the correct lipophilic partitioning free energies that this study depends on; it is also ~2–3× cheaper than polarisable water. The polarisable models (Martini 2 PW / Martini 3 refpol) would only be justified if explicit electrostatic screening gradients or strongly charged ligand transfer were central, which they are not for neutral CBD; antifreeze beads are unnecessary at 310 K with Martini 3 W.
- **Ions:** neutralise the system (the protein and POPS carry net charge) and add **physiological salt, 0.15 M NaCl** (Martini NA⁺/CL⁻ beads), using `gmx genion`/`insane.py -salt 0.15`.

### 1.4 Simulation settings and sampling

GROMACS 2023 with Martini 3: Verlet scheme, reaction-field electrostatics (ε_r = 15) with 1.1 nm cut-offs, 20 fs time step (after staged 2 → 5 → 10 → 20 fs equilibration), velocity-rescale thermostat at **310 K** (τ = 1.0 ps), semi-isotropic Parrinello–Rahman at 1 bar (τ = 12 ps, compressibility 3 × 10⁻⁴ bar⁻¹), LINCS/constraints on ring constructs. Energy minimisation → short position-restrained equilibration of the protein → 50–100 ns NPT equilibration → production. Sampling: **10–20 independent replicas × 20–30 µs** per receptor state (different initial ligand placements and velocity seeds), i.e. several hundred µs of aggregate CG time per state — necessary for converged residence-time statistics. A ligand-free control and a protein-free CBD/bilayer control are run for bilayer-property validation.

---

## 2. Ligand parameterisation and validation

### 2.1 Obtaining the 3D structure of CBD

Download the experimental/curated 3D structure of cannabidiol from a public database (PubChem CID 644019 / DrugBank / ChEBI SDF, or the ligand geometry from a CBD-containing crystal structure in the CSD/PDB). Alternatively, build it from the canonical SMILES

`CCCCCc1cc(O)c(C2CC(C)=CC[C@@H]2C(=C)C)c(O)c1`

with RDKit/OpenBabel (ETKDG embedding), setting the correct (1*R*,6*R*)-*trans* stereochemistry of the terpene ring, then optimise the geometry at the **B3LYP-D3/6-31G\*\*** level (or at least MMFF94 followed by semi-empirical GFN2-xTB) and generate a conformer ensemble (CREST/RDKit) to capture the two accessible aryl–terpene dihedral families. The chosen conformer is used to build the all-atom reference model, parameterised with **CGenFF or GAFF2 with AM1-BCC/RESP charges**, and then run in an atomistic reference simulation (CBD in water, and CBD in a POPC bilayer) — this all-atom trajectory is the reference against which the CG model is optimised and validated.

### 2.2 Carbon numbering convention

Following the numbering of Atalay et al. (2020): the **monoterpene (cyclohexene) moiety carries carbons C1–C10** (ring C1–C6, with C1 bearing the aryl substituent, the C2=C3 trisubstituted alkene, the C7 methyl on C3, and the isopropenyl group C8(=C9)–C10 on C6); the **resorcinol (aromatic) ring carries the primed carbons C1′–C6′** (C1′ bonded to terpene C1, hydroxyls on C2′ and C6′, the pentyl chain on C4′); and the ***n*-pentyl side chain carries the double-primed carbons C1″–C5″** (C1″ benzylic, C5″ terminal).

### 2.3 Coarse-grained mapping (Martini 3)

CBD has 23 heavy atoms (21 C + 2 O). It is mapped onto **8 beads**, using small (S, ~3 heavy atoms) and tiny (T, ~2 heavy atoms) beads for the two rings, as Martini 3 prescribes for ring-containing fragments, and one regular (R, 4-to-1) bead for the flexible alkyl tail:

| Bead | Type | Atoms mapped | Rationale |
|---|---|---|---|
| **AR1** | **SN6** | C1′, C2′ + the 2′-**OH** oxygen | **Aromatic hydroxyl group → SN6**: an aromatic C–OH fragment is a hydrogen-bond donor *and* acceptor of phenol-like polarity; SN6 reproduces the phenol water/octanol partitioning and its H-bonding with lipid phosphates/water |
| **AR2** | **SN6** | C5′, C6′ + the 6′-**OH** oxygen | second **aromatic hydroxyl → SN6** (the resorcinol is symmetric about C4′) |
| **AR3** | **SC4** | C3′, C4′ + C1″ (the benzylic carbon) | **methyl(alkyl)-substituted aromatic carbon fragment → SC4**: a toluene-like apolar aromatic fragment |
| **PEN** | **C1** | C2″, C3″, C4″, C5″ | **aliphatic (alkyl) chain → regular C1 bead** — the standard Martini 3 4-to-1 apolar alkane bead |
| **TP1** | **SC4** | C2, C3 + the C7 methyl | first **isoprene unit**: the methyl-substituted trisubstituted alkene → **SC4** (apolar, slightly more polarisable than a pure alkane) |
| **TP2** | **TC3** | C4, C5 | saturated CH₂–CH₂ segment of the terpene ring → **tiny apolar TC3** bead, needed to keep the six-membered ring geometry with three beads |
| **TP3** | **TC3** | C6, C1 | ring carbons bearing the isopropenyl (C6) and the aryl (C1) links → **TC3**; this bead carries the bonds to AR1 and to IPR |
| **IPR** | **SC4** | C8, C9, C10 | second **isoprene unit**: the isopropenyl (prop-1-en-2-yl) group → **SC4** |

So, in summary: **the alkyl (pentyl) chain is a C1 bead; the two aromatic hydroxyl groups are SN6 beads; the methyl/alkyl-substituted aromatic carbons are an SC4 bead; and the two isoprene units of the terpene moiety are described by a combination of SC4 and TC3 beads** (SC4 for the methylated alkene and for the isopropenyl, TC3 for the two saturated ring segments).

Topology construction: each ring is built as a triangle of beads held by **constraints** (aromatic ring: AR1–AR2–AR3, constraint lengths ≈ 0.29–0.32 nm; terpene ring: TP1–TP2–TP3, ≈ 0.33–0.37 nm), with the inter-ring bond AR1–TP3 and an improper/angle set controlling the near-orthogonal aryl–terpene dihedral and the equatorial orientation of IPR; exclusions within each ring, and reduced-σ ring-bead parameters as per the Martini 3 ring guidelines. If ring-bead crowding causes instabilities, two of the ring beads can be converted to virtual sites constructed from the remaining beads.

### 2.4 Validation of the CG parameters

**(a) Bonded parameters — optimise against an atomistic reference.** Run the all-atom CBD simulations (in water and in a POPC bilayer, ≥ 500 ns each, CHARMM36/CGenFF or GAFF2), map the atomistic trajectory onto the CG beads, and extract the target distributions of all bonds, angles and dihedrals. The CG bonded parameters are then **optimised against this atomistic reference with an automated tool such as SwarmCG** (particle-swarm optimisation of bonded terms against mapped AA distributions, which also reports the Earth-mover/Wasserstein mismatch per term) **or PyCGTool**. As an equivalent alternative they can be optimised **manually and iteratively using Boltzmann inversion**: for each degree of freedom take the mapped AA probability distribution $P^{\mathrm{AA}}(x)$ and set

$$V_{\text{CG}}^{(0)}(x) = -k_\mathrm{B}T\ln\frac{P^{\mathrm{AA}}(x)}{J(x)}$$

(with the Jacobian $J = x^2$ for bonds and $\sin\theta$ for angles), fit it to the Martini functional forms (harmonic bond/angle, RB or cosine dihedral), run the CG model, compare $P^{\mathrm{CG}}(x)$ with $P^{\mathrm{AA}}(x)$ and update by **iterative Boltzmann inversion**,

$$V^{(n+1)}(x) = V^{(n)}(x) + \alpha\,k_\mathrm{B}T\ln\frac{P^{(n)}_{\mathrm{CG}}(x)}{P^{\mathrm{AA}}(x)},\qquad \alpha \approx 0.2\text{–}1,$$

until all distributions agree (and the ring geometry/radius of gyration of the mapped AA and CG models match). Rigid ring distances are converted to constraints.

**(b) Non-bonded parameters — validate the partitioning thermodynamics.** Two independent, quantitative tests:

1. **Water/octanol partition coefficient.** Compute the transfer free energy of the CG CBD between a water slab and a 1-octanol slab (or by double decoupling/thermodynamic integration in each solvent) and convert to a partition coefficient,

$$\log P_{\text{ow}} = -\frac{\Delta G_{\mathrm{w}\rightarrow\mathrm{o}}}{2.303\,RT}$$

then **compare it with the experimental value for CBD** (experimental log *P* ≈ 6.3, i.e. $\Delta G_{\mathrm{w\rightarrow o}} \approx -36$ kJ mol⁻¹ at 310 K). Bead types are adjusted (e.g. SN6 ↔ SN4a/SP1 for the hydroxyls, SC4 ↔ SC3/TC4 for the apolar fragments) until the computed log *P* reproduces the experimental one within ~0.5 log unit; the same check is repeated for water/hexadecane if data permit. This is the decisive test for a lipophilic ligand, because the whole study hinges on CBD partitioning correctly between water, bilayer and protein pockets.
2. **Membrane-permeation PMF, CG vs all-atom.** Since this is a membrane-containing system, compute the **potential of mean force for CBD permeation across the bilayer** — umbrella sampling along the bilayer normal *z* (windows every 0.1 nm from bulk water through the headgroups to the bilayer midplane, 0.5–1 µs/window CG and 50–100 ns/window AA, force constant ~1000 kJ mol⁻¹ nm⁻², unbiased with WHAM/MBAR) — for **both the CG and the atomistic model, and compare them**. The depth and position of the interfacial minimum, the midplane barrier and the water→membrane transfer free energy must agree within ~2–5 kJ mol⁻¹; a CG model that over- or under-stabilises the headgroup region would produce false positives/negatives for lipid-facing protein sites. Additional checks: no CBD-induced artefacts in area per lipid, bilayer thickness or lipid order parameters relative to the atomistic reference, and CBD self-aggregation behaviour comparable between CG and AA.

---

## 3. Analysis

### 3.1 Trajectory preparation (transformations before analysis)

- **Correct the periodic-boundary artefacts and fit the trajectories**, which is mandatory before any contact or density analysis: make molecules whole and remove jumps (`gmx trjconv -pbc whole`, then `-pbc nojump`), re-centre the system on the protein and wrap the membrane and ligands into a consistent representation (`gmx trjconv -pbc mol -center -ur compact`), and finally **fit the trajectory onto the protein backbone (BB beads) with rotational + translational least-squares fitting** (`gmx trjconv -fit rot+trans`) so the receptor frame is fixed and ligand positions are directly comparable across frames and replicas. For membrane systems, re-centre on the bilayer for density profiles (`gmx trjconv -center` on the lipid group) and check with `gmx trjconv -pbc atom` images that no ligand or lipid is split across the boundary. Downsample to 0.5–1 ns/frame for contact analysis; keep the full resolution for residence-time/koff fits.

### 3.2 Software and features analysed

- **Binding-site identification: PyLipID** (originally written for lipids, directly applicable to any small CG molecule) run on the fitted trajectories with the standard **dual cut-off scheme (lower 0.475 nm, upper 0.8 nm)** to avoid rattling-induced fragmentation of contacts. PyLipID yields, per residue: contact occupancy (% of frames in contact), duration, number of binding events, and the survival-function fit of contact durations giving **residence times and *k*_off**; it then defines **binding sites** by community (Louvain) analysis of the residue–residue interaction network, ranks them by residence time/occupancy, computes per-site occupancies and bound-ligand poses (representative pose by density maximum), and provides bootstrapped errors. Sites are accepted only if they appear in independent replicas and in both leaflets/all five subunits where symmetry permits.
- **Manual/complementary contact analysis** (used as a cross-check, with the criteria stated explicitly): with MDAnalysis/`gmx mindist`, a CBD bead and a protein bead are "in contact" if their distance is **< 0.6 nm**; a residue's occupancy is the fraction of frames with ≥ 1 such contact; a binding event is a continuous contact lasting > 10 ns (with a 2 ns tolerance for brief excursions). Ligand centre-of-mass positions in the fitted protein frame are then clustered with **DBSCAN** (ε = 0.5 nm, min_samples set from the sampling rate) and each cluster with total occupancy above a threshold is declared a candidate site; 3D occupancy/density maps (`gmx densmap`, VolMap, MDAnalysis `DensityAnalysis`) are generated for visual confirmation and figure-making.
- **Other features analysed:** CBD partition depth and orientation distributions along *z* (insertion depth of the resorcinol vs terpene end), per-site interaction fingerprints (which residues, which bead types, H-bond-capable SN6 contacts with polar residues/phosphates), lipid and cholesterol competition at each site (occupancies of POPC/POPS/CHOL at the same residues, since a site that merely displaces cholesterol is informative), protein structural stability (RMSD/RMSF of the elastic-network model, pore radius via HOLE/CHAP on backmapped frames, subunit interface distances), bilayer properties (area per lipid, thickness, order parameters) as a control, and **comparison of site occupancies and residence times between the resting (7KOO/7EKI) and the activated–desensitised (7KOQ/7EKT) structures**, which is the test of state-dependent binding.
- Convergence: occupancy/residence time as a function of simulated time and of the number of replicas; bootstrapping across replicas; binding-event counts per site (≥ 20–30 events needed for a meaningful *k*_off).

---

## 4. Expected outcomes and suggested downstream tasks

### 4.1 Expected outcomes

- **More than one candidate binding site is expected, and that is the realistic expectation for a CG prediction**: Martini 3 captures partitioning and shape complementarity but not the chemical detail of a pocket, so the output should be read as a *ranked set of hypotheses* (by occupancy and residence time) rather than a single, precise pose. Typically 2–4 sites will survive the replica-consistency filter, possibly with different rankings in the two receptor states.
- **Given CBD's strongly lipophilic character (log *P* ≈ 6.3) and the experimental evidence that it acts through a membrane pathway, CBD is expected to bind the transmembrane domain** — at lipid-exposed pockets rather than at the orthosteric ECD site. The most likely candidates are the **intrasubunit TMD cavity lined by M1/M2/M3/M4** (the pocket exploited by TMD-binding α7 PAMs such as PNU-120596 and by ivermectin-like modulators), the **inter-subunit TMD groove between M4 of one subunit and M1/M3 of the neighbour**, the **cholesterol-binding/lipid-facing grooves around M4**, and the lipid–water interfacial region near the **MX/MA helices** at the intracellular end of the TMD. A site whose occupancy and residence time differ between the resting and the activated/desensitised structures would directly rationalise the experimental conclusion that CBD stabilises resting/desensitised states and cannot be overcome by PAMs if it shares or allosterically couples to the PAM pocket.
- Quantitative deliverables: per-site residence times and *k*_off, per-residue interaction fingerprints (the residues to mutate), representative bound poses, and the state dependence of all of these.

### 4.2 Suggested downstream tasks

- **Atomistic (all-atom) simulations of the predicted complexes**, obtained by **backmapping** the CG poses (`backward.py`, CG2AT2) into CHARMM36m/POPC-POPS-cholesterol systems, to **refine and analyse the interactions and the stability of each predicted binding site** at chemical resolution: 3–5 × 500 ns–1 µs per site, monitoring pose RMSD, specific hydrogen bonds from the resorcinol hydroxyls, residue contact lifetimes, and whether the ligand remains bound; this step is essential because the CG model cannot resolve H-bond geometry, aromatic stacking or the precise shape of the pocket.
- **Free-energy quantification:** absolute binding free energies at the surviving sites (alchemical double decoupling or restraint-based ABFE at the atomistic level; CG-level PMFs of ligand extraction as a cheaper screen), plus ΔΔG for the residues chosen for mutagenesis.
- **Mechanistic follow-up:** compare the ligand's effect on the gating-relevant degrees of freedom (M2 9′ gate radius, M2–M3 linker, pore hydration) in the resting vs activated/desensitised models, and, if a conformational mechanism is implicated, construct the gating free-energy landscape with enhanced sampling.
- **Experimental validation of the predicted sites:** site-directed mutagenesis of the top-ranked contact residues followed by **single-channel and whole-cell electrophysiology** (loss of CBD inhibition / rightward shift in IC₅₀ in the mutants, with ACh responses preserved), chimeric/concatemeric constructs to test subunit-interface sites, **photoaffinity labelling or photo-crosslinking with a diazirine/benzophenone CBD analogue followed by MS identification** of the labelled residues, competition with TMD-binding PAMs (PNU-120596) and with cholesterol depletion/loading, thermal-shift or radioligand/fluorescence binding assays on purified receptor in defined lipid nanodiscs, and ultimately **cryo-EM of α7 in the presence of CBD** to visualise the site; calcium-imaging assays in cells expressing the mutant receptors would confirm that the predicted site also accounts for the CBD-induced decrease in α7-mediated calcium responses.
