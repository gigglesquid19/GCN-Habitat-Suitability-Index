# GCN-HSI — Great Crested Newt Habitat Suitability Index

A QGIS Processing plugin that semi-automates the **Great Crested Newt (GCN) Habitat Suitability Index (HSI)** assessment methodology described in **Oldham et al. (2000)**. The tool scores up to 10 candidate ponds per run and outputs a polygon layer with per-pond HSI scores and traffic-light symbology.

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

## Reference

Oldham, R.S., Keeble, J., Roberts, M.J. & Latham, D. (2000). *Evaluating the suitability of habitat for the great crested newt (Triturus cristatus)*. Herpetological Journal, 10: 143–155.

---

## License

This plugin is released under the [GNU General Public License v2.0](LICENSE).

© 2026 Ciaran Egan
