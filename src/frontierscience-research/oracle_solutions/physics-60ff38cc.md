# Confidence intervals on the flare duration of NGC 1068 when the best fit sits at $dt_{\max}=1960$ days

## 0. Likelihood and test statistic used throughout

For a Gaussian flare the time-dependent point-source likelihood is
$$
\mathcal L(n_s,\gamma,T_0,dt)=\prod_{i=1}^{N}\left[\frac{n_s}{N}S_i+\Big(1-\frac{n_s}{N}\Big)B_i\right],
$$
$$
S_i=S^{\rm space}_i(\vec x_i)\,S^{E}_i(E_i;\gamma)\,S^{T}_i(t_i;T_0,dt),\qquad
S^{T}_i=\frac{1}{\sqrt{2\pi}\,dt}\exp\!\left[-\frac{(t_i-T_0)^2}{2\,dt^2}\right],
$$
$$
B_i=B^{\rm space}_i\,B^{E}_i\,\frac{1}{T_{\rm live}} .
$$
The test statistic includes the usual marginalisation (look-elsewhere) factor for the flare duration:
$$
TS=-2\ln\!\left[\frac{T_{\rm live}}{\sqrt{2\pi}\,\widehat{dt}}\times\frac{\mathcal L(n_s=0)}{\mathcal L(\hat n_s,\hat\gamma,\hat T_0,\widehat{dt})}\right].
$$
The 2-D plot has $dt$ on the x-axis, $n_s$ on the y-axis, and $\Delta TS=TS_{\rm best\text{-}fit}-TS_{\rm truth}$ on the colour axis.

---

## 1. Which method: Feldman–Cousins, not Wilks

**Use the Feldman–Cousins (FC) method instead of Wilks' contours.**

Wilks' theorem states that $\Delta TS$ follows a $\chi^2$ distribution with $k$ degrees of freedom (so the 90 % 2-D contour would be $\Delta TS<4.61$). It holds only if:
* the true parameters lie in the **interior** of the allowed parameter space;
* the model is regular (smooth likelihood, identifiable parameters);
* the sample is large enough for the asymptotic limit.

Here the **best-fit $dt$ reaches the maximum allowed value of 1960 days**, i.e. it sits **on the boundary** of the parameter space. **Wilks' theorem therefore may not apply.** The $\Delta TS$ distribution near a boundary is a mixture of $\chi^2$ distributions with different numbers of degrees of freedom, not a $\chi^2_2$. Several further problems point the same way:
* as $dt\to dt_{\max}$ the flare becomes steady emission and $T_0$ becomes almost unconstrained (a non-identifiable parameter);
* $n_s\ge0$ is a second physical bound;
* the likelihood surface has two minima (a local one at small $dt$ and the global one at $dt_{\max}$);
* the signal is only a few tens of events.

Wilks' contours would then have the wrong coverage, and they could be unphysical or empty.

FC instead constructs the distribution of $\Delta TS$ explicitly with pseudo-experiments for every hypothesised true parameter point and uses the likelihood-ratio ordering principle. The resulting intervals have correct frequentist coverage by construction, are never empty or unphysical, and move automatically from a two-sided interval to a one-sided limit when the data sit at a boundary. Since the best fit is at the upper edge, we expect the result to be effectively a **lower limit on $dt$**.

---

## 2. Which trials and which parameter combinations

**Use signal trials only.** Each trial scrambles the data in right ascension/time, which preserves the detector acceptance and destroys any real signal. It then **injects** signal events from NGC 1068 with a specified true $(\gamma,T_0,dt,n_s)$: the number of events is Poisson-fluctuated around $n_s$, the energies follow $E^{-\gamma}$, and the arrival times follow a Gaussian centred on $T_0$ with width $dt$. A confidence interval needs the distribution of $\Delta TS$ *given that the truth is a particular signal hypothesis*. Background-only trials describe only the null hypothesis, so they are not used in this construction.

**The signal trials must be injected over combinations of all four parameters $\gamma$, $T_0$, $dt$ and $n_s$.** The two parameters not shown on the plot ($\gamma$ and $T_0$) are not fixed. They change the distribution of $\Delta TS$, so they must be varied in the injections as well. A concrete grid, centred on the data's best fit, is:

| parameter | values | number |
|---|---|---|
| $dt$ [days] | 1, 3, 10, 30, 60, 100, 200, 400, 700, 1000, 1400, **1960** (log-spaced, including the boundary) | 12 |
| $n_s$ | 5, 10, 15, 20, 30, 40, 50, 60, 80, 100 | 10 |
| $\gamma$ | 2.0, 2.5, 3.0, 3.5, 4.0 | 5 |
| $T_0$ [MJD] | the data best-fit $T_0$ plus 4 values evenly spread over the livetime | 5 |

This gives $12\times10\times5\times5=3000$ injected parameter combinations, with **at least 1000 signal trials per combination**. The binomial uncertainty on a 90 % quantile from $N_{\rm tr}$ trials is $\sqrt{0.9\cdot0.1/N_{\rm tr}}\approx1\%$ for $N_{\rm tr}=1000$. The total is about $3\times10^6$ fits, which is affordable on a cluster because each trial is independent. The grid can be refined (more trials, finer $dt$ and $n_s$ steps) near the provisional 90 % boundary.

