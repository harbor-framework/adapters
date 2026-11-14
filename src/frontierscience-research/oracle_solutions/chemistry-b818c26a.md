# Fatty acids and beer foam stability

## 0. Physical basis of lipid-induced foam collapse

Beer foam is a protein-stabilised, air–liquid dispersion. Its lamellae are held together by a viscoelastic interfacial film built from surface-active barley polypeptides — principally **LTP1 (lipid transfer protein 1)**, **protein Z** and hordein-derived hydrophobic polypeptides — cross-linked laterally by hydrophobic protein–protein contacts and by complexation with iso-$\alpha$-acids (and, in part, by polyphenol bridging and metal ions). Foam collapses when that cohesive film is disrupted.

Free fatty acids and other small amphiphiles destroy foam through two coupled mechanisms:

1. **Competitive displacement at the air–water interface.** Small amphiphiles diffuse to and adsorb at the interface faster than large proteins and lower the interfacial tension locally, but they cannot form a viscoelastic network. They therefore replace a cohesive protein film with a mobile, low-viscosity surfactant film (an "orogenic displacement" process), which cannot resist drainage, Laplace-driven disproportionation or film rupture.
2. **Penetration into and plasticisation of the protein film.** The hydrocarbon tail inserts between the hydrophobic faces of the adsorbed polypeptides, breaking the protein–protein hydrophobic contacts that give the film its elasticity, and also competes for the hydrophobic binding cavity of LTP1 (its physiological ligand pocket), neutralising LTP1's foam-positive role.

Both mechanisms scale with **interfacial activity**, i.e. with the lipid's tendency to leave the bulk and sit in/at the lamella. For a homologous series of fatty acids this is governed by hydrophobicity:

$$\Delta G^{\circ}_{\text{ads}} \;\propto\; -n_{\mathrm{C}} \qquad\text{(roughly }\sim -3\ \text{kJ mol}^{-1}\text{ per CH}_2\text{)},\qquad \log K_{\text{ow}} \uparrow \text{ with } n_{\mathrm{C}},\qquad \text{aqueous solubility} \downarrow \text{ with } n_{\mathrm{C}}$$

So the key structure–activity rules are:

- **Chain length.** Each added methylene increases the partition coefficient into the interface by roughly a factor of 3 and decreases aqueous solubility by about an order of magnitude per two carbons. **Long-chain fatty acids (LCFA, C16–C18) are therefore able to penetrate and destabilise the protein film in beer foam far better than medium-chain fatty acids**: at the ~2 µg mL$^{-1}$ dose used here they are essentially quantitatively partitioned into the lamellar interface (indeed they are above or near their solubility limit), so the whole dose acts on the film. **Medium-chain fatty acids are generally the least destructive to beer foam, and the reason is solubility**: being much more water-soluble, they remain largely dissolved in the bulk beer, their interfacial excess is small, and they never reach the surface coverage needed to displace protein.
- **Unsaturation at constant chain length.** Each *cis* double bond kinks the chain, raises aqueous solubility, lowers $\log K_{\text{ow}}$ (stearic $\log P \approx 8.2$; linoleic $\approx 7.1$) and prevents tight, straight-chain packing in the interfacial film. The $\pi$ system also makes the chain slightly more polarisable/hydrophilic. Hence **there is a slightly diminished foam-destabilising effect for a polyunsaturated fatty acid relative to a saturated one of equal chain length**: linoleic acid (C18:2) is a little less damaging than stearic acid (C18:0), although — still being an 18-carbon species — it remains more damaging than a 16-carbon saturated acid.

## 1. Ranking of the five fatty acids (most → least destructive)

| Rank | Fatty acid | Structure | Basis |
|---|---|---|---|
| **1 (most destructive)** | **Stearic acid** | C18:0, straight saturated LCFA | Longest, most hydrophobic, lowest solubility; maximal interfacial partitioning and the straight chain packs tightly into (and most effectively disrupts) the hydrophobic core of the protein film |
| **2** | **Linoleic acid** | C18:2 (9*Z*,12*Z*) | Same C18 length, so still strongly interfacially active and highly film-penetrating; slightly diminished relative to stearic because the two *cis* double bonds raise hydrophilicity/solubility and spoil tight chain packing |
| **3** | **Palmitic acid** | C16:0 | Saturated LCFA, but two carbons shorter than stearic → ~an order of magnitude more soluble and a smaller interfacial driving force, so less film penetration than either C18 species |
| **4** | **Caproic acid** | C6:0, short-chain | Weakly surface-active overall, but its very small molecular volume lets it diffuse to and insert rapidly into the interfacial film, where it behaves as a short-chain co-surfactant/plasticiser that loosens protein–protein hydrophobic contacts; it is also the most acidic/most mobile of the set, so a measurable (if modest) foam penalty remains |
| **5 (least destructive)** | **Capric acid** | C10:0, medium-chain | The archetypal MCFA: freely soluble in beer at 2 µg mL$^{-1}$, so it stays in the bulk (and is readily complexed/solubilised by beer polypeptides and micellar/colloidal material) rather than accumulating at the interface. It is simultaneously too hydrophilic to partition into the lamella like an LCFA and too bulky/too strongly solvated to insert into the dense protein network the way the C6 acid does — hence the smallest effect of all |

