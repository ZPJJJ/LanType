package com.kingzcheung.xime.model

/** Optional scoring resources; ordinary Chinese dictionaries do not depend on these downloads. */
object CandidateModelCatalog {
    const val GRAMMAR = "t9-grammar"
    const val SENTENCE = "t9-sentence"
    const val NGRAM = "t9-ngram"
    const val NGRAM_SMALL = "t9-ngram-small"
    // The commercial edition uses its licensed dictionary and local learning only.
    // Old imported optional models remain on disk but are not auto-installed or offered.
    val models: List<ModelInfo> = emptyList()
}
