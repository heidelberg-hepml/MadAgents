# User prompt

Please generate a clear, well-structured summary of the most important steps you carried out and the key decisions you made, including appropriate citations, written in a style suitable for direct inclusion in a LaTeX document.

----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# MadAgents response 

Here is a LaTeX-ready summary you can paste into your paper and adapt. It focuses on the main ingredients and the key decisions/assumptions.

```latex
\subsection{Simulation and analysis setup}

The signal under study is a simplified scalar leptoquark $S_1$ with quantum numbers
$S_1 \sim (\bar{3},1,1/3)$, pair-produced in proton--proton collisions,
followed by the decay chain
\begin{equation}
  pp \to S_1 S_1^{\dagger} \to (\ell^+ j)(\ell^- j)
  \;
  \Rightarrow \;
  2\ell + 2j~\text{final state},
\end{equation}
closely following the workflow outlined in the HEPTAPOD short note.

\paragraph{Event generation.}
Events are generated with \texttt{MadGraph5\_aMC@NLO} v3.7.0 interfaced to
\texttt{Pythia~8.316} for parton showering and hadronisation.
We use an existing public leptoquark UFO model, \texttt{LQnlo\_5FNS\_v5\_UFO},
and identify the HEPTAPOD scalar $S_1$ with the particle \texttt{LQ1d}
(and its antiparticle \texttt{LQ1d\textasciitilde{}}).  The collider setup is
\begin{itemize}
  \item proton--proton collisions at $\sqrt{s} = 8~\text{TeV}$, implemented as
        $E_{\text{beam}1} = E_{\text{beam}2} = 4000~\text{GeV}$;
  \item leading-order (LO) matrix elements with parton shower (LO+PS),
        no ME--PS matching;
  \item PDFs: LHAPDF with \texttt{NNPDF31\_lo\_as\_0130} ($\texttt{lhaid} = 315200$).
\end{itemize}

The leptoquark mass is scanned over three benchmark points
\begin{equation}
  m_{S_1} \in \{1.0, 1.5, 2.0\}~\text{TeV}.
\end{equation}
For each mass point, we generate $N_{\text{events}} = 20\,000$ unweighted LO
parton-level events and shower them with Pythia~8.  The total width of $S_1$ is
taken from the UFO model defaults (narrow-width regime, $\Gamma/m \lesssim 1\%$).
A simple flavour structure is chosen by turning on only the right-handed
Yukawa coupling between first-generation up quarks and electrons,
\begin{equation}
  y_{11} \ne 0,\quad y_{ij} = 0~\text{for}~(i,j) \neq (1,1),
\end{equation}
so that $S_1$ decays dominantly as $S_1 \to e^+ u$ and $S_1^{\dagger} \to e^- \bar u$.
SM backgrounds (DY+jets, $t\bar t$, dibosons) are not simulated in this
implementation; the focus is on the signal resonance shape and its dependence on
$m_{S_1}$.

\paragraph{Hadron-level reconstruction.}
The analysis is performed at hadron level, using Pythia~8 final states without
additional detector simulation.  Stable final-state particles are taken as those
with \texttt{status} $=1$ in the HepMC record. Neutrinos
($\lvert \text{PID} \rvert \in \{12,14,16\}$) are removed from both lepton and
jet reconstruction.

Electrons are reconstructed from HepMC particles with $\lvert \text{PID} \rvert = 11$,
with kinematic cuts
\begin{equation}
  p_T^e > 50~\text{GeV},\qquad \lvert \eta^e \rvert < 2.5,
\end{equation}
and we require exactly two such electrons per event.

Jets are clustered from all remaining stable particles (excluding neutrinos and
electrons) using the anti-$k_T$ algorithm with radius parameter $R=0.4$ as
implemented in \texttt{pyjet} (FastJet-style clustering). Reconstructed jets must
satisfy
\begin{equation}
  p_T^j > 50~\text{GeV},\qquad \lvert \eta^j \rvert < 5.0,
\end{equation}
and at least two jets are required. Only the two leading jets in $p_T$ are used
for the resonance reconstruction.

\paragraph{Resonance reconstruction and $m_{LQ}^{\min}$.}
In events with exactly two selected electrons $(\ell_1, \ell_2)$ and at least
two selected jets $(j_1, j_2)$, we reconstruct two leptoquark candidates by
forming all possible pairings between leptons and the two leading jets:
\begin{align}
  \text{Pairing A}: &\quad (\ell_1 + j_1),~(\ell_2 + j_2),\\
  \text{Pairing B}: &\quad (\ell_1 + j_2),~(\ell_2 + j_1).
\end{align}
For each pairing we compute the invariant masses $(m_1, m_2)$ of the two
candidates. We select the pairing that minimises $\lvert m_1 - m_2 \rvert$, and
from that pairing define the reconstructed leptoquark mass variable
\begin{equation}
  m_{LQ}^{\min} = \min(m_1, m_2).
\end{equation}
This follows the standard HEPTAPOD/MC4BSM prescription and produces a
resonance-like peak near the true $m_{S_1}$ with a modest low-mass tail.

\paragraph{Histogramming and normalisation.}
Two complementary binnings of $m_{LQ}^{\min}$ are used:
\begin{itemize}
  \item A ``shape'' view: 50 bins from $0$ to $2500~\text{GeV}$ with
        unit-area normalisation per mass point, i.e. each distribution is
        normalised such that
        $\sum_i N_i = 1$ and the bin contents can be interpreted as
        probabilities per bin (or, equivalently, as a discretised probability
        density when divided by the bin width).
  \item A ``fraction per bin'' view: 30 bins from $0$ to $4000~\text{GeV}$,
        where the bin heights are defined as
        \begin{equation}
          f_i = \frac{N_i}{N_{\text{tot}}}
        \end{equation}
        for each mass point. Here $N_i$ is the number of selected events in bin
        $i$ and $N_{\text{tot}}$ is the total number of selected events for that
        benchmark. This representation highlights the actual fraction of events
        in each mass window without any additional $1/\Delta m$ factor.
\end{itemize}
In both cases we overlay the three benchmark spectra ($m_{S_1}=1.0,1.5,2.0$~TeV)
for direct comparison. Poisson uncertainties $\sqrt{N_i}$ are propagated to the
normalised histograms and shown as error bars.

\paragraph{Workflow automation.}
The full chain (environment setup, event generation, showering, analysis and
plotting) is driven by a bash script
\texttt{run\_heptapod\_workflow.sh} residing in the analysis directory. This
script:
\begin{itemize}
  \item sources the prepared environment (MG5\_aMC, Pythia~8, FastJet, Python);
  \item launches the MG5\_aMC generation script for the three benchmark masses
        and stages the resulting LHE and HepMC files;
  \item runs the reconstruction code to produce the $m_{LQ}^{\min}$ histograms;
  \item runs the plotting scripts for both the 50-bin and 30-bin variants;
  \item and ensures that all user-facing deliverables (events, histograms,
        plots, and ambiguity summary) are available under the designated
        output directory.
\end{itemize}

All non-trivial choices that are not fixed by the HEPTAPOD note (collider
energy, PDF set, specific UFO model, Yukawa pattern, use of hadron-level
rather than detector-level objects, exact cuts and binning) are documented in a
separate ``ambiguities and decisions'' note that accompanies this analysis.
```

If you’d like, I can also generate a shorter version (e.g. a compact itemize environment) or split this into separate subsections (event generation, reconstruction, plotting) to match your paper’s structure.