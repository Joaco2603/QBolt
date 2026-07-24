# Goemans-Williamson for Weighted Max-Cut

## Purpose and scope

This module solves weighted Max-Cut on finite, undirected, simple graphs with
non-negative edge weights. It returns a bipartition, the resulting cut weight,
the SDP upper bound, random-rounding metadata, and an empirical ratio only
when an exact positive optimum is supplied.

The current transmission-network weight is the summed nominal circuit voltage
in kV. It is a reproducible importance proxy, not capacity, power flow,
impedance, or failure risk.

## Discrete problem

For an undirected graph \(G=(V,E)\), a cut is a partition \(S,\bar S\). Its
weight is the sum of the weights of edges with endpoints in different parts.
With an Ising label \(s_i\in\{-1,+1\}\), let \(S=\{i:s_i=+1\}\). For edges
stored once,

\[
\operatorname{Cut}(s)=\frac{1}{2}\sum_{\{i,j\}\in E}w_{ij}(1-s_i s_j).
\]

The equivalent minimization-energy convention is
\(H(s)=-\operatorname{Cut}(s)\). The sign and constant convention must remain
explicit when comparing this baseline with QUBO or QAOA results.

## Matrix lifting and SDP relaxation

Let \(X=ss^\top\). In the discrete model, \(X\) is symmetric, positive
semidefinite, has unit diagonal, and has rank one. Dropping only the rank-one
constraint gives the Goemans-Williamson relaxation:

\[
\begin{aligned}
\max_X\quad &\frac{1}{2}\sum_{\{i,j\}\in E}w_{ij}(1-X_{ij})\\
\text{s.t.}\quad &X\succeq0,\\
&X_{ii}=1\quad\forall i.
\end{aligned}
\]

Equivalently, with the weighted Laplacian \(L\), the objective is
\(\frac14\operatorname{Tr}(LX)\). The \(\frac12\) edge-list factor and the
\(\frac14\) Laplacian factor prevent double-counting undirected edges. Every
discrete assignment remains feasible, so the SDP value is an upper bound on
the exact Max-Cut optimum.

The Ising and matrix forms are algebraically equivalent before relaxation and
lead to this same SDP. An Ising input can avoid an intermediate conversion, but
it does not change the dominant SDP solve. Any practical speed claim requires a
reproducible benchmark with the same solver, versions, tolerances, hardware,
graph, and repetitions.

## Geometric interpretation and rounding

Factor a numerically valid SDP solution as \(X=VV^\top\). Each row \(v_i\) is
a unit vector; its dot product with \(v_j\) is \(X_{ij}\), and its angle
determines the probability that random hyperplane rounding separates the two
nodes.

For every round, draw \(r\sim\mathcal N(0,I)\) from a local generator created
with the recorded seed. Assign node \(i\) to the positive partition when
\(v_i^\top r\ge0\), and to the negative partition otherwise. The inclusive
zero rule makes exact numerical ties deterministic. Run a positive number of
rounds and retain the highest-weight cut; retain the earliest round on a tie.
Canonicalize complementary partitions before returning them.

## Numerical and solver contract

- Accept only `networkx.Graph` instances with string node IDs, no self-loops,
  no parallel edges, and explicit finite non-negative `weight` values.
- Allow empty, disconnected, zero-weight, and isolated-node graphs. An empty
  graph bypasses the SDP and returns a zero cut and zero SDP value.
- Solve with CVXPY and SCS. Record solver name, solver status, solver options,
  seed, requested rounds, and winning round.
- Accept `optimal`; accept `optimal_inaccurate` only after post-solve validation.
  Raise an error for all other statuses or a missing primal matrix.
- Symmetrize the returned matrix. Reject diagonal or PSD violations above the
  documented tolerance; clip only negative eigenvalues within tolerance before
  building vectors, then normalize their rows.

## Evaluation and guarantee

Compute cut weight once per graph edge. When an exact positive optimum is
available, report

\[
\text{empirical ratio}=\frac{\operatorname{Cut}_{GW}}{\operatorname{OPT}}.
\]

For \(\operatorname{OPT}=0\), the ratio is undefined and is reported as
`None`, not as \(0/0\) or 1. The \(\alpha_{GW}\approx0.87856\) result is an
expected guarantee for one random hyperplane applied to an exact SDP solution;
it is neither a lower bound for every finite seeded run nor a claim about a
numerically approximate solver result. Selecting the best of several rounds
cannot reduce the expected or observed cut relative to its first round.

## Limitations

- SDP solving is the dominant cost and does not scale like the discrete
  rounding step.
- Rounding varies by seed; numerical solutions vary by solver and tolerance.
- The classical guarantee assumes non-negative weights and an exact SDP
  solution.
- The network weights are voltage proxies and must not be interpreted as
  electrical-flow or resilience quantities.

## References

- M. X. Goemans and D. P. Williamson, *Improved Approximation Algorithms for
  Maximum Cut and Satisfiability Problems Using Semidefinite Programming*,
  JACM 42(6), 1995.
- H. Karloff, *How Good is the Goemans--Williamson MAX CUT Algorithm?*,
  SIAM Journal on Computing 29(1), 1999.
