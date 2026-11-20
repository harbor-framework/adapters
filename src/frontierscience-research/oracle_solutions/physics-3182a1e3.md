# Postselected von Neumann measurement on superpositions of Gaussian and Laguerre–Gaussian modes

## 1. Model setup: generation and description of the Gaussian + LG$_{01}$ superposition

### 1.1 Experimental generation
To create a superposition of Gaussian and $LG_{01}$ modes, we can use a **Mach–Zehnder interferometer**. The initial beam splitter divides the input Gaussian beam into two paths, and each optical path passes through a hologram, creating a superposition of Gaussian and $LG_{01}$ modes. This is achieved by placing a **hologram with a dislocation** (a fork grating, or equivalently a spiral phase plate or SLM pattern imprinting $e^{i\phi}$) in one arm of the interferometer, while the other arm keeps the fundamental mode. The second beam splitter recombines the arms. The method offers a distinct advantage: **by attenuating each arm (neutral-density filters) and using phase plates (or a delay), one can produce arbitrary amplitude and relative-phase superpositions without modifying the experimental setup.** The interference pattern produced by the superposition of the $LG_{00}$ and $LG_{01}$ modes demonstrates this capability: the dark vortex core is displaced off axis, by an amount set by $\gamma$ and in a direction set by $\varphi$.

The superposition is analysed by imaging the transverse intensity on a CCD camera, by interference with a reference beam to read out the phase, and by mode projection (hologram plus single-mode fibre) to measure the $\gamma$ and $\varphi$ content.

### 1.2 Mathematical description
An arbitrary superposition of the $LG_{00}$ mode and the $LG_{01}$ mode, with relative amplitude $\gamma$ and arbitrary relative phase $\varphi$ (also denoted $\delta$ in the experiment), is
$$
|\Psi_i\rangle=\frac{1}{\sqrt{1+\gamma^2}}\Big[|\phi_0\rangle+\gamma e^{i\varphi}|\phi_1\rangle\Big],\qquad
|\phi_l\rangle=\int dx\,dy\;\phi_l(x,y)\,|x\rangle|y\rangle ,
$$
where the amplitude distribution of the LG modes with radial index $p=0$ is
$$
\phi_l(x,y)=N\,\big[x+iy\,{\rm sgn}(l)\big]^{|l|}\exp\!\left(-\frac{x^2+y^2}{2\sigma^2}\right).
$$
Here $\sigma$ is the width (variance parameter) of the $l=0$ state, ${\rm sgn}(\cdot)$ is the sign function, and $N$ is a normalising constant ensuring $\int dx\,dy\,|\phi_l(x,y)|^2=1$.

### 1.3 Algebraic (two-mode) description
The LG modes can be generated from the fundamental Gaussian mode $|0,0\rangle$:
$$
|s,q\rangle_{LG}=\frac{1}{\sqrt{\alpha!\,\beta!}}\big(\hat a_+^\dagger\big)^{\alpha}\big(\hat a_-^\dagger\big)^{\beta}|0,0\rangle_{HG},\qquad
\hat a_\pm=\frac{\hat a\pm i\hat b}{\sqrt2},
$$
with integers $\alpha=(s+q)/2$ and $\beta=(s-q)/2$. The parameters $s$ and $q$ are related to the radial and azimuthal indices of the LG modes by
$$
l=q,\qquad p=\frac{s-|l|}{2}.
$$
$\hat a$ ($\hat a^\dagger$) and $\hat b$ ($\hat b^\dagger$) are the annihilation (creation) operators of the $a$ ($x$) and $b$ ($y$) modes of the HG beam:
$$
\hat a|n,m\rangle_a=\sqrt n\,|n-1,m\rangle_a,\qquad \hat b|n,m\rangle_b=\sqrt m\,|n,m-1\rangle_b .
$$
The HG modes are defined as
$$
|n,m\rangle=\frac{1}{\sqrt{m!\,n!}}(\hat a^\dagger)^m(\hat b^\dagger)^n|0,0\rangle_{HG}.
$$
Using $\phi_1\propto(x+iy)e^{-(x^2+y^2)/2\sigma^2}$, i.e. $|LG_{01}\rangle=\tfrac{1}{\sqrt2}(|1,0\rangle+i|0,1\rangle)$, the initial state rewritten in terms of HG modes is
$$
|\Psi_i\rangle=\frac{1}{\sqrt{1+\gamma^2}}\Big[|0,0\rangle_{HG}+\frac{\gamma e^{i\varphi}}{\sqrt2}\big(|1,0\rangle_{HG}+i|0,1\rangle_{HG}\big)\Big]
$$
$$
=\frac{1}{\sqrt{1+\gamma^2}}\Big[\Big(|0\rangle_a+\frac{\gamma e^{i\varphi}}{\sqrt2}|1\rangle_a\Big)|0\rangle_b+i\frac{\gamma e^{i\varphi}}{\sqrt2}|0\rangle_a|1\rangle_b\Big].
$$
**This is an entangled state between the two modes ($a$ and $b$) of the HG beam**: it cannot be written as a product of an $a$-state and a $b$-state.

