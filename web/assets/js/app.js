import { h, svg, vazio, moeda, moedaInteira, percentual, dataCurta, dataComAno, mesLongo, mesDe, somarMeses, iso, doIso, ClienteApi, ErroApi, debounce } from "./util.js";
import { GraficoFluxo } from "./graficos.js";

const api = new ClienteApi();
const $ = (id) => document.getElementById(id);

const ICONES = {
  filtro: "M3 5h18M6 12h12M10 19h4", mais: "M12 5v14M5 12h14", busca: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5",
  esq: "M15 5l-7 7 7 7", dir: "M9 5l7 7-7 7", fechar: "M6 6l12 12M18 6L6 18", editar: "M4 20h4L19 9l-4-4L4 16v4z",
  lixo: "M5 7h14M10 11v6M14 11v6M7 7l1 13h8l1-13M9 7V4h6v3", tema: "M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z",
};
const icone = (nome) => svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" }, svg("path", { d: ICONES[nome] }));
document.querySelectorAll("[data-icone]").forEach((el) => el.replaceWith(icone(el.dataset.icone)));

// ------------------------------------------------------------------ estado
const estado = {
  sessao: null, meta: { categorias: [], contas: [] },
  periodo: "6m", inicio: null, fim: null,
  tipo: "", situacao: "", categorias: [], contas: [], busca: "", pagina: 1,
  mesMeta: mesDe(new Date()), resumo: null, metasAbertas: false,
};
const somenteLeitura = () => !!estado.sessao?.demo;

function intervalo() {
  const hoje = new Date();
  const fimMes = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0);
  const comecoMeses = (n) => new Date(hoje.getFullYear(), hoje.getMonth() - (n - 1), 1);
  switch (estado.periodo) {
    case "mes": return [comecoMeses(1), fimMes];
    case "3m": return [comecoMeses(3), fimMes];
    case "6m": return [comecoMeses(6), fimMes];
    case "12m": return [comecoMeses(12), fimMes];
    case "custom": return [estado.inicio ? doIso(estado.inicio) : null, estado.fim ? doIso(estado.fim) : null];
    default: return [null, null];
  }
}
function consulta() {
  const [i, f] = intervalo();
  return { inicio: i && iso(i), fim: f && iso(f), tipo: estado.tipo, situacao: estado.situacao, busca: estado.busca,
    categoria: estado.categorias, conta: estado.contas };
}
// o resumo ignora a busca por texto: os totais mostram o período, a tabela mostra a busca
const consultaResumo = () => ({ ...consulta(), busca: "" });

// ------------------------------------------------------------------ avisos
function avisar(texto, erro = false) {
  const el = h("div", { class: `aviso-toast${erro ? " erro" : ""}`, role: erro ? "alert" : "status" }, texto);
  $("avisos").append(el);
  setTimeout(() => el.remove(), erro ? 6000 : 3500);
}
const tratar = (e) => avisar(e instanceof ErroApi ? e.message : "Algo deu errado.", true);

// ------------------------------------------------------------------ gaveta (dialog)
class Gaveta {
  constructor(titulo) {
    this.dialog = h("dialog", { class: "gaveta", "aria-labelledby": "g-titulo" });
    this.corpo = h("div", { class: "gaveta-corpo" });
    this.pe = h("div", { class: "gaveta-pe" });
    this.dialog.append(
      h("div", { class: "gaveta-cab" }, h("h2", { id: "g-titulo" }, titulo),
        h("button", { class: "btn icone fantasma", type: "button", "aria-label": "Fechar", onclick: () => this.fechar() }, icone("fechar"))),
      this.corpo, this.pe);
    this.dialog.addEventListener("close", () => this.dialog.remove());
    this.dialog.addEventListener("click", (e) => { if (e.target === this.dialog) this.fechar(); });
    document.body.append(this.dialog);
    this.dialog.showModal();
  }
  fechar() { this.dialog.close(); }
}

