"""
GCNHabitatSuitability - Custom Ecology Toolbox

Python 3.7+
Author: Ciaran Egan
Company: Carnell Support Services Ltd

Purpose:
Semi-automated Great Crested Newt (GCN) Habitat Suitability Index (HSI) calculator
based on modernised Oldham et al. (2000) methodology. Calculates all 10 HSI variables.

Key Variables Calculated (10/10):
- SI1: Geographic Location (from GCN Risk Zone)
- SI2: Pond Area (user-specified in m²)
- SI3: Pond Permanence (user-specified: Never/Rarely/Sometimes/Annually)
- SI4: Terrestrial Habitat Quality (from surrounding habitat polygons within 250m)
- SI5: Pond Count (calculated from existing ponds within 1km)
- SI6: Shade (user-specified % shoreline shaded)
- SI7: Waterfowl Presence (user-specified from site visit: Absent/Minor/Major)
- SI8: Fish Presence (user-specified from site visit: Absent/Possible/Minor/Major)
- SI9: Water Quality (user-specified from site visit: Good/Moderate/Poor/Bad)
- SI10: Macrophyte Cover (user-specified % from site visit, March-September)

Research suggests Waterfowl, Fish presence are important variables

Output:
CSV file with HSI scores (0-1) for each variable and overall HSI.
"""


# ============================================================================
# IMPORTS
# ============================================================================

import arcpy
import os
import math
import json
import urllib.request
import urllib.parse


# ============================================================================
# CONSTANTS
# ============================================================================

# Buffer distances (meters)
POND_SEARCH_RADIUS = 1000  # 1km for pond count
TERRESTRIAL_BUFFER = 250   # 250m for terrestrial habitat

NE_ARCGIS_ORG_URL = "https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services"
GCN_IRZ_SERVICE_PREFIX = "GCN_Risk_Zones_"

JRC_GSW_URL = "http://global-surface-water.appspot.com/details"
JRC_MIN_RELIABLE_AREA_M2 = 900

# Compactness threshold for road identification: 4*pi*area / perimeter^2
# Circle = 1.0; square ~0.785; road-like elongated polygons typically < 0.05
ROAD_COMPACTNESS_THRESHOLD = 0.05
ROAD_HABITAT_TYPE = "developed land; sealed surface"

# HSI variable count
TOTAL_HSI_VARIABLES = 10
AUTOMATED_VARIABLES = 6

# Variables that require site visits
SITE_VISIT_VARIABLES = [
    "Water Quality",
    "Waterfowl Presence", 
    "Fish Presence",
    "Macrophyte Coverage"
]


# ============================================================================
# GCN HABITAT SUITABILITY TOOL CLASS
# ============================================================================

