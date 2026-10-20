from __future__ import annotations

import shutil
import subprocess
from unittest import mock

import pytest

from tools import cpu_fingerprint


@pytest.mark.parametrize(
    ("system", "original", "reordered", "changed"),
    [
        (
            "win32",
            "target-cpu: skylake\ntarget-feature: +avx2\ntarget-feature: -avx512f\n",
            "target-feature: -avx512f\ntarget-feature: +avx2\ntarget-cpu: skylake\n",
            "target-cpu: skylake\ntarget-feature: -avx2\ntarget-feature: -avx512f\n",
        ),
        (
            "win32",
            "target-cpu: skylake\ntarget-feature: +avx2\n",
            "target-feature: +avx2\ntarget-cpu: skylake\n",
            "target-cpu: znver3\ntarget-feature: +avx2\n",
        ),
        (
            "linux",
            "vendor_id: GenuineIntel\nmodel: 85\nflags: avx avx2\ncpu MHz: 2400\n",
            "flags: avx2 avx\nmodel: 85\nvendor_id: GenuineIntel\nmodel: 85\ncpu MHz: 3000\n",
            "vendor_id: GenuineIntel\nmodel: 85\nflags: avx\n",
        ),
        (
            "darwin",
            "machdep.cpu.brand_string: Apple M1\nhw.optional.arm.FEAT_AES: 1\nhw.memsize: 100\n",
            "hw.memsize: 200\nhw.optional.arm.FEAT_AES: 1\nmachdep.cpu.brand_string: Apple M1\n",
            "machdep.cpu.brand_string: Apple M1\nhw.optional.arm.FEAT_AES: 0\n",
        ),
        (
            "darwin",
            "machdep.cpu.model: 85\nmachdep.cpu.features: AVX SSE\n",
            "machdep.cpu.features: SSE AVX\nmachdep.cpu.model: 85\n",
            "machdep.cpu.model: 86\nmachdep.cpu.features: AVX SSE\n",
        ),
    ],
)
def test_cache_compatibility(system: str, original: str, reordered: str, changed: str):
    original_fingerprint = cpu_fingerprint.fingerprint(original, system)
    assert len(original_fingerprint) == 64
    assert original_fingerprint == cpu_fingerprint.fingerprint(reordered, system)
    assert original_fingerprint != cpu_fingerprint.fingerprint(changed, system)


def test_missing_cpu_information():
    with pytest.raises(ValueError, match="No CPU identity"):
        _ = cpu_fingerprint.fingerprint("unrelated: 123\n\n", "linux")


def test_windows_native_cpu_detection():
    diagnostic = (
        'clang version 20.1.8\n"C:\\Program Files\\LLVM\\bin\\clang.exe" "-cc1" '
        + '"-target-cpu" "skylake" "-target-feature" "+avx2" '
        + '"-target-feature" "-avx512f" "-o" "-.obj"\n'
    )
    with (
        mock.patch.object(shutil, "which", autospec=True, return_value="clang.exe"),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=subprocess.CompletedProcess([], 0, stderr=diagnostic),
        ),
    ):
        assert cpu_fingerprint.windows_cpu_info() == (
            "target-cpu: skylake\ntarget-feature: +avx2\ntarget-feature: -avx512f"
        )


@pytest.mark.parametrize(
    ("diagnostic", "message"),
    [
        ('"-target-feature" "+avx2"', "did not report the native CPU"),
        ('"-target-cpu" "skylake"', "did not report native CPU features"),
    ],
)
def test_windows_requires_cpu_and_features(diagnostic: str, message: str):
    with (
        mock.patch.object(shutil, "which", autospec=True, return_value="clang.exe"),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=subprocess.CompletedProcess([], 0, stderr=diagnostic),
        ),
        pytest.raises(ValueError, match=message),
    ):
        _ = cpu_fingerprint.windows_cpu_info()