---

## 3. Constructing the 2-D Feldman–Cousins contour

Let $\boldsymbol\theta_t=(\gamma_t,T_{0,t},dt_t,n_{s,t})$ denote an injected ("true") point of the grid.

### 3.1 Pseudo-trial $\Delta TS$ (for every $\boldsymbol\theta_t$, every trial $k$)
* **$TS_{\rm best\text{-}fit},k$:** run the **full minimizer** (not a scan) on trial $k$, freely fitting **all four parameters** $(n_s,\gamma,T_0,dt)$, with exactly the same seeding, bounds and settings used on the real data. This gives $TS(\hat{\boldsymbol\theta}_k)$.
* **$TS_{\rm truth},k$:** evaluate the TS of the same trial at the injected truth, with **all four parameters** fixed to $(\gamma_t,T_{0,t},dt_t,n_{s,t})$. This is a single likelihood evaluation; **no new fit** is run, because the truth is known exactly.
* $\Delta TS_k(\boldsymbol\theta_t)=TS_{\rm best\text{-}fit},k-TS_{\rm truth},k$.

Histogramming the $\Delta TS_k$ gives the trial $\Delta TS$ distribution for that $\boldsymbol\theta_t$. Its 90 % quantile is the critical value,
$$
\int_{-\infty}^{\Delta TS_{\rm crit}(\boldsymbol\theta_t)} p(\Delta TS\,|\,\boldsymbol\theta_t)\,d\Delta TS=0.90 .
$$

### 3.2 True-data $\Delta TS$ (one value per $\boldsymbol\theta_t$)
* **$TS_{\rm best\text{-}fit}^{\rm data}$:** the **minimizer** fit of the unscrambled data over **all four parameters** (the fit that returned $dt=1960$ d). This is computed once.
* **$TS_{\rm truth}^{\rm data}(\boldsymbol\theta_t)$:** taken from the **likelihood scan** of the true data, i.e. the TS of the data evaluated at the grid point with **all four parameters** set to $\boldsymbol\theta_t$. **Use the likelihood scan; do not run a new fit.** Fitting would move the parameters away from the hypothesised truth.
* $\Delta TS^{\rm data}(\boldsymbol\theta_t)=TS_{\rm best\text{-}fit}^{\rm data}-TS_{\rm truth}^{\rm data}(\boldsymbol\theta_t)$.

