# How one pre- and post-selected shutter closes $N$ slits, and how $K$ shutters stop $K$ photons

**Setting.** A screen has $N$ slits. A single shutter can be localized in slit $i$, with state $|i\rangle$ for $i=1,\dots,N$, where it acts as a perfect mirror for that slit. It can also be localized at some specific different location, with state $|N+1\rangle$, where it blocks nothing. The shutter is pre-selected at time $t_1$, a photon passes the screen at time $t$ ($t_1<t<t_2$), and the shutter is post-selected at $t_2$. Between these times the shutter has no free evolution. The shutter is massive, and its localized states are taken to be unchanged by the reflection: the photon's momentum kick is much smaller than the shutter's momentum uncertainty, so there is no measurable recoil. This is essential, because a recoil would record which slit reflected the photon and destroy the coherence of the reflected wave.

---

## One-photon case

### 1. Pre- and post-selected states of the shutter
The shutter is pre-selected at $t_1$ in
$$
\boxed{|\Psi_1\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-1}\,|N+1\rangle\right)}
$$
and post-selected at the final time $t_2$ in
$$
\boxed{|\Psi_2\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-1}\,|N+1\rangle\right)}
$$
where $|i\rangle$ is a state of the shutter localized in slit $i$, $i=1,\dots,N$, and $|N+1\rangle$ is a state of the shutter localized in some specific different location. Both states are normalized, since $\frac{N+(N-1)}{2N-1}=1$. Their overlap is $\langle\Psi_2|\Psi_1\rangle=\frac{N-(N-1)}{2N-1}=\frac{1}{2N-1}\neq0$.

These states make the weak value (ABL value) of every slit projector $\Pi_i=|i\rangle\langle i|$ equal to one:
$$
\langle\Pi_i\rangle_w=\frac{\langle\Psi_2|\Pi_i|\Psi_1\rangle}{\langle\Psi_2|\Psi_1\rangle}=\frac{1/(2N-1)}{1/(2N-1)}=1\quad(i=1,\dots,N),\qquad \langle\Pi_{N+1}\rangle_w=-(N-1).
$$
Moreover, $|\Psi_2\rangle$ is orthogonal to $\sum_{i\neq j}|i\rangle+\sqrt{N-1}|N+1\rangle$, the projection of $|\Psi_1\rangle$ onto "not in slit $j$". Hence, if the shutter is probed in any one slit $j$ (as the photon does), it is found there with certainty. In this sense the single shutter is effectively present in all $N$ slits at once.

### 2. Initial photon state and the joint state at time $t$
The photon moving toward the $N$ slits is in
$$
\boxed{|\Psi_{\rm in}\rangle_{\rm ph}=\sum_{i=1}^{N}\alpha_i\,|i\rangle_{\rm ph}},\qquad\sum_i|\alpha_i|^2=1,
$$
where $|i\rangle_{\rm ph}$ is the state of a photon moving toward slit $i$. The initial product state is
$$
|\Psi_1\rangle|\Psi_{\rm in}\rangle_{\rm ph}=\frac{1}{\sqrt{2N-1}}\sum_{j=1}^{N}\alpha_j\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-1}|N+1\rangle\right)|j\rangle_{\rm ph}.
$$
**Interaction at time $t$.** If the shutter is in slit $j$ (term $i=j$), the photon component at slit $j$ is reflected, $|j\rangle_{\rm ph}\to|\tilde j\rangle_{\rm ph}$. If the shutter is elsewhere ($i\neq j$, or $N+1$), that component passes and continues as $|j\rangle_{\rm ph}$ (transmitted). Collecting terms, the joint state of the shutter and the photon after the interaction at time $t$ is the superposition of a reflected part (first line) and a transmitted part (second line):
$$
\boxed{\begin{aligned}
|\Psi\rangle_{s,{\rm ph}}=\;&\frac{1}{\sqrt{2N-1}}\sum_{i=1}^{N}\alpha_i\,|i\rangle|\tilde i\rangle_{\rm ph}\\
&\frac{1}{\sqrt{2N-1}}\sum_{j=1}^{N}\alpha_j\left(\sum_{i\neq j}|i\rangle+\sqrt{N-1}\,|N+1\rangle\right)|j\rangle_{\rm ph}
\end{aligned}}
$$
The first sum contains the reflected components and the second the transmitted ones.

