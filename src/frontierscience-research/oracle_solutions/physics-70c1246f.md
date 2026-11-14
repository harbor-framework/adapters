# Tearing mode of a current sheet bounded by conducting walls at $x=\pm b$

## Setup

**Equilibrium.** Consider a sheared slab field $\mathbf B_0=B_{0y}(x)\,\hat{\mathbf y}$ (plus a possible uniform guide field $B_z$) with a current sheet of half-width $a$:
$$
B_{0y}(x)=\begin{cases} B_0\,x/a, & |x|<a,\\[2pt] B_0\,{\rm sgn}(x), & |x|>a,\end{cases}
$$
so that $J_{0z}=B_{0y}'/\mu_0=B_0/(\mu_0a)$ is uniform inside the sheet and zero outside. Perfectly conducting rigid walls are placed at $x=\pm b$ with $b>a$.

**Perturbation.** Write $B_{1x}(x)\,e^{iky+\gamma t}$. The perturbation is even in $x$ (the tearing parity). Away from the thin resistive layer at $x=0$, inertia and resistivity are negligible ($\gamma\ll k v_A$, $S\gg1$), so the "outer" region is in ideal, force-free equilibrium.

### The outer-region equation
Linearising $\nabla\times(\mathbf J\times\mathbf B)=0$, in 2-D its $z$-component is $\mathbf B\cdot\nabla J_z=0$:
$$
\mathbf B_0\cdot\nabla J_{1z}+\mathbf B_1\cdot\nabla J_{0z}=0\;\;\Rightarrow\;\; ik\,B_{0y}\,J_{1z}+B_{1x}\,J_{0z}'=0 .
$$
With $\mathbf B=\nabla\times(A\hat{\mathbf z})$ we have $B_{1x}=ikA_1$, $\mu_0J_{1z}=-(A_1''-k^2A_1)$ and $\mu_0J_{0z}'=B_{0y}''$, which gives $B_{0y}\,(B_{1x}''-k^2B_{1x})-B_{0y}''\,B_{1x}=0$. Using $\big(B_{0y}^2(B_{1x}/B_{0y})'\big)'=B_{0y}B_{1x}''-B_{0y}''B_{1x}$, this is the **central ODE**:
$$
\boxed{\;\frac{\partial}{\partial x}\left(B_{0y}^{2}\,\frac{\partial}{\partial x}\left(\frac{B_{1x}}{B_{0y}}\right)\right)-k^{2}B_{0y}B_{1x}=0\;}
$$

### Matching quantity
The resistive layer at $x=0$ is matched to the outer solution through the jump in the logarithmic derivative:
$$
\boxed{\;\Delta'\equiv\frac{1}{B_{x}(0^{+})}\frac{\partial B_{1x}}{\partial x}\Big|_{0^{+}}-\frac{1}{B_{x}(0^{-})}\frac{\partial B_{1x}}{\partial x}\Big|_{0^{-}}\;}
$$
Here $B_x(0^\pm)$ denotes $B_{1x}(0^\pm)$. $\Delta'$ measures the free magnetic energy available to drive reconnection ($\delta W\propto-\Delta'$). The mode is unstable for $\Delta'>0$, with the FKR growth rate $\gamma\tau_A\propto(\Delta'a)^{4/5}(ka)^{2/5}S^{-3/5}$.

---

## a) Expectation: do the walls make the plasma more or less stable?

**More stable.** A perfectly conducting wall does not allow the perturbed flux to penetrate it: $B_{1x}$ must vanish there, because the normal field at a perfect conductor cannot change. When the tearing perturbation tries to grow, **eddy currents** are induced in the walls (equivalently, image currents of opposite sign). These currents generate a field that opposes the perturbed field and pushes back on it. The outer solution is forced to bend over and vanish at $x=\pm b$, so less magnetic free energy can flow into the reconnection layer. We therefore expect $\Delta'$ to be reduced compared with the wall-free case, i.e. the walls are stabilising. The effect should be strongest for long wavelengths, whose wall-free eigenfunction would extend to $|x|\sim1/k\gg b$.

---

