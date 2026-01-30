# User prompt

I am a PhD student working on precision simulations for top-quark processes at colliders.
I currently have a baseline leading-order, on-shell simulation for a given process and observable.

Your task is to critically assess the limitations of such a setup and propose systematic and conceptually distinct ways to improve its theoretical precision.

For each proposed improvement:
- Explain which physical effects are being captured that are missing at baseline level.
- Clarify when and why this improvement becomes important for realistic analyses.
- Indicate, at a high level, how such an improvement is typically implemented in modern Monte-Carlo simulations.

Do not assume a specific generator or workflow unless needed.
Reason from first principles and standard practice in collider phenomenology.

The goal is to identify the dominant axes along which precision is improved, not to enumerate tools.

----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# MadAgents response

Let me view your LO, on-shell setup as the leading term in several expansions:

- perturbative QCD: truncation at the lowest non-zero power of $\alpha_s$;
- electroweak: neglect of $\mathcal{O}(\alpha)$ and mixed QCD–EW terms;
- finite-width/off-shell: expansion in $\Gamma_t/m_t$ (narrow-width, factorised production and decay);
- logarithms of scale ratios: only leading-log (LL) resummation via a basic parton shower, if any;
- power corrections $\sim \Lambda_{\text{QCD}}/Q$: modelled non-perturbatively, if at all.

I’ll organise the main precision-improvement directions along these axes. For each: what new physics you capture, when it matters, and how it is implemented in modern (generator-agnostic) Monte Carlo.

I will implicitly assume a *parton-shower–based* LO baseline where relevant, but the axes are the same if you start from a strictly parton-level LO prediction.

---
## 1. Higher-order QCD in production and decay (NLO, NNLO, NLO+PS)

### Physics added
At LO, for a given top process,
$$
\sigma_{\text{LO}} \sim \alpha_{s}^{n} \, \sigma^{(0)}.
$$
Including higher orders gives
$$
\sigma = \alpha_{s}^{n} \sigma^{(0)} + \alpha_{s}^{n+1} \sigma^{(1)} + \alpha_{s}^{n+2} \sigma^{(2)} + \cdots,
$$
where $\sigma^{(1)}$ (NLO) and $\sigma^{(2)}$ (NNLO) contain:

- virtual loop corrections (new colour structures, scale logs, interference);
- real-emission channels (e.g. explicit $t\bar{t}+$jet topologies at NLO);
- new initial states (e.g. $qg$ first entering for $t\bar{t}$ at NLO);
- in decay: gluon emission and virtual corrections in $t\to Wb$, affecting partial widths and decay kinematics.

### When it matters
- Inclusive $t\bar t$ and single-top rates: LO can be off by $\mathcal{O}(30\%)$; NLO/NNLO reduce this to a few percent with smaller scale variation.
- Differential shapes: K-factors are not flat; high-$p_{T}^{t}$, large $M_{t\bar{t}}$, or forward regions are often badly modelled at LO.
- Precision extractions (top mass, couplings, EFT coefficients): theory systematics from missing QCD orders become limiting unless you are at least NLO-accurate in the relevant observables.

### Implementation (high level)
- Fixed-order NLO/NNLO matrix elements with subtraction for IR safety.
- NLO+PS matching: construct an event generator where the total rate and the distribution of the hardest emission (in the shower ordering variable) are NLO-accurate for the core process, while the shower resums soft/collinear radiation.
- NLO in decay: treat tops as unstable, including NLO-corrected decay kernels and radiation in the decay, consistently combined with NLO production and preserving spin correlations.
- NNLO information: used either as standalone predictions or via reweighting / dedicated NNLO+PS frameworks in specific channels.

---
## 2. Hard additional jets: multi-jet matrix elements and merging

### Physics added
A pure LO core process plus shower generates extra jets only via the shower’s soft/collinear approximation. Including explicit matrix elements for $t\bar{t}$ + 1 jet, 2 jets, … adds:

- exact tree-level kinematics and colour factors for multiple hard partons;
- correct angular correlations and energy sharing among well-separated jets;
- at NLO for $t\bar{t}+$jet: loop corrections and stabilised scale dependence in the 1-jet bin.

### When it matters
- Analyses with jet multiplicity or jet kinematics in the selection (e.g. $t\bar{t}$+jets as background).
- High-$p_{T}$ regimes where additional jets are not parametrically soft/collinear.
- Jet-bin–based measurements (0/1/2-jet categories, jet vetoes) where the interplay of hard and soft jets controls acceptance.

