import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Clean-room verifier for dataforge.repair.attestation/v1.
 *
 * Implements ONLY the normative tier of SPEC_repair_attestation.md section 7.
 * The advisory tier (section 7, "Advisory") is out of scope by the specification's
 * own words: it "depends on z3, on infer_verification_schema, on two specific
 * checkers, and on DataForge's CSV round-trip".
 *
 * Every non-obvious reading of the specification is marked with a "SPEC-GAP" comment
 * naming the text that left the question open.
 */
public class Verify {

    // ---------------------------------------------------------------- constants

    /** SPEC 6.1, envelope example. */
    static final String T_STATEMENT = "https://in-toto.io/Statement/v1";
    /** SPEC 6.1, envelope example; also SPEC 2 "a stable predicateType URI". */
    static final String T_PREDICATE = "https://dataforge.dev/RepairAttestation/v1";
    /** SPEC 6.1, signed envelope example. */
    static final String T_PAYLOAD = "application/vnd.in-toto+json";
    /** SPEC 6.2 attestation_version type is the literal "1"; SPEC 7 check 2. */
    static final String VERSION = "1";

    /**
     * Closed sets the specification states INLINE, and can therefore be enforced
     * from this document alone.
     *   mode:                       SPEC 6.2 type column, "apply" | "dry_run"
     *   independent_verification:   SPEC 6.2 type column, "agreed" | "not_run"
     */
    static final Set<String> MODE_SET = set("apply", "dry_run");
    static final Set<String> INDEP_SET = set("agreed", "not_run");

    /**
     * SPEC-GAP (central). The five vocabularies Provenance, VerificationStrength,
     * ReviewReason, VerifierVerdict and SafetyVerdict are NOT in this document.
     * SPEC 6.2: "Vocabularies ... are exactly those in dataforge/domain/vocabulary.py,
     * published as enums in the JSON Schema ... They are not restated here."
     * Both of those sources are outside this document, so a reimplementation "from
     * this document alone" (SPEC 2, SPEC 7) cannot enumerate them.
     *
     * What follows is therefore NOT an enum. It is the set of tokens this document
     * itself attests to, gathered from SPEC 5, SPEC 6.2 notes, SPEC 7 and Appendix A.
     * Membership in these sets is positive evidence; NON-membership proves nothing,
     * and is reported as "skip", never as "pass" and never as "fail".
     */
    // Appendix A rows 2 and 3 ("external fix on a column in authoritative_columns"),
    // row 4 ("entity_consensus fix, no authority"), read with SPEC 5 ("a proven label
    // on an untrusted provenance is credited only on a covered column").
    static final Set<String> PROV_UNTRUSTED_ATTESTED = set("external", "entity_consensus");

    // SPEC 6.2 authority.authoritative_columns: "Empty means only a deterministic fix
    // can honestly be proven", and Appendix A row 1 "Deterministic fix, applied, no
    // schema | verifies; strength_is_earned passes on provenance alone".
    // SPEC-GAP: the document describes this class in PROSE and never gives its token.
    // "deterministic" is an inference from that prose, flagged in every detail string.
    static final Set<String> PROV_DETERMINISTIC_INFERRED = set("deterministic");

    // SPEC 7 check 9 ("a recorded plausibility_only is always believed"), check 10
    // ("a proven untrusted fix"), SPEC 5, SPEC 6.2, Appendix A rows 4 and 5.
    static final String STRENGTH_PROVEN = "proven";
    static final String STRENGTH_PLAUSIBILITY_ONLY = "plausibility_only";
    static final Set<String> STRENGTH_ATTESTED = set(STRENGTH_PROVEN, STRENGTH_PLAUSIBILITY_ONLY);

    // Appendix A row 6: provenance "some_future_corrector" must REJECT under
    // vocabulary_closed. The only non-member this document names.
    static final Set<String> PROV_EXCLUDED_ATTESTED = set("some_future_corrector");

    // SPEC 7 check 8: "verifier accept, safety allow". These are the only members of
    // VerifierVerdict / SafetyVerdict this document names.
    static final String VERDICT_ACCEPT = "accept";
    static final String VERDICT_ALLOW = "allow";

    static final String PASS = "pass";
    static final String FAIL = "fail";
    static final String SKIP = "skip";
    static final String UNSIGNED = "unsigned";

    static final Pattern HEX64 = Pattern.compile("^[0-9a-fA-F]{64}$");

    /**
     * RFC 3339 with the offset constrained to UTC, per SPEC 6.2 "produced_at | RFC 3339 UTC".
     * SPEC-GAP: RFC 3339 permits any numeric offset; the word "UTC" is read as requiring
     * the offset to DENOTE UTC, i.e. "Z" or "+00:00"/"-00:00".
     */
    static final Pattern RFC3339_UTC = Pattern.compile(
            "^(\\d{4})-(\\d{2})-(\\d{2})[Tt ](\\d{2}):(\\d{2}):(\\d{2})(\\.\\d+)?([Zz]|[+-]00:00)$");

    static Set<String> set(String... v) {
        return new LinkedHashSet<>(Arrays.asList(v));
    }

    // ------------------------------------------------------------------- checks

    static final class Check {
        final String name;
        String status;
        String detail;

        Check(String name) { this.name = name; }

        Check set(String status, String detail) {
            this.status = status;
            this.detail = detail;
            return this;
        }
    }

    /** fail dominates skip dominates pass, per SPEC 7 "MUST NOT collapse ... into one status". */
    static String worst(boolean anyFail, boolean anySkip) {
        return anyFail ? FAIL : (anySkip ? SKIP : PASS);
    }

    // --------------------------------------------------------------------- main

