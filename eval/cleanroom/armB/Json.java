import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;

/**
 * Minimal strict JSON parser (RFC 8259) built on the JDK standard library only.
 *
 * Model: LinkedHashMap<String,Object> | List<Object> | String | Boolean | BigDecimal | Json.NULL
 *
 * Json.NULL is a distinct sentinel so that "present and null" can be told apart from
 * "absent". The attestation format needs that distinction: several fields are required to
 * be PRESENT while permitted to be null.
 *
 * Duplicate object keys are recorded (not silently collapsed) because a document whose
 * meaning depends on which parser you use is not a document a verifier should bless.
 */
final class Json {

    static final Object NULL = new Object() {
        @Override public String toString() { return "null"; }
    };

    static final class ParseException extends RuntimeException {
        ParseException(String m) { super(m); }
    }

    static final class Parsed {
        final Object root;
        final List<String> duplicateKeys;
        Parsed(Object root, List<String> duplicateKeys) {
            this.root = root;
            this.duplicateKeys = duplicateKeys;
        }
    }

    private final String s;
    private int i;
    private final List<String> duplicateKeys = new ArrayList<>();

    private Json(String s) { this.s = s; }

    static Parsed parse(String text) {
        if (text.startsWith("\uFEFF")) text = text.substring(1);
        Json p = new Json(text);
        p.ws();
        Object v = p.value("");
        p.ws();
        if (p.i != p.s.length()) {
            throw new ParseException("trailing content at offset " + p.i);
        }
        return new Parsed(v, p.duplicateKeys);
    }

    private void ws() {
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') i++;
            else break;
        }
    }

    private char peek() {
        if (i >= s.length()) throw new ParseException("unexpected end of input at offset " + i);
        return s.charAt(i);
    }

    private Object value(String path) {
        char c = peek();
        switch (c) {
            case '{': return obj(path);
            case '[': return arr(path);
            case '"': return str();
            case 't': lit("true");  return Boolean.TRUE;
            case 'f': lit("false"); return Boolean.FALSE;
            case 'n': lit("null");  return NULL;
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return num();
                throw new ParseException("unexpected character '" + c + "' at offset " + i);
        }
    }

    private void lit(String word) {
        if (!s.startsWith(word, i)) {
            throw new ParseException("invalid literal at offset " + i);
        }
        i += word.length();
    }

    private Object obj(String path) {
        i++; // consume '{'
        LinkedHashMap<String, Object> m = new LinkedHashMap<>();
        ws();
        if (peek() == '}') { i++; return m; }
        while (true) {
            ws();
            if (peek() != '"') throw new ParseException("expected object key at offset " + i);
            String k = str();
            ws();
            if (peek() != ':') throw new ParseException("expected ':' at offset " + i);
            i++;
            ws();
            String child = path.isEmpty() ? k : path + "." + k;
            Object v = value(child);
            if (m.containsKey(k)) duplicateKeys.add(child);
            m.put(k, v);
            ws();
            char c = peek();
            if (c == ',') { i++; continue; }
            if (c == '}') { i++; return m; }
            throw new ParseException("expected ',' or '}' at offset " + i);
        }
    }

    private Object arr(String path) {
        i++; // consume '['
        List<Object> a = new ArrayList<>();
        ws();
        if (peek() == ']') { i++; return a; }
        while (true) {
            ws();
            a.add(value(path + "[" + a.size() + "]"));
            ws();
            char c = peek();
            if (c == ',') { i++; continue; }
            if (c == ']') { i++; return a; }
            throw new ParseException("expected ',' or ']' at offset " + i);
        }
    }

    private String str() {
        i++; // consume opening quote
        StringBuilder b = new StringBuilder();
        while (true) {
            if (i >= s.length()) throw new ParseException("unterminated string");
            char c = s.charAt(i++);
            if (c == '"') return b.toString();
            if (c == '\\') {
                if (i >= s.length()) throw new ParseException("unterminated escape");
                char e = s.charAt(i++);
                switch (e) {
                    case '"':  b.append('"');  break;
                    case '\\': b.append('\\'); break;
                    case '/':  b.append('/');  break;
                    case 'b':  b.append('\b'); break;
                    case 'f':  b.append('\f'); break;
                    case 'n':  b.append('\n'); break;
                    case 'r':  b.append('\r'); break;
                    case 't':  b.append('\t'); break;
                    case 'u': {
                        if (i + 4 > s.length()) throw new ParseException("truncated \\u escape");
                        String hex = s.substring(i, i + 4);
                        for (int k = 0; k < 4; k++) {
                            char h = hex.charAt(k);
                            boolean ok = (h >= '0' && h <= '9') || (h >= 'a' && h <= 'f') || (h >= 'A' && h <= 'F');
                            if (!ok) throw new ParseException("bad \\u escape '" + hex + "'");
                        }
                        b.append((char) Integer.parseInt(hex, 16));
                        i += 4;
                        break;
                    }
                    default: throw new ParseException("bad escape '\\" + e + "'");
                }
                continue;
            }
            if (c < 0x20) {
                throw new ParseException("unescaped control character U+" + String.format("%04X", (int) c) + " in string");
            }
            b.append(c);
        }
    }

    private Object num() {
        int start = i;
        if (peek() == '-') i++;
        // int part
        if (i >= s.length()) throw new ParseException("truncated number");
        if (s.charAt(i) == '0') {
            i++;
        } else if (s.charAt(i) >= '1' && s.charAt(i) <= '9') {
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        } else {
            throw new ParseException("invalid number at offset " + i);
        }
        // frac
        if (i < s.length() && s.charAt(i) == '.') {
            i++;
            if (i >= s.length() || !Character.isDigit(s.charAt(i))) {
                throw new ParseException("invalid fraction at offset " + i);
            }
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        }
        // exp
        if (i < s.length() && (s.charAt(i) == 'e' || s.charAt(i) == 'E')) {
            i++;
            if (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) i++;
            if (i >= s.length() || !Character.isDigit(s.charAt(i))) {
                throw new ParseException("invalid exponent at offset " + i);
            }
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        }
        return new BigDecimal(s.substring(start, i));
    }
}
