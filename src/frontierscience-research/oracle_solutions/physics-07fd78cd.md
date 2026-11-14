# Probabilistic exact inversion of an unknown unitary via singlet-state teleportation

## Idea

We want to output $U^\dagger|\psi\rangle$ while only being allowed to *apply* the unknown $U$. The trick is to apply $U$ not to $|\psi\rangle$ but to one half of a maximally entangled, "singlet-type" state of two qudits. Acting with $U$ on one half of the singlet is equivalent to acting with $U^\dagger$ on the other half. We then teleport $|\psi\rangle$ onto that other half. Of the $d^2$ possible teleportation outcomes, only one (the singlet outcome) needs no Pauli-type correction. The protocol keeps only that outcome, so when it succeeds the output is exactly $U^\dagger|\psi\rangle$.

Notation: $C$ is the register that holds the input $|\psi\rangle$; $A$ and $B$ are the two qudits of the resource state; all are $d$-dimensional with computational basis $\{|0\rangle,\dots,|d-1\rangle\}$.

---

## 1. Preparation

### The $d$-dimensional singlet

The resource is the generalisation of the two-qubit Bell singlet to two qudits:
$$
\boxed{\;|{\cal S}_2^{(d)}\rangle_{AB}=\frac{1}{\sqrt d}\sum_{i=0}^{d-1}(-1)^i\,|i\rangle_A\otimes|d-i-1\rangle_B\;}
$$
For $d=2$ this is $(|01\rangle-|10\rangle)/\sqrt2$. It is maximally entangled: both reduced states are $I/d$.

### Overall initial state

The input state $|\psi\rangle=\sum_{k=0}^{d-1}c_k|k\rangle$ is prepared in a separate register $C$, not inside the singlet pair, because we will later move it onto qudit $B$ with a teleportation-like step:
$$
\boxed{\;|\Psi_{\rm init}\rangle_{CAB}=|\psi\rangle_C\otimes|{\cal S}_2^{(d)}\rangle_{AB}
=\frac{1}{\sqrt d}\sum_{k,i=0}^{d-1}c_k(-1)^i\,|k\rangle_C|i\rangle_A|d-i-1\rangle_B .\;}
$$

### Why the singlet: the invariance property

The protocol relies on the following invariance property of the singlet:
$$
\boxed{\;(U\otimes I)\,|{\cal S}_2^{(d)}\rangle_{AB}=(I\otimes U^\dagger)\,|{\cal S}_2^{(d)}\rangle_{AB}\;}
$$
(up to an irrelevant global phase). This is the singlet version of the "transpose trick" for maximally entangled states, $(U\otimes I)|\Phi\rangle=(I\otimes U^{T})|\Phi\rangle$. For the singlet the operator transferred to the other side is the inverse $U^\dagger$; for qubits this is the familiar statement that the singlet is invariant under $U\otimes U$ up to the phase $\det U$. Applying the unknown $U$ to qudit $A$ is therefore the same as applying the desired $U^\dagger$ to qudit $B$, with no knowledge of $U$ needed.

---

## 2. Intermediate evolution ($U$-dependent step)

Apply the unknown unitary **once**, to qudit $A$ of the singlet, and do nothing to qudit $B$ or to $C$:
$$
|\Psi\rangle_{CAB}=(I_C\otimes U_A\otimes I_B)\,|\Psi_{\rm init}\rangle_{CAB}
=|\psi\rangle_C\otimes(U\otimes I)|{\cal S}_2^{(d)}\rangle_{AB}.
$$
Using the invariance property, $(U\otimes I)|{\cal S}_2^{(d)}\rangle_{AB}=(I\otimes U^\dagger)|{\cal S}_2^{(d)}\rangle_{AB}$, so the transformed state can be written in terms of $U^\dagger$ acting on $B$:
$$
\boxed{\;|\Psi\rangle_{CAB}=\frac{1}{\sqrt d}\sum_{k,i=0}^{d-1}c_k(-1)^i\,|k\rangle_C\otimes|i\rangle_A\otimes U^\dagger|d-i-1\rangle_B .\;}
$$

### Relabelled form

To prepare for the measurement, relabel the summation index of the singlet,
$$
|{\cal S}_2^{(d)}\rangle_{AB}=\frac{1}{\sqrt d}\sum_{i=0}^{d-1}(-1)^i|i\rangle_A\otimes|d-i-1\rangle_B ,
\qquad j\equiv d-i-1\;\;\Longleftrightarrow\;\; i=d-j-1 .
$$
Then $(-1)^i=(-1)^{d-1}(-1)^{-j}=(-1)^{d-1}(-1)^{j}$, and $(-1)^{d-1}$ is a global phase. Hence, up to a global phase,
$$
\boxed{\;|\Psi\rangle_{CAB}=\frac{1}{\sqrt d}\sum_{k,j=0}^{d-1}c_k(-1)^j\,|k\rangle_C\otimes|d-j-1\rangle_A\otimes U^\dagger|j\rangle_B .\;}
$$

---

## 3. Measurement

Perform a **joint singlet (generalised Bell) measurement on $C$ and $A$**, that is, on the register initially holding $|\psi\rangle$ and on the qudit of the singlet to which $U$ was applied. The success element is the projector onto
$$
\boxed{\;|{\cal S}_2^{(d)}\rangle_{CA}=\frac{1}{\sqrt d}\sum_{k=0}^{d-1}(-1)^k\,|k\rangle_C\otimes|d-k-1\rangle_A ,\qquad
P_{{\cal S}_2^{(d)}}=|{\cal S}_2^{(d)}\rangle\langle{\cal S}_2^{(d)}|_{CA}.\;}
$$
The full measurement basis is the $d^2$-element generalised Bell basis of $CA$,
$$
|{\cal S}_{mn}\rangle_{CA}=(X^mZ^n\otimes I)\,|{\cal S}_2^{(d)}\rangle_{CA},\qquad m,n=0,\dots,d-1,
$$
with $X|k\rangle=|k+1 \bmod d\rangle$, $Z|k\rangle=e^{2\pi ik/d}|k\rangle$, and $|{\cal S}_{00}\rangle=|{\cal S}_2^{(d)}\rangle$. Equivalently, the coarse-grained two-outcome POVM $\{P_{{\cal S}_2^{(d)}},\,I-P_{{\cal S}_2^{(d)}}\}$ suffices.

