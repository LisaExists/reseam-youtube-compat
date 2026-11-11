#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply the YouTube compatibility overlay to a verified Reseam patches checkout."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape, unescape

OLD_DARK = '''    legacyColors = listOf("yt_black0", "yt_black1", "yt_black2", "yt_black3", "yt_black1_opacity98"),
'''
NEW_DARK = '''    legacyColors = listOf(
        "yt_black0",
        "yt_black1",
        "yt_black1_opacity95",
        "yt_black1_opacity98",
        "yt_black2",
        "yt_black3",
        "yt_black4",
        "yt_status_bar_background_dark",
        "material_grey_850",
        "yt_sys_color_baseline_dark_menu_background",
        "yt_sys_color_baseline_dark_static_black",
        "yt_sys_color_baseline_dark_raised_background",
        "yt_sys_color_baseline_dark_base_background",
        // YouTube 21.06+ mobile surfaces used by 21.23.492.
        "yt_sys_color_baseline_mobile_dark_default_base_background",
        "yt_sys_color_baseline_mobile_dark_default_raised_background",
        // Default/cooler palette aliases used by the same generation.
        "yt_ref_color_constants_default_baseline_black_black1",
        "yt_ref_color_constants_default_baseline_black_black3",
        "yt_ref_color_constants_cooler_baseline_black_black3",
        "yt_sys_color_baseline_light_inverted_background",
        "yt_sys_color_baseline_light_static_black",
    ),
'''

OLD_LIGHT = '''    legacyColors = listOf("yt_white1", "yt_white2", "yt_white1_opacity98"),
'''
NEW_LIGHT = '''    legacyColors = listOf(
        "yt_white1",
        "yt_white1_opacity95",
        "yt_white1_opacity98",
        "yt_white2",
        "yt_white3",
        "yt_white4",
        "yt_sys_color_baseline_light_base_background",
        "yt_sys_color_baseline_light_raised_background",
        "yt_sys_color_baseline_mobile_light_default_base_background",
        "yt_sys_color_baseline_mobile_light_default_raised_background",
        "yt_ref_color_constants_default_baseline_white_white3",
        "yt_ref_color_constants_cooler_baseline_white_white3",
        "yt_sys_color_baseline_light_menu_background",
    ),
'''

OLD_GUARD = '''                if (paletteStyles.isEmpty()) background.legacyColors.forEach { resources.addColor(it, "@color/${background.color}") }
'''
NEW_GUARD = '''                // Some releases contain palette styles but still read legacy colors in other surfaces.
                // Apply both sets instead of treating palette support as an all-or-nothing switch.
                background.legacyColors.forEach { resources.addColor(it, "@color/${background.color}") }
'''

OLD_DARK_RUNTIME = '''    DARK(
        "reseam_theme_dark_background",
'''
NEW_DARK_RUNTIME = '''    // The legacy resource is present in older supported YouTube builds and is explicitly
    // overridden by the Theme patch below. Resolve through it for old Litho color constants.
    DARK(
        "yt_black1",
'''
OLD_LIGHT_RUNTIME = '''    LIGHT("reseam_theme_light_background", 0xFFFFFFFF.toInt(), 0xFFF9F9F9.toInt(), 0xFAFFFFFF.toInt());
'''
NEW_LIGHT_RUNTIME = '''    LIGHT("yt_white1", 0xFFFFFFFF.toInt(), 0xFFF9F9F9.toInt(), 0xFAFFFFFF.toInt());
'''

OLD_DIALOG = '''fun dialogBackgroundColor(context: Context): Int {
    val surface = themeColor(context, "yt_sys_color_baseline_menu_background")
        ?: if (isDarkMode(context)) appColor(context, "yt_black1", Color.BLACK) else appColor(context, "yt_white1", Color.WHITE)
    // Lift pure black so the dialog remains visible on the AMOLED theme.
    return if (surface == Color.BLACK) 0xFF080808.toInt() else surface
}
'''
NEW_DIALOG = '''fun dialogBackgroundColor(context: Context): Int {
    if (!isDarkMode(context)) return appColor(context, "yt_white1", Color.WHITE)
    val dark = appColor(context, "yt_black1", Color.BLACK)
    // Preserve Reseam's slight dialog lift when the selected dark background is pure black.
    return if (dark == Color.BLACK) 0xFF080808.toInt() else dark
}
'''

