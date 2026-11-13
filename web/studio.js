const templateForm = document.querySelector("#template-form");
const speechForm = document.querySelector("#speech-form");
const templateSelect = speechForm.elements.template;
const templateButton = templateForm.querySelector("button");
const speechButton = speechForm.querySelector("button");
const playback = document.querySelector("#playback");
let busy = false;

function updateButtons() {
  templateButton.disabled = busy;
  speechButton.disabled = busy || !templateSelect.value;
}

function setStatus(form, message, error = false) {
  const status = form.querySelector(".status");
  status.textContent = message;
  status.classList.toggle("error", error);
}

async function fetchData(url, options) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.error || "请求失败，请检查本机服务是否仍在运行。");
  }
  return result;
}

async function loadTemplates(selected = templateSelect.value) {
  const { templates } = await fetchData("/api/templates");
  templateSelect.replaceChildren();
  if (!templates.length) {
    templateSelect.add(new Option("请先生成一个模板", ""));
  }
  for (const name of templates) {
    templateSelect.add(new Option(name, name));
  }
  if (templates.includes(selected)) {
    templateSelect.value = selected;
  }
  updateButtons();
}

async function submit(form, pending, onSuccess) {
  if (busy) return;
  busy = true;
  updateButtons();
  setStatus(form, pending);
  form.setAttribute("aria-busy", "true");
  try {
    const result = await fetchData(form.action, {
      method: "POST",
      headers: { "X-Voice-Studio": "1" },
      body: new FormData(form),
    });
    await onSuccess(result);
  } catch (error) {
    setStatus(form, error instanceof TypeError ? "连接中断，请检查本机服务后重试。" : error.message, true);
  } finally {
    busy = false;
    form.removeAttribute("aria-busy");
    updateButtons();
  }
}

templateForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(templateForm, "正在生成音色模板…", async ({ name }) => {
    await loadTemplates(name);
    templateForm.reset();
    setStatus(templateForm, `已保存「${name}」，可直接用于配音。`);
  });
});

speechForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(speechForm, "正在生成配音，长文案需要多等一会儿…", ({ audio, download }) => {
    playback.querySelector("audio").src = audio;
    playback.querySelector(".download").href = download;
    playback.hidden = false;
    setStatus(speechForm, "配音已生成，可以试听和下载。");
  });
});

templateSelect.addEventListener("change", updateButtons);
loadTemplates().catch(() => {
  templateSelect.replaceChildren(new Option("暂时无法读取模板", ""));
  setStatus(speechForm, "模板列表读取失败，请检查本机服务后刷新。", true);
  updateButtons();
});
