# Classical mechanics as the high-entropy limit of quantum mechanics

Conjecture: just as non-relativistic mechanics is the $v\ll c$ limit of relativity, classical mechanics is the $S\gg0$ (high-entropy) limit of quantum mechanics. Equivalently, quantum mechanics becomes indispensable in the low-entropy regime. Mathematically, $\hbar\to0$ corresponds to sending the zero entropy of pure states to $-\infty$.

---

## 1. Qualitative evidence: quantum effects are low-entropy phenomena

* **Coherence and decoherence.** Coherence is probably the most direct and most important property of a quantum system. It is quickly lost through interaction with the environment (decoherence). Decoherence turns pure superpositions into mixtures and therefore **increases the entropy** of the system. It is one mechanism that drives a system to the high-entropy limit, where it behaves classically. This is in line with the statement.

* **Macroscopic quantum effects need low temperature.** Examples are **superconductivity** (zero resistance, flux quantisation, Josephson effects), **superfluidity** of $^4$He and $^3$He, the **integer and fractional quantum Hall effects**, and **topological insulators** (protected surface states). All of these are harder or impossible to achieve at high temperature, because **thermal noise breaks the coherence** of the system: thermal excitations destroy Cooper pairs, fill gaps and dephase edge states. Entropy is a monotonic function of temperature ($\partial S/\partial T=C/T>0$), so decreasing temperature means decreasing the entropy of the system. Quantum effects appearing at low $T$ is therefore the same as quantum effects appearing at low $S$, in line with the statement.

* **High pressure as an apparent counterexample.** Some quantum effects can be reproduced at high temperature if the pressure is high. Examples are the hydride superconductors H$_3$S ($T_c\approx203$ K at about 150 GPa) and LaH$_{10}$ ($T_c\approx250$ K at about 170 GPa). This might seem to contradict the statement, but high pressure compresses the system into a small phase-space volume, so **high pressure corresponds to low entropy**, in line with the statement. Similarly, **white dwarfs and neutron stars** exhibit quantum (degeneracy-pressure) effects despite temperatures of $10^{6}$–$10^{9}$ K, because their enormous densities make the entropy per particle small ($T\ll T_F$).

* **Bose–Einstein condensates.** A BEC requires a **high phase-space density** (PSD), $n\lambda_{\rm dB}^3\gtrsim2.612$ with $\lambda_{\rm dB}=h/\sqrt{2\pi mk_BT}$. This means both high spatial density (small position spread) and low temperature (small momentum spread). The PSD is directly related to entropy and dimensionality, as the **Sackur–Tetrode equation** for the ideal gas shows:
$$
\frac{S}{Nk_B}=\ln\!\left[\frac{V}{N\lambda_{\rm dB}^3}\right]+\frac52=\frac52-\ln({\rm PSD}).
$$
High PSD is the same as low entropy per particle, again in line with the statement.

* **Occupation numbers.** For thermodynamic systems in equilibrium, entropy can be computed directly from the occupations $\bar n_k$ of the quantum states, $S=-k_B\sum_k[\bar n_k\ln\bar n_k\mp(1\pm\bar n_k)\ln(1\pm\bar n_k)]$. At high temperatures all occupations are small ($\bar n_k\ll1$), the Bose and Fermi distributions reduce to Maxwell–Boltzmann, and classical statistical mechanics applies. Quantum effects related to indistinguishability appear whenever occupations approach unity, and in that same limit the entropy per particle drops. This again agrees with the statement.

* **Negative temperatures.** Infinite entropy corresponds to infinite temperature, but the reverse is not necessarily true. In systems with **finitely many** states (e.g. spin systems), $S(E)$ has a stationary point (a maximum) where $1/T=\partial S/\partial E=0$. This stationary point is the maximum entropy the system can reach, so there is **no high-entropy limit**. These are exactly the systems in which temperature can take negative values. Since entropy is a concave function of energy, the systems that admit a classical description are exactly those for which no such stationary point exists, and for which the temperature can be neither negative nor infinite. Spins, the archetypal finite-state systems, have no classical limit.

---

## 2. Entropy and uncertainty for a single degree of freedom

For one degree of freedom, consider Gaussian states with uncertainty $\Sigma=\sqrt{\det{\rm Cov}(x,p)}$ ($=\sigma_x\sigma_p$ for uncorrelated $x,p$).

