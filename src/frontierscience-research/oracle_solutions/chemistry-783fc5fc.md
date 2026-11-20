# Symmetry-adapted TICA for the α7 nAChR: a C$_5$-constrained dimensionality reduction strategy

## 0. Summary of the strategy

**The primary method is time-lagged independent component analysis (TICA)** — the variational-approach-to-conformational-dynamics (VAC/Koopman) estimator that maximises autocorrelation at lag $\tau$ and therefore finds, by construction, the **slowest** collective degrees of freedom rather than the largest-amplitude ones (which is what PCA would return). The α7 receptor's homopentameric C$_5$ symmetry is then built into the estimator at the level of the **covariance and Koopman matrices**, which become **block circulant**; this collapses a $5N\times5N$ eigenvalue problem to an $N\times N$ one, multiplies the effective sampling by five, and yields symmetry-adapted eigenvectors that are used both to define a global collective coordinate and to quantify subunit-by-subunit asymmetry. The full pipeline is:

1. Featurisation per subunit (intra-subunit and inter-subunit C$\alpha$ distances).
2. Mean-free data, lag-$\tau$ covariance estimation, **reversibility (detailed-balance) symmetrisation**.
3. **C$_5$ symmetrisation (symmetry-collapse) of the Koopman/covariance matrices.**
4. Exploitation of the resulting block-circulant structure $\rightarrow$ **reduced $N\times N$ eigenproblem** for the symmetric ($k=0$) irreducible representation.
5. Projection onto symmetry-adapted eigenvectors $\rightarrow$ per-subunit ICs (subICs) and the global IC.
6. Post-reduction quantification/visualisation of symmetry breaking (subunit variance, permutation-invariant MDS).

## 1. Featurisation and the symmetry group

Label the five identical subunits $S\in\{A,B,C,D,E\}$ arranged cyclically around the pore. For each subunit define the feature vector

$$\mathbf{x}_S(t) \in \mathbb{R}^{N}$$

containing (i) the **intra-subunit** C$\alpha$–C$\alpha$ distances of subunit $S$ and (ii) the **inter-subunit** C$\alpha$–C$\alpha$ distances between $S$ and its clockwise neighbour (A–B, B–C, C–D, D–E, E–A). Assigning each interface to exactly one subunit in a consistent, cyclically equivariant way is essential: it guarantees that the map $S\mapsto \mathbf{x}_S$ commutes with the cyclic relabelling.

The full feature vector is the concatenation

$$\mathbf{X}_t = \big(\mathbf{x}_A(t)^\top,\mathbf{x}_B(t)^\top,\mathbf{x}_C(t)^\top,\mathbf{x}_D(t)^\top,\mathbf{x}_E(t)^\top\big)^\top \in \mathbb{R}^{5N},$$

mean-free, $\langle \mathbf{X}\rangle = 0$ (subtract the *symmetrised* mean, $\bar{\mathbf{x}} = \frac{1}{5}\sum_S \langle\mathbf{x}_S\rangle$, applied to every block, so that the centring itself does not break the symmetry).

The relevant symmetry group is the cyclic group $C_5 = \{\mathcal{R}^0,\mathcal{R}^1,\dots,\mathcal{R}^4\}$, realised on feature space by the **block permutation (rotation) operator**

$$\mathcal{R} = P\otimes \mathbb{I}_N, \qquad P = \begin{bmatrix}0&0&0&0&1\\1&0&0&0&0\\0&1&0&0&0\\0&0&1&0&0\\0&0&0&1&0\end{bmatrix},$$

i.e. $\mathcal{R}$ cyclically relabels $A\to B\to C\to D\to E\to A$ while acting as the identity inside each $N$-dimensional block. $\mathcal{R}$ is orthogonal, $\mathcal{R}^\top = \mathcal{R}^{-1}$, and $\mathcal{R}^5 = \mathbb{I}$.

## 2. Symmetry integration: why and how

Because the five subunits are chemically identical, the underlying dynamics is **equivariant** under $C_5$: the transfer/Koopman operator commutes with the relabelling, $[\mathcal{K},\mathcal{R}] = 0$. Two practical gains follow.

**(a) Data augmentation / statistical efficiency.** Any trajectory frame can be legitimately replicated five times by cyclic relabelling. Equivalently, each subunit's own time series is an independent realisation of the *same* local process. With simulations too short to see a full receptor transition but long enough to see single-subunit dynamics, this is the decisive advantage: the effective number of samples for estimating the $N\times N$ local statistics is multiplied by 5, which suppresses the variance (and the overfitting-induced over-estimation of timescales) that plagues TICA in the short-trajectory / high-dimensional regime.