### Implementation (high level)
- LO multi-jet merging: generate samples with $N=0,1,2,\dots$ partons at matrix-element level, define a merging scale, use matrix elements for emissions above that scale and the shower below; employ Sudakov factors and phase-space partitioning to avoid double counting.
- NLO multi-jet merging: same idea, but with NLO-accurate matrix elements for some multiplicities (e.g. $t\bar t$ and $t\bar{t}+$1 jet), giving NLO accuracy in multiple jet bins in a single, fully exclusive sample.

This axis is conceptually distinct from “just go to NLO for $t\bar t$”: it upgrades the description of *final states with additional hard jets*.

---
## 3. Finite-width, off-shell, and full resonance structure

### Physics added
A typical LO on-shell or narrow-width approximation (NWA) treatment factorises production and decay:
$$
\sigma(pp\to t\bar{t} \to W^{+}b \, W^{-}\bar{b})\approx \sigma(pp\to t\bar{t})\,\text{BR}(t\to Wb)^2.
$$
Even if spin correlations can be included at LO within NWA, this setup neglects:

- finite-width effects (Breit–Wigner mass distributions for tops, distorted near-threshold behaviour);
- non-resonant diagrams ($WWb\bar b$ without two on-shell tops);
- interference between doubly-resonant, singly-resonant, and non-resonant contributions;
- gauge-invariant treatment of the full decay chain over all of phase space.

### When it matters
- Observables involving reconstructed invariant masses or near kinematic edges (e.g. in top-width or off-shell measurements).
- Regions where non-resonant or singly-resonant topologies are enhanced (e.g. $tW$ vs $t\bar{t}$ interference).
- Precision extractions of $m_{t}$ and $\Gamma_{t}$ from differential shapes where $\mathcal{O}(\Gamma_{t}/m_{t})$ corrections are not negligible.

### Implementation (high level)
- Full off-shell matrix elements: simulate the complete final state (e.g. $pp\to W^{+}b \, W^{-} \bar b$ with specified $W$ decays) including all resonant and non-resonant diagrams at LO or NLO, often via complex-mass schemes.
- Resonance-aware NLO+PS: match these off-shell amplitudes to a shower in a way that preserves resonance line shapes and assigns radiation consistently to production or decay.
- Spin-correlated decays: generate decays from the full matrix element, or use spin-density-matrix methods to retain exact spin correlations beyond simple NWA approximations.

This systematically improves the expansion in $\Gamma_{t}/m_{t}$ and enforces gauge invariance for the full resonance structure.

---
## 4. Electroweak corrections and photon radiation

### Physics added
Baseline LO QCD simulations usually omit $\mathcal{O}(\alpha)$ and mixed QCD–EW terms. Adding EW effects includes:

- virtual EW loops (from $W$, $Z$, $\gamma$, Higgs), generating EW Sudakov logarithms $\sim \alpha \log^{2}(Q^{2}/M_{W}^{2})$;
- real photon emission: FSR from charged leptons and $b$-jets, ISR photons, and photon-initiated partonic channels;
- modified angular distributions and interferences from EW–QCD interplay.

### When it matters
- High-$p_{T}$ or high-mass tails ($Q \gg M_{W}$): negative EW Sudakov corrections can reach $\mathcal{O}(10\%)$ or more, comparable to residual QCD scale uncertainties.
- Leptonic observables: photon radiation distorts lepton $p_{T}$, invariant masses, and missing-energy distributions used in top analyses and mass measurements.
- Few-percent–level comparisons to data in differential distributions: missing EW corrections become a clear, systematic bias.

### Implementation (high level)
- Fixed-order NLO EW matrix elements combined with appropriate PDFs (including photon PDFs when needed).
- Combination of NLO QCD and NLO EW, often via additive or multiplicative prescriptions, arranged to avoid double counting.
- QED/EW parton showers: include photon radiation (and possibly $W/Z$ emissions in specialised contexts) so that multiple photon emissions and collinear logs are resummed.

This axis systematically improves the expansion in $\alpha$ and mixed QCD–EW terms, orthogonal to pure QCD corrections.

---
## 5. Logarithmic resummation and improved shower accuracy

### Physics added
Even at NNLO, perturbation theory can be spoiled by large logarithms when observables probe hierarchical scales, e.g. $L=\log(Q/p_T)$, $\log(1-z)$ near threshold. A standard LL shower resums only leading towers $\alpha_s^n L^{2n}$ for some observables.

