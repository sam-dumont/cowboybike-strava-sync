import lxml.etree
from dateutil import parser
from datetime import timedelta
import os

WATTS_FILTER = int(os.getenv("WATTS_FILTER", 1100))


def add_trackpoint(source, start_time, seconds, latlng, distance, power):
    trackpoint = lxml.etree.SubElement(source, "Trackpoint")
    lxml.etree.SubElement(trackpoint, "Time").text = str(
        (start_time + timedelta(seconds=seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )
    if latlng is not None:
        position = lxml.etree.SubElement(trackpoint, "Position")
        lxml.etree.SubElement(position, "LatitudeDegrees").text = str(
            latlng[0]
        )
        lxml.etree.SubElement(position, "LongitudeDegrees").text = str(
            latlng[1]
        )
    lxml.etree.SubElement(trackpoint, "DistanceMeters").text = str(distance)
    extensions = lxml.etree.SubElement(trackpoint, "Extensions")
    tpx = lxml.etree.SubElement(
        extensions,
        "{http://www.garmin.com/xmlschemas/ActivityExtension/v2}TPX",
    )
    lxml.etree.SubElement(
        tpx,
        "{http://www.garmin.com/xmlschemas/ActivityExtension/v2}Watts",
    ).text = (
        str(power) if (power is not None and power < WATTS_FILTER) else "0"
    )


def create_tcx(activity_source, charts_source):

    start_time = parser.parse(activity_source["started_at"])

    attr_qname = lxml.etree.QName(
        "http://www.w3.org/2001/XMLSchema-instance", "schemaLocation"
    )
    nsmap = {
        None: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "up2": "http://www.garmin.com/xmlschemas/UserProfile/v2",
        "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    doc = lxml.etree.Element(
        "TrainingCenterDatabase",
        {
            attr_qname: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd http://www.garmin.com/xmlschemas/UserProfile/v2 https://www8.garmin.com/xmlschemas/UserProfileExtensionv2.xsd http://www.garmin.com/xmlschemas/ActivityExtension/v2 https://www8.garmin.com/xmlschemas/ActivityExtensionv2.xsd"
        },
        nsmap=nsmap,
    )

    attr_qname = lxml.etree.QName(
        "http://www.w3.org/2001/XMLSchema-instance", "type"
    )
    author = lxml.etree.SubElement(
        doc,
        "Author",
        {attr_qname: "Application_t"},
    )
    lxml.etree.SubElement(author, "Name").text = "Cowboy for Strava"
    lxml.etree.SubElement(author, "LangID").text = "en"
    lxml.etree.SubElement(author, "PartNumber").text = "123-4567"
    build = lxml.etree.SubElement(author, "Build")
    version = lxml.etree.SubElement(build, "Version")
    lxml.etree.SubElement(version, "VersionMajor").text = "1"
    lxml.etree.SubElement(version, "VersionMinor").text = "0"
    lxml.etree.SubElement(version, "BuildMajor").text = "0"
    lxml.etree.SubElement(version, "BuildMinor").text = "0"

    activities = lxml.etree.SubElement(doc, "Activities")
    activity = lxml.etree.SubElement(activities, "Activity", Sport="Biking")
    lxml.etree.SubElement(activity, "Id").text = start_time.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    lxml.etree.SubElement(activity, "Notes").text = activity_source["title"]

    creator = lxml.etree.SubElement(
        activity, "Creator", {attr_qname: "Device_t"}
    )
    lxml.etree.SubElement(creator, "Name").text = "Cowboy for Strava"
    lxml.etree.SubElement(creator, "UnitId").text = "0"
    lxml.etree.SubElement(creator, "ProductID").text = "0"
    versionc = lxml.etree.SubElement(creator, "Version")
    lxml.etree.SubElement(versionc, "VersionMajor").text = "1"
    lxml.etree.SubElement(versionc, "VersionMinor").text = "0"
    lxml.etree.SubElement(versionc, "BuildMajor").text = "0"
    lxml.etree.SubElement(versionc, "BuildMinor").text = "0"

    lap = lxml.etree.SubElement(
        activity, "Lap", StartTime=start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    lxml.etree.SubElement(lap, "TriggerMethod").text = "Manual"
    lxml.etree.SubElement(lap, "TotalTimeSeconds").text = str(
        activity_source["unlocked_time"]
    )
    lxml.etree.SubElement(lap, "DistanceMeters").text = str(
        round(activity_source["distance"] * 1000, 3)
    )
    track = lxml.etree.SubElement(lap, "Track")

    add_trackpoint(
        track,
        start_time,
        0,
        [
            charts_source["positions"][0],
            charts_source["distances"][0],
        ],
        0,
        0,
    )

    for index, point in enumerate(charts_source["durations"]):
        if charts_source["distances"][index] is not None:
            add_trackpoint(
                track,
                start_time,
                point,
                charts_source["positions"][index],
                charts_source["distances"][index],
                charts_source["charts"]["user_power"]["data"][index],
            )

    add_trackpoint(
        track,
        start_time,
        0,
        [
            charts_source["positions"][-1],
            charts_source["distances"][-1],
        ],
        len(charts_source["positions"]) + 1,
        0,
    )

    return lxml.etree.ElementTree(doc)
