# Stochastic path integral and action principle for continuous quantum measurement

## 1. Measurement model and state-space parametrisation

### State space
A (possibly mixed) state of an $N$-level system is parametrised by a real vector $\bm q\in\mathbb R^d$. Its components are the expansion coefficients of $\hat\rho$ in an orthogonal operator basis, for example the $d\equiv N^2-1$ generalised Gell-Mann matrices $\hat\lambda_a$:
$$
\hat\rho=\frac{1}{N}\hat 1+\frac12\sum_{a=1}^{d}q_a\hat\lambda_a ,\qquad q_a={\rm Tr}(\hat\rho\hat\lambda_a).
$$
For a qubit ($N=2$, $d=3$) this is the Bloch vector, $\bm q=(x,y,z)$ with $\hat\rho=\frac12(\hat 1+x\hat\sigma_1+y\hat\sigma_2+z\hat\sigma_3)$.

### Continuous weak measurement
The measurement is a sequence of weak measurements, each of duration $\delta t$, with outcomes $r_k$. Each step is described by a Kraus operator $\hat{\cal M}_{\delta t}(r_k)$. The state is updated as
$$
\hat\rho_{k+1}=\frac{\hat{\cal U}_{\delta t}\hat\rho_k\hat{\cal U}_{\delta t}^\dagger}{{\rm Tr}\{\hat{\cal U}_{\delta t}\hat\rho_k\hat{\cal U}_{\delta t}^\dagger\}},\qquad
\hat{\cal U}_{\delta t}\equiv e^{-\frac i\hbar\hat H\delta t}\,\hat{\cal M}_{\delta t},
$$
and the outcome probability is $P(r_k|\hat\rho_k)={\rm Tr}\{\hat\rho_k\hat{\cal M}^\dagger_{\delta t}\hat{\cal M}_{\delta t}\}$. In $\bm q$ variables this defines a deterministic update $\bm q_{k+1}=\bm{\cal E}[\bm q_k,r_k]=\bm q_k+\delta t\,\bm{\cal L}[\bm q_k,r_k]+{\cal O}(\delta t^2)$, where $\bm{\cal L}$ is a vector functional describing the first-order change of the state, and a probability $\ln P(r_k|\bm q_k)=\delta t\,{\cal F}[\bm q_k,r_k]+\text{const}+{\cal O}(\delta t^2)$.

---

## 2. Stochastic path integral with pre- and postselection

### Joint probability density
Fix an initial (preselected) state $\bm q_I$ and a final (postselected) state $\bm q_F$ at time $T=n\,\delta t$. The joint probability density function of all measurement outcomes $\{r_k\}$, all intermediate states $\{\bm q_k\}$ and the chosen final state $\bm q_F$, conditioned on $\bm q_I$, is
$$
\boxed{\;{\mathcal P}\equiv P(\{\bm q_k\},\{r_k\},\bm q_F|\bm q_I)=\delta^d(\bm q_0-\bm q_I)\,\delta^d(\bm q_n-\bm q_F)\prod_{k=0}^{n-1}P(\bm q_{k+1},r_k|\bm q_k)\;}
$$
with $P(\bm q_{k+1},r_k|\bm q_k)=P(\bm q_{k+1}|\bm q_k,r_k)\,P(r_k|\bm q_k)=\delta^d\big(\bm q_{k+1}-\bm{\cal E}[\bm q_k,r_k]\big)P(r_k|\bm q_k)$. The two boundary delta functions implement preselection and postselection as **boundary conditions**. If the postselection is removed (integrate over $\bm q_F$), the chain reduces to ordinary forward-in-time stochastic quantum trajectories.

