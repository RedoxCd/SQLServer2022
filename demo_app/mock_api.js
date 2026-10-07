  (() => {
    // Durées simulées (ms) : à ajuster pour répéter le discours d'animateur.
    const DUREE = { rechercheLente: 6000, rebuild: 5000, backupDiff: 7000, incident: 1500,
                    full: 3200, diff: 900, log: 400, reset: 8000 };
    const JEUX = __JEUX__;
    const SQL = __SQL__;
    const attendre = (ms) => new Promise((r) => setTimeout(r, ms));
    const alea = (a, b) => Math.round(a + Math.random() * (b - a));

    let s;
    function initEtat() {
      s = { db: "en_ligne", indexActif: false, op: null, achats: [], joueurs: new Set(),
            backup: { etat: "inactif", duree_ms: null, erreur: null } };
    }
    initEtat();

    async function operation(nom, ms, fn) {
      s.op = nom;
      try { await attendre(ms); return fn ? fn() : undefined; } finally { s.op = null; }
    }

    window.pywebview = { api: {
      async get_status() {
        const base = { success: true, operation: s.op, sauvegarde: { ...s.backup }, index_active: s.indexActif };
        if (s.op) return { ...base, occupe: true, etat: null };
        return { ...base, occupe: false, etat: s.db,
                 ...(s.db === "en_ligne" ? { index_desactive: !s.indexActif } : {}) };
      },
      async get_sql(nom) {
        return nom in SQL ? { success: true, sql: SQL[nom] } : { success: false, error: "Commande inconnue : " + nom };
      },
      async reessayer_connexion() { return this.get_status(); },
      async rechercher_jeux(texte) {
        await attendre(80);
        const t = (texte || "").trim().toLowerCase();
        const jeux = JEUX.filter((j) => !t || [j.titre, j.genre, j.plateforme].some((x) => x.toLowerCase().includes(t)));
        return { success: true, jeux: jeux.slice(0, 50) };
      },
      async offrir_jeu(jeuxId, ami, visiteur) {
        await attendre(300);
        const jeu = JEUX.find((j) => j.jeux_id === jeuxId);
        ami = (ami || "").trim(); visiteur = (visiteur || "").trim();
        if (!ami || !visiteur) return { success: false, error: "Merci d'écrire un pseudo." };
        s.joueurs.add(ami.toLowerCase());
        const achat = { achats_id: s.achats.length + 1, ami, titre: jeu.titre, offertPar: visiteur,
                        dateAchat: new Date().toISOString().slice(0, 19).replace("T", " "), prix: jeu.prix };
        s.achats.push(achat);
        return { success: true, achats_id: achat.achats_id, joueur_id: 10000000 + achat.achats_id, prix_paye: jeu.prix };
      },
      async rechercher_joueur(pseudo) {
        const ms = s.indexActif ? alea(6, 18) : DUREE.rechercheLente + alea(-400, 400);
        const index_desactive = !s.indexActif;
        await attendre(ms);
        const trouve = s.joueurs.has((pseudo || "").trim().toLowerCase());
        return { success: true, trouve, duree_ms: ms, index_desactive,
                 joueurs: trouve ? [{ joueur_id: 10000001, pseudo, dateCreation: "" }] : [] };
      },
      async activer_index() {
        const debut = performance.now();
        await operation("index", DUREE.rebuild);
        s.indexActif = true;
        s.backup = { etat: "en_cours", duree_ms: null, erreur: null };
        const t0 = performance.now();
        s.backupPromesse = attendre(DUREE.backupDiff).then(() => {
          s.backup = { etat: "ok", duree_ms: Math.round(performance.now() - t0), erreur: null };
        });
        return { success: true, duree_ms: Math.round(performance.now() - debut), backup_lance: true };
      },
      async valider_achat() {
        if (!s.indexActif) return { success: false, error: "L'index n'a pas été activé : la sauvegarde différentielle manque." };
        if (s.backupPromesse) await s.backupPromesse;
        await operation("incident", DUREE.incident, () => { s.db = "absente"; });
        return { success: true, panne: true, duree_ms: DUREE.incident };
      },
      async restaurer() {
        const debut = performance.now();
        await operation("restauration", DUREE.full + DUREE.diff + DUREE.log, () => { s.db = "en_ligne"; });
        const dernier = s.achats[s.achats.length - 1];
        return { success: true, duree_ms: Math.round(performance.now() - debut),
                 etapes: [{ nom: "FULL", duree_ms: DUREE.full }, { nom: "DIFF", duree_ms: DUREE.diff }, { nom: "LOG", duree_ms: DUREE.log }],
                 reveal: dernier ? [dernier] : [] };
      },
      async reset() {
        const debut = performance.now();
        await operation("reset", DUREE.reset);
        initEtat();
        return { success: true, duree_ms: Math.round(performance.now() - debut), index_desactive: true, nb_achats: 0 };
      },
    } };

    // Étiquette « hors ligne » + déclenchement de l'initialisation de app.js
    const badge = document.createElement("div");
    badge.textContent = "MODE DÉMO HORS LIGNE — aucune base de données — panneau animateur : F9 ou Ctrl+Maj+L";
    badge.style.cssText = "position:fixed;left:0;top:0;background:#000;color:#fff;font:11px Helvetica,Arial,sans-serif;padding:4px 10px;z-index:100";
    document.body.append(badge);
    window.addEventListener("load", () => {
      window.dispatchEvent(new Event("pywebviewready"));
      // En test hors ligne, le panneau animateur est ouvert d'office (sinon on reste bloqué après la recherche lente).
      document.getElementById("panneau-animateur").hidden = false;
    });
  })();
