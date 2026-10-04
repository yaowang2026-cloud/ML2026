const chat = document.getElementById("chat");
const cameraInput = document.getElementById("cameraInput");
const networkBtn = document.getElementById("networkBtn");

let online = true;
let currentImage = null;
let currentExtraction = null;


// ============================================================
// HELPERS
// ============================================================

function addMessage(html, type = "bot") {
  const message = document.createElement("div");

  message.className = `message ${type}`;
  message.innerHTML = html;

  chat.appendChild(message);
  chat.scrollTop = chat.scrollHeight;
}


function addActions(buttons) {
  const actions = document.createElement("div");
  actions.className = "actions";

  buttons.forEach(button => {
    const btn = document.createElement("button");

    btn.innerHTML = button.label;
    btn.onclick = button.action;

    actions.appendChild(btn);
  });

  chat.appendChild(actions);
  chat.scrollTop = chat.scrollHeight;
}


// ============================================================
// START VISIT
// ============================================================

function startVisit() {
  addMessage("📷 Nouvelle visite", "user");

  addMessage(`
    Photographiez la page du carnet de grossesse.<br><br>

    ✓ Toute la page doit être visible<br>
    ✓ Évitez les ombres<br>
    ✓ Assurez-vous que l'image est nette
  `);

  addActions([
    {
      label: "📷 Prendre une photo",
      action: () => cameraInput.click()
    },
    {
      label: "🖼️ Choisir une photo",
      action: () => cameraInput.click()
    }
  ]);
}


// ============================================================
// RECEIVE PHOTO
// ============================================================

cameraInput.addEventListener("change", function (event) {
  const file = event.target.files[0];

  if (!file) return;

  currentImage = file;

  const imageURL = URL.createObjectURL(file);

  addMessage(`
    <img class="preview" src="${imageURL}">
  `, "user");

  addMessage("🔍 Vérification de l'image...");

  if (online) {
    processImage();
  } else {
    addMessage(`
      📴 Vous êtes hors ligne.<br><br>

      La photo est conservée sur cet appareil.<br><br>

      🟠 <strong>PENDING_AI</strong><br>
      Traitement dès le retour de la connexion.
    `, "system");
  }
});


// ============================================================
// REAL AI EXTRACTION
// ============================================================

async function processImage() {
  if (!currentImage) {
    addMessage("❌ Aucune image sélectionnée.", "system");
    return;
  }

  addMessage(`
    🤖 Analyse du registre en cours...
  `);

  try {
    const formData = new FormData();

    formData.append("image", currentImage);

    // TEMPORARY:
    // We use page type 4 for our first end-to-end test.
    formData.append("page_type", "4");

    const response = await fetch("/api/extract", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.error || "Erreur pendant l'extraction."
      );
    }

    currentExtraction = data;

    showResults(data);

  } catch (error) {
    console.error(error);

    addMessage(`
      ❌ <strong>Erreur pendant l'analyse.</strong><br><br>
      ${error.message}
    `, "system");
  }
}


// ============================================================
// SHOW EXTRACTION RESULTS
// ============================================================

function showResults(extraction) {
  if (!extraction.fields || extraction.fields.length === 0) {
    addMessage(`
      ⚠️ Aucun champ n'a été extrait.
    `);

    return;
  }

  let resultsHTML = `
    <strong>Extraction terminée ✓</strong><br><br>
  `;

  extraction.fields.forEach(field => {
    const confidence =
      Math.round((field.confidence || 0) * 100);

    let icon = "✅";
    let cssClass = "field";

    if (field.status === "NEEDS_REVIEW") {
      icon = "⚠️";
      cssClass = "field warning";
    }

    if (field.status === "ILLEGIBLE") {
      icon = "❓";
      cssClass = "field warning";
    }

    if (field.status === "NOT_PROVIDED") {
      icon = "➖";
    }

    resultsHTML += `
      <div class="${cssClass}">
        ${icon}
        <strong>${field.label}</strong> :
        ${field.value || "Non fourni"}
        <br>

        Confiance : ${confidence}%
        <br>

        Statut : ${field.status}
      </div>
    `;
  });

  addMessage(resultsHTML);

  reviewNextField();
}


// ============================================================
// REVIEW UNCERTAIN FIELDS
// ============================================================

