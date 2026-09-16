import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;

/**
 * Minimal JSON value model and recursive-descent parser.
 *
 * The JDK ships no JSON parser, so this is written by hand. It is deliberately
 * strict: it accepts RFC 8259 and nothing else, because a verifier that is lax
 * about its input format has already stopped being a verifier.
 *
 * Numbers keep an "integral" flag. JSON Schema draft 2020-12 defines "integer"
 * as any number with a zero fractional part, so 5.0 counts as an integer and
 * 5.5 does not; the flag records that distinction. Booleans are their own kind
 * and are never numbers.
 */
final class JVal {
    static final int OBJ = 0, ARR = 1, STR = 2, NUM = 3, BOOL = 4, NUL = 5;

    final int kind;
    LinkedHashMap<String, JVal> obj;
    List<JVal> arr;
    String str;
    double num;
    boolean integral;
    boolean bool;

    private JVal(int kind) { this.kind = kind; }

    static JVal object() { JVal v = new JVal(OBJ); v.obj = new LinkedHashMap<>(); return v; }
    static JVal array() { JVal v = new JVal(ARR); v.arr = new ArrayList<>(); return v; }
    static JVal string(String s) { JVal v = new JVal(STR); v.str = s; return v; }
    static JVal number(double d, boolean integral) {
        JVal v = new JVal(NUM); v.num = d; v.integral = integral; return v;
    }
    static JVal bool(boolean b) { JVal v = new JVal(BOOL); v.bool = b; return v; }
    static JVal nul() { return new JVal(NUL); }

    boolean isObj()  { return kind == OBJ; }
    boolean isArr()  { return kind == ARR; }
    boolean isStr()  { return kind == STR; }
    boolean isNum()  { return kind == NUM; }
    boolean isBool() { return kind == BOOL; }
    boolean isNull() { return kind == NUL; }

    /** True for a JSON number whose fractional part is zero (JSON Schema "integer"). */
    boolean isInt() { return kind == NUM && integral; }

    long asLong() { return (long) num; }

    /** Member lookup; null when this is not an object or the key is absent. */
    JVal get(String key) { return kind == OBJ ? obj.get(key) : null; }

    int size() { return kind == ARR ? arr.size() : (kind == OBJ ? obj.size() : 0); }

    /** A short, safe rendering of this value's type for use in detail messages. */
    String typeName() {
        switch (kind) {
            case OBJ:  return "object";
            case ARR:  return "array";
            case STR:  return "string";
            case NUM:  return integral ? "integer" : "number";
            case BOOL: return "boolean";
            default:   return "null";
        }
    }
}

class JsonException extends Exception {
    JsonException(String message) { super(message); }
}

final class Json {

    private final String src;
    private int pos;

    private Json(String src) { this.src = src; this.pos = 0; }

    static JVal parse(String text) throws JsonException {
        Json p = new Json(text);
        p.skipWs();
        JVal v = p.parseValue();
        p.skipWs();
        if (p.pos != p.src.length()) {
            throw new JsonException("trailing content at offset " + p.pos);
        }
        return v;
    }

    private JsonException err(String what) {
        return new JsonException(what + " at offset " + pos);
    }

    private void skipWs() {
        while (pos < src.length()) {
            char c = src.charAt(pos);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') pos++;
            else break;
        }
    }

    private char peek() throws JsonException {
        if (pos >= src.length()) throw err("unexpected end of input");
        return src.charAt(pos);
    }

    private JVal parseValue() throws JsonException {
        char c = peek();
        switch (c) {
            case '{': return parseObject();
            case '[': return parseArray();
            case '"': return JVal.string(parseString());
            case 't': expect("true");  return JVal.bool(true);
            case 'f': expect("false"); return JVal.bool(false);
            case 'n': expect("null");  return JVal.nul();
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return parseNumber();
                throw err("unexpected character '" + c + "'");
        }
    }

    private void expect(String literal) throws JsonException {
        if (!src.startsWith(literal, pos)) throw err("expected '" + literal + "'");
        pos += literal.length();
    }

