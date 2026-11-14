# Quantum virial theorem and eigenstates of the Schrödinger–Poisson system (fuzzy dark matter)

## 0. From a quantum field to the Schrödinger equation

Fuzzy dark matter is an ultralight scalar field $\varphi$ of mass $m$ (typically $m\sim10^{-22}$ eV) in a weak gravitational potential $\Phi$ ($|\Phi|\ll c^2$). Its equation of motion is the Klein–Gordon equation in the weak-field metric:
$$
\frac{1}{c^2}\frac{\partial^2\varphi}{\partial t^2}-\nabla^2\varphi+\frac{m^2c^2}{\hbar^2}\varphi+\frac{2m^2}{\hbar^2}\Phi\,\varphi\simeq0 .
$$
In the non-relativistic regime, factor out the fast oscillation at the Compton frequency:
$$
\varphi(\mathbf r,t)=\frac{\hbar}{\sqrt{2m}}\Big[\psi(\mathbf r,t)\,e^{-imc^2t/\hbar}+\psi^*(\mathbf r,t)\,e^{+imc^2t/\hbar}\Big].
$$
Substituting this, averaging over the fast oscillation, and dropping $\ddot\psi$ because the envelope varies slowly ($|\ddot\psi|\ll (mc^2/\hbar)|\dot\psi|$) gives
$$
i\hbar\,\frac{\partial\psi}{\partial t}=-\frac{\hbar^2}{2m}\nabla^2\psi+m\Phi\,\psi .
$$

### 1. Justification with the WKB approximation, and why it can be used
Write the solution in WKB (eikonal) form, with a slowly varying amplitude and a rapidly varying phase:
$$
\psi=\sqrt{\rho/m}\;e^{iS/\hbar},\qquad S\equiv\hbar\theta .
$$
Inserting this into the Schrödinger equation and separating real and imaginary parts gives exactly
$$
\frac{\partial S}{\partial t}+\frac{|\nabla S|^2}{2m}+m\Phi+Q_B=0,\qquad Q_B=-\frac{\hbar^2}{2m}\frac{\nabla^2\sqrt\rho}{\sqrt\rho},
$$
$$
\frac{\partial\rho}{\partial t}+\nabla\cdot\Big(\rho\,\frac{\nabla S}{m}\Big)=0 .
$$
The first is the Hamilton–Jacobi equation of a classical particle plus the "quantum potential" $Q_B$, and the second is a continuity equation. At lowest WKB order ($\hbar\to0$, $Q_B$ dropped) the field describes a cold, collisionless fluid of particles with velocity $\mathbf v=\nabla S/m$, i.e. ordinary cold dark matter. The first correction, $Q_B$, is the quantum pressure.

The WKB description, and hence a classical Schrödinger field, applies because:
* the **occupation number is enormous**, $\mathcal N\sim(\rho/m)\lambda_{\rm dB}^3\gg1$, so the field is classical and a single mean-field wavefunction $\psi$ suffices;
* the WKB expansion parameter is $\lambda_{\rm dB}/L$, with
  $$\lambda_{\rm dB}=\frac{2\pi\hbar}{mv}\approx1.2\ {\rm kpc}\left(\frac{10^{-22}{\rm eV}}{m}\right)\left(\frac{100\,{\rm km/s}}{v}\right).$$
  On scales $L\gg\lambda_{\rm dB}$ the dynamics is classical (CDM-like). On scales $\lesssim\lambda_{\rm dB}$ the quantum term matters and produces the characteristic wave phenomena: cores (solitons), interference and granules. This is why fuzzy dark matter signals in the Milky Way appear on kpc scales.

---

## 2. Moment of inertia and its derivatives

### Schrödinger–Poisson system and definitions
$$
\boxed{\;i\hbar\frac{\partial\psi}{\partial t}=H\psi=-\frac{\hbar^2}{2m}\nabla^2\psi+m\Phi(\mathbf r,t)\psi\;}
$$
Here $H$ is the Hamiltonian operator, $\Phi(\mathbf r,t)$ is the gravitational potential, and $\rho(\mathbf r,t)=m|\psi(\mathbf r,t)|^2$ is the mass density ($\int|\psi|^2d\mathbf r=N=M/m$). The **moment of inertia** is
$$
\boxed{\;I=\frac12\,m\int d\mathbf r\;r^2|\psi|^2=\frac12\int d\mathbf r\,\rho\,r^2\;}
$$

