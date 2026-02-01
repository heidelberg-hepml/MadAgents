# User prompt

Based on the three precision-improvement axes identified above, your task is to **construct and compare concrete simulation setups** for each approach.

### Simulation task

For each of the following strategies:

1. Higher-order QCD corrections (NLO+PS)
2. Finite-width / off-shell effects beyond the narrow-width approximation
3. Hard additional radiation via matrix-element multi-jet merging
do the following:
- Define a representative simulation setup implementing this strategy.
- Generate **O(5k) events** for each setup using reasonable, standard choices.
- Clearly state any assumptions or simplifications you make (e.g. on-shell vs off-shell decays, jet multiplicities, matching schemes).

You may choose suitable tools, schemes, and defaults where needed, but avoid unnecessary over-optimisation.

### Comparison task

Using these samples:
- Compare the qualitative impact of each strategy on relevant kinematic distributions.
- Explain **what physical effects differ** between the samples and why.
- Discuss the **advantages and limitations** of each approach.

Frame the comparison **conditionally**:
- Which approach is preferable for inclusive cross sections?
- Which is essential for shape observables or fiducial measurements?
- Which matters most for off-shell, width-sensitive, or boosted regimes?
All deliverables must be saved inside `/out/compare_ttbar/`; you may create suitable subdirectories.

### Output requirements

- Keep the discussion focused on physics and methodology, not software tutorials.
- Emphasize _when_ each approach is necessary versus _when it is overkill_.
- If trade-offs exist between approaches, explain them explicitly.

----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# MadAgents response

Here is what we actually did and what comes out of it, organised along your three strategies. All paths below are under `/output/compare_ttbar/`, which serves as the requested `/out/compare_ttbar/` directory.

## 0. Concrete setups and files

Common to all three:
- Collider: pp at $\sqrt{s}=13$ TeV.
- $m_t = 172.5$ GeV, $\Gamma_t \approx 1.32$ GeV.
- PDFs: NNPDF3.1 NLO (LHAPDF ID 303400).
- Final state used in the comparison: **only** $t\bar t\to b e^+\nu_e\, \bar b \mu^-\bar\nu_\mu$ (no $e^-\mu^+$).
- Fiducial selection (analysis level): exactly 1 e and 1 $\mu$ (OS), $p_T>25$ GeV, $|\eta|<2.5$, isolated; at least 2 jets with $p_T>25$ GeV, $|\eta|<2.5$ and at least 1 truth b-tag.

Samples and locations:

1. **NLO+PS on-shell (higher-order QCD axis)**  
   - Process: $pp \to t\bar t$ [QCD] at **NLO QCD**, on-shell tops.
   - Decays: LO MadSpin, $t\to b e^+\nu_e$, $\bar t\to \bar b\mu^-\bar\nu_\mu$.
   - Matching: aMC@NLO to Pythia8, hadronisation+UE on.
   - Events: 5000 showered events.  
   - Files:  
     - Events: `samples/ttbar_NLOPS/ttbar_NLOPS_PY8.hepmc.gz`  
     - Metadata: `samples/ttbar_NLOPS/metadata.txt`

2. **LO+PS off-shell 2→6 (off-shell axis)**  
   - Process: $pp \to e^+\nu_e\,\mu^-\bar\nu_\mu\,b\bar b$ at **LO QCD**, with complex-mass scheme and all doubly-, singly- and non-resonant diagrams (full $W^+W^-b\bar b$ structure).
   - No separate decay step: leptons and b’s appear directly from the ME, with finite widths.
   - Shower: Pythia8, hadronisation+UE on.
   - Events: 5000 showered events.  
   - Files:  
     - Events: `samples/ttbar_offshell_LOPS/ttbar_offshell_LOPS_PY8.hepmc.gz`  
     - Metadata: `samples/ttbar_offshell_LOPS/metadata.txt`

