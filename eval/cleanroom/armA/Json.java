import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal JSON model and recursive-descent parser. JDK stdlib only.
 *
 * The model deliberately distinguishes "key absent" from "key present with value null",
 * because the specification's field table (SPEC section 6.2) marks several fields as
 * Required = yes with a type of "X | null" -- i.e. the key must exist and the value may
 * be null. A model that collapsed those two states could not enforce that.
 */
abstract class J {

    static final class Obj extends J {
        final Map<String, J> m = new LinkedHashMap<>();
    }

    static final class Arr extends J {
        final List<J> a = new ArrayList<>();
    }

    static final class Str extends J {
        final String v;
        Str(String v) { this.v = v; }
    }

    static final class Num extends J {
        final String raw;
        Num(String raw) { this.raw = raw; }
        boolean isIntegral() {
            return raw.indexOf('.') < 0 && raw.indexOf('e') < 0 && raw.indexOf('E') < 0;
        }
        long asLong() { return Long.parseLong(raw); }
    }

    static final class Bool extends J {
        final boolean v;
        Bool(boolean v) { this.v = v; }
    }

    static final class Null extends J {
    }

    boolean isNull() { return this instanceof Null; }

    Obj obj() { return (this instanceof Obj) ? (Obj) this : null; }

    Arr arr() { return (this instanceof Arr) ? (Arr) this : null; }

    /** the string value, or null when this node is not a JSON string */
    String str() { return (this instanceof Str) ? ((Str) this).v : null; }

    /** the boolean value, or null when this node is not a JSON boolean */
    Boolean bool() { return (this instanceof Bool) ? ((Bool) this).v : null; }

    /** member lookup: null when absent, or when this node is not an object */
    J get(String k) {
        Obj o = obj();
        return (o == null) ? null : o.m.get(k);
    }

    /** true only when this node is an object that carries the key (value may be null) */
    boolean has(String k) {
        Obj o = obj();
        return o != null && o.m.containsKey(k);
    }

    /** dotted-path lookup; null as soon as any hop is absent or non-object */
    J path(String dotted) {
        J cur = this;
        for (String part : dotted.split("\\.")) {
            if (cur == null) return null;
            cur = cur.get(part);
        }
        return cur;
    }

    String typeName() {
        if (this instanceof Obj) return "object";
        if (this instanceof Arr) return "array";
        if (this instanceof Str) return "string";
        if (this instanceof Num) return "number";
        if (this instanceof Bool) return "boolean";
        return "null";
    }
}

final class JsonException extends Exception {
    private static final long serialVersionUID = 1L;
    JsonException(String m) { super(m); }
}

final class Jp {

    private final String s;
    private int i;

    private Jp(String s) { this.s = s; }

    static J parse(String text) throws JsonException {
        String t = text;
        if (!t.isEmpty() && t.charAt(0) == '\uFEFF') {
            t = t.substring(1);
        }
        Jp p = new Jp(t);
        p.ws();
        J v = p.value();
        p.ws();
        if (p.i != p.s.length()) {
            throw new JsonException("trailing content at offset " + p.i);
        }
        return v;
    }

    private void ws() {
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                i++;
            } else {
                break;
            }
        }
    }

    private char peek() throws JsonException {
        if (i >= s.length()) throw new JsonException("unexpected end of input");
        return s.charAt(i);
    }

    private J value() throws JsonException {
        char c = peek();
        switch (c) {
            case '{': return object();
            case '[': return array();
            case '"': return new J.Str(string());
            case 't': lit("true");  return new J.Bool(true);
            case 'f': lit("false"); return new J.Bool(false);
            case 'n': lit("null");  return new J.Null();
            default:  return number();
        }
    }

    private void lit(String want) throws JsonException {
        if (!s.startsWith(want, i)) {
            throw new JsonException("invalid literal at offset " + i);
        }
        i += want.length();
    }

    private J object() throws JsonException {
        expect('{');
        J.Obj o = new J.Obj();
        ws();
        if (peek() == '}') { i++; return o; }
        while (true) {
            ws();
            if (peek() != '"') throw new JsonException("object key must be a string, offset " + i);
            String k = string();
            ws();
            expect(':');
            ws();
            J v = value();
            // Duplicate keys: last one wins (matches the common JSON.parse behaviour).
            o.m.put(k, v);
            ws();
            char c = peek();
            if (c == ',') { i++; continue; }
            if (c == '}') { i++; return o; }
            throw new JsonException("expected ',' or '}' at offset " + i);
        }
    }

    private J array() throws JsonException {
        expect('[');
        J.Arr a = new J.Arr();
        ws();
        if (peek() == ']') { i++; return a; }
        while (true) {
            ws();
            a.a.add(value());
            ws();
            char c = peek();
            if (c == ',') { i++; continue; }
            if (c == ']') { i++; return a; }
            throw new JsonException("expected ',' or ']' at offset " + i);
        }
    }

    private void expect(char c) throws JsonException {
        if (peek() != c) throw new JsonException("expected '" + c + "' at offset " + i);
        i++;
    }

    private String string() throws JsonException {
        expect('"');
        StringBuilder b = new StringBuilder();
        while (true) {
            if (i >= s.length()) throw new JsonException("unterminated string");
            char c = s.charAt(i++);
            if (c == '"') return b.toString();
            if (c == '\\') {
                if (i >= s.length()) throw new JsonException("unterminated escape");
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
                        if (i + 4 > s.length()) throw new JsonException("truncated \\u escape");
                        String h = s.substring(i, i + 4);
                        i += 4;
                        try {
                            b.append((char) Integer.parseInt(h, 16));
                        } catch (NumberFormatException nfe) {
                            throw new JsonException("bad \\u escape: " + h);
                        }
                        break;
                    }
                    default: throw new JsonException("bad escape \\" + e);
                }
            } else if (c < 0x20) {
                throw new JsonException("raw control character in string at offset " + (i - 1));
            } else {
                b.append(c);
            }
        }
    }

    private J number() throws JsonException {
        int start = i;
        if (i < s.length() && s.charAt(i) == '-') i++;
        while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        if (i < s.length() && s.charAt(i) == '.') {
            i++;
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        }
        if (i < s.length() && (s.charAt(i) == 'e' || s.charAt(i) == 'E')) {
            i++;
            if (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) i++;
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        }
        String raw = s.substring(start, i);
        if (raw.isEmpty() || raw.equals("-")) {
            throw new JsonException("invalid token at offset " + start);
        }
        try {
            Double.parseDouble(raw);
        } catch (NumberFormatException nfe) {
            throw new JsonException("invalid number '" + raw + "' at offset " + start);
        }
        return new J.Num(raw);
    }
}
