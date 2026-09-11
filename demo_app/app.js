(() => {
  "use strict";

  const DUREE_ANIMATION_MS = 900;
  const INTERVALLE_POLLING_MS = 4000;

  const el = {
    overlay: document.getElementById("incident-overlay"),
    banniereErreur: document.getElementById("banniere-erreur"),
    banniereErreurTexte: document.getElementById("banniere-erreur-texte"),
    btnReessayer: document.getElementById("btn-reessayer"),
    pointStatut: document.getElementById("point-statut"),
    texteStatut: document.getElementById("texte-statut"),
    compteur: document.getElementById("compteur"),
    compteurLegende: document.querySelector(".compteur-legende"),
    btnVendre: document.getElementById("btn-vendre"),
    btnIncident: document.getElementById("btn-incident"),
    btnReinitialiser: document.getElementById("btn-reinitialiser"),
  };

  const etat = {
    total: 0,
    etapeMaxTerminee: 0,
    incidentActif: false,
    enCours: false, // une action est en vol, on verrouille les boutons
    pollHandle: null,
  };

  // ------------------------------------------------------------------ //
  // Utilitaires
  // ------------------------------------------------------------------ //
  function formatNombre(n) {
    return Math.round(n).toLocaleString("fr-FR");
  }

  function animerCompteur(depuis, vers) {
    const debut = performance.now();
    function frame(maintenant) {
      const t = Math.min(1, (maintenant - debut) / DUREE_ANIMATION_MS);
      const t2 = 1 - Math.pow(1 - t, 3);
      const valeur = depuis + (vers - depuis) * t2;
      el.compteur.textContent = formatNombre(valeur);
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function majCompteur(nouveauTotal) {
    animerCompteur(etat.total, nouveauTotal);
    etat.total = nouveauTotal;
  }

  function highlightSql(sql) {
    const echap = (s) =>
      s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const motif =
      /(--[^\n]*)|(N?'[^']*')|(\[[^\]]*\])|(\b(?:USE|GO|ALTER|DATABASE|SET|SINGLE_USER|MULTI_USER|WITH|ROLLBACK|IMMEDIATE|BACKUP|LOG|RESTORE|FROM|DISK|TO|NORECOVERY|RECOVERY|REPLACE|MOVE|STOPAT|INIT|DELETE|TRUNCATE|TABLE|INSERT|INTO|VALUES|SELECT|WHERE|AND|OR|ORDER|BY|TOP)\b)/gi;
    let sortie = "";
    let dernier = 0;
    let m;
    while ((m = motif.exec(sql)) !== null) {
      sortie += echap(sql.slice(dernier, m.index));
      const [complet, commentaire, chaine, ident, motCle] = m;
      if (commentaire) sortie += `<span class="sql-comment">${echap(commentaire)}</span>`;
      else if (chaine) sortie += `<span class="sql-string">${echap(chaine)}</span>`;
      else if (ident) sortie += `<span class="sql-ident">${echap(ident)}</span>`;
      else if (motCle) sortie += `<span class="sql-keyword">${echap(motCle)}</span>`;
      dernier = m.index + complet.length;
    }
    sortie += echap(sql.slice(dernier));
    return sortie;
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

  function verrouillerActionsPrincipales(verrouille) {
    if (!etat.incidentActif) {
      el.btnVendre.disabled = verrouille;
    }
    el.btnIncident.disabled = verrouille || etat.incidentActif;
  }

  // ------------------------------------------------------------------ //
  // Étapes de restauration (UI)
  // ------------------------------------------------------------------ //
  function elementsEtape(n) {
    return {
      article: document.getElementById(`etape-${n}`),
      badge: document.querySelector(`[data-badge="${n}"]`),
      boutonRestaurer: document.querySelector(`[data-action="restaurer"][data-etape="${n}"]`),
      boutonVoirSql: document.querySelector(`.bouton-voir-sql[data-etape="${n}"]`),
      panneau: document.querySelector(`[data-panneau="${n}"]`),
      code: document.querySelector(`[data-code="${n}"]`),
      meta: document.querySelector(`[data-panneau="${n}"] .panneau-sql-meta`),
    };
  }

  function reinitialiserEtapesUI() {
    // Les 3 étapes restent verrouillées tant qu'aucun incident n'a été
    // déclenché : declencherIncident() déverrouille ensuite l'étape 1.
    for (let n = 1; n <= 3; n++) {
      const e = elementsEtape(n);
      e.article.classList.remove("terminee");
      e.article.classList.add("verrouillee");
      e.badge.textContent = "en attente";
      e.badge.className = "etape-badge";
      e.boutonRestaurer.disabled = true;
      e.boutonVoirSql.hidden = true;
      e.panneau.hidden = true;
      e.code.innerHTML = "";
      e.meta.textContent = "";
      const chevron = e.boutonVoirSql.querySelector(".chevron");
      if (chevron) chevron.classList.remove("ouvert");
    }
  }

  function deverrouillerEtape(n) {
    const e = elementsEtape(n);
    e.article.classList.remove("verrouillee");
    e.boutonRestaurer.disabled = false;
  }

  function marquerEtapeEnCours(n) {
    const e = elementsEtape(n);
    e.badge.textContent = "en cours…";
    e.badge.className = "etape-badge en-cours";
    e.boutonRestaurer.disabled = true;
  }

  function marquerEtapeTerminee(n, sql, dureeMs) {
    const e = elementsEtape(n);
    e.article.classList.remove("verrouillee");
    e.article.classList.add("terminee");
    e.badge.textContent = "terminée";
    e.badge.className = "etape-badge terminee";
    e.boutonVoirSql.hidden = false;
    e.code.innerHTML = highlightSql(sql);
    e.meta.textContent = `Temps d'exécution : ${dureeMs} ms`;

    if (n < 3) deverrouillerEtape(n + 1);
  }

  function marquerEtapeErreur(n, message) {
    const e = elementsEtape(n);
    e.badge.textContent = "échec";
    e.badge.className = "etape-badge";
    e.boutonRestaurer.disabled = false;
    afficherErreur(`Étape ${n} : ${message}`);
  }

  // ------------------------------------------------------------------ //
  // Actions principales
  // ------------------------------------------------------------------ //
  async function rafraichirStatut(silencieux) {
    try {
      const rep = await window.pywebview.api.get_status();
      if (rep.success) {
        masquerErreur();
        majPointStatut("ok", "Connecté");
        if (!etat.enCours) {
          majCompteur(rep.total);
        }
        el.compteurLegende.textContent = "billets en base";
        el.compteur.classList.remove("en-cours");
        return rep;
      }
      if (rep.restauration_en_cours) {
        majPointStatut("attente", "Restauration en cours");
        el.compteurLegende.textContent = "restauration en cours…";
        el.compteur.classList.add("en-cours");
        return rep;
      }
      majPointStatut("erreur", "Erreur");
      if (!silencieux) afficherErreur(rep.error);
      return rep;
    } catch (e) {
      majPointStatut("erreur", "Erreur");
      if (!silencieux) afficherErreur("Erreur de communication avec l'application : " + e);
      return { success: false, error: String(e) };
    }
  }

  async function vendreBillets() {
    if (etat.enCours) return;
    etat.enCours = true;
    el.btnVendre.disabled = true;
    try {
      const rep = await window.pywebview.api.vendre_billets();
      if (rep.success) {
        masquerErreur();
        majCompteur(rep.total);
      } else {
        afficherErreur(rep.error);
      }
    } finally {
      etat.enCours = false;
      el.btnVendre.disabled = etat.incidentActif;
    }
  }

  async function declencherIncident() {
    if (etat.enCours) return;
    etat.enCours = true;
    el.btnVendre.disabled = true;
    el.btnIncident.disabled = true;

    el.overlay.classList.remove("actif");
    void el.overlay.offsetWidth; // relance l'animation
    el.overlay.classList.add("actif");
    document.body.classList.remove("tremble");
    void document.body.offsetWidth;
    document.body.classList.add("tremble");

    try {
      const rep = await window.pywebview.api.declencher_incident();
      if (rep.success) {
        masquerErreur();
        etat.incidentActif = true;
        reinitialiserEtapesUI();
        deverrouillerEtape(1);
        majCompteur(rep.total);
      } else {
        afficherErreur(rep.error);
        el.btnVendre.disabled = false;
        el.btnIncident.disabled = false;
      }
    } finally {
      etat.enCours = false;
    }
  }

  async function restaurerEtape(n) {
    if (etat.enCours) return;
    etat.enCours = true;
    marquerEtapeEnCours(n);
    try {
      const rep = await window.pywebview.api.restaurer_etape(n);
      if (rep.success) {
        masquerErreur();
        marquerEtapeTerminee(n, rep.sql, rep.duree_ms);
        etat.etapeMaxTerminee = n;
        if (n === 3) {
          etat.incidentActif = false;
          el.btnVendre.disabled = false;
          el.btnIncident.disabled = false;
          const statut = await rafraichirStatut(true);
          if (statut.success) majCompteur(statut.total);
        }
      } else {
        marquerEtapeErreur(n, rep.error);
      }
    } catch (e) {
      marquerEtapeErreur(n, String(e));
    } finally {
      etat.enCours = false;
    }
  }

  async function reinitialiserDemo() {
    if (etat.enCours) return;
    etat.enCours = true;
    try {
      const rep = await window.pywebview.api.reinitialiser();
      etat.incidentActif = false;
      etat.etapeMaxTerminee = 0;
      reinitialiserEtapesUI();
      el.btnVendre.disabled = false;
      el.btnIncident.disabled = false;
      el.overlay.classList.remove("actif");
      document.body.classList.remove("tremble");
      if (rep.success) {
        masquerErreur();
        majCompteur(rep.total);
      } else if (!rep.restauration_en_cours) {
        afficherErreur(rep.error);
      }
    } finally {
      etat.enCours = false;
    }
  }

  function basculerPanneauSql(n) {
    const e = elementsEtape(n);
    const ouvert = !e.panneau.hidden;
    e.panneau.hidden = ouvert;
    const chevron = e.boutonVoirSql.querySelector(".chevron");
    if (chevron) chevron.classList.toggle("ouvert", !ouvert);
  }

  // ------------------------------------------------------------------ //
  // Initialisation
  // ------------------------------------------------------------------ //
  function attacherEvenements() {
    el.btnVendre.addEventListener("click", vendreBillets);
    el.btnIncident.addEventListener("click", declencherIncident);
    el.btnReinitialiser.addEventListener("click", reinitialiserDemo);
    el.btnReessayer.addEventListener("click", async () => {
      const rep = await window.pywebview.api.reessayer_connexion();
      if (rep.success) {
        masquerErreur();
        majPointStatut("ok", "Connecté");
        majCompteur(rep.total);
        el.btnVendre.disabled = false;
        el.btnIncident.disabled = false;
      } else {
        afficherErreur(rep.error);
      }
    });

    document.querySelectorAll('[data-action="restaurer"]').forEach((bouton) => {
      bouton.addEventListener("click", () => restaurerEtape(Number(bouton.dataset.etape)));
    });
    document.querySelectorAll(".bouton-voir-sql").forEach((bouton) => {
      bouton.addEventListener("click", () => basculerPanneauSql(Number(bouton.dataset.etape)));
    });
  }

  async function initialiser() {
    attacherEvenements();
    reinitialiserEtapesUI();

    const rep = await rafraichirStatut(false);
    if (rep.success) {
      el.compteur.textContent = formatNombre(rep.total);
      etat.total = rep.total;
      el.btnVendre.disabled = false;
      el.btnIncident.disabled = false;
    }

    etat.pollHandle = setInterval(() => rafraichirStatut(true), INTERVALLE_POLLING_MS);
  }

  window.addEventListener("pywebviewready", initialiser);
})();