// ------------------------------------------------------------------ máscara de valor
function campoValor(inicial = 0) {
  const input = h("input", { id: "f-valor", inputmode: "numeric", autocomplete: "off", "aria-describedby": "e-valor" });
  let centavos = Math.round(inicial * 100);
  const mostrar = () => { input.value = centavos ? (centavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : ""; };
  input.addEventListener("input", () => { centavos = Math.min(Number(input.value.replace(/\D/g, "") || 0), 999999999999); mostrar(); });
  mostrar();
  return { input, valor: () => (centavos / 100).toFixed(2) };
}
const campo = (rotulo, id, controle, extra) => h("div", { class: "campo" }, h("label", { for: id }, rotulo), controle, h("p", { class: "erro", id: `e-${id.replace("f-", "")}`, role: "alert" }), extra);

// ------------------------------------------------------------------ formulário de lançamento
function abrirFormulario(existente = null) {
  if (somenteLeitura()) return;
  const g = new Gaveta(existente ? "Editar lançamento" : "Novo lançamento");
  let alternar; const tipoAtual = () => alternar.querySelector("input[name=tipo]:checked").value;
  alternar = h("fieldset", { class: "alternar" }, h("legend", { class: "so-leitor" }, "Tipo"),
    ...[["despesa", "Despesa"], ["receita", "Receita"]].map(([v, r]) =>
      h("label", {}, h("input", { type: "radio", name: "tipo", value: v, checked: (existente?.tipo || "despesa") === v }), h("span", {}, r))));
  const data = h("input", { id: "f-data", type: "date", required: true, value: existente?.data || iso(new Date()) });
  const desc = h("input", { id: "f-descricao", maxlength: 120, required: true, value: existente?.descricao || "", autocomplete: "off" });
  const valor = campoValor(existente?.valor || 0);
  const cat = h("input", { id: "f-categoria", list: "lista-cats", maxlength: 60, required: true, value: existente?.categoria || "", autocomplete: "off" });
  const conta = h("input", { id: "f-conta", list: "lista-contas", maxlength: 60, required: true, value: existente?.conta || "Conta corrente", autocomplete: "off" });
  const pago = h("input", { id: "f-pago", type: "checkbox", checked: existente ? existente.pago : true });
  const listaCats = h("datalist", { id: "lista-cats" });
  const preencherCats = () => vazio(listaCats).append(...estado.meta.categorias.filter((c) => c.tipo === tipoAtual()).map((c) => h("option", { value: c.nome })));
  preencherCats();
  alternar.addEventListener("change", preencherCats);
  const listaContas = h("datalist", { id: "lista-contas" }, ...estado.meta.contas.map((c) => h("option", { value: c.nome })));
  g.corpo.append(alternar,
    h("div", { class: "duplo" }, campo("Valor (R$)", "f-valor", valor.input), campo("Data", "f-data", data)),
    campo("Descrição", "f-descricao", desc), campo("Categoria", "f-categoria", cat), campo("Conta", "f-conta", conta),
    h("label", { class: "marcas" }, h("span", { class: "marcas" }, pago, h("span", {}, "Já foi pago ou recebido"))), listaCats, listaContas);
  const salvar = h("button", { class: "btn primario", type: "button" }, existente ? "Salvar alterações" : "Adicionar");
  g.pe.append(h("button", { class: "btn", type: "button", onclick: () => g.fechar() }, "Cancelar"), salvar);
  salvar.addEventListener("click", async () => {
    g.corpo.querySelectorAll(".erro").forEach((e) => (e.textContent = ""));
    g.corpo.querySelectorAll("[aria-invalid]").forEach((e) => e.removeAttribute("aria-invalid"));
    const corpo = { data: data.value, descricao: desc.value, valor: valor.valor(), tipo: tipoAtual(), categoria: cat.value, conta: conta.value, pago: pago.checked };
    salvar.disabled = true;
    try {
      if (existente) await api.put(`/api/lancamentos/${existente.id}`, corpo); else await api.post("/api/lancamentos", corpo);
      g.fechar();
      avisar(existente ? "Lançamento atualizado." : "Lançamento adicionado.");
      await recarregarTudo(true);
    } catch (e) {
      if (e instanceof ErroApi && e.status === 422) {
        for (const [nome, msg] of Object.entries(e.campos)) {
          const el = g.corpo.querySelector(`#e-${nome}`); if (el) el.textContent = msg;
          g.corpo.querySelector(`#f-${nome}`)?.setAttribute("aria-invalid", "true");
        }
        if (!Object.keys(e.campos).length) tratar(e);
      } else tratar(e);
      salvar.disabled = false;
    }
  });
  desc.focus();
}

// ------------------------------------------------------------------ filtros
function abrirFiltros() {
  const g = new Gaveta("Filtros");
  const [i, f] = intervalo();
  const ini = h("input", { id: "f-ini", type: "date", value: i ? iso(i) : "" });
  const fim = h("input", { id: "f-fim", type: "date", value: f ? iso(f) : "" });
  const tipo = h("select", { id: "f-tipo" }, ...[["", "Receitas e despesas"], ["receita", "Só receitas"], ["despesa", "Só despesas"]].map(([v, r]) => h("option", { value: v, selected: estado.tipo === v }, r)));
  const sit = h("select", { id: "f-sit" }, ...[["", "Tudo"], ["pago", "Pago ou recebido"], ["pendente", "Pendente"]].map(([v, r]) => h("option", { value: v, selected: estado.situacao === v }, r)));
  const chips = (nome, itens, marcados) => h("fieldset", { class: "marcas" }, ...itens.map((it) =>
    h("label", {}, h("input", { type: "checkbox", name: nome, value: it.id, checked: marcados.includes(it.id) }), it.nome + (it.tipo === "receita" ? " (receita)" : ""))));
  const cats = chips("cat", estado.meta.categorias, estado.categorias), contas = chips("conta", estado.meta.contas, estado.contas);
  g.corpo.append(h("div", { class: "duplo" }, campo("De", "f-ini", ini), campo("Até", "f-fim", fim)),
    campo("Tipo", "f-tipo", tipo), campo("Situação", "f-sit", sit),
    h("div", { class: "campo" }, h("label", {}, "Categorias"), cats), h("div", { class: "campo" }, h("label", {}, "Contas"), contas));
  const aplicar = h("button", { class: "btn primario", type: "button" }, "Aplicar");
  g.pe.append(h("button", { class: "btn", type: "button", onclick: () => {
    Object.assign(estado, { tipo: "", situacao: "", categorias: [], contas: [], pagina: 1 }); g.fechar(); recarregarTudo();
  } }, "Limpar filtros"), aplicar);
  aplicar.addEventListener("click", () => {
    if (ini.value && fim.value && ini.value > fim.value) { avisar("A data inicial não pode ser depois da final.", true); return; }
    const mudouDatas = ini.value !== (i ? iso(i) : "") || fim.value !== (f ? iso(f) : "");
    if (mudouDatas || estado.periodo === "custom") { estado.periodo = "custom"; estado.inicio = ini.value || null; estado.fim = fim.value || null; $("periodo").value = "custom"; }
    estado.tipo = tipo.value; estado.situacao = sit.value; estado.pagina = 1;
    estado.categorias = [...cats.querySelectorAll("input:checked")].map((e) => Number(e.value));
    estado.contas = [...contas.querySelectorAll("input:checked")].map((e) => Number(e.value));
    g.fechar(); recarregarTudo();
  });
}

// ------------------------------------------------------------------ metas (edição)
function abrirMetas() {
  if (somenteLeitura()) return;
  const g = new Gaveta("Metas por categoria");
  const entradas = new Map();
  api.get("/api/orcamento/metas").then((metas) => {
    g.corpo.append(h("p", { class: "aviso" }, "Defina quanto pretende gastar por mês em cada categoria. Deixe em branco para não ter meta."));
    for (const m of metas) {
      const input = h("input", { id: `m-${m.categoria_id}`, inputmode: "decimal", placeholder: "Sem meta", value: m.limite ? String(m.limite).replace(".", ",") : "" });
      entradas.set(m.categoria_id, input);
      g.corpo.append(h("div", { class: "meta-linha" }, h("label", { for: input.id }, m.categoria), input));
    }
  }).catch(tratar);
  const salvar = h("button", { class: "btn primario", type: "button" }, "Salvar metas");
  g.pe.append(h("button", { class: "btn", type: "button", onclick: () => g.fechar() }, "Cancelar"), salvar);
  salvar.addEventListener("click", async () => {
    const converter = (t) => { t = t.trim(); if (!t) return "0"; return t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t; };
    const metas = [...entradas].map(([categoria_id, el]) => ({ categoria_id, limite: converter(el.value) }));
    try { await api.put("/api/orcamento/metas", { metas }); g.fechar(); avisar("Metas salvas."); carregarMetas(); }
    catch (e) { tratar(e); }
  });
}

// ------------------------------------------------------------------ cores por categoria (cor segue a categoria, não a posição)
const corDaCategoria = (id) => {
  const despesas = estado.meta.categorias.filter((c) => c.tipo === "despesa").map((c) => c.id);
  const i = despesas.indexOf(id);
  return `var(--c${((i < 0 ? id : i) % 8) + 1})`;
};
const grafico = new GraficoFluxo($("grafico-fluxo"));

// ------------------------------------------------------------------ renderização
function rotuloPeriodo() {
  const [i, f] = intervalo();
  const dados = estado.resumo?.mensal;
  const ini = i ? iso(i) : dados?.meses[0] && `${dados.meses[0]}-01`;
  const fi = f ? iso(f) : null;
  if (ini && fi) return `${dataCurta(ini)} a ${dataComAno(fi)}`;
  return ini ? `desde ${dataComAno(ini)}` : "todo o período";
}

function renderAbertura(r) {
  const alvo = vazio($("abertura"));
  if (r.vazio) {
    alvo.append(h("h2", { class: "frase" }, "Nada por aqui ainda."), h("p", { class: "subfrase" }, "Ajuste o período ou os filtros, ou registre o primeiro lançamento."));
    return;
  }
  const k = r.kpis;
  const sobra = k.saldo >= 0;
  alvo.append(
    h("p", { class: "frase" }, `Em ${rotuloPeriodo()}, entraram `, h("strong", { class: "rec num" }, moedaInteira(k.receitas)), " e saíram ", h("strong", { class: "des num" }, moedaInteira(k.despesas)), "."),
    h("p", { class: "subfrase" }, sobra
      ? `Sobraram ${moeda(k.saldo)}${k.taxa_poupanca != null ? `, ${percentual(k.taxa_poupanca)} do que entrou` : ""}.`
      : `Faltaram ${moeda(-k.saldo)}: saiu mais do que entrou neste período.`),
  );
  const gasto = k.receitas > 0 ? Math.min(100, (k.despesas / k.receitas) * 100) : 100;
  const barra = h("div", { class: `fluxo-barra${sobra ? "" : " cheia"}`, role: "img", "aria-label": `${percentual(gasto, 0)} da receita foi gasta.` },
    h("div", { class: "fluxo-gasto" }), h("div", { class: `fluxo-sobra${sobra ? "" : " negativa"}` }), h("span", { class: "fluxo-prumo" }));
  barra.querySelector(".fluxo-gasto").style.width = `${gasto}%`;
  barra.querySelector(".fluxo-sobra").style.width = sobra ? `calc(${100 - gasto}% - 2px)` : "0";
  barra.querySelector(".fluxo-prumo").style.left = `${gasto}%`;
  alvo.append(h("div", { class: "fluxo" }, barra, h("div", { class: "fluxo-legenda" },
    h("span", { class: "l1" }, "Gastos ", h("b", { class: "num" }, percentual(gasto, 0))),
    h("span", { class: "l2" }, sobra ? ["Sobra ", h("b", { class: "num" }, percentual(100 - gasto, 0))] : "Sem sobra"),
    h("span", { class: "l3" }, k.qtd_a_pagar ? `${moeda(k.a_pagar)} ainda a pagar (${k.qtd_a_pagar})` : "Nada pendente"))));
}

function renderLivro(r) {
  const k = r.kpis, v = r.variacao;
  const variacao = (x, bomSeSobe) => {
    if (x == null) return null;
    const bom = bomSeSobe ? x >= 0 : x <= 0;
    return h("span", { class: `var ${bom ? "pos" : "neg"}` }, `${x >= 0 ? "+" : ""}${percentual(x)} vs. período anterior`);
  };
  const item = (rotulo, valor, extra) => h("div", {}, h("dt", {}, rotulo), h("dd", { class: "num" }, valor), extra);
  vazio($("livro")).append(
    item("Receitas", moeda(k.receitas), variacao(v.receitas, true)), item("Despesas", moeda(k.despesas), variacao(v.despesas, false)),
    item("Saldo", moeda(k.saldo)), item("Taxa de poupança", k.taxa_poupanca == null ? "—" : percentual(k.taxa_poupanca)));
}

function renderFichas() {
  const alvo = vazio($("filtros-ativos"));
  const ficha = (texto, remover) => alvo.append(h("span", { class: "ficha" }, texto, h("button", { type: "button", "aria-label": `Remover filtro ${texto}`, onclick: () => { remover(); estado.pagina = 1; recarregarTudo(); } }, "×")));
  if (estado.tipo) ficha(estado.tipo === "receita" ? "Só receitas" : "Só despesas", () => (estado.tipo = ""));
  if (estado.situacao) ficha(estado.situacao === "pago" ? "Pago" : "Pendente", () => (estado.situacao = ""));
  for (const id of estado.categorias) ficha(estado.meta.categorias.find((c) => c.id === id)?.nome || "Categoria", () => (estado.categorias = estado.categorias.filter((x) => x !== id)));
  for (const id of estado.contas) ficha(estado.meta.contas.find((c) => c.id === id)?.nome || "Conta", () => (estado.contas = estado.contas.filter((x) => x !== id)));
}

function renderCategorias(r) {
  const ul = vazio($("rank-categorias"));
  if (!r.categorias?.length) { ul.append(h("li", { class: "vazio" }, "Sem despesas neste período.")); return; }
  for (const c of r.categorias) {
    const ativa = estado.categorias.length === 1 && estado.categorias[0] === c.id;
    const fio = h("span", {}); fio.style.width = `${Math.max(2, c.percentual)}%`; fio.style.background = corDaCategoria(c.id);
    const marca = h("i", {}); marca.style.background = corDaCategoria(c.id);
    ul.append(h("li", {}, h("button", { type: "button", "aria-pressed": ativa, onclick: () => {
      estado.categorias = ativa ? [] : [c.id]; estado.pagina = 1; recarregarTudo(); if (!ativa) $("lancamentos").scrollIntoView();
    } }, h("span", { class: "nome" }, marca, c.nome), h("span", { class: "valor num" }, moeda(c.valor)),
    h("span", { class: "fio" }, fio), h("small", {}, `${percentual(c.percentual)} das despesas · ${c.quantidade} lançamento${c.quantidade === 1 ? "" : "s"}`))));
  }
}

function renderLaterais(r) {
  const maiores = vazio($("maiores"));
  for (const l of r.maiores_despesas || []) maiores.append(h("li", {}, h("div", {}, l.descricao, h("small", {}, `${dataCurta(l.data)} · ${l.categoria}`)), h("span", { class: "valor num" }, moeda(l.valor))));
  const caixa = vazio($("por-conta"));
  const contas = r.contas || [];
  const barra = h("div", { class: "conta-barra", "aria-hidden": "true" });
  contas.forEach((c, i) => { const s = h("span", {}); s.style.width = `${c.percentual}%`; s.style.background = `var(--c${(i % 8) + 1})`; barra.append(s); });
  const lista = h("ul", { class: "lista-simples" }, ...contas.map((c, i) => {
    const marca = h("i", { class: "marca-conta" }); marca.style.background = `var(--c${(i % 8) + 1})`;
    return h("li", {}, h("div", {}, c.nome, h("small", {}, `${percentual(c.percentual)} das despesas`)), h("span", { class: "valor num" }, moeda(c.valor)));
  }));
  caixa.append(barra, lista);
}

function renderResumo(r) {
  estado.resumo = r;
  renderAbertura(r); renderFichas();
  const secoes = ["fluxo", "categorias"].map($);
  if (r.vazio) { vazio($("livro")); secoes.forEach((s) => (s.hidden = true)); return; }
  secoes.forEach((s) => (s.hidden = false));
  renderLivro(r); grafico.atualizar(r.mensal); renderCategorias(r); renderLaterais(r);
}

// ---- indicadores de mercado
async function carregarIndicadores() {
  try {
    const d = await api.get("/api/indicadores");
    if (!d.ativo || !d.itens.length) { $("mercado").hidden = true; $("mercado-nota").textContent = ""; $("mercado-fonte").textContent = ""; return; }
    const dl = vazio($("mercado")); dl.hidden = false;
    for (const i of d.itens) {
      const texto = i.unidade === "R$" ? moeda(i.valor) : `${i.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}%`;
      dl.append(h("div", {}, h("dt", {}, i.nome), h("dd", { class: "num" }, texto, h("small", {}, i.unidade === "R$" ? "cotação de venda" : i.unidade))));
    }
    const cdi = d.itens.find((i) => i.codigo === "cdi");
    const saldo = estado.resumo?.kpis?.saldo;
    $("mercado-nota").textContent = cdi && saldo > 0
      ? `Se o saldo de ${moeda(saldo)} rendesse 100% do CDI por um ano, seriam cerca de ${moeda((saldo * cdi.valor) / 100)} brutos. É só uma estimativa, sem impostos nem taxas.` : "";
    $("mercado-fonte").textContent = `Fonte: Banco Central do Brasil (SGS)${d.desatualizado ? ". Dados desatualizados: o BCB não respondeu agora" : ""}.`;
  } catch { $("mercado").hidden = true; }
}

// ---- metas
async function carregarMetas() {
  $("mes-meta").textContent = mesLongo(estado.mesMeta);
  try {
    const d = await api.get("/api/orcamento", { mes: estado.mesMeta });
    const com = d.itens.filter((i) => i.limite > 0), lista = vazio($("lista-metas"));
    $("resumo-metas").textContent = com.length
      ? `Você gastou ${moeda(d.gasto_com_meta)} de ${moeda(d.total_limite)} planejados nas categorias com meta${d.gasto_sem_meta ? `, e mais ${moeda(d.gasto_sem_meta)} em categorias sem meta` : ""}.`
      : "Nenhuma meta definida ainda. Metas ajudam a perceber cedo quando uma categoria foge do planejado.";
    for (const i of com) {
      const p = i.percentual ?? 0, passou = i.gasto > i.limite, classe = passou ? "estourou" : p >= 80 ? "atencao" : "";
      const trilho = h("span", {}); trilho.style.width = `${Math.min(100, p)}%`;
      const msg = passou ? `Passou ${moeda(i.gasto - i.limite)} da meta.` : `Restam ${moeda(i.limite - i.gasto)}.`;
      lista.append(h("div", { class: `meta ${classe}` }, h("div", { class: "meta-topo" }, h("span", {}, i.categoria), h("span", { class: "num" }, `${moeda(i.gasto)} de ${moeda(i.limite)}`)),
        h("div", { class: "meta-trilho", role: "progressbar", "aria-valuenow": Math.round(p), "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": `${i.categoria}: ${percentual(p, 0)} da meta` }, trilho),
        h("p", {}, `${percentual(p, 0)} da meta. ${msg}`)));
    }
  } catch (e) { tratar(e); }
}

// ---- lista de lançamentos
async function carregarLista() {
  const tabela = $("tabela");
  try {
    const d = await api.get("/api/lancamentos", { ...consulta(), pagina: estado.pagina, tamanho: 15 });
    estado.pagina = d.pagina;
    if (!d.itens.length) {
      vazio(tabela).append(h("div", { class: "vazio" }, h("h3", {}, "Nenhum lançamento encontrado"), h("p", {}, "Tente outro período, outra busca ou limpe os filtros."),
        somenteLeitura() ? null : h("button", { class: "btn primario", type: "button", onclick: () => abrirFormulario() }, "Novo lançamento")));
      vazio($("paginacao")); return;
    }
    const ro = somenteLeitura();
    const linhas = d.itens.map((l) => h("tr", {},
      h("td", { class: "desc" }, h("b", {}, l.descricao), h("small", {}, dataComAno(l.data))),
      h("td", { class: "cat-c" }, l.categoria), h("td", { class: "conta-c" }, l.conta),
      h("td", { class: "sit-c" }, h("button", { class: `selo${l.pago ? "" : " pendente"}`, type: "button", disabled: ro, title: ro ? "" : "Alternar situação",
        onclick: async () => { try { await api.patch(`/api/lancamentos/${l.id}/pago`, { pago: !l.pago }); await recarregarTudo(true); } catch (e) { tratar(e); } } },
        l.pago ? (l.tipo === "receita" ? "Recebido" : "Pago") : "Pendente")),
      h("td", { class: `dir valor-c num ${l.tipo === "receita" ? "v-rec" : "v-des"}` }, `${l.tipo === "receita" ? "+" : "−"} ${moeda(l.valor)}`),
      h("td", { class: "acoes-c" }, ro ? null : h("div", { class: "linha-acoes" },
        h("button", { class: "btn icone fantasma", type: "button", "aria-label": `Editar ${l.descricao}`, onclick: () => abrirFormulario(l) }, icone("editar")),
        h("button", { class: "btn icone fantasma perigo", type: "button", "aria-label": `Excluir ${l.descricao}`, onclick: () => excluir(l) }, icone("lixo"))))));
    vazio(tabela).append(h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Descrição"), h("th", { class: "cat-c" }, "Categoria"), h("th", { class: "conta-c" }, "Conta"), h("th", {}, "Situação"), h("th", { class: "dir" }, "Valor"), h("th", {}, h("span", { class: "so-leitor" }, "Ações")))), h("tbody", {}, linhas)));
    const pag = vazio($("paginacao"));
    pag.append(h("span", {}, `${d.total.toLocaleString("pt-BR")} lançamento${d.total === 1 ? "" : "s"}`),
      h("div", {}, h("button", { class: "btn", type: "button", disabled: d.pagina <= 1, onclick: () => { estado.pagina--; carregarLista(); } }, "Anterior"),
        h("span", {}, `Página ${d.pagina} de ${d.paginas}`), h("button", { class: "btn", type: "button", disabled: d.pagina >= d.paginas, onclick: () => { estado.pagina++; carregarLista(); } }, "Próxima")));
  } catch (e) { tratar(e); }
}

async function excluir(l) {
  const g = new Gaveta("Excluir lançamento");
  g.corpo.append(h("p", {}, `Excluir "${l.descricao}" de ${dataComAno(l.data)} (${moeda(l.valor)})? Isso não pode ser desfeito.`));
  const ok = h("button", { class: "btn primario perigo-fundo", type: "button" }, "Excluir");
  g.pe.append(h("button", { class: "btn", type: "button", onclick: () => g.fechar() }, "Cancelar"), ok);
  ok.addEventListener("click", async () => { try { await api.apagar(`/api/lancamentos/${l.id}`); g.fechar(); avisar("Lançamento excluído."); await recarregarTudo(true); } catch (e) { tratar(e); } });
}

// ------------------------------------------------------------------ carga geral
async function carregarMeta() { estado.meta = await api.get("/api/meta"); }
async function recarregarTudo(comMeta = false) {
  try {
    if (comMeta) await carregarMeta();
    const resumo = await api.get("/api/resumo", consultaResumo());
    renderResumo(resumo);
    await Promise.all([carregarLista(), carregarMetas(), carregarIndicadores()]);
  } catch (e) { tratar(e); }
}

// ------------------------------------------------------------------ importar / exportar
$("btn-exportar").addEventListener("click", async () => {
  try {
    const blob = await api.pedir("GET", "/api/exportar.csv", { consulta: consulta() });
    const a = h("a", { href: URL.createObjectURL(blob), download: "lancamentos.csv" }); document.body.append(a); a.click(); a.remove();
  } catch (e) { tratar(e); }
});
$("btn-importar").addEventListener("click", () => $("arquivo-csv").click());
$("arquivo-csv").addEventListener("change", async (e) => {
  const arquivo = e.target.files[0]; e.target.value = "";
  if (!arquivo) return;
  const f = new FormData(); f.append("arquivo", arquivo);
  try {
    const r = await api.pedir("POST", "/api/importar", { formulario: f });
    avisar(`${r.importados} importado${r.importados === 1 ? "" : "s"}${r.ignorados ? `, ${r.ignorados} ignorado${r.ignorados === 1 ? "" : "s"} (${r.erros[0]})` : ""}.`, r.importados === 0);
    await recarregarTudo(true);
  } catch (err) { tratar(err); }
});

// ------------------------------------------------------------------ eventos
$("periodo").addEventListener("change", (e) => {
  estado.periodo = e.target.value; estado.pagina = 1;
  if (estado.periodo === "custom") { abrirFiltros(); return; }
  recarregarTudo();
});
$("btn-filtros").addEventListener("click", abrirFiltros);
$("btn-novo").addEventListener("click", () => abrirFormulario());
$("btn-metas").addEventListener("click", abrirMetas);
$("mes-ant").addEventListener("click", () => { estado.mesMeta = somarMeses(estado.mesMeta, -1); carregarMetas(); });
$("mes-prox").addEventListener("click", () => { estado.mesMeta = somarMeses(estado.mesMeta, 1); carregarMetas(); });
$("busca").addEventListener("input", debounce((e) => { estado.busca = e.target.value.trim(); estado.pagina = 1; carregarLista(); }));
$("btn-tema").addEventListener("click", () => {
  const escuro = getComputedStyle(document.documentElement).colorScheme === "dark";
  const novo = escuro ? "claro" : "escuro";
  document.documentElement.dataset.tema = novo;
  try { localStorage.setItem("prumo.tema", novo); } catch { /* sem armazenamento */ }
  if (estado.resumo && !estado.resumo.vazio) grafico.desenhar();
});
$("btn-sair").addEventListener("click", async () => { try { await api.post("/api/logout"); } finally { location.href = "/login"; } });

// destaca o item do menu da seção visível
const links = [...document.querySelectorAll(".nav a")];
const observador = new IntersectionObserver((entradas) => {
  for (const e of entradas) if (e.isIntersecting) links.forEach((a) => a.setAttribute("aria-current", String(a.getAttribute("href") === `#${e.target.id}`)));
}, { rootMargin: "-40% 0px -55% 0px" });
links.forEach((a) => { const s = document.querySelector(a.getAttribute("href")); if (s) observador.observe(s); });

// ------------------------------------------------------------------ início
(async function iniciar() {
  try {
    estado.sessao = await api.get("/api/sessao");
    $("btn-sair").hidden = !estado.sessao.autenticacao;
    $("versao").textContent = `Versão ${estado.sessao.versao}`;
    if (estado.sessao.demo) {
      const faixa = $("faixa-demo"); faixa.hidden = false;
      faixa.append("Demonstração com dados fictícios, somente leitura. ");
      if (estado.sessao.repositorio) faixa.append(h("a", { href: estado.sessao.repositorio, rel: "noopener" }, "Ver código no GitHub"));
      $("btn-novo").hidden = $("btn-importar").hidden = $("btn-metas").hidden = true;
    }
    await carregarMeta();
    await recarregarTudo();
  } catch (e) { tratar(e); }
})();
