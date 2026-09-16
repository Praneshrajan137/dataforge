/**
 * Independent implementation of the NORMATIVE attestation verifier.
 *
 * Written from specs/SPEC_repair_attestation.md, sharing no code with the Python
 * reference implementation. That independence is the point: a format only becomes a
 * specification when a second implementation, written from the document rather than from
 * the code, reaches the same verdict on the same inputs. Until then it is one program's
 * behaviour with a version number attached.
 *
 * Both implementations run the committed vectors in tests/fixtures/attestation/vectors.json
 * and `scripts/ci/attestation_conformance.py` fails CI on any disagreement.
 *
 * The only shared artifact is the vocabulary, which is generated from the same source for
 * both languages -- and that is deliberate too. Re-typing a closed vocabulary by hand is
 * exactly what produced three drifts, one of them inside the certificate verifier.
 *
 * Signature verification is separated into an async function because Ed25519 requires
 * WebCrypto. Every other check is synchronous, pure, and dependency-free, which is what
 * makes this reimplementable in any language.
 */

import {
  DISCRIMINATING_COLUMN_TYPES,
  ENFORCEABLE_CONSTRAINT_KINDS,
  PROVENANCE_ORDER,
  REVIEW_REASONS,
  SAFETY_VERDICTS,
  TRUSTED_PROVENANCE,
  VERIFICATION_STRENGTHS,
  VERIFIER_VERDICTS,
} from "../domain/vocabulary.generated";

export const STATEMENT_TYPE = "https://in-toto.io/Statement/v1";
export const PREDICATE_TYPE = "https://dataforge.dev/RepairAttestation/v1";
export const PAYLOAD_TYPE = "application/vnd.in-toto+json";
export const ATTESTATION_VERSION = "1";

const HEX64 = /^[0-9a-f]{64}$/;

export interface AttestationCheck {
  name: string;
  ok: boolean;
  detail: string;
  skipped: boolean;
}

export interface AttestationVerification {
  ok: boolean;
  checks: AttestationCheck[];
  failures: AttestationCheck[];
  skipped: AttestationCheck[];
}

