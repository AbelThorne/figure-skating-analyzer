# Simulateur de Programme — Design Spec

## Vue d'ensemble

Un outil standalone de simulation de programme de patinage artistique, accessible aux coaches et admins via un nouvel item "Programme" dans la sidebar. Le coach peut construire un programme en ajoutant des éléments techniques, appliquer des modificateurs ISU, voir les base values et plages GOE en temps réel, et obtenir une suggestion automatique de la catégorie à laquelle le programme correspond.

L'outil est **éphémère** (rien n'est persisté en base) et **indépendant** du module Entraînement existant.

### Principes fondamentaux

1. **Le programme dicte la catégorie** — aucune restriction basée sur la catégorie. Le coach construit librement, et l'app suggère les catégories compatibles.
2. **Seules les règles universelles ISU bloquent** : max 3 sauts dans une combo, un combo = saut+saut (pas saut+pirouette), Euler uniquement en position 2 d'une combo de 3, etc.
3. **Calcul full client-side** — les données SOV et les règles sont chargées une fois via l'API, tout le calcul se fait dans React.
4. **Validation structurelle (niveau 1)** — nombre d'éléments, niveaux max autorisés, répétitions. Pas de validation fine (nombre de tours dans une pirouette, etc.).
5. **Coaches et admins uniquement** — la page n'apparaît que pour ces rôles.

---

## Backend

### Fichiers de données

Deux fichiers JSON versionnés dans `backend/app/data/` :

#### `sov_2025_2026.json`

Contient toutes les entrées du SOV ISU Communication 2707 (saison 2025-2026). Chaque élément a son code, sa base value, et ses valeurs GOE de -5 à +5. Les variantes avec markers (`<`, `<<`, `e`, et combinaisons comme `e<`) sont des entrées distinctes, exactement comme dans le PDF SOV.

```json
{
  "season": "2025-2026",
  "elements": {
    "1T": {
      "category": "single",
      "type": "jump",
      "base_value": 0.40,
      "goe": [-0.20, -0.16, -0.12, -0.08, -0.04, 0.04, 0.08, 0.12, 0.16, 0.20]
    },
    "3Lz": {
      "category": "single",
      "type": "jump",
      "base_value": 5.90,
      "goe": [-2.95, -2.36, -1.77, -1.18, -0.59, 0.59, 1.18, 1.77, 2.36, 2.95]
    },
    "3Lze": {
      "category": "single",
      "type": "jump",
      "base_value": 4.72,
      "goe": [-2.36, -1.89, -1.42, -0.94, -0.47, 0.47, 0.94, 1.42, 1.89, 2.36]
    },
    "3Lz<": {
      "category": "single",
      "type": "jump",
      "base_value": 4.72,
      "goe": [-2.36, -1.89, -1.42, -0.94, -0.47, 0.47, 0.94, 1.42, 1.89, 2.36]
    },
    "FSSp4": {
      "category": "single",
      "type": "spin",
      "base_value": 3.00,
      "goe": [-1.50, -1.20, -0.90, -0.60, -0.30, 0.30, 0.60, 0.90, 1.20, 1.50]
    },
    "StSq3": {
      "category": "single",
      "type": "step",
      "base_value": 3.30,
      "goe": [-1.65, -1.32, -0.99, -0.66, -0.33, 0.33, 0.66, 0.99, 1.32, 1.65]
    },
    "ChSq1": {
      "category": "single",
      "type": "choreo",
      "base_value": 3.00,
      "goe": [-2.50, -2.00, -1.50, -1.00, -0.50, 0.50, 1.00, 1.50, 2.00, 2.50]
    },
    "3LiB": {
      "category": "pair",
      "type": "lift",
      "base_value": 3.50,
      "goe": [-1.75, -1.40, -1.05, -0.70, -0.35, 0.35, 0.70, 1.05, 1.40, 1.75]
    }
  }
}
```

