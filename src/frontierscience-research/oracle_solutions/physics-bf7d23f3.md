# Josephson junction in the two-component (tunnelling-Hamiltonian) description

Throughout, the junction state is
$$
\Psi(t)=\begin{pmatrix}\Delta_1(t)\\ \Delta_2(t)\end{pmatrix},\qquad \Delta_j=\sqrt{\frac{n_{s,j}}{2}}\,e^{i\phi_j},
$$
and it obeys the Schrödinger equation $i\hbar\,\partial_t\Psi=H\Psi$ with
$$
H=\begin{pmatrix} eV & K\\ K & -eV\end{pmatrix}=eV\,\sigma_z+K\,\sigma_x
$$
(energies per Cooper pair; the pair energy is $+eV$ on side 1 and $-eV$ on side 2, i.e. the electrodes sit at $\pm V/2$ and the total bias across the barrier is $V$).

---

## a) Why $\Delta_1$, $\Delta_2$ can be taken constant inside each bulk electrode

1. **The current is limited by the junction, not by the bulk.** The two electrodes and the tunnel barrier are in series, so the same current flows through all of them. The barrier is a weak link: the maximum supercurrent it can carry, the Josephson critical current $I_0\propto K$, is set by the very small tunnelling amplitude. It is many orders of magnitude smaller than the bulk (depairing) critical current of the electrodes ($J_c^{\rm bulk}\sim10^{7}$–$10^{8}\,{\rm A\,cm^{-2}}$ times a macroscopic cross-section). **The current through the structure is therefore limited by the smaller junction critical current, not by the bulk critical current.**

2. **Because of this size difference, the bulk can be treated as carrying zero current.** The supercurrent density in a superconductor is
   $$
   \mathbf j_s=\frac{n_s e\hbar}{m}\Big(\nabla\phi-\frac{2e}{\hbar}\mathbf A\Big).
   $$
   Since any current that flows is at most $I_0$, which is negligible compared with what the bulk can carry, $\mathbf j_s\approx 0$ in the electrodes on the bulk scale. So $\nabla\phi\approx 0$ in a suitable gauge, and the phase is uniform on each side. The whole phase drop and the whole voltage drop occur across the barrier, which is where the "weakness" (largest phase stiffness cost, i.e. largest kinetic inductance) is.

3. **The amplitude is pinned at its bulk value.** $|\Delta|$ is fixed by the bulk thermodynamics (material, temperature) and by charge neutrality. Near the barrier $|\Delta|$ recovers its bulk value within a coherence length $\xi$, while the electrodes are much thicker than $\xi$. The number of pairs that tunnel is tiny compared with $n_s\times$volume, and it is continually resupplied by the external leads, so $n_{s,j}$ hardly changes.

Hence each electrode can be described by a single spatially uniform complex number $\Delta_j=\sqrt{n_{s,j}/2}\,e^{i\phi_j}$. This is exactly the two-component description used above.

---

## b) Eigenstates for $K=0$, components and the relation between $n_{s,1}$ and $n_{s,2}$

For $K=0$, $H=eV\sigma_z$, which is diagonal. **The eigenstates are the eigenstates of $\sigma_z$:**
$$
\chi_1=\begin{pmatrix}1\\0\end{pmatrix}\quad (E_1=+eV),\qquad
\chi_2=\begin{pmatrix}0\\1\end{pmatrix}\quad (E_2=-eV).
$$
$\chi_1$ describes the condensate entirely on side 1 and $\chi_2$ entirely on side 2. **The energy difference between the two eigenstates is $E_1-E_2=2eV$.**

**Time-dependent components.** Each eigen-component evolves with its own eigenvalue, $e^{-iE_jt/\hbar}$, so for a general state
$$
\Psi(t)=\begin{pmatrix}|\Delta_1|\,e^{i\phi_1(0)}\,e^{-ieVt/\hbar}\\[4pt] |\Delta_2|\,e^{i\phi_2(0)}\,e^{+ieVt/\hbar}\end{pmatrix},
$$
that is,
$$
\Delta_1(t)=\sqrt{\tfrac{n_{s,1}}{2}}\;e^{\,i\left[\phi_1(0)-eVt/\hbar\right]},\qquad
\Delta_2(t)=\sqrt{\tfrac{n_{s,2}}{2}}\;e^{\,i\left[\phi_2(0)+eVt/\hbar\right]},
$$
$$
\phi_1(t)=\phi_1(0)-\frac{eV}{\hbar}t,\qquad \phi_2(t)=\phi_2(0)+\frac{eV}{\hbar}t,\qquad \phi_2-\phi_1=\big[\phi_2(0)-\phi_1(0)\big]+\frac{2eV}{\hbar}t .
$$
Only the phases evolve. The moduli $|\Delta_j|$, and hence $n_{s,j}=2|\Delta_j|^2$, are constant in time.