function check(name: string, ok: boolean, detail: string, skipped = false): AttestationCheck {
  return { name, ok, detail, skipped };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** The premise wire format's identity. An unrecognised value has no agreed semantics. */
const PREMISE_FORMAT = "dataforge.premise/v1";

/** The four premise fields holding an unordered set of column names. SPEC section 6.4.1. */
const PREMISE_SET_FIELDS = [
  "pii_columns",
  "primary_key_columns",
  "not_null_columns",
  "unique_columns",
] as const;

/** The six premise fields holding an array of structured rules, and which keys each rule allows. */
const PREMISE_RULE_FIELDS: Record<string, readonly string[]> = {
  functional_dependencies: ["determinant", "dependent"],
  accepted_values: ["column", "values"],
  regex_constraints: ["column", "pattern"],
  relationships: ["column", "reference", "reference_column"],
  domain_bounds: ["column", "min_value", "max_value", "inclusive_min", "inclusive_max"],
  aggregate_dependencies: ["source_column", "target_column", "aggregate", "group_by"],
};

const PREMISE_FIELDS = new Set<string>([
  "columns",
  ...PREMISE_SET_FIELDS,
  ...Object.keys(PREMISE_RULE_FIELDS),
]);

/**
 * Recompute the authoritative column set from a published premise, per SPEC section 6.4.2.
 *
 * Written from the specification rather than ported from the Python. That distinction is not
 * cosmetic here: this repository has already measured that the "independent" TypeScript verifier was
 * a PORT of the reference implementation -- a character-identical error string for a check the spec
 * never mentioned gave it away -- and a second implementation that merely restates the first cannot
 * disagree with it, so it produces no evidence. The shared inputs are the two projected sets, which
 * are specification, not implementation.
 *
 * Throws a string reason rather than returning a partial set: a premise that is half-understood
 * would confer authority over whichever fields happened to parse.
 */
function authoritativeFromPremise(premise: Record<string, unknown>): Set<string> {
  if (premise.premise_format !== PREMISE_FORMAT) {
    throw `premise_format is ${JSON.stringify(premise.premise_format)}, expected "${PREMISE_FORMAT}"`;
  }
  const unknown = Object.keys(premise)
    .filter((key) => key !== "premise_format" && !PREMISE_FIELDS.has(key))
    .sort();
  if (unknown.length > 0) {
    throw `premise has unknown key(s) [${unknown.join(", ")}], refused rather than ignored`;
  }

  const named = new Map<string, Set<string>>();
  const put = (kind: string, columns: Iterable<string>) => named.set(kind, new Set(columns));

  // `columns` confers authority only for a type that both narrows and can be encoded.
  const declared = premise.columns;
  const typedColumns: string[] = [];
  if (declared !== undefined && declared !== null) {
    if (!isRecord(declared)) throw "premise.columns must be an object";
    for (const [column, spelling] of Object.entries(declared)) {
      if (typeof spelling !== "string") throw `premise.columns[${column}] must be a string`;
      if (DISCRIMINATING_COLUMN_TYPES.has(spelling.trim().toLowerCase())) typedColumns.push(column);
    }
  }
  put("columns", typedColumns);

  for (const field of PREMISE_SET_FIELDS) {
    const value = premise[field];
    if (value === undefined || value === null) {
      put(field, []);
      continue;
    }
    if (!Array.isArray(value)) throw `premise.${field} must be an array of strings`;
    for (const entry of value) {
      if (typeof entry !== "string") throw `premise.${field} contains a non-string entry`;
    }
    put(field, value as string[]);
  }

  for (const [field, allowedKeys] of Object.entries(PREMISE_RULE_FIELDS)) {
    const value = premise[field];
    if (value === undefined || value === null) {
      put(field, []);
      continue;
    }
    if (!Array.isArray(value)) throw `premise.${field} must be an array of objects`;
    const columns: string[] = [];
    for (const rule of value) {
      if (!isRecord(rule)) throw `premise.${field} contains a non-object entry`;
      const strayKeys = Object.keys(rule).filter((key) => !allowedKeys.includes(key));
      if (strayKeys.length > 0) {
        throw `premise.${field} has unknown key(s) [${strayKeys.sort().join(", ")}]`;
      }
      // Which positions a kind NAMES. Both sides of a functional dependency and of an aggregate
      // dependency are named, because a value in either position is checked by it.
      if (field === "functional_dependencies") {
        const determinant = rule.determinant;
        if (!Array.isArray(determinant) || determinant.length === 0) {
          throw `premise.${field} rule has an empty determinant`;
        }
        for (const entry of determinant) columns.push(String(entry));
        columns.push(String(rule.dependent));
      } else if (field === "aggregate_dependencies") {
        columns.push(String(rule.source_column), String(rule.target_column));
      } else {
        if (typeof rule.column !== "string") throw `premise.${field} rule has no column`;
        if (field === "accepted_values") {
          const values = rule.values;
          if (!Array.isArray(values) || values.length === 0) {
            throw `premise.${field} rule for ${rule.column} has an empty value set`;
          }
        }
        columns.push(rule.column);
      }
    }
    put(field, columns);
  }

  const authoritative = new Set<string>();
  for (const [kind, columns] of named) {
    if (!ENFORCEABLE_CONSTRAINT_KINDS.has(kind)) continue;
    for (const column of columns) authoritative.add(column);
  }
  return authoritative;
}

/** SPEC section 7 check 13. Three cases, and the distinction between them is normative. */
function authorityIsEntailed(claimed: Set<string>, premise: unknown): AttestationCheck {
  const claimedSorted = [...claimed].sort();
  if (claimed.size === 0) {
    return check(
      "authority_is_entailed",
      true,
      "no columns are claimed as authoritative, so nothing needs entailing",
    );
  }
  if (premise === null || premise === undefined) {
    return check(
      "authority_is_entailed",
      false,
      `authority over [${claimedSorted.join(", ")}] is claimed but no premise is published, so the claim cannot be checked by anyone`,
    );
  }
  if (!isRecord(premise)) {
    return check("authority_is_entailed", false, "authority.premise must be an object");
  }
  let entailed: Set<string>;
  try {
    entailed = authoritativeFromPremise(premise);
  } catch (reason) {
    return check(
      "authority_is_entailed",
      false,
      `the published premise cannot be read, so authority over [${claimedSorted.join(", ")}] cannot be derived from it: ${String(reason)}`,
    );
  }
  const overclaimed = claimedSorted.filter((column) => !entailed.has(column));
  const underclaimed = [...entailed].filter((column) => !claimed.has(column)).sort();
  if (overclaimed.length === 0 && underclaimed.length === 0) {
    return check(
      "authority_is_entailed",
      true,
      `the published premise entails authority over exactly [${claimedSorted.join(", ")}]`,
    );
  }
  const parts: string[] = [];
  if (overclaimed.length > 0) parts.push(`claimed but not entailed: [${overclaimed.join(", ")}]`);
  if (underclaimed.length > 0) parts.push(`entailed but not claimed: [${underclaimed.join(", ")}]`);
  return check(
    "authority_is_entailed",
    false,
    `the published premise does not entail the authority claimed -- ${parts.join("; ")}`,
  );
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function records(value: unknown): Record<string, unknown>[] {
  return asArray(value).filter(isRecord);
}

function strings(value: unknown): string[] {
  return asArray(value).map((entry) => String(entry));
}

/**
 * Derive strength from provenance and column authority.
 *
 * Reads the TRUSTED allowlist, never an untrusted denylist. The denylist form fails open:
 * a provenance nobody anticipated reads as trustworthy, which is how an `entity_consensus`
 * value was once reported as `proven`.
 */
function verificationStrengthFor(
  provenance: unknown,
  authoritativeSchemaPresent: boolean,
): "proven" | "plausibility_only" {
  const trusted = typeof provenance === "string" && TRUSTED_PROVENANCE.has(provenance);
  return trusted || authoritativeSchemaPresent ? "proven" : "plausibility_only";
}

function digestOf(value: unknown): string | null {
  if (!isRecord(value)) {
    return null;
  }
  const digest = value.digest;
  if (!isRecord(digest)) {
    return null;
  }
  const sha = digest.sha256;
  return typeof sha === "string" ? sha : null;
}

/**
 * Verify an attestation's normative tier, synchronously.
 *
 * Accepts a bare in-toto Statement. For a DSSE envelope, verify the signature with
 * `verifyDsseSignature` first and pass the payload it returns -- never re-parse the
 * envelope afterwards, which the DSSE spec explicitly forbids.
 */
export function verifyStatement(
  statement: unknown,
  options: { dataSha256?: string | null } = {},
): AttestationVerification {
  const checks: AttestationCheck[] = [];

  const finish = (): AttestationVerification => {
    const failures = checks.filter((entry) => !entry.ok && !entry.skipped);
    return {
      ok: failures.length === 0,
      checks,
      failures,
      skipped: checks.filter((entry) => entry.skipped),
    };
  };

  if (!isRecord(statement)) {
    checks.push(check("envelope_recognised", false, "statement is not an object"));
    return finish();
  }

  const typeOk = statement._type === STATEMENT_TYPE;
  const predicateTypeOk = statement.predicateType === PREDICATE_TYPE;
  checks.push(
    check(
      "envelope_recognised",
      typeOk && predicateTypeOk,
      `_type=${JSON.stringify(statement._type)} predicateType=${JSON.stringify(
        statement.predicateType,
      )}`,
    ),
  );
  if (!typeOk || !predicateTypeOk) {
    return finish();
  }

  const predicate = statement.predicate;
  if (!isRecord(predicate)) {
    checks.push(check("schema_complete", false, "predicate is not an object"));
    return finish();
  }

  const version = predicate.attestation_version;
  checks.push(
    check(
      "version_recognised",
      version === ATTESTATION_VERSION,
      `attestation_version=${JSON.stringify(version)}`,
    ),
  );
  if (version !== ATTESTATION_VERSION) {
    return finish();
  }

  // --- schema_complete -------------------------------------------------------
  const missing: string[] = [];
  for (const field of [
    "tool",
    "produced_at",
    "mode",
    "applied",
    "reversible",
    "source",
    "authority",
    "fixes",
    "held",
    "verdicts",
    "journal",
    "limitations",
  ]) {
    if (!(field in predicate)) {
      missing.push(field);
    }
  }
  const tool = predicate.tool;
  if (isRecord(tool)) {
    for (const field of ["name", "version"]) {
      const value = tool[field];
      if (typeof value !== "string" || value.length === 0) {
        missing.push(`tool.${field}`);
      }
    }
  } else {
    missing.push("tool");
  }
  const subject = asArray(statement.subject);
  if (subject.length === 0) {
    missing.push("subject");
  }
  checks.push(
    check(
      "schema_complete",
      missing.length === 0,
      missing.length === 0 ? "all required fields present" : `missing/invalid: ${missing}`,
    ),
  );

  // --- vocabulary_closed -----------------------------------------------------
  const provenances = new Set<string>(PROVENANCE_ORDER);
  const strengths = new Set<string>(VERIFICATION_STRENGTHS as readonly string[]);
  const reasons = new Set<string>(REVIEW_REASONS as readonly string[]);
  const verifierVerdicts = new Set<string>(VERIFIER_VERDICTS as readonly string[]);
  const safetyVerdicts = new Set<string>(SAFETY_VERDICTS as readonly string[]);

  const vocabularyProblems: string[] = [];
  for (const fix of records(predicate.fixes)) {
    if (typeof fix.provenance !== "string" || !provenances.has(fix.provenance)) {
      vocabularyProblems.push(`fix provenance ${JSON.stringify(fix.provenance)}`);
    }
    if (
      typeof fix.verification_strength !== "string" ||
      !strengths.has(fix.verification_strength)
    ) {
      vocabularyProblems.push(
        `fix verification_strength ${JSON.stringify(fix.verification_strength)}`,
      );
    }
  }
  for (const held of records(predicate.held)) {
    if (typeof held.review_reason !== "string" || !reasons.has(held.review_reason)) {
      vocabularyProblems.push(`held review_reason ${JSON.stringify(held.review_reason)}`);
    }
  }
  const verdicts = predicate.verdicts;
  if (isRecord(verdicts)) {
    if (typeof verdicts.verifier !== "string" || !verifierVerdicts.has(verdicts.verifier)) {
      vocabularyProblems.push(`verifier verdict ${JSON.stringify(verdicts.verifier)}`);
    }
    if (typeof verdicts.safety !== "string" || !safetyVerdicts.has(verdicts.safety)) {
      vocabularyProblems.push(`safety verdict ${JSON.stringify(verdicts.safety)}`);
    }
    if (
      verdicts.independent_verification !== "agreed" &&
      verdicts.independent_verification !== "not_run"
    ) {
      vocabularyProblems.push(
        `independent_verification ${JSON.stringify(verdicts.independent_verification)}`,
      );
    }
  } else {
    vocabularyProblems.push("verdicts is not an object");
  }
  if (predicate.mode !== "apply" && predicate.mode !== "dry_run") {
    vocabularyProblems.push(`mode ${JSON.stringify(predicate.mode)}`);
  }
  checks.push(
    check(
      "vocabulary_closed",
      vocabularyProblems.length === 0,
      vocabularyProblems.length === 0
        ? "every enum value is a published member"
        : `unrecognised values: ${vocabularyProblems}`,
    ),
  );

  // --- identity --------------------------------------------------------------
  const applied = predicate.applied === true;
  const sourceDigest = digestOf(predicate.source);
  const postDigest = digestOf(predicate.post);
  const expected = applied ? postDigest : sourceDigest;

  // in-toto v1 permits N subjects. Both verifiers used to read `subject[0]` and ignore the
  // rest, which is a smuggling hole rather than a cosmetic gap: append a second subject
  // naming a malicious file's digest to an otherwise valid attestation and a consumer that
  // checks the first subject reports `verified`, while the statement now also asserts
  // something about a file nobody attested.
  //
  // This predicateType describes ONE repair of ONE artifact, so extra subjects are not
  // verifiable here. The rule is a refusal, not a wider read: every subject must carry the
  // expected digest. Duplicates are allowed; a subject naming a different artifact fails
  // closed.
  const subjectDigests = subject.map((entry) => digestOf(entry));
  const unexpected = subjectDigests.filter((digest) => digest !== expected);
  const subjectDetail =
    subjectDigests.length === 0
      ? "no subject present"
      : unexpected.length > 0
        ? `${unexpected.length} of ${subjectDigests.length} subject(s) name a different ` +
          `artifact than the predicate describes: ${JSON.stringify(unexpected.slice(0, 3))} ` +
          `expected=${JSON.stringify(expected)}`
        : subjectDigests.length > 1
          ? `all ${subjectDigests.length} subject(s) match, subject=${JSON.stringify(expected)}`
          : `subject=${JSON.stringify(expected)}`;

  checks.push(
    check(
      "subject_matches_post_state",
      subjectDigests.length > 0 &&
        unexpected.length === 0 &&
        typeof expected === "string" &&
        HEX64.test(expected),
      subjectDetail,
    ),
  );

  const suppliedDigest = options.dataSha256 ?? null;
  if (suppliedDigest === null) {
    checks.push(
      check(
        "data_identity",
        true,
        "no data supplied, so the digest claim was NOT checked",
        true,
      ),
    );
  } else {
    checks.push(
      check(
        "data_identity",
        suppliedDigest === expected,
        `sha256(data)=${suppliedDigest} expected=${JSON.stringify(expected)}`,
      ),
    );
  }

  // --- reversibility ---------------------------------------------------------
  if (!applied) {
    checks.push(
      check(
        "reversibility_complete",
        true,
        "dry run: nothing was written, so there is nothing to reverse",
      ),
    );
  } else {
    const journal = predicate.journal;
    const txnId = isRecord(journal) ? journal.txn_id : undefined;
    const problems: string[] = [];
    if (predicate.reversible !== true) {
      problems.push("reversible is false for an applied run");
    }
    if (typeof txnId !== "string" || txnId.length === 0) {
      problems.push("journal.txn_id is missing");
    }
    if (typeof predicate.revert_command !== "string" || predicate.revert_command.length === 0) {
      problems.push("revert_command is missing");
    }
    checks.push(
      check(
        "reversibility_complete",
        problems.length === 0,
        problems.length === 0 ? "applied run is fully reversible" : `${problems}`,
      ),
    );
  }

  // --- verdicts --------------------------------------------------------------
  if (!isRecord(verdicts)) {
    checks.push(check("verdicts_accepting", false, "verdicts missing"));
  } else if (!applied) {
    checks.push(
      check(
        "verdicts_accepting",
        verdicts.safety !== "deny",
        `dry run: safety=${JSON.stringify(verdicts.safety)}`,
      ),
    );
  } else {
    checks.push(
      check(
        "verdicts_accepting",
        verdicts.verifier === "accept" && verdicts.safety === "allow",
        `verifier=${JSON.stringify(verdicts.verifier)} safety=${JSON.stringify(
          verdicts.safety,
        )}`,
      ),
    );
  }

  // --- strength and constraints ---------------------------------------------
  const authority = predicate.authority;
  const covered = new Set<string>(
    isRecord(authority) ? strings(authority.authoritative_columns) : [],
  );
  const constraints = isRecord(authority) ? authority.constraints : null;

  const unproven: string[] = [];
  let needsConstraints = false;
  for (const fix of records(predicate.fixes)) {
    const column = typeof fix.column === "string" ? fix.column : "";
    const recorded = fix.verification_strength;
    if (recorded === "plausibility_only") {
      unproven.push(`${column} (recorded plausibility_only)`);
      continue;
    }
    const onAuthority = covered.has(column);
    const derived = verificationStrengthFor(fix.provenance, onAuthority);
    if (derived !== "proven") {
      unproven.push(`${column}:${JSON.stringify(fix.provenance)} (recorded ${JSON.stringify(recorded)})`);
    } else if (!(typeof fix.provenance === "string" && TRUSTED_PROVENANCE.has(fix.provenance))) {
      needsConstraints = true;
    }
  }
  checks.push(
    check(
      "strength_is_earned",
      !(applied && unproven.length > 0),
      applied && unproven.length > 0
        ? `unproven applied writes: ${unproven}`
        : "every applied fix is proven by provenance or by column authority",
    ),
  );

  if (needsConstraints) {
    const hasConstraints = isRecord(constraints) && Object.keys(constraints).length > 0;
    checks.push(
      check(
        "constraints_present",
        hasConstraints,
        hasConstraints
          // Corrected 2026-09-16 alongside the Python detail string. This said the constraints
          // "support the schema-proven writes", which is not what is tested and cannot be: nothing
          // here compares `constraints` to anything. `authority_is_entailed` tests entailment.
          ? "a constraint payload is present (presence only -- see authority_is_entailed)"
          : "a write is proven only by schema authority, but no constraints are embedded",
      ),
    );
  } else {
    checks.push(check("constraints_present", true, "no write depends on schema authority"));
  }

  // --- authority_is_entailed ------------------------------------------------
  // The check that makes `strength_is_earned` mean something. That one derives every fix's strength
  // from membership in `authority.authoritative_columns` and therefore reads the claim as trusted
  // input -- so before this existed, a producer could publish any column list beside any premise and
  // pass all twelve preceding checks. This verifier ACCEPTED all five forgery vectors until it was
  // written, which is the strongest available evidence that the gap was real and not theoretical.
  //
  // The rule is SPEC section 6.4.2, and the two sets it needs are PROJECTED from the Python domain
  // vocabulary rather than restated here, so the two implementations cannot drift about which kinds
  // and which types confer authority. That projection was deliberately withheld from the browser
  // until this consumer existed; see the note in scripts/ci/generate_domain_vocabulary.py.
  const premise = isRecord(authority) ? authority.premise : null;
  checks.push(authorityIsEntailed(covered, premise));

  // --- entailment witness ---------------------------------------------------
  // NOT the same check as `strength_is_earned`. That one re-derives
  // `verification_strength` with the same rule the engine used to stamp it, so within one
  // implementation it validates field consistency rather than the rule -- a wrong trust model
  // is invisible to it, which is the axis `decimal_shift` lived on.
  //
  // A witness states arithmetic facts that can contradict each other. A fix claiming a write
  // whose own witness shows no strict majority is refused here regardless of provenance or
  // column authority, which is a rejection the strength check cannot express.
  //
  // Deliberately NOT recomputed from the data: that would make the normative verifier a CSV
  // parser and force two implementations to agree byte-for-byte on quoting, encodings and line
  // endings. Values are published as sha256(value)[:16], so the data check belongs to whoever
  // holds the table -- in SQL, in any language, with no DataForge code.
  const witnessFixes = records(predicate.fixes);
  const witnessProblems: string[] = [];
  let witnessed = 0;
  for (const fix of witnessFixes) {
    const witness = fix.witness;
    if (witness === undefined || witness === null) continue;
    const label = `${String(fix.column)}@${String(fix.row)}`;
    if (!isRecord(witness)) {
      witnessProblems.push(`${label}: witness is not an object`);
      continue;
    }
    witnessed += 1;

    const groupSize = witness.group_size;
    const support = witness.support;
    if (!Number.isInteger(groupSize) || !Number.isInteger(support)) {
      witnessProblems.push(`${label}: group_size and support must be integers`);
      continue;
    }
    const size = groupSize as number;
    const votes = support as number;
    if (size < 1 || votes < 1) {
      witnessProblems.push(`${label}: group_size=${size} support=${votes} must be >= 1`);
      continue;
    }
    if (votes > size) {
      witnessProblems.push(`${label}: support ${votes} exceeds group_size ${size}`);
      continue;
    }
    // The shipped decision rule is a STRICT majority, not a plurality.
    if (votes * 2 <= size) {
      witnessProblems.push(
        `${label}: support ${votes} of ${size} is not a strict majority, so the written ` +
          `value was not entailed by the rule the product implements`,
      );
      continue;
    }

    const entries = witness.value_digests;
    if (!Array.isArray(entries)) {
      witnessProblems.push(`${label}: value_digests must be a list`);
      continue;
    }
    const counts = new Map<string, number>();
    for (const entry of entries) {
      if (
        Array.isArray(entry) &&
        entry.length === 2 &&
        typeof entry[0] === "string" &&
        Number.isInteger(entry[1])
      ) {
        counts.set(entry[0], entry[1] as number);
      }
    }
    let total = 0;
    for (const value of counts.values()) total += value;
    if (total > size) {
      witnessProblems.push(`${label}: value counts exceed group_size ${size}`);
      continue;
    }
    if (witness.truncated !== true && total !== size) {
      witnessProblems.push(
        `${label}: value counts sum to ${total} but group_size is ${size} and the ` +
          `distribution is not marked truncated`,
      );
      continue;
    }

    const newDigest = witness.new_value_digest;
    const oldDigest = witness.old_value_digest;
    if (counts.get(String(newDigest)) !== votes) {
      witnessProblems.push(
        `${label}: the written value's recorded count does not equal its support`,
      );
      continue;
    }
    if (newDigest === oldDigest) {
      witnessProblems.push(`${label}: the write replaces a value with itself`);
      continue;
    }
    if (oldDigest !== undefined && oldDigest !== null && !counts.has(String(oldDigest))) {
      witnessProblems.push(`${label}: the replaced value does not appear in its own group`);
    }
  }

  if (witnessFixes.length === 0) {
    checks.push(
      check("witness_is_coherent", true, "no fixes, so there is no witness to check", true),
    );
  } else if (witnessProblems.length > 0) {
    checks.push(
      check(
        "witness_is_coherent",
        false,
        witnessProblems.slice(0, 5).join("; ") +
          (witnessProblems.length > 5 ? `; and ${witnessProblems.length - 5} more` : ""),
      ),
    );
  } else if (witnessed === 0) {
    checks.push(
      check(
        "witness_is_coherent",
        true,
        `no entailment witness on any of ${witnessFixes.length} fix(es); the derivation was NOT checked`,
        true,
      ),
    );
  } else {
    checks.push(
      check(
        "witness_is_coherent",
        true,
        `${witnessed} of ${witnessFixes.length} fix(es) carry a coherent entailment witness`,
      ),
    );
  }

  return finish();
}

/**
 * DSSE Pre-Authentication Encoding.
 *
 * `PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body`
 *
 * Lengths are byte lengths, so the type must be encoded before measuring.
 */
export function pae(payloadType: string, body: Uint8Array): Uint8Array {
  const encoder = new TextEncoder();
  const typeBytes = encoder.encode(payloadType);
  const prefix = encoder.encode(
    `DSSEv1 ${typeBytes.length} ${payloadType} ${body.length} `,
  );
  const out = new Uint8Array(prefix.length + body.length);
  out.set(prefix, 0);
  out.set(body, prefix.length);
  return out;
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  const out = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    out[index] = binary.charCodeAt(index);
  }
  return out;
}

export interface DsseResult {
  check: AttestationCheck;
  statement: unknown | null;
}

/**
 * Verify a DSSE envelope and return the statement parsed from the VERIFIED bytes.
 *
 * Async because Ed25519 lives behind WebCrypto. When no key is supplied the signature is
 * reported as `unsigned` and skipped -- never as verified, because absence of a key is not
 * evidence of authenticity.
 */
export async function verifyDsseSignature(
  envelope: unknown,
  publicKeyRaw: Uint8Array | null,
): Promise<DsseResult> {
  if (!isRecord(envelope)) {
    return { check: check("signature", false, "envelope is not an object"), statement: null };
  }
  const payload = envelope.payload;
  const payloadType = envelope.payloadType;
  if (typeof payload !== "string" || typeof payloadType !== "string") {
    return {
      check: check("signature", false, "envelope is missing payload fields"),
      statement: null,
    };
  }
  if (payloadType !== PAYLOAD_TYPE) {
    return {
      check: check("signature", false, `unexpected payloadType ${payloadType}`),
      statement: null,
    };
  }

  let body: Uint8Array;
  let statement: unknown;
  try {
    body = base64ToBytes(payload);
    statement = JSON.parse(new TextDecoder().decode(body));
  } catch {
    return { check: check("signature", false, "payload is not valid base64 JSON"), statement: null };
  }

  if (publicKeyRaw === null) {
    return {
      check: check(
        "signature",
        true,
        "unsigned: no public key supplied, so authenticity was NOT established",
        true,
      ),
      statement,
    };
  }

  const signatures = asArray(envelope.signatures).filter(isRecord);
  if (signatures.length === 0) {
    return { check: check("signature", false, "envelope carries no signatures"), statement: null };
  }

  const key = await crypto.subtle.importKey(
    "raw",
    publicKeyRaw as BufferSource,
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  const preauth = pae(PAYLOAD_TYPE, body);

  for (const entry of signatures) {
    if (typeof entry.sig !== "string") {
      continue;
    }
    let ok = false;
    try {
      ok = await crypto.subtle.verify(
        { name: "Ed25519" },
        key,
        base64ToBytes(entry.sig) as BufferSource,
        preauth as BufferSource,
      );
    } catch {
      ok = false;
    }
    if (ok) {
      return { check: check("signature", true, "DSSE signature verified"), statement };
    }
  }

  return {
    check: check("signature", false, "no signature verified against the key"),
    statement: null,
  };
}

/**
 * Verify either a bare Statement or a DSSE envelope.
 *
 * Composed so the synchronous normative core stays free of crypto: that core is the part
 * a third implementation would port first.
 */
/**
 * SHA-256 of raw bytes, as lowercase hex.
 *
 * Lives here rather than in `verifyStatement` because that core is deliberately synchronous and
 * crypto-free, and WebCrypto's digest is async. Until 2026-09-16 `verifyStatement` DECLARED a
 * `dataBytes` option and never read it, so a caller who passed bytes got `data_identity` silently
 * skipped while believing it had been checked -- the "quietly performs fewer checks, reports the
 * same ok" failure the specification's section 6.3 warns about, in the verifier itself.
 */
async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes as BufferSource);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function verifyAttestation(
  document: unknown,
  options: {
    dataBytes?: Uint8Array | null;
    dataSha256?: string | null;
    publicKeyRaw?: Uint8Array | null;
  } = {},
): Promise<AttestationVerification> {
  const identity = {
    dataSha256:
      options.dataSha256 ??
      (options.dataBytes ? await sha256Hex(options.dataBytes) : null),
  };
  if (isRecord(document) && "payload" in document && "payloadType" in document) {
    const { check: signatureCheck, statement } = await verifyDsseSignature(
      document,
      options.publicKeyRaw ?? null,
    );
    if (statement === null) {
      return {
        ok: false,
        checks: [signatureCheck],
        failures: [signatureCheck],
        skipped: [],
      };
    }
    const inner = verifyStatement(statement, identity);
    const checks = [signatureCheck, ...inner.checks];
    const failures = checks.filter((entry) => !entry.ok && !entry.skipped);
    return {
      ok: failures.length === 0,
      checks,
      failures,
      skipped: checks.filter((entry) => entry.skipped),
    };
  }
  return verifyStatement(document, identity);
}
