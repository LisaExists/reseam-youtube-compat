// SPDX-FileCopyrightText: 2026 LisaExists
// SPDX-License-Identifier: AGPL-3.0-or-later

package app.reseam.patches.youtube.layout

import app.reseam.patch.patch
import app.reseam.patches.youtube.core.YOUTUBE
import app.reseam.patches.youtube.internal.disableBooleanFeature

// These are the two YouTube experiments that switch to the modern floating/resizable miniplayer.
private const val MINIPLAYER_MODERN_FEATURE_LEGACY_KEY = 45630429L
private const val MINIPLAYER_MODERN_FEATURE_KEY = 45622882L

/**
 * Restores YouTube's native classic compact miniplayer by pinning both modern-miniplayer
 * experiments off. This is independent of the separate Reseam "Compact miniplayer" layout patch.
 */
val restoreClassicMiniplayer = patch("Restore classic miniplayer") {
    description("Restores the classic horizontal miniplayer by disabling both modern miniplayer experiments. Select this patch in Reseam Manager before building YouTube; it does not add a toggle inside YouTube settings.")
    compatibleWith(YOUTUBE)

    execute {
        disableBooleanFeature(MINIPLAYER_MODERN_FEATURE_LEGACY_KEY)
        disableBooleanFeature(MINIPLAYER_MODERN_FEATURE_KEY)
    }
}