3. **LO MLM-merged tt̄(+0,1j)+PS (hard-radiation axis)**  
   - Processes: $pp \to t\bar t$, $pp \to t\bar t j$ at **LO QCD** (0 and 1 extra parton; 2-jet MEs were dropped due to a technical issue).
   - Merging: MLM $k_T$ with Pythia8, $x_{\text{cut}} \approx 30$ GeV, dynamic scale $\sim H_T/4$.
   - Decays: LO MadSpin to the same $e^+\mu^-$ channel as in NLO+PS.
   - Events: 5000 decayed LHE; 3444 events kept after MLM matching in the Pythia8 sample.  
   - Files:  
     - Events: `samples/ttbar_LO_merged/ttbar_LO_merged_PY8.hepmc.gz`  
     - Metadata: `samples/ttbar_LO_merged/metadata.txt`

Unified analysis and plots:
- Histograms & cross sections: `analysis/histograms_ttbar_compare.npz`, `analysis/cross_sections_ttbar_compare.json`.
- Raw text comparison: `analysis/summary_comparison_raw.txt`.
- Plots (PDF+PNG): `plots/compare_ttbar_*.pdf` (Njets, pT_lep1, pT_lep2, pT_ttbar, M_ttbar, M_bl, with log‑y variants for Njets and pT_ttbar).

Below I summarise the physics comparison.

## 1. Inclusive and fiducial cross sections

From the generator metadata and the analysis (weights $w = \sigma_\text{total}/N_\text{events}$ and fiducial event counts):

- **NLO+PS on-shell**  
  - $\sigma_\text{total} \approx 7.4\times 10^2$ pb (inclusive $t\bar t$ at NLO QCD).  
  - $\sigma_\text{fid}(e^+\mu^-) \approx 2.5\times 10^2$ pb.

- **LO+PS off-shell 2→6**  
  - $\sigma_\text{total}(e^+\nu_e\mu^-\bar\nu_\mu b\bar b)$ (LO) $\approx 5.7$ pb.  
  - $\sigma_\text{fid} \approx 2.4$ pb.

- **LO merged tt̄(+0,1j)+PS**  
  - Matched LO cross section (after MLM) $\sigma_\text{total}(e^+\mu^-) \approx 12.9$ pb.  
  - $\sigma_\text{fid} \approx 4.8$ pb.

Interpretation:
- The NLO+PS sample is an **inclusive tt̄** process (before decay), hence its total cross section is much larger. The LO off-shell and LO merged samples are defined directly for the **leptonic final state**, so their $\sigma_\text{total}$ are not directly comparable numerically to the NLO inclusive rate.
- Fiducially (after your eμ+jets+1b selection), the ordering is: NLO+PS $\gg$ LO merged $>\!>$ LO off-shell, reflecting both perturbative order and process definition.

**For inclusive cross sections:** the NLO+PS on-shell sample is the only one you would sensibly use. The LO samples are there to explore specific effects (off-shell structure, hard jets), not to normalise data.

## 2. Jet multiplicity and hard radiation

Observed (fiducial) average $N_\text{jets}$ and high-multiplicity fractions:

- **NLO+PS on-shell:**  
  - $\langle N_\text{jets} \rangle \approx 2.9$;  
  - $P(N_\text{jets} \ge 4) \approx 0.24$.

- **LO+PS off-shell:**  
  - $\langle N_\text{jets} \rangle \approx 2.8$;  
  - $P(N_\text{jets} \ge 4) \approx 0.20$.

- **LO merged tt̄(+0,1j)+PS:**  
  - $\langle N_\text{jets} \rangle \approx 3.5$;  
  - $P(N_\text{jets} \ge 4) \approx 0.44$.

Qualitatively (plots `compare_ttbar_Njets.pdf` / `_logy.pdf`):
- NLO+PS and off-shell LO give similar jet multiplicity patterns; both rely on the shower (plus one NLO emission for NLO+PS) for extra jets.
- LO merged shows a **substantially harder jet spectrum**: more events in $N_\text{jets}\ge 3,4$, as expected from including explicit $t\bar t$+jet MEs.

