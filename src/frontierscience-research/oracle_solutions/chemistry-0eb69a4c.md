# Ion-pair-directed Ir-catalysed *para*-selective C–H borylation of 2-chlorobenzylsulfonate tetrabutylammonium salt

## 1. The substrate and its numbering

The substrate is the tetrabutylammonium salt of 2-chlorobenzylsulfonate, i.e. the anion $\mathrm{2\text{-}Cl\text{-}C_6H_4\text{-}CH_2\text{-}SO_3^-}$ paired with $\mathrm{(n\text{-}Bu)_4N^+}$.

SMILES: `[O-]S(=O)(=O)Cc1ccccc1Cl.CCCC[N+](CCCC)(CCCC)CCCC`

**Numbering.** In 2-chlorobenzylsulfonate tetrabutylammonium salt the numbering is as follows: **the number 1 is the carbon of the benzene/aryl ring** — specifically the ring carbon that bears the benzylic $\mathrm{CH_2SO_3^-}$ group, which is the point of attachment of the parent "benzyl" fragment. **The next number, 2, is the carbon bearing the chloro substituent on the benzene ring**, and **the numbering then continues around the aryl/benzene ring in the anticlockwise manner**: C3, C4, C5, C6.

With this numbering the relationships are:

| Position | Relationship to C1 (CH$_2$SO$_3^-$) | Relationship to C2 (Cl) |
|---|---|---|
| C2 | *ortho* | — (substituted) |
| C3 | *meta* | *ortho* |
| C4 | **para** | **meta** |
| C5 | *meta* | *para* |
| C6 | *ortho* | *meta* |

So C4 is *para* to the benzylsulfonate group and *meta* to the chlorine, while C5 is *meta* to the benzylsulfonate group and *para* to the chlorine. These two positions, C4 and C5, are the only ones that are not flanked by a substituent, and distinguishing them is the whole problem of this methodology.

## 2. Reaction conditions for the iridium-catalysed borylation

A generic Ir-catalysed aromatic C–H borylation is run with:

- **Catalyst (Ir source): $[\mathrm{Ir(OMe)cod}]_2$** — di-µ-methoxybis(1,5-cyclooctadiene)diiridium(I), $[\mathrm{Ir(OMe)(cod)}]_2$, typically 1.5–3 mol % Ir;
- **Ligand: 4,4′-di-*tert*-butyl-2,2′-bipyridine (dtbpy)** or **3,4,7,8-tetramethyl-1,10-phenanthroline (tmphen)**, 3–6 mol % (one bidentate N,N-ligand per Ir);
- **Boron partner: bis(pinacolato)diboron, $\mathrm{B_2pin_2}$** (1–2 equiv; HBpin can be used as a co-reagent);
- Solvent such as THF, MTBE, cyclohexane or heptane, 25–80 °C, under inert atmosphere; the substrate is used as its tetraalkylammonium salt so that it is soluble in the organic medium.

The active species is the 16-electron tris(boryl) complex **$\mathrm{Ir(dtbpy)(Bpin)_3}$** (or the tmphen analogue), which performs oxidative addition of the arene C–H bond and then C–B reductive elimination. The key mechanistic feature for selectivity is that this iridium–boryl species is **sterically, not electronically, controlled**: the three bulky Bpin groups on iridium make the metal extremely sensitive to steric congestion at the carbon being attacked. Consequently Ir-catalysed borylation essentially never occurs *ortho* to a substituent, and in a 1,2-disubstituted arene only the two positions remote from both substituents are competent.

## 3. Site of borylation and the reason

### 3.1 Which positions are eliminated by ordinary steric control

- **C2** is already substituted (Cl).
- **C6** is *ortho* to the bulky $\mathrm{CH_2SO_3^-}$ group $\rightarrow$ blocked.
- **C3** is *ortho* to the chlorine $\rightarrow$ blocked.

That leaves **C4** and **C5**. Both are equally unhindered on the arene itself, and this is exactly why traditional routes to this type of product give an essentially **equimolar mixture of the *meta*- and *para*-selective products**: the intrinsic steric and electronic biases of a 1,2-disubstituted ring cannot discriminate between the two remaining C–H bonds, which differ only in being remote from, or adjacent-but-one to, the side chain.

### 3.2 The ion-pair steric shield: why C4 wins

