package com.kingzcheung.xime.settings

/** Curated links verified against Sogou's public index on 2026-10-02; no word data bundled. */
data class CellDictionaryOffer(val sourceId: Int, val name: String, val category: String, val entryCount: Int, val downloadBytes: Int) {
    val id: String get() = "sogou_$sourceId"
    val sourceUrl: String get() = "https://pinyin.sogou.com/dict/detail/index/$sourceId"
    val downloadUrl: String get() = "https://pinyin.sogou.com/d/dict/download_cell.php?id=$sourceId&name=$id"
}

/**
 * Dictionaries shipped in the APK: assets/cell_dictionaries/cell_<id>.dict.yaml, and cell_<id>.en.txt for
 * their English words. Only [defaultOn] ones are switched on by themselves (once).
 */
data class BuiltinCellDictionary(
    val id: String, val name: String, val category: String, val sourceUrl: String = "", val defaultOn: Boolean = false,
) {
    val asset: String get() = "cell_dictionaries/cell_$id.dict.yaml"
    val englishAsset: String get() = "cell_dictionaries/cell_$id.en.txt"
}

object CellDictionaryCatalog {
    const val BUILTIN_CATEGORY = "内置词库"
    const val AI_CATEGORY = "编程与 AI"
    // This edition offers local import only; no scraped game or third-party download catalogue.
    val builtins: List<BuiltinCellDictionary> = emptyList()
    const val SOURCE_URL = ""
    val offers: List<CellDictionaryOffer> = emptyList()
}