### 3. Post-selection: the screen acts as a perfect mirror
Project the shutter onto $|\Psi_2\rangle$ at $t_2$.
* Reflected terms: $\langle\Psi_2|i\rangle=\frac{1}{\sqrt{2N-1}}$ for every $i$.
* Transmitted terms:
$$
\langle\Psi_2|\left(\sum_{i\neq j}|i\rangle+\sqrt{N-1}|N+1\rangle\right)=\frac{1}{\sqrt{2N-1}}\big[(N-1)-(N-1)\big]=0\qquad\text{for every } j .
$$
Hence
$$
\langle\Psi_2|\Psi\rangle_{s,{\rm ph}}=\frac{1}{2N-1}\sum_{i=1}^{N}\alpha_i|\tilde i\rangle_{\rm ph},
$$
and the normalized final state of the photon is
$$
\boxed{|\Psi_{\rm fin}\rangle_{\rm ph}=\sum_{i=1}^{N}\alpha_i\,|\tilde i\rangle_{\rm ph}}
$$
**After the post-selection the photon state has only reflected wave components.** The transmitted components vanish because **all the states of the shutter that accompany a transmitted photon are orthogonal to the post-selected state $|\Psi_2\rangle$**. Every amplitude $\alpha_i$ and every relative phase is preserved, so for any initial photon state the screen operates as a **perfect mirror**: all $N$ slits are closed simultaneously by one shutter. The price is the post-selection probability, $\|\langle\Psi_2|\Psi\rangle\|^2=1/(2N-1)^2$.

---

## Dual problem: $N$ shutters that let the photon through all $N$ slits

Now each slit $i$ has its own shutter, with states $|{\rm op}\rangle_i$ (slit $i$ open) and $|{\rm cl}\rangle_i$ (slit $i$ closed). The pre-selected state of the $N$ shutters at $t_1$ is
$$
\boxed{|\Phi_1\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|{\rm op}\rangle_i\prod_{j\neq i}|{\rm cl}\rangle_j+\sqrt{N-1}\prod_{j=1}^{N}|{\rm cl}\rangle_j\right)}
$$
where $|{\rm op}\rangle_i$ and $|{\rm cl}\rangle_i$ are the states of the shutter corresponding to an open or closed slit $i$. In every term **at least $N-1$ of the $N$ slits are closed**. The post-selected state at the final time $t_2$ is
$$
\boxed{|\Phi_2\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|{\rm op}\rangle_i\prod_{j\neq i}|{\rm cl}\rangle_j-\sqrt{N-1}\prod_{j=1}^{N}|{\rm cl}\rangle_j\right)}
$$
This is the one-shutter construction with the dictionary $|i\rangle\leftrightarrow$ "only slit $i$ open" and $|N+1\rangle\leftrightarrow$ "all slits closed".

**The photon passes undistorted.** A photon at slit $k$ is transmitted only if shutter $k$ is open, and is reflected otherwise. After the interaction,
$$
|\Phi\rangle_{s,{\rm ph}}=\frac{1}{\sqrt{2N-1}}\sum_{k=1}^{N}\alpha_k\left[|{\rm op}\rangle_k\prod_{j\neq k}|{\rm cl}\rangle_j\;|k\rangle_{\rm ph}+\left(\sum_{i\neq k}|{\rm op}\rangle_i\prod_{j\neq i}|{\rm cl}\rangle_j+\sqrt{N-1}\prod_{j}|{\rm cl}\rangle_j\right)|\tilde k\rangle_{\rm ph}\right].
$$
A calculation identical to the one above gives the post-selected overlaps:
* transmitted terms: $\langle\Phi_2|{\rm op}_k,\text{rest cl}\rangle=\frac{1}{\sqrt{2N-1}}$;
* reflected terms: $\frac{1}{\sqrt{2N-1}}\big[(N-1)-(N-1)\big]=0$.

Therefore
$$
\langle\Phi_2|\Phi\rangle_{s,{\rm ph}}=\frac{1}{2N-1}\sum_{k}\alpha_k|k\rangle_{\rm ph}\;\Longrightarrow\;|\Psi_{\rm fin}\rangle_{\rm ph}=\sum_k\alpha_k|k\rangle_{\rm ph}.
$$
The single photon passes the slits **without distortion, as if no shutters were present**, even though at least $N-1$ of the $N$ slits were closed in every component of the pre-selected state.

---

## Generalization to $K$ photons

A single shutter $|\Psi_1\rangle,|\Psi_2\rangle$ removes only the component in which **one** photon passes, because only the transmitted shutter states with one slit excluded are orthogonal to $|\Psi_2\rangle$. Suppose two photons pass through two different slits $j\neq k$ unreflected. The shutter state is then $\sum_{i\neq j,k}|i\rangle+\sqrt{N-1}|N+1\rangle$, and its overlap with $|\Psi_2\rangle$ is $\propto(N-2)-(N-1)=-1\neq0$. A single shutter therefore does **not** stop two photons, and more shutters are needed.

