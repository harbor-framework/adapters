# Infinite quantum Fisher information with a finite mean photon number in a Mach–Zehnder interferometer

## 0. Background and goal

Precise interferometric phase measurement is essential for quantum metrology, imaging and quantum information processing, and the Mach–Zehnder interferometer (MZI) is the paradigm for it. A phase $\theta$ in one arm is read out from the photon statistics at the two output ports.

- With classical (coherent) light the phase uncertainty is limited by the shot-noise limit (SNL), $\Delta\theta\sim1/\sqrt{\langle\hat N\rangle}$.
- **Coherent light combined with squeezed vacuum** in the second input port can **surpass the SNL**.
- **NOON states**, which exploit quantum entanglement between the arms, achieve higher sensitivity and approach the **Heisenberg limit (HL)**. The HL has a generally accepted bound $\Delta\theta\sim1/\langle\hat N\rangle$.
- **Some studies suggest that the HL could be violated when the number of particles fluctuates**. This has raised interest in what the Heisenberg limit means for an unfixed particle number, and it is the question addressed here.

The figure of merit is the **quantum Fisher information (QFI)**, which through the **quantum Cramér–Rao bound (CRB)** determines the best achievable phase sensitivity. **Optimal quantum states and optimal measurements (an optimal POVM) are necessary** to reach the maximum QFI and the minimum CRB. We study the standard MZI and a modified MZI (MMZI) in which the first beam splitter is replaced by an entangled-photon source, and design input states and measurements that enhance the phase sensitivity. We construct a state with **finite $\langle\hat N\rangle$ but divergent QFI** around a target phase $\theta_0$.

---

## 1. Fisher information, QFI and the Cramér–Rao bound

For a phase-dependent state $|\Psi_\phi\rangle$ measured with a POVM $\{\hat E(\xi)\}$, the outcome probabilities are $P(\xi|\phi)=\langle\Psi_\phi|\hat E(\xi)|\Psi_\phi\rangle$ and the **Fisher information** is
$$
\boxed{\;F_{\hat E(\xi)}[|\Psi_\phi\rangle]=\sum_\xi P(\xi|\phi)\left(\frac{\partial\ln P(\xi|\phi)}{\partial\phi}\right)^2 .\;}
$$
The **Cramér–Rao bound** limits the error of any unbiased estimator:
$$
\boxed{\;\Delta\phi\ge\frac{1}{\sqrt{F_{\hat E(\xi)}[|\Psi_\phi\rangle]}} .\;}
$$
The FI is **additive**: for $M$ repeated independent trials of the same measurement the FI is $M\times F_{\hat E(\xi)}[|\Psi_\phi\rangle]$, so
$$
\Delta\phi\ge\frac{1}{\big(M\times F_{\hat E(\xi)}[|\Psi_\phi\rangle]\big)^{1/2}} .
$$
The **QFI** of $|\Psi_\phi\rangle$ is the maximum over all measurements,
$$
\boxed{\;F_Q[|\Psi_\phi\rangle]:=\max_{\{\hat E(\xi)\}}F_{\hat E(\xi)}[|\Psi_\phi\rangle],\;}
$$
and it is **saturated by a particular POVM**. For a pure state $|\Psi_\phi\rangle=e^{-i\phi\hat G}|\Psi\rangle$, $F_Q=4\,{\rm Var}(\hat G)$.

### QFI for a state with a fluctuating photon number
Consider an input state
$$
\boxed{\;|\Psi\rangle=\sum_N\sqrt{P(N)}\,|\psi_N\rangle,\;}
$$
where $P(N)$ is the probability distribution over the total photon number $N$ and $|\psi_N\rangle$ has exactly $N$ photons in the two modes $a,b$. The phase shift $e^{i\theta\hat n_a}$ and the beam splitters conserve $N$. Without an external phase reference, the coherences between different-$N$ sectors cannot be exploited: the physically relevant measurements, including photon counting, are block diagonal in $N$. The Fisher information therefore splits into sectors:
$$
F_{\hat E(N,\Delta)}[|\Psi\rangle]=\sum_NP(N)\,F_{\hat E}[|\psi_N\rangle]\le\sum_NP(N)\,F_Q[|\psi_N\rangle].
$$
In each sector $F_Q[|\psi_N\rangle]=4{\rm Var}(\hat n_a)_{\psi_N}\le4\cdot\frac{N^2}{4}=N^2$, since $0\le n_a\le N$. Equality holds only for the NOON state $(|N,0\rangle+e^{i\chi}|0,N\rangle)/\sqrt2$. Hence the **QFI is proportional to the average of the square of the photon number**:
$$
\boxed{\;F_{\hat E(N,\Delta)}[|\Psi\rangle]\le\max_{|\Psi\rangle}F_Q[|\Psi\rangle]=\langle\hat N^2\rangle ,\;}
$$
and **equality can only be achieved when $|\Psi\rangle$ is a superposition of NOON states**. The QFI is therefore governed by $\langle\hat N^2\rangle$, not by $\langle\hat N\rangle^2$. A photon-number distribution with **finite mean but divergent second moment** gives a finite-resource state with infinite QFI.

