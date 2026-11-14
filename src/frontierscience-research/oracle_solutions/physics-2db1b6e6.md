# Indirect search for WIMPs annihilating in the Sun with IceCube/DeepCore

## 1. Physical picture: why the Sun and why neutrinos

WIMPs ($\chi$) in the Galactic halo pass through the Sun continuously. When one scatters elastically off a solar nucleus and loses enough energy to fall below the local escape velocity, it becomes gravitationally bound. Repeated scatterings then make it sink and thermalize in the solar core. In the core, the accumulated WIMPs **annihilate** (or, in decaying-DM variants, decay) into Standard Model particles: $\chi\chi\to b\bar b,\ W^+W^-,\ \tau^+\tau^-,\ \nu\bar\nu,\dots$. Of the annihilation products, only neutrinos escape the dense solar interior. **The Sun is the only source of WIMPs considered here.**

The number $N$ of WIMPs in the Sun obeys
$$
\frac{dN}{dt}=C_\odot-C_A N^2-C_E N ,
$$
where $C_\odot$ is the capture rate, $C_A$ is the annihilation coefficient ($\Gamma_A=\tfrac12 C_AN^2$), and $C_E$ is the evaporation rate. Neglecting evaporation, the solution is
$$
\Gamma_A(t)=\frac{C_\odot}{2}\tanh^2\!\left(\frac{t}{\tau_{\rm eq}}\right),\qquad \tau_{\rm eq}=\frac{1}{\sqrt{C_\odot C_A}} .
$$
For weak-scale cross-sections, $\tau_{\rm eq}\ll t_\odot\simeq4.6$ Gyr, so capture and annihilation are in **equilibrium**:
$$
\boxed{\Gamma_A=\tfrac12 C_\odot}.
$$
The neutrino flux is then fixed by the **scattering** cross-section, not by the annihilation cross-section. A limit on $\Gamma_A$ therefore translates directly into a limit on the WIMP–nucleon cross-section.

**Capture rate.** For the solar composition and a standard halo,
$$
C_\odot\simeq 3\times10^{20}\,{\rm s^{-1}}\left(\frac{\rho_\chi}{0.3\,{\rm GeV\,cm^{-3}}}\right)\left(\frac{270\,{\rm km\,s^{-1}}}{\bar v}\right)^{3}\left(\frac{100\,{\rm GeV}}{m_\chi}\right)^{2}\frac{\sigma_{\chi p}^{\rm SD}+\sigma_{\chi p}^{\rm SI}+0.07\,\sigma^{\rm SI}_{\chi\,{\rm He}}+\dots}{10^{-6}\,{\rm pb}} ,
$$
up to form-factor and kinematic suppression factors that the solar-capture software computes exactly.

**Why a neutrino telescope is competitive in spin-dependent scattering.** About 3/4 of the solar mass is hydrogen, i.e. free spin-1/2 protons. Capture in the Sun is therefore dominated by **spin-dependent WIMP–proton scattering on hydrogen**, which is not suppressed by any nuclear form factor. Direct-detection targets such as Xe and Ge have their unpaired spins mostly on neutrons, so their sensitivity to $\sigma^{\rm SD}_{\chi p}$ is comparatively weak. In equilibrium, $\Phi_\nu\propto\Gamma_A=C_\odot/2\propto\sigma^{\rm SD}_{\chi p}$, and IceCube monitors a km$^3$-scale target. **Neutrino telescopes can therefore probe spin-dependent WIMP–proton cross-sections with very high sensitivity, giving the world-leading limits on $\sigma^{\rm SD}_{\chi p}$ over most of the mass range.** This is achieved although IceCube was not designed for dark matter: the Sun acts as a gravitational "concentrator" of WIMPs over billions of years, and IceCube only has to count the neutrinos arriving from a known point on the sky.

