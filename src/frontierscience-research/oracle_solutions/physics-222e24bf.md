# Entanglement-assisted weak value amplification

## 1. Weak value amplification and the meter response

### Procedure
1. A **meter** is prepared in a state $|\phi\rangle$ and an **ancilla** (the system whose weak value amplifies the signal) in a preselected state $|\Psi_i\rangle$.
2. **The meter and the ancilla are weakly coupled** by an interaction Hamiltonian $\hat H$. In a typical weak value amplification experiment it has the form
$$
\hat H_{\rm int}=\hbar g\,\hat A\otimes\hat F\,\delta(t-t_0),
$$
where $\hat A$ is an ancilla observable, $\hat F$ is a meter observable, and $g$ is the small coupling parameter we want to estimate. The factor $\delta(t-t_0)$ means the interaction is **impulsive**: it happens on a much faster time scale than the natural evolution of the ancilla and of the meter, so the joint evolution is just $e^{-ig\hat A\otimes\hat F}$.
3. **The ancilla is postselected into a pure final state $|\Psi_f\rangle$.** Only the runs where this projective measurement succeeds are kept.

This procedure **effectively prepares an enhanced meter state that includes the effect of the ancilla**:
$$
|\phi'\rangle=\frac{\hat M|\phi\rangle}{\|\hat M|\phi\rangle\|},\qquad
\hat M=\langle\Psi_f|\exp\!\big(-ig\hat A\otimes\hat F\big)|\Psi_i\rangle ,
$$
where $\hat M$ is a Kraus operator acting on the meter. The postselection probability is $P_s=\|\hat M|\phi\rangle\|^2\simeq|\langle\Psi_f|\Psi_i\rangle|^2$.