**Relation between the densities.** With $K=0$ there is no off-diagonal coupling, so no pair can move from one side to the other: $\dot n_{s,1}=\dot n_{s,2}=0$ and **no current flows**. Nothing can redistribute the condensate, so the densities stay at their equilibrium values. For two identical electrodes (same material, same temperature), the superconducting electron densities must therefore all be equal:
$$
\boxed{n_{s,1}=n_{s,2}\equiv n_{s,0}}\qquad(\text{constant in time}).
$$

---

## c) Energy change of a Cooper pair moving from side 1 to side 2

From the eigenvalues, a pair on side 1 has energy $+eV$ and a pair on side 2 has energy $-eV$. Moving a pair from side 1 to side 2 therefore changes its energy by
$$
\Delta E_{\rm pair}=E_1-E_2=\boxed{2eV}.
$$

**Comparison with the chemical-potential difference.** A bias $V$ shifts the electrochemical potential of the two electrodes by $\mu_1-\mu_2=eV$. The chemical potential is a **single-electron** quantity: it is the energy needed to add one electron. A Cooper pair consists of two electrons and carries charge $2e$, so its chemical potential is $\mu_{\rm pair}=2\mu$ and its energy difference across the junction is $2(\mu_1-\mu_2)=2eV$. **The two results therefore agree.** The factor of 2 between the pair energy $2eV$ and the chemical-potential difference $eV$ arises only because the chemical potential is defined per single electron.

---

## d) Consequences of energy conservation for a DC-biased junction

The off-diagonal elements $K$ transfer a whole Cooper pair **coherently** (elastically) through the barrier. The condensate is a single macroscopic quantum state: transferring a pair creates no quasiparticles and excites no internal degree of freedom, so no channel is available to absorb energy. Yet under a DC bias each pair moving from 1 to 2 would have to release the energy $2eV$.

* **A DC current can only flow if it is dissipative.** A steady current at a finite DC voltage delivers power $IV$, which must be dissipated, for example as heat by inelastic quasiparticle tunnelling once $eV$ exceeds the gap scale, or in a resistive shunt.
* **No DC supercurrent can flow in response to a DC bias.** The coherent pair transport cannot dissipate the energy $2eV$, and energy must be conserved in the tunnelling process. **Therefore no DC supercurrent can flow through a Josephson junction in response to a DC-applied bias.** (A DC supercurrent can flow only at $V=0$, where no energy has to be disposed of.)
* **An AC supercurrent can flow.** Energy conservation forbids a *net* transfer of energy, but not a periodic exchange. The energy of the Cooper pairs can be converted **temporarily** back and forth between electrostatic potential energy ($2eV$ per pair) and the kinetic energy of the supercurrent. Pairs then slosh back and forth across the barrier, **so an AC current can flow.** It has zero time average (no net dissipation) and angular frequency $\omega=2eV/\hbar$, i.e. the quantum $\hbar\omega=2eV$ is the energy released per pair. This is the AC Josephson effect, derived explicitly in (f).

---

## e) Equations of motion for $n_{s,1}$, $n_{s,2}$ and the phases

**Schrödinger's equation in components:**
$$
i\hbar\,\dot\Delta_1=eV\,\Delta_1+K\,\Delta_2,\qquad i\hbar\,\dot\Delta_2=K\,\Delta_1-eV\,\Delta_2 .
$$

**Insert $\Delta_j=\sqrt{n_{s,j}/2}\,e^{i\phi_j}$:**
$$
\dot\Delta_j=\left(\frac{\dot n_{s,j}}{2n_{s,j}}+i\dot\phi_j\right)\Delta_j .
$$
Dividing the first equation by $\Delta_1$ and the second by $\Delta_2$ gives
$$
i\hbar\frac{\dot n_{s,1}}{2n_{s,1}}-\hbar\dot\phi_1=eV+K\sqrt{\frac{n_{s,2}}{n_{s,1}}}\;e^{i(\phi_2-\phi_1)},
$$
$$
i\hbar\frac{\dot n_{s,2}}{2n_{s,2}}-\hbar\dot\phi_2=-eV+K\sqrt{\frac{n_{s,1}}{n_{s,2}}}\;e^{-i(\phi_2-\phi_1)} .
$$

**Change of variable.** The individual phases appear only through their difference, which is the gauge-invariant quantity. We therefore change variables to the phase difference across the barrier, $\theta$, oriented in the standard way so that $0<\theta<\pi$ drives pairs **into** electrode 1: the tunnelling factor is $e^{i(\phi_2-\phi_1)}\equiv e^{i\theta}$, and $\dot\theta=\dot\phi_2-\dot\phi_1$. Then
$$
e^{\pm i\theta}=\cos\theta\pm i\sin\theta ,
$$
and the two equations become
$$
i\hbar\frac{\dot n_{s,1}}{2n_{s,1}}-\hbar\dot\phi_1=eV+K\sqrt{\tfrac{n_{s,2}}{n_{s,1}}}\,(\cos\theta+i\sin\theta),
$$
$$
i\hbar\frac{\dot n_{s,2}}{2n_{s,2}}-\hbar\dot\phi_2=-eV+K\sqrt{\tfrac{n_{s,1}}{n_{s,2}}}\,(\cos\theta-i\sin\theta).
$$

