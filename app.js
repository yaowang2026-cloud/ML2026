const chat = document.getElementById("chat");
const cameraInput = document.getElementById("cameraInput");
const networkBtn = document.getElementById("networkBtn");

let online = true;
let currentImage = null;


// ----------------------
// HELPERS
// ----------------------

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


// ----------------------
// START VISIT
// ----------------------

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


// ----------------------
// RECEIVE PHOTO
// ----------------------

cameraInput.addEventListener("change", function(event) {

  const file = event.target.files[0];

  if (!file) return;

  currentImage = file;

  const imageURL = URL.createObjectURL(file);

  addMessage(`
    <img class="preview" src="${imageURL}">
  `, "user");

  addMessage(`
    🔍 Vérification de la qualité de l'image...
  `);

  setTimeout(() => {

    addMessage(`
      ✅ Page détectée<br>
      ✅ Image lisible<br>
      🔒 Photo enregistrée localement
    `);

    if (online) {

      processImage();

    } else {

      addMessage(`
        📴 Vous êtes hors ligne.<br><br>

        La photo est enregistrée de façon sécurisée
        sur cet appareil.<br><br>

        🟠 <strong>EN ATTENTE DE TRAITEMENT IA</strong>
      `, "system");

    }

  }, 1000);

});


// ----------------------
// MOCK AI
// ----------------------

function processImage() {

  addMessage(`
    🤖 Analyse du registre en cours...
  `);

  setTimeout(showResults, 1500);
}


function showResults() {

  addMessage(`
    <strong>Extraction terminée ✓</strong><br><br>

    <div class="field">
      ✅ Âge : <strong>31 ans</strong><br>
      Confiance : 98%
    </div>

    <div class="field">
      ✅ Grossesse désirée : <strong>Oui</strong><br>
      Confiance : 96%
    </div>

    <div class="field">
      ✅ Tension : <strong>110/70 mmHg</strong><br>
      Confiance : 94%
    </div>

    <div class="field warning">
      ⚠️ Poids : <strong>63 kg ?</strong><br>
      Confiance : 61%<br>
      Statut : À RÉVISER
    </div>
  `);

  addMessage(`
    J'ai un doute sur <strong>1 champ</strong>.<br><br>

    J'ai lu le poids comme <strong>63 kg</strong>.<br>
    Est-ce correct ?
  `);

  addActions([
    {
      label: "✅ Oui, confirmer",
      action: confirmWeight
    },

    {
      label: "✏️ Corriger",
      action: correctWeight
    },

    {
      label: "📷 Reprendre la photo",
      action: () => cameraInput.click()
    }
  ]);
}


// ----------------------
// REVIEW
// ----------------------

function confirmWeight() {

  addMessage("✅ Oui, 63 kg", "user");

  addMessage(`
    Parfait. Toutes les informations ont été vérifiées. ✅
  `);

  patientMatch();
}


function correctWeight() {

  const value = prompt("Entrez le poids corrigé :");

  if (!value) return;

  addMessage(`✏️ ${value} kg`, "user");

  addMessage(`
    Poids corrigé : <strong>${value} kg</strong> ✅
  `);

  patientMatch();
}


// ----------------------
// PATIENT MATCHING
// ----------------------

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
      label: "➕ Créer un nouveau dossier",
      action: saveRecord
    },

    {
      label: "❓ Je ne sais pas",
      action: () =>
        addMessage("Le dossier a été marqué pour révision.")
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


// ----------------------
// ONLINE / OFFLINE
// ----------------------

networkBtn.addEventListener("click", function() {

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