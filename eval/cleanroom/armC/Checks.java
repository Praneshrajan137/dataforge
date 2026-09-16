import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * The normative verification tier of SPEC_repair_attestation.md section 7.
 *
 * Twelve checks, reported individually, in the specification's order, on every
 * run. A check that cannot be evaluated is reported with a non-pass status; it
 * is never omitted and never folded into pass ("A verifier MUST NOT collapse
 * 'passed' and 'skipped' into one status, and MUST fail closed on anything
 * unrecognised" -- section 7, closing paragraph).
 *
 * Every closed vocabulary below is transcribed from the enums published in
 * repair_attestation.schema.json, which section 3.1 names as the artifact that
 * carries "every closed vocabulary". None is invented here.
 */
final class Checks {

    // ---------------------------------------------------------------- statuses
    static final String PASS = "pass";
    static final String FAIL = "fail";
    static final String SKIP = "skip";
    static final String UNSIGNED = "unsigned";

    /** One reported check. */
    static final class Check {
        final String name;
        final String status;
        final String detail;
        Check(String name, String status, String detail) {
            this.name = name; this.status = status; this.detail = detail;
        }
    }

    // ------------------------------------------------- expected constant URIs
    // SPEC 6.1 and the schema's "const" keywords.
    static final String EXPECTED_TYPE = "https://in-toto.io/Statement/v1";
    static final String EXPECTED_PREDICATE_TYPE = "https://dataforge.dev/RepairAttestation/v1";
    static final String EXPECTED_VERSION = "1";

    // -------------------------------------------------- closed vocabularies
    // Transcribed from the JSON Schema enums. Section 7.4 counts seven.
    static final Set<String> PROVENANCE = set(
            "deterministic", "entity_consensus", "external", "llm_cache", "llm_live");
    static final Set<String> VERIFICATION_STRENGTH = set(
            "plausibility_only", "proven");
    static final Set<String> REVIEW_REASON = set(
            "ambiguous_fd", "failed_conformal_threshold", "floor_cannot_verify",
            "inferred_fd_not_declared", "invalid_target", "mined_constraint_not_declared",
            "not_inferable_from_data", "out_of_inferred_domain", "safety_denied",
            "safety_escalation", "stale_precondition", "unverified_entity_consensus",
            "unverified_transposition", "verifier_rejected");
    static final Set<String> VERIFIER_VERDICT = set("accept", "not_run", "reject", "unknown");
    static final Set<String> SAFETY_VERDICT = set("allow", "deny", "escalate");
    static final Set<String> INDEPENDENT_VERIFICATION = set("agreed", "not_run");
    static final Set<String> MODE = set("apply", "dry_run");

    /** SPEC 7.9: the published derivation's trusted set. */
    static final Set<String> TRUSTED_PROVENANCE = set("deterministic");

    private static Set<String> set(String... values) {
        return new LinkedHashSet<>(Arrays.asList(values));
    }

    // ------------------------------------------------------------------ inputs
    private final JVal statement;        // decoded in-toto statement, or null
    private final String statementError; // why it is null
    private final boolean isEnvelope;    // document is a DSSE envelope
    private final JVal envelope;         // the envelope object, or null
    private final byte[] payloadBytes;   // the bytes the signature covers, or null
    private final byte[] pubkeyRaw;      // 32 raw Ed25519 bytes, or null
    private final byte[] dataBytes;      // supplied artifact bytes, or null
    private final String dataPath;

    Checks(JVal statement, String statementError, boolean isEnvelope, JVal envelope,
           byte[] payloadBytes, byte[] pubkeyRaw, byte[] dataBytes, String dataPath) {
        this.statement = statement;
        this.statementError = statementError;
        this.isEnvelope = isEnvelope;
        this.envelope = envelope;
        this.payloadBytes = payloadBytes;
        this.pubkeyRaw = pubkeyRaw;
        this.dataBytes = dataBytes;
        this.dataPath = dataPath;
    }

    // ------------------------------------------------------- derived shortcuts
    private JVal predicate() {
        if (statement == null || !statement.isObj()) return null;
        JVal p = statement.get("predicate");
        return (p != null && p.isObj()) ? p : null;
    }

    private JVal authority() {
        JVal pred = predicate();
        if (pred == null) return null;
        JVal a = pred.get("authority");
        return (a != null && a.isObj()) ? a : null;
    }

    /** True only when predicate.applied is the boolean true. */
    private boolean appliedIsTrue() {
        JVal pred = predicate();
        if (pred == null) return false;
        JVal a = pred.get("applied");
        return a != null && a.isBool() && a.bool;
    }

    private boolean appliedIsDeterminable() {
        JVal pred = predicate();
        if (pred == null) return false;
        JVal a = pred.get("applied");
        return a != null && a.isBool();
    }

    /** The digest checks 5 and 6 both expect, or null with a reason. */
    private static final class Expected {
        String sha256;
        String field;
        String problem;
    }

    private Expected expected() {
        Expected e = new Expected();
        JVal pred = predicate();
        if (pred == null) {
            e.problem = "predicate is unavailable, so no expected digest can be resolved";
            return e;
        }
        if (!appliedIsDeterminable()) {
            e.problem = "predicate.applied is absent or not a boolean, "
                      + "so it is undeterminable whether post.digest or source.digest is expected";
            return e;
        }
        String key = appliedIsTrue() ? "post" : "source";
        e.field = "predicate." + key + ".digest.sha256";
        JVal holder = pred.get(key);
        if (holder == null || holder.isNull()) {
            e.problem = "predicate.applied is " + appliedIsTrue()
                      + " so predicate." + key + " carries the expected digest, but it is "
                      + (holder == null ? "absent" : "null");
            return e;
        }
        if (!holder.isObj()) {
            e.problem = e.field + " is unavailable: predicate." + key + " is " + holder.typeName();
            return e;
        }
        JVal dig = holder.get("digest");
        if (dig == null || !dig.isObj()) {
            e.problem = e.field + " is unavailable: digest is "
                      + (dig == null ? "absent" : dig.typeName());
            return e;
        }
        JVal sha = dig.get("sha256");
        if (sha == null || !sha.isStr()) {
            e.problem = e.field + " is " + (sha == null ? "absent" : sha.typeName())
                      + ", expected a string";
            return e;
        }
        e.sha256 = sha.str;
        return e;
    }

    private Set<String> authoritativeColumns() {
        Set<String> out = new LinkedHashSet<>();
        JVal auth = authority();
        if (auth == null) return out;
        JVal cols = auth.get("authoritative_columns");
        if (cols == null || !cols.isArr()) return out;
        for (JVal c : cols.arr) if (c.isStr()) out.add(c.str);
        return out;
    }

    private List<JVal> fixes() {
        List<JVal> out = new ArrayList<>();
        JVal pred = predicate();
        if (pred == null) return out;
        JVal f = pred.get("fixes");
        if (f == null || !f.isArr()) return out;
        out.addAll(f.arr);
        return out;
    }

    /** SPEC 7.9's published derivation. */
    private String derived(JVal fix, Set<String> authCols) {
        JVal prov = fix.get("provenance");
        JVal col = fix.get("column");
        boolean trusted = prov != null && prov.isStr() && TRUSTED_PROVENANCE.contains(prov.str);
        boolean authoritative = col != null && col.isStr() && authCols.contains(col.str);
        return (trusted || authoritative) ? "proven" : "plausibility_only";
    }

    private boolean provenanceIsTrusted(JVal fix) {
        JVal prov = fix.get("provenance");
        return prov != null && prov.isStr() && TRUSTED_PROVENANCE.contains(prov.str);
    }

    /** SPEC 7.9's definition of "unproven". */
    private boolean unproven(JVal fix, Set<String> authCols) {
        JVal rec = fix.get("verification_strength");
        boolean recordedDowngrade = rec != null && rec.isStr() && "plausibility_only".equals(rec.str);
        return recordedDowngrade || !"proven".equals(derived(fix, authCols));
    }

    // ------------------------------------------------------------------ runner
    List<Check> run() {
        List<Check> out = new ArrayList<>();
        out.add(envelopeRecognised());
        out.add(versionRecognised());
        out.add(schemaComplete());
        out.add(vocabularyClosed());
        out.add(subjectMatchesPostState());
        out.add(dataIdentity());
        out.add(reversibilityComplete());
        out.add(verdictsAccepting());
        out.add(strengthIsEarned());
        out.add(constraintsPresent());
        out.add(signature());
        out.add(witnessIsCoherent());
        return out;
    }

    // --------------------------------------------------- 1 envelope_recognised
    private Check envelopeRecognised() {
        String name = "envelope_recognised";
        if (statement == null) {
            return new Check(name, FAIL, "no in-toto statement to inspect: " + statementError);
        }
        if (!statement.isObj()) {
            return new Check(name, FAIL, "statement is " + statement.typeName() + ", expected object");
        }
        List<String> problems = new ArrayList<>();
        JVal t = statement.get("_type");
        if (t == null || !t.isStr() || !EXPECTED_TYPE.equals(t.str)) {
            problems.add("_type is " + render(t) + ", expected \"" + EXPECTED_TYPE + "\"");
        }
        JVal pt = statement.get("predicateType");
        if (pt == null || !pt.isStr() || !EXPECTED_PREDICATE_TYPE.equals(pt.str)) {
            problems.add("predicateType is " + render(pt)
                    + ", expected \"" + EXPECTED_PREDICATE_TYPE + "\"");
        }
        if (problems.isEmpty()) {
            return new Check(name, PASS, "_type and predicateType are the expected URIs");
        }
        return new Check(name, FAIL, join(problems));
    }

    // ---------------------------------------------------- 2 version_recognised
    private Check versionRecognised() {
        String name = "version_recognised";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL, "predicate is unavailable, so attestation_version "
                    + "cannot be read; an unrecognised version is a REJECT (SPEC 6.2)");
        }
        JVal v = pred.get("attestation_version");
        if (v != null && v.isStr() && EXPECTED_VERSION.equals(v.str)) {
            return new Check(name, PASS, "attestation_version is \"1\"");
        }
        return new Check(name, FAIL, "attestation_version is " + render(v)
                + ", expected \"" + EXPECTED_VERSION + "\"; unrecognised is a REJECT, not a warning");
    }

    // ------------------------------------------------------- 3 schema_complete
    private Check schemaComplete() {
        String name = "schema_complete";
        List<String> p = new ArrayList<>();
        if (statement == null || !statement.isObj()) {
            return new Check(name, FAIL, "no statement object to validate: "
                    + (statementError == null ? "statement is not an object" : statementError));
        }
        JVal pred = statement.get("predicate");
        if (pred == null) {
            return new Check(name, FAIL, "predicate is missing");
        }
        if (!pred.isObj()) {
            return new Check(name, FAIL, "predicate is " + pred.typeName() + ", expected object");
        }

        // predicate.required, minus the enum-bearing fields section 7.4 reserves
        // for vocabulary_closed ("A missing or null value is also a REJECT here,
        // not under schema_complete").
        JVal tool = needObject(pred, "predicate", "tool", p);
        if (tool != null) {
            needString(tool, "predicate.tool", "name", 1, p);
            needString(tool, "predicate.tool", "version", 1, p);
        }
        needString(pred, "predicate", "produced_at", 0, p);
        needBool(pred, "predicate", "applied", p);
        needBool(pred, "predicate", "reversible", p);

        JVal source = needObject(pred, "predicate", "source", p);
        if (source != null) {
            JVal dig = needObject(source, "predicate.source", "digest", p);
            if (dig != null) needHex64(dig, "predicate.source.digest", "sha256", p);
        }

        JVal auth = needObject(pred, "predicate", "authority", p);
        if (auth != null) {
            needStringArray(auth, "predicate.authority", "authoritative_columns", p);
            needStringArray(auth, "predicate.authority", "accepted_constraint_ids", p);
        }

        JVal fixes = needArray(pred, "predicate", "fixes", p);
        if (fixes != null) {
            for (int i = 0; i < fixes.arr.size(); i++) {
                JVal f = fixes.arr.get(i);
                String path = "predicate.fixes[" + i + "]";
                if (!f.isObj()) {
                    p.add(path + " is " + f.typeName() + ", expected object");
                    continue;
                }
                JVal row = f.get("row");
                if (row == null) p.add(path + ".row is missing");
                else if (!row.isInt()) p.add(path + ".row is " + row.typeName() + ", expected integer");
                else if (row.num < 0) p.add(path + ".row is " + fmt(row.num) + ", expected >= 0");
                needString(f, path, "column", 1, p);
                // provenance and verification_strength: owned by vocabulary_closed.
            }
        }

        JVal held = needArray(pred, "predicate", "held", p);
        if (held != null) {
            for (int i = 0; i < held.arr.size(); i++) {
                JVal h = held.arr.get(i);
                if (!h.isObj()) {
                    p.add("predicate.held[" + i + "] is " + h.typeName() + ", expected object");
                }
            }
        }

        needObject(pred, "predicate", "verdicts", p);
        needObject(pred, "predicate", "journal", p);
        needStringArray(pred, "predicate", "limitations", p);

        if (p.isEmpty()) {
            return new Check(name, PASS,
                    "predicate.required, tool.required, authority.required and fixes.items.required "
                    + "are all present and well-typed");
        }
        return new Check(name, FAIL, join(p));
    }

    // ------------------------------------------------------ 4 vocabulary_closed
    private Check vocabularyClosed() {
        String name = "vocabulary_closed";
        List<String> p = new ArrayList<>();
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL,
                    "predicate is unavailable, so none of the seven closed vocabularies can be read");
        }

        checkEnum("predicate.mode", pred.get("mode"), MODE, p);

        JVal fixes = pred.get("fixes");
        if (fixes != null && fixes.isArr()) {
            for (int i = 0; i < fixes.arr.size(); i++) {
                JVal f = fixes.arr.get(i);
                if (!f.isObj()) continue; // shape is schema_complete's business
                String path = "predicate.fixes[" + i + "]";
                checkEnum(path + ".provenance", f.get("provenance"), PROVENANCE, p);
                checkEnum(path + ".verification_strength",
                        f.get("verification_strength"), VERIFICATION_STRENGTH, p);
            }
        }

        JVal held = pred.get("held");
        if (held != null && held.isArr()) {
            for (int i = 0; i < held.arr.size(); i++) {
                JVal h = held.arr.get(i);
                if (!h.isObj()) continue;
                checkEnum("predicate.held[" + i + "].review_reason",
                        h.get("review_reason"), REVIEW_REASON, p);
            }
        }

        JVal verdicts = pred.get("verdicts");
        JVal vv = null, vs = null, vi = null;
        if (verdicts != null && verdicts.isObj()) {
            vv = verdicts.get("verifier");
            vs = verdicts.get("safety");
            vi = verdicts.get("independent_verification");
        }
        checkEnum("predicate.verdicts.verifier", vv, VERIFIER_VERDICT, p);
        checkEnum("predicate.verdicts.safety", vs, SAFETY_VERDICT, p);
        checkEnum("predicate.verdicts.independent_verification", vi, INDEPENDENT_VERIFICATION, p);

        if (p.isEmpty()) {
            return new Check(name, PASS,
                    "every value in the seven closed vocabularies is a published member");
        }
        return new Check(name, FAIL, join(p));
    }

    private void checkEnum(String path, JVal v, Set<String> allowed, List<String> problems) {
        if (v == null) {
            problems.add(path + " is absent; absent is not a member of " + show(allowed));
        } else if (v.isNull()) {
            problems.add(path + " is null; null is not a member of " + show(allowed));
        } else if (!v.isStr()) {
            problems.add(path + " is " + v.typeName() + "; expected a string member of " + show(allowed));
        } else if (!allowed.contains(v.str)) {
            problems.add(path + " = \"" + v.str + "\" is not a member of " + show(allowed));
        }
    }

    // -------------------------------------------- 5 subject_matches_post_state
    private Check subjectMatchesPostState() {
        String name = "subject_matches_post_state";
        if (statement == null || !statement.isObj()) {
            return new Check(name, FAIL, "no statement object, so subject cannot be read");
        }
        Expected exp = expected();
        if (exp.sha256 == null) {
            return new Check(name, FAIL, exp.problem);
        }
        JVal subject = statement.get("subject");
        if (subject == null) {
            return new Check(name, FAIL, "subject is missing; at least one subject is required");
        }
        if (!subject.isArr()) {
            return new Check(name, FAIL, "subject is " + subject.typeName() + ", expected array");
        }
        if (subject.arr.isEmpty()) {
            return new Check(name, FAIL, "subject is empty; at least one subject is required");
        }
        List<String> p = new ArrayList<>();
        for (int i = 0; i < subject.arr.size(); i++) {
            JVal s = subject.arr.get(i);
            String path = "subject[" + i + "]";
            if (!s.isObj()) { p.add(path + " is " + s.typeName() + ", expected object"); continue; }
            JVal dig = s.get("digest");
            if (dig == null || !dig.isObj()) {
                p.add(path + ".digest is " + (dig == null ? "absent" : dig.typeName()));
                continue;
            }
            JVal sha = dig.get("sha256");
            if (sha == null || !sha.isStr()) {
                p.add(path + ".digest.sha256 is " + (sha == null ? "absent" : sha.typeName()));
                continue;
            }
            if (!exp.sha256.equals(sha.str)) {
                p.add(path + ".digest.sha256 = " + abbrev(sha.str)
                        + " names a different artifact than " + exp.field + " = " + abbrev(exp.sha256));
            }
        }
        if (p.isEmpty()) {
            return new Check(name, PASS, "all " + subject.arr.size()
                    + " subject entries carry " + exp.field + " = " + abbrev(exp.sha256));
        }
        return new Check(name, FAIL, join(p));
    }

    // ---------------------------------------------------------- 6 data_identity
    private Check dataIdentity() {
        String name = "data_identity";
        if (dataBytes == null) {
            return new Check(name, SKIP, "no artifact bytes supplied (--data absent), "
                    + "so the attested digest cannot be compared against data");
        }
        Expected exp = expected();
        if (exp.sha256 == null) {
            return new Check(name, FAIL, "bytes were supplied but there is nothing to compare them to: "
                    + exp.problem);
        }
        String actual;
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            actual = Dsse.bytesToHex(md.digest(dataBytes));
        } catch (Exception e) {
            return new Check(name, FAIL, "SHA-256 unavailable: " + e);
        }
        if (actual.equals(exp.sha256)) {
            return new Check(name, PASS, "sha256(" + dataPath + ") = " + abbrev(actual)
                    + " equals " + exp.field);
        }
        return new Check(name, FAIL, "sha256(" + dataPath + ") = " + abbrev(actual)
                + " does not equal " + exp.field + " = " + abbrev(exp.sha256));
    }

    // ------------------------------------------------- 7 reversibility_complete
    private Check reversibilityComplete() {
        String name = "reversibility_complete";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL, "predicate is unavailable, so reversibility cannot be established");
        }
        if (!appliedIsTrue()) {
            return new Check(name, PASS, "predicate.applied is not true; "
                    + "nothing was written, so no revert path is required");
        }
        List<String> p = new ArrayList<>();
        JVal rev = pred.get("reversible");
        if (rev == null || !rev.isBool() || !rev.bool) {
            p.add("applied is true but reversible is " + render(rev) + ", expected true");
        }
        JVal journal = pred.get("journal");
        JVal txn = (journal != null && journal.isObj()) ? journal.get("txn_id") : null;
        if (txn == null || !txn.isStr() || txn.str.isEmpty()) {
            p.add("applied is true but journal.txn_id is " + render(txn)
                    + ", expected a non-empty string");
        }
        JVal revert = pred.get("revert_command");
        if (revert == null || !revert.isStr() || revert.str.isEmpty()) {
            p.add("applied is true but revert_command is " + render(revert)
                    + ", expected a non-empty string");
        }
        if (p.isEmpty()) {
            return new Check(name, PASS,
                    "applied implies reversible, journal.txn_id and revert_command, all present "
                    + "(journal.head_sha256 is deliberately not required by this check, SPEC 7.7)");
        }
        return new Check(name, FAIL, join(p));
    }

    // ----------------------------------------------------- 8 verdicts_accepting
    private Check verdictsAccepting() {
        String name = "verdicts_accepting";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL, "predicate is unavailable, so verdicts cannot be read");
        }
        JVal verdicts = pred.get("verdicts");
        JVal vv = (verdicts != null && verdicts.isObj()) ? verdicts.get("verifier") : null;
        JVal vs = (verdicts != null && verdicts.isObj()) ? verdicts.get("safety") : null;
        String safety = (vs != null && vs.isStr()) ? vs.str : null;

        if (appliedIsTrue()) {
            List<String> p = new ArrayList<>();
            String verifier = (vv != null && vv.isStr()) ? vv.str : null;
            if (!"accept".equals(verifier)) {
                p.add("applied is true so verdicts.verifier must be \"accept\", but it is " + render(vv));
            }
            if (!"allow".equals(safety)) {
                p.add("applied is true so verdicts.safety must be \"allow\", but it is " + render(vs));
            }
            if (p.isEmpty()) {
                return new Check(name, PASS,
                        "applied branch: verdicts.verifier is \"accept\" and verdicts.safety is \"allow\"");
            }
            return new Check(name, FAIL, join(p));
        }

        // Not applied: safety must not be deny, and the verifier verdict is not
        // consulted at all, because a dry run reaches no verifier (SPEC 7.8).
        if (safety == null) {
            return new Check(name, FAIL, "not-applied branch: verdicts.safety is " + render(vs)
                    + ", so it cannot be established that safety is not \"deny\"");
        }
        if ("deny".equals(safety)) {
            return new Check(name, FAIL, "not-applied branch: verdicts.safety is \"deny\"");
        }
        return new Check(name, PASS, "not-applied branch: verdicts.safety is \"" + safety
                + "\", which is not \"deny\"; the verifier verdict is not consulted (SPEC 7.8)");
    }

    // ----------------------------------------------------- 9 strength_is_earned
    private Check strengthIsEarned() {
        String name = "strength_is_earned";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL, "predicate is unavailable, so no strength can be re-derived");
        }
        if (!appliedIsTrue()) {
            return new Check(name, PASS, "predicate.applied is not true; "
                    + "nothing was written, so this check passes (SPEC 7.9)");
        }
        Set<String> authCols = authoritativeColumns();
        List<JVal> fixes = fixes();
        List<String> p = new ArrayList<>();
        for (int i = 0; i < fixes.size(); i++) {
            JVal f = fixes.get(i);
            if (!f.isObj()) continue;
            if (!unproven(f, authCols)) continue;
            JVal rec = f.get("verification_strength");
            JVal prov = f.get("provenance");
            JVal col = f.get("column");
            String d = derived(f, authCols);
            p.add("fixes[" + i + "] (provenance " + render(prov) + ", column " + render(col)
                    + ", recorded " + render(rec) + ") is unproven: derived strength is \"" + d + "\"");
        }
        if (p.isEmpty()) {
            return new Check(name, PASS, "applied, and all " + fixes.size()
                    + " fixes are proven under the SPEC 7.9 derivation");
        }
        return new Check(name, FAIL, join(p));
    }

    // ---------------------------------------------------- 10 constraints_present
    private Check constraintsPresent() {
        String name = "constraints_present";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL, "predicate is unavailable, so authority.constraints "
                    + "cannot be examined");
        }
        Set<String> authCols = authoritativeColumns();
        boolean applied = appliedIsTrue();
        List<String> requiring = new ArrayList<>();
        List<JVal> fixes = fixes();
        for (int i = 0; i < fixes.size(); i++) {
            JVal f = fixes.get(i);
            if (!f.isObj()) continue;
            // Conditioned on the DERIVED strength, never on the recorded label
            // (SPEC 7.10).
            boolean earnedByAuthorityAlone =
                    "proven".equals(derived(f, authCols)) && !provenanceIsTrusted(f);
            if (!earnedByAuthorityAlone) continue;
            // A fix that already fails check 9 is not reported twice (SPEC 7.10).
            if (applied && unproven(f, authCols)) continue;
            requiring.add("fixes[" + i + "]");
        }
        if (requiring.isEmpty()) {
            return new Check(name, PASS, "no fix earns \"proven\" through column authority alone, "
                    + "so embedded constraints are not required");
        }
        JVal auth = authority();
        JVal constraints = (auth == null) ? null : auth.get("constraints");
        if (nonEmpty(constraints)) {
            return new Check(name, PASS, requiring.size()
                    + " fix(es) earn \"proven\" through column authority alone ("
                    + joinShort(requiring) + ") and authority.constraints is embedded and non-empty");
        }
        return new Check(name, FAIL, requiring.size()
                + " fix(es) earn \"proven\" through column authority alone ("
                + joinShort(requiring) + ") but authority.constraints is " + render(constraints)
                + "; the constraint set must be embedded in full (SPEC 6.3)");
    }

    private boolean nonEmpty(JVal v) {
        if (v == null || v.isNull()) return false;
        if (v.isObj()) return !v.obj.isEmpty();
        if (v.isArr()) return !v.arr.isEmpty();
        if (v.isStr()) return !v.str.isEmpty();
        return true;
    }

    // --------------------------------------------------------------- 11 signature
    private Check signature() {
        String name = "signature";
        if (!isEnvelope) {
            return new Check(name, UNSIGNED,
                    "document is a bare in-toto statement, not a DSSE envelope; "
                    + "it carries no signature and is not authentic");
        }
        if (pubkeyRaw == null) {
            return new Check(name, UNSIGNED, "document is a DSSE envelope but no public key "
                    + "was supplied (--pubkey-hex absent); unsigned is neither a pass nor a failure, "
                    + "and no-check-failed does not mean authentic");
        }
        if (payloadBytes == null) {
            return new Check(name, FAIL, "DSSE envelope payload could not be decoded, "
                    + "so there are no bytes to verify");
        }
        JVal sigs = envelope.get("signatures");
        if (sigs == null || !sigs.isArr()) {
            return new Check(name, FAIL, "envelope.signatures is "
                    + (sigs == null ? "absent" : sigs.typeName()) + ", expected an array");
        }
        if (sigs.arr.isEmpty()) {
            return new Check(name, FAIL, "envelope.signatures is empty, so no signature verifies");
        }
        JVal ptv = envelope.get("payloadType");
        String payloadType = (ptv != null && ptv.isStr()) ? ptv.str : Dsse.DEFAULT_PAYLOAD_TYPE;
        byte[] pae = Dsse.pae(payloadType, payloadBytes);

        PublicKey key;
        try {
            key = Dsse.publicKeyFromRaw(pubkeyRaw);
        } catch (Exception e) {
            return new Check(name, FAIL, "supplied public key could not be loaded: " + e.getMessage());
        }

        List<String> attempts = new ArrayList<>();
        for (int i = 0; i < sigs.arr.size(); i++) {
            JVal s = sigs.arr.get(i);
            if (!s.isObj()) { attempts.add("signatures[" + i + "] is " + s.typeName()); continue; }
            JVal sv = s.get("sig");
            if (sv == null || !sv.isStr()) {
                attempts.add("signatures[" + i + "].sig is " + render(sv));
                continue;
            }
            byte[] raw;
            try {
                raw = decodeBase64(sv.str);
            } catch (Exception e) {
                attempts.add("signatures[" + i + "].sig is not valid base64");
                continue;
            }
            if (Dsse.verify(key, pae, raw)) {
                JVal kid = s.get("keyid");
                return new Check(name, PASS, "signatures[" + i + "]"
                        + (kid != null && kid.isStr() ? " (keyid " + abbrev(kid.str) + ")" : "")
                        + " verifies over PAE(\"" + payloadType + "\", payload) "
                        + "with the supplied Ed25519 key");
            }
            attempts.add("signatures[" + i + "] does not verify under the supplied key");
        }
        return new Check(name, FAIL, "no signature verifies over PAE(\"" + payloadType
                + "\", payload) with the supplied key: " + join(attempts));
    }

    static byte[] decodeBase64(String s) {
        try {
            return Base64.getDecoder().decode(s);
        } catch (IllegalArgumentException e) {
            // Tolerate line-wrapped base64; the strict decoder rejects whitespace.
            return Base64.getMimeDecoder().decode(s);
        }
    }

    // -------------------------------------------------------- 12 witness_is_coherent
    private Check witnessIsCoherent() {
        String name = "witness_is_coherent";
        JVal pred = predicate();
        if (pred == null) {
            return new Check(name, FAIL,
                    "predicate is unavailable, so no witness arithmetic can be checked");
        }
        List<JVal> fixes = fixes();
        List<Integer> withWitness = new ArrayList<>();
        for (int i = 0; i < fixes.size(); i++) {
            JVal f = fixes.get(i);
            if (!f.isObj()) continue;
            JVal w = f.get("witness");
            if (w != null && !w.isNull()) withWitness.add(i);
        }
        if (withWitness.isEmpty()) {
            return new Check(name, SKIP, "no fix carries a witness; "
                    + "absence of evidence is not evidence (SPEC 7.12)");
        }
        List<String> p = new ArrayList<>();
        for (int idx : withWitness) {
            String path = "fixes[" + idx + "].witness";
            JVal w = fixes.get(idx).get("witness");
            if (!w.isObj()) { p.add(path + " is " + w.typeName() + ", expected object"); continue; }

            JVal gs = w.get("group_size");
            JVal sup = w.get("support");
            JVal nvd = w.get("new_value_digest");
            JVal vds = w.get("value_digests");
            JVal trunc = w.get("truncated");

            boolean shapeOk = true;
            if (gs == null || !gs.isInt()) { p.add(path + ".group_size is " + render(gs) + ", expected integer"); shapeOk = false; }
            if (sup == null || !sup.isInt()) { p.add(path + ".support is " + render(sup) + ", expected integer"); shapeOk = false; }
            if (nvd == null || !nvd.isStr()) { p.add(path + ".new_value_digest is " + render(nvd) + ", expected string"); shapeOk = false; }
            if (vds == null || !vds.isArr()) { p.add(path + ".value_digests is " + render(vds) + ", expected array"); shapeOk = false; }
            if (trunc != null && !trunc.isBool()) { p.add(path + ".truncated is " + trunc.typeName() + ", expected boolean"); shapeOk = false; }
            if (!shapeOk) continue;

            long groupSize = gs.asLong();
            long support = sup.asLong();
            boolean truncated = trunc != null && trunc.isBool() && trunc.bool;

            // (1) strict majority, not a plurality
            if (!(support * 2 > groupSize)) {
                p.add(path + ": support " + support + " is not a strict majority of group_size "
                        + groupSize + " (support * 2 must exceed group_size)");
            }
            // (2) support cannot exceed the group
            if (support > groupSize) {
                p.add(path + ": support " + support + " exceeds group_size " + groupSize);
            }

            // (3) the count recorded for new_value_digest equals support
            long sum = 0;
            int matches = 0;
            long matchedCount = 0;
            boolean entriesOk = true;
            for (int j = 0; j < vds.arr.size(); j++) {
                JVal pair = vds.arr.get(j);
                if (!pair.isArr() || pair.arr.size() != 2
                        || !pair.arr.get(0).isStr() || !pair.arr.get(1).isInt()) {
                    p.add(path + ".value_digests[" + j + "] is not a [digest, count] pair");
                    entriesOk = false;
                    continue;
                }
                long count = pair.arr.get(1).asLong();
                sum += count;
                if (nvd.str.equals(pair.arr.get(0).str)) { matches++; matchedCount = count; }
            }
            if (entriesOk) {
                if (matches == 0) {
                    p.add(path + ": new_value_digest " + nvd.str
                            + " has no entry in value_digests, so no recorded count equals support "
                            + support);
                } else if (matches > 1) {
                    p.add(path + ": new_value_digest " + nvd.str + " has " + matches
                            + " entries in value_digests, so \"the count recorded\" for it is ambiguous");
                } else if (matchedCount != support) {
                    p.add(path + ": the count recorded for new_value_digest is " + matchedCount
                            + ", which does not equal support " + support);
                }
                // (4) counts sum to group_size unless truncation is declared
                if (!truncated && sum != groupSize) {
                    p.add(path + ": recorded counts sum to " + sum + ", not group_size " + groupSize
                            + ", and truncated is not true");
                }
            }
        }
        if (p.isEmpty()) {
            return new Check(name, PASS, withWitness.size()
                    + " witness block(s) are internally coherent: strict majority, support within "
                    + "group, written value's count equals support, counts sum to group_size "
                    + "(or truncation is declared)");
        }
        return new Check(name, FAIL, join(p));
    }

    // ----------------------------------------------------------------- helpers
    private JVal needObject(JVal parent, String parentPath, String key, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return null; }
        if (!v.isObj()) { p.add(parentPath + "." + key + " is " + v.typeName() + ", expected object"); return null; }
        return v;
    }

    private JVal needArray(JVal parent, String parentPath, String key, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return null; }
        if (!v.isArr()) { p.add(parentPath + "." + key + " is " + v.typeName() + ", expected array"); return null; }
        return v;
    }

    private void needString(JVal parent, String parentPath, String key, int minLength, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return; }
        if (!v.isStr()) { p.add(parentPath + "." + key + " is " + v.typeName() + ", expected string"); return; }
        if (v.str.length() < minLength) {
            p.add(parentPath + "." + key + " is empty, expected minLength " + minLength);
        }
    }

    private void needBool(JVal parent, String parentPath, String key, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return; }
        if (!v.isBool()) p.add(parentPath + "." + key + " is " + v.typeName() + ", expected boolean");
    }

    private void needHex64(JVal parent, String parentPath, String key, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return; }
        if (!v.isStr()) { p.add(parentPath + "." + key + " is " + v.typeName() + ", expected string"); return; }
        if (!isHex64(v.str)) {
            p.add(parentPath + "." + key + " = " + abbrev(v.str)
                    + " does not match ^[0-9a-f]{64}$");
        }
    }

    private void needStringArray(JVal parent, String parentPath, String key, List<String> p) {
        JVal v = parent.get(key);
        if (v == null) { p.add(parentPath + "." + key + " is missing"); return; }
        if (!v.isArr()) { p.add(parentPath + "." + key + " is " + v.typeName() + ", expected array"); return; }
        for (int i = 0; i < v.arr.size(); i++) {
            if (!v.arr.get(i).isStr()) {
                p.add(parentPath + "." + key + "[" + i + "] is " + v.arr.get(i).typeName()
                        + ", expected string");
            }
        }
    }

    static boolean isHex64(String s) {
        if (s.length() != 64) return false;
        for (int i = 0; i < 64; i++) {
            char c = s.charAt(i);
            boolean ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
            if (!ok) return false;
        }
        return true;
    }

    /** Renders a value for a detail message without dumping a whole subtree. */
    private static String render(JVal v) {
        if (v == null) return "absent";
        switch (v.kind) {
            case JVal.STR:  return "\"" + abbrev(v.str) + "\"";
            case JVal.NUM:  return fmt(v.num);
            case JVal.BOOL: return Boolean.toString(v.bool);
            case JVal.NUL:  return "null";
            case JVal.OBJ:  return "an object with " + v.obj.size() + " member(s)";
            default:        return "an array of " + v.arr.size();
        }
    }

    private static String fmt(double d) {
        if (d == Math.rint(d) && Math.abs(d) < 9.0e15) return Long.toString((long) d);
        return Double.toString(d);
    }

    private static String abbrev(String s) {
        if (s.length() <= 24) return s;
        return s.substring(0, 12) + "..." + s.substring(s.length() - 6);
    }

    private static String show(Set<String> allowed) {
        return "{" + String.join(", ", allowed) + "}";
    }

    private static String join(List<String> problems) {
        if (problems.isEmpty()) return "";
        int cap = 6;
        if (problems.size() <= cap) return String.join("; ", problems);
        List<String> head = new ArrayList<>(problems.subList(0, cap));
        head.add("(+" + (problems.size() - cap) + " more)");
        return String.join("; ", head);
    }

    private static String joinShort(List<String> items) {
        if (items.size() <= 4) return String.join(", ", items);
        return String.join(", ", items.subList(0, 4)) + ", (+" + (items.size() - 4) + " more)";
    }
}