Improving resummation (analytically or via more accurate showers) captures:

- higher-logarithmic accuracy (NLL, NNLL, …) for observables sensitive to multiple soft/collinear emissions: small $p_T$ of the $t\bar t$ system, jet vetoes, threshold regions;
- more accurate multi-emission patterns, colour coherence, and recoil, affecting jet shapes and substructure.

### When it matters
- Jet-veto or beam-thrust–like observables, $p_T^{t\bar t}$ at small values, or near-threshold regions where $L$ is large.
- Precision differential predictions where fixed-order convergence is poor and LL showers are not sufficient.

### Implementation (high level)
- Analytical resummation (e.g. NLL/NNLL) in a factorisation framework, matched to NLO/NNLO fixed order; used either directly for specific observables or via reweighting event samples.
- Improved parton showers designed to reproduce known resummed results at NLL (or better) for key observables by suitable choices of evolution variable, splitting kernels, and recoil schemes.

This axis improves the treatment of logarithmically enhanced terms $\alpha_s^n L^m$ on top of fixed-order corrections.

---
## 6. Non-perturbative effects, colour reconnection, PDFs and mass schemes

### Physics added
A purely perturbative, on-shell LO description cannot address:

- hadronisation: formation of $B$ hadrons from $b$ quarks, affecting jet fragmentation patterns and secondary vertices;
- underlying event / multi-parton interactions: additional semi-soft activity influencing jet energies, isolation, and $E_T^{\text{miss}}$;
- colour reconnection: rearrangement of colour flow between top decay products and the rest of the event, impacting reconstructed top-mass observables.

In addition, there are **parametric and scheme** aspects of the hard process:

- PDFs and $\alpha_s$: higher-order-accurate PDFs (NLO/NNLO) with associated $\alpha_s$ running, and their uncertainties, especially at large $x$ relevant for high-$M_{t\bar{t}}$ tails;
- mass schemes: relation between the Monte-Carlo mass parameter and field-theory masses (pole, short-distance masses), which matters for precision top-mass interpretations.

### When it matters
- Any comparison to data with hadronic final states: non-perturbative effects are typically at the few-percent level for many observables, but can induce $\mathcal{O}(1\,\text{GeV})$ shifts in mass-sensitive quantities. The actual size is analysis-dependent and is assessed by varying tunes and models.
- High-x or extreme kinematics: PDF uncertainties can dominate over residual scale uncertainties in some top observables.
- Precise interpretation of the “measured” top mass: understanding how the MC mass parameter relates to a field-theoretic mass requires controlling colour reconnection and hadronisation models.

### Implementation (high level)
- Hadronisation, underlying-event, and colour-reconnection models (string/cluster, MPI, CR), tuned to LEP/Tevatron/LHC data; systematic variations of tunes and models to estimate associated uncertainties.
- Consistent use of NLO/NNLO PDFs and $\alpha_s$ when using higher-order matrix elements; explicit propagation of PDF and $\alpha_s$ errors into top observables.
- Use of short-distance mass schemes in fixed-order predictions where appropriate, and careful comparisons to MC-based templates when extracting a “top mass” from data.

This axis controls power corrections $\sim \Lambda_{\text{QCD}}/Q$ and parametric/scheme systematics, complementary to purely perturbative QCD/EW improvements.

---
## Summary: dominant, conceptually distinct precision axes

Starting from an LO, on-shell baseline for top-quark processes, the main, orthogonal ways to systematically improve theoretical precision are:

1. **Perturbative QCD order in production and decay**: NLO/NNLO fixed order, NLO+PS, NNLO+resummation.
2. **Description of additional hard jets**: multi-jet matrix elements and LO/NLO merging.
3. **Finite-width and off-shell dynamics**: full resonance structure, non-resonant diagrams, and interference beyond the NWA.
4. **Electroweak and QED effects**: NLO EW corrections and photon radiation, especially important in high-scale and leptonic observables.
5. **All-order logarithmic structure**: higher-log resummation and more accurate parton showers for observables with strong scale hierarchies.
6. **Non-perturbative, PDF, and scheme systematics**: hadronisation, UE, colour reconnection, PDFs and $\alpha_s$, and mass schemes.

In realistic precision top analyses, you typically combine several of these axes, guided by which physical effects dominate the uncertainties for your specific observables and phase-space regions.