---

## 2. Input state at the first beam splitter

We take the state in the two arms of the interferometer to be a superposition of NOON states with a Riemann-zeta (power-law) photon-number distribution. This is the state delivered by the first beam splitter, or produced directly in the arms by the source:
$$
\boxed{\;|\Psi(x)\rangle=\frac{1}{\sqrt{\zeta(x)}}\sum_{N=1}^{\infty}\frac{1}{\sqrt{N^x}}\;\frac{|N\rangle_a|0\rangle_b+|0\rangle_a|N\rangle_b}{\sqrt2},\qquad x\in(1,+\infty),\;}
$$
where $\zeta(x)=\sum_{N=1}^\infty1/N^x$ is the Riemann zeta function, which here is the normalization factor. Thus $P(N)=N^{-x}/\zeta(x)$ and $\sum_NP(N)=1$.

---

## 3. Average photon number

$$
\langle\hat N\rangle=\sum_NN\,P(N)=\frac{1}{\zeta(x)}\sum_{N=1}^\infty\frac{N}{N^x}=\frac{\zeta(x-1)}{\zeta(x)},\qquad
\langle\hat N^2\rangle=\frac{\zeta(x-2)}{\zeta(x)} .
$$
For $x=3$:
$$
\boxed{\;\langle\hat N\rangle=\frac{1}{\zeta(3)}\sum_{N=1}^\infty\frac{N}{N^3}=\frac{\zeta(2)}{\zeta(3)}=\frac{\pi^2/6}{1.2021}\approx1.369\;}
$$
This is **finite**: on average only about 1.4 photons are used. Meanwhile
$$
\langle\hat N^2\rangle=\frac{1}{\zeta(3)}\sum_{N=1}^\infty\frac{N^2}{N^3}=\frac{\zeta(1)}{\zeta(3)}=\frac{1}{\zeta(3)}\sum_N\frac1N=\infty
$$
(harmonic series). The appropriate probability distribution keeps the photon number finite while the second moment diverges. More generally, any power law $P(N)=C/N^\alpha$ with $\alpha>2$ has a finite mean. For this protocol we also require $\langle\hat N^2\rangle=\infty$, i.e. $\alpha\le3$, so both conditions hold for $2<\alpha\le3$; $x=3$ is the boundary case.

---

## 4. Evolution through the interferometer and the second beam splitter

**Phase shift.** The phase $\theta$ in arm $a$ acts as $e^{i\theta\hat n_a}$:
$$
|\Psi_\theta\rangle=\frac{1}{\sqrt{\zeta(x)}}\sum_{N=1}^\infty\frac{1}{\sqrt{N^x}}\;\frac{e^{iN\theta}|N\rangle_a|0\rangle_b+|0\rangle_a|N\rangle_b}{\sqrt2}.
$$
Each NOON component acquires the $N$-fold phase $N\theta$, which is the origin of the $N^2$ Fisher information per sector.