**Classical (Gaussian distribution on phase space):**
$$
S_C(\Sigma)=\ln\left(2\pi e\frac{\Sigma}{\hbar}\right)=\ln\left(\frac{\Sigma}{\hbar}\right)+1 .
$$

**Quantum (Gaussian, i.e. thermal-like, state with $\Sigma=\hbar(\bar n+\tfrac12)$):** the von Neumann entropy is built from the upper-level term $\left(\frac{\Sigma}{\hbar}+\frac12\right)\ln\left(\frac{\Sigma}{\hbar}+\frac12\right)$, from which the lower-level term $\left(\frac{\Sigma}{\hbar}-\frac12\right)\ln\left(\frac{\Sigma}{\hbar}-\frac12\right)$ is taken away:
$$
\begin{aligned}
S_Q(\Sigma)=\;&\left(\frac{\Sigma}{\hbar}+\frac{1}{2}\right)\ln\left(\frac{\Sigma}{\hbar}+\frac{1}{2}\right)\\
&\left(\frac{\Sigma}{\hbar}-\frac{1}{2}\right)\ln\left(\frac{\Sigma}{\hbar}-\frac{1}{2}\right).
\end{aligned}
$$

**Comparison.** For large $\Sigma$, $S_Q=\ln(\Sigma/\hbar)+1-\frac{1}{24}(\hbar/\Sigma)^2+\dots$.

| $\Sigma/\hbar$ | 10 | 5 | 3 | 2 | 1 | 0.5 | $1/e\approx0.37$ |
|---|---|---|---|---|---|---|---|
| $S_C$ | 3.3026 | 2.6094 | 2.0986 | 1.6931 | 1.000 | 0.307 | 0 |
| $S_Q$ | 3.3022 | 2.6078 | 2.0939 | 1.6825 | 0.955 | 0 | — |

* The classical and quantum entropies are **very close even when the uncertainty is just a few units of $\hbar$**: the difference is $<0.5\%$ at $3\hbar$.
* They **diverge at about two units of $\hbar$**. In quantum mechanics the entropy decreases faster and **reaches zero at $\hbar/2$**, which is the bound of the Heisenberg uncertainty principle (pure states). Classical mechanics reaches zero entropy at **$\hbar/e$** and then continues into the **negative** region, which is unphysical for a discrete count of states.
* The convergent predictions at high entropy, together with the divergent predictions and the negative classical values at low entropy, reinforce the idea that **quantum mechanics is required at low entropy, much like relativity is required at high speeds**.

---

## 3. Black-body radiation

**Classical prediction (Rayleigh–Jeans law)** for the spectral radiance:
$$
\frac{2\nu^2k_BT}{c^2}=\frac{2\nu^2}{c^2\beta},\qquad\beta=\frac{1}{k_BT}.
$$
It diverges when integrated over $\nu$ (the ultraviolet catastrophe), which is the famous failure of classical statistical mechanics.

