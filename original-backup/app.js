const chat = document.getElementById("chat");
const cameraInput = document.getElementById("cameraInput");
const galleryInput = document.getElementById("galleryInput");
const networkBtn = document.getElementById("networkBtn");

let online = true;
let currentImages = [];
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
    const container = document.createElement("div");
    container.className = "actions";

    buttons.forEach(button => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = button.text || button.label;

        btn.addEventListener("click", () => {
            button.action();
        });

        container.appendChild(btn);
    });

    chat.appendChild(container);
    chat.scrollTop = chat.scrollHeight;
}


// ============================================================
// START VISIT
// ============================================================

function startVisit() {
    currentImages = [];
    currentExtraction = null;

    addMessage(
        `📄 <strong>Nouvelle visite</strong><br><br>
        Ajoutez la première page du carnet de la patiente.`
    );

    showImageOptions();
}

function showImageOptions() {
    addMessage("Comment souhaitez-vous ajouter cette page ?");

    addActions([
        {
            text: "📷 Prendre une photo",
            action: () => cameraInput.click()
        },
        {
            text: "🖼️ Choisir une image",
            action: () => galleryInput.click()
        }
    ]);
}

// ============================================================
// RECEIVE PHOTOS
// ============================================================

// Camera: one photo at a time
cameraInput.addEventListener("change", () => {
    const file = cameraInput.files[0];

    if (!file) return;

    currentImages.push(file);

    const pageNumber = currentImages.length;
    const imageURL = URL.createObjectURL(file);

    addMessage(
        `<img class="preview" src="${imageURL}">
        <br><strong>Page ${pageNumber} ajoutée ✓</strong>`,
        "user"
    );

    cameraInput.value = "";

    askForAnotherPage();
});


// Gallery: one OR multiple images at once
galleryInput.addEventListener("change", () => {
    const files = Array.from(galleryInput.files);

    if (files.length === 0) return;

    files.forEach(file => {
        currentImages.push(file);

        const pageNumber = currentImages.length;
        const imageURL = URL.createObjectURL(file);

        addMessage(
            `<img class="preview" src="${imageURL}">
            <br><strong>Page ${pageNumber} ajoutée ✓</strong>`,
            "user"
        );
    });

    galleryInput.value = "";

    addMessage(
        `📄 <strong>${files.length} image(s) ajoutée(s).</strong><br>
        Total du dossier : ${currentImages.length} page(s).`
    );

    askForAnotherPage();
});
// ============================================================
// REAL AI EXTRACTION
// ============================================================

async function processImages() {
    if (currentImages.length === 0) {
        addMessage("Aucune page à analyser.", "system");
        return;
    }

    addMessage(
        `🤖 <strong>Analyse de ${currentImages.length} page(s) en cours...</strong><br>
        Cela peut prendre quelques secondes.`,
        "system"
    );

    const results = [];

    for (let i = 0; i < currentImages.length; i++) {

        addMessage(
            `🔍 Analyse de la page ${i + 1}/${currentImages.length}...`,
            "system"
        );

        const formData = new FormData();

        formData.append("image", currentImages[i]);

        // TEMPORARY:
        // We will replace this with proper page identification next.
        formData.append("page_type", String(i + 1));

        try {
            const response = await fetch("/api/extract", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || `Erreur lors de l'analyse de la page ${i + 1}`
                );
            }

            results.push({
                pageNumber: i + 1,
                extraction: data
            });

            addMessage(
                `✅ Page ${i + 1} analysée.`,
                "system"
            );

        } catch (error) {
            console.error(error);

            addMessage(
                `❌ <strong>Erreur page ${i + 1}</strong><br>${error.message}`,
                "system"
            );
        }
    }

    currentExtraction = results;

    showMultipleResults(results);
}

function showMultipleResults(results) {

    if (results.length === 0) {
        addMessage(
            "❌ Aucune page n'a pu être analysée.",
            "system"
        );
        return;
    }

    addMessage(
        `📋 <strong>Analyse terminée</strong><br><br>
        ${results.length} page(s) traitée(s).`
    );

    results.forEach(result => {

        const data = result.extraction;

        let html =
            `<strong>📄 Page ${result.pageNumber}</strong><br>
             Statut : <strong>${data.status || "AI_PROCESSED"}</strong><br><br>`;

        if (data.fields && data.fields.length > 0) {

            data.fields.forEach(field => {

                let value = field.value;

                if (
                    value === null ||
                    value === undefined ||
                    value === ""
                ) {
                    value = "—";
                }

                html +=
                    `<strong>${field.label || field.name}</strong>: ${value}<br>
                     <small>
                     ${field.status} · confiance ${
                         Math.round((field.confidence || 0) * 100)
                     }%
                     </small><br><br>`;
            });

        } else {
            html += "Aucun champ extrait.";
        }

        addMessage(html);
    });

    addMessage(
        `👩‍⚕️ Vérifiez les champs marqués <strong>NEEDS_REVIEW</strong> ou <strong>ILLEGIBLE</strong>.`
    );
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

    if (currentImage.length > 0) {
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