**Second beam splitter** ($50{:}50$): $\hat a^\dagger\to(\hat a^\dagger+\hat b^\dagger)/\sqrt2$, $\hat b^\dagger\to(\hat b^\dagger-\hat a^\dagger)/\sqrt2$. Then
$$
|N,0\rangle\to\frac{(\hat a^\dagger+\hat b^\dagger)^N}{\sqrt{N!}\,2^{N/2}}|0\rangle=\sum_{m=0}^N\sqrt{\frac{C_N^m}{2^N}}\,|m\rangle_a|N-m\rangle_b,\qquad
|0,N\rangle\to\sum_{m=0}^N(-1)^m\sqrt{\frac{C_N^m}{2^N}}\,|m\rangle_a|N-m\rangle_b ,
$$
so the output state is
$$
\boxed{\;|\Psi_{\rm out}(\theta)\rangle=\frac{1}{\sqrt{\zeta(x)}}\sum_{N=1}^\infty\frac{1}{\sqrt{N^x}}\sum_{m=0}^N\sqrt{\frac{C_N^m}{2^{N+1}}}\Big[e^{iN\theta}+(-1)^m\Big]|m\rangle_a|N-m\rangle_b .\;}
$$
With $n_a=m=\frac{N-\Delta}{2}$ and $n_b=N-m=\frac{N+\Delta}{2}$, the photon-counting probabilities are
$$
P(N,\Delta|\theta)=P(N)\,\frac{C_N^{(N-\Delta)/2}}{2^N}\Big[1+(-1)^{(N-\Delta)/2}\cos N\theta\Big].
$$

---

## 5. Quantum Fisher information: divergence at finite $\langle\hat N\rangle$

**Each sector.** For the NOON component, ${\rm Var}(\hat n_a)=N^2/4$, so $F_Q[\psi_N]=N^2$, the maximum possible at fixed $N$.

**Total.** Since $|\Psi(x)\rangle$ is a superposition of NOON states, it saturates the bound of §1:
$$
F_Q(\theta)=\sum_{N=1}^\infty P(N)\,N^2=\langle\hat N^2\rangle=\frac{\zeta(x-2)}{\zeta(x)}\;\xrightarrow{\;x=3\;}\;\frac{\zeta(1)}{\zeta(3)}=\frac{1}{\zeta(3)}\sum_{N=1}^\infty\frac1N\;\longrightarrow\;\infty ,
$$
while $\langle\hat N\rangle=\zeta(2)/\zeta(3)\approx1.369$ stays finite.

**Superposed state in the interferometer with dual-Fock sectors.** The same zeta weighting applied to the interferometer's dual-Fock sectors, $\sum_N\sqrt{N^{-3}/\zeta(3)}\,|N\rangle_a|N\rangle_b$ (§6), whose sector QFI is $2N^2+2N$, gives the QFI of the superposed state
$$
\boxed{\;F_Q(\phi)=\sum_{N=1}^{\infty}\frac{N^{-3}}{\zeta(3)}\big(2N^2+2N\big)=\frac{2\times\zeta(1)}{\zeta(3)}+\frac{2\times\zeta(2)}{\zeta(3)}\;\rightarrow\;\infty ,\;}
$$
because $\zeta(1)=\sum_N1/N$ diverges, while the mean photon number stays finite, $\langle\hat N\rangle=2\zeta(2)/\zeta(3)\approx2.74$. Both versions of the zeta-weighted state therefore have infinite QFI at finite $\langle\hat N\rangle$.

**Why this happens.** The QFI is the average of $N^2$ (the sector QFI $\propto N^2$), whereas the resource is the average of $N$. A heavy-tailed $P(N)\propto N^{-3}$ makes the first moment converge ($\sum N^{-2}$) but the second diverge ($\sum N^{-1}$). The rare, very large NOON components, each with Heisenberg sensitivity $1/N$, dominate the information while costing almost nothing on average. The CRB, $\Delta\theta\ge1/\sqrt{MF_Q}\to0$, is then formally below the "Heisenberg limit" $1/\langle\hat N\rangle$ in a neighbourhood of $\theta_0$. This shows that for a fluctuating photon number the relevant bound is $1/\sqrt{\langle\hat N^2\rangle}$, not $1/\langle\hat N\rangle$. In practice the gain comes from rare events, so many repetitions $M$ are needed before the asymptotic CRB is approached.

---

## 6. An alternative strategy, easier to test experimentally: dual Fock states

