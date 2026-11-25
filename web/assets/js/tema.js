try { const t = localStorage.getItem("prumo.tema"); if (t === "claro" || t === "escuro") document.documentElement.dataset.tema = t; } catch (e) { /* sem armazenamento */ }
