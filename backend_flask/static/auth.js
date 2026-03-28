(() => {
  const btn = document.getElementById("togglePw");
  const input = document.getElementById("password");
  if (!btn || !input) return;

  btn.addEventListener("click", () => {
    const isPw = input.getAttribute("type") === "password";
    input.setAttribute("type", isPw ? "text" : "password");
    btn.setAttribute("aria-label", isPw ? "Hide password" : "Show password");
  });
})();

