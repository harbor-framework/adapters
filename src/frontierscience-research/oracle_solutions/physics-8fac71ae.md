# Searching for supernova neutrino bursts with Super-Kamiokande

## 1. Why neutrinos rather than light?

About 99% of the $\sim3\times10^{53}$ erg released in a core collapse is emitted as neutrinos of all flavours, over a few tens of seconds, and only $\sim10^{-4}$ of the energy comes out as light. Neutrinos interact only weakly, so they escape the collapsing core and **travel through the interstellar medium of the Galaxy essentially unattenuated**. Optical photons are absorbed and scattered by interstellar dust: toward the Galactic plane and the Galactic centre the optical extinction reaches $A_V\sim30$ magnitudes or more, a suppression by more than $10^{12}$.

Consequently **neutrinos allow us to search for supernovae on the opposite side of the Galaxy, behind the Galactic centre, where they are normally optically obscured.** A core-collapse supernova at $\sim15$–$20$ kpc on the far side of the Galactic disk, hidden behind the dust lanes of the bulge, would be invisible optically but would still produce hundreds to thousands of events in Super-K. Further advantages:
- Neutrinos arrive hours before the optical shock breakout, which allows an early warning (SNEWS).
- Collapses that fail to explode (direct black-hole formation) have no bright optical counterpart at all, but still emit a neutrino burst.
- The neutrino signal probes the core directly: infall, neutronisation burst, accretion, shock revival and proto-neutron-star cooling.

The historical record of Galactic supernovae is incomplete, since optical observations miss most of the Galaxy. A neutrino search is a nearly complete, unbiased survey of the whole Milky Way.

---

## 2. Trigger for a supernova-neutrino search in Super-K

The dominant supernova signal is inverse beta decay (IBD), $\bar\nu_e+p\to e^++n$, which gives positrons with kinetic energies of roughly 5–50 MeV. Super-K (22.5 kt fiducial, about 11,000 20-inch PMTs) records Cherenkov light at roughly 6–7 hit PMTs per MeV of electron energy. A positron of a few MeV therefore produces a few tens of hits, compressed in time by the light-crossing time of the tank ($\lesssim200$ ns).

**The trigger should require a large number of PMT hits, more than about 20, within a short time window of less than 300 ns** (in practice a sliding window of $\sim200$ ns). Random dark-noise hits ($\sim$ few kHz per PMT, so $\sim$ 10 hits in 200 ns over the whole detector) rarely give more than 20 coincident hits. A real low-energy event above about 3–4 MeV does. The resulting single-event trigger fires on each IBD positron. A supernova search then looks offline or online for **clusters** of such triggered low-energy events.

---

## 3. Trigger efficiency

The hit count is a stochastic function of energy, position and direction (photon statistics, attenuation, PMT coverage $\approx40\%$). The efficiency therefore turns on gradually above threshold:
- for positron kinetic energy $E_{\rm kin}>5.5$ MeV: **efficiency $\approx54\%$**;
- for positron kinetic energy $E_{\rm kin}>8.5$ MeV: **efficiency $\approx99\%$** (fully efficient).

Near 5.5 MeV only about half of the events exceed the hit threshold, whereas by 8.5 MeV essentially all do. For spectrum-averaged supernova IBD positrons, mean energy about 15 MeV, the overall efficiency is therefore close to 100%.

---

## 4. Expected size and duration of a neutrino cluster from the Galactic centre