The sulfonate group is anionic, so in the organic medium it does not exist as a naked anion: the **arylsulfonate/benzylsulfonate anion is electrostatically bound to the tetrabutylammonium cation**, forming a tight, contact ion pair held together purely by the Coulombic attraction between the $\mathrm{SO_3^-}$ head group and the $\mathrm{(n\text{-}Bu)_4N^+}$ centre. It is important to be clear that **this electrostatic pairing has nothing to do with the Ir–L bond or any pairing/coordination at the iridium centre**: the ammonium cation is not a ligand, it does not bind iridium, and it does not modify the Ir–L (Ir–dtbpy/Ir–tmphen) interaction in any way. The cation simply sits on the substrate's anionic tether.

Because the $\mathrm{(n\text{-}Bu)_4N^+}$ ion is anchored on the sulfonate only two atoms away from the ring (via the $\mathrm{CH_2}$ linker), its **four long *n*-butyl chains drape back over the face and edge of the arene adjacent to the side chain**. The ammonium therefore acts as a **non-covalent, electrostatically delivered steric shield** that covers the positions nearest the tether. Operationally:

- the shield covers the *ortho* region (C6) — already blocked anyway — and, decisively, it extends over the ***meta*** position relative to the aryl/benzyl attachment, i.e. over **C5**;
- the only position left open, uncovered by the alkyl chains and not *ortho* to either substituent, is **C4**.

**Therefore the long chain of the ammonium acts like a steric shield and blocks the *meta* (to the aryl/benzyl group) position, C5, so that the only open and available position for the borylation reaction is the C4 position — *meta* to the chloro substituent and *para* to the benzyl(sulfonate) substituent.**

### 3.3 Final answer to "where and why"

**Borylation takes place at C4**, giving the tetrabutylammonium salt of 4-(pinacolboryl)-2-chlorobenzylsulfonate:

$$\mathrm{(n\text{-}Bu)_4N^+}\ \ \mathrm{[2\text{-}Cl\text{-}4\text{-}(Bpin)\text{-}C_6H_3\text{-}CH_2SO_3]^-}$$

SMILES: `[O-]S(=O)(=O)Cc1ccc(cc1Cl)B1OC(C)(C)C(C)(C)O1` (with Bu$_4$N$^+$ as counter-cation).

The reason is the combination of (i) the normal steric control of the $\mathrm{Ir(dtbpy)(Bpin)_3}$ catalyst, which excludes the positions *ortho* to Cl and to the side chain (C3, C6, and substituted C2), and (ii) the electrostatically bound, conformationally mobile $\mathrm{(n\text{-}Bu)_4N^+}$ cation, whose long *n*-butyl chains shield the *meta* position C5. C4, the *para* position with respect to the benzylsulfonate group, is the single remaining accessible C–H bond, so what would otherwise be a ~1:1 *meta*/*para* mixture becomes highly *para*-selective. Again, the selectivity originates entirely from the substrate-bound ion pair and not from anything happening at the Ir–ligand bond.

## 4. Influence of the carbon chain length of the ammonium counter-cation

The magnitude of the shielding — and therefore the selectivity — is directly governed by how much space the alkyl chains of the ammonium occupy near the ring:

**Selectivity increases with increasing carbon chain length of the ammonium cation.**

Thus, for a series of symmetrical tetraalkylammonium counter-cations the *para*:*meta* (C4:C5) ratio rises in the order

$$\mathrm{Me_4N^+ < Et_4N^+ < \mathit{n}\text{-}Pr_4N^+ < \mathit{n}\text{-}Bu_4N^+ < \mathit{n}\text{-}Hex_4N^+ < \mathit{n}\text{-}Oct_4N^+}$$

- With **short chains ($\mathrm{Me_4N^+}$, $\mathrm{Et_4N^+}$)** the cation presents only a small volume around the sulfonate; C5 remains largely exposed, and the C4:C5 ratio stays close to the unselective, statistical ~1:1 value obtained in conventional borylations.
- Lengthening the chains to **$\mathrm{Bu_4N^+}$ and beyond** progressively increases the time-averaged occupancy of the space over C5 (longer chains sweep a larger conformational volume and can fold back along the arene), so the effective steric blockade of the *meta* position grows and *para*(C4) selectivity rises markedly.
- The longest chains give the highest *para*:*meta* ratios, so the practical choice is a long-chain salt: $\mathrm{(n\text{-}Bu)_4N^+}$ already delivers strongly *para*-selective borylation, and still longer chains (*n*-hexyl, *n*-octyl) shield C5 even more completely.

The trend is itself the clearest evidence for the proposed mechanism: because the only variable changed is the size of a non-coordinating counter-ion, the selectivity cannot be arising from a change at iridium — it must come from the substrate-bound electrostatic shield.

## 5. Scope: other substrates that can be borylated *para*-selectively by this methodology

The only structural requirement is an **anionic sulfur-based tether** capable of forming the electrostatic ion pair with the tetraalkylammonium cation. Accordingly, the methodology extends to **different ring systems and tether types, including benzylsulfonates, arylsulfonates, benzylsulfates, arylsulfates, arylsulfamates and benzylsulfamates** (used as their $\mathrm{R_4N^+}$ salts):

- **arylsulfonates**, $\mathrm{Ar\text{-}SO_3^-\,R_4N^+}$ (tether attached directly to the ring);
- **benzylsulfonates**, $\mathrm{Ar\text{-}CH_2SO_3^-\,R_4N^+}$ (the present case);
- **arylsulfates**, $\mathrm{Ar\text{-}OSO_3^-\,R_4N^+}$;
- **benzylsulfates**, $\mathrm{Ar\text{-}CH_2OSO_3^-\,R_4N^+}$;
- **arylsulfamates**, $\mathrm{Ar\text{-}N(R)SO_3^-\,R_4N^+}$;
- **benzylsulfamates**, $\mathrm{Ar\text{-}CH_2N(R)SO_3^-\,R_4N^+}$.

In every case the anionic $\mathrm{SO_3^-}$ head group recruits the bulky ammonium to a defined position relative to the ring, shielding the *ortho*/*meta* region and leaving the *para* C–H exposed. (Neutral analogues — esters, amides, alkyl sulfides, or free sulfonic acids under non-ion-pairing conditions — do not work, because without the charge there is no electrostatic anchoring of the shield.)

