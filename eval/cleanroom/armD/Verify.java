import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

public class Verify {

    private static final String STATEMENT_TYPE = "https://in-toto.io/Statement/v1";
    private static final String PREDICATE_TYPE = "https://dataforge.dev/RepairAttestation/v1";
    private static final String DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json";
    private static final String PREMISE_FORMAT = "dataforge.premise/v1";

    private static final Pattern HEX_64 = Pattern.compile("^[0-9a-f]{64}$");
    private static final Pattern HEX_16 = Pattern.compile("^[0-9a-f]{16}$");

    private static final Set<String> MODE_VOCAB = new HashSet<>(Arrays.asList("apply", "dry_run"));
    private static final Set<String> PROVENANCE_VOCAB = new HashSet<>(Arrays.asList(
            "deterministic", "entity_consensus", "external", "llm_cache", "llm_live"
    ));
    private static final Set<String> STRENGTH_VOCAB = new HashSet<>(Arrays.asList(
            "plausibility_only", "proven"
    ));
    private static final Set<String> REVIEW_REASON_VOCAB = new HashSet<>(Arrays.asList(
            "ambiguous_fd",
            "failed_conformal_threshold",
            "floor_cannot_verify",
            "inferred_fd_not_declared",
            "invalid_target",
            "mined_constraint_not_declared",
            "not_inferable_from_data",
            "out_of_inferred_domain",
            "safety_denied",
            "safety_escalation",
            "stale_precondition",
            "unverified_entity_consensus",
            "unverified_transposition",
            "verifier_rejected"
    ));
    private static final Set<String> VERIFIER_VERDICT_VOCAB = new HashSet<>(Arrays.asList(
            "accept", "not_run", "reject", "unknown"
    ));
    private static final Set<String> SAFETY_VERDICT_VOCAB = new HashSet<>(Arrays.asList(
            "allow", "deny", "escalate"
    ));
    private static final Set<String> INDEPENDENT_VERIFICATION_VOCAB = new HashSet<>(Arrays.asList(
            "agreed", "not_run"
    ));

    private static final Set<String> CONFERS_AUTHORITY_TYPES = new HashSet<>(Arrays.asList(
            "int", "integer", "float", "decimal", "real"
    ));

    private static final Set<String> PREMISE_TOP_KEYS = new HashSet<>(Arrays.asList(
            "premise_format",
            "columns",
            "pii_columns",
            "primary_key_columns",
            "not_null_columns",
            "unique_columns",
            "functional_dependencies",
            "accepted_values",
            "regex_constraints",
            "relationships",
            "domain_bounds",
            "aggregate_dependencies"
    ));

    static final class CheckResult {
        final String name;
        final String status;
        final String detail;

        CheckResult(String name, String status, String detail) {
            this.name = name;
            this.status = status;
            this.detail = detail;
        }
    }

    static final class JsonNum {
        final String raw;
        final boolean isIntegral;
        final Long longVal;
        final double doubleVal;

        JsonNum(String raw, boolean isIntegral, Long longVal, double doubleVal) {
            this.raw = raw;
            this.isIntegral = isIntegral;
            this.longVal = longVal;
            this.doubleVal = doubleVal;
        }

        boolean isIntGe(int min) {
            return isIntegral && longVal != null && longVal >= min;
        }
    }

    static final class JsonParser {
        private final String s;
        private int pos;

        JsonParser(String s) {
            this.s = s;
            this.pos = 0;
        }

        Object parseRoot() {
            skipWs();
            Object v = parseValue();
            skipWs();
            if (pos != s.length()) {
                throw new IllegalArgumentException("Trailing characters at position " + pos);
            }
            return v;
        }

        private void skipWs() {
            while (pos < s.length()) {
                char c = s.charAt(pos);
                if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
                    pos++;
                } else {
                    break;
                }
            }
        }

        private Object parseValue() {
            skipWs();
            if (pos >= s.length()) {
                throw new IllegalArgumentException("Unexpected end of input");
            }
            char c = s.charAt(pos);
            switch (c) {
                case '{':
                    return parseObject();
                case '[':
                    return parseArray();
                case '"':
                    return parseString();
                case 't':
                    if (s.startsWith("true", pos)) {
                        pos += 4;
                        return Boolean.TRUE;
                    }
                    throw new IllegalArgumentException("Invalid token at " + pos);
                case 'f':
                    if (s.startsWith("false", pos)) {
                        pos += 5;
                        return Boolean.FALSE;
                    }
                    throw new IllegalArgumentException("Invalid token at " + pos);
                case 'n':
                    if (s.startsWith("null", pos)) {
                        pos += 4;
                        return null;
                    }
                    throw new IllegalArgumentException("Invalid token at " + pos);
                default:
                    if (c == '-' || (c >= '0' && c <= '9')) {
                        return parseNumber();
                    }
                    throw new IllegalArgumentException("Unexpected char '" + c + "' at " + pos);
            }
        }

        private Map<String, Object> parseObject() {
            pos++; // '{'
            skipWs();
            Map<String, Object> map = new LinkedHashMap<>();
            if (pos < s.length() && s.charAt(pos) == '}') {
                pos++;
                return map;
            }
            while (true) {
                skipWs();
                if (pos >= s.length() || s.charAt(pos) != '"') {
                    throw new IllegalArgumentException("Expected string key at " + pos);
                }
                String key = parseString();
                skipWs();
                if (pos >= s.length() || s.charAt(pos) != ':') {
                    throw new IllegalArgumentException("Expected ':' at " + pos);
                }
                pos++;
                Object val = parseValue();
                map.put(key, val);
                skipWs();
                if (pos >= s.length()) {
                    throw new IllegalArgumentException("Unterminated object");
                }
                char c = s.charAt(pos);
                if (c == '}') {
                    pos++;
                    return map;
                } else if (c == ',') {
                    pos++;
                } else {
                    throw new IllegalArgumentException("Expected ',' or '}' at " + pos);
                }
            }
        }

        private List<Object> parseArray() {
            pos++; // '['
            skipWs();
            List<Object> list = new ArrayList<>();
            if (pos < s.length() && s.charAt(pos) == ']') {
                pos++;
                return list;
            }
            while (true) {
                Object val = parseValue();
                list.add(val);
                skipWs();
                if (pos >= s.length()) {
                    throw new IllegalArgumentException("Unterminated array");
                }
                char c = s.charAt(pos);
                if (c == ']') {
                    pos++;
                    return list;
                } else if (c == ',') {
                    pos++;
                } else {
                    throw new IllegalArgumentException("Expected ',' or ']' at " + pos);
                }
            }
        }

