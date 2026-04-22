#!/usr/bin/env python3
"""
Process Kevin Freel property photos.

Reads source JPEGs from /Users/justinbabcock/Desktop/Websites/kevinfreel/images/_extracted/
Outputs WebP at 3 sizes into /Users/justinbabcock/Desktop/Websites/kevinfreel/images/properties/
Writes a manifest.json describing every photo.
"""
import json
import os
from pathlib import Path
from PIL import Image

SRC_ROOT = Path("/Users/justinbabcock/Desktop/Websites/kevinfreel/images/_extracted")
OUT_ROOT = Path("/Users/justinbabcock/Desktop/Websites/kevinfreel/images/properties")

# Size + quality presets
SIZES = [
    ("", 1920, 75),      # large
    ("-md", 1200, 72),   # medium
    ("-sm", 480, 70),    # thumbnail
]

# Selections per property. The source file is relative to the property subfolder.
# Each entry: (src_filename, output_basename, category, description)
PROPERTIES = [
    {
        "slug": "grandifloras",
        "name": "11 Grandifloras",
        "location": "Homosassa, FL",
        "description": "Sprawling Florida estate with saltwater pool and screened lanai, tucked into mature oaks and pines.",
        "src_folder": "11_Grandifloras_/11 Grandifloras ",
        "photos": [
            ("1.jpg",  "exterior-aerial-1", "aerial",   "Aerial view of the Grandifloras estate surrounded by mature forest and an expansive circular driveway."),
            ("50.jpg", "exterior-1",        "exterior", "Front elevation of the single-story estate with tile roof, arched entry and three-car garage."),
            ("5.jpg",  "detail-1",          "detail",   "Covered front entry with red shutters, patterned tile paving and intimate seating nook."),
            ("15.jpg", "living-1",          "interior", "Open great room with tray ceiling, built-in bookshelves and sliding glass doors to the pool."),
            ("25.jpg", "kitchen-1",         "kitchen",  "Eat-in kitchen with granite island, pendant lighting and sliders opening to the screened lanai."),
            ("10.jpg", "bedroom-1",         "bedroom",  "Generous primary suite with tray ceiling, sitting area and backyard-facing sliders."),
            ("35.jpg", "bedroom-2",         "bedroom",  "Bright guest bedroom with sliding doors leading to the pool patio and a paver deck."),
            ("45.jpg", "pool-1",            "outdoor",  "Screen-enclosed saltwater pool and spa with travertine decking, backing to private woods."),
            ("Grandifloras-17.jpg", "exterior-aerial-2", "aerial", "Overhead view of the estate's cul-de-sac setting surrounded by acres of preserved woodland."),
            ("Grandifloras-11.jpg", "exterior-2", "exterior", "Daytime front elevation with arched windows, red shutters and three-car garage."),
            ("Grandifloras-22.jpg", "interior-1", "interior", "Home office/library with built-in bookshelves, French doors and neutral decor."),
            ("Grandifloras-8.jpg",  "exterior-aerial-3", "aerial", "Zoomed aerial with locator pin showing the estate and its screened pool on the private lot."),
        ],
    },
    {
        "slug": "lemon",
        "name": "1206 W Lemon",
        "location": "Tampa, FL",
        "description": "Three new construction townhomes near downtown Tampa with designer kitchens, oak floors and open layouts.",
        "src_folder": "1206_W_Lemon/1206 W Lemon",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Three coastal-modern townhomes with blue and white siding and individual gated entries."),
            ("40.jpg", "exterior-aerial-1", "aerial",   "Aerial view of the townhomes with the downtown Tampa skyline in the background."),
            ("10.jpg", "kitchen-1",         "kitchen",  "Open chef's kitchen with white cabinetry, oversized island and stainless wall ovens."),
            ("2.jpg",  "interior-1",        "interior", "Bright entry and living area with white oak floors and abundant natural light."),
            ("5.jpg",  "bedroom-1",         "bedroom",  "Primary bedroom with ensuite bath and a view to the gold-accent vanity through the open doorway."),
            ("20.jpg", "bedroom-2",         "bedroom",  "Secondary bedroom with built-in closet and warm oak plank flooring."),
            ("15.jpg", "bathroom-1",        "bathroom", "Powder bath with arched mirror, quartz counter and matte black fixtures."),
            ("35.jpg", "exterior-2",       "exterior", "Angled street view of the townhome trio with blue-and-white siding and arching rooflines."),
            ("1206 W Lemon-39.jpg", "exterior-aerial-2", "aerial", "Lifted aerial view showing the townhomes with the downtown Tampa skyline as a backdrop."),
            ("30.jpg", "bedroom-3",        "bedroom",  "Spacious upstairs bedroom with three oversized windows, oak plank floors and fresh paint."),
            ("11.jpg", "kitchen-2",         "kitchen",  "Kitchen detail showing the waterfall island, natural wood cabinetry and pendant lighting."),
            ("25.jpg", "interior-2",        "interior", "Sunlit upstairs hallway with oak floors and open stair rail."),
        ],
    },
    {
        "slug": "coverdale",
        "name": "12861 Coverdale",
        "location": "Riverview, FL",
        "description": "Light-filled single-family home with vaulted ceilings in an established neighborhood near community amenities.",
        "src_folder": "12861_Coverdale/12861 Coverdale",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Classic white brick home with arched window, attached garage and welcoming front walkway."),
            ("12861 Coverdale-35.jpg", "exterior-2", "exterior", "Front elevation with young palm and fresh landscape island at the entry."),
            ("12861 Coverdale-36.jpg", "exterior-3", "exterior", "Straight-on view of the white brick facade, arched window and tile roofline."),
            ("31.jpg", "exterior-aerial-1", "aerial",   "Overhead aerial of the home and its tree-lined Riverview neighborhood."),
            ("33.jpg", "exterior-aerial-2", "aerial",   "High aerial showing the property's position within the subdivision near community parks."),
            ("12861 Coverdale-38.jpg", "exterior-aerial-3", "aerial", "Lower aerial showing the home's well-kept block and immediate surroundings."),
            ("25.jpg", "living-1",          "interior", "Vaulted-ceiling living and dining area with modern fan and tile flooring."),
            ("10.jpg", "kitchen-1",         "kitchen",  "Galley kitchen with stainless appliances, painted cabinets and natural light."),
            ("20.jpg", "bedroom-1",         "bedroom",  "Secondary bedroom currently used as a nursery with wood-look plank flooring."),
            ("12861 Coverdale-29.jpg", "outdoor-1", "outdoor", "Fenced side yard patio with covered area and access to the backyard."),
            ("12861 Coverdale-31.jpg", "outdoor-2", "outdoor", "Fully fenced backyard with concrete patio, perfect for families and play."),
            ("12861 Coverdale-32.jpg", "detail-1",  "detail",  "Covered front entry detail with hardy board siding and welcoming threshold."),
        ],
    },
    {
        "slug": "central",
        "name": "2204 N Central #1",
        "location": "Tampa, FL",
        "description": "Tampa Heights bungalow-style townhome with craftsman details, designer finishes and a covered front porch.",
        "src_folder": "2204_N_Central_1/2204 N Central #1",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Corner-lot craftsman townhome with white siding, wraparound porch and brick pavers."),
            ("42.jpg", "exterior-2",        "exterior", "Front elevation showing the covered porch, magnolia tree and picket fence."),
            ("2204 N Central #1-5.jpg", "exterior-3", "exterior", "Front view of the white craftsman townhome with mature trees framing the facade."),
            ("2204 N Central #1-6.jpg", "exterior-4", "exterior", "Secondary-angle exterior showing the symmetrical porch and entry columns."),
            ("18.jpg", "living-1",          "interior", "Open living room with modern ceiling fan, oak floors and double French doors to the porch."),
            ("10.jpg", "kitchen-1",         "kitchen",  "Chef's kitchen with waterfall island, lantern pendants and arabesque tile backsplash."),
            ("2204 N Central #1-38.jpg", "kitchen-2", "kitchen", "Alternate kitchen view showing the dark island, gold chair accents and range hood."),
            ("35.jpg", "outdoor-1",         "outdoor",  "Charming covered porch strung with Edison lights overlooking a private artificial-turf yard."),
            ("25.jpg", "interior-1",        "interior", "Spacious walk-in closet with custom shelving, drawers and shoe storage."),
            ("5.jpg",  "bathroom-1",        "bathroom", "Powder bath with circular gold mirror, navy vanity and modern towel ring."),
            ("2204 N Central #1-48.jpg", "exterior-aerial-1", "aerial", "Aerial view of the townhome in its tree-lined Tampa Heights neighborhood."),
            ("2204 N Central #1-49.jpg", "exterior-aerial-2", "aerial", "Aerial showing the home's proximity to downtown Tampa on the horizon."),
        ],
    },
    {
        "slug": "frances",
        "name": "418 W Frances",
        "location": "Tampa, FL",
        "description": "Newly built modern farmhouse in Tampa Heights with designer kitchen, wide-plank oak floors and soaring ceilings.",
        "src_folder": "418_W_Frances/418 W Frances",
        "photos": [
            ("1.jpg",   "exterior-1",        "exterior", "Modern farmhouse facade in sage green stucco and white siding with dramatic black-framed windows."),
            ("30.jpg",  "exterior-2",        "exterior", "Front elevation showing the fresh sod, twin palms and contrast-color siding."),
            ("Drone2.jpg", "exterior-aerial-1", "aerial", "Drone view of 418 W Frances with the Tampa skyline visible beyond the Hillsborough River."),
            ("418 W Frances-2.jpg",  "exterior-3", "exterior", "Secondary front view of the sage-and-white farmhouse framed by a live oak."),
            ("5.jpg",   "kitchen-1",         "kitchen",  "Two-story open kitchen with quartz island, industrial pendants, wall ovens and statement hood."),
            ("418 W Frances-11.jpg", "kitchen-2",  "kitchen",  "Kitchen detail showing the dramatic calacatta quartz island and dome pendants by the stairs."),
            ("10.jpg",  "living-1",          "interior", "Sunlit living room with oversized windows, oak plank flooring and modern front door."),
            ("15.jpg",  "interior-1",        "interior", "Upstairs landing with modern black-and-oak staircase and open-concept floor plan."),
            ("20.jpg",  "bathroom-1",        "bathroom", "Primary bath with double quartz vanity, matte-black fixtures and frameless glass shower."),
            ("418 W Frances-17.jpg", "bedroom-1",  "bedroom",  "Secondary bedroom with oak plank floors and side-by-side closet doors."),
            ("418 W Frances-19.jpg", "bedroom-2",  "bedroom",  "Bedroom with ensuite bath visible through the open door."),
            ("418 W Frances-28.jpg", "bedroom-3",  "bedroom",  "Primary bedroom entry showing closet, ensuite bath and coordinated finishes."),
        ],
    },
    {
        "slug": "12th-ave",
        "name": "419 12th Ave",
        "location": "Indian Rocks Beach, FL",
        "description": "Waterfront Florida cottage on a protected bayou with dock, open layout and tropical curb appeal.",
        "src_folder": "419_12th_Ave/419 12th Ave",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Coastal cottage with mature palms, breeze-block facade detail and manicured lawn."),
            ("40.jpg", "exterior-aerial-1", "aerial",   "Aerial view showing the home's waterfront setting on a protected bayou with Intracoastal access."),
            ("10.jpg", "exterior-2",        "exterior", "Street-level angle showing the expansive front yard, attached garage and palm-lined entrance."),
            ("20.jpg", "kitchen-1",         "kitchen",  "Bright kitchen with quartz island and large windows framing the waterfront view."),
            ("15.jpg", "living-1",          "interior", "Open living room with tile floors and sliding doors leading to the waterfront patio."),
            ("30.jpg", "bedroom-1",         "bedroom",  "Sunlit bedroom with dual banks of windows and a clean, neutral palette."),
            ("25.jpg", "bathroom-1",        "bathroom", "Updated bathroom with floating vanity, gold accents and tile accent wall."),
            ("35.jpg", "outdoor-1",         "outdoor",  "Private dock with boat lift overlooking the tranquil bayou with distant neighborhood homes."),
            ("419 12th-3.jpg", "exterior-aerial-2", "aerial", "Lower aerial of the property and its private dock on a protected Intracoastal cove."),
            ("419 12th-8.jpg", "exterior-aerial-3", "aerial", "Golden-hour aerial showing the home's cul-de-sac waterfront location with panoramic water views."),
            ("419 12th-10.jpg", "exterior-3", "exterior", "Angled view of the front yard and driveway flanked by mature palms and tropical foliage."),
            ("419 12th-13.jpg", "detail-1",   "detail",   "Tropical landscaping detail with lush palms and the home's soft coastal palette."),
        ],
    },
    {
        "slug": "1st-st",
        "name": "724 1st St",
        "location": "Indian Rocks Beach, FL",
        "description": "Mid-century beachside bungalow compound with breeze-block walls, multiple units and coastal charm.",
        "src_folder": "724_1st_St/724 1st St",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Front view of the mid-century bungalow complex with white breeze-block screens and arched entries."),
            ("25.jpg", "exterior-2",        "exterior", "Interior courtyard view between the two bungalow units with turquoise chairs and palms."),
            ("47.jpg", "outdoor-1",         "outdoor",  "Shared gravel courtyard with tropical palms and coral-colored front doors."),
            ("40.jpg", "exterior-3",        "exterior", "Side angle of the rear bungalow unit with fresh asphalt driveway and mature palm."),
            ("724 1st-2.jpg", "exterior-aerial-1", "aerial", "Aerial view of the compound showing proximity to the Gulf of Mexico and beach community."),
            ("10.jpg", "kitchen-1",         "kitchen",  "Updated kitchen with white shaker cabinets, stainless appliances and exterior door to the yard."),
            ("15.jpg", "living-1",          "interior", "Bright open living space with luxury vinyl plank floors and fresh neutral paint."),
            ("5.jpg",  "bedroom-1",         "bedroom",  "Comfortable bedroom with oversized window and plank floors."),
            ("27.jpg", "detail-2",          "detail",   "Coral-painted entry doors framed by breeze-block screens and palms."),
            ("724 1st-14.jpg", "interior-1", "interior", "Second unit interior showing open living and kitchen area with uniform finishes."),
            ("724 1st-34.jpg", "detail-1",   "detail",   "Iconic breeze-block pattern detail that defines the compound's mid-century character."),
            ("724 1st-7.jpg", "exterior-aerial-2", "aerial", "Overhead aerial of the compound outlined in red, steps from the Gulf beach and Intracoastal."),
        ],
    },
    {
        "slug": "morton",
        "name": "7307 S Morton",
        "location": "Tampa, FL",
        "description": "Two-story South Tampa pool home with open kitchen, screened lanai and fenced yard.",
        "src_folder": "7307_S_Morton/7307 S Morton",
        "photos": [
            ("1.jpg",  "exterior-1",        "exterior", "Two-story stucco home with peaked roofline, two-car garage and welcoming front walkway."),
            ("36.jpg", "exterior-2",        "exterior", "Front elevation with paver driveway, tropical landscaping and inviting covered entry."),
            ("7307 S Morton-4.jpg",  "exterior-3", "exterior", "Close-in exterior view showcasing the home's stucco facade and mature tropical plantings."),
            ("10.jpg", "kitchen-1",         "kitchen",  "Bright kitchen with granite counters, globe pendants and stainless appliances."),
            ("7307 S Morton-19.jpg", "kitchen-2", "kitchen", "Staged dining nook overlooking the kitchen with globe chandelier and proteas centerpiece."),
            ("18.jpg", "living-1",          "interior", "Cozy flex room with sectional seating, large windows and a modern ceiling fan."),
            ("25.jpg", "interior-1",        "interior", "Walk-in primary closet with custom built-in shelving and drawers."),
            ("7307 S Morton-33.jpg", "bedroom-1", "bedroom", "Primary bedroom with tray ceiling, plush carpet and soft natural light."),
            ("32.jpg", "outdoor-1",         "outdoor",  "Screened covered lanai with ceiling fan, string lights and a built-in bench."),
            ("35.jpg", "outdoor-2",         "outdoor",  "Spacious fenced backyard with mature oaks and direct patio access."),
            ("7307 S Morton-37.jpg", "outdoor-3", "outdoor", "View from the screened porch overlooking the fenced backyard and neighbor homes."),
            ("33.jpg", "detail-1",          "detail",   "Side yard with paver walkway leading from the patio to the fenced backyard."),
        ],
    },
    {
        "slug": "willow",
        "name": "905 N Willow",
        "location": "Tampa, FL",
        "description": "Two-story new construction home in Tampa's North Hyde Park with open chef's kitchen and luxury finishes.",
        "src_folder": "905_N_Willow/905 N Willow",
        "photos": [
            ("44.jpeg", "exterior-twilight-1", "exterior", "Stunning twilight shot of the modern farmhouse with warm interior glow and paver driveway."),
            ("1.jpg",   "exterior-1",          "exterior", "Daytime front elevation with white board-and-batten siding, second-story balcony and two-car garage."),
            ("43.jpg",  "exterior-2",          "exterior", "Rear view of the home showing the gable profile, fresh landscaping and privacy fencing."),
            ("10.jpg",  "kitchen-1",           "kitchen",  "Open chef's kitchen with waterfall quartz island, globe pendants and statement range hood."),
            ("905 N Willow-14.jpg", "kitchen-2", "kitchen", "Chef's kitchen detail with herringbone tile backsplash, gas range and stainless hood."),
            ("905 N Willow-16.jpg", "living-1", "interior", "Great room with large sliders and open sight lines to the kitchen and dining area."),
            ("20.jpg",  "bedroom-1",           "bedroom",  "Spacious primary suite with tray ceiling and oak-look plank floors."),
            ("905 N Willow-36.jpg", "bedroom-2", "bedroom", "Primary bedroom with tray ceiling, floating oak shelves and ensuite access."),
            ("5.jpg",   "bedroom-3",           "bedroom",  "Secondary bedroom with oversized picture window, transom and fresh oak floors."),
            ("905 N Willow-4.jpg",  "bedroom-4", "bedroom", "Compact bedroom with dual windows framing palm and sky views."),
            ("30.jpg",  "bathroom-1",          "bathroom", "Spa-like primary bath with dual vanity, matte-black fixtures and abundant natural light."),
            ("40.jpg",  "outdoor-1",           "outdoor",  "Covered back patio with paver deck and shaded ceiling fan overlooking the private backyard."),
        ],
    },
]