Notes :
- Le tableau GOE contient 10 valeurs dans l'ordre : [-5, -4, -3, -2, -1, +1, +2, +3, +4, +5]
- `category` : `"single"` ou `"pair"` — permet le filtrage par le toggle couples
- `type` : `"jump"`, `"spin"`, `"step"`, `"choreo"`, `"lift"`, `"throw"`, `"twist"`, `"death_spiral"`, `"pair_spin"`, `"pivot"` — permet le groupement dans le sélecteur
- Les entrées avec suffixes markers (`e`, `<`, `<<`, combinaisons) sont des lignes distinctes
- Les éléments dont le code contient `V` en suffixe (pirouettes réduites) sont aussi des lignes distinctes

#### `program_rules_2025_2026.json`

Contient les règles structurelles par catégorie pour la suggestion et la validation. Chaque catégorie décrit les contraintes pour chaque segment (PC et/ou PL).

```json
{
  "season": "2025-2026",
  "categories": {
    "ISU Senior": {
      "label": "ISU Senior",
      "segments": {
        "PC": {
          "label": "Programme Court",
          "duration": "2:40 +/-10s",
          "total_elements": 7,
          "max_jump_elements": 3,
          "max_spins": 3,
          "max_steps": 1,
          "max_choreo": 0,
          "max_jump_level": null,
          "max_spin_level": null,
          "triples_allowed": true,
          "quads_allowed_m": true,
          "quads_allowed_f": false,
          "axel_required": true,
          "combo_allowed": true,
          "max_combo_jumps": 2,
          "component_factor_m": 1.67,
          "component_factor_f": 1.33,
          "bonus_second_half": false
        },
        "PL": {
          "label": "Programme Libre",
          "duration_m": "4:00 +/-10s",
          "duration_f": "4:00 +/-10s",
          "max_jump_elements": 7,
          "max_spins": 3,
          "max_steps": 1,
          "max_choreo": 1,
          "max_jump_level": null,
          "max_spin_level": null,
          "triples_allowed": true,
          "quads_allowed": true,
          "max_combos": 3,
          "max_sequences": 1,
          "max_combo_with_3_jumps": 1,
          "repeat_triple_max": 2,
          "second_solo_repeat_factor": 0.70,
          "component_factor_m": 3.33,
          "component_factor_f": 2.67,
          "bonus_second_half": true
        }
      }
    },
    "ISU Junior": { "..." : "..." },
    "ISU Advanced Novice": {
      "segments": {
        "PC": {
          "total_elements": 6,
          "max_jump_level": 3,
          "bonus_pc": { "2A": 1, "triple": 1 }
        },
        "PL": {
          "max_jump_elements": 6,
          "max_jump_level": 3,
          "quads_allowed": false,
          "bonus_pl": { "2A": 1, "triple": 1, "second_different_triple": 1 }
        }
      }
    },
    "ISU Intermediate Novice": {
      "segments": {
        "PL": {
          "max_jump_elements": 5,
          "max_jump_level": 2,
          "triples_allowed": false,
          "quads_allowed": false
        }
      }
    },
    "ISU Basic Novice": {
      "segments": {
        "PL": {
          "max_jump_elements": 5,
          "max_jump_level": 2,
          "triples_allowed": false,
          "quads_allowed": false
        }
      }
    },
    "Régional 3 - Niveau C": {
      "segments": {
        "PL": {
          "duration": "2:00 +/-10s",
          "max_jump_elements": 2,
          "allowed_jumps": ["1S", "1T", "1Lo"],
          "combo_allowed": false,
          "max_spins": 1,
          "allowed_spin_types": ["USp"],
          "max_steps": 1,
          "max_spin_level": 1,
          "component_factor": 1.67
        }
      }
    },
    "Régional 3 - Niveau B": {
      "segments": {
        "PL": {
          "duration": "2:30 +/-10s",
          "max_jump_elements": 2,
          "allowed_jumps": ["1S", "1T", "1Lo"],
          "combo_allowed": false,
          "max_spins": 2,
          "allowed_spin_types": ["USp", "LSp", "SSp", "CSp"],
          "max_steps": 1,
          "max_spin_level": 1,
          "component_factor": 1.67
        }
      }
    },
    "Régional 3 - Niveau A": {
      "segments": {
        "PL": {
          "duration": "2:30 +/-10s",
          "max_jump_elements": 4,
          "allowed_jumps": ["1S", "1T", "1Lo", "1F", "1Lz"],
          "max_combos": 2,
          "max_spins": 2,
          "allowed_spin_types": ["USp", "LSp", "SSp", "CSp", "CUSp", "CLSp", "CSSp", "CCSp", "CoSp"],
          "max_steps": 1,
          "max_spin_level": 1,
          "component_factor": 1.67
        }
      }
    },
    "Adulte Master Élite": { "..." : "..." },
    "Adulte Or": { "..." : "..." },
    "Adulte Argent": { "..." : "..." },
    "Adulte Bronze": { "..." : "..." },
    "Occitanie Exhibition": {
      "segments": {
        "PL": {
          "duration": "2:30 +/-10s",
          "max_jump_elements": 1,
          "max_spins": 2,
          "max_steps": 1,
          "max_spin_level": 1,
          "max_step_level": 1,
          "component_factor": 1.0,
          "notes": "Accessoire autorisé. Novice, Junior/Senior (- de 25 ans)"
        }
      }
    },
    "Occitanie Duo": {
      "segments": {
        "PL": {
          "duration": "2:30 +/-10s",
          "max_jump_elements": 2,
          "max_spins": 2,
          "max_steps": 1,
          "max_spin_level": 1,
          "max_step_level": 1,
          "has_duo_element": true,
          "component_factor": 1.0
        }
      }
    }
  }
}
```

