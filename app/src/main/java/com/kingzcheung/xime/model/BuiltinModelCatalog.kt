package com.kingzcheung.xime.model

/** Only the commercial edition’s approved, packaged local models are offered. */
object BuiltinModelCatalog {
    /** CyIME 自己 Release 里的原样转存（许可见该 Release 的 NOTICE-models.txt），海外线路优先。 */
    private const val RELEASE = "https://github.com/Cyletix/CyIME/releases/download/models/"
    const val SPEAKER_MODEL = "speaker-campplus-zh"
    const val SPEAKER_MODEL_FILE = "3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx"
    /** 拍照识别（PP-OCRv5 mobile）。轻量版不带，第一次拍照识别时下载；带模型的安装包仍内置在 assets/ocr/ppocr-v5。 */
    const val OCR_MODEL = "ocr-ppocr-v5"
    /** 拍照识别引擎（OpenCV 原生库）。轻量版不带，和拍照识别模型一起下载（ocr/OcrEngine.kt）。 */
    const val OCR_ENGINE = "ocr-engine"
    /** 日语词库（azooKey 词典 zip）和日语转换引擎（libCyAzooKey.so）。轻量版不带，装「日语」插件时下载（settings/JapanesePack.kt）。 */
    const val JAPANESE_DICTIONARY = "japanese-dictionary"
    const val JAPANESE_ENGINE = "japanese-engine"

    val models = com.kingzcheung.xime.speech.SpeechModelCatalog.models + listOf(
        ModelInfo(OCR_MODEL, "拍照识别模型", "拍照识字用的中英文识别模型，约 21 MB。已随安装包内置，离线使用。", ModelCategory.OTHER,
            versions = listOf(ModelVersion(version = "v5-mobile", size = "20.5 MB",
                files = listOf(
                    ModelFile("ch_PP-OCRv5_det_mobile.onnx", "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx", "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae", 4819576L,
                        mirrors = listOf(RELEASE + "ocr-ppocr-v5-det-mobile.onnx", DownloadMirrors.CYIME_MODELSCOPE + "ocr-ppocr-v5-det-mobile.onnx")),
                    ModelFile("ch_PP-OCRv5_rec_mobile.onnx", "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx", "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5", 16631306L,
                        mirrors = listOf(RELEASE + "ocr-ppocr-v5-rec-mobile.onnx", DownloadMirrors.CYIME_MODELSCOPE + "ocr-ppocr-v5-rec-mobile.onnx")),
                    // 识别模型自带的字符表，RapidAI 同一版本里有原样的一份 (2026-11-03 核对哈希一致)。
                    ModelFile("ppocrv5-characters.txt", "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt", "d1979e9f794c464c0d2e0b70a7fe14dd978e9dc644c0e71f14158cdf8342af1b", 74012L,
                        mirrors = listOf(RELEASE + "ocr-ppocr-v5-characters.txt", DownloadMirrors.CYIME_MODELSCOPE + "ocr-ppocr-v5-characters.txt")),
                )))),
    )
}
