document.querySelectorAll(".copy").forEach((btn) => btn.addEventListener("click", () => {
  const code = btn.closest(".code").querySelector("code");
  const done = (label) => { btn.textContent = label; setTimeout(() => (btn.textContent = "Copy"), 1600); };
  const select = () => { const r = document.createRange(); r.selectNodeContents(code); const s = getSelection(); s.removeAllRanges(); s.addRange(r); done("Selected"); };
  try {
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(code.textContent).then(() => done("Copied"), select); else select();
  } catch (e) { select(); }
}));

// Step completion, remembered in this browser only.
const KEY = "f1-lakehouse-tutorial-done";
let done = new Set();
try { done = new Set(JSON.parse(localStorage.getItem(KEY) || "[]")); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify([...done])); } catch (e) {} };
const stepHeads = [...document.querySelectorAll("h3.step")];
const total = stepHeads.length;
function render() {
  document.querySelectorAll(".check button").forEach((b) => {
    const on = done.has(b.dataset.step);
    b.setAttribute("aria-pressed", on);
    b.lastChild.textContent = on ? "Step " + b.dataset.step + " done" : "Mark step " + b.dataset.step + " as done";
  });
  document.querySelectorAll("nav.toc ol.steps a").forEach((a) => a.classList.toggle("done", done.has(a.dataset.step)));
  const n = stepHeads.filter((h) => done.has(h.dataset.step)).length;
  document.getElementById("done-count").textContent = n;
  document.getElementById("done-bar").style.width = (total ? (100 * n) / total : 0) + "%";
}
stepHeads.forEach((h, i) => {
  // The step's content runs until the next step or section heading.
  let last = h;
  while (last.nextElementSibling && !last.nextElementSibling.matches("h2, h3.step")) last = last.nextElementSibling;
  const box = document.createElement("div");
  box.className = "check";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.dataset.step = h.dataset.step;
  btn.appendChild(document.createTextNode(""));
  btn.addEventListener("click", () => {
    done.has(btn.dataset.step) ? done.delete(btn.dataset.step) : done.add(btn.dataset.step);
    save(); render();
  });
  const next = stepHeads[i + 1];
  const hint = document.createElement("span");
  hint.textContent = next ? "Next: " + next.querySelector(".step-name").textContent : "Last step";
  box.append(btn, hint);
  last.after(box);
});
render();

// Highlight the section in view in the contents rail.
const links = new Map([...document.querySelectorAll("nav.toc a")].map((a) => [a.getAttribute("href").slice(1), a]));
const obs = new IntersectionObserver((entries) => entries.forEach((e) => {
  if (e.isIntersecting) { links.forEach((a) => a.classList.remove("on")); links.get(e.target.id)?.classList.add("on"); }
}), { rootMargin: "0px 0px -70% 0px" });
document.querySelectorAll("article h2[id], article h3[id]").forEach((h) => { if (links.has(h.id)) obs.observe(h); });