class GCNHabitatSuitability:
    """Semi-automated GCN Habitat Suitability Index calculator.
    Calculates 10/10 HSI variables from GIS data based on Oldham et al. (2000)."""

    def __init__(self):
        self.label = "GCN Habitat Suitability Index"
        self.description = (
            "Calculates Great Crested Newt Habitat Suitability Index (HSI) based on\n"
            "Oldham et al. (2000). Automates 5 of 10 variables using GIS data.\n\n"
            "Variables calculated:\n"
            "- Geographic Location (GCN Risk Zone)\n"
            "- Pond Area\n"
            "- Pond Permanence\n"
            "- Terrestrial Habitat Quality\n"
            "- Pond Count (within 1km)\n\n"
            "WARNING: This is a partial assessment. Site visit recommended for\n"
            "complete HSI calculation."
        )
        self.canRunInBackground = True
        self.category = "Ecology Tools"

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------
    def getParameterInfo(self):
        params = []

        # 0 - Assessment Mode (required)
        assessment_mode = arcpy.Parameter(
            displayName="Assessment Mode",
            name="assessment_mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        assessment_mode.filter.type = "ValueList"
        assessment_mode.filter.list = ["Remote Assessment", "Full HSI Assessment"]
        assessment_mode.value = "Remote Assessment"
        assessment_mode.description = (
            "Remote Assessment: calculates 6 variables (SI1-SI6) from GIS data and user observation. "
            "No site visit required but conclusions are more uncertain. "
            "Full HSI Assessment: calculates all 10 variables (SI1-SI10) including Waterfowl Presence, "
            "Fish Presence, Water Quality and Macrophyte Coverage recorded during a site visit. "
            "Recommended for robust conclusions."
        )
        params.append(assessment_mode)

        # 1 - Candidate Pond (required)
        candidate_pond = arcpy.Parameter(
            displayName="Candidate Pond Location",
            name="candidate_pond",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        candidate_pond.filter.list = ["Polygon"]
        candidate_pond.description = (
            "Polygon feature class containing 1-10 candidate pond polygons. "
            "Each feature will be assessed independently. "
            "Pond area is calculated automatically from geometry for each feature."
        )
        params.append(candidate_pond)

        # 2 - Existing Ponds within 1km (required)
        existing_ponds = arcpy.Parameter(
            displayName="Existing Ponds (within 1km)",
            name="existing_ponds",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        existing_ponds.filter.list = ["Polygon"]
        existing_ponds.description = "Polygon feature class of existing ponds within 1km"
        params.append(existing_ponds)

        # 3 - Terrestrial Habitats (required)
        terrestrial_habitats = arcpy.Parameter(
            displayName="Terrestrial Habitats (within 250m)",
            name="terrestrial_habitats",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        terrestrial_habitats.filter.list = ["Polygon"]
        terrestrial_habitats.description = (
            "Polygon feature class of terrestrial habitats within 250m of pond"
        )
        params.append(terrestrial_habitats)

        # 5 - Habitat Type Field (required - field from terrestrial habitats layer)
        habitat_type_field = arcpy.Parameter(
            displayName="Habitat Type Field",
            name="habitat_type_field",
            datatype="Field",
            parameterType="Required",
            direction="Input",
        )
        habitat_type_field.parameterDependencies = [terrestrial_habitats.name]
        habitat_type_field.filter.list = ["Text"]
        habitat_type_field.description = (
            "Field in the terrestrial habitats layer containing habitat type names. "
            "Used to classify habitats as semi-natural or poor structure."
        )
        params.append(habitat_type_field)

        # 6 - GCN Risk Zone (optional)
        gcn_risk_zone = arcpy.Parameter(
            displayName="GCN Risk Zone",
            name="gcn_risk_zone",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        gcn_risk_zone.filter.type = "ValueList"
        gcn_risk_zone.filter.list = ["Green", "Amber", "Red"]
        gcn_risk_zone.description = (
            "Geographic location risk zone from the GCN Impact Risk Zones dataset (Natural England). "
            "Leave blank to auto-query the MAGIC WFS service using the pond centroid. "
            "Green = low risk (optimal for GCN). Amber = medium risk. Red = high risk. "
            "If a manual value is provided it will be used in preference to the MAGIC result, "
            "but a warning will be raised if they differ."
        )
        params.append(gcn_risk_zone)

        # 7 - Pond Permanence (optional)
        pond_permanence = arcpy.Parameter(
            displayName="Pond Permanence",
            name="pond_permanence",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        pond_permanence.filter.type = "ValueList"
        pond_permanence.filter.list = ["Never Dries", "Rarely Dries", "Sometimes Dries", "Dries Annually"]
        pond_permanence.description = (
            "How often the pond dries up. Affects GCN habitat suitability. "
            "Leave blank to auto-query the JRC Global Surface Water dataset (Pekel et al., 2016) "
            "using the pond centroid. "
            "Seasonality should be considered when classifying: ponds that dry out "
            "by mid-to-late Spring or Early Summer (April-June) are likely to do so "
            "every year and should be classified as 'Dries Annually'. "
            "Never Dries = holds water year-round. "
            "Rarely Dries = dries in exceptionally dry years only. "
            "Sometimes Dries = dries in some years, typically late Summer or Autumn. "
            "Note: JRC auto-population is unreliable for ponds smaller than ~900m\xb2 "
            "(30m Landsat resolution). A warning will be raised for small ponds."
        )
        params.append(pond_permanence)

        # 7 - Shoreline Shade (optional - global default, overridable per pond)
        shoreline_shade = arcpy.Parameter(
            displayName="Shoreline Shade (%) - Default",
            name="shoreline_shade",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        shoreline_shade.filter.type = "Range"
        shoreline_shade.filter.list = [0, 100]
        shoreline_shade.description = (
            "Default shoreline shade percentage applied to all ponds. "
            "Override per pond using the Per-Pond Values table below. "
            "Derive from satellite imagery captured between May and September. "
            "0-60% shade is optimal for GCN; values above 60% reduce suitability."
        )
        params.append(shoreline_shade)

        # 8 - Per-Pond Values (optional - grid of per-pond overrides)
        per_pond_values = arcpy.Parameter(
            displayName="Per-Pond Values",
            name="per_pond_values",
            datatype="GPValueTable",
            parameterType="Optional",
            direction="Input",
        )
        per_pond_values.columns = [
            ["GPLong",   "Pond OID"],
            ["GPDouble", "Shade (%)"],
            ["GPString", "Permanence Override"],
            ["GPString", "Risk Zone Override"],
        ]
        per_pond_values.filters[1].type = "Range"
        per_pond_values.filters[1].list = [0, 100]
        per_pond_values.description = (
            "Per-pond values table. Populated automatically when the Candidate Pond layer is set. "
            "Enter Shade (%) for each pond. Leave Permanence Override and Risk Zone Override "
            "blank to use auto-queried values (JRC and MAGIC respectively). "
            "Provide overrides to correct auto-queried values for specific ponds."
        )
        params.append(per_pond_values)

        # 9 - Waterfowl Presence (optional - requires site visit, Full HSI Assessment only)
        waterfowl_presence = arcpy.Parameter(
            displayName="Waterfowl Presence",
            name="waterfowl_presence",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        waterfowl_presence.filter.type = "ValueList"
        waterfowl_presence.filter.list = ["Absent", "Minor", "Major"]
        waterfowl_presence.description = (
            "Impact of waterfowl on the pond (assessed during site visit). "
            "Absent = no evidence of waterfowl impact (moorhens may be present). "
            "Minor = waterfowl present but pond still supports submerged plants and banks are not denuded. "
            "Major = severe impact; little or no submerged plants, turbid water, banks denuded."
        )
        params.append(waterfowl_presence)

        # 10 - Fish Presence (optional - requires site visit, Full HSI Assessment only)
        fish_presence = arcpy.Parameter(
            displayName="Fish Presence",
            name="fish_presence",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        fish_presence.filter.type = "ValueList"
        fish_presence.filter.list = ["Absent", "Possible", "Minor", "Major"]
        fish_presence.description = (
            "Fish presence in the pond (assessed during site visit using netting, torchlight or local knowledge). "
            "Absent = no records of stocking and no fish revealed by netting or torchlight. "
            "Possible = no evidence of fish but local conditions suggest they may be present. "
            "Minor = small numbers of crucian carp, goldfish or stickleback known to be present. "
            "Major = dense populations of fish known to be present."
        )
        params.append(fish_presence)

        # 11 - Water Quality (optional - requires site visit, Full HSI Assessment only)
        water_quality = arcpy.Parameter(
            displayName="Water Quality",
            name="water_quality",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        water_quality.filter.type = "ValueList"
        water_quality.filter.list = ["Good", "Moderate", "Poor", "Bad"]
        water_quality.description = (
            "Water quality assessed during site visit based on invertebrate diversity and submerged plant presence. "
            "Good = abundant and diverse invertebrate community including mayfly larvae and water shrimps. "
            "Moderate = moderate invertebrate diversity. "
            "Poor = low invertebrate diversity (e.g. midge and mosquito larvae only), few submerged plants. "
            "Bad = clearly polluted; only pollution-tolerant invertebrates (e.g. rat-tailed maggots), no submerged plants. "
            "Note: water clarity alone is not a reliable indicator of water quality."
        )
        params.append(water_quality)

        # 12 - Macrophyte Cover (optional - requires site visit, Full HSI Assessment only)
        macrophyte_cover = arcpy.Parameter(
            displayName="Macrophyte Cover (%)",
            name="macrophyte_cover",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        macrophyte_cover.filter.type = "Range"
        macrophyte_cover.filter.list = [0, 100]
        macrophyte_cover.description = (
            "Percentage of pond surface area occupied by macrophyte cover (0-100%). "
            "Includes emergents, floating plants (excluding duckweed) and submerged plants reaching the surface. "
            "Estimate between March and end of September. Optimal cover is 75%, scoring 1.0."
        )
        params.append(macrophyte_cover)

        # 13 - Output Shapefile
        output_shapefile = arcpy.Parameter(
            displayName="Output Shapefile",
            name="output_shapefile",
            datatype="DEShapefile",
            parameterType="Required",
            direction="Output",
        )
        output_shapefile.description = (
            "Output point shapefile containing the pond location with all HSI scores as "
            "attributes. Symbolised automatically with traffic light colouring based on "
            "overall HSI suitability class (Red = Low, Amber = Moderate, Green = High)."
        )
        params.append(output_shapefile)

        return params

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        mode = parameters[0].valueAsText
        full_assessment = (mode == "Full HSI Assessment")
        parameters[9].enabled = full_assessment
        parameters[10].enabled = full_assessment
        parameters[11].enabled = full_assessment
        parameters[12].enabled = full_assessment
        if not full_assessment:
            parameters[9].value = None
            parameters[10].value = None
            parameters[11].value = None
            parameters[12].value = None

        # Auto-populate Per-Pond Values table when candidate pond layer is set
        candidate = parameters[1]
        per_pond_param = parameters[8]
        if (candidate.value and not per_pond_param.altered and
                arcpy.Exists(candidate.valueAsText)):
            try:
                count = int(arcpy.GetCount_management(candidate.valueAsText)[0])
                if 1 <= count <= 10:
                    rows = []
                    with arcpy.da.SearchCursor(
                        candidate.valueAsText, ["OID@"]
                    ) as cursor:
                        for row in cursor:
                            rows.append([row[0], 0, "", ""])
                    per_pond_param.values = rows
            except Exception:
                pass
        return

    def updateMessages(self, parameters):
        # Validate candidate pond has 1-10 features
        candidate_path = parameters[1].valueAsText
        if candidate_path and arcpy.Exists(candidate_path):
            count = int(arcpy.GetCount_management(candidate_path)[0])
            if count == 0:
                parameters[1].setErrorMessage("Candidate pond layer contains no features")
            elif count > 10:
                parameters[1].setErrorMessage(
                    f"Maximum 10 candidate ponds per run. Found: {count}. "
                    "Filter or select up to 10 features."
                )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, parameters, messages):
        try:
            # Extract parameters
            assessment_mode    = parameters[0].valueAsText
            candidate_pond_path = parameters[1].valueAsText
            existing_ponds_path = parameters[2].valueAsText
            terrestrial_path   = parameters[3].valueAsText
            habitat_type_field = parameters[4].valueAsText
            gcn_risk_zone_default     = parameters[5].valueAsText
            pond_permanence_default   = parameters[6].value
            shoreline_shade_default   = parameters[7].value
            per_pond_table     = parameters[8].values
            waterfowl_presence = parameters[9].valueAsText  if assessment_mode == "Full HSI Assessment" else None
            fish_presence      = parameters[10].valueAsText if assessment_mode == "Full HSI Assessment" else None
            water_quality      = parameters[11].valueAsText if assessment_mode == "Full HSI Assessment" else None
            macrophyte_cover   = parameters[12].value       if assessment_mode == "Full HSI Assessment" else None
            output_shapefile   = parameters[13].valueAsText

            arcpy.AddMessage("=" * 70)
            arcpy.AddMessage("GCN HABITAT SUITABILITY INDEX CALCULATOR")
            arcpy.AddMessage("Based on Oldham et al. (2000)")
            arcpy.AddMessage(f"Mode: {assessment_mode}")
            arcpy.AddMessage("=" * 70)
            if assessment_mode == "Remote Assessment":
                arcpy.AddWarning("=" * 70)
                arcpy.AddWarning("REMOTE ASSESSMENT - IMPORTANT LIMITATIONS")
                arcpy.AddWarning("=" * 70)
                arcpy.AddWarning("This run uses 6 of 10 HSI variables. The following key variables are OMITTED:")
                arcpy.AddWarning("  - Waterfowl Presence (SI7) - most significant variable")
                arcpy.AddWarning("  - Fish Presence (SI8)      - most significant variable")
                arcpy.AddWarning("  - Water Quality (SI9)")
                arcpy.AddWarning("  - Macrophyte Cover (SI10)")
                arcpy.AddWarning("Conclusions from this assessment are LESS ROBUST than a full assessment.")
                arcpy.AddWarning("A site visit is strongly recommended to record all 10 variables.")
                arcpy.AddWarning("=" * 70)

            # Step 1: Validate inputs and load all candidate pond features
            arcpy.AddMessage("")
            arcpy.AddMessage("Step 1: Validating inputs...")
            pond_features = self._validate_candidate_pond(candidate_pond_path)
            n_ponds = len(pond_features)
            arcpy.AddMessage(f"  {n_ponds} candidate pond(s) validated")

            # Parse per-pond values table into a lookup dict keyed by OID
            # Columns: [OID, Shade (%), Permanence Override, Risk Zone Override]
            per_pond_dict = {}
            if per_pond_table:
                for row in per_pond_table:
                    try:
                        oid  = int(row[0]) if row[0] not in (None, "") else None
                        shade = float(row[1]) if row[1] not in (None, "") else None
                        perm  = str(row[2]).strip() if row[2] not in (None, "") else None
                        risk  = str(row[3]).strip() if row[3] not in (None, "") else None
                        if oid is not None:
                            per_pond_dict[oid] = {
                                "shade": shade,
                                "permanence": perm if perm else None,
                                "risk_zone":  risk  if risk  else None,
                            }
                    except (ValueError, TypeError):
                        pass

            # Cache MAGIC service listing once for all ponds
            arcpy.AddMessage("")
            arcpy.AddMessage("Step 1b: Fetching GCN Risk Zone service listing...")
            magic_services = None
            try:
                magic_services = self._fetch_magic_services()
                arcpy.AddMessage(f"  Found {len(magic_services)} GCN Risk Zone regional services")
            except Exception as svc_err:
                arcpy.AddWarning(f"  Failed to fetch MAGIC service listing: {str(svc_err)}")
                arcpy.AddWarning("  SI1 will use manually specified values if provided.")

            # Spatial reference for road barrier geometry construction
            sr = arcpy.Describe(candidate_pond_path).spatialReference

            # Per-pond processing loop
            all_results = {}
            small_ponds = []  # ponds below JRC minimum area
            for i, pond in enumerate(pond_features, 1):
                oid      = pond["oid"]
                area_m2  = pond["area"]
                centroid = pond["centroid"]

                arcpy.AddMessage("")
                arcpy.AddMessage(f"--- Pond {i}/{n_ponds}  (OID: {oid}  |  Area: {area_m2:.0f} m\u00b2) ---")

                # Resolve per-pond overrides, falling back to global defaults
                p = per_pond_dict.get(oid, {})
                shoreline_shade  = p.get("shade")      if p.get("shade")      is not None else shoreline_shade_default
                gcn_risk_zone    = p.get("risk_zone")  or gcn_risk_zone_default
                pond_permanence  = p.get("permanence") or pond_permanence_default

                # Step 1b (per pond): MAGIC query for this pond's centroid
                arcpy.AddMessage("  Step 1b: Querying MAGIC WFS for GCN Risk Zone (SI1)...")
                if magic_services:
                    try:
                        magic_zone = self._query_magic_gcn_risk_zone(
                            centroid, candidate_pond_path, magic_services
                        )
                        if magic_zone:
                            if not gcn_risk_zone:
                                gcn_risk_zone = magic_zone
                                arcpy.AddMessage(f"    MAGIC auto-populated: {gcn_risk_zone}")
                            elif gcn_risk_zone != magic_zone:
                                arcpy.AddWarning(
                                    f"    MAGIC returned '{magic_zone}' but override is '{gcn_risk_zone}'. "
                                    "Using override."
                                )
                            else:
                                arcpy.AddMessage(f"    MAGIC confirmed: {gcn_risk_zone}")
                        else:
                            arcpy.AddWarning("    MAGIC returned no risk zone — pond may be outside IRZ extent.")
                    except Exception as magic_err:
                        arcpy.AddWarning(f"    MAGIC query failed: {str(magic_err)}")

                # Step 1c (per pond): JRC query for pond permanence
                arcpy.AddMessage("  Step 1c: JRC Global Surface Water - Pond Permanence (SI3)...")
                if area_m2 < JRC_MIN_RELIABLE_AREA_M2:
                    small_ponds.append((oid, area_m2))
                    arcpy.AddWarning(
                        f"    SKIPPED (OID {oid}): Area {area_m2:.0f}m\u00b2 is below the "
                        f"30m Landsat pixel threshold ({JRC_MIN_RELIABLE_AREA_M2}m\u00b2). "
                        "Default permanence score (0.5) will be applied. "
                        "Manual site assessment is recommended."
                    )
                else:
                    try:
                        jrc_permanence = self._query_jrc_pond_permanence(
                            centroid, candidate_pond_path, area_m2
                        )
                        if jrc_permanence:
                            if not pond_permanence:
                                pond_permanence = jrc_permanence
                                arcpy.AddMessage(f"    JRC auto-populated: {pond_permanence}")
                            elif pond_permanence != jrc_permanence:
                                arcpy.AddWarning(
                                    f"    JRC returned '{jrc_permanence}' but override is '{pond_permanence}'. "
                                    "Using override."
                                )
                            else:
                                arcpy.AddMessage(f"    JRC confirmed: {pond_permanence}")
                        else:
                            arcpy.AddWarning("    JRC returned no water history — permanence must be set manually.")
                    except Exception as jrc_err:
                        arcpy.AddWarning(f"    JRC query failed: {str(jrc_err)}")

                # Step 2 (per pond): Terrestrial habitats within 250m (done first to capture road barriers)
                terrestrial_area, semi_natural_proportion, road_geoms = self._validate_terrestrial_habitats(
                    terrestrial_path, centroid, habitat_type_field
                )
                arcpy.AddMessage(
                    f"  Step 2: Semi-natural proportion within 250m: "
                    f"{semi_natural_proportion * 100:.1f}%"
                )

                # Step 3 (per pond): Existing ponds within 1km (road barriers applied)
                pond_count = self._validate_existing_ponds(
                    existing_ponds_path, centroid, road_geoms, sr
                )
                arcpy.AddMessage(f"  Step 3: Ponds within 1km (after road exclusion): {pond_count}")

                # Count variables with real (non-default) data for this pond
                vars_used = 3  # SI2 (area from geometry), SI4 (terrestrial), SI5 (pond count) always assessed
                if gcn_risk_zone:
                    vars_used += 1  # SI1
                if pond_permanence is not None:
                    vars_used += 1  # SI3 - only if JRC or override provided a value
                if shoreline_shade is not None:
                    vars_used += 1  # SI6
                if waterfowl_presence:
                    vars_used += 1  # SI7
                if fish_presence:
                    vars_used += 1  # SI8
                if water_quality:
                    vars_used += 1  # SI9
                if macrophyte_cover is not None:
                    vars_used += 1  # SI10

                # Step 4-5: Calculate HSI scores for this pond
                hsi_scores = self._calculate_hsi_scores(
                    pond_area_m2=area_m2,
                    pond_count=pond_count,
                    gcn_risk_zone=gcn_risk_zone,
                    pond_permanence=pond_permanence,
                    semi_natural_proportion=semi_natural_proportion,
                    shoreline_shade=shoreline_shade,
                    waterfowl_presence=waterfowl_presence,
                    fish_presence=fish_presence,
                    water_quality=water_quality,
                    macrophyte_cover=macrophyte_cover
                )
                hsi_scores["variables_used"] = vars_used
                all_results[oid] = hsi_scores
                arcpy.AddMessage(
                    f"  Result: HSI {hsi_scores['overall_hsi']:.3f} "
                    f"({self._classify_hsi(hsi_scores['overall_hsi'])})"
                )

            # Post-loop: consolidated warning for ponds below JRC minimum size
            if small_ponds:
                arcpy.AddMessage("")
                arcpy.AddWarning("=" * 70)
                arcpy.AddWarning("POND PERMANENCE — MANUAL ASSESSMENT REQUIRED")
                arcpy.AddWarning("=" * 70)
                arcpy.AddWarning(
                    f"{len(small_ponds)} pond(s) are smaller than the 30m Landsat pixel "
                    f"resolution ({JRC_MIN_RELIABLE_AREA_M2}m\u00b2). "
                    "JRC Global Surface Water cannot reliably detect these ponds. "
                    "A default permanence score of 0.5 (mid-range, 'Sometimes Dries') "
                    "has been used — this may over- or under-estimate suitability."
                )
                arcpy.AddWarning("")
                arcpy.AddWarning("Ponds requiring manual permanence assessment:")
                for sp_oid, sp_area in small_ponds:
                    arcpy.AddWarning(f"  OID {sp_oid:>4}  |  Area: {sp_area:.0f}m\u00b2")
                arcpy.AddWarning("")
                arcpy.AddWarning(
                    "ACTION (Remote Assessment): Review inter-year imagery in Google Earth "
                    "for each pond listed above, looking for evidence of seasonal drying or "
                    "year-round water presence across multiple years (use the historical "
                    "imagery slider). Then re-run with the Permanence Override populated "
                    "in the Per-Pond Values table."
                )
                arcpy.AddWarning("=" * 70)

            # Step 6: Create output shapefile with all pond results
            arcpy.AddMessage("")
            arcpy.AddMessage("Step 6: Creating output shapefile...")
            ordered_oids = [p["oid"] for p in pond_features]
            self._create_output_shapefile(
                output_shapefile, candidate_pond_path, all_results, assessment_mode, ordered_oids
            )
            arcpy.AddMessage(f"  Shapefile saved: {output_shapefile}")
            self._apply_traffic_light_symbology(output_shapefile)
            arcpy.AddMessage("  Traffic light symbology applied")

            # Summary
            arcpy.AddMessage("")
            arcpy.AddMessage("=" * 70)
            arcpy.AddMessage("HSI CALCULATION SUMMARY")
            arcpy.AddMessage("=" * 70)
            arcpy.AddMessage(f"Ponds assessed: {n_ponds}")
            arcpy.AddMessage("")
            for oid, scores in all_results.items():
                arcpy.AddMessage(f"  Pond OID {oid}:")
                area_msg = f"{scores['pond_area']:.3f}" if scores['pond_area'] is not None else "N/A (>2000m\u00b2)"
                arcpy.AddMessage(f"    Geographic Location (SI1): {scores['geographic_location']:.3f}")
                arcpy.AddMessage(f"    Pond Area (SI2):           {area_msg}")
                arcpy.AddMessage(f"    Pond Permanence (SI3):     {scores['permanence']:.3f}")
                arcpy.AddMessage(f"    Terrestrial Habitat (SI4): {scores['terrestrial_habitat']:.3f}")
                arcpy.AddMessage(f"    Pond Count (SI5):          {scores['pond_count']:.3f}")
                arcpy.AddMessage(f"    Shoreline Shade (SI6):     {scores['shade']:.3f}")
                wfl = round(scores['waterfowl'],    3) if scores.get('waterfowl')    is not None else 'Not provided'
                fsh = round(scores['fish'],           3) if scores.get('fish')          is not None else 'Not provided'
                wq  = round(scores['water_quality'],  3) if scores.get('water_quality') is not None else 'Not provided'
                mac = round(scores['macrophyte'],     3) if scores.get('macrophyte')    is not None else 'Not provided'
                arcpy.AddMessage(f"    Waterfowl (SI7):           {wfl}")
                arcpy.AddMessage(f"    Fish (SI8):                {fsh}")
                arcpy.AddMessage(f"    Water Quality (SI9):       {wq}")
                arcpy.AddMessage(f"    Macrophyte (SI10):         {mac}")
                arcpy.AddMessage(f"    Variables with real data:  {scores.get('variables_used', 0)}/10")
                arcpy.AddMessage(f"    OVERALL HSI:               {scores['overall_hsi']:.3f}  ({self._classify_hsi(scores['overall_hsi'])})")
                arcpy.AddMessage("")

            arcpy.AddWarning("=" * 70)
            if assessment_mode == "Remote Assessment":
                arcpy.AddWarning("SUMMARY WARNING: REMOTE ASSESSMENT - PARTIAL RESULTS ONLY")
            else:
                arcpy.AddWarning("SUMMARY: FULL HSI ASSESSMENT")
            arcpy.AddWarning("=" * 70)
            if assessment_mode == "Remote Assessment":
                arcpy.AddWarning("CRITICAL: The two most significant variables were NOT assessed:")
                arcpy.AddWarning("  - Waterfowl Presence (SI7): Major waterfowl impact can severely reduce suitability.")
                arcpy.AddWarning("  - Fish Presence (SI8):      Fish populations are a key predator of GCN larvae.")
                arcpy.AddWarning("")
                arcpy.AddWarning("Additional omitted variables: Water Quality (SI9), Macrophyte Cover (SI10).")
                arcpy.AddWarning("")
                arcpy.AddWarning("RECOMMENDATION: Conduct a site visit to record all 10 variables before")
                arcpy.AddWarning("making any planning or management decisions based on this output.")
            arcpy.AddWarning("=" * 70)

        except Exception as e:
            arcpy.AddError(f"HSI calculation failed: {str(e)}")
            raise

    # ------------------------------------------------------------------
    # Validation Helper Methods
    # ------------------------------------------------------------------
    def _validate_candidate_pond(self, candidate_path):
        """Validate candidate pond layer has 1-10 polygons.
        Returns list of dicts with keys: oid, shape, area, centroid."""
        count = int(arcpy.GetCount_management(candidate_path)[0])

        if count == 0:
            raise ValueError("Candidate pond layer contains no features")

        if count > 10:
            raise ValueError(
                f"Candidate pond layer contains {count} features. "
                "Maximum 10 ponds per run — filter or select up to 10."
            )

        pond_features = []
        with arcpy.da.SearchCursor(candidate_path, ["OID@", "SHAPE@", "SHAPE@AREA"]) as cursor:
            for row in cursor:
                pond_features.append({
                    "oid":      row[0],
                    "shape":    row[1],
                    "area":     round(row[2], 2),
                    "centroid": row[1].centroid,
                })
        return pond_features

    def _validate_existing_ponds(self, ponds_path, candidate_centroid, road_geoms=None, sr=None):
        """Validate existing ponds are within 1km of candidate.
        Ponds on the far side of a road barrier (from road_geoms) are excluded.
        Returns count of accessible ponds."""
        ponds_within_radius = 0
        ponds_outside = 0
        ponds_blocked = 0

        with arcpy.da.SearchCursor(ponds_path, ["SHAPE@"]) as cursor:
            for row in cursor:
                pond_shape = row[0]
                if pond_shape:
                    distance = self._calculate_distance(
                        candidate_centroid, pond_shape.centroid
                    )
                    if distance <= POND_SEARCH_RADIUS:
                        if road_geoms and sr and self._is_blocked_by_road(
                            candidate_centroid, pond_shape.centroid, road_geoms, sr
                        ):
                            ponds_blocked += 1
                        else:
                            ponds_within_radius += 1
                    else:
                        ponds_outside += 1

        if ponds_blocked > 0:
            arcpy.AddWarning(
                f"    {ponds_blocked} pond(s) excluded from SI5 — located beyond road barrier."
            )

        if ponds_within_radius == 0 and ponds_outside > 0 and ponds_blocked == 0:
            raise ValueError(
                f"No existing ponds found within {POND_SEARCH_RADIUS}m of candidate pond. "
                f"Found {ponds_outside} ponds outside the search radius. "
                "Please provide ponds within 1km of the candidate pond."
            )

        return ponds_within_radius

    def _validate_terrestrial_habitats(self, habitats_path, candidate_centroid, habitat_type_field):
        """Validate terrestrial habitats within 250m.

        Two-pass approach: first identifies road barrier polygons (Developed Land;
        Sealed Surface with elongated/road-like shape), then scores remaining habitats
        excluding those on the far side of a road barrier.

        Returns (total_area, semi_natural_proportion, road_geoms) where road_geoms is
        a list of arcpy Geometry objects representing detected road barriers.
        """
        road_geoms = []
        habitat_features = []
        habitats_outside = 0

        with arcpy.da.SearchCursor(
            habitats_path, ["SHAPE@", "SHAPE@AREA", "SHAPE@LENGTH", habitat_type_field]
        ) as cursor:
            for row in cursor:
                habitat_shape = row[0]
                habitat_area  = row[1]
                perimeter     = row[2]
                habitat_type  = row[3]
                if not habitat_shape:
                    continue
                distance = self._calculate_distance(candidate_centroid, habitat_shape.centroid)
                if distance > TERRESTRIAL_BUFFER:
                    habitats_outside += 1
                    continue
                if self._is_road_polygon(habitat_area, perimeter, str(habitat_type) if habitat_type else ""):
                    road_geoms.append(habitat_shape)
                else:
                    habitat_features.append((habitat_shape, habitat_area, habitat_type))

        if road_geoms:
            arcpy.AddMessage(
                f"    Road barrier(s) detected within 250m: {len(road_geoms)} polygon(s). "
                "Habitats on the far side will be excluded from SI4."
            )

        sr = arcpy.Describe(habitats_path).spatialReference
        total_area = 0.0
        semi_natural_area = 0.0
        habitats_within = 0
        habitats_excluded = 0

        for habitat_shape, habitat_area, habitat_type in habitat_features:
            if road_geoms and self._is_blocked_by_road(
                candidate_centroid, habitat_shape.centroid, road_geoms, sr
            ):
                habitats_excluded += 1
                continue
            total_area += habitat_area
            habitats_within += 1
            if habitat_type and self._classify_habitat_type(str(habitat_type)):
                semi_natural_area += habitat_area

        if habitats_excluded > 0:
            arcpy.AddWarning(
                f"    {habitats_excluded} habitat polygon(s) excluded from SI4 — located beyond road barrier."
            )

        if habitats_within == 0 and habitats_outside > 0 and not road_geoms:
            raise ValueError(
                f"No terrestrial habitats found within {TERRESTRIAL_BUFFER}m of candidate pond. "
                f"Found {habitats_outside} habitat polygons outside the buffer. "
                "Please provide habitats within 250m of the candidate pond."
            )

        if habitats_within == 0:
            arcpy.AddWarning("No terrestrial habitats provided. SI4 will be scored as None (0.01).")
            return 0.0, 0.0, road_geoms

        semi_natural_proportion = semi_natural_area / total_area if total_area > 0 else 0.0
        return total_area, semi_natural_proportion, road_geoms

    def _is_road_polygon(self, area, perimeter, habitat_type):
        """Return True if the polygon is a road: Developed Land; Sealed Surface AND elongated.
        Compactness = 4*pi*area / perimeter^2. Roads score near 0; compact shapes near 1.
        """
        if ROAD_HABITAT_TYPE not in habitat_type.lower():
            return False
        if area <= 0 or perimeter <= 0:
            return False
        return (4 * math.pi * area) / (perimeter ** 2) < ROAD_COMPACTNESS_THRESHOLD

    def _is_blocked_by_road(self, centroid, hab_centroid, road_geoms, sr):
        """Return True if any road geometry intersects the straight line from pond centroid
        to habitat/pond centroid, indicating the road acts as a movement barrier.
        """
        line = arcpy.Polyline(arcpy.Array([centroid, hab_centroid]), sr)
        return any(not line.disjoint(road) for road in road_geoms)

    def _calculate_distance(self, point1, point2):
        """Calculate Euclidean distance between two points."""
        dx = point1.X - point2.X
        dy = point1.Y - point2.Y
        return math.sqrt(dx * dx + dy * dy)

    def _query_jrc_pond_permanence(self, centroid, candidate_pond_path, pond_area_m2):
        """
        Query the JRC Global Surface Water /details endpoint for pond permanence.

        Endpoint confirmed via DevTools on global-surface-water.appspot.com/map.
        Response structure used:
          monthly_recurrence_profile.images[0..11]       - Landsat images per month
          monthly_recurrence_profile.observations[0..11] - water detections per month

        Calculates average monthly recurrence (observations / images) across all
        months that have valid Landsat data (typically Mar-Sep for England due to
        winter cloud cover).

        Recurrence thresholds (Oldham 2000 interpretation):
          >= 0.85  -> Never Dries       (water present almost always)
          >= 0.65  -> Rarely Dries      (dries in exceptional drought years only)
          >= 0.35  -> Sometimes Dries   (dries in some years)
          <  0.35  -> Dries Annually    (frequently dries each summer/autumn)

        The caller is responsible for checking pond_area_m2 >= JRC_MIN_RELIABLE_AREA_M2
        before invoking this method.
        Returns a permanence string or None if no valid monthly data available.
        """
        sr = arcpy.Describe(candidate_pond_path).spatialReference
        point_geom = arcpy.PointGeometry(centroid, sr)
        point_wgs84 = point_geom.projectAs(arcpy.SpatialReference(4326))
        lat = point_wgs84.centroid.Y
        lon = point_wgs84.centroid.X

        query_url = (
            f"{JRC_GSW_URL}?"
            + urllib.parse.urlencode({"lat": round(lat, 6), "lon": round(lon, 6)})
        )
        req = urllib.request.Request(
            query_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8-sig"))

        profile = data.get("monthly_recurrence_profile", {})
        images = profile.get("images", [])
        observations = profile.get("observations", [])

        if not images or not observations:
            return None

        recurrence_values = []
        for i in range(12):
            img = images[i] if i < len(images) else None
            obs = observations[i] if i < len(observations) else None
            if img is not None and img > 0 and obs is not None:
                recurrence_values.append(obs / img)

        if not recurrence_values:
            arcpy.AddMessage(
                f"  JRC: no valid monthly observations at lat={lat:.5f}, lon={lon:.5f}"
            )
            return None

        avg_recurrence = sum(recurrence_values) / len(recurrence_values)
        arcpy.AddMessage(
            f"  JRC: {len(recurrence_values)} months with data, "
            f"average monthly recurrence {avg_recurrence:.0%}"
        )

        if avg_recurrence >= 0.85:
            return "Never Dries"
        elif avg_recurrence >= 0.65:
            return "Rarely Dries"
        elif avg_recurrence >= 0.35:
            return "Sometimes Dries"
        return "Dries Annually"

    def _fetch_magic_services(self):
        """Fetch the list of GCN Risk Zone service names from Natural England ArcGIS Online.
        Returns a list of service name strings matching GCN_IRZ_SERVICE_PREFIX."""
        services_url = f"{NE_ARCGIS_ORG_URL}?f=json"
        req = urllib.request.Request(
            services_url, headers={"User-Agent": "ArcGISPro-GCN-HSI-Tool/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            listing = json.loads(response.read().decode("utf-8-sig"))
        return [
            svc["name"]
            for svc in listing.get("services", [])
            if svc.get("name", "").startswith(GCN_IRZ_SERVICE_PREFIX)
        ]

    def _query_magic_gcn_risk_zone(self, centroid, candidate_pond_path, services):
        """
        Query Natural England's ArcGIS Online services for the GCN Impact Risk Zone.

        Accepts a pre-fetched list of service names to avoid redundant network calls
        when processing multiple ponds in a single run.

        Spatially queries each regional service with the pond centroid (WGS84)
        until one returns a matching feature.

        Returns "Red", "Amber", "Green", or None if no region contains the pond.
        """
        # Project centroid to WGS84
        sr = arcpy.Describe(candidate_pond_path).spatialReference
        point_geom = arcpy.PointGeometry(centroid, sr)
        point_wgs84 = point_geom.projectAs(arcpy.SpatialReference(4326))
        lon = point_wgs84.centroid.X
        lat = point_wgs84.centroid.Y

        if not services:
            return None

        # Query each regional service until a feature is returned
        spatial_params = urllib.parse.urlencode({
            "geometry": json.dumps({
                "x": lon,
                "y": lat,
                "spatialReference": {"wkid": 4326}
            }),
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json"
        })

        for svc_name in services:
            query_url = (
                f"{NE_ARCGIS_ORG_URL}/{svc_name}/FeatureServer/0/query?{spatial_params}"
            )
            req = urllib.request.Request(
                query_url, headers={"User-Agent": "ArcGISPro-GCN-HSI-Tool/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8-sig"))

            if "error" in data:
                continue

            features = data.get("features", [])
            if not features:
                continue

            attrs = features[0].get("attributes", {})
            zone_value = (
                attrs.get("Risk_Zone") or
                attrs.get("IRZ_TYPE") or
                attrs.get("ZONE") or
                attrs.get("RISK_ZONE") or
                attrs.get("RISK") or
                attrs.get("risk_lvl")
            )

            if zone_value is None:
                arcpy.AddWarning(
                    f"  Feature found in {svc_name} but risk zone field not recognised. "
                    f"Available attributes: {list(attrs.keys())}. "
                    "Update _query_magic_gcn_risk_zone with the correct field name."
                )
                return None

            region = svc_name.replace(GCN_IRZ_SERVICE_PREFIX, "")
            arcpy.AddMessage(f"  Matched region: {region}")

            zone_str = str(zone_value).upper()
            if "HIGH" in zone_str or "RED" in zone_str:
                return "Red"
            if "MED" in zone_str or "AMBER" in zone_str:
                return "Amber"
            if "LOW" in zone_str or "GREEN" in zone_str:
                return "Green"

            arcpy.AddWarning(
                f"  Unrecognised zone value '{zone_value}' in {svc_name}. "
                "Expected High/Medium/Low or Red/Amber/Green."
            )
            return None

        return None

    # ------------------------------------------------------------------
    # HSI Calculation Methods
    # ------------------------------------------------------------------
    def _calculate_hsi_scores(self, pond_area_m2, pond_count, gcn_risk_zone,
                               pond_permanence, semi_natural_proportion, shoreline_shade,
                               waterfowl_presence=None, fish_presence=None,
                               water_quality=None, macrophyte_cover=None):
        """Calculate HSI scores for each variable.
        
        Note: Actual scoring logic to be refined in next iteration.
        Current implementation uses placeholder scoring based on Oldham (2000).
        """
        scores = {}

        # SI1: Geographic Location (from GCN Risk Zone)
        if gcn_risk_zone:
            zone_scores = {"Green": 1.0, "Amber": 0.5, "Red": 0.01}
            scores["geographic_location"] = zone_scores.get(gcn_risk_zone, 0.5)
        else:
            scores["geographic_location"] = 0.5  # Default mid-range if not provided

        # SI2: Pond Area (placeholder - actual scoring TBD)
        # Optimal range typically 500-5000 m²
        scores["pond_area"] = self._score_pond_area(pond_area_m2)

        # SI3: Pond Permanence
        if pond_permanence is not None:
            permanence_scores = {
                "Never Dries": 0.9,
                "Rarely Dries": 1.0,
                "Sometimes Dries": 0.5,
                "Dries Annually": 0.1
            }
            scores["permanence"] = permanence_scores.get(pond_permanence, 0.5)
        else:
            scores["permanence"] = 0.5  # Default if not provided

        # SI4: Terrestrial Habitat
        scores["terrestrial_habitat"] = self._score_terrestrial_habitat(semi_natural_proportion)

        # SI5: Pond Count (placeholder - actual scoring TBD)
        scores["pond_count"] = self._score_pond_count(pond_count)

        # SI6: Shoreline Shade
        if shoreline_shade is not None:
            scores["shade"] = self._score_shade(shoreline_shade)
        else:
            scores["shade"] = 0.5  # Default if not provided

        # SI7: Waterfowl Presence (optional - site visit)
        if waterfowl_presence:
            waterfowl_scores = {"Absent": 1.0, "Minor": 0.67, "Major": 0.01}
            scores["waterfowl"] = waterfowl_scores.get(waterfowl_presence, 0.5)
        else:
            scores["waterfowl"] = None  # Omitted if not provided

        # SI8: Fish Presence (optional - site visit)
        if fish_presence:
            fish_scores = {"Absent": 1.0, "Possible": 0.67, "Minor": 0.33, "Major": 0.01}
            scores["fish"] = fish_scores.get(fish_presence, 0.5)
        else:
            scores["fish"] = None  # Omitted if not provided

        # SI9: Water Quality (optional - site visit)
        if water_quality:
            wq_scores = {"Good": 1.0, "Moderate": 0.67, "Poor": 0.33, "Bad": 0.01}
            scores["water_quality"] = wq_scores.get(water_quality, 0.5)
        else:
            scores["water_quality"] = None  # Omitted if not provided

        # SI10: Macrophyte Cover (optional - site visit)
        if macrophyte_cover is not None:
            scores["macrophyte"] = self._score_macrophyte_cover(macrophyte_cover)
        else:
            scores["macrophyte"] = None  # Omitted if not provided

        # Overall HSI (weighted geometric mean)
        # Waterfowl and Fish are weighted x1.5 as the most significant variables.
        # All others weighted x1.0. Formula: product(score^weight) ^ (1/sum(weights))
        VARIABLE_WEIGHTS = {
            "geographic_location": 1.0,
            "pond_area":           1.0,
            "permanence":          1.0,
            "terrestrial_habitat": 1.0,
            "pond_count":          1.0,
            "shade":               1.0,
            "waterfowl":           1.5,
            "fish":                1.5,
            "water_quality":       1.0,
            "macrophyte":          1.0,
        }
        product = 1.0
        total_weight = 0.0
        for key, score in scores.items():
            if score is not None and score > 0:
                w = VARIABLE_WEIGHTS.get(key, 1.0)
                product *= score ** w
                total_weight += w
        scores["overall_hsi"] = product ** (1.0 / total_weight) if total_weight > 0 else 0.0

        return scores

    def _score_pond_area(self, area_m2):
        """Score pond area based on Oldham (2000) Figure 2.
        
        Scoring relationship:
        - 0-500m²:   Linear increase from 0 to 1.0 (optimal reached at 500m²)
        - 500-600m²: Plateau at 1.0
        - 600-2000m²: Gradual linear decrease from 1.0 to 0.8
        - >2000m²:   Variable omitted (no data available in Oldham 2000)
        
        Reference values:
        100m²=0.2, 200m²=0.4, 300m²=0.6, 400m²=0.8, 500m²=1.0,
        600m²=1.0, 800m²=0.97, 1000m²=0.94, 1200m²=0.91,
        1400m²=0.89, 1600m²=0.86, 1800m²=0.83, 2000m²=0.80
        """
        if area_m2 <= 0:
            return 0.01
        
        if area_m2 > 2000:
            # Omit variable for ponds >2000m² (no data in Oldham 2000)
            return None
        
        if area_m2 <= 500:
            # Linear increase: 0 at 0m², 1.0 at 500m²
            return area_m2 / 500.0
        elif area_m2 <= 600:
            # Plateau at 1.0 between 500-600m²
            return 1.0
        else:
            # Gradual linear decrease from 1.0 at 600m² to 0.8 at 2000m²
            # slope = (0.8 - 1.0) / (2000 - 600) = -0.0001429
            excess = area_m2 - 600
            score = 1.0 - (excess * 0.0001429)
            return max(score, 0.1)

    def _score_terrestrial_habitat(self, semi_natural_proportion):
        """Score terrestrial habitat quality based on Oldham (2000) Table criteria.
        
        Scoring based on proportion of semi-natural habitat within 250m:
        - Good     (1.0):  >75% semi-natural (rough grassland, scrub, woodland, etc.)
        - Moderate (0.67): 25-75% semi-natural
        - Poor     (0.33): <25% semi-natural (amenity grass, improved pasture, arable)
        - None     (0.01): No suitable habitat
        """
        if semi_natural_proportion > 0.75:
            return 1.0   # Good
        elif semi_natural_proportion >= 0.25:
            return 0.67  # Moderate
        elif semi_natural_proportion > 0.0:
            return 0.33  # Poor
        else:
            return 0.01  # None

    def _classify_habitat_type(self, habitat_type):
        """Classify a habitat type string as semi-natural (True) or poor structure (False).
        
        Primary lookup uses UKHab Level 3 labels (UKHab classification system).
        Falls back to keyword matching for non-standard or legacy habitat type values.
        
        Based on Oldham (2000) criteria:
        Semi-natural = habitats offering good foraging and shelter opportunities.
        Poor structure = habitats offering limited opportunities for foraging/shelter.
        """
        habitat_lower = habitat_type.lower().strip()

        # UKHab Level 3 explicit lookup (authoritative classification)
        UKHAB_L3 = {
            "acid grassland": True,
            "arable and horticulture": False,
            "bog": True,
            "broadleaved mixed and yew woodland": True,
            "built-up areas and gardens": False,
            "calcareous grassland": True,
            "coniferous woodland": True,
            "dense scrub": True,
            "dwarf shrub heath": True,
            "fen marsh and swamp": True,
            "hedgerows": True,
            "inland rock": True,
            "littoral rock": True,
            "littoral sediment": True,
            "neutral grassland": True,
            "rivers and streams": True,
            "standing open water and canals": True,
            "supralittoral rock": True,
            "supralittoral sediment": True,
        }

        if habitat_lower in UKHAB_L3:
            return UKHAB_L3[habitat_lower]

        # Fallback keyword matching for non-standard or legacy habitat type values
        SEMI_NATURAL_KEYWORDS = [
            "woodland", "wood", "broadleaved", "ancient wood",
            "scrub", "hedgerow", "hedge",
            "rough grassland", "unimproved grassland", "marshy grassland",
            "heath", "bog", "fen", "mire", "carr",
            "reedbed", "reed bed", "swamp", "marsh", "wetland",
            "brownfield", "previously developed",
            "traditional orchard", "orchard",
            "low intensity farm", "traditional farm",
            "semi-natural", "semi natural",
            "ruderal", "tall herb",
        ]

        POOR_STRUCTURE_KEYWORDS = [
            "modified grassland", "improved grassland", "improved pasture",
            "amenity grassland", "amenity grass", "mown grass", "lawn",
            "rye grass",
            "arable", "cultivated", "crop",
            "hard standing", "tarmac", "concrete", "pavement", "car park",
            "built", "building", "urban", "residential", "industrial",
            "bare ground", "bare soil", "spoil",
            "introduced shrub", "non-native",
        ]

        for keyword in POOR_STRUCTURE_KEYWORDS:
            if keyword in habitat_lower:
                return False

        for keyword in SEMI_NATURAL_KEYWORDS:
            if keyword in habitat_lower:
                return True

        # Default: treat unknown types as poor structure (conservative approach)
        arcpy.AddWarning(f"Unrecognised habitat type '{habitat_type}' - treated as poor structure.")
        return False

    def _score_macrophyte_cover(self, cover_percent):
        """Score macrophyte cover based on Oldham (2000) Figure.
        
        Scoring relationship (read from graph):
        - 0-75%:   Linear increase from 0.3 at 0% to 1.0 at 75% (optimal)
        - 75-100%: Linear decrease from 1.0 at 75% to 0.8 at 100%
        
        Estimate cover between March and end of September.
        Includes emergents, floating plants (excluding duckweed) and submerged plants.
        """
        if cover_percent <= 75:
            return 0.3 + (cover_percent / 75.0) * 0.7
        else:
            return 1.0 - ((cover_percent - 75) / 25.0) * 0.2

    def _score_pond_count(self, count):
        """Score pond count based on pond density per km².
        
        Calculates density as: count / π (ponds per km² within 1km radius)
        Then applies log-linear scoring from Oldham (2000) Figure 3.
        
        The graph shows a straight line on a log x-axis:
        - x range: 0.1 to ~5 ponds/km² (where score reaches 1.0)
        - y range: 0.1 to 1.0
        - Formula anchored at (0.1, 0.1) and (5, 1.0)
        
        Reference values (density -> score):
        0.1=0.1, 0.5=0.47, 1.0=0.63, 2.0=0.79, 5.0=1.0
        """
        if count <= 0:
            return 0.01
        
        # Calculate density: ponds per km² (1km radius = π km² area)
        density = count / math.pi
        
        if density >= 5:
            return 1.0
        elif density <= 0.1:
            return 0.1
        else:
            # Log-linear from (0.1, 0.1) to (5, 1.0)
            # score = 0.1 + 0.9 * (log10(density) - log10(0.1)) / (log10(5) - log10(0.1))
            # score = 0.1 + 0.9 * (log10(density) + 1) / (log10(5) + 1)
            score = 0.1 + 0.9 * (math.log10(density) + 1) / (math.log10(5) + 1)
            return min(max(score, 0.1), 1.0)

    def _score_shade(self, shade_percent):
        """Score shoreline shade based on percentage shaded.
        
        Scoring relationship:
        - 0-60% shade = 1.0 (optimal)
        - 60-100% shade = linear decrease from 1.0 to 0.2
        
        Reference values:
        0%=1.0, 60%=1.0, 80%=0.6, 100%=0.2
        """
        if shade_percent <= 60:
            return 1.0
        else:
            # Linear decrease from 1.0 at 60% to 0.2 at 100%
            # Slope = (0.2 - 1.0) / (100 - 60) = -0.02
            excess = shade_percent - 60
            score = 1.0 - (excess * 0.02)
            return max(score, 0.2)  # Floor at 0.2 for fully shaded ponds

    # ------------------------------------------------------------------
    # Export Methods
    # ------------------------------------------------------------------

    def _classify_hsi(self, hsi_score):
        """Classify overall HSI score into traffic light suitability class.

        Thresholds based on Oldham (2000) interpretation:
        - High  (Green):    HSI >= 0.68
        - Moderate (Amber): HSI 0.34 - 0.67
        - Low   (Red):      HSI < 0.34
        """
        if hsi_score >= 0.68:
            return "High"
        elif hsi_score >= 0.34:
            return "Moderate"
        return "Low"

    def _create_output_shapefile(self, output_shp_path, candidate_pond_path, all_results, assessment_mode, ordered_oids):
        """Create output shapefile from candidate pond geometry with HSI scores as attributes.

        all_results is a dict keyed by original feature OID.
        ordered_oids is a list of original OIDs in the same order features appear in candidate_pond_path.
        Positional matching is used because CopyFeatures renumbers OIDs in the output shapefile.
        ORIG_OID field stores the original ObjectID for cross-referencing back to the source data.
        HSI_CLASS field holds the traffic light classification (Low / Moderate / High).
        """
        arcpy.management.CopyFeatures(candidate_pond_path, output_shp_path)

        # Field definitions: (name, type, length)
        fields = [
            ("ORIG_OID",   "LONG",   None),
            ("HSI_SCORE",  "DOUBLE", None),
            ("VARS_USED",  "SHORT",  None),
            ("SI1_GEOG",   "DOUBLE", None),
            ("SI2_AREA",   "DOUBLE", None),
            ("SI3_PERM",   "DOUBLE", None),
            ("SI4_TERR",   "DOUBLE", None),
            ("SI5_COUNT",  "DOUBLE", None),
            ("SI6_SHADE",  "DOUBLE", None),
            ("SI7_WFOWL",  "DOUBLE", None),
            ("SI8_FISH",   "DOUBLE", None),
            ("SI9_WQ",     "DOUBLE", None),
            ("SI10_MACP",  "DOUBLE", None),
            ("HSI_CLASS",  "TEXT",   10),
            ("ASSESS_MD",  "TEXT",   25),
        ]
        for fname, ftype, flength in fields:
            if flength:
                arcpy.management.AddField(output_shp_path, fname, ftype, field_length=flength)
            else:
                arcpy.management.AddField(output_shp_path, fname, ftype)

        NOT_ASSESSED = -9999.0
        field_names = [f[0] for f in fields]

        # CopyFeatures renumbers OIDs in the output; use positional matching instead
        with arcpy.da.UpdateCursor(output_shp_path, field_names) as cursor:
            for i, row in enumerate(cursor):
                orig_oid = ordered_oids[i] if i < len(ordered_oids) else None
                scores   = all_results.get(orig_oid, {}) if orig_oid is not None else {}

                def _safe(key):
                    v = scores.get(key)
                    return round(v, 4) if v is not None else NOT_ASSESSED

                overall = scores.get("overall_hsi", 0.0) or 0.0
                row[0]  = orig_oid if orig_oid is not None else int(NOT_ASSESSED)
                row[1]  = round(overall, 4)
                row[2]  = int(scores.get("variables_used", 0))
                row[3]  = _safe("geographic_location")
                row[4]  = _safe("pond_area")
                row[5]  = _safe("permanence")
                row[6]  = _safe("terrestrial_habitat")
                row[7]  = _safe("pond_count")
                row[8]  = _safe("shade")
                row[9]  = _safe("waterfowl")
                row[10] = _safe("fish")
                row[11] = _safe("water_quality")
                row[12] = _safe("macrophyte")
                row[13] = self._classify_hsi(overall) if scores else "Unknown"
                row[14] = assessment_mode
                cursor.updateRow(row)

    def _apply_traffic_light_symbology(self, output_shp_path):
        """Add output shapefile to the active ArcGIS Pro map and apply traffic light symbology.

        Uses a UniqueValueRenderer on the HSI_CLASS field:
        - High     -> Green  (RGB 0, 176, 80)
        - Moderate -> Amber  (RGB 255, 165, 0)
        - Low      -> Red    (RGB 255, 0, 0)

        Falls back gracefully if no active map is available (e.g. running in background).
        """
        TRAFFIC_LIGHT_COLORS = {
            "High":     {"RGB": [0,   176,  80, 100]},
            "Moderate": {"RGB": [255, 165,   0, 100]},
            "Low":      {"RGB": [255,   0,   0, 100]},
        }
        TRAFFIC_LIGHT_LABELS = {
            "High":     "High Suitability (HSI \u2265 0.68)",
            "Moderate": "Moderate Suitability (0.34 \u2013 0.67)",
            "Low":      "Low Suitability (HSI < 0.34)",
        }
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if not active_map:
                arcpy.AddWarning(
                    "No active map found — shapefile created but symbology not applied. "
                    "Add the shapefile to a map and apply symbology manually using HSI_CLASS."
                )
                return

            lyr = active_map.addDataFromPath(output_shp_path)

            sym = lyr.symbology
            sym.updateRenderer("UniqueValueRenderer")
            sym.renderer.fields = ["HSI_CLASS"]
            lyr.symbology = sym

            sym = lyr.symbology
            for grp in sym.renderer.groups:
                for itm in grp.items:
                    cls_val = itm.values[0][0]
                    if cls_val in TRAFFIC_LIGHT_COLORS:
                        itm.symbol.color = TRAFFIC_LIGHT_COLORS[cls_val]
                        itm.label = TRAFFIC_LIGHT_LABELS[cls_val]
            lyr.symbology = sym
            lyr.name = "GCN HSI Result"

        except Exception as sym_err:
            arcpy.AddWarning(
                f"Symbology could not be applied automatically: {str(sym_err)}. "
                "The shapefile was created successfully — apply symbology manually using HSI_CLASS."
            )

    def postExecute(self, parameters):
        return


# ============================================================================
# STANDALONE EXECUTION (for testing)
# ============================================================================

if __name__ == "__main__":
    print("GCNHabitatSuitability module loaded successfully")
    print(f"Automated variables: {AUTOMATED_VARIABLES}/{TOTAL_HSI_VARIABLES}")
    print(f"Site visit required for: {', '.join(SITE_VISIT_VARIABLES)}")
