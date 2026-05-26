# GCN-HSI — Great Crested Newt Habitat Suitability Index

A semi-automated **Great Crested Newt (GCN) Habitat Suitability Index (HSI)** calculator based on **Oldham et al. (2000)**. The tool scores up to 10 candidate ponds per run and outputs a polygon layer with per-pond HSI scores and traffic-light symbology.

This tool is available in two versions:

| Version | Platform | Distribution |
|---|---|---|
| **GCN-HSI QGIS Plugin** | QGIS 3.0+ / 4.0 | QGIS Plugin Repository |
| **GCN-HSI ArcGIS Pro Tool** | ArcGIS Pro | ArcGIS Toolbox (.atbx) |

> **Important:** This tool is designed to assist qualified ecologists — it does not replace a site survey or professional ecological assessment. For any site or collection of sites subject to development, a **Full HSI Assessment** incorporating site-visit data is strongly recommended. Remote Assessment results alone are not sufficient to fully characterise a site's suitability for GCN or to inform planning decisions but can act as an important, rapid screening tool to infer site visits where appropriate.

---

## Professional Use and Development Sites

The Remote Assessment mode (SI1–SI6) provides a useful desk-based screening tool, but **should not be used as the sole basis for ecological assessment on development sites**. The following applies:

- A **Full HSI Assessment** (all 10 variables) requires a physical site visit and should be carried out by a **suitably licensed and experienced ecologist**.
- Where any pond scores **Moderate or High** suitability, further survey work — including eDNA sampling or traditional presence/absence surveys — will typically be required to determine whether GCN are present.
- HSI scoring is one component of a broader ecological assessment. It does not constitute a protected species survey and cannot confirm presence or absence of GCN.
- Research has demonstrated a positive correlation between HSI score and GCN population size — higher scoring ponds are more likely to support larger populations. However, **a low HSI score does not preclude GCN presence**. GCN have been recorded at ponds with low suitability scores, and survey work should not be ruled out on the basis of a low score alone.
- More recent research has identified **Fish Presence (SI8)** and **Waterfowl Presence (SI7)** as particularly influential variables. A **Major** impact from either can result in GCN absence even in an otherwise high-scoring pond. To reflect this, this tool applies **increased weighting to SI7 and SI8** relative to the original Oldham et al. (2000) scoring. Where fish or significant waterfowl activity are recorded during a site visit, this should be given careful weight in the overall assessment.
- For sites subject to planning applications, ecological assessments must comply with relevant national and local planning policy and should be prepared by a qualified ecologist in accordance with the **Chartered Institute of Ecology and Environmental Management (CIEEM)** guidelines.
- In England, consult Natural England's **District Level Licensing** scheme as an alternative consenting route where applicable.

---

## Requirements

- QGIS 3.0 or later (compatible with QGIS 4.0)
- Internet connection (for automated data queries)
- Input GIS data:
  - Candidate pond polygon(s)
  - Existing ponds layer (within 1km search radius)
  - UK Habitat polygons layer (within 250m buffer)

---

## Installation

1. Download the latest release ZIP from the [Releases](../../releases) page.
2. In QGIS, go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the downloaded ZIP and click **Install Plugin**.
4. The tool will appear in the **Processing Toolbox** under **GCN-HSI → Ecology Tools → GCN Habitat Suitability Index**.

---

## Assessment Modes

| Mode | Variables Scored | Site Visit Required |
|---|---|---|
| Remote Assessment | 6 / 10 (SI1–SI6) | No |
| Full HSI Assessment | Up to 10 / 10 | Yes |

---

## Inputs

### Required
| Parameter | Description |
|---|---|
| Assessment Mode | Remote or Full HSI Assessment |
| Candidate Pond(s) | Polygon layer — 1 to 10 ponds per run |
| Existing Ponds | All ponds within 1km of the candidate pond(s) |
| Terrestrial Habitats | UK Habitat polygons within 250m of the candidate pond(s) |
| Habitat Type Field | Field in the Terrestrial Habitats layer containing UKHab habitat classification strings |

### Optional — Global Defaults
| Parameter | Description |
|---|---|
| GCN Risk Zone | Set to `(auto-detect)` to query from national data, or select Green / Amber / Red manually |
| Pond Permanence | Set to `(auto-detect)` to query from national data, or select a permanence class manually |
| Shoreline Shade % | Percentage of shoreline shaded. Used for SI6 scoring |