        private String parseString() {
            pos++; // '"'
            StringBuilder sb = new StringBuilder();
            while (pos < s.length()) {
                char c = s.charAt(pos++);
                if (c == '"') {
                    return sb.toString();
                } else if (c == '\\') {
                    if (pos >= s.length()) {
                        throw new IllegalArgumentException("Unterminated escape");
                    }
                    char e = s.charAt(pos++);
                    switch (e) {
                        case '"':
                        case '\\':
                        case '/':
                            sb.append(e);
                            break;
                        case 'b':
                            sb.append('\b');
                            break;
                        case 'f':
                            sb.append('\f');
                            break;
                        case 'n':
                            sb.append('\n');
                            break;
                        case 'r':
                            sb.append('\r');
                            break;
                        case 't':
                            sb.append('\t');
                            break;
                        case 'u':
                            if (pos + 4 > s.length()) {
                                throw new IllegalArgumentException("Invalid unicode escape");
                            }
                            String hex = s.substring(pos, pos + 4);
                            pos += 4;
                            sb.append((char) Integer.parseInt(hex, 16));
                            break;
                        default:
                            throw new IllegalArgumentException("Invalid escape '\\" + e + "'");
                    }
                } else if (c < 0x20) {
                    throw new IllegalArgumentException("Unescaped control char");
                } else {
                    sb.append(c);
                }
            }
            throw new IllegalArgumentException("Unterminated string");
        }

