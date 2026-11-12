# Mass percent composition of a NaCl / KCl mixture

## 0. Strategy

The 25 g sample contains only NaCl and KCl. All of the chloride is precipitated by added AgNO$_3$:

$$\text{NaCl} + \text{AgNO}_3 \rightarrow \text{AgCl}\downarrow + \text{NaNO}_3$$
$$\text{KCl} + \text{AgNO}_3 \rightarrow \text{AgCl}\downarrow + \text{KNO}_3$$

The AgNO$_3$ is deliberately added in **excess**, so the filtrate (after AgCl is filtered off) still contains unreacted AgNO$_3$. The copper strip dipped into that filtrate is used as an *internal titration* of the leftover silver: the mass gain of the strip tells us how much excess Ag$^+$ was present. Subtracting that excess from the total Ag$^+$ added gives the Ag$^+$ that was consumed by chloride, hence the total mass of Cl$^-$, hence the NaCl/KCl split.

Atomic/molar masses used: Ag $=108$, N $=14$, O $=16$ (AgNO$_3=170$), Cu $=63.5$, Cl $=35.5$, Na $=23$ (NaCl $=58.5$), K $=39.1$ (KCl $=74.6$) g mol$^{-1}$.

## 1. Reaction of the copper strip with the filtrate

Copper is above silver in the electrochemical series, so it displaces silver from solution:

$$\boxed{\text{Cu} + 2\,\text{AgNO}_3 \rightarrow \text{Cu(NO}_3)_2 + 2\,\text{Ag}}$$

i.e. $\text{Cu} + 2\text{Ag}^+ \rightarrow \text{Cu}^{2+} + 2\text{Ag}$. One mole of copper (63.5 g) dissolves for every two moles of silver (2 × 108 = 216 g) deposited.

## 2. Interpreting the mass change of the strip

The strip starts at 100.00 g and ends at 101.52 g, so

$$\Delta m = 101.52 - 100.00 = 1.52\ \text{g (increase)}$$

This increase is **not** the mass of silver deposited. Metallic silver plates *onto* the strip while copper metal simultaneously *leaves* the strip as Cu$^{2+}$. Therefore

$$\underbrace{m(\text{Ag deposited})}_{x} - \underbrace{m(\text{Cu dissolved})}_{y} = 1.52\ \text{g}$$

The strip gains mass only because 216 g of Ag replaces 63.5 g of Cu.

## 3. Solving for the mass of Ag deposited ($x$) and Cu dissolved ($y$)

Stoichiometry of the equation in step 1 gives the proportion

$$\frac{63.5}{y} = \frac{2\times 108}{x} = \frac{216}{x}
\qquad\Longrightarrow\qquad
x = \frac{216}{63.5}\,y = 3.4016\,y$$

Combining with the mass-balance equation $x - y = 1.52$:

$$3.4016\,y - y = 1.52 \;\Rightarrow\; 2.4016\,y = 1.52 \;\Rightarrow\; y = 0.633\ \text{g}$$
$$x = 3.4016 \times 0.633 = 2.153\ \text{g}$$

**Mass of silver deposited $x = 2.15$ g; mass of copper dissolved $y = 0.63$ g.**

(Check: $2.15 - 0.63 = 1.52$ g ✓)

## 4. Total mass of Ag$^+$ added as AgNO$_3$

$$V = 840\ \text{mL} = 0.840\ \text{dm}^3,\qquad c = 0.5\ \text{mol dm}^{-3}$$
$$n(\text{AgNO}_3) = 0.840 \times 0.5 = 0.42\ \text{mol}$$
$$m(\text{AgNO}_3) = 0.42 \times 170 = 71.4\ \text{g}$$

The silver fraction of AgNO$_3$ is $108/170$, so

$$m(\text{Ag}^+) = 71.4 \times \frac{108}{170} = \mathbf{45.36\ \text{g}}$$

## 5. Silver that actually reacted with chloride

The 2.15 g of silver found on the copper strip was the **excess** silver still in the filtrate. Hence the silver that had already been removed as AgCl is

$$m(\text{Ag in AgCl}) = 45.36 - 2.15 = \mathbf{43.21\ \text{g}}$$

## 6. Total mass of chloride in the sample

In AgCl, 108 g of Ag is combined with 35.5 g of Cl, so

$$m(\text{Cl}^-) = 43.21 \times \frac{35.5}{108} = \mathbf{14.2\ \text{g}}$$

All of this chloride came from the NaCl + KCl mixture.

## 7. System of equations for NaCl ($m$) and KCl ($n$)

Let $m$ = mass of NaCl and $n$ = mass of KCl (in grams). Total sample mass:

$$m + n = 25$$

Chloride contributed by each salt is its mass times the chloride mass fraction, $35.5/58.5$ for NaCl and $35.5/74.6$ for KCl:

$$\frac{35.5\,m}{58.5} + \frac{35.5\,n}{74.6} = 14.2$$

## 8. Solving the system

Evaluate the coefficients: $35.5/58.5 = 0.60684$ and $35.5/74.6 = 0.47587$. Substituting $n = 25 - m$:

$$0.60684\,m + 0.47587(25 - m) = 14.2$$
$$0.60684\,m + 11.8968 - 0.47587\,m = 14.2$$
$$0.13097\,m = 2.3032 \;\Rightarrow\; m = 17.6\ \text{g}$$
$$n = 25 - 17.6 = 7.4\ \text{g}$$

**$m(\text{NaCl}) = 17.6$ g and $m(\text{KCl}) = 7.4$ g.**

(Check: $0.60684(17.6) + 0.47587(7.4) = 10.68 + 3.52 = 14.2$ g Cl$^-$ ✓)

## 9. Mass percent of NaCl

$$w(\text{NaCl}) = \frac{17.6}{25}\times 100 = \mathbf{70.4\ \%}$$

## 10. Mass percent of KCl

$$w(\text{KCl}) = \frac{7.4}{25}\times 100 = \mathbf{29.6\ \%}$$

## Final answer

- Ag deposited on the strip $x = 2.15$ g; Cu dissolved $y = 0.63$ g (net gain 1.52 g)
- Ag$^+$ added = 45.36 g; Ag$^+$ precipitated as AgCl = $45.36 - 2.15 = 43.21$ g; Cl$^-$ = 14.2 g
- NaCl = 17.6 g → **70.4 % NaCl**
- KCl = 7.4 g → **29.6 % KCl**