**(b) Model-size reduction and accuracy.** Imposing the symmetry *a priori* removes the $5N(5N+1)/2$-parameter general problem in favour of a few $N\times N$ blocks. The spectrum then decomposes exactly into the irreducible representations of $C_5$, and spurious modes that merely mix statistical noise between subunits are eliminated. Symmetry constraints therefore act as a strong, physically motivated regulariser on the estimation of the dominant dynamical modes: the estimated slow modes are forced to be either fully symmetric or members of exactly degenerate doublets, so their eigenvalues (and the implied relaxation timescales $t_i = -\tau/\ln\lambda_i$) are estimated from five-fold more data and are far less contaminated by noise.

Practically, the symmetrisation is imposed by **explicitly constructing the symmetry-collapsed matrix**

$$\boxed{K_{\text{sum}} = \sum_{k=0}^{4} \mathcal{R}^{k}\,K\,(\mathcal{R}^{\top})^{k}}$$

where $\mathcal{R}$ is the C$_5$ rotation operator. $K_{\text{sum}}$ is, by construction, exactly $C_5$-invariant: $\mathcal{R}K_{\text{sum}}\mathcal{R}^\top = K_{\text{sum}}$. (Equivalently one may use $\frac{1}{5}K_{\text{sum}}$, the group average; the factor of 5 only rescales eigenvalues uniformly.) The same averaging is applied to the instantaneous covariance $C_0$ and to $C_\tau$ before forming $K$.

## 3. Matrix construction

### 3.1 Time-lagged covariance and the Koopman eigenvalue problem

With mean-free features, the **instantaneous** and **time-lagged covariance matrices** are

$$C_0 = \big\langle \mathbf{X}_t\mathbf{X}_t^\top\big\rangle, \qquad \boxed{C_\tau = \big\langle \mathbf{X}_t\,\mathbf{X}_{t+\tau}^\top\big\rangle}$$

estimated as time averages over all frames, $C_\tau = \frac{1}{T-\tau}\sum_{t}\mathbf{X}_t\mathbf{X}_{t+\tau}^\top$.

The Koopman matrix (the finite-dimensional approximation of the Koopman/transfer operator in the chosen feature basis) is

$$\mathbf{K} = C_0^{-1}C_\tau,$$

and the **Koopman eigenvalue problem** is

$$\boxed{\mathbf{K}\mathbf{v} = \lambda\mathbf{v}}$$

equivalently the generalised (TICA) eigenproblem

$$C_\tau\mathbf{v} = \lambda\,C_0\mathbf{v},$$

whose eigenvalues $\lambda_i\in(-1,1]$ are the autocorrelations of the corresponding independent components at lag $\tau$ and whose implied timescales are $t_i = -\tau/\ln|\lambda_i|$. The trivial stationary eigenvalue $\lambda_0 = 1$ is removed by the mean-free construction. Maximising $\lambda$ is exactly the variational principle that makes TICA return the **slowest** modes.

### 3.2 Physical reversibility (detailed balance)

Equilibrium MD obeys detailed balance, so the exact $C_\tau$ must be symmetric. Finite sampling makes the estimate asymmetric, which produces complex eigenvalues and unphysical (non-decaying or oscillating) modes. Reversibility is therefore **enforced by symmetrising the lagged covariance**:

$$\boxed{C_\tau \leftarrow \tfrac{1}{2}\left(C_\tau + C_\tau^\top\right)}$$

(together with the corresponding symmetric estimate $C_0 \leftarrow \frac{1}{2}(\langle\mathbf{X}_t\mathbf{X}_t^\top\rangle + \langle\mathbf{X}_{t+\tau}\mathbf{X}_{t+\tau}^\top\rangle)$, i.e. including both time-shifted blocks). With $C_\tau = C_\tau^\top$ and $C_0 = C_0^\top \succ 0$, the generalised eigenproblem is **self-adjoint**: all $\lambda_i$ are real, eigenvectors are $C_0$-orthogonal, $\mathbf{v}_i^\top C_0\mathbf{v}_j = \delta_{ij}$, and the whole problem reduces to a symmetric (whitened) eigenproblem $\tilde{C}_\tau = C_0^{-1/2}C_\tau C_0^{-1/2}$, which can be solved stably.

### 3.3 The structure induced by C$_5$ symmetry: block circulant matrices

