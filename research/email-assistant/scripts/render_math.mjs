#!/usr/bin/env node
/**
 * render_math.mjs — convert LaTeX math in an HTML file to native MathML.
 *
 * MathML renders natively in Apple Mail, Safari, Chrome/Edge 109+,
 * Firefox, Thunderbird — no JS, no images, no CSS, no fonts.
 * For Outlook desktop (Word engine, no MathML) an MSO conditional-comment
 * fallback shows a Unicode/HTML approximation of the formula.
 *
 * Usage: node render_math.mjs <file.html>   (edits the file in place)
 * Exit: 0 ok (stats to stderr), 2 usage/dependency error.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const LIB = process.env.MATHLIB_DIR || path.join(process.env.HOME, ".local/cron/lib");
const req = createRequire(path.join(LIB, "package.json"));

let katex;
try {
  katex = req("katex");
} catch (e) {
  console.error(`render_math: dependency error (run: npm i katex in ${LIB}): ${e.message}`);
  process.exit(2);
}

const file = process.argv[2];
if (!file || !fs.existsSync(file)) {
  console.error("usage: render_math.mjs <file.html>");
  process.exit(2);
}
let html = fs.readFileSync(file, "utf8");

// protect <style>/<script> blocks from substitution
const blocks = [];
html = html.replace(/<(style|script)\b[\s\S]*?<\/\1>/gi, (m) => {
  blocks.push(m);
  return `\u0000B${blocks.length - 1}\u0000`;
});

// ---------- TeX -> MathML (KaTeX) ----------
function texToMathML(tex, display) {
  const out = katex.renderToString(tex, { displayMode: display, throwOnError: true });
  const m = out.match(/<math[\s\S]*?<\/math>/);
  if (!m) throw new Error("no MathML in KaTeX output");
  return m[0];
}

// ---------- TeX -> Unicode/HTML approximation (Outlook fallback) ----------
const SYM = {
  alpha:"α", beta:"β", gamma:"γ", delta:"δ", epsilon:"ε", zeta:"ζ", eta:"η",
  theta:"θ", iota:"ι", kappa:"κ", lambda:"λ", mu:"μ", nu:"ν", xi:"ξ", pi:"π",
  rho:"ρ", sigma:"σ", tau:"τ", upsilon:"υ", phi:"φ", chi:"χ", psi:"ψ", omega:"ω",
  Gamma:"Γ", Delta:"Δ", Theta:"Θ", Lambda:"Λ", Xi:"Ξ", Pi:"Π", Sigma:"Σ",
  Phi:"Φ", Psi:"Ψ", Omega:"Ω",
  cdot:"⋅", times:"×", div:"÷", pm:"±", mp:"∓", infty:"∞", le:"≤", leq:"≤",
  ge:"≥", geq:"≥", ne:"≠", neq:"≠", approx:"≈", equiv:"≡", sim:"∼", simeq:"≃",
  propto:"∝", to:"→", rightarrow:"→", Rightarrow:"⇒", leftarrow:"←",
  Leftarrow:"⟸",leftrightarrow:"↔",Leftrightarrow:"⇔", mapsto:"↦",
  sum:"Σ", prod:"∏", int:"∫", oint:"∮", partial:"∂", nabla:"∇",
  cup:"∪", cap:"∩", subset:"⊂", supset:"⊃", subseteq:"⊆", supseteq:"⊇",
  in:"∈", notin:"∉", forall:"∀", exists:"∃", neg:"¬", lnot:"¬",
  emptyset:"∅", varnothing:"∅", angle:"∠", perp:"⊥", parallel:"∥",
  triangle:"△", degree:"°", prime:"′", hbar:"ℏ", ell:"ℓ", Re:"ℜ", Im:"ℑ",
  aleph:"ℵ", wp:"℘", ldots:"…", cdots:"⋯", dots:"…",
  langle:"⟨", rangle:"⟩", lceil:"⌈", rceil:"⌉", lfloor:"⌊", rfloor:"⌋",
  quad:" ", qquad:"  ", ",":" ", ";":" ", "!":"",
  left:"", right:"", "{":"{", "}":"}", "|":"|",
  lim:"lim", log:"log", ln:"ln", exp:"exp", sin:"sin", cos:"cos", tan:"tan",
  max:"max", min:"min", arg:"arg", det:"det", dim:"dim", mod:"mod",
  text:"", mathrm:"", mathbf:"", mathit:"", operatorname:"",
};
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// minimal TeX -> inline HTML (sup/sub/frac/sqrt), for the MSO fallback
function texToHtml(tex) {
  let i = 0;
  const out = [];
  const isGroup = () => tex[i] === "{";
  function readGroup() {
    if (tex[i] === "{") { i++; const s = i; let d = 1;
      while (i < tex.length && d > 0) { if (tex[i] === "{") d++; else if (tex[i] === "}") d--; i++; }
      return tex.slice(s, i - 1);
    }
    if (/^\\[a-zA-Z]+/.test(tex.slice(i))) { const m = tex.slice(i).match(/^\\[a-zA-Z]+/); i += m[0].length; return m[0]; }
    const c = tex[i++] ?? ""; return c;
  }
  while (i < tex.length) {
    const c = tex[i];
    if (c === "\\") {
      const m = tex.slice(i).match(/^\\([a-zA-Z]+|.)?/);
      const name = m[1] ?? ""; i += m[0].length;
      if (name === "frac") { const a = readGroup(), b = readGroup(); out.push(esc(texToHtml(a)) + "∕" + esc(texToHtml(b))); }
      else if (name === "sqrt") { let n = null; if (tex[i] === "[") { const e = tex.indexOf("]", i); n = tex.slice(i + 1, e); i = e + 1; }
        const a = readGroup(); out.push(n ? esc(texToHtml(a)) + "^(1∕" + esc(texToHtml(n)) + ")" : "√(" + esc(texToHtml(a)) + ")"); }
      else if (name === "vec" || name === "hat" || name === "bar" || name === "tilde" || name === "overline" || name === "widehat" || name === "widetilde") {
        const a = readGroup(); const suf = { vec:"⃗", hat:"̂", bar:"̄", overline:"̄", widehat:"̂", widetilde:"̃", tilde:"̃" }[name];
        out.push(esc(texToHtml(a)) + suf);
      }
      else if (name in SYM) out.push(SYM[name] ?? name);
      else if (/^[a-z]+$/.test(name)) out.push(name); // unknown command -> bare name
      else out.push(name);
    } else if (c === "^" || c === "_") {
      i++; const a = readGroup();
      out.push(`<${c === "^" ? "sup" : "sub"}>` + esc(texToHtml(a)) + `</${c === "^" ? "sup" : "sub"}>`);
    } else if (c === "{") {
      const g = readGroup(); out.push(esc(texToHtml(g)));
    } else {
      i++; out.push(esc(c));
    }
  }
  return out.join("");
}

// ---------- emit math span ----------
let nDisplay = 0, nInline = 0, nError = 0;
function emitMath(tex, display) {
  const src = tex.replace(/\s+/g, " ").trim();
  let mml, fallback;
  try {
    mml = texToMathML(src, display);
    fallback = texToHtml(src);
  } catch (e) {
    nError++;
    return `<code class="math-error" title="LaTeX error: ${esc(String(e.message || e).slice(0, 120))}">${esc(src)}</code>`;
  }
  if (display) nDisplay++; else nInline++;
  // MSO (Outlook Word engine): no MathML -> show HTML approximation.
  // All other clients: native MathML.
  return (
    `<!--[if mso]><span class="math-fallback">${fallback}</span><![endif]-->` +
    `<!--[if !mso]><!-->` +
    (display
      ? `<div class="math-display" style="text-align:center;margin:12px 0;">${mml}</div>`
      : mml) +
    `<!--<![endif]-->`
  );
}

// display math $$...$$ (multiline, non-greedy) — first
html = html.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => emitMath(tex, true));
// inline math $...$ (single line, supports backslash escapes)
html = html.replace(/\$((?:[^$\\\n]|\\.)+?)\$/g, (_m, tex) => emitMath(tex, false));

html = html.replace(/\u0000B(\d+)\u0000/g, (_m, i) => blocks[+i]);
fs.writeFileSync(file, html);
console.error(`render_math: ${nDisplay} display + ${nInline} inline math -> MathML in ${path.basename(file)}${nError ? ` (${nError} errors)` : ""}`);