**Quantum prediction (Planck's law):**
$$
\frac{2h\nu^3}{c^2}\frac{1}{\exp\left(\frac{h\nu}{k_BT}\right)-1}=\frac{2h\nu^3}{c^2}\frac{1}{e^{h\beta\nu}-1}.
$$

**Standard view: small $\nu$.** The two agree for small $\nu$, since $e^x\approx1+x+O(x^2)$ for $x\ll1$:
$$
\frac{2h\nu^3}{c^2}\frac{1}{e^{h\beta\nu}-1}\approx\frac{2h\nu^3}{c^2}\frac{1}{1+h\beta\nu+O(\nu^2)-1}\approx\frac{2\nu^2}{c^2\beta}.
$$

**High-entropy view: small $\beta$.** The same result is obtained by taking the limit of large temperatures. The classical black-body spectrum is the first term of the expansion in small $\beta$:
$$
\frac{2h\nu^3}{c^2}\frac{1}{e^{h\beta\nu}-1}\approx\frac{2h\nu^3}{c^2}\frac{1}{1+h\beta\nu+O(\beta^2)-1}\approx\frac{2\nu^2}{c^2\beta}.
$$
Since $\beta$ is the inverse temperature, this is the **limit of large temperatures**. Since entropy increases with temperature (for each mode, $S=k_B[(\bar n+1)\ln(\bar n+1)-\bar n\ln\bar n]$ grows without bound as $\bar n=1/(e^{h\beta\nu}-1)\to\infty$), it is also the **limit of large entropy**. The classical distribution is recovered as the high-entropy limit of the quantum distribution, consistent with the conjecture.

---

## 4. Recovery of classical statistical mechanics in thermal equilibrium

**Thermal state.** Thermal equilibrium is described by $\hat\rho=e^{-\beta\hat H}$ (up to normalisation), which is the mixed state that **maximises entropy at a given average energy**. Its entropy is directly connected to $\beta$: $S$ increases monotonically as $T$ increases, so **as $S\to\infty$, $\beta\to0$**. The high-entropy limit is therefore the small-$\beta$ limit.

**Wigner distribution (following Wigner's original paper).** The Wigner distribution of a system in thermal equilibrium at inverse temperature $\beta$ is
$$
W(x,p)=\int dy\,e^{iyp/\hbar}\langle x+y|e^{-\beta\hat H}|x-y\rangle e^{-iyp/\hbar}.
$$

**Transformed Hamiltonian.** Moving the plane-wave factor through the Hamiltonian gives
$$
\hat H=e^{ixp/\hbar}\hat He^{-ixp/\hbar}=\frac{(p+i\hbar\,\partial/\partial x)^2}{2m}+V(x)=\epsilon(x,p)+i\frac{\hbar}{2m}\frac{\partial}{\partial x}-\frac{\hbar^2}{2m}\frac{\partial^2}{\partial x^2},
$$
where $\epsilon(x,p)=p^2/2m+V(x)$ is the classical Hamiltonian. The extra (derivative) terms, which come from expanding the square, contain the quantum corrections; we refer to them as $\hat Q$. Written out with the momentum factor of the cross term, they act as
$$
\hat Q=i\frac{\hbar p}{m}\frac{\partial}{\partial x}-\frac{\hbar^2}{2m}\frac{\partial^2}{\partial x^2},\qquad \hat H=\epsilon(x,p)+\hat Q .
$$
The Wigner function becomes
$$
W(x,p)=\int dy\,e^{iyp/\hbar}e^{-\beta\hat H}|x-y\rangle .
$$

**Wigner's expansion in powers of $\hbar$.** Expanding $e^{-\beta(\epsilon+\hat Q)}$ in $\hbar$, Wigner found that the quantum corrections first appear at **second order in $\hbar$**:
$$
W(x,p)=e^{-\beta\epsilon}\left\{1+\hbar^2\left[-\frac{\beta^2}{8m}V''+\frac{\beta^3}{24m}\Big(V'^2+\frac{p^2}{m}V''\Big)\right]+O(\hbar^4)\right\}.
$$

**Expansion in powers of $\beta$ (high entropy).** We now show that the quantum corrections also appear only at **second order in $\beta$**, which justifies the classical limit at high entropy.

*First order.*
$$
e^{-\beta\hat H}\approx1-\beta\big(\epsilon+\hat Q\big),
$$
so at first order
$$
W(x,p)\approx1-\beta\epsilon(x,p)-\beta\int dy\,\langle x+y|\hat Q|x-y\rangle .
$$
For the last term, insert an identity in the momentum eigenbasis. $\hat Q$ acts on $e^{iky}$ with $\partial_x\to ik$, which gives $i\frac{\hbar p}{m}(ik)=-\frac{\hbar p}{m}k$ and $-\frac{\hbar^2}{2m}(ik)^2=\frac{\hbar^2}{2m}k^2$. Hence
$$
\int dy\,\langle x+y|\hat Q|x-y\rangle=\iint dk\,dy\,e^{i2ky}\left(-\frac{\hbar p}{m}k+\frac{\hbar^2}{2m}k^2\right)=0,
$$
because the $y$-integral gives $\pi\delta(k)$, which kills both the $k$ and the $k^2$ terms. **The first-order quantum terms vanish**: to first order in $\beta$ the Wigner function is exactly the classical one, $1-\beta\epsilon(x,p)$.

*Second order.* The first non-vanishing contributions come from the products of $\hat Q$ with the potential, i.e. from the non-commutativity of $\hat Q$ and $V(x)$:
$$
W(x,p)\approx1-\beta\epsilon(x,p)-\beta^2\epsilon^2(x,p)-\beta^2\int dy\,\langle x+y|\hat QV(x)+V(x)\hat Q|x-y\rangle .
$$
This gives the **first non-zero quantum correction** to the Wigner function, involving $\hbar^2V''/m$ and $\hbar p V'/m$ terms at order $\beta^2$, consistent with the $\beta^2\hbar^2$ term of Wigner's expansion. As $\beta\to0$, i.e. $S\to\infty$, these corrections vanish faster than the classical terms. **Classical statistical mechanics is recovered as the high-entropy limit.**

---

## 5. The high-entropy limit of classical mechanics: stretching maps

Let $\mathcal M=(\mathbb R^2,\omega)$ be the phase space of a single degree of freedom with symplectic form $\omega=dx\wedge dp$. We look for all transformations $R$ that **increase the entropy of every state by the same amount**.

**Requirement.** $R$ should increase the entropy of each distribution $\rho$ by a fixed $\Delta S=\log\lambda>0$:
$$
S(R(\rho))=S(\rho)+\log\lambda,\qquad S(\rho)=-\int_{\mathcal M}\rho\log\rho\,dx\,dp ,
$$
where $R(\rho)$ is the distribution transformed through the map.

**Entropy change of a generic map.** The transformed density is $R(\rho)(R(z))=\rho(z)/|\det AR(z)|$, where $AR=\partial_aR^b$ is the Jacobian matrix. Changing variables $z'=R(z)$,
$$
S(R(\rho))=-\int\rho(z)\big[\log\rho(z)-\log|\det AR|\big]dz .
$$
So for a generic transformation, the increase of entropy is the expectation of the log Jacobian determinant:
$$
\Delta S=\int_{\mathcal M}\rho\,\log|\det AR|\,dx\,dp .
$$
**Since the increase must be the same for all distributions**, including arbitrarily narrow ones around any point, we must have
$$
|\det AR|=\lambda>1\quad\text{everywhere}.
$$
The Jacobian determinant gives how an infinitesimal phase-space volume scales under the transformation. A map that increases entropy uniformly is therefore exactly a map that **stretches phase space uniformly**, and we call it a **stretching map**.

**Not canonical.** A stretching map is *not* a canonical transformation. Canonical transformations, those generated by Hamiltonian evolution, preserve areas in phase space (Liouville's theorem) and therefore **conserve entropy**. For a single degree of freedom, canonical transformations and volume-preserving maps coincide, since $\omega=dx\wedge dp$ is the area form.

**Factorisation.** All stretching maps can be written as
$$
R=T\circ U ,
$$
where $U$ is a canonical (entropy-preserving) transformation and $T$ is a **pure stretching map**:
$$
T(x,p)\mapsto(\sqrt\lambda\,x,\sqrt\lambda\,p),\qquad\lambda\in(1,\infty).
$$
To see this, note that $T^{-1}\circ R$ has unit Jacobian and is therefore canonical. Any stretching map can thus be understood as first performing a canonical transformation, which preserves entropy, followed by a pure stretch of position and momentum.

**Poisson-bracket characterisation.** Stretching maps can alternatively be characterised by how the Poisson brackets transform:
$$
\{R(x),R(p)\}=\partial_xR(x)\,\partial_pR(p)-\partial_xR(p)\,\partial_pR(x)=|\partial_aR^b|=\lambda .
$$
The Poisson bracket of the transformed position and momentum is the Jacobian determinant of the transformation, which is $\lambda$. Since this is an equality, every map that transforms the Poisson brackets in this way is a stretching map.

**Moments.** $T$ is a pure stretching map if and only if
$$
\langle T(x^np^m)\rangle=(\sqrt\lambda)^{(n+m)}\langle x^np^m\rangle
$$
for all $n,m$: the pure stretch rescales every polynomial moment by $\lambda^{(n+m)/2}$, and the moments determine the distribution.

---

## 6. Which operator ordering admits a pure quantum stretching map?

In quantum mechanics we look for a map that rescales the expectations of polynomials in a particular ordering. There are three commonly used orderings, each associated with a quasi-probability distribution whose classical moments reproduce the ordered quantum expectations:
* symmetrized averages, associated with the **Wigner function $W$**;
* normal ordering $(a^\dagger)^na^m$, associated with the **Glauber–Sudarshan $P$ distribution**;
* anti-normal ordering $a^n(a^\dagger)^m$, associated with the **Husimi $Q$ distribution**.

Here $a=\sqrt{\frac{m\omega}{2\hbar}}\big(X+\frac{i}{m\omega}P\big)$.

**(i) Symmetrized ordering (Wigner function): fails.** We would need a map $T_W$ with
$$
\langle T_W(\Pi(\underbrace{X,\dots,X}_{n},\underbrace{P,\dots,P}_{m}))\rangle=(\sqrt\lambda)^{(n+m)}\langle\Pi(\underbrace{X,\dots,X}_{n},\underbrace{P,\dots,P}_{m})\rangle,
$$
where $\Pi(A_1,\dots,A_n)=\frac{1}{n!}\sum_\pi A_{\pi(1)}A_{\pi(2)}\cdots A_{\pi(n)}$ averages the products over all permutations $\pi$. These averages are exactly the moments of the Wigner function:
$$
\langle\Pi(\underbrace{X,\dots,X}_{n},\underbrace{P,\dots,P}_{m})\rangle=\int_{\mathcal M}x^np^m\,W(x,p)\,dx\,dp .
$$
$T_W$ would therefore be a pure stretching map acting on the Wigner function, $W\mapsto\frac1\lambda W(x/\sqrt\lambda,p/\sqrt\lambda)$. **This cannot work.** Wigner functions can have regions with negative values, but the size of these regions cannot exceed a few units of $\hbar$. Under $T_W$ the negative regions would be enlarged by a factor $\lambda$ in area, producing functions that do not correspond to any quantum state. (Equivalently, smoothing any legitimate Wigner function with the vacuum Gaussian must give a non-negative Husimi function. Smoothing the stretched function, whose negative region is now much wider than that Gaussian, gives negative values.) **No pure stretching map exists in the symmetrized ordering.**

**(ii) Normal ordering (Glauber–Sudarshan $P$): fails.** We would need
$$
\langle T_P((a^\dagger)^na^m)\rangle=(\sqrt\lambda)^{(n+m)}\langle(a^\dagger)^na^m\rangle .
$$
For the vacuum, $a|0\rangle=0$, so the mean value of **every** normally ordered observable with $n+m>0$ vanishes. Rescaling zero leaves it unchanged, so $T_P$ would map the vacuum to itself and would **not increase its entropy**. The map cannot increase the entropy of all states, and normal ordering is ruled out as well.

**(iii) Anti-normal ordering (Husimi $Q$): the candidate.** We look for a map $T_Q$ with
$$
\langle T_Q(a^n(a^\dagger)^m)\rangle=(\sqrt\lambda)^{(n+m)}\langle a^n(a^\dagger)^m\rangle.\tag{21}
$$
This ordering solves the vacuum problem, since $\langle0|aa^\dagger|0\rangle=1\neq0$. Anti-normal ordering is connected to the Husimi $Q$ distribution by
$$
\langle a^n(a^\dagger)^m\rangle=\int\alpha^n(\alpha^*)^m\,Q_1(\alpha)\,d^2\alpha .\tag{22}
$$
$T_Q$ therefore corresponds to a pure stretching map on the space where $Q$ is defined:
$$
T_Q(Q_1(\alpha))\equiv Q_\lambda(\alpha)=\frac1\lambda\,Q_1\!\left(\frac{\alpha}{\sqrt\lambda}\right),\tag{23}
$$
where $Q_1$ is the initial (unstretched) distribution and $Q_\lambda$ is the distribution stretched by a factor $\lambda$. With $\alpha=\sqrt\lambda\,\beta$ one verifies
$$
\int\alpha^n(\alpha^*)^mQ_\lambda(\alpha)\,d^2\alpha=\int\alpha^n(\alpha^*)^m\frac1\lambda Q_1\!\left(\frac{\alpha}{\sqrt\lambda}\right)d^2\alpha=\int\sqrt\lambda^{\,n+m}\beta^n(\beta^*)^mQ_1(\beta)\,d^2\beta .\tag{24}
$$
**Since the Husimi distribution is non-negative**, stretching it always gives another non-negative distribution, which avoids the problem of the Wigner function. Anti-normal ordering is therefore a potential candidate, and the only one of the three.

---

## 7. The pure quantum stretching map $T_Q$: definition, properties, role

**Entropy requirement.** By analogy with the classical stretching requirement, $T_Q$ must increase the entropy of **every** quantum state by the fixed amount $\log\lambda>0$:
$$
S(T_Q(\rho))=S(\rho)+\log\lambda .
$$
Measured on the phase-space ($Q$) representation, $S(\rho)=-\int Q\log Q\,d^2\alpha$, this holds exactly, because Eq. (23) is a uniform area-$\lambda$ stretch.

**$T_Q$ is a physical (CPTP) channel.** $T_Q$ is generated by a Lindblad master equation with Hamiltonian $H=0$ and the single jump operator $L=a^\dagger$:
$$
\frac{d\rho}{dt}=a^\dagger\rho\,a-\frac12\{aa^\dagger,\rho\},\qquad T_Q=e^{t\mathcal L},\quad\lambda=e^{t}.
$$
Being of Lindblad form, it is **completely positive and trace preserving**. It is purely dissipative (there is no Hamiltonian part) and is the quantum-limited phase-insensitive amplifier. Two checks:
* $\frac{d}{dt}\langle a\rangle={\rm Tr}[a\,\mathcal L\rho]=\frac12\langle[a,a^\dagger]a\rangle=\frac12\langle a\rangle$, so $\langle a\rangle\to\sqrt\lambda\langle a\rangle$.
* The vacuum $Q_1=\frac1\pi e^{-|\alpha|^2}$ goes to the thermal state with $\bar n=\lambda-1$, whose $Q_\lambda=\frac{1}{\pi\lambda}e^{-|\alpha|^2/\lambda}=\frac1\lambda Q_1(\alpha/\sqrt\lambda)$, exactly Eq. (23).

The channel therefore increases the entropy of all states uniformly.

**Operator rescaling.** In the sense of expectation values, $\langle T_Q(A)\rangle\equiv{\rm Tr}[A\,T_Q(\rho)]$:
$$
T_Q(a)=\sqrt\lambda\,a,\qquad T_Q(a^\dagger)=\sqrt\lambda\,a^\dagger,\qquad T_Q(X)=\sqrt\lambda\,X,\qquad T_Q(P)=\frac{1}{\sqrt\lambda}P .
$$

**Commutator and uncertainty.** The commutator scales as
$$
T_Q([X,P])=\lambda\,[X,P],
$$
so the uncertainty, which is bounded by the commutator, increases proportionally to $\lambda$. Every state is pushed further from the Heisenberg bound $\hbar/2$, i.e. into the regime where Section 2 showed that classical and quantum entropies coincide.

**Undoing the stretch: a shrinking commutator.** Redefine the operators so as to "undo" the stretching:
$$
\hat X_\lambda=\frac{\hat X}{\sqrt\lambda},\qquad\hat P_\lambda=\frac{\hat P}{\sqrt\lambda}.
$$
Then the stretched states have, in terms of $(\hat X_\lambda,\hat P_\lambda)$, the same uncertainties that the original states had, but
$$
[\hat X_\lambda,\hat P_\lambda]=\frac{i\hbar}{\lambda}\equiv i\hbar_{\rm eff},\qquad\hbar_{\rm eff}\to0\ \text{as}\ \lambda\to\infty .
$$
The quantum-to-classical transition thus corresponds to a **shrinking commutator**. Heisenberg's equations for $\hat X_\lambda,\hat P_\lambda$ reduce to Hamilton's equations, so the classical equations of motion are reproduced in the high-entropy limit.

**Moyal → Poisson.** The quantum Lie algebra is the Moyal bracket,
$$
\{\!\{f,g\}\!\}=\frac{2}{\hbar}\,f\sin\!\Big(\frac{\hbar}{2}\big(\overleftarrow{\partial}_x\overrightarrow{\partial}_p-\overleftarrow{\partial}_p\overrightarrow{\partial}_x\big)\Big)g=\{f,g\}+O(\hbar^2).
$$
In the limit $\lambda\to\infty$, together with $\hbar\to0$ (i.e. $\hbar_{\rm eff}=\hbar/\lambda\to0$), the **Moyal-bracket Lie algebra contracts into the Poisson-bracket Lie algebra**. This is an Inönü–Wigner contraction of the Heisenberg–Weyl algebra. As entropy grows, the quantum structure approaches classical Hamiltonian mechanics.

**Universality: factorisation $T_Q\circ U$.** Mirroring the classical result $R=T\circ U$, any map that increases the entropy of all states by $\log\lambda$ can be factorised as
$$
R_Q=T_Q\circ U ,
$$
where $U$ is a unitary (the quantum canonical, entropy-preserving transformation) and $T_Q$ is the pure stretch. It has not been proven that anti-normal ordering is the unique choice. The key point is that **all maps realising the same group contraction of quantum mechanics into classical mechanics factorise in this way in the limit**. This establishes the universal role of $T_Q$ as *the* pure stretching map toward the classical regime.

---

## 8. The Wigner function under $T_Q$: disappearance of negativity

**$Q$ is the Weierstrass transform of $W$.** The Husimi distribution is the Wigner function smoothed by the vacuum Gaussian:
$$
Q=W\ast G,\qquad G(\alpha)=\frac{2}{\pi}e^{-2|\alpha|^2}.
$$
(Check: $W_{\rm vac}\ast G=\frac{2}{\pi}e^{-2|\alpha|^2}\ast\frac2\pi e^{-2|\alpha|^2}=\frac1\pi e^{-|\alpha|^2}=Q_{\rm vac}$.)

**Scaled convolution.** Applying $T_Q$:
$$
Q_\lambda(\alpha)=(W_\lambda\ast G)(\alpha)=\frac1\lambda(W_1\ast G)\!\left(\frac{\alpha}{\sqrt\lambda}\right).
$$
The left-hand side defines the Wigner function $W_\lambda$ of the stretched state; the right-hand side is the stretched $Q_1$. Scaling acts on both $W_1$ and $G$, but the kernel $G$ on the left keeps its fixed vacuum width.

**Fourier transform.** With $\tilde G(k)=e^{-|k|^2/8}$ and the convolution theorem, $\tilde Q_\lambda(k)=\tilde Q_1(\sqrt\lambda k)=\tilde W_1(\sqrt\lambda k)\tilde G(\sqrt\lambda k)$. Hence
$$
\tilde W_\lambda(k)=\frac{\tilde Q_\lambda(k)}{\tilde G(k)}=\tilde W_1(\sqrt\lambda\,k)\,e^{-(\lambda-1)|k|^2/8}=\tilde W_1(\sqrt\lambda\,k)\,\tilde G(\sqrt{\lambda-1}\,k).
$$
Transforming back,
$$
W_\lambda(\beta)=\Big[\tfrac1\lambda W_1\big(\tfrac{\beta}{\sqrt\lambda}\big)\Big]\ast\Big[\tfrac{1}{\lambda-1}G\big(\tfrac{\beta}{\sqrt{\lambda-1}}\big)\Big].
$$
For the large stretching factors of interest, $\sqrt\lambda\simeq\sqrt{\lambda-1}$, so
$$
\boxed{\;W_\lambda(\beta)=\frac{1}{\lambda(\lambda-1)}\,W_1\!\left(\frac{\beta}{\sqrt{\lambda-1}}\right)\ast G\!\left(\frac{\beta}{\sqrt{\lambda-1}}\right)\;}
$$
The stretched Wigner function is the stretched original Wigner function **convolved with a Gaussian whose width grows like $\sqrt{\lambda-1}$**, i.e. as fast as the stretch itself.

**Emergence of classical behaviour.**
* $W_\lambda$ and $Q_\lambda$ differ only by a convolution with the fixed vacuum kernel $G$, of width $\sim\hbar$, while both distributions spread over a scale $\sim\sqrt\lambda$. **As $\lambda\to\infty$, the Wigner function $W_\lambda$ becomes indistinguishable from the $Q_\lambda$ distribution.** The phase-space description becomes unique and classical-like: the ordering ambiguity disappears.
* **Negative regions of $W$, the signature of quantum interference, are smoothed out by the Gaussian convolution.** For a single photon, $W_\lambda(0)=-\frac{2}{\pi}\frac{1}{(2\lambda-1)^2}\to0$, while the positive part spreads over an area $\propto\lambda$. **For large $\lambda$, $W_\lambda$ becomes positive**: it is a bona fide classical probability density that coincides with $Q_\lambda$.
* Combined with $\hbar_{\rm eff}=\hbar/\lambda\to0$, the dynamics of $W_\lambda$, generated by the Moyal bracket, reduces to the **Liouville equation with the Poisson bracket**. Classical Hamiltonian dynamics is recovered in the high-entropy limit ($\lambda\to\infty$ together with $\hbar\to0$).

**Conclusion.** Highly mixed (high-entropy) quantum states are indistinguishable from classical probability distributions. Their phase-space representation is positive, ordering-independent and evolves by Poisson brackets. Classical mechanics is the high-entropy limit of quantum mechanics, just as non-relativistic mechanics is the low-velocity limit of relativity.
