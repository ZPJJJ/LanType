#!/usr/bin/env python3
"""Maintain deterministic deployment manifests and the reviewed resource lock.

Run --write-lock only after reviewing changed resources. CI must verify the
committed lock; it must never refresh the lock to make a failed check pass.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from prepare_resources import (ASSETS, ROOT, HERE, MODEL_ID, MODEL_REV, EXTRA_MODELS,
                               ORT_RUNTIME_NOTICE_PATHS, verify_local_runtime_notices)

UPSTREAM = "6f97a555ced063c0bcad73c600fe420f5e4b2536"
UPSTREAM_URL = "https://github.com/Cyletix/CyIME/tree/" + UPSTREAM
ICE_REV = "9e66b0729083b37d217312294f6d516c8d7234be"
RIME_REV = "0c6861ef7420ee780270ca6d993d18d4101049d0"
SELF = "source-distribution://LanType-1.1.0"
TRANSFORM = "tools/lantype_resources/prepare_resources.py"


def sha(data): return hashlib.sha256(data).hexdigest()

def deployment_manifest():
    entries = {}
    optional = {"pinyin_qwjrtk.schema.yaml", "pinyin_cyletix10.schema.yaml", "pinyin_colemak.schema.yaml", "pinyin_typewise.schema.yaml"}
    for parent in ["rime_ice", "rime_chinese"]:
        for file in sorted((ASSETS / parent).rglob("*")):
            if not file.is_file(): continue
            relative = file.relative_to(ASSETS / parent).as_posix()
            if relative.endswith((".md", ".custom.yaml")) or relative.startswith("LICENSE") or relative in optional: continue
            data = file.read_bytes()
            entries[relative] = f"{sha(data)}\t{len(data)}\t{parent}/{relative}\t{relative}"
    (ASSETS / "rime-bundled-manifest.tsv").write_text("\n".join(entries[k] for k in sorted(entries)) + "\n")
    return len(entries)


def descriptor(path: str):
    result = dict(sourceUrl=UPSTREAM_URL, revision=UPSTREAM, license="GPL-3.0-only", transform="retained or adapted CyIME resource", original=False)
    def set_(url, rev, license, transform="unmodified", original=False):
        result.update(sourceUrl=url, revision=rev, license=license, transform=transform, original=original)
    rime = "https://github.com/rime/rime-pinyin-simp/tree/" + RIME_REV
    cedict = "https://www.mdbg.net/chinese/dictionary?page=cedict"
    scowl = "https://github.com/en-wl/wordlist-diff/tree/rel-2026.02.25"
    mmh = "https://github.com/skishore/makemeahanzi/tree/bddc96d41bef78427ed0e034e9f7e31d71fd1b92"
    mcb = "https://github.com/openvanilla/McBopomofo/tree/18e2060dd5d0b511753ad79a8fe0d112e944f1af"
    if path.startswith("bundled-models/" + MODEL_ID + "/"):
        set_(f"https://huggingface.co/csukuangfj/sherpa-onnx-whisper-base/resolve/{MODEL_REV}/{Path(path).name}", MODEL_REV, "MIT", "upstream INT8 ONNX conversion of OpenAI Whisper base; unmodified files")
    elif path in EXTRA_MODELS:
        _, _, url, license, rev = EXTRA_MODELS[path]; set_(url, rev, license)
    elif path.startswith("ocr/"):
        set_("https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt", "RapidOCR-v3.9.2", "Apache-2.0")
    elif path == "handwriting/lantype-strokes.lth":
        set_(mmh, "bddc96d41bef78427ed0e034e9f7e31d71fd1b92", "LicenseRef-Arphic-1999 AND CC0-1.0", "tools/lantype_resources/build_handwriting.py: Chinese medians normalized/resampled; original Latin geometry")
        result["originalPortion"] = "62 Latin letters and digits only; Chinese source is attributed MakeMeAHanzi/Arphic"
    elif path.startswith("handwriting/hanzi_") or path.startswith("glide_pinyin") or path.startswith("rime_ice/cyime_rare"):
        set_(rime, RIME_REV + "; CC-CEDICT 2026-11-16T07:16:40Z", "Apache-2.0 AND CC-BY-SA-4.0", TRANSFORM)
        result["additionalSourceUrls"] = [cedict]
    elif path in {"english.txt", "english_trie.bin"} or path in {"rime_ice/cyime_english.dict.yaml", "rime_ice/cyime_t9_english.dict.yaml", "rime_ice/cyime_k14_english.dict.yaml", "rime_ice/en_dicts/en.dict.yaml", "rime_ice/melt_eng.dict.yaml"}:
        set_(scowl, "rel-2026.02.25", "LicenseRef-SCOWL AND CC0-1.0", TRANSFORM + ": US size-60 words, original editorial rank, trie/key-code conversion")
    elif path in {"rime_ice/cn_dicts/base.dict.yaml", "rime/pinyin_simp.dict.yaml"}:
        set_(rime, RIME_REV, "Apache-2.0", TRANSFORM + ": preserve AOSP-derived words/readings/frequencies")
    elif path == "rime_ice/cn_dicts/cedict.dict.yaml":
        set_(cedict, "2026-11-16T07:16:40Z; source sha256 e633d741b2cfa2f8fac706f4072a9868c4768b81289295a96db676775c219e28", "CC-BY-SA-4.0", TRANSFORM + ": simplified words and toneless pinyin; fixed fallback weight")
    elif path.startswith("rime_chinese/cyime_cangjie.dict") or path.startswith("rime_chinese/cyime_quick.dict"):
        set_("https://github.com/Jackchows/Cangjie5/tree/c9b64e77951cba48bdfa5de8eaedd1a908666b9b", "c9b64e77951cba48bdfa5de8eaedd1a908666b9b", "MIT AND Apache-2.0", TRANSFORM + ": codes retained, old mixed-corpus frequencies and phrases replaced")
    elif path.startswith("rime_chinese/stroke"):
        set_("https://github.com/rime/rime-stroke/tree/1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48", "1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48", "LGPL-3.0-only AND Apache-2.0 AND CC-BY-SA-4.0", TRANSFORM + ": licensed stroke codes; AOSP/CC-CEDICT weighting and AOSP phrases")
    elif path in {"rime_chinese/cyime_tw.dict.yaml", "rime_chinese/lua/cyime_zhuyin_tones.lua", "rime_chinese/opencc/CyimeTWPhrases.ocd2"}:
        set_(mcb, "18e2060dd5d0b511753ad79a8fe0d112e944f1af", "MIT AND BSD-3-Clause", "McBopomofo data adaptation; phrases reset to weight 1 in commercial edition; see McBopomofo and libtabe notices")
    elif path.startswith("rime_chinese/cyime_aux_") and path.endswith(".dict.yaml"):
        set_("https://github.com/HowcanoeWang/rime-lua-aux-code/tree/f9780033396f8998697c2a004d40bd543c46308b", "f9780033396f8998697c2a004d40bd543c46308b", "MIT", "convert character=code lines to Rime table")
    elif path.startswith("rime_chinese/opencc/") and path.endswith(".ocd2") or path in {"rime_chinese/opencc/s2t.json", "rime_chinese/opencc/s2tw.json", "rime_chinese/opencc/s2hk.json"}:
        set_("https://github.com/BYVoid/OpenCC/tree/e9f3bb3", "e9f3bb3", "Apache-2.0", "compiled with OpenCC from fixed native dependency source")
    elif path.startswith("rime_ice/"):
        set_("https://github.com/iDvel/rime-ice/tree/" + ICE_REV, ICE_REV, "GPL-3.0-only", "CyIME/LanType schema and Lua adaptation; original word tables are replaced")
    elif path.startswith("katex/fonts/"):
        set_("https://github.com/KaTeX/KaTeX/tree/v0.16.22/fonts", "v0.16.22", "OFL-1.1", "unmodified; exact official-tag byte comparison and matching TTF name-table evidence in docs/licensing/katex-fonts-evidence.json")
    elif path.startswith("katex/"):
        set_("https://github.com/KaTeX/KaTeX/tree/v0.16.22", "v0.16.22", "MIT", "unmodified JavaScript, CSS and fonts; font-specific notices in licenses")
    elif path == "PublicSuffixDatabase.list":
        set_("https://publicsuffix.org/list/", "CyIME-1.15.94 snapshot; exact SHA-256 fixed below", "MPL-2.0", TRANSFORM + ": encode editable source_data/public-suffix-list.txt into two length-prefixed UTF-8 sections; exact round trip verified")
    elif path.startswith("licenses/"):
        result.update(license="LicenseRef-Upstream-Notice", transform="full verbatim upstream licence/notice; HTML legalcode rendered as plain text where noted", licenseDocument=True)
    elif path.startswith("rime/"):
        set_(UPSTREAM_URL, UPSTREAM, "Apache-2.0", "retained Xime/Rime configuration; license retained in rime/LICENSE")
    original = path.startswith("association/lantype-original-") or path in {
        "english_bigrams.txt", "english_contractions.txt", "english_glide_words.txt", "rime_ice/cyime_cn_en.dict.yaml",
        "rime_ice/radical_pinyin.dict.yaml", "rime_ice/opencc/emoji.txt", "rime_ice/opencc/others.txt",
        "rime_ice/cyime_readings.txt", "rime_ice/cyime_k14_aliases.tsv"}
    if original: set_(SELF, "lantype-commercial-resources-v1", "CC0-1.0", TRANSFORM, True)
    if path in {"english_us_spelling.tsv", "english_typo_corrections.tsv"}:
        set_(SELF, "LanType-1.0.0 original manually authored tables", "GPL-3.0-or-later", "unmodified LanType editorial examples; provenance in file headers", True)
    if path in {"rime_chinese/cyime_cangjie.schema.yaml", "rime_chinese/cyime_zhuyin.schema.yaml"}:
        set_("https://github.com/rime/" + ("rime-cangjie" if "cangjie" in path else "rime-bopomofo"), UPSTREAM, "LGPL-3.0-only AND GPL-3.0-only", "CyIME adaptations of Rime schema code, retained in LanType")
    if path.startswith("rime_chinese/") and ("NOTICE" in path or "/LICENSE" in path):
        set_(SELF, "lantype-commercial-resources-v1", "LicenseRef-Upstream-Notice", "current distribution notice and full corresponding upstream license")
        result["licenseDocument"] = True
    notices = {
        "SCOWL-Copyright.txt": (scowl, "rel-2026.02.25", "LicenseRef-SCOWL"),
        "Whisper-MIT.txt": ("https://github.com/openai/whisper/blob/main/LICENSE", "OpenAI Whisper MIT code and model weights", "MIT"),
        "Arphic-Public-License.txt": ("https://github.com/skishore/makemeahanzi/blob/bddc96d41bef78427ed0e034e9f7e31d71fd1b92/Arphic-LICENSE", "bddc96d41bef78427ed0e034e9f7e31d71fd1b92", "LicenseRef-Arphic-1999"),
        "MakeMeAHanzi-COPYING.txt": (mmh, "bddc96d41bef78427ed0e034e9f7e31d71fd1b92", "LicenseRef-Arphic-1999"),
        "CC-BY-SA-4.0.txt": ("https://creativecommons.org/licenses/by-sa/4.0/legalcode.en", "4.0", "CC-BY-SA-4.0"),
        "CC-CEDICT-NOTICE.txt": (cedict, "2026-11-16T07:16:40Z", "CC-BY-SA-4.0"),
        "CC0-1.0.txt": ("https://creativecommons.org/publicdomain/zero/1.0/legalcode.en", "1.0", "CC0-1.0"),
        "Rime-Pinyin-Simp-Apache-2.0.txt": (rime, RIME_REV, "Apache-2.0"),
        "Cangjie5-MIT.txt": ("https://github.com/Jackchows/Cangjie5/tree/c9b64e77951cba48bdfa5de8eaedd1a908666b9b", "c9b64e77951cba48bdfa5de8eaedd1a908666b9b", "MIT"),
        "Rime-Stroke-LGPL-3.0.txt": ("https://github.com/rime/rime-stroke/tree/1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48", "1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48", "LGPL-3.0-only"),
        "McBopomofo-LICENSE.txt": (mcb, "18e2060dd5d0b511753ad79a8fe0d112e944f1af", "MIT"),
        "McBopomofo-Data-README.txt": (mcb + "/Source/Data/README.md", "18e2060dd5d0b511753ad79a8fe0d112e944f1af", "MIT AND BSD-3-Clause"),
        "Libtabe-COPYING.txt": ("https://raw.githubusercontent.com/kcwu/libtabe/master/COPYING", "exact notice bytes hash-locked", "BSD-3-Clause"),
        "Aux-Code-MIT.txt": ("https://github.com/HowcanoeWang/rime-lua-aux-code/tree/f9780033396f8998697c2a004d40bd543c46308b", "f9780033396f8998697c2a004d40bd543c46308b", "MIT"),
        "KaTeX-MIT.txt": ("https://github.com/KaTeX/KaTeX/blob/v0.16.22/LICENSE", "v0.16.22", "MIT"),
        "KaTeX-Fonts-Notices.txt": ("https://github.com/KaTeX/KaTeX/tree/v0.16.22/fonts", "v0.16.22", "OFL-1.1"),
        "SIL-OFL-1.1.txt": ("https://openfontlicense.org/documents/OFL.txt", "1.1 (2007-02-26)", "OFL-1.1"),
        "Public-Suffix-MPL-2.0.txt": ("https://www.mozilla.org/MPL/2.0/", "2.0", "MPL-2.0"),
        "Rime-Ice-GPL-3.0.txt": ("https://github.com/iDvel/rime-ice/tree/" + ICE_REV, ICE_REV, "GPL-3.0-only"),
    }
    if path.startswith("licenses/") and Path(path).name in notices:
        url, rev, license = notices[Path(path).name]
        set_(url, rev, license, "full upstream license or attribution notice; font notices extracted from fixed release metadata")
        result["licenseDocument"] = True
    if path in {"NOTICE.txt", "rime-bundled-manifest.tsv", "rime-retired-resources.tsv", "bundled-models/manifest.json"}:
        set_(SELF, "lantype-commercial-resources-v1", "GPL-3.0-only", "tools/lantype_resources/finalize_resources.py or prepare_resources.py", True)
    return result


def write_lock():
    verify_local_runtime_notices()
    current_lock = json.loads((ROOT / "docs/licensing/resources.lock.json").read_text())
    fixed_notices = {entry["path"]:entry for entry in current_lock["resources"]
                     if entry["path"] in ORT_RUNTIME_NOTICE_PATHS}
    sources = json.loads((HERE / "sources.lock.json").read_text())
    native_path = ROOT / "docs/licensing/native-license-files.json"
    native = {x["path"]:x for x in json.loads(native_path.read_text())} if native_path.exists() else {}
    resources = []
    for file in sorted(ASSETS.rglob("*")):
        if not file.is_file() or any(part.startswith(".") for part in file.relative_to(ASSETS).parts): continue
        path = file.relative_to(ASSETS).as_posix(); data=file.read_bytes()
        row = {"path":path, "physicalPath":path, "logicalPath":path[:-3] if path.endswith(".gz") else path,
               "sha256":sha(data), "size":len(data), "hashEncoding":"source-bytes",
               "sourceEncoding":"gzip" if path.endswith(".gz") else "identity", **descriptor(path)}
        if path in native:
            row.update({k:v for k,v in native[path].items() if k not in {"path","sha256","size"}})
        if path in fixed_notices:
            row = dict(fixed_notices[path])
        if path.endswith(".gz"):
            plain=gzip.decompress(data);row.update(decodedSha256=sha(plain),decodedSize=len(plain))
        resources.append(row)
    raw=[]
    for file in sorted((ROOT/'app/src/main/res/raw').glob('kb_*.wav')):
        data=file.read_bytes();raw.append({'path':file.relative_to(ROOT/'app/src/main').as_posix(),'sha256':sha(data),'size':len(data),
            'sourceUrl':SELF,'revision':'lantype-commercial-resources-v1','license':'CC0-1.0','transform':TRANSFORM+': deterministic additive sine synthesis','original':True})
    excluded=json.loads((ROOT/'docs/licensing/excluded-resources.json').read_text())['excluded']
    psl=HERE/'source_data/public-suffix-list.txt';psl_bytes=psl.read_bytes()
    sources['sources'].append({'name':psl.name, 'license':'MPL-2.0', 'revision':'CyIME-1.15.94 exact snapshot', 'sourceUrl':'https://publicsuffix.org/list/',
        'sha256':sha(psl_bytes),'size':len(psl_bytes),'sourceArchive':psl.relative_to(ROOT).as_posix(),'sourceArchiveSha256':sha(psl_bytes),'sourceArchiveEncoding':'identity'})
    lock={'schemaVersion':1,'edition':'LanType commercial GPL, offline runtime','hashPolicy':'sha256/size cover physical source bytes. logicalPath identifies the AAPT-visible path. Gzip source entries, if any, require decodedSha256/decodedSize and an explicit source-gzip expansion; never skip byte verification. All current main assets use identity encoding.',
          'resources':resources,'rawResources':raw,'sourceDatasets':sources['sources'],'excluded':excluded,
          'generatedAssets':[
              {'path':'plugin-market/index.yaml','owner':'app/build-logic/tasks-plugin-market.gradle.kts','license':'GPL-3.0-only','policy':'validate empty offline market and record exact final generated hash'},
              {'path':'builtin-plugins/windows-clipboard.xipk','owner':'app/build-logic/tasks-builtin-sync.gradle.kts','license':'GPL-3.0-only','policy':'validate exact locally generated plugin bytes and manifest; record final hash'},
              {'path':'dexopt/baseline.prof','owner':'Android Gradle Plugin baseline profile compiler','license':'GPL-3.0-only','policy':'record final build generated hash'},
              {'path':'dexopt/baseline.profm','owner':'Android Gradle Plugin baseline profile compiler','license':'GPL-3.0-only','policy':'record final build generated hash'}]}
    path=ROOT/'docs/licensing/resources.lock.json';path.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'resources':len(resources),'rawResources':len(raw),'sourceDatasets':len(sources['sources']),'excludedRecords':len(excluded),'resourceBytes':sum(x['size'] for x in resources)}))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-lock',action='store_true');args=ap.parse_args()
    print('Deployment manifest entries:',deployment_manifest())
    if args.write_lock:write_lock()

if __name__=='__main__':main()
