# Eliminating the optical field: effective spin–oscillator Hamiltonian

**Answer: yes.** Under the Markov approximation, with zero-mean input noise, the optical field can be eliminated exactly at the level of the Heisenberg equations of motion. The result is a direct spin–oscillator coupling
$$
H_{\rm eff}=\tfrac12(x^2+p^2)+g\,x\,S_z,\qquad g=\beta^2 g_p\epsilon ,
$$
with frequencies measured in units of $\omega_p$. The derivation follows.

---

## 0. Why not ordinary adiabatic elimination?

The textbook route would be to treat $\beta$ perturbatively and adiabatically eliminate the field in second-order perturbation theory. That requires the eliminated mode to be far off-resonant, i.e. separated by a large energy gap from the dynamics it mediates. Here the field is a **continuum** of modes $b_\omega$ whose detunings $\Delta_\omega$ run through zero. There is no gap, so the condition for perturbative adiabatic elimination is **not satisfied**, and **we do not use perturbation theory**. Instead we use the fact that the field is linear: its Heisenberg equations can be solved **exactly** and substituted back. The only approximation is the Markov (broad, flat band) limit of the resulting frequency integrals.

---

## 1. Quadratures and Heisenberg equations

Define canonical quadratures ($[x,p]=i$; the field quadratures obey the continuum analogue with the normalization stated below):
$$
x=\frac{a+a^\dagger}{\sqrt2},\quad p=\frac{a-a^\dagger}{i\sqrt2},\qquad
x_\omega=\frac{b_\omega+b_\omega^\dagger}{\sqrt2},\quad p_\omega=\frac{b_\omega-b_\omega^\dagger}{i\sqrt2}.
$$
Then $a^\dagger a=\tfrac12(x^2+p^2)-\tfrac12$, $b_\omega+b_\omega^\dagger=\sqrt2x_\omega$, $a+a^\dagger=\sqrt2x$, and up to a constant
$$
H=\frac{\omega_p}{2}(x^2+p^2)+\int d\omega\,\frac{\Delta_\omega}{2}(x_\omega^2+p_\omega^2)
+\sqrt2\beta\int d\omega\;x_\omega\big(\epsilon S_z-g_p\,x\sin\Delta_\omega\tau\big).
$$
We integrate over the detuning, $d\omega=d\Delta_\omega$. Frequency integrals are normalized so that $\int d\Delta_\omega\,e^{i\Delta_\omega s}=\delta(s)$, i.e. the measure carries the factor $1/2\pi$, equivalently $[b_\omega,b^\dagger_{\omega'}]=2\pi\delta(\omega-\omega')$.

The Heisenberg equations $\dot O=i[H,O]$ are:
$$
\begin{aligned}
&\dot x_\omega=\Delta_\omega p_\omega, &(1)\\
&\dot p_\omega=-\Delta_\omega x_\omega-\sqrt2\beta\big(\epsilon S_z-g_p\,x\sin\Delta_\omega\tau\big), &(2)\\
&\dot S_z=0, &(3)\\
&\dot x=\omega_p\,p, &(4)\\
&\dot p=-\omega_p x-\sqrt2\beta g_p\int d\Delta_\omega\;x_\omega\sin\Delta_\omega\tau . &(5)
\end{aligned}
$$
$S_z$ commutes with $H$, so it is a constant of motion and enters the field equations as a static source. The oscillator couples to the field only through the delayed quadrature $\int d\Delta_\omega\,x_\omega\sin\Delta_\omega\tau$.

---

## 2. Exact solution of the field equations (1)–(2)

Combining (1) and (2):
$$
\ddot x_\omega+\Delta_\omega^2x_\omega=-\sqrt2\beta\,\Delta_\omega\,f_\omega(t),\qquad
f_\omega(t)\equiv\epsilon S_z-g_p\,x(t)\sin\Delta_\omega\tau .
$$
This is a driven harmonic oscillator. With initial data $x_{\omega0}\equiv x_\omega(0)$, $p_{\omega0}\equiv p_\omega(0)$, its solution is
$$
\boxed{\;
x_\omega(t)=x_{\omega0}\cos\Delta_\omega t+p_{\omega0}\sin\Delta_\omega t
-\sqrt2\beta\int_0^t dt'\,\sin\!\big[\Delta_\omega(t-t')\big]\Big(\epsilon S_z-g_p\,x(t')\sin\Delta_\omega\tau\Big)\;}
$$
$$
p_\omega(t)=-x_{\omega0}\sin\Delta_\omega t+p_{\omega0}\cos\Delta_\omega t
-\sqrt2\beta\int_0^t dt'\,\cos\!\big[\Delta_\omega(t-t')\big]\Big(\epsilon S_z-g_p\,x(t')\sin\Delta_\omega\tau\Big).
$$
**Check.** Differentiating $x_\omega(t)$, the boundary term vanishes because $\sin 0=0$, so $\dot x_\omega=\Delta_\omega\big[-x_{\omega0}\sin\Delta_\omega t+p_{\omega0}\cos\Delta_\omega t-\sqrt2\beta\int_0^t\cos[\Delta_\omega(t-t')]f_\omega\,dt'\big]=\Delta_\omega p_\omega$, which is (1). Differentiating $p_\omega(t)$ gives the boundary term $-\sqrt2\beta f_\omega(t)$ plus $-\Delta_\omega x_\omega$, which is (2).

**Noise term.** The homogeneous part is the freely evolving input (vacuum) field. Its quadrature part
$$
\boxed{\;F(t)=\int d\Delta_\omega\;x_{\omega0}\cos\Delta_\omega t\;}
$$
together with its partner $\tilde F(t)=\int d\Delta_\omega\,p_{\omega0}\sin\Delta_\omega t$ is the input noise. In equation (5) it appears in the delayed combination $\mathcal N(t)=\int d\Delta_\omega\,\sin\Delta_\omega\tau\,(x_{\omega0}\cos\Delta_\omega t+p_{\omega0}\sin\Delta_\omega t)$, which is linear in the same initial operators. By assumption the initial fluctuations average to zero, $\langle x_{\omega0}\rangle=\langle p_{\omega0}\rangle=0$, so $\langle F\rangle=\langle\tilde F\rangle=\langle\mathcal N\rangle=0$ and the noise does not contribute to the effective (coherent) dynamics.

---

## 3. Markov approximation: evaluating the frequency integrals

Insert the solution into the source term of (5):
$$
\int d\Delta_\omega\,x_\omega(t)\sin\Delta_\omega\tau
=\mathcal N(t)
-\sqrt2\beta\,\epsilon S_z\int_0^t dt'\,K_1(t-t')
+\sqrt2\beta\,g_p\int_0^t dt'\,x(t')\,K_2(t-t'),
$$
with the memory kernels
$$
K_1(s)=\int d\Delta_\omega\,\sin(\Delta_\omega s)\sin(\Delta_\omega\tau),\qquad
K_2(s)=\int d\Delta_\omega\,\sin(\Delta_\omega s)\sin^2(\Delta_\omega\tau).
$$
**Markov approximation.** The optical field is fast: its bandwidth is much larger than all system rates, and the coupling $\beta$ is flat over that band. We can therefore extend $\Delta_\omega$ over $(-\infty,\infty)$, which makes the kernels memoryless (delta functions):

* Using $\sin A\sin B=\tfrac12[\cos(A-B)-\cos(A+B)]$ and $\int d\Delta_\omega\cos(\Delta_\omega u)=\delta(u)$,
$$
K_1(s)=\tfrac12\big[\delta(s-\tau)-\delta(s+\tau)\big].
$$
* $\sin(\Delta_\omega s)\sin^2(\Delta_\omega\tau)$ is **odd** in $\Delta_\omega$, so over the symmetric band
$$
K_2(s)=0 .
$$
The back-action of the oscillator on itself through the field therefore cancels exactly in the Markov limit.

The time integral of $K_1$ over $s=t-t'\in[0,t]$ picks up only $\delta(s-\tau)$, since $s+\tau>0$. For $t>\tau$, after the light has propagated from the spin to the oscillator,
$$
\int_0^t dt'\,K_1(t-t')=\frac12 .
$$
Hence the **explicit result** of the frequency integral is
$$
\boxed{\;\int d\Delta_\omega\,x_\omega(t)\sin\Delta_\omega\tau=-\frac{\beta}{\sqrt2}\,\epsilon S_z+\mathcal N(t)\;\xrightarrow{\ \langle\mathcal N\rangle=0\ }\;-\frac{\beta}{\sqrt2}\,\epsilon S_z .\;}
$$
Physically, the field quadrature that reaches the oscillator carries the spin signal $\epsilon S_z$, imprinted a time $\tau$ earlier. The delay drops out because $S_z$ is conserved.

---

## 4. Substitution into the oscillator equation

Substituting $-\frac{\beta}{\sqrt2}\epsilon S_z$ into (5):
$$
\dot p=-\omega_p x-\sqrt2\beta g_p\Big(-\frac{\beta}{\sqrt2}\epsilon S_z\Big)
=-\omega_p x+\beta^2 g_p\epsilon\,S_z ,
$$
together with $\dot x=\omega_p p$ and $\dot S_z=0$. The field has disappeared. What remains is a closed set of equations for the oscillator and the spin, in which the oscillator feels a static force proportional to $S_z$ with strength
$$
\boxed{\;g=\beta^2 g_p\,\epsilon .\;}
$$
These equations are generated by a Hamiltonian that is quadratic in $(x,p)$ and has a term linear in $x\,S_z$. The overall sign of that linear term is a matter of convention: the canonical parity transformation $a\to-a$ (i.e. $x\to-x$, $p\to-p$) leaves $\tfrac12(x^2+p^2)$ and $[x,p]=i$ invariant and reverses the sign of the coupling. In the standard form the effective Hamiltonian is
$$
H_{\rm eff}=\frac{\omega_p}{2}(x^2+p^2)+g\,x\,S_z .
$$
Measuring frequencies in units of $\omega_p$ ($\omega_p=1$):
$$
\boxed{\;H_{\rm eff}=\frac12\,(x^2+p^2)+g\,x\,S_z,\qquad g=\beta^2 g_p\epsilon\;}
$$
or equivalently $H_{\rm eff}=\omega_p a^\dagger a+\frac{g}{\sqrt2}(a+a^\dagger)S_z$ up to a constant.

## 5. Summary
1. The Heisenberg equations (1)–(5) are linear in the field, so the field can be solved exactly; no perturbative adiabatic elimination is needed or justified.
2. The free part gives the vacuum noise $F(t)=\int d\Delta_\omega\,x_{\omega0}\cos\Delta_\omega t$, which has zero mean and drops out.
3. In the Markov limit, $\int d\Delta_\omega\sin\Delta_\omega s\sin\Delta_\omega\tau=\tfrac12[\delta(s-\tau)-\delta(s+\tau)]$ and the self-interaction kernel vanishes. The delayed field quadrature reduces to $-\frac{\beta}{\sqrt2}\epsilon S_z$.
4. Substituting into the oscillator equation gives an effective QND-type coupling $H_{\rm eff}=\frac12(x^2+p^2)+g\,xS_z$ with $g=\beta^2g_p\epsilon$, mediated by the light.
