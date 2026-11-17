/* SPDX-License-Identifier: GPL-3.0-or-later
 * Positive Android load/API smoke check for LanType's ORT 1.28.0 replacement.
 *
 * Compile with the fixed ORT commit's include/onnxruntime/core/session headers
 * and the Android ARM64/API 28 toolchain, linking libdl only. This file does not
 * link ORT at build time. The caller must record hashes of the probe and target
 * library, the toolchain, Android device identity, exit code and stdout/stderr.
 *
 * Run only on the explicitly selected Android test target with an absolute
 * library path. Each stdout line is JSON. A final passed=true summary means
 * load + C API 28 + declared provider list + environment lifecycle succeeded.
 * It does not test inference, provider usability, keyboard input, or a phone.
 * No sysfs fixtures, signal recovery, sanitizer or fault injection are used.
 */

#include <dlfcn.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "onnxruntime_c_api.h"

#if ORT_API_VERSION != 28
#error "Use the fixed ORT 1.28.0 C API 28 headers"
#endif

typedef const OrtApiBase *(ORT_API_CALL *GetApiBaseFunction)(void);

static void json_string(const char *value) {
  const unsigned char *p = (const unsigned char *)(value ? value : "");
  putchar('"');
  for (; *p; ++p) {
    if (*p == '"' || *p == '\\') {
      putchar('\\');
      putchar(*p);
    } else if (*p < 0x20 || *p == 0x7f) {
      printf("\\u%04x", (unsigned int)*p);
    } else {
      putchar(*p);
    }
  }
  putchar('"');
}

static void stage(const char *name, const char *state, const char *detail) {
  fputs("{\"schemaVersion\":1,\"probe\":\"lantype-ort-api-smoke\",\"event\":\"stage\",\"stage\":", stdout);
  json_string(name);
  fputs(",\"state\":", stdout);
  json_string(state);
  fputs(",\"detail\":", stdout);
  json_string(detail);
  fputs("}\n", stdout);
}

static bool status_ok(const OrtApi *api, OrtStatus *status, const char *name) {
  if (status == NULL) {
    stage(name, "passed", "");
    return true;
  }
  fputs("{\"schemaVersion\":1,\"probe\":\"lantype-ort-api-smoke\",\"event\":\"ort-status\",\"stage\":", stdout);
  json_string(name);
  printf(",\"state\":\"failed\",\"code\":%d,\"message\":", (int)api->GetErrorCode(status));
  json_string(api->GetErrorMessage(status));
  fputs("}\n", stdout);
  api->ReleaseStatus(status);
  return false;
}

