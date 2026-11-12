# Accelerating CMB cosmological-parameter inference

## 0. Where the time goes

A standard pipeline evaluates, at each MCMC step,
$$
-2\ln\mathcal L(\boldsymbol\theta,\boldsymbol\nu)=\big[\hat C-C^{\rm th}(\boldsymbol\theta)-C^{\rm fg}(\boldsymbol\nu)\big]^T\Sigma^{-1}\big[\hat C-C^{\rm th}(\boldsymbol\theta)-C^{\rm fg}(\boldsymbol\nu)\big]+\text{const},
$$
where $\boldsymbol\theta$ are the cosmological parameters (6 for ΛCDM, 7–10 with extensions), $\boldsymbol\nu$ are about 10–30 foreground and nuisance parameters, $\hat C$ are the measured multi-frequency $TT/TE/EE$ band powers, and $\Sigma$ is their covariance. The foreground model and the matrix algebra are cheap (milliseconds). The **Boltzmann solver** that computes $C^{\rm th}_\ell(\boldsymbol\theta)$ takes $\sim1$–$10$ s per call at the accuracy needed for high-$\ell$ data. A random-walk Metropolis–Hastings (MH) chain needs $\sim10^5$–$10^6$ likelihood calls to converge in $\sim20$–$40$ dimensions, which amounts to days to weeks. The remedy is to (i) make each call cheaper and (ii) need fewer calls.

---

## 1. Approach A: neural-network emulator of the Boltzmann code

**Idea.** Learn the smooth deterministic map $\boldsymbol\theta\mapsto C_\ell^{XY}(\boldsymbol\theta)$ with a neural network (NN), and replace the Boltzmann call by a forward pass costing $\sim$ms on a CPU or $\sim\mu$s per sample in batches on a GPU.

**Implementation.**
1. **Define the training box.** Choose parameter ranges that comfortably contain the posterior, e.g. $\pm5$–$10\sigma$ around current constraints, or the full prior if it is compact.
2. **Design of training points.** Sample the box with a **Latin hypercube**. Each parameter range is divided into $N$ equal strata and every stratum is used exactly once per dimension. This gives uniform marginal coverage and avoids the clumps and holes of purely random sampling for the same budget. The design can be iterated by adding a second, denser hypercube in the high-posterior region.
3. **Generate data.** Run the Boltzmann code at each point and store $C_\ell^{TT,TE,EE,(\phi\phi)}$ for $\ell\le\ell_{\max}\sim3000$–$5000$. This is embarrassingly parallel.
4. **Preprocessing.**
   - Take the **logarithm** of the positive spectra ($TT$, $EE$, $\phi\phi$). This compresses the dynamic range of many orders of magnitude and makes the dependence on amplitude parameters ($A_s$, $\tau$) nearly linear. Rescale $TE$, which changes sign, e.g. by $\sqrt{C^{TT}C^{EE}}$.
   - Standardise each output: subtract the mean and divide by the standard deviation over the training set. Map the inputs to $[0,1]$ or $[-1,1]$.
   - Apply **PCA** to the preprocessed spectra and keep the $\sim20$–$50$ leading components, which capture $>99.99\%$ of the variance. The network then predicts these coefficients, which reduces the output dimension from $\sim10^4$ to $\sim10^2$, smooths noise, and speeds up training.
5. **Train** an MLP (e.g. 4 hidden layers $\times$ 512 units, smooth activations so that gradients exist) with a loss weighted by the data covariance, e.g. $\chi^2$ between emulated and true spectra. Use early stopping on a validation set.
6. **Validate on unseen points.** Accuracy must be measured on a held-out test set (and ideally on a fresh Latin hypercube) that was never used for training or early stopping. Errors on training points say nothing about generalisation.

**Benefits.** A $\sim10^3$–$10^4\times$ speed-up per call. The **whole inference becomes about 100$\times$ faster or more** (days to hours). The emulator is exactly differentiable (autodiff), so gradient-based samplers can be used, and it can be evaluated in large batches on GPUs.