**Roles of the degrees of freedom.** We use the **spatial** degree of freedom of $|\Psi_i\rangle$ as the measuring device (**pointer**) and the **polarization** degree of freedom as the **measured system**.

**Coordinate representation.** The initial state $|\Psi_i\rangle$ in the coordinate representation is
$$
\Psi_i(x,y)=\langle x,y|\Psi_i\rangle=\frac{1}{\sqrt{1+\gamma^2}}\left[\phi_0(x,y)+\gamma e^{i\varphi}\sqrt{\frac{2}{\sigma}}\,(x+iy)\,\phi_0(x,y)\right],\tag{19}
$$
$$
\phi_0(x,y)=\left(\frac{1}{\pi\sigma^2}\right)^{\frac12}e^{-\frac{x^2+y^2}{2\sigma^2}} .
$$

### 1.4 Postselection as a lossless distillation of learnable information
Consider a parameter $g$ imprinted on $N$ probes. The **learnable information** is quantified by the quantum Fisher information (QFI) $F_Q(g)$, and the Cramér–Rao bound is $\Delta g\ge1/\sqrt{NF_Q}$. A postselection succeeds with probability $P_s$ and leaves the state $|\Psi_g\rangle$, whose QFI is $F_Q^{\rm ps}$. The information retained is $NP_sF_Q^{\rm ps}\le NF_Q$. If the postselection is chosen so that the **rejected** events carry (almost) no information about $g$, which happens when the failed-postselection state is $g$-independent to first order, then $P_sF_Q^{\rm ps}\simeq F_Q$. The few postselected photons then carry essentially **all** the learnable information, with $F_Q^{\rm ps}\simeq F_Q/P_s\gg F_Q$, and the distillation is **lossless**. This is valuable when detectors saturate, or when the cost lies in measuring or processing each photon rather than in preparing it. The weak-value scheme below realises exactly this concentration.

---

## 2. Measurement on one mode: coupling, evolved state, weak value

For simplicity, we consider only a measurement performed on **one mode** ($a$, the $x$ mode) of the system.

**Coupling.** The interaction Hamiltonian between the measured system and the pointer is
$$
H=g\,\hat\sigma_x\otimes\hat P_x .
$$
* **$g$** is the interaction coupling parameter between the pointer and the measured system.
* **$\hat\sigma_x=|D\rangle\langle D|-|A\rangle\langle A|$** is the operator of the measured system, where
$$|D\rangle=\frac{1}{\sqrt2}\big(|H\rangle+|V\rangle\big),\qquad |A\rangle=\frac{1}{\sqrt2}\big(|H\rangle-|V\rangle\big)$$
are the diagonal and anti-diagonal polarizations, written in the horizontal ($|H\rangle$) and vertical ($|V\rangle$) polarization basis of the beam.
* **$\hat P_x$** is the momentum operator of the $a$ mode of the pointer, conjugate to $\hat X=\int dx\,x\,|x\rangle\langle x|$, i.e. $[\hat X,\hat P_x]=i$.

In optics this coupling is a polarization-dependent transverse displacement, realised with a birefringent beam displacer (e.g. a calcite or $\alpha$-BBO crystal) or a tilted birefringent plate.

