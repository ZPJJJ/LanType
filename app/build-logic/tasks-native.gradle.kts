import org.gradle.api.tasks.PathSensitivity

// Source-native mode uses only locked, explicitly prepared local build inputs.
// App resources always come from tools/lantype_resources; no old dictionary task runs.
val verifyLanTypeNativeBuildInputs by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("python3", "scripts/prepare-ort-runtime.py", "--accepted-lock",
        "docs/licensing/ort-runtime.lock.json", "--verify-native-input",
        "app/src/main/jni/onnxruntime/lib/arm64-v8a/libonnxruntime.so")
    inputs.file(rootProject.file("docs/licensing/ort-runtime.lock.json"))
    inputs.file(file("src/main/jni/onnxruntime/lib/arm64-v8a/libonnxruntime.so"))
    doFirst {
        val required = listOf(
            "src/main/jni/librime/CMakeLists.txt",
            "src/main/jni/boost/CMakeLists.txt",
            "src/main/jni/onnxruntime/include/onnxruntime_c_api.h",
            "src/main/jni/onnxruntime/lib/arm64-v8a/libonnxruntime.so",
        )
        check(required.all { file(it).isFile }) {
            "Prepare source archives with scripts/restore-native-sources.py and scripts/prepare-native-build.py before the native build."
        }
    }
}

val syncT9Plugin by tasks.registering {
    val authoritative = file("src/main/jni/librime-t9")
    val mirror = file("src/main/jni/librime/plugins/librime-t9")
    inputs.dir(authoritative)
    outputs.dir(mirror)
    doLast {
        copy {
            from(authoritative)
            into(mirror)
            exclude("build_test/**")  // 本地单测构建产物，不入镜像
        }
    }
}

// 2) 把 librime 核心/插件源码目录声明为 native 构建任务的显式输入：
//    AGP 对 CMake 任务的 up-to-date 判断不覆盖 submodule 源文件，
//    缺失该输入时 Android Studio 的 Run 会直接跳过 ninja，
//    改动（尤其 librime/src 核心改动）不会进 APK。
//    声明后：源码一变任务必然执行，ninja 按依赖增量重编，仍然很快。
tasks.configureEach {
    if (name.startsWith("buildCMake") || name.startsWith("configureCMake")) {
        dependsOn(verifyLanTypeNativeBuildInputs)
        inputs.file(rootProject.file("docs/licensing/ort-runtime.lock.json"))
            .withPathSensitivity(PathSensitivity.RELATIVE)
        inputs.file("src/main/jni/onnxruntime/lib/arm64-v8a/libonnxruntime.so")
            .withPathSensitivity(PathSensitivity.RELATIVE)
    }
    if (name.startsWith("buildCMake")) {
        dependsOn(syncT9Plugin)
        inputs.dir("src/main/jni/librime/src")
            .withPathSensitivity(PathSensitivity.RELATIVE)
            .optional(true)
        inputs.dir("src/main/jni/librime-t9")
            .withPathSensitivity(PathSensitivity.RELATIVE)
            .optional(true)
    }
}

tasks.named("preBuild").configure { dependsOn(verifyLanTypeNativeBuildInputs) }