**Ranking: stearic acid > linoleic acid > palmitic acid > caproic acid > capric acid.**

Summary of the governing logic: destructiveness is dominated by chain length (long chain ≫ medium chain, because LCFAs penetrate and destabilise the protein film whereas MCFAs stay dissolved); within a given chain length, polyunsaturation slightly reduces the effect because of the increased hydrophilicity of the kinked, double-bond-containing chain; and the medium-chain member of the series (capric acid) is the least destructive of all on solubility grounds.

## 2. Glyceryl monooleate versus glyceryl dioleate

Both are *non-ionic amphiphiles* built from oleic acid (C18:1) esterified to glycerol:

- **Glyceryl monooleate (GMO)**: one oleoyl chain + two free hydroxyls → polar head of appreciable hydrophilicity (HLB ≈ 3.5–4).
- **Glyceryl dioleate (GDO)**: two oleoyl chains + one free hydroxyl → twice the hydrocarbon volume and only one-third of the hydroxyl complement (HLB ≈ 1.5–2).

**Expected effect: glyceryl dioleate would be more destructive to beer foam than glyceryl monooleate, because of their difference in hydrophobicity, even though both are amphiphilic.** Reasoning:

- The second oleoyl chain roughly doubles the hydrophobic surface while removing a hydrogen-bonding hydroxyl, so GDO's partition coefficient into the lamellar interface/hydrophobic film interior is orders of magnitude larger; its aqueous solubility is negligible. It therefore concentrates in the foam film, where its bulky two-tailed, low-HLB geometry (a cone favouring inverse curvature) is incompatible with a flat, cohesive protein film: it promotes film thinning, lateral de-cohesion and rupture, and it will also compete for the LTP1 lipid-binding cavity.
- GMO, by contrast, is a classic *amphiphilic emulsifier/foam-compatible* lipid: it is far more hydrophilic, partly stays in the bulk or at the interface with its diol head hydrated, and its single chain can be accommodated at the interface while still permitting protein–protein association. Its net effect on foam is therefore much smaller — a modest destabilisation at most (and in practice it can be close to neutral, because its hydroxylated head can participate in the hydrogen-bonded/hydrated interfacial layer).

Both are less damaging per mole than the free LCFAs of equal chain length would be, because neither carries a free carboxylate head; but the comparison asked for is clear: **GDO ≫ GMO in foam destruction, driven by hydrophobicity.**

## 3. Designing a beer with as little foam as possible

**Formulate the beer with long-chain fatty acids (LCFA, e.g. C16–C18 such as palmitic, stearic, oleic/linoleic acids).**

Justification: LCFAs are the class with the highest interfacial activity and lowest aqueous solubility, so even trace additions (µg mL$^{-1}$) partition essentially completely into the air–liquid lamellae, displace and penetrate the LTP1/protein Z/hordein film, strip the proteins of their cohesive hydrophobic contacts and sequester the hydrophobic cavity of LTP1. The result is the fastest foam collapse and the lowest foam formation and head retention per unit mass added. Short- and medium-chain fatty acids would be a poor choice for this goal, since their much higher water solubility keeps them in the bulk liquid and leaves the protein film largely intact. (In practice one would combine the LCFA addition with two-tailed, very hydrophobic amphiphiles such as glyceryl dioleate for the same reason.)

## Final answers

1. **Most → least destructive: stearic acid (C18:0) > linoleic acid (C18:2) > palmitic acid (C16:0) > caproic acid (C6:0) > capric acid (C10:0)** — long-chain fatty acids penetrate and destabilise the foam protein film much more effectively than medium-chain acids; medium-chain acids are the least destructive because of their higher aqueous solubility; and a polyunsaturated acid of equal chain length is slightly less destructive than its saturated analogue because of its greater hydrophilicity.
2. **Glyceryl dioleate is more destructive to beer foam than glyceryl monooleate**, despite both being amphiphilic, because the second oleoyl chain (and the loss of a hydroxyl) makes it far more hydrophobic and therefore far more strongly film-penetrating.
3. To minimise foam generation, formulate with the **long-chain fatty acid** class.