**Pre- and postselection of the measured system.**
$$
|\psi_i\rangle=\cos\!\Big(\frac{\alpha}{2}\Big)|H\rangle+e^{i\delta}\sin\!\Big(\frac{\alpha}{2}\Big)|V\rangle,\qquad |\psi_f\rangle=|H\rangle ,
$$
with $\delta\in[0,2\pi)$ and $\alpha\in(0,\pi)$. These are prepared with a polarizer plus half- and quarter-wave plates and postselected with a polarizer or PBS. The **weak value** is
$$
\langle\hat\sigma_x\rangle_w=\frac{\langle\psi_f|\hat\sigma_x|\psi_i\rangle}{\langle\psi_f|\psi_i\rangle}=e^{i\delta}\tan\!\Big(\frac{\alpha}{2}\Big).
$$
It becomes anomalously large ($\gg1$) as $\alpha\to\pi$, when the pre- and postselected states become nearly orthogonal. Examples: $\alpha=15^\circ$ gives $\tan(7.5^\circ)=0.132$ (small weak value), and $\alpha=165^\circ$ gives $\tan(82.5^\circ)=7.596$ (large weak value).

**Evolution.** The state $|\psi_i\rangle\otimes|\Psi_i\rangle$ evolves under the unitary evolution operator
$$
\hat U(t)=\exp\!\Big(-i\int_0^t\hat H_{\rm int}\,d\tau\Big).
$$
In the derivation, the momentum operator is written in terms of the annihilation and creation operators $\hat a$ and $\hat a^\dagger$ as
$$
\hat P=\frac{i}{2\sigma}\big(\hat a^\dagger-\hat a\big),
$$
where $\sigma$ is the size of the fundamental Gaussian beam. With $\hat X=\sigma(\hat a+\hat a^\dagger)$, one checks $[\hat X,\hat P]=i$. Then
$$
-i\int_0^t g\hat\sigma_x\hat P\,d\tau=\frac{gt}{2\sigma}\,\hat\sigma_x(\hat a^\dagger-\hat a)=\frac{\Gamma}{2}\hat\sigma_x(\hat a^\dagger-\hat a).
$$
Since $\hat\sigma_x^2=I$, the exponential splits onto the projectors $(I\pm\hat\sigma_x)/2$, and the **evolved state** is
$$
|\Phi\rangle=\exp\!\Big(-i\int_0^t\hat H_{\rm int}\,d\tau\Big)|\psi_i\rangle\otimes|\Psi_i\rangle
=\frac12\Big[(I+\hat\sigma_x)\otimes\hat D\Big(\frac\Gamma2\Big)+(I-\hat\sigma_x)\otimes\hat D^\dagger\Big(\frac\Gamma2\Big)\Big]|\psi_i\rangle\otimes|\Psi_i\rangle ,
$$
where $\hat D(\Gamma/2)=e^{\frac\Gamma2(\hat a^\dagger-\hat a)}$ is the displacement operator, $I$ is the $2\times2$ identity operator, and
$$
\Gamma=\frac{gt}{\sigma}
$$
is the coupling strength parameter.

**Properties of $\Gamma$.** $\Gamma$ is **dimensionless** and can take **continuous values**; it characterises the **measurement strength**. If $0<\Gamma\ll1$ the measurement is **weak**, whereas $\Gamma\gg1$ is classified as **strong**.

**Experimental control of $\Gamma$.** $\Gamma$ can be controlled in three ways, corresponding to adjustments of $g$, $t$ and $\sigma$. For example, $\sigma$ can be changed by beam expansion or focusing, and $g$ by the crystal's birefringence or orientation. Experimental research has shown that the simplest and most direct way to adjust $\Gamma$ is by **tuning the coupling duration $t$**, e.g. by changing the length of the birefringent crystal through which the beam passes. Below, we assume that changes of $\Gamma$ come from $t$, while $g$ and $\sigma$ are fixed.