int main(int argc, char **argv) {
  const char *required[] = {
      "CPUExecutionProvider", "NnapiExecutionProvider",
      "XnnpackExecutionProvider", "WebGpuExecutionProvider"};
  void *library = NULL;
  const OrtApi *api = NULL;
  OrtEnv *env = NULL;
  char **providers = NULL;
  int provider_count = 0;
  bool passed = false;
  bool providers_owned = false;
  GetApiBaseFunction get_api_base = NULL;

  /* Preserve the last started stage if an external failure ends the process. */
  setvbuf(stdout, NULL, _IONBF, 0);
  if (argc != 2 || argv[1][0] != '/') {
    stage("arguments", "failed", "Expected one absolute Android path to libonnxruntime.so");
    goto finish;
  }

  stage("dlopen", "starting", argv[1]);
  library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (library == NULL) {
    stage("dlopen", "failed", dlerror());
    goto finish;
  }
  stage("dlopen", "passed", argv[1]);

  dlerror();
  void *symbol = dlsym(library, "OrtGetApiBase");
  const char *loader_error = dlerror();
  if (loader_error != NULL || symbol == NULL) {
    stage("OrtGetApiBase-symbol", "failed", loader_error ? loader_error : "Null symbol");
    goto finish;
  }
  _Static_assert(sizeof(get_api_base) == sizeof(symbol), "Android function pointer size mismatch");
  memcpy(&get_api_base, &symbol, sizeof(get_api_base));
  stage("OrtGetApiBase-symbol", "passed", "");

  const OrtApiBase *base = get_api_base();
  if (base == NULL || base->GetVersionString == NULL || base->GetApi == NULL) {
    stage("OrtApiBase", "failed", "Missing base API");
    goto finish;
  }
  const char *version = base->GetVersionString();
  if (version == NULL || strcmp(version, "1.28.0") != 0) {
    stage("GetVersionString", "failed", version ? version : "Null version");
    goto finish;
  }
  stage("GetVersionString", "passed", version);

  api = base->GetApi(28);
  if (api == NULL || api->CreateEnv == NULL || api->ReleaseEnv == NULL ||
      api->GetAvailableProviders == NULL || api->ReleaseAvailableProviders == NULL ||
      api->GetErrorCode == NULL || api->GetErrorMessage == NULL || api->ReleaseStatus == NULL) {
    stage("GetApi", "failed", "C API 28 or required function pointer missing");
    api = NULL;
    goto finish;
  }
  stage("GetApi", "passed", "28");

  stage("GetAvailableProviders", "starting", "");
  if (!status_ok(api, api->GetAvailableProviders(&providers, &provider_count), "GetAvailableProviders")) {
    goto finish;
  }
  if (providers == NULL || provider_count <= 0 || provider_count > 128) {
    stage("provider-list", "failed", "Invalid provider array or count");
    goto finish;
  }
  providers_owned = true;
  for (int i = 0; i < provider_count; ++i) {
    if (providers[i] == NULL) {
      stage("provider-list", "failed", "Null provider name");
      goto finish;
    }
  }
  fputs("{\"schemaVersion\":1,\"probe\":\"lantype-ort-api-smoke\",\"event\":\"providers\",\"names\":[", stdout);
  for (int i = 0; i < provider_count; ++i) {
    if (i) putchar(',');
    json_string(providers[i]);
  }
  fputs("],\"scope\":\"reported-availability-only\",\"providerInferenceTested\":false}\n", stdout);
  for (size_t r = 0; r < sizeof(required) / sizeof(required[0]); ++r) {
    bool found = false;
    for (int i = 0; i < provider_count; ++i) {
      if (strcmp(providers[i], required[r]) == 0) found = true;
    }
    stage("required-provider", found ? "passed" : "failed", required[r]);
    if (!found) goto finish;
  }

  stage("CreateEnv", "starting", "");
  if (!status_ok(api, api->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "lantype-api-smoke", &env), "CreateEnv")) {
    goto finish;
  }
  if (env == NULL) {
    stage("CreateEnv-result", "failed", "Success returned without an environment");
    goto finish;
  }
  api->ReleaseEnv(env);
  env = NULL;
  stage("ReleaseEnv", "passed", "");
  passed = true;

finish:
  if (api != NULL && env != NULL) api->ReleaseEnv(env);
  if (api != NULL && providers_owned) {
    if (!status_ok(api, api->ReleaseAvailableProviders(providers, provider_count),
                   "ReleaseAvailableProviders")) passed = false;
  }
  if (library != NULL) {
    stage("dlclose", "starting", "");
    if (dlclose(library) != 0) {
      stage("dlclose", "failed", dlerror());
      passed = false;
    } else {
      stage("dlclose", "passed", "");
    }
  }
  printf("{\"schemaVersion\":1,\"probe\":\"lantype-ort-api-smoke\",\"event\":\"summary\","
         "\"passed\":%s,\"apiVersion\":28,\"scope\":\"load-api-environment-only\","
         "\"modelInferenceTested\":false,\"keyboardInputTested\":false,\"physicalDeviceAcceptance\":false}\n",
         passed ? "true" : "false");
  return passed ? 0 : 1;
}