### Doubling the state space
Each delta function is written in Fourier form, $\delta^d(\bm q)=\int\frac{d^d\bm p}{(2\pi i)^d}e^{-\bm p\cdot\bm q}$ with $\bm p$ integrated along the imaginary axis. This introduces a **conjugate variable $\bm p_k$ for every $\bm q_k$**, which doubles the state space into a canonical "quantum phase space" $(\bm q,\bm p)$:
$$
{\mathcal P}=\int\!\prod_{k=-1}^{n}\frac{d^d\bm p_k}{(2\pi i)^d}\exp\Big\{-\bm p_{-1}\!\cdot(\bm q_0-\bm q_I)-\bm p_n\!\cdot(\bm q_n-\bm q_F)
+\sum_{k=0}^{n-1}\Big[-\bm p_k\cdot\big(\bm q_{k+1}-\bm q_k-\delta t\,\bm{\cal L}[\bm q_k,r_k]\big)+\ln P(r_k|\bm q_k)\Big]\Big\}.
$$
Taking the time-continuum limit $\delta t\to0$ ($\bm q_{k+1}-\bm q_k\to\dot{\bm q}\,\delta t$, $\sum_k\delta t\to\int dt$), the **stochastic path integral representation of the PDF** is
$$
\boxed{\;{\mathcal P}=\int{\cal D}\bm p\;e^{\cal S}=\int{\cal D}\bm p\,\exp\bigg[\int_0^Tdt\,\Big(-\bm p\cdot\dot{\bm q}+{\mathcal H}[\bm q,\bm p,r]\Big)\bigg],\;}
$$
with the **stochastic Hamiltonian**
$$
\boxed{\;{\mathcal H}[\bm q,\bm p,r]=\bm p\cdot\bm{\mathcal L}[\bm q,r]+{\mathcal F}[\bm q,r]-\bm p\cdot(\bm q-\bm q_I)\,\delta(t)-\bm p\cdot(\bm q-\bm q_F)\,\delta(t-T).\;}
$$
Here $\bm q(t)$ and $\bm p(t)$ act as effective coordinates and canonically conjugate momenta for the state space. ${\cal F}[\bm q_k,r_k]$ is the linear-order expansion of $\ln P(r_k|\bm q_k)$ in $\delta t$, and $\bm{\cal L}$ is the vector functional giving the first-order change of the state $\bm q_k$. The boundary terms enforce pre- and postselection. Unlike Feynman-type restricted path integrals, $e^{\cal S}$ is a **probability density for classical-looking trajectories through the (doubled, possibly mixed) state space**, not an amplitude.

---

## 3. Action principle: most-likely paths

The most probable paths extremise the action ${\cal S}=\int_0^T(-\bm p\cdot\dot{\bm q}+{\cal H})\,dt$ with respect to $\bm p$, $\bm q$ and the record $r$. Taking the functional derivatives and setting them to zero, $\delta{\cal S}/\delta\bm p=\delta{\cal S}/\delta\bm q=\delta{\cal S}/\delta r=0$, gives (integrating $-\bm p\cdot\delta\dot{\bm q}$ by parts):
$$
\boxed{\;
\begin{aligned}
&-\dot{\bm q}+\bm{\mathcal L}[\bm q,r]=0,\\[2pt]
&\dot{\bm p}+\partial_{\bm q}\big(\bm p\cdot\bm{\mathcal L}[\bm q,r]\big)+\partial_{\bm q}\mathcal F[\bm q,r]=0,\\[2pt]
&\partial_r\big(\bm p\cdot\bm{\mathcal L}[\bm q,r]\big)+\partial_r\mathcal F[\bm q,r]=0,
\end{aligned}\;}
$$
with the forced boundary conditions $\bm q(0)=\bm q_I$ and $\bm q(T)=\bm q_F$. These are Hamilton's equations $\dot{\bm q}=\partial_{\bm p}{\cal H}$, $\dot{\bm p}=-\partial_{\bm q}{\cal H}$, plus an algebraic optimality condition for the readout $r$. Since ${\cal H}$ has no explicit time dependence for $0<t<T$, its value is conserved along optimal paths.

**Recovering the standard theory.** Without postselection, $\bm q_F$ is integrated over. The final delta function then disappears and the integral over $\bm p$ simply re-imposes $\bm q_{k+1}=\bm{\cal E}[\bm q_k,r_k]$ step by step. For any given record $r(t)$, the first equation $\dot{\bm q}=\bm{\cal L}[\bm q,r]$ is exactly the stochastic master (or Schrödinger) equation, and $e^{\int{\cal F}dt}$ is the usual probability of that record. The standard formulation is thus a special case. The conjugate momenta $\bm p$ are what allow a final boundary condition to be imposed and the action to be extremised over paths that end in a postselected $\bm q_F$.

---

## 4. Continuously monitored solid-state qubit

