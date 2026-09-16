import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Clean-room normative verifier for dataforge.repair.attestation/v1.
 *
 * Built from two documents only:
 *   specs/SPEC_repair_attestation.md          (referred to below as MD)
 *   specs/repair_attestation.schema.json      (referred to below as JS)
 *
 * Implements the NORMATIVE tier of MD section 7 (not the advisory tier of the same section).
 * Java 17, standard library only.
 *
 * Usage:
 *   java -cp <dir> Verify --attestation <path> [--pubkey-hex <64 hex>] [--data <path>]
 */
public final class Verify {

    // ---------------------------------------------------------------- constants

    static final String TYPE_URI            = "https://in-toto.io/Statement/v1";
    static final String PREDICATE_TYPE_URI  = "https://dataforge.dev/RepairAttestation/v1";
    static final String VERSION             = "1";
    static final String DSSE_PAYLOAD_TYPE   = "application/vnd.in-toto+json";

    // Closed vocabularies PUBLISHED as enums in JS.
    static final Set<String> MODE            = set("dry_run", "apply");
    static final Set<String> SAFETY          = set("allow", "deny", "escalate");
    static final Set<String> VERIFIER        = set("accept", "not_run", "reject", "unknown");
    static final Set<String> STRENGTH        = set("plausibility_only", "proven");
    static final Set<String> CONSTRAINT_KIND = set("functional_dependency");
    static final Set<String> REVIEW_REASON   = set(
            "ambiguous_fd", "failed_conformal_threshold", "floor_cannot_verify",
            "inferred_fd_not_declared", "invalid_target", "mined_constraint_not_declared",
            "not_inferable_from_data", "out_of_inferred_domain", "safety_denied",
            "safety_escalation", "stale_precondition", "unverified_entity_consensus",
            "unverified_transposition", "verifier_rejected");

    // Closed vocabulary published ONLY in MD section 6.2 (JS types this field
    // ["string","boolean","null"] with no enum at all -- recorded as a disagreement).
    static final Set<String> INDEPENDENT     = set("agreed", "not_run");

    // Provenance: MD section 6.2 promises a closed vocabulary "published as enums in the
    // JSON Schema". JS does NOT publish it (provenance is {"type":"string","minLength":1}).
    // The only provenance tokens either document exhibits as VALID are these two, from
    // MD Appendix A. Everything else is "unrecognised" and MD section 2 / 6.2 / 7 / 9 and
    // Appendix A row 6 all require a REJECT.
    static final Set<String> PROVENANCE_RECOGNISED = set("external", "entity_consensus");

    // MD Appendix A row 1 implies at least one provenance is self-proving ("passes on
    // provenance alone"), and MD section 5 partitions provenance into trusted/untrusted,
    // but NO document names any member of the self-proving subset. It is therefore empty.
    static final Set<String> PROVENANCE_SELF_PROVING = Collections.emptySet();

    static final Pattern HEX64 = Pattern.compile("^[0-9a-f]{64}$");
    static final Pattern HEX16 = Pattern.compile("^[0-9a-f]{16}$");
    static final Pattern RFC3339 = Pattern.compile(
            "^\\d{4}-\\d{2}-\\d{2}[Tt]\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?([Zz]|[+-]\\d{2}:\\d{2})$");

    /** Emission order. 1-10 and 12 are MD section 7's list, verbatim names, in its order.
     *  11 is the witness obligation that only JS states; MD never mentions `witness`, so the
     *  spec supplies no name for it and this one is ours. It sits with the other fix-level
     *  checks, before `signature`, which MD makes last. */
    static final String[] ORDER = {
            "envelope_recognised",
            "version_recognised",
            "schema_complete",
            "vocabulary_closed",
            "subject_matches_post_state",
            "data_identity",
            "reversibility_complete",
            "verdicts_accepting",
            "strength_is_earned",
            "constraints_present",
            "witness_coherent",
            "signature",
    };

    static final String PASS = "pass", FAIL = "fail", SKIP = "skip", UNSIGNED = "unsigned";

    // ---------------------------------------------------------------- state

    static final class Fatal extends RuntimeException {
        Fatal(String m) { super(m); }
    }

    static final class Check {
        final String name;
        String status = FAIL;
        String detail = "not evaluated";
        Check(String name) { this.name = name; }
    }

    private final LinkedHashMap<String, Check> checks = new LinkedHashMap<>();

    private Object root;                       // parsed top-level document
    private Object stmt;                       // the in-toto statement
    private Map<String, Object> envelope;      // non-null when the file is a DSSE envelope
    private byte[] payloadBytes;               // the exact bytes the signature covers
    private String payloadProblem;             // why payloadBytes/stmt could not be obtained
    private List<String> duplicateKeys = new ArrayList<>();

    private byte[] pubkey;                     // 32 raw bytes, or null
    private byte[] data;                       // --data contents, or null
    private String dataPath;

    // ---------------------------------------------------------------- entry point

    public static void main(String[] args) {
        Verify v = new Verify();
        String out;
        try {
            out = v.run(args);
        } catch (Fatal f) {
            System.err.println("verify: " + f.getMessage());
            System.exit(2);
            return;
        } catch (RuntimeException | IOException e) {
            System.err.println("verify: " + e);
            System.exit(2);
            return;
        }
        System.out.println(out);
        System.exit(0);
    }

