(() => {
  "use strict";

  const INTERVALLE_SUIVI_MS = 1000;
  const ICONES = { ok: "✔", erreur: "✘", avert: "⚠", ignore: "—" };

  const $ = (id) => document.getElementById(id);
  const el = {
    banniere: $("banniere-erreur"),
    banniereTexte: $("banniere-erreur-texte"),
    btnFermerBanniere: $("btn-fermer-banniere"),
    pointStatut: $("point-statut"),
    texteStatut: $("texte-statut"),
    listeVerifs: $("liste-verifs"),
    avertissementDuree: $("avertissement-duree"),
    btnCreer: $("btn-creer"),
    btnVerifier: $("btn-verifier"),
    btnReverifier: $("btn-reverifier"),
    blocProgression: $("bloc-progression"),
    progressionTitre: $("progression-titre"),
    tempsEcoule: $("temps-ecoule"),
    listeEtapes: $("liste-etapes"),
    blocResultat: $("bloc-resultat"),
    resultatTitre: $("resultat-titre"),
    resultatIntro: $("resultat-intro"),
    listeControles: $("liste-controles"),
    resultatErreur: $("resultat-erreur"),
    listeDurees: $("liste-durees"),
    btnReessayer: $("btn-reessayer"),
    modale: $("modale"),
    modaleTexte: $("modale-texte"),
    btnModaleAnnuler: $("btn-modale-annuler"),
    btnModaleConfirmer: $("btn-modale-confirmer"),
  };

  const etat = {
    bloquant: true,
    installation: false, // une installation tourne : on verrouille les boutons
    suivi: null,
  };

  // ------------------------------------------------------------------ //
  // Utilitaires
  // ------------------------------------------------------------------ //
  const api = () => window.pywebview.api;

  function creer(tag, classe, texte) {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  function formatDuree(ms) {
    const s = Math.round(ms / 1000);
    if (s < 60) return ms < 1000 ? `${Math.round(ms)} ms` : `${s} s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = String(s % 60).padStart(2, "0");
    return h ? `${h} h ${String(m).padStart(2, "0")} min ${sec} s` : `${m} min ${sec} s`;
  }

  function formatChrono(ms) {
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const mm = h ? String(m).padStart(2, "0") : String(m);
    const ss = String(s % 60).padStart(2, "0");
    return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }

  function formatNombre(n) {
    return Math.round(n).toLocaleString("fr-FR");
  }

  function afficherErreur(message) {
    el.banniereTexte.textContent = message;
    el.banniere.hidden = false;
  }

  function majStatut(niveau, texte) {
    el.pointStatut.className = "point-statut " + niveau;
    el.texteStatut.textContent = texte;
  }

  function majBoutons() {
    el.btnCreer.disabled = etat.bloquant || etat.installation;
    el.btnVerifier.disabled = etat.installation;
    el.btnReverifier.disabled = etat.installation;
    el.btnReessayer.disabled = etat.installation;
  }

  /** Liste de lignes {libelle, etat, detail} avec ✔ / ⚠ / ✘. */
  function rendreListe(conteneur, lignes) {
    conteneur.replaceChildren(
      ...lignes.map((l) => {
        const li = creer("li", `verif ${l.etat}`);
        const texte = creer("div");
        texte.append(creer("strong", "", l.libelle));
        if (l.detail) texte.append(creer("small", "", l.detail));
        li.append(creer("span", "verif-icone", ICONES[l.etat] || "?"), texte);
        return li;
      })
    );
  }

  // ------------------------------------------------------------------ //
  // Prérequis
  // ------------------------------------------------------------------ //
  async function verifierPrerequis() {
    majStatut("attente", "Vérification…");
    const rep = await api().verifier_prerequis();
    if (!rep.success) {
      etat.bloquant = true;
      majStatut("erreur", "Erreur");
      afficherErreur(rep.error);
      majBoutons();
      return;
    }
    rendreListe(el.listeVerifs, rep.verifications);
    etat.bloquant = rep.bloquant;
    majStatut(rep.bloquant ? "erreur" : "ok", rep.bloquant ? "Prérequis manquants" : "Prêt à installer");
    majBoutons();
  }

  // ------------------------------------------------------------------ //
  // Installation
  // ------------------------------------------------------------------ //
  function demander(texte) {
    return new Promise((resolve) => {
      el.modaleTexte.textContent = texte;
      el.modale.hidden = false;
      const fin = (valeur) => {
        el.modale.hidden = true;
        el.btnModaleAnnuler.onclick = el.btnModaleConfirmer.onclick = null;
        resolve(valeur);
      };
      el.btnModaleAnnuler.onclick = () => fin(false);
      el.btnModaleConfirmer.onclick = () => fin(true);
    });
  }

  async function creerBase() {
    if (etat.installation) return;
    el.banniere.hidden = true;
    etat.installation = true;
    majBoutons();
    try {
      let rep = await api().creer_base(false);
      if (!rep.success && rep.confirmation_requise) {
        if (!(await demander(rep.confirmation_requise))) {
          etat.installation = false;
          return;
        }
        rep = await api().creer_base(true);
      }
      if (rep.verifications) rendreListe(el.listeVerifs, rep.verifications);
      if (!rep.success) {
        etat.installation = false;
        afficherErreur(rep.error || "L'installation n'a pas pu démarrer.");
        return;
      }
      el.blocResultat.hidden = true;
      el.blocProgression.hidden = false;
      el.progressionTitre.textContent = "Installation en cours";
      majStatut("attente", "Installation en cours");
      suivre();
    } catch (e) {
      etat.installation = false;
      afficherErreur(String(e));
    } finally {
      majBoutons();
    }
  }

  function suivre() {
    arreterSuivi();
    const tick = async () => {
      const p = await api().get_progression();
      if (!p.success) {
        afficherErreur(p.error);
        return;
      }
      rendreProgression(p);
      if (p.phase === "termine" || p.phase === "erreur") {
        arreterSuivi();
        etat.installation = false;
        majBoutons();
        rendreFin(p);
      }
    };
    tick();
    etat.suivi = setInterval(tick, INTERVALLE_SUIVI_MS);
  }

  function arreterSuivi() {
    if (etat.suivi) clearInterval(etat.suivi);
    etat.suivi = null;
  }

  const ETATS_ETAPE = { attente: "en attente", en_cours: "en cours…", erreur: "échec" };

  function rendreProgression(p) {
    el.tempsEcoule.textContent = formatChrono(p.ecoule_ms);
    el.listeEtapes.replaceChildren(
      ...p.etapes.map((e, i) => {
        const li = creer("li", `etape ${e.etat}`);
        li.append(
          creer("span", "etape-num", `${i + 1}/${p.etapes.length}`),
          creer("span", "etape-titre", e.titre),
          creer("span", "etape-etat", e.etat === "ok" ? formatDuree(e.duree_ms) : ETATS_ETAPE[e.etat])
        );
        if (i === 1 && (e.etat === "en_cours" || e.etat === "ok")) {
          const pct = Math.min(100, (p.joueurs / p.total_joueurs) * 100);
          const barre = creer("div", "barre");
          const remplie = creer("div", "barre-remplie");
          remplie.style.width = `${pct}%`;
          barre.append(remplie);
          li.append(
            barre,
            creer(
              "div",
              "barre-legende",
              `${formatNombre(p.joueurs)} joueurs sur ${formatNombre(p.total_joueurs)} (${Math.floor(pct)} %) — mise à jour par paliers de 5 millions`
            )
          );
        }
        return li;
      })
    );
  }

  // ------------------------------------------------------------------ //
  // Résultat / contrôle final
  // ------------------------------------------------------------------ //
  function rendreFin(p) {
    el.blocResultat.hidden = false;
    el.progressionTitre.textContent = p.phase === "termine" ? "Installation terminée" : "Installation interrompue";

    const durees = p.etapes.filter((e) => e.etat === "ok").map((e) => [e.titre, formatDuree(e.duree_ms)]);
    durees.push(["Total", formatDuree(p.ecoule_ms)]);
    el.listeDurees.replaceChildren(
      ...durees.map(([nom, valeur]) => {
        const li = creer("li");
        li.append(creer("span", "", nom), creer("span", "", valeur));
        return li;
      })
    );
    el.listeDurees.hidden = false;

    if (p.phase === "erreur") {
      majStatut("erreur", "Installation échouée");
      el.resultatTitre.textContent = "L'installation a échoué";
      el.resultatIntro.textContent = "Voici le message complet de SQL Server. Corrigez le problème puis cliquez sur « Réessayer ».";
      el.listeControles.replaceChildren();
      el.resultatErreur.textContent = p.erreur;
      el.resultatErreur.hidden = false;
      el.btnReessayer.hidden = false;
      return;
    }

    el.resultatErreur.hidden = true;
    rendreControle(p.controle);
  }

  function rendreControle(controle) {
    rendreListe(el.listeControles, controle.controles);
    if (controle.ok) {
      majStatut("ok", "Prêt pour l'activité");
      el.resultatTitre.textContent = "Prêt pour l'activité";
      el.resultatIntro.textContent = "La base LootTable est installée et sauvegardée. Vous pouvez lancer l'activité (lancer_activite.bat).";
      el.btnReessayer.hidden = true;
    } else {
      majStatut("erreur", "Installation incomplète");
      el.resultatTitre.textContent = "Installation incomplète";
      const nb = controle.controles.filter((c) => c.etat === "erreur").length;
      el.resultatIntro.textContent = `${nb} contrôle(s) en échec (✘). Cliquez sur « Réessayer » pour recréer la base.`;
      el.btnReessayer.hidden = false;
    }
  }

  async function verifierInstallation() {
    if (etat.installation) return;
    el.banniere.hidden = true;
    etat.installation = true;
    majBoutons();
    majStatut("attente", "Contrôle en cours…");
    try {
      const rep = await api().verifier_installation();
      if (!rep.success) {
        afficherErreur(rep.error);
        majStatut("erreur", "Erreur");
        return;
      }
      el.blocProgression.hidden = true;
      el.blocResultat.hidden = false;
      el.listeDurees.hidden = true;
      el.resultatErreur.hidden = true;
      rendreControle(rep);
    } finally {
      etat.installation = false;
      majBoutons();
    }
  }

  // ------------------------------------------------------------------ //
  // Initialisation
  // ------------------------------------------------------------------ //
  async function initialiser() {
    el.btnCreer.addEventListener("click", creerBase);
    el.btnReessayer.addEventListener("click", creerBase);
    el.btnVerifier.addEventListener("click", verifierInstallation);
    el.btnReverifier.addEventListener("click", verifierPrerequis);
    el.btnFermerBanniere.addEventListener("click", () => (el.banniere.hidden = true));
    await verifierPrerequis();
  }

  window.addEventListener("pywebviewready", initialiser);
})();