### Endpoints

Nouveau fichier `backend/app/routes/program_builder.py` :

- `GET /api/sov` — sert `sov_2025_2026.json`. Guard : `require_coach_or_admin`.
- `GET /api/program-rules` — sert `program_rules_2025_2026.json`. Guard : `require_coach_or_admin`.

Pas de nouveau modèle en base. Pas de logique métier côté serveur.

---

## Frontend

### Navigation

Nouvel item dans la sidebar (`App.tsx`) :
- Label : **"Programme"**
- Icône : `sports_score` (Material Symbols)
- Route : `/programme`
- Visible pour : `coach`, `admin`
- Position : après "Club", avant "Entraînement"

### Page : `ProgramBuilderPage.tsx`

Layout responsive en deux colonnes (`flex` avec `flex-col lg:flex-row`). Sur écrans < `lg`, la colonne droite passe en dessous.

#### Colonne gauche (principale)

**1. Barre de chargement depuis une compétition**

Permet de pré-remplir le programme avec les éléments réels d'un patineur dans une compétition donnée.

- **Sélecteur patineur** : dropdown avec recherche. Par défaut, affiche uniquement les patineurs du club. Un toggle "Tous les patineurs" étend à tous.
- **Sélecteur compétition** : dropdown dépendant. N'affiche que les compétitions où le patineur sélectionné a participé, triées par date décroissante.
- **Sélecteur segment** : si le patineur a participé à PC et PL, permet de choisir lequel charger.
- **Bouton "Charger"** : remplace le programme en cours par les éléments du score sélectionné. Les markers du score original sont appliqués.

APIs utilisées : `api.skaters.list()`, `api.skaters.scores(skaterId)` (existantes).

**2. Sélecteur d'éléments**

Dropdown avec recherche, groupé par type :
- **Sauts** : tous les sauts du SOV (1T, 1S, 1Lo, 1Eu, 1F, 1Lz, 1A, 2T, ..., 5Lz). Codes de base uniquement (pas les variantes avec markers).
- **Pirouettes** : USp, LSp, CSp, SSp, CUSp, CLSp, CCSp, CSSp, FUSp, FLSp, FCSp, FSSp, FCUSp, FCLSp, FCCSp, FCSSp, CoSp, CCoSp, FCoSp, FCCoSp + niveaux (B, 1-4, V)
- **Pas** : StSq (B, 1-4)
- **Chorégraphique** : ChSq1
- **Éléments couples** (visible seulement si le toggle "Couples" est activé) : Lifts (1Li-5RLi, niveaux B-4), Throws (1TTh-4LzTh), Twist Lifts (1Tw-4Tw), Death Spirals (BoDsB-FoDs4), Pair Spins (PSpB-PSp4, PCoSpB-PCoSp4), Pivot (PiF1)

Bouton **"+ Ajouter"** pour ajouter l'élément sélectionné au programme.

**3. Toggle "Éléments couples"**

Décoché par défaut. Quand activé, ajoute les groupes d'éléments propres aux couples dans le sélecteur. Position : à côté du titre de page ou du sélecteur d'éléments.

