# Comet showers from a single random stellar encounter with the Oort cloud

## 1. Assumptions and approximations

1. **Impulse approximation.** The encounter lasts $\sim D/V_s$, which is much shorter than the orbital period of an Oort-cloud comet ($10^6$–$10^7$ yr). During the passage the comets and the Sun are effectively at rest, and each receives an instantaneous velocity kick.
2. **Straight-line stellar trajectory.** Relative to the Sun the star moves on a straight line with constant speed $V_s$. This holds because $V_s\sim20$–$50$ km s$^{-1}$, far above the Sun–star escape speed at the relevant distances. The impulses on the Sun and on a comet then point toward the star's line of closest approach and are approximately parallel.
3. **Test particles.** Comets are massless. The Sun and the comets respond only to the passing star (mass $M_s$) and to the Sun's gravity; comet–comet interactions, the Galactic tide and other stars are neglected for this single encounter.
4. **Thermalized cloud.** The Oort cloud is isotropic, comets are uniformly distributed in orbital phase, and the eccentricities follow the thermal distribution $f(e)\,de=2e\,de$, i.e. uniform in $e^2$ (equivalently, uniform in $J^2$ at fixed $a$).
5. **Nearly radial orbits.** The comets of interest have $e\to1$ and $q=a(1-e)\ll a$.
6. **Loss cone.** Comets with perihelion $q\lesssim R_J$ (Jupiter's orbit) are removed within one or a few orbits by planetary perturbations. In steady state this loss cone is (nearly) empty, and a **shower** occurs when an encounter refills it.
7. **Single encounter, generic parameters.** $M_s$, $V_s$, $D_\odot$ (closest approach to the Sun) are taken from the Gaia DR3 encounter statistics. Typical values are $M_s\sim0.1$–$1\,M_\odot$, $V_s\sim20$–$30$ km s$^{-1}$, and $\sim20$ stars per Myr passing within 1 pc.

---

## 2. Orbital relations

The polar form of the comet's radial equation, measuring the true anomaly $\theta$ from perihelion, is
$$
\boxed{\;r(\theta)=\frac{a(1-e^2)}{1+e\cos\theta}\;}
$$
with perihelion $q=a(1-e)$, aphelion $Q=a(1+e)$, semi-minor axis $b=a\sqrt{1-e^2}$, period $T=2\pi\sqrt{a^3/GM_\odot}$, and Kepler's second law $\frac{dA}{dt}=\frac{\pi ab}{T}$. This equation is used in §5 to find the fraction of the period spent within Jupiter's distance.

**Energy.** $v^2=GM_\odot\big(\frac2r-\frac1a\big)$.

**Time-averaged distance.** The time-averaged Sun–comet separation for a Keplerian orbit is $\langle r\rangle=a\big(1+\frac{e^2}{2}\big)$, and as $e\to1$, $\langle r\rangle\to1.5a$. From energy conservation, the orbital speed of a comet with semi-major axis $a$ at $r=1.5a$ is
$$
V_c^2=GM_\odot\Big(\frac{2}{1.5a}-\frac1a\Big)=\frac{GM_\odot}{3a}\quad\Longrightarrow\quad V_c=\Big(\frac{GM_\odot}{3a}\Big)^{1/2}.
$$

**Eccentricity distribution.** For the thermal distribution, the fraction of orbits with eccentricities between $e$ and unity is
$$
\boxed{\;F_e=\int_e^1 2e'\,de'=1-e^2 ,\;}
$$
which is independent of the semi-major axis of the orbits.

**Perihelion distribution.** With $q=a(1-e)$, i.e. $e=1-q/a$, the fraction of comets with semi-major axis $a$ that pass within a distance $q$ of the Sun is
$$
\boxed{\;F_q=1-\Big(1-\frac qa\Big)^2=\frac{2q}{a}\Big(1-\frac{q}{2a}\Big)\;}
$$
where $q$ is the distance of closest approach and $a$ the semi-major axis. For $q\ll a$, $F_q\simeq2q/a$, which is the angular size of the **loss cone**.

---

## 3. Velocity impulse from the passing star

In the impulse approximation, a body whose closest distance to the star's straight-line path is $D_i$ receives
$$
\boxed{\;\Delta V_i=\frac{2GM_s}{V_sD_i}\;}
$$
where $M_s$ is the mass of the perturbing star, $V_s$ its velocity relative to the Sun, and $D_i$ the closest approach distance. For the Sun $D_i=D_\odot$ and $\Delta V_i=\Delta V_\odot$; for the comet $D_i=D_c$ and $\Delta V_i=\Delta V_c$. This follows from integrating the transverse force $GM_sD_i/(D_i^2+V_s^2t^2)^{3/2}$ over the straight-line passage.

Only the **differential** impulse changes the comet's heliocentric orbit. Because the trajectory is a straight line, $\Delta\vec V_\odot$ and $\Delta\vec V_c$ are (nearly) parallel, so
$$
\boxed{\;\Delta V=\big|\Delta V_c-\Delta V_\odot\big|=\frac{2GM_s}{V_s}\left(\left|\frac{D_\odot-D_c}{D_cD_\odot}\right|\right).\;}
$$
Averaged over all comets at distance $r$ from the Sun (for $D_\odot\gg r$), $\langle|D_\odot-D_c|\rangle\sim r$ and $\langle D_\odot D_c\rangle\sim D_\odot^2$, so $\langle\Delta V\rangle\simeq2GM_sr/(V_sD_\odot^2)$, the tidal impulse. Using the time-averaged distance of a near-parabolic comet, $r=\langle r\rangle\simeq1.5a$, the impulse equation simplifies to
$$
\boxed{\;\langle\Delta V\rangle\simeq\frac{3aGM_s}{V_sD_\odot^2}.\;}
$$
Relative to the comet's typical orbital speed,
$$
\left(\frac{\langle\Delta V\rangle}{V_c}\right)^2=\frac{9a^2G^2M_s^2}{V_s^2D_\odot^4}\cdot\frac{3a}{GM_\odot}
=27\left(\frac{M_s}{M_\odot}\right)^2\left(\frac{a}{D_\odot}\right)^4\left(\frac{GM_\odot}{aV_s^2}\right).
$$

---

## 4. Smear cone versus loss cone: shower criterion and fraction perturbed

The kick rotates each comet's velocity vector by an angle up to $\theta_s\simeq\langle\Delta V\rangle/V_c$. The directions in velocity space that lead into the loss cone are thereby "smeared" over a **smear cone** of half-angle $\theta_s$. Its fractional angular area is $F_s=\pi\theta_s^2/4\pi=\frac14(\langle\Delta V\rangle/V_c)^2$, to be compared with the loss-cone fraction $F_q\simeq2q/a$. Measuring the loss cone in its natural unit $q/a$ (since $F_q\propto q/a$, the loss-cone fraction per unit $q/a$ is $F_q/(q/a)\simeq2$), for $\Delta V/V_c\ll1$ the **ratio of the angular area of the smear cone to that of the loss cone due to the passage of a single star** is
$$
\boxed{\;\frac{F_s}{F_q}=\frac{27}{8}\left(\frac{M_s}{M_\odot}\right)^2\left(\frac{a}{D_\odot}\right)^4\left(\frac{GM_\odot}{aV_s^2}\right).\;}
$$
This is the central result. In this normalization a loss cone with perihelion cutoff $q$ occupies the fraction $q/a$ of the unit, so:
- If $F_s/F_q\gtrsim q/a$, the encounter **completely refills the loss cone** for comets of semi-major axis $a$. A fraction $F_q\simeq2q/a$ of all those comets is put on orbits reaching $q<R_J$ within one orbital period, which is a **comet shower**.
- If $F_s/F_q\ll q/a$, only a correspondingly small part of the loss cone is refilled, a minor enhancement of the background flux.

Hence the **rate (strength) of comet showers for comets with semi-major axis $a$ is proportional to $M_s^2$ and $D_\odot^{-4}$, and depends on the encounter speed through $V_s^2$ in the factor $GM_\odot/(aV_s^2)$, i.e. it falls as $1/V_s^2$**. It rises very steeply with the comet's semi-major axis, $F_s/F_q\propto a^3$, while the refilling threshold $q/a$ falls as $1/a$.

**Fraction of comets perturbed into Earth-crossing / Jupiter-crossing orbits.** Taking the loss cone at $q=R_J$, the fraction of comets of semi-major axis $a$ injected by one encounter is
$$
f_{\rm inj}(a)\simeq\frac{2R_J}{a}\Big(1-\frac{R_J}{2a}\Big)\;\min\!\Big[1,\;\frac{a}{R_J}\,\frac{F_s}{F_q}\Big],
$$
and a fraction $F_{q_\oplus}/F_{q_J}\simeq q_\oplus/R_J\approx0.2$ of these (perihelia inside $\sim1$ AU) actually cross Earth's orbit. The shower lasts about one orbital period of the affected comets, $T(a)=2\pi\sqrt{a^3/GM_\odot}$, which is a few Myr for $a\sim10^4$ AU.

**Critical distance and frequency of showers.** Setting $F_s/F_q=q/a$ gives the largest closest-approach distance that produces a shower among comets of semi-major axis $a$:
$$
D_{\rm crit}^4=\frac{27}{8}\left(\frac{M_s}{M_\odot}\right)^2a^4\frac{GM_\odot}{aV_s^2}\,\frac{a}{q}
\quad\Longrightarrow\quad D_{\rm crit}^2\propto\frac{M_s}{V_s}\,a^{2}\Big(\frac{GM_\odot}{q}\Big)^{1/2}.
$$
For a stellar density $n_*$, encounters within $D_{\rm crit}$ occur at the rate $\nu=\pi n_*V_sD_{\rm crit}^2\propto n_*M_s$. The frequency of showers is thus set by the stellar density and the mass of the passing stars, while their velocity cancels at this level. Slower stars give stronger individual showers, and faster stars arrive more often. For example, with $q=R_J$, a Gliese 710–like encounter ($M_s\approx0.65M_\odot$, $V_s\approx14$ km s$^{-1}$, $D_\odot\approx0.05$ pc $\approx10^4$ AU) gives $F_s/F_q\gg q/a$ for $a\gtrsim2\times10^4$ AU, i.e. a shower from the outer Oort cloud.

---

## 5. Time spent within Jupiter's distance

We want the fraction of its period that an injected comet spends inside $r\le R_J$, which approximates "close to Earth's orbit".

**Small-angle approximation.** The portion of the orbit inside $R_J$ is a short arc around perihelion, $|\theta|\le\Theta\ll1$. With $\cos\theta\simeq1-\theta^2/2$:
$$
\boxed{\;r(\theta)=\frac{a(1-e^2)}{1+e\,(1-\theta^2/2)}=a(1-e^2)\Big(1+\frac{e}{2(1+e)}\theta^2\Big),\qquad\theta\ll1 .\;}
$$

**Area swept.** Here $\Theta$ is the angle between perihelion and the intersection of the elliptical orbit with Jupiter's orbit. The area swept by the radius vector inside $R_J$ is
$$
A=\int_0^{r}\int_{-\Theta}^{\Theta}r'\,dr'\,d\theta=\frac{a^2(1-e^2)^2}{2}\int_{-\Theta}^{\Theta}\Big(1+\frac{e}{1+e}\theta^2\Big)d\theta ,
$$
which to leading order in the small angle simplifies to
$$
A=a^2(1-e^2)^2\,\Theta .
$$

**Intersection angle.** The intersection with Jupiter's orbit (semi-major axis $R_J$) is given, in the same approximation, by
$$
R_J=a(1-e^2)\Big(1+\frac{e}{2(1+e)}\Theta^2\Big),
$$
which, written in terms of the perihelion distance $q=a(1-e)$, gives
$$
\Theta=\pm\sqrt{2\Big(1+\frac1e\Big)\Big(\frac{R_J}{a(1-e)}-1\Big)} .
$$
Consequently,
$$
\boxed{\;A=a^2(1-e^2)^2\,\Theta=a^2(1-e^2)^2\sqrt{2\Big(1+\frac1e\Big)\Big(\frac{R_J}{a(1-e)}-1\Big)} .\;}
$$

**Time fraction from Kepler's second law.** Since area is swept uniformly in time, $\Delta t=T\,\dfrac{\Delta A}{\pi a^2\sqrt{1-e^2}}$, which gives the ratio of the time spent within a Jupiter distance from the Sun to the period:
$$
\boxed{\;\frac{\Delta t}{T}=\frac{\sqrt2}{\pi}\,(1+e)\sqrt{\frac{1-e}{e}}\;\sqrt{\frac{R_J}{a(1-e)}-1}\; .\;}
$$
The fraction vanishes for $q=a(1-e)\to R_J$, when the orbit only grazes Jupiter's, and grows as the perihelion moves inward. For the injected near-parabolic comets ($e\to1$) it is a very small number: they spend almost their whole period in the cloud. The number of shower comets present inside Jupiter's orbit at any time is $N_{\rm in}(a)\simeq N(a)\,f_{\rm inj}(a)\,\Delta t/T$.

---

## 6. Physical interpretation

- **Mechanism.** A passing star does not throw comets directly at the Sun. It gives the comets and the Sun slightly different impulses, and the differential (tidal) kick $\langle\Delta V\rangle\simeq3aGM_s/(V_sD_\odot^2)$ changes the comets' angular momenta. Near-radial orbits with tiny angular momentum are thereby shuffled into the loss cone $q<R_J$, which planets keep empty in steady state.
- **Stellar mass.** $F_s/F_q\propto M_s^2$: doubling the stellar mass quadruples the smear-cone area. Massive stars dominate the strongest showers.
- **Closest approach.** $F_s/F_q\propto D_\odot^{-4}$, the steepest dependence. A star passing at half the distance is 16 times more effective. Showers are triggered essentially only by stars penetrating to $D_\odot\lesssim$ a few $\times10^4$ AU, and the most intense by passages through the cloud itself ($D_\odot\lesssim10^4$ AU), which reach the inner Oort cloud.
- **Velocity.** $F_s/F_q\propto V_s^{-2}$: slow stars act longer and give larger impulses. The rate of shower-producing encounters scales as $V_sD_{\rm crit}^2\propto M_s$, so the velocity largely cancels in the frequency.
- **Comet semi-major axis.** $F_s/F_q\propto a^3$, against a refilling threshold $q/a\propto a^{-1}$. Outer-cloud comets ($a\gtrsim2\times10^4$ AU) are perturbed by almost every encounter and give a quasi-steady flux. Inner-cloud comets ($a\lesssim10^4$ AU) are perturbed only by rare close encounters and then arrive in intense showers lasting $\sim T(a)$, a few Myr.
- **Arrival at Earth.** Of the injected comets, a fraction $\sim q_\oplus/R_J$ cross Earth's orbit. Each spends only the small fraction $\Delta t/T$ of its period within Jupiter's distance, so the instantaneous number of shower comets in the inner Solar System is $N(a)f_{\rm inj}\Delta t/T$. With Gaia DR3 rates ($\sim20$ encounters Myr$^{-1}$ within 1 pc, i.e. $\propto D^2$), the frequency of showers strong enough to raise the inner-Solar-System comet flux substantially is of order one per several tens of Myr.