### Second-order expansion
Expanding the exponential, with the weak values $A_w=\frac{\langle\Psi_f|\hat A|\Psi_i\rangle}{\langle\Psi_f|\Psi_i\rangle}$ and $(A^2)_w=\frac{\langle\Psi_f|\hat A^2|\Psi_i\rangle}{\langle\Psi_f|\Psi_i\rangle}$:
$$
\hat M=\langle\Psi_f|\Psi_i\rangle\Big[1-igA_w\hat F-\frac{g^2}{2}(A^2)_w\hat F^2+{\cal O}(g^3)\Big].
$$
For any meter observable $\hat R$ (all expectation values on the right in $|\phi\rangle$),
$$
\langle\hat R\rangle_{|\phi'\rangle}=\frac{\langle\phi|\hat M^\dagger\hat R\hat M|\phi\rangle}{\langle\phi|\hat M^\dagger\hat M|\phi\rangle}
=\frac{\langle\hat R\rangle+g\,{\rm Re}A_w\,\langle-i[\hat R,\hat F]\rangle+g\,{\rm Im}A_w\,\langle\{\hat R,\hat F\}\rangle+g^2\Big[|A_w|^2\langle\hat F\hat R\hat F\rangle-{\rm Re}\big((A^2)_w\langle\hat R\hat F^2\rangle\big)\Big]}
{1+2g\,{\rm Im}A_w\,\langle\hat F\rangle+g^2\big[|A_w|^2-{\rm Re}(A^2)_w\big]\langle\hat F^2\rangle}
$$
(here ${\rm Re}((A^2)_w\langle\hat R\hat F^2\rangle)$ is shorthand for $\tfrac12[(A^2)_w\langle\hat R\hat F^2\rangle+(A^2)_w^*\langle\hat F^2\hat R\rangle]$). The first-order term follows from $ig(A_w^*\langle\hat F\hat R\rangle-A_w\langle\hat R\hat F\rangle)=g\,{\rm Re}A_w\langle-i[\hat R,\hat F]\rangle+g\,{\rm Im}A_w\langle\{\hat R,\hat F\}\rangle$.

### Linear response
If the second-order terms can be neglected, which requires $g|A_w|\,{\rm Var}(\hat F)^{1/2}\ll1$, then
$$
\boxed{\;\langle\hat R\rangle_{|\phi'\rangle}\approx\langle\hat R\rangle_{|\phi\rangle}+g\,{\rm Re}A_w\,\langle-i[\hat R,\hat F]\rangle_{|\phi\rangle}+g\,{\rm Im}A_w\Big(\langle\{\hat R,\hat F\}\rangle_{|\phi\rangle}-2\langle\hat R\rangle_{|\phi\rangle}\langle\hat F\rangle_{|\phi\rangle}\Big).\;}
$$
The response is linear in $g$ and multiplied by the weak value $A_w$, which can lie far outside the spectrum of $\hat A$ when $\langle\Psi_f|\Psi_i\rangle$ is small. That is the amplification. The price is the small postselection probability $P_s$.

---

## 2. Improving postselection efficiency with entangled ancillas at fixed $A_w$

### Relation between $A_w$ and $P_s$
To leading order $P_s=|\langle\Psi_f|\Psi_i\rangle|^2$, so $|A_w|^2P_s=|\langle\Psi_f|\hat A|\Psi_i\rangle|^2$: large weak values normally come with small $P_s$. **The key point is that different choices of $|\Psi_i\rangle$ and $|\Psi_f\rangle$ can produce the same weak value $A_w$, each with a possibly different postselection probability.** Among them there is an optimal choice that maximises $P_s$. We find it in two steps.

**Maximization 1 (over postselections).** Fix $A_w$ and the preparation $|\Psi_i\rangle$, and maximise $P_s$ over all postselections $|\Psi_f\rangle$. The definition of $A_w$ is equivalent to the linear constraint
$$
\langle\Psi_f|(\hat A-A_w)|\Psi_i\rangle=0 ,
$$
so $|\Psi_f\rangle$ must be orthogonal to $(\hat A-A_w)|\Psi_i\rangle$. The maximisation of $P_s$ is therefore taken over the subspace $V^\perp$ orthogonal to $|\chi\rangle\equiv(\hat A-A_w)|\Psi_i\rangle$. The maximum of $|\langle\Psi_f|\Psi_i\rangle|^2$ over unit vectors in $V^\perp$ is the squared norm of the projection of $|\Psi_i\rangle$ onto $V^\perp$:
$$
\max_{|\Psi_f\rangle\in V^\perp}P_s=1-\frac{|\langle\chi|\Psi_i\rangle|^2}{\langle\chi|\chi\rangle}
=\frac{{\rm Var}(\hat A)_{|\Psi_i\rangle}}{{\rm Var}(\hat A)_{|\Psi_i\rangle}+|A_w-\langle\hat A\rangle|^2},
$$
using $\langle\chi|\chi\rangle={\rm Var}(\hat A)+|A_w-\langle\hat A\rangle|^2$ and $\langle\Psi_i|\chi\rangle=\langle\hat A\rangle-A_w$. When the weak value is larger than any eigenvalue $\Lambda$ of $\hat A$, $|\Lambda|\ll|A_w|$:
$$
\boxed{\;\max_{|\Psi_f\rangle\in V^\perp}P_s\approx\frac{{\rm Var}(\hat A)_{|\Psi_i\rangle}}{|A_w|^2},\qquad
{\rm Var}(\hat A)_{|\Psi_i\rangle}=\langle\Psi_i|\hat A^2|\Psi_i\rangle-\langle\Psi_i|\hat A|\Psi_i\rangle^2 .\;}
$$

**Maximization 2 (over preparations).** This result is then maximised over all preparations $|\Psi_i\rangle$, i.e. we need the largest variance.

### Coupling design: $n$ ancillas
Couple the meter simultaneously to $n$ identical $d$-dimensional ancillas, each through the same single-ancilla observable $\hat a$ (eigenvalues $\lambda_{\max}\ge\dots\ge\lambda_{\min}$). With the interaction of the form above, the meter effectively couples to a single joint ancilla observable
$$
\hat H_{\rm int}=\hbar g\,\hat A\otimes\hat F\,\delta(t-t_0),\qquad \hat A=\sum_{j=1}^n\hat a^{(j)} ,
$$
whose extreme eigenvalues are $n\lambda_{\max}$ and $n\lambda_{\min}$. For any state the variance is bounded by a quarter of the squared spectral width, and the bound is attained by an equal superposition of the extremal eigenvectors. Hence
$$
\boxed{\;\max_{|\Psi_i\rangle}{\rm Var}(\hat A)_{|\Psi_i\rangle}=\frac{n^2}{4}(\lambda_{\max}-\lambda_{\min})^2,\;}
$$
which shows **quadratic scaling with $n$**. For uncorrelated (product) preparations, ${\rm Var}(\hat A)=\sum_j{\rm Var}(\hat a^{(j)})\le\frac n4(\lambda_{\max}-\lambda_{\min})^2$, which is only linear in $n$.

**Joint state.** The preparations with quadratic variance scaling have the maximally entangled (GHZ/NOON) form
$$
\boxed{\;|\Psi_i\rangle=\frac{1}{\sqrt2}\Big(|\lambda_{\max}\rangle^{\otimes n}+e^{i\theta}|\lambda_{\min}\rangle^{\otimes n}\Big),\;}
$$
where $e^{i\theta}$ is an arbitrary relative phase.

**Joint postselection state.** The optimal postselection lies in the same two-dimensional span and is fixed by the constraint $\langle\Psi_f|(\hat A-A_w)|\Psi_i\rangle=0$:
$$
\boxed{\;|\Psi_f\rangle\propto-\big(n\lambda_{\min}-A_w^*\big)|\lambda_{\max}\rangle^{\otimes n}+e^{i\theta}\big(n\lambda_{\max}-A_w^*\big)|\lambda_{\min}\rangle^{\otimes n},\;}
$$
which depends explicitly on the chosen value of $A_w$.

**Resulting weak value and probability.** Direct substitution gives
$\langle\Psi_f|\Psi_i\rangle\propto\frac{n(\lambda_{\max}-\lambda_{\min})}{\sqrt2}$ and $\langle\Psi_f|\hat A|\Psi_i\rangle\propto\frac{n(\lambda_{\max}-\lambda_{\min})}{\sqrt2}A_w$, so
$$
\frac{\langle\Psi_f|\hat A|\Psi_i\rangle}{\langle\Psi_f|\Psi_i\rangle}=A_w,\qquad
P_s=\frac{\frac{n^2}{2}(\lambda_{\max}-\lambda_{\min})^2}{|n\lambda_{\min}-A_w|^2+|n\lambda_{\max}-A_w|^2}\;\approx\;\frac{n^2(\lambda_{\max}-\lambda_{\min})^2}{4|A_w|^2}.
$$

### Fair comparison with uncorrelated ancillas
We consider coupling $n$ **entangled** ancillas to the meter simultaneously. For a fair comparison with the uncorrelated case, the probability of successfully postselecting the $n$ entangled ancillas *once* should be compared with the probability of successfully postselecting a single ancilla (with the same $A_w$) in $n$ independent attempts. A single ancilla has $P_s\approx(\lambda_{\max}-\lambda_{\min})^2/4|A_w|^2$, so $n$ attempts give a success probability with linear scaling in $n$ when $P_s$ is small:
$$
\boxed{\;P_s^{(n)}=1-(1-P_s)^n\approx nP_s .\;}
$$
Entangled ancillas instead achieve **quadratic scaling with $n$**, $P_s^{\rm ent}\approx n^2P_s$. At fixed amplification factor $A_w$, this **improves the postselection efficiency by a factor of $n$**.

---

## 3. Alternative: fixed postselection probability, larger weak value

We can instead **hold the postselection probability fixed and increase the maximum weak value**, by a factor $\sqrt n$ relative to uncorrelated ancillas.

Given a postselection probability $P_s$, any postselected state (up to a global phase) must have the form
$$
\boxed{\;|\Psi_f\rangle=\sqrt{P_s}\,|\Psi_i\rangle+\sqrt{1-P_s}\,e^{i\theta}|\Psi_i^\perp\rangle,\;}
$$
where $|\Psi_i^\perp\rangle$ is an arbitrary state orthogonal to $|\Psi_i\rangle$. Then $\langle\Psi_f|\Psi_i\rangle=\sqrt{P_s}$ and
$$
\boxed{\;A_w=\langle\Psi_i|\hat A|\Psi_i\rangle+\sqrt{\frac{1-P_s}{P_s}}\,e^{-i\theta}\,\langle\Psi_i^\perp|\hat A|\Psi_i\rangle .\;}
$$
By Cauchy–Schwarz, the maximum of $|\langle\Psi_i^\perp|\hat A|\Psi_i\rangle|$ is achieved when $|\Psi_i^\perp\rangle$ is parallel to the component of $\hat A|\Psi_i\rangle$ in the complementary subspace orthogonal to $|\Psi_i\rangle$, i.e. $|\Psi_i^\perp\rangle\propto(1-|\Psi_i\rangle\langle\Psi_i|)\hat A|\Psi_i\rangle$. The maximum value is
$$
\boxed{\;\langle\Psi_i^\perp|\hat A|\Psi_i\rangle=\big\|\hat A|\Psi_i\rangle-\langle\Psi_i|\hat A|\Psi_i\rangle|\Psi_i\rangle\big\|=\sqrt{{\rm Var}(\hat A)_{|\Psi_i\rangle}} .\;}
$$
Hence the largest weak value obtainable from $|\Psi_i\rangle$ with a small postselection probability $P_s$ is approximately
$$
\boxed{\;\max|A_w|\approx\sqrt{\frac{{\rm Var}(\hat A)_{|\Psi_i\rangle}}{P_s}} .\;}
$$
With the entangled state, ${\rm Var}(\hat A)=\frac{n^2}{4}(\lambda_{\max}-\lambda_{\min})^2$ and $\max|A_w|\approx\frac{n(\lambda_{\max}-\lambda_{\min})}{2\sqrt{P_s}}$. With $n$ uncorrelated ancillas, ${\rm Var}\propto n$ and $\max|A_w|\propto\sqrt n$. **At fixed $P_s$, entanglement increases the maximum weak value by a factor $\sqrt n$.**

---

## 4. Fisher information: how much information survives postselection?

### Preliminaries
For a pure state $|\Phi_g\rangle$ carrying information about $g$, the quantum Fisher information is
$$
\boxed{\;I(g)=4\left(\frac{\partial\langle\Phi_g|}{\partial g}\frac{\partial|\Phi_g\rangle}{\partial g}-\left|\frac{\partial\langle\Phi_g|}{\partial g}|\Phi_g\rangle\right|^2\right).\;}
$$
For a general interaction $|\Phi_g\rangle=\exp(-ig\hat H)|\Phi\rangle$, $\partial_g|\Phi_g\rangle=-i\hat H|\Phi_g\rangle$ and this reduces to the simpler form
$$
\boxed{\;I(g)=4\,{\rm Var}(\hat H)_{|\Phi\rangle}.\;}
$$
Here the Hamiltonian is $\hat H_{\rm int}=\hbar g\,\hat A\otimes\hat F\,\delta(t-t_0)$, whose integrated generator is $\hat H=\hat A\otimes\hat F$. $\hat A=\sum_{j=1}^n\hat a^{(j)}$ is a sum of $n$ ancilla observables $\hat a$ of dimension $d$, and $\hat F$ is a meter observable. We compare the quantum Fisher information $I(g)$ about $g$ contained in the post-interaction state
$$
|\Phi_g\rangle=\exp\!\big(-ig\hat A\otimes\hat F\big)|\Psi_i\rangle|\phi\rangle
$$
with the Fisher information $I'(g)$ that remains in the postselected state $\sqrt{P_s}\,|\phi'\rangle$. With no postselection, since $|\Psi_i\rangle|\phi\rangle$ is a product state,
$$
\boxed{\;I(g)=4\Big(\langle\hat A^2\rangle_{|\Psi_i\rangle}\langle\hat F^2\rangle_{|\phi\rangle}-\big(\langle\hat A\rangle_{|\Psi_i\rangle}\langle\hat F\rangle_{|\phi\rangle}\big)^2\Big).\;}
$$
For an unbiased meter ($\langle\hat F\rangle_{|\phi\rangle}=0$) this is $I(g)=4\langle\hat A^2\rangle_{|\Psi_i\rangle}{\rm Var}(\hat F)_{|\phi\rangle}$.

### Information in each postselected outcome
Projectively measuring the ancillas to make a postselection produces $d^n$ independent outcomes, corresponding to some orthonormal basis $\{|\Psi_i^{(k)}\rangle\}_{k=1}^{d^n}$ of the joint ancilla space. We take $|\Psi_i^{(1)}\rangle\equiv|\Psi_f\rangle$, the strategically chosen postselection. In the linear response regime with $g\ll1$, each outcome prepares a particular meter state
$$
|\phi_k'\rangle\propto\big(\langle\Psi_i^{(k)}|\exp(-ig\hat H)|\Psi_i\rangle\big)|\phi\rangle\approx\big(1-igA_w^{(k)}\hat F\big)|\phi\rangle ,
$$
with probability $P^{(k)}\approx|\langle\Psi_i^{(k)}|\Psi_i\rangle|^2$, governed by a different weak value
$$
A_w^{(k)}=\frac{\langle\Psi_i^{(k)}|\hat A|\Psi_i\rangle}{\langle\Psi_i^{(k)}|\Psi_i\rangle}.
$$
Evaluating the Fisher information contained in each postselected (unnormalised) state $\sqrt{P^{(k)}}|\phi'_k\rangle=\langle\Psi_i^{(k)}|\Psi_i\rangle(1-igA_w^{(k)}\hat F)|\phi\rangle$ to second order in $g$ gives
$$
\boxed{\;I^{(k)}(g)\approx4P^{(k)}|A_w^{(k)}|^2\Big[{\rm Var}(\hat F)_{|\phi\rangle}-\langle\hat F^2\rangle_{|\phi\rangle}\Big(2g\,{\rm Im}A_w^{(k)}+|gA_w^{(k)}|^2{\rm Var}(\hat F)_{|\phi\rangle}\Big)\Big].\;}
$$
Summing over all outcomes and using completeness, $\sum_kP^{(k)}|A_w^{(k)}|^2=\sum_k|\langle\Psi_i^{(k)}|\hat A|\Psi_i\rangle|^2=\langle\hat A^2\rangle_{|\Psi_i\rangle}$, the information in the $d^n$ postselections is
$$
\boxed{\;\sum_{k=1}^{d^n}I^{(k)}(g)\approx4\langle\hat A^2\rangle_{|\Psi_i\rangle}{\rm Var}(\hat F)_{|\phi\rangle}-{\cal O}(g).\;}
$$
For an unbiased meter this equals $I(g)$: the postselection measurement as a whole loses no information at leading order. It merely redistributes it among the outcomes.

### The special postselection $k=1$
Use an unbiased meter, $\langle\hat F\rangle_{|\phi\rangle}=0$, so $\langle\hat F^2\rangle={\rm Var}(\hat F)$. Use the free phase of the postselection to make $A_w^{(1)}$ real, which changes neither $|A_w^{(1)}|$ nor $P_s$, so the ${\cal O}(g)$ term drops. Normalise the meter observable so that ${\rm Var}(\hat F)_{|\phi\rangle}=1$; otherwise every Fisher information below carries the same overall factor ${\rm Var}(\hat F)$. Then
$$
\boxed{\;I^{(1)}(g)\approx4P_s|A_w^{(1)}|^2\Big[1-|gA_w^{(1)}|^2{\rm Var}(\hat F)_{|\phi\rangle}\Big].\;}
$$
For this strategically chosen postselection with small $P_s^{(1)}$ and maximised $|A_w^{(1)}|$ (§3), $P_s|A_w^{(1)}|^2\approx{\rm Var}(\hat A)_{|\Psi_i\rangle}$, and the Fisher information is
$$
\boxed{\;I^{(1)}(g)\approx4\,{\rm Var}(\hat A)_{|\Psi_i\rangle}\Big[1-|gA_w^{(1)}|^2{\rm Var}(\hat F)\Big]
=I(g)\left[\frac{{\rm Var}(\hat A)_{|\Psi_i\rangle}}{\langle\hat A^2\rangle_{|\Psi_i\rangle}}\right]\Big[1-|gA_w^{(1)}|^2{\rm Var}(\hat F)\Big],\;}
$$
with $I(g)=4\langle\hat A^2\rangle_{|\Psi_i\rangle}$. **Nearly all the Fisher information can be concentrated into a single, but rarely postselected, meter state.** The remaining information is distributed among the $(d^n-1)$ remaining states and could be retrieved in principle. The special postselected meter state suffers an overall reduction factor $\eta={\rm Var}(\hat A)/\langle\hat A^2\rangle$, as well as a small loss $|gA_w^{(1)}|^2{\rm Var}(\hat F)$. Most weak value amplification experiments operate in the linear response regime $g|A_w^{(1)}|{\rm Var}(\hat F)\ll1$, where this remaining loss is negligible.

### Efficiency factor and comparison
Define the efficiency factor
$$
\boxed{\;\eta=\frac{{\rm Var}(\hat A)_{|\Psi_i\rangle}}{\langle\hat A^2\rangle_{|\Psi_i\rangle}}\le1 .\;}
$$
In the linear response regime $g|A_w|{\rm Var}(\hat F)^{1/2}\ll1$, with an initially unbiased meter $\langle\hat F\rangle_{|\phi\rangle}=0$ and a fixed $P_s\ll1$ with maximal $|A_w|$, the information left in $\sqrt{P_s}|\phi'\rangle$ is
$$
\boxed{\;I'(g)\approx\eta\,I(g)\big[1-|gA_w|^2{\rm Var}(\hat F)\big]\le I(g).\;}
$$
**The efficiency $\eta$ reaches $1$ when $\langle\hat A\rangle_{|\Psi_i\rangle}=0$.** The entangled state of §2 with $\lambda_{\min}=-\lambda_{\max}$ satisfies this. Then nearly all the original Fisher information $I(g)$ is concentrated into the one rarely obtained $|\phi'\rangle$, reduced only by $|gA_w|^2{\rm Var}(\hat F)\ll1$. The remaining information is distributed among the discarded meter states and could be retrieved in principle.

### Example: qubits, $\hat F=\hat a=\sigma_z$
Take ancilla qubits with $\hat a=\sigma_z$ ($\lambda_{\max,\min}=\pm1$) and a meter qubit with $\hat F=\sigma_z$ prepared in $|+\rangle$ (unbiased). Use the GHZ preparation $|\Psi_i\rangle=(|0\rangle^{\otimes n}+e^{i\theta}|1\rangle^{\otimes n})/\sqrt2$. Then $\langle\hat A\rangle=0$, $\langle\hat A^2\rangle={\rm Var}(\hat A)=n^2$, so the initial state yields
$$
\eta=1,\qquad {\rm Var}(\hat F)=1,\qquad I(g)=4\langle\hat A^2\rangle_{|\Psi_i\rangle}=4n^2 .
$$
The interaction $e^{-ig\hat A\sigma_z}$ rotates the meter about $z$ by the angle $\varphi=2g$ per unit eigenvalue, so estimating $g$ means estimating $g=\varphi/2$. Here $I'(g)\approx4n^2[1-|gA_w|^2]$, and the Cramér–Rao bound for the precision of any unbiased estimation of $g=\varphi/2$ using $|\phi'\rangle$ is
$$
\boxed{\;\big[I'(g)\big]^{-1/2}=\frac{1}{2n}\big[1-|gA_w|^2\big]^{-1/2},\;}
$$
or $(M I')^{-1/2}$ for $M$ postselected events. This confirms the optimal (Heisenberg) $1/n$ scaling, despite the low postselection probability.

---

## 5. Conclusion
- Weak value amplification postselects the ancilla to give the meter a linear response $\propto gA_w$ with a large weak value $A_w$, at the cost of a small postselection probability $P_s\approx{\rm Var}(\hat A)/|A_w|^2$, which is the optimum over postselections.
- Because $P_s$ is limited by ${\rm Var}(\hat A)$, adding quantum resources helps. Coupling the meter to $n$ ancillas prepared in the maximally entangled state $\frac1{\sqrt2}(|\lambda_{\max}\rangle^{\otimes n}+e^{i\theta}|\lambda_{\min}\rangle^{\otimes n})$ raises ${\rm Var}(\hat A)$ to $\frac{n^2}{4}(\lambda_{\max}-\lambda_{\min})^2$.
- **If the amplification factor is held fixed, $n$ entangled ancillas improve the postselection probability by a factor of $n$** compared with $n$ attempts using uncorrelated ancillas ($n^2P_s$ versus $1-(1-P_s)^n\approx nP_s$). If instead $P_s$ is held fixed, the maximal weak value grows by a factor $\sqrt n$.
- The postselected meter state retains $I'(g)\approx\eta I(g)[1-|gA_w|^2{\rm Var}(\hat F)]$ with $\eta={\rm Var}(\hat A)/\langle\hat A^2\rangle\to1$ for $\langle\hat A\rangle=0$. Almost all the Fisher information is concentrated in the rare postselected events, and the rest is in principle recoverable from the discarded ones.
- This improvement in postselection efficiency addresses a key practical shortcoming of weak value amplification. It achieves the **optimal scaling with $n$ expected from quantum metrology**: $I(g)=4n^2$ and $[I']^{-1/2}=\frac{1}{2n}[1-|gA_w|^2]^{-1/2}$. Weak value amplification can therefore nearly saturate the quantum Cramér–Rao bound despite the low efficiency of postselection.
