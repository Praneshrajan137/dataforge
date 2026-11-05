/**
 * Component tests for the trust surface.
 *
 * This is the product's central claim -- proven versus plausibility-only, and a certificate a
 * third party can re-check -- so it is the surface where a rendering defect does the most
 * damage. It had no unit test.
 *
 * The distinction these tests care about is not cosmetic. "Proven" means deterministic or
 * verified against an authoritative schema and therefore safe to write; "plausibility-only"
 * means a model proposed it and nothing proved it. Conflating them in the UI would authorise
 * a bad write, which is the exact failure the whole verification layer exists to prevent.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TrustVerdict } from "../observatory";
import type { AttestationVerificationView, Certificate } from "../types";
import {
  AttestationPanel,
  CertificatePanel,
  HeldForReviewList,
  ProofAttribution,
  TrustVerdictPanel,
} from "./trust";

const verdict = (overrides: Partial<TrustVerdict> = {}): TrustVerdict =>
  ({
    level: "proven",
    headline: "Every applied change was proven",
    guaranteeLine: "No unproven change would be written.",
    independentVerification: "not_run",
    metrics: [{ label: "Applied", value: "3", hint: "proven fixes", tone: "verified" }],
    ...overrides,
  }) as TrustVerdict;

const certificate = (overrides: Partial<Certificate> = {}): Certificate =>
  ({
    ok: true,
    checks: [
      { name: "source_hash_matches", ok: true, detail: "The bytes hash to the recorded digest." },
      { name: "no_unproven_writes", ok: true, detail: "Nothing unproven was applied." },
    ],
    ...overrides,
  }) as Certificate;

describe("TrustVerdictPanel", () => {
  it("renders nothing before a run, rather than an empty verdict shell", () => {
    const { container } = render(<TrustVerdictPanel verdict={verdict({ level: "pending" })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("announces the verdict politely, since it appears without the user asking", () => {
    render(<TrustVerdictPanel verdict={verdict()} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAccessibleName("Every applied change was proven");
  });

  it("states the guarantee alongside the headline", () => {
    render(<TrustVerdictPanel verdict={verdict()} />);
    expect(screen.getByText("No unproven change would be written.")).toBeInTheDocument();
  });

  it("claims independent verification ONLY when a second verifier actually agreed", () => {
    render(<TrustVerdictPanel verdict={verdict({ independentVerification: "not_run" })} />);
    expect(screen.getByText("Single verifier")).toBeInTheDocument();
    expect(screen.queryByText(/Independently verified/)).not.toBeInTheDocument();
  });

  it("says so when two independently written verifiers did agree", () => {
    render(<TrustVerdictPanel verdict={verdict({ independentVerification: "agreed" })} />);
    expect(screen.getByText(/Independently verified/)).toBeInTheDocument();
    expect(screen.queryByText("Single verifier")).not.toBeInTheDocument();
  });

  it("carries the verdict level in its class so the rung is visually addressable", () => {
    const { container } = render(<TrustVerdictPanel verdict={verdict({ level: "held" })} />);
    expect(container.firstElementChild?.className).toContain("trust-verdict--held");
  });

  describe("when the result is stale", () => {
    // The defect this replaces: a red error banner rendered directly above a green "every
    // applied change was proven" verdict that described a DIFFERENT run. The claim was true of
    // its own run and false of the screen it appeared on.
    it("says the verdict describes an earlier run", () => {
      render(<TrustVerdictPanel verdict={verdict()} stale />);
      expect(screen.getByText(/describes an earlier run/i)).toBeInTheDocument();
      expect(screen.getByText("Previous run")).toBeInTheDocument();
    });

    it("stops labelling itself as the current trust verdict", () => {
      render(<TrustVerdictPanel verdict={verdict()} stale />);
      expect(screen.queryByText("Trust verdict")).not.toBeInTheDocument();
    });

    it("leaves the warrant ladder rather than keeping the proven rail", () => {
      const { container } = render(<TrustVerdictPanel verdict={verdict({ level: "proven" })} stale />);
      const className = container.firstElementChild?.className ?? "";
      expect(className).toContain("trust-verdict--stale");
      expect(className).not.toContain("trust-verdict--proven");
    });

    it("is machine-detectable as stale, so a test or audit can assert it", () => {
      const { container } = render(<TrustVerdictPanel verdict={verdict()} stale />);
      expect(container.firstElementChild).toHaveAttribute("data-stale", "true");
    });

    it("still shows the underlying result, which the user may need", () => {
      render(<TrustVerdictPanel verdict={verdict()} stale />);
      expect(screen.getByRole("heading", { name: "Every applied change was proven" })).toBeInTheDocument();
    });

    it("does not mark a current verdict as stale", () => {
      const { container } = render(<TrustVerdictPanel verdict={verdict()} />);
      expect(container.firstElementChild).not.toHaveAttribute("data-stale");
      expect(screen.queryByText(/describes an earlier run/i)).not.toBeInTheDocument();
    });
  });
});

describe("CertificatePanel", () => {
  it("reports the passing check count when the certificate self-verifies", () => {
    render(
      <CertificatePanel
        certificate={certificate()}
        independentVerification="not_run"
        auditCommand="dataforge audit ./receipt.json"
        onDownload={() => {}}
      />,
    );
    expect(screen.getByRole("heading", { name: "Re-verified 2/2 checks" })).toBeInTheDocument();
    expect(screen.getByText("self-verifies")).toBeInTheDocument();
  });

  it("counts and surfaces UNMET checks rather than reporting a pass", () => {
    render(
      <CertificatePanel
        certificate={certificate({
          ok: false,
          checks: [
            { name: "source_hash_matches", ok: true, detail: "ok" },
            { name: "no_unproven_writes", ok: false, detail: "An unproven value was applied." },
          ],
        })}
        independentVerification="not_run"
        auditCommand="dataforge audit"
        onDownload={() => {}}
      />,
    );
    expect(screen.getByRole("heading", { name: /1 unmet check/ })).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
    expect(screen.getByText("An unproven value was applied.")).toBeInTheDocument();
  });

  it("humanises each check name instead of printing the raw identifier", () => {
    render(
      <CertificatePanel
        certificate={certificate()}
        independentVerification="not_run"
        auditCommand="x"
        onDownload={() => {}}
      />,
    );
    expect(screen.getByText("source hash matches")).toBeInTheDocument();
    expect(screen.queryByText("source_hash_matches")).not.toBeInTheDocument();
  });

  it("gives the off-machine re-verification command, which is the point of a certificate", () => {
    render(
      <CertificatePanel
        certificate={certificate()}
        independentVerification="not_run"
        auditCommand="dataforge audit ./receipt.json"
        onDownload={() => {}}
      />,
    );
    expect(screen.getByText("dataforge audit ./receipt.json")).toBeInTheDocument();
  });

  it("downloads on request", async () => {
    const onDownload = vi.fn();
    render(
      <CertificatePanel
        certificate={certificate()}
        independentVerification="not_run"
        auditCommand="x"
        onDownload={onDownload}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Download portable certificate/ }));
    expect(onDownload).toHaveBeenCalledOnce();
  });
});

function validDryRunStatement(
  sourceDigest = "a".repeat(64),
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const basePredicate: Record<string, unknown> = {
    attestation_version: "1",
    tool: { name: "dataforge", version: "0.1.0" },
    produced_at: "2026-10-21T00:00:00Z",
    mode: "dry_run",
    applied: false,
    reversible: true,
    source: { name: "hospital_10rows.csv", digest: { sha256: sourceDigest } },
    post: null,
    authority: {
      authoritative_columns: [],
      accepted_constraint_ids: [],
      constraints_sha256: null,
      constraints: null,
      premise: null,
    },
    fixes: [],
    held: [],
    verdicts: {
      safety: "allow",
      verifier: "accept",
      independent_verification: "not_run",
    },
    journal: { txn_id: "txn-demo", patch_plan_sha256: "c".repeat(64) },
    revert_command: "dataforge revert txn-demo",
    limitations: ["Dry run only."],
    ...overrides,
  };
  return {
    _type: "https://in-toto.io/Statement/v1",
    subject: [{ name: "hospital_10rows.csv", digest: { sha256: sourceDigest } }],
    predicateType: "https://dataforge.dev/RepairAttestation/v1",
    predicate: basePredicate,
  };
}

describe("AttestationPanel", () => {
  it("re-verifies the in-toto v1 Statement in the browser and marks skipped checks neutrally", () => {
    const sha = "a".repeat(64);
    const attestation: AttestationVerificationView = {
      ok: true,
      checks: [],
      statement: validDryRunStatement(sha),
    };
    render(
      <AttestationPanel
        attestation={attestation}
        sourceSha256={sha}
        sourceName="hospital_10rows.csv"
        onDownloadAttestation={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Browser verified 11/11 normative checks" }),
    ).toBeInTheDocument();
    expect(screen.getByText("client-verified ? 1 skipped")).toBeInTheDocument();
    const skippedLabel = screen.getByText("witness is coherent (skipped)");
    expect(skippedLabel.closest("li")?.className).toContain("certificate-check--skipped");
    expect(skippedLabel.closest("li")?.className).not.toContain("certificate-check--ok");
  });

  it("refuses a forged authority claim in the browser EVEN WHEN the server claims ok=true", () => {
    const sha = "a".repeat(64);
    const forged = validDryRunStatement(sha, {
      authority: {
        authoritative_columns: ["rating"],
        accepted_constraint_ids: [],
        constraints_sha256: null,
        constraints: null,
        premise: null,
      },
    });
    render(
      <AttestationPanel
        attestation={{ ok: true, checks: [], statement: forged }}
        sourceSha256={sha}
        sourceName="hospital_10rows.csv"
        onDownloadAttestation={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Browser verifier refused 1 normative check(s)" }),
    ).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
    expect(screen.getByText(/no premise is published/i)).toBeInTheDocument();
  });

  it("discloses weak_only_columns when authority is entailed solely by not_null or unique", () => {
    const sha = "a".repeat(64);
    const weakPremise = validDryRunStatement(sha, {
      authority: {
        authoritative_columns: ["provider_number"],
        accepted_constraint_ids: [],
        constraints_sha256: null,
        constraints: null,
        premise: {
          premise_format: "dataforge.premise/v1",
          not_null_columns: ["provider_number"],
        },
      },
    });
    render(
      <AttestationPanel
        attestation={{ ok: true, checks: [], statement: weakPremise }}
        sourceSha256={sha}
        sourceName="hospital_10rows.csv"
        onDownloadAttestation={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Browser verified 11/11 normative checks" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/weak_only_columns=\[provider_number\]/)).toBeInTheDocument();
  });

  it("downloads the raw in-toto Statement on request", async () => {
    const sha = "a".repeat(64);
    const onDownloadAttestation = vi.fn();
    render(
      <AttestationPanel
        attestation={{ ok: true, checks: [], statement: validDryRunStatement(sha) }}
        sourceSha256={sha}
        sourceName="hospital_10rows.csv"
        onDownloadAttestation={onDownloadAttestation}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Download in-toto Statement/ }));
    expect(onDownloadAttestation).toHaveBeenCalledOnce();
  });
});

describe("HeldForReviewList", () => {
  it("renders nothing when nothing is held, rather than an empty queue", () => {
    const { container } = render(<HeldForReviewList items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ProofAttribution", () => {
  it("renders nothing when there is no unsat core, because no constraint was violated", () => {
    const { container } = render(<ProofAttribution labels={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("decodes a known core label into a sentence rather than showing the raw label", () => {
    render(<ProofAttribution labels={["domain::rating::max::row::7"]} />);
    expect(screen.queryByText("domain::rating::max::row::7")).not.toBeInTheDocument();
  });

  it("admits it cannot decode a core instead of silently dropping the reason", () => {
    // Honest opacity: an undecodable reason is still shown verbatim, because hiding it would
    // make a rejection look unexplained.
    render(<ProofAttribution labels={["totally::unknown::shape"]} />);
    expect(screen.getByText(/cannot decode/i)).toBeInTheDocument();
    expect(screen.getByText("totally::unknown::shape")).toBeInTheDocument();
  });
});