**Variation of the second (C2) substituent** is likewise tolerated and is in fact how the electronic contribution is tested: the chloro substituent at C2 **can also be changed to trifluoromethyl ($\mathrm{CF_3}$), Br, $\mathrm{OCF_3}$ or $\mathrm{OCH_3}$** (and similar groups) in order to probe electronic effects as well on the selectivity of *para* borylation. These substituents span a wide range of inductive and resonance character ($\mathrm{CF_3}$, $\mathrm{OCF_3}$ strongly electron-withdrawing; Br and Cl intermediate; $\mathrm{OCH_3}$ electron-donating), and across the series high *para* selectivity is maintained, confirming that the governing factor is the ion-pair steric shield rather than ring electronics — while the small residual variations reveal the secondary electronic preference of the Ir–boryl species.

## 6. Summary

1. **Numbering:** C1 is the aryl-ring carbon bearing the $\mathrm{CH_2SO_3^-}$ group; C2 is the chlorine-bearing ring carbon, and numbering continues anticlockwise around the ring (C3–C6).
2. **Conditions:** $[\mathrm{Ir(OMe)cod}]_2$ with dtbpy (4,4′-di-*tert*-butylbipyridine) or tmphen (3,4,7,8-tetramethyl-1,10-phenanthroline) and $\mathrm{B_2pin_2}$, generating the sterically demanding $\mathrm{Ir(L)(Bpin)_3}$ active species.
3. **Site:** borylation occurs **at C4**, *meta* to Cl and *para* to the benzylsulfonate group.
4. **Why:** the sulfonate is electrostatically ion-paired to $\mathrm{(n\text{-}Bu)_4N^+}$ (an interaction wholly unrelated to the Ir–L bond); the cation's long butyl chains act as a steric shield that blocks the *meta* position (C5), while standard steric control excludes C3 and C6, leaving only C4.
5. **Chain length:** *para* selectivity **increases with increasing carbon chain length** of the tetraalkylammonium cation ($\mathrm{Me_4N^+ < Et_4N^+ < Pr_4N^+ < Bu_4N^+ < Hex_4N^+/Oct_4N^+}$), because longer chains provide a larger, more effective shield.
6. **Scope:** benzylsulfonates, arylsulfonates, benzylsulfates, arylsulfates, arylsulfamates and benzylsulfamates all work as their tetraalkylammonium salts, with the C2 substituent variable from Cl to $\mathrm{CF_3}$, Br, $\mathrm{OCF_3}$ or $\mathrm{OCH_3}$.
