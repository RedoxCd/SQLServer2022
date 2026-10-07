(() => {
  "use strict";

  const INTERVALLE_POLLING_MS = 3000;
  const DELAI_RECHERCHE_JEU_MS = 250;
  const CLICS_LOGO_ANIMATEUR = 5;

  const $ = (id) => document.getElementById(id);
  const el = {
    overlay: $("incident-overlay"),
    banniereErreur: $("banniere-erreur"),
    banniereErreurTexte: $("banniere-erreur-texte"),
    btnReessayer: $("btn-reessayer"),
    pointStatut: $("point-statut"),
    texteStatut: $("texte-statut"),
    logo: $("logo"),
    // catalogue
    champJeu: $("champ-jeu"),
    catalogueInfo: $("catalogue-info"),
    listeJeux: $("liste-jeux"),
    // ami
    recapJeu: $("recap-jeu"),
    champVisiteur: $("champ-visiteur"),
    champAmi: $("champ-ami"),
    amiErreur: $("ami-erreur"),
    btnRetourCatalogue: $("btn-retour-catalogue"),
    btnOffrir: $("btn-offrir"),
    // recherche
    rechercheTitre: $("recherche-titre"),
    champRecherche: $("champ-recherche"),
    btnRechercher: $("btn-rechercher"),
    chronoAvant: $("chrono-avant"),
    chronoApres: $("chrono-apres"),
    valeurAvant: $("valeur-avant"),
    valeurApres: $("valeur-apres"),
    rapport: $("chrono-rapport"),
    rechercheMessage: $("recherche-message"),
    btnRelancer: $("btn-relancer"),
    btnOk: $("btn-ok"),
    // panne / reveal / attente
    panneMessage: $("panne-message"),
    panneChrono: $("panne-chrono"),
    revealAchat: $("reveal-achat"),
    revealDurees: $("reveal-durees"),
    attenteTitre: $("attente-titre"),
    attenteMessage: $("attente-message"),
    attenteChrono: $("attente-chrono"),
    // animateur
    panneau: $("panneau-animateur"),
    animStatut: $("anim-statut"),
    animJournal: $("anim-journal"),
    btnFermerAnim: $("btn-fermer-anim"),
    btnIndex: $("btn-index"),
    btnRestaurer: $("btn-restaurer"),
    btnReset: $("btn-reset"),
  };

  const etat = {
    ecran: "attente",
    jeu: null,
    visiteur: "",
    ami: "",
    avantMs: null,
    apresMs: null,
    indexActif: false, // idx_pseudo reconstruit
    enCours: false, // une action est en vol, on verrouille les boutons
    operation: null, // opération serveur en cours (index, reset...), vue par le polling
    sauvegarde: null,
    confirmationReset: null,
    sequenceJeux: 0,
    pollHandle: null,
    chronoHandle: null,
  };

  // ------------------------------------------------------------------ //
  // Utilitaires
  // ------------------------------------------------------------------ //
  function api() {
    return window.pywebview.api;
  }

  function formatDuree(ms) {
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} s`;
  }

  function formatMmSs(ms) {
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  function formatPrix(prix) {
    return prix.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  }

  function creer(tag, classe, texte) {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  function afficherErreur(message) {
    el.banniereErreurTexte.textContent = message;
    el.banniereErreur.hidden = false;
  }

  function masquerErreur() {
    el.banniereErreur.hidden = true;
  }

  function majPointStatut(niveau, texte) {
    el.pointStatut.className = "point-statut " + niveau;
    el.texteStatut.textContent = texte;
  }

  function journal(texte) {
    const li = creer("li", "", `${new Date().toLocaleTimeString("fr-FR")} — ${texte}`);
    el.animJournal.prepend(li);
  }

  function afficherEcran(nom) {
    etat.ecran = nom;
    document.body.dataset.ecran = nom;
    majBoutons();
  }

  /** Chrono « mm:ss » qui défile pendant une opération longue (reset, restauration). */
  function demarrerChrono(cible) {
    arreterChrono();
    const debut = performance.now();
    cible.hidden = false;
    cible.textContent = "0:00";
    etat.chronoHandle = setInterval(() => {
      cible.textContent = formatMmSs(performance.now() - debut);
    }, 500);
  }

  function arreterChrono() {
    if (etat.chronoHandle) clearInterval(etat.chronoHandle);
    etat.chronoHandle = null;
  }

  // ------------------------------------------------------------------ //
  // Panneau animateur (caché : Ctrl+Maj+L ou 5 clics rapides sur le logo)
  // ------------------------------------------------------------------ //
  function basculerPanneau() {
    el.panneau.hidden = !el.panneau.hidden;
  }

  function majBoutons() {
    const libre = !etat.enCours && !etat.operation;
    el.btnIndex.disabled = !(libre && etat.ecran === "recherche" && !etat.indexActif);
    el.btnRestaurer.disabled = !(libre && etat.ecran === "panne");
    el.btnReset.disabled = !libre;
    el.btnRechercher.disabled = etat.enCours || !!etat.operation;
    el.btnRelancer.disabled = etat.enCours || !!etat.operation;
    el.btnOk.disabled = etat.enCours || !!etat.operation;
  }

  function majStatutAnimateur() {
    const morceaux = [];
    const libelles = {
      index: "Activation de l'index en cours…",
      incident: "Incident en cours…",
      restauration: "Restauration en cours…",
      reset: "Réinitialisation en cours (1 à 2 min)…",
    };
    if (etat.operation) morceaux.push(libelles[etat.operation] || etat.operation);
    const s = etat.sauvegarde;
    if (s && s.etat === "en_cours") morceaux.push("Sauvegarde DIFF en arrière-plan…");
    else if (s && s.etat === "ok") morceaux.push(`Sauvegarde DIFF terminée (${formatDuree(s.duree_ms)}).`);
    else if (s && s.etat === "erreur") morceaux.push(`Sauvegarde DIFF en échec : ${s.erreur}`);
    if (!morceaux.length) morceaux.push(etat.indexActif ? "Index actif." : "Index désactivé.");
    el.animStatut.textContent = morceaux.join(" ");
  }

  // ------------------------------------------------------------------ //
  // Écran 1 : catalogue
  // ------------------------------------------------------------------ //
  async function chargerJeux() {
    const sequence = ++etat.sequenceJeux;
    const rep = await api().rechercher_jeux(el.champJeu.value);
    if (sequence !== etat.sequenceJeux) return; // une recherche plus récente a pris le relais
    if (!rep.success) {
      afficherErreur(rep.error);
      return;
    }
    masquerErreur();
    el.listeJeux.replaceChildren(...rep.jeux.map(carteJeu));
    el.catalogueInfo.textContent = rep.jeux.length
      ? ""
      : "Aucun jeu ne correspond. Essaie un autre mot !";
  }

  function carteJeu(jeu) {
    const carte = creer("article", "carte jeu");
    carte.append(
      creer("h3", "", jeu.titre),
      creer("p", "jeu-meta", `${jeu.plateforme} · ${jeu.genre} · ${jeu.annee}`)
    );
    const pied = creer("div", "jeu-pied");
    const bouton = creer("button", "bouton", "Offrir ce jeu");
    bouton.addEventListener("click", () => choisirJeu(jeu));
    pied.append(creer("span", "jeu-prix", formatPrix(jeu.prix)), bouton);
    carte.append(pied);
    return carte;
  }

  function choisirJeu(jeu) {
    etat.jeu = jeu;
    el.recapJeu.replaceChildren(
      creer("h3", "", jeu.titre),
      creer("p", "jeu-meta", `${jeu.plateforme} · ${jeu.genre}`),
      creer("span", "jeu-prix", formatPrix(jeu.prix))
    );
    el.amiErreur.hidden = true;
    afficherEcran("ami");
    (el.champVisiteur.value ? el.champAmi : el.champVisiteur).focus();
  }

  // ------------------------------------------------------------------ //
  // Écran 2 : offrir le jeu (INSERT joueur + achat, en transaction)
  // ------------------------------------------------------------------ //
  async function offrirJeu() {
    if (etat.enCours) return;
    const visiteur = el.champVisiteur.value.trim();
    const ami = el.champAmi.value.trim();
    if (!visiteur || !ami) {
      el.amiErreur.textContent = "Il manque ton pseudo ou celui de ton ami.";
      el.amiErreur.hidden = false;
      return;
    }
    el.amiErreur.hidden = true;
    etat.enCours = true;
    el.btnOffrir.disabled = true;
    majBoutons();
    try {
      const rep = await api().offrir_jeu(etat.jeu.jeux_id, ami, visiteur);
      if (!rep.success) {
        el.amiErreur.textContent = rep.error;
        el.amiErreur.hidden = false;
        return;
      }
      masquerErreur();
      etat.visiteur = visiteur;
      etat.ami = ami;
      journal(`Cadeau enregistré : achat n°${rep.achats_id} (${formatPrix(rep.prix_paye)}).`);
      preparerRecherche();
    } finally {
      etat.enCours = false;
      el.btnOffrir.disabled = false;
      majBoutons();
    }
  }

  // ------------------------------------------------------------------ //
  // Écran 3 : recherche de l'ami, chrono avant / après
  // ------------------------------------------------------------------ //
  function preparerRecherche() {
    etat.avantMs = null;
    etat.apresMs = null;
    el.champRecherche.value = etat.ami;
    el.valeurAvant.textContent = "—";
    el.valeurApres.textContent = "—";
    el.chronoAvant.classList.remove("actif");
    el.chronoApres.classList.remove("actif");
    el.rapport.hidden = true;
    el.btnRelancer.hidden = true;
    el.btnOk.hidden = true;
    el.rechercheTitre.textContent = "Cadeau enregistré !";
    el.rechercheMessage.textContent = "";
    afficherEcran("recherche");
  }

  async function rechercherAmi() {
    if (etat.enCours || etat.operation) return;
    const pseudo = el.champRecherche.value.trim();
    if (!pseudo) return;
    etat.enCours = true;
    majBoutons();
    // Le vrai cadre (avant / après) est déterminé par is_disabled dans la réponse ;
    // en attendant, on anime celui que l'on attend.
    const cible = etat.indexActif ? el.valeurApres : el.valeurAvant;
    const texteAvant = cible.textContent;
    cible.textContent = "…";
    cible.classList.add("en-cours");
    el.rechercheMessage.textContent = "Recherche en cours parmi 50 millions de joueurs…";
    try {
      const rep = await api().rechercher_joueur(pseudo);
      cible.classList.remove("en-cours");
      cible.textContent = texteAvant;
      if (!rep.success) {
        el.rechercheMessage.textContent = "";
        afficherErreur(rep.error);
        return;
      }
      masquerErreur();
      afficherResultatRecherche(rep, pseudo);
    } finally {
      cible.classList.remove("en-cours");
      etat.enCours = false;
      majBoutons();
    }
  }

  function afficherResultatRecherche(rep, pseudo) {
    const apres = rep.index_desactive === false;
    const cible = apres ? el.valeurApres : el.valeurAvant;
    cible.textContent = formatDuree(rep.duree_ms);
    (apres ? el.chronoApres : el.chronoAvant).classList.add("actif");
    const trouve = rep.trouve ? `« ${pseudo} » trouvé.` : `« ${pseudo} » : aucun joueur trouvé.`;
    journal(`Recherche ${apres ? "AVEC" : "SANS"} index : ${formatDuree(rep.duree_ms)}.`);

    if (apres) {
      etat.apresMs = rep.duree_ms;
      el.btnRelancer.hidden = false;
      el.btnOk.hidden = false;
      el.rechercheMessage.textContent = `${trouve} Quelle différence ! Clique sur OK pour valider ton achat.`;
      if (etat.avantMs !== null) {
        const facteur = Math.max(1, Math.round(etat.avantMs / Math.max(1, rep.duree_ms)));
        el.rapport.textContent = `${facteur.toLocaleString("fr-FR")} fois plus rapide !`;
        el.rapport.hidden = false;
      }
    } else {
      etat.avantMs = rep.duree_ms;
      el.rechercheMessage.textContent =
        `${trouve} C'était long… Demande à l'animateur d'accélérer la recherche !`;
    }
  }

  /** Remet la recherche « avec index » à disposition dès que l'index est actif. */
  function majBoutonsRecherche() {
    if (etat.ecran !== "recherche") return;
    if (etat.indexActif && etat.apresMs === null) {
      el.btnRelancer.hidden = false;
      el.rechercheMessage.textContent =
        "C'est prêt ! Relance la même recherche pour voir la différence.";
    }
  }

  async function validerAchat() {
    if (etat.enCours) return;
    etat.enCours = true;
    majBoutons();
    el.btnOk.textContent = "Validation…";
    try {
      // Écrit une opération dans la base puis déclenche l'incident, sans rien montrer.
      const rep = await api().valider_achat();
      if (!rep.success) {
        afficherErreur(rep.error);
        return;
      }
      masquerErreur();
      journal("Achat validé — la base est tombée en panne.");
      montrerPanne(true);
    } finally {
      el.btnOk.textContent = "OK";
      etat.enCours = false;
      majBoutons();
    }
  }

  // ------------------------------------------------------------------ //
  // Écran 4 : panne, puis restauration (animateur)
  // ------------------------------------------------------------------ //
  function montrerPanne(avecEffet) {
    el.panneChrono.hidden = true;
    el.panneMessage.textContent = "Appelle l'animateur : il va tout réparer.";
    afficherEcran("panne");
    if (avecEffet) {
      el.overlay.classList.remove("actif");
      void el.overlay.offsetWidth; // relance l'animation
      el.overlay.classList.add("actif");
      document.body.classList.remove("tremble");
      void document.body.offsetWidth;
      document.body.classList.add("tremble");
    }
  }

  async function restaurer() {
    if (etat.enCours || etat.ecran !== "panne") return;
    etat.enCours = true;
    majBoutons();
    el.panneMessage.textContent = "Réparation en cours… SQL Server remet les sauvegardes dans l'ordre.";
    demarrerChrono(el.panneChrono);
    try {
      const rep = await api().restaurer();
      arreterChrono();
      if (!rep.success) {
        el.panneMessage.textContent = "La réparation a rencontré un problème.";
        afficherErreur(rep.error);
        return;
      }
      masquerErreur();
      journal(`Restauration terminée : ${formatDuree(rep.duree_ms)}.`);
      montrerReveal(rep);
    } catch (e) {
      arreterChrono();
      afficherErreur(String(e));
    } finally {
      arreterChrono();
      etat.enCours = false;
      majBoutons();
    }
  }

  // ------------------------------------------------------------------ //
  // Écran 5 : reveal
  // ------------------------------------------------------------------ //
  const LIBELLES_ETAPES = {
    FULL: "1. Sauvegarde complète (FULL)",
    DIFF: "2. Sauvegarde différentielle (DIFF)",
    LOG: "3. Journal de transactions (LOG)",
  };

  function montrerReveal(rep) {
    const dernier = rep.reveal[0];
    const lignes = dernier
      ? [
          ["Jeu offert", dernier.titre],
          ["Pseudo de l'ami", dernier.ami],
          ["Offert par", dernier.offertPar || "—"],
          ["Date de l'achat", dernier.dateAchat],
        ]
      : [["Dernier achat", "introuvable (la base est vide ?)"]];
    el.revealAchat.replaceChildren(
      ...lignes.map(([nom, valeur]) => {
        const l = creer("div", "reveal-ligne");
        l.append(creer("span", "", nom), creer("span", "", String(valeur)));
        return l;
      })
    );
    const items = rep.etapes.map((e) => {
      const li = creer("li");
      li.append(creer("span", "", LIBELLES_ETAPES[e.nom] || e.nom), creer("span", "", formatDuree(e.duree_ms)));
      return li;
    });
    const total = creer("li");
    total.append(creer("span", "", "Total"), creer("span", "", formatDuree(rep.duree_ms)));
    el.revealDurees.replaceChildren(...items, total);
    afficherEcran("reveal");
  }

  // ------------------------------------------------------------------ //
  // Animateur : index et reset
  // ------------------------------------------------------------------ //
  async function activerIndex() {
    if (etat.enCours || etat.ecran !== "recherche") return;
    etat.enCours = true;
    el.btnIndex.textContent = "Activation…";
    el.rechercheMessage.textContent = "L'animateur prépare l'index… un peu de patience !";
    majBoutons();
    try {
      const rep = await api().activer_index();
      if (!rep.success) {
        afficherErreur(rep.error);
        return;
      }
      masquerErreur();
      etat.indexActif = true;
      journal(`Index activé : ${formatDuree(rep.duree_ms)} (sauvegarde DIFF lancée en arrière-plan).`);
      majBoutonsRecherche();
    } finally {
      el.btnIndex.textContent = "Activer l'index";
      etat.enCours = false;
      majBoutons();
      majStatutAnimateur();
    }
  }

  function demanderReset() {
    if (etat.enCours) return;
    if (!etat.confirmationReset) {
      el.btnReset.textContent = "Confirmer le reset ?";
      etat.confirmationReset = setTimeout(annulerConfirmationReset, 3000);
      return;
    }
    annulerConfirmationReset();
    reset();
  }

  function annulerConfirmationReset() {
    clearTimeout(etat.confirmationReset);
    etat.confirmationReset = null;
    el.btnReset.textContent = "Reset";
  }

  async function reset() {
    etat.enCours = true;
    el.attenteTitre.textContent = "Préparation de la démo…";
    el.attenteMessage.textContent = "On remet tout en place pour le prochain visiteur. Cela prend 1 à 2 minutes.";
    el.overlay.classList.remove("actif");
    document.body.classList.remove("tremble");
    demarrerChrono(el.attenteChrono);
    afficherEcran("attente");
    try {
      const rep = await api().reset();
      arreterChrono();
      if (!rep.success) {
        el.attenteTitre.textContent = "Réinitialisation impossible";
        el.attenteMessage.textContent = "Préviens l'animateur.";
        afficherErreur(rep.error);
        return;
      }
      masquerErreur();
      const controle = [];
      if (rep.index_desactive !== undefined) controle.push(`idx_pseudo désactivé : ${rep.index_desactive ? "oui" : "NON"}`);
      if (rep.nb_achats !== undefined) controle.push(`achats : ${rep.nb_achats}`);
      journal(`Reset terminé : ${formatDuree(rep.duree_ms)}${controle.length ? " (" + controle.join(", ") + ")" : ""}.`);
      etat.jeu = null;
      etat.ami = "";
      etat.visiteur = "";
      etat.indexActif = false;
      el.champVisiteur.value = "";
      el.champAmi.value = "";
      el.champJeu.value = "";
      nouveauVisiteur();
    } catch (e) {
      arreterChrono();
      afficherErreur(String(e));
    } finally {
      arreterChrono();
      etat.enCours = false;
      majBoutons();
    }
  }

  function nouveauVisiteur() {
    afficherEcran("catalogue");
    chargerJeux();
    el.champJeu.focus();
  }

  // ------------------------------------------------------------------ //
  // Statut / polling
  // ------------------------------------------------------------------ //
  async function rafraichirStatut(silencieux) {
    try {
      const rep = await api().get_status();
      if (!rep.success) {
        majPointStatut("erreur", "Erreur");
        if (!silencieux) afficherErreur(rep.error);
        return rep;
      }
      etat.operation = rep.operation;
      etat.sauvegarde = rep.sauvegarde;
      if (rep.occupe) {
        majPointStatut("attente", "Opération en cours");
      } else if (rep.etat === "en_ligne") {
        masquerErreur();
        majPointStatut("ok", "Connecté");
        const actif = rep.index_desactive === false;
        if (actif !== etat.indexActif && !etat.enCours) {
          etat.indexActif = actif;
          majBoutonsRecherche();
        }
      } else if (rep.etat === "restoring") {
        majPointStatut("attente", "Restauration en cours");
      } else {
        majPointStatut("erreur", "Base injoignable");
        // Base détachée (panne) : on l'affiche même si l'appli a été relancée entre-temps.
        if (!etat.enCours && etat.ecran !== "panne" && etat.ecran !== "reveal") montrerPanne(false);
      }
      majBoutons();
      majStatutAnimateur();
      return rep;
    } catch (e) {
      majPointStatut("erreur", "Erreur");
      if (!silencieux) afficherErreur("Erreur de communication avec l'application : " + e);
      return { success: false, error: String(e) };
    }
  }

  // ------------------------------------------------------------------ //
  // Initialisation
  // ------------------------------------------------------------------ //
  function attacherEvenements() {
    let minuteur;
    el.champJeu.addEventListener("input", () => {
      clearTimeout(minuteur);
      minuteur = setTimeout(chargerJeux, DELAI_RECHERCHE_JEU_MS);
    });
    el.btnRetourCatalogue.addEventListener("click", () => afficherEcran("catalogue"));
    el.btnOffrir.addEventListener("click", offrirJeu);
    [el.champVisiteur, el.champAmi].forEach((c) =>
      c.addEventListener("keydown", (e) => e.key === "Enter" && offrirJeu())
    );
    el.btnRechercher.addEventListener("click", rechercherAmi);
    el.btnRelancer.addEventListener("click", rechercherAmi);
    el.champRecherche.addEventListener("keydown", (e) => e.key === "Enter" && rechercherAmi());
    el.btnOk.addEventListener("click", validerAchat);

    el.btnIndex.addEventListener("click", activerIndex);
    el.btnRestaurer.addEventListener("click", restaurer);
    el.btnReset.addEventListener("click", demanderReset);
    el.btnFermerAnim.addEventListener("click", basculerPanneau);

    // Accès animateur : Ctrl+Maj+L, ou 5 clics rapides sur le logo (écran tactile).
    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        basculerPanneau();
      }
    });
    let clics = [];
    el.logo.addEventListener("click", () => {
      const maintenant = Date.now();
      clics = clics.filter((t) => maintenant - t < 2500).concat(maintenant);
      if (clics.length >= CLICS_LOGO_ANIMATEUR) {
        clics = [];
        basculerPanneau();
      }
    });

    el.btnReessayer.addEventListener("click", async () => {
      const rep = await api().reessayer_connexion();
      if (rep.success) {
        masquerErreur();
        majPointStatut("ok", "Connecté");
        if (etat.ecran === "attente") nouveauVisiteur();
      } else {
        afficherErreur(rep.error);
      }
    });
  }

  async function initialiser() {
    attacherEvenements();
    const rep = await rafraichirStatut(false);
    if (rep.success && etat.ecran === "attente") nouveauVisiteur();
    etat.pollHandle = setInterval(() => rafraichirStatut(true), INTERVALLE_POLLING_MS);
  }

  window.addEventListener("pywebviewready", initialiser);
})();
