package com.kingzcheung.xime.speech

import com.kingzcheung.xime.model.*

/** Commercial distribution catalogue: pinned MIT-licensed Whisper weights only.
 * Legacy IDs stay as migration constants; their model files are never bundled. */
object SpeechModelCatalog {
    const val ZIPFORMER = "zipformer-zh-int8"
    const val ZIPFORMER_JA = "zipformer-ja-reazonspeech-fp32"
    const val ZIPFORMER_JA_INT8 = "zipformer-ja-reazonspeech-int8"
    fun isJapaneseZipformer(id: String) = id == ZIPFORMER_JA || id == ZIPFORMER_JA_INT8
    const val ZIPFORMER_TWO_PASS = "zipformer-sensevoice"
    const val PARAFORMER = "paraformer-zh-en-int8"
    const val SENSEVOICE = "sensevoice-multilingual-int8"
    const val TWO_PASS = "paraformer-sensevoice"
    /** 整句定稿的可选模型：X-ASR 中英 Zipformer（离线、自带标点）；何时代替 SenseVoice 见 [SpeechModelSelection.xasrFinalizes]。 */
    const val XASR = "xasr-zh-en-punct-int8"
    const val WHISPER = "whisper-base-multilingual-int8"
    private const val WHISPER_BASE = "https://huggingface.co/csukuangfj/sherpa-onnx-whisper-base/resolve/bb53ee204431c90d314c1cc08d28d23e5b7927cc"
    val models = listOf(
        ModelInfo(WHISPER, "Whisper Base · 中英离线",
            "随包内置，约 153 MB；中文和美式英文停顿后出字。模型与代码为 MIT 许可，识别速度和准确度依设备与语音而异。",
            ModelCategory.ASR, versions = listOf(ModelVersion(version = "bb53ee204431", size = "153.2 MB",
                files = listOf(
                    ModelFile("base-encoder.int8.onnx", "$WHISPER_BASE/base-encoder.int8.onnx", "0b8fb1304b6109976038efff5ace81720e00386f3ff6b54ee8c75291ca0a1e11", 29120534L),
                    ModelFile("base-decoder.int8.onnx", "$WHISPER_BASE/base-decoder.int8.onnx", "9759d217388a01b3a4c7c15533201067b48ae819c4daafc8624e64b9409dc02d", 130672026L),
                    ModelFile("base-tokens.txt", "$WHISPER_BASE/base-tokens.txt", "b34b360dbb493e781e479794586d661700670d65564001f23024971d1f2fa126", 816730L),
                )))),
    )
}