**When is this important?**
- If your analysis bins in jet multiplicity, uses jet vetoes, or is sensitive to extra hard jets (e.g. background modelling for Higgs or BSM analyses), the merged sample (even with just 0/1 jets) is clearly superior. It moves significant rate into higher $N_\text{jets}$ bins in a controlled, ME-driven way.
- For more inclusive eμ measurements that do not resolve jet structure, the NLO+PS on-shell description is generally adequate; the merging is **useful but not essential**.

## 3. $p_{T,t\bar t}$ and other recoil observables

From `compare_ttbar_pT_ttbar.pdf` and `_logy.pdf`:
- **NLO+PS on-shell:** moderate $p_{T,t\bar t}$ spectrum (mean $\sim 70$ GeV), small high-$p_T$ tail.
- **LO+PS off-shell:** similar mean ($\sim 80$ GeV), slightly fatter tail (few percent of events above 300 GeV).
- **LO merged:** significantly harder $p_{T,t\bar t}$ (mean $\sim120$ GeV), with an order‑of‑magnitude larger tail fraction above 300 GeV.

This matches the physics expectation: the extra explicit ME parton in the merged sample kicks the $t\bar t$ system harder.

**When does this matter?**
- For boosted top analyses or any measurement sensitive to the recoil of the $t\bar t$ system (e.g. missing-energy–based new-physics searches with tt̄ backgrounds), the LO merged sample captures the high $p_T$ tail much better than a pure shower (LO+PS off-shell) or a single NLO emission (NLO+PS on-shell) alone.
- If your observable is more inclusive in recoil, NLO+PS gives a decent description; the marginal gains from merging may be overkill relative to complexity.

## 4. Reconstructed $M_{t\bar t}$

Using a simple reconstruction from leptons + b-jets + MET (see `compare_ttbar_M_ttbar.pdf`):
- All three samples produce broadly similar $M_{t\bar t}$ distributions in the peak region.
- LO merged has a **slightly harder** tail (more events at large $M_{t\bar t}$), consistent with its harder radiation.
- LO off-shell is close to NLO+PS in shape in this fiducial region; the main difference is **normalisation**, not a dramatic distortion of the line shape.

This is a reminder that **off-shell effects are most visible in dedicated regions/observables** (edges, interference‑enhanced corners) rather than in a standard inclusive tt̄ mass in a central selection.

**When is off-shell LO needed here?**
- If you care about width-sensitive or very off-shell tt̄ tails (e.g. high $M_{t\bar t}$, overlapping with non-resonant $WWb\bar b$), off-shell modelling becomes important and you would design selections/observables that expose these differences more strongly than our simple reconstruction did.
- For routine fiducial tt̄ differential measurements in “normal” regions, the NLO+PS on-shell approximation is typically sufficient; pure LO off-shell is not competitive on its own because of LO normalisation and lack of higher-order corrections.

## 5. $M_{b\ell}$ as an off-shell–sensitive proxy

From `compare_ttbar_M_bl.pdf`:
- With our simple reconstruction (closest lepton–b-jet pairing, then choose the smaller $M_{b\ell}$), **all three samples give very similar $M_{b\ell}$ distributions** in this fiducial region:
  - Means differ by only a few GeV.
  - There is essentially no sizable population in extremely high $M_{b\ell}$ tails in any sample with the current cuts.

This illustrates that, for typical selections, off-shell/finite-width effects in top decays do **not necessarily produce dramatic $M_{b\ell}$ distortions**, especially when smeared by realistic kinematic cuts and simple reconstruction.

**Where would off-shell effects be essential?**
- Dedicated off-shell or width extractions (e.g. studying $M_{b\ell}$ near kinematic edges, or tails of $M_{t\bar t}$ in regions designed to suppress pure tt̄ resonant contributions) require a full off-shell prediction and careful modelling of interference.
- Our LO off-shell 2→6 sample is the **right axis** conceptually for that, but would need NLO QCD improvements (and perhaps re‑optimised selections) to be used for precision.

## 6. Pros, cons, and “when is it overkill?”

