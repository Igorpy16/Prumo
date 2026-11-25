// Utilidades pequenas: DOM, formatação em português e cliente da API.
const NS = "http://www.w3.org/2000/svg";

export function h(tag, attrs = {}, ...filhos) {
  const el = document.createElement(tag);
  aplicar(el, attrs);
  anexar(el, filhos);
  return el;
}
export function svg(tag, attrs = {}, ...filhos) {
  const el = document.createElementNS(NS, tag);
  aplicar(el, attrs);
  anexar(el, filhos);
  return el;
}
function aplicar(el, attrs) {
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k === "value" || k === "checked" || k === "disabled") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
}
function anexar(el, filhos) {
  for (const f of filhos.flat(Infinity)) {
    if (f == null || f === false) continue;
    el.append(f.nodeType ? f : document.createTextNode(String(f)));
  }
}
export const vazio = (el) => { el.replaceChildren(); return el; };

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlInteiro = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const moeda = (v) => brl.format(v ?? 0);
export const moedaInteira = (v) => brlInteiro.format(v ?? 0);
export const numero2 = (v) => num.format(v);
export const percentual = (v, casas = 1) => `${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`;
export const abreviar = (v) => {
  const a = Math.abs(v);
  if (a >= 1e6) return `${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (a >= 1e3) return `${(v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return v.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
};

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
export const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const doIso = (s) => { const [a, m, d] = s.split("-").map(Number); return new Date(a, m - 1, d); };
export const dataCurta = (s) => { const d = doIso(s); return `${d.getDate()} ${MESES[d.getMonth()]}`; };
export const dataComAno = (s) => { const d = doIso(s); return `${d.getDate()} ${MESES[d.getMonth()]} ${d.getFullYear()}`; };
export const mesCurto = (ym) => MESES[Number(ym.slice(5)) - 1];
export const mesLongo = (ym) => `${MESES_LONGOS[Number(ym.slice(5)) - 1]} de ${ym.slice(0, 4)}`;
export const mesDe = (d) => iso(d).slice(0, 7);
export const somarMeses = (ym, n) => { const [a, m] = ym.split("-").map(Number); const i = a * 12 + m - 1 + n; return `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`; };

export class ErroApi extends Error {
  constructor(mensagem, status, campos) { super(mensagem); this.status = status; this.campos = campos || {}; }
}

export class ClienteApi {
  async pedir(metodo, caminho, { corpo, consulta, formulario } = {}) {
    const url = new URL(caminho, location.origin);
    for (const [k, v] of Object.entries(consulta || {})) {
      for (const item of [].concat(v)) if (item !== undefined && item !== null && item !== "") url.searchParams.append(k, item);
    }
    const opcoes = { method: metodo, headers: {}, credentials: "same-origin" };
    if (corpo !== undefined) { opcoes.headers["Content-Type"] = "application/json"; opcoes.body = JSON.stringify(corpo); }
    if (formulario) opcoes.body = formulario;
    let r;
    try { r = await fetch(url, opcoes); } catch { throw new ErroApi("Sem conexão com o servidor.", 0); }
    if (r.status === 401 && !caminho.endsWith("/login")) { location.href = "/login"; throw new ErroApi("Sessão expirada.", 401); }
    if (r.status === 204) return null;
    const tipo = r.headers.get("content-type") || "";
    const dados = tipo.includes("json") ? await r.json() : await r.blob();
    if (!r.ok) throw new ErroApi(dados.detail || "Algo deu errado.", r.status, dados.campos);
    return dados;
  }
  get(c, consulta) { return this.pedir("GET", c, { consulta }); }
  post(c, corpo) { return this.pedir("POST", c, { corpo }); }
  put(c, corpo) { return this.pedir("PUT", c, { corpo }); }
  patch(c, corpo) { return this.pedir("PATCH", c, { corpo }); }
  apagar(c, consulta) { return this.pedir("DELETE", c, { consulta }); }
}

export function debounce(fn, ms = 300) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