    public static void main(String[] argv) {
        PrintStream out = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out),
                true, StandardCharsets.UTF_8);
        PrintStream err = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.err),
                true, StandardCharsets.UTF_8);

        String attPath = null;
        String pubHex = null;
        String dataPath = null;

        for (int i = 0; i < argv.length; i++) {
            String a = argv[i];
            switch (a) {
                case "--attestation":
                    if (++i >= argv.length) { err.println("--attestation needs a value"); System.exit(2); }
                    attPath = argv[i];
                    break;
                case "--pubkey-hex":
                    if (++i >= argv.length) { err.println("--pubkey-hex needs a value"); System.exit(2); }
                    pubHex = argv[i];
                    break;
                case "--data":
                    if (++i >= argv.length) { err.println("--data needs a value"); System.exit(2); }
                    dataPath = argv[i];
                    break;
                default:
                    err.println("unknown argument: " + a);
                    System.exit(2);
            }
        }
        if (attPath == null) {
            err.println("usage: Verify --attestation <path> [--pubkey-hex <hex>] [--data <path>]");
            System.exit(2);
        }

        byte[] attBytes;
        try {
            attBytes = Files.readAllBytes(Paths.get(attPath));
        } catch (IOException e) {
            err.println("cannot read attestation: " + e.getMessage());
            System.exit(2);
            return;
        }

        byte[] dataBytes = null;
        if (dataPath != null) {
            try {
                dataBytes = Files.readAllBytes(Paths.get(dataPath));
            } catch (IOException e) {
                err.println("cannot read --data file: " + e.getMessage());
                System.exit(2);
                return;
            }
        }

        J root;
        try {
            root = Jp.parse(new String(attBytes, StandardCharsets.UTF_8));
        } catch (JsonException e) {
            err.println("attestation is not parseable JSON: " + e.getMessage());
            System.exit(2);
            return;
        }

        List<Check> checks = run(root, dataBytes, pubHex);

        boolean ok = true;
        for (Check c : checks) {
            if (FAIL.equals(c.status)) { ok = false; break; }
        }

        StringBuilder b = new StringBuilder();
        b.append("{\"ok\":").append(ok).append(",\"checks\":[");
        for (int i = 0; i < checks.size(); i++) {
            Check c = checks.get(i);
            if (i > 0) b.append(',');
            b.append("{\"name\":").append(jstr(c.name))
             .append(",\"status\":").append(jstr(c.status))
             .append(",\"detail\":").append(jstr(c.detail))
             .append('}');
        }
        b.append("]}");
        out.println(b);
        System.exit(0);
    }

    // ------------------------------------------------------------- orchestration

    static List<Check> run(J root, byte[] dataBytes, String pubHex) {
        // ---- envelope discrimination (SPEC 6.1: bare Statement, or DSSE envelope) ----
        boolean isDsse = false;
        String payloadB64 = null;
        String payloadType = null;
        J signatures = null;

        if (root.obj() != null && root.get("payload") != null && root.get("payload").str() != null
                && (root.has("payloadType") || root.has("signatures"))) {
            isDsse = true;
            payloadB64 = root.get("payload").str();
            J pt = root.get("payloadType");
            payloadType = (pt == null) ? null : pt.str();
            signatures = root.get("signatures");
        }

        J stmt = null;
        String stmtProblem = null;
        byte[] payloadBytes = null;

        if (isDsse) {
            payloadBytes = decodeB64(payloadB64);
            if (payloadBytes == null) {
                // SPEC-GAP: Appendix A row 8 ("payload byte flipped after signing") must
                // REJECT via `signature`, not crash, so an undecodable/unparseable payload
                // still yields a verdict rather than a non-zero exit.
                stmtProblem = "DSSE payload is not decodable base64; no statement to inspect";
            } else {
                try {
                    stmt = Jp.parse(new String(payloadBytes, StandardCharsets.UTF_8));
                } catch (JsonException e) {
                    stmtProblem = "DSSE payload does not decode to parseable JSON (" + e.getMessage() + ")";
                }
            }
            // SPEC 6.1: "Verifiers MUST NOT re-parse the envelope after signature
            // verification to obtain the payload." The statement used for checks 1..10 is
            // the one parsed from the decoded payload bytes above, never from the
            // enclosing envelope object.
        } else {
            stmt = root;
        }

        J pred = (stmt == null) ? null : stmt.get("predicate");

        List<Check> cs = new ArrayList<>();
        cs.add(cEnvelope(stmt, stmtProblem));
        cs.add(cVersion(pred, stmtProblem));
        cs.add(cSchema(stmt, stmtProblem));
        cs.add(cVocabulary(pred, stmtProblem));
        cs.add(cSubjectMatchesPost(stmt, stmtProblem));
        cs.add(cDataIdentity(stmt, dataBytes, stmtProblem));
        cs.add(cReversibility(pred, stmtProblem));
        cs.add(cVerdicts(pred, stmtProblem));
        cs.add(cStrengthIsEarned(pred, stmtProblem));
        cs.add(cConstraintsPresent(pred, stmtProblem));
        cs.add(cSignature(isDsse, payloadType, payloadBytes, signatures, pubHex));
        return cs;
    }

    // -------------------------------------------------- 1. envelope_recognised

    static Check cEnvelope(J stmt, String stmtProblem) {
        Check c = new Check("envelope_recognised");
        if (stmt == null) return c.set(FAIL, stmtProblem);
        String t = str(stmt, "_type");
        String pt = str(stmt, "predicateType");
        List<String> bad = new ArrayList<>();
        if (!T_STATEMENT.equals(t)) {
            bad.add("_type is " + show(t) + ", expected \"" + T_STATEMENT + "\"");
        }
        if (!T_PREDICATE.equals(pt)) {
            bad.add("predicateType is " + show(pt) + ", expected \"" + T_PREDICATE + "\"");
        }
        if (!bad.isEmpty()) return c.set(FAIL, String.join("; ", bad));
        return c.set(PASS, "_type and predicateType are exactly the expected URIs");
    }

    // ---------------------------------------------------- 2. version_recognised

    static Check cVersion(J pred, String stmtProblem) {
        Check c = new Check("version_recognised");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent, so attestation_version is absent");
        J v = pred.get("attestation_version");
        if (v == null) {
            // SPEC 2: "a missing required field ... is a REJECT".
            return c.set(FAIL, "attestation_version absent");
        }
        String s = v.str();
        if (s == null) {
            return c.set(FAIL, "attestation_version is a " + v.typeName() + ", expected the string \"1\"");
        }
        if (!VERSION.equals(s)) {
            // SPEC 6.2: "Unrecognised value is a REJECT, not a warning."
            return c.set(FAIL, "attestation_version is \"" + s + "\", expected \"1\"");
        }
        return c.set(PASS, "attestation_version is \"1\"");
    }

    // ------------------------------------------------------- 3. schema_complete

    static Check cSchema(J stmt, String stmtProblem) {
        Check c = new Check("schema_complete");
        if (stmt == null) return c.set(FAIL, stmtProblem);
        List<String> p = new ArrayList<>();

        // ---- statement level, from the SPEC 6.1 example. SPEC-GAP: the section 6.2
        // table covers the PREDICATE only; no table gives the statement's own required
        // fields. Read check 3 ("every required field present and well-typed") as
        // covering the envelope shown in 6.1 as well, since section 6.2 makes the
        // subject normative ("requiring every subject to name the artifact the
        // predicate describes").
        if (stmt.obj() == null) {
            return c.set(FAIL, "statement is a " + stmt.typeName() + ", expected an object");
        }
        reqString(p, stmt, "_type");
        reqString(p, stmt, "predicateType");
        J subj = stmt.get("subject");
        if (subj == null) {
            p.add("subject absent");
        } else if (subj.arr() == null) {
            p.add("subject is a " + subj.typeName() + ", expected an array");
        } else if (subj.arr().a.isEmpty()) {
            // SPEC-GAP: the document never states a minimum subject count. Read as >= 1
            // because checks 5 and 6 both compare against "the subject digest", and
            // because an attestation about nothing cannot "name the artifact".
            p.add("subject array is empty");
        } else {
            int i = 0;
            for (J s : subj.arr().a) {
                String w = "subject[" + i + "]";
                if (s.obj() == null) {
                    p.add(w + " is a " + s.typeName() + ", expected an object");
                } else {
                    // SPEC-GAP: `name` appears in the 6.1 example but is never marked
                    // required, and 6.1 says "Subjects are matched by digest, so a
                    // renamed file still verifies" -- so only the digest is enforced.
                    J nm = s.get("name");
                    if (nm != null && nm.str() == null) {
                        p.add(w + ".name is a " + nm.typeName() + ", expected a string");
                    }
                    reqHex64(p, s, "digest.sha256", w + ".digest.sha256");
                }
                i++;
            }
        }
        J pred = stmt.get("predicate");
        if (pred == null) {
            p.add("predicate absent");
            return c.set(FAIL, join(p));
        }
        if (pred.obj() == null) {
            p.add("predicate is a " + pred.typeName() + ", expected an object");
            return c.set(FAIL, join(p));
        }

        // ---- predicate level, SPEC 6.2 table, every row marked Required = yes ----
        reqString(p, pred, "attestation_version");
        reqString(p, pred, "tool.name");
        reqString(p, pred, "tool.version");
        reqString(p, pred, "tool.contract_version");
        // SPEC-GAP: tool.name Notes say `"dataforge"` but the Type column says "string",
        // whereas attestation_version's Type column is the literal "1". The table itself
        // distinguishes literal-typed from string-typed fields, so tool.name is treated
        // as an open string and its value is NOT enforced.

        J ts = pred.path("produced_at");
        if (ts == null) {
            p.add("produced_at absent");
        } else if (ts.str() == null) {
            p.add("produced_at is a " + ts.typeName() + ", expected a string");
        } else if (!isRfc3339Utc(ts.str())) {
            p.add("produced_at \"" + ts.str() + "\" is not an RFC 3339 UTC timestamp");
        }

        reqString(p, pred, "mode");   // membership is check 4's job
        Boolean applied = reqBool(p, pred, "applied");
        reqBool(p, pred, "reversible");
        reqHex64(p, pred, "source.digest.sha256", "source.digest.sha256");

        // SPEC 6.2: post.digest.sha256 Required = "when applied".
        boolean isApplied = Boolean.TRUE.equals(applied);
        if (isApplied) {
            reqHex64(p, pred, "post.digest.sha256", "post.digest.sha256");
        } else {
            J post = pred.path("post.digest.sha256");
            if (post != null && !post.isNull() && (post.str() == null || !HEX64.matcher(post.str()).matches())) {
                p.add("post.digest.sha256 present but not 64 hex characters");
            }
        }

        reqStringArray(p, pred, "authority.authoritative_columns");
        reqStringArray(p, pred, "authority.accepted_constraint_ids");
        // SPEC 6.2: "hex(64) | null", Required yes -> the key must exist, value may be null.
        // SPEC-GAP: the document does not say whether the intermediate object
        // `authority.constraints_digest` may itself be null instead of carrying a null
        // sha256. Both spellings are accepted as expressing the same "no digest" state.
        reqNullableHex64Path(p, pred, "authority", "constraints_digest", "sha256",
                "authority.constraints_digest.sha256");
        reqPresentObjectOrNull(p, pred, "authority.constraints");

        // ---- fixes[] ----
        J fixes = pred.get("fixes");
        if (fixes == null) {
            p.add("fixes absent");
        } else if (fixes.arr() == null) {
            p.add("fixes is a " + fixes.typeName() + ", expected an array");
        } else {
            int i = 0;
            for (J f : fixes.arr().a) {
                String w = "fixes[" + i + "]";
                if (f.obj() == null) {
                    p.add(w + " is a " + f.typeName() + ", expected an object");
                } else {
                    J row = f.get("row");
                    if (row == null) {
                        p.add(w + ".row absent");
                    } else if (!(row instanceof J.Num) || !((J.Num) row).isIntegral()) {
                        p.add(w + ".row is not an integer");
                    } else if (((J.Num) row).asLong() < 0) {
                        p.add(w + ".row is negative");
                    }
                    reqString(p, f, "column");
                    reqString(p, f, "provenance");
                    // SPEC 6.2: verification_strength is "**Not nullable.** Absent was
                    // previously read as proven." So absent and null are both failures.
                    J vs = f.get("verification_strength");
                    if (vs == null) {
                        p.add(w + ".verification_strength absent (spec: not nullable)");
                    } else if (vs.isNull()) {
                        p.add(w + ".verification_strength is null (spec: not nullable)");
                    } else if (vs.str() == null) {
                        p.add(w + ".verification_strength is a " + vs.typeName() + ", expected a string");
                    }
                    reqString(p, f, "detector_id");
                }
                i++;
            }
        }

        // ---- held[] ----
        J held = pred.get("held");
        if (held == null) {
            p.add("held absent");
        } else if (held.arr() == null) {
            p.add("held is a " + held.typeName() + ", expected an array");
        } else {
            int i = 0;
            for (J h : held.arr().a) {
                String w = "held[" + i + "]";
                if (h.obj() == null) {
                    p.add(w + " is a " + h.typeName() + ", expected an object");
                } else {
                    // SPEC 6.2: "Held proposals, each with a review_reason from the closed
                    // vocabulary." SPEC-GAP: no other member of a held entry is specified,
                    // so nothing else is required of it.
                    reqString(p, h, "review_reason");
                }
                i++;
            }
        }

        reqString(p, pred, "verdicts.verifier");
        reqString(p, pred, "verdicts.safety");
        reqString(p, pred, "verdicts.independent_verification");

        reqPresentStringOrNull(p, pred, "journal", "txn_id", "journal.txn_id");
        reqNullableHex64Member(p, pred, "journal", "head_sha256", "journal.head_sha256");

        // SPEC 6.2: revert_command "string | null", Required yes, "Required when applied".
        J rc = pred.get("revert_command");
        if (rc == null) {
            p.add("revert_command key absent");
        } else if (!rc.isNull() && rc.str() == null) {
            p.add("revert_command is a " + rc.typeName() + ", expected a string or null");
        }

        reqPresentObjectOrNull(p, pred, "model");
        reqStringArray(p, pred, "limitations");
        reqStringArray(p, pred, "verification.checks_available");

        // SPEC-GAP: SPEC 6.2 fixes[] Notes say "empty for a dry run", and mode is
        // "apply" | "dry_run", but section 7 defines NO check that enforces either that
        // emptiness or the agreement of `mode` with `applied`. Rather than fold a
        // cross-field rule into a check whose stated scope is "every required field
        // present and well-typed", it is reported here and not enforced.
        List<String> notes = new ArrayList<>();
        String mode = str(pred, "mode");
        if ("dry_run".equals(mode) && fixes != null && fixes.arr() != null && !fixes.arr().a.isEmpty()) {
            notes.add("note (not enforced: no section 7 check covers it): mode is \"dry_run\" but fixes[] has "
                    + fixes.arr().a.size() + " entries, against the 6.2 note \"empty for a dry run\"");
        }
        if (mode != null && applied != null
                && (("apply".equals(mode) && !applied) || ("dry_run".equals(mode) && applied))) {
            notes.add("note (not enforced: no section 7 check covers it): mode \"" + mode
                    + "\" disagrees with applied=" + applied);
        }

        if (!p.isEmpty()) {
            return c.set(FAIL, join(p) + (notes.isEmpty() ? "" : "; " + String.join("; ", notes)));
        }
        String d = "all required fields of the 6.2 table and the 6.1 envelope are present and well-typed";
        if (!notes.isEmpty()) d = d + "; " + String.join("; ", notes);
        return c.set(PASS, d);
    }

    // ------------------------------------------------------ 4. vocabulary_closed

    static Check cVocabulary(J pred, String stmtProblem) {
        Check c = new Check("vocabulary_closed");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent, so no enum value can be checked");

        List<String> fails = new ArrayList<>();
        List<String> unknowable = new ArrayList<>();

        // --- sets this document states inline, so they are enforced ---
        String mode = str(pred, "mode");
        if (mode == null) {
            fails.add("mode absent or not a string");
        } else if (!MODE_SET.contains(mode)) {
            fails.add("mode \"" + mode + "\" is not in {apply, dry_run} (6.2 type column)");
        }
        String indep = str(pred, "verdicts.independent_verification");
        if (indep == null) {
            fails.add("verdicts.independent_verification absent or not a string");
        } else if (!INDEP_SET.contains(indep)) {
            fails.add("verdicts.independent_verification \"" + indep
                    + "\" is not in {agreed, not_run} (6.2 type column)");
        }

        // --- the five vocabularies the document externalises ---
        J fixes = pred.get("fixes");
        if (fixes != null && fixes.arr() != null) {
            int i = 0;
            for (J f : fixes.arr().a) {
                String prov = str(f, "provenance");
                if (prov == null) {
                    fails.add("fixes[" + i + "].provenance absent or not a string");
                } else if (PROV_EXCLUDED_ATTESTED.contains(prov)) {
                    // Appendix A row 6, the one non-member this document names.
                    fails.add("fixes[" + i + "].provenance \"" + prov
                            + "\" is named by Appendix A as a REJECT under vocabulary_closed");
                } else if (!PROV_UNTRUSTED_ATTESTED.contains(prov)
                        && !PROV_DETERMINISTIC_INFERRED.contains(prov)) {
                    unknowable.add("fixes[" + i + "].provenance \"" + prov + "\"");
                }
                String vs = str(f, "verification_strength");
                if (vs == null) {
                    fails.add("fixes[" + i + "].verification_strength absent or not a string");
                } else if (!STRENGTH_ATTESTED.contains(vs)) {
                    unknowable.add("fixes[" + i + "].verification_strength \"" + vs + "\"");
                }
                i++;
            }
        }
        J held = pred.get("held");
        if (held != null && held.arr() != null) {
            int i = 0;
            for (J h : held.arr().a) {
                String rr = str(h, "review_reason");
                if (rr == null) {
                    fails.add("held[" + i + "].review_reason absent or not a string");
                } else {
                    // This document names ZERO members of ReviewReason.
                    unknowable.add("held[" + i + "].review_reason \"" + rr + "\"");
                }
                i++;
            }
        }
        String vv = str(pred, "verdicts.verifier");
        if (vv == null) {
            fails.add("verdicts.verifier absent or not a string");
        } else if (!VERDICT_ACCEPT.equals(vv)) {
            unknowable.add("verdicts.verifier \"" + vv + "\"");
        }
        String sv = str(pred, "verdicts.safety");
        if (sv == null) {
            fails.add("verdicts.safety absent or not a string");
        } else if (!VERDICT_ALLOW.equals(sv)) {
            unknowable.add("verdicts.safety \"" + sv + "\"");
        }

        String why = "SPEC 6.2 routes Provenance, VerificationStrength, ReviewReason, "
                + "VerifierVerdict and SafetyVerdict to dataforge/domain/vocabulary.py and to the "
                + "JSON Schema and does not restate them, so their closed sets are not derivable "
                + "from this document; unconfirmable values are reported skip, never pass";

        if (!fails.isEmpty()) {
            return c.set(FAIL, join(fails)
                    + (unknowable.isEmpty() ? "" : "; also unconfirmable: " + String.join(", ", unknowable)));
        }
        if (!unknowable.isEmpty()) {
            return c.set(SKIP, "cannot confirm membership of " + String.join(", ", unknowable) + " -- " + why);
        }
        return c.set(PASS, "mode and verdicts.independent_verification are in the sets stated inline in 6.2, "
                + "and every other enum value present is one this document itself attests to");
    }

    // --------------------------------------------- 5. subject_matches_post_state

    static Check cSubjectMatchesPost(J stmt, String stmtProblem) {
        Check c = new Check("subject_matches_post_state");
        if (stmt == null) return c.set(FAIL, stmtProblem);
        J pred = stmt.get("predicate");
        if (pred == null) return c.set(FAIL, "predicate object absent");
        Boolean applied = (pred.get("applied") == null) ? null : pred.get("applied").bool();
        if (applied == null) {
            return c.set(FAIL, "applied absent or not a boolean, so \"when applied\" cannot be decided");
        }
        if (!applied) {
            // SPEC 7 check 5 is qualified "when applied"; SPEC 6.1 says a dry run's subject
            // is "the unchanged source", so there is no post state to compare.
            return c.set(SKIP, "applied is false; the check is qualified \"when applied\" and 6.1 makes a "
                    + "dry run's subject the unchanged source");
        }
        String post = str(pred, "post.digest.sha256");
        if (post == null) {
            return c.set(FAIL, "applied is true but post.digest.sha256 is absent or not a string");
        }
        J subj = stmt.get("subject");
        if (subj == null || subj.arr() == null || subj.arr().a.isEmpty()) {
            return c.set(FAIL, "subject is absent or empty, so no subject digest can equal post.digest");
        }
        // SPEC 6.2: "requiring every subject to name the artifact the predicate describes".
        // SPEC-GAP: read as ALL subject entries, not "at least one". A single non-matching
        // entry would otherwise let an attestation vouch for an artifact it never verified.
        List<String> bad = new ArrayList<>();
        int i = 0;
        for (J s : subj.arr().a) {
            String d = str(s, "digest.sha256");
            if (d == null) {
                bad.add("subject[" + i + "].digest.sha256 absent or not a string");
            } else if (!d.equalsIgnoreCase(post)) {
                // SPEC-GAP: hex case is never specified; compared case-insensitively.
                bad.add("subject[" + i + "].digest.sha256 " + d + " != post.digest.sha256 " + post);
            }
            i++;
        }
        if (!bad.isEmpty()) return c.set(FAIL, join(bad));
        return c.set(PASS, "all " + subj.arr().a.size() + " subject digest(s) equal post.digest.sha256");
    }

    // ---------------------------------------------------------- 6. data_identity

    static Check cDataIdentity(J stmt, byte[] dataBytes, String stmtProblem) {
        Check c = new Check("data_identity");
        if (dataBytes == null) {
            return c.set(SKIP, "no artifact bytes supplied (--data omitted), so no digest can be recomputed");
        }
        if (stmt == null) return c.set(FAIL, stmtProblem);
        J subj = stmt.get("subject");
        if (subj == null || subj.arr() == null || subj.arr().a.isEmpty()) {
            return c.set(FAIL, "subject is absent or empty, so there is no expected digest");
        }
        String actual = sha256Hex(dataBytes);
        // SPEC-GAP: check 6 says "the expected digest", singular, but `subject` is an
        // array and the predicate also carries source/post digests. Read as the subject
        // digest, because 6.1 defines subject as the artifact the attestation is about
        // ("for an applied repair, the repaired bytes; for a dry run, the unchanged
        // source") and "Subjects are matched by digest".
        List<String> expected = new ArrayList<>();
        boolean matched = false;
        int i = 0;
        for (J s : subj.arr().a) {
            String d = str(s, "digest.sha256");
            if (d == null) {
                return c.set(FAIL, "subject[" + i + "].digest.sha256 absent or not a string");
            }
            expected.add(d);
            if (d.equalsIgnoreCase(actual)) matched = true;
            i++;
        }
        if (!matched) {
            return c.set(FAIL, "sha256 of supplied bytes is " + actual
                    + ", which equals no subject digest (" + String.join(", ", expected) + ")");
        }
        String extra = "";
        if (subj.arr().a.size() > 1) {
            // SPEC-GAP: with several subjects, "the expected digest" is undefined; any match accepted.
            extra = " (matched one of " + subj.arr().a.size()
                    + " subject digests; the spec says \"the expected digest\", singular)";
        }
        return c.set(PASS, "sha256 of supplied bytes equals the subject digest " + actual + extra);
    }

    // -------------------------------------------------- 7. reversibility_complete

    static Check cReversibility(J pred, String stmtProblem) {
        Check c = new Check("reversibility_complete");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent");
        J ap = pred.get("applied");
        Boolean applied = (ap == null) ? null : ap.bool();
        if (applied == null) {
            return c.set(FAIL, "applied absent or not a boolean, so the implication cannot be evaluated");
        }
        if (!applied) {
            // The implication "applied -> ..." is vacuously true, which is a genuine
            // evaluation, not a skip.
            return c.set(PASS, "applied is false; the implication applied -> "
                    + "(reversible, txn_id, revert_command) holds vacuously");
        }
        List<String> bad = new ArrayList<>();
        J rev = pred.get("reversible");
        if (rev == null || rev.bool() == null) {
            bad.add("reversible absent or not a boolean");
        } else if (!rev.bool()) {
            bad.add("applied is true but reversible is false");
        }
        J txn = pred.path("journal.txn_id");
        if (txn == null) {
            bad.add("journal.txn_id absent");
        } else if (txn.isNull()) {
            bad.add("applied is true but journal.txn_id is null");
        } else if (txn.str() == null) {
            bad.add("journal.txn_id is a " + txn.typeName() + ", expected a string");
        } else if (txn.str().trim().isEmpty()) {
            // SPEC-GAP: the document does not say whether an empty string counts as
            // present. Read as absent: an empty txn id identifies no transaction.
            bad.add("journal.txn_id is empty");
        }
        J rc = pred.get("revert_command");
        if (rc == null) {
            bad.add("revert_command absent");
        } else if (rc.isNull()) {
            bad.add("applied is true but revert_command is null (6.2: \"Required when applied\")");
        } else if (rc.str() == null) {
            bad.add("revert_command is a " + rc.typeName() + ", expected a string");
        } else if (rc.str().trim().isEmpty()) {
            bad.add("revert_command is empty");
        }
        // SPEC-GAP: check 7 names reversible, txn_id and revert_command only. 6.2 says
        // journal.head_sha256 "Binds the hash chain INTO the signed payload", but its type
        // is "hex(64) | null" and check 7 does not name it, so a null head is NOT failed here.
        String note = "";
        J head = pred.path("journal.head_sha256");
        if (head != null && head.isNull()) {
            note = "; note: journal.head_sha256 is null, which check 7 does not name and so does not fail";
        }
        if (!bad.isEmpty()) return c.set(FAIL, join(bad) + note);
        return c.set(PASS, "applied is true and reversible, journal.txn_id and revert_command are all present"
                + note);
    }

    // ------------------------------------------------------- 8. verdicts_accepting

    static Check cVerdicts(J pred, String stmtProblem) {
        Check c = new Check("verdicts_accepting");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent");
        List<String> bad = new ArrayList<>();
        String vv = str(pred, "verdicts.verifier");
        if (vv == null) {
            bad.add("verdicts.verifier absent or not a string");
        } else if (!VERDICT_ACCEPT.equals(vv)) {
            bad.add("verdicts.verifier is \"" + vv + "\", expected \"accept\"");
        }
        String sv = str(pred, "verdicts.safety");
        if (sv == null) {
            bad.add("verdicts.safety absent or not a string");
        } else if (!VERDICT_ALLOW.equals(sv)) {
            bad.add("verdicts.safety is \"" + sv + "\", expected \"allow\"");
        }
        // SPEC-GAP: check 8 names only verifier and safety. verdicts.independent_verification
        // may be "not_run" without failing, consistent with SPEC 3 putting re-execution out of scope.
        if (!bad.isEmpty()) return c.set(FAIL, join(bad));
        return c.set(PASS, "verdicts.verifier is \"accept\" and verdicts.safety is \"allow\"");
    }

    // ------------------------------------------------------ 9. strength_is_earned

    static Check cStrengthIsEarned(J pred, String stmtProblem) {
        Check c = new Check("strength_is_earned");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent");

        J ap = pred.get("applied");
        Boolean applied = (ap == null) ? null : ap.bool();
        Set<String> authoritative = lowerSet(pred.path("authority.authoritative_columns"));
        if (authoritative == null) {
            return c.set(FAIL, "authority.authoritative_columns absent or not an array of strings, so no "
                    + "column authority can be established");
        }
        J fixes = pred.get("fixes");
        if (fixes == null || fixes.arr() == null) {
            return c.set(FAIL, "fixes absent or not an array");
        }
        if (fixes.arr().a.isEmpty()) {
            return c.set(PASS, "fixes is empty (6.2: \"empty for a dry run\"), so no strength to earn");
        }

        List<String> fails = new ArrayList<>();
        List<String> unknowable = new ArrayList<>();
        int i = 0;
        for (J f : fixes.arr().a) {
            String w = "fixes[" + i + "]";
            String prov = str(f, "provenance");
            String col = str(f, "column");
            String vs = str(f, "verification_strength");
            i++;
            if (prov == null || col == null || vs == null) {
                fails.add(w + " lacks a string provenance, column or verification_strength");
                continue;
            }
            boolean covered = authoritative.contains(col.toLowerCase(Locale.ROOT));

            if (STRENGTH_PLAUSIBILITY_ONLY.equals(vs)) {
                // SPEC 7 check 9: "a recorded plausibility_only is always believed" --
                // i.e. it is taken at face value, never re-derived upward.
                // Appendix A row 5: "Any fix recorded plausibility_only | REJECT while applied".
                // SPEC-GAP: row 5 does not name the failing check; attributed here because
                // it is a statement about strength.
                if (Boolean.TRUE.equals(applied)) {
                    fails.add(w + " is recorded plausibility_only while applied is true "
                            + "(Appendix A: REJECT while applied)");
                }
                continue;
            }

            if (STRENGTH_PROVEN.equals(vs)) {
                if (PROV_DETERMINISTIC_INFERRED.contains(prov)) {
                    // Appendix A row 1: passes on provenance alone.
                    continue;
                }
                if (PROV_UNTRUSTED_ATTESTED.contains(prov)) {
                    // SPEC 5: "a proven label on an untrusted provenance is credited only on
                    // a covered column". Appendix A rows 2, 3 and 4.
                    if (!covered) {
                        fails.add(w + " provenance \"" + prov + "\" is untrusted and column \"" + col
                                + "\" is not in authority.authoritative_columns, so \"proven\" is not earned");
                    }
                    continue;
                }
                unknowable.add(w + " provenance \"" + prov
                        + "\" (this document never states its trust class, so \"proven\" can be neither "
                        + "derived nor refuted)");
                continue;
            }

            // A third strength tier may well exist; this document names only two.
            unknowable.add(w + " verification_strength \"" + vs
                    + "\" (this document names only \"proven\" and \"plausibility_only\", so this tier "
                    + "cannot be compared with a derived one)");
        }

        if (!fails.isEmpty()) {
            return c.set(FAIL, join(fails)
                    + (unknowable.isEmpty() ? "" : "; also unresolvable: " + String.join("; ", unknowable)));
        }
        if (!unknowable.isEmpty()) {
            return c.set(SKIP, "cannot derive strength for: " + String.join("; ", unknowable)
                    + " -- the Provenance and VerificationStrength vocabularies and their trust classes "
                    + "are not in this document");
        }
        return c.set(PASS, "every fix's recorded strength is earned by its provenance and the column's authority");
    }

    // ----------------------------------------------------- 10. constraints_present

    static Check cConstraintsPresent(J pred, String stmtProblem) {
        Check c = new Check("constraints_present");
        if (stmtProblem != null) return c.set(FAIL, stmtProblem);
        if (pred == null) return c.set(FAIL, "predicate object absent");
        J constraints = pred.path("authority.constraints");
        if (constraints == null) {
            return c.set(FAIL, "authority.constraints key absent (6.2 marks it Required, \"object | null\")");
        }
        boolean embedded = constraints.obj() != null;
        // SPEC-GAP: 6.2 says "object | null" and 6.3 says the field "carries the constraint
        // set itself". An empty object is treated as embedded-but-empty and accepted, since
        // the document sets no minimum content.
        J fixes = pred.get("fixes");
        if (fixes == null || fixes.arr() == null) {
            return c.set(FAIL, "fixes absent or not an array");
        }
        List<String> fails = new ArrayList<>();
        List<String> unknowable = new ArrayList<>();
        int i = 0;
        for (J f : fixes.arr().a) {
            String w = "fixes[" + i + "]";
            String prov = str(f, "provenance");
            String vs = str(f, "verification_strength");
            i++;
            if (prov == null || vs == null) continue; // reported by checks 3 and 9
            if (!STRENGTH_PROVEN.equals(vs)) continue;
            if (PROV_UNTRUSTED_ATTESTED.contains(prov)) {
                if (!embedded) {
                    fails.add(w + " is a \"proven\" fix with untrusted provenance \"" + prov
                            + "\" but authority.constraints is " + constraints.typeName()
                            + ", not an embedded constraint set");
                }
            } else if (!PROV_DETERMINISTIC_INFERRED.contains(prov)) {
                if (!embedded) {
                    unknowable.add(w + " provenance \"" + prov + "\" (trust class unknown, and "
                            + "authority.constraints is null, so the requirement can be neither "
                            + "applied nor dismissed)");
                }
            }
        }
        if (!fails.isEmpty()) {
            return c.set(FAIL, join(fails));
        }
        if (!unknowable.isEmpty()) {
            return c.set(SKIP, "cannot decide: " + String.join("; ", unknowable)
                    + " -- the Provenance vocabulary's trust classes are not in this document");
        }
        return c.set(PASS, embedded
                ? "authority.constraints embeds a constraint set, so any \"proven\" untrusted fix is covered"
                : "no \"proven\" untrusted fix requires embedded constraints");
    }

    // -------------------------------------------------------------- 11. signature

    static Check cSignature(boolean isDsse, String payloadType, byte[] payloadBytes,
                            J signatures, String pubHex) {
        Check c = new Check("signature");

        if (!isDsse) {
            // SPEC 2: "unsigned attestations reported as `unsigned` and never as authentic."
            return c.set(UNSIGNED, "the artifact is a bare in-toto Statement with no DSSE envelope, "
                    + "so there is no signature to verify and it is not authentic");
        }
        boolean haveSigs = signatures != null && signatures.arr() != null && !signatures.arr().a.isEmpty();
        if (!haveSigs) {
            // SPEC-GAP: a DSSE envelope with an absent or empty `signatures` array is never
            // described. Reported unsigned, matching "unsigned ... never as authentic".
            return c.set(UNSIGNED, "DSSE envelope carries no signatures, so it is not authentic");
        }
        if (pubHex == null) {
            // Appendix A row 9: "Signed, no public key supplied | signature reported
            // `unsigned`, overall not authentic".
            return c.set(UNSIGNED, "signed, but no public key was supplied, so authenticity cannot be "
                    + "established (Appendix A: reported unsigned, overall not authentic)");
        }
        String hex = pubHex.trim();
        if (hex.startsWith("0x") || hex.startsWith("0X")) hex = hex.substring(2);
        if (hex.length() != 64 || !hex.matches("[0-9a-fA-F]{64}")) {
            return c.set(FAIL, "--pubkey-hex is not 64 hex characters (32 raw Ed25519 public key bytes)");
        }
        if (payloadBytes == null) {
            return c.set(FAIL, "DSSE payload is not decodable base64, so no PAE preimage can be built");
        }
        if (payloadType == null) {
            // SPEC 4 defines the preimage as PAE(UTF8(PAYLOAD_TYPE), SERIALIZED_BODY); with
            // no payloadType there is no preimage. Fail closed.
            return c.set(FAIL, "DSSE envelope has no payloadType, so PAE(UTF8(PAYLOAD_TYPE), "
                    + "SERIALIZED_BODY) is undefined");
        }

        PublicKey pk;
        try {
            byte[] raw = hexBytes(hex);
            byte[] der = new byte[12 + 32];
            byte[] hdr = hexBytes("302a300506032b6570032100");
            System.arraycopy(hdr, 0, der, 0, 12);
            System.arraycopy(raw, 0, der, 12, 32);
            pk = KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(der));
        } catch (Exception e) {
            return c.set(FAIL, "supplied public key could not be loaded as Ed25519: " + e.getMessage());
        }

        byte[] pae = pae(payloadType, payloadBytes);
        List<String> tried = new ArrayList<>();
        int i = 0;
        for (J s : signatures.arr().a) {
            String w = "signatures[" + i + "]";
            i++;
            String sigB64 = str(s, "sig");
            if (sigB64 == null) {
                tried.add(w + " has no string \"sig\"");
                continue;
            }
            byte[] sig = decodeB64(sigB64);
            if (sig == null) {
                tried.add(w + ".sig is not decodable base64");
                continue;
            }
            try {
                Signature v = Signature.getInstance("Ed25519");
                v.initVerify(pk);
                v.update(pae);
                if (v.verify(sig)) {
                    String note = T_PAYLOAD.equals(payloadType) ? ""
                            : " (note: payloadType is \"" + payloadType + "\", not the \"" + T_PAYLOAD
                              + "\" of 6.1; PAE used the value as carried)";
                    String kid = str(s, "keyid");
                    return c.set(PASS, "DSSE Ed25519 signature " + w + " verifies over "
                            + "PAE(\"" + payloadType + "\", payload) with the supplied key"
                            + (kid == null ? "" : "; keyid " + kid) + note);
                }
                tried.add(w + " does not verify with the supplied key");
            } catch (Exception e) {
                tried.add(w + " verification error: " + e.getMessage());
            }
        }
        // SPEC-GAP: with several signatures the document says nothing about how many must
        // verify, nor whether `keyid` should select one. Every entry is tried and one
        // verifying signature is enough; none verifying is a REJECT (Appendix A rows 8, and
        // "A wrong-key signature REJECTS" in section 9).
        return c.set(FAIL, "no signature verifies against the supplied public key: " + String.join("; ", tried));
    }

    // ------------------------------------------------------------------- helpers

    /** DSSE PAE, SPEC 4: "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body. */
    static byte[] pae(String payloadType, byte[] body) {
        byte[] t = payloadType.getBytes(StandardCharsets.UTF_8);
        // SPEC-GAP: LEN() is never defined. Read as the octet length of the UTF-8 encoding,
        // rendered as ASCII decimal, which is what the cited DSSE protocol specifies.
        byte[] head = ("DSSEv1 " + t.length + " " + payloadType + " " + body.length + " ")
                .getBytes(StandardCharsets.UTF_8);
        byte[] all = new byte[head.length + body.length];
        System.arraycopy(head, 0, all, 0, head.length);
        System.arraycopy(body, 0, all, head.length, body.length);
        return all;
    }

    static byte[] decodeB64(String s) {
        // SPEC-GAP: 6.1 says base64 without naming an alphabet. Standard is tried first,
        // then MIME (tolerating line breaks), then URL-safe.
        try {
            return Base64.getDecoder().decode(s);
        } catch (IllegalArgumentException ignored) {
            // fall through
        }
        try {
            return Base64.getMimeDecoder().decode(s);
        } catch (IllegalArgumentException ignored) {
            // fall through
        }
        try {
            return Base64.getUrlDecoder().decode(s);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    static byte[] hexBytes(String hex) {
        byte[] b = new byte[hex.length() / 2];
        for (int i = 0; i < b.length; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }

    static String sha256Hex(byte[] data) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder b = new StringBuilder(64);
            for (byte x : d) b.append(String.format("%02x", x));
            return b.toString();
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    static boolean isRfc3339Utc(String s) {
        java.util.regex.Matcher m = RFC3339_UTC.matcher(s);
        if (!m.matches()) return false;
        int mo = Integer.parseInt(m.group(2));
        int da = Integer.parseInt(m.group(3));
        int ho = Integer.parseInt(m.group(4));
        int mi = Integer.parseInt(m.group(5));
        int se = Integer.parseInt(m.group(6));
        return mo >= 1 && mo <= 12 && da >= 1 && da <= 31 && ho <= 23 && mi <= 59 && se <= 60;
    }

    static String str(J node, String dotted) {
        if (node == null) return null;
        J v = node.path(dotted);
        return (v == null) ? null : v.str();
    }

    static Set<String> lowerSet(J arr) {
        if (arr == null || arr.arr() == null) return null;
        Set<String> out = new LinkedHashSet<>();
        for (J e : arr.arr().a) {
            if (e.str() == null) return null;
            // SPEC-GAP: the document never says whether column matching is case-sensitive.
            // Compared case-insensitively, matching the digest comparison.
            out.add(e.str().toLowerCase(Locale.ROOT));
        }
        return out;
    }

    static void reqString(List<String> p, J node, String dotted) {
        J v = node.path(dotted);
        if (v == null) {
            p.add(dotted + " absent");
        } else if (v.str() == null) {
            p.add(dotted + " is a " + v.typeName() + ", expected a string");
        }
    }

    static Boolean reqBool(List<String> p, J node, String dotted) {
        J v = node.path(dotted);
        if (v == null) {
            p.add(dotted + " absent");
            return null;
        }
        Boolean b = v.bool();
        if (b == null) p.add(dotted + " is a " + v.typeName() + ", expected a boolean");
        return b;
    }

    static void reqStringArray(List<String> p, J node, String dotted) {
        J v = node.path(dotted);
        if (v == null) {
            p.add(dotted + " absent");
            return;
        }
        if (v.arr() == null) {
            p.add(dotted + " is a " + v.typeName() + ", expected an array of strings");
            return;
        }
        int i = 0;
        for (J e : v.arr().a) {
            if (e.str() == null) p.add(dotted + "[" + i + "] is a " + e.typeName() + ", expected a string");
            i++;
        }
    }

    static void reqHex64(List<String> p, J node, String dotted, String label) {
        J v = node.path(dotted);
        if (v == null) {
            p.add(label + " absent");
        } else if (v.str() == null) {
            p.add(label + " is a " + v.typeName() + ", expected 64 hex characters");
        } else if (!HEX64.matcher(v.str()).matches()) {
            p.add(label + " is not 64 hex characters");
        }
    }

    /** Required key that may hold null, or hex(64). */
    static void reqNullableHex64Member(List<String> p, J node, String parent, String key, String label) {
        J par = node.path(parent);
        if (par == null) {
            p.add(parent + " absent, so " + label + " is absent");
            return;
        }
        if (par.isNull()) {
            p.add(parent + " is null, so the required key " + label + " is absent");
            return;
        }
        if (par.obj() == null) {
            p.add(parent + " is a " + par.typeName() + ", expected an object");
            return;
        }
        if (!par.has(key)) {
            p.add(label + " key absent");
            return;
        }
        J v = par.get(key);
        if (v.isNull()) return;
        if (v.str() == null) {
            p.add(label + " is a " + v.typeName() + ", expected 64 hex characters or null");
        } else if (!HEX64.matcher(v.str()).matches()) {
            p.add(label + " is not 64 hex characters");
        }
    }

    /** authority.constraints_digest.sha256: hex(64) | null, with the middle hop allowed to be null. */
    static void reqNullableHex64Path(List<String> p, J node, String a, String b, String key, String label) {
        J par = node.path(a);
        if (par == null || par.obj() == null) {
            p.add(a + " absent or not an object, so " + label + " is absent");
            return;
        }
        if (!par.has(b)) {
            p.add(label + " absent (" + a + "." + b + " key missing)");
            return;
        }
        J mid = par.get(b);
        if (mid.isNull()) return; // read as "no digest"
        if (mid.obj() == null) {
            p.add(a + "." + b + " is a " + mid.typeName() + ", expected an object or null");
            return;
        }
        if (!mid.has(key)) {
            p.add(label + " key absent");
            return;
        }
        J v = mid.get(key);
        if (v.isNull()) return;
        if (v.str() == null) {
            p.add(label + " is a " + v.typeName() + ", expected 64 hex characters or null");
        } else if (!HEX64.matcher(v.str()).matches()) {
            p.add(label + " is not 64 hex characters");
        }
    }

    static void reqPresentStringOrNull(List<String> p, J node, String parent, String key, String label) {
        J par = node.path(parent);
        if (par == null) {
            p.add(parent + " absent, so " + label + " is absent");
            return;
        }
        if (par.obj() == null) {
            p.add(parent + " is a " + par.typeName() + ", expected an object");
            return;
        }
        if (!par.has(key)) {
            p.add(label + " key absent");
            return;
        }
        J v = par.get(key);
        if (!v.isNull() && v.str() == null) {
            p.add(label + " is a " + v.typeName() + ", expected a string or null");
        }
    }

    static void reqPresentObjectOrNull(List<String> p, J node, String dotted) {
        int dot = dotted.lastIndexOf('.');
        J par = (dot < 0) ? node : node.path(dotted.substring(0, dot));
        String key = (dot < 0) ? dotted : dotted.substring(dot + 1);
        if (par == null || par.obj() == null) {
            p.add(dotted + " absent (parent missing or not an object)");
            return;
        }
        if (!par.has(key)) {
            p.add(dotted + " key absent");
            return;
        }
        J v = par.get(key);
        if (!v.isNull() && v.obj() == null) {
            p.add(dotted + " is a " + v.typeName() + ", expected an object or null");
        }
    }

    static String join(List<String> p) {
        return String.join("; ", p);
    }

    static String show(String s) {
        return (s == null) ? "absent or not a string" : "\"" + s + "\"";
    }

    static String jstr(String s) {
        if (s == null) return "\"\"";
        StringBuilder b = new StringBuilder(s.length() + 16);
        b.append('"');
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"':  b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\b': b.append("\\b");  break;
                case '\f': b.append("\\f");  break;
                case '\n': b.append("\\n");  break;
                case '\r': b.append("\\r");  break;
                case '\t': b.append("\\t");  break;
                default:
                    if (ch < 0x20 || ch == 0x7f) {
                        b.append(String.format("\\u%04x", (int) ch));
                    } else {
                        b.append(ch);
                    }
            }
        }
        b.append('"');
        return b.toString();
    }
}
