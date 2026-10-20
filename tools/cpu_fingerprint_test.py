from __future__ import annotations

import pytest

from tools import cpu_fingerprint


@pytest.mark.parametrize(
    ("system", "original", "reordered", "changed"),
    [
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
