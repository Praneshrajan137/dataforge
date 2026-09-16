import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * A clean-room normative verifier for dataforge.repair.attestation/v1.
 *
 * Built from specs/SPEC_repair_attestation.md and specs/repair_attestation.schema.json
 * only. Implements the normative tier of section 7 -- twelve checks, reported
 * individually and in the specification's order -- and not the advisory tier,
 * which section 7 explicitly excludes from the spec.
 *
 * Usage:
 *   java -cp <dir> Verify --attestation <path> [--pubkey-hex <64 hex chars>] [--data <path>]
 *
 * Exit status: 0 whenever a verdict was produced, including a rejecting one.
 * Non-zero only when no verdict could be produced at all.
 */
public final class Verify {

    private static final int EXIT_VERDICT = 0;
    private static final int EXIT_NO_VERDICT = 2;

    public static void main(String[] args) {
        PrintStream out = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out),
                true, StandardCharsets.UTF_8);
        PrintStream err = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.err),
                true, StandardCharsets.UTF_8);

        String attestationPath = null;
        String pubkeyHex = null;
        String dataPath = null;

        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            switch (a) {
                case "--attestation":
                    if (++i >= args.length) { die(err, "--attestation requires a path"); return; }
                    attestationPath = args[i];
                    break;
                case "--pubkey-hex":
                    if (++i >= args.length) { die(err, "--pubkey-hex requires a value"); return; }
                    pubkeyHex = args[i];
                    break;
                case "--data":
                    if (++i >= args.length) { die(err, "--data requires a path"); return; }
                    dataPath = args[i];
                    break;
                default:
                    die(err, "unrecognised argument: " + a);
                    return;
            }
        }
        if (attestationPath == null) {
            die(err, "--attestation <path> is required");
            return;
        }

        byte[] pubkeyRaw = null;
        if (pubkeyHex != null) {
            String h = pubkeyHex.trim().toLowerCase();
            if (h.startsWith("0x")) h = h.substring(2);
            if (h.length() != 64) {
                die(err, "--pubkey-hex must be 64 hex characters (32 raw Ed25519 bytes), got "
                        + h.length());
                return;
            }
            try {
                pubkeyRaw = Dsse.hexToBytes(h);
            } catch (IllegalArgumentException e) {
                die(err, "--pubkey-hex is not valid hex: " + e.getMessage());
                return;
            }
        }

        String attestationText;
        try {
            attestationText = new String(Files.readAllBytes(Path.of(attestationPath)),
                    StandardCharsets.UTF_8);
        } catch (Exception e) {
            die(err, "cannot read attestation file '" + attestationPath + "': " + e.getMessage());
            return;
        }
        // Strip a UTF-8 BOM if present; it is not part of the JSON text.
        if (!attestationText.isEmpty() && attestationText.charAt(0) == '\uFEFF') {
            attestationText = attestationText.substring(1);
        }

        byte[] dataBytes = null;
        if (dataPath != null) {
            try {
                dataBytes = Files.readAllBytes(Path.of(dataPath));
            } catch (Exception e) {
                die(err, "cannot read data file '" + dataPath + "': " + e.getMessage());
                return;
            }
        }

        JVal document;
        try {
            document = Json.parse(attestationText);
        } catch (JsonException e) {
            die(err, "attestation is not parseable JSON: " + e.getMessage());
            return;
        }

        // --- Resolve the statement -------------------------------------------
        // SPEC 6.1: unsigned, the document is a bare in-toto Statement; signed,
        // that Statement is base64'd into a DSSE envelope's "payload".
        //
        // SPEC 6.1 also states: "Verifiers MUST NOT re-parse the envelope after
        // signature verification to obtain the payload." The payload bytes are
        // therefore decoded exactly once, here, and the statement used by every
        // check is the parse of those same bytes -- the bytes the signature
        // covers. Nothing downstream re-derives the statement from the envelope.
        boolean isEnvelope = false;
        JVal envelope = null;
        byte[] payloadBytes = null;
        JVal statement = null;
        String statementError = null;

        JVal payloadField = document.isObj() ? document.get("payload") : null;
        if (payloadField != null && payloadField.isStr()) {
            isEnvelope = true;
            envelope = document;
            try {
                payloadBytes = Checks.decodeBase64(payloadField.str);
            } catch (Exception e) {
                statementError = "envelope payload is not valid base64";
            }
            if (payloadBytes != null) {
                try {
                    statement = Json.parse(new String(payloadBytes, StandardCharsets.UTF_8));
                } catch (JsonException e) {
                    statementError = "envelope payload does not contain parseable JSON: "
                            + e.getMessage();
                }
            }
        } else {
            statement = document;
        }

        Checks checks = new Checks(statement, statementError, isEnvelope, envelope,
                payloadBytes, pubkeyRaw, dataBytes, dataPath);
        List<Checks.Check> results = checks.run();

        boolean ok = true;
        for (Checks.Check c : results) {
            if (Checks.FAIL.equals(c.status)) { ok = false; break; }
        }

        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":").append(ok).append(",\"checks\":[");
        for (int i = 0; i < results.size(); i++) {
            Checks.Check c = results.get(i);
            if (i > 0) sb.append(',');
            sb.append("{\"name\":\"").append(Json.escape(c.name))
              .append("\",\"status\":\"").append(Json.escape(c.status))
              .append("\",\"detail\":\"").append(Json.escape(c.detail == null ? "" : c.detail))
              .append("\"}");
        }
        sb.append("]}");
        out.println(sb);
        System.exit(EXIT_VERDICT);
    }

    /** Reports a condition under which no verdict can be produced at all. */
    private static void die(PrintStream err, String message) {
        err.println("verify: " + message);
        System.exit(EXIT_NO_VERDICT);
    }
}