    private String run(String[] args) throws IOException {
        String attPath = null, pubHex = null;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--attestation": attPath = need(args, ++i, "--attestation"); break;
                case "--pubkey-hex":  pubHex  = need(args, ++i, "--pubkey-hex");  break;
                case "--data":        dataPath = need(args, ++i, "--data");       break;
                default: throw new Fatal("unknown argument: " + args[i]);
            }
        }
        if (attPath == null) throw new Fatal("--attestation is required");

        if (pubHex != null) {
            String h = pubHex.trim().toLowerCase();
            if (!h.matches("^[0-9a-f]{64}$")) {
                throw new Fatal("--pubkey-hex must be 64 hex characters (32 bytes)");
            }
            pubkey = unhex(h);
        }
        if (dataPath != null) {
            try {
                data = Files.readAllBytes(Path.of(dataPath));
            } catch (IOException e) {
                throw new Fatal("cannot read --data " + dataPath + ": " + e.getMessage());
            }
        }

        byte[] raw;
        try {
            raw = Files.readAllBytes(Path.of(attPath));
        } catch (IOException e) {
            throw new Fatal("cannot read --attestation " + attPath + ": " + e.getMessage());
        }
        Json.Parsed parsed;
        try {
            parsed = Json.parse(new String(raw, StandardCharsets.UTF_8));
        } catch (Json.ParseException e) {
            throw new Fatal("attestation is not parseable JSON: " + e.getMessage());
        }
        root = parsed.root;
        duplicateKeys = parsed.duplicateKeys;

        splitEnvelope();

        for (String n : ORDER) checks.put(n, new Check(n));

        checkEnvelopeRecognised();
        checkVersionRecognised();
        checkSchemaComplete();
        checkVocabularyClosed();
        checkSubjectMatchesPostState();
        checkDataIdentity();
        checkReversibilityComplete();
        checkVerdictsAccepting();
        checkStrengthIsEarned();
        checkConstraintsPresent();
        checkWitnessCoherent();
        checkSignature();

        return emit();
    }

    private static String need(String[] a, int i, String flag) {
        if (i >= a.length) throw new Fatal(flag + " requires a value");
        return a[i];
    }

    /**
     * MD section 6.1: unsigned the artifact is a bare Statement; signed, the Statement
     * becomes the DSSE SERIALIZED_BODY carried base64 in `payload`. The documents give no
     * discriminator rule, so we use the presence of both DSSE-specific members.
     *
     * MD section 6.1: "Verifiers MUST NOT re-parse the envelope after signature
     * verification to obtain the payload." We therefore decode `payload` exactly once and
     * parse the statement from the very bytes the signature covers.
     */
    private void splitEnvelope() {
        Map<String, Object> r = asObj(root);
        if (r == null) { stmt = root; return; }
        if (!(r.containsKey("payload") && r.containsKey("payloadType"))) { stmt = root; return; }
        envelope = r;
        String b64 = asStr(r.get("payload"));
        if (b64 == null) { payloadProblem = "envelope payload is not a string"; return; }
        payloadBytes = b64decode(b64);
        if (payloadBytes == null) { payloadProblem = "envelope payload is not decodable base64"; return; }
        try {
            Json.Parsed p = Json.parse(new String(payloadBytes, StandardCharsets.UTF_8));
            stmt = p.root;
            duplicateKeys.addAll(p.duplicateKeys);
        } catch (Json.ParseException e) {
            payloadProblem = "decoded payload is not parseable JSON: " + e.getMessage();
        }
    }

    /** The alphabet and padding discipline are unspecified; try the plausible readings. */
    private static byte[] b64decode(String s) {
        try { return Base64.getDecoder().decode(s); } catch (RuntimeException ignored) { }
        try { return Base64.getMimeDecoder().decode(s); } catch (RuntimeException ignored) { }
        try { return Base64.getUrlDecoder().decode(s); } catch (RuntimeException ignored) { }
        return null;
    }

    // ---------------------------------------------------------------- accessors

    @SuppressWarnings("unchecked")
    static Map<String, Object> asObj(Object o) { return o instanceof Map ? (Map<String, Object>) o : null; }
    @SuppressWarnings("unchecked")
    static List<Object> asArr(Object o) { return o instanceof List ? (List<Object>) o : null; }
    static String asStr(Object o) { return o instanceof String ? (String) o : null; }
    static Boolean asBool(Object o) { return o instanceof Boolean ? (Boolean) o : null; }
    static BigDecimal asNum(Object o) { return o instanceof BigDecimal ? (BigDecimal) o : null; }

    static boolean isNull(Object o) { return o == Json.NULL; }
    static boolean isInt(Object o) {
        BigDecimal b = asNum(o);
        return b != null && b.stripTrailingZeros().scale() <= 0;
    }
    static Long asInt(Object o) {
        return isInt(o) ? asNum(o).longValueExact() : null;
    }

    static Object at(Object o, String... path) {
        Object cur = o;
        for (String k : path) {
            Map<String, Object> m = asObj(cur);
            if (m == null) return null;
            cur = m.get(k);
        }
        return cur;
    }

    private Map<String, Object> pred() { return asObj(at(stmt, "predicate")); }

    /** MD section 6.2: `applied` is a required bool. Null when it is absent or ill-typed. */
    private Boolean applied() { return asBool(at(stmt, "predicate", "applied")); }

    /**
     * The digest of the artifact the predicate designates.
     *
     * MD section 6.1: "`subject` names the artifact the attestation is about: for an applied
     * repair, the repaired bytes; for a dry run, the unchanged source." MD section 6.2:
     * post "MUST equal the subject digest".
     */
    private String designatedDigest() {
        Boolean ap = applied();
        if (ap == null) return null;
        return ap ? asStr(at(stmt, "predicate", "post", "digest", "sha256"))
                  : asStr(at(stmt, "predicate", "source", "digest", "sha256"));
    }

    private String designatedName() {
        Boolean ap = applied();
        if (ap == null) return "<unknown>";
        return ap ? "predicate.post.digest.sha256" : "predicate.source.digest.sha256";
    }

    // ---------------------------------------------------------------- verdict recording

    private void mark(String name, String status, String detail) {
        Check c = checks.get(name);
        c.status = status;
        c.detail = detail;
    }
    private void pass(String n, String d) { mark(n, PASS, d); }
    private void fail(String n, String d) { mark(n, FAIL, d); }
    private void skip(String n, String d) { mark(n, SKIP, d); }

    private void report(String name, List<String> problems, String okDetail) {
        if (problems.isEmpty()) pass(name, okDetail);
        else fail(name, join(problems));
    }

    private static String join(List<String> problems) {
        StringBuilder b = new StringBuilder();
        int shown = 0;
        for (String p : problems) {
            if (b.length() > 600) break;
            if (shown > 0) b.append("; ");
            b.append(p);
            shown++;
        }
        if (shown < problems.size()) {
            b.append("; ... and ").append(problems.size() - shown).append(" more problem(s)");
        }
        return b.toString();
    }

    // ---------------------------------------------------------------- 1. envelope_recognised

    /** MD section 7.1: "`_type` and `predicateType` are exactly the expected URIs." */
    private void checkEnvelopeRecognised() {
        String n = "envelope_recognised";
        if (stmt == null) {
            fail(n, "no statement to inspect: " + (payloadProblem != null ? payloadProblem : "document is empty"));
            return;
        }
        Map<String, Object> st = asObj(stmt);
        if (st == null) { fail(n, "statement is not a JSON object"); return; }
        List<String> p = new ArrayList<>();
        String t = asStr(st.get("_type"));
        String pt = asStr(st.get("predicateType"));
        if (t == null) p.add("_type absent or not a string");
        else if (!TYPE_URI.equals(t)) p.add("_type is '" + t + "', expected '" + TYPE_URI + "'");
        if (pt == null) p.add("predicateType absent or not a string");
        else if (!PREDICATE_TYPE_URI.equals(pt)) p.add("predicateType is '" + pt + "', expected '" + PREDICATE_TYPE_URI + "'");
        report(n, p, "_type and predicateType are exactly the expected URIs");
    }

    // ---------------------------------------------------------------- 2. version_recognised

    /**
     * MD section 7.2: "`attestation_version` is `\"1\"`." MD section 6.2: "Unrecognised value
     * is a REJECT, not a warning." MD section 2: "an unrecognised version is a REJECT".
     *
     * JS declares the const but omits `attestation_version` from predicate.required, so an
     * absent version is schema-valid. We follow MD and reject absence.
     */
    private void checkVersionRecognised() {
        String n = "version_recognised";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object, so no attestation_version to recognise"); return; }
        Object v = pr.get("attestation_version");
        if (v == null) {
            fail(n, "attestation_version absent (MD 6.2 requires it; JS omits it from predicate.required -- MD followed)");
        } else if (asStr(v) == null) {
            fail(n, "attestation_version is not a string");
        } else if (!VERSION.equals(asStr(v))) {
            fail(n, "attestation_version is '" + asStr(v) + "', expected '" + VERSION + "'");
        } else {
            pass(n, "attestation_version is \"1\"");
        }
    }

    // ---------------------------------------------------------------- 3. schema_complete

    /**
     * MD section 7.3: "every required field present and well-typed."
     *
     * Required-ness is the UNION of MD section 6.2's Required column and JS's `required`
     * arrays: a field either document requires is required. JS's own header says its
     * `required` tuples are GENERATED from one verifier's tuples and that structural
     * validity is "NECESSARY AND NOT SUFFICIENT", so MD's table adding requirements on top
     * is consistent with JS's self-description.
     *
     * Types are the union of the two documents' DECLARED type sets; a document that declares
     * no type contributes neither permission nor restriction.
     */
    private void checkSchemaComplete() {
        String n = "schema_complete";
        List<String> p = new ArrayList<>();
        if (!duplicateKeys.isEmpty()) {
            p.add("duplicate JSON object keys make the document ambiguous: " + duplicateKeys);
        }
        if (payloadProblem != null) p.add(payloadProblem);
        Map<String, Object> st = asObj(stmt);
        if (st == null) { fail(n, join(concat(p, "statement is not a JSON object"))); return; }

        reqStr(st, "", "_type", p);
        reqStr(st, "", "predicateType", p);

        // subject: JS minItems 1; every item requires `digest`, `name` optional string.
        Object so = st.get("subject");
        if (so == null) p.add("missing subject");
        else if (asArr(so) == null) p.add("subject is not an array");
        else {
            List<Object> subj = asArr(so);
            if (subj.isEmpty()) p.add("subject is empty (JS minItems 1)");
            for (int k = 0; k < subj.size(); k++) {
                String base = "subject[" + k + "]";
                Map<String, Object> s = asObj(subj.get(k));
                if (s == null) { p.add(base + " is not an object"); continue; }
                Object dg = s.get("digest");
                if (dg == null) p.add("missing " + base + ".digest");
                else if (asObj(dg) == null) p.add(base + ".digest is not an object");
                else reqHex(asObj(dg), base + ".digest", "sha256", HEX64, 64, p);
                if (s.containsKey("name") && asStr(s.get("name")) == null) {
                    p.add(base + ".name is not a string");
                }
            }
        }

        Object pro = st.get("predicate");
        if (pro == null) { p.add("missing predicate"); report(n, p, ""); return; }
        Map<String, Object> pr = asObj(pro);
        if (pr == null) { p.add("predicate is not an object"); report(n, p, ""); return; }

        // ---- scalars
        reqStr(pr, "predicate", "attestation_version", p);
        reqStr(pr, "predicate", "mode", p);
        reqBool(pr, "predicate", "applied", p);
        reqBool(pr, "predicate", "reversible", p);
        reqStrOrNull(pr, "predicate", "revert_command", p);

        // produced_at: MD "RFC 3339 UTC"; JS {"format":"date-time"} (annotation-only in
        // 2020-12, and RFC 3339 permits non-UTC offsets). MD is stricter; MD followed.
        Object pa = pr.get("produced_at");
        if (pa == null) p.add("missing predicate.produced_at");
        else if (asStr(pa) == null) p.add("predicate.produced_at is not a string");
        else {
            String why = rfc3339Utc(asStr(pa));
            if (why != null) p.add("predicate.produced_at " + why);
        }

        // model: MD says object|null, JS says string|null. Union of declarations.
        Object model = pr.get("model");
        if (model == null) p.add("missing predicate.model");
        else if (!(isNull(model) || model instanceof String || asObj(model) != null)) {
            p.add("predicate.model is neither object (MD) nor string (JS) nor null");
        }

        // ---- tool
        Map<String, Object> tool = asObj(pr.get("tool"));
        if (pr.get("tool") == null) p.add("missing predicate.tool");
        else if (tool == null) p.add("predicate.tool is not an object");
        else {
            reqStrMin1(tool, "predicate.tool", "name", p);
            reqStrMin1(tool, "predicate.tool", "version", p);
            reqStr(tool, "predicate.tool", "contract_version", p); // MD required; JS not
        }

        // ---- source / post
        Map<String, Object> src = asObj(pr.get("source"));
        if (pr.get("source") == null) p.add("missing predicate.source");
        else if (src == null) p.add("predicate.source is not an object");
        else {
            Map<String, Object> d = asObj(src.get("digest"));
            if (src.get("digest") == null) p.add("missing predicate.source.digest");
            else if (d == null) p.add("predicate.source.digest is not an object");
            else reqHex(d, "predicate.source.digest", "sha256", HEX64, 64, p);
        }

        // `post` is conditional in both documents: MD Required column says "when `applied`";
        // JS's post.description says "Null on a dry run." Both directions live here because
        // this check owns required-field presence.
        Boolean ap = asBool(pr.get("applied"));
        Object post = pr.get("post");
        if (ap != null && ap) {
            if (post == null || isNull(post)) {
                p.add("predicate.post is required when applied (MD 6.2)");
            } else if (asObj(post) == null) {
                p.add("predicate.post is not an object");
            } else {
                Map<String, Object> d = asObj(at(post, "digest"));
                if (at(post, "digest") == null) p.add("missing predicate.post.digest");
                else if (d == null) p.add("predicate.post.digest is not an object");
                else reqHex(d, "predicate.post.digest", "sha256", HEX64, 64, p);
            }
        } else if (ap != null && !ap) {
            if (post != null && !isNull(post)) {
                p.add("predicate.post must be null on a dry run (JS post.description)");
            }
        }

        // ---- authority
        Map<String, Object> auth = asObj(pr.get("authority"));
        if (pr.get("authority") == null) p.add("missing predicate.authority");
        else if (auth == null) p.add("predicate.authority is not an object");
        else {
            reqArrOfStr(auth, "predicate.authority", "authoritative_columns", p);
            reqArrOfStr(auth, "predicate.authority", "accepted_constraint_ids", p);
            // constraints_digest: MD requires the field and types the inner .sha256 as
            // hex(64)|null; JS types the outer as object-with-required-sha256|null and does
            // not permit a null .sha256. Union of declarations accepted.
            Object cd = auth.get("constraints_digest");
            if (cd == null) p.add("missing predicate.authority.constraints_digest");
            else if (!isNull(cd)) {
                Map<String, Object> cdo = asObj(cd);
                if (cdo == null) p.add("predicate.authority.constraints_digest is neither object nor null");
                else {
                    Object sh = cdo.get("sha256");
                    if (sh == null) p.add("missing predicate.authority.constraints_digest.sha256");
                    else if (!isNull(sh)) reqHex(cdo, "predicate.authority.constraints_digest", "sha256", HEX64, 64, p);
                }
            }
            // constraints: MD requires the field, object|null. JS declares NO type at all.
            Object cons = auth.get("constraints");
            if (!auth.containsKey("constraints")) p.add("missing predicate.authority.constraints");
            else if (!(isNull(cons) || asObj(cons) != null)) {
                p.add("predicate.authority.constraints is neither object nor null (MD 6.2)");
            }
        }

        // ---- fixes
        Object fo = pr.get("fixes");
        if (fo == null) p.add("missing predicate.fixes");
        else if (asArr(fo) == null) p.add("predicate.fixes is not an array");
        else {
            List<Object> fixes = asArr(fo);
            for (int k = 0; k < fixes.size(); k++) {
                String base = "predicate.fixes[" + k + "]";
                Map<String, Object> f = asObj(fixes.get(k));
                if (f == null) { p.add(base + " is not an object"); continue; }
                reqIntMin(f, base, "row", 0, p);
                reqStrMin1(f, base, "column", p);
                reqStrMin1(f, base, "provenance", p);
                reqStr(f, base, "verification_strength", p);
                reqStrOrNull(f, base, "detector_id", p); // MD required; JS not
                for (String opt : new String[]{"old_value", "new_value"}) {
                    if (f.containsKey(opt) && !(isNull(f.get(opt)) || f.get(opt) instanceof String)) {
                        p.add(base + "." + opt + " is neither string nor null");
                    }
                }
                if (f.containsKey("witness") && !isNull(f.get("witness"))) {
                    schemaWitness(asObj(f.get("witness")), base + ".witness", p);
                }
            }
        }

        // ---- held
        Object ho = pr.get("held");
        if (ho == null) p.add("missing predicate.held");
        else if (asArr(ho) == null) p.add("predicate.held is not an array");
        else {
            List<Object> held = asArr(ho);
            for (int k = 0; k < held.size(); k++) {
                String base = "predicate.held[" + k + "]";
                Map<String, Object> h = asObj(held.get(k));
                if (h == null) { p.add(base + " is not an object"); continue; }
                // MD: "each with a `review_reason` from the closed vocabulary" -> required.
                // JS held.items has no `required` array at all.
                reqStr(h, base, "review_reason", p);
                if (h.containsKey("row")) {
                    Long r = asInt(h.get("row"));
                    if (r == null || r < 0) p.add(base + ".row is not an integer >= 0");
                }
                if (h.containsKey("column") && asStr(h.get("column")) == null) {
                    p.add(base + ".column is not a string");
                }
            }
        }

        // ---- verdicts
        Map<String, Object> vd = asObj(pr.get("verdicts"));
        if (pr.get("verdicts") == null) p.add("missing predicate.verdicts");
        else if (vd == null) p.add("predicate.verdicts is not an object");
        else {
            reqStr(vd, "predicate.verdicts", "verifier", p);
            reqStr(vd, "predicate.verdicts", "safety", p);
            // MD requires it and types it as a 2-value string enum; JS permits
            // string|boolean|null. Union of declarations for the type; MD for presence.
            Object iv = vd.get("independent_verification");
            if (iv == null) p.add("missing predicate.verdicts.independent_verification");
            else if (!(isNull(iv) || iv instanceof String || iv instanceof Boolean)) {
                p.add("predicate.verdicts.independent_verification is not string|boolean|null");
            }
        }

        // ---- journal
        Map<String, Object> jr = asObj(pr.get("journal"));
        if (pr.get("journal") == null) p.add("missing predicate.journal");
        else if (jr == null) p.add("predicate.journal is not an object");
        else {
            reqStrOrNull(jr, "predicate.journal", "txn_id", p);
            Object hs = jr.get("head_sha256");
            if (hs == null) p.add("missing predicate.journal.head_sha256");
            else if (!isNull(hs)) reqHex(jr, "predicate.journal", "head_sha256", HEX64, 64, p);
        }

        // ---- limitations, verification
        reqArrOfStr(pr, "predicate", "limitations", p);
        Map<String, Object> vf = asObj(pr.get("verification"));
        if (pr.get("verification") == null) {
            p.add("missing predicate.verification (MD 6.2 requires verification.checks_available)");
        } else if (vf == null) {
            p.add("predicate.verification is not an object");
        } else {
            reqArrOfStr(vf, "predicate.verification", "checks_available", p);
        }

        report(n, p, "every required field (union of MD 6.2 and JS `required`) is present and well-typed");
    }

    /** JS witness.required = constraint, constraint_kind, group_size, support, value_digests,
     *  new_value_digest. MD never mentions `witness`. */
    private void schemaWitness(Map<String, Object> w, String base, List<String> p) {
        if (w == null) { p.add(base + " is not an object"); return; }
        reqStrMin1(w, base, "constraint", p);
        reqStr(w, base, "constraint_kind", p);
        reqIntMin(w, base, "group_size", 1, p);
        reqIntMin(w, base, "support", 1, p);
        reqHex(w, base, "new_value_digest", HEX16, 16, p);
        if (w.containsKey("old_value_digest")) reqHex(w, base, "old_value_digest", HEX16, 16, p);
        if (w.containsKey("truncated") && asBool(w.get("truncated")) == null) {
            p.add(base + ".truncated is not a boolean");
        }
        if (w.containsKey("determinant_columns")) reqArrOfStr(w, base, "determinant_columns", p);
        if (w.containsKey("determinant_digests")) {
            List<Object> dd = asArr(w.get("determinant_digests"));
            if (dd == null) p.add(base + ".determinant_digests is not an array");
            else for (int i = 0; i < dd.size(); i++) {
                String s = asStr(dd.get(i));
                if (s == null || !HEX16.matcher(s).matches()) {
                    p.add(base + ".determinant_digests[" + i + "] is not 16 lowercase hex characters");
                }
            }
        }
        Object vo = w.get("value_digests");
        if (vo == null) p.add("missing " + base + ".value_digests");
        else if (asArr(vo) == null) p.add(base + ".value_digests is not an array");
        else {
            List<Object> vds = asArr(vo);
            for (int i = 0; i < vds.size(); i++) {
                String e = base + ".value_digests[" + i + "]";
                List<Object> pair = asArr(vds.get(i));
                if (pair == null) { p.add(e + " is not an array"); continue; }
                if (pair.size() != 2) { p.add(e + " must have exactly 2 items"); continue; }
                String d = asStr(pair.get(0));
                if (d == null || !HEX16.matcher(d).matches()) p.add(e + "[0] is not 16 lowercase hex characters");
                Long c = asInt(pair.get(1));
                if (c == null || c < 0) p.add(e + "[1] is not an integer >= 0");
            }
        }
    }

    // ------- small structural helpers

    private static List<String> concat(List<String> l, String s) {
        List<String> out = new ArrayList<>(l);
        out.add(s);
        return out;
    }
    private static String path(String base, String key) { return base.isEmpty() ? key : base + "." + key; }

    private static void reqStr(Map<String, Object> m, String base, String key, List<String> p) {
        Object v = m.get(key);
        if (v == null) p.add("missing " + path(base, key));
        else if (asStr(v) == null) p.add(path(base, key) + " is not a string");
    }
    private static void reqStrMin1(Map<String, Object> m, String base, String key, List<String> p) {
        Object v = m.get(key);
        if (v == null) { p.add("missing " + path(base, key)); return; }
        String s = asStr(v);
        if (s == null) p.add(path(base, key) + " is not a string");
        else if (s.isEmpty()) p.add(path(base, key) + " is empty (JS minLength 1)");
    }
    private static void reqStrOrNull(Map<String, Object> m, String base, String key, List<String> p) {
        Object v = m.get(key);
        if (v == null) p.add("missing " + path(base, key));
        else if (!(isNull(v) || v instanceof String)) p.add(path(base, key) + " is neither string nor null");
    }
    private static void reqBool(Map<String, Object> m, String base, String key, List<String> p) {
        Object v = m.get(key);
        if (v == null) p.add("missing " + path(base, key));
        else if (asBool(v) == null) p.add(path(base, key) + " is not a boolean");
    }
    private static void reqIntMin(Map<String, Object> m, String base, String key, long min, List<String> p) {
        Object v = m.get(key);
        if (v == null) { p.add("missing " + path(base, key)); return; }
        Long i = asInt(v);
        if (i == null) p.add(path(base, key) + " is not an integer");
        else if (i < min) p.add(path(base, key) + " is " + i + ", must be >= " + min);
    }
    private static void reqArrOfStr(Map<String, Object> m, String base, String key, List<String> p) {
        Object v = m.get(key);
        if (v == null) { p.add("missing " + path(base, key)); return; }
        List<Object> a = asArr(v);
        if (a == null) { p.add(path(base, key) + " is not an array"); return; }
        for (int i = 0; i < a.size(); i++) {
            if (asStr(a.get(i)) == null) p.add(path(base, key) + "[" + i + "] is not a string");
        }
    }
    private static void reqHex(Map<String, Object> m, String base, String key, Pattern pat, int len, List<String> p) {
        Object v = m.get(key);
        if (v == null) { p.add("missing " + path(base, key)); return; }
        String s = asStr(v);
        if (s == null) p.add(path(base, key) + " is not a string");
        else if (!pat.matcher(s).matches()) {
            p.add(path(base, key) + " is not " + len + " lowercase hex characters");
        }
    }

    /** MD section 6.2: "RFC 3339 UTC". Returns null when acceptable, else the complaint. */
    private static String rfc3339Utc(String s) {
        if (!RFC3339.matcher(s).matches()) return "is not an RFC 3339 date-time";
        try {
            OffsetDateTime odt = OffsetDateTime.parse(s.replace('t', 'T').replace('z', 'Z'));
            if (odt.getOffset().getTotalSeconds() != 0) return "is not UTC (MD 6.2 requires UTC)";
            return null;
        } catch (RuntimeException e) {
            return "is not a valid date-time (" + e.getMessage() + ")";
        }
    }

    // ---------------------------------------------------------------- 4. vocabulary_closed

    /**
     * MD section 7.4: "every enum value is a member of its published set."
     * MD section 2 / 6.2 / 7 / 9: an unknown enum value is a REJECT, never a
     * pass-with-warning; a verifier "MUST fail closed on anything unrecognised".
     *
     * Sets actually PUBLISHED as enums in JS: mode, verdicts.safety, verdicts.verifier,
     * held[].review_reason, fixes[].verification_strength, witness.constraint_kind.
     * Published only in MD's table: verdicts.independent_verification.
     * NOT PUBLISHED ANYWHERE: fixes[].provenance -- MD 6.2 asserts it is "published as
     * enums in [the JSON Schema]" and JS gives it {"type":"string","minLength":1}.
     */
    private void checkVocabularyClosed() {
        String n = "vocabulary_closed";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object, so no vocabularies to close"); return; }
        List<String> p = new ArrayList<>();

        member(pr.get("mode"), MODE, "predicate.mode", p);
        Map<String, Object> vd = asObj(pr.get("verdicts"));
        if (vd != null) {
            member(vd.get("verifier"), VERIFIER, "predicate.verdicts.verifier", p);
            member(vd.get("safety"), SAFETY, "predicate.verdicts.safety", p);
            Object iv = vd.get("independent_verification");
            if (iv != null && !isNull(iv)) {
                if (iv instanceof Boolean) {
                    p.add("predicate.verdicts.independent_verification is a boolean; MD 6.2's"
                        + " closed set is {\"agreed\",\"not_run\"} (JS permits boolean -- MD followed)");
                } else {
                    member(iv, INDEPENDENT, "predicate.verdicts.independent_verification", p);
                }
            }
        }
        List<Object> held = asArr(pr.get("held"));
        if (held != null) {
            for (int k = 0; k < held.size(); k++) {
                Map<String, Object> h = asObj(held.get(k));
                if (h != null) member(h.get("review_reason"), REVIEW_REASON, "predicate.held[" + k + "].review_reason", p);
            }
        }
        List<Object> fixes = asArr(pr.get("fixes"));
        Set<String> unpublished = new LinkedHashSet<>();
        if (fixes != null) {
            for (int k = 0; k < fixes.size(); k++) {
                Map<String, Object> f = asObj(fixes.get(k));
                if (f == null) continue;
                String base = "predicate.fixes[" + k + "]";
                member(f.get("verification_strength"), STRENGTH, base + ".verification_strength", p);
                Map<String, Object> w = asObj(f.get("witness"));
                if (w != null) member(w.get("constraint_kind"), CONSTRAINT_KIND, base + ".witness.constraint_kind", p);
                String prov = asStr(f.get("provenance"));
                if (prov == null) continue;
                if (!PROVENANCE_RECOGNISED.contains(prov)) unpublished.add(prov);
            }
        }
        if (!unpublished.isEmpty()) {
            p.add("unrecognised provenance " + unpublished + ": MD 6.2 declares Provenance a closed"
                + " vocabulary \"published as enums in [the JSON Schema]\" but JS publishes no such"
                + " enum, so the only recognisable members are the ones MD Appendix A exhibits"
                + " as valid " + PROVENANCE_RECOGNISED + "; MD 2/6.2/7/9 require failing closed"
                + " on an unrecognised enum value");
        }
        report(n, p, "every value is a member of its published closed set");
    }

    private static void member(Object v, Set<String> allowed, String path, List<String> p) {
        if (v == null) return;                       // presence is schema_complete's business
        String s = asStr(v);
        if (s == null) { p.add(path + " is not a string, so cannot be a vocabulary member"); return; }
        if (!allowed.contains(s)) p.add(path + " is '" + s + "', not a member of " + allowed);
    }

    // ---------------------------------------------------------------- 5. subject_matches_post_state

    /**
     * MD section 7.5: "subject digest equals `post.digest` when applied."
     * MD section 6.1: for a dry run the subject is "the unchanged source".
     * JS subject.description: "Every subject must name the artifact the predicate describes:
     * duplicates are allowed, and a subject naming a different artifact is a REJECT. Reading
     * only subject[0] ... let a valid attestation be extended with a subject nobody attested."
     * So all N subjects are compared, not just the first.
     */
    private void checkSubjectMatchesPostState() {
        String n = "subject_matches_post_state";
        Map<String, Object> st = asObj(stmt);
        if (st == null) { fail(n, "no statement to inspect"); return; }
        Boolean ap = applied();
        if (ap == null) { fail(n, "predicate.applied absent or not a boolean, so the designated artifact is undetermined"); return; }
        String expect = designatedDigest();
        if (expect == null) {
            fail(n, "cannot evaluate: " + designatedName() + " is absent or not a string"
                  + (ap ? "" : " (dry run: MD 6.1 designates the unchanged source)"));
            return;
        }
        List<Object> subj = asArr(st.get("subject"));
        if (subj == null) { fail(n, "subject is absent or not an array"); return; }
        if (subj.isEmpty()) { fail(n, "subject is empty; there is nothing attesting to the artifact"); return; }
        List<String> p = new ArrayList<>();
        for (int k = 0; k < subj.size(); k++) {
            String got = asStr(at(subj.get(k), "digest", "sha256"));
            if (got == null) p.add("subject[" + k + "].digest.sha256 absent or not a string");
            else if (!got.equals(expect)) {
                p.add("subject[" + k + "].digest.sha256 (" + got + ") does not equal " + designatedName() + " (" + expect + ")");
            }
        }
        report(n, p, "all " + subj.size() + " subject digest(s) equal " + designatedName()
                + (ap ? " (applied)" : " (dry run, MD 6.1)"));
    }

    // ---------------------------------------------------------------- 6. data_identity

    /** MD section 7.6: "SHA-256 of the supplied bytes equals the expected digest."
     *  "The expected digest" is not defined; we use the artifact the predicate designates
     *  (post when applied, source on a dry run -- MD 6.1), which check 5 has already tied
     *  to every subject. */
    private void checkDataIdentity() {
        String n = "data_identity";
        if (data == null) { skip(n, "no --data supplied, so there are no bytes to hash"); return; }
        String expect = designatedDigest();
        if (expect == null) {
            fail(n, "cannot evaluate: " + designatedName() + " is absent or not a string");
            return;
        }
        String got = sha256hex(data);
        if (got.equals(expect)) {
            pass(n, "sha256(" + dataPath + ") = " + got + " equals " + designatedName());
        } else {
            fail(n, "sha256(" + dataPath + ") = " + got + " does not equal " + designatedName() + " (" + expect + ")");
        }
    }

    // ---------------------------------------------------------------- 7. reversibility_complete

    /** MD section 7.7: "`applied` implies `reversible`, `txn_id`, `revert_command`."
     *  MD 6.2 also marks revert_command "Required when `applied`". */
    private void checkReversibilityComplete() {
        String n = "reversibility_complete";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object"); return; }
        Boolean ap = asBool(pr.get("applied"));
        if (ap == null) { fail(n, "predicate.applied absent or not a boolean, so the implication cannot be evaluated"); return; }
        if (!ap) {
            pass(n, "applied is false, so the implication holds vacuously (nothing was mutated)");
            return;
        }
        List<String> p = new ArrayList<>();
        Boolean rev = asBool(pr.get("reversible"));
        if (rev == null) p.add("predicate.reversible absent or not a boolean");
        else if (!rev) p.add("applied is true but reversible is false");
        String txn = asStr(at(pr, "journal", "txn_id"));
        if (txn == null || txn.isEmpty()) p.add("applied is true but predicate.journal.txn_id is absent, null or empty");
        String rc = asStr(pr.get("revert_command"));
        if (rc == null || rc.isEmpty()) p.add("applied is true but predicate.revert_command is absent, null or empty");
        report(n, p, "applied, and reversible + journal.txn_id + revert_command are all present");
    }

    // ---------------------------------------------------------------- 8. verdicts_accepting

    /** MD section 7.8: "verifier `accept`, safety `allow`." */
    private void checkVerdictsAccepting() {
        String n = "verdicts_accepting";
        Map<String, Object> vd = asObj(at(stmt, "predicate", "verdicts"));
        if (vd == null) { fail(n, "predicate.verdicts absent or not an object"); return; }
        List<String> p = new ArrayList<>();
        String v = asStr(vd.get("verifier"));
        String s = asStr(vd.get("safety"));
        if (v == null) p.add("verdicts.verifier absent or not a string");
        else if (!"accept".equals(v)) p.add("verdicts.verifier is '" + v + "', not 'accept'");
        if (s == null) p.add("verdicts.safety absent or not a string");
        else if (!"allow".equals(s)) p.add("verdicts.safety is '" + s + "', not 'allow'");
        report(n, p, "verdicts.verifier is accept and verdicts.safety is allow");
    }

    // ---------------------------------------------------------------- 9. strength_is_earned

    /**
     * MD section 7.9: "for every fix, strength derived from provenance and the column's
     * authority; a recorded `plausibility_only` is always believed."
     * JS verification_strength.description: "Re-derived by the verifier from provenance and
     * column authority. A recorded value stronger than the derivation is a REJECT; a recorded
     * plausibility_only is always believed."
     * MD section 5: "authority is per column, never per table ... a `proven` label on an
     * untrusted provenance is credited only on a covered column."
     * MD Appendix A: "Any fix recorded `plausibility_only` | REJECT while `applied`".
     */
    private void checkStrengthIsEarned() {
        String n = "strength_is_earned";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object"); return; }
        List<Object> fixes = asArr(pr.get("fixes"));
        if (fixes == null) { fail(n, "predicate.fixes absent or not an array"); return; }
        List<Object> cols = asArr(at(pr, "authority", "authoritative_columns"));
        if (cols == null) { fail(n, "predicate.authority.authoritative_columns absent or not an array, so no strength can be derived"); return; }
        Set<String> authoritative = new LinkedHashSet<>();
        for (Object c : cols) if (asStr(c) != null) authoritative.add(asStr(c));
        Boolean ap = asBool(pr.get("applied"));

        List<String> p = new ArrayList<>();
        int proven = 0, plausible = 0;
        for (int k = 0; k < fixes.size(); k++) {
            String base = "fixes[" + k + "]";
            Map<String, Object> f = asObj(fixes.get(k));
            if (f == null) { p.add(base + " is not an object"); continue; }
            String recorded = asStr(f.get("verification_strength"));
            String prov = asStr(f.get("provenance"));
            String col = asStr(f.get("column"));
            if (recorded == null || !STRENGTH.contains(recorded)) {
                p.add(base + ".verification_strength is '" + recorded + "', not a member of " + STRENGTH);
                continue;
            }
            if (prov == null) { p.add(base + ".provenance absent or not a string"); continue; }
            if (!PROVENANCE_RECOGNISED.contains(prov)) {
                p.add(base + ".provenance '" + prov + "' is unrecognised, so no strength can be derived"
                    + " from it (the Provenance vocabulary is published in neither document)");
                continue;
            }
            if (col == null) { p.add(base + ".column absent or not a string"); continue; }

            boolean selfProving = PROVENANCE_SELF_PROVING.contains(prov);
            boolean covered = authoritative.contains(col);
            String derived = (selfProving || covered) ? "proven" : "plausibility_only";

            if ("proven".equals(recorded)) {
                proven++;
                if (!"proven".equals(derived)) {
                    p.add(base + " records 'proven' on untrusted provenance '" + prov + "' but column '"
                        + col + "' is not in authoritative_columns, so the derivation is"
                        + " 'plausibility_only' (recorded stronger than derived is a REJECT)");
                }
            } else {
                plausible++;
                // "always believed": never upgraded. But MD Appendix A rejects it outright
                // while applied.
                if (ap != null && ap) {
                    p.add(base + " records 'plausibility_only' while applied is true (MD Appendix A:"
                        + " REJECT); the recording is believed, not upgraded");
                }
            }
        }
        report(n, p, fixes.isEmpty()
                ? "no fixes to earn strength for"
                : "all " + fixes.size() + " fix(es) earn their recorded strength (" + proven
                  + " proven, " + plausible + " plausibility_only)");
    }

    // ---------------------------------------------------------------- 10. constraints_present

    /**
     * MD section 7.10: "a `proven` untrusted fix requires embedded constraints."
     * MD section 6.2: authority.constraints is "The constraint set embedded in full. Null
     * only when no authority existed."
     * MD section 6.3 / JS constraints.description: a digest and an id list are dangling
     * pointers; a verifier must be able to read what a fix was proven against without
     * fetching anything.
     */
    private void checkConstraintsPresent() {
        String n = "constraints_present";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object"); return; }
        Map<String, Object> auth = asObj(pr.get("authority"));
        if (auth == null) { fail(n, "predicate.authority absent or not an object"); return; }
        Object cons = auth.get("constraints");
        boolean absent = (cons == null || isNull(cons));
        Map<String, Object> co = asObj(cons);
        boolean empty = (co != null && co.isEmpty());

        List<Object> fixes = asArr(pr.get("fixes"));
        List<String> provenUntrusted = new ArrayList<>();
        if (fixes != null) {
            for (int k = 0; k < fixes.size(); k++) {
                Map<String, Object> f = asObj(fixes.get(k));
                if (f == null) continue;
                String prov = asStr(f.get("provenance"));
                if (!"proven".equals(asStr(f.get("verification_strength")))) continue;
                if (prov != null && PROVENANCE_SELF_PROVING.contains(prov)) continue;
                provenUntrusted.add("fixes[" + k + "]");
            }
        }

        List<Object> ac = asArr(at(auth, "authoritative_columns"));
        List<Object> ids = asArr(at(auth, "accepted_constraint_ids"));
        boolean authorityExisted = (ac != null && !ac.isEmpty()) || (ids != null && !ids.isEmpty());

        List<String> p = new ArrayList<>();
        if (!provenUntrusted.isEmpty()) {
            if (absent) {
                p.add(provenUntrusted.size() + " fix(es) recorded 'proven' on untrusted provenance ("
                    + provenUntrusted + ") but authority.constraints is null or absent; MD 6.3"
                    + " requires the constraint set embedded in full");
            } else if (empty) {
                p.add(provenUntrusted.size() + " fix(es) recorded 'proven' on untrusted provenance ("
                    + provenUntrusted + ") but authority.constraints is an empty object, so there is"
                    + " nothing a third party could read the fix back against");
            }
        }
        if (absent && authorityExisted) {
            p.add("authority.constraints is null or absent while authority existed"
                + " (authoritative_columns/accepted_constraint_ids are non-empty); MD 6.2 permits"
                + " null \"only when no authority existed\"");
        }
        report(n, p, absent
                ? "no embedded constraints, and none required (no proven untrusted fix, no authority)"
                : "constraints are embedded in full" + (provenUntrusted.isEmpty() ? "" : " for " + provenUntrusted.size() + " proven untrusted fix(es)"));
    }

    // ---------------------------------------------------------------- 11. witness_coherent

    /**
     * SOURCE: JS witness.description ONLY. MD never mentions `witness` at all, and MD
     * section 7's numbered list has no entry for it, so the specification states this
     * obligation without naming the check. The name emitted here is ours.
     *
     * "The normative verifier checks this block's INTERNAL COHERENCE (support is a strict
     * majority of group_size, the written value's count equals its support, counts sum to
     * group_size unless truncation is declared). It does not recompute from the data".
     */
    private void checkWitnessCoherent() {
        String n = "witness_coherent";
        Map<String, Object> pr = pred();
        if (pr == null) { fail(n, "predicate absent or not an object"); return; }
        List<Object> fixes = asArr(pr.get("fixes"));
        if (fixes == null) { fail(n, "predicate.fixes absent or not an array"); return; }
        List<String> p = new ArrayList<>();
        int seen = 0;
        for (int k = 0; k < fixes.size(); k++) {
            Map<String, Object> f = asObj(fixes.get(k));
            if (f == null) continue;
            Object wo = f.get("witness");
            if (wo == null || isNull(wo)) continue;
            seen++;
            String base = "fixes[" + k + "].witness";
            Map<String, Object> w = asObj(wo);
            if (w == null) { p.add(base + " is not an object"); continue; }
            Long group = asInt(w.get("group_size"));
            Long support = asInt(w.get("support"));
            String nvd = asStr(w.get("new_value_digest"));
            List<Object> vds = asArr(w.get("value_digests"));
            Boolean trunc = asBool(w.get("truncated"));
            if (group == null || support == null || nvd == null || vds == null) {
                p.add(base + " is missing or ill-typed in group_size/support/new_value_digest/value_digests,"
                    + " so its coherence cannot be evaluated");
                continue;
            }
            if (support > group) {
                p.add(base + ": support " + support + " exceeds group_size " + group);
            }
            if (2 * support <= group) {
                p.add(base + ": support " + support + " is not a strict majority of group_size " + group);
            }
            long sum = 0;
            int matches = 0;
            long matchCount = -1;
            boolean countsUsable = true;
            for (Object e : vds) {
                List<Object> pair = asArr(e);
                if (pair == null || pair.size() != 2) { countsUsable = false; continue; }
                Long c = asInt(pair.get(1));
                String d = asStr(pair.get(0));
                if (c == null || d == null) { countsUsable = false; continue; }
                sum += c;
                if (d.equals(nvd)) { matches++; matchCount = c; }
            }
            if (!countsUsable) {
                p.add(base + ".value_digests contains an ill-formed entry, so counts cannot be summed");
                continue;
            }
            if (matches == 0) {
                p.add(base + ": new_value_digest " + nvd + " does not appear in value_digests, so the"
                    + " written value's count cannot equal its support");
            } else if (matches > 1) {
                p.add(base + ": new_value_digest " + nvd + " appears " + matches + " times in value_digests");
            } else if (matchCount != support) {
                p.add(base + ": the written value's count " + matchCount + " does not equal support " + support);
            }
            boolean truncated = (trunc != null && trunc);
            if (!truncated) {
                if (sum != group) {
                    p.add(base + ": value_digests counts sum to " + sum + ", not group_size " + group
                        + ", and truncation is not declared");
                }
            } else if (sum > group) {
                p.add(base + ": value_digests counts sum to " + sum + ", exceeding group_size " + group
                    + " even though truncation is declared");
            }
        }
        if (seen == 0) { skip(n, "no fix carries a witness block, so there is no internal coherence to check"); return; }
        report(n, p, "all " + seen + " witness block(s) are internally coherent");
    }

    // ---------------------------------------------------------------- 12. signature

    /**
     * MD section 7.11: "when signed, DSSE verification against a supplied public key."
     * MD section 4: SIGNATURE = Sign(PAE(UTF8(PAYLOAD_TYPE), SERIALIZED_BODY)) with
     * PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body.
     * MD section 2 / Appendix A: an unsigned attestation reports `unsigned`, never authentic.
     */
    private void checkSignature() {
        String n = "signature";
        if (envelope == null) {
            mark(n, UNSIGNED, "document is a bare in-toto Statement, not a DSSE envelope; there is no signature to verify, so it is not authentic");
            return;
        }
        String pt = asStr(envelope.get("payloadType"));
        if (pt == null) { fail(n, "envelope payloadType is absent or not a string"); return; }
        if (!DSSE_PAYLOAD_TYPE.equals(pt)) {
            fail(n, "envelope payloadType is '" + pt + "', expected '" + DSSE_PAYLOAD_TYPE + "'");
            return;
        }
        if (payloadBytes == null) { fail(n, payloadProblem != null ? payloadProblem : "envelope payload is unusable"); return; }
        List<Object> sigs = asArr(envelope.get("signatures"));
        if (sigs == null) { fail(n, "envelope signatures is absent or not an array"); return; }
        if (sigs.isEmpty()) { fail(n, "envelope carries an empty signatures array; a DSSE envelope with no signature cannot be authenticated"); return; }
        if (pubkey == null) {
            mark(n, UNSIGNED, "envelope carries " + sigs.size() + " signature(s) but no --pubkey-hex was supplied,"
                    + " so authenticity is unverified; this is NOT authentic (MD Appendix A)");
            return;
        }
        byte[] pae = pae(pt, payloadBytes);
        PublicKey key;
        try {
            key = ed25519(pubkey);
        } catch (Exception e) {
            fail(n, "supplied public key is not a usable Ed25519 key: " + e);
            return;
        }
        List<String> tried = new ArrayList<>();
        for (int k = 0; k < sigs.size(); k++) {
            Map<String, Object> s = asObj(sigs.get(k));
            if (s == null) { tried.add("signatures[" + k + "] is not an object"); continue; }
            String b64 = asStr(s.get("sig"));
            if (b64 == null) { tried.add("signatures[" + k + "].sig is absent or not a string"); continue; }
            byte[] sig = b64decode(b64);
            if (sig == null) { tried.add("signatures[" + k + "].sig is not decodable base64"); continue; }
            try {
                Signature v = Signature.getInstance("Ed25519");
                v.initVerify(key);
                v.update(pae);
                if (v.verify(sig)) {
                    String keyid = asStr(s.get("keyid"));
                    pass(n, "signatures[" + k + "] verifies against the supplied Ed25519 key over"
                            + " PAE(payloadType, payload) (" + pae.length + " preimage bytes"
                            + (keyid != null ? ", keyid " + keyid : "") + ")");
                    return;
                }
                tried.add("signatures[" + k + "] does not verify against the supplied key");
            } catch (Exception e) {
                tried.add("signatures[" + k + "] verification error: " + e);
            }
        }
        fail(n, "no signature verifies against the supplied key: " + join(tried));
    }

    /** MD section 4. LEN is the byte length, rendered as ASCII decimal; SP is one space. */
    static byte[] pae(String payloadType, byte[] body) {
        byte[] t = payloadType.getBytes(StandardCharsets.UTF_8);
        byte[] head = ("DSSEv1 " + t.length + " ").getBytes(StandardCharsets.UTF_8);
        byte[] mid = (" " + body.length + " ").getBytes(StandardCharsets.UTF_8);
        byte[] out = new byte[head.length + t.length + mid.length + body.length];
        int o = 0;
        System.arraycopy(head, 0, out, o, head.length); o += head.length;
        System.arraycopy(t, 0, out, o, t.length);       o += t.length;
        System.arraycopy(mid, 0, out, o, mid.length);   o += mid.length;
        System.arraycopy(body, 0, out, o, body.length);
        return out;
    }

    /** Plumbing: wrap 32 raw bytes in an X.509 SubjectPublicKeyInfo for Ed25519. */
    static PublicKey ed25519(byte[] raw32) throws Exception {
        byte[] prefix = unhex("302a300506032b6570032100");
        byte[] der = new byte[prefix.length + raw32.length];
        System.arraycopy(prefix, 0, der, 0, prefix.length);
        System.arraycopy(raw32, 0, der, prefix.length, raw32.length);
        try {
            return KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(der));
        } catch (Exception e) {
            return KeyFactory.getInstance("EdDSA").generatePublic(new X509EncodedKeySpec(der));
        }
    }

    // ---------------------------------------------------------------- output

    private String emit() {
        boolean ok = true;
        for (Check c : checks.values()) if (FAIL.equals(c.status)) ok = false;
        StringBuilder b = new StringBuilder();
        b.append("{\"ok\":").append(ok).append(",\"checks\":[");
        boolean first = true;
        for (String name : ORDER) {
            Check c = checks.get(name);
            if (!first) b.append(',');
            first = false;
            b.append("{\"name\":").append(jstr(c.name))
             .append(",\"status\":").append(jstr(c.status))
             .append(",\"detail\":").append(jstr(c.detail)).append('}');
        }
        b.append("]}");
        return b.toString();
    }

    static String jstr(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\b': b.append("\\b");  break;
                case '\f': b.append("\\f");  break;
                case '\n': b.append("\\n");  break;
                case '\r': b.append("\\r");  break;
                case '\t': b.append("\\t");  break;
                default:
                    if (c < 0x20 || c > 0x7e) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append('"').toString();
    }

    // ---------------------------------------------------------------- misc

    static Set<String> set(String... v) {
        return Collections.unmodifiableSet(new LinkedHashSet<>(Arrays.asList(v)));
    }

    static byte[] unhex(String h) {
        byte[] out = new byte[h.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }

    static String sha256hex(byte[] b) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(b);
            StringBuilder s = new StringBuilder();
            for (byte x : d) s.append(String.format("%02x", x));
            return s.toString();
        } catch (Exception e) {
            throw new Fatal("SHA-256 unavailable: " + e);
        }
    }
}