### $K=2$
To close $N$ slits for a pair of photons we need **two** pre- and post-selected shutters placed one after the other. The first shutter (the one the photons meet first) is pre-selected at $t_1$ in
$$
\boxed{|\Psi'_1\rangle=\frac{1}{\sqrt{2N-2}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-2}\,|N+1\rangle\right)}
$$
and post-selected at $t_2$ in
$$
\boxed{|\Psi'_2\rangle=\frac{1}{\sqrt{2N-2}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-2}\,|N+1\rangle\right)}
$$
(normalization: $\frac{N+N-2}{2N-2}=1$). If the two photons pass through two **different** slits $j\neq k$ without disturbance, the state of this shutter is $\sum_{i\neq j,k}|i\rangle+\sqrt{N-2}|N+1\rangle$. This is **orthogonal to $|\Psi'_2\rangle$**, since $(N-2)-(N-2)=0$. Therefore, given a successful post-selection, one photon must have been reflected by the first shutter. The remaining (at most one) photon then meets the second shutter, which is pre- and post-selected exactly as in the one-photon example:
$$
\boxed{|\Psi_1\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-1}\,|N+1\rangle\right),\qquad
|\Psi_2\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-1}\,|N+1\rangle\right)}
$$
It reflects any single photon with certainty. If both photons arrive at the **same** slit $j$, the first shutter may let them through, since the overlap is $\propto(N-1)-(N-2)\neq0$. The second shutter then sees one occupied slit, so a successful post-selection requires it to be in slit $j$, where it reflects both photons. In every post-selected outcome both photons are reflected.

### $K=3$
To stop three photons we add another shutter in front of the two described above. It must reflect one photon whenever three photons arrive at three different slits. It is pre- and post-selected in $|\Psi''_1\rangle$ and $|\Psi''_2\rangle$:
$$
\boxed{|\Psi''_1\rangle=\frac{1}{\sqrt{2N-3}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-3}\,|N+1\rangle\right),\qquad
|\Psi''_2\rangle=\frac{1}{\sqrt{2N-3}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-3}\,|N+1\rangle\right)}
$$
If three photons pass slits $j,k,l$ (all different) unreflected, this shutter is left in $\sum_{i\neq j,k,l}|i\rangle+\sqrt{N-3}|N+1\rangle$, which is orthogonal to $|\Psi''_2\rangle$ because $(N-3)-(N-3)=0$. So at least one photon is reflected. Similarly, the second shutter is given by the previous expressions for two photons:
$$
\boxed{|\Psi'_1\rangle=\frac{1}{\sqrt{2N-2}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-2}\,|N+1\rangle\right),\qquad
|\Psi'_2\rangle=\frac{1}{\sqrt{2N-2}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-2}\,|N+1\rangle\right)}
$$
and the third shutter is
$$
\boxed{|\Psi_1\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-1}\,|N+1\rangle\right),\qquad
|\Psi_2\rangle=\frac{1}{\sqrt{2N-1}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-1}\,|N+1\rangle\right)}
$$

### General $K$ (with $K\le N$)
The pattern is now clear. The **$K$-th shutter** (the one designed for $K$ photons) is pre- and post-selected in
$$
\boxed{|\Psi_1^K\rangle=\frac{1}{\sqrt{2N-K}}\left(\sum_{i=1}^{N}|i\rangle+\sqrt{N-K}\,|N+1\rangle\right)}
$$
$$
\boxed{|\Psi_2^K\rangle=\frac{1}{\sqrt{2N-K}}\left(\sum_{i=1}^{N}|i\rangle-\sqrt{N-K}\,|N+1\rangle\right)}
$$
These are normalized because $\frac{N+(N-K)}{2N-K}=1$. The $K=1,2,3$ cases above are $|\Psi^1\rangle\equiv|\Psi\rangle$, $|\Psi^2\rangle\equiv|\Psi'\rangle$ and $|\Psi^3\rangle\equiv|\Psi''\rangle$.

**Key property.** If $K$ photons pass through $K$ different slits $S=\{i_1,\dots,i_K\}$ unreflected, shutter $K$ is left in $\sum_{i\notin S}|i\rangle+\sqrt{N-K}|N+1\rangle$. Then
$$
\langle\Psi_2^K|\Big(\sum_{i\notin S}|i\rangle+\sqrt{N-K}|N+1\rangle\Big)=\frac{(N-K)-(N-K)}{\sqrt{2N-K}}=0 ,
$$
so a successful post-selection guarantees that shutter $K$ reflected at least one photon. A shutter in slit $i$ reflects every photon in that slit.

**How $K$ shutters stop $K$ photons.** Place the shutters one after the other in the order $K, K-1,\dots,1$ along the photons' path. Let $d$ be the number of distinct slits occupied by the photons still travelling. Initially $d\le K$. When the photons reach shutter $k$ with $d\le k$:
* if $d=k$, post-selection forces shutter $k$ to reflect the photons in at least one slit, so afterwards $d\le k-1$;
* if $d<k$, then trivially $d\le k-1$ afterwards.

By induction, $d\le0$ after shutter 1. **Given successful post-selection of all $K$ shutters, all $K$ photons are reflected, whatever their joint state.** Each pre- and post-selected shutter closes all $N$ slits for one photon, and a set of $K$ such shutters prevents the passage of $K$ photons. As in the single-photon case, the reflected multi-photon amplitudes are preserved, so the screen again acts as a mirror, at the cost of a post-selection probability that decreases with $N$ and $K$.