**Lower mass limit from evaporation.** Light WIMPs can be up-scattered by energetic solar nuclei to above the escape velocity and evaporate. The evaporation term $C_EN$ becomes comparable to annihilation for $m_\chi\lesssim3$–$4$ GeV. Below that mass the equilibrium relation $\Gamma_A=C_\odot/2$ fails and no robust flux can be predicted. **We therefore restrict the analysis to $m_\chi\ge 5$ GeV, safely above the evaporation mass of about 4 GeV.** At the upper end ($m_\chi\gtrsim 1$ TeV) neutrinos are absorbed and the $\nu_\tau$ are regenerated inside the Sun, and the propagation software accounts for this.

---

## 2. Signal prediction: software-predicted neutrino spectra

For each benchmark channel $f$ and mass $m_\chi$, the simulation chain computes:

1. hadronization and decay of the annihilation products in the solar core, producing $dN_{\nu}^{f}/dE_\nu$ for all flavors;
2. propagation out of the Sun (NC energy loss, CC absorption, $\tau$ regeneration) and from the Sun to Earth, including three-flavor vacuum and matter (MSW) oscillations;
3. the resulting flux at the detector,
$$
\frac{d\Phi_{\nu_\alpha}}{dE_\nu}=\frac{\Gamma_A}{4\pi d_\odot^2}\sum_f {\rm BR}_f\,\frac{dN^{f}_{\nu_\alpha}}{dE_\nu},\qquad E_\nu\le m_\chi .
$$

Benchmark masses: $m_\chi=5,\,10,\,20,\,35,\,50,\,100,\,250,\,500,\,1000,\,3000,\,10\,000$ GeV. The low-mass points are only accessible because of DeepCore.

**Folding with the detector response.** The expected number of signal events is
$$
\mu_s=T_{\rm live}\sum_{\alpha}\int dE_\nu\;\frac{d\Phi_{\nu_\alpha}}{dE_\nu}\,A^{\rm eff}_{\nu_\alpha}(E_\nu,\theta_\odot),
$$
where $A_{\rm eff}$ (after all selection cuts) is obtained from full detector Monte Carlo. The simulation produces neutrinos weighted to the solar spectrum, propagates them through the ice and the photon simulation, and passes them through triggers, filters and reconstruction. The same Monte Carlo provides the signal PDFs of reconstructed angle and energy (Section 5).

---

## 3. The IceCube Neutrino Observatory and DeepCore: geometry, threshold, topologies

* **IceCube:** 86 strings, 5160 digital optical modules (DOMs) at 1450–2450 m depth, 125 m string spacing, 17 m vertical DOM spacing, about 1 km$^3$ instrumented volume. Its energy threshold is about 100 GeV for well-reconstructed tracks.
* **DeepCore:** 8 densely instrumented strings with high-quantum-efficiency PMTs, 7 m DOM spacing and about 40–70 m string spacing. Together with the 7 surrounding standard strings, they sit in the clearest ice (2100–2450 m) at the bottom centre of the array. **DeepCore lowers the energy threshold to about 5–10 GeV, so the telescope can detect low-energy neutrinos below 10 GeV.** This is essential for WIMP masses of a few tens of GeV and below, and for soft channels like $b\bar b$, whose spectra peak at $E_\nu\sim m_\chi/10$.
* **Veto strategy:** the outer IceCube layers (and the upper DeepCore "veto cap" above the dust layer) act as an **active veto**. Events whose first light is in the veto region, or with causally connected hits there, are rejected as entering atmospheric muons. Only "starting" events with their vertex in the DeepCore fiducial volume are kept. This gives a veto power of $\gtrsim10^{6}$ against downgoing atmospheric muons.
* **Sun–detector geometry:** at the South Pole the Sun's zenith angle varies only between about 66.5° and 113.5° over the year. In **austral winter** the Sun is below the horizon, so its neutrinos are *upgoing* and the Earth itself filters out atmospheric muons. In **austral summer** the Sun is above the horizon and the neutrinos are *downgoing*, so the analysis relies entirely on the DeepCore/IceCube veto and on starting events.
* **Event topologies:** *tracks* from $\nu_\mu$ CC interactions (good pointing: the median $\nu$–$\mu$ angle is about $30^\circ\sqrt{{\rm GeV}/E_\nu}$ at low energy, falling to about 1° above a TeV); *cascades* from $\nu_e$ CC, $\nu_\tau$ CC and all-flavour NC interactions (good energy resolution, poor pointing of tens of degrees at 10 GeV).