### Model
A double-quantum-dot charge qubit is monitored by a quantum point contact (QPC). Its Hamiltonian is
$$
\boxed{\;\hat H=\frac{\epsilon}{2}\hat\sigma_3+\Big(-\frac{\Delta}{2}\Big)\hat\sigma_1\;}
$$
($\hbar=1$), where $\epsilon$ is an energy asymmetry between the dots and $\Delta$ the tunneling strength. The QPC current, rescaled so that its mean is $\pm1$ for the two charge states, gives a Gaussian measurement operator
$$
\boxed{\;\hat{\cal M}_{\delta t}=\Big(\frac{\delta t}{2\pi\tau}\Big)^{1/4}\exp\Big[-\frac{\delta t}{4\tau}\big(r-\hat\sigma_3\big)^2\Big],\qquad \tau=\frac{S_0}{2\Delta\bar{\cal I}^2},\;}
$$
where $\tau$ is the characteristic measurement time of the QPC, set by the sensitivity $\Delta\bar{\cal I}$ (difference of the currents for the two qubit states) and the QPC shot-noise spectral density $S_0$.

### Readout probability
With $\hat{\cal M}^\dagger_{\delta t}\hat{\cal M}_{\delta t}=\sqrt{\delta t/2\pi\tau}\,e^{-\frac{\delta t}{2\tau}(r-\hat\sigma_3)^2}$ and $(r-\hat\sigma_3)^2=r^2-2r\hat\sigma_3+1$,
$$
P(r|\hat\rho)={\rm Tr}\{\hat\rho\hat{\cal M}_{\delta t}^\dagger\hat{\cal M}_{\delta t}\}
=\sqrt{\tfrac{\delta t}{2\pi\tau}}\,e^{-\frac{\delta t}{2\tau}(r^2+1)}\Big[\tfrac{1+z}{2}e^{r\delta t/\tau}+\tfrac{1-z}{2}e^{-r\delta t/\tau}\Big].
$$
Expanding $\ln$ to first order in $\delta t$,
$$
\boxed{\;\ln P(r|\hat\rho)\approx-\big(r^2-2rz+1\big)\frac{\delta t}{2\tau}+\frac12\ln\Big(\frac{\delta t}{2\pi\tau}\Big)+{\cal O}(\delta t^2)\;}
$$
so that, dropping the state-independent constant,
$$
\boxed{\;{\mathcal F}[\bm q,r]=-\frac{r^2-2rz+1}{2\tau}.\;}
$$

### Master equation (state update)
Since $\hat{\cal M}_{\delta t}\propto e^{r\delta t\,\hat\sigma_3/2\tau}$ up to scalars that cancel on normalisation, expanding $\hat\rho(t+\delta t)=\hat{\cal U}_{\delta t}\hat\rho\hat{\cal U}_{\delta t}^\dagger/{\rm Tr}\{\cdot\}$ to first order in $\delta t$ gives
$\hat{\cal U}\hat\rho\hat{\cal U}^\dagger\simeq\hat\rho-i\delta t[\hat H,\hat\rho]+\frac{r\delta t}{2\tau}\{\hat\sigma_3,\hat\rho\}$ and ${\rm Tr}\{\cdot\}\simeq1+\frac{r\delta t}{\tau}\langle\hat\sigma_3\rangle$. In the continuum limit,
$$
\boxed{\;\partial_t\hat\rho=-\frac{i}{\hbar}\big[\hat H,\hat\rho\big]+\frac{r}{2\tau}\{\hat\sigma_3,\hat\rho\}-\frac{r}{\tau}\langle\hat\sigma_3\rangle\hat\rho,\;}
$$
where $[\,,]$, $\{\,,\}$ and $\langle\hat\sigma_3\rangle={\rm Tr}\{\hat\sigma_3\hat\rho\}$ are the commutator, the anticommutator and the expectation value of $\hat\sigma_3$. Projecting on the Pauli matrices ($x={\rm Tr}\hat\rho\hat\sigma_1$, etc.; the Hamiltonian part is a rotation about $(-\Delta,0,\epsilon)$) gives
$$
\bm{\cal L}[\bm q,r]=\Big(-\epsilon y-\frac{xzr}{\tau},\;\;\epsilon x+\Delta z-\frac{yzr}{\tau},\;\;-\Delta y+(1-z^2)\frac{r}{\tau}\Big).
$$

### Stochastic Hamiltonian of the qubit
$$
\boxed{\;\mathcal H=p_x\Big(-\epsilon y-\frac{xzr}{\tau}\Big)+p_y\Big(\epsilon x+\Delta z-\frac{yzr}{\tau}\Big)+p_z\Big(-\Delta y+(1-z^2)\frac{r}{\tau}\Big)-\frac{r^2-2rz+1}{2\tau}\;}
$$
(plus the boundary terms of §2).

