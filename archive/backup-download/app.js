const NOM_FICHIER = "LootTable.bak";

const btnTelecharger = document.getElementById("btn-telecharger");
const fichierTaille = document.getElementById("fichier-taille");
const progressionConteneur = document.getElementById("progression-conteneur");
const progressionBarre = document.getElementById("progression-barre");
const progressionTexte = document.getElementById("progression-texte");
const messageErreur = document.getElementById("message-erreur");
const lienSecours = document.getElementById("lien-secours");

function formaterOctets(octets) {
  if (!octets && octets !== 0) return "";
  const unites = ["o", "Ko", "Mo", "Go"];
  let taille = octets;
  let i = 0;
  while (taille >= 1024 && i < unites.length - 1) {
    taille /= 1024;
    i++;
  }
  return `${taille.toFixed(1)} ${unites[i]}`;
}

async function afficherTaille() {
  try {
    const reponse = await fetch(NOM_FICHIER, { method: "HEAD" });
    const taille = reponse.headers.get("Content-Length");
    if (taille) {
      fichierTaille.textContent = formaterOctets(Number(taille));
    }
  } catch {
    // Si le HEAD échoue, on garde "Taille inconnue" et on laisse le téléchargement tenter quand même.
  }
}

async function telechargerFichier() {
  btnTelecharger.disabled = true;
  messageErreur.hidden = true;
  progressionConteneur.hidden = false;
  progressionTexte.hidden = false;
  progressionBarre.style.width = "0%";
  progressionTexte.textContent = "Connexion…";

  try {
    const reponse = await fetch(NOM_FICHIER);
    if (!reponse.ok) {
      throw new Error(`Le serveur a répondu ${reponse.status}`);
    }

    const tailleTotale = Number(reponse.headers.get("Content-Length")) || 0;
    const lecteur = reponse.body.getReader();
    const morceaux = [];
    let recu = 0;

    while (true) {
      const { done, value } = await lecteur.read();
      if (done) break;
      morceaux.push(value);
      recu += value.length;

      if (tailleTotale) {
        const pourcent = Math.round((recu / tailleTotale) * 100);
        progressionBarre.style.width = `${pourcent}%`;
        progressionTexte.textContent = `${formaterOctets(recu)} / ${formaterOctets(tailleTotale)} (${pourcent}%)`;
      } else {
        progressionTexte.textContent = `${formaterOctets(recu)} téléchargés…`;
      }
    }

    const blob = new Blob(morceaux);
    const urlBlob = URL.createObjectURL(blob);

    const lien = document.createElement("a");
    lien.href = urlBlob;
    lien.download = NOM_FICHIER;
    document.body.appendChild(lien);
    lien.click();
    document.body.removeChild(lien);
    URL.revokeObjectURL(urlBlob);

    progressionTexte.textContent = "Téléchargement terminé ✅";
    progressionBarre.style.width = "100%";
  } catch (erreur) {
    messageErreur.textContent = `Échec du téléchargement : ${erreur.message}`;
    messageErreur.hidden = false;
    lienSecours.hidden = false;
  } finally {
    btnTelecharger.disabled = false;
  }
}

btnTelecharger.addEventListener("click", telechargerFichier);

afficherTaille();