---

## 4. Event selection

The selection is optimised separately for low-energy (DeepCore) and high-energy (IceCube) samples, and separately for summer and winter.

* **Neutrino flavors searched for.** The primary signal is **muon neutrinos ($\nu_\mu+\bar\nu_\mu$) undergoing charged-current interactions, which produce track events** with the best angular resolution toward the Sun. **Electron neutrinos ($\nu_e$) and tau neutrinos ($\nu_\tau$), observed as cascades in DeepCore**, are added in a separate low-energy all-flavor sample. Oscillations over the Sun–Earth distance populate all three flavors roughly equally, so including cascades raises the signal acceptance at $m_\chi\lesssim50$ GeV.
* **Trigger and filter:** the DeepCore Simple Multiplicity Trigger (≥3 hit DOMs in local coincidence within 2.5 µs) for the low-energy stream, and the standard SMT-8 for IceCube. Then the DeepCore veto filter and the IceCube muon filter.
* **Background rejection:** (i) the veto cuts described above remove atmospheric muons in summer; (ii) in winter, an upgoing reconstructed direction (zenith > 90°) removes them via the Earth shield; (iii) a boosted-decision-tree classifier trained on simulated signal versus off-source data (data away from the Sun, so the classifier is never trained on potential signal) uses vertex position, track length, hit timing, likelihood ratios of track versus cascade hypotheses, and reconstruction quality.
* **Reconstruction:** likelihood-based direction and energy reconstruction, with a per-event angular uncertainty $\sigma_i$ estimated from the likelihood landscape (paraboloid fit).
* **Data quality:** only good-run periods are used; the livetime is split into "Sun below horizon" and "Sun above horizon" sub-samples.

The final samples are dominated by atmospheric neutrinos (plus residual atmospheric muons at low energy), with a smaller, irreducible contribution from "solar atmospheric neutrinos" produced by cosmic rays hitting the solar atmosphere.

---

## 5. Analysis method

### 5.1 Multiple annihilation channels
The analysis is performed **separately for several benchmark annihilation channels, each assumed to have a 100 % branching ratio**. These bracket the realistic spectra:
* **$\chi\chi\to b\bar b$**: "soft" spectrum (neutrinos from $B$-meson decays);
* **$\chi\chi\to W^+W^-$** (for $m_\chi>m_W$): "hard" spectrum (prompt $W\to\ell\nu$);
* **$\chi\chi\to\tau^+\tau^-$**: hard spectrum (used in place of $W^+W^-$ for $m_\chi<m_W$);
* optionally **$\chi\chi\to\nu\bar\nu$**: a nearly monochromatic line at $E_\nu\simeq m_\chi$.

For every (channel, $m_\chi$) pair, the signal spectrum, signal PDFs and acceptance are recomputed and the full likelihood fit is repeated. Using several channels makes the results bracket any realistic model, which can be treated as a mixture of soft and hard channels.

### 5.2 Directional, energy-dependent likelihood toward the Sun
Each event $i$ has reconstructed angular separation $\psi_i$ from the Sun's position at the event time, reconstructed energy $E_i$, and angular error $\sigma_i$. The **unbinned extended likelihood** for $n_s$ signal events among $N$ observed events is
$$
\boxed{\;\mathcal L(n_s)=\prod_{i=1}^{N}\left[\frac{n_s}{N}\,S_i(\psi_i,E_i\,|\,m_\chi,f)+\left(1-\frac{n_s}{N}\right)B_i(\psi_i,E_i)\right]\;}
$$
* $S_i=S_\psi(\psi_i\,|\,\sigma_i,E_i)\times S_E(E_i\,|\,m_\chi,f)$ is the **signal probability density function (PDF)**. The spatial part peaks at $\psi=0$ with a width set by the angular resolution, and the energy part is the folded software-predicted spectrum.
* $B_i=B_\psi(\psi_i)\times B_E(E_i)$ is the **background PDF**. **The background depends on the angular separation from the Sun through the probability distribution function $B_\psi(\psi)$**, which reflects the zenith-dependent atmospheric flux and the detector acceptance along the Sun's path. It is constructed from data by scrambling the event times or right ascensions (the Sun moves on the sky), which automatically includes all detector effects and removes any signal correlation.