Partition $\mathbf{K}$ (or the symmetrised $C_\tau$) into $5\times5$ blocks of size $N\times N$ indexed by subunit pairs. $C_5$ equivariance means a block depends only on the *cyclic separation* of the two subunits, and reversibility makes the matrix symmetric overall; since the separation $+2$ is the reverse of $-2$, this gives exactly **three independent blocks**: $K_d$ (same subunit, $K_d = K_d^\top$), $K_{o1}$ (nearest cyclic neighbour) and $K_{o2}$ (next-nearest cyclic neighbour). The resulting matrix is **block circulant and symmetric**:

$$
\mathbf{K} =
\begin{bmatrix}
K_d & K_{o1} & K_{o2} & K_{o2}^\top & K_{o1}^\top \\
K_{o1}^\top & K_d & K_{o1} & K_{o2} & K_{o2}^\top \\
K_{o2}^\top & K_{o1}^\top & K_d & K_{o1} & K_{o2} \\
K_{o2} & K_{o2}^\top & K_{o1}^\top & K_d & K_{o1} \\
K_{o1} & K_{o2} & K_{o2}^\top & K_{o1}^\top & K_d
\end{bmatrix}
$$

Each row is the preceding row shifted cyclically by one block; the transposed partners appear because reversibility ties the $S\!\rightarrow\!S'$ block to the $S'\!\rightarrow\!S$ block. In practice this exact pattern is obtained by applying the symmetry collapse $K_{\text{sum}} = \sum_{k=0}^{4}\mathcal{R}^kK(\mathcal{R}^\top)^k$ to the raw estimate and then the detailed-balance symmetrisation $C_\tau\leftarrow\frac12(C_\tau+C_\tau^\top)$ (the two operations commute).

### 3.4 How the structure simplifies the eigenvalue problem

A block circulant matrix is **block-diagonalised by the discrete Fourier transform over $C_5$**. Writing $\omega = e^{2\pi i/5}$ and the symmetry-adapted (irrep) vectors

$$\mathbf{v}^{(k)} = \frac{1}{\sqrt5}\big(\mathbf{v}_A,\ \omega^{k}\mathbf{v}_A,\ \omega^{2k}\mathbf{v}_A,\ \omega^{3k}\mathbf{v}_A,\ \omega^{4k}\mathbf{v}_A\big)^\top,\qquad k = 0,1,2,3,4,$$

the $5N\times5N$ problem decouples into five $N\times N$ problems, one per irrep,

$$\Big(K_d + \omega^{k}K_{o1} + \omega^{2k}K_{o2} + \omega^{3k}K_{o2}^\top + \omega^{4k}K_{o1}^\top\Big)\mathbf{v}_A = \lambda\,\mathbf{v}_A ,$$

with $k=1,4$ and $k=2,3$ forming the two doubly degenerate $E_1$, $E_2$ representations (the "wave-like" modes with one or two nodes around the ring), and $k=0$ the totally symmetric ($A$) representation.

**Reduced matrix equation for the symmetric mode.** The slowest, functionally relevant mode of a homopentamer undergoing a concerted resting$\rightarrow$open (gating) transition is the breathing/twisting motion in which all five subunits move in phase. This is the $k=0$ irrep, obtained by the substitution

$$\mathbf{v}_A = \mathbf{v}_B = \mathbf{v}_C = \mathbf{v}_D = \mathbf{v}_E .$$

Inserting this ansatz into $\mathbf{K}\mathbf{v} = \lambda\mathbf{v}$ and reading off any one row of the block circulant matrix (all five rows give the same equation, which is precisely the consistency condition that makes the ansatz exact) gives

$$\boxed{\big(K_d + K_{o1} + K_{o2} + K_{o2}^\top + K_{o1}^\top\big)\mathbf{v}_A = \lambda\,\mathbf{v}_A}$$

i.e. the $N\times N$ reduced eigenproblem $K_{\text{red}}\mathbf{v}_A = \lambda\mathbf{v}_A$ with $K_{\text{red}} = K_d + K_{o1} + K_{o2} + K_{o2}^\top + K_{o1}^\top$ (equivalently, $K_{\text{red}}$ is the single $N\times N$ block of $\frac{1}{5}K_{\text{sum}}$ summed over cyclic offsets; in generalised form $C_{\tau,\text{red}}\mathbf{v}_A = \lambda C_{0,\text{red}}\mathbf{v}_A$ with the same offset sums for $C_0$). $K_{\text{red}}$ is symmetric, so its eigenvalues are real and ordered, and the dominant one defines the slowest symmetric collective mode. The dimensionality of the diagonalisation has dropped from $5N$ to $N$ — a factor of 5 in dimension and 125 in cost — while the statistics entering each matrix element have improved five-fold.

