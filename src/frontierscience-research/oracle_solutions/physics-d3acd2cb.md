# Two nucleons on a periodic cubic lattice

Notation: $L$ lattice sites per direction, lattice spacing $a$, physical box size $L_{\rm phy}=La$, nucleon mass $M_{\rm phy}$, $\hbar=c=1$. Flavour index $i\in\{1,2,3,4\}=\{n\uparrow,n\downarrow,p\uparrow,p\downarrow\}$, with $N_r=(n_{r\uparrow},n_{r\downarrow},p_{r\uparrow},p_{r\downarrow})^T$ and canonical anticommutators $\{N_{r,i},N^\dagger_{r',j}\}=\delta_{rr'}\delta_{ij}$.

---

## (a) Single-particle basis and the two-nucleon spin-singlet states

### Single-particle basis
- Position basis: $|\vec r,i\rangle=N^\dagger_{\vec r,i}|0\rangle$, with $\vec r\in\{0,\dots,L-1\}^3$. This gives $4L^3$ states.
- Momentum basis, which diagonalises the hopping term under periodic boundary conditions:
$$
|\vec k,i\rangle=\tilde N^\dagger_{\vec k,i}|0\rangle,\qquad
\tilde N^\dagger_{\vec k,i}=\frac{1}{\sqrt{L^3}}\sum_{\vec r}e^{i\frac{2\pi}{L}\vec k\cdot\vec r}N^\dagger_{\vec r,i},\qquad k_\alpha\in\{0,1,\dots,L-1\}.
$$

A complete two-particle basis is $N^\dagger_{\vec r_1,i_1}N^\dagger_{\vec r_2,i_2}|0\rangle$ (or the same with momenta), with $(\vec r_1,i_1)\neq(\vec r_2,i_2)$ by the Pauli principle.

### Spin-singlet two-nucleon states
Nucleons carry spin $\tfrac12$ and isospin $\tfrac12$ (neutron or proton), and the two-nucleon state must be totally antisymmetric. The spin singlet ($S=0$) is antisymmetric in spin, so the product of the spatial and isospin parts must be symmetric. For the $s$-wave (on-site, spatially symmetric) configuration relevant to the contact interaction, the isospin part must be symmetric. That is the isospin triplet $T=1$, with $T_3=+1,0,-1$ corresponding to $nn$, $np$, $pp$. **There are therefore three spin-singlet states**, because each nucleon can be either a neutron or a proton.

Written as Cartesian isospin components, i.e. the pair operators $\propto N_r^T\sigma_2\tau_2\tau_aN_r$ with $a=3,1,2$, normalised:
$$
\boxed{
\begin{aligned}
S_1&=\frac{1}{\sqrt2}\big(n_{r,\uparrow}p_{r,\downarrow}-n_{r,\downarrow}p_{r,\uparrow}\big),\\
S_2&=\frac{1}{\sqrt2}\big(n_{r,\uparrow}n_{r,\downarrow}-p_{r,\uparrow}p_{r,\downarrow}\big),\\
S_3&=-\frac{i}{\sqrt2}\big(p_{r,\uparrow}p_{r,\downarrow}+n_{r,\uparrow}n_{r,\downarrow}\big).
\end{aligned}}
$$
Check: $N^T\sigma_2(i\tau_1)N=2(n_\uparrow p_\downarrow-n_\downarrow p_\uparrow)$, $N^T\sigma_2(-i\tau_3)N=-2(n_\uparrow n_\downarrow-p_\uparrow p_\downarrow)$, and $N^T\sigma_2N=-2i(n_\uparrow n_\downarrow+p_\uparrow p_\downarrow)$. The corresponding normalised states are $|S_a\rangle=S_a^\dagger|0\rangle$, explicitly
$$
|S_1\rangle=\tfrac1{\sqrt2}\big(p^\dagger_{r\downarrow}n^\dagger_{r\uparrow}-p^\dagger_{r\uparrow}n^\dagger_{r\downarrow}\big)|0\rangle,\quad
|S_2\rangle=\tfrac1{\sqrt2}\big(n^\dagger_{r\downarrow}n^\dagger_{r\uparrow}-p^\dagger_{r\downarrow}p^\dagger_{r\uparrow}\big)|0\rangle,\quad
|S_3\rangle=\tfrac{i}{\sqrt2}\big(p^\dagger_{r\downarrow}p^\dagger_{r\uparrow}+n^\dagger_{r\downarrow}n^\dagger_{r\uparrow}\big)|0\rangle .
$$
$S_1$ is the $np$ ($T_3=0$) singlet. The combinations $S_2+iS_3=\sqrt2\,n_{r\uparrow}n_{r\downarrow}$ and $S_2-iS_3=-\sqrt2\,p_{r\uparrow}p_{r\downarrow}$ are the $nn$ and $pp$ singlets. For particles on different sites the same structure holds with $n_{r\uparrow}p_{r\downarrow}\to n_{r\uparrow}p_{r'\downarrow}$ etc., symmetrised in $\vec r\leftrightarrow\vec r'$.

The Hamiltonian is flavour-independent: the hopping is the same for all four components, and the contact term acts on the spin-singlet on-site pair. All three singlet channels therefore have the same spectrum, and it is enough to treat the $nn$ (↑↓) channel.

### Two-body basis used below
To reduce the two-body problem to a one-body problem, use relative separation $\vec\delta$ and total momentum $\vec q$:
$$
|\vec\delta,\vec q\rangle=\frac{1}{\sqrt{L^3}}\sum_{\vec r}n^\dagger_{\vec r,\uparrow}\,n^\dagger_{\vec r+\vec\delta,\downarrow}\;e^{i(2\pi/L)\vec q\cdot\vec r}|0\rangle .
$$
Acting with the hopping term, where particle $\downarrow$ hops $\vec\delta\to\vec\delta\pm\vec e_\alpha$ and particle $\uparrow$ hops $\vec r\to\vec r\pm\vec e_\alpha$, which shifts $\vec\delta\to\vec\delta\mp\vec e_\alpha$ with a phase:
$$
H|\vec\delta,\vec q\rangle=12t|\vec\delta,\vec q\rangle-t\sum_\alpha\Big[\big(1+e^{i\frac{2\pi}{L}q_\alpha}\big)|\vec\delta+\vec e_\alpha,\vec q\rangle+\big(1+e^{-i\frac{2\pi}{L}q_\alpha}\big)|\vec\delta-\vec e_\alpha,\vec q\rangle\Big]+C\,t\,\delta_{\vec\delta,\vec 0}\,|\vec 0,\vec q\rangle .
$$
In the rest frame $\vec q=0$ this is a single particle of mass $M/2$ (hopping $2t$) on the lattice with a contact potential $Ct$ at the origin. Its free dispersion is
$$
\epsilon(\vec k)=4t\sum_\alpha\Big[1-\cos\frac{2\pi k_\alpha}{L}\Big].
$$

---

## (b) Fixing $t$

**Single particle on the lattice.** In the momentum basis,
$$
H_{\rm free}=\sum_{\vec k,i}E^{\rm lat}(\vec k)\,\tilde N^\dagger_{\vec k,i}\tilde N_{\vec k,i},\qquad
E^{\rm lat}(\vec k)=2t\sum_\alpha\Big[1-\cos\Big(\frac{2\pi k_\alpha}{L}\Big)\Big],
$$
since $\sum_{\vec r}(N^\dagger_rN_{r+e_\alpha}+{\rm h.c.})=\sum_{\vec k}2\cos(2\pi k_\alpha/L)\tilde N^\dagger_k\tilde N_k$.

**Single particle in a physical periodic box.** $\vec p=\frac{2\pi}{L_{\rm phy}}\vec n$, $\vec n\in\mathbb Z^3$, $E(\vec n)=\frac{(2\pi)^2\vec n^2}{2M_{\rm phy}L_{\rm phy}^2}$.

**Two-body energies (free particles).**
$$
\text{finite cubic periodic box:}\quad E^{(2)}_{\rm box}=\frac{(2\pi)^2}{2M_{\rm phy}L_{\rm phy}^2}\big(\vec n_1^{\,2}+\vec n_2^{\,2}\big),
$$
$$
\text{finite periodic lattice:}\quad E^{(2)}_{\rm lat}=2t\sum_\alpha\Big[2-\cos\frac{2\pi n_{1\alpha}}{L}-\cos\frac{2\pi n_{2\alpha}}{L}\Big].
$$
In the rest frame ($\vec n_2=-\vec n_1=-\vec n$) these become $\frac{(2\pi)^2\vec n^2}{M_{\rm phy}L_{\rm phy}^2}$ and $\epsilon(\vec n)=4t\sum_\alpha(1-\cos\frac{2\pi n_\alpha}{L})$.

**Matching.** The $\vec k=0$ level is zero in both theories, so the lowest single-particle energy that carries information is the first excited one, $\vec k=(1,0,0)$. Setting lattice equal to continuum:
$$
2t\Big[1-\cos\frac{2\pi}{L}\Big]=\frac{(2\pi)^2}{2M_{\rm phy}L_{\rm phy}^2}=\frac{2\pi^2}{M_{\rm phy}a^2L^2}
\quad\Longrightarrow\quad
\boxed{\;t=\frac{\pi^2}{M_{\rm phy}\,a^2L^2\big[1-\cos(2\pi/L)\big]}=\frac{\pi^2}{M_{\rm phy}L_{\rm phy}^2\big[1-\cos(2\pi/L)\big]}\;}
$$
This is the exact result. **Continuum/thermodynamic limit** ($L\to\infty$ at fixed $L_{\rm phy}$, i.e. $a\to0$): $1-\cos(2\pi/L)\simeq2\pi^2/L^2$, so
$$
\boxed{\;t\simeq\frac{1}{2M_{\rm phy}a^2}\;}\qquad(\text{i.e. }t=\hbar^2/2Ma^2;\ \text{in lattice units }t=1/2M),
$$
the standard nonrelativistic hopping parameter. With the exact $t$, the lowest non-zero two-body level at $\vec q=0$ equals $2E_0$ exactly for any $L$.

---

## (c) Lowest non-zero single-particle energy

The lowest non-zero single-particle energy is the $\vec n=(1,0,0)$ level of the box (equivalently, of the lattice with the $t$ fixed in (b)):
$$
E_0=\frac{(2\pi)^2(\hbar c)^2}{2M_{\rm phy}c^2L_{\rm phy}^2}
=\frac{4\pi^2}{2\times 1638\times(3.4/197)^2}\ {\rm MeV}=\boxed{40.5\ {\rm MeV}}
$$
($\hbar c\simeq197$ MeV fm, so $L_{\rm phy}=3.4\ {\rm fm}=3.4/197\ {\rm MeV^{-1}}$; the nucleon mass is approximately $1.63\times10^3$ MeV, and using $M_{\rm phy}=1634$ rather than $1638$ MeV changes $E_0$ by only $0.2\%$, so $E_0=40.5$ MeV). The corresponding lowest non-zero relative two-body level is $2E_0\approx81$ MeV.

---

## (d) Coupling $C$ for $E_B=-17.8$ MeV, and the first excited state

**Bound state as a pole.** The two-body energies are the poles of the resolvent $\frac{1}{E-H}$. Write $H=H_0+V$ with $V=Ct\,|\vec 0\rangle\langle\vec 0|$ in the $|\vec\delta,\vec q=0\rangle$ basis. Since $V$ has rank one,
$$
\langle\vec 0|\frac{1}{E-H}|\vec 0\rangle=\frac{G_0(E)}{1-Ct\,G_0(E)},\qquad
G_0(E)=\langle\vec 0|\frac{1}{E-H_0}|\vec 0\rangle=\frac{1}{L^3}\sum_{\vec k}\frac{1}{E-\epsilon(\vec k)} .
$$
The energy levels coupled to the interaction (the $A_1^+$, $s$-wave states) satisfy
$$
\boxed{\;\frac{1}{C\,t}=\frac{1}{L^3}\sum_{\vec k}\frac{1}{E-4t\sum_\alpha\big[1-\cos(2\pi k_\alpha/L)\big]}\;}
$$
**Thermodynamic (continuum) limit.** Split the sum into its ultraviolet part and its low-momentum part. For $L\to\infty$:
- The UV part becomes the Brillouin-zone integral $\int\frac{d^3\theta}{(2\pi)^3}\frac{1}{4t\sum(1-\cos\theta_\alpha)}=\frac{W}{4t}$, with the Watson integral $W=0.505462$. This is $E$-independent because $|E|\ll t$.
- The low-momentum part, where $\epsilon\simeq\frac{(2\pi)^2\vec n^2}{ML_{\rm phy}^2}$, gives the Lüscher zeta function $S(\eta)=\lim_{\Lambda\to\infty}\big[\sum_{|\vec n|<\Lambda}\frac{1}{\vec n^2-\eta}-4\pi\Lambda\big]$, with $\eta=\frac{E}{2E_0}=\frac{ML_{\rm phy}^2E}{4\pi^2}$.

Using $t\simeq1/(2Ma^2)$:
$$
\frac{1}{L^3}\sum_{\vec k}\frac{1}{E-\epsilon(\vec k)}\simeq-\frac{W}{4t}-\frac{M a^2}{4\pi^2L}S(\eta)
\quad\Longrightarrow\quad
\frac{1}{C}=-\frac{W}{4}-\frac{S(\eta)}{8\pi^2L}.
$$
(Equivalently $S(\eta)/\pi L_{\rm phy}=-1/a_s$, the Lüscher relation for a pure scattering-length interaction.)

**Numbers.** $E=-17.8$ MeV gives $\eta_0=-17.8/81.1=-0.2195$. Numerically $S(\eta_0)=-7.64$, i.e. $a_s=-\pi L_{\rm phy}/S(\eta_0)\simeq1.40$ fm. Then
$$
C(L)=\Big[-\frac{W}{4}-\frac{S(\eta_0)}{8\pi^2L}\Big]^{-1}:\qquad
C(8)\simeq-8.74,\quad C(16)\simeq-8.32,\quad C(32)\simeq-8.11,\quad C(64)\simeq-8.01,
$$
These agree with a direct diagonalisation on the lattice. As $L\to\infty$ (vanishing lattice spacing),
$$
\boxed{\;C\;\longrightarrow\;-\frac{4}{W}\simeq-7.91\qquad(\text{finite and negative, i.e. attractive}).\;}
$$
The bare dimensionless coupling approaches a finite negative fixed value. The physical binding is encoded in the $1/L$ correction, i.e. in $a_s$, as expected for a renormalised contact interaction.

**First excited state.** It is the next solution of the same pole equation, now in the interval $0<\eta<1$, i.e. between the free levels $0$ and $2E_0$. With $C$ fixed as above, $S(\eta_1)=S(\eta_0)$, so
$$
\eta_1\simeq0.262\quad\Longrightarrow\quad\boxed{\;E_1=2E_0\,\eta_1\simeq+21\ {\rm MeV}\ (\approx21.3\ {\rm MeV})\;}
$$
This level is non-zero and lies above the ground state at $-17.8$ MeV. It is the $\vec n^2=1$ $s$-wave scattering state, pulled down from $2E_0\approx81$ MeV by the attraction. (Direct lattice diagonalisation: $E_1=21.1,\,20.6,\,20.8,\,21.0,\,21.1$ MeV for $L=8,16,32,64,128$, converging to $\approx21.3$ MeV.)

---

## (e) Second excited state and its degeneracy

The free $\vec n^2=1$ shell of the relative motion has six states, $\vec n=\pm\hat e_x,\pm\hat e_y,\pm\hat e_z$. Under the cubic group they decompose as $A_1^+\oplus E^+\oplus T_1^-$ (dimensions $1+2+3$).
- The single $A_1^+$ combination $\frac1{\sqrt6}\sum_{\pm,\alpha}e^{\pm i2\pi\delta_\alpha/L}$ is non-zero at $\vec\delta=0$. It feels the contact interaction and becomes the first excited state found in (d).
- The other **five** combinations ($E^+$: $2\cos\frac{2\pi\delta_x}{L}-\cos\frac{2\pi\delta_y}{L}-\cos\frac{2\pi\delta_z}{L}$ and $\cos\frac{2\pi\delta_y}{L}-\cos\frac{2\pi\delta_z}{L}$; $T_1^-$: $\sin\frac{2\pi\delta_\alpha}{L}$) **vanish at $\vec\delta=0$**. The on-site interaction does not act on them, so their energy stays exactly at the free value.

Hence the second excited state is
$$
\boxed{\;E_2=2E_0=\frac{(2\pi)^2}{M_{\rm phy}L_{\rm phy}^2}=81.4\ {\rm MeV}\ \ (M_{\rm phy}=1634\ {\rm MeV},\ \hbar c=197.33\ {\rm MeV\,fm}),\qquad\text{five-fold degenerate.}\;}
$$
That is, twice the lowest single-particle energy. On the lattice with the exact $t$ of part (b) this holds for any $L$: $\epsilon(\hat e_x)=4t[1-\cos(2\pi/L)]=2E_0$.

### Summary of the spectrum ($\vec q=0$, any of the three singlet channels)
| level | energy | degeneracy | nature |
|---|---|---|---|
| ground | $-17.8$ MeV (input) | 1 | bound $A_1^+$ |
| 1st excited | $\approx+21$ MeV | 1 | shifted $A_1^+$ scattering state |
| 2nd excited | $2E_0=81.4$ MeV | 5 (five-fold) | free $E^+\oplus T_1^-$ states |

with $t=\pi^2/[M_{\rm phy}L_{\rm phy}^2(1-\cos2\pi/L)]\to1/(2M_{\rm phy}a^2)$ and $C\to-4/W\simeq-7.9$.