## b) Calculation of $\Delta' a$

### Piecewise solutions
In every sub-region $B_{0y}''=0$ (it is linear inside and constant outside), so the ODE reduces to $B_{1x}''=k^2B_{1x}$ and the solutions are exponentials. Imposing even parity gives:
$$
\boxed{B_{1x}(x)=\begin{cases}
Ce^{-kx}+De^{kx}, & x\in(-b,-a)\\
Ae^{-kx}+Be^{kx}, & x\in(-a,0)\\
Ae^{kx}+Be^{-kx}, & x\in(0,a)\\
Ce^{kx}+De^{-kx}, & x\in(a,b)
\end{cases}}
$$

### Boundary and matching conditions
1. **Conducting walls and continuity of $B_{1x}$** (from $\nabla\cdot\mathbf B=0$):
$$
\boxed{B_{1x}(\pm b)=0,\qquad B_{1x}(\pm a^{-})=B_{1x}(\pm a^{+})}
$$
2. **Derivative condition at $x=\pm a$.** $B_{0y}'$ jumps at $x=\pm a$, so $B_{0y}''$ contains a $\delta$-function there. Integrating the central ODE across $x=\pm a$ shows that $B_{0y}^2\,\partial_x(B_{1x}/B_{0y})$ is continuous. Since $B_{0y}$ itself is continuous,
$$
\boxed{\frac{\partial}{\partial x}\left(\frac{B_{1x}}{B_{0y}}\right)\bigg|_{\pm a^{-}}=\frac{\partial}{\partial x}\left(\frac{B_{1x}}{B_{0y}}\right)\bigg|_{\pm a^{+}}}
$$
At $x=a$: inside, $B_{0y}=B_0$ and $B_{0y}'=B_0/a$; outside, $B_{0y}'=0$. The condition becomes
$$
B_{1x}'(a^+)=B_{1x}'(a^-)-\frac{B_{1x}(a)}{a}.
$$
By parity, the conditions at $x=-a$ and $x=-b$ are identical.

### Solving for the coefficients (in terms of $D$)
* Wall: $Ce^{kb}+De^{-kb}=0\Rightarrow C=-De^{-2kb}$.
* Continuity at $a$: $Ae^{ka}+Be^{-ka}=D\,u$, with $u\equiv e^{-ka}-e^{ka-2kb}$.
* Derivative jump at $a$: $k(Ae^{ka}-Be^{-ka})-\frac1a(Ae^{ka}+Be^{-ka})=k(Ce^{ka}-De^{-ka})=-kD\,v$, with $v\equiv e^{-ka}+e^{ka-2kb}$.

Hence $Ae^{ka}-Be^{-ka}=D\big(\tfrac{u}{ka}-v\big)$. Combining this with the continuity equation (adding them, and using $u-v=-2e^{ka-2kb}$) gives $A$; solving the same pair for the coefficient of the decaying exponential gives $B$. The field coefficients in the inner region are related to those in the outer region by
$$
\boxed{A=\left(\frac{e^{2k(b-a)}-1}{2ka}-1\right)e^{-2kb}\,D},\qquad
\boxed{B=\left(1+\frac{e^{2k(a-b)}}{2ka}\right)D}
$$
and $C=-e^{-2kb}D$.