### First derivative
Using $\partial_t\psi=-\frac{i}{\hbar}H\psi$ and $\partial_t\psi^*=\frac{i}{\hbar}H\psi^*$, and the hermiticity of $H$ ($\int r^2\psi\,H\psi^*=\int\psi^*H(r^2\psi)$):
$$
\boxed{\;\dot I=\frac{im}{2\hbar}\int d\mathbf r\,r^2\left(\psi^*H\psi-\psi H\psi^*\right)=\frac{im}{2\hbar}\int d\mathbf r\,\psi^*\,[r^2,H]\,\psi\;}
$$
Only the kinetic operator contributes to the commutator, because the potential energy $m\Phi$ is a multiplicative function and commutes with $r^2$:
$$
[r^2,H]=-\frac{\hbar^2}{2m}[r^2,\nabla^2]=\frac{\hbar^2}{m}\left(3+2\,\mathbf r\cdot\nabla\right).
$$

### Second derivative
Differentiating once more, $\frac{d}{dt}\langle[r^2,H]\rangle=\frac{i}{\hbar}\langle[H,[r^2,H]]\rangle$. There is no extra term from the explicit time dependence of $\Phi$ because $[r^2,m\partial_t\Phi]=0$. Hence
$$
\ddot I=\frac{m}{2\hbar^2}\int d\mathbf r\,\psi^*\,[[r^2,H],H]\,\psi ,
$$
which in units $\hbar=2m=1$ reads
$$
\boxed{\;\ddot I=\frac14\int d\mathbf r\,\psi^*\,[[r^2,H],H]\,\psi\;}
$$

### Evaluation in Madelung variables
Write $\psi=\sqrt{\rho/m}\,e^{i\theta}$ and $\mathbf v=(\hbar/m)\nabla\theta$. The Schrödinger equation becomes
$$
\dot\rho+\nabla\cdot(\rho\mathbf v)=0,\qquad \frac{D\mathbf v}{Dt}=-\nabla\Phi-\frac{1}{m}\nabla Q_B .
$$
Then $\dot I=\int d\mathbf r\,\rho\,\mathbf r\cdot\mathbf v$ and
$$
\ddot I=\int d\mathbf r\,\rho v^2+\int d\mathbf r\,\rho\,\mathbf r\cdot\frac{D\mathbf v}{Dt}
=\int\rho v^2-\int\rho\,\mathbf r\cdot\nabla\Phi-\frac1m\int\rho\,\mathbf r\cdot\nabla Q_B .
$$