The **test statistic** is
$$
TS=2\ln\frac{\mathcal L(\hat n_s)}{\mathcal L(n_s=0)},\qquad \hat n_s\ge0 .
$$
Equivalently, a binned Poisson likelihood in $(\psi,E)$ bins $j$ can be used:
$\mathcal L=\prod_j {\rm Pois}\big(k_j\,|\,\mu_s f^s_j+\mu_b f^b_j\big)$.

### 5.3 Weighting of events outside the dark-matter energy range
Annihilation neutrinos are kinematically confined to $E_\nu\le m_\chi$, and below by the detector threshold. Events whose reconstructed energy lies **outside** the range populated by the signal (after smearing by the energy resolution) cannot be signal. They are handled through the per-event energy weight
$$
w_i=\frac{S_E(E_i\,|\,m_\chi,f)}{B_E(E_i)} .
$$
$S_E$ vanishes beyond the kinematic endpoint $m_\chi$ (smeared by the resolution), so such events receive a weight $w_i\to0$. They then contribute only through the background term of the likelihood and cannot fake a signal. For each mass hypothesis, an energy window $E_{\rm min}\le E_{\rm reco}\le m_\chi+2\sigma_E$ is also applied; events outside it are assigned zero signal weight (equivalently, they are removed from the signal region). This keeps the high-energy atmospheric tail from diluting the sensitivity at low WIMP masses.

### 5.4 Testing the method with simulations and pseudodata
* **Background-only pseudo-experiments:** thousands of scrambled data sets are fitted to obtain the $TS$ distribution under the null hypothesis, which is used for p-values.
* **Signal injection:** simulated signal events drawn from the Monte Carlo for each (channel, $m_\chi$) are injected into scrambled data with known $n_s^{\rm inj}$. This checks that $\hat n_s$ is unbiased and determines the **sensitivity** (the median 90 % C.L. upper limit in background-only pseudodata) and the discovery potential.
* **Coverage tests** of the upper-limit construction (Feldman–Cousins / Neyman belts built from the same pseudo-experiments), and blindness: the analysis is finalized on scrambled data before the true solar positions are unblinded.
* **Systematics** are evaluated by re-running the chain with simulations in which ice scattering and absorption, DOM efficiency, the neutrino cross-sections and the oscillation parameters are varied. The combined effect is typically 20–30 % on $\mu_s$ and is folded into the limits.

### 5.5 From event limits to physics limits
1. The 90 % C.L. upper limit $\mu_s^{90}$ gives the annihilation rate
   $$\Gamma_A^{90}=\frac{\mu_s^{90}}{T_{\rm live}\,\displaystyle\int dE\;\frac{1}{4\pi d_\odot^2}\frac{dN^f_\nu}{dE}A_{\rm eff}(E)} .$$
2. Equilibrium, $\Gamma_A=C_\odot/2$, and the capture formula then yield limits on $\sigma^{\rm SD}_{\chi p}$ (assuming SD-only capture) and on $\sigma^{\rm SI}_{\chi p}$ (assuming SI-only capture), for a standard halo ($\rho_\chi=0.3$–$0.4$ GeV cm$^{-3}$, Maxwellian with $v_0\approx220$ km s$^{-1}$).
3. The results are compared with direct detection. IceCube/DeepCore limits on $\sigma^{\rm SD}_{\chi p}$ reach about $10^{-40}$–$10^{-41}$ cm$^2$ for hard channels at 100 GeV–1 TeV, below those of direct-detection experiments. This is the quantitative statement of why a non-dedicated neutrino telescope places competitive WIMP limits.
