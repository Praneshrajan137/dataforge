import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;

/**
 * DSSE pre-authentication encoding and Ed25519 signature verification.
 *
 * This file is cryptographic plumbing, not specification content. The only
 * specification-derived part is the PAE construction, taken verbatim from
 * SPEC section 4:
 *
 *   SIGNATURE = Sign(PAE(UTF8(PAYLOAD_TYPE), SERIALIZED_BODY))
 *   PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body
 *
 * LEN is the ASCII decimal byte length of the item that follows it.
 */
final class Dsse {

    private Dsse() { }

    static final String DEFAULT_PAYLOAD_TYPE = "application/vnd.in-toto+json";

    /** The 12-byte X.509 SubjectPublicKeyInfo header for a raw Ed25519 key. */
    private static final byte[] ED25519_SPKI_PREFIX = hexToBytes("302a300506032b6570032100");

    static byte[] pae(String payloadType, byte[] body) {
        byte[] type = payloadType.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        write(out, "DSSEv1");
        out.write(' ');
        write(out, Integer.toString(type.length));
        out.write(' ');
        out.write(type, 0, type.length);
        out.write(' ');
        write(out, Integer.toString(body.length));
        out.write(' ');
        out.write(body, 0, body.length);
        return out.toByteArray();
    }

    private static void write(ByteArrayOutputStream out, String ascii) {
        byte[] b = ascii.getBytes(StandardCharsets.US_ASCII);
        out.write(b, 0, b.length);
    }

    /** Wraps 32 raw Ed25519 public-key bytes in SPKI DER and builds a PublicKey. */
    static PublicKey publicKeyFromRaw(byte[] raw) throws Exception {
        if (raw.length != 32) {
            throw new IllegalArgumentException("Ed25519 public key must be 32 bytes, got " + raw.length);
        }
        byte[] der = new byte[ED25519_SPKI_PREFIX.length + 32];
        System.arraycopy(ED25519_SPKI_PREFIX, 0, der, 0, ED25519_SPKI_PREFIX.length);
        System.arraycopy(raw, 0, der, ED25519_SPKI_PREFIX.length, 32);
        return KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(der));
    }

    static boolean verify(PublicKey key, byte[] message, byte[] sig) {
        try {
            Signature s = Signature.getInstance("Ed25519");
            s.initVerify(key);
            s.update(message);
            return s.verify(sig);
        } catch (Exception e) {
            // A malformed signature encoding is a failed verification, not a crash.
            return false;
        }
    }

    static byte[] hexToBytes(String hex) {
        int n = hex.length();
        if ((n & 1) != 0) throw new IllegalArgumentException("odd-length hex string");
        byte[] out = new byte[n / 2];
        for (int i = 0; i < n; i += 2) {
            int hi = Character.digit(hex.charAt(i), 16);
            int lo = Character.digit(hex.charAt(i + 1), 16);
            if (hi < 0 || lo < 0) throw new IllegalArgumentException("non-hex character in key");
            out[i / 2] = (byte) ((hi << 4) | lo);
        }
        return out;
    }

    static String bytesToHex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(Character.forDigit((x >> 4) & 0xf, 16))
                          .append(Character.forDigit(x & 0xf, 16));
        return sb.toString();
    }
}
