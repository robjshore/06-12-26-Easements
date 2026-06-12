#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_easements.py
==================
Generates EASEMENTS.md -- a LOSSLESS, structured representation of the
Galleria Schedule 'A' easements, organised as a parcel relationship matrix
(servient x dominant) with full drill-down detail (including every enumerated
"use") preserved for each easement.

Design:
  * Source of truth = the EASEMENTS list below (one record per easement).
  * Long boilerplate that repeats verbatim across easements is canonicalised
    ONCE (utility sub-systems + standard provisos) and referenced by id, with
    every project-specific VARIATION captured explicitly -> still lossless.
  * The matrix and register are DERIVED from the records so counts cannot drift.
  * A rubric (assert_rubric) gates "done": the build fails loudly if any check
    fails. Convergence = all checks pass.

Run:  python3 build_easements.py   ->  writes EASEMENTS.md  + prints rubric report
"""

import json
import sys
from collections import defaultdict, OrderedDict

# ---------------------------------------------------------------------------
# 1. PARCELS (the matrix axes / graph nodes)
# ---------------------------------------------------------------------------
PARCELS = OrderedDict([
    ("RC",  {"name": "RESIDENTIAL CONDO LANDS",
             "parts": "PARTS 1 to 30 inclusive on Reference Plan 66R-35145",
             "legal": "City of Toronto, part of Lot 10, Registered Plan 61-York",
             "pin": "21313-0704(LT)"}),
    ("PK",  {"name": "PARKING LANDS",
             "parts": "PARTS 31 to 39 inclusive on Reference Plan 66R-35145",
             "legal": "City of Toronto, part of Lot 10, Registered Plan 61-York",
             "pin": "21313-0704(LT)"}),
    ("CM",  {"name": "COMMERCIAL LANDS",
             "parts": "PARTS 40 to 50 inclusive on Reference Plan 66R-35145",
             "legal": "City of Toronto, part of Lot 10, Registered Plan 61-York",
             "pin": "21313-0704(LT)"}),
    ("B13", {"name": "BLOCKS 1 AND 3 LANDS",
             "parts": ("PARTS 7, 10, 11, 12, 31, 32, 50, 51, 60 and 63 on Reference Plan "
                       "66R-30758 (save and except PARTS 3, 4, 5, 8 to 13 incl., 16 to 21 incl., "
                       "23, 24, 27 to 30 incl., 33, 34, 35, 48, 49 and 50 on Reference Plan 66R-35145)"),
             "legal": ("City of Toronto, part of Lot 10, Registered Plan 61-York and part of "
                       "Lots 3 and 14 and all of Lot 15, Plan M-567"),
             "pin": "21313-0704(LT)"}),
    # External / third-party nodes (dominant only):
    ("CITY",     {"name": "City of Toronto", "external": True}),
    ("ROGERS",   {"name": "Rogers Communications Inc.", "external": True}),
    ("ENBRIDGE", {"name": "Enbridge Gas Distribution Inc.", "external": True}),
    ("ADJ",      {"name": "Adjacent lands (Lot 3 Plan M-567 / Lot 10 RP 61-York)", "external": True}),
])

# ---------------------------------------------------------------------------
# 2. PURPOSE CATEGORIES (matrix cell colour / legend)
# ---------------------------------------------------------------------------
PURPOSES = OrderedDict([
    ("ACCESS",     "Access & servicing"),
    ("CONSTR",     "Construction & facilitation"),
    ("UTIL",       "Utilities & services"),
    ("SUPPORT",    "Structural support"),
    ("EGRESS",     "Emergency pedestrian egress"),
    ("CIRC",       "Circulation (pedestrian / vehicular)"),
    ("WASTE",      "Waste, loading & deliveries"),
    ("SIGN",       "Signage / parking meters"),
    ("TEMPCON",    "Temporary construction works"),
    ("AMENITY",    "Amenity (bicycle parking)"),
    ("THIRDPARTY", "Third-party / municipal utility"),
    ("REGISTERED", "Pre-existing registered easement"),
])

# ---------------------------------------------------------------------------
# 3. CANONICAL UTILITY SUB-SYSTEMS  (the enumerated "uses" for UTIL easements)
#    Captured verbatim ONCE; per-easement additions recorded as deltas.
# ---------------------------------------------------------------------------
SYSTEMS = OrderedDict([
    ("fresh_air", ("Fresh air intake systems",
        "connection cables, conduits, ducts, pipes, fans, shafts, wires, generators or other "
        "installations; for free flow and supply of fresh air and ventilation, in/on/along/across/"
        "through such systems and all stairwells")),
    ("exhaust", ("Air exhaust systems",
        "connection cables, conduits, ducts, pipes, fans, shafts, wires, generators or other "
        "installations; for free flow of air exhaustion and ventilation")),
    ("telecom", ("Telecommunications systems",
        "telephone, television, internet and cable duct banks, fibre optics, cable trays, security "
        "cameras, sensors, servers, connection cables, conduits, ducts, pipes, fans, shafts, wires, "
        "generators or other installations and all communication rooms")),
    ("life_safety", ("Life safety systems",
        "fire protection systems, fire sprinkler systems, fire suppression systems, fire alarm "
        "devices, automatic transfer switches, connection cables, conduits, ducts, pipes, fans, "
        "shafts, wires, generators or other installations and all Central Alarm and Control "
        "Facility (CACF) rooms")),
    ("electrical", ("Electrical systems",
        "transformers, meters, connection cables, conduits, ducts, pipes, fans, shafts, wires, "
        "generators or other installations and all electrical rooms")),
    ("mechanical", ("Mechanical systems",
        "window washing equipment, elevator systems, waste management, garbage, refuse disposal "
        "and recycling systems, connection cables, conduits, ducts, pipes, fans, shafts, wires, "
        "generators or other installations and all mechanical and elevator machine rooms")),
    ("water", ("Water, sanitary, storm and gas systems",
        "watermain systems and pumps, sanitary and storm drainage systems, stormwater management "
        "storage facilities, stormwater tanks, jellyfish stormwater treatment filtration systems, "
        "stormwater management chambers, stormceptors, irrigation/water reuse systems, oil grit "
        "separators, gas systems, plumbing systems and private water (foundation drain); "
        "groundwater pumping sampling ports, groundwater discharge pipes, groundwater pumps, storm "
        "pumps, filter cartridges, filtration devices, flow meters, sampling access points and "
        "ports, sanitary discharge meters, test ports, sensors, utility check meters, sump pumps "
        "and pits, inspection chambers, cisterns, trenches, drains, siamese connections, "
        "waterproofing membranes, gas lines, gas meters and regulating stations, meters, "
        "connection cables, conduits, ducts, pipes, fans, shafts, wires, generators or other "
        "installations and all utilities rooms")),
    ("heating_cooling", ("Heating and cooling systems",
        "HVAC (heating, ventilation and air conditioning) systems, chillers, insulation systems, "
        "air handling units and make-up air units, geothermal exchange systems, heat pumps, base "
        "building loops, condensers, boilers, connection cables, conduits, ducts, pipes, fans, "
        "shafts, wires, generators or other installations and all chiller rooms, boiler rooms, "
        "pump rooms and cooling towers")),
])
ALL_SYSTEMS = list(SYSTEMS.keys())

# ---------------------------------------------------------------------------
# 4. CANONICAL PROVISOS  (the repeated conditions; lossless by reference)
# ---------------------------------------------------------------------------
PROVISOS = OrderedDict([
    ("NOTICE", "Reasonable advance written notice to the servient owner (reason, day, time of "
               "entry); except emergencies, exercisable without advance notice."),
    ("NO_INTERFERE", "Entry/work must not materially interfere with the construction, location "
                     "and use of the servient buildings/improvements."),
    ("NO_STRUCT", "Must not impair in any manner the structural integrity of the servient buildings."),
    ("INTERRUPT", "Subject to reasonable interruption from time to time for maintenance, repair, "
                  "construction and reconstruction of the servient lands."),
    ("SECURITY", "Subject to the servient owner's reasonable requirements from time to time, "
                 "including security requirements."),
    ("BUSINESS", "Must not materially interfere with the day-to-day operations of the business(es) "
                 "and uses operating within the servient lands."),
    ("CLEARANCE", "Minimum 2.1 m clearance from the underside of systems/installations to be "
                  "maintained near parking spaces, ramps and drive aisles."),
])

# Common termination triggers (temporary easements):
TERM_RAMP = ("Terminates upon completion of construction of the permanent underground garage "
             "ramp(s) to be situated within the BLOCKS 1 AND 3 LANDS.")
TERM_20YR = ("Terminates on the earlier of: (i) 20 years after registration; or (ii) completion "
             "of construction of the said buildings, structures and appurtenant services within "
             "the BLOCKS 1 AND 3 LANDS.")

# Shared verbatim "use" fragments reused across access/construction easements:
ACCESS_USE = ("Access of persons, vehicles, materials and equipment for servicing, maintenance, "
              "repair, operation, construction and reconstruction of the buildings, structures, "
              "improvements, utilities and services; including works for retaining walls, street "
              "lighting, water, sanitary sewer, storm sewer outfall, rain barrels, structural "
              "support grading, noise attenuation works, acoustic fencing, parking, low impact "
              "development features and amenity areas, with all appurtenances.")
CONSTR_USE = ("Construction, installation, repair, placement, replacement, maintenance, service "
              "and inspection of all parts of the buildings, utilities and services, installations, "
              "signage, landscaping features and appurtenances; including crossing, penetrating, "
              "boring and travelling onto/through any transfer slab, floor slab, ceiling slab, "
              "concrete, concrete block and masonry wall and/or drywall enclosure, expansion "
              "joints, exterior precast concrete, bollard guards, windows and other similar "
              "construction materials/installations.")
SUPPORT_USE = ("Maintaining support from and by the structural members, slabs, pillars, columns, "
               "footings, foundations, side and cross beams, supporting walls and the soil which "
               "support the buildings, installations and appurtenances of the dominant lands.")
EGRESS_USE = ("Emergency pedestrian egress in and through the exit stairwells and corridors of "
              "the servient buildings.")
VEH_LIST = ("emergency vehicles, construction vehicles, service vehicles, garbage and recycling "
            "collection vehicles, garbage tractor, equipment, materials, machinery and personnel")

# ---------------------------------------------------------------------------
# 5. EASEMENT RECORDS  (the data -- one dict per easement, fully detailed)
#    cat: SUBJECT TO (third-party burden) / RESERVING (RC burden to project parcel)
#         / TOGETHER (RC benefit over project parcel) / GRANT (registered)
# ---------------------------------------------------------------------------
def util(systems_full=True, deltas=None):
    """Helper to build the UTIL 'detail' payload."""
    return {"systems": ALL_SYSTEMS if systems_full else [], "deltas": deltas or {}}

EASEMENTS = [
    # ---- SUBJECT TO : burdens on RC in favour of third parties ----
    dict(id="S1", cat="SUBJECT TO", servient="RC", dominant="CITY", purpose="THIRDPARTY",
         summary="Municipal easement (City of Toronto)",
         parts="PARTS 5, 6, 7, 13 to 16 incl. and 21 on RP 66R-35145", levels=None,
         duration="permanent", termination=None, instrument="WH69572", status="registered",
         required=False, provisos=[],
         detail="Easement in favour of The Corporation of the City of Toronto (no purpose "
                "specified in Schedule A; per Instrument No. WH69572)."),
    dict(id="S2", cat="SUBJECT TO", servient="RC", dominant="ROGERS", purpose="THIRDPARTY",
         summary="Rogers telecommunications easement",
         parts="whole of RC", levels=None, duration="permanent", termination=None,
         instrument="ATXXXXXXX [new Rogers]", status="placeholder", required=False, provisos=[],
         detail="Easement in favour of Rogers Communications Inc. Instrument number not yet "
                "assigned (placeholder ATXXXXXXX)."),
    dict(id="S3", cat="SUBJECT TO", servient="RC", dominant="ENBRIDGE", purpose="THIRDPARTY",
         summary="Enbridge gas easement",
         parts="whole of RC", levels=None, duration="permanent", termination=None,
         instrument="ATXXXXXXX [Enbridge]", status="placeholder", required=False, provisos=[],
         detail="Easement in favour of Enbridge Gas Distribution Inc. Instrument number not yet "
                "assigned (placeholder ATXXXXXXX)."),
    dict(id="S4", cat="SUBJECT TO", servient="RC", dominant="CITY", purpose="SUPPORT",
         summary="City support easement — Pedestrian Mews A",
         parts="PARTS 8, 12 and 13 on RP 66R-35145", levels=None, duration="permanent",
         termination=None, instrument="ATXXXXXXX [support for Pedestrian Mews A]",
         status="placeholder", required=False, provisos=[],
         detail="Easement in favour of the City of Toronto for support for Pedestrian Mews A. "
                "Instrument number not yet assigned."),
    dict(id="S5", cat="SUBJECT TO", servient="RC", dominant="CITY", purpose="SUPPORT",
         summary="City support easement — Private Street A",
         parts="PARTS 11, 16, 17, 18, 19, 27, 28 and 29 on RP 66R-35145", levels=None,
         duration="permanent", termination=None,
         instrument="ATXXXXXXX [support for Private Street A]", status="placeholder",
         required=False, provisos=[],
         detail="Easement in favour of the City of Toronto for support for Private Street A. "
                "Instrument number not yet assigned."),

    # ================= RESERVING/SUBJECT TO : RC burdened, in favour of PARKING =================
    dict(id="R-PK-1", cat="RESERVING", servient="RC", dominant="PK", purpose="ACCESS",
         summary="Access & servicing for Parking improvements",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"], detail=ACCESS_USE),
    dict(id="R-PK-2", cat="RESERVING", servient="RC", dominant="PK", purpose="CONSTR",
         summary="Construction & facilitation for Parking",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"], detail=CONSTR_USE),
    dict(id="R-PK-3", cat="RESERVING", servient="RC", dominant="PK", purpose="UTIL",
         summary="Utilities & services for Parking (8 systems)",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Accessing/locating/constructing/installing/maintaining/operating/altering/"
                "expanding/repairing/testing/replacing/removing/inspecting/connecting to "
                "utilities & services; plus crossing/penetrating/boring/travelling through slabs "
                "and walls. Enumerated systems below.",
         util=util(True, {})),
    dict(id="R-PK-4", cat="RESERVING", servient="RC", dominant="PK", purpose="SUPPORT",
         summary="Structural support for Parking",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=SUPPORT_USE),
    dict(id="R-PK-5", cat="RESERVING", servient="RC", dominant="PK", purpose="EGRESS",
         summary="Emergency pedestrian egress for Parking",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=EGRESS_USE),
    dict(id="R-PK-6", cat="RESERVING", servient="RC", dominant="PK", purpose="CIRC",
         summary="Pedestrian/vehicular ingress-egress at grade for Parking",
         parts="common elements", levels="Level 1", duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical vehicular (" + VEH_LIST + ") ingress and egress "
                "in/over/along the at-grade driveways and designated at-grade exterior walkways; "
                "including for transporting goods and materials."),
    dict(id="R-PK-7", cat="RESERVING", servient="RC", dominant="PK", purpose="TEMPCON",
         summary="TEMP underground garage ramp access for Parking",
         parts="PART 22 on RP 66R-35145", levels=None, duration="temporary",
         termination=TERM_RAMP, instrument=None, status="proposed", required=True,
         provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress in/over/along the temporary underground garage ramp; "
                "including transporting goods and materials. Marked 'REQUIRED?' in source."),
    dict(id="R-PK-8", cat="RESERVING", servient="RC", dominant="PK", purpose="SIGN",
         summary="Directional signage / parking meters for Parking",
         parts="common elements", levels="Levels 1 and A", duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT", "SECURITY"],
         detail="Access to, installation, attachment, placement, inspection, maintenance, repair "
                "and replacement of directional signage and/or parking meters, including "
                "appurtenant wires and cables."),

    # ================= RESERVING : RC burdened, in favour of COMMERCIAL =================
    dict(id="R-CM-1", cat="RESERVING", servient="RC", dominant="CM", purpose="ACCESS",
         summary="Access & servicing for Commercial improvements",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=ACCESS_USE + " VARIATION: list expressly includes windows and canopies."),
    dict(id="R-CM-2", cat="RESERVING", servient="RC", dominant="CM", purpose="CONSTR",
         summary="Construction & facilitation for Commercial",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=CONSTR_USE + " VARIATION: expressly includes any windows and canopies."),
    dict(id="R-CM-3", cat="RESERVING", servient="RC", dominant="CM", purpose="UTIL",
         summary="Utilities & services for Commercial (8 systems)",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Utilities & services for the Commercial Lands (full powers as R-PK-3).",
         util=util(True, {
             "exhaust": "adds kitchen exhaust ducts and vents",
             "mechanical": "adds grease/oil interceptors and traps",
             "heating_cooling": "adds refrigeration condensers/compressors and processing "
                                "equipment systems; chillers (on the ceiling of the P1 floor)"})),
    dict(id="R-CM-4", cat="RESERVING", servient="RC", dominant="CM", purpose="SUPPORT",
         summary="Structural support for Commercial",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=SUPPORT_USE),
    dict(id="R-CM-5", cat="RESERVING", servient="RC", dominant="CM", purpose="EGRESS",
         summary="Emergency pedestrian egress for Commercial",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=EGRESS_USE),
    dict(id="R-CM-6", cat="RESERVING", servient="RC", dominant="CM", purpose="CIRC",
         summary="Pedestrian ingress-egress for Commercial",
         parts="common elements", levels="Levels 1 and 2", duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian ingress and egress in/over/along the designated at-grade exterior "
                "walkways, exit stairwells, corridors and vestibules; including for transporting "
                "goods and materials."),
    dict(id="R-CM-7", cat="RESERVING", servient="RC", dominant="CM", purpose="WASTE",
         summary="Waste/recycling circulation for Commercial",
         parts="common elements", levels="Levels 1 and A", duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical vehicular (" + VEH_LIST + ") ingress and egress "
                "in/over/along the at-grade driveways, designated at-grade exterior walkways, "
                "underground garage drive aisles, underground garage walkways, corridors and "
                "vestibules; for transporting garbage, recycling materials, organics, oversized "
                "refuse and containers to and from the shared at-grade loading area and the "
                "commercial waste rooms located on the P1 floor."),
    dict(id="R-CM-8", cat="RESERVING", servient="RC", dominant="CM", purpose="TEMPCON",
         summary="TEMP underground garage ramp access for Commercial",
         parts="PART 22 on RP 66R-35145", levels=None, duration="temporary", termination=TERM_RAMP,
         instrument=None, status="proposed", required=True, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress along the temporary underground garage ramp; for transporting "
                "goods and materials, and garbage, recycling materials, organics, oversized refuse "
                "and containers to/from the shared at-grade loading area and commercial waste "
                "rooms on P1. Marked 'REQUIRED?' in source."),
    dict(id="R-CM-9", cat="RESERVING", servient="RC", dominant="CM", purpose="CIRC",
         summary="Access for leasehold improvements / building systems (Commercial)",
         parts="common elements", levels="Levels 1, 2 and A", duration="permanent",
         termination=None, instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT", "CLEARANCE"],
         detail="Pedestrian and where practical vehicular (construction vehicles, service "
                "vehicles, equipment, materials, machinery and personnel) ingress/egress to "
                "facilitate, effect, inspect, repair, maintain, service, replace, alter, operate, "
                "construct and install leasehold improvements, equipment and systems serving the "
                "building — including new HVAC equipment, condensers and appurtenances, "
                "utilities and services (plumbing, drainage, electrical, ducting, gas lines, "
                "heating and sprinklers) and mechanical systems (fire prevention, suppression and "
                "control); plus crossing/penetrating/boring through slabs and walls. Min. 2.1 m "
                "clearance near parking spaces, ramps and drive aisles."),
    dict(id="R-CM-10", cat="RESERVING", servient="RC", dominant="CM", purpose="SIGN",
         summary="Signage for Commercial",
         parts="common elements", levels="Levels 1, 2 and A", duration="permanent",
         termination=None, instrument=None, status="proposed", required=True,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT", "SECURITY"],
         detail="Access to, installation, attachment, placement, inspection, maintenance, repair "
                "and replacement of signage, including appurtenant wires and cables. Marked "
                "'REQUIRED?' in source."),

    # ================= RESERVING : RC burdened, in favour of BLOCKS 1 & 3 =================
    dict(id="R-B13-1", cat="RESERVING", servient="RC", dominant="B13", purpose="ACCESS",
         summary="Access & servicing for Blocks 1 & 3",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=True,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=ACCESS_USE + " Marked 'REQUIRED?' in source."),
    dict(id="R-B13-2", cat="RESERVING", servient="RC", dominant="B13", purpose="CONSTR",
         summary="Construction & facilitation for Blocks 1 & 3",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=True,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=CONSTR_USE + " Marked 'REQUIRED?' in source."),
    dict(id="R-B13-3", cat="RESERVING", servient="RC", dominant="B13", purpose="UTIL",
         summary="Utilities & services for Blocks 1 & 3 (8 systems)",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Utilities & services for the Blocks 1 & 3 Lands (full powers as R-PK-3).",
         util=util(True, {
             "exhaust": "adds kitchen exhaust ducts and vents",
             "mechanical": "adds swimming pool equipment; grease/oil interceptors and traps",
             "heating_cooling": "adds refrigeration condensers/compressors and processing "
                                "equipment systems; chillers (on the ceiling of the P1 floor)"})),
    dict(id="R-B13-4", cat="RESERVING", servient="RC", dominant="B13", purpose="SUPPORT",
         summary="Structural support for Blocks 1 & 3",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=True, provisos=[],
         detail=SUPPORT_USE + " Marked 'REQUIRED?' in source."),
    dict(id="R-B13-5", cat="RESERVING", servient="RC", dominant="B13", purpose="EGRESS",
         summary="Emergency pedestrian egress for Blocks 1 & 3",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=True, provisos=[],
         detail=EGRESS_USE + " Marked 'REQUIRED?' in source."),
    dict(id="R-B13-6", cat="RESERVING", servient="RC", dominant="B13", purpose="TEMPCON",
         summary="TEMP construction ingress/egress for Blocks 1 & 3",
         parts="common elements", levels=None, duration="temporary", termination=TERM_20YR,
         instrument=None, status="proposed", required=True, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (emergency, construction, "
                "service vehicles, equipment, materials, machinery and personnel) ingress and "
                "egress to facilitate construction of the buildings, structures and appurtenant "
                "services within Blocks 1 & 3. Marked 'REQUIRED?' in source."),
    dict(id="R-B13-7", cat="RESERVING", servient="RC", dominant="B13", purpose="TEMPCON",
         summary="Shoring / caissons / tie-backs for Blocks 1 & 3",
         parts="common elements", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=True, provisos=[],
         detail="Installation, attachment and maintenance of (including) caissons, shoring, "
                "underpinnings, piles and tie-backs, where practical, within the RC Lands. "
                "Marked 'REQUIRED?' in source."),
    dict(id="R-B13-8", cat="RESERVING", servient="RC", dominant="B13", purpose="TEMPCON",
         summary="TEMP crane swing for Blocks 1 & 3",
         parts="common elements", levels=None, duration="temporary", termination=TERM_20YR,
         instrument=None, status="proposed", required=True, provisos=["INTERRUPT"],
         detail="Permit the overhead swing of one or more construction cranes to facilitate "
                "construction of the buildings, structures and appurtenant services within "
                "Blocks 1 & 3. Marked 'REQUIRED?' in source."),
    dict(id="R-B13-9", cat="RESERVING", servient="RC", dominant="B13", purpose="TEMPCON",
         summary="TEMP excavation / fill / storage for Blocks 1 & 3",
         parts="common elements", levels=None, duration="temporary", termination=TERM_20YR,
         instrument=None, status="proposed", required=True, provisos=["INTERRUPT"],
         detail="Excavating, backfilling, removing, replacing fill and topsoil, hard or soft "
                "landscaping, and undertaking any other works — including temporary storage "
                "or placement of construction equipment and materials — within the RC Lands "
                "to facilitate construction within Blocks 1 & 3. Marked 'REQUIRED?' in source."),
    dict(id="R-B13-10", cat="RESERVING", servient="RC", dominant="B13", purpose="TEMPCON",
         summary="TEMP hoarding / fencing / marketing signage for Blocks 1 & 3",
         parts="common elements", levels=None, duration="temporary", termination=TERM_20YR,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Installation, attachment and maintenance of (including) hoarding fencing, "
                "hoarding, overhead hoarding, signage, marketing signage, fencing and rakers, "
                "where practical, within the RC Lands, to facilitate construction within "
                "Blocks 1 & 3."),

    # ===================== GRANT (registered, benefiting RC) =====================
    dict(id="T-ADJ", cat="GRANT", servient="ADJ", dominant="RC", purpose="REGISTERED",
         summary="Registered easement benefiting RC (AT6888184)",
         parts="PARTS 3, 44 and 53 on RP 66R-30758 (save & except PART 1 on RP 66R-34663)",
         levels=None, duration="permanent", termination=None, instrument="AT6888184",
         status="registered", required=False, provisos=[],
         detail="Easement over part of Lot 3 Plan M-567 and part of Lot 10 RP 61-York in favour "
                "of the RESIDENTIAL CONDO LANDS, per Instrument No. AT6888184."),

    # ================= TOGETHER WITH : RC benefits over PARKING =================
    dict(id="T-PK-1", cat="TOGETHER", servient="PK", dominant="RC", purpose="ACCESS",
         summary="Access & servicing over Parking (for RC)",
         parts="whole of PK", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=ACCESS_USE),
    dict(id="T-PK-2", cat="TOGETHER", servient="PK", dominant="RC", purpose="CONSTR",
         summary="Construction & facilitation over Parking (for RC)",
         parts="whole of PK", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=CONSTR_USE),
    dict(id="T-PK-3", cat="TOGETHER", servient="PK", dominant="RC", purpose="UTIL",
         summary="Utilities & services over Parking (for RC) (8 systems)",
         parts="whole of PK", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Utilities & services benefiting the RC Lands (full powers as R-PK-3).",
         util=util(True, {"mechanical": "adds swimming pool equipment"})),
    dict(id="T-PK-4", cat="TOGETHER", servient="PK", dominant="RC", purpose="SUPPORT",
         summary="Structural support over Parking (for RC)",
         parts="whole of PK", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=SUPPORT_USE),
    dict(id="T-PK-5", cat="TOGETHER", servient="PK", dominant="RC", purpose="EGRESS",
         summary="Emergency pedestrian egress over Parking (for RC)",
         parts="whole of PK", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[],
         detail="Emergency pedestrian egress in and through the exit stairwells and corridors of "
                "the buildings within the PARKING LANDS."),
    dict(id="T-PK-6", cat="TOGETHER", servient="PK", dominant="RC", purpose="WASTE",
         summary="Circulation & waste over Parking (for RC)",
         parts="PARTS 31, 33, 34, 35 and 39 on RP 66R-35145", levels=None, duration="permanent",
         termination=None, instrument=None, status="proposed", required=False,
         provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress along the designated at-grade exterior walkway, underground "
                "garage drive aisles, underground garage walkways, underground garage exit "
                "stairwell, corridors and vestibules; for transporting goods and materials, and "
                "garbage, recycling materials, organics, oversized refuse and containers to/from "
                "the shared service elevator."),
    dict(id="T-PK-7", cat="TOGETHER", servient="PK", dominant="RC", purpose="TEMPCON",
         summary="TEMP underground garage ramp over Parking (for RC)",
         parts="PARTS 32 and 36 on RP 66R-35145", levels=None, duration="temporary",
         termination=TERM_RAMP, instrument=None, status="proposed", required=False,
         provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress along the temporary underground garage ramp; for transporting "
                "goods and materials, and garbage, recycling materials, organics, oversized refuse "
                "and containers to/from the shared at-grade loading area."),

    # ================= TOGETHER WITH : RC benefits over COMMERCIAL =================
    dict(id="T-CM-1", cat="TOGETHER", servient="CM", dominant="RC", purpose="ACCESS",
         summary="Access & servicing over Commercial (for RC)",
         parts="whole of CM", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=ACCESS_USE),
    dict(id="T-CM-2", cat="TOGETHER", servient="CM", dominant="RC", purpose="CONSTR",
         summary="Construction & facilitation over Commercial (for RC)",
         parts="whole of CM", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=CONSTR_USE),
    dict(id="T-CM-3", cat="TOGETHER", servient="CM", dominant="RC", purpose="UTIL",
         summary="Utilities & services over Commercial (for RC) (8 systems)",
         parts="whole of CM", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Utilities & services benefiting the RC Lands (full powers as R-PK-3).",
         util=util(True, {"mechanical": "adds swimming pool equipment"})),
    dict(id="T-CM-4", cat="TOGETHER", servient="CM", dominant="RC", purpose="SUPPORT",
         summary="Structural support over Commercial (for RC)",
         parts="whole of CM", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=SUPPORT_USE),
    dict(id="T-CM-5", cat="TOGETHER", servient="CM", dominant="RC", purpose="EGRESS",
         summary="Emergency pedestrian egress over Commercial (for RC)",
         parts="whole of CM", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[],
         detail="Emergency pedestrian egress in and through the exit stairwells and corridors of "
                "the buildings within the COMMERCIAL LANDS."),
    dict(id="T-CM-6", cat="TOGETHER", servient="CM", dominant="RC", purpose="WASTE",
         summary="Circulation, waste & moving over Commercial (for RC)",
         parts="PART 41 on RP 66R-35145", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian (and where practical equipment, materials, machinery and personnel) "
                "ingress and egress along the designated at-grade exterior walkways, shared "
                "service corridors, exit stairwell, moving room, holding area and service "
                "elevator; for transporting garbage, recycling materials, organics, oversized "
                "refuse and containers and/or to facilitate moving and deliveries to/from the "
                "shared at-grade loading area."),
    dict(id="T-CM-7", cat="TOGETHER", servient="CM", dominant="RC", purpose="WASTE",
         summary="At-grade loading & staging area use over Commercial (for RC)",
         parts="PART 42 on RP 66R-35145", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Access to and use of the designated at-grade loading area and staging area "
                "(loading spaces, loading facilities, refuse collection areas, refuse/recycling "
                "storage areas); pedestrian and where practical vehicular ingress/egress for "
                "on-loading, off-loading, temporary storage and truck access for garbage, "
                "recycling, organics, oversized refuse and containers and/or moving and "
                "deliveries. RESTRICTIONS: no parking or storage of refuse outside the designated "
                "area except short-term on pick-up days; temporary parking permitted in the "
                "loading area on a short-term basis for moving/deliveries; subject to interruption "
                "for the Commercial owner's own garbage/recycling collection parking."),
    dict(id="T-CM-8", cat="TOGETHER", servient="CM", dominant="RC", purpose="TEMPCON",
         summary="TEMP underground garage ramp over Commercial (for RC)",
         parts="PART 43 on RP 66R-35145", levels=None, duration="temporary", termination=TERM_RAMP,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress along the temporary underground garage ramp; for transporting "
                "goods and materials, and garbage, recycling materials, organics, oversized refuse "
                "and containers to/from the shared at-grade loading area."),
    dict(id="T-CM-9", cat="TOGETHER", servient="CM", dominant="RC", purpose="CIRC",
         summary="Pedestrian circulation over Commercial (for RC)",
         parts="PARTS 44 and 50 on RP 66R-35145", levels=None, duration="permanent",
         termination=None, instrument=None, status="proposed", required=False,
         provisos=["INTERRUPT"],
         detail="Pedestrian (and where practical equipment, materials, machinery and personnel) "
                "ingress and egress along the designated at-grade exterior walkways, underground "
                "garage exit stairwell, corridor and vestibules; for transporting goods and "
                "materials."),

    # ================= TOGETHER WITH : RC benefits over BLOCKS 1 & 3 =================
    dict(id="T-B13-1", cat="TOGETHER", servient="B13", dominant="RC", purpose="ACCESS",
         summary="Access & servicing over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=ACCESS_USE),
    dict(id="T-B13-2", cat="TOGETHER", servient="B13", dominant="RC", purpose="CONSTR",
         summary="Construction & facilitation over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail=CONSTR_USE),
    dict(id="T-B13-3", cat="TOGETHER", servient="B13", dominant="RC", purpose="UTIL",
         summary="Utilities & services over Blocks 1 & 3 (for RC) (8 systems)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False,
         provisos=["NOTICE", "SECURITY", "BUSINESS", "NO_INTERFERE", "NO_STRUCT", "INTERRUPT"],
         detail="Utilities & services benefiting the RC Lands (full powers as R-PK-3).",
         util=util(True, {"mechanical": "adds swimming pool equipment"})),
    dict(id="T-B13-4", cat="TOGETHER", servient="B13", dominant="RC", purpose="SUPPORT",
         summary="Structural support over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[], detail=SUPPORT_USE),
    dict(id="T-B13-5", cat="TOGETHER", servient="B13", dominant="RC", purpose="EGRESS",
         summary="Emergency pedestrian egress over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=[],
         detail="Emergency pedestrian egress in and through the exit stairwells and corridors of "
                "the buildings within the BLOCKS 1 AND 3 LANDS."),
    dict(id="T-B13-6", cat="TOGETHER", servient="B13", dominant="RC", purpose="CIRC",
         summary="Vehicular/pedestrian access to parking garage over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Pedestrian and where practical all manner of vehicular (" + VEH_LIST + ") "
                "ingress and egress along the at-grade driveways, designated at-grade exterior "
                "walkways, underground garage ramps, underground garage drive aisles, underground "
                "garage walkways, underground garage exit stairwells, walkways, corridors and "
                "vestibules; as necessary for access to/from the underground parking garage "
                "within the RC Lands; including transporting goods and materials, and garbage, "
                "recycling materials, organics, oversized refuse and containers to/from the shared "
                "at-grade loading area (PART 42 on RP 66R-35145)."),
    dict(id="T-B13-7", cat="TOGETHER", servient="B13", dominant="RC", purpose="AMENITY",
         summary="Shared at-grade bicycle parking over Blocks 1 & 3 (for RC)",
         parts="whole of B13", levels=None, duration="permanent", termination=None,
         instrument=None, status="proposed", required=False, provisos=["INTERRUPT"],
         detail="Access to and use of the designated shared at-grade bicycle parking spaces."),
]

# ---------------------------------------------------------------------------
# 6. RUBRIC  (convergence gate -- build fails if any assertion fails)
# ---------------------------------------------------------------------------
def assert_rubric(records):
    report = []
    def check(name, cond, info=""):
        report.append((name, bool(cond), info))
        return bool(cond)

    ids = [r["id"] for r in records]
    check("unique ids", len(ids) == len(set(ids)), f"{len(ids)} ids")
    check("parcels valid", all(r["servient"] in PARCELS and r["dominant"] in PARCELS for r in records))
    check("purposes valid", all(r["purpose"] in PURPOSES for r in records))
    check("provisos valid", all(all(p in PROVISOS for p in r["provisos"]) for r in records))
    check("duration valid", all(r["duration"] in ("permanent", "temporary") for r in records))
    check("temporary has termination",
          all(r["termination"] for r in records if r["duration"] == "temporary"))
    check("util records carry systems",
          all("util" in r for r in records if r["purpose"] == "UTIL"))
    check("util deltas reference real systems",
          all(all(k in SYSTEMS for k in r.get("util", {}).get("deltas", {}))
              for r in records if r["purpose"] == "UTIL"))
    check("status values valid",
          all(r["status"] in ("registered", "placeholder", "proposed") for r in records))
    # Section counts (sanity vs. source document)
    n_subject = sum(1 for r in records if r["cat"] == "SUBJECT TO")
    n_reserve = sum(1 for r in records if r["cat"] == "RESERVING")
    n_together = sum(1 for r in records if r["cat"] == "TOGETHER")
    n_grant = sum(1 for r in records if r["cat"] == "GRANT")
    check("SUBJECT TO count == 5", n_subject == 5, str(n_subject))
    check("RESERVING count == 28", n_reserve == 28, str(n_reserve))
    check("TOGETHER count == 23", n_together == 23, str(n_together))
    check("GRANT count == 1", n_grant == 1, str(n_grant))
    check("total == 57", len(records) == 57, str(len(records)))
    n_required = sum(1 for r in records if r["required"])
    check("REQUIRED? flags == 11", n_required == 11, str(n_required))
    n_placeholder = sum(1 for r in records if r["status"] == "placeholder")
    check("placeholder instruments == 4", n_placeholder == 4, str(n_placeholder))
    check("every record has non-empty detail", all(r["detail"].strip() for r in records))

    ok = all(p for _, p, _ in report)
    return ok, report


# ---------------------------------------------------------------------------
# 7. MARKDOWN GENERATION
# ---------------------------------------------------------------------------
def md_escape(s):
    return s.replace("|", "\\|") if s else s

def cat_label(cat):
    return {"SUBJECT TO": "Subject To (burden → third party)",
            "RESERVING": "Reserving / Subject To (RC burden → project parcel)",
            "TOGETHER": "Together With (benefit to RC)",
            "GRANT": "Granted (registered)"}.get(cat, cat)

def build_markdown(records):
    L = []
    A = L.append
    A("# Galleria Schedule 'A' — Easement Relationship Matrix")
    A("")
    A("> **Source:** `75052279-20068_Preliminary_Sch_A_May2826.docx` (Preliminary Schedule 'A', "
      "McMillan LLP / Galleria Developments Inc.).  ")
    A("> **Purpose of this artifact:** a *lossless*, structured map of every easement — every "
      "parcel relationship and every enumerated use — organised as a servient × dominant "
      "matrix for use as the basis of a visualization aid.  ")
    A("> **Generated by** `build_easements.py` (do not hand-edit; edit the data + regenerate).")
    A("")
    A("---")
    A("")

    # --- Legend: parcels ---
    A("## 1. Parcels (matrix axes / nodes)")
    A("")
    A("| Code | Parcel | Component parts | Legal description | P.I.N. |")
    A("|------|--------|-----------------|-------------------|--------|")
    for code, p in PARCELS.items():
        if p.get("external"):
            A(f"| `{code}` | {md_escape(p['name'])} | — (external party) | — | — |")
        else:
            A(f"| `{code}` | {md_escape(p['name'])} | {md_escape(p['parts'])} | "
              f"{md_escape(p['legal'])} | {p['pin']} |")
    A("")

    # --- Legend: purpose categories ---
    A("## 2. Purpose categories (matrix cell legend)")
    A("")
    A("| Code | Purpose |")
    A("|------|---------|")
    for code, label in PURPOSES.items():
        A(f"| `{code}` | {label} |")
    A("")

    # --- THE MATRIX (counts) ---
    A("## 3. Relationship matrix — counts (servient ↓ × dominant →)")
    A("")
    A("Each cell = number of easements where the **row parcel is burdened (servient)** in favour "
      "of the **column parcel (dominant)**. Click through to Section 6 for full detail.")
    A("")
    doms = [c for c in PARCELS]
    # restrict columns to those actually used as dominant
    used_dom = [c for c in doms if any(r["dominant"] == c for r in records)]
    used_serv = [c for c in doms if any(r["servient"] == c for r in records)]
    header = "| servient \\ dominant | " + " | ".join(f"**{c}**" for c in used_dom) + " | **Total** |"
    sep = "|" + "---|" * (len(used_dom) + 2)
    A(header)
    A(sep)
    grid = defaultdict(lambda: defaultdict(int))
    for r in records:
        grid[r["servient"]][r["dominant"]] += 1
    coltot = defaultdict(int)
    for s in used_serv:
        row = [f"**{s}**"]
        rowtot = 0
        for d in used_dom:
            n = grid[s][d]
            rowtot += n
            coltot[d] += n
            row.append(str(n) if n else "·")
        row.append(f"**{rowtot}**")
        A("| " + " | ".join(row) + " |")
    tot_row = ["**Total**"] + [f"**{coltot[d]}**" for d in used_dom] + [f"**{len(records)}**"]
    A("| " + " | ".join(tot_row) + " |")
    A("")

    # --- THE MATRIX (purpose codes) ---
    A("## 4. Relationship matrix — purposes (servient ↓ × dominant →)")
    A("")
    A("Each cell lists the **purpose categories** present for that relationship (see Section 2). "
      "A `*` marks a cell containing one or more easements flagged **REQUIRED?** in the source; "
      "a `°` marks one or more **temporary** easements.")
    A("")
    A(header)
    A(sep)
    cellmap = defaultdict(lambda: defaultdict(list))
    for r in records:
        cellmap[r["servient"]][r["dominant"]].append(r)
    for s in used_serv:
        row = [f"**{s}**"]
        for d in used_dom:
            rs = cellmap[s][d]
            if not rs:
                row.append("·")
                continue
            codes = []
            seen = set()
            for r in rs:
                c = r["purpose"]
                mark = ""
                if r["required"]:
                    mark += "*"
                if r["duration"] == "temporary":
                    mark += "°"
                tag = c + mark
                if tag not in seen:
                    seen.add(tag)
                    codes.append(tag)
            row.append("<br>".join(codes))
        A("| " + " | ".join(row) + " |")
    A("")
    A("Legend: `*` = contains a REQUIRED?-flagged easement · `°` = contains a temporary easement.")
    A("")

    # --- Open items dashboard ---
    A("## 5. Open items (data-quality flags)")
    A("")
    A("### 5a. Easements flagged `REQUIRED?` in the source (need confirmation)")
    A("")
    A("| ID | Burden on → benefit of | Purpose | Summary |")
    A("|----|----------------------|---------|---------|")
    for r in records:
        if r["required"]:
            A(f"| `{r['id']}` | {r['servient']} → {r['dominant']} | {r['purpose']} | "
              f"{md_escape(r['summary'])} |")
    A("")
    A("### 5b. Placeholder / unassigned instrument numbers")
    A("")
    A("| ID | Beneficiary | Instrument |")
    A("|----|-------------|------------|")
    for r in records:
        if r["status"] == "placeholder":
            A(f"| `{r['id']}` | {PARCELS[r['dominant']]['name']} | {md_escape(r['instrument'])} |")
    A("")

    # --- Full register (lossless drill-down) ---
    A("## 6. Full easement register (lossless detail)")
    A("")
    A("Grouped by relationship. Every record preserves all source detail: scope (parts), levels, "
      "duration, termination trigger, instrument/status, REQUIRED? flag, the full enumerated use, "
      "and applicable provisos (Section 7).")
    A("")
    # group by (servient, dominant)
    groups = OrderedDict()
    for r in records:
        groups.setdefault((r["servient"], r["dominant"]), []).append(r)
    for (s, d), rs in groups.items():
        A(f"### {s} → {d} &nbsp; "
          f"<sub>{md_escape(PARCELS[s]['name'])} burdened, in favour of "
          f"{md_escape(PARCELS[d]['name'])}</sub>")
        A("")
        for r in rs:
            flags = []
            if r["required"]:
                flags.append("**REQUIRED?**")
            if r["duration"] == "temporary":
                flags.append("_temporary_")
            if r["status"] == "registered":
                flags.append("_registered_")
            if r["status"] == "placeholder":
                flags.append("_instrument TBD_")
            flagstr = ("  — " + " · ".join(flags)) if flags else ""
            A(f"#### `{r['id']}` · {PURPOSES[r['purpose']]} — {md_escape(r['summary'])}{flagstr}")
            A("")
            A(f"- **Category:** {cat_label(r['cat'])}")
            A(f"- **Scope:** {md_escape(r['parts'])}" + (f" · **Levels:** {r['levels']}" if r["levels"] else ""))
            A(f"- **Duration:** {r['duration']}" + (f" — {md_escape(r['termination'])}" if r["termination"] else ""))
            if r["instrument"]:
                A(f"- **Instrument:** {md_escape(r['instrument'])} ({r['status']})")
            A(f"- **Use:** {md_escape(r['detail'])}")
            if r["purpose"] == "UTIL" and "util" in r:
                A(f"- **Enumerated systems:**")
                deltas = r["util"]["deltas"]
                for key in r["util"]["systems"]:
                    title, _ = SYSTEMS[key]
                    extra = f" — _{deltas[key]}_" if key in deltas else ""
                    A(f"    - {title}{extra}")
            if r["provisos"]:
                A(f"- **Provisos:** {', '.join(r['provisos'])} (see Section 7)")
            A("")

    # --- Appendix: systems ---
    A("## 7. Appendices (canonical reference — captured once, lossless)")
    A("")
    A("### 7a. Utility sub-systems (full component inventory)")
    A("")
    A("Every `UTIL` easement grants powers over the following eight systems. Project-specific "
      "**additions** for particular parcels are noted inline in Section 6.")
    A("")
    for key, (title, body) in SYSTEMS.items():
        A(f"- **{title}** (`{key}`): {body}.")
    A("")
    A("### 7b. Standard provisos (conditions attached to easements)")
    A("")
    A("| Code | Proviso |")
    A("|------|---------|")
    for code, text in PROVISOS.items():
        A(f"| `{code}` | {text} |")
    A("")
    A("### 7c. Standard termination triggers (temporary easements)")
    A("")
    A(f"- **Ramp trigger:** {TERM_RAMP}")
    A(f"- **20-year trigger:** {TERM_20YR}")
    A("")

    # --- Machine-readable data block ---
    A("## 8. Machine-readable data (for the visualization tool)")
    A("")
    A("```json")
    payload = {
        "parcels": {k: {kk: vv for kk, vv in v.items()} for k, v in PARCELS.items()},
        "purposes": dict(PURPOSES),
        "provisos": dict(PROVISOS),
        "systems": {k: {"title": t, "components": b} for k, (t, b) in SYSTEMS.items()},
        "easements": records,
    }
    A(json.dumps(payload, indent=2, ensure_ascii=False))
    A("```")
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
def main():
    ok, report = assert_rubric(EASEMENTS)
    print("=" * 64)
    print("RUBRIC REPORT")
    print("=" * 64)
    for name, passed, info in report:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}" + (f"  ({info})" if info else ""))
    print("=" * 64)
    if not ok:
        print("RUBRIC FAILED — not converged. EASEMENTS.md not written.")
        sys.exit(1)
    md = build_markdown(EASEMENTS)
    with open("EASEMENTS.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(f"CONVERGED — all checks pass. Wrote EASEMENTS.md ({len(md):,} chars, "
          f"{len(EASEMENTS)} easements).")


if __name__ == "__main__":
    main()