OLD_STATUS_BAR = '''    val disabled = AppearanceSettings.disableTranslucentStatusBar.value
    val result = !disabled && original
'''
NEW_STATUS_BAR = '''    val disabled = AppearanceSettings.disableTranslucentStatusBar.value
    // On YouTube 21.23.492 the original experiment can be false even though the portrait
    // player expects a translucent status bar. Keep it enabled unless the user opts out.
    val result = !disabled
'''

OLD_THEME_COLOR_HELPER = '''private fun themeColor(context: Context, attr: String): Int? {
    val id = context.identifier(attr, "attr")
    val value = TypedValue()
    val resolved = id != 0 && context.theme.resolveAttribute(id, value, true)
    return value.data.takeIf { resolved && value.type in TypedValue.TYPE_FIRST_COLOR_INT..TypedValue.TYPE_LAST_COLOR_INT }
}

'''


def replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{description}: expected one upstream match, found {count}")
    return source.replace(old, new, 1)


def add_youtube_patch_strings(root: Path) -> None:
    """Register generated YouTube patch StringRefs and merge our two resources."""
    build_path = root / "apps/youtube/patch/build.gradle.kts"
    build_source = build_path.read_text(encoding="utf-8")
    object_name = "app.reseam.patches.youtube.YouTubePatchStrings"
    registration = f'reseamStrings {{ objectName = "{object_name}" }}'

    if registration not in build_source:
        if "reseamStrings {" in build_source:
            raise SystemExit("YouTube patch module already registers a different reseamStrings object")
        build_source = replace_once(
            build_source,
            "dependencies {",
            registration + "\\n\\ndependencies {",
            "YouTube patch string-table registration",
        )
        build_path.write_text(build_source, encoding="utf-8")

    strings_path = root / "apps/youtube/patch/src/main/strings/values/strings.xml"
    strings_path.parent.mkdir(parents=True, exist_ok=True)
    if strings_path.exists():
        xml = strings_path.read_text(encoding="utf-8")
        if xml.count("</resources>") != 1:
            raise SystemExit(f"{strings_path.relative_to(root)}: expected exactly one </resources> root close tag")
    else:
        xml = '<?xml version="1.0" encoding="utf-8"?>\\n<resources>\\n</resources>\\n'

    values = {
        "restore_classic_miniplayer": "Restore classic miniplayer",
        "restore_classic_miniplayer_description": (
            "Restores YouTube's classic horizontal miniplayer by disabling both modern miniplayer "
            "experiments; this is a build-time patch, not an in-app setting."
        ),
    }

    for key, value in values.items():
        pattern = rf'<string\\s+name="{re.escape(key)}">(.*?)</string>'
        existing = re.search(pattern, xml, flags=re.DOTALL)
        if existing:
            if unescape(existing.group(1)) != value:
                raise SystemExit(f"{strings_path.relative_to(root)}: conflicting existing value for {key}")
            continue
        entry = f'    <string name="{key}">{escape(value)}</string>\\n'
        xml = xml.replace("</resources>", entry + "</resources>", 1)

    strings_path.write_text(xml, encoding="utf-8")


def replace_bundle_field(section: str, field: str, value: str) -> str:
    pattern = rf'(?m)^({re.escape(field)}\s*=\s*)".*?"\s*$'
    updated, count = re.subn(pattern, lambda match: match.group(1) + '"' + value + '"', section)
    if count != 1:
        raise SystemExit(f"manifest.toml [bundle].{field}: expected one field, found {count}")
    return updated