### $\Delta'$
For the even solution, $B_{1x}(0^\pm)=A+B$, $B_{1x}'(0^+)=k(A-B)$ and $B_{1x}'(0^-)=-k(A-B)$, so
$$
\Delta'=\frac{2k(A-B)}{A+B},\qquad \Delta'a=2ka\,\frac{A-B}{A+B}.
$$
The combinations $A\pm B$ follow most directly from the inner solution written as $B_{1x}(x)=(A+B)\cosh kx+(A-B)\sinh kx$ on $(0,a)$. Its value and slope at $x=a^-$ must equal $Du$ and $kD\big(\tfrac{u}{ka}-v\big)$ (continuity and the derivative condition above):
$$
(A+B)\cosh ka+(A-B)\sinh ka=Du,\qquad (A+B)\sinh ka+(A-B)\cosh ka=D\Big(\frac{u}{ka}-v\Big).
$$
Since $\cosh^2ka-\sinh^2ka=1$,
$$
A+B=D\Big[u\cosh ka-\Big(\frac{u}{ka}-v\Big)\sinh ka\Big],\qquad A-B=D\Big[\Big(\frac{u}{ka}-v\Big)\cosh ka-u\sinh ka\Big].
$$
Multiplying by $2ka/D$ and expanding the hyperbolic functions with $u=e^{-ka}-e^{ka-2kb}$ and $v=e^{-ka}+e^{ka-2kb}$:
$$
\frac{2ka(A-B)}{D}=e^{-2ka}-2ka+1-e^{-2kb}\big(e^{2ka}+2ka+1\big),
$$
$$
\frac{2ka(A+B)}{D}=e^{-2ka}+2ka-1+e^{-2kb}\big(e^{2ka}-2ka-1\big).
$$
Therefore
$$
\boxed{\;\Delta' a=2ka\,\frac{e^{-2ka}-2ka+1-e^{-2kb}\left(e^{2ka}+2ka+1\right)}{e^{-2ka}+2ka-1+e^{-2kb}\left(e^{2ka}-2ka-1\right)}\;}
$$

---

## c) The limit $b\to\infty$

All terms proportional to $e^{-2kb}$ vanish:
$$
\boxed{\;\lim_{b\to\infty}\Delta' a=2ka\,\frac{e^{-2ka}-2ka+1}{e^{-2ka}+2ka-1}\;}
$$
This is exactly the classical result for the same current sheet **without walls**, obtained with $B_{1x}\propto e^{-k|x|}$ for $|x|>a$. **Moving the walls infinitely far away is equivalent to omitting them.** In this limit:
* for $ka\to0$, $\Delta'a\simeq2/(ka)\to+\infty$, so long wavelengths are strongly unstable;
* $\Delta'=0$ when $e^{-2ka}=2ka-1$, i.e. $ka\simeq0.64$; the sheet is tearing-unstable for $ka<0.64$ and stable for $ka>0.64$.

---

## d) Are the expectations confirmed? Physical implications

Evaluating the result:

| $ka$ | $b=a$ | $b=1.5a$ | $b=2a$ | $b=3a$ | $b=5a$ | $b\to\infty$ |
|---|---|---|---|---|---|---|
| 0.2 | −2.03 | −1.05 | −0.10 | +1.63 | +4.25 | +7.23 |
| 0.4 | −2.11 | −1.19 | −0.39 | +0.79 | +1.79 | +2.08 |
| 0.6 | −2.23 | −1.42 | −0.80 | −0.11 | +0.21 | +0.24 |

* For every $k$, $\Delta'a$ increases monotonically with $b$ and approaches the wall-free value from below. **The walls always lower $\Delta'$, i.e. they make the plasma more stable to tearing modes**, which confirms (a). The limit $b\to\infty$ reproduces the wall-free result, which confirms (c).
* Limiting cases:
  * walls at the sheet edge, $b=a$: $\Delta'a=-2ka\coth(ka)<0$ for all $k$;
  * long wavelengths, $ka\to0$: $\Delta'a\to2(b-2a)/a$.

  If the walls are closer than $b=2a$, the sheet is **stable to tearing for all wavelengths**. For $b>2a$ the instability survives, but the band of unstable wavenumbers shrinks: the marginal point moves from $ka\simeq0.64$ (no wall) to $ka\simeq0.635$ for $b=5a$ and to $ka\simeq0.57$ for $b=3a$.
* **Physical implication.** The eddy (image) currents induced in a nearby conductor oppose the growing reconnected flux and remove the free energy that drives the tearing mode. The stabilisation is strongest for long-wavelength modes, which would otherwise reach out to the wall. This is the slab analogue of wall stabilisation in tokamaks, where a close-fitting conducting shell suppresses tearing and kink modes. For a real (resistive) wall the eddy currents decay on the wall time $\tau_w$, so the stabilisation holds only for modes growing faster than $1/\tau_w$; slower modes see the wall-free $\Delta'$ (resistive-wall regime).