**4. Tableau du programme**

Table avec les colonnes :

| Colonne | Description |
|---------|-------------|
| **#** | Position dans le programme (1, 2, 3...) |
| **Élément** | Code de l'élément avec markers en superscript colorés (style `ScoreCardModal`). Pour les combos : `3Lz<+2Tq` avec markers individuels par saut. |
| **Mod.** | Dropdown(s) de modificateurs. Pour un élément simple : 1 dropdown. Pour une combo : 1 dropdown par saut dans la combo. |
| **BV** | Base value après application des markers et multiplicateurs. `font-mono`. |
| **Min** | Score total à GOE -5. `font-mono`, couleur `text-[#ba1a1a]`. Hover (délai 300ms) : tooltip avec les valeurs de -5 à -1. |
| **Max** | Score total à GOE +5. `font-mono`, couleur `text-primary`. Hover (délai 300ms) : tooltip avec les valeurs de +1 à +5. |
| **Actions** | Bouton "+" (ajouter un saut à la combo, visible pour les sauts uniquement, max 3 sauts), bouton "×" (supprimer l'élément) |

**Édition inline d'un élément** :
- Cliquer sur le nom d'un élément dans la colonne "Élément" ouvre un **popover** (mini-modal ancré à l'élément) contenant le même sélecteur d'éléments que le picker principal (dropdown avec recherche, groupé par type).
- Sélectionner un nouvel élément **remplace** l'élément cliqué.
- Si l'élément était une combinaison de sauts (ex: `3Lz+2T`), il est remplacé par le nouvel élément **simple**. La combinaison est défaite — le coach doit ensuite utiliser le bouton "+" pour reconstruire une combo s'il le souhaite.
- Les modificateurs de l'élément remplacé sont réinitialisés.
- Cliquer en dehors du popover ou appuyer sur Échap le ferme sans modification.

**Ligne de total** en bas du tableau :
- BV total (somme des BV)
- Min total (somme des Min)
- Max total (somme des Max)

**Comportement du bouton "+" (combinaison)** :
- Visible à côté de chaque saut individuel
- Cliquer ouvre un sélecteur filtré (sauts uniquement)
- L'élément dans le tableau devient `3Lz+2T`
- Un second "+" apparaît pour ajouter un 3e saut (max 3)
- Règles universelles bloquantes :
  - Max 3 sauts par combinaison
  - Chaque élément dans la combo doit être un saut
  - L'Euler (`1Eu`) n'est autorisé qu'en position 2 d'une combo de 3 sauts
- Le 2e/3e saut peut être le même type que le 1er (autorisé par les règles ISU)

### Modificateurs disponibles par type

**Sauts** :
| Marker | Label | Effet sur BV | Compatibilité |
|--------|-------|-------------|--------------|
| `q` | Quart court | Non (GOE uniquement) | Exclusif avec `<`, `<<` |
| `<` | Sous-rotation | Oui (entrée SOV dédiée) | Exclusif avec `q`, `<<`. Combinable avec `e` |
| `<<` | Déclassé | Oui (SOV de la rotation -1) | Exclusif avec `q`, `<` |
| `e` | Carre incorrecte | Oui (entrée SOV dédiée) | Flip/Lutz uniquement. Exclusif avec `!`. Combinable avec `<` |
| `!` | Carre incertaine | Non (GOE uniquement) | Flip/Lutz uniquement. Exclusif avec `e` |
| `*` | Annulé | Oui (BV = 0) | Exclusif avec tout |
| `x` | Bonus 2e moitié | Oui (BV × 1.10) | Combinable avec tout sauf `*` |
| `+REP` | Répétition | Oui (BV × 0.70) | Combinable avec tout sauf `*`. Note : dans le système ISU, le +REP est auto-calculé. Ici le coach l'applique manuellement pour simuler l'effet. |

**Pirouettes** :
| Marker | Label | Effet sur BV |
|--------|-------|-------------|
| `V` | Valeur réduite | Oui (entrée SOV dédiée, ex: `CCoSp3V`) |
| `*` | Annulé | Oui (BV = 0) |