NOON states with large $N$ are extremely hard to generate. **Dual Fock states are much easier to produce than NOON states when the photon number grows high**: they come directly from parametric down-conversion. We therefore propose an **alternative protocol using dual Fock states $|N\rangle_a|N\rangle_b$ as the input of the MZI** (Holland–Burnett scheme). Their natural photon-number superposition is the two-mode squeezed vacuum (TMSV) produced by an entangled-photon (SPDC) source:
$$
\boxed{\;|\Psi\rangle_{\rm in}=\sum_{N=0}^\infty\sqrt{p_N(\langle\hat N\rangle)}\;|N\rangle_a|N\rangle_b,\qquad p_N(\langle\hat N\rangle)=(1-t_{\langle\hat N\rangle})\,t_{\langle\hat N\rangle}^N,\quad t_{\langle\hat N\rangle}=\frac{1}{1+2/\langle\hat N\rangle},\;}
$$
where $\langle\hat N\rangle$ is the mean total photon number ($\langle N\rangle_{\rm pair}=\langle\hat N\rangle/2$).

**Intermediate (in-arm) state.** With the first beam splitter $\hat a^\dagger\to(\hat a^\dagger+\hat b^\dagger)/\sqrt2$, $\hat b^\dagger\to(\hat b^\dagger-\hat a^\dagger)/\sqrt2$, we have $\hat a^\dagger\hat b^\dagger\to\frac12(\hat b^{\dagger2}-\hat a^{\dagger2})$. Expanding $(\hat b^{\dagger2}-\hat a^{\dagger2})^N/(N!\,2^N)$ binomially and symmetrising $k\leftrightarrow N-k$:
$$
\boxed{\;|\Psi\rangle=\sum_{k=0}^{N}(-1)^k\,C_N^k\,\frac{\sqrt{(2N-2k)!\,(2k)!}}{N!\,2^{N+1/2}}\times\frac{(-1)^N|2N-2k\rangle_a|2k\rangle_b+|2k\rangle_a|2N-2k\rangle_b}{\sqrt2}\;}
$$
For example, $N=1$ gives the Hong–Ou–Mandel state $(|0,2\rangle-|2,0\rangle)/\sqrt2$. The state is a superposition of only even photon-number splittings, with weight spread over all $k$. (The sign factors $(-1)^k$ and $(-1)^N$ follow from the real beam-splitter convention used here; they change with the beam-splitter phase convention and do not affect the QFI below.)

**QFI of the dual Fock state.** In the Schwinger representation $|N\rangle_a|N\rangle_b=|j=N,m=0\rangle$, and the first beam splitter maps $\hat J_z\to\hat J_x$. Hence
$$
{\rm Var}(\hat n_a)_{\rm in\,arm}={\rm Var}(\hat J_x)=\tfrac12\big[j(j+1)-m^2\big]=\tfrac12N(N+1),
$$
and the QFI of the intermediate state is
$$
\boxed{\;F_Q=4\cdot\tfrac12N(N+1)=2N^2+2N .\;}
$$
For a total of $2N$ photons this is about half of the NOON value $(2N)^2$, but it still scales as the square of the photon number.

**QFI of the TMSV input.** The geometric distribution is fixed entirely by the mean total photon number $\langle\hat N\rangle$: the mean pair number is $\bar n=t_{\langle\hat N\rangle}/(1-t_{\langle\hat N\rangle})=\langle\hat N\rangle/2$ and $\sum_Np_NN^2=2\bar n^2+\bar n$. In the TMSV formulas of this section we use the shorthand $\langle\hat N^2\rangle\equiv(2\bar n)^2$, the square of the mean total photon number of the Gaussian source. Then
$$
\boxed{\;F_Q^{\rm TMSV}=\sum_{N=0}^\infty p_N(\langle\hat N\rangle)\,(2N^2+2N)=4\bar n^2+4\bar n=\langle\hat N^2\rangle+2\langle\hat N\rangle .\;}
$$
**Comparison with NOON states.** Take a superposition of NOON states with the same probability distribution as the TMSV, $|\Psi\rangle=\sum_{N=0}^\infty\sqrt{p_N(\langle\hat N\rangle)}\,(|2N\rangle_a|0\rangle_b+|0\rangle_a|2N\rangle_b)/\sqrt2$. Its QFI is
$$
\boxed{\;F_Q^{\rm NOON}=\sum_{N=0}^\infty p_N(\langle\hat N\rangle)\,4N^2=8\bar n^2+4\bar n=2\langle\hat N^2\rangle+2\langle\hat N\rangle .\;}
$$
The NOON superposition saturates the bound of §1 (its QFI equals the second moment $\sum_Np_N(2N)^2$ of its own total photon number). The dual-Fock/TMSV strategy reaches about half of it, so a given QFI requires a higher average photon number (about $\sqrt2$ times more photons at large $\langle\hat N\rangle$). With the zeta distribution it uses $\langle\hat N\rangle\approx2.74$ instead of $1.37$, but its QFI still diverges (§5). In exchange it is far easier to implement and test.