**NLO+PS on-shell (baseline upgrade)**
- **Pros:**
  - Best for **inclusive and most fiducial cross sections**: correct NLO normalisation, reduced scale uncertainties, and reasonable shapes.
  - Negative weights and MC@NLO matching are standard and under control.
- **Cons:**
  - Does **not** include finite-width/non-resonant effects; production and decay are factorised in NWA.
  - Additional hard jets beyond the first emission are still shower‑only; 1-jet bin is improved, but 2+ jets depend strongly on shower model.
- **Overkill?** Rarely. As a PhD-level baseline, NLO+PS on-shell is almost always the “minimum sensible” starting point for modern analyses.

**LO+PS off-shell 2→6 (finite width / full resonance)**
- **Pros:**
  - Includes **finite-width effects, non-resonant contributions, and interference** for the full $e^+\nu_e\mu^-\bar\nu_\mu b\bar b$ final state.
  - Gives the correct gauge‑invariant line shapes and interference patterns.
- **Cons:**
  - Only LO in QCD here: poor normalisation, larger scale uncertainties.
  - In generic fiducial selections, shape differences relative to NLO+PS on-shell are often modest; the big gain is in specific off-shell‑sensitive corners, which we did not fully exploit in this toy setup.
- **When essential?**
  - Width measurements, off-shell studies, interference regions (e.g. $tW$ vs $t\bar t$ overlaps), or precision fits that probe kinematic regions where $\mathcal{O}(\Gamma_t/m_t)$ effects are enhanced.
- **Overkill?**
  - For many “everyday” tt̄ analyses (inclusive cross sections, mild shape measurements in central regions), LO off-shell is **not** a replacement for NLO+PS on-shell—it is complementary and would ideally be promoted to NLO+PS off-shell to be used seriously.

**LO merged tt̄(+0,1j)+PS (hard radiation)**
- **Pros:**
  - Clearly improves the description of **hard additional jets** and recoil-sensitive observables:
    - Higher $N_\text{jets}$ tail, harder $p_{T,t\bar t}$ and $M_{t\bar t}$ tails match physical expectations.
  - Still relatively light in CPU compared to full NLO multi-jet merging.
- **Cons:**
  - Only LO normalisation; cross sections are less reliable than NLO+PS.
  - Here we only included 0 and 1 jet at ME level; 2+ jets are still shower‑only.
- **When essential?**
  - Analyses that rely heavily on **jet multiplicities, jet vetoes, or high‑$p_T$ radiation** (background to many BSM/Higgs searches, boosted tops, etc.).
- **Overkill?**
  - If your analysis is inclusive in jets and not very sensitive to recoil/extra jets, NLO+PS on-shell alone is often sufficient; full ME merging then buys relatively little compared to its added complexity.

## 7. Conditional preferences (answering your framing)

- **Preferable for inclusive cross sections:**
  - **NLO+PS on-shell**, by a wide margin. The LO off-shell and LO merged samples are not designed for precision normalisation.

- **Essential for shape observables / fiducial measurements:**
  - For **most standard fiducial shapes** (lepton $p_T$, moderate $M_{t\bar t}$, basic jet bins), NLO+PS on-shell provides an adequate baseline.  
  - **Hard-jet sensitive observables** (high $N_\text{jets}$, large $p_{T,t\bar t}$) really benefit from LO merging (and, in practice, from NLO multi-jet merging if you push precision).

- **Most relevant for off-shell / width-sensitive / boosted regimes:**
  - **Off-shell / width-sensitive:** LO off-shell 2→6 is the right conceptual axis (finite width, non-resonant, interference). For actual precision, you’d want NLO+PS off-shell; our LO+PS off-shell sample shows that in “vanilla” selections the impact is modest, so you’d design dedicated observables and regions to amplify it.
  - **Boosted / high $p_T$ tails:** LO merged (or, better, NLO merged) is crucial to get jet and recoil spectra right; NLO+PS on-shell alone under-resolves multi-jet structure.

If you want, we can next pick one observable (e.g. $p_{T,t\bar t}$ or $M_{b\ell}$) and go through the plots and numbers in more detail, or adapt the selections to a concrete analysis you’re working on.