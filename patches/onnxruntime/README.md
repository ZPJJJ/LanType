# ORT 1.28.0 native startup candidate

This directory contains a source-level candidate for the CPU cache discovery
initialization failure observed in the signed LanType 1.1.1 APK on the API 35
ARM64 translation environment. It does not change the published APK by itself.
Physical ARM64 startup has not yet been accepted.

## Fixed inputs

- ONNX Runtime: `da9b5e364c465de65c49d91e696cd6485270757f` (`1.28.0`).
- cpuinfo: `4628dc060ce4e82345dc166bbac875609db4ff69`.
- Candidate: [pytorch/cpuinfo PR 457](https://github.com/pytorch/cpuinfo/pull/457),
  still open and unmerged when checked on 2026-11-18 (Asia/Shanghai).
- Production commits: `956614a1e93e1aca95b1cc03484647a187b199b4` and
  `bd8f30173a7d7f08842fdaf838fc7c02a86b92ea`.
- Production patch SHA-256:
  `6281246ef5bafdae6f64a9b1c4bbd64ddcd6b0b65a8150c9bd0343e3cfdf998b`.
- Original `src/arm/linux/init.c` SHA-256:
  `daaf6633d55c983e9b517d748d1fdf3df580c6c8bef03e4fd3811ba47f175e4f`.
- Patched file SHA-256:
  `94a7bd19139090a0568e173f80dea5e42ea1326d04e3eddf46554f5243e5229c`.

The patch preserves upstream attribution and changes only three blocks in
`src/arm/linux/init.c`. It reads the sysfs L2 size in the counting pass as the
population pass already does, and checks the allocated range before both L2
writes and their associated pointer assignments. The backport adapts hunk
locations and retains the frozen baseline's existing L3 behavior. It does not
claim to include all later cpuinfo changes.

## Review and acceptance scope

Independent read-only review found the count/population conditions consistent
for stable sysfs input and no blocking issue introduced by these three blocks.
If the topology changes between reads, bounded writes can leave missing L2
descriptors; this is not a complete atomic topology snapshot. Existing L3 and
cache geometry limitations remain outside this patch.

Only this production patch belongs in an Android build. No host mock filesystem,
test header adapter, sanitizer harness, or prior experimental executable is part
of the product or the native build workflow.

The controlled build must keep CPU, NNAPI, XNNPACK, static WebGPU/Dawn, the full
operator set, API 28 and the `VERS_1.28.0` ABI. A successful build or static ABI
check is not Android acceptance: normal loading, model and keyboard flows must
be exercised against the resulting binary before any release claim.

The original vendor CMake cache remains unavailable. LanType records its own
exact build inputs and toolchain; it does not claim bit-for-bit reproduction of
the previous vendor binary. The upstream cpuinfo BSD-2-Clause license and its
copyright notices continue to apply to this source.