**Postselection and readout.** After the interaction the polarization is projected onto $|\psi_f\rangle=|H\rangle$. The pointer collapses to
$$
|\Psi\rangle=\kappa\,\langle\psi_f|\Phi\rangle=\frac{\kappa\,\langle\psi_f|\psi_i\rangle}{2}\Big[t_+\hat D\Big(\frac\Gamma2\Big)+t_-\hat D^\dagger\Big(\frac\Gamma2\Big)\Big]|\Psi_i\rangle,\qquad t_\pm=1\pm\langle\hat\sigma_x\rangle_w ,
$$
with $\kappa$ the normalisation constant. This expression is exact for any $\Gamma$. The transverse intensity of the postselected beam is recorded with a CCD camera. The centroid shift gives ${\rm Re}\langle\sigma_x\rangle_w$, while ${\rm Im}\langle\sigma_x\rangle_w$ appears in momentum space (the Fourier plane of a lens).

**Displaced Fock states.** The action of the displacement on the number states (needed to expand $\hat D^{(\dagger)}|\Psi_i\rangle$) defines the displaced Fock state
$$
\hat D(\alpha)|n\rangle=e^{-|\alpha|^2/2}\sum_{k=0}^{\infty}\frac{\sqrt{n!}}{k!}\,\left(\alpha\right)^{k-n}L_n^{(k-n)}(|\alpha|^2)\,|k\rangle ,
$$
with $L_n^{(k-n)}$ the associated Laguerre polynomials; here the kets $|k\rangle$ in the sum are the number states generated from the vacuum as $(\hat a^\dagger)^k|0\rangle$.

**Quantum Fisher information.** For a pure-state family $|\Psi_\theta\rangle$, the QFI matrix is
$$
F_{jk}=4\,{\rm Re}\big[\langle\partial_j\Psi|\partial_k\Psi\rangle-\langle\partial_j\Psi|\Psi\rangle\langle\Psi|\partial_k\Psi\rangle\big],\qquad F_Q=F_{gg} ,
$$
and ${\rm Cov}(\hat\theta)\ge(NF)^{-1}$. Without postselection, the generator of $g$ is $t\,\hat\sigma_x\hat P$, so $F_Q=4t^2{\rm Var}_{\psi_i\Psi_i}(\hat\sigma_x\hat P)$. For the Gaussian component ($\langle\hat P^2\rangle=1/4\sigma^2$) this gives $F_Q=t^2/\sigma^2$. With postselection, in the weak regime $|\Psi\rangle\simeq\big[1+\tfrac{\Gamma}{2}\langle\sigma_x\rangle_w(\hat a^\dagger-\hat a)\big]|\Psi_i\rangle$, and
$$
F_Q^{\rm ps}\simeq\frac{t^2}{\sigma^2}\,|\langle\sigma_x\rangle_w|^2=\frac{t^2}{\sigma^2}\tan^2\frac{\alpha}{2},\qquad P_s=|\langle\psi_f|\psi_i\rangle|^2=\cos^2\frac{\alpha}{2},
$$
$$
P_s\,F_Q^{\rm ps}\simeq\sin^2\!\frac{\alpha}{2}\;\frac{t^2}{\sigma^2}\;\xrightarrow{\ \alpha\to\pi\ }\;F_Q .
$$
For large weak values, the rare postselected photons carry essentially all of the information, which is the lossless concentration discussed in 1.4. The off-diagonal QFI elements quantify how well $(g,\gamma,\varphi)$ can be estimated simultaneously from the same pointer.

---

## 3. Effects on quadrature squeezing

Define the two-mode quadrature operators
$$
F_1=\frac{1}{2\sqrt2}\big(\hat a+\hat b+\hat a^\dagger+\hat b^\dagger\big),\qquad
F_2=\frac{1}{2\sqrt2}\big(\hat a+\hat b-\hat a^\dagger-\hat b^\dagger\big).
$$
These two operators satisfy the commutation relation
$$
[F_1,F_2]=\frac{i}{2},
$$
and the corresponding uncertainty relation for their fluctuations is
$$
\Delta F_1^2\,\Delta F_2^2\ge\frac1{16}.
$$
The **squeezing parameter**, which characterises the quadrature squeezing of the $i$-th component of $|\Psi\rangle$ (superpositions of Gaussian and LG states), is defined as
$$
Q_i=4\Delta F_i^2-1 .
$$
The vacuum (coherent) level is $\Delta F_i^2=1/4$, i.e. $Q_i=0$. The values of $Q_i$ are bounded by $Q_i\ge-1$, and the $i$-th component of the quadrature operators of $|\Psi\rangle$ is considered **squeezed if $-\frac14<Q_i<0$**.