Estimate for $d=10$ kpc:
- Energy in $\bar\nu_e$: $\approx\frac16\times3\times10^{53}$ erg $=5\times10^{52}$ erg. With $\langle E_{\bar\nu_e}\rangle\approx15$ MeV $=2.4\times10^{-5}$ erg, this is $N_{\bar\nu_e}\approx2\times10^{57}$ antineutrinos.
- Fluence: $\Phi=N/4\pi d^2=2\times10^{57}/(1.2\times10^{46}\ {\rm cm^2})\approx1.7\times10^{11}$ cm$^{-2}$.
- Free protons in 22.5 kt of water: $N_p=22.5\times10^9\ {\rm g}\times\frac{2}{18}\times6.0\times10^{23}\approx1.5\times10^{33}$.
- IBD cross-section $\sigma\approx9.5\times10^{-44}\,E_eP_e$ cm$^2$ (MeV), averaged over the spectrum: $\langle\sigma\rangle\approx2$–$3\times10^{-41}$ cm$^2$.

$$
N_{\rm ev}\approx\Phi\,\langle\sigma\rangle\,N_p\approx1.7\times10^{11}\times2\times10^{-41}\times1.5\times10^{33}\sim\text{a few}\times10^3 .
$$
Adding the smaller elastic-scattering and $^{16}$O channels and allowing for the detection efficiency and the spread between supernova models, **a supernova near the Galactic centre gives a neutrino cluster of order 1000 events ($\mathcal O(10^3)$)**. These are **distributed over a time scale of order 100 s**. Most arrive in the first few seconds of accretion and early cooling, but the proto-neutron-star cooling tail extends the cluster to $\sim100$ s, so a search should look for clusters within windows of up to roughly 100 s.

---

## 5. Dependence of the number of events on distance

The neutrino fluence falls geometrically, $\Phi\propto1/(4\pi d^2)$. Absorption is negligible and the detector target and efficiency are fixed, so
$$
\boxed{\;N_{\rm ev}(d)=N_{\rm ev}(10\ {\rm kpc})\left(\frac{10\ {\rm kpc}}{d}\right)^2\propto\frac{1}{d^2}.\;}
$$
For example, relative to the $\mathcal O(1000)$ events from the Galactic centre (10 kpc), a supernova at 20 kpc (far side of the Galaxy) gives 4 times fewer events, one in the Large Magellanic Cloud (50 kpc) 25 times fewer, and one in M31 (about 770 kpc) roughly 6000 times fewer, i.e. of order one event or less. This is why the search must also be sensitive to small clusters from distant supernovae.

---

## 6. Backgrounds that must be removed by visual scanning

Most backgrounds (spallation products, radioactivity, muon-induced events) are removed by automated cuts. However, some instrumental pathologies produce bursts of fake low-energy triggers that mimic a cluster, and **these must be removed manually by visually scanning the event displays.** The two classes are:
1. **PMT malfunction**, e.g. "flasher" PMTs that discharge and emit light, producing repetitive events with a characteristic hit pattern around one PMT, or noisy/hot PMTs and channels.
2. **Data-acquisition (DAQ) problems**, e.g. electronics or DAQ errors, readout or timing glitches, and noise bursts after run starts, high-voltage trips or calibration activity. These produce clusters of fake events in a short time.

Both kinds create time-clustered "events" that pass the multiplicity cut. They are identified by eye from the abnormal hit patterns and time structure, and the corresponding clusters or periods are rejected.

---

## 7. Minimum time separation between events in a cluster

Genuine supernova events are separated by $\mathcal O(1\ {\rm ms})$ (of order 1000 events, most of them within the first few seconds). Correlated backgrounds produce pairs or bursts separated by much less:
- muon-decay electrons ($\tau_\mu=2.2\ \mu$s);
- PMT afterpulsing and electronics ringing (about 10–20 $\mu$s after a large signal);
- very short-lived spallation products.

The search should therefore **require a minimum time difference of $50\ \mu$s between all events in the cluster** ($\Delta t>50\ \mu$s between any two events). This is many times the muon lifetime and afterpulse time scales, so these correlated backgrounds are removed. For a supernova event rate $R\lesssim10^3$ s$^{-1}$, the fraction of genuine events lost is only $\approx R\times50\ \mu{\rm s}\lesssim5\%$, and well below 1% for typical rates of order 100 s$^{-1}$, so the signal is essentially unaffected.