**Separate the imaginary parts (densities):**
$$
\hbar\frac{\dot n_{s,1}}{2n_{s,1}}=K\sqrt{\tfrac{n_{s,2}}{n_{s,1}}}\sin\theta,\qquad
\hbar\frac{\dot n_{s,2}}{2n_{s,2}}=-K\sqrt{\tfrac{n_{s,1}}{n_{s,2}}}\sin\theta .
$$

**Separate the real parts (phases):** the real parts of the two equations fix the phase velocities $\dot\phi_1$ and $\dot\phi_2$ of the two condensates in terms of $\theta$, the density ratio and the bias.

### Final answer (e)
The set of differential equations is
$$
\boxed{\;\dot n_{s,1}=\frac{2K}{\hbar}\sqrt{n_{s,1}n_{s,2}}\;\sin\theta\;}
\qquad
\boxed{\;\dot n_{s,2}=-\frac{2K}{\hbar}\sqrt{n_{s,1}n_{s,2}}\;\sin\theta\;}
$$
$$
\boxed{\;\dot\phi_1=-\frac{K}{\hbar}\sqrt{\frac{n_{s,2}}{n_{s,1}}}\;\sin\theta\;}
\qquad
\boxed{\;\dot\phi_2=-\frac{K}{\hbar}\sqrt{\frac{n_{s,1}}{n_{s,2}}}\;\cos\theta+\frac{eV}{\hbar}\;}
$$
The density equations satisfy $\dot n_{s,1}+\dot n_{s,2}=0$ (pair number is conserved; what leaves one side enters the other).

---

## f) Reduction to the DC and AC Josephson effects for $n_{s,1}\approx n_{s,2}$

**Assumptions.** The external circuit (current source and leads) continually replaces the pairs that tunnel, and the tunnelling rate is tiny compared with $n_s$ (part a). The densities therefore stay at their bulk values:
$$
n_{s,1}\simeq n_{s,2}\simeq n_{s,0}.
$$
Then $\sqrt{n_{s,1}n_{s,2}}\to n_{s,0}$ and $\sqrt{n_{s,1}/n_{s,2}}=\sqrt{n_{s,2}/n_{s,1}}\to 1$.

### DC Josephson effect
The current is the charge transferred per unit time, i.e. the rate of change of the electron number on side 1 multiplied by $e$:
$$
\boxed{\,I_j=e\,\frac{dn_{s,1}}{dt}=\frac{2eK\,n_{s,0}}{\hbar}\,\sin\theta=I_0\sin\theta\,},\qquad I_0\equiv\frac{2eKn_{s,0}}{\hbar}.
$$
For $V=0$ the relative phase is not driven ($\dot\theta=2eV/\hbar=0$, see below), so $\theta=\theta_0$ is constant. A **DC supercurrent** $I=I_0\sin\theta_0$, of any value $|I|\le I_0$, flows **at zero voltage**. This is the DC Josephson effect. The critical current $I_0$ is proportional to the tunnelling amplitude $K$, which is why it is so much smaller than the bulk critical current (part a).

### AC Josephson effect
With $n_{s,1}=n_{s,2}$ the two electrodes are equivalent, so the tunnelling amplitude $K$ shifts both condensate phases alike and does not drive the relative phase. The relative phase is driven by the bias alone, i.e. by the difference of the pair energies on the two sides found in (b) and (c): the bias makes the phase on side 1 advance at $-eV/\hbar$ and the phase on side 2 at $+eV/\hbar$, exactly as in the $K=0$ solution of (b). Hence
$$
\frac{d\theta}{dt}=\dot\phi_2-\dot\phi_1=\frac{E_1-E_2}{\hbar}=\frac{2eV}{\hbar}
\quad\Longrightarrow\quad
\boxed{\,V=\frac{\hbar}{2e}\,\frac{d\theta}{dt}\,}.
$$
For a constant (DC) bias $V$, $\theta(t)=\theta_0+\dfrac{2eV}{\hbar}t$ and
$$
I(t)=I_0\sin\!\left(\theta_0+\omega_J t\right),\qquad \omega_J=\frac{2eV}{\hbar},\qquad f_J=\frac{2eV}{h}\approx 483.6\ {\rm GHz\ per\ mV}.
$$
A DC voltage produces an **alternating** supercurrent of frequency $2eV/h$ whose time average is zero. This is the AC Josephson effect, and it is exactly the result anticipated in (d): there is no DC supercurrent under DC bias, and the energy $2eV$ per pair is exchanged periodically (or emitted as photons of energy $\hbar\omega_J=2eV$) rather than dissipated.
