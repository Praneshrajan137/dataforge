# Who verifies an attestation, and what they need

`docs/STRATEGY.md` supplies the rule this document answers to, and `PRODUCT.md` quotes it twice:

> A certificate with a named consumer is a product; one without is a log line.

That rule has been applied twice inside this project, and both times the artifact was correctly
demoted. `SessionCertification` is printed to stdout and discarded, and **no certified threshold has
ever influenced a byte** (`PRODUCT.md`:251-257). The reviewer outcome labels were computed and handed
only to machines until `dataforge/ui/outcome.py` gave them a consumer.

**It has never been applied to the attestation itself.** This document applies it, and the honest
answer is uncomfortable.

## The current state, stated first

`DECISIONS.md`:925-928 already recorded it:

> Every benefit of in-toto is a benefit *to a third-party verifier*, and the audit confirmed there
> are none: 0 stars, 0 forks, 0 issues, no design partner.

Nothing has changed. There is **no named consumer of a DataForge attestation**, and by this project's
own maxim the artifact carrying the entire thesis is therefore a log line rather than a product. That
is not softened by the format being well built, and it is not softened by
[specification-sufficiency.md](specification-sufficiency.md) having closed six defects in it.

Three further facts, each verified rather than assumed:

- **`dataforge attest verify`'s docstring reads *"Verify an attestation without trusting the tool
  that produced it."*** It *is* the tool that produced it. The sentence is true only because a second
  implementation exists, and that second implementation was ported from the first.
- **No page under `docs/docs/` documents the attestation for a third party.** There is no surface a
  stranger lands on. The only prose is in `README.md`, `docs/STRATEGY.md` and
  `docs/ROADMAP_FULL_VISION.md`, all of which address a reader who already has the repository.
- **The conformance suite that certifies independence from DataForge lives inside DataForge.** A
  stranger cannot fetch the vectors without cloning the thing they are trying not to trust.

## What a consumer would actually need, by class

Written as a specification of the missing product, not as a claim that anyone wants it. Each row
names what the party holds, what they would run, and what is missing today.

| Consumer class | Holds | Would run | Missing |
| --- | --- | --- | --- |
| **A data recipient** deciding whether to accept a repaired table from a supplier | the CSV, the attestation | the normative tier over both, with `--data` | nothing technical; they need to be told the artifact exists |
| **An auditor** reconstructing why a value changed, months later | the attestation, not the table | the normative tier minus `data_identity`; reads `fixes[]`, `limitations`, `journal` | a stable statement that `data_identity` skipped is not `data_identity` passed — present in the report, absent from any document they would read |
| **A regulated pipeline** gating promotion on provable non-corruption | attestation per batch, in CI | the normative tier as an exit code | key distribution. §3 puts trust roots out of scope, so a pipeline has no way to decide which signing key is legitimate |
| **A platform** ingesting attestations from many producers | many attestations | schema validation plus the normative tier | a published, versioned, fetchable schema and vector suite. Both exist only inside this repository |
| **A researcher** replicating the claim that the format is independently verifiable | the specification | their own verifier, against the vectors | the vectors, fetchable without cloning DataForge |

Two rows carry the load, and they are the two the maxim actually bites on.

**The auditor row is the one with a real, non-hypothetical hole.** `data_identity` reports `skipped`
when no bytes are supplied — correctly, and both implementations distinguish it from a pass. But an
auditor holding only the attestation is *always* in that case, and no document tells them that the
strongest available reading of their verification is "this document is internally coherent and names
a file I cannot see." That is a documentation gap, and it is the gap most likely to be
mis-summarised by a reader in a hurry as "verified."

**The researcher row is the one that would make the thesis checkable by anyone.** It is also the
cheapest.

## The one concrete step taken

The vectors, the schema and the specification are now a self-describing set, named as such in §3.1 of
`specs/SPEC_repair_attestation.md`, and every check name and closed vocabulary in them is bound to
the implementation by `scripts/ci/spec_correspondence.py`. That is a precondition for publishing them
as a standalone artifact: before it, a fetched copy could disagree with the verifier and nothing
would notice.

**Publishing them outward is not done, and is deliberately not done in this session.** It is an
outward-facing act — a release asset, a tag, or a second repository — and it changes what this project
asserts publicly. That is the operator's call, not a coding decision. What is prepared is the
integrity property that makes it safe; what is missing is the decision to publish.

## What this does and does not claim

- **Not that a consumer exists.** None does. The table above is a specification of demand, derived
  from the format's own capabilities, not evidence of it. No party in it has been contacted, and
  writing down who *would* use something is not adoption.
- **Not that publishing the vectors would create a consumer.** It removes one obstacle. The audit
  finding that there is no design partner stands, and
  `docs/trust/design-partner-evidence.md` remains red.
- **Not that the format is inadequate for these consumers.** For four of the five rows the technical
  surface is already sufficient and the gap is distribution or documentation. Only the regulated
  pipeline is blocked on something the format deliberately excludes — trust roots, out of scope per
  §3, and correctly so, since implying a trust root the format does not have would be the overclaim
  this project keeps retiring.
- **Not a change of status.** Until a named party verifies an attestation they did not produce, the
  maxim's verdict is unchanged and should be quoted unchanged: this is a log line. The work in
  [specification-sufficiency.md](specification-sufficiency.md) made it a *correct* log line, which is
  a precondition for it becoming a product and is not the same thing.