**The three energies** (from the change of variables $\psi\to(\rho,m,\theta)$):
$$
K=\frac12\int\rho v^2\,d\mathbf r=\frac{\hbar^2}{2m^2}\int\rho\,|\nabla\theta|^2d\mathbf r\quad(\text{kinetic energy of bulk flow}),
$$
$$
Q=\frac{\hbar^2}{2m^2}\int|\nabla\sqrt\rho|^2d\mathbf r=\frac{\hbar^2}{8m^2}\int\frac{|\nabla\rho|^2}{\rho}d\mathbf r\quad(\text{quantum / gradient energy}),
$$
$$
W=-\frac{G}{2}\int d\mathbf r\,d\mathbf r'\frac{\rho(\mathbf r)\rho(\mathbf r')}{|\mathbf r-\mathbf r'|}\quad(\text{gravitational potential energy}).
$$
Note that $\frac{\hbar^2}{2m}\int|\nabla\psi|^2=K+Q$: the quantum kinetic energy splits into a flow part and a gradient part.

**Self-gravitation integral.** The potential is
$$
\boxed{\;\Phi(\mathbf r)=-G\int\frac{d\mathbf r'\,\rho(\mathbf r')}{|\mathbf r-\mathbf r'|}\;}
$$
so
$$
V\equiv-\int\rho\,\mathbf r\cdot\nabla\Phi\,d\mathbf r=-G\int d\mathbf r\,d\mathbf r'\,\frac{\rho(\mathbf r)\rho(\mathbf r')\,\mathbf r\cdot(\mathbf r-\mathbf r')}{|\mathbf r-\mathbf r'|^3}.
$$
Swapping $\mathbf r\leftrightarrow\mathbf r'$ and averaging, using $\mathbf r\cdot(\mathbf r-\mathbf r')+\mathbf r'\cdot(\mathbf r'-\mathbf r)=|\mathbf r-\mathbf r'|^2$:
$$
\boxed{\;V=-G\int d\mathbf r\,d\mathbf r'\,\frac{\rho(\mathbf r)\rho(\mathbf r')\,\mathbf r\cdot(\mathbf r-\mathbf r')}{|\mathbf r-\mathbf r'|^3}=-\frac{G}{2}\int d\mathbf r\,d\mathbf r'\,\frac{\rho(\mathbf r)\rho(\mathbf r')}{|\mathbf r-\mathbf r'|}=W\;}
$$
where $W$ is the total potential energy of the system.

**Quantum-pressure term.** Since $\rho\nabla(Q_B/m)=\nabla\cdot\boldsymbol\sigma$ with $\sigma_{ij}=-\frac{\hbar^2}{4m^2}\rho\,\partial_i\partial_j\ln\rho$, integration by parts gives
$$
-\frac1m\int\rho\,\mathbf r\cdot\nabla Q_B=\int{\rm Tr}\,\boldsymbol\sigma=\frac{\hbar^2}{4m^2}\int\frac{|\nabla\rho|^2}{\rho}=2Q .
$$

**Quantum virial theorem:**
$$
\boxed{\;\ddot I=2K+2Q+W\;}
$$

---

## 3. Energy conservation and the stability (equilibrium) condition

The Schrödinger–Poisson Hamiltonian is time-translation invariant, so **the total energy of the system, $E_{\rm tot}=K+W+Q$, is conserved**.

In a steady state ($\ddot I=0$) the virial theorem gives
$$
2K+2Q+W=0\quad\Longrightarrow\quad \frac{Q}{|W|}=\frac12-\frac{K}{|W|}.
$$

**Result.** The total energy of the system is $(K+W+Q)$, which is conserved. In a steady state ($\ddot I=0$), and since $K\ge0$, we have
$$
\boxed{\;\frac{Q}{|W|}\le\frac12\;}
$$
which sets a lower limit on the particle mass $m$ for an equilibrium system with a given density distribution $\rho(\mathbf r)$. The limit is saturated ($Q/|W|=1/2$) if the phase of the wavefunction is position-independent so $\nabla\theta=0$, a condition that is satisfied in the soliton (the ground state below).

Explicitly, $Q\propto\hbar^2/m^2$ at fixed $\rho$ while $W$ is independent of $m$, so the mass bound reads
$$
m\ \ge\ \hbar\left[\frac{\int|\nabla\sqrt\rho|^2d\mathbf r}{|W|}\right]^{1/2}\sim\frac{\hbar}{R\,v_{\rm vir}} .
$$
In words, the de Broglie wavelength cannot exceed the size of the system. At saturation $\nabla\theta=0$ means $K=0$.

**Energy conditions in equilibrium:** $E_{\rm tot}=K+Q+W=W/2=-(K+Q)<0$, so the system is gravitationally bound. For the soliton ($K=0$): $Q=|W|/2$ and $E_{\rm tot}=W/2=-Q$.

**Stability.** For a configuration of size $R$ and mass $M$,
$$
E_{\rm tot}(R)\simeq\alpha\frac{\hbar^2M}{m^2R^2}-\beta\frac{GM^2}{R}\quad(\alpha,\beta>0).
$$
$dE/dR=0$ gives $R_*=2\alpha\hbar^2/(\beta GMm^2)$, which is precisely the virial condition $2Q+W=0$. At $R_*$, $d^2E/dR^2=\beta GM^2/R_*^3>0$. The quantum pressure ($\propto R^{-2}$) always halts gravitational collapse ($\propto R^{-1}$), so the equilibrium is stable. This is why the soliton is the stable attractor at the centre of fuzzy-dark-matter halos.

---

## 4. The Schrödinger–Poisson equations

$$
\boxed{\;i\hbar\frac{\partial\psi}{\partial t}=-\frac{\hbar^2}{2m}\nabla^2\psi+m\Phi\,\psi,\qquad \nabla^2\Phi=4\pi G\rho=4\pi Gm|\psi|^2\;}
$$
with $\Phi(\mathbf r)=-G\int d\mathbf r'\rho(\mathbf r')/|\mathbf r-\mathbf r'|$ and $I=\frac12m\int d\mathbf r\,r^2|\psi|^2$.

---

## 5. Spherical coordinates and stationary states

Seek stationary, spherically symmetric states $\psi(\mathbf r,t)=\psi(r)\,e^{-imEt/\hbar}$, where $E$ is the energy eigenvalue per unit particle mass:
$$
-\frac{\hbar^2}{2m^2}\frac{1}{r^2}\frac{d}{dr}\Big(r^2\frac{d\psi}{dr}\Big)+\Phi(r)\psi=E\,\psi,\qquad
\frac{1}{r^2}\frac{d}{dr}\Big(r^2\frac{d\Phi}{dr}\Big)=4\pi Gm\,\psi^2 .
$$
Equivalently, with $\chi=r\psi$: $-\frac{\hbar^2}{2m^2}\chi''+\Phi\chi=E\chi$.

**Boundary conditions:** $\psi'(0)=\Phi'(0)=0$ (regularity), $\psi\to0$ as $r\to\infty$ (normalisable), $\Phi\to-GM/r$ as $r\to\infty$, and $4\pi m\int_0^\infty\psi^2r^2dr=M$.

**Scaling invariance.** If $\{\psi(r),\Phi(r),E\}$ is a solution with mass $M$, then $\{\lambda^2\psi(\lambda r),\lambda^2\Phi(\lambda r),\lambda^2E\}$ is a solution with mass $\lambda M$. Each level $n$ is therefore a one-parameter family labelled by $M$. Dimensional analysis with $G,\hbar,m,M$ fixes the units:
* length $\hbar^2/(GMm^2)$;
* velocity $GMm/\hbar$;
* density $(Gm^2/\hbar^2)^3M^4$.