def customize_manifest(root: Path) -> None:
    path = root / "manifest.toml"
    manifest = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)(^\[bundle\]\s*\n)(.*?)(?=^\[|\Z)", manifest)
    if not match:
        raise SystemExit("manifest.toml: missing [bundle] table")
    section = match.group(2)
    section = replace_bundle_field(section, "name", "reseam-youtube-compat")
    section = replace_bundle_field(section, "author", "LisaExists")
    section = replace_bundle_field(
        section, "description",
        "YouTube AMOLED theme and classic miniplayer compatibility patches",
    )
    manifest = manifest[:match.start(2)] + section + manifest[match.end(2):]
    path.write_text(manifest, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply_fixes.py <path-to-Reseam-checkout> <expected-upstream-commit>")

    root = Path(sys.argv[1]).resolve()
    expected_commit = sys.argv[2].lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise SystemExit(f"Invalid expected upstream commit: {expected_commit}")
    if not (root / "settings.gradle.kts").is_file():
        raise SystemExit(f"Not a Reseam patches checkout: {root}")

    actual_commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_commit != expected_commit:
        raise SystemExit(
            f"Upstream checkout mismatch: got {actual_commit}, release API says {expected_commit}"
        )

    theme_path = root / "apps/youtube/patch/src/main/kotlin/app/reseam/patches/youtube/layout/Theme.kt"
    theme = theme_path.read_text(encoding="utf-8")
    theme = replace_once(theme, OLD_GUARD, NEW_GUARD, "legacy color fallback")
    theme = replace_once(theme, OLD_DARK, NEW_DARK, "dark legacy color list")
    theme = replace_once(theme, OLD_LIGHT, NEW_LIGHT, "light legacy color list")
    theme_path.write_text(theme, encoding="utf-8")

    runtime_path = root / "apps/youtube/extensions/theme/src/main/kotlin/app/reseam/youtube/theme/ThemePatch.kt"
    runtime = runtime_path.read_text(encoding="utf-8")
    runtime = replace_once(runtime, OLD_DARK_RUNTIME, NEW_DARK_RUNTIME, "legacy dark runtime lookup")
    runtime = replace_once(runtime, OLD_LIGHT_RUNTIME, NEW_LIGHT_RUNTIME, "legacy light runtime lookup")
    runtime_path.write_text(runtime, encoding="utf-8")

    controls_path = root / "apps/youtube/extensions/controls/src/main/kotlin/app/reseam/youtube/controls/Ui.kt"
    controls = controls_path.read_text(encoding="utf-8")
    controls = replace_once(controls, OLD_DIALOG, NEW_DIALOG, "legacy dialog color lookup")
    controls = replace_once(controls, OLD_THEME_COLOR_HELPER, "", "palette-only dialog helper")
    controls_path.write_text(controls, encoding="utf-8")

    navbuttons_path = root / "apps/youtube/extensions/navbuttons/src/main/kotlin/app/reseam/youtube/navbuttons/NavigationButtons.kt"
    navbuttons = navbuttons_path.read_text(encoding="utf-8")
    navbuttons = replace_once(navbuttons, OLD_STATUS_BAR, NEW_STATUS_BAR, "portrait player status bar inset")
    navbuttons_path.write_text(navbuttons, encoding="utf-8")

    overlay_file = (
        Path(__file__).resolve().parent
        / "overrides/apps/youtube/patch/src/main/kotlin/app/reseam/patches/youtube/layout/RestoreClassicMiniplayer.kt"
    )
    destination = root / "apps/youtube/patch/src/main/kotlin/app/reseam/patches/youtube/layout/RestoreClassicMiniplayer.kt"
    if destination.exists():
        raise SystemExit(f"Refusing to overwrite upstream file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(overlay_file, destination)

    add_youtube_patch_strings(root)
    customize_manifest(root)

    print(f"Applied YouTube compatibility overlay to {actual_commit}")
    print(f"Updated: {theme_path.relative_to(root)}")
    print(f"Updated: {runtime_path.relative_to(root)}")
    print(f"Updated: {controls_path.relative_to(root)}")
    print(f"Updated: {navbuttons_path.relative_to(root)}")
    print(f"Added:   {destination.relative_to(root)}")
    print("Updated: manifest.toml [bundle] metadata")


if __name__ == "__main__":
    main()