def process_photo(src_path: Path, out_dir: Path, basename: str) -> dict:
    """Resize and save a single photo at 3 sizes. Returns byte sizes for each."""
    img = Image.open(src_path)
    # Use RGB (drop alpha if any) for JPEG-sourced WebP output
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    src_w, src_h = img.size
    sizes = {}
    for suffix, target_w, quality in SIZES:
        # preserve aspect ratio
        ratio = target_w / src_w
        new_w = target_w
        new_h = int(round(src_h * ratio))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        out_path = out_dir / f"{basename}{suffix}.webp"
        resized.save(out_path, "WEBP", quality=quality, method=6)
        sizes[suffix or "lg"] = out_path.stat().st_size
    return sizes


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = {"properties": []}
    total_bytes = 0
    total_photos = 0
    property_counts = {}

    for prop in PROPERTIES:
        out_dir = OUT_ROOT / prop["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)

        src_folder = SRC_ROOT / prop["src_folder"]
        photos_meta = []
        processed = 0

        for src_name, out_name, category, desc in prop["photos"]:
            src = src_folder / src_name
            if not src.exists():
                print(f"  MISSING: {src}")
                continue
            sizes = process_photo(src, out_dir, out_name)
            photos_meta.append({
                "file": out_name,
                "category": category,
                "description": desc,
            })
            for b in sizes.values():
                total_bytes += b
            processed += 1
            total_photos += 1

        property_counts[prop["slug"]] = processed
        manifest["properties"].append({
            "slug": prop["slug"],
            "name": prop["name"],
            "location": prop["location"],
            "description": prop["description"],
            "photos": photos_meta,
        })
        print(f"[{prop['slug']}] processed {processed} photos")

    # Write manifest
    manifest_path = OUT_ROOT / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n=== SUMMARY ===")
    print(f"Total photos: {total_photos}")
    print(f"Total output size: {total_bytes / (1024*1024):.1f} MB ({total_bytes:,} bytes)")
    for slug, count in property_counts.items():
        print(f"  {slug}: {count} photos")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