---

## 6. Solving for the eigenstates

**Numerical method (shooting).** Work in units $G=\hbar=m=1$. Set $\psi(0)=1$ and $U\equiv\Phi-E$ with shooting parameter $U(0)=U_0$, and integrate
$$
\psi''+\frac2r\psi'=2U\psi,\qquad U''+\frac2rU'=4\pi\psi^2
$$
outward from $r\to0$ with the series start $\psi\simeq1+\tfrac{U_0}{3}r^2$, $U\simeq U_0+\tfrac{2\pi}{3}r^2$. For generic $U_0$, $\psi$ diverges to $\pm\infty$. The eigenvalues are the values of $U_0$ at which the divergence changes sign; the $n$-th one gives a solution with $n$ nodes that decays to zero. Bisection gives $U_0=-2.3025,\,-3.0329,\,-3.3682$ for $n=0,1,2$. For each solution:
* $M=4\pi\int\psi^2r^2dr$;
* $E=-\lim_{r\to\infty}[U(r)+M/r]$, since $\Phi\to-M/r$;
* $W=\frac12\int\rho\Phi\,d^3r$;
* $r_{1/2}$ from $M(<r_{1/2})=M/2$.

Rescaling with $\lambda=1/M$ to unit mass gives the dimensionless coefficients.

**Eigenstates.** Label them $n=0,1,2,\dots$ in order of increasing energy; the eigenstate $n$ has $n$ nodal radii at which the density vanishes. Because of the scaling invariance, all systems at level $n$ form a one-parameter family specified by the total mass $M$:

* **Central potential:**
$$\boxed{\;\Phi_c=-\left(\frac{GMm}{\hbar}\right)^2\phi_n\;}$$
* **Energy eigenvalue and potential energy:**
$$\boxed{\;E=-\left(\frac{GMm}{\hbar}\right)^2\epsilon_n\;},\qquad \boxed{\;W=-\frac{G^2M^3m^2}{\hbar^2}\,w_n\;}$$
* **Central density:**
$$\boxed{\;\rho_c=\left(\frac{Gm^2}{\hbar^2}\right)^3M^4\rho_n\;}$$
* **Half-mass radius and virial velocity:**
$$\boxed{\;r_{1/2}=\frac{\hbar^2}{GMm^2}\,f_n\;},\qquad \boxed{\;v_{\rm vir}=(-W/M)^{1/2}=\frac{GMm}{\hbar}\,w_n^{1/2}\;}$$

| $n$ | $\rho_n$ | $\phi_n$ | $\epsilon_n$ | $w_n$ | $w_n^{1/2}$ | $f_n$ | nodal radii $[\hbar^2/(GMm^2)]$ |
|---|---|---|---|---|---|---|---|
| 0 (soliton) | $4.40\times10^{-3}$ | 0.3155 | 0.1628 | 0.1085 | 0.329 | 3.925 | none |
| 1 | $1.80\times10^{-4}$ | 0.0715 | 0.0308 | 0.0205 | 0.143 | 23.56 | 12.9 |
| 2 | $3.14\times10^{-5}$ | 0.0314 | 0.0125 | 0.00835 | 0.091 | 60.9 | 18.2, 43.9 |

**Consistency checks (ground state).**
* The soliton has $\nabla\theta=0$, so $K=0$ and the virial theorem gives $Q=|W|/2=0.0543\,G^2M^3m^2/\hbar^2$. This saturates $Q/|W|=1/2$.
* Multiplying the eigenvalue equation by $\rho$ and integrating gives $ME=Q+2W$, i.e. $\epsilon_0=2w_0-w_0/2=\tfrac32w_0=0.1628$, in agreement with the direct numerical value.
* The total energy is $E_{\rm tot}=Q+W=W/2=-0.0543\,G^2M^3m^2/\hbar^2<0$, so the state is bound.

The excited states ($n\ge1$) have nodes and much lower central densities. They are unstable to decay toward the ground state, so the $n=0$ soliton is the physically relevant core.

**Astrophysical scale.** For $m=10^{-22}$ eV and $M=10^9M_\odot$, $\hbar^2/(GMm^2)\approx85$ pc. The soliton then has $r_{1/2}\approx3.925\times85\approx335$ pc and $v_{\rm vir}\approx0.329\times224\approx74$ km s$^{-1}$. Since $r_{1/2}\propto1/(Mm^2)$, more massive solitons are smaller and denser ($\rho_c\propto M^4$). This kpc-scale core is the signal of fuzzy dark matter sought in the inner Milky Way and in dwarf galaxies.