**Pas / Chorégraphique** :
| Marker | Label | Effet sur BV |
|--------|-------|-------------|
| `*` | Annulé | Oui (BV = 0) |

### Logique de calcul de la BV

Pour chaque élément du programme :

1. **Composer le code SOV** : prendre le code de base et appliquer les transformations markers.
   - Markers avec entrée SOV dédiée (`<`, `e`, `e<`) : ajouter le suffixe au code. Ex: `3Lz` + `[e, <]` → chercher `3Lze<` dans le SOV
   - Markers sans effet sur BV (`q`, `!`) : code inchangé. Ex: `3F` + `[q]` → chercher `3F` dans le SOV
   - Downgrade (`<<`) : **pas d'entrée SOV dédiée** — transformer le code vers la rotation inférieure. Ex: `3Lz` + `[<<]` → chercher `2Lz` dans le SOV. `2A` + `[<<]` → chercher `1A`
   - Downgrade + edge (`<<`, `e`) : transformer puis suffixer. Ex: `3Lz` + `[<<, e]` → chercher `2Lze`

2. **Chercher la BV** dans le SOV avec le code composé.

3. **Appliquer les multiplicateurs** :
   - Si `*` : BV = 0
   - Si `x` : BV × 1.10
   - Si `+REP` : BV × 0.70
   - `x` et `+REP` se cumulent si les deux sont présents : BV × 1.10 × 0.70

4. **Pour les combos** : la BV du combo = somme des BV individuelles de chaque saut (après markers), puis application des multiplicateurs globaux (`x`, `+REP`) sur la somme.

5. **Min/Max** : BV + GOE[-5] pour le min, BV + GOE[+5] pour le max. Les GOE sont ceux de l'entrée SOV après markers (pas du code de base).

### Affichage des markers (style ScoreCardModal)