        private JsonNum parseNumber() {
            int start = pos;
            if (s.charAt(pos) == '-') {
                pos++;
            }
            if (pos >= s.length()) {
                throw new IllegalArgumentException("Invalid number");
            }
            if (s.charAt(pos) == '0') {
                pos++;
            } else if (s.charAt(pos) >= '1' && s.charAt(pos) <= '9') {
                while (pos < s.length() && s.charAt(pos) >= '0' && s.charAt(pos) <= '9') {
                    pos++;
                }
            } else {
                throw new IllegalArgumentException("Invalid number at " + pos);
            }
            boolean isFloat = false;
            if (pos < s.length() && s.charAt(pos) == '.') {
                isFloat = true;
                pos++;
                if (pos >= s.length() || s.charAt(pos) < '0' || s.charAt(pos) > '9') {
                    throw new IllegalArgumentException("Invalid fraction in number");
                }
                while (pos < s.length() && s.charAt(pos) >= '0' && s.charAt(pos) <= '9') {
                    pos++;
                }
            }
            if (pos < s.length() && (s.charAt(pos) == 'e' || s.charAt(pos) == 'E')) {
                isFloat = true;
                pos++;
                if (pos < s.length() && (s.charAt(pos) == '+' || s.charAt(pos) == '-')) {
                    pos++;
                }
                if (pos >= s.length() || s.charAt(pos) < '0' || s.charAt(pos) > '9') {
                    throw new IllegalArgumentException("Invalid exponent in number");
                }
                while (pos < s.length() && s.charAt(pos) >= '0' && s.charAt(pos) <= '9') {
                    pos++;
                }
            }
            String raw = s.substring(start, pos);
            double d = Double.parseDouble(raw);
            if (!Double.isFinite(d)) {
                throw new IllegalArgumentException("Non-finite number");
            }
            Long lVal = null;
            if (!isFloat) {
                try {
                    lVal = Long.parseLong(raw);
                } catch (NumberFormatException ignored) {
                    lVal = null;
                }
            }
            return new JsonNum(raw, !isFloat, lVal, d);
        }
    }

    public static void main(String[] args) {
        String attestationPath = null;
        String pubkeyHex = null;
        String dataPath = null;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--attestation":
                    if (i + 1 < args.length) attestationPath = args[++i];
                    break;
                case "--pubkey-hex":
                    if (i + 1 < args.length) pubkeyHex = args[++i];
                    break;
                case "--data":
                    if (i + 1 < args.length) dataPath = args[++i];
                    break;
                default:
                    break;
            }
        }

        if (attestationPath == null) {
            System.err.println("Missing --attestation <path>");
            System.exit(1);
            return;
        }

        byte[] dataBytes = null;
        if (dataPath != null) {
            try {
                dataBytes = Files.readAllBytes(Path.of(dataPath));
            } catch (IOException e) {
                System.err.println("Failed to read --data file: " + e.getMessage());
                System.exit(1);
                return;
            }
        }

        String rawAttestation;
        try {
            rawAttestation = Files.readString(Path.of(attestationPath), StandardCharsets.UTF_8);
        } catch (IOException e) {
            System.err.println("Failed to read --attestation file: " + e.getMessage());
            System.exit(1);
            return;
        }

        List<CheckResult> results = verify(rawAttestation, pubkeyHex, dataBytes);
        boolean ok = true;
        for (CheckResult r : results) {
            if ("fail".equals(r.status)) {
                ok = false;
                break;
            }
        }
        System.out.println(formatOutput(ok, results));
        System.exit(0);
    }

    @SuppressWarnings("unchecked")
    private static List<CheckResult> verify(String rawJson, String pubkeyHex, byte[] dataBytes) {
        Object parsedRoot;
        try {
            parsedRoot = new JsonParser(rawJson).parseRoot();
        } catch (Exception e) {
            List<CheckResult> err = new ArrayList<>();
            err.add(new CheckResult("schema_complete", "fail", "Invalid JSON: " + e.getMessage()));
            return err;
        }

        if (!(parsedRoot instanceof Map<?, ?>)) {
            List<CheckResult> err = new ArrayList<>();
            err.add(new CheckResult("schema_complete", "fail", "Root document must be a JSON object"));
            return err;
        }

        Map<String, Object> rootMap = (Map<String, Object>) parsedRoot;
        boolean isDsse = isDsseEnvelope(rootMap);

        Map<String, Object> statement = rootMap;
        CheckResult sigResult;

        if (isDsse) {
            DsseOutcome dsse = verifyDsse(rootMap, pubkeyHex);
            sigResult = dsse.checkResult;
            if ("fail".equals(sigResult.status)) {
                // Normative short-circuit rule (§7): when DSSE signature FAILS, report signature alone.
                return Collections.singletonList(sigResult);
            }
            statement = dsse.statement;
        } else {
            sigResult = new CheckResult("signature", "skip", "Document is not a DSSE envelope");
        }

        List<CheckResult> checks = new ArrayList<>(13);
        checks.add(checkEnvelopeRecognised(statement));
        checks.add(checkVersionRecognised(statement));
        checks.add(checkSchemaComplete(statement));
        checks.add(checkVocabularyClosed(statement));
        checks.add(checkSubjectMatchesPostState(statement));
        checks.add(checkDataIdentity(statement, dataBytes));
        checks.add(checkReversibilityComplete(statement));
        checks.add(checkVerdictsAccepting(statement));

        StrengthCheckOutcome strengthOutcome = checkStrengthIsEarned(statement);
        checks.add(strengthOutcome.result);
        checks.add(checkConstraintsPresent(statement, strengthOutcome.failedFixIndices));
        checks.add(sigResult);
        checks.add(checkWitnessIsCoherent(statement));
        checks.add(checkAuthorityIsEntailed(statement));

        return checks;
    }

    private static boolean isDsseEnvelope(Map<String, Object> map) {
        return map.containsKey("payload") || map.containsKey("payloadType") || map.containsKey("signatures");
    }

    private static final class DsseOutcome {
        final CheckResult checkResult;
        final Map<String, Object> statement;

        DsseOutcome(CheckResult checkResult, Map<String, Object> statement) {
            this.checkResult = checkResult;
            this.statement = statement;
        }
    }

    @SuppressWarnings("unchecked")
    private static DsseOutcome verifyDsse(Map<String, Object> dsse, String pubkeyHex) {
        Object payloadTypeObj = dsse.get("payloadType");
        Object payloadObj = dsse.get("payload");
        Object sigsObj = dsse.get("signatures");

        if (!(payloadTypeObj instanceof String) || !DSSE_PAYLOAD_TYPE.equals(payloadTypeObj)) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Invalid or unexpected DSSE payloadType"), Collections.emptyMap());
        }
        if (!(payloadObj instanceof String)) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Missing or non-string DSSE payload"), Collections.emptyMap());
        }
        if (!(sigsObj instanceof List<?>)) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Missing or invalid DSSE signatures array"), Collections.emptyMap());
        }
        List<?> sigs = (List<?>) sigsObj;
        if (sigs.isEmpty()) {
            return new DsseOutcome(new CheckResult("signature", "fail", "DSSE signatures array is empty"), Collections.emptyMap());
        }

        byte[] payloadBytes;
        try {
            payloadBytes = Base64.getDecoder().decode((String) payloadObj);
        } catch (IllegalArgumentException e) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Invalid base64 in DSSE payload"), Collections.emptyMap());
        }

        Map<String, Object> parsedStatement = Collections.emptyMap();
        boolean statementValidJson = false;
        try {
            String payloadStr = new String(payloadBytes, StandardCharsets.UTF_8);
            Object parsed = new JsonParser(payloadStr).parseRoot();
            if (parsed instanceof Map<?, ?>) {
                parsedStatement = (Map<String, Object>) parsed;
                statementValidJson = true;
            }
        } catch (Exception ignored) {
            statementValidJson = false;
        }

        if (pubkeyHex == null || pubkeyHex.isEmpty()) {
            if (!statementValidJson) {
                return new DsseOutcome(new CheckResult("signature", "fail", "DSSE payload is not a valid JSON object"), Collections.emptyMap());
            }
            return new DsseOutcome(new CheckResult("signature", "skip", "unsigned"), parsedStatement);
        }

        byte[] rawPubKey;
        try {
            rawPubKey = hexToBytes(pubkeyHex.trim());
        } catch (Exception e) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Invalid public key hex"), Collections.emptyMap());
        }
        if (rawPubKey.length != 32) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Public key must be 32 bytes"), Collections.emptyMap());
        }

        byte[] pae = computePae((String) payloadTypeObj, payloadBytes);
        boolean verifiedAny = false;
        try {
            byte[] derHeader = new byte[]{0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00};
            byte[] spki = new byte[derHeader.length + rawPubKey.length];
            System.arraycopy(derHeader, 0, spki, 0, derHeader.length);
            System.arraycopy(rawPubKey, 0, spki, derHeader.length, rawPubKey.length);
            KeyFactory kf = KeyFactory.getInstance("Ed25519");
            PublicKey pubKey = kf.generatePublic(new X509EncodedKeySpec(spki));

            for (Object sObj : sigs) {
                if (!(sObj instanceof Map<?, ?>)) continue;
                Map<String, Object> sMap = (Map<String, Object>) sObj;
                Object sigB64 = sMap.get("sig");
                if (!(sigB64 instanceof String)) continue;
                byte[] sigBytes = Base64.getDecoder().decode((String) sigB64);
                Signature verifier = Signature.getInstance("Ed25519");
                verifier.initVerify(pubKey);
                verifier.update(pae);
                if (verifier.verify(sigBytes)) {
                    verifiedAny = true;
                    break;
                }
            }
        } catch (Exception e) {
            return new DsseOutcome(new CheckResult("signature", "fail", "Signature verification error: " + e.getMessage()), Collections.emptyMap());
        }

        if (!verifiedAny || !statementValidJson) {
            return new DsseOutcome(new CheckResult("signature", "fail", "DSSE signature verification failed"), Collections.emptyMap());
        }

        return new DsseOutcome(new CheckResult("signature", "pass", "DSSE signature verified"), parsedStatement);
    }

    private static byte[] computePae(String payloadType, byte[] body) {
        byte[] typeBytes = payloadType.getBytes(StandardCharsets.UTF_8);
        String prefix = "DSSEv1 " + typeBytes.length + " ";
        String mid = " " + body.length + " ";
        byte[] prefixBytes = prefix.getBytes(StandardCharsets.UTF_8);
        byte[] midBytes = mid.getBytes(StandardCharsets.UTF_8);

        byte[] out = new byte[prefixBytes.length + typeBytes.length + midBytes.length + body.length];
        int p = 0;
        System.arraycopy(prefixBytes, 0, out, p, prefixBytes.length);
        p += prefixBytes.length;
        System.arraycopy(typeBytes, 0, out, p, typeBytes.length);
        p += typeBytes.length;
        System.arraycopy(midBytes, 0, out, p, midBytes.length);
        p += midBytes.length;
        System.arraycopy(body, 0, out, p, body.length);
        return out;
    }

    // Check 1: envelope_recognised
    private static CheckResult checkEnvelopeRecognised(Map<String, Object> st) {
        Object type = st.get("_type");
        Object predType = st.get("predicateType");
        if (STATEMENT_TYPE.equals(type) && PREDICATE_TYPE.equals(predType)) {
            return new CheckResult("envelope_recognised", "pass", "Envelope URIs recognised");
        }
        return new CheckResult("envelope_recognised", "fail", "Unrecognised _type or predicateType");
    }

    // Check 2: version_recognised
    private static CheckResult checkVersionRecognised(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) {
            return new CheckResult("version_recognised", "fail", "Missing predicate");
        }
        Object ver = pred.get("attestation_version");
        if ("1".equals(ver)) {
            return new CheckResult("version_recognised", "pass", "attestation_version is 1");
        }
        return new CheckResult("version_recognised", "fail", "Unrecognised or missing attestation_version");
    }

    // Check 3: schema_complete
    @SuppressWarnings("unchecked")
    private static CheckResult checkSchemaComplete(Map<String, Object> st) {
        // Root required: _type, subject, predicateType, predicate
        if (!st.containsKey("_type") || !(st.get("_type") instanceof String)) {
            return new CheckResult("schema_complete", "fail", "Missing or invalid _type");
        }
        if (!st.containsKey("predicateType") || !(st.get("predicateType") instanceof String)) {
            return new CheckResult("schema_complete", "fail", "Missing or invalid predicateType");
        }
        Object subjObj = st.get("subject");
        if (!(subjObj instanceof List<?>)) {
            return new CheckResult("schema_complete", "fail", "Missing or non-array subject");
        }
        List<?> subjects = (List<?>) subjObj;
        if (subjects.isEmpty()) {
            return new CheckResult("schema_complete", "fail", "subject array must not be empty");
        }
        for (Object item : subjects) {
            if (!(item instanceof Map<?, ?>)) {
                return new CheckResult("schema_complete", "fail", "subject entry must be an object");
            }
            Map<String, Object> sMap = (Map<String, Object>) item;
            if (sMap.containsKey("name") && !(sMap.get("name") instanceof String)) {
                return new CheckResult("schema_complete", "fail", "subject.name must be a string");
            }
            Map<String, Object> digest = getObject(sMap, "digest");
            if (digest == null || !isHex64(digest.get("sha256"))) {
                return new CheckResult("schema_complete", "fail", "subject.digest.sha256 missing or invalid");
            }
        }

        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) {
            return new CheckResult("schema_complete", "fail", "Missing or non-object predicate");
        }

        // predicate.required from JSON Schema:
        // tool, produced_at, mode, applied, reversible, source, authority, fixes, held, verdicts, journal, limitations
        // Note (§7.4): missing or null enum values (including mode) are owned by vocabulary_closed, not schema_complete.
        String[] predRequiredNonEnum = {
                "tool", "produced_at", "applied", "reversible", "source",
                "authority", "fixes", "held", "verdicts", "journal", "limitations"
        };
        for (String req : predRequiredNonEnum) {
            if (!pred.containsKey(req) || pred.get(req) == null) {
                return new CheckResult("schema_complete", "fail", "Missing required predicate field: " + req);
            }
        }

        // tool.required: name, version
        Map<String, Object> tool = getObject(pred, "tool");
        if (tool == null) {
            return new CheckResult("schema_complete", "fail", "predicate.tool must be an object");
        }
        if (!isNonEmptyString(tool.get("name")) || !isNonEmptyString(tool.get("version"))) {
            return new CheckResult("schema_complete", "fail", "tool.name and tool.version are required non-empty strings");
        }
        if (tool.containsKey("contract_version") && tool.get("contract_version") != null
                && !(tool.get("contract_version") instanceof String)) {
            return new CheckResult("schema_complete", "fail", "tool.contract_version must be a string");
        }

        if (!isNonEmptyString(pred.get("produced_at"))) {
            return new CheckResult("schema_complete", "fail", "predicate.produced_at must be a non-empty string");
        }
        if (!(pred.get("applied") instanceof Boolean)) {
            return new CheckResult("schema_complete", "fail", "predicate.applied must be a boolean");
        }
        if (!(pred.get("reversible") instanceof Boolean)) {
            return new CheckResult("schema_complete", "fail", "predicate.reversible must be a boolean");
        }

        // source.digest.sha256
        Map<String, Object> source = getObject(pred, "source");
        if (source == null) {
            return new CheckResult("schema_complete", "fail", "predicate.source must be an object");
        }
        Map<String, Object> sourceDigest = getObject(source, "digest");
        if (sourceDigest == null || !isHex64(sourceDigest.get("sha256"))) {
            return new CheckResult("schema_complete", "fail", "source.digest.sha256 must be a 64-char hex string");
        }

        // post (optional/nullable in schema, object with digest.sha256 when non-null)
        if (pred.containsKey("post") && pred.get("post") != null) {
            Map<String, Object> post = getObject(pred, "post");
            if (post == null) {
                return new CheckResult("schema_complete", "fail", "predicate.post must be an object or null");
            }
            Map<String, Object> postDigest = getObject(post, "digest");
            if (postDigest == null || !isHex64(postDigest.get("sha256"))) {
                return new CheckResult("schema_complete", "fail", "post.digest.sha256 must be a 64-char hex string");
            }
        }

        // authority.required: authoritative_columns, accepted_constraint_ids
        Map<String, Object> authority = getObject(pred, "authority");
        if (authority == null) {
            return new CheckResult("schema_complete", "fail", "predicate.authority must be an object");
        }
        if (!isStringArray(authority.get("authoritative_columns"))
                || !isStringArray(authority.get("accepted_constraint_ids"))) {
            return new CheckResult("schema_complete", "fail", "authority.authoritative_columns and accepted_constraint_ids must be string arrays");
        }
        if (authority.containsKey("constraints_digest") && authority.get("constraints_digest") != null) {
            Map<String, Object> cd = getObject(authority, "constraints_digest");
            if (cd == null || !isHex64(cd.get("sha256"))) {
                return new CheckResult("schema_complete", "fail", "authority.constraints_digest.sha256 invalid");
            }
        }

        // fixes: array of objects; fixes.items.required: row, column, provenance, verification_strength
        // (provenance & verification_strength missing/null are owned by vocabulary_closed per §7.4)
        if (!(pred.get("fixes") instanceof List<?>)) {
            return new CheckResult("schema_complete", "fail", "predicate.fixes must be an array");
        }
        List<?> fixes = (List<?>) pred.get("fixes");
        for (Object fObj : fixes) {
            if (!(fObj instanceof Map<?, ?>)) {
                return new CheckResult("schema_complete", "fail", "Each fix must be an object");
            }
            Map<String, Object> fix = (Map<String, Object>) fObj;
            Object rowObj = fix.get("row");
            if (!(rowObj instanceof JsonNum) || !((JsonNum) rowObj).isIntGe(0)) {
                return new CheckResult("schema_complete", "fail", "fix.row must be an integer >= 0");
            }
            if (!isNonEmptyString(fix.get("column"))) {
                return new CheckResult("schema_complete", "fail", "fix.column must be a non-empty string");
            }
            if (fix.containsKey("detector_id") && fix.get("detector_id") != null && !(fix.get("detector_id") instanceof String)) {
                return new CheckResult("schema_complete", "fail", "fix.detector_id must be a string or null");
            }
            if (fix.containsKey("old_value") && fix.get("old_value") != null && !(fix.get("old_value") instanceof String)) {
                return new CheckResult("schema_complete", "fail", "fix.old_value must be a string or null");
            }
            if (fix.containsKey("new_value") && fix.get("new_value") != null && !(fix.get("new_value") instanceof String)) {
                return new CheckResult("schema_complete", "fail", "fix.new_value must be a string or null");
            }
        }

        // held: array of objects
        if (!(pred.get("held") instanceof List<?>)) {
            return new CheckResult("schema_complete", "fail", "predicate.held must be an array");
        }
        List<?> held = (List<?>) pred.get("held");
        for (Object hObj : held) {
            if (!(hObj instanceof Map<?, ?>)) {
                return new CheckResult("schema_complete", "fail", "Each held item must be an object");
            }
            Map<String, Object> hMap = (Map<String, Object>) hObj;
            if (hMap.containsKey("column") && hMap.get("column") != null && !(hMap.get("column") instanceof String)) {
                return new CheckResult("schema_complete", "fail", "held.column must be a string");
            }
            if (hMap.containsKey("row") && hMap.get("row") != null) {
                Object rObj = hMap.get("row");
                if (!(rObj instanceof JsonNum) || !((JsonNum) rObj).isIntGe(0)) {
                    return new CheckResult("schema_complete", "fail", "held.row must be an integer >= 0");
                }
            }
        }

        // verdicts: object
        if (getObject(pred, "verdicts") == null) {
            return new CheckResult("schema_complete", "fail", "predicate.verdicts must be an object");
        }

        // journal: object
        Map<String, Object> journal = getObject(pred, "journal");
        if (journal == null) {
            return new CheckResult("schema_complete", "fail", "predicate.journal must be an object");
        }
        if (journal.containsKey("txn_id") && journal.get("txn_id") != null && !(journal.get("txn_id") instanceof String)) {
            return new CheckResult("schema_complete", "fail", "journal.txn_id must be a string or null");
        }
        if (journal.containsKey("head_sha256") && journal.get("head_sha256") != null && !isHex64(journal.get("head_sha256"))) {
            return new CheckResult("schema_complete", "fail", "journal.head_sha256 must be a 64-char hex string or null");
        }

        // limitations: string[]
        if (!isStringArray(pred.get("limitations"))) {
            return new CheckResult("schema_complete", "fail", "predicate.limitations must be an array of strings");
        }

        // model: object | null
        if (pred.containsKey("model") && pred.get("model") != null && !(pred.get("model") instanceof Map<?, ?>)) {
            return new CheckResult("schema_complete", "fail", "predicate.model must be an object or null");
        }

        // revert_command: string | null
        if (pred.containsKey("revert_command") && pred.get("revert_command") != null && !(pred.get("revert_command") instanceof String)) {
            return new CheckResult("schema_complete", "fail", "predicate.revert_command must be a string or null");
        }

        // verification: optional object with checks_available string[]
        if (pred.containsKey("verification") && pred.get("verification") != null) {
            Map<String, Object> verif = getObject(pred, "verification");
            if (verif == null) {
                return new CheckResult("schema_complete", "fail", "predicate.verification must be an object");
            }
            if (verif.containsKey("checks_available") && !isStringArray(verif.get("checks_available"))) {
                return new CheckResult("schema_complete", "fail", "verification.checks_available must be a string array");
            }
        }

        return new CheckResult("schema_complete", "pass", "All required schema fields present and well-typed");
    }

    // Check 4: vocabulary_closed
    @SuppressWarnings("unchecked")
    private static CheckResult checkVocabularyClosed(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) {
            return new CheckResult("vocabulary_closed", "fail", "Missing predicate");
        }

        Object mode = pred.get("mode");
        if (!(mode instanceof String) || !MODE_VOCAB.contains(mode)) {
            return new CheckResult("vocabulary_closed", "fail", "Invalid or missing predicate.mode");
        }

        Map<String, Object> verdicts = getObject(pred, "verdicts");
        if (verdicts == null) {
            return new CheckResult("vocabulary_closed", "fail", "Missing predicate.verdicts");
        }
        Object vVerifier = verdicts.get("verifier");
        if (!(vVerifier instanceof String) || !VERIFIER_VERDICT_VOCAB.contains(vVerifier)) {
            return new CheckResult("vocabulary_closed", "fail", "Invalid or missing verdicts.verifier");
        }
        Object vSafety = verdicts.get("safety");
        if (!(vSafety instanceof String) || !SAFETY_VERDICT_VOCAB.contains(vSafety)) {
            return new CheckResult("vocabulary_closed", "fail", "Invalid or missing verdicts.safety");
        }
        Object vIndep = verdicts.get("independent_verification");
        if (!(vIndep instanceof String) || !INDEPENDENT_VERIFICATION_VOCAB.contains(vIndep)) {
            return new CheckResult("vocabulary_closed", "fail", "Invalid or missing verdicts.independent_verification");
        }

        Object fixesObj = pred.get("fixes");
        if (fixesObj instanceof List<?>) {
            for (Object fObj : (List<?>) fixesObj) {
                if (!(fObj instanceof Map<?, ?>)) continue;
                Map<String, Object> fix = (Map<String, Object>) fObj;
                Object prov = fix.get("provenance");
                if (!(prov instanceof String) || !PROVENANCE_VOCAB.contains(prov)) {
                    return new CheckResult("vocabulary_closed", "fail", "Invalid or missing fix.provenance");
                }
                Object strength = fix.get("verification_strength");
                if (!(strength instanceof String) || !STRENGTH_VOCAB.contains(strength)) {
                    return new CheckResult("vocabulary_closed", "fail", "Invalid or missing fix.verification_strength");
                }
            }
        }

        Object heldObj = pred.get("held");
        if (heldObj instanceof List<?>) {
            for (Object hObj : (List<?>) heldObj) {
                if (!(hObj instanceof Map<?, ?>)) continue;
                Map<String, Object> held = (Map<String, Object>) hObj;
                Object reason = held.get("review_reason");
                if (!(reason instanceof String) || !REVIEW_REASON_VOCAB.contains(reason)) {
                    return new CheckResult("vocabulary_closed", "fail", "Invalid or missing held.review_reason");
                }
            }
        }

        return new CheckResult("vocabulary_closed", "pass", "All closed vocabulary values recognised");
    }

    // Helper for Check 5 and Check 6: expected digest
    private static String getExpectedDigest(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) return null;
        Object appliedObj = pred.get("applied");
        if (!(appliedObj instanceof Boolean)) return null;
        boolean applied = (Boolean) appliedObj;
        Map<String, Object> target = getObject(pred, applied ? "post" : "source");
        if (target == null) return null;
        Map<String, Object> digest = getObject(target, "digest");
        if (digest == null) return null;
        Object sha = digest.get("sha256");
        if (sha instanceof String && isHex64(sha)) {
            return (String) sha;
        }
        return null;
    }

    // Check 5: subject_matches_post_state
    @SuppressWarnings("unchecked")
    private static CheckResult checkSubjectMatchesPostState(Map<String, Object> st) {
        String expected = getExpectedDigest(st);
        if (expected == null) {
            return new CheckResult("subject_matches_post_state", "fail", "Missing expected post/source digest");
        }
        Object subjObj = st.get("subject");
        if (!(subjObj instanceof List<?>)) {
            return new CheckResult("subject_matches_post_state", "fail", "Missing subject array");
        }
        List<?> subjects = (List<?>) subjObj;
        if (subjects.isEmpty()) {
            return new CheckResult("subject_matches_post_state", "fail", "Empty subject array");
        }
        for (Object item : subjects) {
            if (!(item instanceof Map<?, ?>)) {
                return new CheckResult("subject_matches_post_state", "fail", "Invalid subject entry");
            }
            Map<String, Object> sMap = (Map<String, Object>) item;
            Map<String, Object> digest = getObject(sMap, "digest");
            if (digest == null || !expected.equals(digest.get("sha256"))) {
                return new CheckResult("subject_matches_post_state", "fail", "Subject digest does not match expected state digest");
            }
        }
        return new CheckResult("subject_matches_post_state", "pass", "Every subject matches expected digest");
    }

    // Check 6: data_identity
    private static CheckResult checkDataIdentity(Map<String, Object> st, byte[] dataBytes) {
        if (dataBytes == null) {
            return new CheckResult("data_identity", "skip", "No data bytes supplied");
        }
        String expected = getExpectedDigest(st);
        if (expected == null) {
            return new CheckResult("data_identity", "fail", "Missing expected state digest in predicate");
        }
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            String actual = bytesToHex(md.digest(dataBytes));
            if (expected.equals(actual)) {
                return new CheckResult("data_identity", "pass", "Supplied data SHA-256 matches expected digest");
            }
            return new CheckResult("data_identity", "fail", "Supplied data SHA-256 does not match expected digest");
        } catch (Exception e) {
            return new CheckResult("data_identity", "fail", "SHA-256 error: " + e.getMessage());
        }
    }

    // Check 7: reversibility_complete
    private static CheckResult checkReversibilityComplete(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null || !(pred.get("applied") instanceof Boolean)) {
            return new CheckResult("reversibility_complete", "fail", "Missing predicate or applied flag");
        }
        boolean applied = (Boolean) pred.get("applied");
        if (!applied) {
            return new CheckResult("reversibility_complete", "pass", "Not applied; reversibility fields not required");
        }
        Object rev = pred.get("reversible");
        if (!Boolean.TRUE.equals(rev)) {
            return new CheckResult("reversibility_complete", "fail", "Applied repair must have reversible=true");
        }
        Map<String, Object> journal = getObject(pred, "journal");
        if (journal == null || !isNonEmptyString(journal.get("txn_id"))) {
            return new CheckResult("reversibility_complete", "fail", "Applied repair requires non-empty journal.txn_id");
        }
        if (!isNonEmptyString(pred.get("revert_command"))) {
            return new CheckResult("reversibility_complete", "fail", "Applied repair requires non-empty revert_command");
        }
        return new CheckResult("reversibility_complete", "pass", "Reversibility fields complete");
    }

    // Check 8: verdicts_accepting
    private static CheckResult checkVerdictsAccepting(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null || !(pred.get("applied") instanceof Boolean)) {
            return new CheckResult("verdicts_accepting", "fail", "Missing predicate or applied flag");
        }
        boolean applied = (Boolean) pred.get("applied");
        Map<String, Object> verdicts = getObject(pred, "verdicts");
        if (verdicts == null) {
            return new CheckResult("verdicts_accepting", "fail", "Missing verdicts");
        }
        Object verifier = verdicts.get("verifier");
        Object safety = verdicts.get("safety");
        if (applied) {
            if ("accept".equals(verifier) && "allow".equals(safety)) {
                return new CheckResult("verdicts_accepting", "pass", "Applied verdicts accepting");
            }
            return new CheckResult("verdicts_accepting", "fail", "Applied repair requires verifier=accept and safety=allow");
        } else {
            if (safety instanceof String && !"deny".equals(safety)) {
                return new CheckResult("verdicts_accepting", "pass", "Dry-run safety verdict is not deny");
            }
            return new CheckResult("verdicts_accepting", "fail", "Dry-run safety verdict must not be deny");
        }
    }

    private static final class StrengthCheckOutcome {
        final CheckResult result;
        final Set<Integer> failedFixIndices;

        StrengthCheckOutcome(CheckResult result, Set<Integer> failedFixIndices) {
            this.result = result;
            this.failedFixIndices = failedFixIndices;
        }
    }

    // Check 9: strength_is_earned
    @SuppressWarnings("unchecked")
    private static StrengthCheckOutcome checkStrengthIsEarned(Map<String, Object> st) {
        Set<Integer> failedIndices = new HashSet<>();
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null || !(pred.get("applied") instanceof Boolean)) {
            return new StrengthCheckOutcome(new CheckResult("strength_is_earned", "fail", "Missing predicate or applied"), failedIndices);
        }
        boolean applied = (Boolean) pred.get("applied");
        Set<String> authCols = getAuthoritativeColumnsSet(pred);
        Object fixesObj = pred.get("fixes");
        if (!(fixesObj instanceof List<?>)) {
            return new StrengthCheckOutcome(new CheckResult("strength_is_earned", "fail", "Missing fixes array"), failedIndices);
        }
        List<?> fixes = (List<?>) fixesObj;
        for (int i = 0; i < fixes.size(); i++) {
            Object fObj = fixes.get(i);
            if (!(fObj instanceof Map<?, ?>)) {
                failedIndices.add(i);
                continue;
            }
            Map<String, Object> fix = (Map<String, Object>) fObj;
            Object prov = fix.get("provenance");
            Object col = fix.get("column");
            Object rec = fix.get("verification_strength");

            boolean derivedProven = "deterministic".equals(prov) || (col instanceof String && authCols.contains(col));
            String derived = derivedProven ? "proven" : "plausibility_only";

            // Recorded strength exceeding derived strength is always a failure
            boolean exceeds = "proven".equals(rec) && !"proven".equals(derived);
            // When applied, any unproven fix (recorded plausibility_only or derived != proven) fails
            boolean unprovenWhenApplied = applied && ("plausibility_only".equals(rec) || !"proven".equals(derived));

            if (exceeds || unprovenWhenApplied) {
                failedIndices.add(i);
            }
        }
        if (!failedIndices.isEmpty()) {
            return new StrengthCheckOutcome(
                    new CheckResult("strength_is_earned", "fail", "One or more fixes have unearned or unproven strength"),
                    failedIndices
            );
        }
        return new StrengthCheckOutcome(
                new CheckResult("strength_is_earned", "pass", "All fixes have earned verification strength"),
                failedIndices
        );
    }

    // Check 10: constraints_present
    @SuppressWarnings("unchecked")
    private static CheckResult checkConstraintsPresent(Map<String, Object> st, Set<Integer> failedCheck9Indices) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) {
            return new CheckResult("constraints_present", "fail", "Missing predicate");
        }
        Set<String> authCols = getAuthoritativeColumnsSet(pred);
        Object fixesObj = pred.get("fixes");
        if (!(fixesObj instanceof List<?>)) {
            return new CheckResult("constraints_present", "fail", "Missing fixes array");
        }
        List<?> fixes = (List<?>) fixesObj;
        boolean requiresConstraints = false;
        for (int i = 0; i < fixes.size(); i++) {
            if (failedCheck9Indices.contains(i)) {
                continue; // Do not double-report a fix that already failed check 9 (§7.10)
            }
            Object fObj = fixes.get(i);
            if (!(fObj instanceof Map<?, ?>)) continue;
            Map<String, Object> fix = (Map<String, Object>) fObj;
            Object prov = fix.get("provenance");
            Object col = fix.get("column");
            boolean isTrusted = "deterministic".equals(prov);
            boolean derivedProven = isTrusted || (col instanceof String && authCols.contains(col));
            if (derivedProven && !isTrusted) {
                requiresConstraints = true;
                break;
            }
        }
        if (!requiresConstraints) {
            return new CheckResult("constraints_present", "pass", "No authority-derived untrusted fix requires embedded constraints");
        }
        Map<String, Object> authority = getObject(pred, "authority");
        if (authority == null) {
            return new CheckResult("constraints_present", "fail", "Missing authority object");
        }
        Object constraints = authority.get("constraints");
        if (constraints instanceof Map<?, ?> && !((Map<?, ?>) constraints).isEmpty()) {
            return new CheckResult("constraints_present", "pass", "Non-empty authority.constraints present");
        }
        return new CheckResult("constraints_present", "fail", "Authority-derived proven fix requires non-empty authority.constraints");
    }

    // Check 12: witness_is_coherent
    @SuppressWarnings("unchecked")
    private static CheckResult checkWitnessIsCoherent(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null || !(pred.get("fixes") instanceof List<?>)) {
            return new CheckResult("witness_is_coherent", "skip", "No fixes with witness");
        }
        List<?> fixes = (List<?>) fixesObj(pred);
        boolean anyWitness = false;
        for (Object fObj : fixes) {
            if (!(fObj instanceof Map<?, ?>)) continue;
            Map<String, Object> fix = (Map<String, Object>) fObj;
            if (!fix.containsKey("witness") || fix.get("witness") == null) {
                continue;
            }
            anyWitness = true;
            Object wObj = fix.get("witness");
            if (!(wObj instanceof Map<?, ?>)) {
                return new CheckResult("witness_is_coherent", "fail", "fix.witness must be an object");
            }
            Map<String, Object> w = (Map<String, Object>) wObj;
            if (!isValidAndCoherentWitness(w)) {
                return new CheckResult("witness_is_coherent", "fail", "Witness failed schema or arithmetic coherence check");
            }
        }
        if (!anyWitness) {
            return new CheckResult("witness_is_coherent", "skip", "No fix carries a witness");
        }
        return new CheckResult("witness_is_coherent", "pass", "All witnesses are coherent");
    }

    private static Object fixesObj(Map<String, Object> pred) {
        return pred.get("fixes");
    }

    private static boolean isValidAndCoherentWitness(Map<String, Object> w) {
        // Required: constraint, constraint_kind, group_size, support, value_digests, new_value_digest
        if (!isNonEmptyString(w.get("constraint"))) return false;
        if (!"functional_dependency".equals(w.get("constraint_kind"))) return false;

        Object gsObj = w.get("group_size");
        Object supObj = w.get("support");
        if (!(gsObj instanceof JsonNum) || !((JsonNum) gsObj).isIntGe(1)) return false;
        if (!(supObj instanceof JsonNum) || !((JsonNum) supObj).isIntGe(1)) return false;
        long groupSize = ((JsonNum) gsObj).longVal;
        long support = ((JsonNum) supObj).longVal;

        Object newDigestObj = w.get("new_value_digest");
        if (!isHex16(newDigestObj)) return false;
        String newValueDigest = (String) newDigestObj;

        if (w.containsKey("old_value_digest") && w.get("old_value_digest") != null && !isHex16(w.get("old_value_digest"))) {
            return false;
        }
        if (w.containsKey("determinant_columns") && w.get("determinant_columns") != null
                && !isStringArray(w.get("determinant_columns"))) {
            return false;
        }
        if (w.containsKey("determinant_digests") && w.get("determinant_digests") != null) {
            Object dd = w.get("determinant_digests");
            if (!(dd instanceof List<?>)) return false;
            for (Object item : (List<?>) dd) {
                if (!isHex16(item)) return false;
            }
        }
        boolean truncated = false;
        if (w.containsKey("truncated") && w.get("truncated") != null) {
            if (!(w.get("truncated") instanceof Boolean)) return false;
            truncated = (Boolean) w.get("truncated");
        }

        Object vdObj = w.get("value_digests");
        if (!(vdObj instanceof List<?>)) return false;
        List<?> vdList = (List<?>) vdObj;

        long sumCounts = 0;
        Long matchingNewDigestCount = null;
        for (Object pairObj : vdList) {
            if (!(pairObj instanceof List<?>)) return false;
            List<?> pair = (List<?>) pairObj;
            if (pair.size() != 2) return false;
            Object dObj = pair.get(0);
            Object cObj = pair.get(1);
            if (!isHex16(dObj)) return false;
            if (!(cObj instanceof JsonNum) || !((JsonNum) cObj).isIntGe(0)) return false;
            long count = ((JsonNum) cObj).longVal;
            sumCounts += count;
            if (newValueDigest.equals(dObj)) {
                if (matchingNewDigestCount != null && matchingNewDigestCount != count) {
                    return false;
                }
                matchingNewDigestCount = count;
            }
        }

        // 1. support * 2 > group_size (strict majority)
        if (support * 2 <= groupSize) return false;
        // 2. support <= group_size
        if (support > groupSize) return false;
        // 3. count recorded for new_value_digest in value_digests equals support
        if (matchingNewDigestCount == null || matchingNewDigestCount != support) return false;
        // 4. recorded counts sum to group_size, unless truncated is true
        if (!truncated && sumCounts != groupSize) return false;

        return true;
    }

    // Check 13: authority_is_entailed
    @SuppressWarnings("unchecked")
    private static CheckResult checkAuthorityIsEntailed(Map<String, Object> st) {
        Map<String, Object> pred = getObject(st, "predicate");
        if (pred == null) {
            return new CheckResult("authority_is_entailed", "fail", "Missing predicate");
        }
        Map<String, Object> authority = getObject(pred, "authority");
        if (authority == null || !isStringArray(authority.get("authoritative_columns"))) {
            return new CheckResult("authority_is_entailed", "fail", "Missing or invalid authority.authoritative_columns");
        }
        List<String> claimedList = (List<String>) authority.get("authoritative_columns");
        Set<String> claimedSet = new LinkedHashSet<>(claimedList);

        boolean hasPremiseKey = authority.containsKey("premise") && authority.get("premise") != null;
        if (claimedSet.isEmpty() && !hasPremiseKey) {
            // §7.13 Case 1: authoritative_columns is empty -> passes
            return new CheckResult("authority_is_entailed", "pass", "Empty authoritative_columns claim requires no premise");
        }

        if (!hasPremiseKey) {
            // §7.13 Case 2: authoritative_columns is non-empty and authority.premise is absent/null -> REJECT
            return new CheckResult("authority_is_entailed", "fail", "Non-empty authoritative_columns requires authority.premise");
        }

        Object premiseObj = authority.get("premise");
        if (!(premiseObj instanceof Map<?, ?>)) {
            return new CheckResult("authority_is_entailed", "fail", "authority.premise must be a JSON object");
        }
        Map<String, Object> premise = (Map<String, Object>) premiseObj;
        Set<String> entailed = validateAndComputeEntailedAuthority(premise);
        if (entailed == null) {
            // Violates §6.4.1
            return new CheckResult("authority_is_entailed", "fail", "authority.premise violates section 6.4.1 format rules");
        }

        if (claimedSet.isEmpty()) {
            // §7.13 Case 1: authoritative_columns is empty -> passes
            return new CheckResult("authority_is_entailed", "pass", "Empty authoritative_columns claim passes");
        }

        if (claimedList.size() != claimedSet.size()) {
            return new CheckResult("authority_is_entailed", "fail", "Duplicate columns in authoritative_columns");
        }

        if (!claimedSet.equals(entailed)) {
            return new CheckResult("authority_is_entailed", "fail",
                    "Claimed authoritative_columns " + claimedSet + " does not equal entailed " + entailed);
        }

        return new CheckResult("authority_is_entailed", "pass", "authoritative_columns equals authoritative(premise)");
    }

    @SuppressWarnings("unchecked")
    private static Set<String> validateAndComputeEntailedAuthority(Map<String, Object> premise) {
        if (!PREMISE_FORMAT.equals(premise.get("premise_format"))) {
            return null;
        }
        for (String key : premise.keySet()) {
            if (!PREMISE_TOP_KEYS.contains(key)) {
                return null; // Unknown top-level key in premise (§6.4.1)
            }
        }

        Set<String> entailed = new LinkedHashSet<>();

        // 1. columns: {column: type_name}
        if (premise.containsKey("columns")) {
            Object colsObj = premise.get("columns");
            if (!(colsObj instanceof Map<?, ?>)) return null;
            Map<String, Object> cols = (Map<String, Object>) colsObj;
            if (cols.isEmpty()) return null; // §6.4.1: "A field whose value is empty is omitted"
            for (Map.Entry<String, Object> e : cols.entrySet()) {
                if (e.getKey() == null || !(e.getValue() instanceof String)) return null;
                String normType = ((String) e.getValue()).trim().toLowerCase(Locale.ROOT);
                if (CONFERS_AUTHORITY_TYPES.contains(normType)) {
                    entailed.add(e.getKey());
                }
            }
        }

        // 2. Four sorted [column] sets: pii_columns, primary_key_columns, not_null_columns, unique_columns
        String[] colSetFields = {"pii_columns", "primary_key_columns", "not_null_columns", "unique_columns"};
        for (String field : colSetFields) {
            if (premise.containsKey(field)) {
                List<String> list = validateSortedNonEmptyColumnArray(premise.get(field));
                if (list == null) return null;
                if (!"pii_columns".equals(field)) {
                    entailed.addAll(list);
                }
            }
        }

        // 3. functional_dependencies: [{determinant: [column], dependent: column}]
        if (premise.containsKey("functional_dependencies")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("functional_dependencies"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList("determinant", "dependent"));
            for (Map<String, Object> r : rules) {
                if (!r.keySet().equals(allowed)) return null;
                if (!(r.get("dependent") instanceof String)) return null;
                if (!isNonEmptyStringArray(r.get("determinant"))) return null;
                entailed.add((String) r.get("dependent"));
                entailed.addAll((List<String>) r.get("determinant"));
            }
        }

        // 4. accepted_values: [{column, values: [string]}]
        if (premise.containsKey("accepted_values")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("accepted_values"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList("column", "values"));
            for (Map<String, Object> r : rules) {
                if (!r.keySet().equals(allowed)) return null;
                if (!(r.get("column") instanceof String)) return null;
                if (!isNonEmptyStringArray(r.get("values"))) return null;
                entailed.add((String) r.get("column"));
            }
        }

        // 5. regex_constraints: [{column, pattern}]
        if (premise.containsKey("regex_constraints")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("regex_constraints"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList("column", "pattern"));
            for (Map<String, Object> r : rules) {
                if (!r.keySet().equals(allowed)) return null;
                if (!(r.get("column") instanceof String) || !(r.get("pattern") instanceof String)) return null;
                entailed.add((String) r.get("column"));
            }
        }

        // 6. relationships: [{column, reference, reference_column}] (confers nothing)
        if (premise.containsKey("relationships")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("relationships"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList("column", "reference", "reference_column"));
            for (Map<String, Object> r : rules) {
                if (!r.keySet().equals(allowed)) return null;
                if (!(r.get("column") instanceof String)
                        || !(r.get("reference") instanceof String)
                        || !(r.get("reference_column") instanceof String)) {
                    return null;
                }
            }
        }

        // 7. domain_bounds: [{column, min_value, max_value, inclusive_min, inclusive_max}]
        if (premise.containsKey("domain_bounds")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("domain_bounds"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList(
                    "column", "min_value", "max_value", "inclusive_min", "inclusive_max"
            ));
            for (Map<String, Object> r : rules) {
                if (!allowed.containsAll(r.keySet())) return null;
                if (!(r.get("column") instanceof String)) return null;
                if (r.containsKey("min_value") && r.get("min_value") != null && !(r.get("min_value") instanceof JsonNum)) {
                    return null;
                }
                if (r.containsKey("max_value") && r.get("max_value") != null && !(r.get("max_value") instanceof JsonNum)) {
                    return null;
                }
                if (r.containsKey("inclusive_min") && !(r.get("inclusive_min") instanceof Boolean)) {
                    return null;
                }
                if (r.containsKey("inclusive_max") && !(r.get("inclusive_max") instanceof Boolean)) {
                    return null;
                }
                entailed.add((String) r.get("column"));
            }
        }

        // 8. aggregate_dependencies: [{source_column, target_column, aggregate, group_by: [column]}] (confers nothing)
        if (premise.containsKey("aggregate_dependencies")) {
            List<Map<String, Object>> rules = getNonEmptyRuleArray(premise.get("aggregate_dependencies"));
            if (rules == null) return null;
            Set<String> allowed = new HashSet<>(Arrays.asList("source_column", "target_column", "aggregate", "group_by"));
            for (Map<String, Object> r : rules) {
                if (!allowed.containsAll(r.keySet())) return null;
                if (!(r.get("source_column") instanceof String) || !(r.get("target_column") instanceof String)) {
                    return null;
                }
                Object agg = r.get("aggregate");
                if (!"sum".equals(agg) && !"avg".equals(agg)) return null;
                if (r.containsKey("group_by") && !isStringArray(r.get("group_by"))) return null;
            }
        }

        return entailed;
    }

    @SuppressWarnings("unchecked")
    private static List<String> validateSortedNonEmptyColumnArray(Object obj) {
        if (!isNonEmptyStringArray(obj)) return null;
        List<String> list = (List<String>) obj;
        for (int i = 1; i < list.size(); i++) {
            if (list.get(i - 1).compareTo(list.get(i)) >= 0) {
                return null; // Must be sorted and set-unique (§6.4.1)
            }
        }
        return list;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> getNonEmptyRuleArray(Object obj) {
        if (!(obj instanceof List<?>)) return null;
        List<?> list = (List<?>) obj;
        if (list.isEmpty()) return null; // §6.4.1: empty fields must be omitted
        List<Map<String, Object>> out = new ArrayList<>(list.size());
        for (Object item : list) {
            if (!(item instanceof Map<?, ?>)) return null;
            out.add((Map<String, Object>) item);
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private static Set<String> getAuthoritativeColumnsSet(Map<String, Object> pred) {
        Map<String, Object> auth = getObject(pred, "authority");
        if (auth == null) return Collections.emptySet();
        Object cols = auth.get("authoritative_columns");
        if (!isStringArray(cols)) return Collections.emptySet();
        return new HashSet<>((List<String>) cols);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> getObject(Map<String, Object> parent, String key) {
        if (parent == null) return null;
        Object v = parent.get(key);
        if (v instanceof Map<?, ?>) {
            return (Map<String, Object>) v;
        }
        return null;
    }

    private static boolean isNonEmptyString(Object o) {
        return (o instanceof String) && !((String) o).isEmpty();
    }

    private static boolean isHex64(Object o) {
        return (o instanceof String) && HEX_64.matcher((String) o).matches();
    }

    private static boolean isHex16(Object o) {
        return (o instanceof String) && HEX_16.matcher((String) o).matches();
    }

    private static boolean isStringArray(Object o) {
        if (!(o instanceof List<?>)) return false;
        for (Object item : (List<?>) o) {
            if (!(item instanceof String)) return false;
        }
        return true;
    }

    private static boolean isNonEmptyStringArray(Object o) {
        return isStringArray(o) && !((List<?>) o).isEmpty();
    }

    private static byte[] hexToBytes(String hex) {
        if (hex.length() % 2 != 0) {
            throw new IllegalArgumentException("Odd-length hex string");
        }
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            int hi = Character.digit(hex.charAt(i * 2), 16);
            int lo = Character.digit(hex.charAt(i * 2 + 1), 16);
            if (hi < 0 || lo < 0) {
                throw new IllegalArgumentException("Invalid hex character");
            }
            out[i] = (byte) ((hi << 4) | lo);
        }
        return out;
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    private static String escapeJson(String s) {
        StringBuilder sb = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    private static String formatOutput(boolean ok, List<CheckResult> checks) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\": ").append(ok).append(", \"checks\": [");
        for (int i = 0; i < checks.size(); i++) {
            if (i > 0) sb.append(", ");
            CheckResult c = checks.get(i);
            sb.append("{\"name\": \"").append(escapeJson(c.name))
              .append("\", \"status\": \"").append(escapeJson(c.status))
              .append("\", \"detail\": \"").append(escapeJson(c.detail))
              .append("\"}");
        }
        sb.append("]}");
        return sb.toString();
    }
}
