import { svg, h, vazio, moeda, abreviar, mesCurto, mesLongo } from "./util.js";

function escalaBonita(maximo) {
  if (maximo <= 0) return { topo: 1, passo: 0.25 };
  const bruto = maximo / 4;
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((f) => f * pot).find((p) => p >= bruto);
  return { topo: Math.ceil(maximo / passo) * passo, passo };
}

/** Barras de receitas e despesas por mês, com a linha do saldo. Redesenha ao mudar de largura. */
export class GraficoFluxo {
  constructor(caixa) {
    this.caixa = caixa;
    this.dados = null;
    this.largura = 0;
    new ResizeObserver(() => {
      const l = Math.round(this.caixa.clientWidth);
      if (l && l !== this.largura && this.dados) this.desenhar();
    }).observe(caixa);
  }

  atualizar(dados) { this.dados = dados; this.desenhar(); }

  desenhar() {
    const { meses, receitas, despesas, saldo } = this.dados;
    this.largura = Math.round(this.caixa.clientWidth) || 720;
    const L = this.largura, A = L < 520 ? 240 : 300;
    const m = { e: L < 520 ? 44 : 56, d: 8, t: 12, b: 28 };
    const w = L - m.e - m.d, alt = A - m.t - m.b;
    const maxV = Math.max(...receitas, ...despesas, 0), minS = Math.min(...saldo, 0);
    const { topo, passo } = escalaBonita(maxV);
    const base = minS < 0 ? Math.ceil(Math.abs(minS) / passo) * -passo : 0;
    const y = (v) => m.t + alt - ((v - base) / (topo - base)) * alt;
    const n = meses.length, faixa = w / n, larg = Math.max(4, Math.min(26, faixa * 0.32));

    const s = svg("svg", { viewBox: `0 0 ${L} ${A}`, width: L, height: A, role: "img",
      "aria-label": `Receitas, despesas e saldo por mês, de ${mesLongo(meses[0])} a ${mesLongo(meses[n - 1])}.` });
    for (let v = base; v <= topo + 1e-9; v += passo) {
      s.append(svg("line", { class: "eixo-linha", x1: m.e, x2: L - m.d, y1: y(v), y2: y(v), opacity: v === 0 ? 1 : 0.55 }));
      s.append(svg("text", { x: m.e - 8, y: y(v) + 4, "text-anchor": "end" }, abreviar(v)));
    }
    const pontos = [];
    meses.forEach((mes, i) => {
      const cx = m.e + faixa * i + faixa / 2;
      s.append(svg("rect", { class: "barra-rec", x: cx - larg - 1, width: larg, y: y(receitas[i]), height: Math.max(0, y(0) - y(receitas[i])), rx: 4 }));
      s.append(svg("rect", { class: "barra-des", x: cx + 1, width: larg, y: y(despesas[i]), height: Math.max(0, y(0) - y(despesas[i])), rx: 4 }));
      if (faixa > 34 || i % 2 === 0) s.append(svg("text", { x: cx, y: A - 8, "text-anchor": "middle" }, mesCurto(mes) + (mes.endsWith("-01") || i === 0 ? ` ${mes.slice(2, 4)}` : "")));
      pontos.push([cx, y(saldo[i])]);
    });
    s.append(svg("polyline", { class: "linha-saldo", points: pontos.map((p) => p.join(",")).join(" ") }));
    pontos.forEach(([px, py]) => s.append(svg("circle", { class: "ponto-saldo", cx: px, cy: py, r: 3.5 })));
    meses.forEach((mes, i) => {
      const zona = svg("rect", { class: "zona-mes", x: m.e + faixa * i, y: m.t, width: faixa, height: alt, tabindex: 0,
        "aria-label": `${mesLongo(mes)}: receitas ${moeda(receitas[i])}, despesas ${moeda(despesas[i])}, saldo ${moeda(saldo[i])}` });
      const mostrar = () => this.dica(mes, i, m.e + faixa * i + faixa / 2);
      zona.addEventListener("mouseenter", mostrar);
      zona.addEventListener("focus", mostrar);
      zona.addEventListener("mouseleave", () => this.esconder());
      zona.addEventListener("blur", () => this.esconder());
      s.append(zona);
    });
    vazio(this.caixa).append(s);
    this.dicaEl = null;
  }

  dica(mes, i, cx) {
    this.esconder();
    const { receitas, despesas, saldo } = this.dados;
    const linha = (rotulo, v) => h("span", {}, h("span", {}, rotulo), h("span", { class: "num" }, moeda(v)));
    const el = h("div", { class: "dica", role: "status" }, h("b", {}, mesLongo(mes)),
      linha("Receitas", receitas[i]), linha("Despesas", despesas[i]), linha("Saldo", saldo[i]));
    this.caixa.append(el);
    const w = el.offsetWidth;
    el.style.top = "8px";
    el.style.left = `${Math.max(4, Math.min(this.largura - w - 4, cx - w / 2))}px`;
    this.dicaEl = el;
  }

  esconder() { this.dicaEl?.remove(); this.dicaEl = null; }
}