**Squeezing parameter of the final state.** Expanding $\Delta F_1^2=\langle F_1^2\rangle-\langle F_1\rangle^2$ in the postselected state $|\Psi\rangle$, the squeezing parameters are
$$
Q_{1,w}=\frac14\Big[\langle\hat a^\dagger\hat a\rangle+\langle\hat b^\dagger\hat b\rangle+\langle\hat a\hat b^\dagger\rangle+\langle\hat a^\dagger\hat b\rangle+\langle\hat a\hat b\rangle+\langle\hat a^\dagger\hat b^\dagger\rangle\Big]
-\frac18\Big[\langle\hat a^2+\hat a^{\dagger2}\rangle+\langle\hat b^2+\hat b^{\dagger2}\rangle\Big]
+\frac18\Big[\langle(\hat a+\hat a^\dagger)^2+(\hat b+\hat b^\dagger)^2\rangle\Big],
$$
and analogously for $Q_{2,w}$ with the signs of the $\hat a^2,\hat b^2,\hat a\hat b$ terms reversed. All expectation values are taken in $|\Psi\rangle$ and are evaluated with the displaced-Fock-state expansion of $\hat D^{(\dagger)}(\Gamma/2)|\Psi_i\rangle$.

**Behaviour.** At $\Gamma=0$ the state is unsqueezed. For small weak values the measurement only slightly perturbs the quadrature noise. For large weak values the coherent superposition $t_+\hat D(\Gamma/2)+t_-\hat D^\dagger(\Gamma/2)$ of two oppositely displaced copies redistributes the noise between $F_1$ and $F_2$, and for suitable $\Gamma$, $\gamma$ and $\varphi$ one quadrature is pushed below the vacuum level ($Q_i<0$). The postselected von Neumann measurement can therefore generate quadrature squeezing in the pointer.

**Concentration of multiparameter Fisher information.** Because the postselected state depends on $(g,\gamma,\varphi)$ through $t_\pm$, which is amplified by $\langle\sigma_x\rangle_w$, the full QFI matrix $\mathbf F$ of all $N$ probes can be compressed into the $NP_s$ postselected states: $P_s\mathbf F^{\rm ps}\simeq\mathbf F$, with $\mathbf F^{\rm ps}\simeq\mathbf F/P_s$. The multiparameter Fisher information is thus concentrated into a small number of states, and squeezing (reduced noise in the quadrature that encodes the parameter) is one manifestation of this concentration.

---

## 4. Effects on the intensity distribution

**Initial state.** Rewritten in the coordinate representation, the initial state is (Eq. (19) above)
$$
\Psi_i(x,y)=\langle x,y|\Psi_i\rangle=\frac{1}{\sqrt{1+\gamma^2}}\left[\phi_0(x,y)+\gamma e^{i\varphi}\sqrt{\frac{2}{\sigma}}\,(x+iy)\,\phi_0(x,y)\right],\qquad
\phi_0(x,y)=\left(\frac{1}{\pi\sigma^2}\right)^{\frac12}e^{-\frac{x^2+y^2}{2\sigma^2}} .
$$

