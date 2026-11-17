cmake_minimum_required(VERSION 3.22.1)
project(lantype_camerax_native LANGUAGES C CXX)

if(NOT ANDROID OR NOT ANDROID_ABI STREQUAL "arm64-v8a")
  message(FATAL_ERROR "This reviewed build profile supports Android ARM64 only")
endif()
if(NOT EXISTS "${CAMERAX_SOURCE}/src/main/cpp/CMakeLists.txt" OR NOT EXISTS "${LIBYUV_SOURCE}/CMakeLists.txt")
  message(FATAL_ERROR "Restore the locked CameraX and libyuv source archives first")
endif()

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_DISABLE_FIND_PACKAGE_JPEG TRUE)
set(UNIT_TEST OFF CACHE BOOL "" FORCE)
add_compile_options(-O3 -flto -fPIC -fomit-frame-pointer -fdata-sections -ffunction-sections)
add_compile_options("-ffile-prefix-map=${LANTYPE_ROOT}=lantype/"
                    "-ffile-prefix-map=${ANDROID_NDK}=android-ndk/")
add_compile_options("$<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions>"
                    "$<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>")

# CameraX's own CMake expects a Prefab target. Provide it from the exact local
# source tree instead of an opaque precompiled libyuv archive.
add_subdirectory("${LIBYUV_SOURCE}" libyuv-build EXCLUDE_FROM_ALL)
add_library(libyuv::yuv ALIAS yuv)
set(libyuv_DIR "${CMAKE_BINARY_DIR}/libyuv-config")
file(MAKE_DIRECTORY "${libyuv_DIR}")
file(WRITE "${libyuv_DIR}/libyuvConfig.cmake" "set(libyuv_FOUND TRUE)\n")
include_directories("${LIBYUV_SOURCE}/include")

# Keep the exact CameraX 1.6.2 JNI implementation and its 16 KiB linker options.
add_subdirectory("${CAMERAX_SOURCE}/src/main/cpp" camera-core-jni)
foreach(native_target image_processing_util_jni surface_util_jni)
  target_link_options(${native_target} PRIVATE
    -flto "-Wl,--gc-sections" "-Wl,--undefined-version"
    "-Wl,--version-script=${CAMERAX_SOURCE}/src/main/cpp/jni.lds"
    "-Wl,-z,max-page-size=16384")
endforeach()