**Drawbacks and effects of training-set limitations.**
- **Training needs GPUs and large amounts of memory.** For example, $10^5$ spectra $\times$ 4 types $\times$ 5000 multipoles $\times$ 8 bytes $\approx16$ GB of data, plus network and optimizer state. CPU-only training is impractically slow.
- **A large up-front cost:** a neural network emulator of the Boltzmann code requires about $10^5$ training examples (§5), i.e. $\sim10^5$–$10^6$ CPU-seconds of Boltzmann runs. This is a one-time cost, amortised over many chains and datasets.
- **Extrapolation.** NNs have no guarantees outside the region they were trained on: outputs can be smooth-looking but wrong. **The emulator must never be used outside its training range.** The sampler's priors must be hard-truncated to the training box, and a chain that pushes against a box edge must trigger retraining on an enlarged box, not continued use of the emulator.
- **Sparse or biased coverage** produces local errors that translate directly into **biased parameter means** or mis-estimated widths. An error $\delta C_\ell$ coherent across $\ell$ (e.g. in the damping tail) acts like a shift in $n_s$ or $\omega_b$. If the training set does not resolve sharp features (e.g. lensing at high $\ell$, extreme $\tau$ or $N_{\rm eff}$), the posterior is subtly wrong while looking well-converged.
- The emulator fixes the physics and precision settings of the Boltzmann code it learned, so a new model extension requires retraining.

---

## 2. Approach B: Gaussian-process (or polynomial) emulator of the PCA coefficients, or of the likelihood

**Idea.** Use the same preprocessing (log and PCA) but regress each PCA coefficient on $\boldsymbol\theta$ with a Gaussian process (GP), or with a low-order polynomial. Alternatively, emulate $\ln\mathcal L(\boldsymbol\theta)$ directly with a GP trained on an iteratively refined design.

**Implementation.** Latin-hypercube design with $N\sim10^3$–$10^4$ points; log and PCA preprocessing; squared-exponential or Matérn kernel per component, with hyperparameters fit by maximising the marginal likelihood; validation on held-out points. Optionally, use active learning: add training points where the GP predictive variance $\times$ posterior density is largest.

**Benefits.** Data-efficient in low dimension (6–8 parameters): good accuracy with $10^3$–$10^4$ runs. It provides a predictive uncertainty that can be propagated into the likelihood as an extra covariance, which flags regions of poor coverage. Training needs only a CPU, and it is easy to interpret.

**Drawbacks.** Training cost scales as $\mathcal O(N^3)$ and memory as $\mathcal O(N^2)$, which caps $N$ at $\sim10^4$. Accuracy degrades rapidly with dimension (curse of dimensionality), so extended models with 10+ cosmological parameters are hard. Prediction costs $\mathcal O(N)$ per call, slower than an NN forward pass. A likelihood emulator is tied to one dataset and foreground model and must be rebuilt for each. GPs revert to the prior mean outside the data, so they are also unreliable outside the training range. A large predictive variance warns of this but does not fix it.

---

## 3. Sampling strategy: Hamiltonian Monte Carlo

With a differentiable emulator, replace MH by **Hamiltonian Monte Carlo (HMC)**, preferably with automatic step-size and trajectory-length tuning (a no-U-turn variant).
- HMC introduces momenta $\mathbf p$ and simulates Hamiltonian dynamics on $H=-\ln\mathcal L(\boldsymbol\theta)-\ln\pi(\boldsymbol\theta)+\tfrac12\mathbf p^TM^{-1}\mathbf p$ with a leapfrog integrator. It proposes distant points with high acceptance probability.
- **HMC converges in fewer steps than standard Metropolis–Hastings.** The random walk explores a correlated posterior diffusively, with the number of steps per independent sample growing like $\sim D$ (and worse for strong degeneracies such as $A_s e^{-2\tau}$ or $\omega_m$–$H_0$). HMC moves ballistically along the gradient, with cost per independent sample growing like $\sim D^{1/4}$ in leapfrog steps. Autocorrelation lengths drop from $\sim10^2$–$10^3$ to $\sim1$–$10$.
- **HMC is especially useful for high-dimensional spaces.** The full CMB likelihood with cosmological, foreground, calibration and beam nuisance parameters has $D\sim20$–$40$ dimensions, and HMC's efficiency degrades only weakly with $D$.
- **Requirement:** **HMC needs a differentiable likelihood, written in a framework such as JAX** (or PyTorch/TensorFlow), so that $\nabla_{\boldsymbol\theta}\ln\mathcal L$ is obtained exactly by automatic differentiation. Finite differences on a Boltzmann code would cost $2D$ calls per gradient and be noisy. An emulator, foreground model and Gaussian likelihood written end to end in JAX give exact gradients for about the cost of one extra forward pass, and are just-in-time compiled and GPU-accelerated.
- Prior bounds must coincide with the emulator's training range (with a reflecting or transformed boundary), consistent with §1.

---

## 4. Quantitative plan for speed and accuracy