**Measurement state of the pointer.** After the postselected measurement the pointer state changes to $|\Psi\rangle$. Its coordinate representation is
$$
\Psi(x,y)=\frac{\kappa}{\sqrt{1+\gamma^2}}\Big\{t_-M_-+t_+M_++t_-T_-+t_+T_++t_-K_-+t_+K_+\Big\},\tag{20}
$$
where
$$
t_\pm=1\pm\langle\sigma_x\rangle_w,\qquad s=\Gamma/2,
$$
$$
M_\pm=\phi_\pm(x)\,\psi(y),\qquad K_\pm=i\sqrt2\,\gamma e^{i\varphi}\,\phi_\pm(x)\,\psi(y),
$$
$$
T_\pm=\gamma e^{i\varphi}\sqrt{\frac{2}{\sigma}}\Big[\pm(1-\sqrt2)\,s+\frac{2x}{\sigma}\Big]\phi_\pm(x)\,\psi(y),
$$
with $\phi_\pm(x)\equiv\phi_{\pm s}(x)$ and
$$
\phi_s(x)=\left(\frac{1}{\pi\sigma^2}\right)^{\frac14}e^{-\frac{s^2}{2}}\,e^{-\frac{x^2}{2\sigma^2}}\,e^{-\left(\frac{x-s}{\sqrt2}\right)^2},\tag{21}
$$
$$
\psi(y)=\left(\frac{1}{\pi\sigma^2}\right)^{\frac14}e^{-\frac{y^2}{2\sigma^2}} .
$$
$M_\pm$ are the displaced fundamental Gaussian components, and $T_\pm$ and $K_\pm$ are the displaced $LG_{01}$ (vortex) components. The intensity is $I(x,y)=|\Psi(x,y)|^2$.

**Effect on the intensity distribution.**
* For **small weak values**, e.g. $\langle\sigma_x\rangle_w=0.132$, $t_+\approx t_-$ and the two displaced copies nearly cancel each other's shift. The spatial profile of $|\Psi\rangle$ does not change dramatically and **retains its initial shape** (displaced vortex and zero-intensity point) as the coupling strength $\Gamma$ increases.
* After a postselected measurement with a **large weak value**, e.g. $\langle\sigma_x\rangle_w=7.596$, $t_+\approx-t_-$ and the copies displaced by $\pm s$ interfere with opposite signs. The spatial intensity distribution of the initial state $|\Psi_i\rangle$ then **changes significantly** as $\Gamma$ increases. In particular, for large weak values and $\Gamma=1$, the intensity distribution of $|\Psi\rangle$ **separates into two parts, each exhibiting a zero-intensity region at the edges of the images, similar to the initial case**.

**Interpretation and relation to previous work.** The spatial intensity distribution of the OAM state changes notably when large weak values of the measured observable are considered after a postselected von Neumann measurement. This is the same weak-value amplification known from single-parameter postselected metrology (Aharonov–Albert–Vaidman, the Hosten–Kwiat spin Hall effect, Dixon et al. beam deflection), where an anomalously large $\langle\sigma_x\rangle_w$ amplifies the pointer shift at the cost of a low $P_s$. Here the amplification acts on a structured OAM pointer and reshapes it. This shows the potential of postselected von Neumann measurements, characterized by weak values, for **OAM-based state engineering**: splitting, reshaping and moving vortices by choosing $\alpha$, $\delta$ and $\Gamma$.

---

## 5. Second-order cross-correlation function

The cross-correlation between the $a$ and $b$ modes of $|\Psi\rangle$ is
$$
g^{(2)}_{a,b,\Psi}=\frac{\langle\Psi|\hat a^\dagger\hat b^\dagger\hat b\hat a|\Psi\rangle}{\langle\Psi|\hat a^\dagger\hat a|\Psi\rangle\langle\Psi|\hat b^\dagger\hat b|\Psi\rangle} .
$$
It is examined for different system parameters of the postselected von Neumann measurement ($\Gamma$, $\langle\sigma_x\rangle_w$, $\gamma$, $\varphi$):
* The case **$\Gamma=0$** corresponds to **no interaction** between the pointer and the measured system. Initially we observe **no correlation** between the two modes of $|\Psi\rangle$: the joint two-photon term $\langle\hat a^\dagger\hat b^\dagger\hat b\hat a\rangle$ vanishes for $|\Psi_i\rangle$, which contains at most one excitation.
* **After the postselected measurement, no correlation occurs** either: $g^{(2)}_{a,b,\Psi}$ never exceeds unity, so no bunching-type cross-correlation between the modes is generated.
* As the **weak value increases, $g^{(2)}_{a,b,\Psi}$ approaches one**, the value for statistically independent (coherent-like) modes. This behaviour is due to the signal amplification effects of anomalously large weak values: the amplified displacement of mode $a$ dominates its photon statistics, so $\langle\hat a^\dagger\hat b^\dagger\hat b\hat a\rangle\to\langle\hat a^\dagger\hat a\rangle\langle\hat b^\dagger\hat b\rangle$.

