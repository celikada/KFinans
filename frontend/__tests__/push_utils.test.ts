import { describe, expect, it } from "vitest";
import { arrayBufferToBase64Url, urlBase64ToUint8Array } from "../lib/push-utils";

describe("urlBase64ToUint8Array", () => {
  it("decodes a url-safe base64 string with padding restored", () => {
    // "hello" → base64 "aGVsbG8="; url-safe form drops/keeps alphabet but here no -_ chars.
    const out = urlBase64ToUint8Array("aGVsbG8");
    expect(Array.from(out)).toEqual([104, 101, 108, 108, 111]); // "hello" bytes
  });

  it("handles url-safe alphabet (- and _)", () => {
    // bytes [251, 255] → standard base64 "+/8=" → url-safe "-_8"
    const out = urlBase64ToUint8Array("-_8");
    expect(Array.from(out)).toEqual([251, 255]);
  });

  it("returns a Uint8Array", () => {
    expect(urlBase64ToUint8Array("AAAA")).toBeInstanceOf(Uint8Array);
  });
});

describe("arrayBufferToBase64Url", () => {
  it("returns empty string for null", () => {
    expect(arrayBufferToBase64Url(null)).toBe("");
  });

  it("encodes bytes to url-safe base64 without padding", () => {
    const buf = new Uint8Array([251, 255]).buffer;
    expect(arrayBufferToBase64Url(buf)).toBe("-_8");
  });

  it("round-trips with urlBase64ToUint8Array", () => {
    const original = new Uint8Array([0, 1, 2, 250, 251, 252, 253, 254, 255]);
    const encoded = arrayBufferToBase64Url(original.buffer);
    const decoded = urlBase64ToUint8Array(encoded);
    expect(Array.from(decoded)).toEqual(Array.from(original));
  });
});