### Optimal-path ODEs ($3+3$ ODEs and $1$ constraint)
From $\dot{\bm q}=\partial_{\bm p}\mathcal H$, $\dot{\bm p}=-\partial_{\bm q}\mathcal H$, $\partial_r\mathcal H=0$:
$$
\boxed{\;
\begin{aligned}
\dot x&=-\epsilon y-xz\,r/\tau,\\
\dot y&=+\epsilon x+\Delta z-yz\,r/\tau,\\
\dot z&=-\Delta y+(1-z^2)\,r/\tau,\\
\dot p_x&=-\epsilon p_y+p_xz\,r/\tau,\\
\dot p_y&=+\epsilon p_x+\Delta p_z+p_yz\,r/\tau,\\
\dot p_z&=-\Delta p_y+(p_xx+p_yy+2p_zz-1)\,r/\tau,\\
r&=z+p_z(1-z^2)-p_xxz-p_yyz,
\end{aligned}\;}
$$
with the (possibly mixed-state) boundary conditions $\bm q_0=(x_I,y_I,z_I)$ and $\bm q_F=(x_F,y_F,z_F)$. The constraint follows from $\partial_r\mathcal H=\frac{1}{\tau}\big[-p_xxz-p_yyz+p_z(1-z^2)\big]-\frac{r-z}{\tau}=0$. For $\bm p=0$ it gives $r=z=\langle\hat\sigma_3\rangle$, the most likely readout without postselection.

---

## 5. Quantum non-demolition regime ($\Delta=0$)

For $\Delta=0$, $\hat\sigma_3$ commutes with $\hat H$ and the measurement is QND. Differentiating the constraint and using the ODEs one finds $\dot r=0$ identically when $\Delta=0$, so along the optimal path the readout is constant, $r=\bar r$. The $z$ equation $\dot z=(1-z^2)\bar r/\tau$ integrates to $z=\tanh(\bar rt/\tau+{\rm artanh}\,z_I)$. For $w=x+iy$, $\dot w=(i\epsilon-z\bar r/\tau)w$, and $\int_0^t z\,\bar r/\tau\,dt'=\ln(\cosh\frac{\bar rt}{\tau}+z_I\sinh\frac{\bar rt}{\tau})$. The most likely path is therefore
$$
\boxed{\;
\bar x(t)=\frac{x_I\cos\epsilon t-y_I\sin\epsilon t}{\cosh\bar rt/\tau+z_I\sinh\bar rt/\tau},\qquad
\bar y(t)=\frac{y_I\cos\epsilon t+x_I\sin\epsilon t}{\cosh\bar rt/\tau+z_I\sinh\bar rt/\tau},\qquad
\bar z(t)=\frac{z_I\cosh\bar rt/\tau+\sinh\bar rt/\tau}{\cosh\bar rt/\tau+z_I\sinh\bar rt/\tau}.\;}
$$
The constant $\bar r$ is fixed by the postselection: $\bar r=\frac{\tau}{T}\big[{\rm artanh}\,z_F-{\rm artanh}\,z_I\big]$. The coherences are rotated at frequency $\epsilon$ and damped by the factor $1/(\cosh+z_I\sinh)$, while $z$ is driven monotonically from $z_I$ to $z_F$ on the measurement time scale $\tau/|\bar r|$.

**Quantum demolition regime ($\Delta\neq0$).** Now measurement (collapse toward $\hat\sigma_3$ eigenstates at rate $\sim1/\tau$) competes with Rabi oscillation at rate $\Delta$, and the full $3+3$ system must be solved as a two-point boundary-value problem. For $\Delta\tau\gtrsim1$ the most likely paths are distorted Rabi oscillations whose amplitude is suppressed by the measurement. For $\Delta\tau\ll1$ the system enters the quantum Zeno regime discussed next.

---

## 6. Quantum jumps in the Zeno regime

Consider an evolving qubit that is measured on a time scale faster than the inverse Rabi frequency, $\tau\ll\Delta^{-1}$, with $\epsilon=0$ and an initial state in the $y$–$z$ plane. The dynamics then stays on the great circle $x=0$. Parametrise $z=\cos\theta$, $y=\sin\theta$ and introduce the momentum $p_\theta$ conjugate to $\theta$. Restricted to this circle, the stochastic Hamiltonian is
$$
\boxed{\;{\mathcal H}=p_\theta\Big(\Delta-\frac{r\sin\theta}{\tau}\Big)-\frac{r^2-2r\cos\theta+1}{2\tau}\;}
$$
and Hamilton's equations plus the readout condition give two ODEs and one constraint:
$$
\boxed{\;\dot\theta=\Delta-\sin\theta\,\frac{r}{\tau},\qquad
\dot p_\theta=p_\theta\,\frac{r\cos\theta}{\tau}+\frac{r\sin\theta}{\tau},\qquad
r=\cos\theta-p_\theta\sin\theta .\;}
$$
(Check: $\dot z=-\sin\theta\,\dot\theta=-\Delta y+(1-z^2)r/\tau$, as in §4.)