### Optional — Per-Pond Overrides
The **Per-Pond Values** table allows individual overrides per pond using its OID:

| Column | Description |
|---|---|
| Pond OID | Feature OID from the Candidate Pond layer |
| Shade (%) | Shoreline shade percentage for this pond |
| Permanence Override | Override permanence class for this pond |
| Risk Zone Override | Override GCN Risk Zone for this pond |

Leave any override cell blank to use the global default or auto-detected value.

### Full HSI Assessment Only
| Parameter | Description |
|---|---|
| Waterfowl Presence | Absent / Minor / Major |
| Fish Presence | Absent / Possible / Minor / Major |
| Water Quality | Good / Moderate / Poor / Bad |
| Macrophyte Cover % | Percentage cover of aquatic macrophytes |

---

## Outputs

A polygon layer copied from the candidate pond input, with the following attribute fields added:

| Field | Description |
|---|---|
| ORIG_OID | Original feature OID from the input layer |
| HSI_SCORE | Overall HSI score (0.0 – 1.0) |
| VARS_USED | Number of variables included in the score |
| HSI_CLASS | High / Moderate / Low |
| ASSESS_MD | Assessment mode used |
| SI1_GEOG | Geographic location score |
| SI2_AREA | Pond area score |
| SI3_PERM | Pond permanence score |
| SI4_TERR | Terrestrial habitat score |
| SI5_COUNT | Pond count score |
| SI6_SHADE | Shoreline shade score |
| SI7_WFOWL | Waterfowl presence score (Full HSI only) |
| SI8_FISH | Fish presence score (Full HSI only) |
| SI9_WQ | Water quality score (Full HSI only) |
| SI10_MACP | Macrophyte cover score (Full HSI only) |

The output layer is automatically symbolised with traffic-light colours:

- **Green** — High suitability (HSI ≥ 0.68)
- **Orange** — Moderate suitability (HSI 0.34–0.67)
- **Red** — Low suitability (HSI < 0.34)

---

## Road Barrier Detection

The tool automatically detects linear road features within the 250m terrestrial habitat buffer. Roads are identified as `Developed Land; Sealed Surface` polygons with a compactness value below the detection threshold. Any habitat polygons or existing ponds located on the far side of a detected road from the candidate pond are excluded from SI4 and SI5 scoring respectively. Detections and exclusions are reported in the Processing Log.

---

## Notes

- Ponds smaller than 900m² cannot be reliably assessed using satellite-derived water history data. For these ponds, a default permanence score is applied and a warning is raised. Manual review of inter-year imagery (e.g. Google Earth) is recommended before overriding via the Per-Pond Values table.
- The HSI score is calculated as a weighted geometric mean of available variables. Variables not assessed (e.g. Full HSI fields in Remote mode) are excluded from the calculation rather than scored as zero.
- This tool is intended to assist qualified ecologists in undertaking HSI assessments. Results should always be reviewed by a suitably experienced ecologist before use in planning or survey decisions.

---

## References

Oldham, R.S., Keeble, J., Roberts, M.J. & Latham, D. (2000). *Evaluating the suitability of habitat for the great crested newt (Triturus cristatus)*. Herpetological Journal, 10: 143–155.

ARG UK (2010). *Advice Note 5: Great Crested Newt Habitat Suitability Index*. Amphibian and Reptile Groups of the United Kingdom.

Bormpoudakis, D., Foster, J., Gent, T., Griffiths, R.A., Russell, L., Starnes, T., Tzanopoulos, J. & Wilkinson, J. (2016). *Developing models to estimate the occurrence in the English countryside of Great Crested Newts, a protected species under the Habitats Directive*. Defra Project WC1108. Project Summary Report. Amphibian and Reptile Conservation, Bournemouth / University of Kent, Canterbury.

Buxton, A.S., Tracey, H. & Downs, N.C. (2021). *How reliable is the habitat suitability index as a predictor of great crested newt presence or absence?* The Herpetological Journal, 31(2): 111–117. ISSN 0268-0130.

---

## License

This plugin is released under the [GNU General Public License v2.0](LICENSE).

© 2026 Ciaran Egan