Réutiliser exactement le style existant de `ScoreCardModal.tsx` :
- Markers en superscript : `font-mono text-[9px] font-bold align-super ml-[1px]`
- Couleurs :
  - `text-[#ba1a1a]` : `*`, `<<`
  - `text-[#e65100]` : `<`, `q`, `e`
  - `text-[#b45309]` : `!`
  - `text-primary` (#2e6385) : `x`
- Pas de fond coloré sur les lignes
- Pour les combos, les markers sont positionnels (un par saut dans la combo)
- Réutiliser le composant `ElementNameCell` existant ou un dérivé

#### Colonne droite (panneau latéral)

**1. Catégorie détectée**

Affiche la catégorie compatible la plus proche :
- Badge visuel avec le nom de la catégorie (ex: "ISU Basic Novice — PL")
- Si plusieurs catégories sont compatibles, les lister toutes avec la plus restrictive en premier
- Si aucune catégorie n'est pleinement compatible, afficher la plus proche avec le nombre de violations

**2. Validation**

Checklist en temps réel comparant le programme contre la catégorie détectée :
- ✓ Vert : règle satisfaite (ex: "Sauts : 3/5 max")
- ⚠ Orange : manque quelque chose (ex: "Pas de StSq (0/1 requis)")
- ✗ Rouge : violation (ex: "Triples présents — interdit pour cette catégorie")

**3. Résumé**

Compteurs rapides :
- Nombre de sauts / pirouettes / pas / chorégraphiques
- Nombre de combos / séquences
- Nombre d'éléments en 2e moitié (avec `x`)

### Moteur de suggestion de catégorie

Le moteur client-side compare le programme contre les règles de chaque catégorie :

1. Pour chaque catégorie dans `program_rules`, vérifier toutes les contraintes
2. Comptabiliser le nombre de violations par catégorie
3. Trier par nombre de violations croissant
4. Afficher les catégories avec 0 violations comme "compatibles"
5. Mettre en avant la catégorie compatible la plus restrictive (celle avec le plus de contraintes)
6. Si aucune n'est compatible, afficher la catégorie avec le moins de violations

Contraintes vérifiées :
- Nombre total d'éléments sauts (≤ max)
- Nombre de pirouettes (≤ max)
- Nombre de pas (≤ max)
- Nombre de séquences chorégraphiques (≤ max)
- Niveau max des sauts (rotation)
- Niveau max des pirouettes
- Triples/quadruples autorisés ou non
- Sauts autorisés (pour Régional 3)
- Types de pirouettes autorisés (pour Régional 3)
- Nombre de combos (≤ max)
- Présence d'un Axel (si requis)

### Séquences de sauts

En plus des combinaisons, le PL autorise les **séquences de sauts** (distinctes des combos) :
- 2 ou 3 sauts de n'importe quel nombre de tours
- Le 2e et/ou le 3e saut doit être un saut de type Axel
- Passage direct de la courbe de réception du 1er/2e saut vers la courbe de départ de l'Axel
- Les sauts dans une séquence reçoivent leur valeur complète

Pour saisir une séquence, le coach utilise le même bouton "+" que pour les combos. Le système détecte automatiquement si c'est une combo ou une séquence en fonction de la présence d'un Axel en position 2 ou 3, et affiche `+SEQ` le cas échéant. Alternativement, un toggle "Séquence" peut être proposé lors de l'ajout du 2e saut.

---

## Structure des fichiers

### Backend
```
backend/app/
  data/
    sov_2025_2026.json          # Données SOV complètes
    program_rules_2025_2026.json # Règles par catégorie
  routes/
    program_builder.py           # GET /api/sov, GET /api/program-rules
```

### Frontend
```
frontend/src/
  pages/
    ProgramBuilderPage.tsx       # Page principale
  components/
    program-builder/
      ProgramTable.tsx           # Tableau du programme
      ElementPicker.tsx          # Sélecteur d'éléments avec recherche
      CompetitionLoader.tsx      # Barre de chargement depuis une compétition
      ModifierDropdown.tsx       # Dropdown de modificateurs par élément
      CategoryPanel.tsx          # Panneau catégorie + validation + résumé
      GoeTooltip.tsx             # Tooltip hover pour valeurs GOE détaillées
  hooks/
    useProgramBuilder.ts         # État et logique du programme (éléments, calculs, validation)
    useSovData.ts                # Chargement et cache des données SOV
    useProgramRules.ts           # Chargement et cache des règles
  utils/
    sov-calculator.ts            # Calcul BV, GOE, composition de codes markers
    program-validator.ts         # Validation du programme contre les règles de catégorie
    category-matcher.ts          # Suggestion de catégorie compatible
```

---

## API Client

Ajouts dans `frontend/src/api/client.ts` :

```typescript
// Types
export interface SovElement {
  category: "single" | "pair";
  type: "jump" | "spin" | "step" | "choreo" | "lift" | "throw" | "twist" | "death_spiral" | "pair_spin" | "pivot";
  base_value: number;
  goe: number[]; // 10 values: [-5, -4, -3, -2, -1, +1, +2, +3, +4, +5]
}

export interface SovData {
  season: string;
  elements: Record<string, SovElement>;
}

export interface ProgramRuleSegment {
  label?: string;
  duration?: string;
  total_elements?: number;
  max_jump_elements?: number;
  max_spins?: number;
  max_steps?: number;
  max_choreo?: number;
  max_jump_level?: number | null;
  max_spin_level?: number | null;
  triples_allowed?: boolean;
  quads_allowed?: boolean;
  combo_allowed?: boolean;
  max_combos?: number;
  max_combo_jumps?: number;
  allowed_jumps?: string[];
  allowed_spin_types?: string[];
  bonus_second_half?: boolean;
  component_factor?: number;
  component_factor_m?: number;
  component_factor_f?: number;
}

export interface ProgramRuleCategory {
  label: string;
  segments: Record<string, ProgramRuleSegment>;
}

export interface ProgramRulesData {
  season: string;
  categories: Record<string, ProgramRuleCategory>;
}

// API calls
api.programBuilder = {
  sov(): Promise<SovData>,
  rules(): Promise<ProgramRulesData>,
};
```

---

## Documents de référence

Les données et règles de cette spec sont extraites de :
- **ISU Communication 2707** — Scale of Values Singles & Pair Skating 2025-2026
- **CSNPA Book 2025/2026** — Règlement national du Patinage Artistique (V 10 décembre 2025)
- **ISU TP Handbook Pair Skating 2025-2026** — Technical Panel Handbook (25 July 2025)
- **Règlement PA Occitanie 2025-2026** — Challenge d'Occitanie Saison 2025-2026