Correspondingly, the fully symmetric collective direction in the original feature space is identified as

$$\boxed{\mathbf{v}_{\text{sym}} \propto \sum_{S=A}^{E}\mathbf{x}_S}$$

the in-phase (zero-node, $k=0$) combination of the subunit feature blocks: the slow mode lives in the subspace spanned by the symmetric sum of subunit coordinates, and $\mathbf{v}_A$ from the reduced problem gives its detailed weighting over the $N$ local distances.

## 4. Dimensionality reduction: projections onto symmetry-adapted eigenvectors

Having solved the reduced problem for $\mathbf{v}_A$ (and, if desired, the first few $\mathbf{v}_A^{(i)}$, $i = 1,2,\dots,m$ with $\lambda_1\ge\lambda_2\ge\dots$), the high-dimensional trajectory is projected as follows.

**Per-subunit independent components (subICs) and the global IC:**

$$\begin{aligned}
\text{subIC}_S &= \mathbf{v}_A^\top \mathbf{x}_S \quad \forall S\in\{A,\dots,E\} \\
\text{IC} &= \sum_{S=A}^{E} \text{subIC}_S
\end{aligned}$$

The *same* eigenvector $\mathbf{v}_A$ is applied to every subunit block — that is what "symmetry-adapted" means — so each $\text{subIC}_S(t)$ is a scalar reporting the progress of subunit $S$ along the slow local mode, and their sum $\text{IC}(t) = \mathbf{v}_{\text{sym}}$-projection is the **global collective coordinate** of the receptor (identical to $\mathbf{v}^{(0)\top}\mathbf{X}_t$ up to the $1/\sqrt5$ normalisation). Repeating with $\mathbf{v}_A^{(1)},\mathbf{v}_A^{(2)},\dots,\mathbf{v}_A^{(m)}$ yields an $m$-dimensional representation $\{\text{IC}_1,\dots,\text{IC}_m\}$, typically $m = 2$–4, in which the resting and open states appear as separated basins and which preserves the **collective** (concerted, in-phase) motions by construction, because the projection vectors are the slow symmetric modes rather than arbitrary linear combinations.

This low-dimensional space is then the natural input to downstream kinetic modelling: clustering of $\{\text{IC}_i\}$ followed by an MSM/VAMP validation (implied-timescale and Chapman–Kolmogorov tests versus $\tau$), free-energy surfaces $F(\text{IC}_1,\text{IC}_2) = -k_BT\ln p(\text{IC}_1,\text{IC}_2)$ for the resting and open ensembles, and identification of which C$\alpha$ distances dominate the mode by inspecting the largest-magnitude entries of $\mathbf{v}_A$ (expected to highlight the loop C closure, the $\beta1$–$\beta2$/Cys-loop–M2–M3 coupling region and the M2 pore-lining contacts).

If the non-symmetric irreps are also of interest, the degenerate $E_1$/$E_2$ blocks ($k=1,2$) give the one- and two-node "wave" modes around the ring; their projections are the complex combinations $\sum_S \omega^{kS}\,\text{subIC}_S$, whose amplitude measures how much of the dynamics corresponds to sequential (domino-like) rather than concerted subunit motion.

## 5. Post-reduction quantification and visualisation of subunit differences

Although the *model* is symmetric, the *trajectory* need not be: in a finite simulation the five subunits occupy different points along the same local mode, and the asymmetry is exactly what reveals whether gating is concerted or sequential. Two complementary diagnostics are used.

**(a) Subunit variance (asymmetry amplitude).** With $\langle\text{subIC}\rangle = \frac{1}{5}\sum_{S=A}^{E}\text{subIC}_S$ (the instantaneous mean over subunits, equal to $\text{IC}/5$), define the per-frame spread

$$\boxed{\sigma = \sqrt{\frac{1}{5}\sum_{S=A}^{E}\big(\text{subIC}_S - \langle \text{subIC}\rangle\big)^{2}}}$$

$\sigma(t)$ is the order parameter for **symmetry breaking**: $\sigma \approx 0$ means all five subunits are in register (fully concerted, pure $k=0$ character), whereas large $\sigma$ means the subunits are dispersed along the mode (sequential/asymmetric activation, significant $E$-irrep amplitude). Plotting the two-dimensional histogram of $(\text{IC},\sigma)$ — the collective progress coordinate against the asymmetry — gives a compact map of the transition: a path that rises in $\sigma$ at intermediate IC indicates an asymmetric transition state, while a low-$\sigma$ ridge indicates a concerted one. Comparing the $(\text{IC},\sigma)$ densities of the resting-state and open-state simulations shows directly how each state samples symmetry breaking, and per-subunit time traces $\text{subIC}_S(t)$ reveal whether a particular subunit leads.