**Structure of the phase space.** Using the constraint, ${\mathcal H}=p_\theta\Delta+\frac{r^2-1}{2\tau}$.
- *Zeno-pinned fixed points.* $\dot\theta=\dot p_\theta=0$ gives $p_\theta=-\tan\theta$, $r=1/\cos\theta$ and $\tan\theta=\Delta\tau$. The state sits at $\theta^*\simeq\Delta\tau$ near the north pole, slightly tilted by the tunnelling; the mirror point $\theta\simeq\pi+\Delta\tau$ is near the south pole. Measurement freezes the Rabi oscillation (quantum Zeno effect).
- *Hyperbolic character.* Linearising about $\theta^*$ gives eigenvalues $\pm1/\tau$. The stable direction is the relaxation of $\theta$ back to the pinned state. The unstable direction lies almost entirely along $p_\theta$, because $\theta$ couples to $p_\theta$ only through terms of order $\theta^{*2}=(\Delta\tau)^2$.
- *Rare jumps.* A quantum jump from one pinned state to the other is a rare event. Its most likely realisation is the heteroclinic orbit of $\mathcal H$ connecting the two hyperbolic points on the energy surface $\mathcal H\simeq\mathcal H(\theta^*)=-\Delta^2\tau/2\approx0$. Along it the readout $r$ swings from $\simeq+1$ to $\simeq-1$, and the optimal record is a smooth crossover rather than a step.

**Jump duration.** Leaving the pinned state requires the momentum to grow along the unstable direction, $p_\theta\propto e^{t/\tau}$, from $|p_\theta|\sim\Delta\tau$ to $|p_\theta|\sim1/\theta^*\sim1/(\Delta\tau)$. Only then is $p_\theta\sin\theta$ of order one, so that $r$ departs from $\cos\theta$ and $\theta$ runs away. This amplification by $(\Delta\tau)^{-2}$ takes $\tau\ln(\Delta\tau)^{-2}=2\tau\ln(1/\Delta\tau)$. By the time-reversal symmetry of the heteroclinic orbit, the approach to the opposite pinned state takes the same time. The characteristic time taken by a quantum jump is therefore
$$
\boxed{\;T\approx4\tau\ln\!\Big(\frac{1}{\Delta\tau}\Big).\;}
$$
This duration is only logarithmically longer than the measurement time and much shorter than the mean waiting time between jumps (of order $1/(\Delta^2\tau)$ in the Zeno regime). A jump is therefore a rare, fast but **continuous** excursion. In the doubled phase space it follows a well-defined most-likely path, the heteroclinic orbit, together with a correspondingly structured most-likely readout $r(t)$.

---

## 7. Summary
1. The PDF of measurement records and state trajectories with pre- and postselection is ${\cal P}=\int{\cal D}\bm p\,e^{\cal S}$, ${\cal S}=\int_0^T(-\bm p\cdot\dot{\bm q}+{\cal H})dt$, ${\cal H}=\bm p\cdot\bm{\cal L}+{\cal F}+$ boundary terms.
2. Doubling the state space with conjugate momenta $\bm p$ allows extremisation. The most likely paths obey $\dot{\bm q}=\bm{\cal L}$, $\dot{\bm p}=-\partial_{\bm q}(\bm p\cdot\bm{\cal L}+{\cal F})$, $\partial_r(\bm p\cdot\bm{\cal L}+{\cal F})=0$, with $\bm q(0)=\bm q_I$ and $\bm q(T)=\bm q_F$. Without postselection ($\bm p=0$) the stochastic master equation is recovered.
3. For the QPC-monitored qubit, ${\cal F}=-(r^2-2rz+1)/2\tau$, which gives the explicit $3+3$ ODEs and the readout constraint. In the QND case the readout is constant and the paths are the closed-form $\tanh$-type solutions above.
4. In the Zeno regime, quantum jumps are heteroclinic orbits between hyperbolic fixed points of the $(\theta,p_\theta)$ phase space, lasting $T\approx4\tau\ln(1/\Delta\tau)$.