function reviewNextField() {
  if (!currentExtraction) return;

  const field = currentExtraction.fields.find(
    field =>
      field.status === "NEEDS_REVIEW" ||
      field.status === "ILLEGIBLE"
  );

  if (!field) {
    addMessage(`
      ✅ Toutes les informations ont été vérifiées.
    `);

    patientMatch();
    return;
  }

  if (field.status === "NEEDS_REVIEW") {
    addMessage(`
      ⚠️ J'ai un doute sur
      <strong>${field.label}</strong>.<br><br>

      J'ai lu :
      <strong>${field.value || "Aucune valeur"}</strong>.<br><br>

      Est-ce correct ?
    `);

    addActions([
      {
        label: "✅ Confirmer",
        action: () => confirmField(field)
      },
      {
        label: "✏️ Modifier",
        action: () => editField(field)
      },
      {
        label: "📷 Reprendre",
        action: () => cameraInput.click()
      }
    ]);

    return;
  }

  if (field.status === "ILLEGIBLE") {
    addMessage(`
      ❓ Je n'arrive pas à lire
      <strong>${field.label}</strong>.<br><br>

      Que souhaitez-vous faire ?
    `);

    addActions([
      {
        label: "✏️ Saisir manuellement",
        action: () => editField(field)
      },
      {
        label: "📷 Reprendre la photo",
        action: () => cameraInput.click()
      }
    ]);
  }
}


// ============================================================
// CONFIRM / EDIT
// ============================================================

function confirmField(field) {
  field.status = "KNOWN";
  field.confidence = 1;

  addMessage(`
    ✅ ${field.label} : ${field.value}
  `, "user");

  reviewNextField();
}


function editField(field) {
  const newValue = prompt(
    `Entrez la valeur pour ${field.label} :`,
    field.value || ""
  );

  if (newValue === null || newValue.trim() === "") {
    return;
  }

  field.value = newValue.trim();
  field.status = "KNOWN";
  field.confidence = 1;

  addMessage(`
    ✏️ ${field.label} : ${field.value}
  `, "user");

  reviewNextField();
}


// ============================================================
// PATIENT MATCHING
// ============================================================

function patientMatch() {
  addMessage(`
    🔗 Entrez le code de la patiente inscrit sur le registre.
  `);

  addActions([
    {
      label: "Demo : A7K4",
      action: showPatient
    }
  ]);
}


function showPatient() {
  addMessage("A7K4", "user");

  addMessage(`
    🔎 Correspondance possible trouvée.<br><br>

    <strong>Patiente A7K4</strong><br>
    Dernière visite : 23/07/2026<br><br>

    S'agit-il de la même patiente ?
  `);

  addActions([
    {
      label: "✅ Même patiente",
      action: saveRecord
    },
    {
      label: "➕ Nouveau dossier",
      action: saveRecord
    },
    {
      label: "❓ Je ne sais pas",
      action: () => {
        addMessage(`
          ⚠️ Le dossier a été marqué pour révision.
        `);
      }
    }
  ]);
}


function saveRecord() {
  addMessage(`
    ✅ <strong>Dossier enregistré</strong><br><br>

    🔗 Visite liée<br>
    🔒 Données sécurisées<br>
    ☁️ Synchronisé
  `);
}


// ============================================================
// FIND PATIENT
// ============================================================

function findPatient() {
  addMessage("🔎 Retrouver une patiente", "user");

  addMessage(`
    Entrez le code anonyme attribué à la patiente.
  `);

  addActions([
    {
      label: "Demo : A7K4",
      action: showPatient
    }
  ]);
}


// ============================================================
// ONLINE / OFFLINE
// ============================================================

networkBtn.addEventListener("click", function () {
  online = !online;

  if (online) {
    networkBtn.innerHTML = "● En ligne";
    networkBtn.className = "online";

    addMessage(`
      🟢 Connexion rétablie.<br>
      Synchronisation en cours...
    `, "system");

    if (currentImage) {
      setTimeout(processImage, 800);
    }

  } else {
    networkBtn.innerHTML = "● Hors ligne";
    networkBtn.className = "offline";

    addMessage(`
      📴 Mode hors ligne activé
    `, "system");
  }
});

// ============================================================
// MESSAGE BAR
// ============================================================

const messageInput =
  document.getElementById("messageInput");

const sendBtn =
  document.getElementById("sendBtn");

const attachBtn =
  document.getElementById("attachBtn");


function sendMessage() {

  const text = messageInput.value.trim();

  if (!text) return;

  addMessage(text, "user");

  messageInput.value = "";

  // Simple conversational commands
  const lowerText = text.toLowerCase();

  if (
    lowerText.includes("nouvelle") ||
    lowerText.includes("visite") ||
    lowerText.includes("photo")
  ) {

    startVisit();
    return;
  }

  if (
    lowerText.includes("patiente") ||
    lowerText.includes("patient") ||
    lowerText.includes("retrouver")
  ) {

    findPatient();
    return;
  }

  addMessage(`
    Je peux vous aider à :<br><br>

    📷 Numériser une nouvelle visite<br>
    🔎 Retrouver une patiente
  `);
}


sendBtn.addEventListener(
  "click",
  sendMessage
);


messageInput.addEventListener(
  "keydown",
  function(event) {

    if (event.key === "Enter") {
      sendMessage();
    }

  }
);


attachBtn.addEventListener(
  "click",
  function() {

    cameraInput.click();

  }
);