**(b) Permutation-invariant distance and MDS.** To compare whole-receptor configurations without being misled by the arbitrary labelling of subunits, treat each frame $i$ as the vector $\text{subIC}_i = (\text{subIC}_A,\dots,\text{subIC}_E)_i$ and define the **minimal permutation distance**

$$\boxed{D_{ij} = \min_{\pi\in C_5}\big\lVert \text{subIC}_i - \pi(\text{subIC}_j)\big\rVert_2}$$

where the minimum runs over the five cyclic relabellings $\pi$ of the subunits (optionally over the ten elements of $D_5$ if the reflection is also physically admissible). $D_{ij}$ is the natural metric on the quotient space feature-space$/C_5$: two frames that differ only by which subunit is "the leading one" are assigned distance zero, so genuinely distinct symmetry-breaking patterns are not confused with relabellings. Feeding the matrix $\{D_{ij}\}$ to **multidimensional scaling (MDS)** produces a 2-D embedding in which each point is a receptor configuration and the geometry reflects permutation-invariant differences; resting and open ensembles appear as separate regions, and intermediate clusters (e.g. "one subunit activated", "two adjacent subunits activated") become visible as distinct lobes. Colour-coding the MDS map by IC, by $\sigma$, or by the $E$-irrep amplitudes connects the embedding back to the physical modes; structures can also be visualised by mapping the dominant components of $\mathbf{v}_A$ back onto the C$\alpha$ pairs and drawing them on one subunit, then replicating by the C$_5$ operation.

## 6. Practical notes and caveats

- **Choice of $\tau$:** scan $\tau$ and verify that the implied timescales $t_i = -\tau/\ln\lambda_i$ plateau; the symmetry collapse and the five-fold data augmentation make this test much better behaved for short trajectories.
- **Conditioning:** whiten with a regularised $C_0$ (eigenvalue cutoff / shrinkage) before diagonalising $K_{\text{red}}$; distance features are strongly correlated.
- **Combining resting and open data:** pool the ensembles so that $C_\tau$ carries information about the transition region, but check the Koopman/VAMP-2 score on held-out trajectories; with no reactive trajectories the slow modes report the state-specific fluctuations that connect to the transition rather than the transition rate itself.
- **Symmetry as a prior, not a constraint on the data:** the symmetrisation $K_{\text{sum}}$ is applied to the *estimator*, while the *projections* $\text{subIC}_S$ retain full per-subunit resolution — which is precisely how a symmetry-constrained model can still quantify symmetry breaking.
- **Scope:** because only one subunit's worth of local dynamics needs to be resolved, this scheme extracts the slow single-subunit mode (and its in-phase collective counterpart) from trajectories far too short to show a complete receptor transition, which is exactly the regime described.

## Final answer

Use **TICA** on per-subunit intra-/inter-subunit C$\alpha$ distance features; estimate $C_0$ and $C_\tau = \langle\mathbf{X}_t\mathbf{X}_{t+\tau}^\top\rangle$; enforce reversibility with $C_\tau\leftarrow\frac12(C_\tau+C_\tau^\top)$ and C$_5$ equivariance with $K_{\text{sum}} = \sum_{k=0}^{4}\mathcal{R}^kK(\mathcal{R}^\top)^k$; exploit the resulting symmetric block-circulant structure of $\mathbf{K}$ (blocks $K_d$, $K_{o1}$, $K_{o2}$, $K_{o2}^\top$, $K_{o1}^\top$) to reduce $\mathbf{K}\mathbf{v}=\lambda\mathbf{v}$, via $\mathbf{v}_A = \mathbf{v}_B = \dots = \mathbf{v}_E$, to the $N\times N$ problem $(K_d+K_{o1}+K_{o2}+K_{o2}^\top+K_{o1}^\top)\mathbf{v}_A = \lambda\mathbf{v}_A$ whose symmetric mode is $\mathbf{v}_{\text{sym}}\propto\sum_S\mathbf{x}_S$; project with $\text{subIC}_S = \mathbf{v}_A^\top\mathbf{x}_S$ and $\text{IC} = \sum_S \text{subIC}_S$; and quantify/visualise asymmetry with $\sigma = \sqrt{\frac15\sum_S(\text{subIC}_S-\langle\text{subIC}\rangle)^2}$ and with MDS on $D_{ij} = \min_{\pi\in C_5}\lVert\text{subIC}_i - \pi(\text{subIC}_j)\rVert_2$.