### Action of the measurement: teleportation onto $B$

The action of the successful outcome on the state is $(P_{{\cal S}_2^{(d)}}\otimes I_B)|\Psi\rangle_{CAB}$. Using the relabelled form,
$$
\begin{aligned}
(P_{{\cal S}_2^{(d)}}\otimes I_B)|\Psi\rangle_{CAB}
&=|{\cal S}_2^{(d)}\rangle_{CA}\otimes\Big(\langle{\cal S}_2^{(d)}|_{CA}\otimes I_B\Big)|\Psi\rangle_{CAB}\\
&=|{\cal S}_2^{(d)}\rangle_{CA}\otimes\frac{1}{d}\sum_{l,k,j}(-1)^l c_k(-1)^j\,
\langle l|k\rangle_C\,\langle d-l-1|d-j-1\rangle_A\;U^\dagger|j\rangle_B\\
&=|{\cal S}_2^{(d)}\rangle_{CA}\otimes\frac{1}{d}\sum_{k}(-1)^{2k}c_k\,U^\dagger|k\rangle_B ,
\end{aligned}
$$
because $\langle l|k\rangle=\delta_{lk}$ and $\langle d-l-1|d-j-1\rangle=\delta_{lj}$ force $l=k=j$. Therefore
$$
\boxed{\;(P_{{\cal S}_2^{(d)}}\otimes I_B)|\Psi\rangle_{CAB}\;\propto\;|{\cal S}_2^{(d)}\rangle_{CA}\otimes U^\dagger\sum_{k=0}^{d-1}c_k|k\rangle_B=|{\cal S}_2^{(d)}\rangle_{CA}\otimes U^\dagger|\psi\rangle_B .\;}
$$
So $|\psi\rangle$ has been teleported onto qudit $B$, the qudit of the singlet on which $U$ was **not** applied, and which therefore effectively evolved under $U^\dagger$. The output is exactly $U^\dagger|\psi\rangle$, with no dependence on the unknown $U$ beyond the desired inverse.

### Success probability

The norm of the projected vector gives the probability:
$$
p_{\rm succ}=\big\|(P_{{\cal S}_2^{(d)}}\otimes I_B)|\Psi\rangle\big\|^2=\frac{1}{d^2}\,\big\|U^\dagger|\psi\rangle\big\|^2=\frac{1}{d^2}.
$$
This has a simple interpretation. The protocol succeeds exactly when the final state of $CA$ is found in the singlet. Because the reduced state of $A$ is maximally mixed and $C$ is in a pure state, all $d^2$ generalised Bell states of $CA$ occur with equal probability $1/d^2$, independent of $|\psi\rangle$ and $U$. Hence
$$
\boxed{\;p_{\rm succ}=\frac{1}{d^2}.\;}
$$
For any other outcome $(m,n)\neq(0,0)$, qudit $B$ is left in $U^\dagger\,\tilde W_{mn}|\psi\rangle$ for some generalised Pauli $\tilde W_{mn}$. Since $U$ is unknown, $\tilde W_{mn}$ cannot in general be commuted through $U^\dagger$ and undone, so these runs are declared failures.

---

## 4. Post-processing and resource count

1. **Heralding.** Read the outcome of the $CA$ measurement. If it is the singlet ($m=n=0$), output qudit $B$, which is exactly $U^\dagger|\psi\rangle$. No correction is needed.
2. **Failure.** Otherwise discard $B$, prepare a fresh singlet on $A B$ and a fresh copy of $|\psi\rangle$ on $C$, and repeat steps 1 to 3.
3. **Cost.** Each attempt uses exactly one application of $U$ and succeeds independently with probability $1/d^2$. The number of attempts $N$ is geometrically distributed, $\Pr(N=n)=(1-d^{-2})^{n-1}d^{-2}$, so
$$
\boxed{\;\langle N_U\rangle=\frac{1}{p_{\rm succ}}=d^2\ \text{applications of }U\text{ on average.}\;}
$$
This matches the $\mathcal O(d^2)$ scaling of tomography and unitary-reversal algorithms. The difference is that the output here is **exact**, with no tomographic or approximation error, and is heralded.

### Summary of the protocol
- **Input state:** $|\psi\rangle_C\otimes|{\cal S}_2^{(d)}\rangle_{AB}$, with the $d$-dimensional singlet $|{\cal S}_2^{(d)}\rangle=\frac1{\sqrt d}\sum_i(-1)^i|i\rangle|d-i-1\rangle$.
- **Evolution:** $U$ on qudit $A$ only, $(U\otimes I)|{\cal S}_2^{(d)}\rangle_{AB}=(I\otimes U^\dagger)|{\cal S}_2^{(d)}\rangle_{AB}$.
- **Measurement:** generalised Bell (singlet) measurement on $CA$, with success projector $P_{{\cal S}_2^{(d)}}=|{\cal S}_2^{(d)}\rangle\langle{\cal S}_2^{(d)}|_{CA}$.
- **Post-processing:** keep $B$ on the singlet outcome (probability $1/d^2$) to obtain $U^\dagger|\psi\rangle$ exactly; otherwise repeat. On average $d^2$ uses of $U$.
