const form = document.getElementById("form");
const erro = document.getElementById("erro");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  erro.textContent = "";
  const botao = form.querySelector("button");
  botao.disabled = true;
  try {
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ senha: form.senha.value }) });
    if (r.ok) { location.href = "/"; return; }
    erro.textContent = (await r.json()).detail || "Não foi possível entrar.";
  } catch { erro.textContent = "Sem conexão com o servidor."; }
  botao.disabled = false;
  form.senha.select();
});