    private JVal parseObject() throws JsonException {
        JVal o = JVal.object();
        pos++; // '{'
        skipWs();
        if (peek() == '}') { pos++; return o; }
        while (true) {
            skipWs();
            if (peek() != '"') throw err("expected object key");
            String key = parseString();
            skipWs();
            if (peek() != ':') throw err("expected ':'");
            pos++;
            skipWs();
            JVal val = parseValue();
            // Last-one-wins on duplicate keys, matching most mainstream parsers.
            o.obj.put(key, val);
            skipWs();
            char c = peek();
            if (c == ',') { pos++; continue; }
            if (c == '}') { pos++; return o; }
            throw err("expected ',' or '}'");
        }
    }

    private JVal parseArray() throws JsonException {
        JVal a = JVal.array();
        pos++; // '['
        skipWs();
        if (peek() == ']') { pos++; return a; }
        while (true) {
            skipWs();
            a.arr.add(parseValue());
            skipWs();
            char c = peek();
            if (c == ',') { pos++; continue; }
            if (c == ']') { pos++; return a; }
            throw err("expected ',' or ']'");
        }
    }

    private String parseString() throws JsonException {
        pos++; // opening quote
        StringBuilder sb = new StringBuilder();
        while (true) {
            if (pos >= src.length()) throw err("unterminated string");
            char c = src.charAt(pos++);
            if (c == '"') return sb.toString();
            if (c == '\\') {
                if (pos >= src.length()) throw err("unterminated escape");
                char e = src.charAt(pos++);
                switch (e) {
                    case '"':  sb.append('"');  break;
                    case '\\': sb.append('\\'); break;
                    case '/':  sb.append('/');  break;
                    case 'b':  sb.append('\b'); break;
                    case 'f':  sb.append('\f'); break;
                    case 'n':  sb.append('\n'); break;
                    case 'r':  sb.append('\r'); break;
                    case 't':  sb.append('\t'); break;
                    case 'u': {
                        if (pos + 4 > src.length()) throw err("truncated \\u escape");
                        String hex = src.substring(pos, pos + 4);
                        pos += 4;
                        try {
                            sb.append((char) Integer.parseInt(hex, 16));
                        } catch (NumberFormatException nfe) {
                            throw err("bad \\u escape '" + hex + "'");
                        }
                        break;
                    }
                    default: throw err("bad escape '\\" + e + "'");
                }
            } else if (c < 0x20) {
                throw err("unescaped control character in string");
            } else {
                sb.append(c);
            }
        }
    }

    private JVal parseNumber() throws JsonException {
        int start = pos;
        if (pos < src.length() && src.charAt(pos) == '-') pos++;
        if (pos >= src.length()) throw err("truncated number");
        if (src.charAt(pos) == '0') {
            pos++;
        } else if (src.charAt(pos) >= '1' && src.charAt(pos) <= '9') {
            while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
        } else {
            throw err("bad number");
        }
        boolean sawFraction = false;
        if (pos < src.length() && src.charAt(pos) == '.') {
            sawFraction = true;
            pos++;
            if (pos >= src.length() || !Character.isDigit(src.charAt(pos))) throw err("bad fraction");
            while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
        }
        if (pos < src.length() && (src.charAt(pos) == 'e' || src.charAt(pos) == 'E')) {
            pos++;
            if (pos < src.length() && (src.charAt(pos) == '+' || src.charAt(pos) == '-')) pos++;
            if (pos >= src.length() || !Character.isDigit(src.charAt(pos))) throw err("bad exponent");
            while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
        }
        String lit = src.substring(start, pos);
        double d;
        try {
            d = Double.parseDouble(lit);
        } catch (NumberFormatException nfe) {
            throw err("unparseable number '" + lit + "'");
        }
        // JSON Schema 2020-12: "integer" is any number with a zero fractional
        // part, so 5.0 is an integer. Guard against non-finite and huge values.
        boolean integral = Double.isFinite(d) && d == Math.rint(d)
                && Math.abs(d) <= 9.007199254740992E15;
        if (sawFraction && !integral) integral = false;
        return JVal.number(d, integral);
    }

    /** Escapes a string as a JSON string body (without the surrounding quotes). */
    static String escape(String s) {
        StringBuilder sb = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b");  break;
                case '\f': sb.append("\\f");  break;
                case '\n': sb.append("\\n");  break;
                case '\r': sb.append("\\r");  break;
                case '\t': sb.append("\\t");  break;
                default:
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
            }
        }
        return sb.toString();
    }
}