---

## 6. Wigner function (phase-space distribution)

**General expressions.** The Wigner function of a state $\rho=|\Psi\rangle\langle\Psi|$ is
$$
W(a,p)=\frac{1}{\pi^2}\iint_{-\infty}^{\infty}\exp\big(\beta^*a-\beta a^*\big)\,C_W(\beta)\,d^2\beta ,
$$
where $C_W(\lambda)$ is the **symmetrically ordered characteristic function**
$$
C_W(\lambda)={\rm Tr}\big[\rho\,e^{\lambda\hat a^\dagger-\lambda^*\hat a}\big].
$$
Writing $\lambda=\lambda'+i\lambda''$ (real and imaginary parts) and $a=x+ip$, we have $\beta^*a-\beta a^*=2i(p\lambda'-x\lambda'')$, and
$$
W(x,p)=\frac{1}{\pi^2}\iint_{-\infty}^{\infty}e^{i2(p\lambda'-x\lambda'')}\,C_W(\lambda)\,d\lambda'\,d\lambda'' .
$$
For $|\Psi\rangle\propto[t_+\hat D(s)+t_-\hat D^\dagger(s)]|\Psi_i\rangle$, $C_W$ follows from $\hat D(\lambda)\hat D(\pm s)=e^{\pm(\lambda s^*-\lambda^*s)/2}\hat D(\lambda\pm s)$ and the matrix elements of $\hat D$ between Fock states (Section 2). The cross terms $t_+t_-^*$ produce interference fringes in phase space.

**Numerical results.** The Wigner function is computed and plotted for different coupling strengths, $\Gamma=0,\,0.3,\,0.5,\,0.7,\,1$, and different values of the superposition parameter $r=1,2,3,4$ (the relative amplitude $\gamma$), for both small and large weak values:
* **$\Gamma=0$:** the original state $|\Psi\rangle$ is a **Gaussian state**: its Wigner function is a single smooth peak and **remains positive** everywhere.
* As $\Gamma$ increases, the **positive peak of the Wigner function shifts from the centre to the edge of phase space**, and **the shape of this peak gradually becomes more irregular**.
* After the postselected von Neumann measurement, the phase-space density $W(z)$ exhibits **squeezing in phase space** compared with the original state, and this **squeezing becomes more pronounced as $\Gamma$ increases**.
* The **initial Gaussian profile ($\Gamma=0$) changes to a non-Gaussian profile** with increasing coupling strength $\Gamma$.

**Conclusions.**
* There is an **increase in the negative regions of the Wigner function as $\Gamma$ grows**. These come from the interference between the two oppositely displaced components weighted by $t_\pm$.
* Larger negative regions indicate a **greater degree of nonclassicality** of the state.
* After the postselected von Neumann measurement, the phase-space distribution of $|\Psi\rangle$ **not only becomes squeezed but also exhibits nonclassicality** for appropriate parameter values.

---

## 7. Signal-to-noise ratio: can the superposition outperform single states?

To compare postselected and non-postselected measurements, define the ratio
$$
\chi=\frac{R_p}{R_n},
$$
where $R_p$ is the SNR of the postselected von Neumann measurement:
$$
R_p=\sqrt{NP_s}\,\frac{\delta x}{\Delta x},\tag{28}
$$
with the variance of the position operator
$$
\Delta x=\sqrt{\langle\Psi|\hat X^2|\Psi\rangle-\langle\Psi|\hat X|\Psi\rangle^2},\tag{29}
$$
and the average shift of the pointer variable $x$ after the postselected measurement
$$
\delta x=\langle\Psi|\hat X|\Psi\rangle-\langle\Psi_i|\hat X|\Psi_i\rangle.\tag{30}
$$
Here $\hat X=\sigma(\hat a+\hat a^\dagger)$ is the position operator, $N$ is the total number of measurements, and $P_s$ is the probability of finding the postselected state for a given preselected state:
$$
P_s=|\langle\psi_f|\psi_i\rangle|^2=\cos^2\theta,\qquad\theta\equiv\alpha/2 .
$$
$NP_s$ is the number of times the system is found in the postselected state. Using the expressions for the states $|\Psi_i\rangle$ and $|\Psi\rangle$:
$$
\langle\Psi|\hat X|\Psi_i\rangle=2\sigma\,{\rm Re}\big[\langle\Psi|\hat a|\Psi_i\rangle\big],\tag{31}
$$
$$
\langle\Psi|\hat X|\Psi\rangle=2\sigma\,{\rm Re}\big[\langle\Psi|\hat a|\Psi\rangle\big],\tag{32}
$$
$$
\langle\Psi|\hat X^2|\Psi\rangle=\sigma^2\Big[2\langle\Psi|\hat a^\dagger\hat a|\Psi\rangle+2{\rm Re}\big[\langle\Psi|\hat a^2|\Psi\rangle\big]+1\Big].\tag{33}
$$

**Non-postselected measurement.** $R_n=\sqrt N\,\delta x_n/\Delta x_n$, evaluated in the full evolved state $|\Phi\rangle$. To evaluate $\chi$ we first calculate
$$
\langle\Psi_i|\hat X_1|\Psi_i\rangle=2\sigma\,{\rm Re}\big[\langle\Psi_i|\hat a|\Psi_i\rangle\big],\tag{36}
$$
$$
\langle\Phi|\hat X|\Phi\rangle=2\sigma\,{\rm Re}\big[\langle\Phi|\hat a|\Phi\rangle\big],\tag{37}
$$
$$
\langle\Phi|\hat X^2|\Phi\rangle=\sigma^2\Big[2\langle\Phi|\hat a^\dagger\hat a|\Phi\rangle+2{\rm Re}\big[\langle\Phi|\hat a^2|\Phi\rangle\big]+1\Big].\tag{38}
$$
The expectation values of $\hat a$, $\hat a^\dagger\hat a$ and $\hat a^2$ in the state $|\Phi\rangle$, using $\langle\psi_i|\hat\sigma_x|\psi_i\rangle=\sin\alpha\cos\delta$ and $\hat D^\dagger(s)\hat a\hat D(s)=\hat a+s$, are
$$
\langle\hat a\rangle=\frac{\gamma e^{i\varphi}}{\sqrt2(1+\gamma^2)}+\frac\Gamma2\sin\alpha\cos\delta,\tag{39}
$$
$$
\langle\hat a^\dagger\hat a\rangle=\frac{\gamma^2}{2(1+\gamma^2)}+\frac{\Gamma^2}{4},
$$
$$
\langle\hat a^2\rangle=\frac{\Gamma^2}{4}+\frac{\Gamma\gamma e^{i\varphi}(1+\sin\alpha\cos\delta)}{\sqrt2(1+\gamma^2)} .
$$
Without postselection the pointer shift is only $\delta x_n\propto\sigma\Gamma\sin\alpha\cos\delta\le\sigma\Gamma$. After postselection it is $\delta x\propto\sigma\Gamma\,{\rm Re}\langle\sigma_x\rangle_w$, which is amplified.

**Conclusions.** The ratio $\chi$ **increases and can become greater than unity with increasing weak values in the weak-measurement regime**. The numerical results indicate that, in this scheme, **anomalous weak values are indeed helpful for increasing the SNR in weak-measurement regimes**. Postselected measurements therefore improve the precision of the measurement compared with the non-postselected case. The interference between the Gaussian and $LG_{01}$ components, i.e. the cross terms $\propto\gamma e^{i\varphi}$ in Eqs. (39) and in $\langle\hat a^2\rangle$, gives additional control over $\delta x$ and $\Delta x$ that a single Gaussian or a single LG state does not have. **The superposition state $|\Psi_i\rangle$ can therefore be used in postselected von Neumann measurement-based precision measurement, when large weak values of the measured system are considered.**
