export function getSelectedLanguage() {
  return localStorage.getItem("selected_language") || "";
}

export function setSelectedLanguage(languageId) {
  localStorage.setItem("selected_language", languageId);
}

