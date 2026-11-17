import groovy.json.JsonSlurper

// Resources have one reviewed source for both prebuilt and rebuilt JNI modes.
val upstreamRoot = rootProject.file("vendor/cyime-1.15.94")
val nativeLock = rootProject.file("docs/licensing/native-prebuilt.lock.json")
val rebuiltCameraRoot = rootProject.file("vendor/lantype-camerax-native")
val cameraNativeLock = rootProject.file("docs/licensing/camerax-rebuilt.lock.json")
val cameraEntries = (JsonSlurper().parse(cameraNativeLock) as Map<*, *>)["outputs"] as List<*>
val approvedCameraPaths = cameraEntries.map { (it as Map<*, *>)["path"] as String }
    .map { it.removePrefix("vendor/lantype-camerax-native/") }
val nativeEntries = (JsonSlurper().parse(nativeLock) as Map<*, *>)["files"] as List<*>
val approvedNativePaths = nativeEntries.map { (it as Map<*, *>)["path"] as String }
    .filter { it.startsWith("jniLibs/") }.map { it.removePrefix("jniLibs/") }
val verifyLanTypeNativeFiles by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("python3", "scripts/prepare-upstream.py", "--verify-only")
}
val verifyLanTypeCameraNativeFiles by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("python3", "scripts/build-camerax-native.py", "--verify-only")
}
val prepareLanTypeApprovedNativeLibraries by tasks.registering(Sync::class) {
    dependsOn(verifyLanTypeNativeFiles, verifyLanTypeCameraNativeFiles)
    from(File(upstreamRoot, "jniLibs")) { include(approvedNativePaths) }
    from(rebuiltCameraRoot) { include(approvedCameraPaths) }
    into(layout.buildDirectory.dir("generated/lantype-approved-jniLibs"))
}
val mergedAssets = layout.buildDirectory.dir("generated/lantype-assets")
val verifyLanTypeApprovedResources by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("python3", "scripts/verify-commercial-resources.py")
}
val prepareLanTypeAssets by tasks.registering {
    dependsOn(verifyLanTypeApprovedResources)
    inputs.dir(file("src/main/assets"))
    outputs.dir(mergedAssets)
    doLast {
        check(File(upstreamRoot, "jniLibs/arm64-v8a/librime_jni.so").isFile) {
            "Missing locked native engine. Run python3 scripts/prepare-upstream.py first."
        }
        // Old upstream APK assets are never inputs to this edition. The resource
        // preparation script materializes only the separately reviewed lock.
        sync {
            from(file("src/main/assets"))
            into(mergedAssets)
            exclude("dexopt/**", "plugin-market/**", "release-notes/**", "builtin-plugins/**")
        }
    }
}
val prepareLanTypeRuntimeLibraries by tasks.registering(Sync::class) {
    dependsOn(verifyLanTypeNativeFiles, verifyLanTypeCameraNativeFiles)
    from(File(upstreamRoot, "jniLibs")) { include("arm64-v8a/libsherpa-onnx-jni.so") }
    from(rebuiltCameraRoot) { include(approvedCameraPaths) }
    into(layout.buildDirectory.dir("generated/lantype-runtime-jniLibs"))
}
dependencies.add("implementation", files(File(upstreamRoot, "java/sherpa-onnx-1.13.8-classes.jar")))
tasks.named("preBuild").configure { dependsOn(prepareLanTypeAssets, prepareLanTypeApprovedNativeLibraries, prepareLanTypeRuntimeLibraries) }