### 3.3 Comparison and the 90 % contour
**The true-data $\Delta TS$ is compared with the trial $\Delta TS$ distribution of the same injected hypothesis.** The FC p-value of each grid point is
$$
p(\boldsymbol\theta_t)=\frac{\#\{k:\ \Delta TS_k(\boldsymbol\theta_t)\ge\Delta TS^{\rm data}(\boldsymbol\theta_t)\}}{N_{\rm tr}} ,
$$
and $\boldsymbol\theta_t$ lies inside the 90 % confidence region if
$$
\Delta TS^{\rm data}(\boldsymbol\theta_t)\le\Delta TS_{\rm crit}(\boldsymbol\theta_t)\quad\Longleftrightarrow\quad p(\boldsymbol\theta_t)>0.10 .
$$

**Projection onto the $(dt,n_s)$ histogram.** For each $(dt,n_s)$ cell, the nuisance parameters are taken at the scan point that maximises the data TS for that $(dt,n_s)$ (profiling). That 4-parameter point is compared with the trials injected at the same $(\gamma,T_0,dt,n_s)$. A conservative alternative is to accept the cell if any $(\gamma,T_0)$ on the grid is accepted. The steps are then:
1. Fill the 2-D histogram (x: $dt$, y: $n_s$) with $\Delta TS^{\rm data}-\Delta TS_{\rm crit}$, or equivalently with $p$.
2. The **90 % contour** is the iso-line $\Delta TS^{\rm data}=\Delta TS_{\rm crit}$ ($p=0.10$), found by interpolating between grid cells (lightly smoothing the $p$ map if needed). Cells with $p>0.10$ are inside.
3. Because the global best fit is at $dt_{\max}$, the region is open toward the right edge of the plot. The confidence interval on $dt$ is read off as $dt>dt_{90}$, a lower limit. If the cells around the local minimum at small $dt$ also pass, FC correctly returns a disconnected region.
4. Overlaying the Wilks contour ($\Delta TS=4.61$) shows how badly the asymptotic approximation fails near the boundary.

---

## 4. When are positive and negative $\Delta TS$ values likely in the pseudo-trials?

With a perfect minimizer, $TS_{\rm best\text{-}fit}\ge TS_{\rm truth}$ always, because the truth is one point of the space the fit explores. Hence $\Delta TS\ge0$.

**Positive (large) $\Delta TS$.** **The best-fit TS likes to choose very long flares.** The factor $T_{\rm live}/(\sqrt{2\pi}\,\widehat{dt})$ penalises short flares and becomes small as $\widehat{dt}\to1960$ d. A long Gaussian also collects every signal-like event in the livetime: the steady NGC 1068 component, background fluctuations near the source, and the injected events. The fit is therefore pulled to $dt\approx dt_{\max}$ with a TS well above the TS at the injected truth. Large positive $\Delta TS$ is most likely when:
* the injected flare is **short** (small $dt_t$), or has **small $n_s$** or a soft $\gamma$ (signal hard to separate from background), so the long-flare fit beats the truth;
* the injected point is far from the region the data prefer.

**Negative $\Delta TS$** ($TS_{\rm best\text{-}fit}<TS_{\rm truth}$). This can only happen when the minimizer **fails to find the global optimum** and stops in a local minimum. It is likely when:
* the truth is a **long flare with sizeable $n_s$**, but the seeds (built from pairs of close-in-time, high-S/B events, see below) start the fit in the **local minimum at small $dt$**, so it never reaches the long-flare optimum;
* the truth is a **very short flare** whose events fall below the S/B threshold or are not paired in the seeds, so the narrow true peak is never explored;
* the truth is near the bounds (e.g. $dt_t=1960$ d or extreme $\gamma$), where the bounded optimizer stops early, or the $T_0$ direction is flat (long flares), so convergence is poor;
* the fit is essentially correct and only finite convergence tolerance gives small values $\Delta TS\approx0^{-}$.

---

## 5. Why the minimizer produces $\Delta TS\neq0$: how IceCube's time-dependent minimizer works

**Goal.** Minimise $-TS(n_s,\gamma,T_0,dt)$ with a bounded quasi-Newton minimizer (L-BFGS-B, as in IceCube's analysis software), within bounds such as $n_s\in[0,N]$, $\gamma\in[1,4]$, $dt\in[dt_{\min},1960\ {\rm d}]$ and $T_0$ within the livetime. Gradient-based minimizers only find the minimum of the basin they start in, so the initial values (seeds) decide whether the global minimum is found.

**S/B threshold.** For every event the **signal-over-background ratio** of its PDFs is computed using the time-independent parts:
$$
\left(\frac{S}{B}\right)_i=\frac{S^{\rm space}_i(\vec x_i)\,S^E_i(E_i;\gamma_{\rm seed})}{B^{\rm space}_i\,B^E_i(E_i)} .
$$
Only events with $(S/B)_i$ above a specified threshold (e.g. $S/B>1$) are considered. **Events below the threshold are not considered at all**: they are dropped from the seeding and from the time-dependent likelihood evaluation. The threshold exists to **reduce computational time**. Most of the $\sim10^6$ events in the sample are far from the source or have background-like energies, so discarding them reduces the number of seed pairs from $\mathcal O(N^2)$ to $\mathcal O(N_{S/B}^2)$ and makes each likelihood evaluation much cheaper.

**Choice of initial values.** For every pair of above-threshold events $i<j$ (with $t_i<t_j$), a flare seed is built:
$$
T_{0,ij}^{\rm seed}=\frac{t_i+t_j}{2},\qquad dt_{ij}^{\rm seed}=\frac{t_j-t_i}{2},
$$
$$
n_{s,ij}^{\rm seed}=\#\{\text{above-threshold events with } t_i\le t\le t_j\},\qquad \gamma^{\rm seed}=2.0\ (\text{or the time-integrated best fit}).
$$
The TS is evaluated at each seed (cheap, with no minimisation). The best few seeds are kept, the full 4-parameter minimisation is run from each, and the result with the highest TS is returned.

**How this causes $\Delta TS\neq0$.**
* Seeds come from pairs of events, so most seeds are **short flares** (pairs close in time far outnumber widely separated ones). The long-flare basin at $dt_{\max}$, where the data's global minimum actually lies, may never be seeded. The fit then stays in the local minimum at small $dt$, which gives negative $\Delta TS$ in trials.
* If injected signal events lie below the S/B threshold (e.g. soft $\gamma$ or low-energy events), no seed lands near the true flare.
* At the boundary $dt=1960$ d the gradient is not zero and $T_0$ is nearly degenerate, so the optimizer can terminate early. Finite tolerances add small scatter around $\Delta TS=0$.

**One improvement.** Supplement the event-pair seeds with **fixed seeds on a coarse log grid of durations that always includes the boundary**: $dt\in\{1,10,100,1000,1960\}$ d, with $T_0$ at the mid-livetime and at the best pair seed. Run the minimizer from each and keep the best result, and fit in $\log dt$ so that the landscape is smoother. A global stage (multi-start or basin hopping) followed by local L-BFGS-B refinement serves the same purpose. The cost is **computational time**: each extra seed adds one minimisation per trial, so 5 extra seeds multiply the cost of the $\sim3\times10^6$ FC trials by up to about 5. This is kept manageable by retaining the S/B threshold, so each likelihood evaluation stays cheap, by launching the extra seeds only when their pre-evaluated TS is competitive, and by distributing the independent trials over a computing cluster. The same seeding must be used for the data and for all trials so that $TS_{\rm best\text{-}fit}$ is defined identically in both.