**Speed.**
- Measure the wall-clock time per likelihood call ($t_{\rm Boltz}\sim1$–$10$ s; $t_{\rm emu}\sim1$–$10$ ms, less per sample in GPU batches) and the effective samples per unit time: ESS/s $=N_{\rm eff}/(t_{\rm wall})$, with $N_{\rm eff}$ from the integrated autocorrelation time.
- Expected gains: emulator $\times10^2$–$10^3$ per call; HMC $\times\sim10$ fewer likelihood-equivalent evaluations per independent sample in $D\sim30$, with the gradient costing about 2–3 forward passes. Net time to convergence ($\hat R-1<0.01$) goes from days to under an hour. The **overall pipeline speed-up is $\gtrsim100\times$**, even after amortising the training cost over a few analyses.

**Accuracy (all on unseen test points).**
- Spectrum level: for test cosmologies, $\Delta\chi^2=(C^{\rm emu}-C^{\rm true})^T\Sigma^{-1}(C^{\rm emu}-C^{\rm true})\ll1$ (target $<0.1$ for the full dataset) and $|\Delta C_\ell|/\sigma_\ell<0.1$ at every $\ell$, where $\sigma_\ell$ includes cosmic variance and noise. Inspect the 99th-percentile error, not only the mean.
- Parameter level: run the full (slow) pipeline once on a reference dataset or simulation and compare. Require posterior mean shifts $<0.1\sigma$ and widths within $5\%$ for every parameter, and check the 2D contours.
- Coverage: on $\sim100$ simulated datasets drawn from cosmologies inside the training box, check that the $68/95\%$ credible intervals contain the truth at the nominal rates.
- Training-set convergence: retrain with $N/4$, $N/2$, $N$ examples and plot the test error against $N$. Accuracy is adequate when the error has plateaued below the targets above.

---

## 5. How many training samples?

The emulator error must be $\lesssim0.1\sigma_\ell$, i.e. sub-0.1% relative accuracy on the spectra at high $\ell$, over a $D\approx6$–$9$ dimensional box.
- **NN:** the generalisation error falls roughly as $N^{-1/2}$ to $N^{-1}$. Empirically, $10^3$ samples give errors at the percent level, and each factor of 10 gains a factor of 3–10. Reaching $\sim0.1\%$ therefore needs **about $10^5$ training examples**. Equivalently, $N^{1/D}\approx(10^5)^{1/7}\approx5$ effective points per dimension, enough to resolve the smooth but nonlinear (oscillatory, damping-tail) dependence. With $\sim10\%$ held out for validation and testing, plan for $\sim1.1\times10^5$ Boltzmann runs ($\sim3\times10^2$–$3\times10^3$ CPU-hours; hours on a cluster).
- **GP:** about $10^3$–$10^4$ points suffice in 6 dimensions because each point is used optimally, but $\mathcal O(N^3)$ scaling prevents going much beyond this, which limits the attainable precision and dimensionality.
- Each extra extended parameter multiplies the required $N$ by a factor of $\sim2$–$3$.

---

## 6. Best balance of efficiency and accuracy

**Recommended pipeline:** an NN emulator of the Boltzmann code (Latin-hypercube training set of $\sim10^5$ points, log and PCA preprocessing, trained on GPUs, validated on unseen points), embedded in a fully differentiable JAX likelihood and sampled with HMC/NUTS. The prior is restricted to the training box, and the emulator should never be used outside its training range.

**Reasoning.**
1. Per-call cost: the NN is faster than both the Boltzmann code and a GP ($\mathcal O(1)$ versus $\mathcal O(N)$ prediction), so it gives the $\gtrsim100\times$ speed-up.
2. Accuracy: with $\sim10^5$ examples the NN reaches the $\Delta\chi^2\ll1$ level needed to leave posteriors unbiased at the $0.1\sigma$ level. A GP cannot use that many examples.
3. Dimensionality: the NN handles extended models and the HMC handles the $\sim30$-dimensional nuisance space, where MH struggles.
4. Differentiability: the NN gives exact, cheap gradients, which unlock HMC's step-count advantage. The two accelerations multiply.
5. The costs (one-off training data generation and GPU/memory requirements) are paid once and amortised. The main risk, extrapolation outside the training range, is removed by construction through prior truncation and checked by held-out validation.

The GP approach remains attractive for very low-dimensional problems, or when a calibrated emulator uncertainty is essential. For standard and extended CMB analyses, NN emulation with HMC offers the best trade-off.