---

## 7. Experimental implementation and the QFI-saturating measurement

**Optimal input state.** The superposition of NOON states $|\Psi(x)\rangle$, with $x=3$ (or any $2<x\le3$), in the two arms. The practical alternative is the dual-Fock/TMSV state from an SPDC source. In the MMZI the entangled-photon source replaces the first beam splitter and feeds the correlated state directly into the arms.

**Measurement basis (POVM).** Photon-number-resolving detectors at the two output ports after the second beam splitter implement
$$
\boxed{\;\hat E(N,\Delta)\;\Leftrightarrow\;\hat E'(n_a,n_b)\;\Leftrightarrow\;\Big|\tfrac{N-\Delta}{2}\Big\rangle_a\Big\langle\tfrac{N-\Delta}{2}\Big|_a\otimes\Big|\tfrac{N+\Delta}{2}\Big\rangle_b\Big\langle\tfrac{N+\Delta}{2}\Big|_b ,\;}
$$
with $N=n_a+n_b$ the total photon number and $\Delta=n_b-n_a$ the difference. $\hat E(n_a,n_b)$ and $\hat E(N,\Delta)$ are complete:
$$
\sum_{n_a,n_b}\hat E(n_a,n_b)=\sum_N\sum_{\Delta=-N}^{N}\hat E(N,\Delta)=\hat I .
$$
**It saturates the QFI.** Using the probabilities of §4, write $m=(N-\Delta)/2$ and note $\sum_{m\ {\rm even}}C_N^m=\sum_{m\ {\rm odd}}C_N^m=2^{N-1}$. In each $N$ sector,
$$
F_{\hat E}[\psi_N]=\sum_m\frac{C_N^m}{2^N}\frac{N^2\sin^2N\theta}{1+(-1)^m\cos N\theta}
=\frac{N^2\sin^2N\theta}{2}\Big[\frac{1}{1+\cos N\theta}+\frac{1}{1-\cos N\theta}\Big]=N^2 ,
$$
for every $\theta$ with $\sin N\theta\neq0$. Hence
$$
F_{\hat E(N,\Delta)}[|\Psi_\theta\rangle]=\sum_NP(N)N^2=\langle\hat N^2\rangle=F_Q\;(\to\infty\text{ for }x=3).
$$
The counting POVM saturates the QFI in a neighbourhood of the target phase $\theta_0$. In practice $\theta_0$ is chosen, with a known control phase in the reference arm, away from the isolated points where $N\theta_0$ is a multiple of $\pi$. Because the detection resolves $N$, the sector decomposition of §1 is realised physically. For the dual-Fock/TMSV input the same photon-number-resolving detection (equivalently, the photon-number difference $\Delta$ conditioned on $N$) saturates $2N^2+2N$ in the neighbourhood of the working point $\theta_0\to0$.

**Summary of the scheme.**
1. Prepare $|\Psi(3)\rangle=\zeta(3)^{-1/2}\sum_NN^{-3/2}(|N,0\rangle+|0,N\rangle)/\sqrt2$ in the arms ($\langle\hat N\rangle=\zeta(2)/\zeta(3)\approx1.37$). The easier alternative is a TMSV/dual-Fock source, which needs more photons.
2. Imprint $\theta$ in arm $a$ and recombine on a 50:50 beam splitter.
3. Count photons at both outputs with number-resolving detectors (POVM $\hat E(N,\Delta)$) and estimate $\theta$ by maximum likelihood near $\theta_0$.
4. The Fisher information $\sum_NP(N)N^2=\zeta(1)/\zeta(3)$ diverges while $\langle\hat N\rangle$ remains finite, and the CRB $\Delta\theta\ge1/\sqrt{MF}$ falls below $1/\langle\hat N\rangle$.
